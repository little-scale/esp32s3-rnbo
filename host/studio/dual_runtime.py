# SPDX-License-Identifier: MIT
"""Studio admission for existing 44.1k/native-16k XIAO SC/RNBO pairs."""
from collections import OrderedDict
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

from host.studio.device import ROOT, DeviceError, idf_python, mac


def companion_root():
    explicit = os.environ.get('SYNTHDEF_PROJECT_ROOT')
    candidates = [Path(explicit).expanduser()] if explicit else [
        ROOT.parent/'WaveShareAmoled18-synthdef', ROOT.parent/'esp32s3-synthdef']
    for path in candidates:
        if all((path/'host'/name).is_file() for name in ('dual_apps.py', 'dual_upload.py')):
            return path.resolve()
    raise ValueError('Install the companion SynthDef checkout, or set SYNTHDEF_PROJECT_ROOT; its verified pairing inventory is required')


class PairedXiao:
    def __init__(self, bridge, *, runner=subprocess.run, clock=time.monotonic):
        self.bridge, self.runner, self.clock = bridge, runner, clock
        self.inspections = OrderedDict()

    def run(self, action, **values):
        project = companion_root()
        command = [str(idf_python()), '-I', '-B', str(ROOT/'host/studio/paired_helper.py'),
                   str(project), str(ROOT), json.dumps(dict(action=action, **values))]
        try:
            result = self.runner(command, cwd=ROOT, env=dict(os.environ, RNBO_PROJECT_ROOT=str(ROOT)),
                                 capture_output=True, text=True, timeout=360)
        except subprocess.TimeoutExpired as error:
            raise DeviceError('Paired operation timed out; it was not retried. Inspect the device and retain its recovery receipts.') from error
        if result.returncode:
            raise DeviceError(result.stderr[-4000:].strip() or 'Paired operation failed; it was not retried')
        try:
            value = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as error:
            raise DeviceError('The paired tool returned no verifiable result') from error
        if type(value) is not dict:
            raise DeviceError('Invalid paired tool reply')
        return value

    def options(self, rate=16000):
        if type(rate) is not int or rate not in (16000,44100):
            raise ValueError('Choose 16000 or 44100 Hz for the XIAO pair')
        try:
            from tools.build_firmware import source_inventory
            from tools.run_hardware_test import artifacts
            directory = 'build/firmware-xiao-player-dual-native16' if rate==16000 else 'build/firmware-xiao-player'
            report = artifacts(ROOT/directory, 'xiao')['report']
            if (report.get('integration_files_sha256') != source_inventory() or
                    report.get('profile') != ('voice-pe-16000-256-v1' if rate==16000 else 'esp32s3-44100-256-v1') or report.get('sample_rate') != rate):
                raise ValueError('Rebuild the current XIAO player at the selected rate before updating')
            return self.run('options',rate=rate)
        except (ValueError, RuntimeError, OSError, KeyError) as error:
            return dict(available=False, reason=str(error)[:1000])

    def target(self, port):
        row = self.bridge._select(port)
        if row['vid'] != 0x303a:
            raise DeviceError('Select the XIAO native USB port with its permanent MAC')
        return dict(port=row['port'], mac=mac(row['serial_number']))

    def inspect(self, port):
        with self.bridge._exclusive():
            target = self.target(port)
            self.bridge.disconnect()
            reply = self.run('inspect', target=target)
        token = secrets.token_hex(24)
        self.inspections[token] = (self.clock(), target, reply)
        while len(self.inspections) > 8:
            self.inspections.popitem(last=False)
        return dict(reply, inspection=token, port=target['port'])

    def perform(self, token, port, action, *, rate, **values):
        record = self.inspections.pop(token, None)
        if not record or self.clock()-record[0] > 600:
            raise DeviceError('Inspect this XIAO pair again before using it')
        _, target, prior = record
        if type(rate) is not int or rate != prior['rate']:
            raise DeviceError('The reviewed pair rate changed; inspect again')
        with self.bridge._exclusive():
            if self.target(port) != target:
                raise DeviceError('The inspected USB device changed; no operation started')
            self.bridge.disconnect()
            return self.run(action, target=target, expected_engine=prior['engine'], rate=rate, **values)
