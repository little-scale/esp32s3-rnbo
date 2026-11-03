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
from hoist_filter_durations import CONTRACT,GUARDED_SOURCE,OPTIONS,UNGUARDED_SOURCE,sha,transform

class InputTests(unittest.TestCase):
    def test_invalid_boolean_requires_no_export_and_creates_no_output(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for index,value in enumerate((0,1,None,'false',[],{})):
                output=root/str(index)
                with self.subTest(value=value),self.assertRaisesRegex(ExportError,'must be a boolean'):
                    prepare(root/'missing',output,'rnbos3patch','main',hoist_filter_durations=value)
                self.assertFalse(output.exists())

    def test_mutually_exclusive_flags_reject_before_reading_an_export(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);output=root/'output'
            with self.assertRaises(ExportError):
                prepare(root/'missing',output,'rnbos3patch','main',filter_delay_max_ms=40,
                        exact_audio_delay44100=True,hoist_filter_durations=True)
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

    def test_inline_compile_contract_checks_actual_types_and_modes(self):
        compiler=shutil.which('c++')
        if not compiler:self.skipTest('C++ compiler not installed')
        with tempfile.TemporaryDirectory() as name:
            source=Path(name)/'types.cpp'
            for audio,clock,flags,good in [('float','double',[],True),('int','double',[],False),('double','double',[],False),('float','float',[],False),('float','long long',[],False),('float','double',['-ffast-math'],False),('float','double',['-ffinite-math-only'],False)]:
                source.write_text('namespace RNBO {using number='+audio+';using Sample='+audio+';using SampleValue='+audio+';using MillisecondTime='+clock+';}\n'+CONTRACT)
                result=subprocess.run([compiler,'-std=c++17','-fsyntax-only',*flags,str(source)],capture_output=True,text=True)
                with self.subTest(audio=audio,clock=clock,flags=flags):self.assertEqual(result.returncode==0,good,result.stderr)

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.directory=Path(cls.temp.name)
        override=os.environ.get('RNBO_S3_TEST_FILTER_HOIST_EXPORT')
        if override:
            cls.export=Path(override)
            if not (cls.export/'rnbo_source.h').is_file():raise unittest.SkipTest('Authorized scalar export not available')
        else:
            cls.export=cls.directory/'fresh-export'
            try:
                result=subprocess.run(['node',str(ROOT/'host/export/export.mjs'),str(ROOT/'tests/fixtures/objects/filters-scalar.rnbopat'),'--out',str(cls.export)],capture_output=True,text=True)
            except FileNotFoundError:raise unittest.SkipTest('Node and authorized RNBO1.4.4 are needed for licensed export tests')
            if result.returncode and 'Set --rnbo-dir or RNBO_DIR' in result.stderr:raise unittest.SkipTest('Authorized RNBO1.4.4 is not installed')
            if result.returncode:raise AssertionError(result.stderr)
        cls.reference=cls.directory/'reference'
        prepare(cls.export,cls.reference,'rnbos3patch','main',filter_delay_max_ms=40)
        cls.original={n:(cls.reference/n).read_bytes() for n in verify_prepared(cls.reference)[2]['prepared_files_sha256']}

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
        historical=ROOT/'build/research/filter-duration-current-runtime-v1/prepared/candidate'
        if historical.is_dir():
            for name,data in updated.items():self.assertEqual(data,(historical/name).read_bytes())
        self.assertEqual([x['statement_count'] for x in record['moved_statements']],[3,2])
        self.assertTrue(record['source_inverse_byte_identity']);self.assertTrue(record['state_dependent_ring_clamps_stay_per_sample'])
        self.assertTrue(record['double_expression_and_float32_return_unchanged']);self.assertTrue(record['production_available'])
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
                  'filter_delay_max_ms':[None,True,39,41,float('nan')],'float32_delay_storage':[True,0],
                  'required_host_services':[['resource']],'other_optimizations':[['exact-audio-delay44100']]}
        for key,values in variants.items():
            for value in values:
                self.options=copy.deepcopy(OPTIONS);self.options[key]=value
                with self.subTest(key=key,value=value):self.reject_atomic()
        self.options=copy.deepcopy(OPTIONS);self.options['unknown']=False;self.reject_atomic()
        self.options=copy.deepcopy(OPTIONS);del self.options['filter_delay_max_ms'];self.reject_atomic()

    def test_source_caller_scalar_sr_clock_ownership_and_ring_guards(self):
        variants=[('rnbo_source.h',b'    number delayTime,',b'    const Sample *delayTime,'),
                  ('rnbo_source.h',b'this->comb_tilde_01_delayTime,',b'this->comb_tilde_01_delayTime + 1,'),
                  ('rnbo_source.h',b'this->sr = sampleRate;',b'number &alias=this->sr;alias=sampleRate;'),
                  ('rnbo_source.h',b'this->sr = sampleRate;',b'this->sr = sampleRate + 1;'),
                  ('rnbo_source.h',b'return ms * this->sr * 0.001;',b'return (number)ms * this->sr * 0.001f;'),
                  ('rnbo_source.h',b'for (i = 0; i < 256; i++)',b'for (i = 0; i < 128; i++)'),
                  ('rnbo_source.h',b'(__delayTime < 0 ? 0 : __delayTime)',b'(__delayTime < 1 ? 1 : __delayTime)'),
                  ('rnbo_source.h',b'new Float64Buffer(',b'new Float32Buffer('),
                  ('rnbo_source.h',b'        true,\n',b'        false,\n'),
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
            source=root/'probe.cpp';source.write_text('#include "rnbo_source.h"\n')
            base=[compiler,'-std=c++17','-fsyntax-only','-I'+str(root/'common'),'-I'+str(root),str(source)]
            for flags,good in [(['-DRNBO_USE_FLOAT32'],True),([],False),(['-DRNBO_USE_FLOAT32','-ffast-math'],False),(['-DRNBO_USE_FLOAT32','-ffinite-math-only'],False)]:
                result=subprocess.run(base+flags,capture_output=True,text=True)
                with self.subTest(flags=flags):self.assertEqual(result.returncode==0,good,result.stderr)

    def test_real_fresh_export_pipeline_metadata_and_default(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name)/'public'
            manifest=prepare(self.export,output,'rnbos3patch','main',filter_delay_max_ms=40,hoist_filter_durations=True)
            provenance,_,snapshot=verify_prepared(output);updated,_=self.apply()
            for relative,data in updated.items():self.assertEqual((output/relative).read_bytes(),data)
            self.assertEqual(len(snapshot['prepared_files_sha256']),42);self.assertEqual(manifest['numerical_profile'],'float32-strict')
            self.assertTrue(manifest['hoist_filter_durations']);self.assertEqual(manifest['hoist_filter_durations_contract']['version'],1)
            self.assertEqual(manifest['hoist_filter_durations_contract']['rounding'],'nearest-even')
            self.assertEqual(manifest['hoist_filter_durations_contract']['ring_storage'],'original internal Float64')
            self.assertFalse(manifest['hoist_filter_durations_contract']['floating_environment_equivalence_claimed'])
            self.assertEqual(provenance['compiler_helpers_sha256']['hoist_filter_durations.py'],sha((WORK/'hoist_filter_durations.py').read_bytes()))
            self.assertEqual(provenance['adaptations'][-1]['name'],'rnbo-1.4.4-hoist-filter-durations-v1')
            self.assertEqual((output/'originals/rnbo_source.h').read_bytes(),(self.export/'rnbo_source.h').read_bytes())
        self.assertNotIn('hoist_filter_durations',json.loads((self.reference/'manifest.json').read_text()))

    def test_pipeline_option_compositions_reject_without_output(self):
        variants=[{'apply_fixes':False},{'apply_fixes':1},{'midi_output_policy':'discard'},
                  {'filter_delay_max_ms':None},{'filter_delay_max_ms':True},{'filter_delay_max_ms':39},{'filter_delay_max_ms':float('nan')},
                  {'float32_delay_storage':True},{'omit_unused_mtof_table':True},{'hoist_cycle_conversions':True},
                  {'compact_average_history':True},{'float32_pink_output':True},{'correct_finite_wrap':True},{'exact_audio_delay44100':True}]
        variants += [{'numerical_profile':profile} for profile in NUMERICAL_PROFILES if profile!='float32-strict']
        with tempfile.TemporaryDirectory() as name:
            for index,extra in enumerate(variants):
                output=Path(name)/str(index);options={'filter_delay_max_ms':40,'hoist_filter_durations':True}|extra
                with self.subTest(options=extra),self.assertRaises(ExportError):prepare(self.export,output,'rnbos3patch','main',**options)
                self.assertFalse(output.exists())
            with self.assertRaises(ExportError):prepare(self.export,Path(name)/'fx','rnbos3patch','fx',filter_delay_max_ms=40,hoist_filter_durations=True)

    def test_pipeline_raw_mutation_and_unknown_files_failure_atomic(self):
        variants=[('source','rnbo_source.h',b'this->sr = sampleRate;',b'this->sr = sampleRate + 1;'),
                  ('ownership','rnbo_source.h',b'        true,\n',b'        false,\n'),
                  ('clock','common/RNBO_Types.h',b'using MillisecondTime = double;',b'using MillisecondTime = float;')]
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for label,relative,old,new in variants:
                raw=root/label;shutil.copytree(self.export,raw);data=(raw/relative).read_bytes();self.assertTrue(old in data)
                (raw/relative).write_bytes(data.replace(old,new,1));(raw/'generator.json').unlink(missing_ok=True)
                output=root/(label+'-output')
                with self.subTest(label=label),self.assertRaises(ExportError):prepare(raw,output,'rnbos3patch','main',filter_delay_max_ms=40,hoist_filter_durations=True)
                self.assertFalse(output.exists())
            for label in ('extra-root','extra-runtime','extra-text','missing-source','symlink'):
                raw=root/label;shutil.copytree(self.export,raw);output=root/(label+'-output')
                if label=='extra-root':(raw/'foreign.h').write_bytes(b'unknown')
                elif label=='extra-runtime':(raw/'common/foreign.h').write_bytes(b'unknown')
                elif label=='extra-text':(raw/'foreign.txt').write_bytes(b'unknown')
                elif label=='missing-source':(raw/'source.rnbopat').unlink();(raw/'generator.json').unlink()
                else:(raw/'alias.h').symlink_to(raw/'rnbo_source.h')
                with self.subTest(label=label),self.assertRaises(ExportError):prepare(raw,output,'rnbos3patch','main',filter_delay_max_ms=40,hoist_filter_durations=True)
                self.assertFalse(output.exists())

    def test_public_cli_fresh_positive_boolean_and_composition_failures(self):
        base=[sys.executable,str(WORK/'prepare.py'),'--export',str(self.export),'--class-name','rnbos3patch','--role','main','--filter-delay-max-ms','40']
        with tempfile.TemporaryDirectory() as name:
            output=Path(name)/'public-cli';result=subprocess.run(base+['--out',str(output),'--hoist-filter-durations'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(sha((output/'rnbo_source.h').read_bytes()),GUARDED_SOURCE)
            for index,extra in enumerate((['false'],['--exact-audio-delay44100'],['--no-runtime-fixes'])):
                output=Path(name)/str(index);result=subprocess.run(base+['--out',str(output),'--hoist-filter-durations',*extra],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0);self.assertFalse(output.exists())
            result=subprocess.run(base+['--out',str(Path(name)/'coerce'),'--hoist-filter-durations=0'],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse((Path(name)/'coerce').exists())

if __name__=='__main__':unittest.main()
