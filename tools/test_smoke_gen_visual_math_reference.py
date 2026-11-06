# SPDX-License-Identifier: MIT
"""Independent math landmarks, domain limits, historical proofs and plan gates."""
import copy,hashlib,importlib.util,json,math,struct,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import visual_gen_provenance as provenance
import build_object_status as publisher
import build_gen_visual_math_report as report_builder
HERE=builder.ROOT/'tests/fixtures/smoke/gen-visual-math'
spec=importlib.util.spec_from_file_location('visual_math_reference',HERE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class VisualMathTests(unittest.TestCase):
 def model(self,name):return next(m for m,s in r.MODEL_SPECS.items()if s['name']==name)
 def test_finite_shapes_exact_right_lane_and_nonzero_domains(self):
  self.assertEqual(len(r.MODELS),101)
  for m,s in r.MODEL_SPECS.items():
   inputs=r.case_input_words(m);out=r.reference_words(m,inputs)
   self.assertEqual(len(inputs),512);self.assertEqual(len(out),512);self.assertEqual(out[1::2],inputs[1::2])
   self.assertTrue(all((w&0x7f800000)!=0x7f800000 for w in out))
   if s['operation']in('/','atan2'):self.assertTrue(all(r.value(w)!=0 for w in inputs[1::2]))
   if s['operation']in('log','log2','log10','sqrt','pow'):self.assertTrue(all(r.value(w)>0 for w in inputs[0::2]))
 def test_math_comparisons_and_constant_landmarks(self):
  for name,x,y,wanted in [('add',.5,.25,.75),('sub',.5,.25,.25),('mul',.5,.25,.125),('div',.5,.25,2),('atan2',1,1,math.pi/4),('hypot',3,4,5),('pow',4,.5,2),('ln',1,0,0),('exp2',-2,0,.25),('fract',-.75,0,-.75),('trunc',-1.5,0,-1),('floor',-1.5,0,-2),('ceil',-1.5,0,-1)]:
   self.assertAlmostEqual(r.operation(self.model(name),x,y),wanted,places=14)
  for name in('ltp','<p'):self.assertEqual(r.operation(self.model(name),-2,1),-2)
  for name in('gtp','>p'):self.assertEqual(r.operation(self.model(name),-2,1),0)
  for lower in r.CONSTANTS:
   self.assertEqual(r.operation(self.model(lower),0,0),r.operation(self.model(lower.upper()),2,-1))
  self.assertEqual(r.operation(self.model('constant'),999,999),3.5)
 def test_limits_and_input_rejections_are_predeclared(self):
  for m,s in r.MODEL_SPECS.items():self.assertEqual(r.ABSOLUTE_TOLERANCES[m]==.001,s['operation']in r.APPROXIMATIONS)
  for m in(True,2399,2501):
   with self.assertRaises(ValueError):r.case_input_words(m)
  with self.assertRaises(ValueError):r.reference_words(2400,(0,)*512)
  for n in(True,0,257):
   with self.assertRaises(ValueError):r.input_words(n)
 def test_exact_partitions_casefold_safe_ids_and_original_graphs(self):
  full=json.loads((HERE/'catalog.json').read_bytes());allcases=[]
  for i in range(1,5):
   cat=json.loads((HERE/f'part{i}.json').read_bytes());builder.visual_math_catalog(cat);allcases+=cat['cases']
   bad=copy.deepcopy(cat);bad['cases'][0]['maximum_absolute_error']=.0005
   with self.assertRaises(ValueError):builder.visual_math_catalog(bad)
  self.assertEqual(allcases,full['cases']);self.assertEqual(len({s['id'].casefold()for s in allcases}),101)
  self.assertEqual(builder.sha(HERE/'reference.py'),builder.VISUAL_MATH_REFERENCE_SHA)
  for row in allcases:
   raw=(HERE/row['patch']).read_bytes();g=next(b['box']for b in json.loads(raw)['patcher']['boxes']if b['box'].get('text')=='gen~')
   self.assertNotIn('expr',g['rnbo_extra_attributes']);self.assertEqual(hashlib.sha256(raw).hexdigest(),row['patch_sha256'])
   self.assertEqual(hashlib.sha256(builder.canonical(g['genpatcher'])).hexdigest(),row['genpatcher_sha256'])
 def test_historical_core_resolves_immutable_source_without_production_read(self):
  old=json.loads((builder.ROOT/'evidence/xiao-smoke-gen-visual-core.json').read_bytes());proof=old['cases'][0]['gen_visual_lowering'];real=provenance.sha
  def checked(path):
   if path==builder.ROOT/'archive/importer/gen_visual.mjs':raise AssertionError('Historical proof must not depend on current producer')
   return real(path)
  with patch.object(provenance,'sha',side_effect=checked):self.assertEqual(provenance.resolve_lowerer(proof).name,'qualified_lowerer.mjs')
  with self.assertRaises(ValueError):provenance.resolve_lowerer(dict(adapter_sha256='0'*64))
  with patch.object(provenance,'sha',return_value='0'*64):
   with self.assertRaises(ValueError):provenance.resolve_lowerer(proof)
 def test_collector_rebinds_bridge_vectors_and_declared_limits(self):
  catalog=json.loads((HERE/'catalog.json').read_bytes());graphs=[]
  for row in catalog['cases']:
   p=json.loads((HERE/row['patch']).read_bytes())['patcher'];graphs.append(next(b['box']['genpatcher']for b in p['boxes']if b['box'].get('text')=='gen~'))
  script="import fs from 'node:fs';import {lowerVisualGen} from './archive/importer/gen_visual.mjs';process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(lowerVisualGen)));"
  lowered=json.loads(subprocess.run(['node','--input-type=module','-e',script],input=json.dumps(graphs),text=True,capture_output=True,cwd=builder.ROOT,check=True).stdout)
  byid={}
  for source,g,v in zip(catalog['cases'],graphs,lowered):
   m=source['model'];inputs=r.case_input_words(m);proof=dict(box_id='gen',policy=v['policy'],nodes=v['nodes'],edges=v['edges'],histories=v['history_count'],operators=v['operators'],source_graph_sha256=hashlib.sha256(json.dumps(g,separators=(',',':')).encode()).hexdigest(),lowered_genexpr_sha256=hashlib.sha256(v['expression'].encode()).hexdigest(),adapter_sha256=builder.sha(builder.ROOT/'archive/importer/gen_visual.mjs'))
   byid[source['id']]=dict(**source,source_sha256=source['patch_sha256'],input_words=list(inputs),expected=list(r.reference_words(m,inputs)),absolute_tolerance=builder.float32(source['maximum_absolute_error']),gen_visual_lowering=proof)
  for part in range(1,5):
   cat=json.loads((HERE/f'part{part}.json').read_bytes());plan=dict(catalog_sha256=builder.VISUAL_MATH_PARTITIONS[part],reference_source_sha256=builder.VISUAL_MATH_REFERENCE_SHA,partition=cat['partition'],surface='patcher',prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,cases=[byid[s['id']]for s in cat['cases']])
   collector.visual_math_plan(plan)
   for mutate in(lambda p:p['cases'][0]['expected'].__setitem__(0,1),lambda p:p['cases'][0].update(absolute_tolerance=.0005),lambda p:p['cases'][0].update(visual_operator='wrong'),lambda p:p['cases'][0]['gen_visual_lowering'].update(adapter_sha256='0'*64),lambda p:p.update(prepare_zero_warm_blocks=4)):
    bad=copy.deepcopy(plan);mutate(bad)
    with self.assertRaises(ValueError):collector.visual_math_plan(bad)
 def test_publication_retains_exact_spelling_limits_and_right_observer(self):
  for part in range(1,5):
   source=f'evidence/xiao-smoke-gen-visual-math-part{part}.json';data=json.loads((builder.ROOT/source).read_bytes());record=dict(id='patcher:gen~',spelling='gen~',surface='patcher')
   for i,case in enumerate(data['cases']):
    observation=publisher.checked_short_smoke(record,dict(source=source,selector=f'/cases/{i}'),data);self.assertEqual(observation['status'],case['status']);self.assertIs(observation['right_pilot_bit_exact'],True)
   for mutate in(lambda d:d['cases'][0].update(visual_operator='unknown'),lambda d:d['cases'][0].update(absolute_tolerance=.0005),lambda d:d['cases'][0].update(right_output_sha256='0'*64),lambda d:d['cases'][0]['gen_visual_lowering'].update(adapter_sha256='0'*64),lambda d:d['cases'][0].update(expected_block_count=20)):
    bad=copy.deepcopy(data);mutate(bad)
    with self.assertRaises(ValueError):publisher.checked_short_smoke(record,dict(source=source,selector='/cases/0'),bad)
 def test_operator_report_has_no_alias_inheritance_or_unmeasured_gain(self):
  products=report_builder.products();report=json.loads(products['evidence/gen-visual-operator-status.json']);rows=report['objects']
  self.assertEqual(len(rows),101);self.assertEqual(len({r['name']for r in rows}),101);self.assertEqual(report['summary']['passed'],99);self.assertEqual(report['summary']['outside_screen'],2)
  self.assertTrue(all(row['cpu_time_saved_percent']is None and row['optimisation']=='unassessed'and row['aliases_inherit_status']is False and row['right_pilot_bit_exact']is True for row in rows))
  text=products['docs/gen-visual-math.md'].decode();self.assertIn('&#124;&#124;',text);self.assertIn('&lt;p',text)
  source=builder.ROOT/'evidence/xiao-smoke-gen-visual-math-part1.json';bad=json.loads(source.read_bytes());bad['cases'][0]['visual_operator']='changed';raw=json.dumps(bad).encode();read=Path.read_bytes
  def replaced(path):return raw if path==source else read(path)
  with patch.object(Path,'read_bytes',replaced):
   with self.assertRaises(ValueError):report_builder.products()
if __name__=='__main__':unittest.main()
