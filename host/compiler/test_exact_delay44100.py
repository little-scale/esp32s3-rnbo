# SPDX-License-Identifier: MIT
import copy,hashlib,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
WORK=Path(__file__).resolve().parent;ROOT=WORK.parents[1]
sys.path.insert(0,str(ROOT/'host/compiler'))
from prepare import cpp_code_mask,prepare,ExportError
from build import verify_prepared
from exact_delay44100 import transform,OPTIONS,CONTRACT,TESTED_SOURCE,GUARDED_SOURCE,HELPER,sha

class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export=Path(os.environ.get('RNBO_S3_TEST_EXACT_DELAY_EXPORT',ROOT/'build/object-qualification/audio-v2-qualified/exports/filters-signal'))
        if not (cls.export/'rnbo_source.h').is_file():raise unittest.SkipTest('Generate the authorized local filters-signal export first')
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.reference=Path(cls.temp.name)/'reference'
        prepare(cls.export,cls.reference,'rnbos3patch','main',filter_delay_max_ms=40)
        snapshot=verify_prepared(cls.reference)[2]
        cls.original={n:(cls.reference/n).read_bytes() for n in snapshot['prepared_files_sha256']}
        cls.helper=(WORK/'exact_delay44100.h').read_bytes()
    def setUp(self):self.files=dict(self.original);self.description=json.loads(self.files['description.json']);self.options=copy.deepcopy(OPTIONS)
    def apply(self,**kw):return transform(self.files,self.description,self.options,kw.get('helper',self.helper),code_mask=kw.get('mask',cpp_code_mask))
    def reject_atomic(self,**kw):
        before=(copy.deepcopy(self.files),copy.deepcopy(self.description),copy.deepcopy(self.options))
        with self.assertRaises((ValueError,TypeError)):self.apply(**kw)
        self.assertEqual((self.files,self.description,self.options),before)
    def test_pure_map_inverse_and_only_proven_algorithm_changes(self):
        before=copy.deepcopy((self.files,self.description,self.options))
        with mock.patch('builtins.open',side_effect=AssertionError('transformation performs I/O')):
            updated,proof=self.apply()
        self.assertEqual((self.files,self.description,self.options),before)
        self.assertEqual(sha(updated['private_exact_delay44100.h']),HELPER)
        self.assertEqual(sha(updated['rnbo_source.h'].replace(CONTRACT.encode(),b'')),TESTED_SOURCE)
        private=ROOT/'build/research/exact-delay44100/prepared/candidate/rnbo_source.h'
        if private.is_file():
            self.assertEqual(updated['rnbo_source.h'].replace(CONTRACT.encode(),b''),private.read_bytes())
        self.assertEqual({n:v for n,v in updated.items() if n not in ('rnbo_source.h','private_exact_delay44100.h')},
                         {n:v for n,v in self.files.items() if n!='rnbo_source.h'})
        self.assertEqual(proof['audio_call_substitutions'],2);self.assertEqual(len(proof['owned_float64_rings']),4)
        self.assertTrue(proof['source_inverse_byte_identity']);self.assertTrue(proof['production_available'])
        self.assertEqual(sha(updated['rnbo_source.h']),GUARDED_SOURCE)
        self.assertFalse(proof['hardware_executed'] or proof['floating_environment_equivalence_claimed'] or proof['nan_payload_equivalence_claimed'])
    def test_reject_unsupported_option_modes_types_and_compositions(self):
        variants={'rnbo_version':['1.4.3'],'apply_fixes':[False,1],'role':['fx'],'sample_rate':[48000,44100.,True],
            'block_frames':[128,256.],'audio_inputs':[2],'audio_outputs':[1],'numerical_profile':['float32-audio-v2'],
            'filter_delay_max_ms':[None,True,39,41,float('nan')],'float32_delay_storage':[True,0],
            'required_host_services':[['data']], 'other_optimizations':[['hoist-cycle'],['float32-delays']]}
        for key,values in variants.items():
            for value in values:
                self.options=copy.deepcopy(OPTIONS);self.options[key]=value
                with self.subTest(key=key,value=value):self.reject_atomic()
        self.options=copy.deepcopy(OPTIONS);self.options['unknown']=False;self.reject_atomic()
        self.options=copy.deepcopy(OPTIONS);del self.options['filter_delay_max_ms'];self.reject_atomic()
    def test_unknown_partial_repeated_maps_and_helpers_reject_atomically(self):
        for action in ('extra','missing','collision','repeat','partial','mutable'):
            self.files=dict(self.original)
            if action=='extra':self.files['foreign.h']=b'not included'
            elif action=='missing':del self.files['common/RNBO_Array.h']
            elif action=='collision':self.files['private_exact_delay44100.h']=self.helper
            elif action=='repeat':self.files=self.apply()[0]
            elif action=='partial':self.files['rnbo_source.h']=self.files['rnbo_source.h'].replace(b'this->mstosamps((__delayTime',b'private_delay44100_capped40((__delayTime',1)
            else:self.files['rnbo_source.h']=bytearray(self.files['rnbo_source.h'])
            with self.subTest(action=action):self.reject_atomic()
        self.files=dict(self.original);self.reject_atomic(helper=self.helper+b'\n')
    def test_source_sr_alias_return_ring_and_types_mutations_fail_closed(self):
        changes=[('rnbo_source.h',b'this->sr = sampleRate;',b'this->sr = sampleRate + 1;'),
            ('rnbo_source.h',b'this->sr = sampleRate;',b'number &alias = this->sr; alias = sampleRate;'),
            ('rnbo_source.h',b'return ms * this->sr * 0.001;',b'return (number)ms * this->sr * 0.001f;'),
            ('rnbo_source.h',b'number mstosamps(MillisecondTime ms)',b'MillisecondTime mstosamps(MillisecondTime ms)'),
            ('rnbo_source.h',b'__delayTime > 40.0',b'__delayTime > 39.0'),
            ('rnbo_source.h',b'for (i = 0; i < 256; i++)',b'for (i = 1; i < 256; i++)'),
            ('rnbo_source.h',b'new Float64Buffer',b'new Float32Buffer'),
            ('common/RNBO_Types.h',b'using MillisecondTime = double;',b'using MillisecondTime = float;'),
            ('patch_config.h',b'RATE 44100',b'RATE 48000')]
        for name,old,new in changes:
            self.files=dict(self.original);self.assertTrue(old in self.files[name],f'missing mutation anchor {old!r}');self.files[name]=self.files[name].replace(old,new,1)
            with self.subTest(name=name,mutation=old):self.reject_atomic()
        self.files=dict(self.original);self.description['parameters'][0]['maximum']=100;self.reject_atomic()
    def test_invalid_masks_reject_without_mutation(self):
        for mask in (lambda _:None,lambda _:'',lambda s:' '*len(s)):
            self.reject_atomic(mask=mask)
    def test_actual_header_float32_accepts_float64_and_fastmath_reject(self):
        compiler=shutil.which('c++');self.assertTrue(compiler)
        updated,_=self.apply()
        with tempfile.TemporaryDirectory() as name:
            d=Path(name)
            for n,v in updated.items():p=d/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v)
            p=d/'probe.cpp';p.write_text('#include "rnbo_source.h"\n')
            base=[compiler,'-std=c++17','-fsyntax-only','-I'+str(d/'common'),'-I'+str(d),str(p)]
            good=subprocess.run(base+['-DRNBO_USE_FLOAT32'],capture_output=True,text=True)
            self.assertEqual(good.returncode,0,good.stderr)
            for flags,message in [([], 'RNBO binary32 samples'),(['-DRNBO_USE_FLOAT32','-ffast-math'],'strict floating-point'),
                                  (['-DRNBO_USE_FLOAT32','-ffinite-math-only'],'strict floating-point')]:
                bad=subprocess.run(base+flags,capture_output=True,text=True);self.assertNotEqual(bad.returncode,0);self.assertIn(message,bad.stderr)
    def test_inline_contract_rejects_integer_or_float_scheduler_and_integer_audio(self):
        compiler=shutil.which('c++');self.assertTrue(compiler)
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)/'types.cpp'
            for audio,time,good in [('float','double',True),('int','double',False),('float','float',False),('float','long long',False)]:
                p.write_text('namespace RNBO {using number='+audio+';using Sample='+audio+';using SampleValue='+audio+';using MillisecondTime='+time+';}\n'+CONTRACT)
                ran=subprocess.run([compiler,'-std=c++17','-fsyntax-only',str(p)],capture_output=True,text=True)
                self.assertEqual(ran.returncode==0,good,ran.stderr)

    def test_fresh_pipeline_matches_guarded_prototype_and_preserves_default(self):
        prototype=ROOT/'build/research/exact-delay44100-admission-v1/prepared'
        with tempfile.TemporaryDirectory()as name:
            output=Path(name)/'public'
            manifest=prepare(self.export,output,'rnbos3patch','main',filter_delay_max_ms=40,exact_audio_delay44100=True)
            provenance=json.loads((output/'provenance.json').read_text());updated,record=self.apply()
            self.assertTrue(manifest['exact_audio_delay44100']);self.assertEqual(manifest['numerical_profile'],'float32-strict')
            contract=manifest['exact_audio_delay44100_contract'];self.assertEqual(contract['version'],1)
            self.assertEqual(contract['rounding'],'nearest-even');self.assertEqual(contract['fallback'],'original-capped-binary64')
            self.assertEqual(contract['scheduler_time'],'binary64');self.assertFalse(contract['floating_environment_equivalence_claimed'])
            self.assertEqual(len(provenance['prepared_files_sha256']),43)
            for key,value in updated.items():self.assertEqual((output/key).read_bytes(),value)
            if prototype.is_dir():
                for key in updated:self.assertEqual((output/key).read_bytes(),(prototype/key).read_bytes())
            self.assertEqual((output/'patch_config.h').read_bytes(),self.original['patch_config.h'])
            self.assertEqual((output/'originals/rnbo_source.h').read_bytes(),(self.export/'rnbo_source.h').read_bytes())
            self.assertEqual(provenance['adaptations'][-1]['name'],'rnbo-1.4.4-exact-audio-delay44100-v1')
            for helper in ('exact_delay44100.py','exact_delay44100.h'):
                self.assertEqual(provenance['compiler_helpers_sha256'][helper],sha((WORK/helper).read_bytes()))
            verify_prepared(output)
        self.assertNotIn('exact_audio_delay44100',json.loads((self.reference/'manifest.json').read_text()))
        self.assertNotIn('private_exact_delay44100.h',self.original)

    def test_pipeline_rejects_compositions_bad_types_and_modes_before_output(self):
        variants=[{'apply_fixes':False},{'apply_fixes':1},{'midi_output_policy':'discard'},
            {'filter_delay_max_ms':None},{'filter_delay_max_ms':True},{'filter_delay_max_ms':39},
            {'filter_delay_max_ms':float('nan')},{'float32_delay_storage':True},{'omit_unused_mtof_table':True},
            {'hoist_cycle_conversions':True},{'compact_average_history':True},{'float32_pink_output':True},
            {'correct_finite_wrap':True}]
        variants += [{'numerical_profile':p}for p in ('float32-cycle-v1','float32-cycle-v2','float32-audio-v1','float32-audio-v2','float32-scalar-powers-v1')]
        variants += [{'exact_audio_delay44100':v}for v in (0,1,None,'yes',[],{})]
        with tempfile.TemporaryDirectory()as name:
            for index,extra in enumerate(variants):
                output=Path(name)/str(index)
                options={'filter_delay_max_ms':40,'exact_audio_delay44100':True}|extra
                with self.subTest(options=extra):
                    with self.assertRaises(ExportError):prepare(self.export,output,'rnbos3patch','main',**options)
                    self.assertFalse(output.exists())
            output=Path(name)/'fx'
            with self.assertRaises(ExportError):prepare(self.export,output,'rnbos3patch','fx',filter_delay_max_ms=40,exact_audio_delay44100=True)
            self.assertFalse(output.exists())

    def test_full_pipeline_raw_source_runtime_ownership_and_unknown_files_fail_atomically(self):
        changes=[('rnbo_source.h',b'this->sr = sampleRate;',b'this->sr = sampleRate + 1;'),
            ('rnbo_source.h',b'this->sr = sampleRate;',b'number &alias = this->sr; alias = sampleRate;'),
            ('rnbo_source.h',b'return ms * this->sr * 0.001;',b'return (number)ms * this->sr * 0.001f;'),
            ('rnbo_source.h',b'new Float64Buffer',b'new Float32Buffer'),
            ('rnbo_source.h',b'        true,\n',b'        false,\n'),
            ('common/RNBO_Types.h',b'using MillisecondTime = double;',b'using MillisecondTime = float;'),
            ('common/RNBO_Version.h',b'1.4.4',b'1.4.5')]
        with tempfile.TemporaryDirectory()as name:
            root=Path(name)
            for index,(path,old,new)in enumerate(changes):
                raw=root/('raw'+str(index));shutil.copytree(self.export,raw)
                source=raw/path;before=source.read_bytes();self.assertTrue(old in before,f'missing mutation anchor {old!r}')
                source.write_bytes(before.replace(old,new,1))
                # Bypass only the unrelated optional generator identity; the
                # actual closed source/runtime/file-map checks must still fail.
                (raw/'generator.json').unlink();output=root/('out'+str(index))
                with self.subTest(path=path,old=old):
                    with self.assertRaises(ExportError):prepare(raw,output,'rnbos3patch','main',filter_delay_max_ms=40,exact_audio_delay44100=True)
                    self.assertFalse(output.exists())
            for kind in ('extra-root','extra-runtime','extra-text','missing-source','linked'):
                raw=root/kind;shutil.copytree(self.export,raw);output=root/(kind+'-out')
                if kind=='extra-root':(raw/'foreign.h').write_bytes(b'unknown')
                elif kind=='extra-runtime':(raw/'common/foreign.h').write_bytes(b'unknown')
                elif kind=='extra-text':(raw/'foreign.txt').write_text('unread data')
                elif kind=='missing-source':(raw/'source.rnbopat').unlink();(raw/'generator.json').unlink()
                else:(raw/'linked.h').symlink_to(raw/'rnbo_source.h')
                with self.subTest(kind=kind):
                    with self.assertRaises(ExportError):prepare(raw,output,'rnbos3patch','main',filter_delay_max_ms=40,exact_audio_delay44100=True)
                    self.assertFalse(output.exists())

    def test_cli_wiring_and_explicit_boolean_switch(self):
        with tempfile.TemporaryDirectory()as name:
            root=Path(name)
            base=[sys.executable,str(WORK/'prepare.py'),'--export',str(self.export),'--class-name','rnbos3patch','--role','main','--filter-delay-max-ms','40']
            good=root/'cli';ran=subprocess.run(base+['--exact-audio-delay44100','--out',str(good)],capture_output=True,text=True)
            self.assertEqual(ran.returncode,0,ran.stderr);manifest=json.loads((good/'manifest.json').read_text());self.assertTrue(manifest['exact_audio_delay44100'])
            self.assertEqual(sha((good/'rnbo_source.h').read_bytes()),GUARDED_SOURCE)
            for index,args in enumerate((['--exact-audio-delay44100','false'],['--exact-audio-delay44100=0'],['--exact-audio-delay44100','--no-runtime-fixes'])):
                output=root/str(index);bad=subprocess.run(base+args+['--out',str(output)],capture_output=True,text=True)
                self.assertNotEqual(bad.returncode,0);self.assertFalse(output.exists())


class BasicInputTests(unittest.TestCase):
    def test_boolean_precheck_needs_no_export_and_never_creates_output(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for index,value in enumerate((None,0,1,'false',[],{})):
                output=root/str(index)
                with self.subTest(value=value),self.assertRaisesRegex(ExportError,'must be a boolean'):
                    prepare(root/'missing-export',output,'rnbos3patch','main',exact_audio_delay44100=value)
                self.assertFalse(output.exists())

    def test_invalid_maps_never_coerce_mutable_or_missing_source_inputs(self):
        for files in (None,[],{},{'rnbo_source.h':bytearray(b'not immutable')},{1:b'bad key'}):
            before=copy.deepcopy(files)
            with self.assertRaises(ValueError):transform(files,{},copy.deepcopy(OPTIONS),b'unknown',code_mask=cpp_code_mask)
            self.assertEqual(files,before)

if __name__=='__main__':unittest.main()
