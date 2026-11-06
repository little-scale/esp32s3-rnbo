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
HERE=ROOT/'tests/fixtures/smoke/rnbo-envelopes-clocks'
spec=importlib.util.spec_from_file_location('envelopes_clocks_reference',HERE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def model(identity):return next(m for m,s in r.MODEL_SPECS.items()if s['id']==identity)
class EnvelopesClocksTests(unittest.TestCase):
    def blocks(self,identity):return r.reference_blocks(model(identity),r.input_words())
    def values(self,identity,call):return tuple(map(r.value,self.blocks(identity)[call][::2]))
    def test_event_boolean_edges_and_repeated_actions(self):
        self.assertEqual([self.values('onoff-events',i)[0]for i in range(5)],[1.,0.,1.,0.,1.])
        self.assertEqual([self.values('gatetotrig-pos',i)[0]for i in range(5)],[1.,0.,0.,1.,0.])
        self.assertEqual([self.values('gatetotrig-neg',i)[0]for i in range(5)],[0.,1.,0.,0.,1.])
        self.assertEqual(self.values('onoff-events',10),(1.,)*256)
    def test_onebang_initial_state_and_positive_rearming_outlets(self):
        self.assertEqual(self.values('onebang-init0-out0',19),(0.,)*256)
        self.assertEqual(self.values('onebang-init0-out1',19),(21.,)*256)
        self.assertEqual(self.values('onebang-init1-out0',19),(1.,)*256)
        self.assertEqual(self.values('onebang-init1-out1',19),(20.,)*256)
        for call in range(20):
            left=self.values('onebang-rearm-out0',call)[0];right=self.values('onebang-rearm-out1',call)[0]
            count=sum(c<=call for c in r._CALLS);self.assertEqual(left+right,count)
            self.assertEqual(left,sum(x>0 for c,x in zip(r._CALLS,r._DRIVES)if c<=call))
    def test_signal_edges_keep_declared_one_block_observer_latency(self):
        self.assertEqual(self.values('edge-out0',0),(0.,)*256)
        self.assertEqual(self.values('edge-out0',1)[:16],(0.,)*16)
        self.assertEqual(self.values('edge-out0',1)[16:48],(1.,)*32)
        self.assertEqual(self.values('edge-out1',1)[:48],(0.,)*48)
        self.assertEqual(self.values('edge-out1',1)[48:96],(1.,)*48)
    def test_closed_form_envelope_minimum_peak_transition_and_release(self):
        vals=self.values('env2-minimum',0)
        self.assertEqual(vals[:16],(0.,)*16);self.assertEqual(vals[16:20],(.5,.5,0.,0.))
        self.assertEqual(vals[64:68],(-1.,-1.,0.,0.))
        self.assertEqual(r.envelope_at(2,('attack',0,1.),2.,4.,False),1.)
        self.assertEqual(r.envelope_at(3,('attack',0,1.),2.,4.,False),.5)
        self.assertEqual(r.envelope_at(100,('attack',0,-.5),2.,4.,True),-.5)
        self.assertEqual(r.envelope_at(4,('release',4,.75),2.,4.,True),.5625)
    def test_exponential_basis_endpoints_symmetry_and_curvature(self):
        for c in(-.9,-.5,.25,.5,.9):
            self.assertEqual(r.curve_basis(0,c),0.);self.assertEqual(r.curve_basis(1,c),1.)
            self.assertAlmostEqual(r.curve_basis(.25,c)+r.curve_basis(.75,-c),1.)
            self.assertLess(r.curve_basis(.25,c),r.curve_basis(.75,c))
        self.assertLess(r.curve_basis(.5,.5),.5);self.assertGreater(r.curve_basis(.5,-.5),.5)
        self.assertEqual(self.values('curve-immediate',0),(1.,)*256)
        self.assertEqual(self.values('curve-gentle',0)[0],0.)
    def test_delay_pipe_and_line_use_original_boundary_deadlines(self):
        vals=self.values('delay-2-all1',0);self.assertEqual(vals[:88],(0.,)*88);self.assertEqual(vals[88:],(1.,)*168)
        self.assertEqual(self.values('pipe-10',0),(0.,)*256)
        vals=self.values('pipe-10',1);self.assertEqual(vals[:185],(0.,)*185);self.assertEqual(vals[185:],(1.,)*71)
        self.assertEqual(self.values('delay-10-all0',2),(0.,)*256)
        vals=self.values('line-ramp',0);self.assertEqual(vals[:88],(0.,)*88);self.assertAlmostEqual(vals[88],1/6,places=7)
    def test_catalog_exact_sources_original_limits_and_partition_ledger(self):
        cases=[]
        for i in range(1,6):
            cat=json.loads((HERE/f'part{i}.json').read_bytes());builder.envelopes_clocks_catalog(cat);cases+=cat['cases']
            changed=copy.deepcopy(cat);changed['cases'][0]['variant']='other'
            with self.assertRaises(ValueError):builder.envelopes_clocks_catalog(changed)
        self.assertEqual(len(cases),31);self.assertEqual(len({s['exact_name']for s in cases}),9)
        self.assertEqual({c['id']for c in cases},{c['id']for c in json.loads((HERE/'catalog.json').read_bytes())['cases']})
        self.assertEqual(builder.sha(HERE/'reference.py'),builder.ENVELOPES_CLOCKS_REFERENCE_SHA)
        for s in cases:
            self.assertEqual(builder.sha(HERE/s['patch']),s['patch_sha256']);self.assertEqual(s['maximum_absolute_error'],r.ABSOLUTE_TOLERANCES[s['model']])
    def test_immediate_fixture_correction_keeps_all_streams_and_limits(self):
        archive=HERE/'list-zero-time-draft-v1';sp=importlib.util.spec_from_file_location('initial_envelopes_ref',archive/'reference.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old)
        for m in r.MODELS:self.assertEqual(old.reference_blocks(m,old.input_words()),r.reference_blocks(m,r.input_words()));self.assertEqual(old.ABSOLUTE_TOLERANCES[m],r.ABSOLUTE_TOLERANCES[m])
        original=json.loads((archive/'catalog.json').read_bytes());changed=[s['id']for s in original['cases']if builder.sha(HERE/s['patch'])!=s['patch_sha256']];self.assertEqual(changed,['curve-immediate'])
        for entry in json.loads((archive/'source-locations.json').read_bytes()).values():self.assertEqual(builder.sha(archive/entry['path']),entry['sha256'])
    def test_bad_models_input_and_missing_arm_rejected(self):
        for m,ins,calls in((True,r.input_words(),20),(3399,r.input_words(),20),(3400,(0,0),20),(3400,r.input_words(),0)):
            with self.assertRaises(ValueError):r.reference_blocks(m,ins,calls)
        with patch.object(r,'parameter_events',return_value=r.parameter_events(3400)[1:]):
            with self.assertRaises(ValueError):r.reference_blocks(3400,r.input_words())
    def _plan(self,i):
        cat=json.loads((HERE/f'part{i}.json').read_bytes());rows=[]
        for src in cat['cases']:
            row=copy.deepcopy(src);m=src['model'];inputs=r.input_words();bs=r.reference_blocks(m,inputs)
            row.update(arena_bytes=1048576,source_sha256=src['patch_sha256'],absolute_tolerance=builder.float32(src['maximum_absolute_error']),input_words=list(inputs),expected=list(bs[0]),expected_blocks=[list(b)for b in bs],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in bs for w in b))).hexdigest(),expected_parameter_count=2,parameters=r.parameters(),parameter_events=[dict(before_call=e['before_call'],id=e['id'],parameter_slot=0 if e['id']=='drive'else 1,value_word=r.word(e['value']),normalized_word=r.word((e['value']+8)/16 if e['id']=='drive'else e['value']))for e in r.parameter_events(m)])
            rows.append(row)
        pool,indices=builder.block_pool(rows)
        for row,refs in zip(rows,indices):row['expected_block_indices']=refs;del row['expected_blocks']
        return dict(family='rnbo-envelopes-clocks',catalog_sha256=builder.ENVELOPES_CLOCKS_PARTITIONS[i],reference_source_sha256=builder.ENVELOPES_CLOCKS_REFERENCE_SHA,surface='patcher',partition=cat['partition'],prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,expected_block_storage='shared-512-word-pool',expected_reference_unique_blocks=len(pool),expected_block_pool=[list(b)for b in pool],cases=rows)
    def test_collector_rebinds_exact_mode_outputs_events_and_tolerances(self):
        for i in range(1,6):
            p=self._plan(i);collector.envelopes_clocks_plan(p)
            for change in(lambda q:q['cases'][0].update(arena_bytes=4096),lambda q:q['cases'][0].update(variant='other'),lambda q:q['cases'][0].update(absolute_tolerance=.001),lambda q:q['cases'][0].update(source_sha256='0'*64),lambda q:q['cases'][0]['parameter_events'][0].update(value_word=0),lambda q:q['expected_block_pool'][0].__setitem__(0,r.word(7)),lambda q:q['cases'].pop(),lambda q:q.update(prepare_zero_warm_blocks=1)):
                changed=copy.deepcopy(p);change(changed)
                with self.assertRaises(ValueError):collector.envelopes_clocks_plan(changed)
    def test_parameter_description_order_and_raw_pilot(self):
        p=self._plan(1)
        for row in p['cases']:
            row['parameters'].reverse()
            for e in row['parameter_events']:e['parameter_slot']=1-e['parameter_slot']
        collector.envelopes_clocks_plan(p)
        bs=list(r.reference_blocks(3400,r.input_words()));digest=hashlib.sha256(b''.join(struct.pack('<256I',*b[1::2])for b in bs)).hexdigest()
        self.assertTrue(collector.right_pilot_observation(dict(right_output_sha256=digest),bs)['right_pilot_bit_exact'])
        with self.assertRaises(ValueError):collector.right_pilot_observation(dict(right_output_sha256='0'*64),bs)
    def test_published_sources_outputs_and_limits_bind_independently(self):
        for i in range(1,4):
            source=f'evidence/xiao-smoke-rnbo-envelopes-clocks-part{i}.json';data=json.loads((ROOT/source).read_bytes())
            for j,c in enumerate(data['cases']):
                rec=dict(surface='patcher',id='patcher:'+c['exact_name'],spelling=c['exact_name'])
                self.assertEqual(publisher.checked_short_smoke(rec,dict(source=source,selector=f'/cases/{j}'),data)['status'],c['status'])
            rec=dict(surface='patcher',id='patcher:'+data['cases'][0]['exact_name'],spelling=data['cases'][0]['exact_name'])
            for key,value in(('arena_capacity',4096),('variant','other'),('hot_inlet',1),('signal_input','other'),('source_sha256','0'*64),('absolute_tolerance',.002),('expected_stream_sha256','0'*64),('right_output_sha256','0'*64)):
                changed=copy.deepcopy(data);changed['cases'][0][key]=value
                with self.assertRaises(ValueError):publisher.checked_short_smoke(rec,dict(source=source,selector='/cases/0'),changed)
    def _fault_files(self,base,index,corrupt=False):
        import collect_envelopes_clocks_fault as fault
        bd=base/'build';rd=base/'run';bd.mkdir();rd.mkdir();plan=self._plan(index);row=plan['cases'][0];row['module_sha256']='c'*64;digest=hashlib.sha256(builder.canonical(plan)).hexdigest()
        build=dict(plan=plan,plan_sha256=digest,artifacts={'test.elf':dict(sha256='a'*64)});bp=bd/'build-report.json';bp.write_bytes(builder.canonical(build))
        curve=index==4;prefix=13 if curve else 16;lines=[f"RNBO_SMOKE START plan_sha256={digest} cases=1 firmware_elf_sha256={'a'*64}"]
        for ordinal,a in enumerate(row['parameter_events'][:prefix]):
            actual=0 if corrupt and ordinal==1 else a['value_word']
            lines.append(f"RNBO_SMOKE EVENT case_id={row['id']} ordinal={ordinal} before_call={a['before_call']} parameter_slot={a['parameter_slot']} resolved_index={a['parameter_slot']} value_word={a['value_word']:08x} actual_word={actual:08x} normalized_word={a['normalized_word']:08x} event_us=1")
        if curve:
            a=row['parameter_events'][13];lines.append(f"RNBO_SMOKE EVENT_RESULT case_id={row['id']} ordinal=13 before_call=10 parameter_slot={a['parameter_slot']} value_word=3f800000 status=-4 readback_status=0 elapsed_us=2 statistics_status=0 platform_errors=0 late_platform_allocations=1 invalid_samples=0")
            lines.append('I (1) test: FAIL condition=result==RNBO_S3_OK && elapsed>=0 && readback==RNBO_S3_OK')
        else:
            lines.append(f"RNBO_SMOKE PROCESS_RESULT case_id={row['id']} before_call=13 status=-4 elapsed_us=100 statistics_status=0 platform_errors=1 late_platform_allocations=0 invalid_samples=0")
            lines.append('I (1) test: FAIL condition=result==RNBO_S3_OK && elapsed>=0')
        lp=rd/'test-serial.log';lp.write_text('\n'.join(lines)+'\n');run=dict(format='rnbo-hardware-smoke-run-v1',result='failed',flash_attempted=True,left_installed=True,complete_fault_line=True,done_line=None,case_lines=[],test_build_report_sha256=builder.sha(bp),serial_log_sha256=builder.sha(lp),test_elf_sha256='a'*64);(rd/'hardware-smoke.json').write_bytes(builder.canonical(run))
        return bd,rd
    def test_fault_collector_requires_exact_stage_and_successful_action_prefix(self):
        import tempfile
        import collect_envelopes_clocks_fault as fault
        for index in(4,5):
            with tempfile.TemporaryDirectory()as tmp:
                d=fault.collect(*self._fault_files(Path(tmp),index));self.assertEqual(d['partition'],index);self.assertFalse(d['numeric_pass_claimed']);self.assertEqual(d['output_words_checked'],0)
            with tempfile.TemporaryDirectory()as tmp:
                with self.assertRaises(ValueError):fault.collect(*self._fault_files(Path(tmp),index,corrupt=True))
    def test_fault_publication_cannot_promote_faults_to_output_or_cpu_pass(self):
        for index in(4,5):
            d=json.loads((ROOT/f'evidence/xiao-smoke-rnbo-envelopes-clocks-part{index}.json').read_bytes());rec=dict(surface='patcher',id='patcher:'+d['exact_name'],spelling=d['exact_name'],working_state='partial',board_evidence=True,optimisation_state='unassessed',optimisations=[],cpu_measurement_ids=[]);item=dict(source=f'evidence/xiao-smoke-rnbo-envelopes-clocks-part{index}.json')
            publisher.checked_envelopes_clocks_fault(rec,item,d)
            for key,value in(('numeric_pass_claimed',True),('output_words_checked',5120),('finalization_checked',True),('before_call',0),('successful_events',22),('source_sha256','0'*64),('platform_errors',2)):
                changed=copy.deepcopy(d);changed[key]=value
                with self.assertRaises(ValueError):publisher.checked_envelopes_clocks_fault(rec,item,changed)
            changed=copy.deepcopy(rec);changed['working_state']='board'
            with self.assertRaises(ValueError):publisher.checked_envelopes_clocks_fault(changed,item,d)
if __name__=='__main__':unittest.main()
