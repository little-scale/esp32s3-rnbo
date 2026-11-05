# SPDX-License-Identifier: MIT
"""Gen predicate aliases, bounded loops and absolute-age state; no devices."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import build_hardware_smoke as builder
import collect_hardware_smoke as collector

BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/gen-control-structures'
spec=importlib.util.spec_from_file_location('gen_control_ref',BASE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class GenControlReferenceTests(unittest.TestCase):
    def test_comparators_pass_first_operand_and_each_symbol_has_its_own_source(self):
        for model in range(1100,1112,2):
            inputs=r.case_input_words(model);a=r.reference_blocks(model,inputs);b=r.reference_blocks(model+1,inputs)
            self.assertEqual(a,b)
            predicate=r.PREDICATES[(model-1100)//2]
            for i in (0,1,15,16,127,128,255):
                x,y=map(r.value,inputs[2*i:2*i+2]);left,right=map(r.value,a[0][2*i:2*i+2])
                self.assertEqual(left,x if predicate(x,y) else 0)
                self.assertEqual(right,y if predicate(y,x) else 0)
        self.assertNotEqual(r.reference_blocks(1104,r.case_input_words(1104)),r.reference_blocks(1106,r.case_input_words(1106)))
    def test_history_and_function_instances_have_nonzero_initial_and_previous_sample_values(self):
        for model,initial in ((1119,(.25,-.5)),(1121,(.25,.25))):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs);flat=[w for b in blocks for w in b]
            self.assertEqual(tuple(map(r.value,flat[:2])),initial)
            for n in (1,2,255,256,257,511,512,5119):self.assertEqual(tuple(flat[2*n:2*n+2]),inputs[2*((n-1)%256):2*((n-1)%256)+2])
    def test_loop_polynomials_include_zero_and_one_trips_and_break_continue(self):
        # Explicit small sums, independent of Gen execution and implementation loops.
        for model in (1122,1123,1124):
            inputs=r.case_input_words(model);block=r.reference_blocks(model,inputs)[0]
            counts=set()
            for frame in range(256):
                n,y=map(r.value,inputs[2*frame:2*frame+2]);n=int(n);counts.add(n)
                expected=sum((i+1)*y for i in range(n)) if model==1122 else sum(i*i*y for i in range(n)) if model==1123 else sum((i+1)*y for i in range(n)if i!=2)
                self.assertEqual(r.value(block[2*frame]),expected)
            self.assertEqual(counts,set(range(6)))
    def test_elapsed_and_branch_history_cross_each_host_boundary(self):
        inputs=r.case_input_words(1114);blocks=r.reference_blocks(1114,inputs)
        for n in (0,1,255,256,257,5119):self.assertEqual(r.value(blocks[n//256][2*(n%256)]),n)
        inputs=r.case_input_words(1125);flat=[r.value(w) for b in r.reference_blocks(1125,inputs)for w in b]
        changes=[int(r.value(inputs[2*n])>0)-int(r.value(inputs[2*n])<0)for n in range(256)]
        for n in (0,1,255,256,257,5119):self.assertEqual(flat[2*n],sum(changes[k%256]for k in range(n)))
    def test_catalog_and_embedded_expression_identity_reject_changed_forms(self):
        catalog=json.loads((BASE/'catalog.json').read_bytes());builder.gen_control_catalog(catalog)
        self.assertEqual(len(catalog['cases']),26)
        for row in catalog['cases']:
            patch=(BASE/row['patch']).read_bytes();code=(BASE/row['genexpr']).read_bytes()
            self.assertEqual(hashlib.sha256(patch).hexdigest(),row['patch_sha256'])
            self.assertEqual(hashlib.sha256(code).hexdigest(),row['genexpr_sha256'])
            gen=next(v['box']for v in json.loads(patch)['patcher']['boxes']if v['box']['text']=='gen~')
            self.assertEqual(gen['rnbo_extra_attributes']['expr'].encode(),code)
        for key,value in (('exact_name','alias'),('syntax','call'),('maximum_absolute_error',1e-3)):
            bad=copy.deepcopy(catalog);bad['cases'][-1][key]=value
            with self.assertRaises(builder.ExportError):builder.gen_control_catalog(bad)
    def test_collector_binds_fresh_streams_and_does_not_allow_fitted_reference(self):
        catalog=json.loads((BASE/'catalog.json').read_bytes());cases=[]
        for row in catalog['cases']:
            inputs=list(r.case_input_words(row['model']));blocks=[list(b)for b in r.reference_blocks(row['model'],inputs)]
            cases.append(dict(row,source_sha256=row['patch_sha256'],input_words=inputs,expected=blocks[0],expected_blocks=blocks,
                absolute_tolerance=0,expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest()))
        plan=dict(cases=cases,surface='genexpr',warmup_blocks=4,timed_blocks=16,prepare_zero_warm_blocks=0,
            catalog_sha256=builder.GEN_CONTROL_CATALOG_SHA,reference_source_sha256=builder.GEN_CONTROL_REFERENCE_SHA)
        collector.gen_control_plan(plan)
        for key,value in (('genexpr_sha256','0'*64),('exact_name','other'),('absolute_tolerance',1e-6),('parameter_events',[])):
            first=dict(cases[0],**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):collector.gen_control_plan(dict(plan,cases=[first]+cases[1:]))
        first=copy.deepcopy(cases[0]);first['expected_blocks'][19][511]^=1
        first['expected_stream_sha256']=hashlib.sha256(struct.pack('<10240I',*(w for b in first['expected_blocks']for w in b))).hexdigest()
        with self.assertRaises(ValueError):collector.gen_control_plan(dict(plan,cases=[first]+cases[1:]))
        with self.assertRaises(ValueError):collector.gen_control_plan(dict(plan,prepare_zero_warm_blocks=True))
        words=list(r.case_input_words(1100));words[0]=r.word(99)
        with self.assertRaises(ValueError):r.reference_blocks(1100,words)

if __name__=='__main__':unittest.main()
