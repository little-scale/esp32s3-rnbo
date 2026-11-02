#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Admission tests for catalog-to-firmware configuration, no toolchain/device."""
import argparse
import copy
import json
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from build_object_benchmark import configuration, c_string, c_float, ExportError

class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.directory=Path(self.temporary.name)
        self.catalog={"sample_rate":44100,"block_frames":256,"fixtures":[{
            "id":"test","patch":"test.rnbopat","role":"main","blocks":512,"warmup_blocks":4,"seed":305419896,
            "cases":[{"id":"first","parameters":{"frequency":440}},
                     {"id":"boundary","parameters":{},"events":[{"block":7,"id":"frequency","form":"normalized","value":1}]}],
            "comparison_tolerance":{"maximum_absolute_error":2e-6,"maximum_pcm_lsb_error":1,"relative_rms_level_difference":1e-4}}]}
        description={"parameters":[{"index":0,"paramId":"frequency","minimum":20,"maximum":10000,"initialValue":440,"exponent":1,"steps":0}]}
        (self.directory/"description.json").write_text(json.dumps(description))
        patch=self.directory/"test.rnbopat";patch.write_text("fixture-source")
        manifest={"role":"main","numerical_profile":"float32-strict","editable_source_sha256":hashlib.sha256(patch.read_bytes()).hexdigest(),"parameter_schema_sha256":"schema","source_tree_sha256":"raw",
                  "parameter_count":1,"audio_inputs":0,"audio_outputs":2,"required_host_services":[]}
        self.modules={k:{"report":{"prepared_export":{"manifest":copy.deepcopy(manifest)}},"export_path":str(self.directory),"artifact_sha256":str(i)*64,"inspection":{"loaded_bytes_upper_bound":65536}} for i,k in enumerate(("strict","optimized"))}
        self.args=argparse.Namespace(catalog=self.directory/"catalog.json",fixture_id="test",blocks=None,rounds=3,timing_exclude_blocks=32,arena_bytes=1048576)
    def tearDown(self):self.temporary.cleanup()
    def generate(self):
        self.args.catalog.write_text(json.dumps(self.catalog));return configuration(self.args,self.modules)
    def test_events_and_exact_policy(self):
        header,policy=self.generate()
        self.assertIn("#define BENCH_MAX_ABS "+float(2e-6).hex(),header)
        self.assertEqual([(e["block"],e["kind"],e["value"]) for e in policy["events"]],[(0,1,440),(7,2,1)])
    def fx(self):
        fixture=self.catalog['fixtures'][0];fixture['role']='fx'
        fixture['stimulus']={'kind':'midi-stereo-v1','base':60,'depth':12,'rate':.5,'pilot_frequency':371,'pilot_amplitude':.125}
        for m in self.modules.values():
            manifest=m['report']['prepared_export']['manifest'];manifest['role']='fx';manifest['audio_inputs']=2
        return fixture
    def test_partial_fx_stimulus_cannot_be_benchmarked_as_generic_input(self):
        self.fx()['stimulus']={'kind':'midi-stereo-v1'}
        with self.assertRaisesRegex(ExportError,'stimulus fields'):self.generate()
    def test_declared_fx_stimulus_and_case_override(self):
        fixture=self.fx();fixture['cases'][1]['stimulus']={'depth':24,'rate':20}
        header,policy=self.generate()
        self.assertEqual(policy['stimuli'][1]['depth'],24)
        self.assertEqual(policy['stimuli'][1]['rate'],20)
        self.assertIn('static const object_stimulus bench_stimuli[]',header)
    def test_unknown_stimulus_kind(self):
        self.fx()['stimulus']['kind']='generic'
        with self.assertRaisesRegex(ExportError,'Unknown FX stimulus kind'):self.generate()
    def test_unknown_case_stimulus_field(self):
        self.fx()['cases'][0]['stimulus']={'ignored_field':1}
        with self.assertRaisesRegex(ExportError,'stimulus fields'):self.generate()
    def test_case_cannot_change_stimulus_kind(self):
        self.fx()['cases'][0]['stimulus']={'kind':'frequency-stereo-v1'}
        with self.assertRaisesRegex(ExportError,'stimulus fields'):self.generate()
    def test_pitch_domain(self):
        self.fx()['stimulus']['depth']=100
        with self.assertRaisesRegex(ExportError,'pitch stimulus'):self.generate()
    def test_nonfinite_stimulus(self):
        self.fx()['stimulus']['rate']=float('nan')
        with self.assertRaises(ExportError):self.generate()
    def test_main_cannot_ignore_declared_input(self):
        self.catalog['fixtures'][0]['stimulus']={'kind':'midi-stereo-v1'}
        with self.assertRaisesRegex(ExportError,'Main cannot'):self.generate()
    def test_fx_memory_budget(self):
        self.fx();self.args.blocks=1024
        with self.assertRaisesRegex(ExportError,'PSRAM budget'):self.generate()
    def average(self):
        fixture=self.fx();fixture['family']='average';fixture['stimulus']={'kind':'impulse-step-v1'}
        fixture['verification']={'kind':'average-window-v1','parameter_id':'window','default_window':16,'maximum_window':64,'maximum_absolute_error':2e-6}
        fixture['semantic']={'kind':'average','default_window':16,'maximum_absolute_error':2e-6}
        fixture['cases']=[{'id':name,'parameters':parameters,'events':[]} for name,parameters in [('one',{'window':1}),('default',{}),('odd-window',{'window':63}),('maximum',{'window':64})]]
        self.average_schema={'index':0,'paramId':'window','minimum':1,'maximum':64,'initialValue':16,'exponent':1,'steps':0}
        self.write_average_schema();return fixture
    def write_average_schema(self):
        (self.directory/'description.json').write_text(json.dumps({'parameters':[self.average_schema]}))
    def test_average_contract_windows_and_oracle_budget(self):
        self.average();header,policy=self.generate()
        self.assertIn('#define BENCH_HAS_ORACLE 1u',header)
        self.assertEqual([(v['window'],v['initial_available']) for v in policy['verifications']],[(1,0),(16,16),(63,0),(64,0)])
        self.assertEqual(policy['psram_budget']['oracle_cache_bytes'],1048576)
        self.assertLessEqual(policy['psram_budget']['required_upper_bound_bytes'],8388608)
    def test_average_cold_default_has_no_prepared_history(self):
        self.average();self.catalog['fixtures'][0]['warmup_blocks']=0
        self.assertEqual(self.generate()[1]['verifications'][1]['initial_available'],0)
    def test_retrigger_same_default_preserves_warm_history(self):
        fixture=self.average();fixture['cases'][1]['parameters']={'window':16}
        self.assertEqual(self.generate()[1]['verifications'][1]['initial_available'],16)
    def test_average_fractional_window_rejected(self):
        fixture=self.average();fixture['cases'][0]['parameters']['window']=1.5
        with self.assertRaisesRegex(ExportError,'integer1..64'):self.generate()
    def test_average_events_rejected_until_modeled(self):
        fixture=self.average();fixture['cases'][0]['events']=[{'block':1,'id':'window','value':32}]
        with self.assertRaisesRegex(ExportError,'events are not yet modeled'):self.generate()
    def test_average_unknown_parameter_rejected(self):
        fixture=self.average();fixture['cases'][0]['parameters']={'another':1}
        with self.assertRaisesRegex(ExportError,'Unknown average parameter'):self.generate()
    def test_average_wider_semantic_tolerance_rejected(self):
        fixture=self.average();fixture['verification']['maximum_absolute_error']=3e-6
        with self.assertRaisesRegex(ExportError,'verification contract'):self.generate()
    def test_average_schema_exponent_and_steps_guard(self):
        self.average()
        for field,value in [('exponent',2),('steps',1)]:
            with self.subTest(field=field):
                before=dict(self.average_schema);self.average_schema[field]=value;self.write_average_schema()
                with self.assertRaisesRegex(ExportError,'window schema'):self.generate()
                self.average_schema=before;self.write_average_schema()
    def test_wave2_input_cannot_ignore_missing_verification(self):
        fixture=self.fx();fixture['stimulus']={'kind':'impulse-step-v1'}
        with self.assertRaisesRegex(ExportError,'explicit verification'):self.generate()
    def wave2(self,name='biquad-response'):
        root=Path(__file__).resolve().parents[1]/'tests/fixtures/objects/wave2'
        catalog=json.loads((root/'catalog.json').read_text())
        fixture=copy.deepcopy(next(f for f in catalog['fixtures'] if f['id']==name))
        fixture['verification']={'kind':'biquad-response-v1' if name=='biquad-response' else 'nonlinear-chain-v1',
                                 'maximum_absolute_error':3e-6 if name=='biquad-response' else 2e-6}
        self.catalog['fixtures']=[fixture];self.args.fixture_id=name;self.args.arena_bytes=4096
        shutil.copyfile(root/fixture['patch'],self.directory/fixture['patch'])
        rows=([('a0',0,0,1,.5),('b2',1,0,.8,.2),('a1',2,-1,1,.25),('a2',3,-1,1,.125),('b1',4,-.95,.95,-.4)]
              if name=='biquad-response' else [('exponent',0,.25,4,2)])
        parameters=[dict(paramId=p,index=i,minimum=lo,maximum=hi,initialValue=v,exponent=1,steps=0) for p,i,lo,hi,v in rows]
        (self.directory/'description.json').write_text(json.dumps({'parameters':parameters}))
        schema=('5ee44b4347d4f1d490c0ecb696d9fca49b9ece2d69635b837422dbf98ad9ea30' if name=='biquad-response' else
                '754c55e5f56bd5c2731847a19ed276e1ad4045849e3bcc2909acd4ec76b73ef1')
        raw=('3bf669da7e420a82f5c2370a4449c9ec791cdbef655b227fbb2057ab295015b5' if name=='biquad-response' else
             'b246e2357fc3829af9d44eec0efc1aa69a82bd9157be093663005ea0eb1ea28b')
        for module in self.modules.values():
            exported=module['report']['prepared_export'];manifest=exported['manifest']
            manifest.update(role='fx',audio_inputs=2,parameter_count=len(rows),parameter_schema_sha256=schema,
                            editable_source_sha256=hashlib.sha256((self.directory/fixture['patch']).read_bytes()).hexdigest())
            exported['provenance']={'raw_files_sha256':{'rnbo_source.h':raw}}
        return fixture
    def test_biquad_keeps_double_catalog_coefficients_and_native_dc_order(self):
        self.wave2();header,policy=self.generate();slow=policy['verifications'][2]
        self.assertEqual(slow['coefficients']['a0'],.05)
        self.assertNotEqual(slow['coefficients']['a0'],float.fromhex('0x1.99999a0000000p-5'))
        self.assertEqual(slow['dc_expected'],-.125*(.05/(1-.95)))
        self.assertIn(float(.05).hex(),header)
        self.assertEqual([p['paramId'] for p in policy['parameter_schema']],['a0','b2','a1','a2','b1'])
        self.assertEqual(policy['verifications'][0]['maximum_absolute_error'],3e-6)
        self.assertEqual(policy['psram_budget']['oracle_cache_bytes'],1048576)
    def test_nonlinear_grid_and_positive_exponent_contract(self):
        self.wave2('nonlinear-domains');header,policy=self.generate()
        self.assertEqual([s['kind'] for s in policy['stimuli']],[6,6,6])
        self.assertEqual([v['exponent'] for v in policy['verifications']],[2,.25,4])
        self.assertTrue(all(v['maximum_absolute_error']==2e-6 for v in policy['verifications']))
        self.assertIn('{3u,0,0,',header)
    def test_wave2_metadata_identity_cannot_be_spoofed(self):
        for field in ('editable_source_sha256','parameter_schema_sha256','raw'):
            self.wave2()
            exported=self.modules['optimized']['report']['prepared_export']
            if field=='raw':exported['provenance']['raw_files_sha256']['rnbo_source.h']='0'*64
            else:
                for module in self.modules.values():module['report']['prepared_export']['manifest'][field]='0'*64
            with self.assertRaises(ExportError):self.generate()
    def wrap_finite(self):
        from build_object_benchmark import _WRAP_IDENTITY,_WRAP_CONTRACT
        root=Path(__file__).resolve().parents[1]/'tests/fixtures/objects/wave2'
        fixture=copy.deepcopy(json.loads((root/'wrap-finite-target.json').read_text())['fixtures'][0])
        self.catalog['fixtures']=[fixture];self.args.fixture_id=fixture['id'];self.args.arena_bytes=4096
        shutil.copyfile(root/fixture['patch'],self.directory/fixture['patch'])
        (self.directory/'description.json').write_text(json.dumps({'parameters':[]}))
        for module in self.modules.values():
            module['artifact_sha256']='a'*64
            exported=module['report']['prepared_export'];m=exported['manifest']
            m.update(role='fx',audio_inputs=2,parameter_count=0,editable_source_sha256=_WRAP_IDENTITY['patch'],
                parameter_schema_sha256=_WRAP_IDENTITY['schema'],correct_finite_wrap=True,finite_wrap_contract=copy.deepcopy(_WRAP_CONTRACT))
            exported['provenance']={'raw_files_sha256':{'rnbo_source.h':_WRAP_IDENTITY['raw_source']}}
            module['report']['prepared_snapshot']={'prepared_files_sha256':{'rnbo_source.h':_WRAP_IDENTITY['corrected_source'],'private_finite_wrap.h':_WRAP_IDENTITY['helper']}}
        return fixture
    def test_wrap_exact_same_corrected_image_contract(self):
        self.wrap_finite();header,policy=self.generate()
        self.assertEqual([s['kind'] for s in policy['stimuli']],[7,8,9,10])
        self.assertTrue(all(v=={'kind':'wrap-finite-v1','maximum_absolute_error':0,'model':'exact-binary32-modulo2',
            'rounding':'exact-binary32','gate':'raw-binary32-equality','bit_exact':True} for v in policy['verifications']))
        self.assertEqual(policy['parameter_schema'],[]);self.assertIn('{4u,0,0,',header)
        self.assertEqual(policy['events'],[])
    def test_wrap_rejects_original_and_different_image_before_unsafe_build(self):
        self.wrap_finite();self.modules['strict']['report']['prepared_export']['manifest']['correct_finite_wrap']=False
        with self.assertRaisesRegex(ExportError,'corrected module'):self.generate()
        self.wrap_finite();self.modules['optimized']['artifact_sha256']='b'*64
        with self.assertRaisesRegex(ExportError,'same corrected module'):self.generate()
    def test_wrap_source_helper_contract_and_guard_count_fail_closed(self):
        for change in ('source','helper','raw','contract'):
            self.wrap_finite();module=self.modules['optimized']
            if change=='contract':module['report']['prepared_export']['manifest']['finite_wrap_contract']['guard_count']=1
            elif change=='raw':module['report']['prepared_export']['provenance']['raw_files_sha256']['rnbo_source.h']='0'*64
            else:module['report']['prepared_snapshot']['prepared_files_sha256']['rnbo_source.h' if change=='source' else 'private_finite_wrap.h']='0'*64
            with self.subTest(change=change),self.assertRaises(ExportError):self.generate()
    def test_wrap_cases_stimulus_events_and_tolerances_cannot_change(self):
        changes=[lambda f:f['cases'].reverse(),lambda f:f['cases'][0]['events'].append({'block':1,'id':'x','value':0}),
            lambda f:f['cases'][0].update(stimulus={'kind':'mixed-tone-v1'}),
            lambda f:f['verification'].update(bit_exact=False),lambda f:f['comparison_tolerance'].update(maximum_absolute_error=1e-8),
            lambda f:f.update(warmup_blocks=0)]
        for change in changes:
            f=self.wrap_finite();change(f)
            with self.subTest(change=change),self.assertRaises(ExportError):self.generate()
    def test_wave2_models_reject_unknown_cases_events_and_coefficients(self):
        mutations=[lambda f:f['cases'].pop(),
                   lambda f:f['cases'].reverse(),
                   lambda f:f['cases'][0].update(id='other'),
                   lambda f:f['cases'][1]['parameters'].update(a0=.9),
                   lambda f:f['cases'][1]['parameters'].update(a0=True),
                   lambda f:f['cases'][0]['events'].append({'block':1,'id':'a0','value':1}),
                   lambda f:f['semantic']['defaults'].update(b1=-.5),
                   lambda f:f['cases'][0].update(stimulus={'kind':'mixed-tone-v1'}),
                   lambda f:f['verification'].update(maximum_absolute_error=4e-6),
                   lambda f:f.update(warmup_blocks=0)]
        for change in mutations:
            with self.subTest(change=change):
                fixture=self.wave2();change(fixture)
                with self.assertRaises(ExportError):self.generate()
    def test_wave2_blocks_pair_tolerance_and_schema_reject(self):
        self.wave2();self.args.blocks=256
        with self.assertRaises(ExportError):self.generate()
        self.args.blocks=None
        fixture=self.wave2();fixture['comparison_tolerance']['maximum_absolute_error']=3e-6
        with self.assertRaises(ExportError):self.generate()
        self.wave2();description=json.loads((self.directory/'description.json').read_text())
        description['parameters'][0]['exponent']=2
        (self.directory/'description.json').write_text(json.dumps(description))
        with self.assertRaises(ExportError):self.generate()
    def test_average_cancellation_case_retains_same_gate(self):
        fixture=self.average();fixture['cases'].append({'id':'cancellation','parameters':{},'events':[],'stimulus':{'kind':'mixed-tone-v1'}})
        policy=self.generate()[1]
        self.assertEqual(policy['stimuli'][-1]['kind'],5)
        self.assertEqual(policy['verifications'][-1]['maximum_absolute_error'],2e-6)
    def test_average_cannot_admit_the_unreviewed_nonlinear_grid(self):
        for override in (False,True):
            with self.subTest(override=override):
                fixture=self.average()
                if override:fixture['cases'][0]['stimulus']={'kind':'nonlinear-grid-v1'}
                else:fixture['stimulus']={'kind':'nonlinear-grid-v1'}
                with self.assertRaisesRegex(ExportError,'average verification contract/input'):self.generate()
    def test_average_extra_oracle_cache_budget_rejects_oversize(self):
        self.average();self.args.blocks=1024
        with self.assertRaisesRegex(ExportError,'PSRAM budget'):self.generate()
    def test_wrong_source(self):
        self.modules["optimized"]["report"]["prepared_export"]["manifest"]["source_tree_sha256"]="other"
        with self.assertRaises(ExportError):self.generate()
    def test_unknown_parameter(self):
        self.catalog["fixtures"][0]["cases"][0]["parameters"]={"unknown":1}
        with self.assertRaises(ExportError):self.generate()
    def test_actual_bounds(self):
        self.catalog["fixtures"][0]["cases"][0]["parameters"]["frequency"]=10001
        with self.assertRaises(ExportError):self.generate()
    def test_normalized_bounds(self):
        self.catalog["fixtures"][0]["cases"][1]["events"][0]["value"]=1.01
        with self.assertRaises(ExportError):self.generate()
    def test_duplicate_block_parameter(self):
        self.catalog["fixtures"][0]["cases"][0]["events"]=[{"block":0,"id":"frequency","value":20}]
        with self.assertRaises(ExportError):self.generate()
    def ordered_parameters(self):
        description={"parameters":[
            {"index":0,"paramId":"target","minimum":-1,"maximum":1,"initialValue":0,"exponent":1,"steps":0},
            {"index":1,"paramId":"milliseconds","minimum":0,"maximum":1000,"initialValue":10,"exponent":1,"steps":0},
            {"index":2,"paramId":"extra","minimum":0,"maximum":1,"initialValue":0,"exponent":1,"steps":0}]}
        (self.directory/"description.json").write_text(json.dumps(description))
        for module in self.modules.values():module['report']['prepared_export']['manifest']['parameter_count']=3
        self.catalog['fixtures'][0]['cases']=[{'id':'ordered','parameters':{},'events':[]}]
        return self.catalog['fixtures'][0]['cases'][0]
    def test_same_block_setters_preserve_authored_order_including_reverse(self):
        case=self.ordered_parameters()
        duration={'block':1,'id':'milliseconds','value':5};target={'block':1,'id':'target','value':-.5}
        for source,expected in [([duration,target],[1,0]),([target,duration],[0,1])]:
            case['events']=source
            header,policy=self.generate()
            self.assertEqual([e['index'] for e in policy['events']],expected)
            self.assertEqual(policy['event_order'],'stable-block-source-order-v1')
            indices=re.findall(r'\{1u,(\d+)u,1u,',header)
            self.assertEqual(list(map(int,indices)),expected)
    def test_stable_chronological_order_does_not_sort_parameter_indices(self):
        case=self.ordered_parameters();case['events']=[
            {'block':2,'id':'milliseconds','value':9},
            {'block':1,'id':'milliseconds','value':5},
            {'block':0,'id':'extra','value':1},
            {'block':2,'id':'target','value':1},
            {'block':1,'id':'target','value':-.5}]
        events=self.generate()[1]['events']
        self.assertEqual([(e['block'],e['index']) for e in events],[(0,2),(1,1),(1,0),(2,1),(2,0)])
    def test_initial_map_precedes_explicit_events_without_reordering_keys(self):
        case=self.ordered_parameters();case['parameters']={'milliseconds':0,'target':1}
        case['events']=[{'block':0,'id':'extra','form':'normalized','value':.5}]
        self.assertEqual([(e['index'],e['kind']) for e in self.generate()[1]['events']],[(1,1),(0,1),(2,2)])
    def test_map_list_duplicate_remains_rejected_across_forms(self):
        case=self.ordered_parameters();case['parameters']={'milliseconds':0}
        case['events']=[{'block':0,'id':'milliseconds','form':'normalized','value':.5}]
        with self.assertRaisesRegex(ExportError,'duplicate parameter event'):self.generate()
    def test_real_backend_dispatch_consumes_the_generated_table_in_order(self):
        compiler=shutil.which('cc')
        if not compiler:self.skipTest('C compiler required for dispatch check')
        case=self.ordered_parameters();case['parameters']={'milliseconds':0,'target':1}
        case['events']=[{'block':1,'id':'milliseconds','value':5},{'block':1,'id':'target','value':-.5}]
        header,policy=self.generate()
        events=re.search(r'static const bench_event bench_events\[\]=\{[\s\S]*?\n\};',header)[0]
        backend=(Path(__file__).resolve().parents[1]/'object-benchmark/main/benchmark.c').read_text()
        dispatch=backend[backend.index('static void dispatch('):backend.index('\nstatic void step(')]
        source='''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define CHECK(x) do { if(!(x)) abort(); } while(0)
#define RNBO_S3_OK 0
typedef struct { uint32_t block,index,kind;float value; } bench_event;
typedef struct { const char *name;uint32_t event_begin,event_count; } bench_case;
typedef struct { uint32_t struct_bytes,kind,parameter_index;float value; } rnbo_s3_event;
typedef struct { struct { int(*event)(void*,const rnbo_s3_event*); } module;void *context; } object_image;
typedef struct { uint64_t event_us,events; } profile_metrics;
static void allocation_probe_begin(void){} static void allocation_probe_end(void){}
static int64_t esp_timer_get_time(void){return 0;}
static int record(void *unused,const rnbo_s3_event *event){(void)unused;printf("%u %u %.9g\\n",event->parameter_index,event->kind,(double)event->value);return 0;}
'''+events+'\n'+dispatch+'''
int main(void){object_image image={{record},0};bench_case test={"ordered",0,4};profile_metrics metrics={0};
dispatch(&image,&test,0,&metrics);dispatch(&image,&test,1,&metrics);return metrics.events==4?0:1;}
'''
        path=self.directory/'dispatch.c';path.write_text(source);executable=self.directory/'dispatch'
        subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror',str(path),'-o',str(executable)],check=True,capture_output=True)
        result=subprocess.run([str(executable)],check=True,capture_output=True,text=True)
        self.assertEqual(result.stdout.splitlines(),['1 1 0','0 1 1','1 1 5','0 1 -0.5'])
    def test_event_after_pass(self):
        self.catalog["fixtures"][0]["cases"][1]["events"][0]["block"]=512
        with self.assertRaises(ExportError):self.generate()
    def test_nonfinite_tolerance(self):
        self.catalog["fixtures"][0]["comparison_tolerance"]["maximum_absolute_error"]=float("nan")
        with self.assertRaises(ExportError):self.generate()
    def test_catalog_patch_identity(self):
        (self.directory/"test.rnbopat").write_text("changed")
        with self.assertRaises(ExportError):self.generate()
    def test_strict_reference_profile(self):
        self.modules["strict"]["report"]["prepared_export"]["manifest"]["numerical_profile"]="optimized"
        with self.assertRaises(ExportError):self.generate()
    def test_explicit_optional_reference_is_truthfully_recorded(self):
        self.args.reference_profile='float32-audio-v2'
        self.modules['strict']['report']['prepared_export']['manifest']['numerical_profile']='float32-audio-v2'
        header,policy=self.generate()
        self.assertEqual(policy['numerical_profiles']['strict'],'float32-audio-v2')
        self.assertIn('#define BENCH_REFERENCE_PROFILE',header)
    def test_requested_profile_must_match_actual_reference(self):
        self.args.reference_profile='float32-audio-v2'
        with self.assertRaisesRegex(ExportError,'differs from explicit request'):self.generate()
    def test_profile_identifiers_cannot_break_log_fields(self):
        self.modules['optimized']['report']['prepared_export']['manifest']['numerical_profile']='two words'
        with self.assertRaisesRegex(ExportError,'Unsafe numerical profile'):self.generate()
    def test_safe_literals(self):
        self.assertEqual(c_string('";\\\n'), '"\\x22""\\x3b""\\x5c""\\x0a"')
        self.assertTrue(c_float(.2).endswith("f"))
        with self.assertRaises(ExportError):c_float(float("inf"))

if __name__=="__main__":unittest.main()
