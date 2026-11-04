# SPDX-License-Identifier: MIT
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tests/fixtures/smoke/rnbo-codebox'
spec=importlib.util.spec_from_file_location('smoke_rnbo_codebox_reference',SOURCE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class CodeboxReferenceTests(unittest.TestCase):
    def inputs(self,a,b):return(r.word(a),r.word(b))*256
    def pair(self,m,a,b):return r.reference_words(m,self.inputs(a,b))[:2]
    def test_cartesian_domains_and_model_dimensions(self):
        words=r.input_words();self.assertEqual(len(set(zip(words[::2],words[1::2]))),256)
        self.assertTrue({0,0x80000000}.issubset(words))
        for m in r.MODELS:
            x=r.case_input_words(m);self.assertEqual(len(r.reference_words(m,x)),512)
            self.assertEqual(r.ABSOLUTE_TOLERANCES[m],0)
            if m in(227,228):self.assertTrue(all(r.value(w)!=0 for w in x))
    def test_exact_arithmetic_and_operand_reversal(self):
        expect={220:(1.5,.5),221:(2.,2.),222:(-1.5,.5),223:(1.5,-.5),224:(1.,1.),225:(2.,-2.),226:(-.75,-.75),227:(-3.,-1/3),228:(0.,-.5),229:(-.5,-.5),230:(1.5,1.5)}
        for m,pair in expect.items():self.assertEqual(self.pair(m,1.5,-.5),tuple(r.word(x)for x in pair))
    def test_relations_equality_and_truth_are_not_cpp_generated_models(self):
        for m,pair in{231:(0,0),232:(1,1),233:(0,1),234:(0,1),235:(1,0),236:(1,0)}.items():
            self.assertEqual(self.pair(m,-.5,.25),tuple(r.word(x)for x in pair))
        for m,pair in{237:(0,0),238:(1,1),239:(1,1),240:(0,1)}.items():
            self.assertEqual(self.pair(m,-1.,0.),tuple(r.word(x)for x in pair))
        self.assertEqual(self.pair(231,-0.,0.),(r.word(1.),r.word(1.)))
    def test_raw_unary_zero_sign_observations(self):
        self.assertEqual(self.pair(223,-0.,0.),(0x80000000,0))
        self.assertEqual(self.pair(222,-0.,0.),(0,0x80000000))
        self.assertEqual(self.pair(220,-0.,0.),(0,0))
    def test_catalog_embedded_original_code_and_syntax_are_exact(self):
        rows=json.loads((SOURCE/'catalog.json').read_bytes())['cases'];self.assertEqual(len(rows),45)
        self.assertEqual(len({x['exact_name']for x in rows}),45)
        for row in rows:
            p=json.loads((SOURCE/row['patch']).read_bytes())['patcher']
            codeboxes=[b['box']for b in p['boxes']if b['box']['text']=='codebox~']
            self.assertEqual(len(p['boxes']),5);self.assertEqual(len(codeboxes),1)
            self.assertEqual(codeboxes[0]['rnbo_extra_attributes']['code'],(SOURCE/row['codebox']).read_text())
            self.assertEqual(row['surface'],'codebox');self.assertIn(row['model'],r.MODELS)
            self.assertEqual(row['maximum_absolute_error'],0)
    def test_malformed_inputs_and_invalid_divisor_reject(self):
        for m,x in((True,r.input_words()),(219,r.input_words()),(220,()),(220,(0,)),(220,(0x7fc00000,0)*256),(220,(True,0)*256),(220,self.inputs(9,0)),(227,self.inputs(0,1)),(228,self.inputs(1,0))):
            with self.assertRaises(ValueError):r.reference_words(m,x)
        for f in(True,0,255,257):
            with self.assertRaises(ValueError):r.input_words(f)

if __name__=='__main__':unittest.main()
