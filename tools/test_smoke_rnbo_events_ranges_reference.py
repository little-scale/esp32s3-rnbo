# SPDX-License-Identifier: MIT
"""Independent event ordering/state checks and family admission mutations."""
import copy
import importlib.util
import json
import hashlib
import struct
import collect_hardware_smoke as collector
from pathlib import Path
import unittest
from unittest.mock import patch
import build_hardware_smoke as builder

HERE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-events-ranges'
spec=importlib.util.spec_from_file_location('event_ranges',HERE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class EventRangesTests(unittest.TestCase):
    def test_shape_pilot_and_holds(self):
        for model in r.MODELS:
            blocks=r.reference_blocks(model,r.input_words());events=r.parameter_events(model)
            self.assertEqual(len(events),21);self.assertEqual(len(blocks),20)
            self.assertTrue(all(len(b)==512 and b[1::2]==r.input_words()[1::2]for b in blocks))
            self.assertEqual(blocks[12],blocks[13]);self.assertEqual(blocks[13],blocks[14])
            self.assertEqual(r.ABSOLUTE_TOLERANCES[model],0)
    def test_pass_predicates_are_values_not_booleans(self):
        for m,yes,no in ((196,2,3),(197,3,2),(198,-2,3),(199,2,3),(200,3,2),(201,2,1)):
            self.assertEqual(r._operation(m,yes,0),yes)
            self.assertEqual(r._operation(m,no,0),0)
        for m in range(196,202):
            values=[r._operation(m,e['value'],0)for e in r.parameter_events(m)if e['before_call']==10]
            self.assertNotEqual(values[0],values[-1])
    def test_range_endpoints_and_multiple_crossings(self):
        self.assertEqual([r._operation(202,x,0)for x in(-8,-1,0,1,8)],[-1,-1,0,1,1])
        self.assertEqual([r._operation(203,x,0)for x in(-8,-2,-1,0,1,2,8)],[0,0,-1,0,-1,0,0])
        self.assertEqual([r._operation(204,x,0)for x in(-8,-2,-1,0,1,2,8)],[0,0,-1,0,1,0,0])
    def test_unit_windows_and_interpolation(self):
        for m in(206,207,208):
            self.assertTrue(all(0<=e['value']<=1 for e in r.parameter_events(m)))
        for m in(207,208):self.assertEqual([r._operation(m,x,0)for x in(0,.25,.5,.75,1)],[0,.5,1,.5,0])
        self.assertEqual([r._operation(206,x,0)for x in(0,.25,.5,.75,1)],[-1,-.5,0,.5,1])
    def test_delta_uses_every_event_and_holds_without_events(self):
        b=r.reference_blocks(209,r.input_words())
        self.assertEqual([r.value(b[i][0])for i in(0,1,6,7,10,11,12,13,14,16)],[1,-3,3.5,0,-1,0,.5,.5,.5,1])
        # Dropping the first two events beforecall10 must change the event delta.
        events=r.parameter_events(209);mutated=[e for i,e in enumerate(events)if i not in(10,11)]
        mutated.extend([events[-1],events[-1]])  # preserve required21 count, aftercall19
        with patch.object(r,'parameter_events',return_value=mutated):self.assertNotEqual(r.reference_blocks(209,r.input_words())[10],b[10])
    def test_catalog_and_reference_are_frozen(self):
        cat=json.loads((HERE/'catalog.json').read_bytes());builder.event_range_catalog(cat)
        self.assertEqual(builder.sha(HERE/'reference.py'),builder.EVENT_RANGE_REFERENCE_SHA)
        for field,value in(('model',196),('exact_name','other'),('patch_sha256','0'*64)):
            changed=copy.deepcopy(cat);changed['cases'][-1][field]=value
            with self.assertRaises(ValueError):builder.event_range_catalog(changed)
    def test_collector_rebinds_events_domain_stream_and_exact_source(self):
        cat=json.loads((HERE/'catalog.json').read_bytes());cases=[]
        for source in cat['cases']:
            row=copy.deepcopy(source);model=row['model'];inputs=r.input_words();blocks=r.reference_blocks(model,inputs)
            row.update(source_sha256=row['patch_sha256'],absolute_tolerance=0.,input_words=list(inputs),expected=list(blocks[0]),
                expected_blocks=[list(b)for b in blocks],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest(),
                expected_parameter_count=1,parameters=[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0)],
                parameter_events=[dict(before_call=e['before_call'],id='drive',parameter_slot=0,value_word=r.word(e['value']),normalized_word=r.word((e['value']+8)/16))for e in r.parameter_events(model)])
            cases.append(row)
        pool,indices=builder.block_pool(cases)
        for row,refs in zip(cases,indices):row['expected_block_indices']=refs;del row['expected_blocks']
        plan=dict(family='rnbo-events-ranges',catalog_sha256=builder.EVENT_RANGE_CATALOG_SHA,reference_source_sha256=builder.EVENT_RANGE_REFERENCE_SHA,
            surface='patcher',prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,expected_block_storage='shared-512-word-pool',
            expected_reference_unique_blocks=len(pool),expected_block_pool=[list(b)for b in pool],cases=cases)
        collector.event_range_plan(plan)
        mutations=[lambda p:p['cases'][0].update(exact_name='eqp~'),lambda p:p['cases'][0].update(absolute_tolerance=1e-6),
            lambda p:p['cases'][0]['parameter_events'][0].update(value_word=r.word(2.)),
            lambda p:p['cases'][-1]['expected_block_indices'].__setitem__(10,0),
            lambda p:p.update(prepare_zero_warm_blocks=1),lambda p:p['cases'][0].update(source_sha256='0'*64),
            lambda p:p['cases'].pop()]
        for mutate in mutations:
            changed=copy.deepcopy(plan);mutate(changed)
            with self.assertRaises(ValueError):collector.event_range_plan(changed)

    def test_invalid_inputs_and_order(self):
        for m,x in((True,r.input_words()),(195,r.input_words()),(196,(0,0)),(196,(0x7fc00000,)+r.input_words()[1:])):
            with self.assertRaises(ValueError):r.reference_blocks(m,x)
        for count in(True,0,21,.5):
            with self.assertRaises(ValueError):r.reference_blocks(196,r.input_words(),count)
        e=r.parameter_events(196);e[2],e[3]=e[3],e[2]
        with patch.object(r,'parameter_events',return_value=e):
            with self.assertRaises(ValueError):r.reference_blocks(196,r.input_words())
if __name__=='__main__':unittest.main()
