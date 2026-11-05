# SPDX-License-Identifier: MIT
"""Independent list fingerprints and exact-source guards, without devices."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import build_hardware_smoke as builder
import collect_hardware_smoke as collector

BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-codebox-list-functions'
spec=importlib.util.spec_from_file_location('list_function_reference',BASE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class ListFunctionReferenceTests(unittest.TestCase):
    def test_documented_value_and_index_fingerprints(self):
        witnesses={'delace':(325,206),'slice':(104,434),'ecils':(425,105),'filter':(325,316),
                   'indexmap':(430,1),'join':(942,1),'lace':(689,1),'len':(5,1),'median':(3,1),
                   'rot':(541,1),'sort':(730,521),'sum':(16,1),'swap':(546,1),'thin':(437,1),
                   'union':(696,1),'listsect':(206,1),'listcompare':(0,100),
                   'listswapelements':(546,1),'listscramble':(114,1)}
        for name,expected in witnesses.items():
            with self.subTest(name=name):self.assertEqual(r.expected_pair(name,4,1),expected)
        self.assertEqual(r.expected_pair('listcompare',4,4),(1,0))
        self.assertEqual(r.score([]),0);self.assertEqual(r.score([0]),100)
    def test_slice_empty_and_oversize_and_rotation_are_independent(self):
        a=[4,2,3,2,5]
        for n in (0,1,4,5,6):
            k=min(5,n)
            self.assertEqual(r.expected_pair('slice',4,n),(r.score(a[:k]),r.score(a[k:])))
            left,right=(a[:-k],a[-k:])if k else(a,[])
            self.assertEqual(r.expected_pair('ecils',4,n),(r.score(left),r.score(right)))
        self.assertEqual(r.expected_pair('rot',4,-1),(r.score([2,3,2,5,4]),-1))
        self.assertEqual(r.expected_pair('rot',4,6)[0],r.expected_pair('rot',4,1)[0])
    def test_flat_and_dotted_sources_do_not_inherit_status(self):
        catalog=json.loads((BASE/'catalog.json').read_bytes());builder.list_function_catalog(catalog)
        self.assertEqual(len(catalog['cases']),34)
        for model in range(1200,1215):
            inputs=r.case_input_words(model);self.assertEqual(r.reference_words(model,inputs),r.reference_words(model+15,inputs))
        for row in catalog['cases']:
            raw=(BASE/row['patch']).read_bytes();code=(BASE/row['codebox']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['patch_sha256'])
            self.assertEqual(builder.checked_codebox_source(row,raw),hashlib.sha256(code).hexdigest())
        for key,value in (('exact_name','listsum'),('syntax','named-value'),('maximum_absolute_error',1e-6)):
            bad=copy.deepcopy(catalog);bad['cases'][-1][key]=value
            with self.assertRaises(builder.ExportError):builder.list_function_catalog(bad)
    def test_scramble_mapping_validation_is_an_invariant_not_a_fixed_sequence(self):
        a=[4,10,30,20,50]
        for indices in ([0,1,2,3,4],[4,3,2,1,0],[1,4,0,3,2]):
            shuffled=[a[i]for i in indices]
            self.assertEqual(sum(shuffled),r.expected_pair('listscramble',4,0)[0])
            self.assertEqual(len(set(indices)),5)
        source=(BASE/'listscramble-call.rnbo').read_text()
        self.assertIn('indices[j]==raw',source);self.assertIn('shuffled[i]==wanted',source)
        self.assertNotIn('a[index]',source)  # no unchecked random index dereference
    def test_collector_rejects_changed_reference_or_call_form(self):
        catalog=json.loads((BASE/'catalog.json').read_bytes());cases=[]
        for row in catalog['cases']:
            inputs=list(r.case_input_words(row['model']))
            cases.append(dict(row,source_sha256=row['patch_sha256'],codebox_source_sha256=row['codebox_sha256'],
                input_words=inputs,expected=list(r.reference_words(row['model'],inputs)),absolute_tolerance=0))
        plan=dict(cases=cases,surface='codebox',prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,
            catalog_sha256=builder.LIST_FUNCTION_CATALOG_SHA,reference_source_sha256=builder.LIST_FUNCTION_REFERENCE_SHA)
        collector.list_function_plan(plan)
        rejected=next(c for c in cases if c['id']=='listrot-call')
        remaining=[c for c in cases if c['id']!='listrot-call']
        fault=dict(rejected,status='native_preflight_failed',stage='native-preflight',returncode=3,
                   native_process_status=-4,native_fault_call=0,native_samples_checked=0,
                   native_harness_sha256='a'*64,failure_log_sha256='b'*64)
        gated=dict(plan,cases=remaining,admission_failures=[fault])
        collector.list_function_plan(gated)
        with self.assertRaises(ValueError):
            collector.list_function_plan(dict(gated,admission_failures=[dict(fault,native_process_status=0)]))
        for key,value in (('exact_name','list.sum'),('codebox_source_sha256','0'*64),('absolute_tolerance',1e-6),('expected',[0]*512),('expected_blocks',[])):
            bad=dict(plan,cases=[dict(cases[0],**{key:value})]+cases[1:])
            with self.subTest(key=key),self.assertRaises(ValueError):collector.list_function_plan(bad)
        with self.assertRaises(ValueError):collector.list_function_plan(dict(plan,prepare_zero_warm_blocks=True))
        words=list(r.case_input_words(1200));words[0]=r.word(99)
        with self.assertRaises(ValueError):r.reference_words(1200,words)

if __name__=='__main__':unittest.main()
