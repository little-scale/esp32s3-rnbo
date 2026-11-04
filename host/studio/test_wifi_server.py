# SPDX-License-Identifier: MIT
"""Wi-Fi setup/routing at the local server boundary; no credentials or hardware."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('wifi_server_under_test',Path(__file__).with_name('server.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
IDENTITY='001122334455'
class USB:
    def __init__(self):
        self.calls=[];self.device=dict(device_id=IDENTITY,transport='usb',board='xiao',board_model='XIAO',
            wifi=dict(supported=True,configured=False,connected=False,ip='',device_id=IDENTITY))
    def snapshot(self):return dict(device=copy.deepcopy(self.device),parameters=[])
    def scan_wifi(self):self.calls.append(('scan',));return dict(networks=[dict(ssid='Test network',rssi=-40,channel=1,secure=True)])
    def configure_wifi(self,ssid,password,key):
        self.calls.append(('setup',ssid,password,key));self.device['wifi']['configured']=True;return self.snapshot()
    def forget_wifi(self):
        self.calls.append(('forget',));self.device['wifi'].update(configured=False,connected=False,ip='');return self.snapshot()
    def control(self,data):self.calls.append(('control',data));return self.snapshot()
    def disconnect(self):self.calls.append(('disconnect',))
    def connect(self,port):self.calls.append(('connect',port));return self.snapshot()
class WifiServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.private=Path(self.temp.name)/'private';self.patcher=patch.object(s,'PRIVATE',self.private);self.patcher.start();self.addCleanup(self.patcher.stop)
        self.usb=USB();self.studio=s.Studio(bridge=self.usb)
    def test_usb_setup_persists_only_key_and_later_dhcp_updates_public_address(self):
        result=self.studio.setup_wifi(dict(ssid='Example network',password='test-only-password'))
        self.assertTrue(result['wifi']['paired']);self.assertEqual(result['paired'][0]['ip'],'')
        raw=(self.private/'pairings.json').read_text();self.assertNotIn('test-only-password',raw);self.assertNotIn('Example network',raw)
        key=self.usb.calls[0][3];self.assertEqual(len(key),64);self.assertNotIn(key,json.dumps(result))
        self.usb.device['wifi'].update(connected=True,ip='192.168.1.23')
        self.assertEqual(self.studio.wifi_status()['paired'][0]['ip'],'192.168.1.23')
        with patch.object(self.studio.pairings,'_write',side_effect=AssertionError('unchanged status must not rewrite storage')):
            self.studio.wifi_status()
    def test_scanning_is_usb_only_does_not_pair_and_releases_worker_on_failure(self):
        self.assertEqual(self.studio.scan_wifi()['networks'][0]['ssid'],'Test network')
        self.assertEqual(self.studio.pairings.public_list(),[])
        self.studio.active_bridge=object()
        with self.assertRaisesRegex(ValueError,'USB'):self.studio.scan_wifi()
        self.studio.active_bridge=self.usb
        with patch.object(self.usb,'scan_wifi',side_effect=RuntimeError('scan failed')):
            with self.assertRaises(RuntimeError):self.studio.scan_wifi()
        self.assertFalse(self.studio.worker.locked())
    def test_setup_and_forget_require_usb_and_idle_worker(self):
        self.studio.active_bridge=object()
        with self.assertRaisesRegex(ValueError,'USB'):self.studio.setup_wifi(dict(ssid='x',password='12345678'))
        with self.assertRaisesRegex(ValueError,'USB'):self.studio.forget_wifi()
        self.assertEqual(self.usb.calls,[])
        self.studio.active_bridge=self.usb;self.studio.worker.acquire()
        with self.assertRaisesRegex(ValueError,'Wait'):self.studio.setup_wifi({})
        self.studio.worker.release()
    def test_forget_removes_only_matching_pairing_and_does_not_publish_keys(self):
        self.studio.setup_wifi(dict(ssid='x',password='12345678'))
        self.studio.pairings.put(dict(id='aabbccddeeff',label='Other',ip='',keyhex='1'*64))
        result=self.studio.forget_wifi();self.assertFalse(result['wifi']['configured'])
        self.assertEqual([p['id'] for p in result['paired']],['aabbccddeeff'])
        self.assertFalse(self.studio.worker.locked())
    def test_failed_setup_never_saves_pairing_and_releases_worker(self):
        with patch.object(self.usb,'configure_wifi',side_effect=RuntimeError('setup failed')):
            with self.assertRaises(RuntimeError):self.studio.setup_wifi(dict(ssid='x',password='12345678'))
        self.assertFalse(self.studio.worker.locked());self.assertEqual(self.studio.pairings.public_list(),[])
    def test_wifi_connect_selects_paired_target_and_usb_return_closes_network(self):
        self.studio.pairings.put(dict(id=IDENTITY,label='XIAO',ip='192.168.1.3',keyhex='a'*64))
        import host.studio.network as n
        class Network:
            def __init__(inner,record):inner.record=record;inner.closed=False
            def connect_network(inner,ip):inner.ip=ip;return dict(device=dict(transport='wifi',device_id=IDENTITY),parameters=[])
            def disconnect(inner):inner.closed=True
        with patch.object(n,'NetworkBridge',Network):
            result=self.studio.connect_wifi(dict(id=IDENTITY,ip='192.168.1.4'));network=self.studio.active_bridge
        self.assertEqual(result['device']['transport'],'wifi');self.assertEqual(network.ip,'192.168.1.4')
        self.assertIn(('disconnect',),self.usb.calls)
        self.studio.connect_usb('test-port');self.assertTrue(network.closed);self.assertIs(self.studio.active_bridge,self.usb)
        with self.assertRaises(ValueError):self.studio.connect_wifi(dict(id=IDENTITY,ip='8.8.8.8'))
    def test_controls_check_connection_target_and_busy_worker_before_dispatch(self):
        payload=dict(action='volume',value=25,target=dict(device_id=IDENTITY,transport='usb'))
        self.studio.control_device(payload)
        self.assertEqual(self.usb.calls[-1],('control',dict(action='volume',value=25)))
        count=len(self.usb.calls)
        for target in [None,dict(device_id='aabbccddeeff',transport='usb'),dict(device_id=IDENTITY,transport='wifi')]:
            with self.assertRaises(ValueError):self.studio.control_device(dict(payload,target=target))
        self.studio.worker.acquire()
        try:
            with self.assertRaisesRegex(ValueError,'Wait'):self.studio.control_device(payload)
        finally:self.studio.worker.release()
        self.assertEqual(len(self.usb.calls),count)
    def test_unsupported_network_address_does_not_hide_healthy_usb_device(self):
        self.studio.setup_wifi(dict(ssid='x',password='12345678'))
        self.usb.device['wifi'].update(connected=True,ip='8.8.8.8')
        self.assertEqual(self.studio.device_snapshot()['device']['transport'],'usb')
        self.assertIn('private IPv4',self.studio.wifi_status()['wifi']['error'])
        self.assertEqual(self.studio.pairings.public_list()[0]['ip'],'')
    def test_new_explicit_audio_profile_is_accepted_without_changing_default(self):
        patch=dict(patcher=dict(classnamespace='rnbo',boxes=[],lines=[]))
        self.assertEqual(s.build_settings(dict(patch=patch))['numerical_profile'],'float32-auto-v1')
        self.assertEqual(s.build_settings(dict(patch=patch,numerical_profile='float32-audio-v3'))['numerical_profile'],'float32-audio-v3')
    def test_unpaired_board_status_is_visible_without_creating_pairing(self):
        self.assertTrue(self.studio.device_snapshot()['device']['wifi']['supported'])
        self.assertEqual(self.studio.wifi_status()['paired'],[])
if __name__=='__main__':unittest.main()
