# SPDX-License-Identifier: MIT
"""Tests use fresh licensed RNBO output; no generated fixture is committed."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

WORK=Path(__file__).resolve().parent
ROOT=WORK.parents[1]
sys.path.insert(0,str(WORK))
from prepare import ExportError,NUMERICAL_PROFILES,cpp_code_mask,prepare
from build import verify_prepared
from bounded_line_ramps import CONTRACT,GUARDED_SOURCE,OPTIONS,UNGUARDED_SOURCE,sha,transform


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
    def test_invalid_boolean_requires_no_export_and_creates_no_output(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for index,value in enumerate((0,1,None,'false',[],{})):
                output=root/str(index)
                with self.subTest(value=value),self.assertRaisesRegex(ExportError,'must be a boolean'):
                    prepare(root/'missing',output,'rnbos3patch','main',bounded_line_ramps=value)
                self.assertFalse(output.exists())

    def test_mutually_exclusive_flags_reject_before_reading_an_export(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);output=root/'output'
            with self.assertRaises(ExportError):
                prepare(root/'missing',output,'rnbos3patch','main',exact_audio_delay44100=True,bounded_line_ramps=True)
            self.assertFalse(output.exists())

    def test_invalid_maps_and_option_types_are_not_coerced(self):
        for files in (None,[],{}, {'rnbo_source.h':bytearray(b'mutable')},{1:b'invalid key'}):
            before=copy.deepcopy(files)
            with self.assertRaises(ValueError):transform(files,{},copy.deepcopy(OPTIONS),code_mask=cpp_code_mask)
            self.assertEqual(files,before)
        for options in (None,[],{},dict(OPTIONS,sample_rate=44100.),dict(OPTIONS,apply_fixes=1),dict(OPTIONS,filter_delay_max_ms=True)):
            before=copy.deepcopy(options)
            with self.assertRaises(ValueError):transform({}, {},options,code_mask=cpp_code_mask)
            self.assertEqual(options,before)

    def test_inline_compile_contract_checks_types_abi_capacity_and_modes(self):
        compiler=shutil.which('c++')
        if not compiler:self.skipTest('C++ compiler not installed')
        with tempfile.TemporaryDirectory() as name:
            source=Path(name)/'types.cpp'
            variants=[('float','double','unsigned long long','unsigned int',1,0,16,[],True),
                      ('int','double','unsigned long long','unsigned int',1,0,16,[],False),
                      ('double','double','unsigned long long','unsigned int',1,0,16,[],False),
                      ('float','float','unsigned long long','unsigned int',1,0,16,[],False),
                      ('float','double','long long','unsigned int',1,0,16,[],False),
                      ('float','double','unsigned int','unsigned int',1,0,16,[],False),
                      ('float','double','unsigned long long','unsigned long long',1,0,16,[],False),
                      ('float','double','unsigned long long','unsigned int',1,1,16,[],False),
                      ('float','double','unsigned long long','unsigned int',2,0,16,[],False),
                      ('float','double','unsigned long long','unsigned int',None,0,16,[],False),
                      ('float','double','unsigned long long','unsigned int',1,0,0,[],False),
                      ('float','double','unsigned long long','unsigned int',1,0,8,[],False),
                      ('float','double','unsigned long long','unsigned int',1,0,16,['-ffast-math'],False),
                      ('float','double','unsigned long long','unsigned int',1,0,16,['-ffinite-math-only'],False)]
            for audio,clock,u64,u32,major,minor,capacity,flags,good in variants:
                macros=('#define RNBO_S3_ABI_MAJOR '+str(major)+'u\n#define RNBO_S3_ABI_MINOR '+str(minor)+'u\n')if major is not None else ''
                source.write_text(macros+'#define RNBO_FIXEDLISTSIZE '+str(capacity)+'\nnamespace RNBO {using number='+audio+';using Sample='+audio+';using SampleValue='+audio+';using MillisecondTime='+clock+';using UInt64='+u64+';using UInt32='+u32+';}\n'+CONTRACT)
                result=subprocess.run([compiler,'-std=c++17','-fsyntax-only',*flags,str(source)],capture_output=True,text=True)
                with self.subTest(audio=audio,clock=clock,u64=u64,u32=u32,abi=(major,minor),capacity=capacity,flags=flags):self.assertEqual(result.returncode==0,good,result.stderr)

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.directory=Path(cls.temp.name)
        override=os.environ.get('RNBO_S3_TEST_BOUNDED_LINE_EXPORT')
        if override:
            cls.export=Path(override)
            if not (cls.export/'rnbo_source.h').is_file():raise unittest.SkipTest('Authorized scalar export not available')
        else:
            cls.export=cls.directory/'fresh-export'
            try:
                result=subprocess.run(['node',str(ROOT/'host/export/export.mjs'),str(ROOT/'tests/fixtures/objects/wave2/line-timing.rnbopat'),'--out',str(cls.export)],capture_output=True,text=True)
            except FileNotFoundError:raise unittest.SkipTest('Node and authorized RNBO1.4.4 are needed for licensed export tests')
            if result.returncode and 'Set --rnbo-dir or RNBO_DIR' in result.stderr:raise unittest.SkipTest('Authorized RNBO1.4.4 is not installed')
            if result.returncode:raise AssertionError(result.stderr)
        cls.reference=cls.directory/'reference'
        prepare(cls.export,cls.reference,'rnbos3patch','main')
        cls.original={n:(cls.reference/n).read_bytes() for n in verify_prepared(cls.reference)[2]['prepared_files_sha256']}


    def test_all_reviewed_exact_metadata_epochs_and_unknown_generator_mutations(self):
        import bounded_line_ramps as module
        from prepare import canonical
        original=dict(self.original)
        for stamp,expected in [
            ('de348978139adf64571ccde382b2be79fa80027e5557b0340dda80cf9428b079',module.FILE_MAP),
            ('56fb9edda0184c282b64f9ba66ab70817866cb981fa5aee4b3050e804bac3065',module.GENEXPR_FILE_MAP),
            ('4af4ee869ca842cd9ffbd0421367b46f491767c203971d3c83fff4e89fd3ce5e',module.INTEGER_UI_FILE_MAP)]:
            generator=json.loads(original['generator.json']);generator['patcher_adapter_sha256']=stamp
            self.files=dict(original);self.files['generator.json']=(json.dumps(generator,indent=2)+'\n').encode()
            baseline=dict(self.files);before=copy.deepcopy(self.files)
            _,record=self.apply()
            self.assertEqual(record['whole_input_map_sha256'],expected)
            self.assertEqual(sha(canonical({n:sha(v)for n,v in sorted(self.files.items())})),expected)
            self.assertEqual(self.files,before)
            for key,value in [('patcher_adapter_sha256','f'*64),('adapter_sha256','0'*64),
                              ('generated_sha256','0'*64),('voices',2),('class_name','other'),('unknown',False)]:
                changed=dict(generator);changed[key]=value
                self.files=dict(baseline);self.files['generator.json']=(json.dumps(changed,indent=2)+'\n').encode()
                with self.subTest(epoch=stamp,key=key):self.reject_atomic()
        self.files=original

    def setUp(self):
        self.files=dict(self.original);self.description=json.loads(self.files['description.json']);self.options=copy.deepcopy(OPTIONS)

    def apply(self,mask=cpp_code_mask):return transform(self.files,self.description,self.options,code_mask=mask)

    def reject_atomic(self,mask=cpp_code_mask):
        before=copy.deepcopy((self.files,self.description,self.options))
        with self.assertRaises(ValueError):self.apply(mask)
        self.assertEqual(before,(self.files,self.description,self.options))

    def test_pure_map_preserves_all_other_bytes_and_historical_inverse(self):
        before=copy.deepcopy((self.files,self.description,self.options))
        with mock.patch('builtins.open',side_effect=AssertionError('Pure map must not perform I/O')):updated,record=self.apply()
        self.assertEqual(before,(self.files,self.description,self.options))
        self.assertEqual(len(updated),42);self.assertEqual(sha(updated['rnbo_source.h']),GUARDED_SOURCE)
        self.assertEqual(sha(updated['rnbo_source.h'].replace(CONTRACT.encode(),b'')),UNGUARDED_SOURCE)
        self.assertEqual({k:v for k,v in updated.items() if k!='rnbo_source.h'},{k:v for k,v in self.original.items() if k!='rnbo_source.h'})
        historical=ROOT/'build/research/line-timing-fix-candidates-v1/prepared/integer-relative'
        if historical.is_dir():
            for name,data in updated.items():
                if name=='generator.json':assert_generator_epoch_only(self,data,(historical/name).read_bytes())
                else:self.assertEqual(data.replace(CONTRACT.encode(),b'') if name=='rnbo_source.h' else data,(historical/name).read_bytes())
        self.assertTrue(record['bounded_single_active_segment']);self.assertTrue(record['experimental'])
        self.assertTrue(record['source_inverse_byte_identity']);self.assertTrue(record['original_duration_conversion_unchanged'])
        self.assertFalse(record['baseline_bit_identity_claimed'] or record['target_cpu_gain_claimed'])
        self.assertFalse(record['hardware_executed'] or record['floating_environment_equivalence_claimed'] or record['nan_payload_equivalence_claimed'])

    def test_unknown_partial_repeated_files_masks_and_descriptions_reject(self):
        for mode in ('extra','missing','mutable','repeat'):
            self.files=dict(self.original)
            if mode=='extra':self.files['foreign.h']=b'// unknown'
            elif mode=='missing':del self.files['patch_config.h']
            elif mode=='mutable':self.files['rnbo_source.h']=bytearray(self.files['rnbo_source.h'])
            else:self.files=self.apply()[0]
            with self.subTest(mode=mode):self.reject_atomic()
        self.files=dict(self.original);self.description['parameters'][1]['initialValue']=17;self.reject_atomic()
        self.description=json.loads(self.files['description.json'])
        for mask in (lambda _:None,lambda _:'',lambda value:' '*len(value)):self.reject_atomic(mask)

    def test_all_option_mismatches_reject_without_mutation(self):
        variants={'rnbo_version':['1.4.5'],'apply_fixes':[False,1],'role':['fx'],'sample_rate':[48000,44100.,True],
                  'block_frames':[128,256.],'audio_inputs':[2],'audio_outputs':[1],'numerical_profile':['float32-audio-v2'],
                  'filter_delay_max_ms':[0,True,40,41,float('nan')],'float32_delay_storage':[True,0],
                  'required_host_services':[['resource']],'other_optimizations':[['exact-audio-delay44100']]}
        for key,values in variants.items():
            for value in values:
                self.options=copy.deepcopy(OPTIONS);self.options[key]=value
                with self.subTest(key=key,value=value):self.reject_atomic()
        self.options=copy.deepcopy(OPTIONS);self.options['unknown']=False;self.reject_atomic()
        self.options=copy.deepcopy(OPTIONS);del self.options['filter_delay_max_ms'];self.reject_atomic()

    def test_source_route_clock_state_sr_duration_and_resource_guards(self):
        variants=[('rnbo_source.h',b'this->pack_01_in2_set(v);',b'this->pack_01_in1_number_set(v);'),
                  ('rnbo_source.h',b'this->pack_01_in1_number_set(v);',b'if (v) this->pack_01_in1_number_set(v);'),
                  ('rnbo_source.h',b'this->sr = sampleRate;',b'number &alias=this->sr;alias=sampleRate;'),
                  ('rnbo_source.h',b'this->linetilde_01_currentValue = v[0];',b'number &alias=this->linetilde_01_currentValue;alias=v[0];'),
                  ('rnbo_source.h',b'return ms * this->sr * 0.001;',b'return (number)ms * this->sr * 0.001f;'),
                  ('rnbo_source.h',b'894770446',b'894770447'),
                  ('rnbo_source.h',b'this->sampsToMs((SampleIndex)(256)) + this->_currentTime',b'this->sampsToMs((SampleIndex)(128)) + this->_currentTime'),
                  ('rnbo_source.h',b'return this->audioProcessSampleCount + this->sampleOffsetIntoNextAudioBuffer;',b'return (number)this->audioProcessSampleCount;'),
                  ('common/RNBO_Types.h',b'using MillisecondTime = double;',b'using MillisecondTime = float;'),
                  ('patch_config.h',b'RATE 44100',b'RATE 48000')]
        for name,old,new in variants:
            self.files=dict(self.original);self.assertTrue(old in self.files[name],f'missing mutation anchor {old!r}')
            self.files[name]=self.files[name].replace(old,new,1)
            with self.subTest(file=name,mutation=old):self.reject_atomic()

    def test_actual_generated_header_compile_contract(self):
        compiler=shutil.which('c++')
        if not compiler:self.skipTest('C++ compiler not installed')
        updated,_=self.apply()
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for relative,data in updated.items():
                path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            source=root/'probe.cpp';source.write_text('#include "rnbo_s3_module.h"\n#include "rnbo_source.h"\n')
            base=[compiler,'-std=c++17','-fsyntax-only','-I'+str(root/'common'),'-I'+str(root),'-I'+str(ROOT/'module-sdk/include'),'-DRNBO_FIXEDLISTSIZE=16',str(source)]
            for flags,good in [(['-DRNBO_USE_FLOAT32'],True),([],False),(['-DRNBO_USE_FLOAT32','-ffast-math'],False),(['-DRNBO_USE_FLOAT32','-ffinite-math-only'],False)]:
                result=subprocess.run(base+flags,capture_output=True,text=True)
                with self.subTest(flags=flags):self.assertEqual(result.returncode==0,good,result.stderr)
            source.write_text('#include "rnbo_s3_module.h"\n#undef RNBO_S3_ABI_MINOR\n#define RNBO_S3_ABI_MINOR 1u\n#include "rnbo_source.h"\n')
            future=subprocess.run(base+['-DRNBO_USE_FLOAT32'],capture_output=True,text=True)
            self.assertNotEqual(future.returncode,0);self.assertIn('ABI revision1.0',future.stderr)
            source.write_text('#include "rnbo_s3_module.h"\n#undef RNBO_FIXEDLISTSIZE\n#define RNBO_FIXEDLISTSIZE 0\n#include "rnbo_source.h"\n')
            dynamic_list=subprocess.run(base+['-DRNBO_USE_FLOAT32'],capture_output=True,text=True)
            self.assertNotEqual(dynamic_list.returncode,0);self.assertIn('capacity16',dynamic_list.stderr)

    def test_real_fresh_export_pipeline_metadata_and_default(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name)/'public'
            manifest=prepare(self.export,output,'rnbos3patch','main',bounded_line_ramps=True)
            provenance,_,snapshot=verify_prepared(output);updated,_=self.apply()
            for relative,data in updated.items():self.assertEqual((output/relative).read_bytes(),data)
            self.assertEqual(len(snapshot['prepared_files_sha256']),42);self.assertEqual(manifest['numerical_profile'],'float32-strict')
            self.assertTrue(manifest['bounded_line_ramps']);self.assertEqual(manifest['bounded_line_ramps_contract']['version'],1)
            self.assertEqual(manifest['bounded_line_ramps_contract']['rounding'],'nearest-even')
            self.assertTrue(manifest['bounded_line_ramps_contract']['experimental'])
            self.assertFalse(manifest['bounded_line_ramps_contract']['baseline_bit_identity_claimed'])
            self.assertFalse(manifest['bounded_line_ramps_contract']['target_cpu_gain_claimed'])
            self.assertEqual(manifest['bounded_line_ramps_contract']['event_time'],'original binary64')
            self.assertFalse(manifest['bounded_line_ramps_contract']['floating_environment_equivalence_claimed'])
            self.assertEqual(provenance['compiler_helpers_sha256']['bounded_line_ramps.py'],sha((WORK/'bounded_line_ramps.py').read_bytes()))
            self.assertEqual(provenance['adaptations'][-1]['name'],'rnbo-1.4.4-bounded-line-ramps-v1')
            self.assertEqual((output/'originals/rnbo_source.h').read_bytes(),(self.export/'rnbo_source.h').read_bytes())
        self.assertNotIn('bounded_line_ramps',json.loads((self.reference/'manifest.json').read_text()))

    def test_pipeline_option_compositions_reject_without_output(self):
        variants=[{'apply_fixes':False},{'apply_fixes':1},{'midi_output_policy':'discard'},
                  {'filter_delay_max_ms':0},{'filter_delay_max_ms':True},{'filter_delay_max_ms':39},{'filter_delay_max_ms':float('nan')},
                  {'float32_delay_storage':True},{'omit_unused_mtof_table':True},{'hoist_cycle_conversions':True},
                  {'compact_average_history':True},{'float32_pink_output':True},{'correct_finite_wrap':True},{'exact_audio_delay44100':True},{'hoist_filter_durations':True},{'hoist_train_reciprocal':True}]
        variants += [{'numerical_profile':profile} for profile in NUMERICAL_PROFILES if profile!='float32-strict']
        with tempfile.TemporaryDirectory() as name:
            for index,extra in enumerate(variants):
                output=Path(name)/str(index);options={'bounded_line_ramps':True}|extra
                with self.subTest(options=extra),self.assertRaises(ExportError):prepare(self.export,output,'rnbos3patch','main',**options)
                self.assertFalse(output.exists())
            with self.assertRaises(ExportError):prepare(self.export,Path(name)/'fx','rnbos3patch','fx',bounded_line_ramps=True)

    def test_pipeline_raw_mutation_and_unknown_files_failure_atomic(self):
        variants=[('source','rnbo_source.h',b'this->sr = sampleRate;',b'this->sr = sampleRate + 1;'),
                  ('clock','rnbo_source.h',b'894770446',b'894770447'),
                  ('time-type','common/RNBO_Types.h',b'using MillisecondTime = double;',b'using MillisecondTime = float;')]
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for label,relative,old,new in variants:
                raw=root/label;shutil.copytree(self.export,raw);data=(raw/relative).read_bytes();self.assertTrue(old in data)
                (raw/relative).write_bytes(data.replace(old,new,1));(raw/'generator.json').unlink(missing_ok=True)
                output=root/(label+'-output')
                with self.subTest(label=label),self.assertRaises(ExportError):prepare(raw,output,'rnbos3patch','main',bounded_line_ramps=True)
                self.assertFalse(output.exists())
            for label in ('extra-root','extra-runtime','extra-text','missing-source','symlink'):
                raw=root/label;shutil.copytree(self.export,raw);output=root/(label+'-output')
                if label=='extra-root':(raw/'foreign.h').write_bytes(b'unknown')
                elif label=='extra-runtime':(raw/'common/foreign.h').write_bytes(b'unknown')
                elif label=='extra-text':(raw/'foreign.txt').write_bytes(b'unknown')
                elif label=='missing-source':(raw/'source.rnbopat').unlink();(raw/'generator.json').unlink()
                else:(raw/'alias.h').symlink_to(raw/'rnbo_source.h')
                with self.subTest(label=label),self.assertRaises(ExportError):prepare(raw,output,'rnbos3patch','main',bounded_line_ramps=True)
                self.assertFalse(output.exists())

    def test_public_cli_fresh_positive_boolean_and_composition_failures(self):
        base=[sys.executable,str(WORK/'prepare.py'),'--export',str(self.export),'--class-name','rnbos3patch','--role','main']
        with tempfile.TemporaryDirectory() as name:
            output=Path(name)/'public-cli';result=subprocess.run(base+['--out',str(output),'--bounded-line-ramps'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(sha((output/'rnbo_source.h').read_bytes()),GUARDED_SOURCE)
            for index,extra in enumerate((['false'],['--exact-audio-delay44100'],['--no-runtime-fixes'])):
                output=Path(name)/str(index);result=subprocess.run(base+['--out',str(output),'--bounded-line-ramps',*extra],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0);self.assertFalse(output.exists())
            result=subprocess.run(base+['--out',str(Path(name)/'coerce'),'--bounded-line-ramps=0'],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse((Path(name)/'coerce').exists())

if __name__=='__main__':unittest.main()
