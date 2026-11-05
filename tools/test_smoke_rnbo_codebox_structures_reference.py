# SPDX-License-Identifier: MIT
"""Independent structural witnesses and rejection of altered evidence contracts."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import build_object_status as status

BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-codebox-structures'
spec=importlib.util.spec_from_file_location('codebox_structure_ref',BASE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class CodeboxStructureTests(unittest.TestCase):
    def test_only_exact_lifecycle_hooks_can_join_existing_object_inventory(self):
        for name in ('init','startup','dspsetup'):
            row=dict(registry_lookup='codebox-hook:'+name,exact_name=name+'()',syntax='lifecycle-hook')
            self.assertEqual(status.lifecycle_identity(row),'codebox-hook:'+name)
            for key,value in (('exact_name','other()'),('registry_lookup','codebox:'+name),('syntax','call')):
                with self.subTest(key=key),self.assertRaises(ValueError):status.lifecycle_identity(dict(row,**{key:value}))
        with self.assertRaises(ValueError):status.lifecycle_identity(dict(registry_lookup='structure:hook-combined',exact_name='hook-combined',syntax='lifecycle-hook'))
    def test_short_circuit_side_effects_cross_all_callback_boundaries(self):
        for model in (1305,1306,1307,1318):
            inputs=r.case_input_words(model);flat=[r.value(w)for b in r.reference_blocks(model,inputs)for w in b]
            p=q=0
            for n in range(5120):
                x=r.value(inputs[2*(n%256)])
                if model==1318:expected=(p+.25,q-.5)
                elif model==1305:expected=(p+1 if x>0 else q+1,p+q+1)
                elif model==1306:expected=(int(x>0),p+int(x>0))
                else:expected=(1,q+int(x<=0))
                self.assertEqual(tuple(flat[2*n:2*n+2]),expected)
                p+=int(x>0);q+=int(x<=0)
    def test_loop_sums_include_zero_trips_and_do_while_one_trip(self):
        for model in range(1310,1315):
            inputs=r.case_input_words(model);block=r.reference_blocks(model,inputs)[0]
            counts=set()
            for i in range(256):
                n,y=map(r.value,inputs[2*i:2*i+2]);n=int(n);counts.add(n)
                if model==1310:expected=sum((j+1)*y for j in range(n))
                elif model==1311:expected=sum((j+1)*(k+1)*y for j in range(n)for k in range(2))
                elif model==1312:expected=sum((j+1)*y for j in range(min(n,4))if j!=2)
                elif model==1313:expected=sum(j*j*y for j in range(n))
                else:expected=sum((j+1)*y for j in range(max(1,n)))
                self.assertEqual(r.value(block[2*i]),expected)
            self.assertEqual(counts,set(range(6)))
    def test_delay_has_nonzero_initial_conditions_and_preserves_last_sample(self):
        inputs=r.case_input_words(1317);flat=[w for b in r.reference_blocks(1317,inputs)for w in b]
        self.assertEqual(tuple(map(r.value,flat[:2])),(.25,-.5))
        for n in (1,255,256,257,511,512,5119):
            self.assertEqual(tuple(flat[2*n:2*n+2]),inputs[2*((n-1)%256):2*((n-1)%256)+2])
    def test_lifecycle_counts_and_startup_observation_of_init_remain_fixed(self):
        for model in range(1320,1324):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
            for call,frame in ((0,0),(0,255),(1,0),(19,255)):
                x,y=map(r.value,inputs[2*frame:2*frame+2])
                self.assertEqual(tuple(map(r.value,blocks[call][2*frame:2*frame+2])),
                                 (111+x,1+y)if model==1323 else(1+x,y))
    def test_catalog_graph_and_scalar_reference_limits_are_bound(self):
        catalog=json.loads((BASE/'catalog.json').read_bytes());builder.structure_catalog(catalog)
        self.assertEqual(len(catalog['cases']),24)
        for row in catalog['cases']:
            source=(BASE/row['patch']).read_bytes();code=(BASE/row['codebox']).read_bytes()
            self.assertEqual(hashlib.sha256(source).hexdigest(),row['patch_sha256'])
            self.assertEqual(hashlib.sha256(code).hexdigest(),row['codebox_sha256'])
            self.assertEqual(builder.checked_codebox_source(row,source),row['codebox_sha256'])
        bad=copy.deepcopy(catalog);bad['cases'][0]['maximum_absolute_error']=1e-3
        with self.assertRaises(builder.ExportError):builder.structure_catalog(bad)
        for count in (True,0,21):
            with self.assertRaises(ValueError):r.reference_blocks(1300,r.input_words(),count)
        words=list(r.input_words());words[0]=r.word(99)
        with self.assertRaises(ValueError):r.reference_blocks(1300,words)
    def test_collector_rejects_fitted_stream_changed_source_or_tolerance(self):
        catalog=json.loads((BASE/'catalog.json').read_bytes());cases=[]
        for row in catalog['cases']:
            inputs=list(r.case_input_words(row['model']));blocks=[list(b)for b in r.reference_blocks(row['model'],inputs)]
            cases.append(dict(row,source_sha256=row['patch_sha256'],codebox_source_sha256=row['codebox_sha256'],
                input_words=inputs,expected=blocks[0],expected_blocks=blocks,absolute_tolerance=0,
                expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest()))
        plan=dict(cases=cases,surface='codebox',prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,
            catalog_sha256=builder.STRUCTURE_CATALOG_SHA,reference_source_sha256=builder.STRUCTURE_REFERENCE_SHA)
        collector.structure_plan(plan)
        for key,value in (('registry_lookup','codebox-hook:other'),('source_sha256','0'*64),('absolute_tolerance',1e-6),('parameter_events',[])):
            with self.subTest(key=key),self.assertRaises(ValueError):
                collector.structure_plan(dict(plan,cases=[dict(cases[0],**{key:value})]+cases[1:]))
        first=copy.deepcopy(cases[0]);first['expected_blocks'][19][511]^=1
        first['expected_stream_sha256']=hashlib.sha256(struct.pack('<10240I',*(w for b in first['expected_blocks']for w in b))).hexdigest()
        with self.assertRaises(ValueError):collector.structure_plan(dict(plan,cases=[first]+cases[1:]))
        with self.assertRaises(ValueError):collector.structure_plan(dict(plan,prepare_zero_warm_blocks=True))

if __name__=='__main__':unittest.main()
