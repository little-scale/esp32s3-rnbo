# SPDX-License-Identifier: MIT
"""Value identity, control-flow preservation and actual compiler type gates."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from onepole_clamp import CONTRACT, transform
from prepare import ExportError, cpp_code_mask, prepare
from build import verify_prepared

ROOT = Path(__file__).resolve().parents[2]
NAME = '__onepole_tilde_01_a0'
STATEMENT = f'{NAME} = ({NAME} > 0.99999 ? 0.99999 : ({NAME} < 0.00001 ? 0.00001 : {NAME}));'


def source(declaration='float '+NAME+' = input;', statement=STATEMENT):
    return ('float changed(float input, bool enabled) {\n    '+declaration+'\n    if (enabled)\n        '+statement+'\n    else\n        return 17.0f;\n    return '+NAME+';\n}\n').encode()


class LocalProofTests(unittest.TestCase):
    def apply(self, data):
        return transform(data, code_mask=cpp_code_mask)

    def compile(self, text, flags=(), run=False):
        compiler=shutil.which('c++')
        if not compiler:self.skipTest('A C++ compiler is required')
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'probe.cpp';path.write_text(text);binary=Path(name)/'probe'
            command=[compiler,'-std=c++17','-fno-fast-math','-ffp-contract=off',*flags,str(path)]
            command+=['-o',str(binary)]if run else['-fsyntax-only']
            result=subprocess.run(command,capture_output=True,text=True)
            if run and result.returncode==0:
                result=subprocess.run([str(binary)],capture_output=True,text=True)
            return result

    def test_one_statement_inverse_no_input_mutation_and_explicit_limits(self):
        original=source();before=bytes(original);output,record=self.apply(original)
        self.assertEqual(original,before)
        self.assertTrue(record['full_inverse_byte_identity'])
        self.assertEqual(record['statement_count'],1)
        self.assertEqual(output.count(CONTRACT.encode()),1)
        self.assertIn(b'0.99999f',output)
        self.assertIn(b'0.00001f',output)
        self.assertFalse(record['baseline_accuracy_failures_repaired'])
        self.assertFalse(record['target_cpu_gain_claimed'])
        self.assertFalse(record['floating_environment_equivalence_claimed'])
        self.assertFalse(record['nan_payload_equivalence_claimed'])

    def test_comments_strings_and_near_matches_do_not_become_executable_edits(self):
        for data in (('/*\n'+STATEMENT+'\n*/\n').encode(),
                     ('const char *x=R"text(\n'+STATEMENT+'\n)text";\n').encode(),
                     source(statement=STATEMENT.replace('0.99999','0.99998')),
                     source(statement=STATEMENT.replace(NAME,NAME+'_other')),
                     source(statement='float '+STATEMENT),
                     source(statement='holder.'+STATEMENT)):
            with self.subTest(data=data),self.assertRaises(ValueError):self.apply(data)

    def test_repeated_input_invalid_masks_directives_and_line_splices_reject(self):
        output,_=self.apply(source())
        for data in (output,bytearray(source()),b'#line 100\n'+source(),b'# 100 "file"\n'+source(),source()+b'\nint x=__COUNTER__;\n',
                     b'#/**/line 100 "file"\n'+source(),b'#/**/ 100 "file"\n'+source(),
                     b'%:line 100\n'+source(),b'%: /**/ 100 "file"\n'+source(),b'??=line 100\n'+source(),
                     b'#define RUN \\\n'+source(),b'// line splice\\\n'+source()):
            with self.subTest(data=data[:70]),self.assertRaises(ValueError):self.apply(data)
        for mask in (lambda _:None,lambda _:''):
            with self.assertRaises(ValueError):transform(source(),code_mask=mask)

    def test_actual_operand_types_fast_math_and_macro_operands_fail_closed(self):
        for declaration,good in [('float '+NAME+' = input;',True),('double '+NAME+' = input;',False),
                                 ('volatile float '+NAME+' = input;',False),('float &'+NAME+' = input;',False),
                                 ('int '+NAME+' = 0;',False)]:
            output,_=self.apply(source(declaration=declaration));result=self.compile(output.decode())
            with self.subTest(declaration=declaration):self.assertEqual(result.returncode==0,good,result.stderr)
        output,_=self.apply(source())
        for flags in (['-ffast-math'],['-ffinite-math-only']):
            with self.subTest(flags=flags):self.assertNotEqual(self.compile(output.decode(),flags).returncode,0)
        output,_=self.apply(source(declaration='float storage=input;',statement=STATEMENT))
        result=self.compile('#define '+NAME+' storage\n'+output.decode())
        self.assertNotEqual(result.returncode,0)
        self.assertIn('rejects macros',result.stderr)
        for definition in ('#define static_assert(...)', '#define float double',
                           '#define decltype(...) float', '#define is_same is_convertible',
                           '#define value true', '#define std custom_namespace'):
            raw=definition.encode()+b'\n'+source(declaration='double '+NAME+' = input;')
            output,_=self.apply(raw)
            result=self.compile(output.decode())
            with self.subTest(definition=definition):
                self.assertNotEqual(result.returncode,0)
                self.assertIn('rejects macros',result.stderr)

    def test_unbraced_if_else_loop_switch_and_do_while_keep_execution(self):
        bodies=[f'if (enabled)\n        {STATEMENT}\n    else\n        return 17.0f;',
                f'for (int i=0;i<(enabled ? 1 : 0);++i)\n        {STATEMENT}',
                f'do\n        {STATEMENT}\n    while (false);',
                f'switch (enabled) {{case false:\n        {STATEMENT}\n        break;case true:return 17.0f;}}']
        prefix='#include <cstdint>\n#include <cstring>\n#include <cstdio>\n'
        text=prefix
        for i,body in enumerate(bodies):
            raw=('float changed'+str(i)+'(float input, bool enabled) {\n    float '+NAME+'=input;\n    '+body+'\n    return '+NAME+';\n}\n').encode()
            output,_=self.apply(raw)
            text+='\n#line 1\n'+raw.decode().replace('changed'+str(i),'reference'+str(i))+output.decode()
        text+='''
static std::uint32_t bits(float v){std::uint32_t u;std::memcpy(&u,&v,4);return u;}
static float word(std::uint32_t u){float v;std::memcpy(&v,&u,4);return v;}
int main(){
 const std::uint32_t edges[]={0,0x80000000u,1,0x80000001u,0x3727c5abu,0x3727c5acu,0x3727c5adu,0x3f7fff57u,0x3f7fff58u,0x3f7fff59u,0x7f7fffffu,0xff7fffffu};
 for(auto u:edges)for(int enabled=0;enabled<2;++enabled){float x=word(u);
'''
        for i in range(len(bodies)):
            text+=f'if(bits(reference{i}(x,enabled))!=bits(changed{i}(x,enabled)))return {i+1};\n'
        text+='}return 0;}\n'
        for flags in (['-O3'],['-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined']):
            result=self.compile(text,flags,run=True)
            with self.subTest(flags=flags):self.assertEqual(result.returncode,0,result.stderr)

    def test_source_line_expressions_after_replacement_preserve_original_values(self):
        raw=('float changed(float input, bool enabled) {\n    float '+NAME+'=input;\n    '+STATEMENT+'\n    return __LINE__;\n}\n').encode()
        output,_=self.apply(raw)
        text='#line 1\n'+raw.decode().replace('changed','reference')+output.decode()
        text+='int main(){return changed(0,true)==reference(0,true) ? 0 : 1;}\n'
        result=self.compile(text,run=True);self.assertEqual(result.returncode,0,result.stderr)

    def test_multiple_statements_and_operand_suffixes_are_independent(self):
        raw=source()+source().replace(b'changed',b'changed2').replace(b'_01_',b'_237_')
        output,record=self.apply(raw)
        self.assertEqual(record['statement_count'],2)
        self.assertEqual([s['operand']for s in record['statements']],[NAME,NAME.replace('_01_','_237_')])
        result=self.compile(output.decode());self.assertEqual(result.returncode,0,result.stderr)


class PipelineTests(unittest.TestCase):
    def test_option_types_and_incompatible_modes_reject_before_export_reads(self):
        with tempfile.TemporaryDirectory()as name:
            root=Path(name)
            for value in (0,1,None,'true',[]):
                with self.subTest(value=value),self.assertRaises(ExportError):
                    prepare(root/'missing',root/'output','patch','fx',float32_onepole_clamp=value)
                self.assertFalse((root/'output').exists())
            for options in ({'apply_fixes':False},{'numerical_profile':'float32-audio-v2'},
                            {'hoist_train_reciprocal':True},{'bounded_line_ramps':True},
                            {'filter_delay_max_ms':40},{'correct_finite_wrap':True}):
                with self.subTest(options=options),self.assertRaises(ExportError):
                    prepare(root/'missing',root/'output','patch','fx',float32_onepole_clamp=True,**options)
                self.assertFalse((root/'output').exists())

    def test_fresh_licensed_three_form_pipeline_default_and_provenance(self):
        with tempfile.TemporaryDirectory()as name:
            root=Path(name)
            for form in ('onepole-fixed-stereo','onepole-scalar-stereo','onepole-signal-cutoff'):
                raw=root/(form+'-raw')
                try:ran=subprocess.run(['node',str(ROOT/'archive/importer/integer-ui/export.mjs'),str(ROOT/'tests/fixtures/objects/wave3'/(form+'.rnbopat')),'--out',str(raw)],capture_output=True,text=True)
                except FileNotFoundError:self.skipTest('Node and authorised RNBO1.4.4 required')
                if ran.returncode and 'Set --rnbo-dir or RNBO_DIR' in ran.stderr:self.skipTest('Authorised RNBO1.4.4 not installed')
                self.assertEqual(ran.returncode,0,ran.stderr)
                reference=root/(form+'-reference');candidate=root/(form+'-candidate')
                original=prepare(raw,reference,'rnbos3patch','fx')
                manifest=prepare(raw,candidate,'rnbos3patch','fx',float32_onepole_clamp=True)
                provenance,_,snap=verify_prepared(candidate)
                self.assertNotIn('float32_onepole_clamp',original)
                self.assertTrue(manifest['float32_onepole_clamp'])
                self.assertEqual(manifest['numerical_profile'],'float32-strict')
                self.assertFalse(manifest['float32_onepole_clamp_contract']['floating_environment_equivalence_claimed'])
                self.assertIn('onepole_clamp.py',provenance['compiler_helpers_sha256'])
                for relative in snap['prepared_files_sha256']:
                    if relative!='rnbo_source.h':self.assertEqual((candidate/relative).read_bytes(),(reference/relative).read_bytes())
                expected,record=transform((reference/'rnbo_source.h').read_bytes(),code_mask=cpp_code_mask)
                self.assertEqual((candidate/'rnbo_source.h').read_bytes(),expected)
                self.assertEqual(record['statement_count'],1 if form=='onepole-signal-cutoff' else 2)
                self.assertTrue((candidate/'originals/rnbo_source.h').is_file())


if __name__=='__main__':unittest.main()
