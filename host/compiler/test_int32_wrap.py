# SPDX-License-Identifier: MIT
"""Portable adapter guards plus independent widened-arithmetic/UBSan proofs.

Synthetic runtime hashes are overridden only in isolated unit tests. The exact
production pins also receive a smoke test when the local real export exists.
"""
from pathlib import Path
import hashlib
import os
import subprocess
import tempfile
import unittest
from unittest import mock
import int32_wrap
from prepare import cpp_code_mask

ROOT=Path(__file__).resolve().parents[2]
MATH=b'#include <stdint.h>\nnamespace RNBO_Math {\n inline int32_t rnbo_imul(int32_t x, int32_t y) { return x * y; }\n}\n'
PINK="""Index {p}_generateRandomNumber() {{
    this->{p}_last = (BinOpInt)((BinOpInt)(rnbo_imul(this->{p}_last, 196314165) + 907633515) | (BinOpInt)0);
    Int tmp = (Int)(this->{p}_last);
    return tmp;
}}"""

def source(prefixes=(),number='float',index='uint32_t'):
    # Multibyte notices exercise byte offsets independently of character spans.
    return ('// original café notice: preserved exactly\nnamespace RNBO {\n'
            f'using Index={index};using Int=intptr_t;using BinOpInt=int32_t;using number={number};using SampleValue={number};\n'
            'using ::RNBO_Math::rnbo_imul;\nstruct Patch {\n'+
            ''.join('Index '+p+'_last;\n'+PINK.format(p=p)+'\n' for p in prefixes)+
            '};\n}\n').encode()


def packet(code):
    return {'common/RNBO_Math.h':MATH,'common/RNBO_Types.h':b'synthetic type header',
            'common/RNBO_AudioSignal.h':b'synthetic audio header','common/RNBO_Version.h':b'synthetic1.4.4',
            'rnbo_source.h':code,'unrelated.bin':b'\0unchanged\xff'}


def adapt(files):
    pins={name:hashlib.sha256(files[name]).hexdigest() for name in int32_wrap.RUNTIME_SHA256}
    with mock.patch.dict(int32_wrap.RUNTIME_SHA256,pins,clear=True):
        return int32_wrap.define_int32_wrap(files,code_mask=cpp_code_mask)


class GuardTests(unittest.TestCase):
    def test_no_pink_still_fixes_imul_and_preserves_source_and_input(self):
        original=packet(source());snapshot=dict(original);updated,records=adapt(original)
        self.assertEqual(original,snapshot);self.assertEqual(updated['rnbo_source.h'],original['rnbo_source.h'])
        self.assertEqual(len(records),1);self.assertIn(b'rnbo_defined_i32_from_u32',updated['common/RNBO_Math.h'])
        self.assertEqual(updated['unrelated.bin'],original['unrelated.bin'])
    def test_multiple_reviewed_pink_objects(self):
        updated,records=adapt(packet(source(('pink_tilde_01','pink_tilde_02'))))
        self.assertEqual(len(records),2);self.assertEqual(len(records[1]['methods']),2)
        self.assertEqual(updated['rnbo_source.h'].count(b'const uint32_t next'),2)
        self.assertNotIn(b'+ 907633515)',updated['rnbo_source.h'])
    def test_inverse_preserves_every_byte_outside_recorded_spans(self):
        original=packet(source(('pink_tilde_01','pink_tilde_03')));updated,records=adapt(original)
        for record in records:
            before=original[record['file']];after=updated[record['file']];a=b=0;old=[];new=[]
            for edit in record['edits']:
                start,stop=edit['input_span_bytes'];first,last=edit['prepared_span_bytes']
                old.append(before[a:start]);new.append(after[b:first]);a=stop;b=last
                self.assertEqual(hashlib.sha256(before[start:stop]).hexdigest(),edit['input_span_sha256'])
                self.assertEqual(hashlib.sha256(after[first:last]).hexdigest(),edit['prepared_span_sha256'])
            old.append(before[a:]);new.append(after[b:]);self.assertEqual(b''.join(old),b''.join(new))
            self.assertTrue(record['inverse_byte_identity'])
    def test_changed_runtime_hash_rejected(self):
        files=packet(source());pins={k:hashlib.sha256(files[k]).hexdigest() for k in int32_wrap.RUNTIME_SHA256}
        files['common/RNBO_Types.h']+=b' mutation'
        with mock.patch.dict(int32_wrap.RUNTIME_SHA256,pins,clear=True):
            with self.assertRaisesRegex(ValueError,'runtime'):int32_wrap.define_int32_wrap(files,code_mask=cpp_code_mask)
    def test_changed_imul_body_rejected_even_with_known_file_pin(self):
        files=packet(source());files['common/RNBO_Math.h']=MATH.replace(b'return x * y;',b'return x * y + 1;')
        with self.assertRaisesRegex(ValueError,'imul body'):adapt(files)
    def test_pink_multiplier_mutation_rejected(self):
        with self.assertRaisesRegex(ValueError,'affine recurrence'):adapt(packet(source(('pink_tilde_01',)).replace(b'196314165',b'196314167')))
    def test_pink_addend_mutation_rejected(self):
        with self.assertRaisesRegex(ValueError,'affine recurrence'):adapt(packet(source(('pink_tilde_01',)).replace(b'907633515',b'907633517')))
    def test_unknown_pink_naming_rejected(self):
        with self.assertRaisesRegex(ValueError,'naming'):adapt(packet(source(('pink_tilde_alpha',))))
    def test_missing_pink_generator_rejected(self):
        with self.assertRaisesRegex(ValueError,'method'):adapt(packet(source(('pink_tilde_01',)).replace(b'_generateRandomNumber()',b'_unknownNext()')))
    def test_duplicate_pink_prefix_rejected(self):
        body=PINK.format(p='pink_tilde_01').encode();code=source(('pink_tilde_01',)).replace(body,body+b'\n'+body)
        with self.assertRaisesRegex(ValueError,'one method'):adapt(packet(code))
    def test_changed_pink_state_type_rejected(self):
        files=packet(source(('pink_tilde_01',)));files['rnbo_source.h']=files['rnbo_source.h'].replace(b'Index pink_tilde_01_last;',b'uint64_t pink_tilde_01_last;')
        with self.assertRaisesRegex(ValueError,'state declaration'):adapt(files)
    def test_duplicate_state_declaration_rejected(self):
        files=packet(source(('pink_tilde_01',)));files['rnbo_source.h']=files['rnbo_source.h'].replace(b'Index pink_tilde_01_last;',b'Index pink_tilde_01_last;Index pink_tilde_01_last;')
        with self.assertRaisesRegex(ValueError,'state declaration'):adapt(files)
    def test_second_application_rejected(self):
        files=packet(source(('pink_tilde_01',)));updated,_=adapt(files)
        pins={k:hashlib.sha256(files[k]).hexdigest() for k in int32_wrap.RUNTIME_SHA256}
        with mock.patch.dict(int32_wrap.RUNTIME_SHA256,pins,clear=True):
            with self.assertRaisesRegex(ValueError,'runtime'):int32_wrap.define_int32_wrap(updated,code_mask=cpp_code_mask)
    def test_real_pinned_runtime_when_available(self):
        base=ROOT/'build/object-qualification/wave2-3/prepared/noise-colour/float32-strict'
        if not (base/'rnbo_source.h').exists():self.skipTest('Local authorized RNBO export is not available')
        files={name:(base/name).read_bytes() for name in (*int32_wrap.RUNTIME_SHA256,'rnbo_source.h')}
        updated,records=int32_wrap.define_int32_wrap(files,code_mask=cpp_code_mask)
        self.assertEqual(len(records),2);self.assertNotEqual(updated['rnbo_source.h'],files['rnbo_source.h'])


class ArithmeticProofTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name)
    def compile(self,files,main,*,sanitized=True):
        directory=self.directory;directory.joinpath('math.h').write_bytes(files['common/RNBO_Math.h']);directory.joinpath('source.h').write_bytes(files['rnbo_source.h'])
        path=directory/'proof.cpp';path.write_text('#include "math.h"\n#include "source.h"\n#include <cassert>\n#include <cstdio>\n'+main)
        flags=[os.environ.get('CXX','c++'),'-std=c++17','-O3','-fno-fast-math','-ffp-contract=off','-UNDEBUG']
        if sanitized:flags+=['-fsanitize=undefined,signed-integer-overflow','-fno-sanitize-recover=all']
        return subprocess.run([*flags,str(path),'-o',str(directory/'proof')],capture_output=True,text=True)
    def execute(self):return subprocess.run([str(self.directory/'proof')],capture_output=True,text=True)
    def test_original_imul_ubsan_fails(self):
        result=self.compile(packet(source()),'int main(){volatile int32_t a=907633515,b=196314165;std::printf("%lld",(long long)RNBO_Math::rnbo_imul(a,b));}')
        self.assertEqual(result.returncode,0,result.stderr);ran=self.execute();self.assertNotEqual(ran.returncode,0);self.assertIn('overflow',ran.stderr)
    def test_imul_only_still_leaves_pink_addition_overflow(self):
        original=packet(source(('pink_tilde_01',)));fixed,_=adapt(original);fixed['rnbo_source.h']=original['rnbo_source.h']
        built=self.compile(fixed,'int main(){RNBO::Patch p{};auto a=p.pink_tilde_01_generateRandomNumber();auto b=p.pink_tilde_01_generateRandomNumber();std::printf("%llu",(unsigned long long)a+b);}')
        self.assertEqual(built.returncode,0,built.stderr);ran=self.execute();self.assertNotEqual(ran.returncode,0);self.assertIn('overflow',ran.stderr)
    def test_defined_helpers_against_widened_oracle_edges_and_random(self):
        fixed,_=adapt(packet(source(('pink_tilde_01',))))
        main=r'''
static int32_t oracle(uint32_t bits){int64_t result=bits;if(bits>2147483647u)result-=INT64_C(4294967296);return static_cast<int32_t>(result);}
int main(){
 const int32_t edges[]={INT32_MIN,INT32_MIN+1,-1073741824,-65536,-46341,-32768,-2,-1,0,1,2,32767,46340,65535,1073741823,INT32_MAX-1,INT32_MAX};
 for(int32_t a:edges)for(int32_t b:edges){int64_t wide=(int64_t)a*b;assert(RNBO_Math::rnbo_imul(a,b)==oracle((uint32_t)((uint64_t)wide&UINT64_C(0xffffffff))));}
 uint32_t rng=0x12345678,state=0;RNBO::Patch patch{};
 for(unsigned n=0;n<200000;++n){
  rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;int32_t a=oracle(rng);
  rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;int32_t b=oracle(rng);
  int64_t wide=(int64_t)a*b;assert(RNBO_Math::rnbo_imul(a,b)==oracle((uint32_t)((uint64_t)wide&UINT64_C(0xffffffff))));
  assert(RNBO_Math::rnbo_defined_i32_from_u32(rng)==oracle(rng));
  uint64_t affine=(uint64_t)state*UINT32_C(196314165)+UINT32_C(907633515);state=(uint32_t)(affine&UINT64_C(0xffffffff));
  assert(patch.pink_tilde_01_generateRandomNumber()==state);
 }
 std::puts("DEFINED_INT32_ORACLE PASS edges=289 random_pairs=200000 pink_steps=200000");
}'''
        built=self.compile(fixed,main);self.assertEqual(built.returncode,0,built.stderr);ran=self.execute();self.assertEqual(ran.returncode,0,ran.stderr);self.assertIn('PASS',ran.stdout)
    def test_wrong_sample_precision_fails_compile_domain_guard(self):
        fixed,_=adapt(packet(source(('pink_tilde_01',),number='double')));built=self.compile(fixed,'int main(){return 0;}')
        self.assertNotEqual(built.returncode,0);self.assertIn('Float32 audio',built.stderr)
    def test_wrong_index_width_fails_compile_domain_guard(self):
        fixed,_=adapt(packet(source(('pink_tilde_01',),index='uint64_t')));built=self.compile(fixed,'int main(){return 0;}')
        self.assertNotEqual(built.returncode,0);self.assertIn('uint32 Index',built.stderr)

if __name__=='__main__':unittest.main()
