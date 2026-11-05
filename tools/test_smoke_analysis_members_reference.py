# SPDX-License-Identifier: MIT
"""Window sums, oscillator epochs and immutable member/seed screen scope."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import unittest
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import build_object_status as status
BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-codebox-analysis-members'
spec=importlib.util.spec_from_file_location('analysis_reference',BASE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class AnalysisMemberReferenceTests(unittest.TestCase):
    def test_published_failures_remain_primary_and_noise_flags_do_not_compare_sequences(self):
        root=BASE.parents[3]
        target=json.loads((root/'evidence/xiao-smoke-rnbo-codebox-analysis-members.json').read_text())
        native=json.loads((root/'evidence/rnbo-codebox-analysis-members-native.json').read_text())
        self.assertEqual(target['summary'],dict(executed=19,passed=16,output_mismatches=3,compile_failures=3,cpu_review=12))
        self.assertEqual(sum(v['samples_checked']for v in target['cases']),194560)
        self.assertEqual(sum(v['numeric_mismatches']for v in target['cases']),20270)
        self.assertEqual(sum(v['within_tolerance_differences']for v in target['cases']),1524)
        self.assertFalse(native['noise_sequence_compared']);self.assertFalse(native['primary_per_sample_reference_changed'])
        byid={v['id']:v for v in target['cases']}
        self.assertEqual({k for k,v in byid.items()if v['status']=='output_mismatch'},{o+'-window-change-named-list'for o in r.AVERAGES})
        self.assertEqual(len({status.analysis_member_identity(v)for v in target['cases']}),11)
        for row in native['cases']:
            t=byid[row['id']]
            for k in('input_words_sha256','expected_stream_sha256'):self.assertEqual(row[k],t[k])
            self.assertEqual(row['bit_differences'],t['bit_mismatches']);self.assertEqual(row['max_error'],t['max_absolute_error']);self.assertTrue(t['finalized'])
        for row in native['window_selector_diagnostic']:
            t=byid[row['id']];self.assertEqual(row['original_per_sample_numeric_mismatches'],t['numeric_mismatches'])
            self.assertEqual(row['original_per_sample_max_error'],t['max_absolute_error'])
            self.assertEqual(row['block_held_selector_outside_2e6'],0)
            self.assertTrue(row['selector_in_producer_before_sample_loop']);self.assertEqual(t['first_mismatch_word'],146)
        self.assertEqual(native['window_diagnostic_script_sha256'],hashlib.sha256((BASE/'window_diagnostic.py').read_bytes()).hexdigest())
        bad=dict(target['cases'][0],exact_name='average')
        with self.assertRaises(ValueError):status.analysis_member_identity(bad)

    def test_available_history_not_zero_padded_and_channels_are_independent(self):
        for model in(1800,1804,1808):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
            for channel,width in((0,8),(1,16)):
                for age in(0,1,7,8,15,16,255,256,257,5119):
                    values=[r.value(inputs[2*(k%256)+channel])for k in range(max(0,age-width+1),age+1)]
                    if model==1804:values=[abs(v)for v in values]
                    if model==1808:values=[v*v for v in values]
                    mean=math.fsum(values)/len(values);expected=math.sqrt(mean)if model==1808 else mean
                    self.assertEqual(blocks[age//256][2*(age%256)+channel],r.word(expected))
            self.assertNotEqual(blocks[0][0],blocks[0][1])
    def test_explicit_reset_schedules_include_consecutive_and_host_boundary_actions(self):
        self.assertTrue(all(r.reset_at(n,0)for n in(37,38,255,256)))
        self.assertTrue(all(r.reset_at(n,1)for n in(91,92,511,512)))
        for model in(1801,1805,1809):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
            for ch,ages in((0,(37,38,255,256)),(1,(91,92,511,512))):
                for n in ages:
                    x=r.value(inputs[2*(n%256)+ch]);expected=abs(x)if model in(1805,1809)else x
                    self.assertEqual(blocks[n//256][2*(n%256)+ch],r.word(expected))
    def test_signal_reset_pulses_are_isolated_not_a_guessed_held_gate_contract(self):
        for ch in(0,1):
            hits=[n for n in range(5120)if r.pulse_at(n,ch)];self.assertGreater(len(hits),10)
            self.assertTrue(all(b-a>1 for a,b in zip(hits,hits[1:])))
        for model in(1802,1806,1810):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
            for ch,age in((0,255),(1,511)):
                expected=r.value(inputs[2*(age%256)+ch]);expected=abs(expected)if model!=1802 else expected
                self.assertEqual(blocks[age//256][2*(age%256)+ch],r.word(expected))
    def test_named_list_followups_keep_the_original_per_sample_window_reference(self):
        for original,followup in((1803,1819),(1807,1820),(1811,1821)):
            inputs=r.case_input_words(original);self.assertEqual(inputs,r.case_input_words(followup))
            self.assertEqual(r.reference_blocks(original,inputs),r.reference_blocks(followup,inputs))
            blocks=r.reference_blocks(original,inputs)
            for ch,age in((0,73),(1,91),(0,146),(1,182)):
                x=r.value(inputs[2*(age%256)+ch]);expected=x if original==1803 else abs(x)
                self.assertEqual(blocks[age//256][2*(age%256)+ch],r.word(expected))
    def test_cycle_current_phase_and_non_block_period_detect_lost_state(self):
        inputs=r.case_input_words(1814);blocks=r.reference_blocks(1814,inputs)
        for n in(0,1,255,256,257,511,512,1023,5119):self.assertEqual(tuple(map(r.value,blocks[n//256][2*(n%256):2*(n%256)+2])),((n%512)/512,(n%1024)/1024))
        self.assertNotEqual(blocks[0],blocks[1])
        blocks=r.reference_blocks(1812,r.case_input_words(1812));self.assertAlmostEqual(r.value(blocks[0][0]),1);self.assertAlmostEqual(r.value(blocks[1][0]),-1)
        blocks=r.reference_blocks(1813,r.case_input_words(1813))
        for age in(255,256):self.assertEqual(r.value(blocks[age//256][2*(age%256)]),1)
    def test_catalog_identity_and_screens_cannot_be_promoted_to_rng_sequence_proof(self):
        c=json.loads((BASE/'catalog.json').read_text());builder.analysis_member_catalog(c);self.assertEqual(len(c['cases']),22)
        for row in c['cases']:
            raw=(BASE/row['patch']).read_bytes();code=(BASE/row['codebox']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),row['patch_sha256']);self.assertEqual(hashlib.sha256(code).hexdigest(),row['codebox_sha256'])
            box=next(b['box']for b in json.loads(raw)['patcher']['boxes']if b['box']['text']=='codebox~');self.assertEqual(box['rnbo_extra_attributes']['code'].encode(),code)
            self.assertEqual(status.analysis_member_identity(row),row['registry_lookup'])
        for row in c['cases'][16:19]:self.assertIn('not RNG sequence',row['scope']);self.assertEqual(row['maximum_absolute_error'],0)
        for key,v in(('scope','all modes qualified'),('member','clear'),('maximum_absolute_error',1)):
            bad=copy.deepcopy(c);bad['cases'][0][key]=v
            with self.assertRaises(builder.ExportError):builder.analysis_member_catalog(bad)
    def test_collector_recomputes_streams_and_rejects_epoch_or_arena_changes(self):
        c=json.loads((BASE/'catalog.json').read_text());cases=[]
        for row in c['cases']:
            inputs=list(r.case_input_words(row['model']));blocks=[list(b)for b in r.reference_blocks(row['model'],inputs)];cases.append(dict(row,source_sha256=row['patch_sha256'],codebox_source_sha256=row['codebox_sha256'],input_words=inputs,expected=blocks[0],expected_blocks=blocks,absolute_tolerance=struct.unpack('<f',struct.pack('<f',row['maximum_absolute_error']))[0],arena_bytes=2097152,expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest()))
        plan=dict(cases=cases,surface='codebox',warmup_blocks=4,timed_blocks=16,prepare_zero_warm_blocks=0,catalog_sha256=builder.ANALYSIS_MEMBER_CATALOG_SHA,reference_source_sha256=builder.ANALYSIS_MEMBER_REFERENCE_SHA,expected_stream_policy='Fresh prepared analysis/resource member state; twenty continuous256-frame callbacks with only authored reset/seed/window-change actions')
        collector.analysis_member_plan(plan)
        for key,v in(('scope','all noise sequences verified'),('arena_bytes',4096),('absolute_tolerance',1)):
            bad=dict(cases[0],**{key:v})
            with self.assertRaises(ValueError):collector.analysis_member_plan(dict(plan,cases=[bad]+cases[1:]))
        bad=copy.deepcopy(cases[0]);bad['expected_blocks'][19][511]^=1;bad['expected_stream_sha256']=hashlib.sha256(struct.pack('<10240I',*(w for b in bad['expected_blocks']for w in b))).hexdigest()
        with self.assertRaises(ValueError):collector.analysis_member_plan(dict(plan,cases=[bad]+cases[1:]))
        with self.assertRaises(ValueError):collector.analysis_member_plan(dict(plan,prepare_zero_warm_blocks=True))
if __name__=='__main__':unittest.main()
