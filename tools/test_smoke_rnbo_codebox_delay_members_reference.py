# SPDX-License-Identifier: MIT
"""Independent resource/member reference and source/limit audit checks."""
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

BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-codebox-delay-members'
spec=importlib.util.spec_from_file_location('delay_member_reference',BASE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class DelayMemberReferenceTests(unittest.TestCase):
    def test_published_results_keep_modes_rejections_and_costs_separate(self):
        root=BASE.parents[3];data=json.loads((root/'evidence/xiao-smoke-rnbo-codebox-delay-members.json').read_bytes())
        self.assertEqual(data['summary'],dict(executed=22,passed=17,output_mismatches=5,compile_failures=11,cpu_review=9))
        native=json.loads((root/'evidence/rnbo-codebox-delay-members-native.json').read_bytes());byid={row['id']:row for row in data['cases']}
        for row in native['cases']:
            actual=byid[row['id']]
            self.assertEqual(row['bit_differences'],actual['bit_mismatches'])
            self.assertEqual(row['max_error'],actual['max_absolute_error'])
            self.assertEqual(row['within_declared_maximum_error'],actual['status']=='pass')
            self.assertEqual(row['strict_numeric_word_differences'],actual['numeric_mismatches']+actual['within_tolerance_differences'])
        self.assertTrue(all(row['stage']=='C++'and row['hardware_executed']is False for row in native['rejected_forms']))
        # Mixed read/next outcomes do not qualify the complete member surface.
        coverage=json.loads((root/'site/data/coverage.json').read_bytes())
        rows={row['id']:row for row in status.make_status(json.loads((root/'site/data/inventory.json').read_bytes()),coverage)['objects']}
        self.assertEqual(rows['codebox-member:delay.next']['working']['status'],'partial')
        self.assertEqual(rows['codebox-member:delay.read']['working']['status'],'partial')
        self.assertEqual(rows['codebox-member:delay.write']['working']['status'],'board')
        self.assertEqual(rows['codebox-member:delay.step']['working']['status'],'board')
        for member in ('comb.clear','comb.reset','allpass.clear','allpass.reset'):
            actual=byid[member.replace('.','-')+'-integer']
            self.assertEqual(actual['status'],'pass')
            self.assertGreater(actual['median_us'],40000)
            self.assertEqual(actual['cpu_review_reasons'],['median_budget'])
    def test_integer_delay_double_step_and_overwrite_have_absolute_sample_age(self):
        for model in (1500,1503,1504,1505):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
            for n in (0,1,2,15,16,255,256,257,5119):
                expected=0 if n<2 else r.value(inputs[2*((n-2)%256)])
                self.assertEqual(r.value(blocks[n//256][2*(n%256)]),expected)
    def test_clear_and_reset_have_zero_history_but_keep_right_pilot(self):
        for model in (1501,1502):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
            for n in (37,38,39,255,256,257):
                self.assertEqual(r.value(blocks[n//256][2*(n%256)]),0)
            for n in range(5120):self.assertEqual(blocks[n//256][2*(n%256)+1],inputs[2*(n%256)+1])
    def test_interpolators_reproduce_affine_data_and_declared_positions(self):
        for mode in ('cubic','spline'):
            self.assertAlmostEqual(r.interpolate(mode,.75,(-1,0,1,2)),.75,places=12)
        # Full-neighbor Hermite slopes are twice the affine derivative here.
        self.assertEqual(r.interpolate('fastcubic',.75,(-1,0,1,2)),.65625)
        self.assertAlmostEqual(r.interpolate('spline6',.75,(-2,-1,0,1,2,3)),.75,places=12)
        for model in (1513,1514,1521):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
            self.assertEqual(r.value(blocks[1][2*17]),.5*(r.LEFT[15]+r.LEFT[14]))
        for model in (1519,1520):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
            self.assertEqual(r.value(blocks[1][2*17]),r.LEFT[14])
    def test_comb_and_allpass_default_recurrences_and_first_echo(self):
        inputs=r.input_words()
        comb=r.reference_blocks(1507,inputs)[0];allpass=r.reference_blocks(1510,inputs)[0]
        self.assertEqual(r.value(comb[0]),.5*r.LEFT[0])
        self.assertEqual(r.value(comb[4]),.5*r.LEFT[2]+.5*r.LEFT[0]+.25*r.value(comb[0]))
        self.assertEqual(r.value(allpass[0]),-.5*r.LEFT[0])
        self.assertEqual(r.value(allpass[6]),-.5*r.LEFT[3]+r.LEFT[0]+.5*r.value(allpass[0]))
    def test_source_member_identities_and_resource_harness_are_bound(self):
        catalog=json.loads((BASE/'catalog.json').read_bytes());builder.delay_member_catalog(catalog)
        self.assertEqual(len(catalog['cases']),33)
        identities=set()
        for row in catalog['cases']:
            source=(BASE/row['patch']).read_bytes();code=(BASE/row['codebox']).read_bytes()
            self.assertEqual(hashlib.sha256(source).hexdigest(),row['patch_sha256'])
            self.assertEqual(builder.checked_codebox_source(row,source),hashlib.sha256(code).hexdigest())
            identities.add(status.delay_member_identity(row))
        self.assertEqual(len(identities),13)
        bad=copy.deepcopy(catalog);bad['cases'][0]['maximum_absolute_error']=.001
        with self.assertRaises(builder.ExportError):builder.delay_member_catalog(bad)
        with self.assertRaises(ValueError):status.delay_member_identity(dict(registry_lookup='codebox-member:delay.seed',exact_name='delay.seed()',syntax='stateful-member-call'))
        # Keep the native output observer identical; only creation capacity differs.
        original=(BASE.parents[3]/'tests/native/smoke_stream_test.cpp').read_text()
        resource=(BASE/'native_stream_test.cpp').read_text()
        self.assertEqual(resource[resource.index('static bool observing'):],
            original[original.index('static bool observing'):].replace('options{sizeof(options),4096,0,12345}',
                                                                        'options{sizeof(options),2097152,0,12345}'))
    def test_collector_rejects_altered_references_capacity_and_policy(self):
        catalog=json.loads((BASE/'catalog.json').read_bytes());cases=[]
        for row in catalog['cases']:
            inputs=list(r.case_input_words(row['model']));blocks=[list(b)for b in r.reference_blocks(row['model'],inputs)]
            cases.append(dict(row,source_sha256=row['patch_sha256'],codebox_source_sha256=row['codebox_sha256'],input_words=inputs,
                expected=blocks[0],expected_blocks=blocks,absolute_tolerance=struct.unpack('<f',struct.pack('<f',row['maximum_absolute_error']))[0],
                arena_bytes=2097152,expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest()))
        plan=dict(cases=cases,surface='codebox',prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,
            expected_stream_policy='Fresh prepared resource member state; twenty continuous256-frame callbacks with only authored in-program clear/reset calls',
            catalog_sha256=builder.DELAY_MEMBER_CATALOG_SHA,reference_source_sha256=builder.DELAY_MEMBER_REFERENCE_SHA)
        collector.delay_member_plan(plan)
        for key,value in (('arena_bytes',4096),('absolute_tolerance',.001),('source_sha256','0'*64),('parameter_events',[])):
            with self.subTest(key=key),self.assertRaises(ValueError):collector.delay_member_plan(dict(plan,cases=[dict(cases[0],**{key:value})]+cases[1:]))
        first=copy.deepcopy(cases[0]);first['expected_blocks'][19][511]^=1
        first['expected_stream_sha256']=hashlib.sha256(struct.pack('<10240I',*(w for b in first['expected_blocks']for w in b))).hexdigest()
        with self.assertRaises(ValueError):collector.delay_member_plan(dict(plan,cases=[first]+cases[1:]))
        with self.assertRaises(ValueError):collector.delay_member_plan(dict(plan,expected_stream_policy='No resets'))

if __name__=='__main__':unittest.main()
