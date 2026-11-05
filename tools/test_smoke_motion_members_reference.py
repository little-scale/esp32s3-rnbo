# SPDX-License-Identifier: MIT
"""Independent waveform/state witnesses and immutable source-to-result bindings."""
import copy,hashlib,importlib.util,json,struct,unittest
from pathlib import Path
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import build_object_status as status
BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-codebox-motion-members'
spec=importlib.util.spec_from_file_location('motion_reference',BASE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class MotionMemberReferenceTests(unittest.TestCase):
 def test_published_results_keep_phase_edge_and_trajectory_mismatches(self):
  root=BASE.parents[3];parts=[json.loads((root/f'evidence/xiao-smoke-rnbo-codebox-motion-members-part{i}.json').read_text())for i in(1,2)];cases=[v for d in parts for v in d['cases']]
  self.assertEqual(len(cases),36);self.assertEqual(sum(v['samples_checked']for v in cases),368640);self.assertEqual(sum(v['numeric_mismatches']for v in cases),52125)
  self.assertEqual({v['id']for v in cases if v['status']=='output_mismatch'},{'phasor-next','phasor-constructor','phasor-input-reset','gatetotrig-falling','bline-next','bline-reset','bline-set','bline-constructor'})
  self.assertTrue(all(v['finalized']and v['nonfinite_outputs']==0 for v in cases));self.assertEqual(sum(len(d['cpu_review_backlog'])for d in parts),6)
  for v in cases:self.assertEqual(v['absolute_tolerance'],struct.unpack('<f',struct.pack('<f',r.ABSOLUTE_TOLERANCES[v['model']]))[0])
  native=json.loads((root/'evidence/rnbo-codebox-motion-members-native.json').read_text());self.assertFalse(native['primary_references_changed_after_output']);self.assertEqual(native['source_catalog_sha256'],hashlib.sha256((BASE/'catalog.json').read_bytes()).hexdigest());self.assertEqual(native['sample_witness_script_sha256'],hashlib.sha256((BASE/'capture_witnesses.py').read_bytes()).hexdigest())
  byid={v['id']:v for v in cases}
  for v in native['sample_witnesses']:
   self.assertEqual(v['outside_original_limit'],byid[v['id']]['numeric_mismatches']);self.assertEqual(v['max_error'],byid[v['id']]['max_absolute_error'])

 def model(self,owner,variant):return 2000+r.ROWS.index((owner,variant))
 def blocks(self,owner,variant):
  m=self.model(owner,variant);return r.reference_blocks(m,r.case_input_words(m))
 def test_current_phase_directions_input_resets_and_long_period_state(self):
  for variant in('next','negative'):
   b=self.blocks('phasor',variant)
   for n in(0,1,255,256,511,512,1023,1024,5119):
    for ch,period in((0,512),(1,1024)):self.assertEqual(b[n//256][2*(n%256)+ch],r.word(((-n if variant=='negative'else n)%period)/period))
   self.assertNotEqual(b[0],b[1])
  for variant in('reset','input-reset'):
   b=self.blocks('phasor',variant)
   for n in(255,256,511,512):
    ch=0 if n<511 else 1;self.assertEqual(b[n//256][2*(n%256)+ch],r.word(0))
 def test_train_phase_width_and_continuity(self):
  b=self.blocks('train','next');self.assertEqual([r.value(b[0][i])for i in(0,1,254,256,257)],[1,0,1,0,0]);self.assertNotEqual(b[0],b[1])
  allwords=[w for block in b for w in block]
  self.assertEqual(sum(r.value(allwords[2*n])for n in range(512)),128)
  self.assertEqual(sum(r.value(allwords[2*n+1])for n in range(1024)),512)
 def test_hysteresis_holds_across_block_origin_and_equal_threshold(self):
  b=self.blocks('thresh','next');self.assertEqual(r.value(b[0][0]),0);self.assertEqual(r.value(b[1][0]),1)
  b=self.blocks('thresh','equal');inputs=r.case_input_words(self.model('thresh','equal'))
  for n in range(5120):
   for ch in(0,1):self.assertEqual(r.value(b[n//256][2*(n%256)+ch]),int(r.value(inputs[2*(n%256)+ch])>=.5))
 def test_dyadic_ramps_reach_targets_and_restart_after_reset(self):
  for owner in('rampsmooth','bline'):
   b=self.blocks(owner,'next');self.assertEqual(r.value(b[0][0]),.125);self.assertEqual(r.value(b[0][1]),-.0625)
   self.assertEqual(r.value(b[0][14]),1);self.assertEqual(r.value(b[0][31]),-1)
   self.assertNotEqual(b[0],b[2]);br=self.blocks(owner,'reset');self.assertEqual(r.value(br[1][0]),.125)
 def test_octaves_and_linear_maps_have_absolute_math(self):
  for owner in('mtof','ftom','ease','easexfade','xfademul'):
   m=self.model(owner,'next');inputs=r.case_input_words(m);block=r.reference_blocks(m,inputs)[0]
   for f in range(256):
    for ch in(0,1):
     x=r.value(inputs[2*f+ch]);out=r.value(block[2*f+ch]);tuning=440 if ch==0 else 432
     if owner=='mtof':self.assertEqual(out,tuning*2**((x-69)/12))
     elif owner=='ftom':self.assertAlmostEqual(tuning*2**((out-69)/12),x)
     elif owner=='ease':self.assertEqual(out,x)
     elif owner=='easexfade':self.assertEqual(out,-1+2*x if ch==0 else 2-4*x)
     else:self.assertEqual(out,1-x if ch==0 else x)
 def test_exact_catalog_embedded_sources_and_constructor_member_identity(self):
  catalog=json.loads((BASE/'catalog.json').read_text());self.assertEqual(len(catalog['cases']),36);observed=[]
  for i in(1,2):
   part=json.loads((BASE/f'part{i}.json').read_text());builder.motion_member_catalog(part);observed+=part['cases'];bad=copy.deepcopy(part);bad['cases'][0]['maximum_absolute_error']=1
   with self.assertRaises(builder.ExportError):builder.motion_member_catalog(bad)
  self.assertEqual(observed,catalog['cases'])
  for a in observed:
   code=(BASE/a['codebox']).read_bytes();raw=(BASE/a['patch']).read_bytes();self.assertEqual(hashlib.sha256(code).hexdigest(),a['codebox_sha256']);self.assertEqual(hashlib.sha256(raw).hexdigest(),a['patch_sha256']);box=next(v['box']for v in json.loads(raw)['patcher']['boxes']if v['box']['text']=='codebox~');self.assertEqual(box['rnbo_extra_attributes']['code'].encode(),code)
   self.assertEqual(status.motion_member_identity(a),'codebox:'+a['owner']if a['variant']=='constructor'else a['registry_lookup'])
   bad=dict(a,exact_name='other')
   with self.assertRaises(ValueError):status.motion_member_identity(bad)
 def test_collector_reconstructs_frozen_pool_and_rejects_reset_or_tolerance_fitting(self):
  for i in(1,2):
   catalog=json.loads((BASE/f'part{i}.json').read_text());cases=[]
   for a in catalog['cases']:
    inputs=list(r.case_input_words(a['model']));b=[list(v)for v in r.reference_blocks(a['model'],inputs)];cases.append(dict(a,source_sha256=a['patch_sha256'],codebox_source_sha256=a['codebox_sha256'],input_words=inputs,expected=b[0],expected_blocks=b,absolute_tolerance=struct.unpack('<f',struct.pack('<f',a['maximum_absolute_error']))[0],arena_bytes=2097152,expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for block in b for w in block))).hexdigest()))
   pool,indices=builder.block_pool(cases)
   for a,idx in zip(cases,indices):a['expected_block_indices']=idx;del a['expected_blocks']
   plan=dict(cases=cases,surface='codebox',warmup_blocks=4,timed_blocks=16,prepare_zero_warm_blocks=0,partition=catalog['partition'],catalog_sha256=builder.MOTION_MEMBER_PARTITIONS[i],reference_source_sha256=builder.MOTION_MEMBER_REFERENCE_SHA,expected_stream_policy='Fresh prepared motion member state; twenty continuous256-frame callbacks with only authored reset/set/input-reset actions',expected_block_storage='shared-512-word-pool',expected_reference_unique_blocks=len(pool),expected_block_pool=[list(v)for v in pool])
   collector.motion_member_plan(plan)
   for field,new in(('prepare_zero_warm_blocks',1),('expected_stream_policy','reset every block')):
    with self.assertRaises(ValueError):collector.motion_member_plan(dict(plan,**{field:new}))
   bad=copy.deepcopy(plan);bad['cases'][0]['absolute_tolerance']=.001
   with self.assertRaises(ValueError):collector.motion_member_plan(bad)
   bad=copy.deepcopy(plan);bad['expected_block_pool'][0][0]^=1
   with self.assertRaises(ValueError):collector.motion_member_plan(bad)
if __name__=='__main__':unittest.main()
