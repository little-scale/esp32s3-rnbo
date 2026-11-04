# SPDX-License-Identifier: MIT
"""Exact-source Gen delay promotion fix; no generated DSP is vendored."""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from build import verify_prepared
from prepare import (GEN_DELAY_BOOL_CLAMP_ADAPTATION, cpp_code_mask,
                     gen_delay_bool_clamp, prepare)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ('delay-one-and-three-samples', 'delay-three-sample-feedback')


class GenDelayIntegerPromotionTests(unittest.TestCase):
    def test_integral_promotion_value_and_evaluation_count(self):
        compiler = shutil.which('c++')
        if not compiler:
            self.skipTest('C++ compiler unavailable')
        source = r'''
#include <cstdint>
#include <limits>
struct Result { unsigned value; int reads; };
constexpr bool observed(bool x, int &reads) { ++reads; return x; }
constexpr Result original(int tap, bool different, unsigned maximum) {
    int reads=0;
    auto value=(tap>maximum?maximum:(tap<observed(different,reads)?observed(different,reads):tap));
    return {value,reads};
}
constexpr Result explicit_promotion(int tap, bool different, unsigned maximum) {
    int reads=0;
    auto value=(tap>maximum?maximum:(tap<static_cast<std::int32_t>(observed(different,reads))?observed(different,reads):tap));
    return {value,reads};
}
constexpr bool check() {
    for(int tap: {1,3}) for(bool different: {false,true})
        for(unsigned maximum: {0u,1u,2u,3u,16u,std::numeric_limits<unsigned>::max()}) {
            auto a=original(tap,different,maximum), b=explicit_promotion(tap,different,maximum);
            if(a.value!=b.value || a.reads!=b.reads || a.reads!=(static_cast<unsigned>(tap)>maximum?0:1)) return false;
        }
    return true;
}
static_assert(check(), "Explicit promotion preserves values and lazy evaluation");
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'promotion.cpp'; path.write_text('#include <initializer_list>\n'+source)
            process = subprocess.run([compiler, '-std=c++17', '-fsyntax-only', str(path)],
                                     capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)


class GenDelaySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(os.environ.get('RNBO_S3_TEST_GEN_DELAY_EXPORTS',
                         ROOT/'build/hardware/gen-state-boundaries-inputs-v3'))
        if not all((cls.base/'prepared'/name/'rnbo_source.h').is_file() for name in FIXTURES):
            raise unittest.SkipTest('Prepare the original authorized Gen Delay fixtures locally')
        cls.sources = {name: (cls.base/'prepared'/name/'rnbo_source.h').read_bytes() for name in FIXTURES}
        cls.types = (cls.base/'prepared'/FIXTURES[0]/'common/RNBO_Types.h').read_bytes()
        cls.raws = {name: (cls.base/'raw'/name if (cls.base/'raw'/name/'rnbo_source.h').is_file()
                          else cls.base/'prepared'/name/'originals') for name in FIXTURES}

    def test_exact_three_comparison_casts_and_independent_inverse(self):
        expected = {'delay-one-and-three-samples':
                    '6e73ee965c0f764384b319d04059dfc98834b62d242d39603d59a6d82796cf68',
                    'delay-three-sample-feedback':
                    '0cf6a88b8a8ac2762ccaff7cb2fcf4c5839428580a0ae297664eb94989a09340'}
        import hashlib
        for name, source in self.sources.items():
            changed, record = gen_delay_bool_clamp(source, self.types)
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256(changed).hexdigest(), expected[name])
                self.assertEqual(record['name'], GEN_DELAY_BOOL_CLAMP_ADAPTATION)
                self.assertEqual(record['cast_count'], 2 if name == FIXTURES[0] else 1)
                self.assertTrue(record['whole_source_inverse_verified'])
                # Independent inverse: only this exact inserted cast token is removed.
                self.assertEqual(changed.replace(b'static_cast<Int>', b''), source)
                self.assertEqual(changed.count(b'Float64BufferRef'), source.count(b'Float64BufferRef'))
                for method in record['methods']:
                    self.assertIn(method['tap_samples'], (1,3))
                    self.assertEqual(method['casts'], 1)

    def test_unknown_changed_or_repeated_methods_are_left_unchanged(self):
        source = self.sources[FIXTURES[1]]
        variants = [source.replace(b'(3 > ', b'(2 > ', 1),
                    source.replace(b'gen_01_feedbackDelay_reader !=', b'gen_01_feedbackDelay_reader ==', 1),
                    source.replace(b'number gen_01_feedbackDelay_read(', b'number other_read(', 1),
                    gen_delay_bool_clamp(source, self.types)[0], b'// no Gen Delay reader\n']
        for variant in variants:
            with self.subTest(source=variant[:20]):
                self.assertEqual(gen_delay_bool_clamp(variant, self.types), (variant, None))
        # One unknown reader does not authorize touching its bytes; only the
        # separate remaining recognized method receives its own exact cast.
        source = self.sources[FIXTURES[0]]
        altered = source.replace(b'number gen_01_leftDelay_read(', b'number other_read(', 1)
        changed, record = gen_delay_bool_clamp(altered, self.types)
        self.assertEqual(record['cast_count'], 1)
        self.assertEqual(record['methods'][0]['method'], 'gen_01_rightDelay_read')
        self.assertEqual(changed.replace(b'static_cast<Int>', b''), altered)

    def test_type_shadow_volatile_effectful_and_runtime_variants_are_noops(self):
        source = self.sources[FIXTURES[1]]
        variants = [source.replace(b'    Int gen_01_feedbackDelay_reader;',
                                  b'    volatile Int gen_01_feedbackDelay_reader;'),
                    source.replace(b'    Int gen_01_feedbackDelay_writer;',
                                  b'    number gen_01_feedbackDelay_writer;'),
                    source.replace(b'gen_01_feedbackDelay_reader !=', b'gen_01_feedbackDelay_reader++ !=', 1),
                    b'using Int = CustomInt;\n'+source,
                    b'#define Int CustomInt\n'+source,
                    b'#define gen_01_feedbackDelay_reader accessor()\n'+source]
        for variant in variants:
            self.assertNotEqual(variant, source)
            self.assertEqual(gen_delay_bool_clamp(variant, self.types), (variant, None))
        self.assertEqual(gen_delay_bool_clamp(source, self.types+b'\n'), (source, None))

    def test_comments_strings_and_duplicate_definitions_do_not_add_authority(self):
        source = self.sources[FIXTURES[1]]
        prefix = b'// number gen_01_fake_read() {}\nconst char *s=R"tag(3 < (reader != writer))tag";\n'
        modified = prefix+source.replace(b'3 < (this->', b'3 < /* preserve */ (this->', 1)
        changed, record = gen_delay_bool_clamp(modified, self.types)
        self.assertEqual(record['cast_count'], 1)
        self.assertTrue(changed.startswith(prefix)); self.assertIn(b'/* preserve */', changed)
        self.assertEqual(changed.replace(b'static_cast<Int>',b''), modified)
        from bounded_filters import _method
        text=source.decode(); a,b=_method(cpp_code_mask(text),'gen_01_feedbackDelay_read')
        duplicate=source+b'\n'+text[a:b].encode()
        self.assertEqual(gen_delay_bool_clamp(duplicate,self.types),(duplicate,None))

    def test_normal_prepare_applies_only_the_changed_source_and_records_original(self):
        for name in FIXTURES:
            raw=self.raws[name]
            if not (raw/'rnbo_source.h').is_file():self.skipTest('Original raw exports required')
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                out=Path(temp)/'prepared';manifest=prepare(raw,out,'rnbos3patch','fx')
                provenance,_,snapshot=verify_prepared(out)
                self.assertEqual(manifest['numerical_profile'],'float32-strict')
                self.assertEqual(manifest['adaptations'][-1],GEN_DELAY_BOOL_CLAMP_ADAPTATION)
                expected,record=gen_delay_bool_clamp(self.sources[name],self.types)
                self.assertEqual((out/'rnbo_source.h').read_bytes(),expected)
                self.assertEqual((out/'originals/rnbo_source.h').read_bytes(),(raw/'rnbo_source.h').read_bytes())
                self.assertEqual(provenance['adaptations'][-1],record)
                self.assertEqual(len(snapshot['prepared_files_sha256']),42)
                prior=json.loads((self.base/'prepared'/name/'provenance.json').read_text())['prepared_files_sha256']
                for path in prior:
                    if path!='rnbo_source.h':
                        self.assertEqual((out/path).read_bytes(),(self.base/'prepared'/name/path).read_bytes(),path)

    def test_no_fixes_and_unrelated_prepare_profiles_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp); raw=self.raws[FIXTURES[0]]
            result=prepare(raw,temp/'unfixed','rnbos3patch','fx',apply_fixes=False)
            self.assertNotIn(GEN_DELAY_BOOL_CLAMP_ADAPTATION,result['adaptations'])
            self.assertEqual((temp/'unfixed/rnbo_source.h').read_bytes(),(raw/'rnbo_source.h').read_bytes())
        other=ROOT/'build/research/dbtoa-f32-profile-v1/raw'
        if (other/'rnbo_source.h').is_file():
            with tempfile.TemporaryDirectory() as temp:
                for profile in ('float32-strict','float32-auto-v1','float32-dbtoa-v1'):
                    out=Path(temp)/profile;manifest=prepare(other,out,'rnbos3patch','fx',numerical_profile=profile)
                    self.assertNotIn(GEN_DELAY_BOOL_CLAMP_ADAPTATION,manifest['adaptations'])
                    prior=ROOT/'build/research/dbtoa-f32-profile-v1/prepared'/('candidate'if profile=='float32-dbtoa-v1'else'reference')
                    self.assertEqual((out/'rnbo_source.h').read_bytes(),(prior/'rnbo_source.h').read_bytes())


if __name__=='__main__':
    unittest.main()
