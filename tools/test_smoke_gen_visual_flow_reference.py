# SPDX-License-Identifier: MIT
"""State continuity, explicit outlet routing and immutable visual-flow proof guards."""
import copy,hashlib,importlib.util,json,math,struct,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import build_object_status as publisher
import visual_gen_provenance as provenance
HERE=builder.ROOT/'tests/fixtures/smoke/gen-visual-flow'
spec=importlib.util.spec_from_file_location('visual_flow_reference',HERE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def model(identity):return next(m for m,s in r.MODEL_SPECS.items()if s['id']==identity)
def left(identity,call=0):
 m=model(identity);return tuple(map(r.value,r.reference_blocks(m,r.case_input_words(m))[call][::2]))
class VisualFlowTests(unittest.TestCase):
 def test_sample_difference_change_and_cross_block_previous_input(self):
  self.assertEqual(left('delta')[:8],(0,.25,0,-.75,0,.5,1,0))
  self.assertEqual(left('change')[:8],(0,1,0,-1,0,1,1,0))
  self.assertEqual(left('delta',1)[0],-.75);self.assertEqual(left('change',1)[0],-1)
 def test_held_samples_retain_state_and_thresholds_are_distinct(self):
  self.assertEqual(left('latch')[:6],(0,.25,.25,.25,-.5,-0.))
  self.assertEqual(left('latch',1)[0],.75);self.assertEqual(left('sah-zero',1)[0],.125)
  self.assertNotEqual(left('sah-zero'),left('sah-half'));self.assertNotEqual(left('sah-zero'),left('sah-signal'))
 def test_prefix_reset_and_smoothing_landmarks(self):
  self.assertEqual(left('accum-reset-zero')[:8],(0,.25,.5,0,-.5,-.5,.5,1.5))
  self.assertEqual(left('accum-reset-signal')[:4],(0,0,0,-.5))
  self.assertEqual(left('accum-reset-zero'),left('plusequals-reset-zero'))
  self.assertEqual(left('slide-up2-down4')[:6],(0,.125,.1875,.015625,-.11328125,-.056640625))
  self.assertNotEqual(left('slide-up2-down4'),left('slide-up4-down2'))
  self.assertNotEqual(left('dcblock')[0],left('dcblock',1)[0])
 def test_counter_three_outputs_and_wrap_continuity(self):
  self.assertEqual(left('counter-out0')[:8],(1,2,3,4,5,6,0,1))
  self.assertEqual(left('counter-out1')[:8],(0,0,0,0,0,0,1,0))
  self.assertEqual(left('counter-out2')[:8],(0,0,0,0,0,0,1,1))
  self.assertEqual(left('counter-out0')[255],4);self.assertEqual(left('counter-out0',1)[0],5)
  self.assertEqual(left('counter-out2',19)[255],5120//7)
 def test_range_coordinates_conversions_and_explicit_finite_scope(self):
  def op(n,x,y=0):return r.stateless(r.spec(model(n)),x,y)
  self.assertEqual(op('fold',2),0);self.assertEqual(op('wrap',2),0);self.assertEqual(op('clip',2),1)
  self.assertEqual(op('mix',.5,-.5),.25);self.assertEqual(op('smoothstep',0),.5);self.assertEqual(op('mod',-1.5,1),-.5)
  self.assertEqual(op('cartopol-out0',3,4),5);self.assertAlmostEqual(op('cartopol-out1',1,1),math.pi/4)
  self.assertEqual(op('poltocar-out0',2,0),2);self.assertEqual(op('poltocar-out1',2,0),0)
  self.assertEqual(op('mtof',69),440);self.assertAlmostEqual(op('ftom',440*2**(.25/12)),69.25)
  self.assertEqual(op('isnan',1),0);self.assertEqual(op('fixnan',1),1)
 def test_all_words_right_lane_and_models_are_fixed(self):
  self.assertEqual(len(r.MODELS),42);self.assertEqual(len({s['name']for s in r.MODEL_SPECS.values()}),33)
  for m in r.MODELS:
   ins=r.case_input_words(m);bs=r.reference_blocks(m,ins);self.assertEqual(len(bs),20)
   self.assertTrue(all(len(b)==512 and b[1::2]==ins[1::2]for b in bs));self.assertTrue(all((w&0x7f800000)!=0x7f800000 for b in bs for w in b))
  for m,ins,count in((True,r.input_words(),20),(3199,r.input_words(),20),(3200,(0,0),20),(3200,r.input_words(),0)):
   with self.assertRaises(ValueError):r.reference_blocks(m,ins,count)
 def test_catalog_sources_snapshot_and_distinct_spellings(self):
  all_sources=[]
  for i in(1,2,3):
   c=json.loads((HERE/f'part{i}.json').read_bytes());builder.visual_flow_catalog(c);all_sources+=c['cases']
   changed=copy.deepcopy(c);changed['cases'][0]['observed_outlet']=9
   with self.assertRaises(ValueError):builder.visual_flow_catalog(changed)
  self.assertEqual(len(all_sources),42);self.assertEqual(all_sources,json.loads((HERE/'catalog.json').read_bytes())['cases'])
  self.assertEqual(builder.sha(HERE/'reference.py'),builder.VISUAL_FLOW_REFERENCE_SHA)
  for s in all_sources:self.assertEqual(builder.sha(HERE/s['patch']),s['patch_sha256'])
  snapshot='tests/fixtures/smoke/gen-visual-flow/qualified_lowerer.mjs';self.assertEqual(builder.sha(HERE/'qualified_lowerer.mjs'),provenance.QUALIFIED_LOWERERS[snapshot])
 def test_port_draft_corrections_do_not_change_any_numerical_stream(self):
  folder=HERE/'port-draft-v1';sp=importlib.util.spec_from_file_location('flow_draft',folder/'reference.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old)
  for m in r.MODELS:self.assertEqual(old.reference_blocks(m,old.case_input_words(m)),r.reference_blocks(m,r.case_input_words(m)));self.assertEqual(old.ABSOLUTE_TOLERANCES[m],r.ABSOLUTE_TOLERANCES[m])
  changed=[s['visual_operator']for s in json.loads((folder/'catalog.json').read_bytes())['cases']if builder.sha(HERE/s['patch'])!=s['patch_sha256']]
  self.assertEqual(set(changed),{'scale','mtof','ftom'})
  for src in json.loads((folder/'source-locations.json').read_bytes()).values():self.assertEqual(builder.sha(folder/src['path']),src['sha256'])
 def _plans(self):
  cat=json.loads((HERE/'catalog.json').read_bytes());graphs=[next(b['box']['genpatcher']for b in json.loads((HERE/s['patch']).read_bytes())['patcher']['boxes']if b['box'].get('text')=='gen~')for s in cat['cases']]
  adapter=HERE/'qualified_lowerer.mjs';script="import fs from 'node:fs';import {lowerVisualGen} from "+json.dumps(adapter.as_uri())+";process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(lowerVisualGen)));"
  lowered=json.loads(subprocess.run(['node','--input-type=module','-e',script],input=json.dumps(graphs),text=True,capture_output=True,check=True).stdout);rows={}
  for source,g,v in zip(cat['cases'],graphs,lowered):
   m=source['model'];ins=r.case_input_words(m);bs=r.reference_blocks(m,ins);proof=dict(box_id='gen',policy=v['policy'],nodes=v['nodes'],edges=v['edges'],histories=v['history_count'],operators=v['operators'],source_graph_sha256=hashlib.sha256(json.dumps(g,separators=(',',':')).encode()).hexdigest(),lowered_genexpr_sha256=hashlib.sha256(v['expression'].encode()).hexdigest(),adapter_sha256=builder.sha(adapter))
   rows[source['id']]=dict(**source,source_sha256=source['patch_sha256'],absolute_tolerance=builder.float32(source['maximum_absolute_error']),input_words=list(ins),expected=list(bs[0]),expected_blocks=[list(b)for b in bs],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in bs for w in b))).hexdigest(),gen_visual_lowering=proof)
  rows['visual-mtof']['arena_bytes']=1048576
  return [dict(family='gen-visual-flow',catalog_sha256=builder.VISUAL_FLOW_PARTITIONS[i],reference_source_sha256=builder.VISUAL_FLOW_REFERENCE_SHA,partition=(part:=json.loads((HERE/f'part{i}.json').read_bytes()))['partition'],surface='patcher',prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,cases=[rows[s['id']]for s in part['cases']])for i in(1,2,3)]
 def test_collector_rebinds_state_stream_and_every_selected_outlet(self):
  for plan in self._plans():
   collector.visual_flow_plan(plan)
   for mutate in(lambda p:p['cases'][0].update(observed_outlet=9),lambda p:p['cases'][0].update(absolute_tolerance=.001),lambda p:p['cases'][0]['expected_blocks'][1].__setitem__(0,r.word(7)),lambda p:p['cases'][0]['gen_visual_lowering'].update(adapter_sha256='0'*64),lambda p:p.update(prepare_zero_warm_blocks=4),lambda p:p['cases'].pop()):
    changed=copy.deepcopy(plan);mutate(changed)
    with self.assertRaises(ValueError):collector.visual_flow_plan(changed)
 def test_historical_snapshots_do_not_resolve_current_producer(self):
  old=json.loads((builder.ROOT/'evidence/xiao-smoke-gen-visual-math-part1.json').read_bytes());proof=old['cases'][0]['gen_visual_lowering'];real=provenance.sha
  def checked(path):
   if path==builder.ROOT/'host/export/gen_visual.mjs':raise AssertionError('Historical proof must resolve its frozen source')
   return real(path)
  with patch.object(provenance,'sha',side_effect=checked):self.assertNotEqual(provenance.resolve_lowerer(proof),HERE/'qualified_lowerer.mjs')
 def test_published_full_streams_and_rejections_bind_to_exact_sources(self):
  import build_gen_visual_flow_report as report
  for i in(1,2,3):
   source=f'evidence/xiao-smoke-gen-visual-flow-part{i}.json';data=json.loads((builder.ROOT/source).read_bytes())
   for j,c in enumerate(data['cases']):self.assertEqual(publisher.checked_short_smoke(report.record(),dict(source=source,selector=f'/cases/{j}'),data)['status'],c['status'])
   for j,c in enumerate(data['compile_failures']):
    item=dict(source=source,selector=f'/compile_failures/{j}');publisher.checked_visual_flow_rejection(report.record(),item,data)
    for key,value in(('source_sha256','0'*64),('status','pass'),('samples_checked',10240)):
     bad=copy.deepcopy(data);bad['compile_failures'][j][key]=value
     with self.assertRaises(ValueError):publisher.checked_visual_flow_rejection(report.record(),item,bad)
   for key,value in(('observed_outlet',9),('absolute_tolerance',.001),('expected_stream_sha256','0'*64),('right_output_sha256','0'*64),('expected_block_count',1)):
    bad=copy.deepcopy(data);bad['cases'][0][key]=value
    with self.assertRaises(ValueError):publisher.checked_short_smoke(report.record(),dict(source=source,selector='/cases/0'),bad)
 def test_mtof_resource_tier_and_wrong_snapshot_cannot_be_relabelled(self):
  import build_gen_visual_flow_report as report
  source='evidence/xiao-smoke-gen-visual-flow-part3.json';data=json.loads((builder.ROOT/source).read_bytes());j=next(i for i,c in enumerate(data['cases'])if c['id']=='visual-mtof');c=data['cases'][j]
  self.assertEqual(c['arena_capacity'],1048576);self.assertGreater(c['arena_high_water'],4096)
  for mutate in(lambda d:d['cases'][j].update(arena_capacity=4096),lambda d:d['cases'][j]['gen_visual_lowering'].update(adapter_sha256=provenance.QUALIFIED_LOWERERS['tests/fixtures/smoke/gen-visual-math/qualified_lowerer.mjs'])):
   bad=copy.deepcopy(data);mutate(bad)
   with self.assertRaises(ValueError):publisher.checked_short_smoke(report.record(),dict(source=source,selector=f'/cases/{j}'),bad)
 def test_report_preserves_all42_outcomes_and_separate_operator_statuses(self):
  import build_gen_visual_flow_report as report
  d=json.loads(report.products()['evidence/gen-visual-flow-status.json']);self.assertEqual(len(d['cases']),42);self.assertEqual(len(d['objects']),33)
  self.assertEqual(d['summary']['passed'],39);self.assertEqual(d['summary']['outside_screen'],1);self.assertEqual(d['summary']['target_compile_failures'],2);self.assertEqual(d['summary']['cpu_review'],2)
  objects={o['name']:o for o in d['objects']};self.assertEqual(objects['ftom']['status'],'partial');self.assertEqual(objects['mod']['status'],'unverified');self.assertEqual(objects['%']['status'],'unverified')
  self.assertTrue(all(c['status']=='pass'for c in d['cases']if c['name']=='counter'))
  self.assertTrue(all(c['median_us']is None and c['samples_checked']==0 and not c['finalization_checked']for c in d['cases']if c['status']=='compile_failed'))
  self.assertTrue(all(c['cpu_time_saved_percent']is None for c in d['cases']))
if __name__=='__main__':unittest.main()
