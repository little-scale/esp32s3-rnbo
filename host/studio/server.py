#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Local RNBO patch compiler and USB studio. Run from any working directory."""
from __future__ import annotations
import argparse
import base64
import binascii
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from host.compiler import package as player_package
from host import native_export
from host.visual.layout import compile_layout
from host.studio.trial import BLOCKS as TRIAL_BLOCKS, compare_audio as compare_trial_audio, device_check as trial_device_check
WEB = Path(__file__).parent / 'web'
PRIVATE = ROOT / 'build/private/studio'
MAX_PATCH = 1024 * 1024
MAX_BODY = 48 * 1024 * 1024
MAX_PACKAGE = 128 + player_package.MAX_METADATA + player_package.MAX_ELF

def encoded(value):
    return json.dumps(value, allow_nan=False).encode()

def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False

def package_preview(value):
    """Return only the bounded display subset; malformed visuals never reject DSP."""
    fallback = {'available': False}
    if (type(value) is not dict or value.get('format') != 'rnbo-s3-visual-v1'
            or value.get('available') is not True or value.get('width') != 336 or value.get('height') != 232):
        return fallback
    nodes, segments, parameters = (value.get(key) for key in ('nodes', 'segments', 'parameters'))
    if (type(nodes) is not list or not 1 <= len(nodes) <= 96 or type(segments) is not list
            or len(segments) > 384 or type(parameters) is not list or len(parameters) > 32):
        return fallback
    labels = []
    for parameter in parameters:
        if type(parameter) is not dict or not isinstance(parameter.get('name'), str):
            return fallback
        labels.append({'name': parameter['name'][:95]})
    clean_nodes = []
    for node in nodes:
        if (type(node) is not dict or not isinstance(node.get('label'), str)
                or any(type(node.get(key)) is not int for key in ('x', 'y', 'width', 'height', 'parameter'))):
            return fallback
        x, y, width, height, parameter = (node[key] for key in ('x', 'y', 'width', 'height', 'parameter'))
        if (not 0 <= x < 336 or not 0 <= y < 232 or not 1 <= width <= 336 - x
                or not 1 <= height <= 232 - y or parameter != 255 and not 0 <= parameter < len(labels)):
            return fallback
        clean_nodes.append(dict(x=x, y=y, width=width, height=height, parameter=parameter, label=node['label'][:31]))
    clean_segments = []
    for segment in segments:
        if (type(segment) is not list or len(segment) != 4 or any(type(point) is not int for point in segment)
                or any(not 0 <= segment[index] < (336 if index % 2 == 0 else 232) for index in range(4))):
            return fallback
        clean_segments.append(list(segment))
    return dict(available=True, width=336, height=232, nodes=clean_nodes, segments=clean_segments, parameters=labels)

def kill_build_group(process):
    # The leader may already have exited while a compiler child holds stdout.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

def build_settings(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a patch and board settings')
    if 'patch' in data:
        raise ValueError(native_export.GUIDANCE)
    files, class_name = native_export.normalise(native_export.unpack(data))
    patch = data.get('visual_patch')
    if patch is None and 'source.rnbopat' in files:
        patch = json.loads(files['source.rnbopat'])
    if patch is not None and (not isinstance(patch, dict) or not isinstance(patch.get('patcher'), dict)
                              or len(encoded(patch)) > MAX_PATCH):
        raise ValueError('Optional patch drawing must be a .rnbopat object up to 1 MiB')
    name = data.get('name', 'RNBO Export')
    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        raise ValueError('Choose a short export name')
    name = name.replace('\\', '/').rsplit('/', 1)[-1]
    title = re.sub(r'\.zip$', '', name, flags=re.I).strip()[:64] or 'RNBO Patch'
    board = data.get('board', 'xiao')
    role = data.get('role', 'main')
    volume = data.get('initial_volume', 50)
    arena = data.get('arena_bytes', 1048576)
    if any(key in data for key in ('voices', 'filter_delay_max_ms', 'float32_delays', 'numerical_profile')):
        raise ValueError('Set voices and delay sizes in Max. Native exports use the baseline Float32 wrapper; importer optimisation profiles are retired.')
    if role != 'main':
        raise ValueError('The player accepts one Main patch with its effects included')
    if board not in ('xiao', 'amoled'):
        raise ValueError('Select XIAO or AMOLED V2')
    if type(volume) is not int or not 0 <= volume <= 100:
        raise ValueError('Startup volume must be 0–100%')
    if type(arena) is not int or arena not in (1048576, 2097152, 4194304):
        raise ValueError('Arena must be 1, 2 or 4 MiB')
    return dict(name=name, title=title, visual_patch=patch, export_files=files, class_name=class_name,
                board=board, role=role, initial_volume=volume, arena_bytes=arena)



class Studio:
    def __init__(self, components=None, bridge=None):
        if bridge is None:
            from device import DeviceBridge
            bridge = DeviceBridge()
        self.bridge = bridge
        from host.studio.network import PairingStore
        self.pairings = PairingStore(PRIVATE / 'pairings.json')
        self.active_bridge = bridge
        self.network_bridge = None
        self.last_wifi = {'supported': False, 'configured': False, 'connected': False, 'paired': False, 'ip': '', 'device_id': ''}
        self.components = Path(components).expanduser().resolve() if components else None
        self.jobs = {}
        self.lock = threading.RLock()
        self.worker = threading.Lock()
        self.job_thread = None
        self.active_process = None
        self.stopping = threading.Event()
        self.token = secrets.token_urlsafe(32)

    def _remember_wifi(self, snapshot):
        device = snapshot.get('device') or {}
        value = device.get('wifi')
        if type(value) is dict:
            self.last_wifi = {key:value.get(key) for key in ('supported','configured','connected','ip','device_id','error') if key in value}
            identity = self.last_wifi.get('device_id')
            if isinstance(identity, str) and re.fullmatch(r'[0-9a-f]{12}', identity):
                if self.last_wifi.get('connected') and self.last_wifi.get('ip'):
                    try: self.pairings.update_ip(identity,self.last_wifi['ip'])
                    except ValueError: self.last_wifi['error'] = 'Wireless control requires a private IPv4 network; USB remains available'
        return snapshot

    def device_snapshot(self):
        with self.lock:
            return self._remember_wifi(self.active_bridge.snapshot())

    def control_device(self, data):
        target = data.get('target')
        if (type(target) is not dict or set(target) != {'device_id','transport'}
                or target.get('transport') not in ('usb','wifi')
                or not isinstance(target.get('device_id'),str)):
            raise ValueError('Choose the connected player before sending controls')
        with self.lock:
            if self.worker.locked(): raise ValueError('Wait for the current build or upload before sending controls')
            device = self.active_bridge.snapshot().get('device') or {}
            if any(device.get(key) != target[key] for key in ('device_id','transport')):
                raise ValueError('The selected connection changed; send controls to the current player')
            return self._remember_wifi(self.active_bridge.control({k:v for k,v in data.items() if k!='target'}))

    def configure_midi(self, data):
        target=data.get('target')
        if (type(target) is not dict or set(target)!={'device_id','transport'}
                or target.get('transport') not in ('usb','wifi') or not isinstance(target.get('device_id'),str)
                or set(data)!={'target','mode'} or data['mode'] not in ('off','uart')):
            raise ValueError('Choose the connected player and MIDI input mode')
        with self.lock:
            if self.worker.locked():raise ValueError('Wait for the current build or upload before changing MIDI')
            device=self.active_bridge.snapshot().get('device') or {}
            if any(device.get(k)!=target[k] for k in ('device_id','transport')):
                raise ValueError('The selected player connection changed')
            return self._remember_wifi(self.active_bridge.configure_midi(data['mode']))

    def wifi_status(self):
        if not self.worker.locked():
            try:
                self.device_snapshot()
            except RuntimeError:
                pass  # Another ordinary status/control may own the device.
        result = dict(self.last_wifi)
        result['paired'] = any(p['id'] == result.get('device_id') for p in self.pairings.public_list())
        return dict(wifi=result, paired=self.pairings.public_list())

    def connect_usb(self, port):
        with self.lock:
            if self.worker.locked(): raise ValueError('Wait for the current build or upload')
            if self.network_bridge: self.network_bridge.disconnect()
            self.active_bridge = self.bridge
            return self._remember_wifi(self.bridge.connect(port))

    def connect_wifi(self, data, *, during_upload=False):
        from host.studio.network import NetworkBridge, validate_ip
        with self.lock:
            if self.worker.locked() and not during_upload:
                raise ValueError('Wait for the current build or upload')
            record = self.pairings.get(data.get('id'))
            address = validate_ip(data.get('ip') or record.get('ip'))
            self.bridge.disconnect()
            if self.network_bridge: self.network_bridge.disconnect()
            self.network_bridge = NetworkBridge(record)
            self.active_bridge = self.network_bridge
            return self._remember_wifi(self.network_bridge.connect_network(address))

    def scan_wifi(self):
        if self.active_bridge is not self.bridge:
            raise ValueError('Connect over USB before scanning nearby networks')
        if not self.worker.acquire(blocking=False): raise ValueError('Wait for the current build or upload')
        try: return self.bridge.scan_wifi()
        finally: self.worker.release()

    def setup_wifi(self, data):
        if self.active_bridge is not self.bridge:
            raise ValueError('Connect over USB before changing Wi-Fi settings')
        if not self.worker.acquire(blocking=False): raise ValueError('Wait for the current build or upload')
        try:
            before = self.bridge.snapshot().get('device') or {}
            identity = before.get('device_id')
            if not isinstance(identity,str) or not re.fullmatch(r'[0-9a-f]{12}',identity):
                raise ValueError('Connect the player over USB first')
            key = secrets.token_hex(32)
            snapshot = self.bridge.configure_wifi(data.get('ssid'),data.get('password'),key)
            value = (snapshot.get('device') or {}).get('wifi') or {}
            if value.get('device_id') != identity or not value.get('configured'):
                raise ValueError('The board did not confirm saved Wi-Fi settings')
            from host.studio.network import validate_ip
            address = ''
            if value.get('connected') and value.get('ip'):
                try: address = validate_ip(value['ip'])
                except ValueError: pass
            self.pairings.put(dict(id=identity,ip=address,keyhex=key,label=before.get('board_model') or before.get('board') or 'RNBO player'))
            self._remember_wifi(snapshot)
            return self.wifi_status()
        finally: self.worker.release()

    def forget_wifi(self):
        if self.active_bridge is not self.bridge:
            raise ValueError('Connect over USB before forgetting Wi-Fi')
        if not self.worker.acquire(blocking=False): raise ValueError('Wait for the current build or upload')
        try:
            before = self.bridge.snapshot().get('device') or {}
            snapshot = self.bridge.forget_wifi()
            if before.get('device_id'): self.pairings.remove(before['device_id'])
            self._remember_wifi(snapshot)
            return self.wifi_status()
        finally: self.worker.release()

    def environment(self):
        return dict(source='cycling74-minimal-export',
                    idf=(Path(os.environ.get('IDF_PATH', str(Path.home() / 'esp/esp-idf'))) / 'tools/idf.py').is_file(),
                    python_serial=importlib.util.find_spec('serial') is not None,
                    amoled_components=bool(self.components and self.components.is_dir()) or (ROOT / 'build/vendor-amoled').is_dir())

    def status(self):
        return dict(csrf=self.token, environment=self.environment(), busy=self.worker.locked())

    def job(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r'[0-9a-f]{32}', identity):
            raise ValueError('Invalid build identifier')
        with self.lock:
            if identity not in self.jobs:
                raise ValueError('This build is not available in the current Studio session; compile again')
            return json.loads(json.dumps({k:v for k,v in self.jobs[identity].items() if not k.startswith('_')}))

    def update(self, identity, **values):
        with self.lock:
            self.jobs[identity].update(values)

    def log(self, identity, text):
        with self.lock:
            row = self.jobs[identity]
            row['log'] = (row['log'] + text)[-200000:]

    def execute(self, identity, command, timeout=1200):
        self.log(identity, '\n' + ' '.join(str(s) for s in command[:2]) + '\n')
        with self.lock:
            if self.stopping.is_set():
                raise RuntimeError('Studio is shutting down')
            process = subprocess.Popen([str(s) for s in command], cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace', start_new_session=True)
            self.active_process = process
        expired = threading.Event()
        def stop():
            expired.set()
            kill_build_group(process)
        timer = threading.Timer(timeout, stop)
        timer.start()
        try:
            assert process.stdout
            output = ''
            for line in process.stdout:
                self.log(identity, line)
                output = (output + line)[-200000:]
            result = process.wait()
            if result or expired.is_set():
                raise RuntimeError('Build timed out' if expired.is_set() else 'Build failed; see compiler output below')
            return output
        finally:
            timer.cancel()
            kill_build_group(process)
            process.wait()
            process.stdout.close()
            with self.lock:
                if self.active_process is process:
                    self.active_process = None

    def close(self):
        self.stopping.set()
        with self.lock:
            process = self.active_process
            thread = self.job_thread
        if process is not None:
            kill_build_group(process)
            process.wait()
        # An in-progress flash finishes before releasing the process-wide
        # singleton lock. Interrupting a write halfway is not a safe shutdown.
        if thread is not None and thread is not threading.current_thread():
            thread.join()
        self.bridge.disconnect()
        if self.network_bridge: self.network_bridge.disconnect()

    def component_source(self):
        if self.components:
            return self.components
        # Reconstruct original collection names from our already pinned offline
        # cache. build_firmware.py independently verifies every tree before use.
        cached = ROOT / 'build/vendor-amoled'
        destination = PRIVATE / 'amoled-components'
        lock = json.loads((ROOT / 'firmware/dependencies.amoled.json').read_text())['components']
        for name in lock:
            normalized = name.split('__', 1)[1] if '__' in name and not name.startswith('waveshare__') else name
            source = cached / normalized
            if not source.is_dir():
                raise ValueError('AMOLED dependencies are missing. Start Studio with --components-from PATH to the pinned collection')
            target = destination / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, target)
        return destination

    def start_build(self, data):
        if self.stopping.is_set():
            raise ValueError('Studio is shutting down')
        settings = build_settings(data)
        environment = self.environment()
        if not environment['idf']:
            raise ValueError('Install ESP-IDF 5.5 before compiling the exported C++')
        with self.lock:
            if self.stopping.is_set():
                raise ValueError('Studio is shutting down')
            if not self.worker.acquire(blocking=False):
                raise ValueError('A build or upload is already running')
            identity = uuid.uuid4().hex
            self.jobs[identity] = dict(id=identity, state='queued', stage='Queued', log='', error=None, result=None,
                                       _settings=settings, _build=None)
            self.job_thread = threading.Thread(target=self.build, args=(identity, settings), daemon=True)
            self.job_thread.start()
        return self.job(identity)

    def build(self, identity, settings):
        directory = PRIVATE / identity
        try:
            directory.mkdir(parents=True, exist_ok=False)
            native_export.write(settings['export_files'], directory / 'export')
            (directory / 'settings.json').write_bytes(encoded({k:v for k,v in settings.items() if k not in ('export_files', 'visual_patch')}))
            self.update(identity, state='building', stage='Preparing Max Minimal Export')
            command = [sys.executable, ROOT / 'host/compiler/prepare.py', '--export', directory / 'export',
                       '--out', directory / 'prepared', '--class-name', settings['class_name'], '--role', settings['role'],
                       '--numerical-profile', 'float32-strict']
            self.execute(identity, command)
            manifest = json.loads((directory / 'prepared/manifest.json').read_text())
            trial = manifest.get('float32_trial')
            parameter_count = manifest.get('parameter_count')
            if type(parameter_count) is not int or not 0 <= parameter_count <= 32:
                raise ValueError('The player supports at most 32 input parameters')
            self.update(identity, stage='Checking default patch on this computer')
            self.execute(identity, [sys.executable, ROOT / 'host/compiler/build.py', '--export', directory / 'prepared',
                                    '--build-dir', directory / 'native'])
            render = [directory / 'native/rnbo_render', '--output', directory / 'preflight.wav',
                      '--blocks', str(TRIAL_BLOCKS if trial else 4), '--warmup', '4', '--seed', '305419896',
                      '--arena-bytes', str(settings['arena_bytes'])]
            if trial: render += ['--float-output', directory / 'preflight.f32']
            output = self.execute(identity, render, timeout=60)
            preflight = json.loads(output.strip().splitlines()[-1])
            if any(type(preflight.get(key)) is not int or preflight[key] != 0
                   for key in ('errors', 'invalid_samples', 'late_platform_allocations')):
                raise ValueError('The default patch did not pass its native startup screen')
            (directory / 'preflight.json').write_bytes(encoded(preflight))
            self.log(identity, 'Native startup screen passed; this does not prove dynamic target allocation safety.\n')
            comparison = None
            self.update(identity, stage='Compiling board-independent audio module')
            self.execute(identity, [sys.executable, ROOT / 'host/compiler/build_module.py', '--export', directory / 'prepared',
                                   '--build-dir', directory / 'module', '--max-arena-bytes', str(settings['arena_bytes'])])
            description = json.loads((directory / 'prepared/description.json').read_text())
            visual = compile_layout(settings['visual_patch'], description, settings['title'])
            if len(encoded(visual)) > 60000:
                visual = compile_layout(None, description, settings['title'])
            result = player_package.build(directory / 'module', directory / 'patch.rnbopkg',
                                          settings['title'].encode('utf-8')[:63].decode('utf-8', 'ignore'), settings['initial_volume'], visual)
            parameters = [dict(index=p['index'], name=p.get('name', p['paramId']), min=p['minimum'], max=p['maximum'],
                               initial=p.get('initialValue', p['minimum'])) for p in description.get('parameters', [])]
            result.update(kind='package', title=settings['title'], parameters=parameters, sample_rate=44100,
                          block_frames=256, package_bytes=result['bytes'], package_sha256=result['sha256'],
                          physical_inputs=result.get('metadata', {}).get('physical_inputs'),
                          float32_trial=trial, trial_comparison=comparison, trial_report_available=bool(trial),
                          preflight_scope='native default startup screen; not target allocation proof',
                          visual=package_preview(visual))
            self.update(identity, state='ready', stage='Package ready to load', result=result, _build=directory / 'patch.rnbopkg')
        except Exception as error:
            self.log(identity, '\n' + str(error) + '\n')
            self.update(identity, state='failed', stage='Build failed', error=str(error))
        finally:
            self.worker.release()

    def import_package(self, data):
        name, text = data.get('name'), data.get('package_base64')
        if (not isinstance(name, str) or not name.lower().endswith('.rnbopkg') or len(name) > 160
                or not isinstance(text, str) or not 0 < len(text) <= 4 * ((MAX_PACKAGE + 2) // 3)):
            raise ValueError('Open a bounded .rnbopkg file')
        try:
            raw = base64.b64decode(text, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError('The package encoding is invalid') from error
        if not 128 <= len(raw) <= MAX_PACKAGE:
            raise ValueError('The package exceeds the v1 size limit or is truncated')
        package = player_package.parse(raw)
        with self.lock:
            if self.stopping.is_set():
                raise ValueError('Studio is shutting down')
            if not self.worker.acquire(blocking=False):
                raise ValueError('A build or upload is already running')
            try:
                identity = uuid.uuid4().hex
                directory = PRIVATE / identity
                directory.mkdir(parents=True, mode=0o700, exist_ok=False)
                path = directory / 'patch.rnbopkg'
                path.write_bytes(raw)
                path.chmod(0o400)
                result = dict(kind='package', origin='imported', title=package['metadata']['name'],
                    role='main', sample_rate=44100, block_frames=256, arena_bytes=package['arena_bytes'],
                    package_bytes=len(raw), package_sha256=package['package_sha256'], elf_sha256=package['elf_sha256'],
                    physical_inputs=package['metadata'].get('physical_inputs'),
                    float32_trial=package['metadata'].get('float32_trial'), trial_report_available=False,
                    preflight_scope='Saved package validated; native startup screen not rerun',
                    visual=package_preview(package['metadata'].get('visual')))
                self.jobs[identity] = dict(id=identity, state='ready', stage='Saved package ready to load',
                    log='Saved package envelope, hashes and zero-import ELF validated. No rebuild.\n',
                    error=None, result=result, _build=path, _settings={'board':'xiao', 'role':'main'})
            finally:
                self.worker.release()
        return self.job(identity)

    def start_upload(self, data):
        if self.stopping.is_set():
            raise ValueError('Studio is shutting down')
        identity = data.get('id')
        self.job(identity)
        with self.lock:
            row = self.jobs[identity]
            if data.get('transport', 'usb') not in ('usb', 'wifi'):
                raise ValueError('Choose USB or Wi-Fi')
            if data.get('transport') == 'wifi' and row.get('result', {}).get('kind') != 'package':
                raise ValueError('Player firmware installation requires USB')
            if row['state'] not in ('ready', 'done') or not row['_build']:
                raise ValueError('Compile the patch successfully before uploading')
            build = row['_build']; board = row['_settings']['board']
            if self.stopping.is_set():
                raise ValueError('Studio is shutting down')
            if not self.worker.acquire(blocking=False):
                raise ValueError('A build or upload is already running')
            self.update(identity, state='uploading', stage='Checking USB board', error=None)
            self.job_thread = threading.Thread(target=self.upload, args=(identity, build, board, data.get('port'), data if data.get('transport') == 'wifi' else None), daemon=True)
            self.job_thread.start()
        return self.job(identity)

    def upload(self, identity, build, board, port, network=None):
        try:
            transport = self.bridge
            if network:
                self.connect_wifi({'id':network.get('device_id'),'ip':network.get('ip')},during_upload=True)
                transport = self.active_bridge
            else:
                if self.network_bridge: self.network_bridge.disconnect()
                self.active_bridge = self.bridge
            def progress(message):
                self.log(identity, str(message) + '\n')
                if str(message).startswith('USB: '):
                    self.update(identity, stage=str(message))
            if self.jobs[identity].get('result', {}).get('kind') == 'player':
                self.bridge.flash(build, board, port, progress, expected_kind='player')
            else:
                observed = transport.upload_package(build, port, progress, expected_sha256=self.jobs[identity]['result']['package_sha256'])
                result = self.job(identity).get('result', {})
                if result.get('float32_trial'):
                    check = trial_device_check(observed)
                    self.record_trial_device(identity, build, check)
                    self.log(identity, 'Trial runtime smoke recorded; outputs remain unverified.\n')
            self.update(identity, state='done', stage='Player installed' if self.jobs[identity].get('result', {}).get('kind') == 'player' else 'Package active')
        except Exception as error:
            self.log(identity, '\n' + str(error) + '\n')
            if self.job(identity).get('result', {}).get('float32_trial'):
                match = re.search(r'Candidate uses (\d+)us per callback', str(error))
                self.record_trial_device(identity, build, dict(qualification='unverified',
                    scope='package upload/admission failed; no successful running-output claim',
                    error=str(error), startup_render_us=int(match[1]) if match else None,
                    promotes_reviewed_catalog=False))
            # Keep a successful compiler artifact available for retry/download.
            self.update(identity, state='ready', stage='Upload failed — ready to retry', error=str(error))
        finally:
            self.worker.release()

    def record_trial_device(self, identity, build, check):
        result = self.job(identity).get('result', {})
        result['trial_device_check'] = check
        self.update(identity, result=result)
        report = build.parent / 'trial-review.json'
        try:
            if result.get('trial_report_available') and report.is_file() and not report.is_symlink():
                review = json.loads(report.read_bytes());review['hardware_check'] = check
                report.write_bytes(encoded(review))
        except (OSError, ValueError) as error:
            # A report-storage error must not describe a committed, healthy
            # package as an upload failure. Keep the observation in the job.
            self.log(identity, 'Runtime observation is in this job; trial report could not be updated: ' + str(error) + '\n')

    def start_install(self, data):
        board = data.get('board')
        if board not in ('xiao', 'amoled'):
            raise ValueError('Choose a board for player installation')
        if not self.environment()['idf']:
            raise ValueError('Install ESP-IDF before installing the player')
        with self.lock:
            if self.stopping.is_set():
                raise ValueError('Studio is shutting down')
            if not self.worker.acquire(blocking=False):
                raise ValueError('A build or upload is already running')
            identity = uuid.uuid4().hex
            self.jobs[identity] = dict(id=identity, state='building', stage='Building stable player', log='', error=None,
                result=None, _settings={'board': board}, _build=None)
            self.job_thread = threading.Thread(target=self.install, args=(identity, board, data.get('port')), daemon=True)
            self.job_thread.start()
        return self.job(identity)

    def install(self, identity, board, port):
        try:
            # The fixed build tool verifies pinned sources and incrementally
            # rebuilds if they changed. Never trust a cached report alone.
            command = [sys.executable, ROOT / 'tools/build_firmware.py', board, '--player', '--variant', 'player-v1']
            if board == 'amoled':
                command += ['--components-from', self.component_source()]
            self.execute(identity, command)
            build = ROOT / 'build' / ('firmware-' + board + '-player-player-v1')
            from tools.run_hardware_test import artifacts
            checked = artifacts(build, board)
            if checked['report'].get('player') is not True:
                raise ValueError('The build is not a stable player')
            self.update(identity, _build=build, result=dict(kind='player', board=board), state='uploading',
                        stage='Installing stable player')
            if self.network_bridge: self.network_bridge.disconnect()
            self.active_bridge = self.bridge
            self.bridge.flash(build, board, port, lambda text: self.log(identity, str(text) + '\n'), expected_kind='player')
            self.update(identity, state='done', stage='Stable player installed')
        except Exception as error:
            self.log(identity, '\n' + str(error) + '\n')
            self.update(identity, state='failed', stage='Player installation failed', error=str(error))
        finally:
            self.worker.release()

    def artifact(self, identity):
        self.job(identity)
        with self.lock:
            row = self.jobs[identity]
            if not row['_build'] or row.get('result', {}).get('kind') != 'package':
                raise ValueError('No completed patch package is available')
            path = row['_build']
            expected = row['result']['package_sha256']
        raw = path.read_bytes()
        if player_package.digest(raw) != expected:
            raise ValueError('The package changed after compilation')
        player_package.parse(raw)
        return path

    def trial_report(self, identity):
        job = self.job(identity)
        if not job.get('result', {}).get('trial_report_available'):
            raise ValueError('No detailed trial report is stored in this Studio session; imported packages carry the audit identity only')
        with self.lock:
            directory = self.jobs[identity]['_build'].parent
        path = directory / 'trial-review.json'
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('Trial report is missing, linked or oversized')
        review = json.loads(path.read_bytes())
        audit = directory / 'prepared/float32-trial-audit.json'
        expected = job['result']['float32_trial']['audit_sha256']
        if (hashlib.sha256(audit.read_bytes()).hexdigest() != expected
                or review.get('transform_audit_sha256') != expected
                or review.get('transform') != json.loads(audit.read_bytes())):
            raise ValueError('Trial report does not match the package audit')
        return review


class Handler(BaseHTTPRequestHandler):
    server_version = 'RNBOStudio/1'
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_args):
        pass

    def send(self, status, data, content_type='application/json'):
        raw = encoded(data) if content_type == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def allowed(self, mutation=False):
        expected = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        host = self.headers.get('Host', '')
        if host not in expected:
            raise ValueError('Studio is available only through its local address')
        origin = self.headers.get('Origin')
        if origin and origin not in {'http://' + h for h in expected}:
            raise ValueError('Cross-site requests are not allowed')
        if mutation:
            if self.server.studio.stopping.is_set():
                raise ValueError('Studio is shutting down')
            if not secrets.compare_digest(self.headers.get('X-Studio-Token', '').encode('utf-8'), self.server.studio.token.encode('utf-8')):
                raise ValueError('Refresh Studio before sending this request')

    def do_GET(self):
        try:
            self.allowed()
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            studio = self.server.studio
            if url.path == '/api/status': self.send(200, studio.status())
            elif url.path == '/api/devices': self.send(200, {'devices':studio.bridge.scan()})
            elif url.path == '/api/device': self.send(200, studio.device_snapshot())
            elif url.path == '/api/wifi': self.send(200, studio.wifi_status())
            elif url.path == '/api/job': self.send(200, {'job':studio.job(query.get('id', [''])[0])})
            elif url.path == '/api/trial-report': self.send(200, studio.trial_report(query.get('id', [''])[0]))
            elif url.path == '/api/example': self.send(200, {'guidance':native_export.GUIDANCE})
            elif url.path == '/api/artifact':
                path = studio.artifact(query.get('id', [''])[0])
                self.send(200, path.read_bytes(), 'application/octet-stream')
            elif url.path in ('/', '/app.js', '/style.css'):
                name = 'index.html' if url.path == '/' else url.path[1:]
                mime = {'index.html':'text/html; charset=utf-8', 'app.js':'text/javascript; charset=utf-8', 'style.css':'text/css; charset=utf-8'}[name]
                self.send(200, (WEB / name).read_bytes(), mime)
            else: self.send(404, {'error':'Not found'})
        except (ValueError, OSError, RuntimeError, RecursionError) as error:
            self.send(400, {'error':str(error)})

    def do_POST(self):
        try:
            self.allowed(mutation=True)
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Expected a JSON request')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                raise ValueError('Request is empty or too large')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected request fields')
            studio = self.server.studio
            if self.path == '/api/build': self.send(202, {'job':studio.start_build(data)})
            elif self.path == '/api/import-package': self.send(200, {'job':studio.import_package(data)})
            elif self.path == '/api/install-player': self.send(202, {'job':studio.start_install(data)})
            elif self.path == '/api/upload': self.send(202, {'job':studio.start_upload(data)})
            elif self.path == '/api/connect': self.send(200, studio.connect_usb(data.get('port')))
            elif self.path == '/api/wifi/scan': self.send(200, studio.scan_wifi())
            elif self.path == '/api/wifi/setup': self.send(200, studio.setup_wifi(data))
            elif self.path == '/api/wifi/forget': self.send(200, studio.forget_wifi())
            elif self.path == '/api/wifi/connect': self.send(200, studio.connect_wifi(data))
            elif self.path == '/api/disconnect':
                studio.active_bridge.disconnect(); self.send(200, {'device':None, 'parameters':[]})
            elif self.path == '/api/control': self.send(200, studio.control_device(data))
            elif self.path == '/api/midi/configure': self.send(200, studio.configure_midi(data))
            else: self.send(404, {'error':'Not found'})
        except (ValueError, OSError, RuntimeError, RecursionError) as error:
            self.send(400, {'error':str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8788)
    parser.add_argument('--components-from', type=Path)
    args = parser.parse_args()
    PRIVATE.mkdir(parents=True, exist_ok=True)
    # Prevent two studios racing for the same compiler cache and USB port.
    import fcntl
    lockfile = (PRIVATE / 'server.lock').open('a')
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error('RNBO Studio is already running')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.daemon_threads = False
    server.studio = Studio(args.components_from)
    exit_signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, 'SIGHUP'):
        exit_signals.append(signal.SIGHUP)
    def request_exit(_signum, _frame):
        raise KeyboardInterrupt
    for exit_signal in exit_signals:
        signal.signal(exit_signal, request_exit)
    print(f'RNBO Studio: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for exit_signal in exit_signals:
            signal.signal(exit_signal, signal.SIG_IGN)
        server.studio.stopping.set()
        server.server_close()
        server.studio.close()
        lockfile.close()

if __name__ == '__main__':
    main()
