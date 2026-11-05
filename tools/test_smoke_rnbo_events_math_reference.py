# SPDX-License-Identifier: MIT
"""Independent event maths, source admission and exact-pilot mutation checks."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import build_object_status as publisher

HERE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-events-math'
spec=importlib.util.spec_from_file_location('events_math_reference',HERE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class EventMathTests(unittest.TestCase):
    def test_finite_domains_schedule_hold_and_pilot(self):
        for model,name in r.MODEL_NAMES.items():
            events=r.parameter_events(model);lo,hi=r.domain(name)
            self.assertEqual(len(events),21);self.assertTrue(all(lo<=e['value']<=hi for e in events))
            blocks=r.reference_blocks(model,r.input_words());self.assertEqual(len(blocks),20)
            self.assertEqual(blocks[6],blocks[7]);self.assertEqual(blocks[12],blocks[13]);self.assertEqual(blocks[13],blocks[14])
            self.assertTrue(all(len(b)==512 and b[1::2]==r.input_words()[1::2]for b in blocks))
            self.assertTrue(all(math.isfinite(r.value(w))for b in blocks for w in b))
    def test_independent_mathematical_landmarks(self):
        values=[('sin',0,0),('cos',0,1),('acos',0,math.pi/2),('asin',0,0),('acosh',1,0),('atan2',2,math.pi/4),
            ('hypot',1.5,2.5),('pow',4,32),('fastpow',4,32),('exp2',-2,.25),('expm1',0,0),('log1p',0,0),
            ('ln',1,0),('log2',4,2),('log10',1,0),('sqrt',4,2),('cbrt',-8,-2),('atodb',1,0),('dbtoa',0,1)]
        for name,x,y in values:self.assertAlmostEqual(r.operation(name,x),y,places=13)
        for name in('hann','welch'):self.assertEqual([r.operation(name,x)for x in(0,.5,1)],[0,1,0])
        self.assertAlmostEqual(r.operation('hamming',0),.08)
        self.assertAlmostEqual(r.operation('blackman',.5),1)
    def test_conversion_constants_do_not_multiply_input(self):
        for n in('DEGTORAD','degtorad'):self.assertEqual(r.operation(n,2),math.pi/180)
        for n in('RADTODEG','radtodeg'):self.assertEqual(r.operation(n,2),180/math.pi)
        self.assertAlmostEqual(r.operation('degrees',math.pi),180)
        self.assertAlmostEqual(r.operation('radians',180),math.pi)
    def test_named_approximations_keep_predeclared_screen(self):
        for m,n in r.MODEL_NAMES.items():
            self.assertEqual(r.ABSOLUTE_TOLERANCES[m]==.001,n in r.APPROXIMATIONS)
        for name in('cosT8','cosT8safe'):
            m=next(m for m,n in r.MODEL_NAMES.items()if n==name)
            self.assertTrue(any(abs(e['value'])==3 for e in r.parameter_events(m)))
            self.assertEqual(r.operation(name,3),math.cos(3))
    def test_partition_and_casefold_safe_sources_are_frozen(self):
        full=json.loads((HERE/'catalog.json').read_bytes());cases=full['cases']
        self.assertEqual(len(cases),44);self.assertEqual(len({c['id'].casefold()for c in cases}),44)
        self.assertEqual({c['patch']for c in cases},{p.name for p in HERE.glob('*.rnbopat')})
        combined=[]
        for part in(1,2):
            cat=json.loads((HERE/('part'+str(part)+'.json')).read_bytes());builder.event_math_catalog(cat);combined+=cat['cases']
            changed=copy.deepcopy(cat);changed['cases'][0]['maximum_absolute_error']*=2
            with self.assertRaises(ValueError):builder.event_math_catalog(changed)
        self.assertEqual(combined,cases)
        self.assertEqual(builder.sha(HERE/'reference.py'),builder.EVENT_MATH_REFERENCE_SHA)
    def _plan(self,part):
        cat=json.loads((HERE/('part'+str(part)+'.json')).read_bytes());cases=[]
        for source in cat['cases']:
            row=copy.deepcopy(source);model=row['model'];inputs=r.input_words();blocks=r.reference_blocks(model,inputs)
            row.update(source_sha256=row['patch_sha256'],absolute_tolerance=builder.float32(source['maximum_absolute_error']),input_words=list(inputs),expected=list(blocks[0]),
                expected_blocks=[list(b)for b in blocks],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest(),
                expected_parameter_count=1,parameters=[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0)],
                parameter_events=[dict(before_call=e['before_call'],id='drive',parameter_slot=0,value_word=r.word(e['value']),normalized_word=r.word((e['value']+8)/16))for e in r.parameter_events(model)])
            cases.append(row)
        pool,indices=builder.block_pool(cases)
        for row,refs in zip(cases,indices):row['expected_block_indices']=refs;del row['expected_blocks']
        return dict(family='rnbo-events-math',catalog_sha256=builder.EVENT_MATH_PARTITIONS[part],reference_source_sha256=builder.EVENT_MATH_REFERENCE_SHA,
            surface='patcher',partition=cat['partition'],prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,expected_block_storage='shared-512-word-pool',
            expected_reference_unique_blocks=len(pool),expected_block_pool=[list(b)for b in pool],cases=cases)
    def test_collector_recomputes_stream_controls_domain_and_tolerance(self):
        for part in(1,2):
            plan=self._plan(part);collector.event_math_plan(plan)
            mutations=[lambda p:p['cases'][0].update(exact_name='other'),lambda p:p['cases'][0].update(absolute_tolerance=.001),
                lambda p:p['cases'][0]['parameter_events'][0].update(value_word=r.word(2.)),
                lambda p:p['cases'][0]['input_domain'].__setitem__(0,-8.),lambda p:p.update(prepare_zero_warm_blocks=1),
                lambda p:p['cases'][0].update(source_sha256='0'*64),lambda p:p['cases'].pop()]
            for mutate in mutations:
                changed=copy.deepcopy(plan);mutate(changed)
                with self.assertRaises(ValueError):collector.event_math_plan(changed)
    def test_right_capture_digest_cannot_use_left_numeric_tolerance(self):
        blocks=[list(b)for b in r.reference_blocks(210,r.input_words())]
        digest=lambda b:hashlib.sha256(b''.join(struct.pack('<256I',*v[1::2])for v in b)).hexdigest()
        observation=collector.right_pilot_observation(dict(right_output_sha256=digest(blocks)),blocks)
        self.assertIs(observation['right_pilot_bit_exact'],True)
        for index in(1,3,5,17,31):
            changed=copy.deepcopy(blocks);changed[-1][index]^=1  # includes signed zeros and subnormals
            with self.assertRaises(ValueError):collector.right_pilot_observation(dict(right_output_sha256=digest(changed)),blocks)
        for raw in(None,'','0'*64):
            with self.assertRaises(ValueError):collector.right_pilot_observation(dict(right_output_sha256=raw),blocks)
    def test_publication_preserves_limits_exact_source_and_raw_observer(self):
        for part in(1,2):
            data=json.loads((HERE.parents[3]/'evidence'/('xiao-smoke-rnbo-events-math-part'+str(part)+'.json')).read_bytes())
            for index,case in enumerate(data['cases']):
                record=dict(surface='patcher',id='patcher:'+case['exact_name'],spelling=case['exact_name'])
                item=dict(selector='/cases/'+str(index),source='evidence/xiao-smoke-rnbo-events-math-part'+str(part)+'.json')
                observation=publisher.checked_short_smoke(record,item,data)
                self.assertEqual(observation['status'],case['status']);self.assertIs(observation['right_pilot_bit_exact'],True)
            record=dict(surface='patcher',id='patcher:'+data['cases'][0]['exact_name'],spelling=data['cases'][0]['exact_name'])
            for key,value in(('absolute_tolerance',.0005),('source_sha256','0'*64),('right_output_sha256','0'*64),('right_pilot_bit_exact',False)):
                changed=copy.deepcopy(data);changed['cases'][0][key]=value
                with self.assertRaises(ValueError):publisher.checked_short_smoke(record,dict(selector='/cases/0',source='evidence/xiao-smoke-rnbo-events-math-part'+str(part)+'.json'),changed)

    def test_invalid_model_input_order_and_domains(self):
        for m,x in((True,r.input_words()),(209,r.input_words()),(210,(0,0)),(210,(0x7fc00000,)+r.input_words()[1:])):
            with self.assertRaises(ValueError):r.reference_blocks(m,x)
        es=r.parameter_events(210)
        for mutate in(lambda e:e[0].update(value=2.),lambda e:e.reverse()):
            bad=copy.deepcopy(es);mutate(bad)
            with patch.object(r,'parameter_events',return_value=bad):
                with self.assertRaises(ValueError):r.reference_blocks(210,r.input_words())
if __name__=='__main__':unittest.main()
