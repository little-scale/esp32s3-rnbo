# SPDX-License-Identifier: MIT
"""Finite-state robustness and guarded real-export correctness admission."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from prepare import ExportError, cpp_code_mask, prepare
from build import verify_prepared
from stable_onepole import CONTRACT, CONTEXTS, HELPER_SHA256, OPTIONS, sha, transform

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'host/compiler'
HELPER=(WORK/'onepole_stable.h').read_bytes()



def assert_generator_epoch_only(case, actual, historical):
    """Historical metadata is kept; only the explicitly reviewed stamp differs."""
    if actual == historical: return
    left=json.loads(actual); right=json.loads(historical)
    case.assertEqual(set(left),set(right))
    known={'de348978139adf64571ccde382b2be79fa80027e5557b0340dda80cf9428b079',
           '56fb9edda0184c282b64f9ba66ab70817866cb981fa5aee4b3050e804bac3065',
           '4af4ee869ca842cd9ffbd0421367b46f491767c203971d3c83fff4e89fd3ce5e'}
    case.assertIn(left['patcher_adapter_sha256'],known)
    case.assertIn(right['patcher_adapter_sha256'],known)
    left['patcher_adapter_sha256']=right['patcher_adapter_sha256']
    case.assertEqual((json.dumps(left,indent=2)+'\n').encode(),historical)


class InputTests(unittest.TestCase):
    def test_option_types_and_modes_reject_before_reading_an_export(self):
        with tempfile.TemporaryDirectory()as name:
            root=Path(name)
            for value in (0,1,None,'true',[],{}):
                with self.subTest(value=value),self.assertRaises(ExportError):
                    prepare(root/'missing',root/'out','patch','fx',stable_onepole=value)
                self.assertFalse((root/'out').exists())
            for args in ({'role':'main'},{'apply_fixes':False},{'apply_fixes':1},
                         {'numerical_profile':'float32-audio-v2'},{'midi_output_policy':'discard'},
                         {'float32_onepole_clamp':True},{'bounded_line_ramps':True},
                         {'filter_delay_max_ms':40},{'hoist_filter_durations':True},
                         {'hoist_train_reciprocal':True},{'float32_pink_output':True},
                         {'float32_delay_storage':True},{'omit_unused_mtof_table':True},
                         {'hoist_cycle_conversions':True},{'compact_average_history':True},
                         {'correct_finite_wrap':True},{'exact_audio_delay44100':True}):
                options={'role':'fx',**args}
                with self.subTest(args=args),self.assertRaises(ExportError):
                    prepare(root/'missing',root/'out','patch',stable_onepole=True,**options)
                self.assertFalse((root/'out').exists())

    def test_invalid_maps_options_and_helper_bytes_are_not_coerced(self):
        for files in (None,[],{}, {'rnbo_source.h':bytearray(b'mutable')},{1:b'bad'}):
            before=copy.deepcopy(files)
            with self.assertRaises(ValueError):transform(files,{},copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=HELPER)
            self.assertEqual(files,before)
        for options in (None,[],{},dict(OPTIONS,sample_rate=44100.),dict(OPTIONS,apply_fixes=1),dict(OPTIONS,unknown=False)):
            with self.assertRaises(ValueError):transform({}, {},options,code_mask=cpp_code_mask,helper=HELPER)
        for helper in (bytearray(HELPER),HELPER+b'\n',None):
            with self.assertRaises(ValueError):transform({}, {},copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=helper)

    def test_actual_original_helper_finite_state_and_frequency_properties(self):
        compiler=shutil.which('c++')
        if not compiler:self.skipTest('C++ compiler required')
        self.assertEqual(sha(HELPER),HELPER_SHA256)
        with tempfile.TemporaryDirectory()as name:
            root=Path(name);records=[]
            for mode,flags in [('O3',['-O3']),('UBSan',['-O2','-fsanitize=undefined,signed-integer-overflow,float-cast-overflow','-fno-sanitize-recover=all'])]:
                binary=root/mode
                result=subprocess.run([compiler,'-std=c++17',*flags,'-fno-fast-math','-ffp-contract=off','-fno-builtin','-I'+str(WORK),str(ROOT/'tests/native/onepole_stable.cpp'),'-o',str(binary)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                result=subprocess.run([str(binary)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stderr,'')
                record=json.loads(result.stdout);records.append(record)
                self.assertEqual(record['state_nonfinite_or_return_mismatch'],0)
                self.assertEqual(record['coefficient_nonfinite_or_out_of_bounds'],0)
                self.assertGreater(record['standalone_state_trials'],1000000)
                self.assertGreater(record['coefficient_frequency_trials'],1000000)
                self.assertEqual(record['forced_debt_overflow_y_bits'],'7f7fffff')
                self.assertEqual(record['forced_symmetric_y_bits'],'ff7fffff')
                self.assertEqual(record['opposite_extreme_result_bits'],'00000000')
            self.assertEqual(records[0],records[1])

    def test_compile_contract_rejects_wrong_types_clock_abi_and_fast_math(self):
        compiler=shutil.which('c++')
        if not compiler:self.skipTest('C++ compiler required')
        with tempfile.TemporaryDirectory()as name:
            source=Path(name)/'types.cpp'
            for audio,clock,extra,good in [('float','double',[],True),('double','double',[],False),
                                         ('int','double',[],False),('float','float',[],False),
                                         ('float','long long',[],False),('float','double',['-ffast-math'],False),
                                         ('float','double',['-ffinite-math-only'],False)]:
                source.write_text('namespace RNBO{using number='+audio+';using Sample='+audio+';using SampleValue='+audio+';using MillisecondTime='+clock+';}\n'+CONTRACT)
                result=subprocess.run([compiler,'-std=c++17','-fsyntax-only','-I'+str(WORK),'-DRNBO_S3_ABI_MAJOR=1u','-DRNBO_S3_ABI_MINOR=0u','-DRNBO_FIXEDLISTSIZE=16',*extra,str(source)],capture_output=True,text=True)
                with self.subTest(audio=audio,clock=clock,extra=extra):self.assertEqual(result.returncode==0,good,result.stderr)
            source.write_text('namespace RNBO{using number=float;using Sample=float;using SampleValue=float;using MillisecondTime=double;}\n'+CONTRACT)
            for flags in ([],['-DRNBO_S3_ABI_MAJOR=2u','-DRNBO_S3_ABI_MINOR=0u','-DRNBO_FIXEDLISTSIZE=16'],['-DRNBO_S3_ABI_MAJOR=1u','-DRNBO_S3_ABI_MINOR=0u','-DRNBO_FIXEDLISTSIZE=32']):
                result=subprocess.run([compiler,'-std=c++17','-fsyntax-only','-I'+str(WORK),*flags,str(source)],capture_output=True,text=True)
                with self.subTest(flags=flags):self.assertNotEqual(result.returncode,0)


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup);cls.root=Path(cls.temp.name);cls.exports={};cls.references={};cls.maps={}
        for context in CONTEXTS:
            raw=cls.root/(context+'-raw')
            try:result=subprocess.run(['node',str(ROOT/'host/export/export.mjs'),str(ROOT/'tests/fixtures/objects/wave3'/(context+'.rnbopat')),'--out',str(raw)],capture_output=True,text=True)
            except FileNotFoundError:raise unittest.SkipTest('Node and authorised RNBO1.4.4 required')
            if result.returncode and 'Set --rnbo-dir or RNBO_DIR' in result.stderr:raise unittest.SkipTest('Authorised RNBO1.4.4 not installed')
            if result.returncode:raise AssertionError(result.stderr)
            reference=cls.root/(context+'-reference');prepare(raw,reference,'rnbos3patch','fx')
            cls.exports[context]=raw;cls.references[context]=reference;cls.maps[context]={n:(reference/n).read_bytes()for n in verify_prepared(reference)[2]['prepared_files_sha256']}


    def test_all_three_contexts_both_exact_metadata_epochs_and_unknown_mutations(self):
        import stable_onepole as module
        from prepare import canonical
        for context,original in self.maps.items():
            for stamp,expected in [
                ('de348978139adf64571ccde382b2be79fa80027e5557b0340dda80cf9428b079',module.CONTEXTS[context]['file_map']),
                ('56fb9edda0184c282b64f9ba66ab70817866cb981fa5aee4b3050e804bac3065',module.GENEXPR_FILE_MAPS[context]),
                ('4af4ee869ca842cd9ffbd0421367b46f491767c203971d3c83fff4e89fd3ce5e',module.INTEGER_UI_FILE_MAPS[context])]:
                generator=json.loads(original['generator.json']);generator['patcher_adapter_sha256']=stamp
                files=dict(original);files['generator.json']=(json.dumps(generator,indent=2)+'\n').encode()
                before=copy.deepcopy(files)
                _,record=transform(files,json.loads(files['description.json']),copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=HELPER)
                self.assertEqual(record['whole_input_map_sha256'],expected)
                self.assertEqual(sha(canonical({n:sha(v)for n,v in sorted(files.items())})),expected)
                self.assertEqual(files,before)
                for key,value in [('patcher_adapter_sha256','f'*64),('adapter_sha256','0'*64),
                                  ('generated_sha256','0'*64),('voices',2),('class_name','other'),('unknown',False)]:
                    changed=dict(generator);changed[key]=value
                    bad=dict(files);bad['generator.json']=(json.dumps(changed,indent=2)+'\n').encode();snapshot=copy.deepcopy(bad)
                    with self.subTest(context=context,epoch=stamp,key=key),self.assertRaises(ValueError):
                        transform(bad,json.loads(bad['description.json']),copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=HELPER)
                    self.assertEqual(bad,snapshot)

    def test_pure_three_form_transform_preserves_all_other_files_and_private_code(self):
        for context,files in self.maps.items():
            description=json.loads(files['description.json']);before=copy.deepcopy((files,description,OPTIONS))
            with mock.patch('builtins.open',side_effect=AssertionError('Pure transform performs no I/O')):
                candidate,record=transform(files,description,copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=HELPER)
            self.assertEqual(before,(files,description,OPTIONS));self.assertEqual(len(candidate),43)
            self.assertEqual(candidate['onepole_stable.h'],HELPER)
            for n in files:
                if n!='rnbo_source.h':self.assertEqual(candidate[n],files[n])
            self.assertTrue(record['source_inverse_byte_identity']);self.assertTrue(record['assertion_removal_byte_identity'])
            self.assertEqual(record['added_state_members'],0);self.assertFalse(record['baseline_bit_identity_claimed'])
            self.assertFalse(record['target_cpu_gain_claimed'])
            historical=ROOT/'build/research/onepole-finite-scale-v1/prepared'/context
            if historical.is_dir():
                stripped=candidate['rnbo_source.h'].replace(CONTRACT.encode(),b'#include "onepole_stable.h"\n')
                self.assertEqual(stripped,(historical/'rnbo_source.h').read_bytes())
                self.assertEqual(candidate['onepole_stable.h'],(historical/'onepole_stable.h').read_bytes())

    def test_near_maps_helpers_caller_state_and_types_reject_atomically(self):
        original=self.maps['onepole-scalar-stereo'];description=json.loads(original['description.json'])
        mutations=[('rnbo_source.h',b'number onepole_tilde_01_b1;',b'double onepole_tilde_01_b1;'),
                   ('rnbo_source.h',b'this->onepole_tilde_01_freqInHz = v;',b'this->onepole_tilde_01_freqInHz = v + 1;'),
                   ('rnbo_source.h',b'onepole_tilde_01_b1 = 0;',b'onepole_tilde_01_b1 = 1;'),
                   ('common/RNBO_Types.h',b'using MillisecondTime = double;',b'using MillisecondTime = float;'),
                   ('patch_config.h',b'RATE 44100',b'RATE 48000')]
        for name,old,new in mutations:
            files=dict(original);self.assertIn(old,files[name]);files[name]=files[name].replace(old,new,1);before=copy.deepcopy(files)
            with self.subTest(name=name,old=old),self.assertRaises(ValueError):transform(files,description,copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=HELPER)
            self.assertEqual(files,before)
        for kind in ('extra','missing','mutable','repeat','helper'):
            files=dict(original);helper=HELPER
            if kind=='extra':files['foreign.h']=b'unknown'
            elif kind=='missing':del files['patch_config.h']
            elif kind=='mutable':files['rnbo_source.h']=bytearray(files['rnbo_source.h'])
            elif kind=='helper':helper=HELPER.replace(b'0.99999f',b'0.99998f')
            else:files=transform(files,description,copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=HELPER)[0]
            before=copy.deepcopy(files)
            with self.subTest(kind=kind),self.assertRaises(ValueError):transform(files,description,copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=helper)
            self.assertEqual(files,before)

    def test_every_option_and_description_mismatch_rejects(self):
        files=self.maps['onepole-scalar-stereo'];description=json.loads(files['description.json'])
        values={'rnbo_version':'1.4.5','apply_fixes':1,'role':'main','sample_rate':44100.,'block_frames':128,
                'audio_inputs':0,'audio_outputs':1,'numerical_profile':'float32-audio-v2','filter_delay_max_ms':40,
                'float32_delay_storage':True,'required_host_services':['data'],'other_optimizations':['onepole-clamp']}
        for key,value in values.items():
            options=copy.deepcopy(OPTIONS);options[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):transform(files,description,options,code_mask=cpp_code_mask,helper=HELPER)
        changed=copy.deepcopy(description);changed['parameters'][0]['initialValue']=17
        with self.assertRaises(ValueError):transform(files,changed,copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=HELPER)
        for mask in (lambda _:None,lambda _:'',lambda value:' '*len(value)):
            with self.assertRaises(ValueError):transform(files,description,copy.deepcopy(OPTIONS),code_mask=mask,helper=HELPER)

    def test_actual_public_pipeline_metadata_defaults_and_all_three_maps(self):
        for context,raw in self.exports.items():
            with tempfile.TemporaryDirectory()as name:
                output=Path(name)/'public';manifest=prepare(raw,output,'rnbos3patch','fx',stable_onepole=True)
                provenance,_,snapshot=verify_prepared(output)
                files=self.maps[context];expected,record=transform(files,json.loads(files['description.json']),copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=HELPER)
                for n,data in expected.items():self.assertEqual((output/n).read_bytes(),data)
                self.assertEqual(len(snapshot['prepared_files_sha256']),43)
                self.assertTrue(manifest['stable_onepole']);self.assertEqual(manifest['numerical_profile'],'float32-strict')
                self.assertEqual(manifest['stable_onepole_contract']['correctness_profile'],'stable-onepole-v1')
                self.assertFalse(manifest['stable_onepole_contract']['baseline_bit_identity_claimed'])
                self.assertEqual(manifest['stable_onepole_contract']['scheduler_time'],'unchanged binary64')
                self.assertFalse(manifest['stable_onepole_contract']['floating_environment_equivalence_claimed'])
                self.assertEqual(provenance['compiler_helpers_sha256']['onepole_stable.h'],HELPER_SHA256)
                self.assertEqual(provenance['adaptations'][-1]['name'],record['name'])
                self.assertEqual((output/'originals/rnbo_source.h').read_bytes(),(raw/'rnbo_source.h').read_bytes())
            self.assertNotIn('stable_onepole',json.loads((self.references[context]/'manifest.json').read_text()))

    def test_unknown_export_files_and_linked_aliases_reject_without_output(self):
        raw=self.exports['onepole-scalar-stereo']
        with tempfile.TemporaryDirectory()as name:
            root=Path(name)
            for kind in ('extra','symlink'):
                copydir=root/kind;shutil.copytree(raw,copydir)
                if kind=='extra':(copydir/'foreign.txt').write_text('unknown')
                else:(copydir/'alias.h').symlink_to(copydir/'rnbo_source.h')
                out=root/(kind+'-out')
                with self.subTest(kind=kind),self.assertRaises(ExportError):prepare(copydir,out,'rnbos3patch','fx',stable_onepole=True)
                self.assertFalse(out.exists())

    def test_actual_generated_header_type_and_abi_contract(self):
        compiler=shutil.which('c++')
        if not compiler:self.skipTest('C++ compiler required')
        files=self.maps['onepole-signal-cutoff'];candidate,_=transform(files,json.loads(files['description.json']),copy.deepcopy(OPTIONS),code_mask=cpp_code_mask,helper=HELPER)
        with tempfile.TemporaryDirectory()as name:
            root=Path(name)
            for n,data in candidate.items():p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            source=root/'probe.cpp';source.write_text('#include "rnbo_s3_module.h"\n#define RNBO_FIXEDLISTSIZE 16\n#include "rnbo_source.h"\n')
            for flags,good in [(['-DRNBO_USE_FLOAT32'],True),([],False),(['-DRNBO_USE_FLOAT32','-ffast-math'],False)]:
                result=subprocess.run([compiler,'-std=c++17','-fsyntax-only','-I'+str(ROOT/'module-sdk/include'),'-I'+str(root),'-I'+str(root/'common'),*flags,str(source)],capture_output=True,text=True)
                with self.subTest(flags=flags):self.assertEqual(result.returncode==0,good,result.stderr)


if __name__=='__main__':unittest.main()
