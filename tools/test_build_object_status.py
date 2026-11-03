# SPDX-License-Identifier: MIT
"""Prevent missing names, alias overclaims and unsupported performance numbers."""
import copy
import json
import unittest

from build_object_status import ROOT,make_status,checked_measurements,pointer


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
            changed=next(r for r in forged['objects'] if r['id']==record['id'])['optimisations'][0]
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


if __name__=='__main__':unittest.main()
