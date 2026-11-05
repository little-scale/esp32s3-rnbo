# SPDX-License-Identifier: MIT
"""Lossless bounded list codes, independent routing contracts and evidence guards."""
import copy
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import build_object_status as publisher
import build_event_routing_report as report
ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'tests/fixtures/smoke/rnbo-event-routing'
spec=importlib.util.spec_from_file_location('event_routing_reference',HERE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def model(identity):return next(m for m,s in r.MODEL_SPECS.items()if s['id']==identity)
def op(identity,x):return r.operation(r.spec(model(identity)),x)
class EventRoutingTests(unittest.TestCase):
    def test_all_bounded_lists_have_unique_exact_binary32_codes(self):
        seen=set()
        for size in range(6):
            for values in itertools.product(range(8),repeat=size):
                code=r.encode(values);self.assertNotIn(code,seen);seen.add(code)
                self.assertEqual(r.decode(code),values);self.assertEqual(r.value(r.word(code)),code)
        self.assertEqual(len(seen),sum(8**n for n in range(6)))
        self.assertNotEqual(r.encode([]),r.encode([0]));self.assertNotEqual(r.encode([0]),r.encode([0,0]))
        self.assertNotEqual(r.encode([1,2]),r.encode([2,1]))
    def test_invalid_observer_domain_is_rejected(self):
        for x in((0,)*6,[-1],[8],[1.],None):
            with self.assertRaises(ValueError):r.encode(x)
        for x in(-1,True,8,32769+8**1,196608):
            with self.assertRaises(ValueError):r.decode(x)
    def test_lists_are_unsorted_tagged_and_independently_varied(self):
        values=[e['value']for e in r.drive_events(2800)]
        self.assertEqual({int(x)for x in values},set(range(4)))
        self.assertEqual({int((x-int(x))*8)for x in values},set(range(8)))
        self.assertTrue(any(r.input_list(x)!=sorted(r.input_list(x))for x in values))
        self.assertTrue(any(len(set(r.input_list(x)))<3 for x in values))
        self.assertEqual(r.input_list(.125),[7,0,1]);self.assertEqual(r.input_list(.125,True),[0,7,1])
    def test_independent_list_landmarks_preserve_order_and_lengths(self):
        x=.125
        for identity,wanted in(('append-two-values',[7,0,1,4,5]),('prepend-two-values',[4,5,7,0,1]),
                ('join-two-inputs',[7,0,1,4,5]),('list-join-two-values',[7,0,1,4,5]),('list-reverse',[1,0,7]),
                ('list-rotate-left',[0,1,7]),('list-rotate-right',[1,7,0]),('list-slice-out0',[7]),('list-slice-out1',[0,1]),
                ('list-ecils-out0',[7,0]),('list-ecils-out1',[1]),('list-sub-out0',[2]),('list-sub-out1',1),
                ('list-intersection',[1]),('list-swap-zero-two',[1,0,7]),('list-sort-ascending',[0,1,7]),
                ('list-sort-descending',[7,1,0]),('list-median',1),('list-sum',8),('list-len',3),
                ('list-nth-element',0),('list-nth-replacement',[7,6,1]),('list-mth-out0',0),('list-mth-out1',[7,1]),
                ('list-index-out0',0),('list-index-out1',[7,1])):
            self.assertEqual(op(identity,x),wanted,identity)
    def test_pak_cold_input_and_unjoin_extra_outlets(self):
        self.assertEqual(op('pak-cold-input',.125),[0,1,0])
        for i,v in enumerate((7,0,1)):self.assertEqual(op('unpack-out'+str(i),.125),v)
        self.assertEqual(op('unjoin-single-out2',.125),[1]);self.assertEqual(op('unjoin-pair-out0',.125),[7,0])
        self.assertEqual(op('unjoin-pair-out1',.125),[1])
        self.assertNotEqual(r.encode(r.CONTROL_LISTS[1]),r.encode(r.CONTROL_LISTS[2]))
    def test_routepass_retains_selector_and_unmatched_routes_hold(self):
        self.assertEqual(op('route-out0',1.5),[6,4]);self.assertEqual(op('routepass-out0',1.5),[1,6,4])
        self.assertEqual(op('route-out2',.125),[0,7,1]);self.assertIsNone(op('route-out1',1.5))
        self.assertEqual(op('gate-out0',1.5),5.5);self.assertIsNone(op('gate-out1',1.5))
        self.assertEqual(op('switch-three-inputs',2.875),7.875);self.assertIsNone(op('switch-three-inputs',.125))
        self.assertEqual(op('split-out0',1.),1.);self.assertIsNone(op('split-out0',2.125))
    def test_selects_count_bangs_and_swap_checks_outlet_order(self):
        for n in('sel','select'):
            self.assertEqual(op(n+'-out0',1.5),1);self.assertIsNone(op(n+'-out0',2.875))
            m=model(n+'-out2');bs=r.reference_blocks(m,r.input_words())
            expected=sum(int(e['value'])not in(1,2)for e in r.drive_events(m))
            self.assertEqual(r.value(bs[-1][0]),expected)
        self.assertEqual(op('swap-out0',1.5),6);self.assertEqual(op('swap-out1',1.5),4)
        self.assertEqual(op('swap-right-before-left',1.5),2)
    def test_sources_partitions_alias_docs_and_zero_limits_are_fixed(self):
        all_cases=[]
        for i in range(1,5):
            cat=json.loads((HERE/f'part{i}.json').read_bytes());builder.event_routing_catalog(cat);all_cases+=cat['cases']
            changed=copy.deepcopy(cat);changed['cases'][0]['output_kind']='other'
            with self.assertRaises(ValueError):builder.event_routing_catalog(changed)
        self.assertEqual(len(all_cases),62);self.assertEqual(len({s['exact_name']for s in all_cases}),30)
        self.assertEqual(all_cases,json.loads((HERE/'catalog.json').read_bytes())['cases'])
        for s in all_cases:
            self.assertEqual(builder.sha(HERE/s['patch']),s['patch_sha256']);self.assertEqual(s['maximum_absolute_error'],0)
            if s['exact_name']in('pak','routepass'):
                self.assertTrue(s['reference_sources'][0]['local_package_path'].endswith('rnbo_'+s['exact_name']+'.maxref.xml'))
    def _plan(self,i):
        cat=json.loads((HERE/f'part{i}.json').read_bytes());rows=[]
        for src in cat['cases']:
            row=copy.deepcopy(src);m=src['model'];inputs=r.input_words();bs=r.reference_blocks(m,inputs)
            row.update(source_sha256=src['patch_sha256'],absolute_tolerance=0.,input_words=list(inputs),expected=list(bs[0]),
                expected_blocks=[list(b)for b in bs],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in bs for w in b))).hexdigest(),
                expected_parameter_count=2,parameters=r.parameters(),parameter_events=[dict(before_call=e['before_call'],id=e['id'],parameter_slot=0 if e['id']=='drive'else 1,
                    value_word=r.word(e['value']),normalized_word=r.word((e['value']+8)/16 if e['id']=='drive'else e['value']))for e in r.parameter_events(m)])
            rows.append(row)
        pool,indices=builder.block_pool(rows)
        for row,refs in zip(rows,indices):row['expected_block_indices']=refs;del row['expected_blocks']
        return dict(family='rnbo-event-routing',catalog_sha256=builder.EVENT_ROUTING_PARTITIONS[i],reference_source_sha256=builder.EVENT_ROUTING_REFERENCE_SHA,
            surface='patcher',partition=cat['partition'],prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,
            expected_block_storage='shared-512-word-pool',expected_reference_unique_blocks=len(pool),expected_block_pool=[list(b)for b in pool],cases=rows)
    def test_collector_rejects_changed_sources_list_codes_order_and_limits(self):
        for i in range(1,5):
            p=self._plan(i);collector.event_routing_plan(p)
            for change in(lambda q:q['cases'][0].update(output_kind='other'),lambda q:q['cases'][0].update(absolute_tolerance=1e-6),
                    lambda q:q['cases'][0]['parameter_events'][0].update(value_word=r.word(0.)),lambda q:q['cases'][0].update(source_sha256='0'*64),
                    lambda q:q['expected_block_pool'][0].__setitem__(0,r.word(1.)),lambda q:q['cases'].pop()):
                changed=copy.deepcopy(p);change(changed)
                with self.assertRaises(ValueError):collector.event_routing_plan(changed)
    def test_raw_right_capture_is_independent(self):
        bs=[list(b)for b in r.reference_blocks(2800,r.input_words())]
        digest=lambda b:hashlib.sha256(b''.join(struct.pack('<256I',*v[1::2])for v in b)).hexdigest()
        self.assertTrue(collector.right_pilot_observation(dict(right_output_sha256=digest(bs)),bs)['right_pilot_bit_exact'])
        changed=copy.deepcopy(bs);changed[-1][3]^=1
        with self.assertRaises(ValueError):collector.right_pilot_observation(dict(right_output_sha256=digest(changed)),bs)
    def test_invalid_models_inputs_and_arming_are_rejected(self):
        for m,ins,calls in((True,r.input_words(),20),(2799,r.input_words(),20),(2800,(0,0),20),(2800,r.input_words(),0)):
            with self.assertRaises(ValueError):r.reference_blocks(m,ins,calls)
        actions=r.parameter_events(2800)[1:]
        with patch.object(r,'parameter_events',return_value=actions):
            with self.assertRaises(ValueError):r.reference_blocks(2800,r.input_words())
    def test_no_match_observation_fix_preserves_all_original_goldens(self):
        archive=HERE/'unobserved-no-match-v1';spec=importlib.util.spec_from_file_location('original_routing_reference',archive/'reference.py')
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        for m in r.MODELS:
            self.assertEqual(old.reference_blocks(m,old.input_words()),r.reference_blocks(m,r.input_words()))
            self.assertEqual(old.ABSOLUTE_TOLERANCES[m],r.ABSOLUTE_TOLERANCES[m])
        locations=json.loads((archive/'source-locations.json').read_bytes())['sources']
        for entry in locations.values():self.assertEqual(builder.sha(archive/entry['path']),entry['sha256'])
        changed=[s['id']for s in json.loads((archive/'catalog.json').read_bytes())['cases']if builder.sha(HERE/s['patch'])!=s['patch_sha256']]
        self.assertEqual(set(changed),{'list-intersection','list-sub-out0'})
    def test_published_cases_bind_exact_forms_codes_and_pilot(self):
        for i in range(1,5):
            source=f'evidence/xiao-smoke-rnbo-event-routing-part{i}.json';data=json.loads((ROOT/source).read_bytes())
            for j,c in enumerate(data['cases']):
                record=dict(surface='patcher',id='patcher:'+c['exact_name'],spelling=c['exact_name'])
                self.assertEqual(publisher.checked_short_smoke(record,dict(source=source,selector=f'/cases/{j}'),data)['status'],c['status'])
            record=dict(surface='patcher',id='patcher:'+data['cases'][0]['exact_name'],spelling=data['cases'][0]['exact_name'])
            for k,v in(('variant','other'),('source_sha256','0'*64),('absolute_tolerance',1e-6),('expected_stream_sha256','0'*64),('right_output_sha256','0'*64)):
                changed=copy.deepcopy(data);changed['cases'][0][k]=v
                with self.assertRaises(ValueError):publisher.checked_short_smoke(record,dict(source=source,selector='/cases/0'),changed)
            for group in('compile_failures','admission_failures'):
                for j,c in enumerate(data.get(group,[])):
                    record=report.record_for(c);item=dict(source=source,selector=f'/{group}/{j}')
                    publisher.checked_routing_rejection(record,item,data)
                    changed=copy.deepcopy(data);changed[group][j]['source_sha256']='0'*64
                    with self.assertRaises(ValueError):publisher.checked_routing_rejection(record,item,changed)
    def test_target_fault_cannot_be_promoted_to_output_or_finalization_pass(self):
        data=json.loads((ROOT/'evidence/xiao-event-routing-rotation-fault.json').read_bytes());record=report.record_for(dict(exact_name='list.rot'))
        publisher.checked_routing_target_fault(record,{},data)
        for k,v in(('event_status',0),('output_words_checked',10240),('numeric_pass_claimed',True),('finalization_checked',True),('source_sha256','0'*64)):
            changed=dict(data);changed[k]=v
            with self.assertRaises(ValueError):publisher.checked_routing_target_fault(record,{},changed)
    def test_complete_report_keeps_all_62_source_outcomes(self):
        products=report.products();data=json.loads(products['evidence/rnbo-event-routing-status.json'])
        self.assertEqual(len(data['cases']),62);self.assertEqual(len(data['objects']),30)
        self.assertEqual(data['summary']['target_completed'],58);self.assertEqual(data['summary']['target_event_faults'],1);self.assertEqual(data['summary']['target_compile_failures'],3)
    def test_mixed_target_success_and_rejections_stay_partial(self):
        coverage=json.loads((ROOT/'site/data/coverage.json').read_bytes());inventory=json.loads((ROOT/'site/data/inventory.json').read_bytes())
        rows={x['id']:x for x in publisher.make_status(inventory,coverage)['objects']}
        for name in('list.rot','message'):
            row=rows['patcher:'+name];self.assertEqual(row['working']['status'],'partial')
            self.assertTrue(row['board_evidence']);self.assertTrue(all(c['status']=='pass'for c in row['hardware_smoke']))
            changed=copy.deepcopy(coverage);record=next(c for c in changed['objects']if c['id']=='patcher:'+name)
            record['qualification']=[q for q in record['qualification']if q.get('evidence_kind')not in('rnbo-routing-rejection','xiao-routing-event-fault')]
            with self.assertRaises(ValueError):publisher.make_status(inventory,changed)
