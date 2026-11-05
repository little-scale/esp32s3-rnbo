# SPDX-License-Identifier: MIT
"""Independent arithmetic/state models and immutable execution-screen scope."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/gen-execution-forms'
spec=importlib.util.spec_from_file_location('gen_execution_reference',BASE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class GenExecutionReferenceTests(unittest.TestCase):
    def test_public_observations_keep_screen_and_rejection_scope(self):
        root=BASE.parents[3]
        target=json.loads((root/'evidence/xiao-smoke-gen-execution-forms.json').read_text())
        native=json.loads((root/'evidence/gen-execution-forms-native.json').read_text())
        self.assertEqual(target['summary'],dict(executed=5,passed=5,output_mismatches=0,compile_failures=14,admission_failures=5,cpu_review=0))
        self.assertFalse(target['full_qualification_claimed']);self.assertFalse(native['noise_sequence_compared'])
        self.assertEqual(sum(v['samples_checked']for v in target['cases']),51200)
        byid={v['id']:v for v in target['cases']}
        self.assertEqual(set(byid),{'noise-range-variation','local-add-assign','local-multiply-assign','local-subtract-assign','local-divide-assign'})
        for v in native['cases']:
            t=byid[v['id']]
            for key in ('input_words_sha256','expected_stream_sha256'):self.assertEqual(v[key],t[key])
            self.assertEqual(v['bit_differences'],t['bit_mismatches']);self.assertEqual(v['max_error'],t['max_absolute_error'])
            self.assertTrue(t['finalized']);self.assertEqual(t['arena_high_water'],0);self.assertEqual(t['cpu_review_reasons'],[])
        self.assertEqual(len(native['rejected_forms']),19)
        self.assertTrue(all(not v['hardware_executed']for v in native['rejected_forms']))
        c=json.loads((BASE/'catalog.json').read_text());ids={v['id']for v in c['cases']}
        observed=list(target['cases'])+target['compile_failures']+target['admission_failures']
        self.assertEqual(len(observed),24);self.assertEqual({v['id']for v in observed},ids)

    def test_primitive_arithmetic_reference_including_division_rounding(self):
        for model,fn in ((1712,lambda a,b:a+b),(1713,lambda a,b:a*b),(1714,lambda a,b:a-b),(1715,lambda a,b:a/b)):
            inputs=r.case_input_words(model);block=r.reference_blocks(model,inputs)[0]
            for i in range(256):
                a,b=map(r.value,inputs[2*i:2*i+2]);self.assertEqual(block[2*i],r.word(fn(a,b)));self.assertEqual(block[2*i+1],inputs[2*i+1])
        # 1/3 requires rounding to a binary32 word, not decimal/rational identity.
        words=r.case_input_words(1715);frame=9*16+2
        self.assertEqual(r.reference_blocks(1715,words)[0][2*frame],0x3eaaaaab)
    def test_integer_domain_prevents_undefined_shifts_and_zero_divisors(self):
        for model in range(1716,1722):
            v=r.case_input_words(model);block=r.reference_blocks(model,v)[0]
            for i in range(256):
                a,b=map(r.value,v[2*i:2*i+2]);self.assertTrue(a.is_integer()and b.is_integer());self.assertGreaterEqual(a,0)
                if model in(1720,1721):self.assertIn(b,range(4))
                else:self.assertGreater(b,0)
                self.assertGreaterEqual(r.value(block[2*i]),0)
        v=r.case_input_words(1716);block=r.reference_blocks(1716,v)[0]
        for i in range(256):self.assertLess(r.value(block[2*i]),r.value(v[2*i+1]))
    def test_history_prefix_and_parity_cross_every_host_boundary(self):
        for model,initial in ((1722,0),(1723,1)):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs);state=initial
            for age in range(5120):
                x=r.value(inputs[2*(age%256)])
                self.assertEqual(r.value(blocks[age//256][2*(age%256)]),state)
                state=state+x/16 if model==1722 else state*x
            self.assertNotEqual(blocks[0],blocks[1])
            self.assertNotEqual(blocks[0],blocks[19])
    def test_noise_and_fft_screen_limits_are_explicit_and_not_numeric_oracles(self):
        catalog=json.loads((BASE/'catalog.json').read_text())
        for row in catalog['cases'][:12]:
            self.assertEqual(row['reference_policy'],'declared-basic-execution-screen')
            self.assertIn('No exact default value',row['scope'])if row['model']!=1700 else self.assertIn('no exact sequence',row['scope'])
            flags=r.reference_blocks(row['model'],r.case_input_words(row['model']))
            self.assertTrue(all(r.value(w)==1 for b in flags for w in b[::2]))
        self.assertIn('at least one adjacent change per32samples',catalog['cases'][0]['scope'])
    def test_catalog_embedded_sources_and_screen_scope_are_frozen(self):
        c=json.loads((BASE/'catalog.json').read_text());builder.gen_execution_catalog(c);self.assertEqual(len(c['cases']),24)
        for row in c['cases']:
            raw=(BASE/row['patch']).read_bytes();code=(BASE/row['genexpr']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['patch_sha256']);self.assertEqual(hashlib.sha256(code).hexdigest(),row['genexpr_sha256'])
            gen=next(e['box']for e in json.loads(raw)['patcher']['boxes']if e['box']['text']=='gen~');self.assertEqual(gen['rnbo_extra_attributes']['expr'].encode(),code)
        for key,value in (('scope','fully qualified'),('maximum_absolute_error',.1),('exact_name','another')):
            bad=copy.deepcopy(c);bad['cases'][0][key]=value
            with self.assertRaises(builder.ExportError):builder.gen_execution_catalog(bad)
    def test_collector_recomputes_all_reference_blocks_and_retains_complete_ledger(self):
        c=json.loads((BASE/'catalog.json').read_text());cases=[]
        for row in c['cases']:
            inputs=list(r.case_input_words(row['model']));blocks=[list(v)for v in r.reference_blocks(row['model'],inputs)]
            cases.append(dict(row,source_sha256=row['patch_sha256'],input_words=inputs,expected=blocks[0],expected_blocks=blocks,absolute_tolerance=0,
                expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest()))
        plan=dict(cases=cases,surface='genexpr',warmup_blocks=4,timed_blocks=16,prepare_zero_warm_blocks=0,catalog_sha256=builder.GEN_EXEC_CATALOG_SHA,reference_source_sha256=builder.GEN_EXEC_REFERENCE_SHA)
        collector.gen_execution_plan(plan)
        for key,value in (('scope','numeric FFT verified'),('absolute_tolerance',.001),('input_words',[0]*512)):
            bad=dict(cases[0],**{key:value})
            with self.assertRaises(ValueError):collector.gen_execution_plan(dict(plan,cases=[bad]+cases[1:]))
        bad=copy.deepcopy(cases[-1]);bad['expected_blocks'][19][511]^=1
        bad['expected_stream_sha256']=hashlib.sha256(struct.pack('<10240I',*(w for b in bad['expected_blocks']for w in b))).hexdigest()
        with self.assertRaises(ValueError):collector.gen_execution_plan(dict(plan,cases=cases[:-1]+[bad]))
        with self.assertRaises(ValueError):collector.gen_execution_plan(dict(plan,cases=cases[:-1]))
        with self.assertRaises(ValueError):collector.gen_execution_plan(dict(plan,prepare_zero_warm_blocks=True))
if __name__=='__main__':unittest.main()
