#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Admission tests for catalog-to-firmware configuration, no toolchain/device."""
import argparse
import copy
import json
import hashlib
from pathlib import Path
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
    def test_average_cancellation_case_retains_same_gate(self):
        fixture=self.average();fixture['cases'].append({'id':'cancellation','parameters':{},'events':[],'stimulus':{'kind':'mixed-tone-v1'}})
        policy=self.generate()[1]
        self.assertEqual(policy['stimuli'][-1]['kind'],5)
        self.assertEqual(policy['verifications'][-1]['maximum_absolute_error'],2e-6)
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
