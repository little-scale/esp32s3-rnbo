# SPDX-License-Identifier: MIT
import base64
import importlib.util
import struct
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('rnbo_studio_server', Path(__file__).with_name('server.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

class FakeBridge:
    def __init__(self): self.calls = []
    def scan(self): return [{'port':'test-port','label':'Test ESP32-S3','serial_number':'test'}]
    def snapshot(self): return {'device':None,'parameters':[]}
    def connect(self, port): self.calls.append(port); return self.snapshot()
    def disconnect(self): pass
    def control(self, data): self.calls.append(data); return self.snapshot()

class SettingsTests(unittest.TestCase):
    def valid(self):
        return {'name':'example.rnbopat','patch':{'patcher':{'boxes':[],'lines':[]}},'board':'xiao'}
    def test_defaults_are_explicit_and_preserve_storage(self):
        value = s.build_settings(self.valid())
        self.assertEqual(value['initial_volume'],50)
        self.assertEqual(value['voices'],1)
        self.assertEqual(value['numerical_profile'],'float32-auto-v1')
        self.assertFalse(value['float32_delays'])
        self.assertIsNone(value['filter_delay_max_ms'])
        self.assertEqual(value['title'],'example')
    def test_invalid_inputs_cannot_become_tool_arguments(self):
        for key,values in {'patch':[[],{'patcher':None}], 'board':['; echo bad',None], 'voices':[True,3], 'initial_volume':[True,-1,101], 'arena_bytes':[True,4096], 'filter_delay_max_ms':[True,float('nan'),-1,0,1001], 'float32_delays':['yes',1], 'role':['fx',True], 'numerical_profile':['unknown',True], 'name':['a.cpp',None]}.items():
            for value in values:
                with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                    s.build_settings(dict(self.valid(),**{key:value}))
    def test_oversized_source_is_rejected_before_creating_job(self):
        value=self.valid();value['patch']['patcher']['padding']='x'*s.MAX_PATCH
        with self.assertRaises(ValueError):s.build_settings(value)
    def test_private_job_fields_are_not_exposed(self):
        studio=s.Studio(bridge=FakeBridge());identity='a'*32
        studio.jobs[identity]={'id':identity,'state':'ready','_build':Path('/private'),'_settings':{'secret':1}}
        self.assertEqual(studio.job(identity),{'id':identity,'state':'ready'})
        for value in ([],None,'../../secret'):
            with self.assertRaises(ValueError):studio.job(value)
    def test_busy_build_does_not_create_a_second_job(self):
        studio=s.Studio(bridge=FakeBridge());studio.worker.acquire()
        with patch.object(studio,'environment',return_value={'node':True,'rnbo':True,'idf':True}):
            with self.assertRaisesRegex(ValueError,'already running'):studio.start_build(self.valid())
        self.assertFalse(studio.jobs)
        studio.worker.release()
    def test_upload_failure_keeps_compiled_artifact_retryable(self):
        studio=s.Studio(bridge=FakeBridge());identity='b'*32
        studio.jobs[identity]={'id':identity,'state':'uploading','log':'','result':{'board':'xiao'}}
        studio.worker.acquire()
        studio.upload(identity,Path('/test'),'xiao','test-port')
        self.assertEqual(studio.job(identity)['state'],'ready')
        self.assertIn('package',studio.job(identity)['error'])
        self.assertFalse(studio.worker.locked())

    def test_too_many_parameters_stop_before_module_compilation(self):
        studio=s.Studio(bridge=FakeBridge());identity='e'*32;commands=[]
        settings=s.build_settings(self.valid())
        studio.jobs[identity]={'id':identity,'state':'queued','log':'','error':None}
        def execute(_identity,command):
            commands.append(str(command[1]))
            if str(command[1]).endswith('prepare.py'):
                prepared=Path(command[command.index('--out')+1]);prepared.mkdir()
                (prepared/'manifest.json').write_text(json.dumps({'parameter_count':33}))
        studio.worker.acquire()
        with tempfile.TemporaryDirectory() as temp, patch.object(s,'PRIVATE',Path(temp)), patch.object(studio,'execute',side_effect=execute):
            studio.build(identity,settings)
        self.assertEqual(studio.job(identity)['state'],'failed')
        self.assertIn('32 input parameters',studio.job(identity)['error'])
        self.assertFalse(any(name.endswith('build_firmware.py') or name.endswith('build_module.py') for name in commands))
        self.assertFalse(studio.worker.locked())

    def test_compile_builds_checked_package_and_never_board_firmware(self):
        studio=s.Studio(bridge=FakeBridge());identity='f'*32;commands=[]
        settings=s.build_settings(self.valid())
        studio.jobs[identity]={'id':identity,'state':'queued','log':'','error':None}
        def execute(_identity,command,**kwargs):
            commands.append([str(x) for x in command])
            if str(command[1]).endswith('prepare.py'):
                prepared=Path(command[command.index('--out')+1]);prepared.mkdir()
                (prepared/'manifest.json').write_text(json.dumps({'parameter_count':0}))
                (prepared/'description.json').write_text(json.dumps({'parameters':[]}))
            if str(command[0]).endswith('rnbo_render'):
                return json.dumps({'errors':0,'invalid_samples':0,'late_platform_allocations':0})
            return ''
        studio.worker.acquire()
        with tempfile.TemporaryDirectory() as temp, patch.object(s,'PRIVATE',Path(temp)), \
             patch.object(studio,'execute',side_effect=execute), \
             patch.object(s.player_package,'build',return_value={'bytes':1234,'sha256':'b'*64}):
            studio.build(identity,settings)
        result=studio.job(identity)
        self.assertEqual(result['state'],'ready');self.assertEqual(result['result']['kind'],'package')
        self.assertEqual(result['result']['package_bytes'],1234)
        self.assertTrue(any('build_module.py' in ' '.join(c) and '--max-arena-bytes' in c for c in commands))
        self.assertFalse(any('build_firmware.py' in ' '.join(c) for c in commands))
        self.assertFalse(studio.worker.locked())

    def test_player_install_is_explicit_separate_firmware_action(self):
        bridge=FakeBridge();bridge.flash=lambda *args,**kwargs:bridge.calls.append((args,kwargs))
        studio=s.Studio(bridge=bridge);identity='1'*32
        studio.jobs[identity]={'id':identity,'state':'building','log':'','error':None}
        studio.worker.acquire()
        with patch.object(studio,'execute') as execute, \
             patch('tools.run_hardware_test.artifacts',return_value={'report':{'player':True}}):
            studio.install(identity,'xiao','test-port')
        self.assertEqual(studio.job(identity)['state'],'done')
        self.assertIn('--player',execute.call_args.args[1])
        self.assertEqual(bridge.calls[-1][1],{'expected_kind':'player'})

class SavedPackageTests(unittest.TestCase):
    @staticmethod
    def package(visual=None):
        spec = importlib.util.spec_from_file_location('saved_package_elf', s.ROOT / 'tests/dynamic/test_inspect_module.py')
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        raw, rows = module.fixture()
        struct.pack_into('<IIIBBH',raw,rows['.dynsym']['offset']+16,1,0x100c,4,0x12,0,1)
        metadata={'name':'Saved','source_sha256':'b'*64,'initial_volume':25}
        if visual is not None:metadata['visual']=visual
        return s.player_package.create(bytes(raw),metadata,'main',4096)

    def test_saved_package_import_after_restart_uses_same_upload_without_compiler(self):
        raw=self.package();bridge=FakeBridge()
        bridge.upload_package=lambda *args,**kwargs:bridge.calls.append((args,kwargs))
        studio=s.Studio(bridge=bridge)
        with tempfile.TemporaryDirectory() as temp,patch.object(s,'PRIVATE',Path(temp)),patch.object(s.subprocess,'Popen') as launch:
            job=studio.import_package({'name':'saved.rnbopkg','package_base64':base64.b64encode(raw).decode()})
            self.assertEqual(job['state'],'ready');self.assertEqual(job['result']['origin'],'imported')
            self.assertNotIn('parameters',job['result'])
            path=studio.artifact(job['id']);self.assertEqual(path.read_bytes(),raw)
            self.assertEqual(path.stat().st_mode & 0o222,0)
            studio.start_upload({'id':job['id'],'port':'test-port'});studio.job_thread.join(2)
            self.assertEqual(studio.job(job['id'])['state'],'done')
            self.assertEqual(bridge.calls[-1][0][:2],(path,'test-port'))
            self.assertEqual(bridge.calls[-1][1]['expected_sha256'],s.player_package.digest(raw))
            launch.assert_not_called()

    def test_corrupt_oversized_wrong_role_and_bad_encoding_reject_before_registration(self):
        raw=self.package();wrong_role=bytearray(raw);struct.pack_into('<I',wrong_role,20,2)
        bad=[base64.b64encode(value).decode() for value in (raw[:-1],raw+b'x',bytes(wrong_role),raw[:-1]+bytes([raw[-1]^1]))]
        bad += ['!!!!','x'*(4*((s.MAX_PACKAGE+2)//3)+1)]
        studio=s.Studio(bridge=FakeBridge())
        with tempfile.TemporaryDirectory() as temp,patch.object(s,'PRIVATE',Path(temp)):
            for text in bad:
                with self.subTest(length=len(text)),self.assertRaises(ValueError):
                    studio.import_package({'name':'saved.rnbopkg','package_base64':text})
            self.assertEqual(list(Path(temp).iterdir()),[])
        self.assertEqual(studio.jobs,{})
        self.assertEqual(studio.bridge.calls,[])

    def test_import_exposes_only_bounded_visual_subset_and_ignores_invalid_layout(self):
        visual=dict(format='rnbo-s3-visual-v1',available=True,width=336,height=232,
            parameters=[{'name':'Cutoff','id':'private-looking-source-id'}],
            nodes=[dict(x=4,y=2,width=80,height=18,parameter=0,label='Cutoff',source_extra='ignored')],
            segments=[[4,20,80,20]],source_coordinates=[{'private':'not needed for display'}])
        with tempfile.TemporaryDirectory() as temp,patch.object(s,'PRIVATE',Path(temp)):
            studio=s.Studio(bridge=FakeBridge())
            raw=self.package(visual)
            job=studio.import_package({'name':'saved.rnbopkg','package_base64':base64.b64encode(raw).decode()})
            result=job['result']['visual']
            self.assertTrue(result['available']);self.assertEqual(result['nodes'][0]['parameter'],0)
            self.assertEqual(result['parameters'],[{'name':'Cutoff'}]);self.assertNotIn('source_coordinates',result)
            self.assertNotIn('source_extra',result['nodes'][0])
            visual['nodes'][0]['x']=1000000000
            raw=self.package(visual)
            job=studio.import_package({'name':'saved.rnbopkg','package_base64':base64.b64encode(raw).decode()})
            self.assertEqual(job['result']['visual'],{'available':False})
            self.assertEqual(job['state'],'ready')
        visual['nodes'][0]['x']=4
        for changed in ({'nodes':visual['nodes']*97},{'segments':[[0,0,336,0]]},
                        {'parameters':[{'name':'x'}]*33},{'width':99999999}):
            self.assertEqual(s.package_preview(dict(visual,**changed)),{'available':False})

    def test_import_rejects_busy_or_closed_session(self):
        raw=self.package();data={'name':'saved.rnbopkg','package_base64':base64.b64encode(raw).decode()}
        studio=s.Studio(bridge=FakeBridge());studio.worker.acquire()
        with self.assertRaisesRegex(ValueError,'already running'):studio.import_package(data)
        studio.worker.release();studio.close()
        with self.assertRaisesRegex(ValueError,'shutting down'):studio.import_package(data)
        self.assertEqual(studio.jobs,{})


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler)
        cls.bridge=FakeBridge();cls.server.studio=s.Studio(bridge=cls.bridge)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path,body=None,headers=None):
        request=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers or {})
        try:
            with urllib.request.urlopen(request) as response:return response.status,response.read(),response.headers
        except urllib.error.HTTPError as response:
            with response:return response.code,response.read(),response.headers
    def test_status_and_example_are_real_read_only_endpoints(self):
        code,raw,headers=self.request('/api/status');self.assertEqual(code,200)
        self.assertEqual(json.loads(raw)['csrf'],self.server.studio.token)
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        code,raw,_=self.request('/api/example');self.assertEqual(code,200)
        self.assertIn('patcher',json.loads(raw)['patch'])
    def test_cross_site_and_dns_rebinding_hosts_are_rejected(self):
        for headers in ({'Host':'attacker.example'},{'Origin':'https://attacker.example'}):
            code,_,_=self.request('/api/status',headers=headers);self.assertEqual(code,400)
    def test_mutations_require_session_token_and_json(self):
        before=len(self.bridge.calls)
        for headers in ({'Content-Type':'application/json'},{'Content-Type':'application/json','X-Studio-Token':'wrong'},{'X-Studio-Token':self.server.studio.token}):
            code,_,_=self.request('/api/connect',{'port':'test-port'},headers);self.assertEqual(code,400)
        self.assertEqual(len(self.bridge.calls),before)
        code,_,_=self.request('/api/connect',{'port':'test-port'},{'Content-Type':'application/json','X-Studio-Token':self.server.studio.token})
        self.assertEqual(code,200);self.assertEqual(self.bridge.calls[-1],'test-port')
    def test_no_filesystem_serving_or_arbitrary_commands(self):
        code,_,_=self.request('/../server.py');self.assertEqual(code,404)
        code,_,_=self.request('/api/execute',{'cmd':'bad'},{'Content-Type':'application/json','X-Studio-Token':self.server.studio.token})
        self.assertEqual(code,404)

if __name__=='__main__':unittest.main()
