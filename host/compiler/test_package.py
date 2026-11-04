# SPDX-License-Identifier: MIT
"""Package framing and independent ELF admission; no target execution."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from package import build, create, parse, digest, HEADER, strict_json

spec = importlib.util.spec_from_file_location('package_elf_fixture', Path(__file__).resolve().parents[2] / 'tests/dynamic/test_inspect_module.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)

def elf():
    raw, rows = f.fixture()
    # Resolve the fixture's host_ping locally so the real inspector sees no imports.
    offset = rows['.dynsym']['offset'] + 16
    struct.pack_into('<IIIBBH', raw, offset, 1, 0x100c, 4, 0x12, 0, 1)
    return bytes(raw)

class PackageTests(unittest.TestCase):
    metadata = dict(name='Test', source_sha256='b'*64, initial_volume=50)
    def test_roundtrip_header_hashes_role_and_metadata(self):
        raw = create(elf(), self.metadata, 'main', 1048576)
        self.assertEqual(HEADER.size, 128)
        self.assertEqual(HEADER.unpack_from(raw)[:10], (b'RNBOS3P1',128,1,1,1,44100,256,1048576,len(json.dumps(self.metadata,sort_keys=True,separators=(',',':')).encode()),len(elf())))
        result = parse(raw)
        self.assertEqual(result['elf'], elf()); self.assertEqual(result['metadata'], self.metadata)
        self.assertEqual(result['role'], 'main')
    def test_tampering_lengths_padding_and_unknown_role_reject(self):
        raw = create(elf(), self.metadata, 'main', 4096)
        bad = [raw[:-1],raw+b'x',raw[:128]+bytes([raw[128]^1])+raw[129:],raw[:108]+b'X'+raw[109:]]
        for offset,value in ((20,2),(12,2),(32,4095),(36,65537)):
            changed=bytearray(raw);struct.pack_into('<I',changed,offset,value);bad.append(bytes(changed))
        for changed in bad:
            with self.subTest(length=len(changed)), self.assertRaises(ValueError): parse(changed)
    def test_imports_and_invalid_required_metadata_reject(self):
        with self.assertRaises(ValueError): create(bytes(f.fixture()[0]),self.metadata,'main',4096)
        for change in ({'name':'é'*32},{'initial_volume':True},{'source_sha256':'x'*64}):
            with self.assertRaises(ValueError): create(elf(),dict(self.metadata,**change),'main',4096)
        with self.assertRaises(ValueError): create(elf(),self.metadata,'fx',4096)
    def test_metadata_rejects_duplicate_keys_and_nonfinite_values(self):
        for value in (b'{"name":"first","name":"last"}', b'{"visual":NaN}',
                      b'{"visual":Infinity}', b'{"visual":1e999}'):
            with self.subTest(value=value),self.assertRaises(ValueError): strict_json(value)

    def test_writer_binds_report_artifact_dimensions_and_actual_arena(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'module.elf';path.write_bytes(elf())
            report=dict(format='rnbo-esp32s3-dynamic-module-build',format_version=1,imports=[],dynamic_abi={'major':1},
                sample_rate=44100,block_frames=256,role='main',artifact=dict(path=str(path),bytes=len(elf()),sha256=digest(elf())),
                state_policy={'maximum_arena_bytes':2097152},prepared_export={'manifest':dict(role='main',sample_rate=44100,
                block_frames=256,audio_inputs=0,audio_outputs=2,source_tree_sha256='b'*64)})
            (root/'build-report.json').write_text(json.dumps(report))
            output=root/'patch.rnbopkg';result=build(root,output,'Name')
            self.assertEqual(parse(output.read_bytes())['arena_bytes'],2097152)
            self.assertEqual(result['sha256'],digest(output.read_bytes()))
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):build(root,output,'Name')

if __name__=='__main__':unittest.main()
