# SPDX-License-Identifier: MIT
"""Exclusive, bounded RNBO serial controls and application-only uploads.

Importing this module never enumerates or opens a USB device. Serial support is
loaded only for an explicit device operation. Flashing is restricted to a pinned
ESP32-S3 identity and the existing matching factory partition layout.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from host.clients.capture import BOARDS, CaptureError, decode_response, open_serial, validate_status
from tools.run_hardware_test import artifacts, connect_restored_console
from host.compiler.package import parse as parse_package

PRIVATE = ROOT / 'build/private/studio/uploads'
ESP_VIDS = frozenset((0x303A, 0x2886))
FLASH_BYTES = {'xiao': 0x800000, 'amoled': 0x1000000}
APP_OFFSET, APP_CAPACITY = 0x10000, 0x300000
PARTITION_OFFSET, PARTITION_BYTES = 0x8000, 0x1000
MAX_LINE, MAX_REPLY, MAX_PARAMETERS = 16384, 65536, 32
MAX_TOOL_LOG = 256 * 1024
HASH = re.compile(r'[0-9a-f]{64}')
PARAMETER = re.compile(
    r'parameter ([0-9]+) id=(.*?) name=(.*?) unit=(.*?) '
    r'min=(\S+) max=(\S+) default=(\S+)$')
FAULT_COUNTERS = ('nonfinite', 'write_errors', 'dma_errors', 'queue_errors',
                  'module_errors', 'audio_heap_allocations', 'audio_heap_frees',
                  'late_platform_allocations', 'render_deadline_overruns')
FATAL_MARKERS = (b'guru meditation', b'assert failed', b'assertion failed',
                 b'abort() was called', b'stack smashing', b'brownout detector',
                 b'stack overflow', b'corrupt heap',
                 b'rnbo_smoke fault', b': fail ', b'rnbo_object_benchmark fail ')


class DeviceError(RuntimeError):
    pass


class ProtocolTimeout(DeviceError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reject_fatal(raw):
    lowered = bytes(raw).lower()
    if any(marker in lowered for marker in FATAL_MARKERS):
        raise DeviceError('The device reported a fatal UART fault; reconnect only after diagnosing it')


def reject_session_restart(raw):
    # Initial boot/settling is allowed before the first verified frame counter.
    # Later ROM/reset banners mean the state/transfer has been lost, even when
    # the rebooted application has the same ELF and sends valid JSON next.
    for line in bytes(raw).splitlines():
        line = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', line).strip().lower()
        if line.startswith((b'esp-rom:', b'rst:0x', b'rebooting')):
            raise DeviceError('The board restarted during the connection; the command was not retried. Reconnect and check its state.')


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def f32(value):
    try:
        result = struct.unpack('<f', struct.pack('<f', value))[0]
    except (OverflowError, struct.error) as error:
        raise DeviceError('A device value does not fit finite Float32') from error
    if not math.isfinite(result):
        raise DeviceError('A device value does not fit finite Float32')
    return result


def mac(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12}', value):
        raise DeviceError('The USB device needs a complete, stable MAC identity')
    return value.replace(':', '').lower()


def serial_ports():
    try:
        from serial.tools import list_ports
    except ImportError as error:
        raise DeviceError('USB controls need pyserial. Start Studio with the ESP-IDF Python environment.') from error
    return list(list_ports.comports())


def idf_python():
    configured = os.environ.get('IDF_PYTHON_ENV_PATH')
    candidates = [Path(configured) / 'bin/python'] if configured else sorted(
        (Path.home() / '.espressif/python_env').glob('idf5.5_py*_env/bin/python'))
    candidates = [p for p in candidates if p.is_file()]
    if not candidates:
        raise DeviceError('Set IDF_PYTHON_ENV_PATH to an ESP-IDF 5.5 environment with esptool installed')
    return candidates[-1]


class DeviceBridge:
    def __init__(self, *, ports=None, opener=None, runner=None, clock=None,
                 sleep=None, private_root=None, python=None, verifier=None):
        # Injectable boundaries let portable tests use no serial dependency or
        # actual subprocess/device. HTTP callers cannot supply these arguments.
        self._ports = ports or serial_ports
        self._opener = opener or open_serial
        self._runner = runner or subprocess.run
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._private = Path(private_root) if private_root is not None else PRIVATE
        self._python = python
        self._verifier = verifier or artifacts
        self._lock = threading.RLock()
        self._flashing = threading.Event()
        self._stream = None
        self._buffer = bytearray()
        self._identity = None
        self._board = None
        self._firmware = None
        self._schema = []
        self._player = False
        self._last_generation = None
        self._last_frames = self._last_uptime = None

    @contextmanager
    def _exclusive(self):
        if not self._lock.acquire(blocking=False):
            raise DeviceError('The USB device is busy; wait for the current operation')
        try:
            if self._flashing.is_set():
                raise DeviceError('An upload is in progress')
            yield
        finally:
            self._lock.release()

    def _inventory(self):
        result = []
        for p in self._ports():
            port = getattr(p, 'device', None)
            if (getattr(p, 'vid', None) not in ESP_VIDS or not isinstance(port, str)
                    or not port or len(port) > 240 or port.startswith('-')
                    or any(c in port for c in '\r\n\0')):
                continue
            serial = getattr(p, 'serial_number', None)
            if serial is not None and (not isinstance(serial, str) or len(serial) > 128
                                       or any(c in serial for c in '\r\n\0')):
                continue
            result.append(dict(port=port, serial_number=serial,
                               vid=getattr(p, 'vid', None), pid=getattr(p, 'pid', None),
                               location=getattr(p, 'location', None),
                               label=str(getattr(p, 'description', None) or 'ESP32-S3 USB')[:200]))
        return result

    def scan(self):
        with self._exclusive():
            return [{k: row[k] for k in ('port', 'label', 'serial_number')}
                    for row in self._inventory()]

    def _select(self, port):
        rows = self._inventory()
        if port is None and len(rows) == 1:
            return rows[0]
        matches = [row for row in rows if row['port'] == port]
        if len(matches) != 1:
            raise DeviceError('Choose one currently listed ESP32 USB device')
        return matches[0]

    def _resolve(self, identity, deadline):
        while self._clock() < deadline:
            rows = self._inventory()
            if identity['serial_number']:
                def same(row):
                    try:
                        return mac(row['serial_number']) == mac(identity['serial_number'])
                    except DeviceError:
                        return row['serial_number'] == identity['serial_number']
                matches = [row for row in rows if same(row)]
            else:
                matches = [row for row in rows if all(row[k] == identity[k]
                           for k in ('port', 'vid', 'pid', 'location'))]
            if len(matches) > 1:
                raise DeviceError('Multiple USB devices advertise the selected identity')
            if len(matches) == 1:
                return matches[0]
            self._sleep(.05)
        raise DeviceError('The selected USB device did not reconnect; choose it again')

    def _disconnect(self):
        stream, self._stream = self._stream, None
        self._identity = self._board = self._firmware = None
        self._schema = []
        self._player = False
        self._last_generation = None
        self._last_frames = self._last_uptime = None
        self._buffer.clear()
        if stream is not None:
            stream.close()

    def disconnect(self):
        with self._exclusive():
            self._disconnect()

    def _exchange(self, commands, expected, *, schema=False, timeout=3, allow_error=False):
        if self._stream is None:
            raise DeviceError('Connect a device first')
        payload = ('\n'.join(commands) + '\n').encode('ascii')
        deadline = self._clock() + timeout
        consumed = 0
        metadata = []
        try:
            if self._stream.write(payload) != len(payload):
                raise DeviceError('The complete USB command was not written')
            while self._clock() < deadline:
                reject_fatal(self._buffer)
                if self._last_frames is not None:
                    reject_session_restart(self._buffer)
                while b'\n' in self._buffer:
                    end = self._buffer.index(10)
                    line = bytes(self._buffer[:end]).strip()
                    del self._buffer[:end + 1]
                    consumed += end + 1
                    if end > MAX_LINE or consumed > MAX_REPLY:
                        raise DeviceError('USB reply exceeded its size limit')
                    if line.startswith((b'{', b'[')):
                        probe = json.loads(line) if allow_error else None
                        reply = probe if type(probe) is dict and set(probe) == {'error'} and isinstance(probe['error'], str) else decode_response(line)
                        if expected is not None and expected not in reply:
                            raise DeviceError('Unexpected USB reply; reconnect before sending controls')
                        return reply, metadata
                    if line.startswith(b'parameter '):
                        if not schema or len(metadata) >= MAX_PARAMETERS:
                            raise DeviceError('Unexpected or oversized parameter schema')
                        metadata.append(line.decode('utf-8', 'strict'))
                if len(self._buffer) > MAX_LINE:
                    raise DeviceError('USB reply line exceeded its size limit')
                waiting = max(0, int(self._stream.in_waiting))
                chunk = self._stream.read(min(waiting or 1, 4096))
                self._buffer.extend(chunk)
                if not chunk:
                    self._sleep(.005)
            raise ProtocolTimeout('Timed out waiting for an RNBO USB reply')
        except ProtocolTimeout:
            raise
        except (OSError, CaptureError, UnicodeError, DeviceError) as error:
            self._disconnect()
            raise DeviceError(str(error)) from error

    def _player_status(self, raw=None):
        if raw is None:
            raw, _ = self._exchange(('player-info',), 'runtime')
        board = next((key for key, (label, _) in BOARDS.items() if raw.get('board') == label), None)
        if (raw.get('runtime') != 'rnbo-esp32s3-player' or type(raw.get('api_version')) is not int
                or raw['api_version'] != 1 or board is None or raw.get('rate') != 44100
                or raw.get('block_frames') != 256 or not isinstance(raw.get('firmware_elf_sha256'), str)
                or not HASH.fullmatch(raw['firmware_elf_sha256'])
                or type(raw.get('generation')) is not int or raw['generation'] < 0
                or 'main' not in raw
                or type(raw.get('volume')) is not int or not 0 <= raw['volume'] <= 100
                or any(type(raw.get(key)) is not bool for key in ('paused', 'panic', 'maintenance'))):
            raise DeviceError('Malformed or unsupported player status')
        if ((self._board is not None and board != self._board)
                or (self._firmware is not None and raw['firmware_elf_sha256'] != self._firmware)):
            raise DeviceError('The connected player identity changed; reconnect')
        for key, previous in (('frames', self._last_frames), ('uptime_us', self._last_uptime),
                              ('generation', self._last_generation)):
            if type(raw.get(key)) is not int or raw[key] < 0 or previous is not None and raw[key] < previous:
                self._disconnect()
                raise DeviceError('The player session moved backwards; reconnect')
        for role in ('main',):
            image = raw.get(role)
            if image is None:
                continue
            if (type(image) is not dict or not isinstance(image.get('name'), str)
                    or not 1 <= len(image['name'].encode('utf-8')) <= 63
                    or any(not isinstance(image.get(k), str) or not HASH.fullmatch(image[k])
                           for k in ('package_sha256', 'source_sha256'))
                    or type(image.get('arena_bytes')) is not int or not 4096 <= image['arena_bytes'] <= 4194304
                    or type(image.get('arena_used')) is not int or not 0 <= image['arena_used'] <= image['arena_bytes']
                    or type(image.get('context_bytes')) is not int or image['context_bytes'] <= 0
                    or type(image.get('sample_position')) is not int or image['sample_position'] < 0
                    or type(image.get('parameter_count')) is not int or not 0 <= image['parameter_count'] <= MAX_PARAMETERS
                    or type(image.get('parameters')) is not list or len(image['parameters']) != image['parameter_count']):
                raise DeviceError('Malformed player image metadata')
            for index, parameter in enumerate(image['parameters']):
                if (type(parameter) is not dict or type(parameter.get('index')) is not int or parameter['index'] != index
                        or not isinstance(parameter.get('name'), str)
                        or any(not finite(parameter.get(k)) for k in ('min', 'max', 'initial', 'actual', 'normalized'))
                        or parameter['min'] > parameter['max'] or not 0 <= parameter['normalized'] <= 1):
                    raise DeviceError('Malformed player parameter metadata')
        self._last_frames, self._last_uptime, self._last_generation = raw['frames'], raw['uptime_us'], raw['generation']
        self._board, self._firmware = board, raw['firmware_elf_sha256']
        return raw

    def _status(self):
        if self._player:
            return self._player_status()
        raw, _ = self._exchange(('status',), 'runtime')
        board = next((key for key, (label, _) in BOARDS.items() if raw.get('board') == label), None)
        if board is None:
            raise DeviceError('This is not a supported RNBO board firmware')
        try:
            validate_status(raw, board)
        except CaptureError as error:
            raise DeviceError(str(error)) from error
        firmware = raw.get('firmware_elf_sha256')
        if (not isinstance(firmware, str) or not HASH.fullmatch(firmware)
                or type(raw.get('panic')) is not bool
                or type(raw.get('volume')) is not int or not 0 <= raw['volume'] <= 100):
            raise DeviceError('The RNBO status identity or controls are malformed')
        if self._board is not None and board != self._board:
            raise DeviceError('The connected board profile changed')
        if self._firmware is not None and firmware != self._firmware:
            raise DeviceError('The connected firmware changed; reconnect to refresh its controls')
        frames, uptime = raw.get('frames'), raw.get('uptime_us')
        if (type(frames) is not int or frames < 0
                or self._last_frames is not None and frames < self._last_frames
                or uptime is not None and (type(uptime) is not int or uptime < 0
                    or self._last_uptime is not None and uptime < self._last_uptime)):
            self._disconnect()
            raise DeviceError('The device position moved backwards; its session may have restarted')
        self._last_frames = frames
        if uptime is not None:
            self._last_uptime = uptime
        self._board, self._firmware = board, firmware
        return raw

    def _parameters(self, *, discover=False):
        commands = ('parameters', 'parameter-values') if discover else ('parameter-values',)
        reply, lines = self._exchange(commands, 'parameters', schema=discover)
        values = reply['parameters']
        if type(values) is not list or len(values) > MAX_PARAMETERS:
            raise DeviceError('Invalid parameter readback')
        if discover:
            metadata = []
            for line in lines:
                m = PARAMETER.fullmatch(line)
                if m is None:
                    raise DeviceError('Invalid parameter description')
                index, identity, name, unit, low, high, initial = m.groups()
                numbers = tuple(float(x) for x in (low, high, initial))
                if (not all(math.isfinite(x) for x in numbers) or numbers[0] > numbers[1]
                        or not identity or len(identity) > 128 or len(name) > 256 or len(unit) > 128):
                    raise DeviceError('Invalid parameter range or name')
                metadata.append(dict(index=int(index), name=name or identity,
                                     min=numbers[0], max=numbers[1], initial=numbers[2]))
            if (len(metadata) != len(values) or [p['index'] for p in metadata] != list(range(len(values)))):
                raise DeviceError('Parameter descriptions and readbacks disagree')
            self._schema = metadata
        if len(values) != len(self._schema):
            raise DeviceError('The parameter schema changed; reconnect')
        by_index = {}
        for entry in values:
            if (type(entry) is not dict or type(entry.get('index')) is not int
                    or entry['index'] in by_index or not 0 <= entry['index'] < len(values)
                    or not finite(entry.get('actual')) or not finite(entry.get('normalized'))
                    or not 0 <= f32(entry['normalized']) <= 1):
                raise DeviceError('Invalid parameter value or normalized readback')
            f32(entry['actual'])
            by_index[entry['index']] = entry
        return [dict(row, actual=by_index[row['index']]['actual'],
                     normalized=by_index[row['index']]['normalized']) for row in self._schema]

    def _snapshot(self):
        raw = self._status()
        neutral = raw.get('source') == 'engine-neutral-stereo-tone' and raw.get('module_source_sha256') == 'none'
        if self._player:
            parameters = [dict(p, role=role, generation=raw['generation'])
                          for role in ('main',) for p in (raw.get(role) or {}).get('parameters', [])]
        else:
            parameters = [] if neutral else self._parameters()
        device = dict(raw, board_model=raw['board'], board=self._board,
                      port=self._identity['port'], serial_number=self._identity['serial_number'],
                      transport='usb', device_id=mac(self._identity['serial_number']))
        return dict(device=device, parameters=parameters)

    def snapshot(self):
        if self._flashing.is_set():
            return dict(device=None, parameters=[], busy=True)
        if self._stream is None:
            return dict(device=None, parameters=[])
        with self._exclusive():
            if self._stream is None:
                return dict(device=None, parameters=[])
            try:
                return self._snapshot()
            except Exception:
                self._disconnect()
                raise

    def _connect(self, identity, *, board=None, firmware=None, boot=None, events=None):
        self._disconnect()
        deadline = self._clock() + 15
        def opening():
            selected = self._resolve(identity, deadline)
            self._identity = selected
            return self._opener(selected['port'], 115200, 3)
        boot_bytes = boot if boot is not None else bytearray()
        self._stream = connect_restored_console(opening, boot_bytes,
            events if events is not None else [], clock=self._clock, sleep=self._sleep)
        self._board, self._firmware = board, firmware
        try:
            reject_fatal(boot_bytes)
            limit = self._clock() + 9
            while True:
                try:
                    probe, _ = self._exchange(('player-info',), None, allow_error=True)
                    self._player = probe.get('runtime') == 'rnbo-esp32s3-player'
                    raw = self._player_status(probe) if self._player else self._status()
                    break
                except ProtocolTimeout:
                    if self._clock() >= limit:
                        raise
            neutral = raw.get('source') == 'engine-neutral-stereo-tone' and raw.get('module_source_sha256') == 'none'
            if not neutral and not self._player:
                self._parameters(discover=True)
            return self._snapshot()
        except Exception:
            self._disconnect()
            raise

    def connect(self, port):
        with self._exclusive():
            return self._connect(self._select(port))

    def scan_wifi(self):
        with self._exclusive():
            if not self._player or self._stream is None:
                raise DeviceError('Connect the updated player over USB before scanning')
            before = self._player_status()
            if not before.get('wifi',{}).get('supported'):
                raise DeviceError('Install the Wi-Fi player update first')
            reply, _ = self._exchange(('player-wifi-scan',),'networks',timeout=20)
            networks = reply.get('networks')
            if type(networks) is not list or len(networks)>24:
                raise DeviceError('Invalid nearby-network list')
            for row in networks:
                if (type(row) is not dict or not isinstance(row.get('ssid'),str)
                        or not 1<=len(row['ssid'].encode('utf-8'))<=32
                        or any(ord(c)<32 or ord(c)==127 for c in row['ssid'])
                        or type(row.get('rssi')) is not int or not -127<=row['rssi']<=0
                        or type(row.get('channel')) is not int or not 1<=row['channel']<=14
                        or type(row.get('secure')) is not bool):
                    raise DeviceError('Invalid nearby-network description')
            return dict(networks=networks)

    def configure_wifi(self, ssid, password, key):
        if (not isinstance(ssid, str) or not isinstance(password, str) or '\0' in ssid + password
                or not 1 <= len(ssid.encode('utf-8')) <= 32
                or len(password.encode('utf-8')) not in (0, *range(8, 64))
                or not isinstance(key, str) or not HASH.fullmatch(key)):
            raise ValueError('Use a network name up to 32 bytes and an empty or 8–63 byte password')
        with self._exclusive():
            if not self._player or self._stream is None:
                raise DeviceError('Connect the updated player over USB before setting up Wi-Fi')
            before = self._player_status()
            if not before.get('wifi', {}).get('supported'):
                raise DeviceError('Install the Wi-Fi player update first')
            command = 'player-wifi-setup ' + ssid.encode('utf-8').hex() + ' ' + (password.encode('utf-8').hex() or '-') + ' ' + key
            reply, _ = self._exchange((command,), 'wifi_configured', timeout=30)
            if reply.get('wifi_configured') is not True:
                raise DeviceError('The board did not confirm Wi-Fi setup')
            return self._snapshot()

    def forget_wifi(self):
        with self._exclusive():
            if not self._player or self._stream is None:
                raise DeviceError('Connect the player over USB to forget its Wi-Fi settings')
            reply, _ = self._exchange(('player-wifi-forget',), 'wifi_forgotten', timeout=30)
            if reply.get('wifi_forgotten') is not True:
                raise DeviceError('The board did not confirm Wi-Fi removal')
            return self._snapshot()

    def configure_midi(self, mode):
        if mode not in ('off','uart'):
            raise ValueError('Choose MIDI off or UART')
        with self._exclusive():
            if not self._player or self._stream is None:
                raise DeviceError('Connect the MIDI-capable player first')
            before=self._player_status()
            if before.get('midi_input_version')!=1:
                raise DeviceError('Install the updated MIDI player first')
            reply,_=self._exchange(('player-midi-config '+mode,),'midi_configured',timeout=15)
            if reply.get('midi_configured') is not True:
                raise DeviceError('The player did not confirm MIDI configuration')
            return self._snapshot()

    def midi_stream(self, data, *, loopback=False):
        if not isinstance(data,str) or not 2<=len(data)<=256 or len(data)%2 or not re.fullmatch('[0-9a-fA-F]+',data):
            raise ValueError('MIDI stream must contain 1..128 hexadecimal bytes')
        with self._exclusive():
            if not self._player or self._stream is None:raise DeviceError('Connect the MIDI player first')
            before=self._player_status()
            if before.get('midi_input_version')!=1:raise DeviceError('Install the updated MIDI player first')
            reply,_=self._exchange((f"{'player-midi-loopback' if loopback else 'player-midi-stream'} {before['generation']} {data}",),'midi_stream_accepted')
            if reply.get('midi_stream_accepted') is not True:raise DeviceError('MIDI diagnostic stream was not accepted')
            return self._snapshot()

    def control(self, payload):
        if self._player:
            return self.player_control(payload)
        if type(payload) is not dict:
            raise ValueError('Choose a supported device control')
        action = payload.get('action')
        allowed = {'action', 'index', 'value'} if action == 'param' else {'action', 'value'} if action == 'volume' else {'action'}
        if action not in ('pause', 'resume', 'volume', 'param') or set(payload) != allowed:
            raise ValueError('Choose volume, pause, resume or a normalized parameter')
        if action == 'volume' and (not finite(payload['value']) or not float(payload['value']).is_integer()
                                   or not 0 <= payload['value'] <= 100):
            raise ValueError('Volume must be an integer percentage from 0 to 100')
        if action == 'param' and (type(payload['index']) is not int or not finite(payload['value'])
                                  or not 0 <= payload['value'] <= 1):
            raise ValueError('A parameter needs its index and a normalized value from 0 to 1')
        with self._exclusive():
            if self._stream is None:
                raise DeviceError('Connect a device first')
            if action == 'param' and not 0 <= payload['index'] < len(self._schema):
                raise ValueError('Unknown parameter index')
            before = self._status()  # Reject stale firmware before any mutation.
            command, key = {'pause': ('panic', 'panic'), 'resume': ('resume', 'resume_requested')}.get(action, (None, None))
            if action == 'volume':
                command, key = f"volume {int(payload['value'])}", 'volume'
            elif action == 'param':
                command, key = f"normalized {payload['index']} {f32(payload['value']):.9g}", 'queued'
            reply, _ = self._exchange((command,), key)
            if action == 'volume':
                if reply.get('accepted') is not True or reply[key] != int(payload['value']):
                    raise DeviceError('Volume was not accepted')
            elif reply[key] is not True:
                raise DeviceError('The control was not accepted')
            deadline = self._clock() + (15 if action in ('pause', 'resume') else 3)
            while True:
                result = self._snapshot()
                status = result['device']
                if action == 'param':
                    if status.get('allocation_fault') or status.get('reconstruction_failed'):
                        raise DeviceError('The patch reported a fault after the parameter was queued')
                    for field in FAULT_COUNTERS:
                        if (type(before.get(field)) is not int or type(status.get(field)) is not int
                                or status[field] != before[field]):
                            raise DeviceError('A runtime counter changed after the parameter was queued: ' + field)
                applied = (status['panic'] is True and status.get('rebuilding') is False
                           and status.get('ready_to_resume') is True if action == 'pause'
                           else status['panic'] is False if action == 'resume'
                           else status['volume'] == int(payload['value']) if action == 'volume'
                           else type(status.get('frames')) is int and status['frames'] >= before.get('frames', 0) + 512)
                if applied:
                    if action == 'param':
                        observed = result['parameters'][payload['index']]
                        # The text protocol has no correlated event ID or steps/
                        # exponent schema. Quantization can legitimately change
                        # the requested normalized value. Report the queue ACK
                        # and later readback, never claim exact application.
                        result['control'] = dict(action='param', index=payload['index'],
                            queued=True, requested_normalized=f32(payload['value']),
                            observed_actual=observed['actual'], observed_normalized=observed['normalized'],
                            confirmation='queued-and-post-block-readback', exact_application_verified=False)
                    return result
                if self._clock() >= deadline:
                    raise DeviceError('The device did not confirm the requested control')
                self._sleep(.03)

    def player_control(self, payload):
        if type(payload) is not dict:
            raise ValueError('Choose a player control')
        action = payload.get('action')
        keys = ({'action', 'role', 'generation', 'index', 'value'} if action == 'param'
                else {'action', 'value'} if action == 'volume' else {'action'})
        if set(payload) != keys or action not in ('pause', 'resume', 'volume', 'param'):
            raise ValueError('Choose a supported player control')
        if action == 'volume' and (type(payload['value']) is not int or not 0 <= payload['value'] <= 100):
            raise ValueError('Volume must be an integer percentage')
        if action == 'param' and (payload['role'] != 'main'
                or type(payload['generation']) is not int or type(payload['index']) is not int
                or not finite(payload['value']) or not 0 <= payload['value'] <= 1):
            raise ValueError('Invalid role, generation, index or normalized parameter')
        with self._exclusive():
            before = self._player_status()
            if before['maintenance']:
                raise DeviceError('The player is changing patches; wait')
            command = 'player-' + action
            expected = None
            if action == 'volume': command += ' ' + str(payload['value'])
            elif action == 'param':
                image = before.get(payload['role'])
                if (payload['generation'] != before['generation'] or image is None
                        or not 0 <= payload['index'] < image['parameter_count']):
                    raise DeviceError('The active patch changed; refresh its controls')
                command += f" {1 if payload['role'] == 'main' else 2} {payload['generation']} {payload['index']} {f32(payload['value']):.9g}"
            reply, _ = self._exchange((command,), expected)
            if reply.get('error') or reply.get('accepted') is False or (action == 'param' and reply.get('queued') is not True):
                raise DeviceError('The player did not accept the control')
            deadline = self._clock() + 5
            while True:
                result = self._snapshot()
                now = result['device']
                if now['generation'] != before['generation']:
                    raise DeviceError('The active patch changed during the control')
                for key in FAULT_COUNTERS:
                    if type(now.get(key)) is not int or now[key] != before.get(key):
                        raise DeviceError('A runtime counter changed after the player control: ' + key)
                matched = (now['paused'] if action == 'pause' else not now['paused'] if action == 'resume'
                           else now['volume'] == payload['value'] if action == 'volume'
                           else now['frames'] >= before['frames'] + 512)
                if matched:
                    if action == 'param':
                        result['control'] = dict(queued=True, confirmation='queued-and-post-block-readback',
                                                 exact_application_verified=False)
                    return result
                if self._clock() >= deadline:
                    raise DeviceError('The player did not confirm its control state')
                self._sleep(.03)

    def upload_package(self, path, port, log, *, expected_sha256=None):
        # Read and validate immutable bytes before any device operation. Native
        # code is trusted; hashes are integrity checks, not a security boundary.
        raw = Path(path).read_bytes()
        if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise DeviceError('The package changed after compilation')
        package = parse_package(raw)
        role = package['role']
        role_id = 1 if role == 'main' else 2
        with self._exclusive():
            self._connect(self._select(port))
            if not self._player:
                raise DeviceError('Install the stable player before loading a package')
            before = self._player_status()
            if package['metadata'].get('midi_input_ports') and before.get('midi_input_version') != 1:
                raise DeviceError('This MIDI-input package needs the updated MIDI player. Install it over USB first.')
            if package['metadata'].get('physical_inputs'):
                if before.get('physical_inputs_version') != 1:
                    raise DeviceError('This package uses physical inputs. Install the updated player over USB first.')
                if self._board != 'xiao':
                    raise DeviceError('This physical-input package requires the XIAO board profile; AMOLED pins differ.')
            self._flashing.set()
            begun = False
            try:
                reply, _ = self._exchange((f"player-begin {role_id} {len(raw)} {package['package_sha256']}",), 'upload')
                if reply.get('upload') != 'ready' or reply.get('offset') != 0 or reply.get('chunk_bytes') != 1024:
                    raise DeviceError('The player rejected package staging')
                begun = True
                for offset in range(0, len(raw), 1024):
                    chunk = raw[offset:offset+1024]
                    reply, _ = self._exchange((f"player-data {offset} {chunk.hex()}",), 'upload')
                    if reply.get('upload') != 'chunk' or type(reply.get('offset')) is not int or reply['offset'] != offset + len(chunk):
                        raise DeviceError('The player acknowledged an incorrect package offset')
                log('Committing ' + role.upper() + ' package; audio pauses briefly')
                reply, _ = self._exchange(('player-commit',), 'upload', timeout=60)
                if (reply.get('upload') != 'committed' or reply.get('role') != role_id
                        or reply.get('package_sha256') != package['package_sha256']
                        or type(reply.get('generation')) is not int or reply['generation'] <= before['generation']):
                    raise DeviceError('The player did not confirm the complete package commit')
                begun = False
                result = self._snapshot()
                started = result['device']['frames']
                deadline = self._clock() + 10
                while True:
                    status = result['device']
                    active = status.get(role)
                    if (status['generation'] != reply['generation'] or not active
                            or active['package_sha256'] != package['package_sha256']
                            or active['source_sha256'] != package['metadata']['source_sha256']
                            or active['arena_bytes'] != package['arena_bytes'] or status['maintenance']):
                        raise DeviceError('The running package differs from the committed package')
                    if status.get('allocation_fault') or status.get('reconstruction_failed'):
                        raise DeviceError('The committed package reported a runtime fault')
                    for field in FAULT_COUNTERS:
                        if type(status.get(field)) is not int or status[field] != before.get(field):
                            raise DeviceError('A runtime counter changed after package loading: ' + field)
                    if status['paused'] or status['volume'] != package['metadata']['initial_volume']:
                        raise DeviceError('The Main package did not confirm its startup controls')
                    if status['frames'] >= started + 512:
                        break
                    if self._clock() >= deadline:
                        raise DeviceError('The committed package did not advance audio')
                    self._sleep(.03)
                    result = self._snapshot()
                log('Package committed and active; player firmware unchanged')
                return result
            except Exception:
                if begun and self._stream is not None:
                    try: self._exchange(('player-abort',), 'upload')
                    except Exception: self._disconnect()
                raise
            finally:
                self._flashing.clear()

    def flash(self, build_dir, board, port, log, *, expected_kind='legacy'):
        """Upload only a matching factory application; never erase/layout/bootloader.

        A private 3 MiB application backup, partition snapshots, bounded tool logs
        and a receipt are retained for every attempted upload. A failed write is
        not automatically replayed or called successful. Root can inspect/recover
        from the pinned backup. The first version requires an existing identical
        partition table; it does not install a new board layout.
        """
        if board not in FLASH_BYTES:
            raise ValueError('Select XIAO or AMOLED V2')
        if not callable(log):
            raise ValueError('An upload needs a log callback')
        directory = Path(build_dir).expanduser().resolve()
        if not directory.is_relative_to(ROOT / 'build') or not directory.is_dir():
            raise ValueError('Choose a compiled firmware build in this workspace')
        with self._exclusive():
            checked = self._verifier(directory, board)
            if expected_kind not in ('legacy', 'player'):
                raise ValueError('Invalid firmware kind')
            is_player = expected_kind == 'player'
            if is_player and checked['report'].get('player') is not True:
                raise DeviceError('Not a stable player firmware build')
            manifest = checked['report'].get('prepared_export', {}).get('manifest', {})
            count = 0 if is_player else manifest.get('parameter_count')
            source = 'none' if is_player else manifest.get('source_tree_sha256')
            initial_volume = 50 if is_player else checked['report'].get('initial_volume_percent')
            if type(count) is not int or not 0 <= count <= MAX_PARAMETERS:
                raise DeviceError(f'Studio supports compiled patches with 0 to {MAX_PARAMETERS} parameters; compile a smaller patch before uploading')
            if not is_player and (not isinstance(source, str) or not HASH.fullmatch(source)):
                raise DeviceError('The compiled patch source identity is missing')
            if type(initial_volume) is not int or not 0 <= initial_volume <= 100:
                raise DeviceError('The compiled startup volume is missing or invalid')
            report_hash = checked['report_sha256']
            expected_elf = checked['elf_sha256']
            if not HASH.fullmatch(report_hash) or not HASH.fullmatch(expected_elf):
                raise DeviceError('The firmware integrity inventory is malformed')
            initial_app = checked['app'].read_bytes()
            expected_app = hashlib.sha256(initial_app).hexdigest()
            table = checked['partition'].read_bytes()
            if not table or len(table) > PARTITION_BYTES:
                raise DeviceError('The expected partition table has an invalid size')
            interpreter = Path(self._python) if self._python is not None else idf_python()
            if not interpreter.is_file():
                raise DeviceError('The ESP-IDF Python interpreter is unavailable')
            identity = self._select(port)
            key = mac(identity['serial_number'])
            self._disconnect()
            self._private.mkdir(parents=True, exist_ok=True)
            output = self._private / uuid.uuid4().hex
            output.mkdir(mode=0o700)
            staged_app = output / 'application.bin'
            staged_app.write_bytes(initial_app)
            staged_app.chmod(0o400)
            (output / 'expected-partition.bin').write_bytes(table)
            receipt = dict(format='rnbo-studio-upload-v1', board=board, device_mac=key,
                           selected_port=identity['port'], started_at_utc=datetime.now(timezone.utc).isoformat(),
                           build_report_sha256=report_hash, expected_firmware_elf_sha256=expected_elf,
                           application_sha256=expected_app, partition_sha256=hashlib.sha256(table).hexdigest(),
                           application_write_offset=APP_OFFSET, application_partition_bytes=APP_CAPACITY,
                           commands=[], write_attempted=False, readback_verified=False,
                           connected_identity_verified=False, result='in-progress')

            def save():
                temporary = output / 'receipt.tmp'
                temporary.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
                temporary.replace(output / 'receipt.json')

            def unchanged():
                current = self._verifier(directory, board)
                if (current['report_sha256'] != report_hash or current['elf_sha256'] != expected_elf
                        or current['partition'].read_bytes() != table
                        or sha(current['app']) != expected_app or sha(staged_app) != expected_app):
                    raise DeviceError('Firmware artifacts changed during upload; compile again')
                return current

            def parse_identity(text, *, flash_size=False):
                text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
                if not re.search(r'(?:Chip is|Chip type:|Detecting chip type[^\n]*?)\s*ESP32-S3\b', text, re.I):
                    raise DeviceError('The selected device did not identify as ESP32-S3')
                found = {mac(value) for value in re.findall(r'\bMAC:\s*((?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})\b', text)}
                if found != {key}:
                    raise DeviceError('The physical board identity changed; no further write is permitted')
                if flash_size:
                    sizes = re.findall(r'Detected flash size:\s*(\d+)\s*(KB|MB)\b', text, re.I)
                    sizes = {int(n) * (1024 if unit.upper() == 'KB' else 1024 * 1024) for n, unit in sizes}
                    if sizes != {FLASH_BYTES[board]}:
                        raise DeviceError('The flash capacity does not match the selected board profile')

            def tool(operation, arguments=(), *, timeout=90, flash_size=False, writing=False):
                unchanged()  # This gate precedes every ROM read and write.
                selected = self._resolve(identity, self._clock() + 15)
                if mac(selected['serial_number']) != key:
                    raise DeviceError('USB identity changed before the operation')
                command = [str(interpreter), '-m', 'esptool', '--chip', 'esp32s3',
                           '--port', selected['port'], '--baud', '921600', '--after', 'watchdog_reset',
                           operation, *[str(a) for a in arguments]]
                record = dict(operation=operation, arguments=[str(a) for a in arguments], port=selected['port'])
                receipt['commands'].append(record)
                if writing:
                    receipt['write_attempted'] = True
                save()
                log('USB: ' + operation.replace('_', ' '))
                completed = self._runner(command, cwd=ROOT, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, timeout=timeout, check=False,
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
                raw = completed.stdout or b''
                if isinstance(raw, str):
                    raw = raw.encode('utf-8')
                record['returncode'] = completed.returncode
                record['log_bytes'] = len(raw)
                record['log_sha256'] = hashlib.sha256(raw).hexdigest()
                logfile = output / f"{len(receipt['commands']):02d}-{operation}.log"
                logfile.write_bytes(raw[:MAX_TOOL_LOG])
                record['log_path'] = str(logfile)
                save()
                if len(raw) > MAX_TOOL_LOG:
                    raise DeviceError('The upload tool exceeded its output limit')
                if completed.returncode:
                    raise DeviceError('The USB operation failed; inspect the private upload log: ' + str(logfile))
                parse_identity(raw.decode('utf-8', 'replace'), flash_size=flash_size)
                # A returned watchdog-reset command can precede USB disappearance.
                # No command is sent in this settling interval; resolve again next.
                self._sleep(2)

            def read_file(name, address, count):
                destination = output / name
                tool('read_flash', (hex(address), hex(count), destination), timeout=180)
                if destination.is_symlink() or not destination.is_file() or destination.stat().st_size != count:
                    raise DeviceError('The complete requested flash region was not read')
                return destination

            def partition_matches(path):
                actual = path.read_bytes()
                if actual[:len(table)] != table or any(b != 0xff for b in actual[len(table):]):
                    raise DeviceError('The existing partition layout differs from this build. '
                                      'Install the reviewed base layout first; Studio did not erase or rewrite it.')

            self._flashing.set()
            try:
                save()
                tool('flash_id', flash_size=True)
                partition = read_file('partition-before.bin', PARTITION_OFFSET, PARTITION_BYTES)
                partition_matches(partition)
                receipt['partition_before_sha256'] = sha(partition)
                backup = read_file('original-application-3MiB.bin', APP_OFFSET, APP_CAPACITY)
                receipt['backup'] = dict(path=str(backup), bytes=APP_CAPACITY, sha256=sha(backup))
                save()
                # Re-probe identity/capacity and layout after the backup, then
                # resolve the same USB MAC immediately before the only write.
                tool('flash_id', flash_size=True)
                final_partition = read_file('partition-prewrite.bin', PARTITION_OFFSET, PARTITION_BYTES)
                partition_matches(final_partition)
                if sha(backup) != receipt['backup']['sha256']:
                    raise DeviceError('The recovery backup changed before writing')
                tool('write_flash', (hex(APP_OFFSET), staged_app), timeout=180, writing=True)
                readback = read_file('application-readback.bin', APP_OFFSET, len(initial_app))
                if sha(readback) != expected_app:
                    raise DeviceError('Uploaded application readback differs; the original backup is retained at ' + str(backup))
                receipt['readback_verified'] = True
                receipt['readback_sha256'] = sha(readback)
                unchanged()
                boot = bytearray()
                boot_events = []
                result = self._connect(identity, board=board, firmware=expected_elf,
                                       boot=boot, events=boot_events)
                (output / 'startup.log').write_bytes(boot)
                receipt['startup_log_sha256'] = hashlib.sha256(boot).hexdigest()
                receipt['startup_events'] = boot_events
                device = result['device']
                first_frames = device.get('frames')
                if type(first_frames) is not int or first_frames < 0:
                    raise DeviceError('The uploaded patch did not report a valid audio position')
                ready_deadline = self._clock() + 15
                while True:
                    device = result['device']
                    if is_player and not self._player:
                        raise DeviceError('The uploaded firmware is not the expected stable player')
                    if not is_player and (self._player or device.get('module_source_sha256') != source or len(result['parameters']) != count):
                        raise DeviceError('The running patch identity or parameter count differs from the compiled build')
                    if device.get('allocation_fault') or device.get('reconstruction_failed'):
                        raise DeviceError('The uploaded patch reports a runtime allocation or reconstruction fault')
                    for field in FAULT_COUNTERS:
                        if type(device.get(field)) is not int or device[field] != 0:
                            raise DeviceError('The uploaded patch reports a runtime problem: ' + field)
                    frames = device.get('frames')
                    if (type(frames) is int and frames >= first_frames + 512
                            and ((is_player and device.get('maintenance') is False)
                                 or (not is_player and device.get('panic') is False and device.get('rebuilding') is False))
                            and (is_player or device.get('volume') == initial_volume)):
                        break
                    if self._clock() >= ready_deadline:
                        raise DeviceError('The uploaded patch did not confirm running audio and its compiled startup volume')
                    self._sleep(.05)
                    result = self._snapshot()
                receipt['connected_identity_verified'] = True
                receipt['audio_progress_verified'] = True
                receipt['initial_volume_percent'] = initial_volume
                receipt['device_status'] = device
                receipt['result'] = 'completed'
                log('Application readback and running firmware identity verified')
                return result
            except Exception as error:
                receipt['result'] = 'failed'
                receipt['error'] = str(error)
                self._disconnect()
                raise
            finally:
                receipt['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
                try:
                    save()
                    log('Private upload receipt: ' + str(output / 'receipt.json'))
                finally:
                    self._flashing.clear()
