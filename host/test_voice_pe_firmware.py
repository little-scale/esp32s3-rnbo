# SPDX-License-Identifier: GPL-3.0-or-later
# Adapted from the Voice PE donor's computer-only installer tests.
"""Computer-only Voice PE migration/update guards; no USB access."""
import hashlib,json,struct,tempfile,unittest,zlib,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,MagicMock,patch
import voice_pe_firmware as vpe


def table(rows):
    data=b''.join(struct.pack('<HBBII16sI',0x50aa,t,s,o,n,label.encode().ljust(16,b'\0'),0) for label,t,s,o,n in rows)
    return (data+b'\xeb\xeb'+b'\xff'*14+hashlib.md5(data).digest()).ljust(0xc00,b'\xff')


def app(name='rnbo_s3_voice-pe',marker=b'Home Assistant Voice PE'):
    header=bytearray(24);header[0:2]=b'\xe9\x01';header[23]=1
    payload=bytearray(512);struct.pack_into('<I',payload,0,0xabcd5432)
    payload[48:80]=name.encode().ljust(32,b'\0');payload[256:256+len(marker)]=marker
    return bytes(header)+struct.pack('<II',0x3c000020,len(payload))+payload+b'\0'*16+b'\0'*32


class Chip:
    def __init__(self,migration=False):
        self.memory=bytearray(b'\xff'*vpe.FLASH_BYTES);self.writes=[];self.sync_stub_detected=True
        self.memory[:4]=b'\xe9\x03\x02\x4f'
        self.memory[0x8000:0x9000]=table(vpe.STOCK if migration else vpe.PROJECT).ljust(4096,b'\xff')
        old=app('home-assistant-voice' if migration else 'waveshare_synthdef')
        self.memory[0x10000:0x10000+len(old)]=old
        self.memory[0xf90000:0xf90008]=b'USER NVS'
    def read_flash(self,offset,size):return bytes(self.memory[offset:offset+size])
    def flash_md5sum(self,offset,size):return hashlib.md5(self.read_flash(offset,size)).hexdigest()
    def sync(self):pass
    def write(self,command,esp):
        assert esp is self
        args=command[command.index('--flash_size')+2:]
        for offset,file in zip(args[::2],args[1::2],strict=True):
            at=int(offset,0);data=Path(file).read_bytes();self.writes.append(at)
            end=(at+len(data)+4095)&~4095
            self.memory[at:end]=b'\xff'*(end-at);self.memory[at:at+len(data)]=data


class VoiceFirmwareTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.table=self.root/'part.bin';self.table.write_bytes(table(vpe.PROJECT))
        self.app=self.root/'app.bin';self.app.write_bytes(app())
        self.valid=patch.object(vpe,'verified_image');self.valid.start()
    def tearDown(self):self.valid.stop();self.tmp.cleanup()
    def run_install(self,chip):
        esptool=SimpleNamespace(main=Mock(side_effect=chip.write))
        return vpe.install(chip,esptool,self.table.read_bytes(),self.app.read_bytes(),self.table,self.app,self.root/'private','1020ba0697d4')
    def test_stock_migration_is_backed_up_before_selective_writes(self):
        chip=Chip(True);before=bytes(chip.memory)
        result=self.run_install(chip)
        self.assertEqual(chip.writes,[0x8000,0x9000,0x10000])
        backup=next((self.root/'private').rglob('esp-flash-before.bin'))
        self.assertEqual(backup.read_bytes(),before)
        self.assertEqual(backup.stat().st_mode&0o777,0o600)
        self.assertEqual(vpe.partitions(chip.read_flash(0x8000,4096)),vpe.PROJECT)
        self.assertEqual(chip.read_flash(0x9000,8192),b'\xff'*8192)
        self.assertEqual(chip.memory[:0x8000],before[:0x8000])
        self.assertEqual(chip.memory[0xf90000:],before[0xf90000:])
        self.assertEqual(result['status'],'installed_verified')
    def test_newer_stock_migration_preserves_all_settings_pages(self):
        chip=Chip(True);chip.memory[0x8000:0x9000]=table(vpe.STOCK_LATEST).ljust(4096,b'\xff')
        chip.memory[-8:]=b'LAST NVS';before=bytes(chip.memory[0xf90000:])
        result=self.run_install(chip)
        self.assertEqual(vpe.partitions(chip.read_flash(0x8000,4096)),vpe.PROJECT_LATEST)
        self.assertEqual(chip.memory[0xf90000:],before)
        self.assertEqual(result['nvs_preserved_bytes'],0x70000)

    def test_newer_project_update_preserves_its_partition_table(self):
        chip=Chip();chip.memory[0x8000:0x9000]=table(vpe.PROJECT_LATEST).ljust(4096,b'\xff')
        before=bytes(chip.memory[:0x10000]);self.run_install(chip)
        self.assertEqual(chip.writes,[0x10000]);self.assertEqual(chip.memory[:0x10000],before)

    def test_dual_app_device_cannot_overwrite_synthdef_from_legacy_updater(self):
        chip=Chip();rnbo=app('rnbo_s3_voice-pe')
        chip.memory[0x7d0000:0x7d0000+len(rnbo)]=rnbo
        before=bytes(chip.memory)
        with self.assertRaisesRegex(ValueError,'Dual apps detected'):self.run_install(chip)
        self.assertEqual(chip.writes,[]);self.assertEqual(chip.memory,before)
        self.assertFalse((self.root/'private').exists())

    def test_project_update_writes_only_app_preserving_storage_and_ota(self):
        chip=Chip();before=bytes(chip.memory);result=self.run_install(chip)
        self.assertEqual(chip.writes,[0x10000]);self.assertEqual(result['installation'],'application update')
        self.assertEqual(chip.memory[:0x10000],before[:0x10000]);self.assertEqual(chip.memory[0x7d0000:],before[0x7d0000:])
        self.assertTrue(next((self.root/'private').rglob('application-before.bin')).exists())
    def test_unknown_layout_and_bad_table_rejected_before_write(self):
        for corrupt in (0,1):
            chip=Chip();changed=list(vpe.PROJECT);changed[-1]=('nvs',1,2,0xf80000,0x6d000)
            blob=bytearray(table(changed))
            if corrupt:blob[50]^=1
            chip.memory[0x8000:0x9000]=blob.ljust(4096,b'\xff')
            with self.assertRaises(ValueError):self.run_install(chip)
            self.assertEqual(chip.writes,[])
    def test_other_stock_model_rejected_before_backup_or_write(self):
        chip=Chip(True);other=app('other-board',b'Other device');chip.memory[0x10000:0x10000+len(other)]=other
        with self.assertRaisesRegex(ValueError,'identify stock'):self.run_install(chip)
        self.assertEqual(chip.writes,[]);self.assertFalse((self.root/'private').exists())
    def test_other_project_model_never_written(self):
        chip=Chip();other=app(marker=b'Waveshare AMOLED');chip.memory[0x10000:0x10000+len(other)]=other
        with self.assertRaisesRegex(ValueError,'different board'):self.run_install(chip)
        self.assertEqual(chip.writes,[])
    def test_app1_ota_selection_rejected_for_project_updates(self):
        chip=Chip();ota=bytearray(b'\xff'*32);struct.pack_into('<I',ota,0,2);struct.pack_into('<I',ota,24,2)
        struct.pack_into('<I',ota,28,zlib.crc32(ota[:4],0xffffffff));chip.memory[0x9000:0x9020]=ota
        with self.assertRaisesRegex(ValueError,'app0'):self.run_install(chip)
        self.assertEqual(chip.writes,[])
    def test_failed_backup_never_calls_programmer(self):
        chip=Chip()
        with patch.object(chip,'flash_md5sum',return_value='bad'):
            with self.assertRaisesRegex(ValueError,'Backup verification failed'):self.run_install(chip)
        self.assertEqual(chip.writes,[])
    def test_partial_backup_never_calls_programmer(self):
        chip=Chip();read=chip.read_flash
        def short(offset,size):return b'' if size>=4096 and offset==0x10000 else read(offset,size)
        with patch.object(chip,'read_flash',side_effect=short):
            with self.assertRaisesRegex(ValueError,'Incomplete backup'):self.run_install(chip)
        self.assertEqual(chip.writes,[])
    def test_overlarge_or_wrong_new_app_rejected(self):
        chip=Chip()
        for data in (app(marker=b'wrong-board'),b'Home Assistant Voice PE'+b'\0'*0x3c0000):
            self.app.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'Voice PE application'):self.run_install(chip)
            self.assertEqual(chip.writes,[])
    def test_device_write_failure_retains_verified_backup(self):
        chip=Chip()
        with patch.object(chip,'write',side_effect=RuntimeError('USB lost')):
            with self.assertRaisesRegex(RuntimeError,'USB lost'):self.run_install(chip)
        saved=next((self.root/'private').rglob('backup.json'))
        record=json.loads(saved.read_text())
        self.assertEqual(record['status'],'writing')
        self.assertTrue(all(row['verified'] for row in record['files']))
        self.assertTrue((saved.parent/'application-before.bin').exists())

    def test_active_slot_and_crc(self):
        self.assertEqual(vpe.active_slot(b'\xff'*8192),0)
        with self.assertRaises(ValueError):vpe.active_slot(b'\0'*8192)
        for seq,state in ((1,2),(2,2),(3,2),(1,1)):
            data=bytearray(b'\xff'*8192);struct.pack_into('<I',data,0,seq);struct.pack_into('<I',data,24,state)
            struct.pack_into('<I',data,28,zlib.crc32(data[:4],0xffffffff))
            if state==1:
                with self.assertRaisesRegex(ValueError,'pending'):vpe.active_slot(data)
            else:self.assertEqual(vpe.active_slot(data),(seq-1)%2)


    def test_nonempty_future_storage_blocks_stock_migration_before_backup(self):
        chip=Chip(True);chip.memory[0xefffff]=0
        with self.assertRaisesRegex(ValueError,'wholly erased'):self.run_install(chip)
        self.assertEqual(chip.writes,[]);self.assertFalse((self.root/'private').exists())

    def test_rnbo_project_update_preserves_foreign_filesystem_bytes(self):
        chip=Chip();old=app();chip.memory[0x10000:0x10000+len(old)]=old
        chip.memory[0xb90000:0xb9000b]=b'OTHER FILES'
        self.run_install(chip)
        self.assertEqual(chip.writes,[0x10000])
        self.assertEqual(chip.memory[0xb90000:0xb9000b],b'OTHER FILES')

    def test_changed_source_file_during_backup_cannot_replace_reviewed_image(self):
        chip=Chip();reviewed=self.app.read_bytes();save=vpe.save_region
        def mutate(*args):
            result=save(*args);self.app.write_bytes(app('other-board',b'Other device'));return result
        with patch.object(vpe,'save_region',side_effect=mutate):self.run_install(chip)
        self.assertEqual(chip.read_flash(vpe.APP_OFFSET,len(reviewed)),reviewed)
        self.assertEqual(chip.writes,[vpe.APP_OFFSET])
