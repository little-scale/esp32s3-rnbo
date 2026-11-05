# SPDX-License-Identifier: MIT
"""List state landmarks, whole-source ledger, stream and pilot provenance guards."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import tempfile
from unittest.mock import patch
import build_object_status as publisher
import build_list_extended_report as report
import collect_list_extended_fault as fault_collector
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'tests/fixtures/smoke/rnbo-list-extended'
spec=importlib.util.spec_from_file_location('list_extended_reference',HERE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def model(identity):return next(m for m,s in r.MODEL_SPECS.items()if s['id']==identity)
def outputs(identity):return tuple(map(r.value,r.event_outputs(model(identity))))
class ExtendedListTests(unittest.TestCase):
    def test_list_order_length_and_trailing_zero_landmarks(self):
        self.assertEqual(outputs('list-thin')[0],r.encode([7,0]))
        self.assertEqual(outputs('list-thin')[1],r.encode([6,1,4]))
        self.assertEqual(outputs('list-unique')[1],r.encode([6]))
        self.assertEqual(outputs('list-filter-out0')[1],r.encode([6]))
        self.assertEqual(outputs('list-filter-out1')[1],r.encode([0]))
        self.assertEqual(outputs('list-union')[0],r.encode([7,0,0,1,4]))
        self.assertEqual(outputs('list-lace')[0],r.encode([7,1,0,4]))
        self.assertEqual(outputs('list-delace-out0')[0],r.encode([7,0]))
        self.assertEqual(outputs('list-delace-out1')[0],r.encode([0]))
        self.assertNotEqual(r.encode([0]),r.encode([0,0]))
    def test_repetition_comparison_and_suppression(self):
        self.assertEqual(outputs('list-compare-out0')[:4],(0,1,1,0))
        self.assertEqual(outputs('list-compare-out1')[:4],(r.encode([0,1]),)*4)
        self.assertEqual(outputs('list-change-flag')[:4],(1,1,0,1))
        self.assertEqual(outputs('list-change-emission-sum')[:3],(r.encode([7,0,0]),r.encode([7,0,0])+r.encode([6,1,4]),r.encode([7,0,0])+r.encode([6,1,4])))
        self.assertEqual(outputs('list-reg-hot'),outputs('list-reg-cold-store-bang'))
    def test_indexing_and_group_stream_boundaries(self):
        self.assertEqual(outputs('list-indexmap')[:2],(r.encode([0,7]),r.encode([4,6])))
        self.assertEqual(outputs('list-lookup')[:2],(r.encode([2,2]),r.encode([5,2])))
        self.assertEqual(outputs('list-group-three')[:4],(0,0,r.encode([0,4,4]),r.encode([0,4,4])))
        self.assertEqual(outputs('list-stream-forward')[:4],(0,0,r.encode([0,4,4]),r.encode([4,4,7])))
        self.assertEqual(outputs('list-stream-reverse')[:4],(0,0,r.encode([4,4,0]),r.encode([7,4,4])))
        self.assertEqual(outputs('list-stream-ready')[:4],(0,0,1,1))
    def test_fifo_lifo_and_size_have_distinct_landmarks(self):
        self.assertEqual(outputs('list-queue-out0')[:6],(7,0,0,6,1,4))
        self.assertEqual(outputs('list-stack-out0')[:6],(0,4,4,7,2,1))
        self.assertEqual(outputs('list-queue-out1'),tuple(2*i for i in range(1,22)))
        self.assertEqual(outputs('list-stack-out1'),tuple(2*i for i in range(1,22)))
        self.assertEqual(outputs('list-queue-bounded-out0')[:4],(0,4,4,7))
        self.assertEqual(outputs('list-stack-bounded-out0')[:4],(7,6,6,4))
        for n in('queue','stack'):self.assertEqual(outputs('list-'+n+'-bounded-out1'),tuple(6*i for i in range(1,22)))
    def test_multi_emission_observer_scope_and_exact_range(self):
        self.assertEqual(outputs('iter-chunk1')[0],sum(r.encode([x])for x in(7,0,0)))
        self.assertEqual(outputs('iter-chunk2')[0],r.encode([7,0])+r.encode([0]))
        self.assertEqual(outputs('listfunnel-offset0')[0],sum(r.encode(x)for x in([0,7],[1,0],[2,0])))
        self.assertEqual(outputs('listfunnel-offset2')[0],sum(r.encode(x)for x in([2,7],[3,0],[4,0])))
        for m in r.MODELS:
            self.assertTrue(all(0<=r.value(w)<2**24 and r.value(w)==int(r.value(w))for w in r.event_outputs(m)))
    def test_sources_and_partitions_are_fixed(self):
        all_cases=[]
        for i in range(1,7):
            cat=json.loads((HERE/f'part{i}.json').read_bytes());builder.list_extended_catalog(cat);all_cases+=cat['cases']
            changed=copy.deepcopy(cat);changed['cases'][0]['variant']='other'
            with self.assertRaises(ValueError):builder.list_extended_catalog(changed)
        self.assertEqual(len(all_cases),32);self.assertEqual(len({s['exact_name']for s in all_cases}),17)
        self.assertEqual({s['id'] for s in all_cases},{s['id']for s in json.loads((HERE/'catalog.json').read_bytes())['cases']})
        self.assertEqual(builder.sha(HERE/'reference.py'),builder.LIST_EXTENDED_REFERENCE_SHA)
        for s in all_cases:self.assertEqual(builder.sha(HERE/s['patch']),s['patch_sha256']);self.assertEqual(s['maximum_absolute_error'],0)
    def _plan(self,i):
        cat=json.loads((HERE/f'part{i}.json').read_bytes());rows=[]
        for src in cat['cases']:
            row=copy.deepcopy(src);m=src['model'];inputs=r.input_words();bs=r.reference_blocks(m,inputs)
            row.update(source_sha256=src['patch_sha256'],absolute_tolerance=0.,input_words=list(inputs),expected=list(bs[0]),expected_blocks=[list(b)for b in bs],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in bs for w in b))).hexdigest(),expected_parameter_count=2,parameters=r.parameters(),parameter_events=[dict(before_call=e['before_call'],id=e['id'],parameter_slot=0 if e['id']=='drive'else 1,value_word=r.word(e['value']),normalized_word=r.word((e['value']+8)/16 if e['id']=='drive'else e['value']))for e in r.parameter_events(m)])
            rows.append(row)
        pool,indices=builder.block_pool(rows)
        for row,refs in zip(rows,indices):row['expected_block_indices']=refs;del row['expected_blocks']
        return dict(family='rnbo-list-extended',catalog_sha256=builder.LIST_EXTENDED_PARTITIONS[i],reference_source_sha256=builder.LIST_EXTENDED_REFERENCE_SHA,surface='patcher',partition=cat['partition'],prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,expected_block_storage='shared-512-word-pool',expected_reference_unique_blocks=len(pool),expected_block_pool=[list(b)for b in pool],cases=rows)
    def test_collector_rejects_changed_state_stream_source_and_actions(self):
        for i in(1,2):
            p=self._plan(i);collector.list_extended_plan(p)
            for change in(lambda q:q['cases'][0].update(output_kind='other'),lambda q:q['cases'][0].update(absolute_tolerance=1),lambda q:q['cases'][0].update(source_sha256='0'*64),lambda q:q['cases'][0]['parameter_events'][0].update(value_word=0),lambda q:q['expected_block_pool'][0].__setitem__(0,r.word(1.)),lambda q:q['cases'].pop(),lambda q:q.update(prepare_zero_warm_blocks=1)):
                changed=copy.deepcopy(p);change(changed)
                with self.assertRaises(ValueError):collector.list_extended_plan(changed)
    def test_ids_not_abi_indices_and_raw_pilot(self):
        p=self._plan(1)
        for row in p['cases']:
            row['parameters'].reverse()
            for e in row['parameter_events']:e['parameter_slot']=1-e['parameter_slot']
        collector.list_extended_plan(p)
        bs=r.reference_blocks(2900,r.input_words());digest=hashlib.sha256(b''.join(struct.pack('<256I',*b[1::2])for b in bs)).hexdigest()
        self.assertTrue(collector.right_pilot_observation(dict(right_output_sha256=digest),list(bs))['right_pilot_bit_exact'])
        with self.assertRaises(ValueError):collector.right_pilot_observation(dict(right_output_sha256='0'*64),list(bs))
    def test_same_callback_updates_and_quiet_holds(self):
        for m in r.MODELS:
            bs=r.reference_blocks(m,r.input_words());es=r.event_outputs(m)
            self.assertEqual(bs[10][0],es[12]);self.assertEqual(bs[12],bs[13]);self.assertEqual(bs[13],bs[14])
            self.assertTrue(all(b[1::2]==r.input_words()[1::2]for b in bs))
            self.assertEqual(len(r.parameter_events(m)),22)
    def test_completed_publication_binds_exact_forms_and_pilot(self):
        for i in(1,2):
            source=f'evidence/xiao-smoke-rnbo-list-extended-part{i}.json';data=json.loads((ROOT/source).read_bytes())
            for j,c in enumerate(data['cases']):
                rec=dict(surface='patcher',id='patcher:'+c['exact_name'],spelling=c['exact_name'])
                self.assertEqual(publisher.checked_short_smoke(rec,dict(source=source,selector=f'/cases/{j}'),data)['status'],c['status'])
            rec=dict(surface='patcher',id='patcher:'+data['cases'][0]['exact_name'],spelling=data['cases'][0]['exact_name'])
            for key,value in(('output_kind','other'),('source_sha256','0'*64),('absolute_tolerance',1),('expected_stream_sha256','0'*64),('right_output_sha256','0'*64)):
                changed=copy.deepcopy(data);changed['cases'][0][key]=value
                with self.assertRaises(ValueError):publisher.checked_short_smoke(rec,dict(source=source,selector='/cases/0'),changed)
    def test_faults_cannot_be_promoted_to_complete_numeric_or_memory_pass(self):
        for i in range(3,7):
            data=json.loads((ROOT/f'evidence/xiao-list-extended-growth-fault-part{i}.json').read_bytes());rec=report.fault_record(data)
            publisher.checked_list_target_fault(rec,{},data)
            for k,v in(('event_status',0),('late_platform_allocations',0),('fault_event',1),('before_call',0),('source_sha256','0'*64),('numeric_pass_claimed',True),('output_words_checked',3584),('finalization_checked',True)):
                changed=dict(data);changed[k]=v
                with self.assertRaises(ValueError):publisher.checked_list_target_fault(rec,{},changed)
    def test_synthetic_fault_serial_requires_bound_source_and_full_event_prefix(self):
        # The collector is also exercised without private build artifacts, for CI.
        from prepare import canonical
        plan=self._plan(3);row=plan['cases'][0];row['module_sha256']='1'*64
        digest=lambda raw:hashlib.sha256(raw).hexdigest();elf='2'*64;ph=digest(canonical(plan));actions=row['parameter_events']
        lines=[f'RNBO_SMOKE START firmware_elf_sha256={elf} plan_sha256={ph} cases=1']
        for i,a in enumerate(actions[:8]):lines.append(f"RNBO_SMOKE EVENT case_id={row['id']} ordinal={i} before_call={a['before_call']} parameter_slot={a['parameter_slot']} value_word={a['value_word']:08x} actual_word={a['value_word']:08x} normalized_word={a['normalized_word']:08x} event_us=1")
        a=actions[8];lines.append(f"RNBO_SMOKE EVENT_RESULT case_id={row['id']} ordinal=8 before_call=7 parameter_slot={a['parameter_slot']} value_word={a['value_word']:08x} status=-4 readback_status=0 elapsed_us=2 statistics_status=0 platform_errors=0 late_platform_allocations=2 invalid_samples=0")
        lines.append('I (1) test: FAIL condition=result==RNBO_S3_OK && elapsed>=0 && readback==RNBO_S3_OK')
        with tempfile.TemporaryDirectory()as td:
            bd=Path(td)/'build';rd=Path(td)/'run';bd.mkdir();rd.mkdir()
            bp=bd/'build-report.json';lp=rd/'test-serial.log';rp=rd/'hardware-smoke.json'
            bp.write_bytes(json.dumps(dict(plan=plan,plan_sha256=ph,artifacts={'test.elf':{'sha256':elf}})).encode())
            def write(serial):
                lp.write_text('\n'.join(serial)+'\n');rp.write_bytes(json.dumps(dict(format='rnbo-hardware-smoke-run-v1',result='failed',flash_attempted=True,left_installed=True,complete_fault_line=True,done_line=None,case_lines=[],test_build_report_sha256=digest(bp.read_bytes()),serial_log_sha256=digest(lp.read_bytes()),test_elf_sha256=elf)).encode())
            write(lines);self.assertEqual(fault_collector.collect(bd,rd)['late_platform_allocations'],2)
            for serial in (lines[:3]+lines[4:],lines[:-2]+[lines[-2].replace('status=-4','status=0')]+lines[-1:],lines+['RNBO_SMOKE DONE cases=1'],lines[:-2]+[lines[-2].replace('late_platform_allocations=2','late_platform_allocations=0')]+lines[-1:]):
                write(serial)
                with self.assertRaises(ValueError):fault_collector.collect(bd,rd)
    def test_report_retains_all_originals_and_bounded_controls(self):
        data=json.loads(report.products()['evidence/rnbo-list-extended-status.json'])
        self.assertEqual(len(data['cases']),32);self.assertEqual(len(data['objects']),17)
        self.assertEqual(data['summary']['passed'],27);self.assertEqual(data['summary']['outside_screen'],1);self.assertEqual(data['summary']['event_faults'],4)
        self.assertEqual(sum(o['status']=='partial'for o in data['objects']),3)
        self.assertTrue(all(c['median_us']is None and c['samples_checked']==0 for c in data['cases']if c['status']=='event_fault'))
        archive=HERE/'initial-28-v1';sp=importlib.util.spec_from_file_location('list_original',archive/'reference.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old)
        for m in old.MODELS:self.assertEqual(old.reference_blocks(m,old.input_words()),r.reference_blocks(m,r.input_words()))
if __name__=='__main__':unittest.main()
