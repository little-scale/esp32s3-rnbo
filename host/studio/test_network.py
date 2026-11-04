# SPDX-License-Identifier: MIT
"""Authenticated framing and existing player checks, using fake sockets only."""
import hashlib
import hmac
import json
from pathlib import Path
import socket
import stat
import tempfile
import unittest
from unittest.mock import patch

import network as n
import test_player as existing

RECORD = dict(id='001122334455', ip='192.168.1.8', keyhex='ab' * 32, label='Test Player')
SERVER_NONCE = '11' * 32
CLIENT_NONCE = '22' * 32


class Peer:
    """Independent fake server validates the canonical wire MAC messages."""
    def __init__(self, clock=None, player=None, **changes):
        self.clock = clock or existing.legacy.Clock()
        self.player = player or existing.Player()
        self.device_id = RECORD['id']; self.key = bytes.fromhex(RECORD['keyhex'])
        self.server_nonce = SERVER_NONCE; self.pending = bytearray(); self.sent = []
        self.closed = False; self.timeouts = []; self.fragment = 7; self.delay = 0
        self.auth_ack = True; self.bad_mac = False; self.bad_seq = False
        self.response_override = None; self.replay = None; self.responses = []
        self.timeout_command = None; self.eof = False; self.client_nonce = None
        for key, value in changes.items(): setattr(self, key, value)
        self.queue(dict(protocol='rnbo-wifi-v1', nonce=self.server_nonce, device_id=self.device_id))

    def queue(self, value):
        self.pending.extend(json.dumps(value, separators=(',', ':')).encode() + b'\n')

    def sign(self, text):
        return hmac.new(self.key, text.encode('utf-8'), hashlib.sha256).hexdigest()

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def recv(self, count):
        self.clock.sleep(self.delay)
        if not self.pending:
            if self.eof: return b''
            raise socket.timeout('not included in public errors: ' + RECORD['keyhex'])
        size = min(count, self.fragment, len(self.pending))
        result = bytes(self.pending[:size]); del self.pending[:size]
        return result

    def sendall(self, raw):
        value = json.loads(raw); self.sent.append(value)
        if 'auth' in value:
            self.client_nonce = value['client_nonce']
            self.assertion = self.sign('RNBO-WIFI1 AUTH ' + self.server_nonce + ' ' + self.client_nonce)
            accepted = hmac.compare_digest(value['auth'], self.assertion)
            self.queue(dict(authenticated=self.auth_ack if accepted else False))
            return
        sequence, command = value['seq'], value['command']
        context = self.server_nonce + ' ' + self.client_nonce
        expected = self.sign(f'RNBO-WIFI1 REQUEST {context} {sequence} {command}')
        if not hmac.compare_digest(value['mac'], expected):
            raise AssertionError('Client request MAC differs from the independent protocol')
        response = self.player.response(command).decode().strip()
        if self.timeout_command == command:
            return  # Command executed; response lost. It must never be retried.
        if self.response_override is not None: response = self.response_override
        envelope = dict(seq=sequence - 1 if self.bad_seq else sequence, response=response,
            mac='00' * 32 if self.bad_mac else self.sign(f'RNBO-WIFI1 RESPONSE {context} {sequence} {response}'))
        if self.replay is not None: envelope = self.replay
        self.responses.append(dict(envelope)); self.queue(envelope)

    def close(self): self.closed = True


class TransportTests(unittest.TestCase):
    def stream(self, peer=None, record=None, client_nonce=CLIENT_NONCE):
        peer = peer or Peer()
        self.peer = peer
        def factory(address, timeout):
            self.assertEqual(address, (RECORD['ip'], 8789)); self.assertEqual(timeout, 3)
            return peer
        return n.AuthenticatedSocketStream(record or RECORD, socket_factory=factory,
            clock=peer.clock.time, nonce_factory=lambda: client_nonce)

    def test_canonical_auth_and_fragmented_signed_reply(self):
        stream = self.stream(); self.assertTrue(self.peer.client_nonce)
        self.assertEqual(self.peer.sent[0], dict(client_nonce=CLIENT_NONCE, auth=self.peer.assertion))
        payload = b'player-info\n'; self.assertEqual(stream.write(payload), len(payload))
        reply = bytearray()
        while stream.in_waiting: reply.extend(stream.read(3))
        self.assertEqual(json.loads(reply)['runtime'], 'rnbo-esp32s3-player')
        self.assertEqual(self.peer.sent[-1]['seq'], 1)
        stream.write(payload); self.assertEqual(self.peer.sent[-1]['seq'], 2)
        stream.close(); self.assertTrue(self.peer.closed)

    def test_wrong_device_rejected_before_sending_auth(self):
        peer = Peer(device_id='aabbccddeeff')
        with self.assertRaisesRegex(n.DeviceError, 'paired RNBO'): self.stream(peer)
        self.assertEqual(peer.sent, []); self.assertTrue(peer.closed)

    def test_wrong_key_and_nonboolean_auth_ack_rejected(self):
        for peer, record in ((Peer(), dict(RECORD, keyhex='cd' * 32)), (Peer(auth_ack=1), RECORD)):
            with self.subTest(record=record['id']), self.assertRaises(n.DeviceError): self.stream(peer, record)
            self.assertTrue(peer.closed)

    def test_response_mac_checked_before_embedded_JSON(self):
        stream = self.stream(Peer(response_override='{this is invalid', bad_mac=True))
        with self.assertRaisesRegex(n.DeviceError, 'authentication'): stream.write(b'player-info\n')
        self.assertTrue(stream.closed); self.assertEqual(stream.in_waiting, 0)

    def test_signed_malformed_JSON_or_wrong_sequence_rejected(self):
        for peer in (Peer(response_override='{invalid'), Peer(bad_seq=True)):
            stream = self.stream(peer)
            with self.assertRaises(n.DeviceError): stream.write(b'player-info\n')
            self.assertTrue(peer.closed)

    def test_recorded_response_cannot_replay_on_fresh_client_challenge(self):
        first = Peer(); stream = self.stream(first)
        stream.write(b'player-info\n'); recorded = first.responses[-1]; stream.close()
        peer = Peer(replay=recorded)
        next_stream = self.stream(peer, client_nonce='33' * 32)
        with self.assertRaisesRegex(n.DeviceError, 'authentication'):
            next_stream.write(b'player-info\n')
        self.assertTrue(peer.closed)

    def test_same_session_replay_and_corrupt_payload_rejected(self):
        peer = Peer(); stream = self.stream(peer); stream.write(b'player-info\n')
        peer.replay = peer.responses[-1]
        with self.assertRaisesRegex(n.DeviceError, 'sequence'): stream.write(b'player-info\n')
        peer = Peer(); stream = self.stream(peer); peer.bad_mac = True
        with self.assertRaises(n.DeviceError): stream.write(b'player-info\n')

    def test_time_limit_is_total_even_when_peer_trickles(self):
        peer = Peer(); stream = self.stream(peer); peer.fragment = 1; peer.delay = .5
        with self.assertRaises(n.ProtocolTimeout): stream.write(b'player-info\n')
        self.assertTrue(peer.closed)
        self.assertEqual(sum(frame.get('command') == 'player-info' for frame in peer.sent), 1)

    def test_oversized_or_truncated_wire_closes(self):
        for raw in (b'x' * (n.MAX_WIRE + 1), b'{"protocol":'):
            peer = Peer(); peer.pending[:] = raw; peer.eof = True; peer.fragment = 4096
            with self.assertRaises(n.DeviceError): self.stream(peer)
            self.assertTrue(peer.closed)

    def test_invalid_command_sends_no_request(self):
        for payload in (b'player-info', b'\n', b'x' * 8192 + b'\n', b'player-info\r\n', b'bad\0command\n'):
            peer = Peer(); stream = self.stream(peer); before = len(peer.sent)
            with self.subTest(payload=payload[:30]), self.assertRaises(n.DeviceError): stream.write(payload)
            self.assertEqual(len(peer.sent), before)

    def test_commit_gets_long_timeout_without_retry(self):
        peer = Peer(); stream = self.stream(peer)
        peer.player.response = lambda command: b'{"upload":"committed"}\n'
        stream.write(b'player-commit\n')
        self.assertTrue(any(timeout > 59 for timeout in peer.timeouts))


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / 'private/pairings.json'
        self.store = n.PairingStore(self.path)

    def test_private_atomic_storage_and_public_listing(self):
        self.assertEqual(self.store.list(), [])
        public = self.store.put(dict(RECORD, ip=''))
        self.assertEqual(public, {key: dict(RECORD, ip='')[key] for key in ('id', 'label', 'ip')})
        self.assertNotIn(RECORD['keyhex'], json.dumps(self.store.list()))
        self.assertEqual(self.store.get(RECORD['id'])['keyhex'], RECORD['keyhex'])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.store.save(RECORD); self.assertEqual(len(self.store.public_list()), 1)
        self.assertEqual(list(self.path.parent.glob('.pairings-*')), [])
        self.store.remove(RECORD['id']); self.assertEqual(self.store.list(), [])

    def test_invalid_record_cannot_replace_saved_pairing(self):
        self.store.put(RECORD); old = self.path.read_bytes()
        for changes in (dict(ip='8.8.8.8'), dict(keyhex='secret'), dict(id='not-a-device'), dict(label='bad\nlabel')):
            with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError): self.store.put(dict(RECORD, **changes))
            self.assertEqual(self.path.read_bytes(), old)

    def test_DHCP_update_preserves_a_concurrently_rotated_pairing_key(self):
        self.store.put(RECORD)
        stale = self.store.get(RECORD['id'])
        rotated = dict(RECORD, keyhex='cd' * 32, label='New Pairing')
        self.store.put(rotated)
        public = self.store.update_ip(RECORD['id'], '10.1.2.3')
        self.assertEqual(stale['keyhex'], RECORD['keyhex'])
        self.assertEqual(self.store.get(RECORD['id']), dict(rotated, ip='10.1.2.3'))
        self.assertEqual(public, dict(id=RECORD['id'], label='New Pairing', ip='10.1.2.3'))
        saved = self.path.read_bytes()
        self.assertIsNone(self.store.update_ip('aabbccddeeff', '10.2.3.4'))
        self.assertEqual(self.path.read_bytes(), saved)

    def test_corrupt_insecure_and_symlink_storage_not_overwritten(self):
        self.store.put(RECORD); self.path.write_text('{malformed'); old = self.path.read_bytes()
        with self.assertRaises(n.DeviceError): self.store.put(RECORD)
        self.assertEqual(self.path.read_bytes(), old)
        self.path.unlink(); self.store.put(RECORD); self.path.chmod(0o644)
        with self.assertRaises(n.DeviceError): self.store.get(RECORD['id'])
        self.path.unlink(); target = self.path.parent / 'other'; target.write_text('preserve')
        self.path.symlink_to(target)
        with self.assertRaises(n.DeviceError): self.store.put(RECORD)
        self.assertEqual(target.read_text(), 'preserve')

    def test_only_RFC1918_numeric_IPs_accepted(self):
        for value in ('10.1.2.3', '172.16.0.1', '172.31.255.254', '192.168.4.1'):
            self.assertEqual(n.validate_ip(value), value)
        for value in ('127.0.0.1', '8.8.8.8', '169.254.1.2', '172.32.0.1', '224.0.0.1',
                      'localhost', '192.168.1.8.example', '::1', '::ffff:192.168.1.8', 123, None, ''):
            with self.subTest(value=value), self.assertRaises(ValueError): n.validate_ip(value)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.clock = existing.legacy.Clock(); self.player = existing.Player(); self.peers = []
        def factory(address, timeout):
            self.assertEqual(address, (RECORD['ip'], 8789))
            peer = Peer(clock=self.clock, player=self.player); self.peers.append(peer); return peer
        self.bridge = n.NetworkBridge(RECORD, socket_factory=factory, clock=self.clock.time,
            sleep=self.clock.sleep, nonce_factory=lambda: CLIENT_NONCE)
        self.bridge._ports = lambda: self.fail('Network bridge must not enumerate USB')
        self.bridge._opener = lambda *a: self.fail('Network bridge must not open serial')
        self.bridge._runner = lambda *a, **k: self.fail('Network bridge must not run ROM tools')

    def test_direct_signed_player_connect_control_and_transport_labels(self):
        self.assertEqual(self.bridge.snapshot(), dict(device=None, parameters=[]))
        result = self.bridge.connect_network()
        self.assertEqual(result['device']['transport'], 'wifi')
        self.assertEqual(result['device']['device_id'], RECORD['id'])
        self.assertEqual(result['parameters'], []); self.assertEqual(self.bridge.scan(), [])
        result = self.bridge.control(dict(action='volume', value=7))
        self.assertEqual(result['device']['volume'], 7)
        self.assertTrue(self.bridge.control(dict(action='pause'))['device']['paused'])
        self.assertFalse(any(command in ('status', 'parameters') for command in self.player.commands))
        with self.assertRaisesRegex(n.DeviceError, 'requires USB'): self.bridge.flash(None, None, None, None)

    def test_empty_address_or_unsafe_target_does_not_create_socket(self):
        for address in ('', '127.0.0.1', 'example.com'):
            with self.assertRaises(ValueError): self.bridge.connect_network(address)
        self.assertEqual(self.peers, [])

    def test_mutation_timeout_closes_without_automatic_retry(self):
        self.bridge.connect_network(); self.peers[-1].timeout_command = 'player-volume 13'
        with self.assertRaises(n.ProtocolTimeout) as caught:
            self.bridge.control(dict(action='volume', value=13))
        self.assertEqual(self.player.commands.count('player-volume 13'), 1)
        self.assertEqual(self.player.volume, 13)  # Executed despite lost ACK.
        self.assertTrue(self.peers[-1].closed); self.assertIsNone(self.bridge._stream)
        self.assertNotIn(RECORD['keyhex'], str(caught.exception))

    def test_inherited_package_checks_and_contiguous_commit_reused(self):
        self.assertIs(n.NetworkBridge.upload_package, n.DeviceBridge.upload_package)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.rnbopkg'; path.write_bytes(bytes(range(256)) * 9)
            package = dict(role='main', arena_bytes=4096,
                package_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                metadata=dict(source_sha256='b' * 64, initial_volume=25))
            with patch.dict(n.DeviceBridge.upload_package.__globals__, parse_package=lambda _: package):
                result = self.bridge.upload_package(path, '/dev/ignored', lambda _: None,
                    expected_sha256=package['package_sha256'])
                self.assertEqual(result['device']['generation'], 1)
                self.assertEqual(result['device']['transport'], 'wifi')
                self.assertEqual(self.player.data, path.read_bytes())
                self.assertEqual([int(command.split()[1]) for command in self.player.commands
                    if command.startswith('player-data ')], [0, 1024, 2048])
                self.player.bad_commit = True
                with self.assertRaisesRegex(n.DeviceError, 'complete package commit'):
                    self.bridge.upload_package(path, None, lambda _: None)

    def test_false_offset_and_stale_generation_remain_rejections(self):
        self.player.main = dict(name='Test', package_sha256='a' * 64, source_sha256='b' * 64,
            arena_bytes=4096, arena_used=0, context_bytes=32, sample_position=0,
            parameter_count=1, parameters=[dict(index=0, name='Gain', min=0, max=1, initial=.5, actual=.5, normalized=.5)])
        self.player.generation = 2; self.player.paused = False
        self.bridge.connect_network()
        with self.assertRaisesRegex(n.DeviceError, 'changed'):
            self.bridge.control(dict(action='param', role='main', generation=1, index=0, value=.5))
        self.assertFalse(any(command.startswith('player-param ') for command in self.player.commands))


if __name__ == '__main__':
    unittest.main()
