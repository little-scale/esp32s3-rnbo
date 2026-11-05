# SPDX-License-Identifier: MIT
"""Event-prefix/reset contracts, observer integrity and source/stream mutations."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import build_object_status as publisher
import build_event_state_report as report
ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'tests/fixtures/smoke/rnbo-event-state'
spec=importlib.util.spec_from_file_location('event_state_reference',HERE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def model(identity):return next(m for m,s in r.MODEL_SPECS.items()if s['id']==identity)
def outputs(identity):return tuple(map(r.value,r.event_outputs(model(identity))))

class EventStateTests(unittest.TestCase):
    def test_prefixes_neutral_resets_and_duplicate_events(self):
        self.assertEqual(outputs('accum-prefix')[:9],(1,-1,-1,-.5,-1,-2.5,-.5,1.5,-6.5))
        self.assertEqual(outputs('accum-neutral-reset')[:9],(1,-1,0,.5,0,-1.5,.5,2.5,-5.5))
        self.assertEqual(outputs('mulequals-prefix')[:9],(1,-2,-2,-1,.5,-.75,-1.5,-3,24))
        self.assertEqual(outputs('mulequals-neutral-reset')[:9],(1,-2,1,.5,-.25,.375,.75,1.5,-12))
        self.assertEqual(outputs('accum-prefix'),outputs('plusequals-prefix'))
        self.assertEqual(outputs('accum-prefix'),outputs('plus-assign-prefix'))
        self.assertEqual(outputs('mulequals-prefix'),outputs('multiply-assign-prefix'))
    def test_change_observers_detect_suppression_and_transitions(self):
        self.assertEqual(outputs('change-changed-value-sum')[:9],(1,-1,-1,-.5,-1,-2.5,-.5,-.5,-8.5))
        self.assertEqual(outputs('change-rise-count')[:9],(1,1,1,2,2,2,2,2,2))
        self.assertEqual(outputs('change-fall-count')[:9],(0,0,1,1,1,1,1,1,1))
    def test_counter_directions_and_explicit_resets(self):
        for identity,wanted in(('counter-up',(0,1,2,3,0,1,2,3)),('counter-down',(0,3,2,1,0,3,2,1)),
                               ('counter-bounce',(0,1,2,3,2,1,0,1)),('counter-negative-up',(-2,-1,0,1,2,-2,-1,0))):
            self.assertEqual(outputs(identity)[:8],wanted)
        for identity in('counter-reset-next','counter-reset-now'):
            self.assertEqual(outputs(identity),tuple(e['value']for e in r.drive_events(model(identity))))
    def test_latch_peaks_and_trigger_order_landmarks(self):
        self.assertEqual(set(outputs('latch-closed')),{0})
        self.assertEqual(outputs('latch-positive-control')[:9],(1,1,1,.5,.5,.5,2,2,2))
        self.assertEqual(outputs('peak-value')[:10],(1,1,1,1,1,1,2,2,2,8))
        self.assertEqual(outputs('trough-value')[:10],(0,-2,-2,-2,-2,-2,-2,-2,-8,-8))
        for op in('peak','trough'):
            self.assertTrue(all(a+b==1 for a,b in zip(outputs(op+'-new-flag'),outputs(op+'-not-new-flag'))))
        self.assertEqual(outputs('t-right-before-left'),outputs('trigger-right-before-left'))
        self.assertEqual(outputs('t-right-before-left'),tuple(-e['value']for e in r.drive_events(model('t-right-before-left'))))
    def test_rational_smoothing_and_edge_capture_are_distinct(self):
        self.assertEqual(outputs('slide-up2-down4')[:3],(.5,-.125,-.0625))
        self.assertEqual(outputs('rampsmooth-up2-down4')[:3],(.5,-.125,-.0625))
        self.assertEqual(outputs('slide-up2-down4')[7],1.41357421875)
        self.assertEqual(outputs('rampsmooth-up2-down4')[7],2.)
        self.assertEqual(outputs('sah-threshold-zero')[:8],(1,1,1,.5,.5,.5,2,2))
        self.assertEqual(outputs('sah-threshold-half')[:8],(1,1,1,1,1,1,2,2))
        for m,s in r.MODEL_SPECS.items():self.assertEqual(r.ABSOLUTE_TOLERANCES[m],2e-6 if s['operation']in('slide','rampsmooth')else 0)
    def test_ordered_actions_and_holds(self):
        for m in r.MODELS:
            events=r.parameter_events(m);bs=r.reference_blocks(m,r.input_words());values=r.event_outputs(m)
            self.assertEqual(len(events),22);self.assertEqual(len(bs),20)
            self.assertEqual(bs[10][0],values[12]);self.assertEqual(bs[12],bs[13]);self.assertEqual(bs[13],bs[14])
            self.assertTrue(all(b[1::2]==r.input_words()[1::2]for b in bs))
            self.assertTrue(all(len(set(b[::2]))==1 for b in bs))
    def test_sources_aliases_and_catalog_are_fixed(self):
        combined=[]
        for i in(1,2):
            c=json.loads((HERE/f'part{i}.json').read_bytes());builder.event_state_catalog(c);combined+=c['cases']
            changed=copy.deepcopy(c);changed['cases'][0]['variant']='other'
            with self.assertRaises(ValueError):builder.event_state_catalog(changed)
        self.assertEqual(len(combined),36);self.assertEqual(len({x['exact_name']for x in combined}),15)
        self.assertEqual(combined,json.loads((HERE/'catalog.json').read_bytes())['cases'])
        self.assertEqual(builder.sha(HERE/'reference.py'),builder.EVENT_STATE_REFERENCE_SHA)
        for c in combined:self.assertEqual(builder.sha(HERE/c['patch']),c['patch_sha256'])
    def _plan(self,i):
        cat=json.loads((HERE/f'part{i}.json').read_bytes());rows=[]
        for src in cat['cases']:
            row=copy.deepcopy(src);m=src['model'];inputs=r.input_words();bs=r.reference_blocks(m,inputs)
            row.update(source_sha256=src['patch_sha256'],absolute_tolerance=builder.float32(src['maximum_absolute_error']),input_words=list(inputs),expected=list(bs[0]),
                expected_blocks=[list(b)for b in bs],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in bs for w in b))).hexdigest(),
                expected_parameter_count=2,parameters=r.parameters(),
                parameter_events=[dict(before_call=e['before_call'],id=e['id'],parameter_slot=0 if e['id']=='drive'else 1,value_word=r.word(e['value']),normalized_word=r.word((e['value']+8)/16 if e['id']=='drive'else e['value']))for e in r.parameter_events(m)])
            rows.append(row)
        pool,indices=builder.block_pool(rows)
        for row,refs in zip(rows,indices):row['expected_block_indices']=refs;del row['expected_blocks']
        return dict(family='rnbo-event-state',catalog_sha256=builder.EVENT_STATE_PARTITIONS[i],reference_source_sha256=builder.EVENT_STATE_REFERENCE_SHA,
            surface='patcher',partition=cat['partition'],prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,
            expected_block_storage='shared-512-word-pool',expected_reference_unique_blocks=len(pool),expected_block_pool=[list(b)for b in pool],cases=rows)
    def test_collector_rebinds_scenario_state_stream_and_order(self):
        for i in(1,2):
            p=self._plan(i);collector.event_state_plan(p)
            for change in(lambda q:q['cases'][0].update(variant='other'),lambda q:q['cases'][0].update(absolute_tolerance=.001),
                          lambda q:q['cases'][0]['parameter_events'][0].update(value_word=r.word(7.)),
                          lambda q:q['cases'][0].update(source_sha256='0'*64),lambda q:q['expected_block_pool'][0].__setitem__(0,r.word(7.)),
                          lambda q:q.update(prepare_zero_warm_blocks=1),lambda q:q['cases'].pop()):
                changed=copy.deepcopy(p);change(changed)
                with self.assertRaises(ValueError):collector.event_state_plan(changed)
    def test_parameter_ids_survive_description_reordering(self):
        p=self._plan(1)
        for row in p['cases']:
            row['parameters'].reverse()
            for e in row['parameter_events']:e['parameter_slot']=1-e['parameter_slot']
        collector.event_state_plan(p)
        p['cases'][0]['parameter_events'][0]['parameter_slot']=1-p['cases'][0]['parameter_events'][0]['parameter_slot']
        with self.assertRaises(ValueError):collector.event_state_plan(p)
    def test_arming_preserves_original_expectations_and_is_not_optional(self):
        old_spec=importlib.util.spec_from_file_location('startup_exposed_reference',HERE/'startup-exposed-v1/reference.py')
        old=importlib.util.module_from_spec(old_spec);old_spec.loader.exec_module(old)
        for m in r.MODELS:
            self.assertEqual(old.reference_blocks(m,old.input_words()),r.reference_blocks(m,r.input_words()))
            self.assertEqual(old.ABSOLUTE_TOLERANCES[m],r.ABSOLUTE_TOLERANCES[m])
            graph=json.loads((HERE/(r.MODEL_NAMES[m]+'.rnbopat')).read_bytes())['patcher']
            texts={b['box']['id']:b['box']['text']for b in graph['boxes']}
            self.assertEqual(texts['armed-input'],'gate 1 0');self.assertEqual(texts['arm-order'],'t f f')
            actions=r.parameter_events(m)
            self.assertEqual(actions[0],dict(before_call=0,id='arm',value=1.));self.assertEqual(len(actions),22)
        actions=r.parameter_events(2700)[1:]
        with patch.object(r,'parameter_events',return_value=actions):
            with self.assertRaises(ValueError):r.reference_blocks(2700,r.input_words())
    def test_raw_right_observer_cannot_accept_numeric_tolerance(self):
        bs=[list(b)for b in r.reference_blocks(2700,r.input_words())]
        digest=lambda b:hashlib.sha256(b''.join(struct.pack('<256I',*v[1::2])for v in b)).hexdigest()
        self.assertTrue(collector.right_pilot_observation(dict(right_output_sha256=digest(bs)),bs)['right_pilot_bit_exact'])
        for index in(1,3,5,31):
            changed=copy.deepcopy(bs);changed[-1][index]^=1
            with self.assertRaises(ValueError):collector.right_pilot_observation(dict(right_output_sha256=digest(changed)),bs)
    def test_invalid_models_inputs_schedules_and_call_counts(self):
        for m,inputs,calls in((True,r.input_words(),20),(2699,r.input_words(),20),(2700,(0,0),20),(2700,r.input_words(),0),(2700,r.input_words(),True)):
            with self.assertRaises(ValueError):r.reference_blocks(m,inputs,calls)
        bad=r.parameter_events(2700);bad.reverse()
        with patch.object(r,'parameter_events',return_value=bad):
            with self.assertRaises(ValueError):r.reference_blocks(2700,r.input_words())
    def test_published_scenarios_bind_state_and_raw_capture(self):
        for i in(1,2):
            source=f'evidence/xiao-smoke-rnbo-event-state-part{i}.json';data=json.loads((ROOT/source).read_bytes())
            for j,c in enumerate(data['cases']):
                record=dict(surface='patcher',id='patcher:'+c['exact_name'],spelling=c['exact_name'])
                self.assertEqual(publisher.checked_short_smoke(record,dict(source=source,selector=f'/cases/{j}'),data)['status'],c['status'])
            record=dict(surface='patcher',id='patcher:'+data['cases'][0]['exact_name'],spelling=data['cases'][0]['exact_name'])
            for k,v in(('variant','other'),('source_sha256','0'*64),('absolute_tolerance',.001),('expected_stream_sha256','0'*64),('right_output_sha256','0'*64)):
                changed=copy.deepcopy(data);changed['cases'][0][k]=v
                with self.assertRaises(ValueError):publisher.checked_short_smoke(record,dict(source=source,selector='/cases/0'),changed)
    def test_report_completeness_and_restoration_binding(self):
        products=report.products();summary=json.loads(products['evidence/rnbo-event-state-status.json'])['summary']
        self.assertEqual(summary['executed'],36);self.assertEqual(summary['exact_spellings'],15)
        self.assertEqual(summary['drive_events'],756);self.assertEqual(summary['arm_events'],36)
        original=Path.read_bytes
        def changed(path):
            raw=original(path)
            if path.name=='xiao-smoke-rnbo-event-state-player-restoration.json':
                v=json.loads(raw);v['test_result_sha256']='0'*64;return json.dumps(v).encode()
            return raw
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaises(ValueError):report.products()
