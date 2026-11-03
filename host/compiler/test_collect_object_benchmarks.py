# SPDX-License-Identifier: MIT
"""Reject incomplete or internally inconsistent target evidence."""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import struct
import unittest
from collect_object_benchmarks import (collect,fields,sha,board_evidence,WRAP_ORACLE,WRAP_STIMULI,
    wrap_cache_hashes,wrap_input_coverage,exact_wrap_word,POWER_KIND,POWER_DENSE,
    POWER_DESCRIPTION,POWER_CORRECTED,POWER_COMPOSED,POWER_COMPILE_CONTRACT,
    power_cases,power_events,power_schedule_sha,power_verification,power_input_data,
    WAVE2_ORACLES,WAVE4_KIND,WAVE4_MODELS,WAVE4_INPUTS,WAVE4_IDENTITIES,
    WAVE4_SCHEMA,WAVE4_RUNTIME,WAVE4_ADAPTATIONS,wave4_verification,wave4_input_bytes,
    wave4_oracle_bytes,wave4_cache_hashes,GEN_KIND,GEN_INPUT,GEN_MODELS,GEN_IDENTITIES,GEN_SCHEMA,
    gen_cases,gen_events,gen_schedule_sha,gen_verification,gen_input_bytes,gen_cache_data,
    GEN_FEEDBACK_MODE,GEN_FEEDBACK_PROFILE,GEN_FEEDBACK_PIN,GEN_FEEDBACK_CONTRACT,GEN_FEEDBACK_CATALOG_SHA,
    GEN_ARITH_KIND,GEN_ARITH_MODELS,GEN_ARITH_IDENTITIES,gen_arith_verification,gen_arith_oracle_bytes)

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

    def explicit_board(self,board='xiao',device='ba:1e:48:12:34:56'):
        self.report['board']=board
        self.report['artifacts']={'build/unit.elf':{'bytes':123,'sha256':'c'*64},
            'build/unit.bin':{'bytes':456,'sha256':'d'*64},
            'build/partition_table/partition-table.bin':{'bytes':3072,'sha256':'e'*64}}
        self.seal()
        path=self.run/'hardware-test.json';run=json.loads(path.read_text())
        run.update(format='rnbo-isolated-hardware-test',format_version=1,board=board,device_id=device,
                   flash_bytes={'xiao':0x800000,'amoled':0x1000000}[board],test_app_sha256='d'*64)
        run['restoration']['status']={'board':{'xiao':'XIAO ESP32-S3','amoled':'Waveshare AMOLED 1.8 V2'}[board]}
        path.write_text(json.dumps(run));return path,run

    def test_explicit_xiao_board_and_device_are_bound(self):
        self.explicit_board();result=collect(self.build,self.run)
        self.assertEqual(result['board'],'xiao');self.assertEqual(result['device_id'],'ba:1e:48:12:34:56')
        self.assertEqual(result['board_binding']['restored_status_board'],'XIAO ESP32-S3')
        self.assertEqual(result['cases'][0]['observed_process_reduction_percent'],50)

    def test_explicit_amoled_board_and_device_are_bound(self):
        self.explicit_board('amoled','28:84:85:3a:d3:90');result=collect(self.build,self.run)
        self.assertEqual(result['board'],'amoled')
        self.assertEqual(result['board_binding']['build_board'],'amoled')

    def test_legacy_amoled_output_is_not_relabelled(self):
        original=collect(self.build,self.run)
        self.report['board']='amoled';self.seal();result=collect(self.build,self.run)
        # Adding build metadata changes its hash and the runner report hash;
        # historical numeric/semantic output and its field shape stay intact.
        provenance={'build_report_sha256','hardware_report_sha256'}
        self.assertEqual({k:v for k,v in result.items()if k not in provenance},
                         {k:v for k,v in original.items()if k not in provenance})
        for field in ('board','device_id','board_binding'):self.assertNotIn(field,result)

    def test_xiao_cannot_use_legacy_runner_without_board(self):
        self.report['board']='xiao';self.seal()
        with self.assertRaisesRegex(ValueError,'explicit runner board'):collect(self.build,self.run)

    def test_explicit_runner_build_board_mismatch_rejected(self):
        path,run=self.explicit_board();self.report['board']='amoled'
        (self.build/'build-report.json').write_text(json.dumps(self.report));run['test_build_report_sha256']=sha(self.build/'build-report.json');path.write_text(json.dumps(run))
        with self.assertRaisesRegex(ValueError,'Runner/build board'):collect(self.build,self.run)

    def test_explicit_board_requires_build_board(self):
        path,run=self.explicit_board();del self.report['board']
        (self.build/'build-report.json').write_text(json.dumps(self.report));run['test_build_report_sha256']=sha(self.build/'build-report.json');path.write_text(json.dumps(run))
        with self.assertRaisesRegex(ValueError,'Runner/build board'):collect(self.build,self.run)

    def test_unknown_or_partial_explicit_boards_rejected(self):
        _,run=self.explicit_board()
        for board in (None,True,'','XIAO','other',{},[]):
            with self.subTest(board=board):
                altered=copy.deepcopy(run);altered['board']=board
                with self.assertRaisesRegex(ValueError,'Unknown explicit runner board'):board_evidence(self.report,altered)

    def test_explicit_board_requires_exact_device_identity(self):
        _,run=self.explicit_board()
        for device in (None,False,'','ba1e4812345','ba:1e:48:12:34','ba:1e:48:12:34:zz',{},' ba1e48123456'):
            with self.subTest(device=device):
                altered=copy.deepcopy(run);altered['device_id']=device
                with self.assertRaisesRegex(ValueError,'exact runner device identity'):board_evidence(self.report,altered)

    def test_restored_status_board_mismatch_rejected(self):
        path,run=self.explicit_board();run['restoration']['status']['board']='Waveshare AMOLED 1.8 V2';path.write_text(json.dumps(run))
        with self.assertRaisesRegex(ValueError,'Restored status board'):collect(self.build,self.run)

    def test_explicit_board_requires_restored_status(self):
        _,run=self.explicit_board()
        for status in (None,{},[],{'board':'xiao'}):
            with self.subTest(status=status):
                altered=copy.deepcopy(run);altered['restoration']['status']=status
                with self.assertRaisesRegex(ValueError,'Restored status board'):board_evidence(self.report,altered)

    def test_restored_device_if_present_must_match_exact_identity(self):
        _,run=self.explicit_board();run['restoration']['status']['device_id']='BA:1E:48:12:34:56'
        self.assertEqual(board_evidence(self.report,run)['device_id'],'ba:1e:48:12:34:56')
        run['restoration']['status']['device_id']='28:84:85:3a:d3:90'
        with self.assertRaisesRegex(ValueError,'Restored status device'):board_evidence(self.report,run)

    def test_compact_runner_and_restored_device_forms_normalize_exactly(self):
        path,run=self.explicit_board(device='BA1E48123456')
        run['restoration']['status']['device_id']='ba:1e:48:12:34:56';path.write_text(json.dumps(run))
        result=collect(self.build,self.run)
        self.assertEqual(result['device_id'],'ba:1e:48:12:34:56')
        self.assertEqual(result['board_binding']['runner_device_id'],'BA1E48123456')
        run['device_id']='ba:1e:48:12:34:56';run['restoration']['status']['device_id']='BA1E48123456'
        self.assertEqual(board_evidence(self.report,run)['device_id'],'ba:1e:48:12:34:56')
        run['restoration']['status']['device_id']='ba1e48123457'
        with self.assertRaisesRegex(ValueError,'Restored status device'):board_evidence(self.report,run)

    def test_explicit_board_requires_recognized_runner_format(self):
        _,run=self.explicit_board()
        for fields in ({'format':None},{'format':'other'},{'format_version':True},{'format_version':2}):
            with self.subTest(fields=fields):
                altered=copy.deepcopy(run);altered.update(fields)
                with self.assertRaisesRegex(ValueError,'hardware runner record format'):board_evidence(self.report,altered)

    def test_explicit_board_flash_size_must_match_exactly(self):
        _,run=self.explicit_board()
        for size in (None,True,0,0x1000000,float(0x800000),'8388608'):
            with self.subTest(size=size):
                altered=copy.deepcopy(run);altered['flash_bytes']=size
                with self.assertRaisesRegex(ValueError,'flash size'):board_evidence(self.report,altered)

    def test_explicit_firmware_hashes_must_match_build_artifacts(self):
        _,run=self.explicit_board()
        for field in ('test_elf_sha256','test_app_sha256'):
            for value in (None,'f'*64,'invalid',True):
                with self.subTest(field=field,value=value):
                    altered=copy.deepcopy(run);altered[field]=value
                    with self.assertRaisesRegex(ValueError,'identity differs from build artifact'):board_evidence(self.report,altered)

    def test_explicit_board_rejects_missing_ambiguous_or_malformed_artifacts(self):
        _,run=self.explicit_board();base=copy.deepcopy(self.report)
        for mutation in ('missing','no-elf','no-app','two-elf','two-app','bad-sha','bad-bytes'):
            with self.subTest(mutation=mutation):
                report=copy.deepcopy(base);artifacts=report['artifacts']
                if mutation=='missing':del report['artifacts']
                elif mutation=='no-elf':del artifacts['build/unit.elf']
                elif mutation=='no-app':del artifacts['build/unit.bin']
                elif mutation=='two-elf':artifacts['build/other.elf']=dict(artifacts['build/unit.elf'])
                elif mutation=='two-app':artifacts['build/other.bin']=dict(artifacts['build/unit.bin'])
                elif mutation=='bad-sha':artifacts['build/unit.elf']['sha256']='not-a-hash'
                else:artifacts['build/unit.bin']['bytes']=True
                with self.assertRaises(ValueError):board_evidence(report,run)
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


class FiniteWrapObservationTests(unittest.TestCase):
    """Synthetic admission records only; these never claim device execution."""
    @classmethod
    def setUpClass(cls):
        # Publicly sealed filename/hash metadata only, never runtime bodies or
        # an installed RNBO dependency. Same normal fixed runtime as wrap.
        root=Path(__file__).resolve().parents[2]
        table=json.loads((root/'evidence/pink-output-compiler.json').read_text())['prepared_snapshot']['prepared_files_sha256']
        cls.runtime_hashes={name:value for name,value in table.items() if name.startswith('common/')}

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.build=self.root/'build';self.run=self.root/'run'
        self.build.mkdir();self.run.mkdir();self.fixture()

    def fixture(self,rounds=3):
        fixture={'id':'wrap-finite-stereo','family':'wrap','role':'fx','blocks':512,
            'warmup_blocks':4,'seed':305419896,'cases':copy.deepcopy(WRAP_ORACLE['cases']),
            'stimulus':{'kind':'wrap-finite-boundaries-v1'},
            'semantic':{'kind':'wrap-finite','range':[-1,1],'upper_exclusive':True,'maximum_absolute_error':0,'bit_exact':True},
            'verification':{'kind':'wrap-finite-v1','maximum_absolute_error':0,'bit_exact':True},
            'comparison_tolerance':{'maximum_absolute_error':0,'maximum_pcm_lsb_error':0,'relative_rms_level_difference':0}}
        plan={'fixture':fixture,'rounds':rounds,'blocks':512,'timing_exclude_blocks':32,'arena_bytes':4096,
              'catalog_path':'/synthetic/catalog.json','catalog_sha256':'d'*64,
              'patch_sha256':WRAP_ORACLE['patch'],'description_sha256':WRAP_ORACLE['description'],
              'parameter_schema':[],'events':[],'numerical_profiles':{'strict':'float32-strict','optimized':'float32-strict'},
              'stimuli':[],'verifications':[]}
        manifest={'role':'fx','audio_inputs':2,'audio_outputs':2,'sample_rate':44100,'block_frames':256,
                  'numerical_profile':'float32-strict','editable_source_sha256':WRAP_ORACLE['patch'],
                  'parameter_schema_sha256':WRAP_ORACLE['schema'],'parameter_count':0,
                  'correct_finite_wrap':True,'finite_wrap_contract':copy.deepcopy(WRAP_ORACLE['contract'])}
        provenance={'raw_files_sha256':{'rnbo_source.h':WRAP_ORACLE['raw_source']},
            'prepared_files_sha256':{**self.runtime_hashes,'rnbo_source.h':WRAP_ORACLE['prepared_source'],'description.json':WRAP_ORACLE['description'],
                'private_finite_wrap.h':WRAP_ORACLE['helper'],'rnbo_s3_finite_wrap_source.h':WRAP_ORACLE['compile_contract']},
            'adaptations':[{'name':'rnbo-1.4.4-finite-wrap-even24-v1','context':'wrap-finite-stereo','guard_count':2,
                'input_sha256':WRAP_ORACLE['raw_source'],'prepared_sha256':WRAP_ORACLE['prepared_source'],
                'runtime_tree_sha256':WRAP_ORACLE['runtime']}]}
        self.report={'benchmark':plan,'modules':{p:{'artifact_sha256':'a'*64,'inspection':{'loaded_bytes_upper_bound':65536},
            'report':{'prepared_export':{'manifest':copy.deepcopy(manifest),'provenance':copy.deepcopy(provenance)}}} for p in ('strict','optimized')},
            'source_files_sha256':{f'object-benchmark/main/{name}':str(i)*64 for i,name in enumerate(('stimulus.c','stimulus.h','wave2_oracle.c','wave2_oracle.h'),1)}}
        budget={'workspace_bytes':2101248,'oracle_cache_bytes':1048576,'arena_bytes':8192,'opaque_context_upper_bound_bytes':2097152,
                'loaded_images_upper_bound_bytes':131072,'loader_heap_alignment_reserve_bytes':524288,'physical_psram_bytes':8388608}
        budget['required_upper_bound_bytes']=sum(v for k,v in budget.items() if k!='physical_psram_bytes');plan['psram_budget']=budget
        samples=rounds*512*512
        self.lines=['RNBO_OBJECT_BENCHMARK NUMERICAL_PROFILES fixture=wrap-finite-stereo reference=float32-strict candidate=float32-strict']
        for case in fixture['cases']:
            cid=case['id'];kind=WRAP_STIMULI[case['stimulus']['kind']];ih,oh=wrap_cache_hashes(kind)
            plan['stimuli'].append({'kind':kind,'settings':copy.deepcopy(case['stimulus']),**{k:0. for k in ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')}})
            plan['verifications'].append({'kind':'wrap-finite-v1','maximum_absolute_error':0,'model':'exact-binary32-modulo2',
                'rounding':'exact-binary32','gate':'raw-binary32-equality','bit_exact':True})
            self.lines.append(f'RNBO_OBJECT_BENCHMARK INPUT fixture=wrap-finite-stereo case={cid} input_sha256={ih} input_bytes=1048576 layout=float32_stereo_interleaved_le stimulus_kind={kind}')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK ORACLE fixture=wrap-finite-stereo case={cid} oracle_sha256={oh} oracle_bytes=1048576 layout=float32_stereo_interleaved_le oracle_kind=wrap-finite-v1 max_abs_tolerance=0 max_cache_rounding_error=0 model=exact-binary32-modulo2 rounding=exact-binary32')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE fixture=wrap-finite-stereo case={cid} samples={samples} max_abs=0 rms_error=0 relative_rms=0 pcm_different=0 max_pcm_lsb=0')
            for profile in ('strict','optimized'):
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_PROFILE fixture=wrap-finite-stereo case={cid} profile={profile} timed_blocks={rounds*480} process_us=12000 peak_us=25')
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_SEMANTIC fixture=wrap-finite-stereo case={cid} profile={profile} semantic_kind=wrap-finite-v1 samples={samples} max_abs=0 max_model_error_bound=0 max_abs_tolerance=0 oracle_sha256={oh}')
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_BITS fixture=wrap-finite-stereo case={cid} profile={profile} oracle_sha256={oh} samples={samples} bit_different=0')
        self.lines.append(f'RNBO_OBJECT_BENCHMARK PASS fixture=wrap-finite-stereo firmware_elf_sha256={"c"*64} strict_module_sha256={"a"*64} optimized_module_sha256={"a"*64} host_heap_allocations=0 host_heap_frees=0 local_late_allocations=0 psram_before=123 psram_after=123 internal_before=42 internal_after=42 images=4 finalized_images=4 cases=4 rounds={rounds} blocks_per_pass=512 timing_exclude=32 warmup=4 seed=305419896 compared_samples={samples*4} input_cases=4 input_rechecks={rounds*12} pilot_sample_checks=0 oracle_cases=4 oracle_rechecks={rounds*12} semantic_sample_checks={samples*8} dc_sample_checks=0 oracle_bit_sample_checks={samples*8} oracle_bit_differences=0')
        self.seal()

    def seal(self):
        (self.build/'build-report.json').write_text(json.dumps(self.report));log=self.run/'test-serial.log';log.write_text('\n'.join(self.lines)+'\n')
        (self.run/'hardware-test.json').write_text(json.dumps({'result':'passed','restoration':{'result':'restored'},
            'test_build_report_sha256':sha(self.build/'build-report.json'),'serial_log_sha256':sha(log),
            'pass_line':self.lines[-1],'test_elf_sha256':'c'*64}))

    def change_line(self,prefix,before,after):
        i=next(i for i,line in enumerate(self.lines) if line.startswith('RNBO_OBJECT_BENCHMARK '+prefix+' '))
        self.lines[i]=self.lines[i].replace(before,after)

    def rejected(self):
        self.seal()
        with self.assertRaises(ValueError):collect(self.build,self.run)

    def test_complete_raw_control_counts_distinct_values_and_zero_rounding(self):
        result=collect(self.build,self.run)
        self.assertTrue(result['identical_artifact_control']);self.assertEqual(result['pass']['oracle_bit_sample_checks'],6291456)
        self.assertEqual(result['stimulus_provenance']['distinct_input_coverage']['all_cases_union_words'],4080)
        self.assertEqual([c['input']['distinct_input_coverage']['distinct_input_words'] for c in result['cases']],[44,2416,4080,18])
        self.assertEqual(len(result['cases'][0]['bit_comparison']),2)
        self.fixture(rounds=1);self.assertEqual(collect(self.build,self.run)['pass']['oracle_bit_sample_checks'],2097152)

    def test_unrepaired_original_and_different_artifacts_are_rejected(self):
        for field,value in [('correct_finite_wrap',False),('parameter_count',1),('numerical_profile','float32-audio-v2')]:
            with self.subTest(field=field):
                self.fixture();self.report['modules']['strict']['report']['prepared_export']['manifest'][field]=value;self.rejected()
        self.fixture();self.report['modules']['optimized']['artifact_sha256']='b'*64
        self.lines[-1]=self.lines[-1].replace('optimized_module_sha256='+'a'*64,'optimized_module_sha256='+'b'*64);self.rejected()

    def test_closed_graph_raw_prepared_helper_runtime_and_guard_contracts(self):
        mutations=[('manifest','editable_source_sha256','0'*64),('manifest','parameter_schema_sha256','0'*64),
                   ('raw_files_sha256','rnbo_source.h','0'*64),('prepared_files_sha256','rnbo_source.h','0'*64),
                   ('prepared_files_sha256','private_finite_wrap.h','0'*64),('prepared_files_sha256','rnbo_s3_finite_wrap_source.h','0'*64)]
        mutations.append(('prepared_files_sha256','common/RNBO_Types.h','0'*64))
        for section,key,value in mutations:
            with self.subTest(section=section,key=key):
                self.fixture();e=self.report['modules']['strict']['report']['prepared_export'];(e['manifest'] if section=='manifest' else e['provenance'][section])[key]=value;self.rejected()
        self.fixture();self.report['modules']['strict']['report']['prepared_export']['manifest']['finite_wrap_contract']['guard_count']=1;self.rejected()
        self.fixture();self.report['modules']['strict']['report']['prepared_export']['provenance']['adaptations'][0]['runtime_tree_sha256']='0'*64;self.rejected()

    def test_fixed_case_order_semantics_events_and_settings_cannot_change(self):
        for mutation in ('order','events','seed','range','tolerance','override'):
            with self.subTest(mutation=mutation):
                self.fixture();f=self.report['benchmark']['fixture']
                if mutation=='order':f['cases'].reverse()
                elif mutation=='events':f['cases'][0]['events']=[{'block':0,'id':'foreign','value':0}]
                elif mutation=='seed':f['seed']=1
                elif mutation=='range':f['semantic']['range']=[0,1]
                elif mutation=='tolerance':f['comparison_tolerance']['maximum_absolute_error']=1e-9
                else:f['cases'][0]['stimulus']['amplitude']=1
                self.rejected()

    def test_input_or_oracle_sha_must_match_complete_independent_bytes(self):
        for prefix,key in [('INPUT','input_sha256'),('ORACLE','oracle_sha256')]:
            with self.subTest(prefix=prefix):
                self.fixture();i=next(i for i,l in enumerate(self.lines) if ' '+prefix+' ' in l)
                value=fields(self.lines[i],'RNBO_OBJECT_BENCHMARK '+prefix+' ')[key]
                self.lines[i]=self.lines[i].replace(value,'0'*64);self.rejected()
        self.fixture();self.change_line('INPUT','stimulus_kind=7','stimulus_kind=7 ignored=0');self.rejected()

    def test_numeric_zero_does_not_replace_raw_bit_identity(self):
        self.change_line('CASE_BITS','bit_different=0','bit_different=1');self.rejected()
        self.fixture();self.change_line('CASE_BITS','samples=786432','samples=786431');self.rejected()
        self.fixture();self.lines=[l for l in self.lines if ' CASE_BITS ' not in l];self.rejected()
        self.fixture();i=next(i for i,l in enumerate(self.lines) if ' CASE_BITS ' in l);self.lines.insert(i,self.lines[i]);self.rejected()
        self.fixture();self.change_line('CASE_BITS','bit_different=0','bit_different=0 ignored=0');self.rejected()

    def test_both_pass_bit_fields_are_mandatory(self):
        for field,value in [('oracle_bit_sample_checks','6291456'),('oracle_bit_differences','0')]:
            with self.subTest(field=field):
                self.fixture();self.lines[-1]=self.lines[-1].replace(' '+field+'='+value,'');self.rejected()
        self.fixture();self.lines[-1]=self.lines[-1].replace(' oracle_bit_sample_checks=6291456 oracle_bit_differences=0','');self.rejected()
        self.fixture();self.lines[-1]=self.lines[-1].replace('oracle_bit_differences=0','oracle_bit_differences=1');self.rejected()

    def test_wrong_precision_metadata_counter_or_source_identity_rejected(self):
        for before,after in [('rounding=exact-binary32','rounding=once-float32'),('max_cache_rounding_error=0','max_cache_rounding_error=1e-9'),
                             ('max_abs_tolerance=0','max_abs_tolerance=1e-9'),('model=exact-binary32-modulo2','model=observed-output')]:
            with self.subTest(before=before):
                self.fixture();self.change_line('ORACLE',before,after);self.rejected()
        self.fixture();self.lines[-1]=self.lines[-1].replace('oracle_bit_sample_checks=6291456','oracle_bit_sample_checks=6291455');self.rejected()
        self.fixture();del self.report['source_files_sha256']['object-benchmark/main/wave2_oracle.c'];self.rejected()

    def test_python_oracle_matches_independent_fraction_at_corners_and_strata(self):
        words=[0,0x80000000,1,0x80000001,0x7fffff,0x800000,0x3f7fffff,0x3f800000,0xbf800000,
               0x4b7fffff,0x4b800001,0xcc000001,0x4f800000,0xcf800000,0x7f7fffff,0xff7fffff]
        for exponent in range(255):
            for mantissa in (0,1,0x3fffff,0x400000,0x7ffffe,0x7fffff):
                words.extend((exponent<<23|mantissa,0x80000000|exponent<<23|mantissa))
        for word in words:
            value=struct.unpack('<f',struct.pack('<I',word))[0]
            exact=Fraction.from_float(value);wrapped=exact-2*((exact+1)//2)
            expected=word if word&0x7fffffff==0 else struct.unpack('<I',struct.pack('<f',float(wrapped)))[0]
            self.assertEqual(exact_wrap_word(word),expected)
        for word in (0x7f800000,0xff800000,0x7fc12345):
            with self.assertRaises(ValueError):exact_wrap_word(word)

    def test_legacy_bit_counters_are_atomic_optional_zero_and_never_claim_bits(self):
        # Reuse a real historical-protocol synthetic Main control.
        legacy=ObservationTests('test_observed_case_cost_and_identity');legacy.setUp()
        self.addCleanup(legacy.doCleanups)
        collect(legacy.build,legacy.run)
        original=list(legacy.lines)
        for addition in (' oracle_bit_sample_checks=0',' oracle_bit_differences=0',
                         ' oracle_bit_sample_checks=1 oracle_bit_differences=0',
                         ' oracle_bit_sample_checks=0 oracle_bit_differences=1'):
            legacy.lines=list(original);legacy.lines[-1]+=addition;legacy.seal()
            with self.assertRaises(ValueError):collect(legacy.build,legacy.run)
        legacy.lines=list(original);legacy.lines[-1]+=' oracle_bit_sample_checks=0 oracle_bit_differences=0';legacy.seal()
        collect(legacy.build,legacy.run)
        legacy.lines.insert(0,'RNBO_OBJECT_BENCHMARK CASE_BITS fixture=unit case=default profile=strict oracle_sha256='+('a'*64)+' samples=3072 bit_different=0')
        legacy.seal()
        with self.assertRaises(ValueError):collect(legacy.build,legacy.run)


class PowerModeObservationTests(unittest.TestCase):
    """Synthetic protocol/admission negatives; never hardware observations."""
    seal=Wave2ObservationTests.seal
    rejected=Wave2ObservationTests.rejected

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.build=self.root/'build';self.run=self.root/'run'
        self.build.mkdir();self.run.mkdir();self.fixture()

    def fixture(self):
        root=Path(__file__).resolve().parents[2]
        table=json.loads((root/'evidence/pink-output-compiler.json').read_text())['prepared_snapshot']['prepared_files_sha256']
        runtime={k:v for k,v in table.items() if k.startswith('common/')}
        contract=WAVE2_ORACLES['nonlinear-chain-v1']
        fixture={'id':'nonlinear-domains','family':'nonlinear','role':'fx','blocks':512,'warmup_blocks':4,
            'seed':305419896,'stimulus':{'kind':'nonlinear-grid-v1'},'cases':power_cases(),
            'semantic':{'kind':'nonlinear','exponent_default':2,'maximum_absolute_error':2e-6},
            'verification':{'kind':POWER_KIND,'maximum_absolute_error':2e-6},
            'comparison_tolerance':{'maximum_absolute_error':2e-6,'maximum_pcm_lsb_error':1,'relative_rms_level_difference':1e-4}}
        plan={'fixture':fixture,'rounds':3,'blocks':512,'timing_exclude_blocks':32,'arena_bytes':4096,
            'catalog_path':'/synthetic/power-modes.json','catalog_sha256':'d'*64,'patch_sha256':contract['patch'],
            'description_sha256':POWER_DESCRIPTION,'parameter_schema':copy.deepcopy(contract['parameters']),
            'events':[e for c in power_cases() for e in power_events(c)],
            'numerical_profiles':{'strict':'float32-strict','optimized':'float32-scalar-powers-v1'},'stimuli':[],'verifications':[]}
        wrap_contract={**WRAP_ORACLE['contract'],'context':'nonlinear-domains','guard_count':1}
        manifest={'role':'fx','audio_inputs':2,'audio_outputs':2,'sample_rate':44100,'block_frames':256,
            'parameter_count':1,'editable_source_sha256':contract['patch'],'parameter_schema_sha256':contract['schema'],
            'correct_finite_wrap':True,'finite_wrap_contract':wrap_contract}
        self.report={'benchmark':plan,'modules':{},'source_files_sha256':{f'object-benchmark/main/{name}':str(i)*64
            for i,name in enumerate(('stimulus.c','stimulus.h','wave2_oracle.c','wave2_oracle.h'),1)}}
        for profile in ('strict','optimized'):
            m=copy.deepcopy(manifest);m['numerical_profile']=plan['numerical_profiles'][profile]
            p={'raw_files_sha256':{'rnbo_source.h':contract['raw_source']},'prepared_files_sha256':{
                **runtime,'rnbo_source.h':POWER_CORRECTED if profile=='strict' else POWER_COMPOSED,
                'description.json':POWER_DESCRIPTION,'private_finite_wrap.h':WRAP_ORACLE['helper'],
                'rnbo_s3_finite_wrap_source.h':WRAP_ORACLE['compile_contract']},
                'adaptations':[{'name':'rnbo-1.4.4-finite-wrap-even24-v1','context':'nonlinear-domains','guard_count':1,
                    'input_sha256':contract['raw_source'],'prepared_sha256':POWER_CORRECTED,'runtime_tree_sha256':WRAP_ORACLE['runtime']}]}
            if profile=='optimized':
                m.update(base_numerical_profile='float32-strict',numerical_identity='changed-rounding-float32-scalar-powers-v1',
                    scalar_powers_contract={'context':'nonlinear-domains','special_exponents':[2,4,.25],'base_domain':[0,1],
                    'fallback':'original-powf-with-fixnan','fixnan_retained':True,'bit_identity_claimed':False,'finite_wrap_composition':True})
                p['prepared_files_sha256']['rnbo_s3_scalar_powers_source.h']=POWER_COMPILE_CONTRACT
                p['adaptations'].append({'name':'rnbo-1.4.4-float32-scalar-powers-v1','input_sha256':POWER_CORRECTED,
                    'prepared_sha256':POWER_COMPOSED,'finite_wrap_composition':True,'runtime_tree_sha256':WRAP_ORACLE['runtime'],'inverse_byte_identity':True})
            self.report['modules'][profile]={'artifact_sha256':('a' if profile=='strict' else 'b')*64,
                'inspection':{'loaded_bytes_upper_bound':65536},'report':{'prepared_export':{'manifest':m,'provenance':p},
                'compiler':{'version':'test'},'dependencies':{'test':'1'},'private_support_archives':{'test':'hash'},
                'source_files_sha256':{'module-sdk/dynamic/rnbo_s3_dynamic.cpp':'a'*64}}}
        budget={'workspace_bytes':2101248,'oracle_cache_bytes':1048576,'arena_bytes':8192,'opaque_context_upper_bound_bytes':2097152,
            'loaded_images_upper_bound_bytes':131072,'loader_heap_alignment_reserve_bytes':524288,'physical_psram_bytes':8388608}
        budget['required_upper_bound_bytes']=sum(v for k,v in budget.items() if k!='physical_psram_bytes');plan['psram_budget']=budget
        self.lines=['RNBO_OBJECT_BENCHMARK NUMERICAL_PROFILES fixture=nonlinear-domains reference=float32-strict candidate=float32-scalar-powers-v1']
        for i,c in enumerate(fixture['cases']):
            cid=c['id'];kind=6 if i<3 else 11;ih=power_input_data(kind)[0];oh=hashlib.sha256(cid.encode()).hexdigest()
            plan['stimuli'].append({'kind':kind,'settings':{'kind':'nonlinear-grid-v1' if kind==6 else POWER_DENSE},
                **{k:0. for k in ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')}})
            v=power_verification(fixture,c);plan['verifications'].append(v)
            prefix=f'fixture=nonlinear-domains case={cid}'
            self.lines.extend([
                f'RNBO_OBJECT_BENCHMARK INPUT {prefix} input_sha256={ih} input_bytes=1048576 layout=float32_stereo_interleaved_le stimulus_kind={kind}',
                f'RNBO_OBJECT_BENCHMARK ORACLE {prefix} oracle_sha256={oh} oracle_bytes=1048576 layout=float32_stereo_interleaved_le oracle_kind={POWER_KIND} initial_exponent=2 event_schedule_sha256={v["event_schedule_sha256"]} max_abs_tolerance=2e-6 max_cache_rounding_error=0 model=float64-tanh-wrap-clip-pow-events-v1 rounding=once-float32',
                f'RNBO_OBJECT_BENCHMARK CASE {prefix} samples=786432 max_abs=0 rms_error=0 relative_rms=0 pcm_different=0 max_pcm_lsb=0',
                f'RNBO_OBJECT_BENCHMARK CASE_ROUNDING {prefix} samples=786432 float_bit_different=4 zero_sign_different={1 if cid=="dense-quarter" else 0}'])
            for profile in ('strict','optimized'):
                self.lines.extend([f'RNBO_OBJECT_BENCHMARK CASE_PROFILE {prefix} profile={profile} timed_blocks=1440 process_us=12000 peak_us=25',
                    f'RNBO_OBJECT_BENCHMARK CASE_SEMANTIC {prefix} profile={profile} semantic_kind={POWER_KIND} samples=786432 max_abs=0 max_model_error_bound=0 max_abs_tolerance=2e-6 oracle_sha256={oh}'])
        self.lines.append(f'RNBO_OBJECT_BENCHMARK PASS fixture=nonlinear-domains firmware_elf_sha256={"c"*64} strict_module_sha256={"a"*64} optimized_module_sha256={"b"*64} host_heap_allocations=0 host_heap_frees=0 local_late_allocations=0 psram_before=123 psram_after=123 internal_before=42 internal_after=42 images=4 finalized_images=4 cases=15 rounds=3 blocks_per_pass=512 timing_exclude=32 warmup=4 seed=305419896 compared_samples=11796480 input_cases=15 input_rechecks=135 pilot_sample_checks=0 oracle_cases=15 oracle_rechecks=135 semantic_sample_checks=23592960 dc_sample_checks=0 oracle_bit_sample_checks=0 oracle_bit_differences=0')
        self.seal()

    def test_power_modes_record_changed_rounding_without_bit_gate(self):
        r=collect(self.build,self.run);self.assertFalse(r['identical_artifact_control'])
        self.assertEqual(len(r['cases']),15);self.assertEqual(r['cases'][4]['rounding_comparison']['zero_sign_different'],1)
        self.assertEqual(r['cases'][-1]['input']['oracle']['verification']['event_schedule'],power_events(power_cases()[-1]))
        self.assertIn('normalized-event',r['stimulus_provenance']['rounding_scope'])

    def test_public_catalog_and_stable_wire_schedule(self):
        root=Path(__file__).resolve().parents[2];path=root/'tests/fixtures/objects/wave2/power-modes-target.json'
        self.assertEqual(json.loads(path.read_text())['fixtures'][0]['cases'],power_cases())
        events=power_events(power_cases()[-1]);wire=struct.pack('<II',0x40000000,len(events))
        for event in events:
            wire+=struct.pack('<III',event['block'],0,1)+struct.pack('<f',event['value'])
        self.assertEqual(power_schedule_sha(events),hashlib.sha256(wire).hexdigest())
        self.assertEqual(events[0]['block'],0);self.assertEqual(events[-1]['block'],511)

    def test_power_case_schedule_and_normalized_spoofs_rejected(self):
        original=copy.deepcopy(self.report)
        for mutation in ('order','normalized','value','block','extra','missing'):
            with self.subTest(mutation=mutation):
                self.report=copy.deepcopy(original);f=self.report['benchmark']['fixture']
                if mutation=='order':f['cases'][-1]['events'].reverse()
                elif mutation=='normalized':f['cases'][-1]['events'][0]['form']='normalized'
                elif mutation=='value':f['cases'][-1]['events'][0]['value']=.25
                elif mutation=='block':self.report['benchmark']['events'][-1]['block']=510
                elif mutation=='extra':f['cases'][0]['stimulus']={'kind':POWER_DENSE}
                else:f['cases'].pop()
                self.rejected()

    def test_power_closed_source_composition_and_runtime_required(self):
        original=copy.deepcopy(self.report)
        for mutation in ('uncorrected','source','runtime','contract','profile','support','compiler','sdk','inverse'):
            with self.subTest(mutation=mutation):
                self.report=copy.deepcopy(original);m=self.report['modules']['optimized']['report'];e=m['prepared_export']
                if mutation=='uncorrected':self.report['modules']['strict']['report']['prepared_export']['manifest']['correct_finite_wrap']=False
                elif mutation=='source':e['provenance']['prepared_files_sha256']['rnbo_source.h']='1'*64
                elif mutation=='runtime':e['provenance']['prepared_files_sha256']['common/RNBO_Types.h']='1'*64
                elif mutation=='contract':e['manifest']['scalar_powers_contract']['bit_identity_claimed']=True
                elif mutation=='profile':e['manifest']['numerical_profile']='float32-strict'
                elif mutation=='support':del e['provenance']['prepared_files_sha256']['rnbo_s3_scalar_powers_source.h']
                elif mutation=='compiler':m['compiler']['version']='other'
                elif mutation=='sdk':m['source_files_sha256']['module-sdk/dynamic/rnbo_s3_dynamic.cpp']='f'*64
                else:e['provenance']['adaptations'][-1]['inverse_byte_identity']=False
                self.rejected()

    def test_power_input_oracle_wirehash_and_rounding_records_required(self):
        original=list(self.lines)
        for mutation in ('input','wire','initial','missing','extra','duplicate','negative','too-many','zero-sign','sensitivity'):
            with self.subTest(mutation=mutation):
                self.lines=list(original);i=next(i for i,l in enumerate(self.lines) if 'CASE_ROUNDING' in l and 'case=dense-quarter ' in l)
                if mutation=='input':self.lines[1]=self.lines[1].replace('input_sha256=','input_sha256=a')
                elif mutation=='wire':self.lines[2]=self.lines[2].replace('event_schedule_sha256=','event_schedule_sha256=a')
                elif mutation=='initial':self.lines[2]=self.lines[2].replace('initial_exponent=2','initial_exponent=4')
                elif mutation=='missing':self.lines.pop(i)
                elif mutation=='extra':self.lines[i]+=' profile=strict'
                elif mutation=='duplicate':self.lines.insert(i,self.lines[i])
                elif mutation=='negative':self.lines[i]=self.lines[i].replace('float_bit_different=4','float_bit_different=-1')
                elif mutation=='too-many':self.lines[i]=self.lines[i].replace('float_bit_different=4','float_bit_different=786433')
                elif mutation=='zero-sign':self.lines[i]=self.lines[i].replace('zero_sign_different=1','zero_sign_different=5')
                else:self.lines[i]=self.lines[i].replace('zero_sign_different=1','zero_sign_different=0')
                self.rejected()

    def test_power_truth_and_pair_gates_not_widened(self):
        original=copy.deepcopy(self.report);lines=list(self.lines)
        for mutation in ('pair','truth','rounding','bits','budget'):
            with self.subTest(mutation=mutation):
                self.report=copy.deepcopy(original);self.lines=list(lines)
                if mutation=='pair':self.report['benchmark']['fixture']['comparison_tolerance']['maximum_pcm_lsb_error']=2
                elif mutation=='truth':
                    i=next(i for i,l in enumerate(self.lines) if 'CASE_SEMANTIC' in l)
                    self.lines[i]=self.lines[i].replace('max_abs=0','max_abs=3e-6').replace('max_model_error_bound=0','max_model_error_bound=3e-6')
                elif mutation=='rounding':self.lines[2]=self.lines[2].replace('rounding=once-float32','rounding=twice-float32')
                elif mutation=='bits':self.lines.insert(0,'RNBO_OBJECT_BENCHMARK CASE_BITS fixture=nonlinear-domains case=square')
                else:self.report['benchmark']['psram_budget']['oracle_cache_bytes']=0
                self.rejected()

    def test_rounding_diagnostics_not_accepted_in_legacy_kind(self):
        legacy=Wave2ObservationTests();legacy.setUp();self.addCleanup(legacy.doCleanups)
        legacy.fixture('nonlinear');legacy.lines.insert(0,'RNBO_OBJECT_BENCHMARK CASE_ROUNDING fixture=nonlinear-domains case=square samples=786432 float_bit_different=0 zero_sign_different=0')
        legacy.rejected()



class Wave4ObservationTests(unittest.TestCase):
    """Closed metadata, numerical-cache and protocol tests; no target execution."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.build=self.root/'build';self.run=self.root/'run'
        self.build.mkdir();self.run.mkdir();self.fixture()

    def fixture(self,identity='codebox-delta-state'):
        from wave4_contract import benchmark_fixture
        root=Path(__file__).resolve().parents[2];directory=root/'tests/fixtures/objects/wave4'
        catalog=json.loads((directory/'catalog.json').read_text());fixture=benchmark_fixture(catalog,directory,identity)
        pins=json.loads((directory/'identities.json').read_text());pin=WAVE4_IDENTITIES[identity];code=pin['model_code'];observer=1 if code==8 else 2
        runtime=pins['runtime_files_sha256'];manifest={'role':'fx','audio_inputs':2,'audio_outputs':2,'sample_rate':44100,'block_frames':256,
            'parameter_count':0,'parameter_schema_sha256':WAVE4_SCHEMA,'editable_source_sha256':pin['patch'],
            'numerical_profile':'float32-strict','scheduler_time':'float64','rnbo_version':'1.4.4','class_name':'rnbos3patch',
            'source_tree_sha256':pins['entries'][identity]['source_tree_sha256'],'voices':1,'voice_topology':'single-export',
            'required_host_services':[],'midi_output_ports':0,'adaptations':list(WAVE4_ADAPTATIONS)}
        plan={'fixture':fixture,'rounds':3,'blocks':64,'timing_exclude_blocks':32,'arena_bytes':4096,
              'catalog_path':'/synthetic/wave4/catalog.json','catalog_sha256':sha(directory/'catalog.json'),
              'patch_sha256':pin['patch'],'description_sha256':'d'*64,'parameter_schema':[],'events':[],
              'numerical_profiles':{'strict':'float32-strict','optimized':'float32-strict'},'stimuli':[],
              'verifications':[wave4_verification(fixture,c)for c in fixture['cases']]}
        budget={'workspace_bytes':266240,'oracle_cache_bytes':131072,'arena_bytes':8192,
            'opaque_context_upper_bound_bytes':2097152,'loaded_images_upper_bound_bytes':131072,
            'loader_heap_alignment_reserve_bytes':524288,'physical_psram_bytes':8388608}
        budget['required_upper_bound_bytes']=sum(v for k,v in budget.items()if k!='physical_psram_bytes');plan['psram_budget']=budget
        self.report={'board':'xiao','artifacts':{'build/app.elf':{'bytes':100,'sha256':'c'*64},'build/app.bin':{'bytes':100,'sha256':'d'*64}},
            'benchmark':plan,'modules':{side:{'artifact_sha256':'a'*64,'inspection':{'loaded_bytes_upper_bound':65536},
                'report':{'prepared_export':{'manifest':copy.deepcopy(manifest),'provenance':{'raw_files_sha256':{'rnbo_source.h':pin['source']}}},
                          'prepared_snapshot':{'prepared_files_sha256':{**runtime,'rnbo_source.h':pin['source']}}}}for side in ('strict','optimized')},
            'source_files_sha256':{f'object-benchmark/main/{name}':str(i)*64 for i,name in enumerate(('stimulus.c','stimulus.h','wave4_oracle.c','wave4_oracle.h'),1)}}
        self.lines=[f'RNBO_OBJECT_BENCHMARK NUMERICAL_PROFILES fixture={identity} reference=float32-strict candidate=float32-strict']
        samples=98304
        for case in fixture['cases']:
            name=case['id'];kind=WAVE4_INPUTS[name];ih,oh=wave4_cache_hashes(code,kind)
            plan['stimuli'].append({'kind':kind,'settings':{'kind':name},**{k:0. for k in ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')}})
            self.lines.append(f'RNBO_OBJECT_BENCHMARK INPUT fixture={identity} case={name} input_sha256={ih} input_bytes=131072 layout=float32_stereo_interleaved_le stimulus_kind={kind}')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK ORACLE fixture={identity} case={name} oracle_sha256={oh} oracle_bytes=131072 layout=float32_stereo_interleaved_le oracle_kind={WAVE4_KIND} max_abs_tolerance=0 max_cache_rounding_error=0 model=independent-binary32-operations-and-input-history rounding=once-binary32-per-output-operation model_code={code} observer_channel={observer}')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE fixture={identity} case={name} samples={samples} max_abs=0 rms_error=0 relative_rms=0 pcm_different=0 max_pcm_lsb=0')
            for side in ('strict','optimized'):
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_SEMANTIC fixture={identity} case={name} profile={side} semantic_kind={WAVE4_KIND} samples={samples} max_abs=0 max_model_error_bound=0 max_abs_tolerance=0 oracle_sha256={oh}')
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_WAVE4_BITS fixture={identity} case={name} profile={side} oracle_sha256={oh} samples={samples} bit_different=0 zero_sign_different=0 observer_samples={samples//2 if code==8 else 0} observer_bit_different=0')
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_PROFILE fixture={identity} case={name} profile={side} timed_blocks=96 process_us=960 peak_us=11')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_ROUNDING fixture={identity} case={name} samples={samples} float_bit_different=0 zero_sign_different=0')
        self.lines.append(f'RNBO_OBJECT_BENCHMARK PASS fixture={identity} firmware_elf_sha256='+('c'*64)+' strict_module_sha256='+('a'*64)+' optimized_module_sha256='+('a'*64)+
            f' host_heap_allocations=0 host_heap_frees=0 local_late_allocations=0 psram_before=123 psram_after=123 internal_before=42 internal_after=42 images=4 finalized_images=4 cases=3 rounds=3 blocks_per_pass=64 timing_exclude=32 warmup=4 seed=305419896 compared_samples=294912 input_cases=3 input_rechecks=27 pilot_sample_checks=0 oracle_cases=3 oracle_rechecks=27 semantic_sample_checks=589824 dc_sample_checks=0 oracle_bit_sample_checks=0 oracle_bit_differences=0 wave4_bit_sample_checks=589824 wave4_bit_differences=0 wave4_zero_sign_differences=0 observer_bit_sample_checks={294912 if code==8 else 0} observer_bit_differences=0')
        self.seal()

    def seal(self):
        (self.build/'build-report.json').write_text(json.dumps(self.report));log=self.run/'test-serial.log';log.write_text('\n'.join(self.lines)+'\n')
        (self.run/'hardware-test.json').write_text(json.dumps({'format':'rnbo-isolated-hardware-test','format_version':1,'board':'xiao','flash_bytes':8388608,'device_id':'ba:1e:48:12:34:56',
            'result':'passed','restoration':{'result':'restored','status':{'board':'XIAO ESP32-S3'}},
            'test_build_report_sha256':sha(self.build/'build-report.json'),'serial_log_sha256':sha(log),'pass_line':self.lines[-1],
            'test_elf_sha256':'c'*64,'test_app_sha256':'d'*64}))

    def change(self,prefix,old,new):
        index=next(i for i,line in enumerate(self.lines)if line.startswith('RNBO_OBJECT_BENCHMARK '+prefix+' '))
        self.lines[index]=self.lines[index].replace(old,new)

    def rejected(self):
        self.seal()
        with self.assertRaises(ValueError):collect(self.build,self.run)

    def test_all_thirteen_exact_surfaces_are_admitted_separately(self):
        for identity in WAVE4_IDENTITIES:
            with self.subTest(identity=identity):
                self.fixture(identity);result=collect(self.build,self.run)
                self.assertTrue(result['identical_artifact_control']);self.assertEqual(result['pass']['semantic_sample_checks'],589824)
                surface=result['stimulus_provenance']['surface_identity']
                self.assertFalse(surface['aliases_inherit_qualification'])
                self.assertEqual(surface['exact_entries'],self.report['benchmark']['fixture']['exact_entries'])
                self.assertEqual(result['pass']['observer_bit_sample_checks'],294912 if identity=='codebox-delta-state'else 0)

    def test_input_and_oracle_complete_bytes_match_independent_native_models(self):
        import importlib.util
        directory=Path(__file__).resolve().parents[2]/'tests/fixtures/objects/wave4'
        def module(name):
            spec=importlib.util.spec_from_file_location('test_wave4_'+name,directory/(name+'.py'));value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
        inputs=module('inputs');models=module('models')
        for name,kind in WAVE4_INPUTS.items():
            with self.subTest(input=name):
                left,right=inputs.generate(name,16384);raw=b''.join(struct.pack('<ff',a,b)for a,b in zip(left,right))
                self.assertEqual(wave4_input_bytes(kind),raw)
                for code,model in enumerate(WAVE4_MODELS,1):
                    expected,_=models.expected_outputs(model,left,right);wire=b''.join(struct.pack('<ff',a,b)for a,b in zip(*expected))
                    self.assertEqual(wave4_oracle_bytes(code,kind),wire,(name,model))

    def test_delta_vector_history_is_carried_and_wrong_reset_is_detectable(self):
        data=wave4_input_bytes(14);continuous=wave4_oracle_bytes(8,14);wrong=bytearray()
        for start in range(0,len(data),256*8):
            previous=0.0
            for x,y in struct.iter_unpack('<ff',data[start:start+256*8]):wrong.extend(struct.pack('<ff',x-previous,y));previous=x
        self.assertNotEqual(continuous,bytes(wrong))
        self.assertNotEqual(continuous[256*8:256*8+4],wrong[256*8:256*8+4])

    def test_mutated_input_and_oracle_hashes_rejected(self):
        for prefix,key in (('INPUT','input_sha256'),('ORACLE','oracle_sha256')):
            with self.subTest(prefix=prefix):
                self.fixture();index=next(i for i,line in enumerate(self.lines)if line.startswith('RNBO_OBJECT_BENCHMARK '+prefix+' '));old=fields(self.lines[index],'RNBO_OBJECT_BENCHMARK '+prefix+' ')[key]
                self.lines[index]=self.lines[index].replace(old,'f'*64);self.rejected()

    def test_original_surface_domain_model_and_event_metadata_cannot_change(self):
        for mutation in ('alias','entries','domain','surface','model','observer','events','case-order','seed','blocks','rounds','tolerance'):
            with self.subTest(mutation=mutation):
                self.fixture();plan=self.report['benchmark'];f=plan['fixture']
                if mutation=='alias':f['aliases_inherit_qualification']=True
                elif mutation=='entries':f['exact_entries']=['patcher:delta~']
                elif mutation=='domain':f['domain']['maximum']=2
                elif mutation=='surface':f['surface']='patcher'
                elif mutation=='model':f['verification']['model_code']=1
                elif mutation=='observer':f['verification']['observer_channel']=2
                elif mutation=='events':plan['events']=[{'block':0,'id':'x','index':0,'kind':1,'value':0}]
                elif mutation=='case-order':f['cases'].reverse()
                elif mutation=='seed':f['seed']=1
                elif mutation=='blocks':plan['blocks']=65
                elif mutation=='rounds':plan['rounds']=1
                else:f['comparison_tolerance']['maximum_absolute_error']=1e-20
                self.rejected()

    def test_module_source_runtime_schema_profile_and_control_are_pinned(self):
        for mutation in ('raw','prepared','runtime','schema','patch','params','profile','adaptation','different-image','services','source-tree','class','version'):
            with self.subTest(mutation=mutation):
                self.fixture();m=self.report['modules']['strict'];export=m['report']['prepared_export'];manifest=export['manifest']
                if mutation=='raw':export['provenance']['raw_files_sha256']['rnbo_source.h']='f'*64
                elif mutation=='prepared':m['report']['prepared_snapshot']['prepared_files_sha256']['rnbo_source.h']='f'*64
                elif mutation=='runtime':m['report']['prepared_snapshot']['prepared_files_sha256']['common/RNBO_Types.h']='f'*64
                elif mutation=='schema':manifest['parameter_schema_sha256']='f'*64
                elif mutation=='patch':manifest['editable_source_sha256']='f'*64
                elif mutation=='params':manifest['parameter_count']=1
                elif mutation=='profile':manifest['numerical_profile']='float32-audio-v1'
                elif mutation=='adaptation':manifest['adaptations'].append('unreviewed')
                elif mutation=='different-image':m['artifact_sha256']='b'*64
                elif mutation=='source-tree':manifest['source_tree_sha256']='f'*64
                elif mutation=='class':manifest['class_name']='other'
                elif mutation=='version':manifest['rnbo_version']='1.4.3'
                else:manifest['required_host_services']=['resource']
                self.rejected()

    def test_missing_partial_wrong_global_or_percase_bit_counters_rejected(self):
        for before,after in [(' wave4_bit_differences=0',''),('wave4_bit_sample_checks=589824','wave4_bit_sample_checks=1'),
                             ('wave4_zero_sign_differences=0','wave4_zero_sign_differences=1'),
                             ('observer_bit_sample_checks=294912','observer_bit_sample_checks=0'),
                             ('oracle_bit_sample_checks=0','oracle_bit_sample_checks=1')]:
            with self.subTest(before=before):
                self.fixture();self.lines[-1]=self.lines[-1].replace(before,after);self.rejected()

    def test_only_operation_signed_zero_bit_differences_are_permitted(self):
        self.fixture('minimum-alias-signal');self.change('CASE_WAVE4_BITS','bit_different=0 zero_sign_different=0','bit_different=1 zero_sign_different=1')
        self.lines[-1]=self.lines[-1].replace('wave4_bit_differences=0','wave4_bit_differences=1').replace('wave4_zero_sign_differences=0','wave4_zero_sign_differences=1');self.seal()
        r=collect(self.build,self.run);self.assertEqual(r['cases'][0]['wave4_bit_comparison']['strict']['zero_sign_different'],1)
        self.change('CASE_WAVE4_BITS','bit_different=1 zero_sign_different=1','bit_different=2 zero_sign_different=1');self.rejected()

    def test_observer_signed_zero_is_fatal_despite_zero_numerical_error(self):
        self.change('CASE_WAVE4_BITS','observer_bit_different=0','observer_bit_different=1');self.rejected()
        self.fixture();self.change('CASE_WAVE4_BITS','observer_samples=49152','observer_samples=0');self.rejected()

    def test_nonzero_tiny_model_error_cannot_be_hidden_by_pair_equality(self):
        self.change('CASE_SEMANTIC','max_abs=0 max_model_error_bound=0','max_abs=1.401298464324817e-45 max_model_error_bound=1.401298464324817e-45');self.rejected()

    def test_oracle_rounding_model_observer_and_closed_fieldset_are_exact(self):
        for before,after in [('max_cache_rounding_error=0','max_cache_rounding_error=1e-45'),
                             ('model_code=8','model_code=1'),('observer_channel=1','observer_channel=2'),
                             ('rounding=once-binary32-per-output-operation','rounding=once-float32'),
                             ('model=independent-binary32-operations-and-input-history','model=observed-output'),
                             ('observer_channel=1','observer_channel=1 extra=0')]:
            with self.subTest(before=before):
                self.fixture();self.change('ORACLE',before,after);self.rejected()

    def test_missing_duplicate_bit_rows_and_same_pair_rounding_differences_rejected(self):
        for mutation in ('missing-bits','duplicate-bits','missing-rounding','different-pair','missing-source','missing-budget'):
            with self.subTest(mutation=mutation):
                self.fixture();i=next(i for i,l in enumerate(self.lines)if ' CASE_WAVE4_BITS 'in l)
                if mutation=='missing-bits':self.lines.pop(i)
                elif mutation=='duplicate-bits':self.lines.insert(i,self.lines[i])
                elif mutation=='missing-rounding':self.lines=[l for l in self.lines if ' CASE_ROUNDING 'not in l]
                elif mutation=='different-pair':self.change('CASE_ROUNDING','float_bit_different=0 zero_sign_different=0','float_bit_different=1 zero_sign_different=1')
                elif mutation=='missing-source':del self.report['source_files_sha256']['object-benchmark/main/wave4_oracle.h']
                else:self.report['benchmark']['psram_budget']['oracle_cache_bytes']=0
                self.rejected()

    def test_legacy_modes_do_not_inherit_new_bit_or_observer_claims(self):
        legacy=ObservationTests('test_observed_case_cost_and_identity');legacy.setUp();self.addCleanup(legacy.doCleanups)
        original=list(legacy.lines);zero=' wave4_bit_sample_checks=0 wave4_bit_differences=0 wave4_zero_sign_differences=0 observer_bit_sample_checks=0 observer_bit_differences=0'
        legacy.lines[-1]+=zero;legacy.seal();collect(legacy.build,legacy.run)
        for extra in (' wave4_bit_differences=0',zero.replace('observer_bit_sample_checks=0','observer_bit_sample_checks=1')):
            legacy.lines=list(original);legacy.lines[-1]+=extra;legacy.seal()
            with self.assertRaises(ValueError):collect(legacy.build,legacy.run)
        legacy.lines=list(original);legacy.lines.insert(0,'RNBO_OBJECT_BENCHMARK CASE_WAVE4_BITS fixture=unit case=default profile=strict samples=1 bit_different=0 zero_sign_different=0 observer_samples=0 observer_bit_different=0 oracle_sha256='+('a'*64));legacy.seal()
        with self.assertRaises(ValueError):collect(legacy.build,legacy.run)

class GenHistoryObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.build=self.root/'build';self.run=self.root/'run'
        self.build.mkdir();self.run.mkdir();self.fixture()

    def fixture(self,identity='history-feedback'):
        directory=Path(__file__).resolve().parents[2]/'tests/fixtures/gen/target'
        catalog=json.loads((directory/'catalog.json').read_text())
        fixture=copy.deepcopy(next(f for f in catalog['fixtures']if f['id']==identity));fixture['family']='gen-history'
        runtime=json.loads((directory/'identities.json').read_text())['runtime_files_sha256'];pin=GEN_IDENTITIES[identity];code=GEN_MODELS[identity]
        manifest={'role':'fx','audio_inputs':2,'audio_outputs':2,'sample_rate':44100,'block_frames':256,'parameter_count':1,
            'parameter_schema_sha256':pin['schema'],'editable_source_sha256':pin['patch'],'source_tree_sha256':pin['source_tree'],
            'numerical_profile':'float32-strict','scheduler_time':'float64','rnbo_version':'1.4.4','class_name':'rnbos3patch',
            'voices':1,'voice_topology':'single-export','required_host_services':[],'midi_output_ports':0,'adaptations':list(WAVE4_ADAPTATIONS)}
        plan={'fixture':fixture,'rounds':3,'blocks':64,'timing_exclude_blocks':32,'arena_bytes':65536,
            'catalog_path':'/synthetic/gen/catalog.json','catalog_sha256':sha(directory/'catalog.json'),'patch_sha256':pin['patch'],
            'description_sha256':pin['description'],'parameter_schema':copy.deepcopy(GEN_SCHEMA),
            'events':[e for c in gen_cases()for e in gen_events(c)],'event_order':'stable-block-source-order-v1',
            'comparison_policy':{'pcm_gain':.25},'numerical_profiles':dict.fromkeys(('strict','optimized'),'float32-strict'),
            'stimuli':[{'kind':15,'settings':{'kind':GEN_INPUT},**dict.fromkeys(('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level'),0.)}for _ in fixture['cases']],
            'verifications':[gen_verification(fixture,c)for c in fixture['cases']]}
        budget={'workspace_bytes':266240,'oracle_cache_bytes':131072,'arena_bytes':131072,'opaque_context_upper_bound_bytes':2097152,
            'loaded_images_upper_bound_bytes':131072,'loader_heap_alignment_reserve_bytes':524288,'physical_psram_bytes':8388608}
        budget['required_upper_bound_bytes']=sum(v for k,v in budget.items()if k!='physical_psram_bytes');plan['psram_budget']=budget
        self.report={'board':'xiao','artifacts':{'build/app.elf':{'bytes':100,'sha256':'c'*64},'build/app.bin':{'bytes':100,'sha256':'d'*64}},
            'benchmark':plan,'modules':{side:{'artifact_sha256':'a'*64,'inspection':{'loaded_bytes_upper_bound':65536},
                'report':{'prepared_export':{'manifest':copy.deepcopy(manifest),'provenance':{'raw_files_sha256':{'rnbo_source.h':pin['source']}}},
                    'prepared_snapshot':{'prepared_files_sha256':{**runtime,'rnbo_source.h':pin['source']}}}}for side in ('strict','optimized')},
            'source_files_sha256':{f'object-benchmark/main/{name}':str(i)*64 for i,name in enumerate(('stimulus.c','stimulus.h','gen_history_oracle.c','gen_history_oracle.h'),1)}}
        self.lines=[f'RNBO_OBJECT_BENCHMARK NUMERICAL_PROFILES fixture={identity} reference=float32-strict candidate=float32-strict']
        samples=98304;total_events=total_witnesses=0
        for case,v in zip(fixture['cases'],plan['verifications']):
            name=case['id'];cache,mask,rounding=gen_cache_data(code,name);oh=hashlib.sha256(cache).hexdigest()
            events=len(case['events'])*3;witnesses=sum(mask)*3;total_events+=2*events;total_witnesses+=2*witnesses
            common=f'fixture={identity} case={name}';hashes=f'oracle_sha256={oh} event_schedule_sha256={v["event_schedule_sha256"]} reset_witness_sha256={v["reset_witness_sha256"]}'
            self.lines.append(f'RNBO_OBJECT_BENCHMARK INPUT {common} input_sha256={hashlib.sha256(gen_input_bytes()).hexdigest()} input_bytes=131072 layout=float32_stereo_interleaved_le stimulus_kind=15')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK ORACLE {common} oracle_sha256={oh} oracle_bytes=131072 layout=float32_stereo_interleaved_le oracle_kind={GEN_KIND} max_abs_tolerance=2e-6 max_cache_rounding_error={rounding:.17g} model=fresh-float64-input-convolution-or-integer-cycle rounding=once-float32 model_code={code} initial_epoch_frames=-1024 event_schedule_sha256={v["event_schedule_sha256"]} reset_witness_sha256={v["reset_witness_sha256"]} witness_minimum_separation=8e-6 model_tail_bound={v["model_tail_bound"]:.17g} model_evaluation_bound={v["model_evaluation_bound"]:.17g}')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE {common} samples={samples} max_abs=0 rms_error=0 relative_rms=0 pcm_different=0 max_pcm_lsb=0')
            bound=(rounding+v['model_tail_bound'])+v['model_evaluation_bound']
            for side in ('strict','optimized'):
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_SEMANTIC {common} profile={side} semantic_kind={GEN_KIND} samples={samples} max_abs=0 max_model_error_bound={bound:.17g} max_abs_tolerance=2e-6 oracle_sha256={oh}')
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_GEN_RESET {common} profile={side} {hashes} reset_events={events} witness_events={witnesses} witness_sample_checks={2*witnesses} witness_differences=0 max_abs=0 max_abs_tolerance=2e-6')
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_PROFILE {common} profile={side} timed_blocks=96 process_us=960 peak_us=11')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_ROUNDING {common} samples={samples} float_bit_different=0 zero_sign_different=0')
        self.lines.append(f'RNBO_OBJECT_BENCHMARK PASS fixture={identity} firmware_elf_sha256='+('c'*64)+' strict_module_sha256='+('a'*64)+' optimized_module_sha256='+('a'*64)+
            f' host_heap_allocations=0 host_heap_frees=0 local_late_allocations=0 psram_before=123 psram_after=123 internal_before=42 internal_after=42 images=4 finalized_images=4 cases=3 rounds=3 blocks_per_pass=64 timing_exclude=32 warmup=4 seed=305419896 compared_samples=294912 input_cases=3 input_rechecks=27 pilot_sample_checks=0 oracle_cases=3 oracle_rechecks=27 semantic_sample_checks=589824 dc_sample_checks=0 oracle_bit_sample_checks=0 oracle_bit_differences=0 gen_reset_events={total_events} gen_reset_witness_events={total_witnesses} gen_reset_witness_sample_checks={2*total_witnesses} gen_reset_witness_differences=0 pcm_gain=0.25')
        self.seal()

    def seal(self):
        (self.build/'build-report.json').write_text(json.dumps(self.report));log=self.run/'test-serial.log';log.write_text('\n'.join(self.lines)+'\n')
        (self.run/'hardware-test.json').write_text(json.dumps({'format':'rnbo-isolated-hardware-test','format_version':1,'board':'xiao','flash_bytes':8388608,'device_id':'ba:1e:48:12:34:56',
            'result':'passed','restoration':{'result':'restored','status':{'board':'XIAO ESP32-S3'}},'test_build_report_sha256':sha(self.build/'build-report.json'),
            'serial_log_sha256':sha(log),'pass_line':self.lines[-1],'test_elf_sha256':'c'*64,'test_app_sha256':'d'*64}))

    def feedback_comparison(self):
        self.fixture();plan=self.report['benchmark'];f=plan['fixture'];pin=GEN_IDENTITIES['history-feedback']
        f['qualification_mode']=GEN_FEEDBACK_MODE
        f['comparison_tolerance']={'maximum_absolute_error':2e-6,'maximum_pcm_lsb_error':1,'relative_rms_level_difference':1e-4}
        plan['catalog_sha256']=GEN_FEEDBACK_CATALOG_SHA
        plan['numerical_profiles']['optimized']=GEN_FEEDBACK_PROFILE
        plan['verifications']=[gen_verification(f,c)for c in f['cases']]
        for side in ('strict','optimized'):
            module=self.report['modules'][side];report=module['report'];provenance=report['prepared_export']['provenance']
            files=report['prepared_snapshot']['prepared_files_sha256']
            files.update({'patch_config.h':GEN_FEEDBACK_PIN['reference_config'],'description.json':pin['description'],
                          'source.rnbopat':pin['patch'],'generator.json':'5'*64,'RNBO-runtime-LICENSE':'6'*64})
            provenance['prepared_files_sha256']=copy.deepcopy(files);provenance['adaptations']=[]
            report.update(compiler={'version':'gcc14.2'},dependencies={'loader':'2.0.0'},private_support_archives={'libm':'7'*64},
                dynamic_abi={'major':1,'minor':0},state_policy={'caller_owned':True,'maximum_arena_bytes':65536},
                allocation_accounting={'allocator':'private-arena'},imports=[],
                source_files_sha256={'module-sdk/dynamic/rnbo_s3_dynamic.cpp':'8'*64,'module-sdk/cmake/dynamic/main/CMakeLists.txt':'9'*64})
        candidate=self.report['modules']['optimized'];candidate['artifact_sha256']='b'*64;r=candidate['report'];manifest=r['prepared_export']['manifest']
        manifest.update(numerical_profile=GEN_FEEDBACK_PROFILE,base_numerical_profile='float32-strict',
            numerical_identity='changed-rounding-float32-gen-feedback-v1',gen_feedback_contract=copy.deepcopy(GEN_FEEDBACK_CONTRACT))
        manifest['adaptations'].append('rnbo-1.4.4-float32-gen-feedback-v1')
        files=r['prepared_snapshot']['prepared_files_sha256'];files.update({'rnbo_source.h':GEN_FEEDBACK_PIN['source'],
            'patch_config.h':GEN_FEEDBACK_PIN['config'],'rnbo_s3_gen_feedback_source.h':GEN_FEEDBACK_PIN['compile_contract']})
        provenance=r['prepared_export']['provenance'];provenance['prepared_files_sha256']=copy.deepcopy(files)
        provenance['adaptations']=[{'name':'rnbo-1.4.4-float32-gen-feedback-v1','file':'rnbo_source.h','method':'gen_01_perform',
            'input_sha256':pin['source'],'prepared_sha256':GEN_FEEDBACK_PIN['source'],'input_method_sha256':GEN_FEEDBACK_PIN['input_method'],
            'prepared_method_sha256':GEN_FEEDBACK_PIN['prepared_method'],'inserted_bytes':1,'inverse_byte_identity':True,
            'input_map_sha256':GEN_FEEDBACK_PIN['input_map'],
            'runtime_tree_sha256':WAVE4_RUNTIME,'editable_source_sha256':pin['patch'],'description_file_sha256':pin['description'],
            'compile_contract_file':'rnbo_s3_gen_feedback_source.h','compile_contract_sha256':GEN_FEEDBACK_PIN['compile_contract'],
            'changed_rounding':True,'bit_identity_claimed':False,'scheduler_time_unchanged':True,'transformer_sha256':GEN_FEEDBACK_PIN['transformer']}]
        self.change('NUMERICAL_PROFILES','candidate=float32-strict','candidate='+GEN_FEEDBACK_PROFILE)
        self.change('PASS','optimized_module_sha256='+('a'*64),'optimized_module_sha256='+('b'*64));self.seal()

    def change(self,prefix,old,new,case=None):
        index=next(i for i,line in enumerate(self.lines)if line.startswith('RNBO_OBJECT_BENCHMARK '+prefix+' ')and(case is None or ' case='+case+' 'in line))
        self.lines[index]=self.lines[index].replace(old,new)

    def rejected(self):
        self.seal()
        with self.assertRaises(ValueError):collect(self.build,self.run)

    def test_three_exact_programs_reconcile_witness_totals(self):
        totals=[0,0,0]
        for identity in GEN_MODELS:
            self.fixture(identity);result=collect(self.build,self.run);p=result['pass']
            self.assertEqual(p['gen_reset_events'],420)
            self.assertEqual(p['gen_reset_witness_events'],0 if identity=='two-history-swap'else 414)
            for i,key in enumerate(('gen_reset_events','gen_reset_witness_events','gen_reset_witness_sample_checks')):totals[i]+=p[key]
            self.assertTrue(result['identical_artifact_control']);self.assertEqual(result['stimulus_provenance']['pcm_gain'],.25)
        self.assertEqual(totals,[1260,828,1656])

    def test_complete_input_oracles_and_witness_masks_match_separate_python_model(self):
        import importlib.util
        directory=Path(__file__).resolve().parents[2]/'tests/fixtures/gen/target'
        def module(name):
            spec=importlib.util.spec_from_file_location('independent_gen_'+name,directory/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
        inputs=module('inputs');models=module('models');self.assertEqual(gen_input_bytes(),inputs.interleaved())
        for code in GEN_MODELS.values():
            for case in gen_cases():
                with self.subTest(code=code,case=case['id']):
                    expected=models.expected_outputs(code,inputs.generate(16384),case['events'])
                    cache,mask,rounding=gen_cache_data(code,case['id'])
                    self.assertEqual(cache,models.cache_bytes(expected));self.assertEqual(mask,models.reset_witness_bytes(expected))
                    self.assertEqual(rounding,expected['maximum_cache_rounding_error'])
        self.assertEqual(struct.unpack_from('<ff',gen_cache_data(3,'continuous')[0]),(2.,3.))
        self.assertEqual(struct.unpack_from('<ff',gen_cache_data(3,'retrigger-every-block')[0]),(1.,2.))
        self.assertEqual(gen_cache_data(3,'boundary-resets')[1][31],0)
        self.assertEqual(gen_cache_data(1,'retrigger-every-block')[1][0],0)

    def test_unknown_normalized_reordered_or_mutated_schedule_fails_closed(self):
        for mutation in ('normalized','same-zero','missing','order','schema','bool-block','extra-case'):
            with self.subTest(mutation=mutation):
                self.fixture();p=self.report['benchmark'];f=p['fixture']
                if mutation=='normalized':f['cases'][1]['events'][0]['form']='normalized'
                elif mutation=='same-zero':f['cases'][1]['events'][0]['value']=0.
                elif mutation=='missing':p['events'].pop()
                elif mutation=='order':p['events'][0],p['events'][1]=p['events'][1],p['events'][0]
                elif mutation=='schema':p['parameter_schema'][0]['steps']=1
                elif mutation=='bool-block':f['cases'][1]['events'][0]['block']=True
                else:f['cases'].append(copy.deepcopy(f['cases'][0]))
                self.rejected()

    def test_all_source_schema_runtime_and_same_image_pins_are_required(self):
        for mutation in ('raw','prepared','runtime','schema','source-tree','module','profile','unknown-support'):
            with self.subTest(mutation=mutation):
                self.fixture();m=self.report['modules']['optimized'];mf=m['report']['prepared_export']['manifest']
                if mutation=='raw':m['report']['prepared_export']['provenance']['raw_files_sha256']['rnbo_source.h']='1'*64
                elif mutation=='prepared':m['report']['prepared_snapshot']['prepared_files_sha256']['rnbo_source.h']='1'*64
                elif mutation=='runtime':m['report']['prepared_snapshot']['prepared_files_sha256']['common/RNBO_Math.h']='1'*64
                elif mutation=='schema':mf['parameter_schema_sha256']='1'*64
                elif mutation=='source-tree':mf['source_tree_sha256']='1'*64
                elif mutation=='module':m['artifact_sha256']='b'*64
                elif mutation=='profile':mf['numerical_profile']='float32-audio-v1'
                else:mf['required_host_services']=['buffer']
                self.rejected()

    def test_full_input_oracle_schedule_mask_hashes_and_closed_fields_are_enforced(self):
        for prefix,before,after in [('INPUT','input_sha256=','input_sha256=0'),('ORACLE','oracle_sha256=','oracle_sha256=0'),
                ('ORACLE','event_schedule_sha256=','event_schedule_sha256=0'),('ORACLE','reset_witness_sha256=','reset_witness_sha256=0'),
                ('CASE_GEN_RESET','reset_witness_sha256=','reset_witness_sha256=0'),('CASE_GEN_RESET','event_schedule_sha256=','event_schedule_sha256=0'),
                ('ORACLE','model_code=1','model_code=2'),('ORACLE','initial_epoch_frames=-1024','initial_epoch_frames=0'),
                ('ORACLE','witness_minimum_separation=8e-6','witness_minimum_separation=4e-6'),('CASE_GEN_RESET','reset_events=0','reset_events=0 extra=0')]:
            with self.subTest(prefix=prefix,before=before):
                self.fixture();self.change(prefix,before,after);self.rejected()

    def test_tail_evaluation_cache_rounding_and_semantic_sum_cannot_be_removed_or_widened(self):
        for key in ('model_tail_bound','model_evaluation_bound','max_cache_rounding_error'):
            self.fixture();i=next(i for i,l in enumerate(self.lines)if ' ORACLE 'in l);record=fields(self.lines[i],'RNBO_OBJECT_BENCHMARK ORACLE ')
            old=next(t for t in self.lines[i].split()if t.startswith(key+'='));self.lines[i]=self.lines[i].replace(old,key+'=0')
            self.assertNotEqual(record[key],0);self.rejected()
        self.fixture();i=next(i for i,l in enumerate(self.lines)if ' CASE_SEMANTIC 'in l)
        old=next(t for t in self.lines[i].split()if t.startswith('max_model_error_bound='));self.lines[i]=self.lines[i].replace(old,'max_model_error_bound=0');self.rejected()
        self.fixture();self.change('CASE_SEMANTIC','max_abs=0','max_abs=3e-6');self.rejected()

    def test_witness_counts_errors_sample_coverage_and_pass_totals_are_exact(self):
        for prefix,before,after in [('CASE_GEN_RESET','reset_events=18','reset_events=17'),('CASE_GEN_RESET','witness_events=18','witness_events=17'),
                ('CASE_GEN_RESET','witness_sample_checks=36','witness_sample_checks=35'),('CASE_GEN_RESET','witness_differences=0','witness_differences=1'),
                ('CASE_GEN_RESET','max_abs=0','max_abs=3e-6'),('CASE_GEN_RESET','reset_events=18','reset_events=true'),
                ('PASS','gen_reset_events=420','gen_reset_events=419'),('PASS','gen_reset_witness_events=414','gen_reset_witness_events=0'),
                ('PASS','gen_reset_witness_sample_checks=828','gen_reset_witness_sample_checks=827'),('PASS','gen_reset_witness_differences=0','gen_reset_witness_differences=1')]:
            with self.subTest(before=before):
                self.fixture();self.change(prefix,before,after,'boundary-resets'if prefix=='CASE_GEN_RESET'else None);self.rejected()
        self.fixture('two-history-swap');self.change('CASE_GEN_RESET','witness_events=0','witness_events=1');self.rejected()
        self.fixture('two-history-swap');self.change('CASE_GEN_RESET','max_abs=0','max_abs=1e-8');self.rejected()

    def test_gain_missing_duplicate_witness_and_rounding_records_are_rejected(self):
        for mutation in ('pass-gain','plan-gain','missing-pass','partial-pass','missing-witness','duplicate-witness','missing-rounding','rounding-difference','missing-budget','missing-source'):
            with self.subTest(mutation=mutation):
                self.fixture()
                if mutation=='pass-gain':self.change('PASS','pcm_gain=0.25','pcm_gain=0.5')
                elif mutation=='plan-gain':self.report['benchmark']['comparison_policy']['pcm_gain']=.5
                elif mutation=='missing-pass':self.lines[-1]=self.lines[-1].replace(' pcm_gain=0.25','')
                elif mutation=='partial-pass':self.lines[-1]=self.lines[-1].replace(' gen_reset_events=420','')
                elif mutation=='missing-witness':self.lines.pop(next(i for i,l in enumerate(self.lines)if ' CASE_GEN_RESET 'in l))
                elif mutation=='duplicate-witness':self.lines.insert(0,next(l for l in self.lines if ' CASE_GEN_RESET 'in l))
                elif mutation=='missing-rounding':self.lines=[l for l in self.lines if ' CASE_ROUNDING 'not in l]
                elif mutation=='rounding-difference':self.change('CASE_ROUNDING','float_bit_different=0','float_bit_different=1')
                elif mutation=='missing-budget':del self.report['benchmark']['psram_budget']
                else:del self.report['source_files_sha256']['object-benchmark/main/gen_history_oracle.c']
                self.rejected()

    def test_legacy_cannot_claim_gen_witnesses_or_gain(self):
        legacy=ObservationTests('test_observed_case_cost_and_identity');legacy.setUp();self.addCleanup(legacy.doCleanups)
        original=list(legacy.lines)
        for extra in (' gen_reset_events=0',' pcm_gain=0.25'):
            legacy.lines=list(original);legacy.lines[-1]+=extra;legacy.seal()
            with self.assertRaises(ValueError):collect(legacy.build,legacy.run)
        legacy.lines=list(original);legacy.lines.insert(0,next(l for l in self.lines if ' CASE_GEN_RESET 'in l));legacy.seal()
        with self.assertRaises(ValueError):collect(legacy.build,legacy.run)

    def test_feedback_comparison_mode_does_not_widen_old_control_admission(self):
        f=self.report['benchmark']['fixture'];old=gen_verification(f,f['cases'][0])
        f['qualification_mode']=GEN_FEEDBACK_MODE
        with self.assertRaises(ValueError):gen_verification(f,f['cases'][0])
        f['comparison_tolerance']={'maximum_absolute_error':2e-6,'maximum_pcm_lsb_error':1,'relative_rms_level_difference':1e-4}
        self.assertEqual(gen_verification(f,f['cases'][0]),old)
        self.rejected()  # An old same-ELF/strict-strict record cannot become a performance pair by relabelling.
        for identity in ('two-history-swap','three-history-rotation'):
            self.fixture(identity);f=self.report['benchmark']['fixture'];f['qualification_mode']=GEN_FEEDBACK_MODE
            f['comparison_tolerance']={'maximum_absolute_error':2e-6,'maximum_pcm_lsb_error':1,'relative_rms_level_difference':1e-4}
            with self.assertRaises(ValueError):gen_verification(f,f['cases'][0])
        for mode in ('float32-feedback-comparison-v2',True,None):
            self.fixture();f=self.report['benchmark']['fixture'];f['qualification_mode']=mode
            with self.assertRaises(ValueError):gen_verification(f,f['cases'][0])

    def test_feedback_profile_pair_accepts_bounded_rounding_diagnostics_without_bit_identity(self):
        self.feedback_comparison()
        self.change('CASE_ROUNDING','float_bit_different=0 zero_sign_different=0','float_bit_different=1 zero_sign_different=1')
        self.seal();result=collect(self.build,self.run)
        self.assertFalse(result['identical_artifact_control']);self.assertEqual(result['qualification_mode'],GEN_FEEDBACK_MODE)
        self.assertEqual(result['numerical_profiles']['optimized'],GEN_FEEDBACK_PROFILE)
        self.assertEqual(result['cases'][0]['rounding_comparison']['float_bit_different'],1)
        self.assertEqual(result['pass']['gen_reset_witness_sample_checks'],828)
        self.assertIn('no universal bit identity',result['stimulus_provenance']['rounding_scope'])

    def test_feedback_profile_numeric_rounding_is_permitted_only_with_consistent_diagnostics(self):
        self.feedback_comparison()
        self.change('CASE_ROUNDING','float_bit_different=0 zero_sign_different=0','float_bit_different=2 zero_sign_different=1')
        self.rejected()
        self.change('CASE','max_abs=0','max_abs=1e-7')
        self.change('CASE','max_pcm_lsb=0','max_pcm_lsb=1')
        self.change('CASE','pcm_different=0','pcm_different=1')
        i=next(i for i,l in enumerate(self.lines)if ' CASE_SEMANTIC 'in l and ' profile=optimized 'in l)
        row=fields(self.lines[i],'RNBO_OBJECT_BENCHMARK CASE_SEMANTIC ')
        v=self.report['benchmark']['verifications'][0];rounding=gen_cache_data(1,'continuous')[2]
        bound=((1e-7+rounding)+v['model_tail_bound'])+v['model_evaluation_bound']
        old=next(t for t in self.lines[i].split()if t.startswith('max_model_error_bound='))
        self.lines[i]=self.lines[i].replace('max_abs=0','max_abs=1e-7').replace(old,'max_model_error_bound='+format(bound,'.17g'))
        self.seal();result=collect(self.build,self.run)
        self.assertEqual(result['cases'][0]['output_comparison']['max_abs'],1e-7)
        self.assertEqual(result['cases'][0]['output_comparison']['max_pcm_lsb'],1)
        self.change('CASE_ROUNDING','float_bit_different=2 zero_sign_different=1','float_bit_different=1 zero_sign_different=1');self.rejected()

    def test_feedback_profile_exact_source_contract_and_adaptation_are_pinned(self):
        for mutation in ('source','config','type-header','missing-adaptation','inverse','bytes','method','clock','transformer','contract','unrelated-file','provenance-disagrees','reference-profile'):
            with self.subTest(mutation=mutation):
                self.feedback_comparison();r=self.report['modules']['optimized']['report'];m=r['prepared_export']['manifest'];p=r['prepared_export']['provenance'];files=r['prepared_snapshot']['prepared_files_sha256'];a=p['adaptations'][0]
                if mutation=='source':files['rnbo_source.h']='1'*64
                elif mutation=='config':files['patch_config.h']='1'*64
                elif mutation=='type-header':files['rnbo_s3_gen_feedback_source.h']='1'*64
                elif mutation=='missing-adaptation':p['adaptations']=[]
                elif mutation=='inverse':a['inverse_byte_identity']=False
                elif mutation=='bytes':a['inserted_bytes']=2
                elif mutation=='method':a['prepared_method_sha256']='1'*64
                elif mutation=='clock':a['scheduler_time_unchanged']=False
                elif mutation=='transformer':a['transformer_sha256']='0'*64
                elif mutation=='contract':m['gen_feedback_contract']['bit_identity_claimed']=True
                elif mutation=='unrelated-file':files['unexpected.h']='1'*64;p['prepared_files_sha256']=copy.deepcopy(files)
                elif mutation=='provenance-disagrees':p['prepared_files_sha256']['generator.json']='1'*64
                else:self.report['modules']['strict']['report']['prepared_export']['manifest']['base_numerical_profile']='float32-strict'
                self.rejected()

    def test_feedback_pair_requires_matched_toolchain_sdk_and_memory_policy(self):
        for field in ('compiler','dependencies','private_support_archives','dynamic_abi','state_policy','allocation_accounting','source_files_sha256','imports'):
            with self.subTest(field=field):
                self.feedback_comparison();r=self.report['modules']['optimized']['report']
                if field=='imports':r[field]=['malloc']
                elif field=='source_files_sha256':r[field]['module-sdk/dynamic/rnbo_s3_dynamic.cpp']='1'*64
                else:r[field]['unreviewed']=True
                self.rejected()
        self.feedback_comparison();self.report['modules']['optimized']['artifact_sha256']='a'*64;self.rejected()

    def test_feedback_comparison_numerical_and_diagnostic_limits_are_not_widened(self):
        for mutation in ('absolute','pcm','rms','unknown-mode','case-error','semantic-error','witness-error','rounding-count','missing-rounding'):
            with self.subTest(mutation=mutation):
                self.feedback_comparison();f=self.report['benchmark']['fixture']
                if mutation=='absolute':f['comparison_tolerance']['maximum_absolute_error']=2.1e-6
                elif mutation=='pcm':f['comparison_tolerance']['maximum_pcm_lsb_error']=2
                elif mutation=='rms':f['comparison_tolerance']['relative_rms_level_difference']=1.1e-4
                elif mutation=='unknown-mode':f['qualification_mode']='float32-feedback-comparison-v2'
                elif mutation=='case-error':self.change('CASE','max_abs=0','max_abs=3e-6')
                elif mutation=='semantic-error':self.change('CASE_SEMANTIC','max_abs=0','max_abs=3e-6')
                elif mutation=='witness-error':self.change('CASE_GEN_RESET','max_abs=0','max_abs=3e-6','boundary-resets')
                elif mutation=='rounding-count':self.change('CASE_ROUNDING','float_bit_different=0 zero_sign_different=0','float_bit_different=1 zero_sign_different=2')
                else:self.lines=[l for l in self.lines if ' CASE_ROUNDING 'not in l]
                self.rejected()

class GenArithmeticObservationTests(unittest.TestCase):
    setUp=GenHistoryObservationTests.setUp
    seal=GenHistoryObservationTests.seal
    change=GenHistoryObservationTests.change
    rejected=GenHistoryObservationTests.rejected

    def fixture(self,identity='mul-infix'):
        directory=Path(__file__).resolve().parents[2]/'tests/fixtures/gen/arithmetic'
        catalog=json.loads((directory/'catalog.json').read_text());fixture=copy.deepcopy(next(f for f in catalog['fixtures']if f['id']==identity));fixture['family']='gen-arithmetic'
        pins=json.loads((directory/'identities.json').read_text());pin=GEN_ARITH_IDENTITIES[identity];code=GEN_ARITH_MODELS[identity]
        manifest={'role':'fx','audio_inputs':2,'audio_outputs':2,'sample_rate':44100,'block_frames':256,'parameter_count':0,
            'parameter_schema_sha256':pin['schema'],'editable_source_sha256':pin['patch'],'source_tree_sha256':pin['source_tree'],
            'numerical_profile':'float32-strict','scheduler_time':'float64','rnbo_version':'1.4.4','class_name':'rnbos3patch',
            'voices':1,'voice_topology':'single-export','required_host_services':[],'midi_output_ports':0,'adaptations':list(WAVE4_ADAPTATIONS)}
        plan={'fixture':fixture,'rounds':3,'blocks':64,'timing_exclude_blocks':32,'arena_bytes':4096,
            'catalog_path':'/synthetic/gen/arithmetic/catalog.json','catalog_sha256':sha(directory/'catalog.json'),
            'patch_sha256':pin['patch'],'description_sha256':pin['description'],'parameter_schema':[],'events':[],
            'comparison_policy':{'pcm_gain':.5},'numerical_profiles':dict.fromkeys(('strict','optimized'),'float32-strict'),
            'stimuli':[{'kind':kind,'settings':{'kind':name},**dict.fromkeys(('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level'),0.)}for name,kind in WAVE4_INPUTS.items()],
            'verifications':[gen_arith_verification(fixture,c)for c in fixture['cases']]}
        budget={'workspace_bytes':266240,'oracle_cache_bytes':131072,'arena_bytes':8192,'opaque_context_upper_bound_bytes':2097152,
            'loaded_images_upper_bound_bytes':131072,'loader_heap_alignment_reserve_bytes':524288,'physical_psram_bytes':8388608}
        budget['required_upper_bound_bytes']=sum(v for k,v in budget.items()if k!='physical_psram_bytes');plan['psram_budget']=budget
        self.report={'board':'xiao','artifacts':{'build/app.elf':{'bytes':100,'sha256':'c'*64},'build/app.bin':{'bytes':100,'sha256':'d'*64}},
            'benchmark':plan,'modules':{side:{'artifact_sha256':'a'*64,'inspection':{'loaded_bytes_upper_bound':65536},
                'report':{'imports':[],'prepared_export':{'manifest':copy.deepcopy(manifest),'provenance':{'raw_files_sha256':{'rnbo_source.h':pin['source']}}},
                    'prepared_snapshot':{'prepared_files_sha256':{**pins['runtime_files_sha256'],'rnbo_source.h':pin['source'],
                        'patch_config.h':'a0d544c36042ca826ec6cd9deb332b80b68346e0986d49af73b16f7fc5486d5b',
                        'description.json':pin['description'],'source.rnbopat':pin['patch'],'RNBO-runtime-LICENSE':'4'*64,'generator.json':'5'*64}}}}for side in ('strict','optimized')},
            'source_files_sha256':{f'object-benchmark/main/{name}':str(i)*64 for i,name in enumerate(('stimulus.c','stimulus.h','gen_arithmetic_oracle.c','gen_arithmetic_oracle.h'),1)}}
        self.lines=[f'RNBO_OBJECT_BENCHMARK NUMERICAL_PROFILES fixture={identity} reference=float32-strict candidate=float32-strict']
        for name,kind in WAVE4_INPUTS.items():
            common=f'fixture={identity} case={name}';ih=hashlib.sha256(wave4_input_bytes(kind)).hexdigest();oh=hashlib.sha256(gen_arith_oracle_bytes(code,kind)).hexdigest()
            self.lines.append(f'RNBO_OBJECT_BENCHMARK INPUT {common} input_sha256={ih} input_bytes=131072 layout=float32_stereo_interleaved_le stimulus_kind={kind}')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK ORACLE {common} oracle_sha256={oh} oracle_bytes=131072 layout=float32_stereo_interleaved_le oracle_kind={GEN_ARITH_KIND} max_abs_tolerance=0 max_cache_rounding_error=0 model=independent-binary32-operations rounding=once-binary32-per-output-operation model_code={code} observer_channel=2')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE {common} samples=98304 max_abs=0 rms_error=0 relative_rms=0 pcm_different=0 max_pcm_lsb=0')
            for side in ('strict','optimized'):
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_SEMANTIC {common} profile={side} semantic_kind={GEN_ARITH_KIND} samples=98304 max_abs=0 max_model_error_bound=0 max_abs_tolerance=0 oracle_sha256={oh}')
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_GEN_ARITH_BITS {common} profile={side} oracle_sha256={oh} samples=98304 bit_different=0 zero_sign_different=0')
                self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_PROFILE {common} profile={side} timed_blocks=96 process_us=960 peak_us=11')
            self.lines.append(f'RNBO_OBJECT_BENCHMARK CASE_ROUNDING {common} samples=98304 float_bit_different=0 zero_sign_different=0')
        self.lines.append(f'RNBO_OBJECT_BENCHMARK PASS fixture={identity} firmware_elf_sha256='+('c'*64)+' strict_module_sha256='+('a'*64)+' optimized_module_sha256='+('a'*64)+
            ' host_heap_allocations=0 host_heap_frees=0 local_late_allocations=0 psram_before=123 psram_after=123 internal_before=42 internal_after=42 images=4 finalized_images=4 cases=3 rounds=3 blocks_per_pass=64 timing_exclude=32 warmup=4 seed=305419896 compared_samples=294912 input_cases=3 input_rechecks=27 pilot_sample_checks=0 oracle_cases=3 oracle_rechecks=27 semantic_sample_checks=589824 dc_sample_checks=0 oracle_bit_sample_checks=0 oracle_bit_differences=0 gen_arith_bit_sample_checks=589824 gen_arith_bit_differences=0 gen_arith_zero_sign_differences=0')
        self.seal()

    def test_fifteen_exact_source_contexts_are_individually_admitted(self):
        self.assertEqual(len(GEN_ARITH_IDENTITIES),15)
        for identity in GEN_ARITH_MODELS:
            with self.subTest(identity=identity):
                self.fixture(identity);value=collect(self.build,self.run)
                self.assertTrue(value['identical_artifact_control']);self.assertEqual(value['pass']['gen_arith_bit_sample_checks'],589824)
                self.assertEqual(value['stimulus_provenance']['surface_identity']['exact_entries'],self.report['benchmark']['fixture']['exact_entries'])

    def test_complete_45_oracle_caches_match_independent_public_python_model(self):
        import importlib.util
        path=Path(__file__).resolve().parents[2]/'tests/fixtures/gen/arithmetic/models.py'
        spec=importlib.util.spec_from_file_location('independent_Gen_arithmetic_math',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        count=0
        for identity,code in GEN_ARITH_MODELS.items():
            for kind in WAVE4_INPUTS.values():
                with self.subTest(identity=identity,kind=kind):
                    pairs=list(struct.iter_unpack('<ff',wave4_input_bytes(kind)));planes=tuple(tuple(p[i]for p in pairs)for i in (0,1))
                    self.assertEqual(gen_arith_oracle_bytes(code,kind),m.cache_bytes(m.expected_outputs(code,planes)));count+=1
        self.assertEqual(count,45)
        for unsupported in (0,7,8,11,True):
            with self.assertRaises(ValueError):gen_arith_oracle_bytes(unsupported,12)

    def test_product_underflow_matches_independent_exact_rational_rounding(self):
        def rounded_magnitude(v):
            if not v:return 0
            def nearest(q):
                n,r=divmod(q.numerator,q.denominator)
                return n+int(2*r>q.denominator or 2*r==q.denominator and n%2)
            if v<Fraction(1,1<<126):return nearest(v*(1<<149))
            e=v.numerator.bit_length()-v.denominator.bit_length()
            if v<(Fraction(1<<e)if e>=0 else Fraction(1,1<<-e)):e-=1
            q=v/(Fraction(1<<(e-23))if e>=23 else Fraction(1,1<<(23-e)));n=nearest(q)
            if n==1<<24:n>>=1;e+=1
            return((e+127)<<23)|(n-(1<<23))
        words=(0,0x80000000,1,0x80000001,3,0x80000003,0x7fffff,0x807fffff,0x800000,0x3f000000,0xbf000000,0x3f000001,0x3f7fffff,0x3f800000)
        for a in words:
            for b in words:
                x,y=struct.unpack('<ff',struct.pack('<II',a,b));sign=(a^b)&0x80000000
                exact=abs(Fraction.from_float(x)*Fraction.from_float(y));want=sign|rounded_magnitude(exact)
                got=struct.unpack('<I',struct.pack('<f',x*y))[0];self.assertEqual(got,want,(hex(a),hex(b)))

    def test_source_names_schema_runtime_and_zero_import_control_cannot_be_forged(self):
        for mutation in ('name','surface','canonical','alias-inherits','model','state-model','param','event','raw','prepared','runtime','schema','different-ELF','optional-profile','imports'):
            with self.subTest(mutation=mutation):
                self.fixture();p=self.report['benchmark'];f=p['fixture'];r=self.report['modules']['optimized']['report'];m=r['prepared_export']['manifest']
                if mutation=='name':f['source']['exact_name']='mul'
                elif mutation=='surface':f['source']['surface']='codebox'
                elif mutation=='canonical':f['source']['canonical']='mult'
                elif mutation=='alias-inherits':f['aliases_inherit_qualification']=True
                elif mutation=='model':f['verification']['model_code']=9
                elif mutation=='state-model':f['verification']['model_code']=8
                elif mutation=='param':p['parameter_schema']=[{'paramId':'gain','index':0}]
                elif mutation=='event':p['events']=[{'block':0,'index':0,'kind':1,'value':1}]
                elif mutation=='raw':r['prepared_export']['provenance']['raw_files_sha256']['rnbo_source.h']='1'*64
                elif mutation=='prepared':r['prepared_snapshot']['prepared_files_sha256']['rnbo_source.h']='1'*64
                elif mutation=='runtime':r['prepared_snapshot']['prepared_files_sha256']['common/RNBO_Math.h']='1'*64
                elif mutation=='schema':m['parameter_schema_sha256']='1'*64
                elif mutation=='different-ELF':self.report['modules']['optimized']['artifact_sha256']='b'*64
                elif mutation=='optional-profile':m['numerical_profile']='float32-audio-v1'
                else:r['imports']=['malloc']
                self.rejected()

    def test_exact_numeric_model_input_and_cache_hashes_cannot_be_relaxed(self):
        for prefix,before,after in [('INPUT','input_sha256=','input_sha256=0'),('ORACLE','oracle_sha256=','oracle_sha256=0'),
            ('ORACLE','model_code=10','model_code=9'),('ORACLE','observer_channel=2','observer_channel=1'),
            ('ORACLE','max_abs_tolerance=0','max_abs_tolerance=1e-6'),('ORACLE','max_cache_rounding_error=0','max_cache_rounding_error=1e-45'),
            ('CASE_SEMANTIC','max_abs=0 max_model_error_bound=0','max_abs=1.401298464324817e-45 max_model_error_bound=1.401298464324817e-45'),
            ('ORACLE','model=independent-binary32-operations','model=generated-code'),
            ('ORACLE','observer_channel=2','observer_channel=2 extra=0')]:
            with self.subTest(prefix=prefix,before=before):
                self.fixture();self.change(prefix,before,after);self.rejected()
        for field in ('maximum_absolute_error','maximum_pcm_lsb_error','relative_rms_level_difference'):
            self.fixture();self.report['benchmark']['fixture']['comparison_tolerance'][field]=1;self.rejected()

    def test_operation_signed_zero_diagnostics_are_allowed_but_other_differences_fail(self):
        self.change('CASE_GEN_ARITH_BITS','bit_different=0 zero_sign_different=0','bit_different=1 zero_sign_different=1')
        self.change('PASS','gen_arith_bit_differences=0 gen_arith_zero_sign_differences=0','gen_arith_bit_differences=1 gen_arith_zero_sign_differences=1')
        self.seal();result=collect(self.build,self.run);self.assertEqual(result['pass']['gen_arith_bit_differences'],1)
        self.change('CASE_GEN_ARITH_BITS','bit_different=1 zero_sign_different=1','bit_different=2 zero_sign_different=1');self.rejected()

    def test_closed_bits_counters_no_observer_and_pair_rounding_are_required(self):
        for mutation in ('missing-bits','duplicate-bits','observer-field','bool-count','wrong-hash','missing-rounding','pair-bits','partial-pass','wrong-samples','wrong-totals','reset-fields','gain-field','budget','source'):
            with self.subTest(mutation=mutation):
                self.fixture();i=next(i for i,l in enumerate(self.lines)if ' CASE_GEN_ARITH_BITS 'in l)
                if mutation=='missing-bits':self.lines.pop(i)
                elif mutation=='duplicate-bits':self.lines.insert(i,self.lines[i])
                elif mutation=='observer-field':self.lines[i]+=' observer_samples=0'
                elif mutation=='bool-count':self.lines[i]=self.lines[i].replace('bit_different=0','bit_different=true')
                elif mutation=='wrong-hash':self.lines[i]=self.lines[i].replace('oracle_sha256=','oracle_sha256=0')
                elif mutation=='missing-rounding':self.lines=[l for l in self.lines if ' CASE_ROUNDING 'not in l]
                elif mutation=='pair-bits':self.change('CASE_ROUNDING','float_bit_different=0 zero_sign_different=0','float_bit_different=1 zero_sign_different=1')
                elif mutation=='partial-pass':self.change('PASS',' gen_arith_bit_differences=0','')
                elif mutation=='wrong-samples':self.change('PASS','gen_arith_bit_sample_checks=589824','gen_arith_bit_sample_checks=1')
                elif mutation=='wrong-totals':self.change('PASS','gen_arith_bit_differences=0','gen_arith_bit_differences=1')
                elif mutation=='reset-fields':self.lines[-1]+=' gen_reset_events=0'
                elif mutation=='gain-field':self.lines[-1]+=' pcm_gain=0.5'
                elif mutation=='budget':del self.report['benchmark']['psram_budget']
                else:del self.report['source_files_sha256']['object-benchmark/main/gen_arithmetic_oracle.h']
                self.rejected()

    def test_old_modes_keep_shape_and_cannot_inherit_gen_arithmetic_results(self):
        legacy=ObservationTests('test_observed_case_cost_and_identity');legacy.setUp();self.addCleanup(legacy.doCleanups)
        zero=' gen_arith_bit_sample_checks=0 gen_arith_bit_differences=0 gen_arith_zero_sign_differences=0';original=list(legacy.lines)
        legacy.lines[-1]+=zero;legacy.seal();collect(legacy.build,legacy.run)
        for extra in (' gen_arith_bit_differences=0',zero.replace('gen_arith_bit_sample_checks=0','gen_arith_bit_sample_checks=1')):
            legacy.lines=list(original);legacy.lines[-1]+=extra;legacy.seal()
            with self.assertRaises(ValueError):collect(legacy.build,legacy.run)
        legacy.lines=list(original);legacy.lines.insert(0,next(l for l in self.lines if ' CASE_GEN_ARITH_BITS 'in l));legacy.seal()
        with self.assertRaises(ValueError):collect(legacy.build,legacy.run)

if __name__=='__main__':unittest.main()
