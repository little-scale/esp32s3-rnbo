# SPDX-License-Identifier: MIT
"""Portable fake-USB tests. No enumeration, serial open or real tool execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('studio_device_tested', Path(__file__).with_name('device.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class Clock:
    def __init__(self): self.now = 0.
    def time(self): return self.now
    def sleep(self, seconds): self.now += seconds


class Device:
    def __init__(self):
        self.firmware = 'a' * 64
        self.source = 'b' * 64
        self.frames = 1024
        self.volume = 50
        self.panic = False
        self.parameters = [dict(index=0, actual=50., normalized=.5)]
        self.schema = ['parameter 0 id=cutoff name=Cut Off unit=Hz min=0 max=100 default=50']
        self.commands = []
        self.bad = {}
        self.neutral = False
        self.quantize = False
        self.fault = False
        self.ignore_parameter = False
        self.freeze_frames = False
        self.rebuilding = False
        self.queue_errors = 0
        self.error_on_parameter = False
        self.pause_ready_polls = 0
        self.uptime = 100000

    def response(self, command):
        self.commands.append(command)
        if command in self.bad:
            return self.bad[command]
        if command == 'status':
            if not self.freeze_frames: self.frames += 256
            value = dict(runtime='rnbo-esp32s3-bringup', board='XIAO ESP32-S3',
                         source='engine-neutral-stereo-tone' if self.neutral else 'rnbo-static-module',
                         module_source_sha256='none' if self.neutral else self.source,
                         firmware_elf_sha256=self.firmware, rate=44100, block_frames=256,
                         channels=2, frames=self.frames, panic=self.panic, volume=self.volume,
                         uptime_us=self.uptime,
                         rebuilding=self.rebuilding, ready_to_resume=self.panic, allocation_fault=self.fault,
                         reconstruction_failed=False)
            value.update({key: 0 for key in d.FAULT_COUNTERS})
            value['queue_errors'] = self.queue_errors
            if self.panic and self.pause_ready_polls:
                self.pause_ready_polls -= 1
                value['ready_to_resume'] = False
        elif command == 'parameters':
            return ('\n'.join(self.schema) + ('\n' if self.schema else '')).encode()
        elif command == 'parameter-values':
            value = dict(parameters=self.parameters)
        elif command == 'panic':
            self.panic = True; value = dict(panic=True)
        elif command == 'resume':
            self.panic = False; value = dict(resume_requested=True)
        elif command.startswith('volume '):
            self.volume = int(command.split()[1]); value = dict(volume=self.volume, accepted=True)
        elif command.startswith('normalized '):
            _, index, v = command.split(); v = float(v)
            if self.quantize: v = round(v * 4) / 4
            if not self.ignore_parameter:
                self.parameters[int(index)].update(actual=v * 100, normalized=v)
            if self.error_on_parameter: self.queue_errors += 1
            value = dict(queued=True)
        else:
            value = dict(error='unsupported command')
        return (json.dumps(value) + '\n').encode()


class Serial:
    def __init__(self, device, clock):
        self.device = device; self.clock = clock; self.buffer = bytearray(); self.closed = False
    @property
    def in_waiting(self): return len(self.buffer)
    def write(self, payload):
        if self.closed: raise OSError('closed')
        for command in payload.decode('ascii').splitlines():
            self.buffer.extend(self.device.response(command))
        return len(payload)
    def read(self, count):
        if self.closed: raise OSError('closed')
        self.clock.sleep(.02)
        data = bytes(self.buffer[:count]); del self.buffer[:count]
        return data
    def close(self): self.closed = True


def usb(serial='001122334455', port='/dev/test-esp', vid=0x303A):
    return SimpleNamespace(device=port, serial_number=serial, vid=vid, pid=0x1001,
                           location='usb:1', description='Test ESP32-S3')


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock(); self.device = Device(); self.streams = []; self.ports = [usb()]
        def open_fake(port, baud, timeout):
            self.assertEqual((port, baud), ('/dev/test-esp', 115200))
            stream = Serial(self.device, self.clock); self.streams.append(stream); return stream
        self.bridge = d.DeviceBridge(ports=lambda: self.ports, opener=open_fake,
                                     clock=self.clock.time, sleep=self.clock.sleep)

    def test_disconnected_get_does_not_enumerate_or_open_even_when_busy(self):
        bridge = d.DeviceBridge(ports=lambda: self.fail('unexpected enumeration'),
                                opener=lambda *a: self.fail('unexpected serial open'))
        self.assertEqual(bridge.snapshot(), dict(device=None, parameters=[]))
        self.assertEqual(self.streams, [])

    def test_scan_is_ESP_only_and_does_not_open(self):
        self.ports += [usb(port='/dev/other', vid=0x1234)]
        self.assertEqual(self.bridge.scan(), [dict(port='/dev/test-esp', label='Test ESP32-S3', serial_number='001122334455')])
        self.assertEqual(self.streams, [])
        with self.assertRaises(d.DeviceError): self.bridge.connect('/dev/arbitrary')

    def test_connect_discovers_space_names_and_normalizes_board(self):
        result = self.bridge.connect('/dev/test-esp')
        self.assertEqual(result['device']['board'], 'xiao')
        self.assertEqual(result['device']['board_model'], 'XIAO ESP32-S3')
        self.assertEqual(result['parameters'], [dict(index=0, name='Cut Off', min=0., max=100., initial=50., actual=50., normalized=.5)])
        self.assertIn('parameters', self.device.commands)
        self.bridge.disconnect(); self.assertTrue(self.streams[-1].closed)

    def test_controls_use_only_reviewed_protocol_and_return_actual_quantized_values(self):
        self.bridge.connect('/dev/test-esp')
        self.assertEqual(self.bridge.control(dict(action='volume', value=7))['device']['volume'], 7)
        self.assertTrue(self.bridge.control(dict(action='pause'))['device']['panic'])
        self.assertFalse(self.bridge.control(dict(action='resume'))['device']['panic'])
        self.device.quantize = True
        result = self.bridge.control(dict(action='param', index=0, value=.3))
        self.assertEqual(result['parameters'][0]['normalized'], .25)
        self.assertEqual(result['control']['observed_normalized'], .25)
        self.assertFalse(result['control']['exact_application_verified'])
        self.assertTrue(any(command.startswith('normalized 0 ') for command in self.device.commands))
        self.assertNotIn('pause', self.device.commands)

    def test_invalid_payloads_do_not_send_commands(self):
        self.bridge.connect('/dev/test-esp'); before = list(self.device.commands)
        bad = [dict(action='raw', command='erase'), dict(action='pause', extra=1),
               dict(action='volume', value=True), dict(action='volume', value=1.5),
               dict(action='volume', value=10 ** 1000),
               dict(action='volume', value=101), dict(action='param', index=True, value=.5),
               dict(action='param', index=99, value=.5), dict(action='param', index=0, value=float('nan')),
               dict(action='param', index=0, value=1.01)]
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(ValueError): self.bridge.control(payload)
        self.assertEqual(self.device.commands, before)

    def test_queued_parameter_is_truthfully_readback_not_exact_application(self):
        self.bridge.connect('/dev/test-esp'); self.device.ignore_parameter = True
        result = self.bridge.control(dict(action='param', index=0, value=.75))
        self.assertEqual(result['control']['requested_normalized'], .75)
        self.assertEqual(result['control']['observed_normalized'], .5)
        self.assertEqual(result['control']['confirmation'], 'queued-and-post-block-readback')
        self.assertFalse(result['control']['exact_application_verified'])

    def test_runtime_fault_after_parameter_queue_is_not_success(self):
        self.bridge.connect('/dev/test-esp'); self.device.error_on_parameter = True
        with self.assertRaisesRegex(d.DeviceError, 'counter changed'):
            self.bridge.control(dict(action='param', index=0, value=.75))

    def test_pause_waits_for_detached_reconstruction_ready_to_resume(self):
        self.bridge.connect('/dev/test-esp'); self.device.pause_ready_polls = 3
        result = self.bridge.control(dict(action='pause'))
        self.assertTrue(result['device']['ready_to_resume'])
        self.assertEqual(self.device.pause_ready_polls, 0)

    def test_firmware_change_prevents_control_and_closes_on_snapshot(self):
        self.bridge.connect('/dev/test-esp'); self.device.firmware = 'c' * 64
        with self.assertRaisesRegex(d.DeviceError, 'firmware changed'):
            self.bridge.control(dict(action='volume', value=12))
        self.assertNotIn('volume 12', self.device.commands)
        with self.assertRaises(d.DeviceError): self.bridge.snapshot()
        self.assertTrue(self.streams[-1].closed)

    def test_complete_error_malformed_JSON_and_size_limits_are_not_skipped(self):
        for response in (b'{"error":"invalid command or capture state"}\n', b'{broken}\n', b'x' * (d.MAX_LINE + 1)):
            with self.subTest(response=response[:30]):
                self.device.bad['status'] = response
                with self.assertRaises(d.DeviceError): self.bridge.connect('/dev/test-esp')
                self.assertTrue(self.streams[-1].closed)

    def test_fatal_UART_preceding_healthy_JSON_rejects_and_disconnects(self):
        for marker in d.FATAL_MARKERS:
            with self.subTest(marker=marker):
                self.device.bad.clear(); self.bridge.connect('/dev/test-esp')
                healthy = self.device.response('status')
                self.device.bad['status'] = marker + b'\n' + healthy
                with self.assertRaisesRegex(d.DeviceError, 'fatal UART'): self.bridge.snapshot()
                self.assertTrue(self.streams[-1].closed)
                self.assertIsNone(self.bridge._stream)

    def test_restarted_frame_position_or_uptime_rejects_same_ELF_session(self):
        for field in ('frames', 'uptime'):
            with self.subTest(field=field):
                self.bridge.connect('/dev/test-esp')
                setattr(self.device, field, 0)
                with self.assertRaisesRegex(d.DeviceError, 'backwards'): self.bridge.snapshot()
                self.assertTrue(self.streams[-1].closed)
                self.device.frames = 1024; self.device.uptime = 100000

    def test_command_free_boot_fault_rejects_even_if_later_status_healthy(self):
        def opening(*args):
            stream = Serial(self.device, self.clock)
            stream.buffer.extend(b'Guru Meditation Error: Core 0 panic\n')
            self.streams.append(stream)
            return stream
        self.bridge._opener = opening
        with self.assertRaisesRegex(d.DeviceError, 'fatal UART'):
            self.bridge.connect('/dev/test-esp')
        self.assertTrue(self.streams[-1].closed)
        self.assertEqual(self.device.commands, [])

    def test_schema_mismatch_and_nonfinite_parameter_reject(self):
        self.device.schema = []
        with self.assertRaises(d.DeviceError): self.bridge.connect('/dev/test-esp')
        self.device.schema = ['parameter 0 id=x name=X unit= min=0 max=1 default=0']
        self.device.parameters[0]['actual'] = 1e300
        with self.assertRaises(d.DeviceError): self.bridge.connect('/dev/test-esp')

    def test_neutral_runtime_has_no_static_parameter_commands(self):
        self.device.neutral = True
        result = self.bridge.connect('/dev/test-esp')
        self.assertEqual(result['parameters'], [])
        self.assertNotIn('parameter-values', self.device.commands)


class FakeTool:
    def __init__(self, test):
        self.test = test; self.commands = []; self.image = None
        self.chip = 'ESP32-S3'; self.size = 8; self.fail = None
        self.partition = test.table + b'\xff' * (4096 - len(test.table))
        self.corrupt_readback = False; self.change_after_backup = False
        self.replace_after_partition = False; self.boot_wrong = False; self.on_write = None

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        self.test.assertIsInstance(command, list)
        self.test.assertNotIn('shell', kwargs)
        self.test.assertLessEqual(kwargs['timeout'], 180)
        index = command.index('watchdog_reset') + 1
        op, args = command[index], command[index + 1:]
        text = f'Chip is {self.chip} (revision v0.2)\nMAC: 00:11:22:33:44:55\nDetected flash size: {self.size}MB\n'.encode()
        if self.fail == op:
            return subprocess.CompletedProcess(command, 2, stdout=text + b'failure\n')
        if op == 'read_flash':
            address, count, target = int(args[0], 16), int(args[1], 16), Path(args[2])
            if address == d.PARTITION_OFFSET:
                target.write_bytes(self.partition)
                if self.replace_after_partition and target.name == 'partition-prewrite.bin':
                    self.test.ports[:] = [usb('aabbccddeeff')]
            else:
                self.test.assertEqual(address, d.APP_OFFSET)
                if target.name == 'original-application-3MiB.bin':
                    self.test.assertEqual(count, d.APP_CAPACITY)
                    target.write_bytes(b'\xe9\0\0\x30' + b'O' * (count - 4))
                    if self.change_after_backup: self.test.app.write_bytes(b'changed')
                else:
                    data = self.image[:count]
                    if self.corrupt_readback: data = bytes([data[0] ^ 1]) + data[1:]
                    target.write_bytes(data)
        elif op == 'write_flash':
            self.test.assertEqual(args[0], '0x10000')
            if self.on_write: self.on_write()
            self.image = Path(args[1]).read_bytes()
            if not self.boot_wrong: self.test.device.firmware = self.test.elf_hash
        else:
            self.test.assertEqual(op, 'flash_id')
        return subprocess.CompletedProcess(command, 0, stdout=text)


class FlashTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name).resolve()
        self.build = self.root / 'build/instrument'; self.build.mkdir(parents=True)
        self.app = self.build / 'application.bin'; self.app.write_bytes(b'\xe9\0\0\x30' + b'N' * 124)
        elf = self.build / 'application.elf'; elf.write_bytes(b'test-only compiled artifact')
        self.elf_hash = d.sha(elf)
        self.table = struct.pack('<HBBII16sI', 0x50aa, 0, 0, 0x10000, 0x300000, b'factory', 0) + b'\xff' * (3072 - 32)
        partition = self.build / 'partition-table.bin'; partition.write_bytes(self.table)
        inventory = {str(p.relative_to(self.root)): dict(bytes=p.stat().st_size, sha256=d.sha(p)) for p in (self.app, elf, partition)}
        report = dict(board='xiao', initial_volume_percent=50, artifacts=inventory, prepared_export=dict(manifest=dict(source_tree_sha256='b' * 64, parameter_count=1)))
        (self.build / 'build-report.json').write_text(json.dumps(report))
        self.python = self.root / 'idf-python'; self.python.write_text('fake executable boundary')
        self.clock = Clock(); self.device = Device(); self.ports = [usb()]; self.streams = []
        self.runner = FakeTool(self); self.log = []
        self.root_patch = patch.object(d, 'ROOT', self.root); self.root_patch.start()
        # Use the REAL artifact validator against this isolated fake build tree.
        self.artifact_patch = patch.dict(d.artifacts.__globals__, ROOT=self.root); self.artifact_patch.start()
        def open_fake(*args):
            stream = Serial(self.device, self.clock); self.streams.append(stream); return stream
        self.bridge = d.DeviceBridge(ports=lambda: self.ports, opener=open_fake, runner=self.runner,
            clock=self.clock.time, sleep=self.clock.sleep, private_root=self.root / 'uploads', python=self.python)

    def tearDown(self):
        self.artifact_patch.stop(); self.root_patch.stop(); self.temporary.cleanup()

    def upload(self): return self.bridge.flash(self.build, 'xiao', '/dev/test-esp', self.log.append)
    def receipt(self): return json.loads(next((self.root / 'uploads').glob('*/receipt.json')).read_bytes())
    def operations(self): return [cmd[cmd.index('watchdog_reset') + 1] for cmd in self.runner.commands]

    def test_app_only_backup_readback_identity_and_receipt(self):
        result = self.upload(); self.assertEqual(result['device']['firmware_elf_sha256'], self.elf_hash)
        receipt = self.receipt(); self.assertEqual(receipt['result'], 'completed')
        self.assertTrue(receipt['readback_verified']); self.assertTrue(receipt['connected_identity_verified'])
        self.assertEqual(Path(receipt['backup']['path']).stat().st_size, 0x300000)
        self.assertEqual(d.sha(Path(receipt['backup']['path'])), receipt['backup']['sha256'])
        self.assertEqual(self.operations(), ['flash_id', 'read_flash', 'read_flash', 'flash_id', 'read_flash', 'write_flash', 'read_flash'])
        self.assertEqual(self.runner.image, self.app.read_bytes())
        self.assertFalse(self.bridge._flashing.is_set())

    def test_mismatched_partition_never_writes_or_erases(self):
        self.runner.partition = b'bad' + self.runner.partition[3:]
        with self.assertRaisesRegex(d.DeviceError, 'partition layout'): self.upload()
        self.assertNotIn('write_flash', self.operations()); self.assertNotIn('erase_flash', self.operations())
        self.assertFalse(self.receipt()['write_attempted'])

    def test_wrong_chip_or_flash_size_reject_before_memory_access(self):
        for field, value in (('chip', 'ESP32-S2'), ('size', 16)):
            setattr(self.runner, field, value)
            with self.assertRaises(d.DeviceError): self.upload()
            self.assertEqual(self.operations()[-1], 'flash_id')
            setattr(self.runner, field, 'ESP32-S3' if field == 'chip' else 8)
        self.assertNotIn('read_flash', self.operations())

    def test_artifact_mutation_after_backup_stops_before_write(self):
        self.runner.change_after_backup = True
        with self.assertRaises(ValueError): self.upload()
        self.assertNotIn('write_flash', self.operations())
        self.assertIn('backup', self.receipt())

    def test_device_replaced_at_same_port_cannot_be_written(self):
        self.runner.replace_after_partition = True
        with self.assertRaisesRegex(d.DeviceError, 'did not reconnect'): self.upload()
        self.assertNotIn('write_flash', self.operations())

    def test_readback_mismatch_retains_backup_and_does_not_connect(self):
        self.runner.corrupt_readback = True
        with self.assertRaisesRegex(d.DeviceError, 'readback differs'): self.upload()
        receipt = self.receipt(); self.assertTrue(receipt['write_attempted'])
        self.assertFalse(receipt['readback_verified']); self.assertEqual(receipt['result'], 'failed')
        self.assertEqual(self.streams, [])

    def test_wrong_running_firmware_is_not_an_upload_success(self):
        self.runner.boot_wrong = True
        with self.assertRaisesRegex(d.DeviceError, 'firmware changed'): self.upload()
        self.assertFalse(self.receipt()['connected_identity_verified'])
        self.assertTrue(self.streams[-1].closed)

    def test_tool_error_cleans_up_and_keeps_recovery_material(self):
        self.runner.fail = 'write_flash'
        with self.assertRaises(d.DeviceError): self.upload()
        receipt = self.receipt(); self.assertEqual(receipt['result'], 'failed'); self.assertIn('backup', receipt)
        self.assertFalse(self.bridge._flashing.is_set()); self.assertEqual(self.bridge.snapshot(), dict(device=None, parameters=[]))

    def test_poll_and_control_do_not_race_upload(self):
        def during_write():
            self.assertEqual(self.bridge.snapshot(), dict(device=None, parameters=[], busy=True))
            with self.assertRaisesRegex(d.DeviceError, 'upload'): self.bridge.control(dict(action='pause'))
        self.runner.on_write = during_write
        self.upload()

    def test_invalid_artifact_fails_before_device_enumeration(self):
        self.app.write_bytes(b'changed')
        self.bridge._ports = lambda: self.fail('must validate artifact before enumeration')
        with self.assertRaises(ValueError): self.upload()
        self.assertEqual(self.runner.commands, [])

    def test_compiled_parameter_count_and_startup_volume_preflight_before_USB(self):
        report_path = self.build / 'build-report.json'
        original = json.loads(report_path.read_text())
        self.bridge._ports = lambda: self.fail('preflight must precede enumeration')
        for count in (None, True, 33, -1):
            report = json.loads(json.dumps(original))
            report['prepared_export']['manifest']['parameter_count'] = count
            report_path.write_text(json.dumps(report))
            with self.subTest(count=count), self.assertRaises(d.DeviceError): self.upload()
        report = json.loads(json.dumps(original)); report['initial_volume_percent'] = 101
        report_path.write_text(json.dumps(report))
        with self.assertRaises(d.DeviceError): self.upload()
        self.assertEqual(self.runner.commands, [])

    def test_uploaded_identity_alone_is_not_running_audio_readiness(self):
        for field, value in (('freeze_frames', True), ('panic', True), ('rebuilding', True), ('volume', 0)):
            with self.subTest(field=field):
                setattr(self.device, field, value)
                with self.assertRaisesRegex(d.DeviceError, 'running audio'):
                    self.upload()
                self.assertFalse(self.bridge._flashing.is_set())
                self.assertIsNone(self.bridge._stream)
                setattr(self.device, field, False if field != 'volume' else 50)

    def test_postflash_fault_and_parameter_schema_mismatch_reject(self):
        self.device.fault = True
        with self.assertRaisesRegex(d.DeviceError, 'runtime allocation'): self.upload()
        self.device.fault = False
        self.device.parameters = []; self.device.schema = []
        with self.assertRaisesRegex(d.DeviceError, 'parameter count'): self.upload()


if __name__ == '__main__':
    unittest.main()
