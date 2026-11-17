# SPDX-License-Identifier: MIT
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from host.studio import dual_runtime as runtime, paired_helper as helper
from test_server import s, FakeBridge
from test_native_export import payload

MAC = '001122334455'
TARGET = dict(mac=MAC, port='/dev/test-esp')


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.engine = 'synthdef'; self.rate=16000
        self.dual = Mock()
        self.dual.MODELS = {'xiao':'XIAO ESP32-S3'}
        self.dual.probe.side_effect = lambda *a: dict(model='XIAO ESP32-S3', rate=self.rate, engine=self.engine, busy=False)
        self.dual.device_lock.side_effect = lambda *a: nullcontext()
        self.dual.wait_port.return_value = TARGET['port']
        self.dual.boot.side_effect = lambda board, engine, *args: setattr(self, 'engine', engine)
        self.apps = Mock(ROOT=Path('/companion'))
        self.apps.load_targets.return_value = (b'synth', b'rnbo')

    def call(self, action, **kw):
        return helper.perform(self.dual,self.apps,action,TARGET,Path('/rnbo-build'),Path('/sc-build'),**kw)

    def test_inspect_uses_live_probe_only_and_same_engine_never_reboots(self):
        self.assertEqual(self.call('inspect')['engine'],'synthdef')
        self.call('synthdef',expected_engine='synthdef')
        self.dual.fade.assert_not_called(); self.dual.boot.assert_not_called()
        self.apps.load_targets.assert_not_called()

    def test_wrong_board_rate_busy_inventory_or_changed_engine_stops_before_fade(self):
        for field,value in [('model','Other'),('rate',44100),('busy',True),('engine','rnbo')]:
            with self.subTest(field=field):
                self.dual.probe.side_effect=None
                self.dual.probe.return_value=dict(model='XIAO ESP32-S3',rate=16000,busy=False,engine='synthdef')
                self.dual.probe.return_value[field]=value
                with self.assertRaises(ValueError):self.call('rnbo',expected_engine='synthdef')
        self.dual.fade.assert_not_called(); self.dual.boot.assert_not_called()

    def test_switch_fades_once_and_checks_the_new_runtime(self):
        result=self.call('rnbo',expected_engine='synthdef')
        self.assertTrue(result['switched']);self.assertEqual(result['engine'],'rnbo')
        self.dual.fade.assert_called_once_with(MAC,'synthdef',TARGET['port'])
        self.dual.boot.assert_called_once_with('xiao','rnbo',MAC,TARGET['port'])

    def test_44100_pair_switches_both_directions_at_the_reviewed_rate(self):
        self.rate=44100
        self.assertEqual(self.call('inspect')['rate'],44100)
        first=self.call('rnbo',expected_engine='synthdef',rate=44100)
        second=self.call('synthdef',expected_engine='rnbo',rate=44100)
        self.assertEqual((first['rate'],second['rate']),(44100,44100))
        self.assertEqual(self.dual.boot.call_count,2)
        self.dual.installed_pair.assert_called_with('xiao',MAC,44100)

    def test_missing_pair_inventory_prevents_any_fade_or_reboot(self):
        self.dual.installed_pair.side_effect=ValueError('Uncommissioned device')
        with self.assertRaisesRegex(ValueError,'Uncommissioned'):
            self.call('rnbo',expected_engine='synthdef')
        self.dual.fade.assert_not_called();self.dual.boot.assert_not_called()

    def test_unidentified_firmware_never_falls_back_to_a_maintenance_reboot(self):
        self.dual.probe.side_effect=None;self.dual.probe.return_value=None
        with self.assertRaisesRegex(ValueError,'no restart or write'):
            self.call('inspect')
        self.dual.fade.assert_not_called();self.dual.boot.assert_not_called()

    def test_changed_build_or_package_is_rejected_before_usb(self):
        with self.assertRaisesRegex(ValueError,'build changed'):
            self.call('update',expected_engine='synthdef',app_sha256='0'*64)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'patch.rnbopkg';p.write_bytes(b'package')
            with self.assertRaisesRegex(ValueError,'package changed'):
                self.call('upload',package=p,package_sha256='0'*64)
        self.dual.probe.assert_not_called(); self.dual.boot.assert_not_called()

    def test_package_admission_precedes_probe_and_route_is_called_once(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'patch.rnbopkg';p.write_bytes(b'package');sha=hashlib.sha256(b'package').hexdigest()
            self.dual.prepare.side_effect=ValueError('Wrong-rate package')
            with self.assertRaisesRegex(ValueError,'Wrong-rate'):
                self.call('upload',package=p,package_sha256=sha)
            self.dual.probe.assert_not_called()
            self.dual.prepare.side_effect=None
            self.dual.route.return_value=dict(verified=True,package_sha256=sha)
            self.call('upload',package=p,package_sha256=sha,expected_engine='synthdef')
            self.dual.route.assert_called_once()

    def test_update_calls_only_the_guarded_rnbo_updater_and_restores_selection(self):
        runner=Mock(return_value=subprocess.CompletedProcess([],0,stdout='verified',stderr=''))
        result=self.call('update',expected_engine='synthdef',app_sha256=hashlib.sha256(b'rnbo').hexdigest(),runner=runner)
        command=runner.call_args.args[0]
        self.assertIn('update',command);self.assertEqual(command[command.index('--engine')+1],'rnbo')
        self.assertNotIn('setup',command);self.assertNotIn('erase_flash',command)
        self.assertTrue(result['updated']);self.assertEqual(result['engine'],'synthdef')
        self.dual.boot.assert_not_called()


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.row=dict(port=TARGET['port'],vid=0x303a,serial_number=MAC)
        self.bridge=Mock()
        self.bridge._exclusive.side_effect=lambda:nullcontext()
        self.bridge._select.side_effect=lambda port:dict(self.row)
        self.clock=0
        self.adapter=runtime.PairedXiao(self.bridge,clock=lambda:self.clock)
        self.adapter.run=Mock(return_value=dict(engine='synthdef',rate=16000,device_id=MAC,ready=True))

    def test_hotplug_expiry_and_replay_prevent_child_mutations(self):
        item=self.adapter.inspect(TARGET['port']);self.adapter.run.reset_mock()
        self.row['serial_number']='aabbccddeeff'
        with self.assertRaisesRegex(RuntimeError,'changed'):self.adapter.perform(item['inspection'],TARGET['port'],'rnbo',rate=16000)
        self.adapter.run.assert_not_called()
        self.row['serial_number']=MAC
        item=self.adapter.inspect(TARGET['port']);self.clock=601;self.adapter.run.reset_mock()
        with self.assertRaisesRegex(RuntimeError,'again'):self.adapter.perform(item['inspection'],TARGET['port'],'rnbo',rate=16000)
        self.adapter.run.assert_not_called()
        item=self.adapter.inspect(TARGET['port']);self.adapter.perform(item['inspection'],TARGET['port'],'rnbo',rate=16000)
        with self.assertRaisesRegex(RuntimeError,'again'):self.adapter.perform(item['inspection'],TARGET['port'],'rnbo',rate=16000)

    def test_helper_is_isolated_and_failures_are_not_retried(self):
        runner=Mock(return_value=subprocess.CompletedProcess([],1,stdout='',stderr='Busy USB'))
        adapter=runtime.PairedXiao(self.bridge,runner=runner)
        with patch.object(runtime,'companion_root',return_value=Path('/companion')),patch.object(runtime,'idf_python',return_value=Path('/python')):
            with self.assertRaisesRegex(RuntimeError,'Busy USB'):adapter.run('inspect',target=TARGET)
        runner.assert_called_once();command=runner.call_args.args[0]
        self.assertEqual(command[:3],['/python','-I','-B']);self.assertEqual(json.loads(command[-1])['target'],TARGET)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.studio=s.Studio(bridge=FakeBridge())
        self.studio.paired_xiao=Mock()
        self.studio.paired_xiao.perform.return_value=dict(engine='rnbo',rate=16000,verified=True)

    def test_explicit_xiao_profile_preserves_board_and_headless_startup_volume(self):
        settings=s.build_settings(dict(payload(),board='xiao',profile='voice-pe-16000-256-v1'))
        self.assertEqual((settings['board'],settings['sample_rate'],settings['initial_volume']),('xiao',16000,50))

    def test_pair_actions_never_use_factory_flasher_and_release_worker(self):
        with patch.object(self.studio.bridge,'flash_bundle',create=True,side_effect=AssertionError('No factory flasher')):
            result=self.studio.start_dual(dict(action='rnbo',inspection='token',port=TARGET['port'],rate=16000))
            self.studio.job_thread.join(2)
        self.assertEqual(self.studio.job(result['id'])['state'],'done')
        self.studio.paired_xiao.perform.assert_called_once_with('token',TARGET['port'],'rnbo',rate=16000)
        self.assertFalse(self.studio.worker.locked())

    def test_changed_build_rejects_before_thread_and_wrong_rate_package_never_switches(self):
        self.studio.paired_xiao.options.return_value=dict(available=True,app_sha256='a'*64)
        with self.assertRaisesRegex(ValueError,'changed'):
            self.studio.start_dual(dict(action='update',inspection='token',port=TARGET['port'],rate=16000,app_sha256='b'*64))
        with patch.object(self.studio,'artifact',return_value=Path(__file__)),patch.object(s.player_package,'parse',return_value=dict(sample_rate=44100,block_frames=256)):
            with self.assertRaisesRegex(ValueError,'pair rate'):
                self.studio.start_dual(dict(action='upload',inspection='token',port=TARGET['port'],rate=16000,job_id='a'*32))
        self.studio.paired_xiao.perform.assert_not_called();self.assertEqual(self.studio.jobs,{})

    def test_bad_settings_and_busy_inspection_never_touch_usb(self):
        for data in ({'action':'setup'},{'action':'rnbo','inspection':[],'port':'x'},
                     {'action':'rnbo','inspection':'x','port':'x','board':'xiao'}):
            with self.assertRaises(ValueError):self.studio.start_dual(data)
        self.studio.worker.acquire()
        with self.assertRaisesRegex(ValueError,'busy'):self.studio.inspect_dual({'port':TARGET['port']})
        self.studio.worker.release();self.studio.paired_xiao.inspect.assert_not_called()

    def test_failed_live_probe_releases_worker_without_marking_a_pair_ready(self):
        self.studio.paired_xiao.inspect.side_effect=ValueError('No verified pair inventory')
        with self.assertRaisesRegex(ValueError,'inventory'):
            self.studio.inspect_dual({'port':TARGET['port']})
        self.assertFalse(self.studio.worker.locked())

    def test_failed_paired_action_releases_worker_and_does_not_retry(self):
        self.studio.paired_xiao.perform.side_effect=RuntimeError('Busy peer')
        result=self.studio.start_dual(dict(action='rnbo',inspection='token',port=TARGET['port'],rate=44100))
        self.studio.job_thread.join(2)
        self.assertEqual(self.studio.job(result['id'])['state'],'failed')
        self.assertFalse(self.studio.worker.locked())
        self.studio.paired_xiao.perform.assert_called_once()


if __name__=='__main__':unittest.main()
