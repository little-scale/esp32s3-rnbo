# SPDX-License-Identifier: MIT
"""Independent list contracts and absolute-age array witnesses, without devices."""
import copy
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
import unittest
import build_hardware_smoke as builder
import build_object_status as status
import collect_hardware_smoke as collector

BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-codebox-containers'
spec=importlib.util.spec_from_file_location('container_reference',BASE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class ContainerReferenceTests(unittest.TestCase):
    def test_list_return_and_mutation_are_independent_outputs(self):
        expected={'push':(6,101),'pop':(5,28),'shift':(7,34),'concat':(151,53),
                  'fill':(105,105),'unshift':(6,80),'splice':(8,47),'slice':(14,53),
                  'includes':(0,53),'indexOf':(-1,53),'reverse':(61,61)}
        # Explicit witnesses calculated from [x,2,3,2,5], x7/y8, without RNBO.
        for name,pair in expected.items():
            with self.subTest(name=name):self.assertEqual(r.list_result(name,7,8),pair)
        self.assertEqual(r.list_result('includes',0,2)[0],1)
        self.assertEqual(r.list_result('indexOf',0,2)[0],1)
    def test_array_age_crosses_host_boundaries_and_truncates_integer_writes(self):
        for model in range(1011,1028):
            words=r.case_input_words(model);blocks=r.reference_blocks(model,words)
            self.assertEqual(len(blocks),20)
            flat=[r.value(w)for b in blocks for w in b]
            self.assertEqual(flat[1:8:2],[2,3,4,5])
            for n in (4,5,255,256,257,511,512,5119):
                self.assertEqual(flat[2*n+1],flat[2*(n-4)])
        self.assertEqual(r.value(r.reference_blocks(1011,r.case_input_words(1011))[0][0]),-4)
        # A nonintegral sample distinguishes integer storage from Float32.
        self.assertEqual(r.value(r.reference_blocks(1011,r.case_input_words(1011))[0][2]),-3)
        self.assertEqual(r.value(r.reference_blocks(1017,r.case_input_words(1017))[0][2]),-3.75)
    def test_original_programs_catalog_identity_and_surface_join_are_exact(self):
        catalog=json.loads((BASE/'catalog.json').read_bytes());builder.container_catalog(catalog)
        self.assertEqual(len(catalog['cases']),28)
        for row in catalog['cases']:
            source=(BASE/row['patch']).read_bytes();code=(BASE/row['codebox']).read_bytes()
            self.assertEqual(hashlib.sha256(source).hexdigest(),row['patch_sha256'])
            self.assertEqual(hashlib.sha256(code).hexdigest(),row['codebox_sha256'])
            self.assertEqual(builder.checked_codebox_source(row,source),row['codebox_sha256'])
            self.assertEqual(status.container_identity(row),row['registry_lookup'])
        for key in ('exact_name','registry_lookup','maximum_absolute_error'):
            bad=copy.deepcopy(catalog);bad['cases'][0][key]='changed'
            with self.assertRaises(builder.ExportError):builder.container_catalog(bad)
        bad=dict(catalog['cases'][0],registry_lookup='codebox:push')
        with self.assertRaises(ValueError):status.container_identity(bad)
    def test_reference_rejects_changed_vectors_or_counts(self):
        words=list(r.case_input_words(1000));words[0]=r.word(99)
        with self.assertRaises(ValueError):r.reference_blocks(1000,words)
        for count in (0,21,True):
            with self.assertRaises(ValueError):r.reference_blocks(1000,r.case_input_words(1000),count)

    def test_collector_binds_independent_streams_types_and_zero_tolerance(self):
        catalog=json.loads((BASE/'catalog.json').read_bytes());cases=[]
        for row in catalog['cases']:
            inputs=list(r.case_input_words(row['model']));blocks=[list(b)for b in r.reference_blocks(row['model'],inputs)]
            cases.append(dict(row,source_sha256=row['patch_sha256'],codebox_source_sha256=row['codebox_sha256'],
                input_words=inputs,expected=blocks[0],expected_blocks=blocks,absolute_tolerance=0,
                expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest()))
        plan=dict(cases=cases,surface='codebox',prepare_zero_warm_blocks=0,
            catalog_sha256=builder.CONTAINER_CATALOG_SHA,reference_source_sha256=builder.CONTAINER_REFERENCE_SHA)
        collector.container_plan(plan)
        for key,value in (('registry_lookup','codebox:push'),('source_sha256','0'*64),
                          ('absolute_tolerance',1e-6),('input_words',[0]*512)):
            first=dict(cases[0],**{key:value});bad=dict(plan,cases=[first]+cases[1:])
            with self.subTest(key=key),self.assertRaises(ValueError):collector.container_plan(bad)
        # Rehashing a fitted expected stream must not evade the independent model.
        first=copy.deepcopy(cases[0]);first['expected_blocks'][19][511]^=1
        first['expected_stream_sha256']=hashlib.sha256(struct.pack('<10240I',*(w for b in first['expected_blocks']for w in b))).hexdigest()
        with self.assertRaises(ValueError):collector.container_plan(dict(plan,cases=[first]+cases[1:]))
        with self.assertRaises(ValueError):collector.container_plan(dict(plan,prepare_zero_warm_blocks=True))

if __name__=='__main__':unittest.main()
