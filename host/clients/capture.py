#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record bounded post-volume PCM from the RNBO ESP32-S3 bring-up serial shell.

This client owns one serial connection and sends only status/capture commands.
It does not discover, flash, upload, or change audio controls. A successful
download proves buffer capture, not electrical codec/DAC output or listening.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import tempfile
import threading
import time
from typing import Callable, Protocol
import wave

RUNTIME = "rnbo-esp32s3-bringup"
RATE = 44100
MAX_FRAMES = 44100
MAX_CHUNK_BYTES = 1024
MAX_REPLY_BYTES = 4096
MAX_NOISE_BYTES = 65536
BOARDS = {"amoled": ("Waveshare AMOLED 1.8 V2", 1), "xiao": ("XIAO ESP32-S3", 2)}


class CaptureError(RuntimeError):
    pass


class Transport(Protocol):
    def request(self, command: str) -> dict: ...


def integer(value: object, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CaptureError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def positive_timeout(value: float, name: str) -> float:
    if not math.isfinite(value) or not 0 < value <= 120:
        raise CaptureError(f"{name} must be greater than zero and at most 120 seconds")
    return value


def decode_response(line: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CaptureError(f"Duplicate response key: {key}")
            result[key] = value
        return result
    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise CaptureError("Non-finite JSON response")
        return parsed
    try:
        response = json.loads(line, object_pairs_hook=pairs, parse_float=finite_float,
                              parse_constant=lambda _: (_ for _ in ()).throw(CaptureError("Non-finite JSON response")))
    except (ValueError, UnicodeError) as exc:
        raise CaptureError("Malformed JSON response") from exc
    if not isinstance(response, dict):
        raise CaptureError("Expected a JSON object response")
    if "error" in response:
        raise CaptureError(f"Device rejected capture command: {response['error']!r}")
    return response


class JsonLineTransport:
    """One outstanding request at a time, with bounded log/line consumption.

    The supplied stream is already open and must have read/write and in_waiting.
    Its read/write timeouts must also be finite. Plain ESP-IDF log lines may be
    interleaved; malformed or unexpected JSON is never silently skipped.
    """
    def __init__(self, stream, timeout: float = 2.0, *, clock: Callable[[], float] = time.monotonic):
        self.stream = stream
        self.timeout = positive_timeout(timeout, "Command timeout")
        self.clock = clock
        self.buffer = bytearray()
        self.lock = threading.Lock()

    def request(self, command: str) -> dict:
        if not command or len(command) > 120 or any(c in command for c in "\r\n\0"):
            raise CaptureError("Invalid serial command")
        try:
            payload = (command + "\n").encode("ascii")
        except UnicodeError as exc:
            raise CaptureError("Serial command must be ASCII") from exc
        with self.lock:
            deadline = self.clock() + self.timeout
            if self.stream.write(payload) != len(payload):
                raise CaptureError("Incomplete serial command write")
            consumed = 0
            while self.clock() < deadline:
                while b"\n" in self.buffer:
                    end = self.buffer.index(10)
                    line = bytes(self.buffer[:end]).strip()
                    del self.buffer[:end + 1]
                    consumed += end + 1
                    if consumed > MAX_NOISE_BYTES or end > MAX_REPLY_BYTES:
                        raise CaptureError("Serial response/log limit exceeded")
                    if line.startswith((b"{", b"[")):
                        return decode_response(line)
                if len(self.buffer) > MAX_REPLY_BYTES:
                    raise CaptureError("Serial response line is too large")
                waiting = max(0, int(self.stream.in_waiting))
                chunk = self.stream.read(min(waiting, MAX_REPLY_BYTES) if waiting else 1)
                self.buffer.extend(chunk)
            raise CaptureError(f"Timed out waiting for response to {command.split()[0]}")


def validate_status(status: dict, board: str) -> dict:
    expected_board, channels = BOARDS[board]
    if status.get("runtime") != RUNTIME:
        raise CaptureError("Device runtime is not rnbo-esp32s3-bringup")
    if status.get("board") != expected_board:
        raise CaptureError(f"Expected board {expected_board!r}, received {status.get('board')!r}")
    if integer(status.get("rate"), "Status rate", RATE, RATE) != RATE:
        raise CaptureError("Unexpected sample rate")
    integer(status.get("channels"), "Status channels", channels, channels)
    integer(status.get("block_frames"), "Status block_frames", 256, 256)
    source = status.get("source")
    if not isinstance(source, str) or not source or len(source.encode()) > 128 or "\0" in source:
        raise CaptureError("Status source identity is missing or malformed")
    for field in ("firmware_elf_sha256", "module_source_sha256"):
        value = status.get(field)
        if field == "module_source_sha256" and value == "none" and source == "engine-neutral-stereo-tone":
            continue
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value)):
            raise CaptureError(f"Malformed advertised {field}")
    if "frames" in status:
        integer(status["frames"], "Status frames", 0, 0xffffffffffffffff)
    return status


def validate_info(info: dict, recording_id: int, frames: int, channels: int, previous_frames: int = 0) -> tuple[int, int, int]:
    if integer(info.get("capture_id"), "Capture ID", 1, 0xffffffff) != recording_id:
        raise CaptureError("Recording ID changed during capture")
    integer(info.get("requested"), "Requested capture frames", frames, frames)
    integer(info.get("channels"), "Capture channels", channels, channels)
    integer(info.get("rate"), "Capture rate", RATE, RATE)
    integer(info.get("bytes"), "Capture bytes", frames * channels * 2, frames * channels * 2)
    state = integer(info.get("state"), "Capture state", 1, 2)
    completed = integer(info.get("frames"), "Completed capture frames", previous_frames, frames)
    maximum = integer(info.get("max_chunk_bytes"), "Negotiated maximum chunk bytes", 1, MAX_CHUNK_BYTES)
    if state == 2 and completed != frames:
        raise CaptureError("Capture marked complete before all requested frames were recorded")
    return state, completed, maximum


@dataclass(frozen=True)
class CaptureResult:
    pcm: bytes
    metadata: dict


def record(transport: Transport, *, board: str = "amoled", frames: int = MAX_FRAMES,
           chunk_bytes: int = MAX_CHUNK_BYTES, recording_timeout: float = 5.0,
           transfer_timeout: float = 60.0, poll_interval: float = 0.025,
           clock: Callable[[], float] = time.monotonic,
           sleep: Callable[[float], None] = time.sleep) -> CaptureResult:
    if board not in BOARDS:
        raise CaptureError("Board must be amoled or xiao")
    integer(frames, "Requested frames", 1, MAX_FRAMES)
    integer(chunk_bytes, "Chunk bytes", 1, MAX_CHUNK_BYTES)
    positive_timeout(recording_timeout, "Recording timeout")
    positive_timeout(transfer_timeout, "Transfer timeout")
    if not math.isfinite(poll_interval) or not 0.001 <= poll_interval <= 1:
        raise CaptureError("Poll interval must be between 0.001 and 1 second")
    status_before = validate_status(transport.request("status"), board)
    channels = BOARDS[board][1]
    started = transport.request(f"capture {frames}")
    if started.get("recording") is not True:
        raise CaptureError("Device did not acknowledge recording start")
    integer(started.get("frames"), "Acknowledged frames", frames, frames)
    recording_id = integer(started.get("capture_id"), "Recording ID", 1, 0xffffffff)
    deadline = clock() + recording_timeout
    completed = 0
    while True:
        if clock() >= deadline:
            raise CaptureError("Recording did not complete before the deadline")
        info = transport.request("capinfo")
        state, completed, maximum = validate_info(info, recording_id, frames, channels, completed)
        if state == 2:
            break
        sleep(min(poll_interval, max(0, deadline - clock())))
    complete_info = dict(info)
    negotiated_chunk = min(chunk_bytes, maximum)
    # Allocation is bounded by locally validated frames/channels, never by a
    # device-advertised byte count. No audio data is committed until verified.
    pcm = bytearray()
    total_bytes = frames * channels * 2
    deadline = clock() + transfer_timeout
    chunks = 0
    while len(pcm) < total_bytes:
        if clock() >= deadline:
            raise CaptureError("Capture download did not complete before the deadline")
        offset = len(pcm)
        count = min(negotiated_chunk, total_bytes - offset)
        response = transport.request(f"capread {recording_id} {offset} {count}")
        if integer(response.get("capture_id"), "Chunk recording ID", 1, 0xffffffff) != recording_id:
            raise CaptureError("Recording ID changed while downloading PCM")
        integer(response.get("offset"), "Chunk offset", offset, offset)
        if "count" in response:
            integer(response["count"], "Chunk count", count, count)
        data = response.get("data")
        if not isinstance(data, str) or len(data) != count * 2 or not re.fullmatch(r"[0-9a-fA-F]+", data):
            raise CaptureError("Chunk data is not the exact requested length of hexadecimal PCM")
        pcm.extend(bytes.fromhex(data))
        chunks += 1
    final_info = transport.request("capinfo")
    final_state, _, final_maximum = validate_info(final_info, recording_id, frames, channels, frames)
    if final_state != 2 or final_maximum != maximum:
        raise CaptureError("Recording changed during download")
    status_after = validate_status(transport.request("status"), board)
    for field in ("runtime", "board", "source", "rate", "block_frames", "channels", "device_id", "firmware_elf_sha256", "module_source_sha256"):
        if status_after.get(field) != status_before.get(field):
            raise CaptureError(f"Device identity/configuration changed during capture: {field}")
    if "frames" in status_before and status_after.get("frames", 0) < status_before["frames"]:
        raise CaptureError("Device audio clock restarted during capture")
    metadata = {"format": "rnbo-esp32s3-pcm-capture-evidence", "format_version": 1,
                "evidence_kind": "device-post-volume-pcm-buffer", "runtime": RUNTIME,
                "board": BOARDS[board][0], "source": status_before["source"],
                "sample_rate": RATE, "channels": channels, "sample_format": "pcm_s16le",
                "frames": frames, "pcm_bytes": total_bytes, "capture_id": recording_id,
                "max_chunk_bytes": maximum, "read_chunk_bytes": negotiated_chunk, "read_chunks": chunks,
                "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
                "status_before": status_before, "status_after": status_after,
                "capture_complete": complete_info, "capture_after_download": final_info,
                "firmware_elf_sha256": status_before.get("firmware_elf_sha256"),
                "module_source_sha256": status_before.get("module_source_sha256") if status_before.get("module_source_sha256") != "none" else None,
                "module_source_identity_state": "not-applicable-engine-neutral" if status_before.get("module_source_sha256") == "none" else ("advertised" if status_before.get("module_source_sha256") else "unavailable"),
                "identity_limitations": [f"{label} digest not advertised" for label, key in
                                         (("Firmware ELF", "firmware_elf_sha256"), ("Module source tree", "module_source_sha256"))
                                         if status_before.get(key) is None],
                "external_audio_verified": False,
                "capture_tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "host_python": platform.python_version(),
                "recorded_at_utc": datetime.now(timezone.utc).isoformat()}
    return CaptureResult(bytes(pcm), metadata)


def save(result: CaptureResult, output: Path, *, serial_port: str | None = None) -> tuple[Path, Path]:
    if output.is_symlink() or output.with_suffix(output.suffix + ".json").is_symlink():
        raise CaptureError("Output and evidence sidecar must not be symbolic links")
    output = output.resolve()
    if output.suffix.lower() != ".wav":
        raise CaptureError("Output must have a .wav extension")
    sidecar = output.with_suffix(output.suffix + ".json")
    if output.exists() or sidecar.exists():
        raise CaptureError("Output or evidence sidecar already exists; choose a new filename")
    frames = integer(result.metadata.get("frames"), "Evidence frames", 1, MAX_FRAMES)
    channels = integer(result.metadata.get("channels"), "Evidence channels", 1, 2)
    if len(result.pcm) != frames * channels * 2:
        raise CaptureError("PCM byte length does not match evidence frames/channels")
    integer(result.metadata.get("sample_rate"), "Evidence sample rate", RATE, RATE)
    if result.metadata.get("pcm_sha256") != hashlib.sha256(result.pcm).hexdigest():
        raise CaptureError("PCM bytes changed after the capture was verified")
    memory = io.BytesIO()
    with wave.open(memory, "wb") as audio:
        audio.setnchannels(channels);audio.setsampwidth(2);audio.setframerate(RATE)
        audio.writeframes(result.pcm)
    wav_data = memory.getvalue()
    metadata = dict(result.metadata)
    metadata["wav_sha256"] = hashlib.sha256(wav_data).hexdigest()
    metadata["wav_file"] = output.name
    metadata["serial_port"] = serial_port
    encoded = (json.dumps(metadata, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = []
    created = []
    try:
        for final, data in ((output, wav_data), (sidecar, encoded)):
            with tempfile.NamedTemporaryFile(prefix=".capture-", dir=output.parent, delete=False) as stream:
                temporary.append(Path(stream.name))
                stream.write(data);stream.flush();os.fsync(stream.fileno())
            # An exclusive link makes each complete file visible atomically and
            # refuses to replace a destination created by another session.
            os.link(temporary[-1], final)
            created.append(final)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
    return output, sidecar


def open_serial(port: str, baud: int, timeout: float):
    positive_timeout(timeout,"Command timeout")
    try:
        import serial
    except ImportError as exc:
        raise CaptureError("Serial capture requires pyserial in the Python environment used for this command") from exc
    stream = serial.Serial(port=None, baudrate=baud, timeout=min(timeout, 0.05),
                           write_timeout=timeout, exclusive=True)
    # Verified on the primary AMOLED V2/macOS USB connection: starting with
    # false/false caused a reset while pyserial applied the lines separately.
    # Set true/false before open, then release DTR after open. Other host/board
    # combinations still require their own reconnect qualification.
    stream.dtr=True;stream.rts=False;stream.port=port
    try:
        stream.open()
        stream.dtr=False
    except BaseException:
        stream.close()
        raise
    return stream


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Exact serial device path; close other serial clients first")
    parser.add_argument("--board", choices=tuple(BOARDS), default="amoled")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frames", type=int, default=MAX_FRAMES)
    parser.add_argument("--chunk-bytes", type=int, default=MAX_CHUNK_BYTES)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--command-timeout", type=float, default=2.0)
    parser.add_argument("--recording-timeout", type=float, default=5.0)
    parser.add_argument("--transfer-timeout", type=float, default=60.0)
    args = parser.parse_args()
    stream = None
    try:
        integer(args.frames, "Frames", 1, MAX_FRAMES)
        integer(args.chunk_bytes, "Chunk bytes", 1, MAX_CHUNK_BYTES)
        integer(args.baud, "Baud rate", 1200, 4000000)
        positive_timeout(args.command_timeout, "Command timeout")
        positive_timeout(args.recording_timeout, "Recording timeout")
        positive_timeout(args.transfer_timeout, "Transfer timeout")
        sidecar = args.output.with_suffix(args.output.suffix+".json")
        if args.output.suffix.lower() != ".wav" or args.output.exists() or sidecar.exists() or args.output.is_symlink() or sidecar.is_symlink():
            raise CaptureError("Choose a new .wav output filename and unused sidecar filename")
        stream = open_serial(args.port, args.baud, args.command_timeout)
        result = record(JsonLineTransport(stream, args.command_timeout), board=args.board, frames=args.frames,
                        chunk_bytes=args.chunk_bytes, recording_timeout=args.recording_timeout,
                        transfer_timeout=args.transfer_timeout)
        output, sidecar = save(result, args.output, serial_port=args.port)
    except (CaptureError, OSError, ValueError) as exc:
        parser.exit(1, f"Capture failed: {exc}\n")
    finally:
        if stream is not None:
            stream.close()
    print(json.dumps({"wav":str(output), "evidence":str(sidecar), "frames":args.frames,
                      "channels":BOARDS[args.board][1], "external_audio_verified":False}))


if __name__ == "__main__":
    main()
