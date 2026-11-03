# SPDX-License-Identifier: MIT
"""Smoke-runner safeguards and completion semantics, without device access."""
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("hardware_smoke", ROOT / "tools/run_hardware_smoke.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class SmokeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.device = "02:00:00:00:00:01"  # fictional locally administered test identity
        self.output = self.root / "out"
        self.table = struct.pack("<HBBII16sI", 0x50aa, 0, 0, 0x10000, 0x300000, b"factory", 0) + b"\xff" * (3072 - 32)
        self.test = self.make_build("test", smoke=True)
        self.current = self.make_build("current")
        self.test_elf = runner.sha(self.test / "test.elf")
        self.backup = self.root / "private/original.bin"
        self.backup.parent.mkdir()
        with self.backup.open("wb") as stream:
            stream.truncate(0x800000)
            stream.seek(0x8000)
            stream.write(self.table)
        self.backup_info = {"device_mac": self.device, "backup_sha256": runner.sha(self.backup),
                            "backup_bytes": 0x800000, "application_write_offset": 0x10000}
        self.write_backup_info()
        self.commands = []
        self.writes = []
        self.enumerations = []
        self.wrong_current = False
        self.lost_ack = False
        self.flash_failure = False
        self.duplicate = False
        self.volume = 50
        self.panic = False
        self.clock = 0.
        self.payload = (b"RNBO_SMOKE CASE id=good status=pass\n"
                        b"RNBO_SMOKE CASE id=bad status=output_mismatch bit_mismatches=7\n" +
                        f"RNBO_SMOKE DONE firmware_elf_sha256={self.test_elf} cases=2 passed=1 mismatched=1\n".encode())

    def make_build(self, label, smoke=False):
        directory = self.root / "build" / label
        directory.mkdir(parents=True)
        app, elf, table = directory / f"{label}.bin", directory / f"{label}.elf", directory / "partition_table/partition-table.bin"
        table.parent.mkdir()
        app.write_bytes(b"\xe9\x00\x00\x30" + label.encode())
        elf.write_bytes(label.encode())
        table.write_bytes(self.table)
        report = {"format": "rnbo-hardware-smoke-build-v1" if smoke else "instrument-build",
                  "board": "xiao", "artifacts": {
                      str(path.relative_to(self.root)): {"bytes": path.stat().st_size, "sha256": runner.sha(path)}
                      for path in (app, elf, table)}}
        if not smoke:
            report["prepared_export"] = {"manifest": {"source_tree_sha256": "a" * 64}}
        (directory / "build-report.json").write_text(json.dumps(report))
        return directory

    def write_backup_info(self):
        (self.backup.parent / "backup.json").write_text(json.dumps(self.backup_info))

    def status(self):
        result = {"runtime": "rnbo-esp32s3-bringup", "board": "XIAO ESP32-S3", "rate": 44100,
                  "channels": 2, "block_frames": 256, "source": "static-rnbo", "frames": 1024,
                  "firmware_elf_sha256": "0" * 64 if self.wrong_current else runner.sha(self.current / "current.elf"),
                  "module_source_sha256": "a" * 64, "allocation_fault": False,
                  "panic": self.panic, "volume": self.volume, "ready_to_resume": self.panic}
        result.update({field: 0 for field in runner.hardware.FAULT_COUNTERS})
        return result

    def request(self, command):
        self.commands.append(command)
        if command == "status":
            return self.status()
        if command == "volume 0":
            self.volume = 0
            if self.lost_ack:
                raise OSError("lost mute acknowledgement")
            return {"accepted": True}
        if command == "panic":
            self.panic = True
            return {"panic": True}
        raise AssertionError(command)

    def invoke(self, mute=False):
        outer = self
        class Connection:
            def __init__(self):
                self.data = bytearray(outer.payload if outer.writes else b"")
            @property
            def in_waiting(self):
                return len(self.data)
            def read(self, count):
                value = bytes(self.data[:count]); del self.data[:count]
                return value
            def close(self):
                pass
        def clock():
            self.clock += .05
            return self.clock
        def ports():
            self.enumerations.append(True)
            port = types.SimpleNamespace(device=f"/dev/mock-{len(self.enumerations)}", serial_number=self.device.replace(":", ""))
            other = types.SimpleNamespace(device="/dev/unrelated", serial_number="aabbccddeeff")
            return [port, port] if self.duplicate else [other, port]
        def flash(arguments, **kwargs):
            self.writes.append(arguments)
            kwargs["stdout"].write("app-only mock write\n")
            if self.flash_failure:
                raise subprocess.CalledProcessError(2, arguments)
            return subprocess.CompletedProcess(arguments, 0)
        serial = types.ModuleType("serial"); serial.SerialException = OSError
        serial_tools = types.ModuleType("serial.tools")
        serial_tools.list_ports = types.SimpleNamespace(comports=ports)
        arguments = ["--test-build", str(self.test), "--device-id", self.device,
                     "--backup", str(self.backup), "--out", str(self.output), "--timeout", "2"]
        if mute:
            arguments += ["--mute-current-instrument", "--current-build", str(self.current)]
        with ExitStack() as stack:
            stack.enter_context(patch.object(runner.hardware, "ROOT", self.root))
            stack.enter_context(patch.dict(sys.modules, {"serial": serial, "serial.tools": serial_tools}))
            stack.enter_context(patch.object(runner.hardware, "open_serial", side_effect=lambda *args: Connection()))
            stack.enter_context(patch.object(runner.hardware, "JsonLineTransport", side_effect=lambda *args: types.SimpleNamespace(request=self.request)))
            stack.enter_context(patch.object(runner.subprocess, "run", side_effect=flash))
            stack.enter_context(patch.object(runner.time, "monotonic", side_effect=clock))
            stack.enter_context(patch.object(runner.time, "sleep", return_value=None))
            stack.enter_context(redirect_stdout(io.StringIO()))
            return runner.main(arguments)

    def report(self):
        return json.loads((self.output / "hardware-smoke.json").read_text())

    def test_mixed_cases_complete_and_only_app_is_written_without_restoration(self):
        self.assertEqual(self.invoke(), 0)
        report = self.report()
        self.assertEqual(report["result"], "completed")
        self.assertTrue(report["left_installed"])
        self.assertFalse(report["restore_attempted"])
        self.assertFalse(report["completion_means_all_cases_passed"])
        self.assertEqual(len(report["case_lines"]), 2)
        self.assertIn("output_mismatch", report["case_lines"][1])
        self.assertEqual(len(self.writes), 1)
        args = self.writes[0]
        self.assertEqual(args[args.index("write_flash") + 1:], ["0x10000", str(self.test / "test.bin")])
        self.assertEqual(self.commands, [])
        self.assertEqual((self.output / "test-serial.log").read_bytes(), self.payload)
        self.assertEqual(report["serial_log_sha256"], runner.sha(self.output / "test-serial.log"))

    def test_fault_after_done_takes_precedence_and_preserves_cases(self):
        self.payload += b"E (1) rnbo_object_benchmark: FAIL allocation\n"
        self.assertEqual(self.invoke(), 1)
        report = self.report()
        self.assertEqual(report["result"], "failed")
        self.assertTrue(report["left_installed"])
        self.assertEqual(len(report["case_lines"]), 2)
        self.assertIn("reported a fault", report["error"])
        self.assertEqual(len(self.writes), 1)
        self.assertEqual((self.output / "test-serial.log").read_bytes(), self.payload)

    def test_exact_done_identity_duplicate_fields_and_complete_newline_required(self):
        valid = f"RNBO_SMOKE DONE firmware_elf_sha256={self.test_elf}"
        for index, payload in enumerate((valid + "x\n", valid + f" firmware_elf_sha256={self.test_elf}\n", valid)):
            with self.subTest(payload=payload):
                self.output = self.root / f"bad-done-{index}"
                self.payload = payload.encode()
                self.assertEqual(self.invoke(), 1)
                self.assertIsNone(self.report()["done_line"])

    def test_optional_mute_checks_identity_before_commands_and_ready_before_flash(self):
        self.assertEqual(self.invoke(mute=True), 0)
        self.assertEqual(self.commands, ["status", "volume 0", "panic", "status"])
        report = self.report()
        self.assertTrue(report["controls"]["last_status"]["ready_to_resume"])
        self.assertEqual(report["controls"]["last_status"]["volume"], 0)
        # One resolution to check the old instrument, a fresh one to write,
        # and another resolution after reset to receive the smoke results.
        self.assertEqual(len(self.enumerations), 3)
        self.assertIn("/dev/mock-2", self.writes[0])

    def test_wrong_current_firmware_aborts_before_mutation(self):
        self.wrong_current = True
        self.assertEqual(self.invoke(mute=True), 1)
        self.assertEqual(self.commands, ["status"])
        self.assertEqual(self.writes, [])
        self.assertFalse(self.report()["left_installed"])

    def test_lost_mute_ack_never_flashes_or_automatically_restores(self):
        self.lost_ack = True
        self.assertEqual(self.invoke(mute=True), 1)
        self.assertEqual(self.commands, ["status", "volume 0"])
        self.assertEqual(self.writes, [])
        self.assertFalse(self.report()["restore_attempted"])
        self.assertTrue(self.report()["controls"]["mute_attempted"])

    def test_failed_flash_records_unknown_install_state_without_second_write(self):
        self.flash_failure = True
        self.assertEqual(self.invoke(), 1)
        report = self.report()
        self.assertTrue(report["flash_attempted"])
        self.assertIsNone(report["left_installed"])
        self.assertFalse(report["restore_attempted"])
        self.assertEqual(len(self.writes), 1)
        self.assertIn("app-only mock write", (self.output / "flash.log").read_text())

    def test_duplicate_exact_usb_identity_is_rejected_before_write(self):
        self.duplicate = True
        self.assertEqual(self.invoke(), 1)
        self.assertEqual(self.writes, [])
        self.assertIn("Multiple USB", self.report()["error"])

    def test_backup_identity_hash_size_and_partition_guards_precede_usb(self):
        original = dict(self.backup_info)
        variants = ({"device_mac": "aa:bb:cc:dd:ee:ff"}, {"backup_sha256": "0" * 64},
                    {"backup_bytes": 0x1000000}, {"application_write_offset": 0})
        for changes in variants:
            with self.subTest(changes=changes):
                self.backup_info = dict(original, **changes); self.write_backup_info()
                with self.assertRaisesRegex(ValueError, "backup does not match"):
                    self.invoke()
                self.assertFalse(self.enumerations)
        self.backup_info = original
        with self.backup.open("r+b") as stream:
            stream.seek(0x8000); stream.write(b"bad!")
        self.backup_info["backup_sha256"] = runner.sha(self.backup); self.write_backup_info()
        with self.assertRaisesRegex(ValueError, "partition tables"):
            self.invoke()
        self.assertFalse(self.enumerations)

    def test_flash_profile_header_geometry_and_artifact_hash_guards(self):
        app = self.test / "test.bin"
        app.write_bytes(b"\xe9\x00\x00\x40bad-size")
        report_path = self.test / "build-report.json"
        report = json.loads(report_path.read_text())
        record = report["artifacts"][str(app.relative_to(self.root))]
        record.update(bytes=app.stat().st_size, sha256=runner.sha(app))
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "flash size"):
            self.invoke()
        app.write_bytes(b"\xe9\x00\x00\x30changed")
        with self.assertRaisesRegex(ValueError, "changed after compilation"):
            self.invoke()
        self.assertFalse(self.enumerations)

    def test_partition_geometry_cannot_be_overridden_by_matching_backup(self):
        table = self.test / "partition_table/partition-table.bin"
        altered = struct.pack("<HBBII16sI", 0x50aa, 0, 0, 0x20000, 0x300000, b"factory", 0) + b"\xff" * (3072 - 32)
        table.write_bytes(altered)
        with self.backup.open("r+b") as stream:
            stream.seek(0x8000); stream.write(altered)
        self.backup_info["backup_sha256"] = runner.sha(self.backup); self.write_backup_info()
        report_path = self.test / "build-report.json"
        report = json.loads(report_path.read_text())
        report["artifacts"][str(table.relative_to(self.root))]["sha256"] = runner.sha(table)
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "reviewed factory"):
            self.invoke()
        self.assertFalse(self.enumerations)


if __name__ == "__main__":
    unittest.main()
