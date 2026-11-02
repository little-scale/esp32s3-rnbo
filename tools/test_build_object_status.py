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
        self.assertEqual(row['optimisation']['status'],'experimental')
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
