# SPDX-License-Identifier: MIT
"""Closed power-profile admission, deliberate rounding and exact fallback tests."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from bounded_filters import _method
from prepare import ExportError, cpp_code_mask, prepare
from scalar_powers import scalar_powers
from wrap_finite import correct_finite_wrap

ROOT=Path(__file__).resolve().parents[2]
SHA=lambda value:hashlib.sha256(value).hexdigest()


class ScalarPowerInputTests(unittest.TestCase):
    def test_invalid_maps_fail_without_mutation(self):
        for files in (None, [], {}, {"rnbo_source.h":"text"}, {"rnbo_source.h":b"unknown"}):
            before=copy.deepcopy(files)
            with self.assertRaises(ValueError):scalar_powers(files,{},code_mask=cpp_code_mask)
            self.assertEqual(files,before)


class ScalarPowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export=ROOT/'build/object-qualification/wave2-final/exports/nonlinear-domains'
        if not (cls.export/'rnbo_source.h').is_file():raise unittest.SkipTest('Generate the authorized nonlinear-domains export first')
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        p=Path(cls.temp.name)/'baseline';prepare(cls.export,p,'rnbos3patch','fx')
        provenance=json.loads((p/'provenance.json').read_text())
        cls.files={name:(p/name).read_bytes()for name in provenance['prepared_files_sha256']}
        cls.description=json.loads(cls.files['description.json'])
        cls.wrapped=correct_finite_wrap(cls.files,cls.description,code_mask=cpp_code_mask)[0]

    def adapt(self,wrapped=False):
        return scalar_powers(self.wrapped if wrapped else self.files,self.description,
                             code_mask=cpp_code_mask,finite_wrap_corrected=wrapped)

    def rejected(self,files,description=None,**kwargs):
        description=self.description if description is None else description
        snapshot=copy.deepcopy(files);desc=copy.deepcopy(description)
        with self.assertRaises(ValueError):scalar_powers(files,description,code_mask=kwargs.pop('code_mask',cpp_code_mask),**kwargs)
        self.assertEqual(files,snapshot);self.assertEqual(description,desc)

    def test_solo_header_equals_measured_private_candidate_and_full_inverse(self):
        updated,record=self.adapt();source=updated['rnbo_source.h'].decode();old=self.files['rnbo_source.h'].decode()
        self.assertEqual(SHA(updated['rnbo_source.h']),'4b5477f15f11a7bb8ca66b5844a5e73b20134d219f207df72d4f74ad8676269f')
        private=ROOT/'build/research/nonlinear-powers-v1/prepared/candidate/rnbo_source.h'
        if private.is_file():self.assertEqual(updated['rnbo_source.h'],private.read_bytes())
        a,b=_method(cpp_code_mask(old),'dspexpr_02_perform');c,d=_method(cpp_code_mask(source),'dspexpr_02_perform')
        self.assertEqual(source[:c]+old[a:b]+source[d:],old)
        self.assertEqual([k for k in self.files if updated[k]!=self.files[k]],['rnbo_source.h'])
        self.assertEqual(set(updated)-set(self.files),{'rnbo_s3_scalar_powers_source.h'})
        self.assertTrue(record['inverse_byte_identity'] and record['original_fixnan_retained'])
        self.assertFalse(record['bit_identity_claimed'] or record['floating_exception_identity_claimed'])

    def test_reviewed_wrap_first_composition_is_pinned_and_preserves_support(self):
        updated,record=self.adapt(True)
        self.assertEqual(SHA(updated['rnbo_source.h']),'f0774e0e80519692ad9da7b645460433b14981e6e3ec1f0ce0591042a8a607b2')
        self.assertTrue(record['finite_wrap_composition'])
        self.assertEqual([k for k in self.wrapped if updated[k]!=self.wrapped[k]],['rnbo_source.h'])
        for name in ('private_finite_wrap.h','rnbo_s3_finite_wrap_source.h'):
            self.assertEqual(updated[name],self.wrapped[name])
        self.rejected(self.wrapped)
        self.rejected(self.files,finite_wrap_corrected=True)
        self.rejected(updated,finite_wrap_corrected=True)
        self.rejected(self.files,finite_wrap_corrected=1)

    def test_unknown_header_near_matches_aliases_comments_and_partial_rewrites_reject(self):
        original=self.files['rnbo_source.h']
        for old,new in [(b'fixnan(rnbo_pow(in1[(Index)i], in2))',b'rnbo_pow(in1[(Index)i], in2)'),
                        (b'hi = 1;',b'hi = 2;'),(b'i < 256',b'i < 128'),
                        (b'number in2',b'double in2')]:
            self.assertIn(old,original);files=dict(self.files);files['rnbo_source.h']=original.replace(old,new,1);self.rejected(files)
        for suffix in (b'\n// dspexpr_02_perform near match\n',b'\nconst char* alias="dspexpr_02_perform";\n',b'\n/* unclosed'):
            files=dict(self.files);files['rnbo_source.h']+=suffix;self.rejected(files)
        self.rejected(self.adapt()[0])
        for name in ('rnbo_s3_scalar_powers_source.h','private_finite_wrap.h','rnbo_s3_finite_wrap_source.h'):
            files=dict(self.files);files[name]=b'partial';self.rejected(files)
        for name in ('private_finite_wrap.h','rnbo_s3_finite_wrap_source.h'):
            files=dict(self.wrapped);files[name]+=b'\n';self.rejected(files,finite_wrap_corrected=True)

    def test_runtime_description_width_version_and_masks_reject_atomically(self):
        desc=copy.deepcopy(self.description);desc['parameters'][0]['maximum']=8;self.rejected(self.files,desc)
        for name in ('description.json','common/RNBO_Types.h','common/RNBO_Version.h','common/RNBO_Math.h'):
            files=dict(self.files);files[name]+=b'\n';self.rejected(files)
        for action in ('add','remove'):
            files=dict(self.files)
            if action=='add':files['common/extra.h']=b'extra'
            else:del files['common/RNBO_Types.h']
            self.rejected(files)
        for mask in (lambda s:s+' ',lambda s:' '*len(s),lambda s:cpp_code_mask(s).replace('number in2','double in2')):
            self.rejected(self.files,code_mask=mask)

    def test_pipeline_metadata_and_float32_compile_contract(self):
        compiler=shutil.which('c++')
        with tempfile.TemporaryDirectory()as tmp:
            for wrapped in (False,True):
                p=Path(tmp)/str(wrapped)
                manifest=prepare(self.export,p,'rnbos3patch','fx',numerical_profile='float32-scalar-powers-v1',correct_finite_wrap=wrapped)
                provenance=json.loads((p/'provenance.json').read_text());contract=manifest['scalar_powers_contract']
                self.assertEqual(manifest['base_numerical_profile'],'float32-strict')
                self.assertEqual(manifest['numerical_identity'],'changed-rounding-float32-scalar-powers-v1')
                self.assertEqual(contract['finite_wrap_composition'],wrapped);self.assertFalse(contract['bit_identity_claimed'])
                self.assertEqual(provenance['adaptations'][-1]['name'],'rnbo-1.4.4-float32-scalar-powers-v1')
                self.assertEqual(provenance['compiler_helpers_sha256']['scalar_powers.py'],SHA((ROOT/'host/compiler/scalar_powers.py').read_bytes()))
                self.assertEqual((p/'rnbo_source.h').read_bytes(),self.adapt(wrapped)[0]['rnbo_source.h'])
                self.assertEqual((p/'patch_config.h').read_text().count('RNBO_S3_PATCH_SOURCE'),1)
                self.assertIn('rnbo_s3_scalar_powers_source.h',(p/'patch_config.h').read_text())
                if compiler:
                    probe=p/'probe.cpp';probe.write_text('#include "rnbo_s3_scalar_powers_source.h"\n')
                    cmd=[compiler,'-std=c++17','-fsyntax-only','-I'+str(p/'common'),str(probe)]
                    good=subprocess.run(cmd+['-DRNBO_USE_FLOAT32'],capture_output=True,text=True);self.assertEqual(good.returncode,0,good.stderr)
                    bad=subprocess.run(cmd,capture_output=True,text=True);self.assertNotEqual(bad.returncode,0);self.assertIn('requires binary32 RNBO samples',bad.stderr)

    def test_unsupported_roles_adapters_and_standalone_wrap_reject_without_output(self):
        extras=[{'apply_fixes':False},{'midi_output_policy':'discard'},{'filter_delay_max_ms':40},
                {'float32_delay_storage':True},{'omit_unused_mtof_table':True},{'hoist_cycle_conversions':True},
                {'compact_average_history':True},{'float32_pink_output':True}]
        with tempfile.TemporaryDirectory()as tmp:
            for index,extra in enumerate(extras):
                out=Path(tmp)/str(index)
                with self.assertRaises(ExportError):prepare(self.export,out,'rnbos3patch','fx',numerical_profile='float32-scalar-powers-v1',**extra)
                self.assertFalse(out.exists())
            out=Path(tmp)/'main'
            with self.assertRaises(ExportError):prepare(self.export,out,'rnbos3patch','main',numerical_profile='float32-scalar-powers-v1')
            self.assertFalse(out.exists())
            stereo=ROOT/'build/object-optimisation/wrap-target-v1/raw/wrap-finite-stereo'
            if (stereo/'rnbo_source.h').exists():
                for wrapped in (False,True):
                    out=Path(tmp)/('stereo'+str(wrapped))
                    with self.assertRaises(ExportError):prepare(stereo,out,'rnbos3patch','fx',numerical_profile='float32-scalar-powers-v1',correct_finite_wrap=wrapped)
                    self.assertFalse(out.exists())

    def test_generated_methods_keep_exact_fallback_neighbors_and_math_truth(self):
        compiler=shutil.which('c++')
        if not compiler:self.skipTest('C++ compiler required')
        old=self.files['rnbo_source.h'].decode();new=self.adapt()[0]['rnbo_source.h'].decode()
        a,b=_method(cpp_code_mask(old),'dspexpr_02_perform');c,d=_method(cpp_code_mask(new),'dspexpr_02_perform')
        notice=old[:old.index('*/')+2]
        cpp=notice+'\n#define RNBO_USE_FLOAT32\n#include <cmath>\n#include "RNBO_Types.h"\n#include "RNBO_Math.h"\n#include <cassert>\n#include <cstdio>\n#include <cstring>\n#include <initializer_list>\n'
        cpp+='#define RNBO_RESTRICT __restrict__\nnamespace RNBO { struct Reference{\n'+old[a:b]+'\n};struct Candidate{\n'+new[c:d]+'\n};}\n'
        cpp+=r'''
static float word(uint32_t bits){float x;std::memcpy(&x,&bits,4);return x;}
static uint32_t bits(float x){uint32_t b;std::memcpy(&b,&x,4);return b;}
int main(){
 RNBO::Reference reference;RNBO::Candidate candidate;float in[256],a[256],b[256];uint32_t rng=0x12345678u;unsigned long long checked=0,fallback=0;double maximum=0;
 const float exponents[]={.25f,2.f,4.f,word(0x3e7fffff),word(0x3e800001),word(0x3fffffff),word(0x40000001),word(0x407fffff),word(0x40800001),.5f,1.5f,2.5f};
 for(float exponent:exponents)for(unsigned batch=0;batch<256;++batch){
  for(unsigned i=0;i<256;++i){rng=rng*1664525u+1013904223u;in[i]=word(rng%0x3f800001u);}
  in[0]=0;in[1]=word(0x80000000u);in[2]=word(1);in[3]=word(0x7fffff);in[4]=word(0x800000);in[5]=word(0x3f7fffff);in[6]=1;
  volatile float runtime=exponent;reference.dspexpr_02_perform(in,runtime,a,256);candidate.dspexpr_02_perform(in,runtime,b,256);
  bool specialized=exponent==.25f||exponent==2.f||exponent==4.f;
  for(unsigned i=0;i<256;++i){assert(std::isfinite(b[i]));double error=std::fabs((double)b[i]-std::pow((double)in[i],(double)exponent));assert(error<=2e-6);if(error>maximum)maximum=error;++checked;if(!specialized){assert(bits(a[i])==bits(b[i]));++fallback;}}
 }
 for(float &x:in)x=word(0x80000000u);
 reference.dspexpr_02_perform(in,.25f,a,256);candidate.dspexpr_02_perform(in,.25f,b,256);
 assert(bits(a[0])==0&&bits(b[0])==0x80000000u); // Explicit deliberate sign difference.
 std::printf("checks=%llu exact_fallback=%llu quarter_negative_zero_differs=1 truth_max=%.17g\n",checked,fallback,maximum);
}
'''
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)
            for name,data in self.files.items():
                if name.startswith('common/'):
                    path=p/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            path=p/'probe.cpp';path.write_text(cpp)
            built=subprocess.run([compiler,'-std=c++17','-O3','-UNDEBUG','-fno-fast-math','-ffp-contract=off',
                                  '-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(p/'common'),str(path),'-o',str(p/'probe')],capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stderr)
            ran=subprocess.run([str(p/'probe')],capture_output=True,text=True,timeout=60)
            self.assertEqual(ran.returncode,0,ran.stderr)
            self.assertIn('checks=786432 exact_fallback=589824 quarter_negative_zero_differs=1',ran.stdout)


if __name__=='__main__':unittest.main()
