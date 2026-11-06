# SPDX-License-Identifier: MIT
"""Real producer regeneration and rejection of self-consistent edited exports."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from build import verify_prepared
from prepare import prepare
from regenerated_export import RegeneratedGraph, regenerate
from stable_onepole import CONTEXTS

ROOT = Path(__file__).resolve().parents[2]


class InputTests(unittest.TestCase):
    def test_metadata_cannot_construct_a_certificate(self):
        for value in (None, {}, {'every_prepared_byte_equal': True}, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                RegeneratedGraph(value, files={}, role='fx', class_name='rnbos3patch', record={})
        unissued = object.__new__(RegeneratedGraph)
        self.assertFalse(unissued.matches({}, 'fx'))

    def test_invalid_maps_fail_without_invoking_a_producer(self):
        with mock.patch('subprocess.run', side_effect=AssertionError('must not invoke producer')):
            for files in (None, [], {}, {'rnbo_source.h': bytearray(b'x')}, {1: b'x'}):
                with self.subTest(files=files), self.assertRaises(ValueError):
                    regenerate(files, 'fx')


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        # A new authored graph, including the valid name that defeats raw
        # identifier substitution. Never commit licensed generated code.
        source = json.loads((ROOT / 'tests/fixtures/objects/wave3/onepole-scalar-stereo.rnbopat').read_bytes())
        for item in source['patcher']['boxes']:
            box = item['box']
            if box.get('text', '').startswith('param '):
                parts = box['text'].split()
                parts[1] = 'onepole_tilde_01_b1'
                box['text'] = ' '.join(parts)
                break
        cls.patch = cls.root / 'renamed.rnbopat'
        cls.patch.write_text(json.dumps(source))
        cls.raw = cls.root / 'raw'
        try:
            result = subprocess.run(['node', str(ROOT / 'archive/importer/integer-ui/export.mjs'), str(cls.patch),
                                     '--out', str(cls.raw)], capture_output=True, text=True, timeout=120)
        except FileNotFoundError:
            raise unittest.SkipTest('Node and authorised RNBO 1.4.4 required')
        if result.returncode and 'Set --rnbo-dir or RNBO_DIR' in result.stderr:
            raise unittest.SkipTest('Authorised RNBO 1.4.4 not installed')
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.normal = cls.root / 'normal'
        prepare(cls.raw, cls.normal, 'rnbos3patch', 'fx')
        cls.files = {n: (cls.normal / n).read_bytes()
                     for n in verify_prepared(cls.normal)[2]['prepared_files_sha256']}
        cls.certificate = regenerate(cls.files, 'fx')

    def test_real_generation_binds_all_files_role_and_class(self):
        cert = self.certificate
        self.assertTrue(cert.matches(self.files, 'fx'))
        self.assertFalse(cert.matches(self.files, 'main'))
        self.assertFalse(cert.matches(self.files, 'fx', 'other'))
        self.assertEqual(cert.record['prepared_files'], 42)
        self.assertTrue(cert.record['every_prepared_byte_equal'])
        self.assertFalse(cert.record['target_execution'])
        self.assertNotIn('package_directory', cert.record['inspection'])
        self.assertTrue(cert.record['node_version'].startswith('v'))
        for name in self.files:
            files = dict(self.files)
            files[name] += b'\n'
            with self.subTest(file=name):
                self.assertFalse(cert.matches(files, 'fx'))
        for files in ({**self.files, 'extra.h': b''}, {n: b for n, b in self.files.items() if n != 'patch_config.h'}):
            self.assertFalse(cert.matches(files, 'fx'))
        record = cert.record
        record['every_prepared_byte_equal'] = False
        self.assertTrue(cert.record['every_prepared_byte_equal'], 'audit metadata must be a copy')
        with self.assertRaises(AttributeError):
            cert._role = 'main'

    def test_malformed_successful_inspector_responses_fail_cleanly(self):
        for response in (b'[]', b'null', b'{}', b'{bad json'):
            result = subprocess.CompletedProcess(['node'], 0, response, b'')
            with self.subTest(response=response), mock.patch('subprocess.run', return_value=result):
                with self.assertRaisesRegex(ValueError, 'inspect'):
                    regenerate(self.files, 'fx')

    def test_new_editable_graph_with_known_cpp_uses_fresh_admission(self):
        source = json.loads((ROOT / 'tests/fixtures/objects/wave3/onepole-scalar-stereo.rnbopat').read_bytes())
        source['patcher']['boxes'].append({'box': {'id': 'extra-comment', 'maxclass': 'comment',
                                                   'text': 'UI edits do not change filter code'}})
        patch = self.root / 'ui-edit.rnbopat'
        patch.write_text(json.dumps(source))
        raw = self.root / 'ui-edit-raw'
        result = subprocess.run(['node', str(ROOT / 'archive/importer/integer-ui/export.mjs'), str(patch),
                                 '--out', str(raw)], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        candidate = self.root / 'ui-edit-candidate'
        manifest = prepare(raw, candidate, 'rnbos3patch', 'fx', stable_onepole=True)
        provenance, _, _ = verify_prepared(candidate)
        adaptation = provenance['adaptations'][-1]
        self.assertEqual(adaptation['input_sha256'], CONTEXTS['onepole-scalar-stereo']['source'])
        self.assertEqual(adaptation['context'], 'regenerated-per-instance-envelope')
        self.assertTrue(adaptation['regenerated']['every_prepared_byte_equal'])
        self.assertTrue(manifest['stable_onepole'])

    def test_fresh_regeneration_rejects_config_description_and_metadata_edits(self):
        mutations = []
        files = dict(self.files)
        self.assertIn(b'RATE 44100', files['patch_config.h'])
        files['patch_config.h'] = files['patch_config.h'].replace(b'RATE 44100', b'RATE 48000')
        mutations.append(('config', files))
        files = dict(self.files)
        desc = json.loads(files['description.json'])
        self.assertTrue(desc['parameters'])
        desc['parameters'][0]['initialValue'] += 1
        files['description.json'] = json.dumps(desc).encode()
        mutations.append(('description', files))
        files = dict(self.files)
        meta = json.loads(files['generator.json'])
        meta['voices'] = 4
        files['generator.json'] = json.dumps(meta).encode()
        mutations.append(('voices', files))
        for label, files in mutations:
            before = copy.deepcopy(files)
            with self.subTest(label=label), self.assertRaises(ValueError):
                regenerate(files, 'fx')
            self.assertEqual(files, before)

    def test_self_consistent_raw_cpp_alias_edit_is_rejected(self):
        raw = self.root / 'edited-raw'
        raw.mkdir()
        originals = self.normal / 'originals'
        for path in originals.rglob('*'):
            if path.is_file():
                target = raw / path.relative_to(originals)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
        source = (raw / 'rnbo_source.h').read_bytes()
        anchor = b'RNBO_ASSERT(n == 256);'
        self.assertIn(anchor, source)
        source = source.replace(anchor, anchor + b'\n    static_cast<unsigned char*>(static_cast<void*>(this))[128] = 255;', 1)
        (raw / 'rnbo_source.h').write_bytes(source)
        metadata = json.loads((raw / 'generator.json').read_bytes())
        metadata['generated_sha256'] = hashlib.sha256(source).hexdigest()
        (raw / 'generator.json').write_text(json.dumps(metadata))
        edited = self.root / 'edited-normal'
        prepare(raw, edited, 'rnbos3patch', 'fx')
        files = {n: (edited / n).read_bytes() for n in verify_prepared(edited)[2]['prepared_files_sha256']}
        with self.assertRaisesRegex(ValueError, 'fresh regeneration differs'):
            regenerate(files, 'fx')
        self.assertEqual((self.raw / 'rnbo_source.h').read_bytes(), (originals / 'rnbo_source.h').read_bytes())


if __name__ == '__main__':
    unittest.main()
