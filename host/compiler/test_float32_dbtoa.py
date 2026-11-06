# SPDX-License-Identifier: MIT
"""Closed dbtoa source/profile admission and actual compile-time type guards."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from build import verify_prepared
from float32_audio import (DBTOA_CONTRACT, DBTOA_CONTRACT_FILE, DBTOA_INPUT_MAPS,
                           DBTOA_KERNEL, DBTOA_MANIFEST_CONTRACT, DBTOA_PROFILE,
                           float32_audio, prepare_dbtoa)
from prepare import ExportError, NUMERICAL_PROFILES, cpp_code_mask, prepare

ROOT = Path(__file__).resolve().parents[2]


class DbtoaContextTests(unittest.TestCase):
    def test_invalid_context_and_compositions_reject_before_export_io(self):
        variants = [('role', 'main'), ('class_name', 'other'), ('apply_fixes', False),
                    ('apply_fixes', 1), ('midi_output_policy', 'discard'), ('filter_delay_max_ms', 40)]
        variants += [(name, True) for name in (
            'float32_delay_storage', 'omit_unused_mtof_table', 'hoist_cycle_conversions',
            'compact_average_history', 'float32_pink_output', 'correct_finite_wrap',
            'exact_audio_delay44100', 'hoist_filter_durations', 'hoist_train_reciprocal',
            'bounded_line_ramps', 'float32_onepole_clamp', 'stable_onepole', 'gen_abs_intrinsic')]
        with tempfile.TemporaryDirectory() as temp:
            for name, value in variants:
                options = dict(class_name='rnbos3patch', role='fx', numerical_profile=DBTOA_PROFILE)
                options[name] = value
                with self.subTest(name=name), self.assertRaises(ExportError):
                    prepare(Path(temp)/'missing', Path(temp)/'out', **options)
                self.assertFalse((Path(temp)/'out').exists())

    def test_compile_contract_rejects_wrong_types_math_abi_and_evaluation(self):
        compiler = shutil.which('c++')
        if not compiler:
            self.skipTest('C++ compiler unavailable')
        variants = [({}, True)]
        variants += [({name: value}, False) for name, value in (
            ('number', 'double'), ('sample', 'double'), ('output', 'double'),
            ('clock', 'float'), ('result', 'double'), ('major', 2), ('minor', 1),
            ('major', None), ('evaluation', 2), ('flags', ['-ffast-math']),
            ('flags', ['-ffinite-math-only']), ('approximate', 1))]
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); (directory/DBTOA_CONTRACT_FILE).write_bytes(DBTOA_CONTRACT)
            for override, good in variants:
                settings = dict(number='float', sample='float', output='float', clock='double',
                                result='float', major=1, minor=0, evaluation=0, flags=[], approximate=0)
                settings.update(override)
                source = ('namespace RNBO {using number='+settings['number']+';using Sample='+settings['sample']+
                          ';using SampleValue='+settings['output']+';using MillisecondTime='+settings['clock']+';}\n'
                          'namespace RNBO_Math {inline '+settings['result']+' rnbo_pow(float,float){return 0;}}\n')
                (directory/'rnbo_source.h').write_text(source)
                macros = ''.join('#define RNBO_S3_ABI_'+name.upper()+' '+str(settings[name])+'u\n'
                                 for name in ('major', 'minor') if settings[name] is not None)
                macros += '#define RNBO_USE_APPROXIMATE_MATH '+str(settings['approximate'])+'\n'
                if settings['evaluation']:
                    macros += '#include <float.h>\n#undef FLT_EVAL_METHOD\n#define FLT_EVAL_METHOD '+str(settings['evaluation'])+'\n'
                (directory/'test.cpp').write_text(macros+'#include "'+DBTOA_CONTRACT_FILE+'"\n')
                process = subprocess.run([compiler, '-std=c++17', '-ffp-contract=off', '-fsyntax-only',
                                          *settings['flags'], str(directory/'test.cpp')], capture_output=True, text=True)
                with self.subTest(override=override):
                    self.assertEqual(process.returncode == 0, good, process.stderr)


class DbtoaPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name); cls.raw = cls.directory/'raw'
        try:
            process = subprocess.run(['node', str(ROOT/'archive/importer/integer-ui/export.mjs'),
                str(ROOT/'tests/fixtures/smoke/rnbo-functions/dbtoa-signal.rnbopat'), '--out', str(cls.raw)],
                capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            raise unittest.SkipTest('Node and licensed frontend required')
        if process.returncode and 'Set --rnbo-dir or RNBO_DIR' in process.stderr:
            raise unittest.SkipTest('Licensed frontend unavailable')
        if process.returncode:
            raise AssertionError(process.stderr)
        cls.strict = cls.directory/'strict'; cls.candidate = cls.directory/'candidate'
        cls.baseline = prepare(cls.raw, cls.strict, 'rnbos3patch', 'fx')
        cls.manifest = prepare(cls.raw, cls.candidate, 'rnbos3patch', 'fx', numerical_profile=DBTOA_PROFILE)
        cls.files = {name: (cls.strict/name).read_bytes()
                     for name in verify_prepared(cls.strict)[2]['prepared_files_sha256']}
        cls.source = cls.files['rnbo_source.h']; cls.description = json.loads(cls.files['description.json'])

    def test_exact_four_literal_edits_with_whole_source_inverse_and_43_file_contract(self):
        self.assertIn(DBTOA_PROFILE, NUMERICAL_PROFILES)
        changed, record = float32_audio(self.source, code_mask=cpp_code_mask, profile=DBTOA_PROFILE)
        self.assertEqual(record['literal_replacement_count'], 4)
        self.assertEqual(len(record['methods']), 2)
        self.assertEqual({m['kernel_sha256'] for m in record['methods']}, {DBTOA_KERNEL})
        self.assertEqual(changed.count(b'rnbo_pow(10.0f, in1[(Index)i] * 0.05f)'), 2)
        # Independently reverse the exact local expressions, not arbitrary f suffixes.
        self.assertEqual(changed.replace(b'rnbo_pow(10.0f, in1[(Index)i] * 0.05f)',
                                         b'rnbo_pow(10, in1[(Index)i] * 0.05)'), self.source)
        provenance, manifest, snapshot = verify_prepared(self.candidate)
        self.assertEqual(len(snapshot['prepared_files_sha256']), 43)
        self.assertEqual(manifest['numerical_profile'], DBTOA_PROFILE)
        self.assertEqual(manifest['base_numerical_profile'], 'float32-strict')
        self.assertEqual(manifest['dbtoa_contract'], DBTOA_MANIFEST_CONTRACT)
        self.assertFalse(manifest['dbtoa_contract']['bit_identity_claimed'])
        self.assertEqual((self.candidate/DBTOA_CONTRACT_FILE).read_bytes(), DBTOA_CONTRACT)
        self.assertEqual((self.candidate/'rnbo_source.h').read_bytes(), changed)
        for name, data in self.files.items():
            if name not in ('rnbo_source.h', 'patch_config.h'):
                self.assertEqual((self.candidate/name).read_bytes(), data, name)
        self.assertEqual((self.candidate/'patch_config.h').read_bytes(), self.files['patch_config.h'] +
                         ('#define RNBO_S3_PATCH_SOURCE "'+DBTOA_CONTRACT_FILE+'"\n').encode())
        self.assertTrue(provenance['adaptations'][-1]['whole_source_inverse_verified'])

    def test_changed_unknown_duplicate_no_audio_and_already_changed_methods_reject(self):
        mutations = [self.source.replace(b'rnbo_pow(10,', b'rnbo_pow(11,', 1),
                     self.source.replace(b'* 0.05)', b'* 0.06)', 1),
                     self.source.replace(b'dspexpr_02_perform', b'dspexpr_01_perform'),
                     self.source.replace(b'dspexpr_', b'other_'),
                     float32_audio(self.source, code_mask=cpp_code_mask, profile=DBTOA_PROFILE)[0],
                     self.source.replace(b'dspexpr_', b'codebox_tilde_')]
        for source in mutations:
            with self.subTest(source_sha=hashlib.sha256(source).hexdigest()), self.assertRaises(ValueError):
                float32_audio(source, code_mask=cpp_code_mask, profile=DBTOA_PROFILE)

    def test_comments_strings_and_other_source_bytes_remain_unchanged(self):
        prefix = b'// void dspexpr_99_perform() {} rnbo_pow(10, in1[(Index)i] * 0.05)\nconst char *a=R"tag(dspexpr_99_perform 10 0.05)tag";\n'
        source = prefix + self.source.replace(b'* 0.05)', b'* /* keep .05 */ 0.05)', 1)
        changed, record = float32_audio(source, code_mask=cpp_code_mask, profile=DBTOA_PROFILE)
        restored = changed.decode()
        for edit in sorted(record['edits'], key=lambda e: e['prepared_span'], reverse=True):
            a, b = edit['prepared_span']; restored = restored[:a]+edit['before']+restored[b:]
        self.assertEqual(restored.encode(), source)
        self.assertTrue(changed.startswith(prefix))
        self.assertIn(b'/* keep .05 */', changed)

    def test_full_map_runtime_config_graph_metadata_and_description_guards_are_atomic(self):
        for name in ('rnbo_source.h', 'description.json', 'generator.json', 'patch_config.h',
                     'source.rnbopat', 'common/RNBO_Math.h'):
            files = dict(self.files); files[name] += b'\n'; before = copy.deepcopy(files)
            with self.subTest(name=name), self.assertRaises(ValueError):
                prepare_dbtoa(files, self.description, code_mask=cpp_code_mask)
            self.assertEqual(files, before)
        for mutation in ('missing', 'extra', 'mutable', 'repeat', 'description'):
            files = dict(self.files); description = copy.deepcopy(self.description)
            if mutation == 'missing': files.pop('source.rnbopat')
            elif mutation == 'extra': files['unreviewed.h'] = b''
            elif mutation == 'mutable': files['rnbo_source.h'] = bytearray(self.source)
            elif mutation == 'repeat': files = prepare_dbtoa(files, description, code_mask=cpp_code_mask)[0]
            else: description['numInputChannels'] = 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                prepare_dbtoa(files, description, code_mask=cpp_code_mask)

    def test_original_and_current_producer_maps_only(self):
        observed = set()
        for stamp in ('56fb9edda0184c282b64f9ba66ab70817866cb981fa5aee4b3050e804bac3065',
                      '4af4ee869ca842cd9ffbd0421367b46f491767c203971d3c83fff4e89fd3ce5e'):
            files = dict(self.files); generator = json.loads(files['generator.json'])
            generator['patcher_adapter_sha256'] = stamp
            files['generator.json'] = (json.dumps(generator, indent=2)+'\n').encode()
            _, record = prepare_dbtoa(files, self.description, code_mask=cpp_code_mask)
            observed.add(record['input_map_sha256'])
        self.assertEqual(observed, set(DBTOA_INPUT_MAPS))

    def test_earlier_profiles_and_auto_do_not_inherit_dbtoa(self):
        for profile in ('float32-cycle-v2', 'float32-audio-v1', 'float32-audio-v2', 'float32-audio-v3'):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                float32_audio(self.source, code_mask=cpp_code_mask, profile=profile)
        unchanged, report = float32_audio(self.source, code_mask=cpp_code_mask, profile='float32-auto-v1')
        self.assertEqual(unchanged, self.source)
        self.assertEqual(report['known_method_count'], 0)
        self.assertEqual(report['skipped_method_count'], 2)
        self.assertEqual(self.baseline['numerical_profile'], 'float32-strict')


if __name__ == '__main__':
    unittest.main()
