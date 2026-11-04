# SPDX-License-Identifier: MIT
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'tests/fixtures/smoke/rnbo-codebox-numeric'
spec=importlib.util.spec_from_file_location('smoke_codebox_numeric_ref',SOURCE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class CodeboxNumericReferenceTests(unittest.TestCase):
 def pair(self,m,a,b):return r.reference_words(m,(r.word(a),r.word(b))*256)[:2]
 def test_all_declared_domains_finite_outputs_and_fixed_limits(self):
  for model in r.MODELS:
   inputs=r.case_input_words(model);outputs=r.reference_words(model,inputs)
   self.assertEqual(len(inputs),512);self.assertEqual(len(outputs),512)
   self.assertTrue(all(w&0x7f800000!=0x7f800000 for w in outputs))
   self.assertEqual(r.ABSOLUTE_TOLERANCES[model],0 if model<312 else 2e-6)
   if model>=312:self.assertTrue(all(abs(r.value(w))<8 for w in outputs))
 def test_nearest_away_and_signed_fraction_are_independent_policies(self):
  self.assertEqual(self.pair(303,.5,-.5),(r.word(1),r.word(-1)))
  self.assertEqual(self.pair(303,r.value(0x3effffff),r.value(0xbeffffff)),(0,0x80000000))
  self.assertEqual(self.pair(304,-1.75,1.75),(r.word(-.75),r.word(.75)))
  self.assertEqual(self.pair(311,-1.75,1.75),(r.word(-1),r.word(1)))
 def test_subnormal_definition_zero_and_finite_nan_scope(self):
  tiny=r.value(1);negative=r.value(0x80000001)
  self.assertEqual(self.pair(309,tiny,negative),(r.word(1),r.word(1)))
  self.assertEqual(self.pair(310,tiny,negative),(0,0))
  self.assertEqual(self.pair(309,r.value(0x00800000),-0.),(0,0))
  self.assertEqual(self.pair(308,negative,-0.),(0x80000001,0x80000000))
  self.assertEqual(self.pair(307,tiny,-4.),(0,0))
  self.assertEqual(self.pair(306,tiny,-0.),(r.word(1),0))
 def test_binary_operand_reversal_and_math_landmarks(self):
  self.assertEqual(self.pair(321,2.,.5),(r.word(2**.5),r.word(.25)))
  self.assertEqual(self.pair(329,1.,-1.),(r.word(3*3.141592653589793/4),r.word(-3.141592653589793/4)))
  self.assertEqual(self.pair(335,3.,4.),(r.word(5),r.word(5)))
  self.assertEqual(self.pair(312,4.,0.),(r.word(2),0))
  self.assertEqual(self.pair(317,1.,1.),(0,0))
  self.assertEqual(self.pair(314,0.,0.),(r.word(1),r.word(1)))
 def test_fortythree_original_embedded_sources_are_bound(self):
  rows=json.loads((SOURCE/'catalog.json').read_bytes())['cases'];self.assertEqual(len(rows),43)
  self.assertEqual(len({x['exact_name']for x in rows}),43)
  for row in rows:
   patch=json.loads((SOURCE/row['patch']).read_bytes())['patcher'];boxes=[x['box']for x in patch['boxes']if x['box']['text']=='codebox~']
   self.assertEqual(len(patch['boxes']),5);self.assertEqual(len(boxes),1)
   self.assertEqual(boxes[0]['rnbo_extra_attributes']['code'],(SOURCE/row['codebox']).read_text())
   self.assertEqual(row['surface'],'codebox');self.assertEqual(row['maximum_absolute_error'],r.ABSOLUTE_TOLERANCES[row['model']])
 def test_invalid_or_unsafe_domains_do_not_gain_expectations(self):
  for m,inputs in((True,r.input_words()),(299,r.input_words()),(300,()),(300,(0x7f800000,0)*256),(300,(True,0)*256),(312,(r.word(-1),0)*256),(317,(0,r.word(1))*256),(333,(0,r.word(1))*256),(334,(r.word(1),0)*256),(321,(r.word(-1),r.word(1))*256),(329,(0,0)*256)):
   with self.assertRaises(ValueError):r.reference_words(m,inputs)
  for count in(True,0,255,257):
   with self.assertRaises(ValueError):r.input_words(count)
if __name__=='__main__':unittest.main()
