# SPDX-License-Identifier: MIT
"""Automatic conversion preserves unknown code and strict qualification defaults."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from bounded_filters import _method
from float32_audio import float32_audio
from prepare import cpp_code_mask, prepare, NUMERICAL_PROFILES
from build import verify_prepared

ROOT = Path(__file__).resolve().parents[2]
PROFILE = 'float32-auto-v1'


def auto(source):
    return float32_audio(source, code_mask=cpp_code_mask, profile=PROFILE)


class AutoInputTests(unittest.TestCase):
    def test_no_matching_methods_is_an_unchanged_explicit_noop(self):
        source = b'namespace test { double clock(double ms) { return ms * .001; } }\n'
        result, report = auto(source)
        self.assertEqual(result, source)
        self.assertEqual(report['input_sha256'], report['prepared_sha256'])
        self.assertEqual(report['methods'], [])
        for key in ('matched_method_count', 'eligible_method_count', 'known_method_count',
                    'skipped_method_count', 'literal_suffix_count'):
            self.assertEqual(report[key], 0)
        self.assertFalse(report['source_changed'] or report['all_double_removed_claimed'])
        self.assertIn(PROFILE, NUMERICAL_PROFILES)

    def test_unreviewed_method_is_preserved_and_its_fingerprint_reported(self):
        source = b'void dspexpr_91_perform() { double gain = .3; }\n'
        result, report = auto(source)
        self.assertEqual(result, source)
        self.assertEqual(report['matched_method_count'], 1)
        self.assertEqual(report['known_method_count'], 0)
        self.assertEqual(report['skipped_method_count'], 1)
        entry = report['skipped_methods'][0]
        self.assertEqual(entry['method'], 'dspexpr_91_perform')
        self.assertEqual(entry['reason'], 'unreviewed-method-fingerprint')
        normalized = re.sub(r'\s+', '', source.decode()).replace('dspexpr_91', 'OBJECT')
        self.assertEqual(entry['kernel_sha256'], hashlib.sha256(normalized.encode()).hexdigest())
        for profile in ('float32-audio-v1', 'float32-audio-v2', 'float32-audio-v3'):
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, 'unsupported RNBO'):
                float32_audio(source, code_mask=cpp_code_mask, profile=profile)

    def test_duplicate_names_reject_even_when_both_methods_are_unreviewed(self):
        source = b'void dspexpr_91_perform() { double gain = .3; }\n'
        with self.assertRaisesRegex(ValueError, 'unique supported audio methods'):
            auto(source + source)

    def test_comments_and_strings_do_not_create_candidates_or_edits(self):
        source = (b'// void dspexpr_91_perform() { .3 }\n'
                  b'const char *a="void cycle_tilde_01_perform() { .5 }";\n'
                  b'const char *b=R"tag(void lores_01_perform() { .7 })tag";\n')
        result, report = auto(source)
        self.assertEqual(result, source)
        self.assertEqual(report['matched_method_count'], 0)


class AutoLicensedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('node'):
            raise unittest.SkipTest('Node and licensed RNBO1.4.4 frontend required')
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        for identity, fixture, role in (
                ('cycle', 'tests/fixtures/objects/cycle-fixed.rnbopat', 'main'),
                ('no-match', 'tests/fixtures/gen/arithmetic/abs-call.rnbopat', 'fx')):
            raw = cls.root / (identity + '-raw')
            result = subprocess.run(['node', str(ROOT / 'host/export/export.mjs'),
                                     str(ROOT / fixture), '--out', str(raw)],
                                    capture_output=True, text=True)
            if result.returncode and 'Set --rnbo-dir or RNBO_DIR' in result.stderr:
                raise unittest.SkipTest('Licensed RNBO1.4.4 frontend unavailable')
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            prepare(raw, cls.root / (identity + '-strict'), 'rnbos3patch', role)
        cls.source = (cls.root / 'cycle-strict/rnbo_source.h').read_bytes()

    def test_known_methods_equal_v3_while_unknown_neighbors_remain_exact(self):
        expected, explicit = float32_audio(self.source, code_mask=cpp_code_mask, profile='float32-audio-v3')
        unknown = b'\nvoid dspexpr_909_perform() { double untouched = .3; }\n'
        result, report = auto(self.source + unknown)
        self.assertEqual(result, expected + unknown)
        self.assertGreater(report['known_method_count'], 0)
        self.assertEqual(report['methods'], explicit['methods'])
        self.assertEqual(report['literal_suffix_count'], explicit['literal_suffix_count'])
        self.assertEqual(report['skipped_methods'][0]['method'], 'dspexpr_909_perform')
        with self.assertRaisesRegex(ValueError, 'unsupported RNBO'):
            float32_audio(self.source + unknown, code_mask=cpp_code_mask, profile='float32-audio-v3')

    def test_changed_known_method_is_skipped_without_partial_literal_changes(self):
        _, explicit = float32_audio(self.source, code_mask=cpp_code_mask, profile='float32-audio-v3')
        name = explicit['methods'][0]['method']
        text = self.source.decode(); start, end = _method(cpp_code_mask(text), name)
        changed = (text[:end - 1] + 'double unknown_coefficient = .314159;\n' + text[end - 1:]).encode()
        result, report = auto(changed)
        self.assertEqual(result, changed)
        self.assertEqual(report['known_method_count'], 0)
        self.assertEqual(report['skipped_method_count'], 1)
        with self.assertRaisesRegex(ValueError, 'unsupported RNBO'):
            float32_audio(changed, code_mask=cpp_code_mask, profile='float32-audio-v3')

    def test_repeated_auto_is_byte_idempotent_and_does_not_claim_more_conversions(self):
        result, first = auto(self.source)
        repeated, second = auto(result)
        self.assertTrue(first['source_changed'])
        self.assertEqual(repeated, result)
        self.assertEqual(second['literal_suffix_count'], 0)
        self.assertEqual(second['skipped_method_count'], first['known_method_count'])
        self.assertFalse(second['source_changed'])

    def test_prepare_records_skips_and_noop_without_changing_other_file_bytes(self):
        for identity, role in (('cycle', 'main'), ('no-match', 'fx')):
            output = self.root / (identity + '-auto')
            manifest = prepare(self.root / (identity + '-raw'), output, 'rnbos3patch', role,
                               numerical_profile=PROFILE)
            provenance, _, snapshot = verify_prepared(output)
            strict = self.root / (identity + '-strict')
            strict_snapshot = verify_prepared(strict)[2]['prepared_files_sha256']
            change = provenance['adaptations'][-1]
            self.assertEqual(change['name'], 'rnbo-1.4.4-' + PROFILE)
            self.assertEqual(manifest['numerical_profile'], PROFILE)
            self.assertEqual(manifest['scheduler_time'], 'float64')
            for name in strict_snapshot:
                if name != 'rnbo_source.h':
                    self.assertEqual((strict / name).read_bytes(), (output / name).read_bytes(), name)
            if identity == 'no-match':
                self.assertEqual(strict_snapshot, snapshot['prepared_files_sha256'])
                self.assertEqual(change['known_method_count'], 0)
                self.assertFalse(change['source_changed'])

    def test_qualification_cli_default_stays_strict_and_auto_is_an_explicit_choice(self):
        for label, arguments, expected in (
                ('default', [], 'float32-strict'), ('auto', ['--numerical-profile', PROFILE], PROFILE)):
            output = self.root / ('cli-' + label)
            result = subprocess.run([sys.executable, str(ROOT / 'host/compiler/prepare.py'),
                '--export', str(self.root / 'cycle-raw'), '--out', str(output),
                '--class-name', 'rnbos3patch', '--role', 'main', *arguments], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads((output / 'manifest.json').read_bytes())['numerical_profile'], expected)
        self.assertEqual((self.root / 'cli-default/rnbo_source.h').read_bytes(), self.source)


class AutoDDDTests(unittest.TestCase):
    def test_authorized_ddd_auto_output_equals_v3_byte_for_byte(self):
        directory = Path(os.environ.get('RNBO_S3_TEST_AUDIO_V3_EXPORT',
                         ROOT / 'build/private/ddd-optimisation-v1/strict'))
        path = directory / 'rnbo_source.h'
        if not path.is_file():
            self.skipTest('Optional authorized DDD source is not available')
        source = path.read_bytes()
        explicit, v3 = float32_audio(source, code_mask=cpp_code_mask, profile='float32-audio-v3')
        result, report = auto(source)
        self.assertEqual(result, explicit)
        self.assertEqual(report['methods'], v3['methods'])
        self.assertEqual(report['known_method_count'], 15)
        self.assertEqual(report['skipped_method_count'], 0)
        self.assertEqual(report['literal_suffix_count'], 32)


if __name__ == '__main__':
    unittest.main()
