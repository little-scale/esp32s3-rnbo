# SPDX-License-Identifier: MIT
"""Old-state, sample-age and independent convolution witnesses for Gen."""
import copy,hashlib,importlib.util,json,struct,unittest
from pathlib import Path
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/gen-routing-causality'
spec=importlib.util.spec_from_file_location('gen_causal_reference',BASE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class GenRoutingCausalityReferenceTests(unittest.TestCase):
 def test_published_target_outcomes_keep_rejections_and_rounding_separate(self):
  root=BASE.parents[3];d=json.loads((root/'evidence/xiao-smoke-gen-routing-causality.json').read_text());self.assertEqual(d['summary']['executed'],15);self.assertEqual(d['summary']['passed'],15);self.assertEqual(len(d['compile_failures']),10);self.assertEqual(len(d['admission_failures']),1)
  self.assertEqual({v['registry_lookup']for v in d['compile_failures']},{'in','out','gen','expr','send','s','receive','r','setparam'});self.assertEqual(d['admission_failures'][0]['id'],'history-conditional-update')
  self.assertEqual(sum(v['samples_checked']for v in d['cases']),153600);self.assertEqual(sum(v['numeric_mismatches']for v in d['cases']),0);self.assertEqual(sum(v['within_tolerance_differences']for v in d['cases']),8610);self.assertEqual(sum(v['zero_sign_differences']for v in d['cases']),0);self.assertEqual([v['id']for v in d['cases']if v['cpu_review_reasons']],['loop-history-feedback'])
  for v in d['cases']:self.assertEqual(v['absolute_tolerance'],struct.unpack('<f',struct.pack('<f',r.ABSOLUTE_TOLERANCES[v['model']]))[0])
  n=json.loads((root/'evidence/gen-routing-causality-native.json').read_text());self.assertFalse(n['primary_references_changed_after_output']);self.assertEqual(n['source_catalog_sha256'],hashlib.sha256((BASE/'catalog.json').read_bytes()).hexdigest())

 def words(self,name):
  model=next(m for m,n in r.MODEL_NAMES.items()if n==name);return r.reference_blocks(model,r.case_input_words(model))
 def test_chain_initial_values_and_three_sample_delay_cross_callbacks(self):
  b=self.words('history-chain3');inputs=r.case_input_words(2212);self.assertEqual(b[0][:6],tuple(r.word(v)for v in(.75,-.75,-.5,.5,.25,-.25)))
  for n in(3,255,256,257,511,512,5119):
   for ch in(0,1):self.assertEqual(b[n//256][2*(n%256)+ch],inputs[2*((n-3)%256)+ch])
 def test_read_fanout_and_last_conditional_update(self):
  inputs=r.case_input_words(2216);b=self.words('history-conditional-update');other=self.words('history-conditional-tail');third=self.words('history-conditional-ternary');self.assertEqual(b,other);self.assertEqual(b,third);held=.25
  for n in range(5120):
   x,y=map(r.value,inputs[2*(n%256):2*(n%256)+2]);self.assertEqual(b[n//256][2*(n%256)],r.word(held))
   if y>0:held=x
  b=self.words('history-read-twice');self.assertEqual(b[0][0],r.word(.5));self.assertEqual(b[1][0],r.word(2*r.value(inputs[510])))
 def test_coupled_convolution_matches_algebraic_recurrence_with_tight_error(self):
  inputs=r.case_input_words(2214);b=self.words('history-cross-feedback');state=[.25,-.5]
  for n in range(5120):
   for ch in(0,1):self.assertAlmostEqual(r.value(b[n//256][2*(n%256)+ch]),state[ch],delta=1e-7)
   x,y=map(r.value,inputs[2*(n%256):2*(n%256)+2]);state=[x+.5*state[1],y+.25*state[0]]
 def test_three_state_rotation_and_declared_imperative_policy_are_distinct(self):
  b=self.words('history-rotate-temporaries');self.assertEqual(b[0][:8],tuple(r.word(v)for v in(1,2,2,4,4,1,1,2)));self.assertNotEqual(b[0],b[1]);c=self.words('history-rotate-imperative');self.assertNotEqual(c,b);self.assertEqual(c[0][:4],tuple(r.word(v)for v in(2,4,4,2)))
 def test_history_age_impulses_cross_ordinary_block_edges(self):
  b=self.words('history-impulse-age')
  for n in(0,254,255,256,257,262,263,510,511,512):
   self.assertEqual(b[n//256][2*(n%256)],r.word(int(n%257==255)));self.assertEqual(b[n//256][2*(n%256)+1],r.word(int(n%263==0)))
 def test_catalog_embedded_programs_and_no_alias_inheritance(self):
  catalog=json.loads((BASE/'catalog.json').read_text());builder.gen_causal_catalog(catalog);self.assertEqual(len(catalog['cases']),26)
  names={v['registry_lookup']for v in catalog['cases']if v['model']<2210};self.assertEqual(names,{'in','out','gen','expr','send','s','receive','r','setparam'})
  for a in catalog['cases']:
   raw=(BASE/a['patch']).read_bytes();code=(BASE/a['genexpr']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),a['patch_sha256']);self.assertEqual(hashlib.sha256(code).hexdigest(),a['genexpr_sha256']);box=next(v['box']for v in json.loads(raw)['patcher']['boxes']if v['box']['text']=='gen~');self.assertEqual(box['rnbo_extra_attributes']['expr'].encode(),code)
  bad=copy.deepcopy(catalog);bad['cases'][0]['scope']='all Gen forms'
  with self.assertRaises(builder.ExportError):builder.gen_causal_catalog(bad)
 def test_collector_rejects_reference_reset_and_tolerance_fitting(self):
  catalog=json.loads((BASE/'catalog.json').read_text());cases=[]
  for a in catalog['cases']:
   inputs=list(r.case_input_words(a['model']));b=[list(v)for v in r.reference_blocks(a['model'],inputs)];cases.append(dict(a,source_sha256=a['patch_sha256'],input_words=inputs,expected=b[0],expected_blocks=b,expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for block in b for w in block))).hexdigest(),absolute_tolerance=struct.unpack('<f',struct.pack('<f',a['maximum_absolute_error']))[0]))
  plan=dict(cases=cases,surface='genexpr',catalog_sha256=builder.GEN_CAUSAL_CATALOG_SHA,reference_source_sha256=builder.GEN_CAUSAL_REFERENCE_SHA,prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,expected_stream_policy='Fresh prepared state, no automatic zero warmup; four checked manual warmups then sixteen timed callbacks without resets');collector.gen_causal_plan(plan)
  for key,v in(('prepare_zero_warm_blocks',1),('expected_stream_policy','resets each block')):
   with self.assertRaises(ValueError):collector.gen_causal_plan(dict(plan,**{key:v}))
  bad=copy.deepcopy(plan);bad['cases'][14]['absolute_tolerance']=.001
  with self.assertRaises(ValueError):collector.gen_causal_plan(bad)
  bad=copy.deepcopy(plan);bad['cases'][12]['expected_blocks'][1][0]^=1
  with self.assertRaises(ValueError):collector.gen_causal_plan(bad)
if __name__=='__main__':unittest.main()
