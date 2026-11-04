# SPDX-License-Identifier: MIT
"""V3 checks on an authorized local DDD export; no generated DSP is vendored."""
import os
from pathlib import Path
import re
import tempfile
import unittest

from bounded_filters import _method
from float32_audio import float32_audio
from prepare import NUMERICAL_PROFILES, cpp_code_mask, prepare

ROOT = Path(__file__).resolve().parents[2]

class Float32AudioV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = Path(os.environ.get('RNBO_S3_TEST_AUDIO_V3_EXPORT', ROOT / 'build/private/ddd-optimisation-v1/strict'))
        if not (cls.directory / 'rnbo_source.h').is_file():
            raise unittest.SkipTest('Prepare the authorized DDD patch locally to exercise its reviewed kernels')
        cls.source = (cls.directory / 'rnbo_source.h').read_bytes()

    def candidate(self, source=None, profile='float32-audio-v3'):
        return float32_audio(self.source if source is None else source, code_mask=cpp_code_mask, profile=profile)

    @staticmethod
    def outside(source, methods):
        text=source.decode(); masked=cpp_code_mask(text)
        for start,end in sorted([_method(masked,m['method']) for m in methods],reverse=True):
            text=text[:start]+text[end:]
        return text

    def test_v3_admits_exact_15_methods_and_32_suffixes_only(self):
        result, report=self.candidate()
        self.assertIn('float32-audio-v3',NUMERICAL_PROFILES)
        self.assertEqual(len(report['methods']),15);self.assertEqual(report['literal_suffix_count'],32)
        self.assertEqual(sum(m['local_float32_ms_to_samples'] for m in report['methods']),0)
        self.assertEqual(self.outside(self.source,report['methods']),self.outside(result,report['methods']))
        # Independently reverse only decimal-float suffixes inside declared spans.
        restored=result.decode(); masked=cpp_code_mask(restored)
        for start,end in sorted([_method(masked,m['method']) for m in report['methods']],reverse=True):
            body=restored[start:end]
            body=re.sub(r'(?<![\w.])((?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)f\b',r'\1',body)
            restored=restored[:start]+body+restored[end:]
        self.assertEqual(restored.encode(),self.source)
        self.assertIn(b'rnbo_exp(.057762265f * (midivalue - 69.0f))',result)
        self.assertIn(b'rnbo_cos(2.0f * pi01() / 44100 * cutoff[(Index)i])',result)

    def test_old_profiles_still_reject_ddd_and_old_admitted_output_is_unchanged(self):
        for profile in ('float32-audio-v1','float32-audio-v2','float32-cycle-v2'):
            with self.subTest(profile=profile),self.assertRaisesRegex(ValueError,'unsupported RNBO'):
                self.candidate(profile=profile)
        old=ROOT/'build/user-patches/3sawsDrone3/prepared-cap40/rnbo_source.h'
        if old.is_file():
            source=old.read_bytes()
            v1,_=self.candidate(source,profile='float32-audio-v1')
            v2,_=self.candidate(source,profile='float32-audio-v2')
            v3,_=self.candidate(source)
            self.assertEqual(v1,v2);self.assertEqual(v2,v3)

    def test_changed_coefficients_delay_phase_and_algorithms_reject(self):
        mutations=[(b'uint32_trunc(5 *',b'uint32_trunc(6 *'),
                   (b'uint32_trunc(0.1 *',b'uint32_trunc(0.2 *'),
                   (b'0.882497',b'0.882498'),(b'number outdiff = 2000 - 100;',b'number outdiff = 2001 - 100;'),
                   (b'* 0.99;',b'* 0.98;'),(b'number effectiveDelay = 10000;',b'number effectiveDelay = 10001;'),
                   (b'262143',b'262142')]
        for old,new in mutations:
            changed=self.source.replace(old,new,1)
            self.assertNotEqual(changed,self.source,old)
            with self.subTest(old=old),self.assertRaisesRegex(ValueError,'unsupported RNBO'):
                self.candidate(changed)
        with self.assertRaisesRegex(ValueError,'unsupported RNBO'):self.candidate(self.candidate()[0])

    def test_scheduler_setup_ring_types_and_state_declarations_preserved(self):
        result,report=self.candidate()
        for name in ('process','initialize','prepareToProcess','mstosamps','fillRNBODefaultMtofLookupTable256',
                     'lores_01_reset','lores_01_dspsetup','delaytilde_01_del_read','delaytilde_01_del_write',
                     'delaytilde_01_del_step','delaytilde_01_del_calcSizeInSamples'):
            before=self.source.decode();after=result.decode()
            # Full bodies (including shared double conversion and buffer APIs).
            a,b=_method(cpp_code_mask(before),name);c,d=_method(cpp_code_mask(after),name)
            self.assertEqual(before[a:b],after[c:d],name)
        self.assertEqual(result.count(b'Float64Buffer'),self.source.count(b'Float64Buffer'))
        self.assertEqual(result.count(b'number lores_01_'),self.source.count(b'number lores_01_'))

    def test_comments_and_strings_outside_audio_are_not_rewritten(self):
        prefix=b'// .1 0.7 lores_01_perform\nconst char *label=R"tag(0.882497 .057762265)tag";\n'
        result,_=self.candidate(prefix+self.source)
        self.assertTrue(result.startswith(prefix))

    def test_public_prepare_records_profile_and_preserves_other_41_files(self):
        raw=self.directory.parent/'export'
        if not (raw/'rnbo_source.h').is_file():self.skipTest('The paired authorized raw export is needed for CLI integration')
        with tempfile.TemporaryDirectory() as temp:
            strict,candidate=(Path(temp)/name for name in ('strict','candidate'))
            baseline=prepare(raw,strict,'rnbos3patch','main')
            manifest=prepare(raw,candidate,'rnbos3patch','main',numerical_profile='float32-audio-v3')
            self.assertEqual(manifest['numerical_profile'],'float32-audio-v3')
            self.assertEqual(manifest['source_tree_sha256'],baseline['source_tree_sha256'])
            paths=[p.relative_to(strict) for p in strict.rglob('*') if p.is_file() and p.name not in ('manifest.json','provenance.json','rnbo_source.h')]
            for path in paths:self.assertEqual((strict/path).read_bytes(),(candidate/path).read_bytes(),str(path))
            self.assertEqual((candidate/'rnbo_source.h').read_bytes(),self.candidate((strict/'rnbo_source.h').read_bytes())[0])

if __name__=='__main__':unittest.main()
