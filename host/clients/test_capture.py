# SPDX-License-Identifier: MIT
"""Protocol/capture checks use fake transports, without claiming board results."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import types
import tempfile
import unittest
from unittest import mock
import wave

from capture import (BOARDS, CaptureError, JsonLineTransport, MAX_REPLY_BYTES,
                     decode_response, record, save)
from capture import open_serial


class Clock:
    def __init__(self): self.time = 0.0
    def __call__(self): return self.time
    def sleep(self, seconds): self.time += seconds


class FakeDevice:
    def __init__(self, board="amoled", *, maximum=1024, mutate=None, incomplete=False):
        self.board = board
        self.channels = BOARDS[board][1]
        self.maximum = maximum
        self.mutate = mutate
        self.incomplete = incomplete
        self.commands = []
        self.frames = 0
        self.id = 123456
        self.reads = 0
        self.statuses = 0
        self.pcm = b""

    def request(self, command):
        self.commands.append(command)
        words = command.split()
        if command == "status":
            self.statuses += 1
            response = {"runtime":"rnbo-esp32s3-bringup", "board":BOARDS[self.board][0],
                        "source":"static-rnbo", "rate":44100, "block_frames":256,
                        "channels":self.channels, "frames":self.statuses * 100000,
                        "volume":25, "panic":False, "nonfinite":0,
                        "firmware_elf_sha256":"a"*64, "module_source_sha256":"b"*64}
        elif words[0] == "capture":
            self.frames = int(words[1])
            self.pcm = b"".join(struct.pack("<h", (i % 1000)-500) for i in range(self.frames*self.channels))
            response = {"recording":True, "frames":self.frames, "capture_id":self.id}
        elif command == "capinfo":
            response = {"state":1 if self.incomplete else 2,
                        "frames":0 if self.incomplete else self.frames,
                        "requested":self.frames, "channels":self.channels, "rate":44100,
                        "bytes":self.frames*self.channels*2, "capture_id":self.id,
                        "max_chunk_bytes":self.maximum}
        elif words[0] == "capread":
            recording, offset, count = map(int, words[1:])
            assert recording == self.id and 1 <= count <= self.maximum
            assert 0 <= offset <= len(self.pcm) and offset+count <= len(self.pcm)
            self.reads += 1
            response = {"capture_id":self.id, "offset":offset, "count":count,
                        "data":self.pcm[offset:offset+count].hex()}
        else:
            raise AssertionError(f"Unexpected command {command}")
        if self.mutate:
            self.mutate(command, response, self)
        return response


class FakeStream:
    def __init__(self, data: bytes, clock: Clock):
        self.data = bytearray(data)
        self.writes = []
        self.clock = clock
    @property
    def in_waiting(self): return len(self.data)
    def read(self, count):
        chunk = bytes(self.data[:count]);del self.data[:count]
        if not chunk:self.clock.sleep(0.01)
        return chunk
    def write(self, data):self.writes.append(data);return len(data)


class CaptureTests(unittest.TestCase):
    def capture(self, device, **kwargs):
        clock = Clock()
        return record(device, frames=kwargs.pop("frames", 257), clock=clock,
                      sleep=clock.sleep, **kwargs)

    def test_primary_mono_wav_and_proof_match_complete_pcm(self):
        device = FakeDevice(maximum=128)
        result = self.capture(device)
        self.assertEqual(result.pcm, device.pcm)
        self.assertEqual(len(result.pcm), 257*2)
        self.assertEqual(result.metadata["read_chunks"], 5)
        self.assertEqual(result.metadata["read_chunk_bytes"], 128)
        self.assertEqual(device.commands[-2:], ["capinfo", "status"])
        self.assertEqual(result.metadata["status_before"]["volume"], 25)
        with tempfile.TemporaryDirectory() as directory:
            output, sidecar = save(result, Path(directory)/"mono.wav", serial_port="fake-test-only")
            with wave.open(str(output), "rb") as audio:
                self.assertEqual((audio.getnchannels(),audio.getframerate(),audio.getnframes()), (1,44100,257))
                self.assertEqual(audio.readframes(257), device.pcm)
            proof = json.loads(sidecar.read_text())
            self.assertEqual(proof["wav_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(proof["pcm_sha256"], hashlib.sha256(device.pcm).hexdigest())
            self.assertFalse(proof["external_audio_verified"])
            with self.assertRaises(CaptureError):save(result, output)

    def test_stereo_xiao_length_channels_and_partial_last_chunk(self):
        device = FakeDevice("xiao")
        result = self.capture(device, board="xiao")
        self.assertEqual(result.metadata["channels"], 2)
        self.assertEqual(len(result.pcm), 1028)
        self.assertEqual(result.metadata["read_chunks"], 2)
        self.assertTrue(any(command.endswith(" 1024 4") for command in device.commands))

    def test_wrong_runtime_or_board_rejected_before_recording(self):
        for field, value in (("runtime","synthdef"), ("board","other board"), ("channels",2), ("rate",48000)):
            with self.subTest(field=field):
                device = FakeDevice(mutate=lambda c,r,d: r.update({field:value}) if c=="status" else None)
                with self.assertRaises(CaptureError):self.capture(device)
                self.assertEqual(device.commands,["status"])

    def test_changed_id_rejected_during_recording_and_download(self):
        for command in ("capinfo","capread"):
            with self.subTest(command=command):
                device = FakeDevice(mutate=lambda c,r,d: r.update(capture_id=d.id+1) if c.startswith(command) else None)
                with self.assertRaisesRegex(CaptureError,"ID changed"):self.capture(device)

    def test_wrong_offset_count_truncated_or_nonhex_chunk_rejected(self):
        for changed in ({"offset":1},{"count":1},{"data":"00"},{"data":"g"*2048}):
            with self.subTest(changed=changed):
                device = FakeDevice("xiao", mutate=lambda c,r,d: r.update(changed) if c.startswith("capread") else None)
                with self.assertRaises(CaptureError):self.capture(device,board="xiao")

    def test_unbounded_or_missing_negotiation_rejected_without_data_reads(self):
        for maximum in (0,1025,2**63,None,True):
            with self.subTest(maximum=maximum):
                device = FakeDevice(maximum=maximum)
                with self.assertRaises(CaptureError):self.capture(device)
                self.assertEqual(device.reads,0)

    def test_completed_flag_requires_exact_frames_and_bytes(self):
        for changed in ({"frames":256},{"bytes":2**63},{"requested":2**63}):
            with self.subTest(changed=changed):
                device = FakeDevice(mutate=lambda c,r,d:r.update(changed) if c=="capinfo" else None)
                with self.assertRaises(CaptureError):self.capture(device)
                self.assertEqual(device.reads,0)

    def test_never_complete_times_out(self):
        device = FakeDevice(incomplete=True)
        with self.assertRaisesRegex(CaptureError,"did not complete"):
            self.capture(device,recording_timeout=0.1)
        self.assertLess(len(device.commands),10)
        self.assertEqual(device.reads,0)

    def test_final_identity_or_recording_change_rejects_result(self):
        def changed_status(command,response,device):
            if command=="status" and device.statuses>1:response["module_source_sha256"]="c"*64
        with self.assertRaisesRegex(CaptureError,"identity/configuration changed"):
            self.capture(FakeDevice(mutate=changed_status))
        def changed_recording(command,response,device):
            if command=="capinfo" and device.reads:response["capture_id"]+=1
        with self.assertRaisesRegex(CaptureError,"ID changed"):
            self.capture(FakeDevice(mutate=changed_recording))

    def test_locally_invalid_frame_limit_sends_no_commands(self):
        for frames in (0,44101,2**63,True):
            device = FakeDevice()
            with self.assertRaises(CaptureError):self.capture(device,frames=frames)
            self.assertEqual(device.commands,[])

    def test_missing_digests_remain_explicitly_unknown(self):
        def remove(command,response,device):
            response.pop("firmware_elf_sha256",None);response.pop("module_source_sha256",None)
        result = self.capture(FakeDevice(mutate=remove))
        self.assertIsNone(result.metadata["firmware_elf_sha256"])
        self.assertEqual(len(result.metadata["identity_limitations"]),2)

    def test_engine_neutral_firmware_has_no_rnbo_module_digest(self):
        def tone(command,response,device):
            if command=="status":response.update(source="engine-neutral-stereo-tone",module_source_sha256="none")
        result = self.capture(FakeDevice(mutate=tone))
        self.assertIsNone(result.metadata["module_source_sha256"])
        self.assertEqual(result.metadata["module_source_identity_state"],"not-applicable-engine-neutral")


class TransportTests(unittest.TestCase):
    def test_plain_boot_logs_are_bounded_and_json_response_decodes(self):
        clock = Clock();stream = FakeStream(b"I (123) audio: ready\n{\"ok\":true}\n",clock)
        self.assertEqual(JsonLineTransport(stream,clock=clock).request("status"),{"ok":True})
        self.assertEqual(stream.writes,[b"status\n"])

    def test_missing_response_or_unterminated_response_times_out(self):
        for data in (b"",b'{"partial":true}'):
            clock = Clock();stream = FakeStream(data,clock)
            with self.assertRaisesRegex(CaptureError,"Timed out"):
                JsonLineTransport(stream,timeout=0.1,clock=clock).request("status")

    def test_oversized_or_malformed_json_rejected(self):
        for data in (b"x"*(MAX_REPLY_BYTES+1),b'{bad json}\n',b'{"a":1,"a":2}\n',b'{"a":1e999}\n'):
            clock = Clock();stream = FakeStream(data,clock)
            with self.assertRaises(CaptureError):JsonLineTransport(stream,clock=clock).request("status")

    def test_device_error_is_not_a_successful_response(self):
        with self.assertRaisesRegex(CaptureError,"Device rejected"):
            decode_response(b'{"error":"invalid command or capture state"}')

    def test_serial_connection_is_exclusive_with_control_intent_set_before_open(self):
        class Serial:
            def __init__(self, **kwargs):self.kwargs=kwargs;self.opened=False
            def open(self):
                self.opened=True
                assert self.dtr is True and self.rts is False and self.port=="fake-port"
            def close(self):pass
        with mock.patch.dict("sys.modules", {"serial":types.SimpleNamespace(Serial=Serial)}):
            stream = open_serial("fake-port",115200,2)
        self.assertTrue(stream.opened)
        self.assertIs(stream.dtr,False)
        self.assertIsNone(stream.kwargs["port"])
        self.assertTrue(stream.kwargs["exclusive"])
        self.assertEqual(stream.kwargs["timeout"],0.05)

    def test_pyserial_is_optional_with_a_clear_missing_dependency_error(self):
        with mock.patch.dict("sys.modules", {"serial":None}):
            with self.assertRaisesRegex(CaptureError,"requires pyserial"):
                open_serial("fake-port",115200,2)


if __name__ == "__main__":unittest.main()
