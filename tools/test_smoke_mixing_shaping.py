# SPDX-License-Identifier: MIT
"""Independent maths landmarks, exact sources and output/parameter evidence guards."""
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
ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'tests/fixtures/smoke/rnbo-mixing-shaping'
spec=importlib.util.spec_from_file_location('mixing_shaping_reference',HERE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def model(identity):return next(m for m,s in r.MODEL_SPECS.items()if s['id']==identity)
def op(identity,t):return r.operation(r.spec(model(identity)),t)
class MixingShapingTests(unittest.TestCase):
    def test_cartesian_polar_outputs_and_all_four_quadrants(self):
        for sign,label in((1,'positive-y'),(-1,'negative-y')):
            self.assertEqual(op('cartopol-'+label+'-out0',.5),.75)
            self.assertEqual(op('cartopol-'+label+'-out1',.5),sign*math.pi/2)
            self.assertAlmostEqual(op('cartopol-'+label+'-out0',0),math.sqrt(4+.75**2))
        self.assertEqual(op('poltocar-out0',.5),.75);self.assertEqual(op('poltocar-out1',.5),0)
        self.assertLess(op('poltocar-out0',0),0);self.assertLess(op('poltocar-out1',0),0)
        self.assertLess(op('poltocar-out0',1),0);self.assertGreater(op('poltocar-out1',1),0)
    def test_distinct_interpolation_basis_landmarks(self):
        for mode in('cubic','fastcubic','spline'):
            self.assertEqual(r.interpolate(mode,0),.25);self.assertEqual(r.interpolate(mode,1),1.25)
        self.assertEqual(r.interpolate('cubic',.25),.603515625)
        self.assertEqual(r.interpolate('spline',.25),.552734375)
        self.assertEqual(r.interpolate('fastcubic',.25),.69921875)
        self.assertAlmostEqual(r.interpolate('spline6',0),27.25/120)
        self.assertAlmostEqual(r.interpolate('spline6',1),59/120)
        self.assertEqual(r.interpolate('spline6',.375),r.interpolate('spline6-inlets',.375))
        self.assertEqual(r.interpolate('linear',.5),.75);self.assertAlmostEqual(r.interpolate('cosine',.5),.75)
    def test_fade_modes_power_identity_and_signed_mixing(self):
        for t in(0,.125,.25,.5,.75,.875,1):
            self.assertEqual(r.gain(t,0,2,'lin')+r.gain(t,1,2,'lin'),1)
            self.assertAlmostEqual(sum(r.gain(t,i,2,'eqpower')**2 for i in(0,1)),1)
            self.assertAlmostEqual(sum(r.gain(t,i,2,'cos')**2 for i in(0,1)),1)
        self.assertEqual(op('mix-weight0p25',0),-1.625);self.assertEqual(op('mix-moving-weight',1),-.5)
        self.assertEqual(op('pan-lin-out0',.5),.375);self.assertEqual(op('pan-lin-out1',.5),.375)
        self.assertEqual(op('xfade-lin',.5),.125)
        self.assertNotEqual(op('xfade-eqpower',.5),op('xfade-cos',.25))
    def test_three_channel_negative_wrap_and_periods(self):
        self.assertEqual(op('pan-three-wrap',.125),.75);self.assertEqual(op('xfade-three-wrap',.125),.25)
        for mode in('pan-three-wrap','xfade-three-wrap'):
            self.assertEqual(op(mode,.125),op(mode,.5))
            self.assertEqual(op(mode,.25),op(mode,.625))
        self.assertEqual(op('pan-three-wrap',0),0)
    def test_shaping_thresholds_rounding_and_decay_units(self):
        self.assertEqual(op('kink-slope2p0',.25),.5);self.assertEqual(op('kink-slope2p0',1),1)
        self.assertEqual(op('quantize-q4',.46875),0);self.assertEqual(op('quantize-q4',.53125),.25)
        self.assertEqual(op('smoothstep-rising',.25),0);self.assertEqual(op('smoothstep-falling',.25),1)
        self.assertEqual(op('smoothstep-rising',.5),.5);self.assertEqual(op('smoothstep-falling',.5),.5)
        self.assertEqual(op('trapezoid-plateau',.25),1);self.assertEqual(op('trapezoid-plateau',.875),.5);self.assertEqual(op('trapezoid-plateau',1),0)
        self.assertAlmostEqual(op('t60-decay',0),.001);self.assertAlmostEqual(op('t60time-duration',0),math.log(.001)/math.log(.25))
        self.assertAlmostEqual(op('phasewrap-wide',.5),0)
    def test_signal_phase_varies_within_blocks_and_right_pilot_does_not(self):
        m=model('interp-signal-linear');bs=r.reference_blocks(m,r.input_words())
        self.assertNotEqual(bs[2][0],bs[2][-2]);self.assertEqual(r.value(bs[2][0]),.625);self.assertEqual(r.value(bs[2][-2]),.859375)
        for m in r.MODELS:
            bs=r.reference_blocks(m,r.input_words());self.assertEqual(bs[12],bs[13]);self.assertEqual(bs[13],bs[14])
            self.assertTrue(all(b[1::2]==r.input_words()[1::2]for b in bs));self.assertEqual(len(r.parameter_events(m)),22)
    def test_source_modes_partitions_and_predeclared_limits(self):
        cases=[]
        for i in range(1,5):
            cat=json.loads((HERE/f'part{i}.json').read_bytes());builder.mixing_shaping_catalog(cat);cases+=cat['cases']
            changed=copy.deepcopy(cat);changed['cases'][0]['variant']='other'
            with self.assertRaises(ValueError):builder.mixing_shaping_catalog(changed)
        self.assertEqual(len(cases),63);self.assertEqual(len({s['exact_name']for s in cases}),22)
        self.assertEqual(cases,json.loads((HERE/'catalog.json').read_bytes())['cases']);self.assertEqual(builder.sha(HERE/'reference.py'),builder.MIXING_SHAPING_REFERENCE_SHA)
        for s in cases:
            self.assertEqual(builder.sha(HERE/s['patch']),s['patch_sha256']);self.assertEqual(s['maximum_absolute_error'],r.ABSOLUTE_TOLERANCES[s['model']])
            self.assertIn(s['maximum_absolute_error'],(0,2e-6,1e-4,1e-3))
    def _plan(self,i):
        cat=json.loads((HERE/f'part{i}.json').read_bytes());rows=[]
        for src in cat['cases']:
            row=copy.deepcopy(src);m=src['model'];inputs=r.input_words();bs=r.reference_blocks(m,inputs)
            row.update(source_sha256=src['patch_sha256'],absolute_tolerance=builder.float32(src['maximum_absolute_error']),input_words=list(inputs),expected=list(bs[0]),expected_blocks=[list(b)for b in bs],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in bs for w in b))).hexdigest(),expected_parameter_count=2,parameters=r.parameters(),parameter_events=[dict(before_call=e['before_call'],id=e['id'],parameter_slot=0 if e['id']=='drive'else 1,value_word=r.word(e['value']),normalized_word=r.word((e['value']+8)/16 if e['id']=='drive'else e['value']))for e in r.parameter_events(m)])
            rows.append(row)
        pool,indices=builder.block_pool(rows)
        for row,refs in zip(rows,indices):row['expected_block_indices']=refs;del row['expected_blocks']
        return dict(family='rnbo-mixing-shaping',catalog_sha256=builder.MIXING_SHAPING_PARTITIONS[i],reference_source_sha256=builder.MIXING_SHAPING_REFERENCE_SHA,surface='patcher',partition=cat['partition'],prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,expected_block_storage='shared-512-word-pool',expected_reference_unique_blocks=len(pool),expected_block_pool=[list(b)for b in pool],cases=rows)
    def test_collector_rebinds_exact_mode_outputs_events_and_tolerances(self):
        for i in range(1,5):
            p=self._plan(i);collector.mixing_shaping_plan(p)
            for change in(lambda q:q['cases'][0].update(variant='other'),lambda q:q['cases'][0].update(absolute_tolerance=.001),lambda q:q['cases'][0].update(source_sha256='0'*64),lambda q:q['cases'][0]['parameter_events'][0].update(value_word=0),lambda q:q['expected_block_pool'][0].__setitem__(0,r.word(7)),lambda q:q['cases'].pop(),lambda q:q.update(prepare_zero_warm_blocks=1)):
                changed=copy.deepcopy(p);change(changed)
                with self.assertRaises(ValueError):collector.mixing_shaping_plan(changed)
    def test_parameter_description_order_and_raw_pilot(self):
        p=self._plan(1)
        for row in p['cases']:
            row['parameters'].reverse()
            for e in row['parameter_events']:e['parameter_slot']=1-e['parameter_slot']
        collector.mixing_shaping_plan(p)
        bs=list(r.reference_blocks(3000,r.input_words()));digest=hashlib.sha256(b''.join(struct.pack('<256I',*b[1::2])for b in bs)).hexdigest()
        self.assertTrue(collector.right_pilot_observation(dict(right_output_sha256=digest),bs)['right_pilot_bit_exact'])
        with self.assertRaises(ValueError):collector.right_pilot_observation(dict(right_output_sha256='0'*64),bs)
    def test_fixture_correction_preserves_all_63_references_and_limits(self):
        archive=HERE/'message-to-signal-v1';sp=importlib.util.spec_from_file_location('initial_mixing_ref',archive/'reference.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old)
        for m in r.MODELS:self.assertEqual(old.reference_blocks(m,old.input_words()),r.reference_blocks(m,r.input_words()));self.assertEqual(old.ABSOLUTE_TOLERANCES[m],r.ABSOLUTE_TOLERANCES[m])
        original=json.loads((archive/'catalog.json').read_bytes());changed=[]
        for s in original['cases']:
            if builder.sha(HERE/s['patch'])!=s['patch_sha256']:changed.append(s)
        self.assertEqual(len(changed),11);self.assertTrue(all(s['exact_name']in('pan~','xfade~')for s in changed))
        for entry in json.loads((archive/'source-locations.json').read_bytes()).values():self.assertEqual(builder.sha(archive/entry['path']),entry['sha256'])
    def test_bad_models_input_and_arming_are_rejected(self):
        for m,ins,calls in((True,r.input_words(),20),(2999,r.input_words(),20),(3000,(0,0),20),(3000,r.input_words(),0)):
            with self.assertRaises(ValueError):r.reference_blocks(m,ins,calls)
        with patch.object(r,'parameter_events',return_value=r.parameter_events(3000)[1:]):
            with self.assertRaises(ValueError):r.reference_blocks(3000,r.input_words())
    def test_published_sources_outputs_and_limits_bind_independently(self):
        for i in range(1,5):
            source=f'evidence/xiao-smoke-rnbo-mixing-shaping-part{i}.json';data=json.loads((ROOT/source).read_bytes())
            for j,c in enumerate(data['cases']):
                rec=dict(surface='patcher',id='patcher:'+c['exact_name'],spelling=c['exact_name'])
                self.assertEqual(publisher.checked_short_smoke(rec,dict(source=source,selector=f'/cases/{j}'),data)['status'],c['status'])
            rec=dict(surface='patcher',id='patcher:'+data['cases'][0]['exact_name'],spelling=data['cases'][0]['exact_name'])
            for key,value in(('variant','other'),('hot_inlet',1),('signal_input','other'),('source_sha256','0'*64),('absolute_tolerance',.002),('expected_stream_sha256','0'*64),('right_output_sha256','0'*64)):
                changed=copy.deepcopy(data);changed['cases'][0][key]=value
                with self.assertRaises(ValueError):publisher.checked_short_smoke(rec,dict(source=source,selector='/cases/0'),changed)
    def test_report_keeps_constructor_gaps_and_all_mode_controls(self):
        import build_mixing_shaping_report as report
        d=json.loads(report.products()['evidence/rnbo-mixing-shaping-status.json'])
        self.assertEqual(len(d['cases']),63);self.assertEqual(len(d['objects']),22)
        self.assertEqual(d['summary']['passed'],61);self.assertEqual(d['summary']['outside_screen'],2);self.assertEqual(d['summary']['cpu_review'],5)
        gaps=[c for c in d['cases']if c['status']=='output_mismatch'];self.assertEqual({c['case']for c in gaps},{'interp-spline6','interp-signal-spline6'})
        self.assertEqual(sum(o['status']=='partial'for o in d['objects']),2)
        self.assertTrue(all(c['status']=='pass'for c in d['cases']if c['variant']=='spline6-inlets'))
        self.assertTrue(all(c['cpu_time_saved_percent']is None for c in d['cases']))
if __name__=='__main__':unittest.main()
