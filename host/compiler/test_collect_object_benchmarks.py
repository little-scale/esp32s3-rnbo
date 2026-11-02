# SPDX-License-Identifier: MIT
"""Reject incomplete or internally inconsistent target evidence."""
import json
from pathlib import Path
import tempfile
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
                'modules':{p:{'artifact_sha256':c*64,'report':{'prepared_export':{'manifest':{'role':'main','audio_inputs':0,'audio_outputs':2}}}} for p,c in (('strict','a'),('optimized','b'))}}
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

if __name__=='__main__':unittest.main()
