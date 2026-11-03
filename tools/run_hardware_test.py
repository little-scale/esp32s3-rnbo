#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run an isolated board-specific test application and restore the identified instrument.

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
import re
from pathlib import Path
import subprocess
import struct
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


FLASH_BYTES = {"amoled": 0x1000000, "xiao": 0x800000}
FAULT_COUNTERS = ("nonfinite", "write_errors", "dma_errors", "queue_errors", "module_errors",
                  "audio_heap_allocations", "audio_heap_frees", "late_platform_allocations",
                  "render_deadline_overruns")


def device_identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12}", value):
        raise ValueError("Expected a complete board MAC identity")
    return value.replace(":", "").lower()


def healthy(result, strict=False):
    if result.get("allocation_fault") or result.get("reconstruction_failed"):
        raise RuntimeError("Instrument reports an allocation or reconstruction fault")
    for field in FAULT_COUNTERS:
        value = result.get(field, None if strict else 0)
        if type(value) is not int or value != 0:
            raise RuntimeError(f"Instrument health check failed: {field}={value}")


def artifacts(directory, board="amoled"):
    report_path = directory / "build-report.json"
    report = read_json(report_path)
    if report.get("board") != board:
        raise ValueError(f"Build does not match the selected {board} profile")
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
    header = app[0].read_bytes()[:4]
    expected_size_code = 3 if board == 'xiao' else 4
    if len(header) != 4 or header[0] != 0xe9 or header[3] >> 4 != expected_size_code:
        raise ValueError(f"Application must declare the selected {board} flash size")
    factory = []
    table = partitions[0].read_bytes()
    for offset in range(0, len(table) - 31, 32):
        magic, kind, subtype, address, size, _, _ = struct.unpack_from('<HBBII16sI', table, offset)
        if magic in (0xffff, 0xebeb):
            break
        if magic != 0x50aa or size == 0 or address + size > FLASH_BYTES[board]:
            raise ValueError('Invalid or out-of-profile partition geometry')
        if kind == 0:
            factory.append((subtype, address, size))
    if factory != [(0, 0x10000, 0x300000)]:
        raise ValueError('Expected exactly the reviewed factory application partition')
    return {"report": report, "report_sha256": sha(report_path), "app": app[0],
            "elf_sha256": sha(elf[0]), "partition": partitions[0]}


def restore_schema(build, prepared, supplied, require_defaults=False):
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
        if supplied is not None and identity not in supplied:
            raise ValueError(f"Supply known original --restore-param {identity}=VALUE")
        if require_defaults and "initialValue" not in param:
            raise ValueError(f"Compiled initial value missing for {identity}")
        value = supplied[identity] if supplied is not None else param.get('initialValue',param['minimum'])
        if not math.isfinite(value) or not param["minimum"] <= value <= param["maximum"]:
            raise ValueError(f"Invalid original parameter value: {identity}")
        result[identity] = {"index": param["index"], "actual": value,
                            'minimum':param['minimum'],'maximum':param['maximum']}
    if supplied is not None and set(result) != set(supplied):
        raise ValueError("Unknown restore parameter identity")
    return result


def live_parameters(transport, schema):
    values=transport.request('parameter-values').get('parameters')
    if not isinstance(values,list) or len(values)!=len(schema):
        raise ValueError('Live parameter readback does not match the admitted schema')
    by_index={}
    for item in values:
        index=item.get('index');value=item.get('actual')
        if type(index) is not int or index in by_index or type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError('Invalid live parameter readback')
        by_index[index]=value
    result={}
    for identity,param in schema.items():
        value=by_index.get(param['index'])
        if value is None:
            raise ValueError('Live parameter value is outside its admitted range')
        # The ABI and %.9g readback represent Float32, while the source JSON
        # bounds are decimal doubles. Compare their actual ABI values: e.g.
        # the valid upper endpoint 0.99 reads as 0.99000001. No epsilon admits
        # an adjacent out-of-range Float32 value.
        try:
            lower,actual,upper=(struct.unpack('<f',struct.pack('<f',v))[0]
                                for v in (param['minimum'],value,param['maximum']))
        except (OverflowError,struct.error) as exc:
            raise ValueError('Live parameter value does not fit Float32') from exc
        if not all(math.isfinite(v) for v in (lower,actual,upper)) or not lower<=actual<=upper:
            raise ValueError('Live parameter value is outside its admitted range')
        result[identity]={**param,'actual':value}
    return result


def same_parameter_values(expected, actual):
    return all(struct.pack('<f',p['actual'])==struct.pack('<f',actual[k]['actual']) for k,p in expected.items())


def main():
    import serial
    from serial.tools import list_ports
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", choices=tuple(FLASH_BYTES), default="amoled")
    parser.add_argument("--device-id", required=True, help="USB serial/MAC identity of this exact board")
    parser.add_argument("--test-build", type=Path, required=True)
    parser.add_argument("--restore-build", type=Path, required=True)
    parser.add_argument("--restore-prepared", type=Path, required=True)
    parser.add_argument("--restore-param", action="append", default=[])
    parser.add_argument('--restore-live-controls',action='store_true',
                        help='Snapshot and verify current parameter values and Panic state; requires quiet startup')
    parser.add_argument('--restore-running-defaults', action='store_true',
                        help='XIAO only: require and restore automatic unpaused startup at 50%% with compiled defaults')
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--pass-token", required=True, help="Exact test PASS marker on one complete log line")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not 2 <= args.timeout <= 600 or not args.pass_token or len(args.pass_token) > 160:
        parser.error("Invalid bounded timeout or PASS marker")
    if args.out.exists():
        parser.error("Use a fresh output directory")
    device_key = device_identity(args.device_id)
    test = artifacts(args.test_build.resolve(), args.board)
    restore = artifacts(args.restore_build.resolve(), args.board)
    supplied = {}
    for item in args.restore_param:
        identity, separator, value = item.partition("=")
        if not separator or identity in supplied:
            parser.error("Restore parameters must be unique ID=ACTUAL_VALUE entries")
        supplied[identity] = float(value)
    if args.restore_live_controls and supplied:
        parser.error('Choose live controls or explicit restore parameters')
    if args.restore_live_controls and restore['report'].get('initial_volume_percent')!=0:
        raise ValueError('Live-control recovery requires an instrument built with startup volume zero')
    running_defaults = args.restore_running_defaults
    if args.board == 'xiao' and restore['report'].get('initial_volume_percent') != 0 and not running_defaults:
        raise ValueError('Audible XIAO recovery requires explicit --restore-running-defaults startup50 mode')
    if running_defaults and (args.board != 'xiao' or supplied or args.restore_live_controls or
                             restore['report'].get('initial_volume_percent') != 50):
        raise ValueError('Running-default recovery requires XIAO startup50 and no parameter replay/live snapshot')
    schema = restore_schema(restore, args.restore_prepared.resolve(),
                            None if args.restore_live_controls or running_defaults else supplied,
                            require_defaults=running_defaults)
    module_source = restore['report'].get('prepared_export', {}).get('manifest', {}).get('source_tree_sha256')
    if running_defaults and not re.fullmatch('[0-9a-f]{64}', module_source or ''):
        raise ValueError('Running-default recovery requires a pinned module source identity')
    backup = args.backup.resolve()
    backup_info = read_json(backup.parent / "backup.json")
    backup_ids = [device_identity(backup_info[k]) for k in ('mac', 'device_mac') if k in backup_info]
    if (not backup_ids or any(value != device_key for value in backup_ids) or
            backup.stat().st_size != FLASH_BYTES[args.board] or sha(backup) != backup_info["backup_sha256"] or
            backup_info.get('backup_bytes', FLASH_BYTES[args.board]) != FLASH_BYTES[args.board] or
            backup_info.get('application_write_offset', 0x10000) != 0x10000):
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
                       if re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12}", p.serial_number or "")
                       and device_identity(p.serial_number) == device_key]
            if len(matches) > 1:
                raise RuntimeError("Multiple USB devices advertise the selected board identity")
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
        result = validate_status(transport.request("status"), args.board)
        if result["firmware_elf_sha256"] != restore["elf_sha256"]:
            raise RuntimeError("Current instrument identity differs from the restoration candidate")
        if module_source and result.get('module_source_sha256') != module_source:
            raise RuntimeError("Current module source identity differs from the restoration candidate")
        healthy(result, strict=running_defaults)
        return result

    def check_defaults(transport, result):
        if result['panic'] or result['volume'] != 50:
            raise RuntimeError('Expected unpaused startup50 controls; no parameter replay permitted')
        values = live_parameters(transport, schema)
        if not same_parameter_values(schema, values):
            raise RuntimeError('Current parameters differ from compiled startup defaults')
        return values

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
        if running_defaults:
            check_defaults(transport, before)
        if before["frames"] < 512 or (before["panic"] and not args.restore_live_controls) or before["allocation_fault"]:
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
            if (current["panic"] and not args.restore_live_controls) or current["allocation_fault"] or current.get('reconstruction_failed'):
                raise RuntimeError("Instrument state changed before testing; no mutation attempted")
            if running_defaults:
                if current['frames'] < before['frames'] or current.get('uptime_us', 0) < before.get('uptime_us', 0):
                    raise RuntimeError('Instrument reset during read-only reconnect; no mutation attempted')
                check_defaults(transport, current)
            if args.restore_live_controls:
                if current['panic'] and not current.get('ready_to_resume'):
                    raise RuntimeError('Wait for the muted instrument to finish reconstruction')
                schema=live_parameters(transport,schema)
            before = current
            (output / "before.json").write_text(json.dumps({'status':before,'parameters':schema}, indent=2) + "\n")
            restore_required = True
            transport.request("volume 0")
            transport.request("panic")
            deadline = time.monotonic() + 15
            while True:
                quiet = status(transport)
                if quiet['volume'] == 0 and quiet['panic'] and quiet.get('ready_to_resume'):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('Instrument did not reach acknowledged muted readiness before flash')
                time.sleep(.1)
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
                if any(marker in captured for marker in (b"Guru Meditation", b"assert failed:",
                                                          b": FAIL ", b"RNBO_OBJECT_BENCHMARK FAIL ")):
                    raise RuntimeError("Test firmware reported a fault; inspect test-serial.log")
                pass_line = next((line.strip() for line in complete
                                  if line.startswith(args.pass_token) and line.endswith("\n")), None)
                if pass_line:
                    fields = [token.split('=', 1) for token in pass_line.split() if '=' in token]
                    tokens = dict(fields)
                    if len(tokens) != len(fields) or tokens.get('firmware_elf_sha256') != test['elf_sha256']:
                        raise RuntimeError("PASS line does not identify the firmware actually tested")
                    if test['report'].get('format') == 'rnbo-esp32s3-object-benchmark-build':
                        expected = {'fixture': test['report']['benchmark']['fixture']['id'],
                                    'strict_module_sha256': test['report']['modules']['strict']['artifact_sha256'],
                                    'optimized_module_sha256': test['report']['modules']['optimized']['artifact_sha256']}
                        if any(tokens.get(k) != v for k, v in expected.items()):
                            raise RuntimeError('Benchmark PASS fixture/module identity mismatch')
                    break
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
                if running_defaults:
                    check_defaults(transport, after)
                else:
                    for identity, parameter in schema.items():
                        acknowledgement = transport.request(f"param {parameter['index']} {parameter['actual']:.9g}")
                        if acknowledgement.get("queued") is not True:
                            raise RuntimeError(f"Restore parameter was rejected: {identity}")
                    time.sleep(.15)
                    if args.restore_live_controls:
                        if not same_parameter_values(schema,live_parameters(transport,schema)):
                            raise RuntimeError('Restored parameter readback differs from snapshot')
                        if before['panic']:
                            transport.request('panic')
                            deadline=time.monotonic()+15
                            while True:
                                after=status(transport)
                                if after['panic'] and after.get('ready_to_resume'):break
                                if time.monotonic()>=deadline:raise RuntimeError('Restored Panic reconstruction did not finish')
                                time.sleep(.1)
                            if not same_parameter_values(schema,live_parameters(transport,schema)):
                                raise RuntimeError('Parameter state changed during Panic reconstruction')
                    transport.request(f"volume {before['volume']}")
                    time.sleep(0.15)
                    after = status(transport)
                    if after["volume"] != before["volume"] or after["panic"] != before['panic'] or after["allocation_fault"]:
                        raise RuntimeError("Restored controls/fault state do not match")
                restored = {"result": "restored", "status": after, "parameters": schema,
                            "parameter_readback_available": args.restore_live_controls or running_defaults, "instance_phase_restored": False,
                            "startup50_audible": running_defaults}
            finally:
                connection.close()
        except StopIteration:
            pass
        except BaseException as failure:
            # A failed verification must not leave an unknown audible state.
            if restore_required:
                try:
                    connection = connect()
                    try:
                        recovery_transport = JsonLineTransport(connection, 5)
                        recovery_transport.request('volume 0')
                        recovery_transport.request('panic')
                    finally:
                        connection.close()
                except BaseException:
                    pass
            restored = {"result": "failed", "error": f"{type(failure).__name__}: {failure}"}
            if error is None:
                error = "Test passed but restoration could not be verified"
        report = {"format": "rnbo-isolated-hardware-test", "format_version": 1,
                  "result": "passed" if error is None else "failed", "error": error,
                  "board": args.board, "flash_bytes": FLASH_BYTES[args.board],
                  "restore_policy": "running-defaults-startup50" if running_defaults else ("quiet-live-snapshot" if args.restore_live_controls else "explicit-parameter-replay"),
                  "backup_sha256": backup_info['backup_sha256'], "restore_module_source_sha256": module_source,
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
    except (OSError, ValueError, RuntimeError, CaptureError, subprocess.CalledProcessError) as failure:
        raise SystemExit(f"Hardware test failed: {failure}")
