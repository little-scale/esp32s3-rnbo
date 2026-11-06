# SPDX-License-Identifier: MIT
import hashlib
import array
import json
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import tempfile
import unittest

from float32_audio import float32_audio
from float32_trial import float32_trial
from prepare import cpp_code_mask, prepare, NUMERICAL_PROFILES
from build import verify_prepared

ROOT=Path(__file__).resolve().parents[2]


def trial(source):
    return float32_trial(source,code_mask=cpp_code_mask)


class TrialSourceTests(unittest.TestCase):
    def test_unknown_signal_method_is_attempted_but_not_added_to_auto(self):
        source=b'void custom_01_perform(const Sample *in, SampleValue *out, Index n) { out[0] = in[0] * .37; }\n'
        result,r=trial(source)
        self.assertIn(b'* .37f;',result)
        self.assertEqual(r['trial_method_count'],1)
        self.assertEqual(r['qualification'],'unverified');self.assertTrue(r['experimental'])
        self.assertFalse(r['hardware_qualified'] or r['native_functional_qualified'])
        self.assertEqual(r['methods'][0]['input_method_sha256'],hashlib.sha256(source.rstrip()).hexdigest())
        self.assertEqual(r['methods'][0]['prepared_method_sha256'],hashlib.sha256(result.rstrip()).hexdigest())
        self.assertEqual(float32_audio(source,code_mask=cpp_code_mask,profile='float32-auto-v1')[0],source)
        self.assertEqual(trial(result)[0],result)

    def test_comments_strings_existing_suffixes_integers_and_shared_helpers_are_preserved(self):
        source=b'''number safediv(number a,number b) { return b == 0.0 ? 0.0 : a / b; }
void custom_01_perform(Sample *out, Index n) {
 // literal .37 and 2.5 in a comment
 const char *s = R"tag(2.5 })tag";
 out[0] = this->safediv(.37, 1.0f) + 2 + 0x10;
}
'''
        result,r=trial(source)
        self.assertIn(b'safediv(.37f, 1.0f) + 2 + 0x10',result)
        self.assertTrue(result.startswith(source[:source.index(b'void custom')]))
        self.assertIn(b'// literal .37 and 2.5 in a comment',result)
        self.assertIn(b'R"tag(2.5 })tag"',result)
        self.assertEqual(r['literal_suffix_count'],1)
        self.assertIn('shared-generated-helper-not-object-specific',[m['reason'] for m in r['skipped_methods']])

    def test_clock_setup_explicit_double_members_and_sensitive_helpers_are_excluded(self):
        examples=[
            b'double value;\nvoid custom_01_perform(Sample *out) { auto v=this->value;out[0]=v*.37; }\n',
            b'double first, second;\nvoid custom_01_perform(Sample *out) {out[0]=this->second*.37;}\n',
            b'void custom_01_perform(Sample *out) { double x=.37;out[0]=x; }\n',
            b'void custom_01_perform(Sample *out) {out[0]=this->_currentTime*.37;}\n',
            b'void custom_01_perform(Sample *out) {out[0]=this->mstosamps(.37);}\n',
            b'MillisecondTime helper_01_next(number x) {return x*0.001;}\nvoid custom_01_perform(Sample *out){out[0]=this->helper_01_next(.37);}\n',
            b'double helper_01_next(number x) {return x*.5;}\nvoid custom_01_perform(Sample *out){out[0]=helper_01_next(.37);}\n',
            b'void custom_01_perform(number x) { x *= .37; }\n',
            b'number helper_01_next(number x){return x;}\ndouble helper_01_next(double x){return x;}\nvoid custom_01_perform(Sample *out){out[0]=this->helper_01_next(.37);}\n',
        ]
        for source in examples:
            with self.subTest(source=source):
                result,r=trial(source);self.assertEqual(result,source);self.assertEqual(r['trial_method_count'],0)
                self.assertGreater(r['skipped_method_count'],0)

    def test_audio_helpers_can_be_attempted_but_shared_event_helpers_cannot(self):
        source=b'''void process() {this->custom_01_perform();}
void custom_01_perform(Sample *out) {out[0]=this->custom_01_next(0.3);}
number custom_01_next(number x) {return x*.37;}
'''
        result,r=trial(source)
        self.assertEqual(r['trial_method_count'],2)
        self.assertIn(b'x*.37f',result)
        shared=source+b'void processNumMessage(number x) {this->custom_01_next(x);}\n'
        result,r=trial(shared)
        self.assertIn(b'return x*.37;',result)
        self.assertEqual(r['trial_method_count'],1)
        self.assertIn('also-reachable-from-lifecycle-or-event',[m['reason'] for m in r['skipped_methods']])

    def test_malformed_nested_and_ambiguous_methods_do_not_get_partial_rewrites(self):
        with self.assertRaisesRegex(ValueError,'unterminated'):
            trial(b'void custom_01_perform(Sample *out) {out[0]=.37;\n')
        repeated=b'void custom_01_perform(Sample *out) {out[0]=.37;}\n'*2
        result,r=trial(repeated);self.assertEqual(result,repeated)
        self.assertTrue(all(m['reason']=='ambiguous-or-overloaded-method' for m in r['skipped_methods']))


class TrialLicensedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('node'):raise unittest.SkipTest('Licensed RNBO frontend required')
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name)
        for label,operator in [('scalar','*~ 0.37'),('gen','gen~ @expr "out1 = in1 * 0.37;"')]:
            boxes=[dict(id='constant',maxclass='newobj',text='sig~ 0.3'),dict(id='op',maxclass='newobj',text=operator),
                   dict(id='left',maxclass='newobj',text='out~ 1'),dict(id='right',maxclass='newobj',text='out~ 2')]
            source={'patcher':{'classnamespace':'rnbo','boxes':[{'box':b} for b in boxes],
                'lines':[{'patchline':{'source':[a,0],'destination':[b,0]}} for a,b in [('constant','op'),('op','left'),('op','right')]]}}
            path=cls.root/(label+'.rnbopat');path.write_text(json.dumps(source))
            result=subprocess.run(['node',str(ROOT/'archive/importer/integer-ui/export.mjs'),str(path),'--out',str(cls.root/(label+'-raw'))],capture_output=True,text=True)
            if result.returncode and 'Set --rnbo-dir or RNBO_DIR' in result.stderr:raise unittest.SkipTest('Licensed RNBO frontend required')
            if result.returncode:raise AssertionError(result.stdout+result.stderr)

    def test_gen_trial_compiles_and_renders_an_independently_calculated_constant(self):
        if not shutil.which('cmake') or not shutil.which('c++'):self.skipTest('Native C++ build tools required')
        prepared=self.root/'gen-render-trial';native=self.root/'gen-native'
        prepare(self.root/'gen-raw',prepared,'rnbos3patch','main',numerical_profile='float32-trial-v1')
        command=[sys.executable,str(ROOT/'host/compiler/build.py'),'--export',str(prepared),'--build-dir',str(native)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        output=self.root/'gen.f32'
        result=subprocess.run([str(native/'rnbo_render'),'--output',str(self.root/'gen.wav'),'--float-output',str(output),
                               '--blocks','4','--warmup','4'],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(report['errors'],0);self.assertEqual(report['invalid_samples'],0)
        f32=lambda v:struct.unpack('<f',struct.pack('<f',v))[0]
        expected=f32(f32(.3)*f32(.37))
        values=array.array('f');values.frombytes(output.read_bytes())
        if sys.byteorder!='little':values.byteswap()
        self.assertEqual(len(values),4*256*2)
        self.assertTrue(all(v==expected for v in values))

    def test_public_preparation_records_audit_and_keeps_reviewed_default(self):
        for label in ('scalar','gen'):
            with self.subTest(label=label):
                out=self.root/(label+'-trial')
                m=prepare(self.root/(label+'-raw'),out,'rnbos3patch','main',numerical_profile='float32-trial-v1')
                audit=(out/'float32-trial-audit.json').read_bytes();report=json.loads(audit)
                self.assertEqual(m['float32_trial']['audit_sha256'],hashlib.sha256(audit).hexdigest())
                self.assertEqual(report['qualification'],'unverified')
                self.assertIn('float32-trial-v1',NUMERICAL_PROFILES)
                self.assertGreater(report['trial_method_count'],0)
                self.assertEqual(m['scheduler_time'],'float64')
                verify_prepared(out)
                reference,_=float32_audio((out/'originals/rnbo_source.h').read_bytes(),code_mask=cpp_code_mask,profile='float32-auto-v1')
                self.assertNotEqual(reference,(out/'rnbo_source.h').read_bytes())


if __name__=='__main__':unittest.main()
