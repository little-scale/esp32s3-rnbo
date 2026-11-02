# SPDX-License-Identifier: MIT
"""Exercise recovery after failures without opening USB or invoking esptool."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("hardware_runner", ROOT / "tools/run_hardware_test.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class HardwareRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.out = self.root / "output"
        self.device = "28:84:85:3a:d3:90"
        self.calls = []
        self.control_failure = False
        self.flash_failure = False
        self.bad_pass_identity = False
        self.original_volume = 37
        self.volume = self.original_volume
        self.panic = False
        self.live=False
        self.values={0:440.0,1:0.2}
        self.bad_readback=False
        self.test = self.make_build("test")
        self.restore = self.make_build("restore")
        self.prepared = self.root / "prepared"
        self.prepared.mkdir()
        description = {"parameters": [
            {"paramId": "frequency", "index": 0, "minimum": 20, "maximum": 10000},
            {"paramId": "level", "index": 1, "minimum": 0, "maximum": 1}]}
        raw = json.dumps(description).encode()
        (self.prepared / "description.json").write_bytes(raw)
        manifest = {"format": "prepared-test"}
        (self.prepared / "manifest.json").write_text(json.dumps(manifest))
        report = json.loads((self.restore / "build-report.json").read_text())
        report["prepared_export"] = {"manifest": manifest, "provenance": {
            "prepared_files_sha256": {"description.json": hashlib.sha256(raw).hexdigest()}}}
        (self.restore / "build-report.json").write_text(json.dumps(report))
        private = self.root / "private"
        private.mkdir()
        self.backup = private / "original.bin"
        with self.backup.open("wb") as output:
            output.truncate(0x1000000)
        (private / "backup.json").write_text(json.dumps({
            "mac": self.device, "backup_sha256": runner.sha(self.backup)}))
        self.restore_elf = runner.sha(self.restore / "restore.elf")
        self.test_elf = runner.sha(self.test / "test.elf")

    def make_build(self, label):
        directory = self.root / "build" / label
        directory.mkdir(parents=True)
        paths = [directory / (label + ".bin"), directory / (label + ".elf"),
                 directory / "partition_table/partition-table.bin"]
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bytes(3072) if "partition-table" in path.name else label.encode())
        artifacts = {str(p.relative_to(self.root)): {"bytes": p.stat().st_size, "sha256": runner.sha(p)} for p in paths}
        (directory / "build-report.json").write_text(json.dumps({"board": "amoled", 'initial_volume_percent':0,"artifacts": artifacts}))
        return directory

    def status(self):
        return {"runtime": "rnbo-esp32s3-bringup", "board": "Waveshare AMOLED 1.8 V2",
                "source": "static-rnbo", "rate": 44100, "block_frames": 256,
                "channels": 1, "frames": 1024, "firmware_elf_sha256": self.restore_elf,
                "module_source_sha256": "a" * 64, "volume": self.volume,
                "panic": self.panic, "allocation_fault": False,'ready_to_resume':self.panic}

    def request(self, command):
        self.calls.append(("command", command))
        if command == "status":
            return self.status()
        if command=='parameter-values':
            values=dict(self.values)
            if self.bad_readback and any(k=='flash' for k,v in self.calls):values[1]=0.9
            return {'parameters':[{'index':i,'actual':v} for i,v in values.items()]}
        if command.startswith("volume "):
            self.volume = int(command.split()[1])
            if self.control_failure and self.volume == 0:
                raise OSError("lost acknowledgement after muting")
            return {"accepted": True}
        if command == "panic":
            self.panic = True
            return {"panic": True}
        if command.startswith("param "):
            _,i,value=command.split();self.values[int(i)]=float(value)
            return {"queued": True}
        raise AssertionError(command)

    def flash(self, arguments, **kwargs):
        image = Path(arguments[-1])
        self.calls.append(("flash", image.name))
        if image.name == "test.bin" and self.flash_failure:
            raise subprocess.CalledProcessError(2, arguments)
        self.volume = 100
        self.panic = False
        self.values={0:440.0,1:0.2}
        return subprocess.CompletedProcess(arguments, 0)

    def run_case(self):
        outer = self
        class Connection:
            def __init__(self):
                identity = "0" * 64 if outer.bad_pass_identity else outer.test_elf
                self.data = f"TEST PASS firmware_elf_sha256={identity}\n".encode()
            @property
            def in_waiting(self): return len(self.data)
            def read(self, size):
                data, self.data = self.data[:size], self.data[size:]
                return data
            def close(self): pass
        serial_module = types.ModuleType("serial")
        serial_module.SerialException = OSError
        tools_module = types.ModuleType("serial.tools")
        tools_module.list_ports = types.SimpleNamespace(comports=lambda: [
            types.SimpleNamespace(device="/dev/fake", serial_number=self.device)])
        arguments = ["run_hardware_test.py", "--device-id", self.device,
                     "--test-build", str(self.test), "--restore-build", str(self.restore),
                     "--restore-prepared", str(self.prepared), "--restore-param", "frequency=440",
                     "--restore-param", "level=0.2", "--backup", str(self.backup),
                     "--pass-token", "TEST PASS ", "--out", str(self.out)]
        if self.live:
            at=arguments.index('--restore-param');del arguments[at:at+4]
            arguments.append('--restore-live-controls')
        with patch.dict(sys.modules, {"serial": serial_module, "serial.tools": tools_module}), \
             patch.object(runner, "ROOT", self.root), patch.object(sys, "argv", arguments), \
             patch.object(runner, "open_serial", side_effect=lambda *args: Connection()), \
             patch.object(runner, "JsonLineTransport", side_effect=lambda *args: types.SimpleNamespace(request=self.request)), \
             patch.object(runner.subprocess, "run", side_effect=self.flash), patch.object(runner.time, "sleep"):
            try:
                runner.main()
            except SystemExit as error:
                self.assertEqual(error.code, 1)
        return json.loads((self.out / "hardware-test.json").read_text())

    def test_pass_restores_volume_and_parameters_after_test_image(self):
        result = self.run_case()
        self.assertEqual(result["result"], "passed")
        self.assertEqual(result["restoration"]["result"], "restored")
        self.assertEqual([name for kind, name in self.calls if kind == "flash"], ["test.bin", "restore.bin"])
        self.assertEqual(self.volume, self.original_volume)
        self.assertIn(("command", "param 0 440"), self.calls)

    def test_failed_test_flash_still_restores_instrument(self):
        self.flash_failure = True
        result = self.run_case()
        self.assertEqual(result["result"], "failed")
        self.assertEqual(result["restoration"]["result"], "restored")
        self.assertEqual([name for kind, name in self.calls if kind == "flash"], ["test.bin", "restore.bin"])
        self.assertEqual(self.volume, self.original_volume)

    def test_lost_mute_acknowledgement_is_inside_recovery_scope(self):
        self.control_failure = True
        result = self.run_case()
        self.assertEqual(result["result"], "failed")
        self.assertEqual([name for kind, name in self.calls if kind == "flash"], ["restore.bin"])
        self.assertEqual(result["restoration"]["result"], "restored")
        self.assertEqual(self.volume, self.original_volume)

    def test_stale_pass_line_with_wrong_firmware_is_rejected_and_restored(self):
        self.bad_pass_identity = True
        result = self.run_case()
        self.assertEqual(result["result"], "failed")
        self.assertIn("firmware actually tested", result["error"])
        self.assertEqual(result["restoration"]["result"], "restored")

    def test_live_snapshot_restores_muted_instrument_and_changed_parameters(self):
        self.live=True;self.panic=True;self.values={0:333.0,1:0.432000011}
        result=self.run_case()
        self.assertEqual(result['result'],'passed')
        self.assertTrue(self.panic)
        self.assertEqual(self.volume,self.original_volume)
        self.assertEqual(self.values[0],333.0)
        self.assertTrue(result['restoration']['parameter_readback_available'])
        self.assertEqual(result['restoration']['parameters']['level']['actual'],0.432000011)

    def test_live_restoration_mismatch_cannot_claim_success(self):
        self.live=True;self.bad_readback=True
        result=self.run_case()
        self.assertEqual(result['result'],'failed')
        self.assertEqual(result['restoration']['result'],'failed')
        self.assertIn('readback differs',result['restoration']['error'])

    def test_invalid_live_snapshot_leaves_instrument_untouched(self):
        self.live=True;self.values[1]=2.0
        result=self.run_case()
        self.assertEqual(result['result'],'failed')
        self.assertEqual(result['restoration']['result'],'not needed; no mutation attempted')
        self.assertFalse(any(k=='flash' or v.startswith('volume ') or v=='panic' for k,v in self.calls))
        self.assertEqual(self.volume,self.original_volume)


if __name__ == "__main__":
    unittest.main()
