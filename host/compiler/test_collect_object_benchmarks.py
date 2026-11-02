# SPDX-License-Identifier: MIT
"""Reject incomplete or internally inconsistent target evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import struct
import unittest
from collect_object_benchmarks import collect,fields,sha

class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.build=self.root/'build';self.run=self.root/'run'
        self.build.mkdir();self.run.mkdir()
        fixture={'id':'unit','family':'unit','role':'main','warmup_blocks':4,'seed':1,'cases':[{'id':'default'}],
                 'comparison_tolerance':{'maximum_absolute_error':0.001,'maximum_pcm_lsb_error':1,'relative_rms_level_difference':0.01}}
        report={'benchmark':{'fixture':fixture,'rounds':3,'blocks':2,'timing_exclude_blocks':0},
                'modules':{p:{'artifact_sha256':c*64,'report':{'prepared_export':{'manifest':{'role':'main','audio_inputs':0,'audio_outputs':2,'numerical_profile':'float32-strict' if p=='strict' else 'float32-audio-v1'}}}} for p,c in (('strict','a'),('optimized','b'))}}
        self.report=report
        (self.build/'build-report.json').write_text(json.dumps(report))
        self.lines=['RNBO_OBJECT_BENCHMARK CASE fixture=unit case=default samples=3072 max_abs=0 rms_error=0 relative_rms=0 pcm_different=0 max_pcm_lsb=0',
            'RNBO_OBJECT_BENCHMARK CASE_PROFILE fixture=unit case=default profile=strict timed_blocks=6 process_us=120 peak_us=25',
            'RNBO_OBJECT_BENCHMARK CASE_PROFILE fixture=unit case=default profile=optimized timed_blocks=6 process_us=60 peak_us=15',
            'RNBO_OBJECT_BENCHMARK PASS fixture=unit firmware_elf_sha256='+('c'*64)+' strict_module_sha256='+('a'*64)+' optimized_module_sha256='+('b'*64)+
            ' host_heap_allocations=0 host_heap_frees=0 local_late_allocations=0 psram_before=123 psram_after=123 internal_before=42 internal_after=42 images=4 finalized_images=4 cases=1 rounds=3 blocks_per_pass=2 timing_exclude=0 warmup=4 seed=1 compared_samples=3072']
        self.seal()
    def seal(self):
        (self.build/'build-report.json').write_text(json.dumps(self.report))
        log=self.run/'test-serial.log';log.write_text('\n'.join(self.lines)+'\n')
        (self.run/'hardware-test.json').write_text(json.dumps({'result':'passed','restoration':{'result':'restored'},
            'test_build_report_sha256':sha(self.build/'build-report.json'),'serial_log_sha256':sha(log),
            'pass_line':self.lines[-1],'test_elf_sha256':'c'*64}))
    def fx(self):
        fixture=self.report['benchmark']['fixture'];fixture['role']='fx'
        fixture['stimulus']={'kind':'midi-stereo-v1','base':60,'depth':12,'rate':.5,'pilot_frequency':371,'pilot_amplitude':.125}
        fixture['cases'][0]['stimulus']={}
        for module in self.report['modules'].values():
            module['report']['prepared_export']['manifest'].update(role='fx',audio_inputs=2)
        self.report['benchmark'].update(catalog_path='/frozen/catalog-fx.json',catalog_sha256='d'*64,patch_sha256='e'*64,
            stimuli=[{'kind':1,'settings':dict(fixture['stimulus']),'base':60,'depth':12,'rate':.5,'pilot_frequency':371,'pilot_amplitude':.125,'excitation':0,'level':0}])
        self.report['source_files_sha256']={'object-benchmark/main/stimulus.c':'f'*64,'object-benchmark/main/stimulus.h':'1'*64}
        self.lines.insert(0,'RNBO_OBJECT_BENCHMARK INPUT fixture=unit case=default input_sha256='+('9'*64)+' input_bytes=4096 layout=float32_stereo_interleaved_le stimulus_kind=1')
        self.lines[-1]+=' input_cases=1 input_rechecks=9 pilot_sample_checks=3072'
        self.seal()
    def test_fx_input_and_stimulus_provenance(self):
        self.fx();result=collect(self.build,self.run)
        self.assertEqual(result['role'],'fx')
        self.assertEqual(result['cases'][0]['input']['input_sha256'],'9'*64)
        self.assertEqual(result['cases'][0]['input']['declared_settings']['base'],60)
        self.assertEqual(result['stimulus_provenance']['generator_source_sha256']['object-benchmark/main/stimulus.c'],'f'*64)
        self.assertIn('excluded',result['scope'])
    def average(self):
        self.fx();plan=self.report['benchmark'];fixture=plan['fixture'];fixture['family']='average'
        fixture['stimulus']={'kind':'impulse-step-v1'};fixture['semantic']={'kind':'average','default_window':16,'maximum_absolute_error':2e-6}
        fixture['verification']={'kind':'average-window-v1','parameter_id':'window','default_window':16,'maximum_window':64,'maximum_absolute_error':2e-6}
        fixture['cases'][0]['parameters']={};fixture['cases'][0]['events']=[]
        plan['stimuli']=[{'kind':4,'settings':{'kind':'impulse-step-v1'},'base':0.,'depth':0.,'rate':0.,'pilot_frequency':0.,'pilot_amplitude':0.,'excitation':0.,'level':0.}]
        plan['verifications']=[{'kind':'average-window-v1','window':16,'initial_available':16,'maximum_absolute_error':2e-6,'default_window':16,'maximum_window':64,'parameter_id':'window','model':'fresh-float64-window-sum','rounding':'once-float32','gate':'cache-error-plus-maximum-cache-rounding-error'}]
        plan['arena_bytes']=1048576
        for module in self.report['modules'].values():
            module['inspection']={'loaded_bytes_upper_bound':65536};module['report']['prepared_export']['manifest']['parameter_count']=1
        budget={'workspace_bytes':12288,'oracle_cache_bytes':4096,'arena_bytes':2097152,'opaque_context_upper_bound_bytes':2097152,'loaded_images_upper_bound_bytes':131072,'loader_heap_alignment_reserve_bytes':524288,'physical_psram_bytes':8388608}
        budget['required_upper_bound_bytes']=sum(v for k,v in budget.items() if k!='physical_psram_bytes');plan['psram_budget']=budget
        self.report['source_files_sha256'].update({'object-benchmark/main/average_oracle.c':'2'*64,'object-benchmark/main/average_oracle.h':'3'*64})
        self.lines[0]=self.lines[0].replace('stimulus_kind=1','stimulus_kind=4')
        self.lines[-1]=self.lines[-1].replace('pilot_sample_checks=3072','pilot_sample_checks=0')+' oracle_cases=1 oracle_rechecks=9 semantic_sample_checks=6144'
        self.lines.insert(1,'RNBO_OBJECT_BENCHMARK ORACLE fixture=unit case=default oracle_sha256='+('8'*64)+' oracle_bytes=4096 layout=float32_stereo_interleaved_le oracle_kind=average-window-v1 window=16 initial_available=16 max_abs_tolerance=2e-6 max_cache_rounding_error=0 model=fresh-float64-window-sum rounding=once-float32')
        for profile in ('strict','optimized'):
            self.lines.insert(-1,'RNBO_OBJECT_BENCHMARK CASE_SEMANTIC fixture=unit case=default profile='+profile+' semantic_kind=average-window-v1 samples=3072 max_abs=0 max_model_error_bound=0 max_abs_tolerance=2e-6 oracle_sha256='+('8'*64))
        self.seal()
    def test_average_oracle_provenance_and_independent_coverage(self):
        self.average();result=collect(self.build,self.run)
        self.assertEqual(result['cases'][0]['input']['oracle']['oracle_sha256'],'8'*64)
        self.assertEqual(result['cases'][0]['semantic_comparison']['strict']['samples'],3072)
        self.assertEqual(result['pass']['pilot_sample_checks'],0)
        self.assertIn('oracle_source_sha256',result['stimulus_provenance'])
    def test_average_missing_oracle_record_rejected(self):
        self.average();self.lines.pop(1);self.seal()
        with self.assertRaisesRegex(ValueError,'ORACLE evidence'):collect(self.build,self.run)
    def test_average_wrong_oracle_history_rejected(self):
        self.average();self.lines[1]=self.lines[1].replace('initial_available=16','initial_available=0');self.seal()
        with self.assertRaisesRegex(ValueError,'history/window'):collect(self.build,self.run)
    def test_average_wrong_oracle_sha_link_rejected(self):
        self.average();self.lines[-2]=self.lines[-2].replace('8'*64,'7'*64);self.seal()
        with self.assertRaisesRegex(ValueError,'oracle identity'):collect(self.build,self.run)
    def test_average_missing_semantic_profile_rejected(self):
        self.average();self.lines.pop(-2);self.seal()
        with self.assertRaisesRegex(ValueError,'semantic measurements'):collect(self.build,self.run)
    def test_average_wrong_semantic_counter_rejected(self):
        self.average();self.lines[-1]=self.lines[-1].replace('semantic_sample_checks=6144','semantic_sample_checks=3072');self.seal()
        with self.assertRaisesRegex(ValueError,'coverage'):collect(self.build,self.run)
    def test_average_strict_cancellation_failure_cannot_be_hidden_by_pair_equality(self):
        self.average();index=next(i for i,line in enumerate(self.lines) if 'CASE_SEMANTIC' in line and 'profile=strict' in line)
        self.lines[index]=self.lines[index].replace('max_abs=0','max_abs=3e-6').replace('max_model_error_bound=0','max_model_error_bound=3e-6');self.seal()
        with self.assertRaisesRegex(ValueError,'unchanged model limit'):collect(self.build,self.run)
    def test_average_rounding_error_participates_in_conservative_gate(self):
        self.average();self.lines[1]=self.lines[1].replace('max_cache_rounding_error=0','max_cache_rounding_error=2e-8')
        for i,line in enumerate(self.lines):
            if 'CASE_SEMANTIC' in line:self.lines[i]=line.replace('max_abs=0','max_abs=1.99e-6').replace('max_model_error_bound=0','max_model_error_bound=2.01e-6')
        self.seal()
        with self.assertRaisesRegex(ValueError,'unchanged model limit'):collect(self.build,self.run)
    def test_average_missing_oracle_cache_budget_rejected(self):
        self.average();self.report['benchmark']['psram_budget']['oracle_cache_bytes']=0;self.seal()
        with self.assertRaisesRegex(ValueError,'PSRAM budget'):collect(self.build,self.run)
    def test_average_window_events_rejected(self):
        self.average();self.report['benchmark']['fixture']['cases'][0]['events']=[{'block':1,'id':'window','value':1}];self.seal()
        with self.assertRaisesRegex(ValueError,'events'):collect(self.build,self.run)
    def test_average_bad_oracle_sha_rejected(self):
        self.average();self.lines[1]=self.lines[1].replace('8'*64,'bad');self.seal()
        with self.assertRaisesRegex(ValueError,'oracle SHA'):collect(self.build,self.run)
    def test_average_wrong_oracle_recheck_count_rejected(self):
        self.average();self.lines[-1]=self.lines[-1].replace('oracle_rechecks=9','oracle_rechecks=8');self.seal()
        with self.assertRaisesRegex(ValueError,'coverage'):collect(self.build,self.run)
    def test_average_oracle_precision_cannot_be_relabelled(self):
        self.average();self.lines[1]=self.lines[1].replace('rounding=once-float32','rounding=float64');self.seal()
        with self.assertRaisesRegex(ValueError,'precision/model'):collect(self.build,self.run)
    def test_average_missing_oracle_source_identity_rejected(self):
        self.average();del self.report['source_files_sha256']['object-benchmark/main/average_oracle.c'];self.seal()
        with self.assertRaisesRegex(ValueError,'oracle source'):collect(self.build,self.run)
    def test_average_compiled_window_mismatch_rejected(self):
        self.average();self.report['benchmark']['verifications'][0]['window']=64;self.seal()
        with self.assertRaisesRegex(ValueError,'Compiled verification'):collect(self.build,self.run)
    def test_average_module_parameter_count_rejected(self):
        self.average();self.report['modules']['strict']['report']['prepared_export']['manifest']['parameter_count']=2;self.seal()
        with self.assertRaisesRegex(ValueError,'parameter count'):collect(self.build,self.run)
    def test_average_rejects_new_grid_base_and_override(self):
        self.average();baseline=copy.deepcopy(self.report);lines=list(self.lines)
        for override in (False,True):
            with self.subTest(override=override):
                self.report=copy.deepcopy(baseline);self.lines=list(lines);f=self.report['benchmark']['fixture']
                if override:f['cases'][0]['stimulus']={'kind':'nonlinear-grid-v1'}
                else:f['stimulus']={'kind':'nonlinear-grid-v1'}
                self.seal()
                with self.assertRaisesRegex(ValueError,'unmodeled input'):collect(self.build,self.run)
    def optional_reference(self):
        profiles={'strict':'float32-audio-v2','optimized':'private-cycle-invariants-v1'}
        for key,value in profiles.items():self.report['modules'][key]['report']['prepared_export']['manifest']['numerical_profile']=value
        self.report['benchmark']['numerical_profiles']=profiles
        self.lines.insert(0,'RNBO_OBJECT_BENCHMARK NUMERICAL_PROFILES fixture=unit reference=float32-audio-v2 candidate=private-cycle-invariants-v1')
        self.seal()
    def test_explicit_optional_reference_preserves_actual_profile(self):
        self.optional_reference();result=collect(self.build,self.run)
        self.assertEqual(result['cases'][0]['profiles']['strict']['numerical_profile'],'float32-audio-v2')
    def test_missing_profile_record_is_rejected(self):
        self.optional_reference();self.lines.pop(0);self.seal()
        with self.assertRaisesRegex(ValueError,'numerical profile record'):collect(self.build,self.run)
    def test_reference_cannot_be_relabelled_strict(self):
        self.optional_reference();self.lines[0]=self.lines[0].replace('reference=float32-audio-v2','reference=float32-strict');self.seal()
        with self.assertRaisesRegex(ValueError,'numerical profile record'):collect(self.build,self.run)
    def test_duplicate_profile_record_is_rejected(self):
        self.optional_reference();self.lines.insert(0,self.lines[0]);self.seal()
        with self.assertRaisesRegex(ValueError,'numerical profile record'):collect(self.build,self.run)
    def test_manifest_profile_must_match_build_plan(self):
        self.optional_reference();self.report['modules']['optimized']['report']['prepared_export']['manifest']['numerical_profile']='another';self.seal()
        with self.assertRaisesRegex(ValueError,'Build numerical profiles'):collect(self.build,self.run)
    def test_legacy_non_strict_reference_is_rejected(self):
        self.report['modules']['strict']['report']['prepared_export']['manifest']['numerical_profile']='float32-audio-v2';self.seal()
        with self.assertRaisesRegex(ValueError,'Legacy reference'):collect(self.build,self.run)
    def test_missing_fx_input_rejected(self):
        self.fx();self.lines.pop(0);self.seal()
        with self.assertRaisesRegex(ValueError,'Incomplete FX INPUT'):collect(self.build,self.run)
    def test_duplicate_fx_input_rejected(self):
        self.fx();self.lines.insert(0,self.lines[0]);self.seal()
        with self.assertRaisesRegex(ValueError,'Incomplete FX INPUT'):collect(self.build,self.run)
    def test_unknown_fx_case_rejected(self):
        self.fx();self.lines[0]=self.lines[0].replace('case=default','case=unknown');self.seal()
        with self.assertRaisesRegex(ValueError,'INPUT case'):collect(self.build,self.run)
    def test_malformed_input_sha_rejected(self):
        self.fx();self.lines[0]=self.lines[0].replace('9'*64,'not-a-sha');self.seal()
        with self.assertRaisesRegex(ValueError,'input SHA256'):collect(self.build,self.run)
    def test_partial_input_bytes_rejected(self):
        self.fx();self.lines[0]=self.lines[0].replace('input_bytes=4096','input_bytes=4092');self.seal()
        with self.assertRaisesRegex(ValueError,'byte coverage'):collect(self.build,self.run)
    def test_wrong_input_layout_rejected(self):
        self.fx();self.lines[0]=self.lines[0].replace('float32_stereo_interleaved_le','planar');self.seal()
        with self.assertRaisesRegex(ValueError,'layout'):collect(self.build,self.run)
    def test_wrong_input_kind_rejected(self):
        self.fx();self.lines[0]=self.lines[0].replace('stimulus_kind=1','stimulus_kind=2');self.seal()
        with self.assertRaisesRegex(ValueError,'stimulus kind'):collect(self.build,self.run)
    def test_missing_pilot_checks_rejected(self):
        self.fx();self.lines[-1]=self.lines[-1].replace('pilot_sample_checks=3072','pilot_sample_checks=3071');self.seal()
        with self.assertRaisesRegex(ValueError,'pilot coverage'):collect(self.build,self.run)
    def test_insufficient_input_rechecks_rejected(self):
        self.fx();self.lines[-1]=self.lines[-1].replace('input_rechecks=9','input_rechecks=8');self.seal()
        with self.assertRaisesRegex(ValueError,'pilot coverage'):collect(self.build,self.run)
    def test_compiled_settings_cannot_diverge_from_catalog(self):
        self.fx();self.report['benchmark']['stimuli'][0]['base']=61;self.seal()
        with self.assertRaisesRegex(ValueError,'Compiled stimulus differs'):collect(self.build,self.run)
    def test_stimulus_kind_override_rejected(self):
        self.fx();self.report['benchmark']['fixture']['cases'][0]['stimulus']={'kind':'reson-stereo-v1'};self.seal()
        with self.assertRaisesRegex(ValueError,'stimulus fields'):collect(self.build,self.run)
    def test_missing_generator_identity_rejected(self):
        self.fx();del self.report['source_files_sha256']['object-benchmark/main/stimulus.c'];self.seal()
        with self.assertRaisesRegex(ValueError,'generator source'):collect(self.build,self.run)
    def test_module_role_must_match_fixture(self):
        self.report['modules']['strict']['report']['prepared_export']['manifest']['role']='fx';self.seal()
        with self.assertRaisesRegex(ValueError,'role/channel'):collect(self.build,self.run)
    def test_main_cannot_claim_external_input(self):
        self.lines.insert(0,'RNBO_OBJECT_BENCHMARK INPUT fixture=unit case=default input_sha256='+('9'*64)+' input_bytes=4096 layout=float32_stereo_interleaved_le stimulus_kind=1');self.seal()
        with self.assertRaisesRegex(ValueError,'Main fixture cannot'):collect(self.build,self.run)
    def test_main_cannot_claim_pilot_counter(self):
        self.lines[-1]+=' input_cases=0 input_rechecks=0 pilot_sample_checks=1';self.seal()
        with self.assertRaisesRegex(ValueError,'unexpected FX'):collect(self.build,self.run)

    def test_observed_case_cost_and_identity(self):
        result=collect(self.build,self.run)
        self.assertEqual(result['cases'][0]['observed_speed_ratio'],2)
        self.assertEqual(result['cases'][0]['observed_process_reduction_percent'],50)
        self.assertFalse(result['identical_artifact_control'])
    def test_stale_log_cannot_receive_sealed_report(self):
        with (self.run/'test-serial.log').open('a') as f:f.write('changed\n')
        with self.assertRaisesRegex(ValueError,'Serial log changed'):collect(self.build,self.run)
    def test_declared_pass_does_not_override_failed_case(self):
        self.lines[0]=self.lines[0].replace('max_abs=0','max_abs=0.2');self.seal()
        with self.assertRaisesRegex(ValueError,'output limits'):collect(self.build,self.run)
    def test_missing_profile_rejected_even_with_pass(self):
        self.lines.pop(1);self.seal()
        with self.assertRaisesRegex(ValueError,'Incomplete case'):collect(self.build,self.run)
    def test_nonfinite_and_duplicate_fields_rejected(self):
        for value in ('process_us=nan','process_us=1 process_us=2'):
            with self.assertRaises(ValueError):fields('TEST '+value,'TEST ')
    def test_changed_build_report_rejected(self):
        with (self.build/'build-report.json').open('a') as f:f.write(' ')
        with self.assertRaisesRegex(ValueError,'Build report changed'):collect(self.build,self.run)

class Wave2ObservationTests(unittest.TestCase):
    """Synthetic logs exercise admission; they never stand for hardware runs."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.build=self.root/'build';self.run=self.root/'run'
        self.build.mkdir();self.run.mkdir();self.fixture()

    def fixture(self,kind='biquad'):
        root=Path(__file__).resolve().parents[2]
        catalog=json.loads((root/'tests/fixtures/objects/wave2/catalog.json').read_text())
        name='biquad-response' if kind=='biquad' else 'nonlinear-domains'
        f=copy.deepcopy(next(f for f in catalog['fixtures'] if f['id']==name));self.kind=kind
        verification='biquad-response-v1' if kind=='biquad' else 'nonlinear-chain-v1';limit=3e-6 if kind=='biquad' else 2e-6
        f['verification']={'kind':verification,'maximum_absolute_error':limit}
        if kind=='biquad':
            schema=[('a0',0,0,1,.5),('b2',1,0,.8,.2),('a1',2,-1,1,.25),('a2',3,-1,1,.125),('b1',4,-.95,.95,-.4)]
            schema_hash='5ee44b4347d4f1d490c0ecb696d9fca49b9ece2d69635b837422dbf98ad9ea30'
            source_hash='3bf669da7e420a82f5c2370a4449c9ec791cdbef655b227fbb2057ab295015b5'
        else:
            schema=[('exponent',0,.25,4,2)]
            schema_hash='754c55e5f56bd5c2731847a19ed276e1ad4045849e3bcc2909acd4ec76b73ef1'
            source_hash='b246e2357fc3829af9d44eec0efc1aa69a82bd9157be093663005ea0eb1ea28b'
        projection=[dict(paramId=i,index=n,minimum=lo,maximum=hi,initialValue=v,exponent=1,steps=0) for i,n,lo,hi,v in schema]
        by_id={p['paramId']:p for p in projection};patch_hash=sha(root/'tests/fixtures/objects/wave2'/f['patch'])
        model='fresh-float64-difference-equation' if kind=='biquad' else 'float64-tanh-wrap-clip-pow'
        plan={'fixture':f,'rounds':3,'blocks':512,'timing_exclude_blocks':32,'arena_bytes':4096,
              'catalog_path':'/synthetic/catalog.json','catalog_sha256':'d'*64,'patch_sha256':patch_hash,
              'description_sha256':'e'*64,'parameter_schema':projection,'events':[],
              'numerical_profiles':{'strict':'float32-strict','optimized':'float32-strict'},'stimuli':[],'verifications':[]}
        manifest={'role':'fx','audio_inputs':2,'audio_outputs':2,'sample_rate':44100,'block_frames':256,
                  'numerical_profile':'float32-strict','editable_source_sha256':patch_hash,
                  'parameter_schema_sha256':schema_hash,'parameter_count':len(projection)}
        self.report={'benchmark':plan,'modules':{p:{'artifact_sha256':'a'*64,'inspection':{'loaded_bytes_upper_bound':65536},
            'report':{'prepared_export':{'manifest':copy.deepcopy(manifest),'provenance':{'raw_files_sha256':{'rnbo_source.h':source_hash}}}}}
            for p in ('strict','optimized')},'source_files_sha256':{
                'object-benchmark/main/stimulus.c':'1'*64,'object-benchmark/main/stimulus.h':'2'*64,
                'object-benchmark/main/wave2_oracle.c':'3'*64,'object-benchmark/main/wave2_oracle.h':'4'*64}}
        budget={'workspace_bytes':2101248,'oracle_cache_bytes':1048576,'arena_bytes':8192,
                'opaque_context_upper_bound_bytes':2097152,'loaded_images_upper_bound_bytes':131072,
                'loader_heap_alignment_reserve_bytes':524288,'physical_psram_bytes':8388608}
        budget['required_upper_bound_bytes']=sum(v for k,v in budget.items() if k!='physical_psram_bytes');plan['psram_budget']=budget
        self.lines=[f'RNBO_OBJECT_BENCHMARK NUMERICAL_PROFILES fixture={name} reference=float32-strict candidate=float32-strict']
        for case in f['cases']:
            cid=case['id'];oh=hashlib.sha256(cid.encode()).hexdigest()
            for identity,value in case['parameters'].items():
                rounded=struct.unpack('<f',struct.pack('<f',value))[0]
                plan['events'].append({'block':0,'index':by_id[identity]['index'],'kind':1,'value':rounded,'id':identity})
            plan['stimuli'].append({'kind':4 if kind=='biquad' else 6,'settings':dict(f['stimulus']),
                **{k:0. for k in ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')}})
            v={'kind':verification,'maximum_absolute_error':limit,'model':model,'rounding':'once-float32','gate':'cache-error-plus-maximum-cache-rounding-error'}
            if kind=='biquad':
                coefficients=dict(a0=.5,a1=.25,a2=.125,b1=-.4,b2=.2)|case['parameters'];v['coefficients']=coefficients
                gain=(coefficients['a0']+coefficients['a1']+coefficients['a2'])/(1+coefficients['b1']+coefficients['b2']);v['dc_expected']=-.125*gain
                detail=' '.join(k+'='+format(value,'.17g') for k,value in coefficients.items())
            else:v['exponent']=case['parameters'].get('exponent',2);detail='exponent='+format(v['exponent'],'.17g')
            plan['verifications'].append(v)
            self.lines.append(f'RNBO_OBJECT_BENCHMARK INPUT fixture={name} case={cid} input_sha256={"9"*64} input_bytes=1048576 layout=float32_stereo_interleaved_le stimulus_kind={4 if kind=="biquad" else 6}')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK ORACLE fixture={name} case={cid} oracle_sha256={oh} oracle_bytes=1048576 layout=float32_stereo_interleaved_le oracle_kind={verification} {detail} max_abs_tolerance={limit} max_cache_rounding_error=0 model={model} rounding=once-float32')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE fixture={name} case={cid} samples=786432 max_abs=0 rms_error=0 relative_rms=0 pcm_different=0 max_pcm_lsb=0')
            for profile in ('strict','optimized'):
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_PROFILE fixture={name} case={cid} profile={profile} timed_blocks=1440 process_us=12000 peak_us=25')
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_SEMANTIC fixture={name} case={cid} profile={profile} semantic_kind={verification} samples=786432 max_abs=0 max_model_error_bound=0 max_abs_tolerance={limit} oracle_sha256={oh}')
                if kind=='biquad':self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_DC fixture={name} case={cid} profile={profile} expected={v["dc_expected"]:.17g} max_abs=0 samples=3 mean_frames=1024 max_abs_tolerance=3e-6 oracle_sha256={oh}')
        self.lines.append(f'RNBO_OBJECT_BENCHMARK PASS fixture={name} firmware_elf_sha256={"c"*64} strict_module_sha256={"a"*64} optimized_module_sha256={"a"*64} host_heap_allocations=0 host_heap_frees=0 local_late_allocations=0 psram_before=123 psram_after=123 internal_before=42 internal_after=42 images=4 finalized_images=4 cases=3 rounds=3 blocks_per_pass=512 timing_exclude=32 warmup=4 seed=305419896 compared_samples=2359296 input_cases=3 input_rechecks=27 pilot_sample_checks=0 oracle_cases=3 oracle_rechecks=27 semantic_sample_checks=4718592 dc_sample_checks={18 if kind=="biquad" else 0}')
        self.seal()

    def seal(self):
        (self.build/'build-report.json').write_text(json.dumps(self.report));log=self.run/'test-serial.log';log.write_text('\n'.join(self.lines)+'\n')
        (self.run/'hardware-test.json').write_text(json.dumps({'result':'passed','restoration':{'result':'restored'},
            'test_build_report_sha256':sha(self.build/'build-report.json'),'serial_log_sha256':sha(log),'pass_line':self.lines[-1],'test_elf_sha256':'c'*64}))

    def change_line(self,prefix,before,after):
        index=next(i for i,line in enumerate(self.lines) if line.startswith('RNBO_OBJECT_BENCHMARK '+prefix+' '))
        self.lines[index]=self.lines[index].replace(before,after)

    def rejected(self):
        self.seal()
        with self.assertRaises(ValueError):collect(self.build,self.run)

    def test_biquad_exact_model_counts_dc_and_context(self):
        result=collect(self.build,self.run)
        self.assertTrue(result['identical_artifact_control']);self.assertEqual(result['pass']['semantic_sample_checks'],4718592)
        self.assertEqual(result['pass']['compared_samples'],2359296);self.assertEqual(result['pass']['dc_sample_checks'],18)
        slow=result['cases'][2]['input']['oracle']['verification']
        self.assertEqual(slow['coefficients']['a0'],.05)
        self.assertEqual(slow['dc_expected'],-.125*((.05+0+0)/(1-.95+0)))
        self.assertEqual(result['cases'][0]['dc_comparison']['strict']['mean_frames'],1024)
    def test_nonlinear_exact_model_domains_and_no_dc(self):
        self.fixture('nonlinear');result=collect(self.build,self.run)
        self.assertEqual(result['cases'][1]['input']['oracle']['exponent'],.25)
        self.assertEqual(result['pass']['semantic_sample_checks'],4718592)
        self.assertNotIn('dc_comparison',result['cases'][0])
    def test_matching_but_wrong_model_label_rejected(self):
        for kind in ('biquad','nonlinear'):
            with self.subTest(kind=kind):
                self.fixture(kind)
                for v in self.report['benchmark']['verifications']:v['model']='wrong-matching-model'
                self.lines=[line.replace('model=fresh-float64-difference-equation','model=wrong-matching-model').replace('model=float64-tanh-wrap-clip-pow','model=wrong-matching-model') for line in self.lines]
                self.rejected()
    def test_float32_quantized_coefficient_truth_rejected(self):
        value=struct.unpack('<f',struct.pack('<f',-.4))[0]
        self.report['benchmark']['verifications'][0]['coefficients']['b1']=value
        self.change_line('ORACLE','b1=-0.40000000000000002','b1='+format(value,'.17g'));self.rejected()
    def test_wrong_printed_coefficients_and_exponent_rejected(self):
        self.change_line('ORACLE','a0=0.5','a0=0.6');self.rejected()
        self.fixture('nonlinear');self.change_line('ORACLE','exponent=2','exponent=3');self.rejected()
    def test_wrong_case_set_or_events_rejected(self):
        for mutation in ('unknown','missing','events','bool-value'):
            with self.subTest(mutation=mutation):
                self.fixture();cases=self.report['benchmark']['fixture']['cases']
                if mutation=='unknown':cases[0]['id']='unreviewed'
                elif mutation=='missing':cases.pop()
                elif mutation=='events':cases[0]['events']=[{'block':1,'id':'a0','value':.5}]
                else:cases[1]['parameters']['a0']=True
                self.rejected()
    def test_warmup_seed_blocks_or_stimulus_changed_rejected(self):
        for mutation in ('warmup','seed','blocks','input','override'):
            with self.subTest(mutation=mutation):
                self.fixture('nonlinear');plan=self.report['benchmark'];f=plan['fixture']
                if mutation=='warmup':f['warmup_blocks']=0
                elif mutation=='seed':f['seed']=1
                elif mutation=='blocks':plan['blocks']=256
                elif mutation=='input':f['stimulus']={'kind':'mixed-tone-v1'}
                else:f['cases'][0]['stimulus']={'kind':'mixed-tone-v1'}
                self.rejected()
    def test_patch_schema_raw_source_spoof_rejected(self):
        for mutation in ('patch','schema','raw','count','audio'):
            with self.subTest(mutation=mutation):
                self.fixture();plan=self.report['benchmark']
                if mutation=='patch':plan['patch_sha256']='0'*64
                for m in self.report['modules'].values():
                    e=m['report']['prepared_export'];manifest=e['manifest']
                    if mutation=='patch':manifest['editable_source_sha256']='0'*64
                    elif mutation=='schema':manifest['parameter_schema_sha256']='0'*64
                    elif mutation=='raw':e['provenance']['raw_files_sha256']['rnbo_source.h']='0'*64
                    elif mutation=='count':manifest['parameter_count']=1
                    else:manifest['sample_rate']=48000
                self.rejected()
    def test_parameter_projection_and_event_table_rejected(self):
        for mutation in ('range','index','initial','exponent','steps','missing','value','event-kind','event-block','duplicate'):
            with self.subTest(mutation=mutation):
                self.fixture();p=self.report['benchmark']
                if mutation in ('range','index','initial','exponent','steps'):
                    field={'range':'maximum','index':'index','initial':'initialValue','exponent':'exponent','steps':'steps'}[mutation];p['parameter_schema'][0][field]=42
                elif mutation=='missing':p['events'].pop()
                elif mutation=='value':p['events'][0]['value']=.5
                elif mutation=='event-kind':p['events'][0]['kind']=2
                elif mutation=='event-block':p['events'][0]['block']=1
                else:p['events'][1]=dict(p['events'][0])
                self.rejected()
    def test_pair_or_semantic_tolerance_widening_rejected(self):
        for mutation in ('pair','pcm','relative','semantic','declaration'):
            with self.subTest(mutation=mutation):
                self.fixture();f=self.report['benchmark']['fixture']
                if mutation=='pair':f['comparison_tolerance']['maximum_absolute_error']=3e-6
                elif mutation=='pcm':f['comparison_tolerance']['maximum_pcm_lsb_error']=2
                elif mutation=='relative':f['comparison_tolerance']['relative_rms_level_difference']=.001
                elif mutation=='semantic':f['semantic']['maximum_absolute_error']=4e-6
                else:f['verification']['maximum_absolute_error']=4e-6
                self.rejected()
    def test_equal_output_does_not_hide_semantic_failure(self):
        self.change_line('CASE_SEMANTIC','max_abs=0 max_model_error_bound=0','max_abs=4e-6 max_model_error_bound=4e-6');self.rejected()
    def test_rounding_error_is_charged_within_unchanged_limit(self):
        self.change_line('ORACLE','max_cache_rounding_error=0','max_cache_rounding_error=2e-8')
        self.change_line('CASE_SEMANTIC','max_abs=0 max_model_error_bound=0','max_abs=2.99e-6 max_model_error_bound=3.01e-6');self.rejected()
    def test_oracle_hash_layout_bytes_kind_and_precision_rejected(self):
        for before,after in [('oracle_sha256=', 'oracle_sha256=bad'),('oracle_bytes=1048576','oracle_bytes=1048572'),('layout=float32_stereo_interleaved_le','layout=planar'),('oracle_kind=biquad-response-v1','oracle_kind=nonlinear-chain-v1'),('rounding=once-float32','rounding=float64')]:
            with self.subTest(before=before):
                self.fixture();self.change_line('ORACLE',before,after);self.rejected()
    def test_missing_oracle_source_or_budget_rejected(self):
        self.report['source_files_sha256'].pop('object-benchmark/main/wave2_oracle.h');self.rejected()
        self.fixture();self.report['benchmark']['psram_budget']['oracle_cache_bytes']=0;self.rejected()
    def test_semantic_kind_hash_and_counts_rejected(self):
        for before,after in [('semantic_kind=biquad-response-v1','semantic_kind=average-window-v1'),('oracle_sha256=','oracle_sha256=bad'),('samples=786432','samples=786431')]:
            with self.subTest(before=before):
                self.fixture();self.change_line('CASE_SEMANTIC',before,after);self.rejected()
        self.fixture();self.lines[-1]=self.lines[-1].replace('semantic_sample_checks=4718592','semantic_sample_checks=2359296');self.rejected()
    def test_dc_expected_samples_window_hash_limit_and_failure(self):
        for before,after in [('expected=-0.13671875','expected=0.21875'),('samples=3','samples=6'),('mean_frames=1024','mean_frames=1'),('oracle_sha256=','oracle_sha256=bad'),('max_abs_tolerance=3e-6','max_abs_tolerance=4e-6'),('max_abs=0','max_abs=4e-6')]:
            with self.subTest(before=before):
                self.fixture();self.change_line('CASE_DC',before,after);self.rejected()
    def test_dc_records_and_total_checks_required(self):
        for mutation in ('missing','duplicate','wrong-case','count','missing-hash','extra-metadata'):
            with self.subTest(mutation=mutation):
                self.fixture();i=next(i for i,l in enumerate(self.lines) if ' CASE_DC ' in l)
                if mutation=='missing':self.lines.pop(i)
                elif mutation=='duplicate':self.lines.insert(i,self.lines[i])
                elif mutation=='wrong-case':self.lines[i]=self.lines[i].replace('case=default','case=wrong')
                elif mutation=='count':self.lines[-1]=self.lines[-1].replace('dc_sample_checks=18','dc_sample_checks=9')
                elif mutation=='missing-hash':self.lines[i]=self.lines[i].partition(' oracle_sha256=')[0]
                else:self.lines[i]+=' wrong_mean_policy=final_sample'
                self.rejected()
    def test_unknown_oracle_metadata_rejected(self):
        self.change_line('ORACLE','rounding=once-float32','rounding=once-float32 initial_history=observed-output');self.rejected()
    def test_nonlinear_missing_historical_zero_dc_count_tolerated(self):
        self.fixture('nonlinear');self.lines[-1]=self.lines[-1].replace(' dc_sample_checks=0','');self.seal()
        self.assertEqual(collect(self.build,self.run)['pass']['semantic_sample_checks'],4718592)
    def test_nonlinear_cannot_claim_dc_or_repurpose_pilot(self):
        self.fixture('nonlinear');self.lines[-1]=self.lines[-1].replace('dc_sample_checks=0','dc_sample_checks=18');self.rejected()
        self.fixture('nonlinear');self.report['benchmark']['fixture'].pop('verification');self.rejected()


if __name__=='__main__':unittest.main()
