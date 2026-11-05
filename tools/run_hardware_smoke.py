#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Flash one XIAO smoke app, record its batch, and leave that app installed.

DONE means completion, including numerical CASE failures. There is deliberately
no restore, erase, bootloader write, or assumption about the previously run app.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_hardware_test as hardware

sha = hardware.sha
artifacts = hardware.artifacts
device_identity = hardware.device_identity
MAX_SERIAL_BYTES = 4 * 1024 * 1024
FAULTS = (b"RNBO_SMOKE FAULT", b": FAIL ", b"Guru Meditation", b"assert failed",
          b"Assertion failed", b"abort() was called", b"Stack smashing",
          b"Brownout detector")


def collect_serial(connection, expected_elf, timeout, captured, case_lines, *, complete_fault_line=False):
    """Accept only complete, firmware-bound DONE; faults take precedence."""
    deadline = time.monotonic() + timeout
    pending = bytearray()
    done = None
    while time.monotonic() < deadline:
        chunk = connection.read(min(max(1, connection.in_waiting), 65536))
        captured.extend(chunk)
        pending.extend(chunk)
        if len(captured) > MAX_SERIAL_BYTES:
            raise RuntimeError("Smoke serial output limit exceeded")
        # Include partial fault lines, including a fault following DONE in this read.
        fault = any(marker in pending for marker in FAULTS)
        if fault and complete_fault_line:
            first=min(pending.find(marker)for marker in FAULTS if marker in pending)
            if b"\n" not in pending[first:]:
                # The serial connection has a bounded read timeout. Preserve the
                # complete diagnostic instead of stopping midway through FAIL.
                tail=connection.read_until(b"\n",65536)
                captured.extend(tail);pending.extend(tail)
                if len(captured)>MAX_SERIAL_BYTES:raise RuntimeError("Smoke serial output limit exceeded")
        while b"\n" in pending:
            raw, _, remainder = pending.partition(b"\n")
            pending[:] = remainder
            if len(raw) > 65536:
                raise RuntimeError("Smoke serial line limit exceeded")
            line = raw.decode("utf-8", "replace").rstrip("\r")
            if line.startswith("RNBO_SMOKE CASE "):
                case_lines.append(line)
            if line.startswith("RNBO_SMOKE DONE "):
                fields = line.split()[2:]
                pairs = [item.split("=", 1) for item in fields]
                if (done is not None or any(not 32 <= byte <= 126 for byte in raw.rstrip(b"\r"))
                        or any(len(pair) != 2 or not re.fullmatch(r"[a-z][a-z0-9_]*", pair[0]) or not pair[1] for pair in pairs)
                        or len({pair[0] for pair in pairs}) != len(pairs)):
                    raise RuntimeError("Malformed or duplicate smoke DONE fields")
                values = dict(pairs)
                identity = values.get("firmware_elf_sha256", "")
                if not re.fullmatch(r"[0-9a-f]{64}", identity) or identity != expected_elf:
                    raise RuntimeError("Smoke DONE does not identify the flashed firmware")
                done = line
        if fault:
            raise RuntimeError("Smoke firmware reported a fault; inspect test-serial.log")
        if len(pending) > 65536:
            raise RuntimeError("Smoke serial line limit exceeded")
        if done is not None:
            return done
    raise RuntimeError("A complete firmware-bound smoke DONE line was not received")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-build", type=Path, required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--complete-fault-line",action="store_true",help="Capture the remainder of a fault line before recording failure")
    parser.add_argument("--board", choices=("xiao",), default="xiao")
    parser.add_argument("--mute-current-instrument", action="store_true",
                        help="Verify --current-build, then mute and Panic before replacing it")
    parser.add_argument("--current-build", type=Path)
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or not 2 <= args.timeout <= 600:
        parser.error("Timeout must be between 2 and 600 seconds")
    if args.out.exists() or args.out.is_symlink():
        parser.error("Use a fresh output directory")
    if args.mute_current_instrument != (args.current_build is not None):
        parser.error("Use --mute-current-instrument and --current-build together")

    device_key = device_identity(args.device_id)
    test = artifacts(args.test_build.resolve(), args.board)
    if test["report"].get("format") != "rnbo-hardware-smoke-build-v1":
        raise ValueError("Expected a hardware smoke build report")
    current = artifacts(args.current_build.resolve(), args.board) if args.current_build else None
    if args.backup.is_symlink() or not args.backup.is_file():
        raise ValueError("Expected an original private full-flash backup file")
    backup = args.backup.resolve()
    backup_info = hardware.read_json(backup.parent / "backup.json")
    identities = [device_identity(backup_info[key]) for key in ("mac", "device_mac") if key in backup_info]
    if (not identities or any(value != device_key for value in identities)
            or backup.stat().st_size != hardware.FLASH_BYTES[args.board]
            or sha(backup) != backup_info.get("backup_sha256")
            or backup_info.get("backup_bytes", hardware.FLASH_BYTES[args.board]) != hardware.FLASH_BYTES[args.board]
            or backup_info.get("application_write_offset", 0x10000) != 0x10000):
        raise ValueError("Private full-flash backup does not match this board")
    table = test["partition"].read_bytes()
    with backup.open("rb") as stream:
        stream.seek(0x8000)
        original_table = stream.read(len(table))
    if table != original_table or (current and current["partition"].read_bytes() != table):
        raise ValueError("Smoke, current and original partition tables must match")

    # Importing pyserial does not enumerate/open USB. All access occurs below,
    # after the complete static artifact/backup checks.
    import serial
    from serial.tools import list_ports

    output = args.out.resolve()
    output.mkdir(parents=True)
    captured = bytearray()
    cases = []
    done = error = None
    flash_attempted = flashed = False
    controls = {}
    started = datetime.now(timezone.utc).isoformat()
    (output / "flash.log").write_text("")

    def port():
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            matches = [entry.device for entry in list_ports.comports()
                       if re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12}", entry.serial_number or "")
                       and device_identity(entry.serial_number) == device_key]
            if len(matches) > 1:
                raise RuntimeError("Multiple USB devices advertise the selected board identity")
            if len(matches) == 1:
                return matches[0]
            time.sleep(.1)
        raise RuntimeError("The exact selected XIAO did not re-enumerate")

    def connect():
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                return hardware.open_serial(port(), 115200, 5)
            except serial.SerialException:
                time.sleep(.1)
        raise RuntimeError("The selected XIAO USB connection is unavailable")

    def instrument_status(transport):
        status = hardware.validate_status(transport.request("status"), args.board)
        if status.get("firmware_elf_sha256") != current["elf_sha256"]:
            raise RuntimeError("Current instrument firmware identity differs; no flash permitted")
        source = current["report"].get("prepared_export", {}).get("manifest", {}).get("source_tree_sha256")
        if source and status.get("module_source_sha256") != source:
            raise RuntimeError("Current instrument module identity differs; no flash permitted")
        hardware.healthy(status, strict=True)
        return status

    try:
        if current:
            connection = connect()
            try:
                transport = hardware.JsonLineTransport(connection, 5)
                before = instrument_status(transport)
                if type(before.get("frames")) is not int or before["frames"] < 512:
                    raise RuntimeError("Current instrument is not settled")
                controls["before"] = before
                # A lost acknowledgement aborts before flash; there is no implicit
                # recovery write or attempt to make the old instrument audible.
                controls["mute_attempted"] = True
                transport.request("volume 0")
                transport.request("panic")
                deadline = time.monotonic() + 15
                while True:
                    quiet = instrument_status(transport)
                    controls["last_status"] = quiet
                    if quiet.get("volume") == 0 and quiet.get("panic") is True and quiet.get("ready_to_resume") is True:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Instrument did not acknowledge muted ready state")
                    time.sleep(.1)
            finally:
                connection.close()
        # Revalidate all executable bytes and geometry immediately before the
        # only write, then resolve the exact USB identity again.
        checked = artifacts(args.test_build.resolve(), args.board)
        if checked["report_sha256"] != test["report_sha256"] or checked["partition"].read_bytes() != table:
            raise ValueError("Smoke build changed before flash")
        selected_port = port()
        with (output / "flash.log").open("w") as log:
            flash_attempted = True
            subprocess.run([sys.executable, "-m", "esptool", "--chip", "esp32s3", "--port", selected_port,
                            "--baud", "921600", "--after", "watchdog_reset", "write_flash", "0x10000",
                            str(test["app"])], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=90)
        flashed = True
        connection = connect()
        try:
            done = collect_serial(connection, test["elf_sha256"], args.timeout, captured, cases,complete_fault_line=args.complete_fault_line)
        finally:
            connection.close()
    except BaseException as failure:
        error = f"{type(failure).__name__}: {failure}"
    finally:
        serial_log = output / "test-serial.log"
        serial_log.write_bytes(captured)
        report = {"format": "rnbo-hardware-smoke-run-v1", "result": "completed" if error is None else "failed",
                  "error": error, "board": args.board, "flash_bytes": hardware.FLASH_BYTES[args.board],
                  "device_id": device_key, "backup_sha256": backup_info["backup_sha256"],
                  "started_at_utc": started, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                  "test_build_report_sha256": test["report_sha256"], "test_elf_sha256": test["elf_sha256"],
                  "test_app_sha256": sha(test["app"]), "partition_table_sha256": sha(test["partition"]),
                  "runner_sha256": sha(Path(__file__)), "guard_runner_sha256": sha(Path(hardware.__file__)),
                  "current_build_report_sha256": current["report_sha256"] if current else None,
                  "controls": controls, "flash_attempted": flash_attempted,
                  "left_installed": True if flashed else (None if flash_attempted else False),
                  "restore_attempted": False, "completion_means_all_cases_passed": False,
                  "complete_fault_line":args.complete_fault_line,
                  "done_line": done, "case_lines": cases,
                  "serial_log_sha256": sha(serial_log), "flash_log_sha256": sha(output / "flash.log")}
        (output / "hardware-smoke.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"result": report["result"], "report": str(output / "hardware-smoke.json"),
                      "left_installed": report["left_installed"], "error": error}))
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
