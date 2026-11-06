# SPDX-License-Identifier: MIT
import json
import base64
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_server import s, FakeBridge
from test_firmware import payload, files, zipped, f
import test_device as legacy
from test_player import Player


class FirmwareServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = patch.object(s, 'PRIVATE', Path(self.temp.name))
        self.private.start(); self.addCleanup(self.private.stop)
        self.bridge = FakeBridge()
        self.calls = []
        self.bridge.flash_bundle = lambda *args, **kwargs: self.calls.append((args, kwargs))
        self.studio = s.Studio(bridge=self.bridge)

    def test_open_is_read_only_and_upload_uses_the_pinned_bundle_without_building(self):
        item = self.studio.import_firmware(payload())
        self.assertEqual(item['board'], 'xiao')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.studio.jobs, {})
        self.assertNotIn('directory', item)
        with patch.object(self.studio, 'execute', side_effect=AssertionError('No compiler permitted')):
            self.studio.start_firmware_upload(dict(id=item['id'], port='test-port'))
            self.studio.job_thread.join(2)
        job = next(iter(self.studio.jobs.values()))
        self.assertEqual(job['state'], 'done')
        self.assertEqual(job['result']['kind'], 'player')
        args, kwargs = self.calls[0]
        self.assertEqual(args[1:3], ('xiao', 'test-port'))
        self.assertEqual(kwargs['expected_manifest_sha256'], self.studio.firmwares[item['id']]['manifest_sha256'])
        self.assertFalse(self.studio.worker.locked())

    def test_busy_shutdown_wrong_target_and_changed_files_prevent_upload(self):
        item = self.studio.import_firmware(payload())
        for data in ({'id':item['id'],'port':None}, {'id':'missing','port':'test-port'},
                     {'id':item['id'],'port':'test-port','transport':'wifi'}):
            with self.assertRaises(ValueError): self.studio.start_firmware_upload(data)
        self.studio.worker.acquire()
        with self.assertRaisesRegex(ValueError,'already running'):
            self.studio.start_firmware_upload(dict(id=item['id'],port='test-port'))
        with self.assertRaises(ValueError): self.studio.import_firmware(payload())
        self.studio.worker.release()
        path=self.studio.firmwares[item['id']]['directory']/'firmware.json'
        path.chmod(0o600);path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'changed'):self.studio.start_firmware_upload(dict(id=item['id'],port='test-port'))
        self.assertEqual(self.calls,[])
        self.studio.stopping.set()
        with self.assertRaisesRegex(ValueError,'shutting down'):self.studio.import_firmware(payload())

    def test_upload_failure_is_not_reported_as_success_and_releases_worker(self):
        item=self.studio.import_firmware(payload())
        def fail(*args,**kwargs):raise RuntimeError('Device partition layout differs')
        self.bridge.flash_bundle=fail
        self.studio.start_firmware_upload(dict(id=item['id'],port='test-port'));self.studio.job_thread.join(2)
        job=next(iter(self.studio.jobs.values()))
        self.assertEqual(job['state'],'failed');self.assertIn('partition',job['error'])
        self.assertFalse(self.studio.worker.locked())

    def test_first_install_requires_explicit_erase_confirmation_and_full_bundle(self):
        item=self.studio.import_firmware(payload())
        data=dict(id=item['id'],port='test-port',mode='first-install')
        with self.assertRaisesRegex(ValueError,'Confirm'):self.studio.start_firmware_upload(data)
        with self.assertRaisesRegex(ValueError,'bootloader'):self.studio.start_firmware_upload(dict(data,erase_confirmed=True))
        full=dict(name='full.zip',firmware_base64=base64.b64encode(zipped(files(full=True))).decode())
        item=self.studio.import_firmware(full);self.assertTrue(item['first_install_available'])
        self.studio.start_firmware_upload(dict(id=item['id'],port='test-port',mode='first-install',erase_confirmed=True))
        self.studio.job_thread.join(2)
        self.assertTrue(self.calls[-1][1]['first_install'])


class FirmwareBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = legacy.FlashTests('test_app_only_backup_readback_identity_and_receipt')
        self.fixture.setUp(); self.addCleanup(self.fixture.tearDown)
        self.fixture.device = Player()
        value = files(elf_hash=self.fixture.elf_hash)
        value['partition-table.bin'] = self.fixture.table
        meta = json.loads(value['firmware.json'])
        meta['files']['partition-table.bin'] = dict(bytes=len(self.fixture.table),sha256=f.digest(self.fixture.table))
        value['firmware.json'] = f.encoded(meta)
        self.directory = self.fixture.root/'build/bundle'
        self.checked = f.stage(zipped(value), self.directory)

    def flash(self):
        return self.fixture.bridge.flash_bundle(self.directory,'xiao','/dev/test-esp',self.fixture.log.append,
            expected_manifest_sha256=self.checked['report_sha256'])

    def test_real_bridge_retains_app_backup_single_write_readback_and_running_identity(self):
        result=self.flash()
        self.assertEqual(result['device']['firmware_elf_sha256'],self.fixture.elf_hash)
        self.assertEqual(self.fixture.operations(),['flash_id','read_flash','read_flash','flash_id','read_flash','write_flash','read_flash'])
        receipt=self.fixture.receipt()
        self.assertEqual(receipt['application_write_offset'],0x10000)
        self.assertTrue(receipt['readback_verified'] and receipt['connected_identity_verified'])
        self.assertEqual(Path(receipt['backup']['path']).stat().st_size,0x300000)

    def test_manifest_changed_after_selection_prevents_all_rom_access(self):
        path=self.directory/'firmware.json';path.chmod(0o600);path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(RuntimeError,'changed'):self.flash()
        self.assertEqual(self.fixture.operations(),[])

    def test_imported_image_changed_after_backup_prevents_write(self):
        runner=self.fixture.runner
        def changing(command,**kwargs):
            result=runner(command,**kwargs)
            if any(str(arg).endswith('original-application-3MiB.bin') for arg in command):
                p=self.directory/'application.bin';p.chmod(0o600);p.write_bytes(b'changed')
            return result
        self.fixture.bridge._runner=changing
        with self.assertRaisesRegex(ValueError,'hash or size'):self.flash()
        self.assertNotIn('write_flash',self.fixture.operations())


class FactoryTool:
    def __init__(self, fixture, board):
        self.fixture,self.board=fixture,board
        self.memory=bytearray(b'Z'*f.FLASH_BYTES[board])
        self.commands=[];self.written=False;self.fail=None;self.short_backup=False;self.corrupt_boot=False
        self.swap_after_backup=False;self.capacity=f.FLASH_BYTES[board]//1048576

    def __call__(self,command,**kwargs):
        index=command.index('--after');after=command[index+1];op,args=command[index+2],command[index+3:]
        self.commands.append((op,after,args))
        text=f'Chip is ESP32-S3 (revision v0.2)\nMAC: 00:11:22:33:44:55\nDetected flash size: {self.capacity}MB\n'.encode()
        if self.fail==op:return subprocess.CompletedProcess(command,2,stdout=text)
        if op=='read_flash':
            address,size,target=int(args[0],16),int(args[1],16),Path(args[2])
            raw=bytes(self.memory[address:address+size])
            if self.short_backup and target.name=='original-full-flash.bin':raw=raw[:-1]
            if self.corrupt_boot and target.name=='bootloader-readback.bin':raw=bytes([raw[0]^1])+raw[1:]
            target.write_bytes(raw)
            if self.swap_after_backup and target.name=='original-full-flash.bin':self.fixture.ports[:]=[legacy.usb('aabbccddeeff')]
        elif op=='erase_flash':self.memory[:]=b'\xff'*len(self.memory)
        elif op=='write_flash':
            assert args[:6]==['--flash_mode','keep','--flash_freq','keep','--flash_size','keep']
            for position in range(6,len(args),2):
                offset=int(args[position],16);assert offset in (0,0x8000,0x10000)
                raw=Path(args[position+1]).read_bytes();self.memory[offset:offset+len(raw)]=raw
            self.written=True;self.fixture.device.firmware=self.fixture.elf_hash
        else:assert op=='flash_id'
        return subprocess.CompletedProcess(command,0,stdout=text)


class FactoryBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=legacy.FlashTests('test_app_only_backup_readback_identity_and_receipt')
        self.fixture.setUp();self.addCleanup(self.fixture.tearDown)

    def setup_board(self,board='xiao'):
        fixture=self.fixture;tool=FactoryTool(fixture,board)
        class BootPlayer(Player):
            def response(self,command):
                if not tool.written:raise AssertionError('Old firmware must never be queried')
                raw=json.loads(super().response(command))
                if command=='player-info':raw['board']=legacy.d.BOARDS[board][0]
                return (json.dumps(raw)+'\n').encode()
        fixture.device=BootPlayer();fixture.bridge._runner=tool
        self.directory=fixture.root/'build/full'
        self.checked=f.stage(zipped(files(board,fixture.elf_hash,full=True)),self.directory)
        self.board=board;self.tool=tool

    def flash(self):
        return self.fixture.bridge.flash_bundle(self.directory,self.board,'/dev/test-esp',self.fixture.log.append,
            expected_manifest_sha256=self.checked['report_sha256'],first_install=True)

    def test_first_install_backs_up_entire_unit_and_verifies_three_fixed_regions(self):
        for board in ('xiao','amoled'):
            with self.subTest(board=board):
                self.setup_board(board)
                result=self.flash();self.assertEqual(result['device']['firmware_elf_sha256'],self.fixture.elf_hash)
                receipt=self.fixture.receipt() if board=='xiao' else json.loads(sorted((self.fixture.root/'uploads').glob('*/receipt.json'),key=lambda p:p.stat().st_mtime)[-1].read_bytes())
                self.assertEqual(receipt['backup']['bytes'],f.FLASH_BYTES[board])
                self.assertEqual(Path(receipt['backup']['path']).read_bytes(),b'Z'*f.FLASH_BYTES[board])
                self.assertTrue(receipt['erase_attempted'] and receipt['readback_verified'])
                self.assertEqual([c[0]for c in self.tool.commands],['flash_id','read_flash','flash_id','erase_flash','write_flash','read_flash','read_flash','read_flash'])
                self.assertTrue(all(c[1]=='no_reset'for c in self.tool.commands[:-1]))
                self.assertEqual(self.tool.commands[-1][1],'watchdog_reset')
                self.assertEqual(self.tool.memory[0x9000:0x10000],b'\xff'*0x7000)
                self.fixture.bridge.disconnect()
                import shutil
                shutil.rmtree(self.directory)

    def test_short_backup_or_wrong_capacity_prevents_erase(self):
        for failure in ('short','capacity','swap'):
            with self.subTest(failure=failure):
                self.setup_board()
                self.tool.short_backup=failure=='short';self.tool.swap_after_backup=failure=='swap'
                if failure=='capacity':self.tool.capacity=16
                with self.assertRaises(RuntimeError):self.flash()
                self.assertNotIn('erase_flash',[c[0]for c in self.tool.commands])
                self.assertFalse(self.tool.written)
                self.fixture.ports[:]=[legacy.usb()]
                import shutil
                shutil.rmtree(self.directory)

    def test_failed_erase_and_bad_readback_are_not_retried(self):
        for failure in ('erase','readback'):
            with self.subTest(failure=failure):
                self.setup_board()
                self.tool.fail='erase_flash' if failure=='erase' else None
                self.tool.corrupt_boot=failure=='readback'
                with self.assertRaises(RuntimeError):self.flash()
                operations=[c[0]for c in self.tool.commands]
                self.assertEqual(operations.count('erase_flash'),1)
                self.assertEqual(operations.count('write_flash'),0 if failure=='erase' else 1)
                self.assertFalse(self.fixture.bridge._flashing.is_set())
                import shutil
                shutil.rmtree(self.directory)
