# SPDX-License-Identifier: MIT
"""Prevent missing names, alias overclaims and unsupported performance numbers."""
import copy
import json
import hashlib
import tempfile
from pathlib import Path
import unittest

from build_object_status import ROOT,make_status,checked_measurements,pointer,checked_short_smoke,public_sources,checked_codebox_build_failure


class ObjectStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory=json.loads((ROOT/'site/data/inventory.json').read_text())
        cls.coverage=json.loads((ROOT/'site/data/coverage.json').read_text())

    def test_complete_spelling_inventory_and_separate_supplemental_surfaces(self):
        data=make_status(self.inventory,self.coverage)
        rows={r['id']:r for r in data['objects']}
        self.assertEqual(len(rows),1455)
        self.assertTrue({r['id'] for r in self.inventory['spellings']}<=rows.keys())
        self.assertEqual(sum(r['surface']=='patcher' for r in rows.values()),703)
        self.assertEqual(sum(r['surface']=='host' for r in rows.values()),7)
        self.assertIsNone(rows['codebox-reference:filtercoeff_op']['performance'])
        self.assertEqual(rows['codebox-reference:filtercoeff_op']['working']['status'],'unverified')

    def test_tested_alias_does_not_qualify_untested_canonical_or_codebox(self):
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertEqual(rows['patcher:noise~']['working']['status'],'board')
        self.assertEqual(rows['patcher:noise']['working']['status'],'unverified')
        self.assertEqual(rows['codebox:noise']['working']['status'],'unverified')
        self.assertEqual(rows['patcher:mtof']['working']['status'],'in_patch')
        self.assertEqual(rows['patcher:mtof~']['working']['status'],'board')
        self.assertIsNone(rows['patcher:noise~']['performance'])
        self.assertEqual(rows['patcher:average~']['working']['status'],'partial')

    def test_all_percentages_recompute_from_exact_raw_evidence_and_vectors(self):
        checked=checked_measurements(self.coverage,ROOT)
        self.assertEqual(len(checked),159)
        for measurement in checked.values():
            if measurement.get('cpu_time_change_measured',measurement['CPU_savings_claimed']):
                expected=100*(1-measurement['candidate_process_us']/measurement['reference_process_us'])
                self.assertAlmostEqual(measurement['cpu_time_saved_percent'],expected,places=10)
            else:self.assertIsNone(measurement['cpu_time_saved_percent'])

    def test_xiao_wave4_exact_entries_have_board_scope_and_no_control_gain(self):
        data=json.loads((ROOT/'evidence/xiao-wave4.json').read_text())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        identities={identity for observation in data['observations']
                    for identity in observation['exact_surface']['exact_entries']}
        self.assertEqual(len(identities),15)
        for identity in identities:
            row=rows[identity]
            self.assertEqual(row['working']['status'],'board')
            self.assertIn('XIAO ESP32-S3',row['working']['detail'])
            self.assertIsNone(row['performance'])
            self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertTrue(any(s['url'].endswith('/evidence/xiao-wave4.json') for s in row['sources']))
        # Explicit reset now has its own later hardware run; it is not inherited from next().
        self.assertEqual(rows['codebox-member:delta.reset']['working']['status'],'board')
        self.assertTrue(any(s['url'].endswith('/evidence/xiao-smoke-rnbo-codebox-members-part1.json')
                            for s in rows['codebox-member:delta.reset']['sources']))
        self.assertFalse(any(s['url'].endswith('/evidence/xiao-wave4.json')
                             for s in rows['codebox-member:delta.reset']['sources']))
        # Named add/sub calls now have their own later codebox execution;
        # their status is not inherited from Wave4's + and - expressions.
        for identity in ('codebox:add','codebox:sub'):
            self.assertEqual(rows[identity]['working']['status'],'board')
            self.assertTrue(any(s['url'].endswith('/evidence/xiao-smoke-rnbo-codebox.json')for s in rows[identity]['sources']))
            self.assertFalse(any(s['url'].endswith('/evidence/xiao-wave4.json')for s in rows[identity]['sources']))
        # abs now has its own later boundary-event execution, not inherited Wave4 coverage.
        self.assertEqual(rows['patcher:abs']['working']['status'],'board')
        self.assertTrue(any(s['url'].endswith('/evidence/xiao-smoke-rnbo-events.json')for s in rows['patcher:abs']['sources']))
        self.assertFalse(any(s['url'].endswith('/evidence/xiao-wave4.json')for s in rows['patcher:abs']['sources']))

    def test_actual_rnbo_short_smoke_adds_only_exact_scenarios_without_gains(self):
        source='evidence/xiao-smoke-rnbo-stateless.json';data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertEqual(data['summary']['executed'],36);self.assertEqual(data['summary']['passed'],36)
        self.assertGreaterEqual(len(self.coverage['objects']),92)
        for case in data['cases']:
            identity='patcher:'+case['exact_name'];row=rows[identity]
            observation=next(v for v in row['hardware_smoke']if v['case']==case['id'])
            self.assertEqual(observation['mean_us'],case['mean_us']);self.assertIsNone(observation['cpu_time_saved_percent'])
            self.assertIsNone(row['performance']);self.assertTrue(any(s['url'].endswith('/'+source)for s in row['sources']))
            if identity in ('patcher:+~','patcher:*~'):
                self.assertEqual(row['working']['status'],'in_patch');self.assertEqual(row['optimisation']['status'],'available')
            else:
                self.assertEqual(row['working']['label'],'Short hardware check')
                self.assertEqual(row['working']['test_level'],'short-functional-hardware-check')
                self.assertEqual(row['optimisation']['status'],'unassessed')

    def test_actual_signal_routing_preserves_numeric_differences_and_no_gain_claim(self):
        source='evidence/xiao-smoke-rnbo-signal-routing.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':1,'executed':20,
                                         'output_mismatches':0,'passed':20})
        for case in data['cases']:
            row=rows['patcher:'+case['exact_name']]
            observation=next(v for v in row['hardware_smoke']if v['case']==case['id'])
            self.assertEqual(row['working']['status'],'board')
            self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertIsNone(row['performance'])
            self.assertEqual(observation['input_words_sha256'],case['input_words_sha256'])
            self.assertEqual(observation['max_absolute_error'],case['max_absolute_error'])
            self.assertIsNone(observation['cpu_time_saved_percent'])
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),204800)
        self.assertEqual(sum(c['within_tolerance_differences']for c in data['cases']),10240)
        self.assertEqual(sum(c['zero_sign_differences']for c in data['cases']),3520)
        self.assertEqual({c['exact_name']for c in data['cases']if c['cpu_review_reasons']},{'cubicinterp~'})
        self.assertEqual(rows['patcher:gate']['working']['status'],'unverified')

    def test_dbtoa_experiment_uses_only_matched_target_times_and_keeps_precision_scope(self):
        data=json.loads((ROOT/'evidence/dbtoa-float32.json').read_bytes())
        raw=json.loads((ROOT/'evidence/xiao-smoke-dbtoa-f32-comparison.json').read_bytes())
        row={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}['patcher:dbtoa~']
        self.assertEqual(row['optimisation']['status'],'experimental')
        self.assertAlmostEqual(row['performance']['percent'],91.64116707737867)
        target=data['target'];self.assertEqual(target['samples_checked'],491520)
        self.assertFalse(target['pass']['direct_target_pairwise_outputs_checked'])
        self.assertEqual(raw['summary']['passed'],48)
        for case in [target['aggregate'],*target['cases']]:
            selected=raw['cases']if 'model'not in case else[c for c in raw['cases']if c['model']==case['model']]
            for phase,prefix in (('A','reference'),('B','candidate')):
                times=[t for c in selected if c['comparison_phase']==phase for t in c['times_us']]
                self.assertEqual(sum(times),case[prefix+'_process_us'])
                self.assertEqual(len(times),case[prefix+'_timed_vectors'])
            self.assertAlmostEqual(case['cpu_time_saved_percent'],100*(1-case['candidate_process_us']/case['reference_process_us']))
        self.assertIn('changed rounding',row['optimisation']['detail'])
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertIsNone(rows['codebox:dbtoa']['performance'])
        self.assertEqual(rows['codebox:dbtoa']['optimisation']['status'],'unassessed')

    def test_signal_state_followup_keeps_all_streams_and_documented_onoff_mismatch(self):
        data=json.loads((ROOT/'evidence/xiao-smoke-rnbo-signal-state-followup.json').read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':0,'executed':7,
                                         'output_mismatches':1,'passed':6})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),71680)
        for case in data['cases']:
            row=rows['patcher:'+case['exact_name']]
            self.assertIsNone(row['performance']);self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertEqual(row['working']['status'],'partial'if case['exact_name']=='onoff~'else'board')
            observation=next(c for c in row['hardware_smoke']if c['case']==case['id'])
            self.assertEqual(observation['expected_block_count'],20)
            self.assertEqual(observation['expected_stream_sha256'],case['expected_stream_sha256'])
            self.assertEqual(observation['numeric_mismatches'],case['numeric_mismatches'])
        for name in ('onepole_lin~','counter~','normalize~'):
            self.assertEqual(len(rows['patcher:'+name]['hardware_smoke']),2)
        onoff=next(c for c in data['cases']if c['exact_name']=='onoff~')
        self.assertEqual((onoff['first_mismatch_call'],onoff['first_mismatch_word']), (0,2))
        self.assertEqual(onoff['numeric_mismatches'],5120)
        self.assertIn('per-sample toggle',rows['patcher:onoff~']['working']['detail'])

    def test_character_partitions_qualify_exact_bare_names_and_raw_pilots_without_gains(self):
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']};names=set();samples=0
        for index,count in ((1,43),(2,42)):
            data=json.loads((ROOT/f'evidence/xiao-smoke-rnbo-character-constants-part{index}.json').read_bytes())
            self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':0,'executed':count,
                                             'output_mismatches':0,'passed':count})
            self.assertEqual(data['partition']['index'],index)
            for case in data['cases']:
                self.assertNotIn(case['exact_name'],names);names.add(case['exact_name'])
                row=rows['codebox:'+case['exact_name']]
                self.assertEqual(row['working']['status'],'board')
                self.assertEqual(row['optimisation']['status'],'unassessed');self.assertIsNone(row['performance'])
                observation=next(c for c in row['hardware_smoke']if c['case']==case['id'])
                self.assertEqual(observation['strict_zero_sign_channels'],2)
                self.assertEqual(observation['raw_pilot_channel'],1)
                self.assertEqual(observation['strict_zero_sign_mismatches'],0)
                self.assertEqual(case['bit_mismatches'],0);samples+=case['samples_checked']
        self.assertEqual(len(names),85);self.assertEqual(samples,870400)
        all_characters={r['spelling']for r in self.coverage['objects']if r['id'].startswith('codebox:CHAR_')}
        self.assertEqual(len(all_characters),95)

    def test_actual_numeric_smoke_keeps_mismatches_tolerances_and_cpu_review_visible(self):
        data=json.loads((ROOT/'evidence/xiao-smoke-rnbo-numeric.json').read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertGreaterEqual(len(self.coverage['objects']),123)
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':8,'executed':33,'output_mismatches':3,'passed':30})
        failed=set();reviewed=set()
        for case in data['cases']:
            identity='patcher:'+case['exact_name'];row=rows[identity]
            observation=next(v for v in row['hardware_smoke']if v['case']==case['id'])
            self.assertEqual(observation['numeric_mismatches'],case['numeric_mismatches'])
            self.assertEqual(observation['absolute_tolerance'],case['absolute_tolerance'])
            self.assertEqual(observation['input_words_sha256'],case['input_words_sha256'])
            self.assertIsNone(observation['cpu_time_saved_percent'])
            if case['status']=='output_mismatch':
                failed.add(case['exact_name']);self.assertEqual(row['working']['status'],'partial')
                self.assertEqual(row['working']['label'],'Short check / known gaps')
            if case['cpu_review_reasons']:reviewed.add(case['exact_name']);self.assertIn('flagged for later review',row['working']['detail'])
            if identity not in ('patcher:/~','patcher:pow~'):
                self.assertIsNone(row['performance']);self.assertEqual(row['optimisation']['status'],'unassessed')
        self.assertEqual(failed,{'round~','isdenorm~','fixdenorm~'})
        self.assertEqual(reviewed,{'exp2~','log~','ln~','log2~','log2f~','log10~','log1p~','pow~'})
        self.assertEqual(rows['patcher:/~']['working']['status'],'in_patch')
        self.assertEqual(rows['patcher:pow~']['working']['status'],'board')
        self.assertEqual(rows['patcher:pow~']['performance']['measurement_id'],'scalar-powers-composed-original:aggregate')
        self.assertEqual(next(v for v in rows['patcher:expm1~']['hardware_smoke']if v['case']=='expm1-signal')['within_tolerance_differences'],640)
        self.assertEqual(next(v for v in rows['patcher:pow~']['hardware_smoke']if v['case']=='power-signal')['within_tolerance_differences'],400)

    def test_actual_functions_smoke_retains_policy_memory_and_cpu_scope(self):
        source='evidence/xiao-smoke-rnbo-functions.json';data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertGreaterEqual(len(self.coverage['objects']),156)
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':11,'executed':35,'output_mismatches':1,'passed':34})
        reviewed=set()
        for case in data['cases']:
            row=rows['patcher:'+case['exact_name']]
            observation=next(v for v in row['hardware_smoke']if v['case']==case['id'])
            self.assertEqual(observation['arena_capacity'],1048576)
            self.assertEqual(observation['arena_high_water'],case['arena_high_water'])
            self.assertEqual(observation['absolute_tolerance'],case['absolute_tolerance'])
            self.assertIsNone(observation['cpu_time_saved_percent'])
            self.assertIn('Arena reserved 1,048,576 bytes',row['working']['detail'])
            self.assertTrue(any(s['url'].endswith('/'+source)for s in row['sources']))
            if case['cpu_review_reasons']:
                reviewed.add(case['exact_name'])
                self.assertIn('active CPU review queue',row['working']['detail'])
                self.assertTrue(any(s['url'].endswith('/docs/cpu-review-backlog.md')for s in row['sources']))
            if case['exact_name']not in('mtof~','tanh~','dbtoa~'):
                self.assertIsNone(row['performance']);self.assertEqual(row['optimisation']['status'],'unassessed')
                self.assertEqual(row['working']['status'],'partial'if case['exact_name']=='fasttan~'else'board')
        self.assertEqual(reviewed,{'tanh~','atan2~','sinh~','cosh~','asinh~','acosh~','atanh~','mtof~','ftom~','atodb~','dbtoa~'})
        self.assertEqual(rows['patcher:mtof~']['optimisation']['status'],'available')
        self.assertEqual(rows['patcher:tanh~']['optimisation']['status'],'none')
        self.assertEqual(rows['patcher:dbtoa~']['optimisation']['status'],'experimental')
        self.assertEqual(rows['patcher:dbtoa~']['performance']['measurement_id'],
                         'dbtoa-float32-signal-v1:aggregate')
        self.assertEqual(rows['patcher:mtof~']['working']['status'],'board')
        self.assertEqual(rows['patcher:tanh~']['working']['status'],'board')
        self.assertIn('high-water 262,416 bytes',rows['patcher:mtof~']['working']['detail'])
        self.assertIn('high-water 160 bytes',rows['patcher:ftom~']['working']['detail'])
        self.assertIn('14.659 ms median, exceeding the 5.805 ms block period',rows['patcher:dbtoa~']['working']['detail'])
        failed=rows['patcher:fasttan~']['working']
        self.assertEqual(failed['label'],'Short check / known gaps')
        self.assertIn('not a documented accuracy guarantee',failed['detail'])
        for name in('radtodeg~','RADTODEG~','degtorad~','DEGTORAD~'):
            self.assertIn('zero-input constant source, not a signal converter',rows['patcher:'+name]['working']['detail'])

    def test_actual_boundary_smoke_preserves_prior_states_and_exposes_event_scope(self):
        source='evidence/xiao-smoke-rnbo-events.json';data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertGreaterEqual(len(self.coverage['objects']),188)
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':0,'executed':35,'output_mismatches':0,'passed':35})
        self.assertEqual(sum(c['parameter_events_applied']for c in data['cases']),735)
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),358400)
        for case in data['cases']:
            row=rows['patcher:'+case['exact_name']];observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(observation['expected_block_count'],20)
            self.assertEqual(observation['expected_stream_sha256'],case['expected_stream_sha256'])
            self.assertEqual(observation['parameter_events_applied'],21)
            self.assertEqual(observation['event_total_us'],sum(e['event_us']for e in case['parameter_events']))
            self.assertEqual(observation['event_peak_us'],max(e['event_us']for e in case['parameter_events']))
            self.assertEqual(observation['strict_zero_sign_channels'],2)
            self.assertEqual(observation['strict_zero_sign_mismatches'],0)
            self.assertEqual(observation['absolute_tolerance'],0)
            self.assertIn('separate from callback times',row['working']['detail'])
            self.assertIn('no within-block timing or isolated-opcode cost',row['working']['detail'])
            self.assertIsNone(observation['cpu_time_saved_percent']);self.assertIsNone(row['performance'])
            self.assertTrue(any(s['url'].endswith('/'+source)for s in row['sources']))
            if case['exact_name']in('+','*','/'):
                self.assertEqual(row['working']['status'],'in_patch');self.assertEqual(row['optimisation']['status'],'unassessed')
            else:
                self.assertEqual(row['working']['label'],'Short hardware check');self.assertEqual(row['optimisation']['status'],'unassessed')
        self.assertIn('Cold operand fixed at 0',rows['patcher:or']['working']['detail'])
        self.assertIn('Cold operand fixed at 2',rows['patcher:add']['working']['detail'])
        for name in('minimum','min','maximum','max'):
            self.assertIn('Only value outlet0 is observed',rows['patcher:'+name]['working']['detail'])

    def test_extra_event_results_keep_all_five_failures_and_exact_spelling_scope(self):
        source='evidence/xiao-smoke-rnbo-events-extra.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':0,'executed':40,'output_mismatches':5,'passed':35})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),409600)
        self.assertEqual(sum(c['parameter_events_applied']for c in data['cases']),840)
        failed={'isdenorm','fixdenorm','rmod','!%','step'}
        self.assertEqual({c['exact_name']for c in data['cases']if c['status']=='output_mismatch'},failed)
        for case in data['cases']:
            row=rows['patcher:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(row['working']['status'],'partial'if case['exact_name']in failed else'board')
            self.assertTrue(row['board_evidence'])
            self.assertEqual(observation['numeric_mismatches'],case['numeric_mismatches'])
            self.assertEqual(observation['max_absolute_error'],case['max_absolute_error'])
            self.assertEqual(observation['absolute_tolerance'],0)
            self.assertEqual(observation['strict_zero_sign_channels'],2)
            self.assertEqual(observation['strict_zero_sign_mismatches'],0)
            self.assertEqual(observation['parameter_events_applied'],21)
            self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])
            self.assertTrue(any(s['url'].endswith('/'+source)for s in row['sources']))
        for name in ('rmod','!%'):
            observation=rows['patcher:'+name]['hardware_smoke'][0]
            self.assertEqual(observation['numeric_mismatches'],512)
            self.assertEqual(observation['max_absolute_error'],2**-24)
        self.assertIn('finite only',rows['patcher:isnan']['working']['detail'])
        self.assertIn('initial number-store value',rows['patcher:constant']['working']['detail'])
        # A later codebox scenario has its own retained mismatch, rather than
        # inheriting the event-object result above.
        self.assertEqual(rows['codebox:step']['working']['status'],'partial')
        self.assertTrue(any(s['url'].endswith('/evidence/xiao-smoke-rnbo-codebox-range.json')for s in rows['codebox:step']['sources']))
        self.assertFalse(any(s['url'].endswith('/'+source)for s in rows['codebox:step']['sources']))

    def test_constant_results_add_only_scoped_observations_and_preserve_sig_composition(self):
        source='evidence/xiao-smoke-rnbo-constants.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertGreaterEqual(len(self.coverage['objects']),248)
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':0,'executed':21,'output_mismatches':0,'passed':21})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),215040)
        for case in data['cases']:
            row=rows['patcher:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(observation['status'],'pass')
            self.assertEqual(observation['numeric_mismatches'],0)
            self.assertEqual(case['bit_mismatches'],0)
            self.assertEqual(observation['absolute_tolerance'],0)
            self.assertEqual(row['working']['status'],'in_patch'if case['exact_name']=='sig~'else'board')
            self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])
            self.assertTrue(any(s['url'].endswith('/'+source)for s in row['sources']))
        self.assertIn('explicit initial values',rows['patcher:sig~']['working']['detail'])
        self.assertIn('44,100 Hz',rows['patcher:samplerate~']['working']['detail'])
        self.assertIn('256-frame',rows['patcher:vectorsize~']['working']['detail'])

    def test_actual_codebox_smoke_separates_numeric_passes_and_nonexecuted_rejections(self):
        source='evidence/xiao-smoke-rnbo-codebox.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertEqual(data['summary'],{'admission_failures':1,'compile_failures':1,'cpu_review':0,'executed':43,'output_mismatches':0,'passed':43})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),440320)
        self.assertEqual(sum(c['zero_sign_differences']for c in data['cases']),2880)
        for case in data['cases']:
            row=rows['codebox:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(row['surface'],'codebox')
            self.assertEqual(row['working']['status'],'board')
            self.assertEqual(observation['numeric_mismatches'],0)
            self.assertEqual(observation['absolute_tolerance'],0)
            self.assertEqual(observation['codebox_source_sha256'],case['codebox_source_sha256'])
            self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])
        for name in ('mod','^^'):
            row=rows['codebox:'+name]
            self.assertEqual(row['working']['status'],'unverified')
            self.assertFalse(row['board_evidence'])
            self.assertNotIn('hardware_smoke',row)
            self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertIsNone(row['performance'])
            self.assertIn('not executed'if name=='mod'else'not compiled or executed',row['working']['detail'])
            self.assertTrue(any(s['url'].endswith('/'+source)for s in row['sources']))
        self.assertEqual(rows['codebox:%']['working']['status'],'board')
        self.assertEqual(rows['codebox:xor']['working']['status'],'board')
        self.assertEqual(rows['patcher:mod']['working']['status'],'board')
        # Explicit reset now has its own later hardware run; it is not inherited from next().
        self.assertEqual(rows['codebox-member:delta.reset']['working']['status'],'board')
        self.assertTrue(any(s['url'].endswith('/evidence/xiao-smoke-rnbo-codebox-members-part1.json')
                            for s in rows['codebox-member:delta.reset']['sources']))
        self.assertFalse(any(s['url'].endswith('/evidence/xiao-wave4.json')
                             for s in rows['codebox-member:delta.reset']['sources']))

    def test_actual_codebox_named_constants_are_bit_exact_without_syntax_inheritance(self):
        source='evidence/xiao-smoke-rnbo-codebox-constants.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertGreaterEqual(len(self.coverage['objects']),333)
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':0,'executed':40,'output_mismatches':0,'passed':40})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),409600)
        self.assertTrue({'CHAR_'+str(n)for n in range(10)}<={c['exact_name']for c in data['cases']})
        for case in data['cases']:
            row=rows['codebox:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(row['surface'],'codebox')
            self.assertEqual(row['working']['status'],'board')
            self.assertEqual(case['syntax'],'named-value')
            self.assertEqual(case['bit_mismatches'],0)
            self.assertEqual(case['zero_sign_differences'],0)
            self.assertEqual(observation['codebox_source_sha256'],case['codebox_source_sha256'])
            self.assertEqual(observation['absolute_tolerance'],0)
            self.assertIn('named-value syntax',row['working']['detail'])
            self.assertIn('Zero-argument calls',row['working']['detail'])
            self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertIsNone(row['performance'])

    def test_actual_codebox_numeric_retains_accuracy_failures_and_separate_cpu_queue(self):
        source='evidence/xiao-smoke-rnbo-codebox-numeric.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertGreaterEqual(len(self.coverage['objects']),376)
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':14,'executed':43,'output_mismatches':3,'passed':40})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),440320)
        self.assertEqual(sum(c['zero_sign_differences']for c in data['cases']),2780)
        failed={'round','isdenorm','fixdenorm'};reviewed=set()
        for case in data['cases']:
            row=rows['codebox:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(row['working']['status'],'partial'if case['exact_name']in failed else'board')
            self.assertTrue(row['board_evidence'])
            self.assertEqual(observation['numeric_mismatches'],case['numeric_mismatches'])
            self.assertEqual(observation['max_absolute_error'],case['max_absolute_error'])
            self.assertEqual(observation['absolute_tolerance'],case['absolute_tolerance'])
            self.assertEqual(observation['codebox_source_sha256'],case['codebox_source_sha256'])
            self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])
            self.assertTrue(any(s['url'].endswith('/'+source)for s in row['sources']))
            if case['cpu_review_reasons']:
                reviewed.add(case['exact_name'])
                self.assertIn('flagged for later review',row['working']['detail'])
                self.assertTrue(any(s['url'].endswith('/docs/cpu-review-backlog.md')for s in row['sources']))
        self.assertEqual(reviewed,{'exp2','log','ln','log2','log10','log1p','pow','tanh','atan2','sinh','cosh','asinh','acosh','atanh'})
        self.assertEqual(rows['codebox:isdenorm']['hardware_smoke'][0]['max_absolute_error'],2147483648.)
        self.assertEqual(rows['codebox:round']['hardware_smoke'][0]['absolute_tolerance'],0)
        self.assertIn('finite inputs only',rows['codebox:isnan']['working']['detail'])
        self.assertEqual(rows['codebox:mod']['working']['status'],'unverified')
        self.assertEqual(rows['codebox:^^']['working']['status'],'unverified')

    def test_actual_codebox_range_separates_valid_instances_from_rejected_calls(self):
        source='evidence/xiao-smoke-rnbo-codebox-range.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        raw={r['id']:r for r in self.coverage['objects']}
        self.assertGreaterEqual(len(raw),421)
        self.assertEqual(data['summary'],{'admission_failures':3,'compile_failures':4,'cpu_review':6,'executed':40,'output_mismatches':4,'passed':36})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),409600)
        self.assertEqual(sum(c['zero_sign_differences']for c in data['cases']),2600)
        failed={'step','fastpow','fastexp','fasttan'};reviewed=set()
        for case in data['cases']:
            row=rows['codebox:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(row['working']['status'],'partial'if case['exact_name']in failed else'board')
            self.assertTrue(row['board_evidence'])
            self.assertEqual(observation['numeric_mismatches'],case['numeric_mismatches'])
            self.assertEqual(observation['absolute_tolerance'],case['absolute_tolerance'])
            self.assertEqual(observation['codebox_source_sha256'],case['codebox_source_sha256'])
            self.assertEqual(observation['arena_capacity'],1048576)
            self.assertEqual(observation['arena_high_water'],262256 if case['exact_name']=='mtof'else 0)
            self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])
            self.assertFalse(any(s['url'].endswith('/evidence/xiao-smoke-gen-range.json')for s in row['sources']))
            if case['cpu_review_reasons']:reviewed.add(case['exact_name'])
        self.assertEqual(reviewed,{'log2f','atodb','dbtoa','t60','mtof','ftom'})
        for name in('mtof','ftom'):
            record=raw['codebox:'+name];row=rows[record['id']]
            observations=row['hardware_smoke']
            self.assertEqual(len(observations),1)
            self.assertEqual(observations[0]['case'],name+'-stateful-next')
            self.assertIn('.next(input, 440)',record['working_note'])
            self.assertTrue(any('separate direct '+name in gap for gap in record['known_gaps']))
            self.assertFalse(any(q.get('evidence_kind')=='rnbo-codebox-build-failure'for q in record['qualification']))
        for name in('rdiv','rmod','rsub','rminus','switch'):
            row=rows['codebox:'+name];record=raw[row['id']]
            self.assertEqual(row['working']['status'],'unverified')
            self.assertFalse(row['board_evidence']);self.assertFalse(row.get('hardware_smoke'))
            self.assertIsNone(row['performance'])
            self.assertEqual(record['qualification'][0]['evidence_kind'],'rnbo-codebox-build-failure')
        self.assertIn('not a documented accuracy guarantee',rows['codebox:fastpow']['working']['detail'])
        self.assertEqual(rows['codebox:step']['hardware_smoke'][0]['absolute_tolerance'],0)

    def test_actual_codebox_shaping_retains_curve_limits_and_callback_cpu_scope(self):
        source='evidence/xiao-smoke-rnbo-codebox-shaping.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':18,'executed':40,'output_mismatches':2,'passed':38})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),409600)
        failed={'ease_in_bounce','ease_out_bounce'};reviewed=set()
        for case in data['cases']:
            row=rows['codebox:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(row['working']['status'],'partial'if case['exact_name']in failed else'board')
            self.assertEqual(observation['absolute_tolerance'],case['absolute_tolerance'])
            self.assertEqual(observation['numeric_mismatches'],case['numeric_mismatches'])
            self.assertEqual(observation['codebox_source_sha256'],case['codebox_source_sha256'])
            self.assertEqual(case['arena_high_water'],0)
            self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])
            self.assertEqual(row['optimisation']['status'],'unassessed')
            if case['cpu_review_reasons']:
                reviewed.add(case['exact_name']);self.assertEqual(case['status'],'pass')
                self.assertTrue(any(s['url'].endswith('/docs/cpu-review-backlog.md')for s in row['sources']))
        self.assertEqual(len(reviewed),18)
        for name in failed:
            observation=rows['codebox:'+name]['hardware_smoke'][0]
            self.assertEqual(observation['numeric_mismatches'],320)
            self.assertLess(observation['absolute_tolerance'],2.01e-6)
            self.assertEqual(observation['max_absolute_error'],2.4437904357910156e-6)
        self.assertIn('not a documented universal error guarantee',rows['codebox:cosineinterp']['working']['detail'])
        self.assertEqual(rows['codebox:imod']['hardware_smoke'][0]['absolute_tolerance'],0)
        # The later configured class API has its own evidence; it is not
        # inherited from these separately named easing functions.
        self.assertEqual(rows['codebox:ease']['working']['status'],'board')
        self.assertTrue(any(q['url'].endswith('/evidence/xiao-smoke-rnbo-codebox-misc.json')for q in rows['codebox:ease']['sources']))
        self.assertFalse(any(q['url'].endswith('/'+source)for q in rows['codebox:ease']['sources']))

    def test_actual_codebox_stateful_uses_full_stream_and_only_executed_counter_source(self):
        source='evidence/xiao-smoke-rnbo-codebox-stateful.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        raw={r['id']:r for r in self.coverage['objects']}
        self.assertGreaterEqual(len(raw),473)
        self.assertEqual(data['summary'],{'admission_failures':1,'compile_failures':1,'cpu_review':0,'executed':11,'output_mismatches':1,'passed':10})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),112640)
        self.assertEqual(sum(c['zero_sign_differences']for c in data['cases']),640)
        for case in data['cases']:
            row=rows['codebox:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(row['working']['status'],'partial'if case['exact_name']=='downsamp'else'board')
            self.assertEqual(observation['expected_block_count'],20)
            self.assertEqual(observation['expected_stream_sha256'],case['expected_stream_sha256'])
            self.assertEqual(observation['expected_stream_policy'],data['expected_stream_policy'])
            self.assertEqual(observation['numeric_mismatches'],case['numeric_mismatches'])
            self.assertEqual(observation['codebox_source_sha256'],case['codebox_source_sha256'])
            self.assertEqual(observation['cpu_review_reasons'],[])
            self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])
        self.assertEqual(rows['codebox:counter']['hardware_smoke'][0]['case'],'counter-input-stateful')
        self.assertTrue(any('port validation' in gap for gap in raw['codebox:counter']['known_gaps']))
        self.assertFalse(any(q.get('evidence_kind')=='rnbo-codebox-build-failure'for q in raw['codebox:counter']['qualification']))
        self.assertEqual(rows['codebox:downsamp']['hardware_smoke'][0]['numeric_mismatches'],7290)
        self.assertEqual(rows['codebox:downsamp']['hardware_smoke'][0]['absolute_tolerance'],0)
        history=rows['codebox:history']
        self.assertEqual(history['working']['status'],'unverified')
        self.assertFalse(history['board_evidence']);self.assertFalse(history.get('hardware_smoke'))
        self.assertEqual(raw['codebox:history']['qualification'][0]['evidence_kind'],'rnbo-codebox-build-failure')
        self.assertTrue(all('gen-'not in q['source']for q in raw['codebox:history']['qualification']))

    def test_actual_signal_range_keeps_exact_surface_quality_limits_and_cpu_queue(self):
        source='evidence/xiao-smoke-rnbo-signal-range.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':6,'executed':37,'output_mismatches':3,'passed':34})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),378880)
        failed={'step~','fastpow~','fastexp~'};reviewed=set()
        for case in data['cases']:
            row=rows['patcher:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(row['working']['status'],'partial'if case['exact_name']in failed else'board')
            self.assertEqual(observation['numeric_mismatches'],case['numeric_mismatches'])
            self.assertEqual(observation['absolute_tolerance'],case['absolute_tolerance'])
            self.assertEqual(observation['input_words_sha256'],case['input_words_sha256'])
            self.assertTrue(any(q['url'].endswith('/'+source)for q in row['sources']))
            self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])
            self.assertEqual(row['optimisation']['status'],'unassessed')
            if case['cpu_review_reasons']:reviewed.add(case['exact_name']);self.assertEqual(case['status'],'pass')
        self.assertEqual(reviewed,{'cosineinterp~','hann~','hamming~','blackman~','t60~','triangle~'})
        self.assertEqual(rows['patcher:step~']['hardware_smoke'][0]['absolute_tolerance'],0)
        self.assertIn('not a documented accuracy guarantee',rows['patcher:fastpow~']['working']['detail'])
        self.assertFalse(any(q['url'].endswith('/'+source)for q in rows['codebox:step']['sources']))
        self.assertEqual(rows['patcher:quantize~']['hardware_smoke'][0]['absolute_tolerance'],0)

    def test_actual_codebox_filters_bind_stream_and_reserved_vs_measured_resources(self):
        source='evidence/xiao-smoke-rnbo-codebox-filters.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertGreaterEqual(len(self.coverage['objects']),522)
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':5,'executed':12,'output_mismatches':0,'passed':12})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),122880)
        self.assertEqual(sum(c['zero_sign_differences']for c in data['cases']),320)
        high_water={'delay':524352,'comb':1048704,'allpass':1048704,
                    'average':705760,'average_absolute':705760,'average_rms':705760}
        reviewed=set()
        for case in data['cases']:
            row=rows['codebox:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(row['working']['status'],'board')
            self.assertEqual(observation['expected_block_count'],20)
            self.assertEqual(observation['expected_stream_sha256'],case['expected_stream_sha256'])
            self.assertEqual(observation['expected_stream_policy'],data['expected_stream_policy'])
            self.assertEqual(observation['arena_capacity'],2097152)
            self.assertEqual(observation['arena_high_water'],high_water.get(case['exact_name'],0))
            self.assertEqual(observation['numeric_mismatches'],0)
            self.assertEqual(observation['codebox_source_sha256'],case['codebox_source_sha256'])
            self.assertEqual(row['optimisation']['status'],'unassessed')
            self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])
            if case['cpu_review_reasons']:reviewed.add(case['exact_name'])
        self.assertEqual(reviewed,{'comb','allpass','average','average_absolute','average_rms'})
        self.assertIn('No independently enforced raw-word',rows['codebox:comb']['working']['detail'])
        self.assertEqual(rows['patcher:onepole~']['working']['status'],'partial')
        self.assertFalse(any(q['url'].endswith('/'+source)for q in rows['patcher:onepole~']['sources']))

    def test_signal_stateful_appends_xiao_scope_without_erasing_broader_native_failure(self):
        source='evidence/xiao-smoke-rnbo-signal-stateful.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':2,'executed':15,'output_mismatches':1,'passed':14})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),153600)
        reviewed=set()
        for case in data['cases']:
            row=rows['patcher:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            expected='partial'if case['exact_name']in('downsamp~','slide~')else'board'
            self.assertEqual(row['working']['status'],expected);self.assertTrue(row['board_evidence'])
            self.assertEqual(observation['status'],case['status'])
            self.assertEqual(observation['expected_block_count'],20)
            self.assertEqual(observation['expected_stream_sha256'],case['expected_stream_sha256'])
            self.assertEqual(observation['arena_capacity'],1048576)
            self.assertEqual(observation['arena_high_water'],705760 if case['exact_name'].startswith('average_')else 0)
            self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])
            if case['cpu_review_reasons']:reviewed.add(case['exact_name'])
        self.assertEqual(reviewed,{'average_absolute~','average_rms~'})
        slide=rows['patcher:slide~']
        self.assertEqual(slide['working']['label'],'Partial / known gaps')
        self.assertIn('long signed-rate',slide['working']['detail'])
        self.assertEqual(slide['hardware_smoke'][0]['status'],'pass')
        self.assertEqual(slide['optimisation']['status'],'none')
        for name in('delta~','sah~','slide~'):
            row=rows['patcher:'+name]
            for evidence in('wave3-stateful.json','xiao-smoke-rnbo-signal-stateful.json'):
                self.assertTrue(any(q['url'].endswith('/evidence/'+evidence)for q in row['sources']))
        self.assertEqual(rows['patcher:sah']['working']['status'],'unverified')
        self.assertEqual(rows['patcher:downsamp~']['hardware_smoke'][0]['numeric_mismatches'],7290)
        self.assertIn('phase-policy',rows['patcher:downsamp~']['working']['detail'])

    def test_misc_codebox_keeps_pointwise_class_options_and_bounded_numeric_scope(self):
        source='evidence/xiao-smoke-rnbo-codebox-misc.json'
        data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertGreaterEqual(len(self.coverage['objects']),556)
        self.assertEqual(data['summary'],{'compile_failures':0,'cpu_review':3,'executed':22,'output_mismatches':0,'passed':22})
        self.assertEqual(sum(c['samples_checked']for c in data['cases']),225280)
        reviewed=set()
        for case in data['cases']:
            row=rows['codebox:'+case['exact_name']]
            observation=next(o for o in row['hardware_smoke']if o['case']==case['id'])
            self.assertEqual(row['working']['status'],'board')
            self.assertEqual(observation['absolute_tolerance'],case['absolute_tolerance'])
            self.assertEqual(observation['codebox_source_sha256'],case['codebox_source_sha256'])
            self.assertEqual(observation['numeric_mismatches'],0)
            self.assertEqual(case['arena_high_water'],0)
            self.assertEqual(row['optimisation']['status'],'unassessed');self.assertIsNone(row['performance'])
            if case['cpu_review_reasons']:reviewed.add(case['exact_name'])
        self.assertEqual(reviewed,{'safepow','cubicinterp','easexfade'})
        self.assertIn('syncupdate 0',rows['codebox:ease']['working']['detail'])
        self.assertIn('pointwise',rows['codebox:easexfade']['working']['detail'])
        self.assertIn('bare named-value',rows['codebox:number_max']['working']['detail'])
        self.assertEqual(rows['codebox:number_max']['hardware_smoke'][0]['max_absolute_error'],0)

    def test_xiao_source_selector_cannot_qualify_an_unexecuted_alias_or_program(self):
        forged=copy.deepcopy(self.coverage)
        record=next(r for r in forged['objects'] if r['id']=='patcher:min~')
        qualification=next(q for q in record['qualification'] if q.get('evidence_kind')=='xiao-wave4-model-output')
        qualification['selector']='/observations/0'
        with self.assertRaisesRegex(ValueError,'exact source/surface'):
            make_status(self.inventory,forged)

    def test_power_primary_uses_composed_reference_and_fallbacks_claim_no_gain(self):
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        row=rows['patcher:pow~']
        self.assertEqual(row['optimisation']['status'],'available')
        self.assertEqual(row['performance']['measurement_id'],'scalar-powers-composed-original:aggregate')
        self.assertAlmostEqual(row['performance']['percent'],24.10277964828581)
        fallback=[m for m in self.coverage['measurements'] if m.get('observation_class')=='unchanged-powf-fallback-workload']
        self.assertEqual(len(fallback),7)
        self.assertTrue(all(m['cpu_time_saved_percent'] is None and not m['CPU_savings_claimed'] for m in fallback))
        forged=copy.deepcopy(self.coverage)
        control=next(m for m in forged['measurements'] if m['id']==fallback[0]['id'])
        control['CPU_savings_claimed']=True
        with self.assertRaisesRegex(ValueError,'Controls must have no savings claim'):checked_measurements(forged,ROOT)

    def test_train_controls_and_limitations_are_not_transferred_to_phasor(self):
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        row=rows['patcher:train~']
        self.assertEqual(row['working']['status'],'partial')
        self.assertEqual(row['optimisation']['status'],'available')
        self.assertEqual(row['performance']['measurement_id'],'train-scalar-reciprocal-private:aggregate')
        self.assertAlmostEqual(row['performance']['percent'],39.05835132291203)
        self.assertIn('zero-width: control (no gain claimed)',row['performance']['detail'])
        self.assertIn('full-width: control (no gain claimed)',row['performance']['detail'])
        self.assertIsNone(rows['patcher:phasor~']['performance'])
        self.assertEqual(rows['patcher:phasor~']['optimisation']['status'],'none')
        forged=copy.deepcopy(self.coverage)
        control=next(m for m in forged['measurements'] if m['id']=='train-scalar-reciprocal-private:zero-width')
        control['CPU_savings_claimed']=True
        with self.assertRaisesRegex(ValueError,'Controls must have no savings claim'):checked_measurements(forged,ROOT)

    def test_train_public_option_requires_the_saved_pair_and_admission(self):
        record=next(r for r in self.coverage['objects'] if r['id']=='patcher:train~')
        option=next(o for o in record['optimisations'] if o['id']=='train-scalar-reciprocal-hoist-private')
        self.assertEqual(option['flag'],'--hoist-train-reciprocal')
        self.assertEqual(option['state'],'available')
        self.assertTrue(any('duty check fails' in gap for gap in record['known_gaps']))
        group=next(g for g in self.coverage['measurement_groups'] if g['id']=='train-scalar-reciprocal-private')
        self.assertEqual(group['role'],'main')
        self.assertIn('Main fixture',group['scope'])
        for kind in ('candidate','reference','private_record_only'):
            forged=copy.deepcopy(self.coverage)
            measurement=next(m for m in forged['measurements'] if m['id']=='train-scalar-reciprocal-private:aggregate')
            altered_group=next(g for g in forged['measurement_groups'] if g['id']==group['id'])
            if kind=='candidate':measurement['candidate_module_sha256']='0'*64
            elif kind=='reference':measurement['reference_module_sha256']='0'*64
            else:altered_group['compiler_admission_source']='evidence/train-reciprocal-hoist.json'
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'Compiler admission'):
                checked_measurements(forged,ROOT)

    def test_native_line_failures_stay_partial_without_board_or_cpu_claims(self):
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        row=rows['patcher:line~']
        self.assertEqual(row['working']['status'],'partial')
        self.assertFalse(row['board_evidence'])
        self.assertIsNone(row['performance'])
        self.assertEqual(row['optimisation']['status'],'experimental')
        self.assertIn('late allocation',row['working']['detail'])
        for kind in ('board','missing_location','evidence_hash'):
            forged=copy.deepcopy(self.coverage)
            record=next(r for r in forged['objects'] if r['id']=='patcher:line~')
            if kind=='board':record['board_evidence']=True
            elif kind=='missing_location':del record['board_evidence']
            else:forged['sources']['evidence/line-timing-modes.json']['sha256']='0'*64
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'[Bb]oard|Qualification evidence'):
                make_status(self.inventory,forged)

    def test_bounded_line_experimental_option_requires_its_actual_public_pair(self):
        record=next(r for r in self.coverage['objects'] if r['id']=='patcher:line~')
        option=next(o for o in record['optimisations'] if o['id']=='bounded-line-ramps')
        self.assertEqual(option['flag'],'--bounded-line-ramps')
        self.assertEqual(option['state'],'experimental')
        for kind in ('flag','reference','candidate','historical_only'):
            forged=copy.deepcopy(self.coverage)
            changed=next(r for r in forged['objects'] if r['id']==record['id'])['optimisations'][0]
            if kind=='flag':changed['flag']='--unreviewed-line-option'
            elif kind=='reference':changed['reference_module_sha256']='0'*64
            elif kind=='candidate':changed['candidate_module_sha256']='0'*64
            else:changed['compiler_admission_source']='evidence/line-timing-modes.json'
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'Experimental compiler admission'):
                make_status(self.inventory,forged)

    def test_stable_onepole_keeps_default_gaps_and_has_no_board_or_cpu_credit(self):
        record=next(r for r in self.coverage['objects'] if r['id']=='patcher:onepole~')
        option=next(o for o in record['optimisations'] if o['id']=='stable-onepole')
        self.assertEqual(option['flag'],'--stable-onepole')
        self.assertEqual(option['state'],'experimental')
        row=next(r for r in make_status(self.inventory,self.coverage)['objects'] if r['id']==record['id'])
        self.assertEqual(row['working']['status'],'partial')
        self.assertFalse(row['board_evidence']);self.assertIsNone(row['performance'])
        self.assertIn('five exceed',row['working']['detail'])
        self.assertIn('strict baseline',row['working']['detail'])
        self.assertIn('finite recovery',row['optimisation']['detail'])
        graph_source='evidence/stable-onepole-graphs.json'
        graph_evidence=json.loads((ROOT/graph_source).read_bytes())
        self.assertTrue(any(q['source']==graph_source for q in record['qualification']))
        self.assertTrue(any(s['url'].endswith('/'+graph_source) for s in row['sources']))
        self.assertEqual(graph_evidence['native']['summary']['graphs'],10)
        self.assertEqual(len(graph_evidence['target_compilation']['variants']),4)
        self.assertFalse(graph_evidence['target_execution'])
        self.assertFalse(graph_evidence['target_cpu_gain_claimed'])
        self.assertIsNone(graph_evidence['performance_percentage'])
        source=self.coverage['sources'][graph_source]
        self.assertEqual(source['path'],graph_source)
        self.assertEqual(source['bytes'],(ROOT/graph_source).stat().st_size)
        self.assertTrue(source['url'].endswith('/'+graph_source))
        for kind in ('flag','reference','candidate','historical_only'):
            forged=copy.deepcopy(self.coverage)
            changed=next(o for r in forged['objects'] if r['id']==record['id'] for o in r['optimisations'] if o['id']=='stable-onepole')
            if kind=='flag':changed['flag']='--unreviewed-onepole-profile'
            elif kind=='reference':changed['reference_module_sha256']='0'*64
            elif kind=='candidate':changed['candidate_module_sha256']='0'*64
            else:changed['compiler_admission_source']='evidence/onepole-float32-clamp.json'
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'Experimental compiler admission'):
                make_status(self.inventory,forged)

    def test_stateful_native_accuracy_and_alias_boundaries_remain_visible(self):
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        for name,state,board in (('onepole~','partial',False),('slide~','partial',True),
                                 ('delta~','board',True),('sah~','board',True)):
            with self.subTest(name=name):
                row=rows['patcher:'+name]
                self.assertEqual(row['working']['status'],state)
                self.assertEqual(row['board_evidence'],board)
                self.assertIsNone(row['performance'])
                self.assertEqual(row['optimisation']['status'],'experimental' if name=='onepole~' else 'none')
                self.assertTrue(any(s['url'].endswith('/evidence/wave3-stateful.json') for s in row['sources']))
        self.assertIn('five exceed',rows['patcher:onepole~']['working']['detail'])
        self.assertIn('one long signed-rate',rows['patcher:slide~']['working']['detail'])
        self.assertTrue(rows['patcher:sah~']['is_alias'])
        self.assertEqual(rows['patcher:sah']['working']['status'],'unverified')
        self.assertIsNone(rows['patcher:sah']['performance'])
        # The later codebox instance scenario is independently executed;
        # its status is not inherited from the sah~ native evidence.
        self.assertEqual(rows['codebox:sah']['working']['status'],'board')
        self.assertIsNone(rows['codebox:sah']['performance'])
        self.assertTrue(any(s['url'].endswith('/evidence/xiao-smoke-rnbo-codebox-stateful.json')for s in rows['codebox:sah']['sources']))
        self.assertFalse(any(s['url'].endswith('/evidence/wave3-stateful.json')for s in rows['codebox:sah']['sources']))
        self.assertEqual(rows['patcher:comb~']['performance']['measurement_id'],
                         'filters-scalar-v2-storage:aggregate')

    def test_stateful_partial_cannot_claim_board_or_unbound_evidence(self):
        for kind in ('board','missing_location','evidence_hash','missing_evidence'):
            forged=copy.deepcopy(self.coverage)
            record=next(r for r in forged['objects'] if r['id']=='patcher:onepole~')
            if kind=='board':record['board_evidence']=True
            elif kind=='missing_location':del record['board_evidence']
            elif kind=='evidence_hash':forged['sources']['evidence/wave3-stateful.json']['sha256']='0'*64
            else:record['qualification'][0]['source']='evidence/nonexistent-wave3.json'
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'[Bb]oard|Qualification evidence'):
                make_status(self.inventory,forged)

    def test_onepole_clamp_option_binds_public_pair_without_repair_or_cpu_credit(self):
        record=next(r for r in self.coverage['objects'] if r['id']=='patcher:onepole~')
        option=next(o for o in record['optimisations'] if o['id']=='float32-onepole-clamp')
        self.assertEqual(option['state'],'experimental')
        self.assertEqual(option['flag'],'--float32-onepole-clamp')
        row=next(r for r in make_status(self.inventory,self.coverage)['objects'] if r['id']==record['id'])
        self.assertFalse(row['board_evidence'])
        self.assertEqual(row['working']['status'],'partial')
        self.assertIsNone(row['performance'])
        self.assertIn('five exceed',row['working']['detail'])
        self.assertIn('recurrence unchanged',row['optimisation']['detail'])
        for kind in ('flag','candidate','reference','historical_only'):
            forged=copy.deepcopy(self.coverage)
            changed=next(o for r in forged['objects'] if r['id']==record['id'] for o in r['optimisations'] if o['id']=='float32-onepole-clamp')
            if kind=='flag':changed['flag']='--stable-onepole-not-admitted'
            elif kind=='candidate':changed['candidate_module_sha256']='0'*64
            elif kind=='reference':changed['reference_module_sha256']='0'*64
            else:changed['compiler_admission_source']='evidence/wave3-stateful.json'
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'Experimental compiler admission'):
                make_status(self.inventory,forged)

    def test_exact_delay_availability_requires_the_measured_image_and_option(self):
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        for name in ('patcher:comb~','patcher:allpass~'):
            record=next(r for r in self.coverage['objects'] if r['id']==name)
            option=next(o for o in record['optimisations'] if o['id']=='exact-signal-delay44100')
            self.assertEqual(option['state'],'available')
            self.assertIn('--exact-audio-delay44100',option['flag'])
            self.assertIn('Public build reproduces the entire previously measured image',rows[name]['optimisation']['detail'])
            self.assertEqual(rows[name]['performance']['measurement_id'],'filters-scalar-v2-storage:aggregate')
        for kind in ('option','source_hash','historical_only'):
            forged=copy.deepcopy(self.coverage)
            group=next(g for g in forged['measurement_groups'] if g['id']=='filters-signal-exact44100-private')
            if kind=='option':group['equivalent_public_option']='--unqualified-option'
            elif kind=='source_hash':forged['sources'][group['compiler_admission_source']]['sha256']='0'*64
            else:group['compiler_admission_source']='evidence/exact-delay44100.json'
            with self.assertRaisesRegex(ValueError,'Compiler admission'):checked_measurements(forged,ROOT)

    def test_scalar_filter_availability_binds_the_current_reference_too(self):
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        for name in ('patcher:comb~','patcher:allpass~'):
            record=next(r for r in self.coverage['objects'] if r['id']==name)
            option=next(o for o in record['optimisations'] if o['id']=='scalar-filter-duration-hoist')
            self.assertEqual(option['state'],'available')
            self.assertIn('--hoist-filter-durations',option['flag'])
            self.assertIn('Current-runtime public pair reproduces both',rows[name]['optimisation']['detail'])
            self.assertEqual(rows[name]['performance']['measurement_id'],'filters-scalar-v2-storage:aggregate')
        forged=copy.deepcopy(self.coverage)
        measurement=next(m for m in forged['measurements'] if m['id']=='filters-scalar-duration-hoist-private:aggregate')
        measurement['reference_module_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Compiler admission reference'):checked_measurements(forged,ROOT)

    def test_correction_cost_is_shown_without_claiming_cpu_saving(self):
        measurement=next(m for m in self.coverage['measurements'] if m['id']=='finite-wrap-correction-bounded:aggregate')
        self.assertTrue(measurement['cpu_time_change_measured'])
        self.assertFalse(measurement['CPU_savings_claimed'])
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertLess(rows['patcher:wrap~']['performance']['percent'],0)
        self.assertEqual(rows['patcher:wrap~']['optimisation']['status'],'available')
        forged=copy.deepcopy(self.coverage)
        next(m for m in forged['measurements'] if m['id']==measurement['id'])['CPU_savings_claimed']=True
        with self.assertRaisesRegex(ValueError,'Saving claim differs'):checked_measurements(forged,ROOT)
        forged=copy.deepcopy(self.coverage)
        control=next(m for m in forged['measurements'] if m['id']=='finite-wrap-direct-control:aggregate')
        control['CPU_savings_claimed']=True
        with self.assertRaisesRegex(ValueError,'Controls must have no savings claim'):checked_measurements(forged,ROOT)

    def test_identical_artifact_timing_noise_cannot_be_presented_as_gain(self):
        data=copy.deepcopy(self.coverage)
        control=next(m for m in data['measurements'] if m['same_artifact_control'])
        control['CPU_savings_claimed']=True
        control['cpu_time_saved_percent']=100*(1-control['candidate_process_us']/control['reference_process_us'])
        with self.assertRaisesRegex(ValueError,'identical-artifact control'):checked_measurements(data,ROOT)

    def test_forged_time_module_or_evidence_hash_rejects_publication(self):
        for kind in ('time','module','hash'):
            with self.subTest(kind=kind):
                data=copy.deepcopy(self.coverage);measurement=data['measurements'][0]
                if kind=='time':measurement['candidate_process_us']-=1
                elif kind=='module':measurement['candidate_module_sha256']='0'*64
                else:data['sources'][measurement['source']]['sha256']='0'*64
                with self.assertRaises(ValueError):checked_measurements(data,ROOT)

    def test_unknown_or_duplicate_coverage_cannot_silently_disappear(self):
        for kind in ('unknown','duplicate'):
            with self.subTest(kind=kind):
                data=copy.deepcopy(self.coverage)
                if kind=='unknown':data['objects'][0]['id']='codebox:not-a-real-operation'
                else:data['objects'].append(copy.deepcopy(data['objects'][0]))
                with self.assertRaises(ValueError):make_status(self.inventory,data)

    def test_disabling_alias_isolation_rejects(self):
        data=copy.deepcopy(self.coverage);data['merge_policy']['codebox_inherits']=True
        with self.assertRaisesRegex(ValueError,'propagate'):make_status(self.inventory,data)

    def test_explicit_json_pointer_handles_arrays_and_escaped_keys(self):
        self.assertEqual(pointer({'a/b':[{'~value':9}]},'/a~1b/0/~0value'),9)


class ShortSmokeStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'evidence').mkdir()
        self.source='evidence/xiao-smoke-rnbo-stateless.json'
        self.item={'source':self.source,'selector':'/cases/0','level':'S3-XIAO-short-functional-hardware-check','evidence_kind':'xiao-rnbo-short-smoke'}
        self.record={'id':'patcher:floor~','spelling':'floor~','surface':'patcher','aliases_inherit_status':False,
            'working_state':'board','working_test_level':'short-functional-hardware-check',
            'working_note':'Passed the declared short hardware scenario.','optimisation_state':'unassessed',
            'optimisations':[],'qualification':[self.item],'cpu_measurement_ids':[]}
        self.data={'format':'rnbo-hardware-smoke-results-v1','board':'xiao','family':'rnbo-stateless','surface':'patcher',
            'test_level':'short-functional-hardware-check','full_qualification_claimed':False,
            'cases':[{'id':'floor-signal','exact_name':'floor~','status':'pass','finalized':True,'samples_checked':10240,
            'bit_mismatches':2,'zero_sign_differences':2,'mean_us':40.0,'median_us':40.0,'peak_us':40,
            'times_us':[40]*16,'context_bytes':12720,'arena_high_water':0,'cpu_review_reasons':[],
            'reference_policy':'basic-mathematical-function'}]}
        self.inventory=json.loads((ROOT/'site/data/inventory.json').read_bytes())
        self.coverage={'format':'curated-RNBO-exact-spelling-status-mapping-v1','merge_policy':{'patcher_aliases_inherit':False,'codebox_inherits':False},
            'measurement_groups':[],'measurements':[],'objects':[self.record],'sources':{},'snapshot_date':'2026-11-04',
            'verified_public_revision':{'sha':'synthetic-unit-fixture'}}
        self.write()

    def write(self):
        encoded=(json.dumps(self.data,sort_keys=True)+'\n').encode();(self.root/self.source).write_bytes(encoded)
        self.coverage['sources'][self.source]={'sha256':hashlib.sha256(encoded).hexdigest()}

    def result(self):
        self.write();return{r['id']:r for r in make_status(self.inventory,self.coverage,self.root)['objects']}

    def test_short_hardware_label_has_absolute_times_and_no_alias_or_gain(self):
        rows=self.result();row=rows['patcher:floor~']
        self.assertTrue(row['board_evidence']);self.assertEqual(row['working']['label'],'Short hardware check')
        self.assertIn('mean 40.00µs',row['working']['detail']);self.assertEqual(row['hardware_smoke'][0]['test_level'],'short-functional-hardware-check')
        self.assertIsNone(row['performance']);self.assertIsNone(row['hardware_smoke'][0]['cpu_time_saved_percent'])
        self.assertEqual(row['optimisation']['status'],'unassessed')
        self.assertEqual(rows['codebox:floor']['working']['status'],'unverified')

    def test_rejected_codebox_form_is_visible_without_hardware_or_gain_claim(self):
        record=dict(self.record,id='codebox:mod',spelling='mod',surface='codebox',working_state='unverified',board_evidence=False)
        failure={'exact_name':'mod','status':'compile_failed','source_sha256':'a'*64,
                 'codebox_source_sha256':'b'*64,'compile_log_sha256':'c'*64}
        data=dict(self.data,family='rnbo-codebox',surface='codebox',compile_failures=[failure])
        item=dict(self.item,selector='/compile_failures/0',evidence_kind='rnbo-codebox-build-failure')
        checked_codebox_build_failure(record,item,data)
        for key,value in (('spelling','%'),('surface','patcher'),('working_state','board'),('board_evidence',True),
                          ('cpu_measurement_ids',['made-up']),('optimisation_state','available')):
            with self.subTest(key=key),self.assertRaises(ValueError):
                checked_codebox_build_failure(dict(record,**{key:value}),item,data)
        failure['compile_log_sha256']='bad'
        with self.assertRaises(ValueError):checked_codebox_build_failure(record,item,data)

    def test_codebox_short_result_cannot_qualify_patcher_or_gen_surface(self):
        self.numeric();self.record.update(id='codebox:floor',spelling='floor',surface='codebox')
        self.data['cases'][0].update(exact_name='floor',codebox_source_sha256='d'*64)
        for family in ('rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-shaping','rnbo-codebox-misc'):
            self.data.update(family=family,surface='codebox',prepare_zero_warm_blocks=0)
            rows=self.result()
            self.assertEqual(rows['codebox:floor']['working']['status'],'board')
            self.assertEqual(rows['patcher:floor']['working']['status'],'unverified')
            observation=rows['codebox:floor']['hardware_smoke'][0]
            self.assertEqual(observation['codebox_source_sha256'],'d'*64)
            for surface in ('patcher','genexpr'):
                self.data['surface']=surface
                with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)
            self.data['surface']='codebox'
        self.data.pop('prepare_zero_warm_blocks')
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)
        self.data['prepare_zero_warm_blocks']=0
        self.data['cases'][0].pop('codebox_source_sha256')
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)

    def test_codebox_range_predeclared_approximation_limit_has_a_closed_scope(self):
        self.numeric();self.record.update(id='codebox:fastsin',spelling='fastsin',surface='codebox')
        self.data.update(family='rnbo-codebox-range',surface='codebox',prepare_zero_warm_blocks=0)
        self.data['cases'][0].update(exact_name='fastsin',codebox_source_sha256='a'*64,
            absolute_tolerance=0.0010000000474974513,max_absolute_error=.0008,
            bit_mismatches=2,zero_sign_differences=0,within_tolerance_differences=2,numeric_mismatches=0)
        row=self.result()['codebox:fastsin']
        self.assertEqual(row['working']['status'],'board')
        self.assertIsNone(row['performance'])
        self.data['family']='rnbo-codebox-numeric'
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)
        self.data['family']='rnbo-codebox-range';self.data['prepare_zero_warm_blocks']=4
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)

    def test_stateful_codebox_status_requires_twenty_block_identity(self):
        self.numeric();self.record.update(id='codebox:history',spelling='history',surface='codebox')
        self.data.update(family='rnbo-codebox-stateful',surface='codebox',prepare_zero_warm_blocks=0,
            expected_stream_policy='Fresh prepared codebox state; twenty continuous256-frame callbacks without resets')
        case=self.data['cases'][0];case.update(exact_name='history',codebox_source_sha256='a'*64,
            expected_block_count=20,expected_stream_sha256='b'*64)
        for family in ('rnbo-codebox-stateful','rnbo-codebox-filters'):
            self.data['family']=family
            observation=self.result()['codebox:history']['hardware_smoke'][0]
            self.assertEqual(observation['expected_block_count'],20)
        for changes in ({'expected_block_count':1},{'expected_block_count':True},{'expected_stream_sha256':'bad'}):
            original=dict(case);case.update(changes)
            with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)
            case.clear();case.update(original)
        self.data['expected_stream_policy']='reset each callback'
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)

    def test_signal_range_approximation_limit_is_bound_to_family_and_prepare_epoch(self):
        self.numeric();self.record.update(id='patcher:fastpow~',spelling='fastpow~')
        self.data.update(family='rnbo-signal-range',prepare_zero_warm_blocks=0)
        self.data['cases'][0].update(exact_name='fastpow~',absolute_tolerance=0.0010000000474974513,
            max_absolute_error=.0008,bit_mismatches=2,zero_sign_differences=0,
            within_tolerance_differences=2,numeric_mismatches=0)
        self.assertEqual(self.result()['patcher:fastpow~']['working']['status'],'board')
        self.data['family']='rnbo-numeric'
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)
        self.data.update(family='rnbo-signal-range',prepare_zero_warm_blocks=4)
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)

    def test_signal_stateful_status_requires_its_own_surface_and_continuous_policy(self):
        self.numeric();self.record.update(id='patcher:change~',spelling='change~')
        self.data.update(family='rnbo-signal-stateful',surface='patcher',prepare_zero_warm_blocks=0,
            expected_stream_policy='Fresh prepared signal state; twenty continuous256-frame callbacks without resets')
        case=self.data['cases'][0];case.update(exact_name='change~',expected_block_count=20,expected_stream_sha256='b'*64)
        for family in ('rnbo-signal-stateful','rnbo-signal-state-followup'):
            self.data['family']=family
            self.assertEqual(self.result()['patcher:change~']['hardware_smoke'][0]['expected_block_count'],20)
        self.data['surface']='codebox'
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)
        self.data['surface']='patcher';self.data['expected_stream_policy']='Fresh prepared codebox state; twenty continuous256-frame callbacks without resets'
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)

    def test_signal_routing_requires_numeric_fields_zero_prepare_and_its_surface(self):
        self.numeric();self.record.update(id='patcher:gate~',spelling='gate~')
        self.data.update(family='rnbo-signal-routing',surface='patcher',prepare_zero_warm_blocks=0)
        case=self.data['cases'][0];case.update(exact_name='gate~')
        observation=checked_short_smoke(self.record,self.item,self.data)
        self.assertIsNone(observation['cpu_time_saved_percent'])
        for changes in ({'surface':'codebox'},{'surface':'genexpr'},
                        {'prepare_zero_warm_blocks':4},{'prepare_zero_warm_blocks':False}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                checked_short_smoke(self.record,self.item,dict(self.data,**changes))
        case.pop('input_words_sha256')
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)

    def test_existing_stronger_status_and_optimisation_are_preserved(self):
        self.record.pop('working_test_level');self.record['working_state']='in_patch'
        self.record['working_note']='Existing verified composition.';self.record['optimisation_state']='available'
        self.record['optimisations']=[{'state':'available','note':'Existing optimisation.'}]
        row=self.result()['patcher:floor~']
        self.assertEqual(row['working']['status'],'in_patch');self.assertEqual(row['working']['label'],'In a verified patch')
        self.assertEqual(row['optimisation']['status'],'available');self.assertIn('Existing verified composition.',row['working']['detail'])
        self.assertEqual(len(row['hardware_smoke']),1)
        self.data['cases'][0].update(status='output_mismatch',bit_mismatches=3)
        row=self.result()['patcher:floor~'];self.assertEqual(row['working']['status'],'in_patch')
        self.assertEqual(row['hardware_smoke'][0]['status'],'output_mismatch')

    def test_mismatch_is_explicit_and_cpu_spikes_are_only_review_flags(self):
        case=self.data['cases'][0];case.update(status='output_mismatch',bit_mismatches=3,times_us=[600]*16,mean_us=600.,median_us=600.,peak_us=600,cpu_review_reasons=['median_budget'])
        with self.assertRaisesRegex(ValueError,'working label differs'):self.result()
        self.record.update(working_state='partial',board_evidence=True)
        row=self.result()['patcher:floor~'];self.assertEqual(row['working']['label'],'Short check / known gaps')
        self.assertIn('output_mismatch',row['working']['detail']);self.assertIn('flagged for later review',row['working']['detail'])
        self.assertIsNone(row['performance']);self.assertEqual(row['optimisation']['status'],'unassessed')

    def test_smoke_scope_spelling_counters_and_timing_cannot_be_forged(self):
        original=copy.deepcopy(self.data)
        for mutation in ('Gen','surface','full','name','finalized','samples','counter','status','raw-times','mean','cpu-reason','selector'):
            with self.subTest(mutation=mutation):
                self.data=copy.deepcopy(original);case=self.data['cases'][0];item=copy.deepcopy(self.item)
                if mutation=='Gen':self.data['family']='gen-numeric'
                elif mutation=='surface':self.data['surface']='codebox'
                elif mutation=='full':self.data['full_qualification_claimed']=True
                elif mutation=='name':case['exact_name']='floor'
                elif mutation=='finalized':case['finalized']=False
                elif mutation=='samples':case['samples_checked']=True
                elif mutation=='counter':case['bit_mismatches']=True
                elif mutation=='status':case['status']='output_mismatch'
                elif mutation=='raw-times':case['times_us'].pop()
                elif mutation=='mean':case['mean_us']=39
                elif mutation=='cpu-reason':case['cpu_review_reasons']=['peak_spike']
                else:item['selector']='/compile_failures/0'
                with self.assertRaises(ValueError):checked_short_smoke(self.record,item,self.data)

    def numeric(self):
        self.data['family']='rnbo-numeric'
        self.data['cases'][0].update(bit_mismatches=3,zero_sign_differences=1,numeric_mismatches=0,
            within_tolerance_differences=2,nonfinite_outputs=0,max_absolute_error=1e-7,
            absolute_tolerance=1.9999999949504854e-6,input_words_sha256='1'*64)

    def character(self):
        self.numeric();self.record.update(id='codebox:CHAR_A',spelling='CHAR_A',surface='codebox')
        self.data.update(family='rnbo-character-constants',surface='codebox',prepare_zero_warm_blocks=0,
            strict_zero_sign_channels=2,raw_pilot_channel=1,
            partition={'index':1,'total':2,'case_count':43,'parent_catalog_sha256':'a'*64})
        case=self.data['cases'][0];case.update(exact_name='CHAR_A',codebox_source_sha256='b'*64,
            bit_mismatches=0,zero_sign_differences=0,numeric_mismatches=0,within_tolerance_differences=0,
            max_absolute_error=0,absolute_tolerance=0,strict_zero_sign_channels=2,
            strict_zero_sign_mismatches=0,raw_pilot_channel=1,syntax='named-value',ascii_decimal=65,
            codebox_inlet_names=['in2'],codebox_pilot_inlet_ordinal=0)
        self.data['cases']=[copy.deepcopy(case)for _ in range(43)]

    def test_character_constant_requires_partition_zero_tolerance_and_strict_pilot(self):
        self.character();observation=checked_short_smoke(self.record,self.item,self.data)
        self.assertEqual(observation['raw_pilot_channel'],1)
        original=copy.deepcopy(self.data)
        for kind in ('partition','count','hash','top_mask','case_mask','pilot','counter','limit','surface','syntax','ordinal'):
            self.data=copy.deepcopy(original);case=self.data['cases'][0]
            if kind=='partition':self.data['partition']['index']=True
            elif kind=='count':self.data['partition']['case_count']=42
            elif kind=='hash':self.data['partition']['parent_catalog_sha256']='bad'
            elif kind=='top_mask':self.data['strict_zero_sign_channels']=0
            elif kind=='case_mask':case['strict_zero_sign_channels']=0
            elif kind=='pilot':case['raw_pilot_channel']=True
            elif kind=='counter':case.pop('strict_zero_sign_mismatches')
            elif kind=='limit':case['absolute_tolerance']=1e-6
            elif kind=='syntax':case['syntax']='call'
            elif kind=='ordinal':case['codebox_pilot_inlet_ordinal']=False
            else:self.data['surface']='patcher'
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                checked_short_smoke(self.record,self.item,self.data)

    def test_character_pilot_signed_zero_failure_is_a_numeric_gate_failure(self):
        self.character();case=self.data['cases'][0]
        case.update(status='output_mismatch',bit_mismatches=1,numeric_mismatches=1,strict_zero_sign_mismatches=1)
        observation=checked_short_smoke(self.record,self.item,self.data)
        self.assertEqual(observation['status'],'output_mismatch')
        self.assertEqual(observation['strict_zero_sign_mismatches'],1)

    def test_numeric_smoke_passes_declared_tolerance_without_claiming_bit_identity(self):
        self.numeric();row=self.result()['patcher:floor~'];observation=row['hardware_smoke'][0]
        self.assertEqual(row['working']['label'],'Short hardware check')
        self.assertEqual(observation['numeric_mismatches'],0);self.assertEqual(observation['within_tolerance_differences'],2)
        self.assertIn('Declared absolute tolerance',row['working']['detail'])
        self.assertEqual(observation['absolute_tolerance'],1.9999999949504854e-6)
        self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])

    def test_numeric_nonfinite_failures_are_visible_and_require_partial_state(self):
        self.numeric();case=self.data['cases'][0]
        case.update(status='output_mismatch',bit_mismatches=5,numeric_mismatches=2,nonfinite_outputs=1,max_absolute_error=1.)
        with self.assertRaisesRegex(ValueError,'working label differs'):self.result()
        self.record.update(working_state='partial',board_evidence=True)
        row=self.result()['patcher:floor~'];self.assertEqual(row['working']['label'],'Short check / known gaps')
        self.assertIn('nonfinite outputs 1',row['working']['detail'])
        self.assertEqual(row['hardware_smoke'][0]['numeric_mismatches'],2)

    def test_numeric_smoke_rejects_incomplete_or_contradictory_counts_and_limits(self):
        for mutation in ('missing','numeric','within','nonfinite','bool','tolerance','finite-error','hash','wrong-status','missing-family-fields'):
            with self.subTest(mutation=mutation):
                self.numeric();case=self.data['cases'][0]
                if mutation=='missing':del case['nonfinite_outputs']
                elif mutation=='numeric':case['numeric_mismatches']=1
                elif mutation=='within':case['within_tolerance_differences']=4
                elif mutation=='nonfinite':case['nonfinite_outputs']=1
                elif mutation=='bool':case['numeric_mismatches']=False
                elif mutation=='tolerance':case['absolute_tolerance']=1e-5
                elif mutation=='finite-error':case['max_absolute_error']=1.
                elif mutation=='hash':case['input_words_sha256']='not-a-digest'
                elif mutation=='wrong-status':case['status']='output_mismatch'
                else:
                    for key in ('numeric_mismatches','within_tolerance_differences','nonfinite_outputs','max_absolute_error','absolute_tolerance','input_words_sha256'):case.pop(key)
                with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)

    def functions(self):
        self.numeric();self.data['family']='rnbo-functions'
        self.data['cases'][0].update(absolute_tolerance=0.0010000000474974513,
            max_absolute_error=0.0005,arena_capacity=1048576,arena_high_water=262144)

    def boundary(self):
        self.data=json.loads((ROOT/'evidence/xiao-smoke-rnbo-events.json').read_bytes())
        self.data['cases']=self.data['cases'][:1]
        self.data['cases'][0]['exact_name']='floor~'

    def test_extra_event_family_retains_boundary_contract(self):
        self.boundary();self.data['family']='rnbo-events-extra'
        observation=self.result()['patcher:floor~']['hardware_smoke'][0]
        self.assertEqual(observation['parameter_events_applied'],21)
        self.data['cases'][0]['absolute_tolerance']=1e-6
        with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)

    def test_boundary_readbacks_allow_only_zero_sign_equivalence(self):
        self.boundary();case=self.data['cases'][0]
        minus_zero=case['parameter_events'][15];self.assertEqual(minus_zero['value_word'],0x80000000)
        minus_zero.update(actual_word=0,actual_zero_sign_difference=True)
        normalized_zero=case['parameter_events'][8];self.assertEqual(normalized_zero['expected_normalized_word'],0)
        normalized_zero.update(normalized_word=0x80000000,normalized_zero_sign_difference=True)
        observation=self.result()['patcher:floor~']['hardware_smoke'][0]
        self.assertEqual(observation['parameter_events_applied'],21);self.assertEqual(observation['strict_zero_sign_mismatches'],0)
        self.assertIn('before full256-frame callbacks',observation['parameter_event_scope'])
        self.assertIsNone(observation['cpu_time_saved_percent'])

    def test_boundary_schema_events_timing_and_strict_observer_reject_forgery(self):
        self.boundary();original=copy.deepcopy(self.data)
        for mutation in('numeric-missing','epsilon','strict-mask','strict-count','stream-hash','block-count','parameter-count',
                        'schema-hash','exponent','event-count','ordinal','call','slot','event-id','index','requested-word',
                        'actual-word','normalized-word','normalized-model','bool-word','readback-diagnostic','timing-sum','timing-peak','scope'):
            with self.subTest(mutation=mutation):
                self.data=copy.deepcopy(original);case=self.data['cases'][0];event=case['parameter_events'][0]
                if mutation=='numeric-missing':case.pop('nonfinite_outputs')
                elif mutation=='epsilon':case['absolute_tolerance']=1e-6
                elif mutation=='strict-mask':case['strict_zero_sign_channels']=1
                elif mutation=='strict-count':case['strict_zero_sign_mismatches']=1
                elif mutation=='stream-hash':case['expected_stream_sha256']='not-a-hash'
                elif mutation=='block-count':case['expected_block_count']=1
                elif mutation=='parameter-count':case['parameter_count']=True
                elif mutation=='schema-hash':case['parameter_schema_sha256']='bad'
                elif mutation=='exponent':case['parameters'][0]['exponent']=2.
                elif mutation=='event-count':case['parameter_events'].pop()
                elif mutation=='ordinal':event['ordinal']=1
                elif mutation=='call':event['before_call']=20
                elif mutation=='slot':event['parameter_slot']=True
                elif mutation=='event-id':event['id']='lookalike'
                elif mutation=='index':event['resolved_index']=1
                elif mutation=='requested-word':event['value_word']+=1
                elif mutation=='actual-word':event['actual_word']+=1
                elif mutation=='normalized-word':event['normalized_word']+=1
                elif mutation=='normalized-model':event['normalized_word']+=1;event['expected_normalized_word']+=1
                elif mutation=='bool-word':event['value_word']=True
                elif mutation=='readback-diagnostic':event['actual_zero_sign_difference']=True
                elif mutation=='timing-sum':case['event_total_us']+=1
                elif mutation=='timing-peak':case['event_peak_us']+=1
                else:case['parameter_event_scope']='sample-accurate within-block scheduling'
                with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)

    def test_functions_allow_predeclared_unit_limits_and_distinguish_reserved_memory(self):
        self.functions();row=self.result()['patcher:floor~'];observation=row['hardware_smoke'][0]
        self.assertEqual(observation['absolute_tolerance'],0.0010000000474974513)
        self.assertEqual(observation['arena_capacity'],1048576);self.assertEqual(observation['arena_high_water'],262144)
        self.assertIn('reserved 1,048,576 bytes',row['working']['detail']);self.assertIn('observed high-water 262,144 bytes',row['working']['detail'])
        self.assertIsNone(row['performance']);self.assertIsNone(observation['cpu_time_saved_percent'])

    def test_larger_function_limits_cannot_transfer_to_older_families(self):
        self.functions()
        for family in ('rnbo-stateless','rnbo-numeric'):
            self.data['family']=family
            with self.subTest(family=family),self.assertRaisesRegex(ValueError,'tolerance/error'):
                checked_short_smoke(self.record,self.item,self.data)
        self.data['family']='rnbo-functions';self.data['cases'][0]['absolute_tolerance']=0.0010001
        with self.assertRaisesRegex(ValueError,'tolerance/error'):checked_short_smoke(self.record,self.item,self.data)

    def test_functions_require_complete_counters_and_bounded_measured_arena(self):
        for mutation in ('missing-numeric','missing-capacity','bool-capacity','over-capacity','negative-highwater'):
            with self.subTest(mutation=mutation):
                self.functions();case=self.data['cases'][0]
                if mutation=='missing-numeric':case.pop('numeric_mismatches')
                elif mutation=='missing-capacity':case.pop('arena_capacity')
                elif mutation=='bool-capacity':case['arena_capacity']=True
                elif mutation=='over-capacity':case['arena_high_water']=1048577
                else:case['arena_high_water']=-1
                with self.assertRaises(ValueError):checked_short_smoke(self.record,self.item,self.data)

    def test_legacy_smoke_retains_the_exact_gate_and_output_shape(self):
        observation=checked_short_smoke(self.record,self.item,self.data)
        self.assertNotIn('numeric_mismatches',observation);self.assertNotIn('absolute_tolerance',observation)
        self.data['cases'][0]['bit_mismatches']=3
        with self.assertRaisesRegex(ValueError,'status/counters'):checked_short_smoke(self.record,self.item,self.data)

    def test_content_hash_and_bound_scenario_are_required(self):
        self.data['cases'][0]['mean_us']=39;self.write()
        self.coverage['sources'][self.source]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'evidence changed'):public_sources(self.record,self.coverage,self.root)
        self.data['cases'][0]['mean_us']=40;self.write();self.record['qualification']=[]
        with self.assertRaisesRegex(ValueError,'bound hardware scenario'):make_status(self.inventory,self.coverage,self.root)


if __name__=='__main__':unittest.main()
