# SPDX-License-Identifier: MIT
"""Independent sample-state references and visual-source admission mutations."""
import copy,hashlib,importlib.util,json,struct,tempfile,unittest
from pathlib import Path
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import build_object_status as publisher
HERE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/gen-visual-core'
spec=importlib.util.spec_from_file_location('visual_reference',HERE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class GenVisualTests(unittest.TestCase):
 def test_shapes_finite_domains_and_division(self):
  for m,n in r.MODEL_NAMES.items():
   inputs=r.case_input_words(m);blocks=r.reference_blocks(m,inputs)
   self.assertEqual(len(blocks),20);self.assertTrue(all(len(b)==512 for b in blocks))
   self.assertTrue(all((w&0x7f800000)!=0x7f800000 for b in blocks for w in b))
   if n=='divide':self.assertTrue(all(r.value(w)>0 for w in inputs[1::2]))
  for m in(True,2299,2400):
   with self.assertRaises(ValueError):r.case_input_words(m)
  with self.assertRaises(ValueError):r.reference_blocks(2300,(0,)*512)
 def test_history_initials_delay_chain_fanout_and_rotations(self):
  out=lambda name:[tuple(r.value(w)for w in b[i:i+2])for b in r.reference_blocks(2300+r.NAMES.index(name),r.case_input_words(2300+r.NAMES.index(name)))for i in range(0,512,2)]
  self.assertEqual([x[0]for x in out('one-sample-history')[:4]],[.25,0,.25,.25])
  self.assertEqual([x[0]for x in out('two-sample-history')[:4]],[.5,.25,0,.25])
  self.assertEqual(out('two-state-swap')[:4],[(.25,-.5),(-.5,.25),(.25,-.5),(-.5,.25)])
  self.assertEqual(out('three-state-rotation')[:4],[(1.,2.),(2.,4.),(4.,1.),(1.,2.)])
  self.assertTrue(all(a==.25 for a,b in out('unconnected-history')))
  self.assertEqual(out('history-read-twice')[0],(.5,-.25))
 def test_finite_convolutions_match_independent_recurrences(self):
  for name in('feedback-half','cross-feedback'):
   m=2300+r.NAMES.index(name);inputs=r.case_input_words(m);blocks=r.reference_blocks(m,inputs);old=(.25,-.5)if name=='cross-feedback'else(0.,0.)
   for n in range(5120):
    a,b=(r.value(w)for w in inputs[(n%256)*2:(n%256)*2+2]);actual=tuple(r.value(w)for w in blocks[n//256][(n%256)*2:(n%256)*2+2])
    expected=old if name=='cross-feedback'else(a+.5*old[0],b)
    for x,y in zip(actual,expected):self.assertLessEqual(abs(x-y),2e-7)
    old=(a+.5*old[1],b+.25*old[0])if name=='cross-feedback'else(expected[0],0.)
 def test_catalog_sources_are_embedded_graphs_without_authored_expr(self):
  cat=json.loads((HERE/'catalog.json').read_bytes());builder.visual_gen_catalog(cat);self.assertEqual(len(cat['cases']),21)
  self.assertEqual(builder.sha(HERE/'reference.py'),builder.VISUAL_GEN_REFERENCE_SHA)
  for row in cat['cases']:
   raw=(HERE/row['patch']).read_bytes();p=json.loads(raw)['patcher'];gen=next(b['box']for b in p['boxes']if b['box'].get('text')=='gen~')
   self.assertNotIn('expr',gen['rnbo_extra_attributes']);self.assertEqual(hashlib.sha256(raw).hexdigest(),row['patch_sha256'])
   self.assertEqual(hashlib.sha256(builder.canonical(gen['genpatcher'])).hexdigest(),row['genpatcher_sha256'])
  bad=copy.deepcopy(cat);bad['cases'][0]['model']=2301
  with self.assertRaises(ValueError):builder.visual_gen_catalog(bad)
 def test_bridge_and_collector_reject_changed_source_lowering_and_state(self):
  cat=json.loads((HERE/'catalog.json').read_bytes());cases=[]
  # Reconstruct the actual compiler bridge, then freeze it in an independent plan.
  import subprocess
  for row in cat['cases']:
   source=json.loads((HERE/row['patch']).read_bytes())['patcher'];gen=next(b['box']for b in source['boxes']if b['box'].get('text')=='gen~')
   code="import fs from 'node:fs';import {lowerVisualGen} from './host/export/gen_visual.mjs';process.stdout.write(JSON.stringify(lowerVisualGen(JSON.parse(fs.readFileSync(0,'utf8')))));"
   v=json.loads(subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(gen['genpatcher']),text=True,capture_output=True,cwd=builder.ROOT,check=True).stdout)
   proof=dict(box_id='gen',policy=v['policy'],nodes=v['nodes'],edges=v['edges'],histories=v['history_count'],operators=v['operators'],source_graph_sha256=hashlib.sha256(json.dumps(gen['genpatcher'],separators=(',',':')).encode()).hexdigest(),lowered_genexpr_sha256=hashlib.sha256(v['expression'].encode()).hexdigest(),adapter_sha256=builder.sha(builder.ROOT/'host/export/gen_visual.mjs'))
   with tempfile.TemporaryDirectory()as d:
    p=Path(d);raw=(HERE/row['patch']).read_bytes();(p/'source.rnbopat').write_bytes(raw);(p/'generator.json').write_text(json.dumps(dict(visual_gen=[proof],gen_visual_adapter_sha256=proof['adapter_sha256'])))
    self.assertEqual(builder.visual_gen_bridge(p,raw,row),dict(gen_visual_lowering=proof,genpatcher_sha256=row['genpatcher_sha256']))
    meta=json.loads((p/'generator.json').read_bytes());meta['visual_gen'][0]['lowered_genexpr_sha256']='0'*64;(p/'generator.json').write_text(json.dumps(meta))
    with self.assertRaises(ValueError):builder.visual_gen_bridge(p,raw,row)
   model=row['model'];inputs=r.case_input_words(model);blocks=r.reference_blocks(model,inputs)
   cases.append(dict(**row,source_sha256=row['patch_sha256'],absolute_tolerance=builder.float32(row['maximum_absolute_error']),input_words=list(inputs),expected=list(blocks[0]),expected_blocks=[list(b)for b in blocks],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest(),gen_visual_lowering=proof))
  plan=dict(catalog_sha256=builder.VISUAL_GEN_CATALOG_SHA,reference_source_sha256=builder.VISUAL_GEN_REFERENCE_SHA,surface='patcher',prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,cases=cases)
  collector.visual_gen_plan(plan)
  for mutate in(lambda p:p['cases'][0].update(source_sha256='0'*64),lambda p:p['cases'][0]['gen_visual_lowering'].update(adapter_sha256='0'*64),lambda p:p['cases'][0]['expected_blocks'][1].__setitem__(0,1),lambda p:p.update(prepare_zero_warm_blocks=4)):
   bad=copy.deepcopy(plan);mutate(bad)
   with self.assertRaises(ValueError):collector.visual_gen_plan(bad)
 def test_publication_requires_exact_visual_source_and_current_helper(self):
  data=json.loads((builder.ROOT/'evidence/xiao-smoke-gen-visual-core.json').read_bytes());record=dict(id='patcher:gen~',spelling='gen~',surface='patcher')
  item=lambda i:dict(selector='/cases/'+str(i),source='evidence/xiao-smoke-gen-visual-core.json')
  for i,case in enumerate(data['cases']):
   observation=publisher.checked_short_smoke(record,item(i),data);self.assertEqual(observation['status'],'pass');self.assertEqual(observation['expected_block_count'],20)
  for mutate in(lambda d:d['cases'][0].update(genpatcher_sha256='0'*64),lambda d:d['cases'][0].update(absolute_tolerance=.001),lambda d:d['cases'][0]['gen_visual_lowering'].update(adapter_sha256='0'*64),lambda d:d['cases'][0].update(expected_block_count=1)):
   bad=copy.deepcopy(data);mutate(bad)
   with self.assertRaises(ValueError):publisher.checked_short_smoke(record,item(0),bad)
if __name__=='__main__':unittest.main()
