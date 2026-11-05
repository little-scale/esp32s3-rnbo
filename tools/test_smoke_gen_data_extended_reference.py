# SPDX-License-Identifier: MIT
"""Independent Gen table/phase contracts and immutable evidence/source limits."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import build_hardware_smoke as builder
import collect_hardware_smoke as collector

BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/gen-data-extended'
spec=importlib.util.spec_from_file_location('gen_data_extended_ref',BASE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class ExtendedGenDataReferenceTests(unittest.TestCase):
    def test_published_device_results_preserve_native_portability_disagreements(self):
        root=BASE.parents[3]
        parts=[json.loads((root/f'evidence/xiao-smoke-gen-data-extended-part{i}.json').read_bytes())for i in(1,2)]
        cases=[r for part in parts for r in part['cases']]
        self.assertEqual(len(cases),24)
        self.assertEqual(sum(r['status']=='pass'for r in cases),17)
        self.assertEqual(sum(r['status']=='output_mismatch'for r in cases),7)
        self.assertEqual(sum(r['samples_checked']for r in cases),245760)
        self.assertEqual(sum(r['numeric_mismatches']for r in cases),35340)
        self.assertEqual(sum(r['within_tolerance_differences']for r in cases),8296)
        self.assertEqual(sum(r['zero_sign_differences']for r in cases),1920)
        native=json.loads((root/'evidence/gen-data-extended-native.json').read_bytes())
        byid={r['id']:r for r in cases};different=set()
        for row in native['cases']:
            target=byid[row['id']]
            self.assertEqual(row['input_words_sha256'],target['input_words_sha256'])
            self.assertEqual(row['expected_stream_sha256'],target['expected_stream_sha256'])
            if row['bit_differences']!=target['bit_mismatches']or row['max_error']!=target['max_absolute_error']:different.add(row['id'])
        self.assertEqual(different,{'peek-channel-'+mode for mode in('ignore','wrap','clamp','fold','mirror')})
        self.assertFalse(native['native_target_diagnostics_equal'])
        self.assertTrue(native['negative_channel_sanitizer']['host_diagnostic_only'])
        self.assertNotEqual(native['negative_channel_sanitizer']['returncode'],0)
        self.assertIn('-2 is outside',native['negative_channel_sanitizer']['first_diagnostic'])
        self.assertEqual(byid['cycle-frequency-long-period']['status'],'pass')
        self.assertEqual(byid['splat-accum']['status'],'pass')
        self.assertEqual(byid['splat-mix-half']['status'],'pass')
        self.assertEqual([r['id']for r in cases if r['cpu_review_reasons']],['lookup-signal'])
    def test_boundary_policies_distinguish_reflected_endpoint_conventions(self):
        samples=(-2,-1,0,1,6,7,8,9)
        expected={
            'ignore':(None,None,0,1,6,7,None,None),
            'clamp':(0,0,0,1,6,7,7,7),
            'wrap':(6,7,0,1,6,7,0,1),
            'fold':(2,1,0,1,6,7,6,5),
            'mirror':(1,0,0,1,6,7,7,6)}
        for mode,wanted in expected.items():self.assertEqual(tuple(r.bounded(k,8,mode)for k in samples),wanted)
        self.assertEqual(tuple(r.bounded(k,2,'fold')for k in(-2,-1,0,1,2,3)),(0,1,0,1,0,1))
        self.assertEqual(tuple(r.bounded(k,2,'mirror')for k in(-2,-1,0,1,2,3)),(1,0,0,1,1,0))
    def test_lookup_endpoints_and_wave_phase_period_are_declared_separately(self):
        self.assertEqual(r.table_sample(0,0),r.TABLE[0][0])
        self.assertEqual(r.table_sample(0,7),r.TABLE[0][7])
        for ch in(0,1):
            self.assertEqual(r.table_sample(ch,0,'wrap'),r.table_sample(ch,8,'wrap'))
            self.assertEqual(r.table_sample(ch,-1,'wrap'),r.TABLE[ch][7])
            self.assertEqual(r.table_sample(ch,2.25),.75*r.TABLE[ch][2]+.25*r.TABLE[ch][3])
        # Explicit phase index output is unwrapped in this predeclared screen.
        inputs=r.case_input_words(1624);blocks=r.reference_blocks(1624,inputs)
        self.assertEqual(r.value(blocks[0][1]),8*r.value(inputs[0]))
    def test_splat_distribution_and_prefix_sum_observe_write_state_across_blocks(self):
        for model in(1609,1612):
            inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
            for frame in(0,1,31,127,255):
                x=r.value(inputs[2*frame]);left,right=map(r.value,blocks[0][2*frame:2*frame+2])
                self.assertEqual(left+right,x)
        inputs=r.case_input_words(1610);blocks=r.reference_blocks(1610,inputs);total=0
        for n in range(5120):
            total+=r.value(inputs[2*(n%256)])
            self.assertEqual(tuple(map(r.value,blocks[n//256][2*(n%256):2*(n%256)+2])),(.75*total,.25*total))
        self.assertNotEqual(blocks[0],blocks[1])
    def test_long_period_cycle_exposes_reset_at_each_host_block(self):
        blocks=r.reference_blocks(1630,r.case_input_words(1630))
        self.assertEqual(r.value(blocks[0][0]),1)
        self.assertEqual(r.value(blocks[1][0]),-1)
        self.assertEqual(r.value(blocks[2][0]),1)
        self.assertAlmostEqual(r.value(blocks[1][1]),0,places=12)
        self.assertEqual(r.value(blocks[2][1]),-1)
        self.assertNotEqual(blocks[0],blocks[1])
        self.assertNotEqual(blocks[0],blocks[2])
    def test_catalog_sources_and_partitions_are_exact(self):
        parent=json.loads((BASE/'catalog.json').read_bytes());self.assertEqual(len(parent['cases']),31)
        observed=[]
        for i,count in((1,16),(2,15)):
            part=json.loads((BASE/f'part{i}.json').read_bytes());builder.gen_extended_catalog(part)
            self.assertEqual(len(part['cases']),count);observed+=part['cases']
            bad=copy.deepcopy(part);bad['cases'][0]['maximum_absolute_error']=.001
            with self.assertRaises(builder.ExportError):builder.gen_extended_catalog(bad)
            for row in part['cases']:
                patch=(BASE/row['patch']).read_bytes();code=(BASE/row['genexpr']).read_bytes()
                self.assertEqual(hashlib.sha256(patch).hexdigest(),row['patch_sha256'])
                self.assertEqual(hashlib.sha256(code).hexdigest(),row['genexpr_sha256'])
                gen=next(x['box']for x in json.loads(patch)['patcher']['boxes']if x['box']['text']=='gen~')
                self.assertEqual(gen['rnbo_extra_attributes']['expr'].encode(),code)
        self.assertEqual({r['id']for r in observed},{r['id']for r in parent['cases']})
        self.assertEqual(len(observed),31)
    def test_collector_rejects_changed_storage_tolerance_reference_or_epoch(self):
        catalog=json.loads((BASE/'part1.json').read_bytes());cases=[]
        for row in catalog['cases']:
            inputs=list(r.case_input_words(row['model']));blocks=[list(b)for b in r.reference_blocks(row['model'],inputs)]
            cases.append(dict(row,source_sha256=row['patch_sha256'],input_words=inputs,expected=blocks[0],expected_blocks=blocks,
                absolute_tolerance=struct.unpack('<f',struct.pack('<f',row['maximum_absolute_error']))[0],arena_bytes=2097152,
                expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest()))
        plan=dict(cases=cases,surface='genexpr',prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,
            partition=catalog['partition'],producer_storage_view=catalog['producer_storage_view'],storage_policy=catalog['storage_policy'],
            expected_stream_policy='Fresh prepared state, no automatic zero warmup; four checked manual warmups then sixteen timed callbacks without resets',
            catalog_sha256=builder.GEN_EXT_PARTITIONS[1],reference_source_sha256=builder.GEN_EXT_REFERENCE_SHA)
        collector.gen_extended_plan(plan)
        for key,value in(('genexpr_sha256','0'*64),('arena_bytes',4096),('absolute_tolerance',.001),('parameter_events',[])):
            with self.subTest(key=key),self.assertRaises(ValueError):collector.gen_extended_plan(dict(plan,cases=[dict(cases[0],**{key:value})]+cases[1:]))
        first=copy.deepcopy(cases[0]);first['expected_blocks'][19][511]^=1
        first['expected_stream_sha256']=hashlib.sha256(struct.pack('<10240I',*(w for b in first['expected_blocks']for w in b))).hexdigest()
        with self.assertRaises(ValueError):collector.gen_extended_plan(dict(plan,cases=[first]+cases[1:]))
        for key,value in(('prepare_zero_warm_blocks',True),('storage_policy','Float64 rewritten'),('expected_stream_policy','Reset every block')):
            with self.subTest(key=key),self.assertRaises(ValueError):collector.gen_extended_plan(dict(plan,**{key:value}))
        with self.assertRaises(ValueError):r.reference_blocks(1600,[r.word(99)]*512)

if __name__=='__main__':unittest.main()
