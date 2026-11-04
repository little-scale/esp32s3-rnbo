# SPDX-License-Identifier: MIT
import importlib.util,json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'tests/fixtures/smoke/rnbo-codebox-filters'
spec=importlib.util.spec_from_file_location('codebox_filters_ref',SOURCE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class CodeboxFiltersReferenceTests(unittest.TestCase):
 def test_twenty_continuous_finite_streams_and_fixed_error_limits(self):
  self.assertEqual(r.PREPARE_ZERO_WARM_BLOCKS,0)
  for m in r.MODELS:
   blocks=r.reference_blocks(m,r.case_input_words(m));self.assertEqual(len(blocks),20);self.assertTrue(all(len(b)==512 for b in blocks));self.assertTrue(all(w&0x7f800000!=0x7f800000 for b in blocks for w in b));self.assertEqual(r.ABSOLUTE_TOLERANCES[m],0 if m in(600,610,611)else 2e-6)
 def test_exact_delay_and_declared_millisecond_sample_lengths(self):
  for m in(600,601,602):
   blocks=r.reference_blocks(m,r.case_input_words(m));self.assertTrue(all(b[1::2]==r.case_input_words(m)[1::2]for b in blocks));self.assertNotEqual(blocks[0],blocks[1])
  x=(r.word(1),0)*256;delay=r.reference_blocks(600,x,1)[0];self.assertEqual(delay[:6],(0,0,0,0,r.word(1),0))
  for ms,samples in((.045351473922902494,2),(.06802721088435375,3)):
   self.assertEqual(r.value(r.word(r.value(r.word(ms))*44100*.001)),samples)
 def test_comb_allpass_and_biquad_independent_impulse_equations(self):
  x=(r.word(1),0)+(0,0)*255
  comb=r.reference_blocks(601,x,1)[0][::2];self.assertEqual(comb[:3],(r.word(.5),0,r.word(.625)))
  allpass=r.reference_blocks(602,x,1)[0][::2];self.assertEqual(allpass[:4],(r.word(-.5),0,0,r.word(.75)))
  biquad=r.reference_blocks(603,x,1)[0][::2];self.assertEqual(biquad[:3],tuple(r.word(v)for v in(.5,.375,.15625)))
 def test_window_truth_uses_available_samples_and_exact_fsum_not_running_sum(self):
  x=(r.word(1),r.word(-1))+(0,0)*255
  for m in(606,607):
   out=r.reference_blocks(m,x,1)[0];self.assertEqual(out[0],r.word(1));self.assertEqual(out[2],r.word(.5));self.assertEqual(out[4],r.word(1/3));self.assertEqual(out[16],0)
  rms=r.reference_blocks(608,x,1)[0];self.assertEqual(rms[0],r.word(1));self.assertEqual(rms[2],r.word((.5)**.5))
 def test_ramp_trigger_hysteresis_and_boundary_state_witnesses(self):
  x=(r.word(1),r.word(-1))*256;ramp=r.reference_blocks(609,x,1)[0];self.assertEqual(ramp[:4],(r.word(.25),r.word(-.25),r.word(.5),r.word(-.5)))
  gates=r.reference_blocks(610,r.case_input_words(610));self.assertEqual(gates[0][:2],(r.word(1),r.word(1)));self.assertEqual(gates[1][:2],(0,0))
  thresholds=r.reference_blocks(611,r.input_words());self.assertEqual(thresholds[0][:2],(0,0));self.assertEqual(thresholds[1][:2],(r.word(1),r.word(1)))
  edge=r.reference_blocks(611,(r.word(-.25),r.word(.25))*256,1)[0];self.assertEqual(edge[:2],(0,r.word(1)))
 def test_original_api_bodies_and_all_tolerances_match_catalog(self):
  cases=json.loads((SOURCE/'catalog.json').read_bytes())['cases'];self.assertEqual(len(cases),12)
  for row in cases:
   p=json.loads((SOURCE/row['patch']).read_bytes())['patcher'];b=next(x['box']for x in p['boxes']if x['box']['text']=='codebox~');self.assertEqual(b['rnbo_extra_attributes']['code'],(SOURCE/row['codebox']).read_text());self.assertEqual(row['maximum_absolute_error'],r.ABSOLUTE_TOLERANCES[row['model']])
   if row['model']<603:self.assertNotIn('strict_zero_sign_channels',row)
 def test_invalid_models_domains_and_callback_lengths_fail_closed(self):
  for m,x in((True,r.input_words()),(599,r.input_words()),(600,()),(600,(0x7fc00000,0)*256),(603,(r.word(2),0)*256)):
   with self.assertRaises(ValueError):r.reference_blocks(m,x)
  for count in(True,0,21,.5):
   with self.assertRaises(ValueError):r.reference_blocks(600,r.input_words(),count)
if __name__=='__main__':unittest.main()
