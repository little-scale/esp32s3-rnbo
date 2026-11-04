# SPDX-License-Identifier: MIT
"""Finite-bit Gen abs admission, generated type checks and atomic failures."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from gen_abs_intrinsic import CONTRACT, CONTRACT_FILE, MANIFEST_CONTRACT, SOURCE, OUTPUT, transform
from prepare import ExportError, prepare, cpp_code_mask
from build import verify_prepared

ROOT=Path(__file__).resolve().parents[2]


class GenAbsInputTests(unittest.TestCase):
    def test_invalid_boolean_and_compositions_reject_before_export_io(self):
        modes=[('gen_abs_intrinsic',x)for x in (0,1,None,'yes')]
        modes += [('role','main'),('class_name','other'),('apply_fixes',False),('apply_fixes',1),
                  ('midi_output_policy','discard'),('numerical_profile','float32-gen-feedback-v1'),('filter_delay_max_ms',40)]
        modes += [(key,True)for key in ('float32_delay_storage','omit_unused_mtof_table','hoist_cycle_conversions',
            'compact_average_history','float32_pink_output','correct_finite_wrap','exact_audio_delay44100',
            'hoist_filter_durations','hoist_train_reciprocal','bounded_line_ramps','float32_onepole_clamp','stable_onepole')]
        with tempfile.TemporaryDirectory()as name:
            directory=Path(name)
            for key,value in modes:
                args={'class_name':'rnbos3patch','role':'fx','gen_abs_intrinsic':True};args[key]=value
                with self.subTest(key=key,value=value),self.assertRaises(ExportError):
                    prepare(directory/'absent',directory/'output',**args)
                self.assertFalse((directory/'output').exists())

    def test_compile_contract_rejects_wrong_audio_clock_abi_flags_and_evaluation(self):
        compiler=shutil.which('c++')
        if not compiler:self.skipTest('C++ compiler unavailable')
        with tempfile.TemporaryDirectory()as name:
            directory=Path(name);(directory/CONTRACT_FILE).write_bytes(CONTRACT)
            variants=[('float','float','float','double',1,0,[],0,True),
                ('double','float','float','double',1,0,[],0,False),('float','double','float','double',1,0,[],0,False),
                ('float','float','double','double',1,0,[],0,False),('float','float','float','float',1,0,[],0,False),
                ('float','float','float','double',None,0,[],0,False),('float','float','float','double',1,None,[],0,False),
                ('float','float','float','double',2,0,[],0,False),('float','float','float','double',1,1,[],0,False),
                ('float','float','float','double',1,0,['-ffast-math'],0,False),
                ('float','float','float','double',1,0,['-ffinite-math-only'],0,False),
                ('float','float','float','double',1,0,[],2,False)]
            for number,sample,out,clock,major,minor,flags,evaluation,good in variants:
                (directory/'rnbo_source.h').write_text('namespace RNBO{using number='+number+';using Sample='+sample+
                    ';using SampleValue='+out+';using MillisecondTime='+clock+';}')
                macros='\n'.join('#define '+key+' '+str(value)for key,value in [('RNBO_S3_ABI_MAJOR',major),('RNBO_S3_ABI_MINOR',minor)]if value is not None)
                if evaluation:macros+='\n#include <float.h>\n#undef FLT_EVAL_METHOD\n#define FLT_EVAL_METHOD '+str(evaluation)
                path=directory/'types.cpp';path.write_text(macros+'\n#include "'+CONTRACT_FILE+'"\n')
                result=subprocess.run([compiler,'-std=c++17','-fsyntax-only',*flags,str(path)],capture_output=True,text=True)
                with self.subTest(types=(number,sample,out,clock),abi=(major,minor),flags=flags,evaluation=evaluation):
                    self.assertEqual(result.returncode==0,good,result.stderr)


class GenAbsPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.directory=Path(cls.temp.name);cls.raw=cls.directory/'raw'
        try:result=subprocess.run(['node',str(ROOT/'host/export/export.mjs'),str(ROOT/'tests/fixtures/gen/arithmetic/abs-call.rnbopat'),
                                   '--out',str(cls.raw)],capture_output=True,text=True)
        except FileNotFoundError:raise unittest.SkipTest('Node and licensed frontend required')
        if result.returncode and 'Set --rnbo-dir or RNBO_DIR'in result.stderr:raise unittest.SkipTest('Licensed frontend unavailable')
        if result.returncode:raise AssertionError(result.stderr)
        cls.strict=cls.directory/'strict';prepare(cls.raw,cls.strict,'rnbos3patch','fx')
        cls.files={name:(cls.strict/name).read_bytes()for name in verify_prepared(cls.strict)[2]['prepared_files_sha256']if name!='patch_config.h'}
        cls.description=json.loads(cls.files['description.json'])

    def test_exact_producer_epochs_and_unknown_metadata_remain_closed(self):
        import gen_abs_intrinsic as module
        for stamp,expected in (
                ('56fb9edda0184c282b64f9ba66ab70817866cb981fa5aee4b3050e804bac3065',module.INPUT_MAP),
                ('4af4ee869ca842cd9ffbd0421367b46f491767c203971d3c83fff4e89fd3ce5e',module.INTEGER_UI_INPUT_MAP)):
            files=dict(self.files);generator=json.loads(files['generator.json'])
            generator['patcher_adapter_sha256']=stamp
            files['generator.json']=(json.dumps(generator,indent=2)+'\n').encode()
            before=copy.deepcopy(files)
            changed,record=transform(files,self.description,code_mask=cpp_code_mask)
            self.assertEqual(files,before)
            self.assertEqual(record['input_map_sha256'],expected)
            self.assertEqual(module.sha(changed['rnbo_source.h']),OUTPUT)
            for key,value in (('patcher_adapter_sha256','f'*64),('adapter_sha256','0'*64),
                              ('generated_sha256','0'*64),('voices',2),('class_name','other'),('unknown',False)):
                bad=dict(files);metadata=dict(generator);metadata[key]=value
                bad['generator.json']=(json.dumps(metadata,indent=2)+'\n').encode()
                before=copy.deepcopy(bad)
                with self.subTest(stamp=stamp,key=key),self.assertRaises(ValueError):
                    transform(bad,self.description,code_mask=cpp_code_mask)
                self.assertEqual(bad,before)

    def test_fresh_public_option_preserves_strict_profile_and_two_callee_inverse(self):
        out=self.directory/'candidate';m=prepare(self.raw,out,'rnbos3patch','fx',gen_abs_intrinsic=True)
        provenance,_,snapshot=verify_prepared(out)
        self.assertEqual(m['numerical_profile'],'float32-strict');self.assertIs(m['gen_abs_intrinsic'],True)
        self.assertEqual(m['gen_abs_intrinsic_contract'],MANIFEST_CONTRACT)
        self.assertEqual(snapshot['prepared_files_sha256']['rnbo_source.h'],OUTPUT)
        old=self.files['rnbo_source.h'];new=(out/'rnbo_source.h').read_bytes()
        self.assertEqual(new.replace(b'__builtin_fabsf(',b'rnbo_abs('),old)
        self.assertEqual(new.count(b'__builtin_fabsf('),2)
        for name,data in self.files.items():
            if name!='rnbo_source.h':self.assertEqual((out/name).read_bytes(),data,name)
        self.assertEqual(provenance['adaptations'][-1]['input_sha256'],SOURCE)
        self.assertEqual(provenance['adaptations'][-1]['callee_replacements'],2)
        self.assertEqual((out/CONTRACT_FILE).read_bytes(),CONTRACT)
        self.assertIn(CONTRACT_FILE,(out/'patch_config.h').read_text())
        from gen_arithmetic_contract import admit_module
        fixture=json.loads((ROOT/'tests/fixtures/gen/abs-intrinsic/catalog.json').read_bytes())['fixtures'][0]
        module={'report':{'prepared_export':{'manifest':m,'provenance':provenance},'prepared_snapshot':snapshot}}
        admit_module(fixture,module,candidate=True)
        changed=copy.deepcopy(module)
        changed['report']['prepared_snapshot']['prepared_files_sha256']['generator.json']='0'*64
        with self.assertRaises(ValueError):admit_module(fixture,changed,candidate=True)

    def test_unknown_or_repeated_source_maps_and_description_reject_atomically(self):
        for mutation in ('source','graph','runtime','metadata','extra','missing','mutable','repeat'):
            files=dict(self.files)
            if mutation=='extra':files['other.h']=b''
            elif mutation=='missing':files.pop('source.rnbopat')
            elif mutation=='mutable':files['rnbo_source.h']=bytearray(files['rnbo_source.h'])
            elif mutation=='repeat':files=transform(files,self.description,code_mask=cpp_code_mask)[0]
            else:files[{'source':'rnbo_source.h','graph':'source.rnbopat','runtime':'common/RNBO_Math.h','metadata':'generator.json'}[mutation]]+=b'\n'
            before=copy.deepcopy(files)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):transform(files,self.description,code_mask=cpp_code_mask)
            self.assertEqual(files,before)
        with self.assertRaises(ValueError):transform(self.files,{},code_mask=cpp_code_mask)

    def test_unknown_raw_file_or_symbolic_link_leaves_no_prepared_output(self):
        for link in (False,True):
            raw=self.directory/('link-raw'if link else'extra-raw');shutil.copytree(self.raw,raw)
            if link:(raw/'extra.h').symlink_to(raw/'rnbo_source.h')
            else:(raw/'extra.h').write_text('unknown')
            out=raw.parent/(raw.name+'-output')
            with self.assertRaises(ExportError):prepare(raw,out,'rnbos3patch','fx',gen_abs_intrinsic=True)
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
