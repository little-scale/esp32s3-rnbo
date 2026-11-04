# SPDX-License-Identifier: MIT
"""Real bridge protocol with fake serial/ROM only; never enumerates USB."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_device as legacy

d = legacy.d

class Player:
    def __init__(self):
        self.frames=1024;self.uptime=100000;self.firmware='a'*64;self.generation=0
        self.paused=True;self.volume=50;self.main=None;self.commands=[];self.data=bytearray()
        self.bad_offset=False;self.bad_commit=False;self.runtime_fault=False
    def response(self, command):
        self.commands.append(command)
        if command=='player-info':
            self.frames+=256;self.uptime+=5805
            reply=dict(runtime='rnbo-esp32s3-player',api_version=1,board='XIAO ESP32-S3',firmware_elf_sha256=self.firmware,
                rate=44100,block_frames=256,generation=self.generation,paused=self.paused,panic=self.paused or self.main is None,
                maintenance=False,volume=self.volume,main=self.main,frames=self.frames,uptime_us=self.uptime,
                allocation_fault=False,reconstruction_failed=False,**{key:0 for key in d.FAULT_COUNTERS})
            if self.runtime_fault:reply['module_errors']=1
        elif command.startswith('player-begin '):
            _,role,total,sha=command.split();assert role=='1';self.total=int(total);self.expected=sha;self.data.clear()
            reply=dict(upload='ready',offset=0,chunk_bytes=1024)
        elif command.startswith('player-data '):
            _,offset,hexdata=command.split();assert int(offset)==len(self.data)
            chunk=bytes.fromhex(hexdata);assert 0<len(chunk)<=1024;self.data.extend(chunk)
            reply=dict(upload='chunk',offset=len(self.data)+(1 if self.bad_offset else 0))
        elif command=='player-abort':self.data.clear();reply=dict(upload='aborted')
        elif command=='player-commit':
            assert len(self.data)==self.total and hashlib.sha256(self.data).hexdigest()==self.expected
            self.generation+=1;self.paused=False;self.volume=25
            self.main=dict(name='Test',package_sha256=self.expected,source_sha256='b'*64,arena_bytes=4096,
                arena_used=0,context_bytes=32,sample_position=0,parameter_count=1,
                parameters=[dict(index=0,name='Gain',unit='',min=0,max=1,initial=.5,actual=.5,normalized=.5)])
            reply=dict(upload='committed',generation=self.generation,role=1,package_sha256='c'*64 if self.bad_commit else self.expected)
        elif command=='player-pause':self.paused=True;reply={'paused':True}
        elif command=='player-resume':self.paused=False;reply={'paused':False}
        elif command.startswith('player-volume '):self.volume=int(command.split()[1]);reply={'volume':self.volume}
        elif command.startswith('player-param '):
            _,role,generation,index,value=command.split();assert role=='1' and int(generation)==self.generation
            self.main['parameters'][int(index)].update(actual=float(value),normalized=float(value));reply={'queued':True}
        else:raise AssertionError(command)
        return (json.dumps(reply)+'\n').encode()

class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.clock=legacy.Clock();self.player=Player();self.streams=[]
        def opening(*args):
            stream=legacy.Serial(self.player,self.clock);self.streams.append(stream);return stream
        self.bridge=d.DeviceBridge(ports=lambda:[legacy.usb()],opener=opening,clock=self.clock.time,sleep=self.clock.sleep,
            runner=lambda *a,**k:self.fail('Package upload must never run esptool'))
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'test.rnbopkg';self.path.write_bytes(bytes(range(256))*9)
        self.package=dict(role='main',arena_bytes=4096,package_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
                          metadata=dict(source_sha256='b'*64,initial_volume=25))
    def upload(self):
        with patch.object(d,'parse_package',return_value=self.package):
            return self.bridge.upload_package(self.path,'/dev/test-esp',lambda text:None,expected_sha256=self.package['package_sha256'])
    def test_empty_player_connect_then_contiguous_chunks_commit_and_generation_controls(self):
        self.assertEqual(self.bridge.connect('/dev/test-esp')['parameters'],[])
        result=self.upload();self.assertEqual(result['device']['generation'],1)
        self.assertEqual(result['parameters'][0]['role'],'main')
        self.assertEqual(result['parameters'][0]['generation'],1)
        commands=[x for x in self.player.commands if x.startswith('player-data ')]
        self.assertEqual([int(x.split()[1]) for x in commands],[0,1024,2048])
        self.assertEqual(self.player.data,self.path.read_bytes())
        result=self.bridge.control(dict(action='param',role='main',generation=1,index=0,value=.75))
        self.assertEqual(result['parameters'][0]['actual'],.75)
        self.assertFalse(result['control']['exact_application_verified'])
        self.assertTrue(self.bridge.control({'action':'pause'})['device']['paused'])
        self.assertFalse(self.bridge.control({'action':'resume'})['device']['paused'])
    def test_stale_generation_and_unsupported_fx_send_no_parameter_command(self):
        self.upload();before=len(self.player.commands)
        with self.assertRaisesRegex(d.DeviceError,'changed'):
            self.bridge.control(dict(action='param',role='main',generation=0,index=0,value=.5))
        self.assertFalse(any(x.startswith('player-param') for x in self.player.commands[before:]))
        with self.assertRaises(ValueError):self.bridge.control(dict(action='param',role='fx',generation=1,index=0,value=.5))
        with self.assertRaises(ValueError):self.bridge.control(dict(action='bypass',value=True))
    def test_bad_chunk_aborts_without_commit_or_rom_operation(self):
        self.player.bad_offset=True
        with self.assertRaisesRegex(d.DeviceError,'offset'):self.upload()
        self.assertIn('player-abort',self.player.commands)
        self.assertNotIn('player-commit',self.player.commands);self.assertIsNone(self.player.main)
    def test_false_commit_and_changed_package_never_claim_success(self):
        self.player.bad_commit=True
        with self.assertRaisesRegex(d.DeviceError,'complete package commit'):self.upload()
        self.path.write_bytes(b'changed');before=len(self.player.commands)
        with self.assertRaisesRegex(d.DeviceError,'changed'):self.upload()
        self.assertEqual(len(self.player.commands),before)
    def test_player_install_accepts_healthy_empty_player_with_silent_frame_progress(self):
        fixture=legacy.FlashTests();fixture.setUp()
        try:
            player=Player();fixture.device=player
            fixture.bridge._opener=lambda *a:legacy.Serial(player,fixture.clock)
            report=json.loads((fixture.build/'build-report.json').read_text());report.update(player=True)
            report.pop('prepared_export');(fixture.build/'build-report.json').write_text(json.dumps(report))
            result=fixture.bridge.flash(fixture.build,'xiao','/dev/test-esp',lambda text:None,expected_kind='player')
            self.assertIsNone(result['device']['main']);self.assertTrue(result['device']['panic'])
            self.assertTrue(fixture.receipt()['audio_progress_verified'])
            self.assertEqual(fixture.operations().count('write_flash'),1)
        finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
