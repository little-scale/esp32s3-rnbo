# SPDX-License-Identifier: MIT
import importlib.util,json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'tests/fixtures/smoke/rnbo-codebox-stateful'
spec=importlib.util.spec_from_file_location('codebox_stateful_ref',SOURCE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class CodeboxStatefulReferenceTests(unittest.TestCase):
 def test_continuous20callback_shapes_limits_and_state_epoch(self):
  self.assertEqual(r.PREPARE_ZERO_WARM_BLOCKS,0);self.assertEqual((r.MANUAL_WARM_CALLS,r.TIMED_CALLS),(4,16))
  for model in r.MODELS:
   blocks=r.reference_blocks(model,r.case_input_words(model));self.assertEqual(len(blocks),20);self.assertTrue(all(len(b)==512 for b in blocks));self.assertEqual(blocks[0],r.reference_words(model,r.case_input_words(model)));self.assertEqual(r.ABSOLUTE_TOLERANCES[model],2e-6 if model in(504,505)else 0)
 def test_history_change_latch_and_samplehold_cross_vector_boundary(self):
  for m,pair in((500,(.75,1)),(501,(-1,-1)),(502,(.75,1)),(503,(.125,1))):
   blocks=r.reference_blocks(m,r.case_input_words(m));self.assertEqual(blocks[1][:2],tuple(r.word(x)for x in pair));self.assertNotEqual(blocks[1],blocks[0])
  history=r.reference_blocks(500,r.input_words());self.assertEqual(history[0][:2],(0,0));self.assertEqual(history[0][2:4],r.input_words()[:2])
 def test_initial_and_causal_recurrence_equations(self):
  pair=(r.word(1),r.word(-1))*256
  slide=r.reference_blocks(504,pair,1)[0];self.assertEqual(slide[:2],(r.word(.5),r.word(-.5)))
  dc=r.reference_blocks(505,pair,1)[0];self.assertEqual(dc[:2],(r.word(1),r.word(-1)));self.assertEqual(dc[2:4],(r.word(.5),r.word(-.75)))
  slopes=r.reference_blocks(508,pair,1)[0];self.assertEqual(slopes[:2],(r.word(.25),r.word(-.25)))
  accum=r.reference_blocks(506,pair,2);self.assertEqual(accum[0][:2],(r.word(1/1024),r.word(-1/1024)));self.assertEqual(accum[1][:2],(r.word(257/1024),r.word(-257/1024)))
 def test_counter_period_and_downsample_phase_not_reset_each_block(self):
  inputs=r.case_input_words(507);self.assertEqual(set(inputs),{r.word(1)})
  blocks=r.reference_blocks(507,inputs);self.assertEqual(blocks[0][:2],(r.word(1),r.word(1)));self.assertEqual(blocks[1][:2],(r.word(257%7),r.word(257%5)))
  down=r.reference_blocks(509,r.input_words());self.assertEqual(down[0][:6],(0,0,0,0,0,0));self.assertEqual(down[1][:2],(r.word(.75),r.word(1)))
  self.assertIn('declared',r.REFERENCE_POLICIES[507]);self.assertIn('declared',r.REFERENCE_POLICIES[509])
 def test_zero_cross_initial_policy_and_completed_report_window(self):
  blocks=r.reference_blocks(510,r.case_input_words(510));self.assertEqual(blocks[0][:2],(0,0));self.assertEqual(blocks[1][:2],(r.word(1),r.word(1)))
  counts=r.reference_blocks(511,r.case_input_words(511));self.assertEqual(counts[0][:8],(0,)*8);self.assertNotEqual(counts[1],counts[0]);self.assertIn('declared',r.REFERENCE_POLICIES[511])
 def test13_original_source_forms_and_api_paths_match(self):
  cases=json.loads((SOURCE/'catalog.json').read_bytes())['cases'];self.assertEqual(len(cases),13);self.assertEqual(len({x['exact_name']for x in cases}),12)
  for row in cases:
   p=json.loads((SOURCE/row['patch']).read_bytes())['patcher'];box=next(b['box']for b in p['boxes']if b['box']['text']=='codebox~');self.assertEqual(box['rnbo_extra_attributes']['code'],(SOURCE/row['codebox']).read_text());self.assertEqual(row['maximum_absolute_error'],r.ABSOLUTE_TOLERANCES[row['model']])
 def test_bad_models_shapes_nonfinite_and_lengths_reject(self):
  for m,x in((True,r.input_words()),(499,r.input_words()),(500,()),(500,(True,0)*256),(500,(0x7f800000,0)*256),(500,(r.word(2),0)*256),(507,r.input_words())):
   with self.assertRaises(ValueError):r.reference_blocks(m,x)
  for count in(True,0,21,.5):
   with self.assertRaises(ValueError):r.reference_blocks(500,r.input_words(),count)
  for frames in(True,1,255,257):
   with self.assertRaises(ValueError):r.input_words(frames)
if __name__=='__main__':unittest.main()
