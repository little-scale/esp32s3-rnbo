# SPDX-License-Identifier: MIT
import base64
import hashlib
import io
import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest import mock
import zipfile

from host.studio import firmware as f


def image(board='xiao', elf_hash='a' * 64):
    header = bytearray(24)
    header[0:2] = bytes([0xe9, 1])
    header[3] = (3 if board == 'xiao' else 4) << 4
    struct.pack_into('<H', header, 12, 9)
    header[23] = 1
    data = bytearray(256)
    struct.pack_into('<I', data, 0, 0xabcd5432)
    project = ('rnbo_s3_' + board).encode()
    data[48:48 + len(project)] = project
    data[144:176] = bytes.fromhex(elf_hash)
    raw = header + struct.pack('<II', 0x3c000020, len(data)) + data
    checksum = 0xef
    for byte in data:
        checksum ^= byte
    raw += bytes((15 - len(raw) % 16) % 16) + bytes([checksum])
    return bytes(raw) + hashlib.sha256(raw).digest()


def files(board='xiao', elf_hash='a' * 64, *, full=False):
    partition = struct.pack('<HBBII16sI', 0x50aa, 0, 0, 0x10000, 0x300000, b'factory', 0) + b'\xff' * 32
    value = {'application.bin': image(board, elf_hash), 'partition-table.bin': partition}
    if full:
        value['bootloader.bin'] = image(board, elf_hash)
    value['firmware.json'] = f.encoded(dict(format=f.FORMAT, player=True, board=board,
        sample_rate=44100, block_frames=256, player_api_version=1, usb_midi_host=False,
        firmware_elf_sha256=elf_hash,
        files={n:dict(bytes=len(b), sha256=f.digest(b)) for n, b in value.items()}))
    return value


def zipped(value=None, extra=None):
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in (value or files()).items():
            archive.writestr(name, raw)
        if extra:
            archive.writestr(*extra)
    return result.getvalue()


def payload():
    return dict(name='player.zip', firmware_base64=base64.b64encode(zipped()).decode())


class FirmwareTests(unittest.TestCase):
    def test_current_options_hide_stale_builds_and_never_use_arbitrary_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'build-report.json').write_text('{}')
            with mock.patch.object(f,'CURRENT_BUILDS',{'xiao':root,'amoled':root}), mock.patch.object(f,'create',side_effect=lambda _,board: zipped(files(board,full=True)) if board=='xiao' else (_ for _ in ()).throw(ValueError('Player build is older; rebuild'))):
                rows=f.current_options()
                self.assertTrue(rows[0]['available']);self.assertEqual(rows[0]['features'],['USB','Wi-Fi'])
                self.assertFalse(rows[1]['available']);self.assertIn('rebuild',rows[1]['reason'])
                self.assertNotIn('directory',rows[0]);self.assertEqual(rows[0]['sha256'],f.digest(f.current_bundle('xiao')[0]))
                with self.assertRaisesRegex(ValueError,'Choose'):f.current_bundle('../xiao')

    def test_bundle_creation_requires_current_sources_and_network_component(self):
        inventory={'firmware/main/player_main.c':'a'*64}
        report=dict(player=True, player_api_version=1, components=['player_network'], integration_files_sha256=inventory)
        for change in ({'integration_files_sha256':{}}, {'integration_files_sha256':{'firmware/main/player_main.c':'b'*64}}, {'components':[]}):
            with self.subTest(change=change), mock.patch('tools.run_hardware_test.artifacts', return_value={'report':{**report,**change}}), mock.patch('tools.build_firmware.source_inventory', return_value=inventory):
                with self.assertRaisesRegex(ValueError, 'rebuild|Rebuild'):
                    f.create(Path('/unused-build'),'amoled')

    def test_current_build_packages_all_images_and_is_reproducible(self):
        inventory={'firmware/main/player_main.c':'a'*64}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve(); value=files('amoled',full=True)
            (root/'bootloader').mkdir(); (root/'partition_table').mkdir()
            app=root/'rnbo_s3_amoled.bin'; app.write_bytes(value['application.bin'])
            partition=root/'partition_table/partition-table.bin'; partition.write_bytes(value['partition-table.bin'])
            (root/'bootloader/bootloader.bin').write_bytes(value['bootloader.bin'])
            (root/'flasher_args.json').write_text(json.dumps({'flash_files':{'0x0':'bootloader/bootloader.bin','0x8000':'partition_table/partition-table.bin','0x10000':'rnbo_s3_amoled.bin'}}))
            checked=dict(report=dict(player=True,player_api_version=1,components=['player_network'],integration_files_sha256=inventory),app=app,partition=partition,elf_sha256='a'*64)
            with mock.patch('tools.run_hardware_test.artifacts',return_value=checked), mock.patch('tools.build_firmware.source_inventory',return_value=inventory):
                raw=f.create(root,'amoled'); self.assertEqual(raw,f.create(root,'amoled'))
            decoded,meta=f.unpack(raw)
            self.assertEqual(meta['board'],'amoled')
            self.assertEqual(set(decoded),{'application.bin','partition-table.bin','bootloader.bin','firmware.json'})

    def test_full_bundle_includes_a_checked_bootloader_for_first_install(self):
        raw=zipped(files(full=True));decoded,meta=f.unpack(raw)
        self.assertIn('bootloader.bin',meta['files'])
        with tempfile.TemporaryDirectory() as temp:
            checked=f.stage(raw,Path(temp)/'full')
            self.assertEqual(checked['bootloader'].read_bytes(),decoded['bootloader.bin'])
        value=files(full=True);value['bootloader.bin']=b'bad'
        meta=json.loads(value['firmware.json']);meta['files']['bootloader.bin']=dict(bytes=3,sha256=f.digest(b'bad'))
        value['firmware.json']=f.encoded(meta)
        with self.assertRaisesRegex(ValueError,'image'):f.unpack(zipped(value))
    def test_both_board_images_validate_and_stage_without_a_compiler(self):
        for board in ('xiao', 'amoled'):
            raw = zipped(files(board))
            decoded, meta = f.unpack(raw)
            self.assertEqual(meta['board'], board)
            with tempfile.TemporaryDirectory() as temp:
                directory = Path(temp) / 'import'
                checked = f.stage(raw, directory)
                self.assertEqual(checked['elf_sha256'], 'a' * 64)
                self.assertEqual(checked['app'].read_bytes(), decoded['application.bin'])
                self.assertEqual(checked['report_sha256'], f.digest(decoded['firmware.json']))
                self.assertEqual(stat.S_IMODE(checked['app'].stat().st_mode), 0o400)
                with self.assertRaisesRegex(ValueError, 'board'):
                    f.verify_staged(directory, 'amoled' if board == 'xiao' else 'xiao')

    def test_inventory_malformed_metadata_and_corruption_reject(self):
        for change in ({'board':[]}, {'player':1}, {'player_api_version':True}, {'usb_midi_host':'yes'},
                       {'files':{}}, {'format':'not-firmware'}, {'firmware_elf_sha256':'bad'}):
            value = files(); meta = json.loads(value['firmware.json']); meta.update(change)
            value['firmware.json'] = f.encoded(meta)
            with self.subTest(change=change), self.assertRaises(ValueError):
                f.unpack(zipped(value))
        for name in ('application.bin', 'partition-table.bin'):
            value = files(); value[name] = value[name][:-1] + bytes([value[name][-1] ^ 1])
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'hash or size'):
                f.unpack(zipped(value))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            f.metadata(b'{"format":1,"format":2}')

    def test_archive_paths_links_extras_and_expanded_limit_reject(self):
        for name in ('../application.bin', '/application.bin', 'nested/application.bin'):
            value=files();value[name]=value.pop('application.bin')
            with self.subTest(name=name), self.assertRaises(ValueError):f.unpack(zipped(value))
        with self.assertRaises(ValueError):f.unpack(zipped(extra=('extra.bin', b'bad')))
        linked = zipfile.ZipInfo('application.bin');linked.create_system=3
        linked.external_attr=(stat.S_IFLNK | 0o777) << 16
        value=files(); application=value.pop('application.bin')
        with self.assertRaisesRegex(ValueError, 'Linked'):f.unpack(zipped(value, extra=(linked,application)))
        value=files();value['application.bin']=b'0'*(f.APP_CAPACITY+1)
        with self.assertRaisesRegex(ValueError, 'oversized'):f.unpack(zipped(value))

    def test_wrong_chip_board_descriptor_and_rehashed_corrupt_image_reject(self):
        valid = image()
        for offset in (0, 3, 12, 32, 80, len(valid)-1):
            changed=bytearray(valid);changed[offset]^=1
            with self.subTest(offset=offset), self.assertRaises(ValueError):f.image_info(bytes(changed),'xiao')
        with self.assertRaises(ValueError):f.image_info(valid[:-16], 'xiao')
        value=files();meta=json.loads(value['firmware.json']);meta['firmware_elf_sha256']='b'*64
        value['firmware.json']=f.encoded(meta)
        with self.assertRaisesRegex(ValueError,'identity'):f.unpack(zipped(value))

    def test_staged_payload_changes_are_detected_before_flashing(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/'import';f.stage(zipped(),directory)
            p=directory/'application.bin';p.chmod(0o600);p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'hash or size'):f.verify_staged(directory)

    def test_partition_geometry_and_checksum_reject(self):
        for address,size in ((0x20000,0x300000),(0x10000,0x400000)):
            raw=struct.pack('<HBBII16sI',0x50aa,0,0,address,size,b'factory',0)+b'\xff'*32
            with self.assertRaises(ValueError):f.partition_info(raw,'xiao')
        raw=files()['partition-table.bin'][:32]
        md5=b'\xeb\xeb'+b'\xff'*14+hashlib.md5(raw).digest()
        f.partition_info(raw+md5,'xiao')
        with self.assertRaisesRegex(ValueError,'checksum'):f.partition_info(raw+md5[:-1]+b'X','xiao')
