# SPDX-License-Identifier: MIT
"""Member identity, observable reset schedules and immutable numerical contracts."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import build_object_status as status

BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-codebox-members'
spec=importlib.util.spec_from_file_location('member_reference',BASE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class MemberReferenceTests(unittest.TestCase):
    def test_published_results_keep_failures_and_member_scopes_separate(self):
        root=BASE.parents[3]
        coverage=json.loads((root/'site/data/coverage.json').read_bytes())
        rows={row['id']:row for row in status.make_status(json.loads((root/'site/data/inventory.json').read_bytes()),coverage)['objects']}
        self.assertEqual(rows['codebox-member:onepole.next']['working']['status'],'board')
        for member in ('reset','clear'):
            self.assertEqual(rows['codebox-member:onepole.'+member]['working']['status'],'partial')
        self.assertEqual(rows['codebox-member:history.reset']['working']['status'],'unverified')
        self.assertIsNone(rows['codebox-member:history.reset']['performance'])
        # The earlier detailed delta method qualification is retained alongside this screen.
        sources={q['source']for q in next(row for row in coverage['objects']if row['id']=='codebox-member:delta.next')['qualification']}
        self.assertIn('evidence/xiao-wave4.json',sources)
        self.assertIn('evidence/xiao-smoke-rnbo-codebox-members-part1.json',sources)
        cases=[row for i in(1,2)for row in json.loads((root/f'evidence/xiao-smoke-rnbo-codebox-members-part{i}.json').read_bytes())['cases']]
        self.assertEqual(len(cases),35)
        self.assertEqual(sum(row['status']=='pass'for row in cases),27)
        self.assertEqual(sum(row['status']=='output_mismatch'for row in cases),8)
        native=json.loads((root/'evidence/rnbo-codebox-members-native.json').read_bytes())
        byid={row['id']:row for row in cases}
        for row in native['cases']:
            device=byid[row['id']]
            self.assertEqual(row['bit_differences'],device['bit_mismatches'])
            self.assertEqual(row['max_error'],device['max_absolute_error'])
            self.assertEqual(row['within_declared_maximum_error'],device['status']=='pass')
            self.assertEqual(row['strict_numeric_word_differences'],device['numeric_mismatches']+device['within_tolerance_differences'])
    def test_reset_schedules_observe_consecutive_and_host_boundary_samples(self):
        for n,ch in ((37,0),(38,0),(255,0),(256,0),(294,0),(295,0),(91,1),(92,1),(511,1),(512,1)):
            self.assertTrue(r.reset_at(n,ch))
        for n,ch in ((36,0),(39,0),(91,0),(37,1),(90,1),(93,1)):
            self.assertFalse(r.reset_at(n,ch))
        self.assertNotEqual([n for n in range(5120)if r.reset_at(n,0)],[n for n in range(5120)if r.reset_at(n,1)])
    def test_delta_after_reset_ignores_prior_input_but_other_lane_keeps_state(self):
        model=1401;inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
        for n in (1,37,38,91,92,255,256,511,512,5119):
            for ch in (0,1):
                x=r.value(inputs[2*(n%256)+ch]);previous=0 if n==0 or r.reset_at(n,ch)else r.value(inputs[2*((n-1)%256)+ch])
                self.assertEqual(r.value(blocks[n//256][2*(n%256)+ch]),x-previous)
    def test_all_reset_and_clear_references_change_an_observed_sample(self):
        for model in sorted(r.MODELS):
            owner,method=r.row(model)
            if method=='next' or owner=='history':continue
            baseline=1400+r.ROWS.index((owner,'next'))
            actual=r.reference_blocks(model,r.case_input_words(model));continuous=r.reference_blocks(baseline,r.case_input_words(baseline))
            self.assertNotEqual(actual,continuous,owner+'.'+method+' is not observable')
    def test_elapsed_and_counter_age_are_absolute_between_authored_resets(self):
        for owner in ('elapsed','counter'):
            model=1400+r.ROWS.index((owner,'reset'));inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
            for n in (0,37,38,91,92,255,256,511,512,5119):
                for ch in (0,1):
                    last=max([-1]+[k for k in range(n+1)if r.reset_at(k,ch)])
                    age=n if last==-1 else n-last
                    expected=age if owner=='elapsed'else(age+1)%(7 if ch==0 else 5)
                    self.assertEqual(r.value(blocks[n//256][2*(n%256)+ch]),expected)
    def test_partitions_sources_and_member_owners_are_exact(self):
        parent=json.loads((BASE/'catalog.json').read_bytes());self.assertEqual(len(parent['cases']),36)
        observed=[]
        for index in (1,2):
            part=json.loads((BASE/f'part{index}.json').read_bytes());builder.member_catalog(part);observed+=part['cases']
            for row in part['cases']:
                source=(BASE/row['patch']).read_bytes();code=(BASE/row['codebox']).read_bytes()
                self.assertEqual(builder.checked_codebox_source(row,source),hashlib.sha256(code).hexdigest())
                self.assertEqual(status.stateful_member_identity(row),row['registry_lookup'])
            bad=copy.deepcopy(part);bad['cases'][0]['maximum_absolute_error']=.001
            with self.assertRaises(builder.ExportError):builder.member_catalog(bad)
        self.assertEqual(observed,parent['cases'])
        for name in ('counter.next()','dcblock.reset()','biquad.clear()','history.reset()'):
            row=dict(exact_name=name,registry_lookup='codebox-member:'+name[:-2],syntax='stateful-member-call')
            self.assertEqual(status.stateful_member_identity(row),row['registry_lookup'])
            with self.assertRaises(ValueError):status.stateful_member_identity(dict(row,registry_lookup='codebox:'+name[:-2]))
        with self.assertRaises(ValueError):status.stateful_member_identity(dict(exact_name='delta.clear()',registry_lookup='codebox-member:delta.clear',syntax='stateful-member-call'))
    def test_collector_rejects_fitted_stream_tolerance_source_and_partition(self):
        catalog=json.loads((BASE/'part1.json').read_bytes());cases=[]
        for row in catalog['cases']:
            inputs=list(r.case_input_words(row['model']));blocks=[list(b)for b in r.reference_blocks(row['model'],inputs)]
            cases.append(dict(row,source_sha256=row['patch_sha256'],codebox_source_sha256=row['codebox_sha256'],
                input_words=inputs,expected=blocks[0],expected_blocks=blocks,
                absolute_tolerance=struct.unpack('<f',struct.pack('<f',row['maximum_absolute_error']))[0],
                expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest()))
        plan=dict(cases=cases,surface='codebox',prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,
            expected_stream_policy='Fresh prepared member state; twenty continuous256-frame callbacks with only authored in-program member reset/clear calls',
            partition=catalog['partition'],catalog_sha256=builder.MEMBER_PARTITIONS[1],reference_source_sha256=builder.MEMBER_REFERENCE_SHA)
        collector.member_plan(plan)
        for key,value in (('registry_lookup','codebox:delta'),('source_sha256','0'*64),('absolute_tolerance',.001),('parameter_events',[])):
            with self.subTest(key=key),self.assertRaises(ValueError):collector.member_plan(dict(plan,cases=[dict(cases[0],**{key:value})]+cases[1:]))
        first=copy.deepcopy(cases[0]);first['expected_blocks'][19][511]^=1
        first['expected_stream_sha256']=hashlib.sha256(struct.pack('<10240I',*(w for b in first['expected_blocks']for w in b))).hexdigest()
        with self.assertRaises(ValueError):collector.member_plan(dict(plan,cases=[first]+cases[1:]))
        with self.assertRaises(ValueError):collector.member_plan(dict(plan,partition=dict(catalog['partition'],index=True)))
        with self.assertRaises(ValueError):collector.member_plan(dict(plan,expected_stream_policy='No resets'))
        with self.assertRaises(ValueError):r.reference_blocks(1400,[r.word(99)]*512)

if __name__=='__main__':unittest.main()
