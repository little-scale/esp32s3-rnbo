# SPDX-License-Identifier: MIT
"""Exact alias identities, unit contracts, clock scope and lossless block pools."""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
BASE=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-codebox-context-aliases'
spec=importlib.util.spec_from_file_location('context_alias_reference',BASE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class ContextAliasReferenceTests(unittest.TestCase):
 def test_published_outcomes_preserve_clock_failures_and_separate_auxiliary_forms(self):
  root=BASE.parents[3]
  results=[json.loads((root/f'evidence/xiao-smoke-rnbo-codebox-context-aliases-part{i}.json').read_text())for i in(1,2)]
  cases=[v for d in results for v in d['cases']]
  self.assertEqual(len(cases),43);self.assertEqual(sum(v['samples_checked']for v in cases),440320)
  self.assertEqual({v['id']for v in cases if v['status']=='output_mismatch'},{'currenttime','sampleoffset','currentsampletime'})
  self.assertEqual(sum(v['numeric_mismatches']for v in cases),15300)
  self.assertEqual(sum(v['within_tolerance_differences']for v in cases),16005)
  self.assertEqual(sum(v['zero_sign_differences']for v in cases),7680)
  self.assertEqual(sum(len(d.get('admission_failures',[]))for d in results),8)
  self.assertEqual(sum(len(d['cpu_review_backlog'])for d in results),13)
  for v in cases:
   self.assertEqual(v['absolute_tolerance'],struct.unpack('<f',struct.pack('<f',r.ABSOLUTE_TOLERANCES[v['model']]))[0])
  native=json.loads((root/'evidence/rnbo-codebox-context-aliases-native.json').read_text())
  self.assertFalse(native['primary_references_changed_after_output']);self.assertTrue(native['stopped_harness_run']['rerun_plan_unchanged'])
  self.assertEqual(native['clock_diagnostic_script_sha256'],hashlib.sha256((BASE/'clock_diagnostic.py').read_bytes()).hexdigest())
  self.assertEqual(native['source_catalog_sha256'],hashlib.sha256((BASE/'catalog.json').read_bytes()).hexdigest())
  for d in native['clock_diagnostic']:
   self.assertEqual(d['callback_held_outside_original_limit'],0)
   self.assertEqual(d['helper_sha256'],hashlib.sha256((BASE/'clock_capture.cpp').read_bytes()).hexdigest())
  coverage=json.loads((root/'site/data/coverage.json').read_text());rows={v['id']:v for v in coverage['objects']}
  self.assertFalse(any('compound-add-state'in v or'compound-multiply-state'in v for v in rows))
  self.assertEqual(len(rows['codebox:^^']['qualification']),2)
  for identity in('+=','*='):
   self.assertFalse(rows['codebox:'+identity]['board_evidence'])
   self.assertEqual(rows['codebox:'+identity]['working_state'],'unverified')

 def test_pass_predicates_both_orders_and_reverse_math(self):
  for model in range(1900,1906):
   inputs=r.case_input_words(model);b=r.reference_blocks(model,inputs)[0];p=r.PREDICATES[model-1900]
   for i in range(256):
    x,y=map(r.value,inputs[2*i:2*i+2]);self.assertEqual(r.value(b[2*i]),x if p(x,y)else 0);self.assertEqual(r.value(b[2*i+1]),y if p(y,x)else 0)
  inputs=r.case_input_words(1906);b=r.reference_blocks(1906,inputs)[0]
  self.assertEqual(r.value(b[2*15]),r.value(inputs[31])-r.value(inputs[30]))
  inputs=r.case_input_words(1907);b=r.reference_blocks(1907,inputs)[0]
  for i in range(256):self.assertEqual(b[2*i],r.word(Fraction(r.value(inputs[2*i+1]))/Fraction(r.value(inputs[2*i]))))
 def test_default_tempo_unit_identities_and_small_outputs_cannot_accept_zero(self):
  for model,n in r.MODEL_NAMES.items():
   if n not in r.CONVERSIONS:continue
   inputs=r.case_input_words(model);b=r.reference_blocks(model,inputs)[0];nonzero=[abs(r.value(w))for w in b]
   self.assertGreater(min(nonzero),100*r.ABSOLUTE_TOLERANCES[model],n)
  self.assertEqual(r.convert('beatstoms',1),500);self.assertEqual(r.convert('beatstosamps',1),22050);self.assertEqual(r.convert('beatstoticks',1),480)
  self.assertEqual(r.convert('tickstosamps',480),22050);self.assertEqual(r.convert('tickstosamples',480),22050)
  for x in(0.125,0.5,1,2):
   self.assertEqual(r.convert('tickstobeats',r.convert('beatstoticks',x)),Fraction(x))
   self.assertEqual(r.convert('hztobeats',r.convert('beatstohz',x)),Fraction(x))
 def test_per_sample_clock_expectations_remain_separate_from_callback_origin(self):
  models={n:m for m,n in r.MODEL_NAMES.items()}
  for n in('sampleoffset','samplecount','currentsampletime','currenttime'):
   b=r.reference_blocks(models[n],r.case_input_words(models[n]))
   for age in(0,1,255,256,257,5119):
    expected=age%256 if n=='sampleoffset'else age//256*256 if n=='samplecount'else age if n=='currentsampletime'else age*1000/44100
    self.assertEqual(b[age//256][2*(age%256)],r.word(expected))
 def test_state_alias_and_compound_language_references_cross_blocks(self):
  for model in(1912,1916):
   v=r.case_input_words(model);b=r.reference_blocks(model,v);state=[0,0]
   for age in range(5120):
    for ch in(0,1):state[ch]+=r.value(v[2*(age%256)+ch])/64;self.assertEqual(b[age//256][2*(age%256)+ch],r.word(state[ch]))
  for model in(1913,1917):
   v=r.case_input_words(model);b=r.reference_blocks(model,v);state=[1,1]
   for age in range(5120):
    for ch in(0,1):state[ch]*=r.value(v[2*(age%256)+ch]);self.assertEqual(b[age//256][2*(age%256)+ch],r.word(state[ch]))
  c=json.loads((BASE/'catalog.json').read_text());lexical=[v for v in c['cases']if v['syntax']=='compound-assignment'];self.assertEqual(len(lexical),2)
  self.assertTrue(all(v['registry_lookup'].startswith('language:')for v in lexical))
 def test_whole_catalog_partitions_and_embedded_sources_are_frozen(self):
  parent=json.loads((BASE/'catalog.json').read_text());self.assertEqual(len(parent['cases']),51);observed=[]
  for i,count in((1,26),(2,25)):
   c=json.loads((BASE/f'part{i}.json').read_text());builder.context_alias_catalog(c);self.assertEqual(len(c['cases']),count);observed+=c['cases']
   bad=copy.deepcopy(c);bad['cases'][0]['scope']='complete arbitrary semantics'
   with self.assertRaises(builder.ExportError):builder.context_alias_catalog(bad)
  self.assertEqual(observed,parent['cases'])
  for row in parent['cases']:
   raw=(BASE/row['patch']).read_bytes();code=(BASE/row['codebox']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),row['patch_sha256']);self.assertEqual(hashlib.sha256(code).hexdigest(),row['codebox_sha256'])
   box=next(v['box']for v in json.loads(raw)['patcher']['boxes']if v['box']['text']=='codebox~');self.assertEqual(box['rnbo_extra_attributes']['code'].encode(),code)
 def test_unit_tolerance_extension_is_explicit_not_a_global_relaxation(self):
  with self.assertRaises(builder.ExportError):builder.absolute_tolerance(r,1941)
  self.assertEqual(builder.absolute_tolerance(r,1941,ceiling=2e-3),struct.unpack('<f',struct.pack('<f',.002))[0])
  self.assertEqual(builder.absolute_tolerance(r,1944),struct.unpack('<f',struct.pack('<f',1e-10))[0])
 def test_device_ceiling_extension_is_generated_only_for_the_pinned_family(self):
  root=BASE.parents[3]
  row=json.loads((BASE/'part2.json').read_text())['cases'][0];inputs=r.case_input_words(row['model']);b=r.reference_blocks(row['model'],inputs)
  plan=dict(family=builder.CONTEXT_ALIAS_FAMILY,cases=[dict(row,expected=list(b[0]),expected_blocks=[list(v)for v in b],module_sha256='0'*64,input_words=list(inputs),absolute_tolerance=0)],warmup_blocks=4,timed_blocks=16,prepare_zero_warm_blocks=0)
  header,_=builder.generate_header(plan,r.input_words())
  self.assertIn('#define SMOKE_ABSOLUTE_TOLERANCE_CEILING 0x1.0624dep-9f',header)
  header,_=builder.generate_header(dict(plan,family='rnbo-codebox'),r.input_words())
  self.assertNotIn('#define SMOKE_ABSOLUTE_TOLERANCE_CEILING',header)
  driver=(root/'hardware-smoke/main/smoke.c').read_text()
  self.assertIn('#define SMOKE_ABSOLUTE_TOLERANCE_CEILING .001f',driver)
  self.assertIn('test->absolute_tolerance<=SMOKE_ABSOLUTE_TOLERANCE_CEILING',driver)

 def test_compact_pool_reconstructs_twenty_blocks_and_collector_rejects_fitting(self):
  for index in(1,2):
   c=json.loads((BASE/f'part{index}.json').read_text());cases=[]
   for row in c['cases']:
    inputs=list(r.case_input_words(row['model']));blocks=[list(b)for b in r.reference_blocks(row['model'],inputs)]
    cases.append(dict(row,source_sha256=row['patch_sha256'],codebox_source_sha256=row['codebox_sha256'],input_words=inputs,expected=blocks[0],expected_blocks=blocks,absolute_tolerance=struct.unpack('<f',struct.pack('<f',row['maximum_absolute_error']))[0],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in blocks for w in b))).hexdigest()))
   pool,refs=builder.block_pool(cases)
   for row,indices in zip(cases,refs):row['expected_block_indices']=indices;del row['expected_blocks']
   plan=dict(cases=cases,surface='codebox',warmup_blocks=4,timed_blocks=16,prepare_zero_warm_blocks=0,partition=c['partition'],catalog_sha256=builder.CONTEXT_ALIAS_PARTITIONS[index],reference_source_sha256=builder.CONTEXT_ALIAS_REFERENCE_SHA,expected_stream_policy='Fresh prepared codebox state; twenty continuous256-frame callbacks without resets',expected_block_storage='shared-512-word-pool',expected_reference_unique_blocks=len(pool),expected_block_pool=[list(b)for b in pool])
   collector.context_alias_plan(plan)
   self.assertLess(len(pool),20*len(cases))
   bad=copy.deepcopy(plan);bad['cases'][0]['expected_block_indices'][19]=len(pool)
   with self.assertRaises(ValueError):collector.context_alias_plan(bad)
   bad=copy.deepcopy(plan);bad['expected_block_pool'][0][0]^=1
   with self.assertRaises(ValueError):collector.context_alias_plan(bad)
   with self.assertRaises(ValueError):collector.context_alias_plan(dict(plan,prepare_zero_warm_blocks=True))
   bad=dict(cases[0],absolute_tolerance=1)
   with self.assertRaises(ValueError):collector.context_alias_plan(dict(plan,cases=[bad]+cases[1:]))
if __name__=='__main__':unittest.main()
