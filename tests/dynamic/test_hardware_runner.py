# SPDX-License-Identifier: MIT
"""Exercise recovery after failures without opening USB or invoking esptool."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("hardware_runner", ROOT / "tools/run_hardware_test.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RestoredStatusTests(unittest.TestCase):
    def test_command_free_boot_phase_drains_bytes_and_waits_before_returning(self):
        clock=[0.];events=[];raw=bytearray();operations=[]
        class Connection:
            in_waiting=4
            def read(self,size):operations.append(('read',size));clock[0]+=.5;return b'boot'
            def write(self,_):raise AssertionError('No command permitted during boot phase')
        connection=Connection()
        result=runner.connect_restored_console(lambda:connection,raw,events,
            clock=lambda:clock[0],sleep=lambda _:None)
        self.assertIs(result,connection);self.assertEqual(clock[0],2.)
        self.assertEqual(raw,b'boot'*4)
        self.assertEqual(events,[{'event':'command-free-boot-read','elapsed_seconds':2.}])

    def test_boot_disconnect_reopens_but_oversized_output_stops(self):
        clock=[0.];events=[];closed=[];attempt=[0]
        class Connection:
            in_waiting=1
            def read(self,size):clock[0]+=1;return b'x'
            def close(self):closed.append(True)
        def connect():
            attempt[0]+=1;clock[0]+=.1
            if attempt[0]==1:raise OSError('USB re-enumerating')
            return Connection()
        raw=bytearray()
        runner.connect_restored_console(connect,raw,events,clock=lambda:clock[0],sleep=lambda _:None)
        self.assertEqual(attempt[0],2)
        self.assertEqual(events[0]['event'],'boot-io-disconnect')
        with self.assertRaisesRegex(runner.CaptureError,'output limit'):
            runner.connect_restored_console(lambda:Connection(),bytearray(b'x'*65536),[],
                clock=lambda:clock[0],sleep=lambda _:None)
        self.assertEqual(closed,[True])

    def test_missing_first_reply_retries_read_only_status_then_checks_audio(self):
        events=[];clock=[0.];calls=[]
        def query():
            calls.append('status');clock[0]+=5
            if len(calls)==1:raise runner.CaptureError('Timed out waiting for response to status')
            return {'frames':1024}
        result=runner.wait_restored_audio(query,events,clock=lambda:clock[0],sleep=lambda _:None)
        self.assertEqual(result,{'frames':1024})
        self.assertEqual(calls,['status','status'])
        self.assertEqual(events,[{'event':'status-response-timeout','remaining_seconds':10.}])

    def test_slow_boot_connection_cannot_bypass_settle_deadline(self):
        clock=[0.];closed=[]
        class Connection:
            def close(self):closed.append(True)
        def connect():clock[0]=14.;return Connection()
        with self.assertRaisesRegex(RuntimeError,'boot connection deadline'):
            runner.connect_restored_console(connect,bytearray(),[],clock=lambda:clock[0],sleep=lambda _:None)
        self.assertEqual(closed,[True])

    def test_fault_identity_or_malformed_response_never_retries(self):
        for failure in (RuntimeError('Current instrument identity differs'),
                        RuntimeError('Instrument fault'),runner.CaptureError('Malformed JSON response')):
            calls=[]
            def query():calls.append('status');raise failure
            with self.assertRaises(type(failure)):
                runner.wait_restored_audio(query,[],sleep=lambda _:None)
            self.assertEqual(calls,['status'])

    def test_missing_replies_stop_at_deadline_and_keep_timeout_observations(self):
        events=[];clock=[0.]
        def query():clock[0]+=5;raise runner.CaptureError('Timed out waiting for response to status')
        with self.assertRaisesRegex(runner.CaptureError,'Timed out'):
            runner.wait_restored_audio(query,events,clock=lambda:clock[0],sleep=lambda _:None)
        self.assertEqual(len(events),3)
        self.assertEqual(events[-1]['remaining_seconds'],0)


class HardwareRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.out = self.root / "output"
        self.device = "28:84:85:3a:d3:90"
        self.calls = []
        self.board = 'amoled'
        self.running_defaults = False
        self.fail_log = False
        self.duplicate_usb = False
        self.bad_fault_after_flash = False
        self.control_failure = False
        self.flash_failure = False
        self.missing_restore_status = 0
        self.bad_pass_identity = False
        self.pass_identity_suffix = ""
        self.duplicate_pass_identity = False
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
            output.seek(0x8000)
            output.write((self.restore / 'partition_table/partition-table.bin').read_bytes())
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
            if 'partition-table' in path.name:
                path.write_bytes(struct.pack('<HBBII16sI', 0x50aa, 0, 0, 0x10000, 0x300000, b'factory', 0) + b'\xff' * (3072 - 32))
            elif path.suffix == '.bin':
                path.write_bytes(b'\xe9\x00\x00\x40' + label.encode())
            else:
                path.write_bytes(label.encode())
        artifacts = {str(p.relative_to(self.root)): {"bytes": p.stat().st_size, "sha256": runner.sha(p)} for p in paths}
        (directory / "build-report.json").write_text(json.dumps({"board": "amoled", 'initial_volume_percent':0,"artifacts": artifacts}))
        return directory

    def status(self):
        result = {"runtime": "rnbo-esp32s3-bringup", "board": "XIAO ESP32-S3" if self.board == 'xiao' else "Waveshare AMOLED 1.8 V2",
                "source": "static-rnbo", "rate": 44100, "block_frames": 256,
                "channels": 2 if self.board == 'xiao' else 1, "frames": 1024, "firmware_elf_sha256": self.restore_elf,
                "module_source_sha256": "a" * 64, "volume": self.volume,
                "panic": self.panic, "allocation_fault": False, 'ready_to_resume':self.panic, 'uptime_us':1000000}
        result.update({field: 0 for field in runner.FAULT_COUNTERS})
        if self.bad_fault_after_flash and any(k == 'flash' for k, _ in self.calls):
            result['dma_errors'] = 1
        return result

    def request(self, command):
        self.calls.append(("command", command))
        if command == "status":
            if self.missing_restore_status and any(k=='flash' and v=='restore.bin' for k,v in self.calls):
                self.missing_restore_status-=1
                raise runner.CaptureError('Timed out waiting for response to status')
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
        self.volume = 50 if self.running_defaults else 100
        self.panic = False
        self.values={0:440.0,1:0.2}
        return subprocess.CompletedProcess(arguments, 0)

    def run_case(self):
        outer = self
        class Connection:
            def __init__(self):
                identity = "0" * 64 if outer.bad_pass_identity else outer.test_elf
                identity += outer.pass_identity_suffix
                extra = f" firmware_elf_sha256={identity}" if outer.duplicate_pass_identity else ""
                self.data = (("RNBO_OBJECT_BENCHMARK FAIL comparison\n" if outer.fail_log else "") +
                             f"TEST PASS firmware_elf_sha256={identity}{extra}\n").encode()
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
            types.SimpleNamespace(device="/dev/fake", serial_number=self.device)] * (2 if self.duplicate_usb else 1))
        arguments = ["run_hardware_test.py", "--device-id", self.device,
                     "--test-build", str(self.test), "--restore-build", str(self.restore),
                     "--restore-prepared", str(self.prepared), "--restore-param", "frequency=440",
                     "--restore-param", "level=0.2", "--backup", str(self.backup),
                     "--pass-token", "TEST PASS ", "--out", str(self.out)]
        arguments.extend(['--board', self.board])
        if self.live or self.running_defaults:
            at=arguments.index('--restore-param');del arguments[at:at+4]
            arguments.append('--restore-running-defaults' if self.running_defaults else '--restore-live-controls')
        with patch.dict(sys.modules, {"serial": serial_module, "serial.tools": tools_module}), \
             patch.object(runner, "ROOT", self.root), patch.object(sys, "argv", arguments), \
             patch.object(runner, "open_serial", side_effect=lambda *args: Connection()), \
             patch.object(runner, "JsonLineTransport", side_effect=lambda *args: types.SimpleNamespace(request=self.request)), \
             patch.object(runner, "connect_restored_console", side_effect=lambda connect,*args:connect()) as boot_phase, \
             patch.object(runner.subprocess, "run", side_effect=self.flash), patch.object(runner.time, "sleep"):
            try:
                runner.main()
            except SystemExit as error:
                self.assertEqual(error.code, 1)
            self.boot_phase_calls=boot_phase.call_count
        return json.loads((self.out / "hardware-test.json").read_text())

    def test_pass_restores_volume_and_parameters_after_test_image(self):
        result = self.run_case()
        self.assertEqual(result["result"], "passed")
        self.assertEqual(result["restoration"]["result"], "restored")
        self.assertEqual([name for kind, name in self.calls if kind == "flash"], ["test.bin", "restore.bin"])
        self.assertEqual(self.volume, self.original_volume)
        self.assertIn(("command", "param 0 440"), self.calls)

    def test_restoration_retries_one_missing_status_without_reflashing_or_replaying_controls(self):
        self.missing_restore_status=1
        result=self.run_case()
        self.assertEqual(result['result'],'passed')
        self.assertEqual(result['restoration']['result'],'restored')
        self.assertEqual(self.boot_phase_calls,1)
        self.assertEqual(len(result['restoration_status_events']),1)
        self.assertEqual([v for k,v in self.calls if k=='flash'],['test.bin','restore.bin'])
        self.assertEqual(self.calls.count(('command','param 0 440')),1)

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


    def enable_xiao(self):
        self.board = 'xiao'
        self.running_defaults = True
        self.volume = self.original_volume = 50
        description = json.loads((self.prepared / 'description.json').read_text())
        for param in description['parameters']:
            param['initialValue'] = self.values[param['index']]
        raw = json.dumps(description).encode()
        (self.prepared / 'description.json').write_bytes(raw)
        manifest = {'format': 'prepared-test', 'source_tree_sha256': 'a' * 64}
        (self.prepared / 'manifest.json').write_text(json.dumps(manifest))
        for directory, label in ((self.test, 'test'), (self.restore, 'restore')):
            app = directory / (label + '.bin')
            app.write_bytes(b'\xe9\x00\x00\x30' + label.encode())
            path = directory / 'build-report.json'
            report = json.loads(path.read_text())
            report.update(board='xiao', initial_volume_percent=50)
            report['artifacts'][str(app.relative_to(self.root))] = {'bytes': app.stat().st_size, 'sha256': runner.sha(app)}
            if label == 'restore':
                report['prepared_export'] = {'manifest': manifest, 'provenance': {
                    'prepared_files_sha256': {'description.json': hashlib.sha256(raw).hexdigest()}}}
            path.write_text(json.dumps(report))
        with self.backup.open('wb') as output:
            output.truncate(0x800000)
            output.seek(0x8000)
            output.write((self.restore / 'partition_table/partition-table.bin').read_bytes())
        (self.backup.parent / 'backup.json').write_text(json.dumps({
            'device_mac': self.device, 'backup_sha256': runner.sha(self.backup),
            'backup_bytes': 0x800000, 'application_write_offset': 0x10000}))

    def test_xiao_auto_start_defaults_restore_without_parameter_replay(self):
        self.enable_xiao()
        result = self.run_case()
        self.assertEqual(result['result'], 'passed')
        self.assertEqual(result['board'], 'xiao')
        self.assertEqual(result['flash_bytes'], 0x800000)
        self.assertEqual(result['restore_policy'], 'running-defaults-startup50')
        self.assertEqual(self.volume, 50)
        self.assertFalse(self.panic)
        self.assertFalse(any(k == 'command' and v.startswith('param ') for k, v in self.calls))
        self.assertTrue(result['restoration']['parameter_readback_available'])

    def test_xiao_failed_flash_restores_running_defaults(self):
        self.enable_xiao()
        self.flash_failure = True
        result = self.run_case()
        self.assertEqual(result['result'], 'failed')
        self.assertEqual(result['restoration']['result'], 'restored')
        self.assertEqual(self.volume, 50)
        self.assertFalse(self.panic)

    def test_xiao_changed_parameter_rejected_before_mutation(self):
        self.enable_xiao()
        self.values[0] = 333
        with self.assertRaisesRegex(RuntimeError, 'differ from compiled'):
            self.run_case()
        self.assertFalse(any(k == 'flash' or v.startswith('volume ') or v == 'panic' for k, v in self.calls))

    def test_xiao_audible_restore_cannot_bypass_explicit_defaults_mode(self):
        self.enable_xiao()
        self.running_defaults = False
        with self.assertRaisesRegex(ValueError, 'explicit --restore-running-defaults'):
            self.run_case()
        self.assertFalse(self.calls)

    def test_xiao_wrong_startup_volume_rejected_before_mutation(self):
        self.enable_xiao()
        self.volume = 25
        with self.assertRaisesRegex(RuntimeError, 'startup50'):
            self.run_case()
        self.assertFalse(any(k == 'flash' for k, _ in self.calls))

    def test_xiao_bad_restored_defaults_fail_and_mute(self):
        self.enable_xiao()
        self.bad_readback = True
        result = self.run_case()
        self.assertEqual(result['result'], 'failed')
        self.assertEqual(result['restoration']['result'], 'failed')
        self.assertEqual(self.volume, 0)
        self.assertTrue(self.panic)

    def test_xiao_restored_dma_fault_fail_and_mute(self):
        self.enable_xiao()
        self.bad_fault_after_flash = True
        result = self.run_case()
        self.assertEqual(result['result'], 'failed')
        self.assertIn('dma_errors', result['restoration']['error'])
        self.assertEqual(self.volume, 0)

    def test_pass_elf_identity_suffix_is_rejected_and_restored(self):
        self.pass_identity_suffix = 'suffix'
        result = self.run_case()
        self.assertEqual(result['result'], 'failed')
        self.assertEqual(result['restoration']['result'], 'restored')

    def test_duplicate_pass_elf_identity_is_rejected_and_restored(self):
        self.duplicate_pass_identity = True
        result = self.run_case()
        self.assertEqual(result['result'], 'failed')
        self.assertEqual(result['restoration']['result'], 'restored')

    def test_failure_precedes_pass_in_same_usb_read(self):
        self.fail_log = True
        result = self.run_case()
        self.assertEqual(result['result'], 'failed')
        self.assertIn('reported a fault', result['error'])
        self.assertEqual(result['restoration']['result'], 'restored')

    def test_duplicate_usb_identity_never_writes(self):
        self.duplicate_usb = True
        with self.assertRaisesRegex(RuntimeError, 'Multiple USB'):
            self.run_case()
        self.assertFalse(self.calls)

    def test_cross_board_build_never_writes(self):
        self.enable_xiao()
        path = self.test / 'build-report.json'
        report = json.loads(path.read_text());report['board'] = 'amoled'
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'selected xiao'):
            self.run_case()
        self.assertFalse(self.calls)

    def test_mislabeled_executable_flash_size_never_writes(self):
        self.enable_xiao()
        path = self.test / 'test.bin'
        path.write_bytes(b'\xe9\x00\x00\x40test')
        report_path = self.test / 'build-report.json'
        report = json.loads(report_path.read_text())
        report['artifacts'][str(path.relative_to(self.root))] = {'bytes': path.stat().st_size, 'sha256': runner.sha(path)}
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'flash size'):
            self.run_case()
        self.assertFalse(self.calls)

    def test_conflicting_backup_identity_never_writes(self):
        self.enable_xiao()
        path = self.backup.parent / 'backup.json'
        report = json.loads(path.read_text());report['mac'] = '11:22:33:44:55:66'
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'backup does not match'):
            self.run_case()
        self.assertFalse(self.calls)


class LiveParameterBoundsTests(unittest.TestCase):
    schema={'feedback':{'index':0,'minimum':0.1,'maximum':0.99}}

    def read(self,value):
        transport=types.SimpleNamespace(request=lambda command:{'parameters':[{'index':0,'actual':value}]})
        return runner.live_parameters(transport,self.schema)

    def test_decimal_readback_round_trips_both_float32_endpoints(self):
        for value in (0.1,0.99):
            actual=struct.unpack('<f',struct.pack('<f',value))[0]
            serialized=float(f'{actual:.9g}')
            self.assertEqual(self.read(serialized)['feedback']['actual'],serialized)

    def test_adjacent_float32_values_outside_range_are_rejected(self):
        for bound,step in ((0.1,-1),(0.99,1)):
            bits=struct.unpack('<I',struct.pack('<f',bound))[0]
            outside=struct.unpack('<f',struct.pack('<I',bits+step))[0]
            with self.assertRaisesRegex(ValueError,'outside'):
                self.read(float(f'{outside:.9g}'))

    def test_finite_double_overflow_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Float32'):
            self.read(1e300)


if __name__ == "__main__":
    unittest.main()
