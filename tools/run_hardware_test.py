#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run an isolated AMOLED test application and restore the identified instrument.

Writes only the application partition. A matching private full-flash backup and
matching partition tables are required. Serial identity is resolved again after
each reset; the restoration attempt is in the same operation's finally block.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host/clients"))
from capture import CaptureError, JsonLineTransport, open_serial, validate_status


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError(f"Missing, linked or oversized JSON: {path}")
    return json.loads(path.read_text())


def artifacts(directory):
    report_path = directory / "build-report.json"
    report = read_json(report_path)
    if report.get("board") != "amoled":
        raise ValueError("The connected board requires the AMOLED 16 MiB profile")
    files = report.get("artifacts", {})
    if not files:
        raise ValueError("Build report requires an artifact integrity inventory")
    for name, record in files.items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT / "build") or not path.is_file():
            raise ValueError(f"Artifact is outside the local build tree: {name}")
        if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError(f"Artifact changed after compilation: {name}")
    app = [ROOT / name for name in files if name.endswith(".bin") and "partition-table" not in name and "bootloader" not in name]
    elf = [ROOT / name for name in files if name.endswith(".elf") and "bootloader" not in name]
    partitions = [ROOT / name for name in files if name.endswith("partition-table.bin")]
    if len(app) != 1 or len(elf) != 1 or len(partitions) != 1:
        raise ValueError("Build report must identify one app, ELF and partition table")
    if not 0 < app[0].stat().st_size <= 0x300000:
        raise ValueError("Application exceeds the reviewed factory partition")
    return {"report": report, "report_sha256": sha(report_path), "app": app[0],
            "elf_sha256": sha(elf[0]), "partition": partitions[0]}


def restore_schema(build, prepared, supplied):
    manifest = read_json(prepared / "manifest.json")
    admitted = build["report"].get("prepared_export", {})
    if admitted.get("manifest") != manifest:
        raise ValueError("Restore export does not match the identified instrument")
    path = prepared / "description.json"
    expected = admitted["provenance"]["prepared_files_sha256"]["description.json"]
    if sha(path) != expected:
        raise ValueError("Restore parameter description changed after admission")
    params = read_json(path)["parameters"]
    result = {}
    for param in params:
        identity = param["paramId"]
        if identity in result:
            raise ValueError("Duplicate restore parameter identity")
        if identity not in supplied:
            raise ValueError(f"Supply known original --restore-param {identity}=VALUE")
        value = supplied[identity]
        if not math.isfinite(value) or not param["minimum"] <= value <= param["maximum"]:
            raise ValueError(f"Invalid original parameter value: {identity}")
        result[identity] = {"index": param["index"], "actual": value}
    if set(result) != set(supplied):
        raise ValueError("Unknown restore parameter identity")
    return result


def main():
    import serial
    from serial.tools import list_ports
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", required=True, help="USB serial/MAC identity of this exact board")
    parser.add_argument("--test-build", type=Path, required=True)
    parser.add_argument("--restore-build", type=Path, required=True)
    parser.add_argument("--restore-prepared", type=Path, required=True)
    parser.add_argument("--restore-param", action="append", default=[])
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--pass-token", required=True, help="Exact test PASS marker on one complete log line")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not 2 <= args.timeout <= 600 or not args.pass_token or len(args.pass_token) > 160:
        parser.error("Invalid bounded timeout or PASS marker")
    if args.out.exists():
        parser.error("Use a fresh output directory")
    test = artifacts(args.test_build.resolve())
    restore = artifacts(args.restore_build.resolve())
    supplied = {}
    for item in args.restore_param:
        identity, separator, value = item.partition("=")
        if not separator or identity in supplied:
            parser.error("Restore parameters must be unique ID=ACTUAL_VALUE entries")
        supplied[identity] = float(value)
    schema = restore_schema(restore, args.restore_prepared.resolve(), supplied)
    backup = args.backup.resolve()
    backup_info = read_json(backup.parent / "backup.json")
    if (backup.stat().st_size != 0x1000000 or sha(backup) != backup_info["backup_sha256"] or
            backup_info["mac"].lower() != args.device_id.lower()):
        raise ValueError("Private recovery backup does not match this board")
    original_prefix = backup.read_bytes()[:0x10000]
    table = restore["partition"].read_bytes()
    if test["partition"].read_bytes() != table or original_prefix[0x8000:0x8000+len(table)] != table:
        raise ValueError("Test, instrument and original partition tables must match")
    output = args.out.resolve()
    output.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat()
    source_hash = sha(Path(__file__))

    def port():
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            matches = [p.device for p in list_ports.comports()
                       if (p.serial_number or "").lower() == args.device_id.lower()]
            if len(matches) == 1:
                return matches[0]
            time.sleep(0.1)
        raise RuntimeError("The expected board did not re-enumerate")

    def connect():
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                return open_serial(port(), 115200, 5)
            except serial.SerialException:
                time.sleep(0.1)
        raise RuntimeError("The expected board USB connection is unavailable")

    def status(transport):
        result = validate_status(transport.request("status"), "amoled")
        if result["firmware_elf_sha256"] != restore["elf_sha256"]:
            raise RuntimeError("Current instrument identity differs from the restoration candidate")
        return result

    def flash(build, filename):
        # Recheck immediately before each write. Never write bootloader/data.
        if sha(build["app"]) != build["report"]["artifacts"][str(build["app"].relative_to(ROOT))]["sha256"]:
            raise ValueError("Application changed before flash")
        with (output / filename).open("w") as log:
            subprocess.run([sys.executable, "-m", "esptool", "--chip", "esp32s3", "--port", port(),
                            "--baud", "921600", "--after", "watchdog_reset", "write_flash", "0x10000",
                            str(build["app"])], stdout=log, stderr=subprocess.STDOUT, check=True)

    connection = connect()
    try:
        transport = JsonLineTransport(connection, 5)
        before = status(transport)
        if before["frames"] < 512 or before["panic"] or before["allocation_fault"]:
            raise RuntimeError("Expected a settled, running, healthy instrument before the test")
    finally:
        connection.close()
    (output / "before.json").write_text(json.dumps(before, indent=2) + "\n")
    error = None
    pass_line = None
    restored = {"result": "not attempted"}
    restore_required = False
    try:
        connection = connect()
        try:
            transport = JsonLineTransport(connection, 5)
            current = status(transport)
            if current["panic"] or current["allocation_fault"]:
                raise RuntimeError("Instrument state changed before testing; no mutation attempted")
            before = current
            (output / "before.json").write_text(json.dumps(before, indent=2) + "\n")
            restore_required = True
            transport.request("volume 0")
            transport.request("panic")
        finally:
            connection.close()
        flash(test, "flash-test.log")
        connection = connect()
        captured = bytearray()
        try:
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline and len(captured) < 4 * 1024 * 1024:
                captured.extend(connection.read(connection.in_waiting or 1))
                complete = captured.decode("utf-8", "replace").splitlines(keepends=True)
                pass_line = next((line.strip() for line in complete
                                  if args.pass_token in line and line.endswith("\n")), None)
                if pass_line:
                    if f"firmware_elf_sha256={test['elf_sha256']}" not in pass_line:
                        raise RuntimeError("PASS line does not identify the firmware actually tested")
                    break
                if any(marker in captured for marker in (b"Guru Meditation", b"assert failed:", b": FAIL ")):
                    raise RuntimeError("Test firmware reported a fault; inspect test-serial.log")
            if not pass_line:
                raise RuntimeError("A complete test PASS line was not received")
        finally:
            (output / "test-serial.log").write_bytes(captured)
            connection.close()
    except BaseException as failure:
        error = f"{type(failure).__name__}: {failure}"
    finally:
        try:
            if not restore_required:
                restored = {"result": "not needed; no mutation attempted"}
                raise StopIteration
            flash(restore, "restore-instrument.log")
            connection = connect()
            try:
                transport = JsonLineTransport(connection, 5)
                deadline = time.monotonic() + 15
                while True:
                    after = status(transport)
                    if after["frames"] >= 512:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Restored audio did not start")
                    time.sleep(0.1)
                for identity, parameter in schema.items():
                    acknowledgement = transport.request(f"param {parameter['index']} {parameter['actual']:.9g}")
                    if acknowledgement.get("queued") is not True:
                        raise RuntimeError(f"Restore parameter was rejected: {identity}")
                transport.request(f"volume {before['volume']}")
                time.sleep(0.15)
                after = status(transport)
                if after["volume"] != before["volume"] or after["panic"] or after["allocation_fault"]:
                    raise RuntimeError("Restored controls/fault state do not match")
                restored = {"result": "restored", "status": after, "parameters": schema,
                            "parameter_readback_available": False, "instance_phase_restored": False}
            finally:
                connection.close()
        except StopIteration:
            pass
        except BaseException as failure:
            restored = {"result": "failed", "error": f"{type(failure).__name__}: {failure}"}
            if error is None:
                error = "Test passed but restoration could not be verified"
        report = {"format": "rnbo-isolated-hardware-test", "format_version": 1,
                  "result": "passed" if error is None else "failed", "error": error,
                  "device_id": args.device_id, "started_at_utc": started,
                  "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                  "test_build_report_sha256": test["report_sha256"],
                  "test_elf_sha256": test["elf_sha256"], "test_app_sha256": sha(test["app"]),
                  "pass_line": pass_line, "restoration": restored,
                  "restore_build_report_sha256": restore["report_sha256"],
                  "runner_sha256": source_hash,
                  "serial_log_sha256": sha(output / "test-serial.log") if (output / "test-serial.log").exists() else None}
        (output / "hardware-test.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"result": report["result"], "report": str(output / "hardware-test.json"),
                      "pass_line": pass_line, "restoration": restored["result"], "error": error}))
    if error:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, CaptureError, subprocess.CalledProcessError) as failure:
        raise SystemExit(f"Hardware test failed: {failure}")
