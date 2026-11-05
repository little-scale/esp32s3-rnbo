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
HERE=ROOT/'tests/fixtures/smoke/rnbo-analysis-timing'
spec=importlib.util.spec_from_file_location('analysis_timing_reference',HERE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def model(identity):return next(m for m,s in r.MODEL_SPECS.items()if s['id']==identity)
class AnalysisTimingTests(unittest.TestCase):
    def blocks(self,identity):return r.reference_blocks(model(identity),r.input_words())
    def values(self,identity,call):return tuple(map(r.value,self.blocks(identity)[call][::2]))
    def test_manual_reports_distinguish_mean_absolute_peak_and_last(self):
        mean=sum(abs(x)for x in r.LEFT)/16
        self.assertEqual(self.values('avg-manual',1),(mean,)*256)
        self.assertEqual(self.values('peakamp-manual',1),(1.,)*256)
        self.assertEqual(self.values('snapshot-manual',1),(-.125,)*256)
        self.assertEqual(self.values('avg-manual',2),(2*mean,)*256)
        # Three bangs before call10: two empty report windows; snapshot retains last.
        self.assertEqual(self.values('avg-manual',10),(0.,)*256)
        self.assertEqual(self.values('peakamp-manual',10),(0.,)*256)
        self.assertEqual(self.values('snapshot-manual',10),(-1.,)*256)
    def test_threshold_equal_and_hysteresis_boundaries(self):
        self.assertEqual(self.values('thresh-equal-zero',2),(1.,)*256)
        self.assertEqual(self.values('thresh-hysteresis',2),(0.,)*256)
        self.assertEqual(self.values('thresh-equal-positive',2),(0.,)*256)
        vals=self.values('thresh-signal-hysteresis',2)
        self.assertEqual(vals[:8],(0.,1.,0.,1.,0.,1.,0.,1.))
        self.assertEqual(self.values('thresh-signal-equal-zero',2)[:3],(1.,1.,0.))
    def test_crossings_zero_and_repeated_events(self):
        vals=[self.values('zerox-events',i)[0]for i in range(6)]
        self.assertEqual(vals,[0.,1.,1.,0.,1.,0.])
        self.assertEqual(self.values('zerox-count-2',1),(1.,)*256)
        self.assertEqual(self.values('zerox-count-3',2),(2.,)*256)
        self.assertEqual(self.values('zerox-count-7',6),(4.,)*256)
    def test_running_mean_absolute_and_rms_use_partial_window(self):
        self.assertEqual(self.values('average-seven',1),(-.5,)*256)
        self.assertEqual(self.values('average_absolute-seven',1),(1.5,)*256)
        self.assertAlmostEqual(self.values('average_rms-seven',1)[0],(2.5)**.5,places=6)
        # At call10 there have been13 values; only last7 contribute.
        window=r._DRIVES[6:13]
        self.assertAlmostEqual(self.values('average-seven',10)[0],sum(window)/7,places=6)
    def test_clocks_vary_within_block_and_continue_without_host_resets(self):
        for ident in('samplecount-signal','currentsampletime-signal','elapsed-free'):
            self.assertEqual(self.values(ident,0),tuple(map(float,range(256))))
            self.assertEqual(self.values(ident,19)[-1],5119.)
        self.assertEqual(self.values('currentsampletime',19),(4864.,)*256)
        self.assertAlmostEqual(self.values('currenttime-signal',19)[-1],5119000/44100,places=5)
        self.assertEqual(self.values('elapsed-reset',13)[0],256.)
        self.assertEqual(self.values('elapsed-reset',14)[0],512.)
        self.assertEqual(self.values('elapsed-reset',15)[0],0.)
    def test_catalog_exact_sources_and_predeclared_limits(self):
        cases=[]
        for i in(1,2):
            cat=json.loads((HERE/f'part{i}.json').read_bytes());builder.analysis_timing_catalog(cat);cases+=cat['cases']
            changed=copy.deepcopy(cat);changed['cases'][0]['variant']='other'
            with self.assertRaises(ValueError):builder.analysis_timing_catalog(changed)
        self.assertEqual(len(cases),23);self.assertEqual(len({s['exact_name']for s in cases}),16)
        self.assertEqual(cases,json.loads((HERE/'catalog.json').read_bytes())['cases']);self.assertEqual(builder.sha(HERE/'reference.py'),builder.ANALYSIS_TIMING_REFERENCE_SHA)
        for s in cases:
            self.assertEqual(builder.sha(HERE/s['patch']),s['patch_sha256']);self.assertEqual(s['maximum_absolute_error'],r.ABSOLUTE_TOLERANCES[s['model']])
            self.assertIn(s['maximum_absolute_error'],(0,2e-6,2e-5))
    def test_bad_models_input_and_missing_arm_rejected(self):
        for m,ins,calls in((True,r.input_words(),20),(3299,r.input_words(),20),(3300,(0,0),20),(3300,r.input_words(),0)):
            with self.assertRaises(ValueError):r.reference_blocks(m,ins,calls)
        with patch.object(r,'parameter_events',return_value=r.parameter_events(3300)[1:]):
            with self.assertRaises(ValueError):r.reference_blocks(3300,r.input_words())
    def _plan(self,i):
        cat=json.loads((HERE/f'part{i}.json').read_bytes());rows=[]
        for src in cat['cases']:
            row=copy.deepcopy(src);m=src['model'];inputs=r.input_words();bs=r.reference_blocks(m,inputs)
            row.update(arena_bytes=1048576,source_sha256=src['patch_sha256'],absolute_tolerance=builder.float32(src['maximum_absolute_error']),input_words=list(inputs),expected=list(bs[0]),expected_blocks=[list(b)for b in bs],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in bs for w in b))).hexdigest(),expected_parameter_count=2,parameters=r.parameters(),parameter_events=[dict(before_call=e['before_call'],id=e['id'],parameter_slot=0 if e['id']=='drive'else 1,value_word=r.word(e['value']),normalized_word=r.word((e['value']+8)/16 if e['id']=='drive'else e['value']))for e in r.parameter_events(m)])
            rows.append(row)
        pool,indices=builder.block_pool(rows)
        for row,refs in zip(rows,indices):row['expected_block_indices']=refs;del row['expected_blocks']
        return dict(family='rnbo-analysis-timing',catalog_sha256=builder.ANALYSIS_TIMING_PARTITIONS[i],reference_source_sha256=builder.ANALYSIS_TIMING_REFERENCE_SHA,surface='patcher',partition=cat['partition'],prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,expected_block_storage='shared-512-word-pool',expected_reference_unique_blocks=len(pool),expected_block_pool=[list(b)for b in pool],cases=rows)
    def test_collector_rebinds_exact_mode_outputs_events_and_tolerances(self):
        for i in range(1,3):
            p=self._plan(i);collector.analysis_timing_plan(p)
            for change in(lambda q:q['cases'][0].update(arena_bytes=4096),lambda q:q['cases'][0].update(variant='other'),lambda q:q['cases'][0].update(absolute_tolerance=.001),lambda q:q['cases'][0].update(source_sha256='0'*64),lambda q:q['cases'][0]['parameter_events'][0].update(value_word=0),lambda q:q['expected_block_pool'][0].__setitem__(0,r.word(7)),lambda q:q['cases'].pop(),lambda q:q.update(prepare_zero_warm_blocks=1)):
                changed=copy.deepcopy(p);change(changed)
                with self.assertRaises(ValueError):collector.analysis_timing_plan(changed)
    def test_parameter_description_order_and_raw_pilot(self):
        p=self._plan(1)
        for row in p['cases']:
            row['parameters'].reverse()
            for e in row['parameter_events']:e['parameter_slot']=1-e['parameter_slot']
        collector.analysis_timing_plan(p)
        bs=list(r.reference_blocks(3300,r.input_words()));digest=hashlib.sha256(b''.join(struct.pack('<256I',*b[1::2])for b in bs)).hexdigest()
        self.assertTrue(collector.right_pilot_observation(dict(right_output_sha256=digest),bs)['right_pilot_bit_exact'])
        with self.assertRaises(ValueError):collector.right_pilot_observation(dict(right_output_sha256='0'*64),bs)
    def test_published_sources_outputs_and_limits_bind_independently(self):
        for i in range(1,3):
            source=f'evidence/xiao-smoke-rnbo-analysis-timing-part{i}.json';data=json.loads((ROOT/source).read_bytes())
            for j,c in enumerate(data['cases']):
                rec=dict(surface='patcher',id='patcher:'+c['exact_name'],spelling=c['exact_name'])
                self.assertEqual(publisher.checked_short_smoke(rec,dict(source=source,selector=f'/cases/{j}'),data)['status'],c['status'])
            rec=dict(surface='patcher',id='patcher:'+data['cases'][0]['exact_name'],spelling=data['cases'][0]['exact_name'])
            for key,value in(('arena_capacity',4096),('variant','other'),('hot_inlet',1),('signal_input','other'),('source_sha256','0'*64),('absolute_tolerance',.002),('expected_stream_sha256','0'*64),('right_output_sha256','0'*64)):
                changed=copy.deepcopy(data);changed['cases'][0][key]=value
                with self.assertRaises(ValueError):publisher.checked_short_smoke(rec,dict(source=source,selector='/cases/0'),changed)
    def test_report_retains_all_four_timing_screens_and_resource_scope(self):
        import build_analysis_timing_report as report
        d=json.loads(report.products()['evidence/rnbo-analysis-timing-status.json'])
        self.assertEqual(d['summary']['source_scenarios'],23);self.assertEqual(d['summary']['exact_spellings'],16)
        self.assertEqual(d['summary']['passed'],19);self.assertEqual(d['summary']['outside_screen'],4)
        self.assertEqual({c['case']for c in d['cases']if c['status']!='pass'},{'avg-manual','currentsampletime-signal','currenttime','currenttime-signal'})
        self.assertEqual(d['summary']['cpu_review'],0);self.assertEqual(d['cpu_review_queue_after'],164)
        self.assertTrue(all(c['arena_capacity']==1048576 and c['cpu_time_saved_percent']is None for c in d['cases']))
        averages=[c for c in d['cases']if c['case'].startswith(('average-','average_absolute-','average_rms-'))]
        self.assertEqual(len(averages),3);self.assertTrue(all(c['arena_high_water']==352880 for c in averages))
if __name__=='__main__':unittest.main()
