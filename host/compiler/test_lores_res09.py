# SPDX-License-Identifier: MIT
"""The exact fixed-.9 signal-cutoff form is reviewed separately, not wildcarded."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from bounded_filters import _method
from float32_audio import float32_audio
from prepare import cpp_code_mask, prepare

ROOT=Path(__file__).resolve().parents[2]


class LoresResonance09Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('node'):raise unittest.SkipTest('Licensed RNBO frontend required')
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        directory=Path(cls.temp.name)
        result=subprocess.run(['node',str(ROOT/'archive/importer/integer-ui/export.mjs'),str(ROOT/'tests/fixtures/objects/lores-res09.rnbopat'),
                               '--out',str(directory/'raw')],capture_output=True,text=True)
        if result.returncode and 'Set --rnbo-dir or RNBO_DIR' in result.stderr:raise unittest.SkipTest('Licensed RNBO frontend required')
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        prepare(directory/'raw',directory/'strict','rnbos3patch','fx')
        cls.source=(directory/'strict/rnbo_source.h').read_bytes()

    def test_only_exact_audio_method_changes_and_uses_float_constants(self):
        source=self.source+b'\ndouble untouched_clock(double t) { return t * 0.001; }\n'
        result,report=float32_audio(source,code_mask=cpp_code_mask,profile='float32-auto-v1')
        self.assertEqual(len(report['methods']),1)
        method=report['methods'][0]
        self.assertEqual(method['kernel_sha256'],'85d6f0eb56e7e2f1450d1d10605e2f98f8d5f5ebb2acc9af93743fd6798f519f')
        self.assertEqual(method['method'],'lores_01_perform')
        self.assertEqual(len(method['literal_changes']),8)
        before=source.decode();after=result.decode()
        a,b=_method(cpp_code_mask(before),method['method']);c,d=_method(cpp_code_mask(after),method['method'])
        self.assertEqual(before[:a]+before[b:],after[:c]+after[d:])
        for required in ('if (0.9f !=','rnbo_exp(0.9f * 0.125f) * 0.882497f','rnbo_cos(2.0f * pi01()','-2.0f * res_temp','1.0f +'):
            self.assertIn(required,after[c:d])

    def test_unreviewed_coefficients_resonances_or_recurrences_stay_unchanged(self):
        for old,new in ((b'0.9',b'0.91'),(b'0.882497',b'0.882498'),(b'-2.0 * res_temp',b'-2.1 * res_temp')):
            changed=self.source.replace(old,new)
            self.assertNotEqual(changed,self.source)
            result,report=float32_audio(changed,code_mask=cpp_code_mask,profile='float32-auto-v1')
            self.assertEqual(result,changed)
            self.assertEqual(report['known_method_count'],0)
            self.assertEqual(report['skipped_method_count'],1)

    def test_earlier_explicit_profiles_do_not_inherit_new_method(self):
        for profile in ('float32-audio-v1','float32-audio-v2'):
            with self.subTest(profile=profile),self.assertRaisesRegex(ValueError,'no unique supported audio methods'):
                float32_audio(self.source,code_mask=cpp_code_mask,profile=profile)


if __name__=='__main__':unittest.main()
