# SPDX-License-Identifier: MIT
"""Offline qualification-runner tests. No serial port is opened."""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from capture import CaptureError
from qualify_audio import COUNTERS, Qualification, expectations, metrics, projected_notes


class Clock:
    def __init__(self):self.now=0
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


def expected(fixture="sine"):
    params=({"frequency":{"index":0,"minimum":20,"maximum":10000},"level":{"index":1,"minimum":0,"maximum":1}}
            if fixture=="sine" else {"level":{"index":0,"minimum":0,"maximum":1},"poly/level":{"index":1,"minimum":0,"maximum":1}})
    return {"board":"amoled","fixture":fixture,"firmware_elf_sha256":"a"*64,
            "module_source_sha256":"b"*64,"parameters":params}


class FakeAudioDevice:
    def __init__(self,fixture="sine",*,bad_pitch=False,bad_identity=False):
        self.fixture=fixture;self.frequency=440;self.level=0.2 if fixture=="sine" else 0.1
        self.volume=81;self.panic=False;self.ready=False;self.sustain=False
        self.note=False;self.velocity=100;self.pedal_held=False
        self.commands=[];self.capture_id=123;self.pcm=b"";self.capture_frames=0
        self.bad_pitch=bad_pitch;self.bad_identity=bad_identity;self.audio_frames=1000
        self.parameters={0:440,1:0.2} if fixture=="sine" else {0:0.1,1:0.1}

    def request(self,command):
        self.commands.append(command);words=command.split()
        if command=="status":
            self.audio_frames+=256
            return {"runtime":"rnbo-esp32s3-bringup","board":"Waveshare AMOLED 1.8 V2",
                    "source":"static-rnbo","rate":44100,"block_frames":256,"channels":1,
                    "frames":self.audio_frames,"firmware_elf_sha256":("c" if self.bad_identity else "a")*64,
                    "module_source_sha256":"b"*64,"volume":self.volume,"panic":self.panic,
                    "allocation_fault":False,"rebuilding":False,"ready_to_resume":self.ready,
                    "reconstruction_failed":False,"audio_stack_free":4000,"render_us":1800,"peak_us":2300,
                    **dict.fromkeys(COUNTERS,0)}
        if words[0]=="volume":
            self.volume=int(words[1]);return {"volume":self.volume,"accepted":True}
        if words[0] in ("param","normalized"):
            index=int(words[1]);value=float(words[2])
            if self.fixture=="sine" and index==0:
                self.frequency=20+value*9980 if words[0]=="normalized" else value
                self.parameters[index]=self.frequency
            else:self.level=value;self.parameters[index]=value
            return {"queued":True}
        if command=="panic":
            self.panic=True;self.ready=True;self.note=False;self.pedal_held=False;self.sustain=False
            return {"panic":True}
        if command=="resume":
            self.panic=False;self.ready=False;return {"resume_requested":True}
        if words[0]=="midi":
            status,a,b=map(int,words[1:]);kind=status&0xf0
            if kind==0x90 and b:
                self.note=True;self.pedal_held=False;self.frequency=440*2**((a-69)/12);self.velocity=b
            elif kind==0x80 or (kind==0x90 and not b):
                self.pedal_held=self.sustain;self.note=self.sustain
            elif kind==0xb0 and a==64:
                self.sustain=b>=64
                if not self.sustain and self.pedal_held:self.note=False;self.pedal_held=False
            elif kind==0xb0 and a==123:self.note=False
            return {"queued":True}
        if words[0]=="capture":
            self.capture_frames=int(words[1]);self.capture_id+=1
            amplitude=self.level*0.5*self.volume/100
            if self.fixture=="midi4":amplitude*=self.velocity/127*0.8
            if self.panic or (self.fixture=="midi4" and not self.note):amplitude=0
            hz=self.frequency*(1.1 if self.bad_pitch else 1)
            self.pcm=b"".join(struct.pack("<h",round(amplitude*32767*math.sin(2*math.pi*hz*i/44100))) for i in range(self.capture_frames))
            return {"recording":True,"frames":self.capture_frames,"capture_id":self.capture_id}
        if command=="capinfo":
            return {"state":2,"frames":self.capture_frames,"requested":self.capture_frames,
                    "channels":1,"rate":44100,"bytes":len(self.pcm),"capture_id":self.capture_id,"max_chunk_bytes":1024}
        if words[0]=="capread":
            recording,offset,count=map(int,words[1:]);assert recording==self.capture_id
            return {"capture_id":self.capture_id,"offset":offset,"data":self.pcm[offset:offset+count].hex()}
        raise AssertionError(command)


class QualificationTests(unittest.TestCase):
    def run_fixture(self,device,fixture="sine"):
        clock=Clock();temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        out=Path(temporary.name)/"run"
        restored={"frequency":440,"level":0.2} if fixture=="sine" else {"level":0.1,"poly/level":0.1}
        report=Qualification(device,expected(fixture),out,restored,idle_midi_baseline=fixture=="midi4",
                             clock=clock,sleep=clock.sleep).run()
        self.assertTrue((out/"qualification.json").is_file())
        return report

    def test_sine_volume_pitch_panic_resume_and_restore(self):
        device=FakeAudioDevice()
        report=self.run_fixture(device)
        self.assertEqual(report["result"],"passed",report.get("error"))
        self.assertEqual(len(report["cases"]),8)
        self.assertEqual(device.volume,81)
        self.assertEqual(device.frequency,440)
        self.assertEqual(device.level,0.2)
        self.assertFalse(device.panic)
        self.assertEqual(next(c for c in device.commands if c.startswith("volume")),"volume 25")
        self.assertFalse(report["cpu_overrun_absence_proven"])
        self.assertFalse(report["external_audio_or_listening_verified"])
        self.assertFalse(report["restoration"]["parameter_readback_available"])

    def test_midi4_note_release_sustain_panic_recovery(self):
        device=FakeAudioDevice("midi4")
        # This original single-note fake tests lifecycle/sustain only. The new
        # true-polyphony path is checked by projection-unit tests and target
        # execution, rather than teaching the fake a second voice allocator.
        with mock.patch.object(Qualification,"run_midi4_chord"):
            report=self.run_fixture(device,"midi4")
        self.assertEqual(report["result"],"passed",report.get("error"))
        self.assertTrue(any(case["name"]=="sustain-held" for case in report["cases"]))
        self.assertFalse(device.note)
        self.assertFalse(device.sustain)
        self.assertEqual(device.volume,81)

    def test_failed_pitch_keeps_evidence_and_restores_controls(self):
        device=FakeAudioDevice(bad_pitch=True)
        report=self.run_fixture(device)
        self.assertEqual(report["result"],"failed")
        self.assertIn("measured pitch",report["error"])
        self.assertEqual(report["restoration"]["result"],"restored")
        self.assertEqual((device.volume,device.frequency,device.level),(81,440,0.2))

    def test_wrong_firmware_identity_never_receives_mutations_or_restoration(self):
        device=FakeAudioDevice(bad_identity=True)
        report=self.run_fixture(device)
        self.assertEqual(report["result"],"failed")
        self.assertEqual(device.commands,["status"])
        self.assertEqual(report["restoration"]["result"],"not-needed-no-controls-sent")

    def test_original_values_required_before_any_device_request(self):
        with tempfile.TemporaryDirectory() as directory:
            device=FakeAudioDevice()
            with self.assertRaises(CaptureError):
                Qualification(device,expected(),Path(directory)/"run",{}).run()
            self.assertEqual(device.commands,[])

    def test_boot_default_zero_telemetry_is_not_used_as_original_volume(self):
        class BootingDevice(FakeAudioDevice):
            first=True
            def request(self,command):
                response=super().request(command)
                if command=="status" and self.first:
                    self.first=False
                    response.update(frames=0,volume=0,audio_stack_free=0)
                return response
        device=BootingDevice()
        report=self.run_fixture(device)
        self.assertEqual(report["result"],"passed",report.get("error"))
        self.assertEqual(report["restoration"]["original_volume"],81)
        self.assertEqual(device.volume,81)

    def test_original_panicked_state_is_restored_after_testing(self):
        device=FakeAudioDevice();device.panic=True;device.ready=True
        report=self.run_fixture(device)
        self.assertEqual(report["result"],"passed",report.get("error"))
        self.assertTrue(device.panic)
        self.assertTrue(device.ready)

    def test_metric_pitch_and_silence_are_independent_of_fixture_driver(self):
        pcm=b"".join(struct.pack("<h",round(3276*math.sin(2*math.pi*440*i/44100))) for i in range(44100))
        values=metrics(pcm,1)[0]
        self.assertAlmostEqual(values["positive_crossing_frequency_hz"],440,places=3)
        self.assertEqual(metrics(bytes(88200),1)[0]["nonzero_samples"],0)


class ProjectionTests(unittest.TestCase):
    amplitude=0.007874015748031496
    def signal(self,notes,phase=0.37):
        frequencies=[440*2**((note-69)/12) for note in notes]
        return b"".join(struct.pack("<h",round(32767*self.amplitude*sum(math.sin(2*math.pi*hz*i/44100+phase*(j+1)) for j,hz in enumerate(frequencies)))) for i in range(44100))

    def test_single_noninteger_pitch_projection_preserves_amplitude(self):
        result=projected_notes(self.signal([60]),1,[60],[74],self.amplitude)
        self.assertLess(abs(result[0]["partials"][0]["amplitude"]-self.amplitude),self.amplitude*0.01)

    def test_four_simultaneous_partials_each_measured(self):
        result=projected_notes(self.signal([60,64,67,71]),1,[60,64,67,71],[74],self.amplitude)
        self.assertEqual(sum(p["expected_present"] for p in result[0]["partials"]),4)

    def test_one_released_partial_absent_while_three_remain(self):
        projected_notes(self.signal([64,67,71]),1,[64,67,71],[60,74],self.amplitude)

    def test_fifth_voice_present_and_oldest_absent(self):
        projected_notes(self.signal([64,67,71,74]),1,[64,67,71,74],[60],self.amplitude)

    def test_missing_voice_is_a_failure(self):
        with self.assertRaisesRegex(CaptureError,"missing or has wrong amplitude"):
            projected_notes(self.signal([60,64,67]),1,[60,64,67,71],[74],self.amplitude)

    def test_stolen_voice_that_keeps_sounding_is_a_failure(self):
        with self.assertRaisesRegex(CaptureError,"still present"):
            projected_notes(self.signal([60,64,67,71,74]),1,[64,67,71,74],[60],self.amplitude)


if __name__=="__main__":unittest.main()
