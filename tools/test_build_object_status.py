# SPDX-License-Identifier: MIT
"""Prevent missing names, alias overclaims and unsupported performance numbers."""
import copy
import json
import hashlib
import tempfile
from pathlib import Path
import unittest

from build_object_status import ROOT,make_status,checked_measurements,pointer,checked_short_smoke,public_sources


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
        self.assertEqual(len(checked),154)
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
        for identity in ('codebox:add','codebox:sub','codebox-member:delta.reset','patcher:abs'):
            self.assertEqual(rows[identity]['working']['status'],'unverified')

    def test_actual_rnbo_short_smoke_adds_only_exact_scenarios_without_gains(self):
        source='evidence/xiao-smoke-rnbo-stateless.json';data=json.loads((ROOT/source).read_bytes())
        rows={r['id']:r for r in make_status(self.inventory,self.coverage)['objects']}
        self.assertEqual(data['summary']['executed'],36);self.assertEqual(data['summary']['passed'],36)
        self.assertEqual(len(self.coverage['objects']),92)
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
        for name,state in (('onepole~','partial'),('slide~','partial'),
                           ('delta~','native'),('sah~','native')):
            with self.subTest(name=name):
                row=rows['patcher:'+name]
                self.assertEqual(row['working']['status'],state)
                self.assertFalse(row['board_evidence'])
                self.assertIsNone(row['performance'])
                self.assertEqual(row['optimisation']['status'],'experimental' if name=='onepole~' else 'none')
                self.assertTrue(any(s['url'].endswith('/evidence/wave3-stateful.json') for s in row['sources']))
        self.assertIn('five exceed',rows['patcher:onepole~']['working']['detail'])
        self.assertIn('one long signed-rate',rows['patcher:slide~']['working']['detail'])
        self.assertTrue(rows['patcher:sah~']['is_alias'])
        for identity in ('patcher:sah','codebox:sah'):
            self.assertEqual(rows[identity]['working']['status'],'unverified')
            self.assertIsNone(rows[identity]['performance'])
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

    def test_content_hash_and_bound_scenario_are_required(self):
        self.data['cases'][0]['mean_us']=39;self.write()
        self.coverage['sources'][self.source]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'evidence changed'):public_sources(self.record,self.coverage,self.root)
        self.data['cases'][0]['mean_us']=40;self.write();self.record['qualification']=[]
        with self.assertRaisesRegex(ValueError,'bound hardware scenario'):make_status(self.inventory,self.coverage,self.root)


if __name__=='__main__':unittest.main()
