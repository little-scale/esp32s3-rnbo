# SPDX-License-Identifier: MIT
"""Authenticated player transport and private local pairings.

HMAC authenticates commands/replies; it does not encrypt their contents. This
module never discovers/open USB, invokes ROM tools, or stores LAN credentials.
Both peer and fresh client nonces bind each connection against transcript replay.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import tempfile
import threading
import time

try:
    from .device import DeviceBridge, DeviceError, ProtocolTimeout, MAX_LINE, ROOT
except ImportError:
    from device import DeviceBridge, DeviceError, ProtocolTimeout, MAX_LINE, ROOT

PORT = 8789
PAIRINGS = ROOT / 'build/private/studio/pairings.json'
HEX64 = re.compile(r'[0-9a-f]{64}')
DEVICE_ID = re.compile(r'[0-9a-f]{12}')
PRIVATE_NETS = tuple(ipaddress.IPv4Network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
MAX_WIRE = 65536
MAX_COMMAND = 8191
MAX_PAIRINGS = 64


def validate_ip(value):
    """Return a numeric RFC1918 IPv4 address; never resolve a hostname."""
    try:
        address = ipaddress.IPv4Address(value) if type(value) is str else None
    except ipaddress.AddressValueError:
        address = None
    if address is None or not any(address in network for network in PRIVATE_NETS):
        raise ValueError('Choose a numeric private IPv4 address on your local network')
    return str(address)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate field')
            result[key] = value
        return result

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError('Nonfinite value')
        return parsed

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_float=number,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite value')))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise DeviceError('Malformed network protocol data') from error


def _record(value):
    if type(value) is not dict or set(value) != {'id', 'ip', 'keyhex', 'label'}:
        raise ValueError('A pairing needs its device identity, private address, label and key')
    identity, key, label = value['id'], value['keyhex'], value['label']
    if (type(identity) is not str or not DEVICE_ID.fullmatch(identity)
            or type(key) is not str or not HEX64.fullmatch(key)
            or type(label) is not str or not 1 <= len(label.encode('utf-8')) <= 128
            or any(ord(c) < 32 or ord(c) == 127 for c in label)):
        raise ValueError('Invalid pairing identity, label or key')
    ip = '' if value['ip'] == '' else validate_ip(value['ip'])
    return dict(id=identity, ip=ip, keyhex=key, label=label)


class PairingStore:
    """One Studio process owns this atomic, private JSON store.

    list()/public_list() deliberately omit keys. get() returns a private copy
    for the trusted bridge constructor, and must not be exposed by an HTTP API.
    Empty IP is allowed while USB provisioning waits for DHCP.
    """
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else PAIRINGS
        self._lock = threading.RLock()

    def _read(self):
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise DeviceError('Pairing storage cannot use a symbolic link')
        try:
            descriptor = os.open(self.path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        except FileNotFoundError:
            return []
        except OSError:
            raise DeviceError('Cannot read private pairing storage') from None
        try:
            with os.fdopen(descriptor, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 65536:
                    raise DeviceError('Pairing storage must be a private, bounded regular file')
                value = _json(stream.read(65537))
            if (type(value) is not dict or set(value) != {'version', 'devices'}
                    or type(value['version']) is not int or value['version'] != 1
                    or type(value['devices']) is not list or len(value['devices']) > MAX_PAIRINGS):
                raise ValueError('Invalid store')
            records = [_record(row) for row in value['devices']]
            if len({row['id'] for row in records}) != len(records):
                raise ValueError('Duplicate device')
            return records
        except (ValueError, OSError, UnicodeError):
            raise DeviceError('Invalid private pairing storage; it was not overwritten') from None

    def _write(self, records):
        parent = self.path.parent
        if self.path.is_symlink() or parent.is_symlink():
            raise DeviceError('Pairing storage cannot use a symbolic link')
        parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        parent.chmod(0o700)
        descriptor, temporary = tempfile.mkstemp(prefix='.pairings-', dir=parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(dict(version=1, devices=records), stream, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(',', ':'))
                stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            # Persist the rename as well as the file contents.
            directory = os.open(parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            raise DeviceError('Cannot save private pairing storage') from None
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def list(self):
        with self._lock:
            return [{key: row[key] for key in ('id', 'label', 'ip')} for row in self._read()]

    public_list = list

    def get(self, identity):
        with self._lock:
            for row in self._read():
                if row['id'] == identity:
                    return dict(row)
        raise DeviceError('This device is not paired with Studio')

    def put(self, record):
        checked = _record(record)
        with self._lock:
            records = [row for row in self._read() if row['id'] != checked['id']]
            if len(records) >= MAX_PAIRINGS:
                raise DeviceError('The pairing store is full')
            records.append(checked)
            self._write(sorted(records, key=lambda row: row['id']))
        return {key: checked[key] for key in ('id', 'label', 'ip')}

    save = put

    def update_ip(self, identity, address):
        """Update DHCP metadata without writing back a stale pairing key."""
        address = validate_ip(address)
        with self._lock:
            records = self._read()
            for row in records:
                if row['id'] == identity:
                    if row['ip'] != address:
                        row['ip'] = address
                        self._write(records)
                    return {key: row[key] for key in ('id', 'label', 'ip')}
        return None

    def remove(self, identity):
        with self._lock:
            records = self._read()
            updated = [row for row in records if row['id'] != identity]
            if len(records) != len(updated):
                self._write(updated)


class AuthenticatedSocketStream:
    """Synchronous authenticated requests exposed as a serial-style stream.

    write never retries. A timeout/error can mean a mutating command executed
    without its reply reaching us; close and inspect a fresh connection rather
    than automatically repeating it. All sequence/MAC checks precede parsing the
    embedded player response. Socket creation is injectable for portable tests.
    """
    def __init__(self, record, *, socket_factory=None, clock=None, nonce_factory=None):
        self._record = _record(record)
        ip = validate_ip(self._record['ip'])
        self._key = bytes.fromhex(self._record['keyhex'])
        self._clock = clock or time.monotonic
        self._pending = bytearray()
        self._received = bytearray()
        self._seq = 0
        self.closed = False
        self._socket = None
        try:
            factory = socket_factory or socket.create_connection
            self._socket = factory((ip, PORT), timeout=3)
            hello = _json(self._line(self._clock() + 3))
            if (type(hello) is not dict or set(hello) != {'protocol', 'nonce', 'device_id'}
                    or hello['protocol'] != 'rnbo-wifi-v1'
                    or hello['device_id'] != self._record['id']
                    or type(hello['nonce']) is not str or not HEX64.fullmatch(hello['nonce'])):
                raise DeviceError('The network peer is not the paired RNBO device')
            self._nonce = hello['nonce']
            self._client_nonce = (nonce_factory or (lambda: secrets.token_hex(32)))()
            if type(self._client_nonce) is not str or not HEX64.fullmatch(self._client_nonce):
                raise DeviceError('Cannot create a fresh network challenge')
            self._context = self._nonce + ' ' + self._client_nonce
            self._send(dict(client_nonce=self._client_nonce, auth=self._mac('AUTH ' + self._context)), 3)
            acknowledgement = _json(self._line(self._clock() + 3))
            if (type(acknowledgement) is not dict or set(acknowledgement) != {'authenticated'}
                    or acknowledgement['authenticated'] is not True):
                raise DeviceError('The network device did not accept authentication')
        except Exception as error:
            self.close()
            self._raise(error)

    def _mac(self, message):
        return hmac.new(self._key, ('RNBO-WIFI1 ' + message).encode('utf-8'), hashlib.sha256).hexdigest()

    @staticmethod
    def _raise(error):
        if isinstance(error, (socket.timeout, TimeoutError, ProtocolTimeout)):
            raise ProtocolTimeout('The Wi-Fi request timed out; its command was not retried') from None
        if isinstance(error, DeviceError):
            raise error from None
        # Never expose socket/fake/library error contents, which may include
        # credentials or a raw peer packet. Address/keys are not logged here.
        raise DeviceError('The authenticated Wi-Fi connection failed') from None

    def _line(self, deadline):
        while True:
            end = self._pending.find(b'\n')
            if end >= 0:
                if end > MAX_WIRE:
                    raise DeviceError('The Wi-Fi response exceeded its size limit')
                line = bytes(self._pending[:end]); del self._pending[:end + 1]
                return line
            if len(self._pending) > MAX_WIRE:
                raise DeviceError('The Wi-Fi response exceeded its size limit')
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise ProtocolTimeout('The Wi-Fi request timed out')
            self._socket.settimeout(remaining)
            chunk = self._socket.recv(min(4096, MAX_WIRE + 1 - len(self._pending)))
            if not chunk:
                raise DeviceError('The Wi-Fi connection ended before a complete response')
            self._pending.extend(chunk)

    def _send(self, value, timeout):
        self._socket.settimeout(timeout)
        self._socket.sendall(json.dumps(value, ensure_ascii=False, allow_nan=False,
            separators=(',', ':')).encode('utf-8') + b'\n')

    def write(self, payload):
        try:
            if (self.closed or type(payload) is not bytes or len(payload) > MAX_WIRE
                    or not payload.endswith(b'\n')):
                raise DeviceError('The Wi-Fi command is not a complete command line')
            commands = payload[:-1].split(b'\n')
            if (not commands or any(not command or len(command) > MAX_COMMAND
                    or any(byte < 32 or byte > 126 for byte in command) for command in commands)):
                raise DeviceError('The Wi-Fi command is outside the player protocol limits')
            for raw in commands:
                if self._seq >= 0xffffffff:
                    raise DeviceError('Reconnect before the network sequence is exhausted')
                command = raw.decode('ascii')
                sequence = self._seq + 1
                timeout = 60 if command == 'player-commit' else 3
                deadline = self._clock() + timeout
                self._send(dict(seq=sequence, command=command,
                    mac=self._mac(f'REQUEST {self._context} {sequence} {command}')), timeout)
                envelope = _json(self._line(deadline))
                if (type(envelope) is not dict or set(envelope) != {'seq', 'response', 'mac'}
                        or type(envelope['seq']) is not int or envelope['seq'] != sequence
                        or type(envelope['response']) is not str or type(envelope['mac']) is not str
                        or not HEX64.fullmatch(envelope['mac'])):
                    raise DeviceError('The Wi-Fi response sequence or envelope is invalid')
                response = envelope['response']
                if (len(response.encode('utf-8')) > MAX_LINE or not hmac.compare_digest(envelope['mac'],
                        self._mac(f'RESPONSE {self._context} {sequence} {response}'))):
                    raise DeviceError('The Wi-Fi response authentication failed')
                # Only authenticated bytes can now become a player JSON reply.
                parsed = _json(response)
                if type(parsed) is not dict:
                    raise DeviceError('The authenticated response is not a player JSON object')
                line = json.dumps(parsed, ensure_ascii=False, allow_nan=False,
                    separators=(',', ':')).encode('utf-8')
                if len(line) > MAX_LINE or len(self._received) + len(line) + 1 > MAX_WIRE:
                    raise DeviceError('The authenticated reply queue exceeded its size limit')
                self._received.extend(line + b'\n')
                self._seq = sequence
            return len(payload)
        except Exception as error:
            self.close()
            self._raise(error)

    @property
    def in_waiting(self):
        return len(self._received)

    def read(self, count):
        if self.closed:
            raise DeviceError('The Wi-Fi connection is closed')
        result = bytes(self._received[:count]); del self._received[:count]
        return result

    def close(self):
        self.closed = True
        self._received.clear(); self._pending.clear()
        connection, self._socket = self._socket, None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


class NetworkBridge(DeviceBridge):
    def __init__(self, paired_record, *, socket_factory=None, clock=None, sleep=None, nonce_factory=None):
        super().__init__(ports=lambda: [], clock=clock, sleep=sleep)
        self._record = _record(paired_record)
        self._ip = self._record['ip']
        self._socket_factory = socket_factory
        self._nonce_factory = nonce_factory

    def scan(self):
        return []  # Network pairings are listed by PairingStore, never USB.

    def _select(self, port=None):
        # The inherited package upload's port argument is intentionally ignored.
        return dict(port=validate_ip(self._ip), serial_number=self._record['id'])

    def _connect(self, identity, *, board=None, firmware=None, boot=None, events=None):
        self._disconnect()
        record = dict(self._record, ip=validate_ip(identity['port']))
        try:
            self._stream = AuthenticatedSocketStream(record, socket_factory=self._socket_factory,
                clock=self._clock, nonce_factory=self._nonce_factory)
            self._identity = dict(port=record['ip'], serial_number=record['id'])
            self._board, self._firmware, self._player = board, firmware, True
            return self._snapshot()  # First signed player-info proves the peer key.
        except Exception:
            self._disconnect()
            raise

    def _exchange(self, *args, **kwargs):
        try:
            return super()._exchange(*args, **kwargs)
        except Exception:
            self._disconnect()  # No retry/abort mutation on an uncertain session.
            raise

    def _snapshot(self):
        result = super()._snapshot()
        result['device'].update(transport='wifi', device_id=self._record['id'])
        return result

    def connect_network(self, ip=None):
        address = validate_ip(self._ip if ip is None else ip)
        with self._exclusive():
            self._ip = address
            return self._connect(self._select())

    def connect(self, port=None):
        return self.connect_network(port)

    def flash(self, *args, **kwargs):
        raise DeviceError('Player firmware installation requires USB; Wi-Fi only loads patch packages')
