# SPDX-License-Identifier: MIT
import importlib.util,json,math
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'tests/fixtures/smoke/rnbo-codebox-range'
spec=importlib.util.spec_from_file_location('codebox_range_reference',SOURCE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class CodeboxRangeReferenceTests(unittest.TestCase):
 def pair(self,m,a,b):return r.reference_words(m,(r.word(a),r.word(b))*256)[:2]
 def test_all_finite_domains_and_predeclared_limits(self):
  for m in r.MODELS:
   out=r.reference_words(m,r.case_input_words(m));self.assertEqual(len(out),512);self.assertTrue(all(w&0x7f800000!=0x7f800000 for w in out))
  self.assertTrue(all(r.ABSOLUTE_TOLERANCES[m]==1e-3 for m in range(422,428)))
  self.assertEqual(r.ABSOLUTE_TOLERANCES[432],5e-4);self.assertEqual(r.ABSOLUTE_TOLERANCES[433],5e-4)
 def test_exact_range_mapping_and_fractional_interpolation(self):
  self.assertEqual(self.pair(400,-4,4),(r.word(-1),r.word(1)))
  self.assertEqual(self.pair(401,-2,2),(0,0));self.assertEqual(self.pair(402,1,-1),(r.word(-1),r.word(-1)))
  self.assertEqual(self.pair(403,-4,4),(r.word(-8),r.word(8)))
  self.assertEqual(self.pair(404,1,-1),(r.word(.5),r.word(-.5)))
  self.assertEqual(self.pair(405,0,-1),(r.word(.5),0))
  self.assertEqual(self.pair(409,.25,2),(r.word(1),r.word(-1)))
 def test_tuple_axes_and_boolean_route_order(self):
  self.assertEqual(self.pair(407,3,4),(r.word(5),r.word(math.atan2(4,3))))
  self.assertEqual(self.pair(408,2,0),(r.word(2),0))
  for m in(410,411):
   self.assertEqual(self.pair(m,1,.5),(r.word(.5),r.word(-.5)))
   self.assertEqual(self.pair(m,0,.5),(r.word(-.5),r.word(.5)))
  self.assertEqual(self.pair(412,1,2),(0,r.word(1)))
  self.assertEqual(self.pair(415,1,2),(0,r.word(2)))
  self.assertEqual(self.pair(417,1,2),(r.word(1),0))
 def test_reverse_arithmetic_and_practical_midi_unit_conventions(self):
  self.assertEqual(self.pair(419,2,-.5),(r.word(-.25),r.word(-4)))
  self.assertEqual(self.pair(420,2,.5),(r.word(.5),0))
  self.assertEqual(self.pair(421,1,2),(r.word(1),r.word(-1)))
  self.assertEqual(self.pair(432,69,81),(r.word(440),r.word(880)))
  quarter=r.value(r.word(440*2**(.25/12)));self.assertEqual(self.pair(433,440,quarter),(r.word(69),r.word(69)))
  self.assertEqual(self.pair(434,1000,10),(r.word(44100),r.word(441)))
  self.assertEqual(self.pair(435,44100,441),(r.word(1000),r.word(10)))
 def test_47_source_forms_bodies_and_tolerances_remain_distinct(self):
  cases=json.loads((SOURCE/'catalog.json').read_bytes())['cases'];self.assertEqual(len(cases),47)
  self.assertEqual(len({x['id']for x in cases}),47)
  for row in cases:
   p=json.loads((SOURCE/row['patch']).read_bytes())['patcher'];b=next(x['box']for x in p['boxes']if x['box']['text']=='codebox~')
   self.assertEqual(b['rnbo_extra_attributes']['code'],(SOURCE/row['codebox']).read_text());self.assertEqual(row['maximum_absolute_error'],r.ABSOLUTE_TOLERANCES[row['model']])
  for name in('mtof','ftom'):
   a=[x for x in cases if x['exact_name']==name];self.assertEqual({x['syntax']for x in a},{'call','stateful-next'})
 def test_invalid_domains_and_zero_divisors_reject(self):
  for m,inputs in((True,r.input_words()),(399,r.input_words()),(400,()),(400,(0x7fc00000,0)*256),(419,(0,r.word(1))*256),(430,(0,r.word(1))*256),(433,(0,r.word(440))*256),(410,(r.word(2),0)*256),(409,(r.word(2),0)*256)):
   with self.assertRaises(ValueError):r.reference_words(m,inputs)
  for frames in(True,0,255,257):
   with self.assertRaises(ValueError):r.input_words(frames)
if __name__=='__main__':unittest.main()
