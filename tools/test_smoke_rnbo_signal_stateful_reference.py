# SPDX-License-Identifier: MIT
import importlib.util,json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'tests/fixtures/smoke/rnbo-signal-stateful'
spec=importlib.util.spec_from_file_location('signal_stateful_ref',SOURCE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class SignalStatefulReferenceTests(unittest.TestCase):
 def test_all_fifteen_models_carry_state_across_twenty_callbacks(self):
  self.assertEqual(r.PREPARE_ZERO_WARM_BLOCKS,0);self.assertEqual((r.MANUAL_WARM_CALLS,r.TIMED_CALLS),(4,16))
  for m in r.MODELS:
   x=r.case_input_words(m);blocks=r.reference_blocks(m,x);self.assertEqual(len(blocks),20);self.assertTrue(all(len(b)==512 for b in blocks));self.assertTrue(all(w&0x7f800000!=0x7f800000 for b in blocks for w in b));self.assertEqual(blocks[0],r.reference_words(m,x));self.assertNotEqual(blocks[0],blocks[1]);self.assertEqual(r.ABSOLUTE_TOLERANCES[m],2e-6 if m in(703,706,710,711,714)else 0)
 def test_delta_change_latch_and_samplehold_boundary_values(self):
  for m,expected in((712,(-.75,-1)),(701,(-1,-1)),(702,(.75,1)),(713,(.125,1))):
   blocks=r.reference_blocks(m,r.case_input_words(m));self.assertEqual(blocks[1][:2],tuple(r.word(x)for x in expected))
  delta=r.reference_blocks(712,r.input_words());self.assertEqual(delta[0][:2],(0,0));self.assertEqual(delta[0][2:4],(r.word(.25),r.word(1)))
 def test_causal_recurrences_and_accumulator_dyadic_growth(self):
  x=(r.word(1),r.word(-1))*256
  dc=r.reference_blocks(703,x,1)[0];self.assertEqual(dc[:4],(r.word(1),r.word(-1),r.word(.5),r.word(-.75)))
  slide=r.reference_blocks(714,x,1)[0];self.assertEqual(slide[:2],(r.word(.5),r.word(-.5)))
  ramp=r.reference_blocks(706,x,1)[0];self.assertEqual(ramp[:4],(r.word(.25),r.word(-.25),r.word(.5),r.word(-.5)))
  clipped=r.reference_blocks(704,x,1)[0];self.assertEqual(clipped[:2],(r.word(.25),r.word(-.25)))
  small=(r.word(1/1024),r.word(-1/1024))*256;accum=r.reference_blocks(700,small,2);self.assertEqual(accum[0][:2],small[:2]);self.assertEqual(accum[1][:2],(r.word(257/1024),r.word(-257/1024)))
 def test_declared_downsample_and_crossing_windows_are_not_perblock_reset(self):
  down=r.reference_blocks(705,r.input_words());self.assertEqual(down[0][:6],(0,)*6);self.assertEqual(down[1][:2],(r.word(.75),r.word(1)))
  cross=r.reference_blocks(708,r.case_input_words(708));self.assertEqual(cross[0][:2],(0,0));self.assertEqual(cross[1][:2],(r.word(1),r.word(1)))
  count=r.reference_blocks(709,r.case_input_words(709));self.assertEqual(count[0][:8],(0,)*8)
  for m in(705,708,709):self.assertIn('declared',r.REFERENCE_POLICIES[m])
 def test_positive_edges_and_growing_available_average_count(self):
  pulses=r.reference_blocks(707,r.case_input_words(707));self.assertEqual(pulses[0][:2],(r.word(1),r.word(1)));self.assertEqual(pulses[1][:2],(0,0))
  x=(r.word(-1),r.word(1))+(0,0)*255
  absolute=r.reference_blocks(710,x,1)[0];self.assertEqual(absolute[:6],tuple(r.word(v)for v in(1,1,.5,.5,1/3,1/3)));self.assertEqual(absolute[16],0)
  rms=r.reference_blocks(711,x,1)[0];self.assertEqual(rms[:4],tuple(r.word(v)for v in(1,1,.5**.5,.5**.5)))
 def test_original_exact_spellings_routes_and_literal_controls(self):
  cases=json.loads((SOURCE/'catalog.json').read_bytes())['cases'];self.assertEqual(len(cases),15);self.assertEqual(len({c['exact_name']for c in cases}),15)
  for row in cases:
   p=json.loads((SOURCE/row['patch']).read_bytes())['patcher'];boxes={b['box']['id']:b['box']for b in p['boxes']};self.assertEqual(len(boxes),6)
   for side in('left','right'):
    text=row['exact_name']+(' '+row['literal_parameters'][side]if row['literal_parameters'][side]else'');self.assertEqual(boxes['operator-'+side]['text'],text)
   self.assertEqual(row['maximum_absolute_error'],r.ABSOLUTE_TOLERANCES[row['model']]);self.assertEqual(row['surface'],'patcher')
   if row['model']in(702,713):self.assertEqual(len(p['lines']),6)
 def test_invalid_models_domains_and_shape_reject(self):
  for m,x in((True,r.input_words()),(699,r.input_words()),(701,()),(701,(0x7fc00000,0)*256),(701,(True,0)*256),(701,(r.word(2),0)*256),(700,r.input_words())):
   with self.assertRaises(ValueError):r.reference_blocks(m,x)
  for count in(True,0,21,.5):
   with self.assertRaises(ValueError):r.reference_blocks(701,r.input_words(),count)
  for n in(True,1,255,257):
   with self.assertRaises(ValueError):r.input_words(n)
if __name__=='__main__':unittest.main()
