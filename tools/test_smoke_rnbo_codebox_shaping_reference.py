# SPDX-License-Identifier: MIT
"""Portable mathematical/source checks for finite scalar RNBO codebox shaping."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1];DIRECTORY=ROOT/'tests/fixtures/smoke/rnbo-codebox-shaping'
spec=importlib.util.spec_from_file_location('codebox_shaping_reference',DIRECTORY/'reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class CodeboxShapingReferenceTests(unittest.TestCase):
    def test_easing_endpoints_reflections_and_primary_non_penner_shapes(self):
        for family in reference.FAMILIES:
            for mode in reference.MODES:
                self.assertAlmostEqual(reference.easing(family,mode,0),0,places=12)
                self.assertAlmostEqual(reference.easing(family,mode,1),1,places=12)
            self.assertAlmostEqual(reference.easing(family,'in_out',.5),.5,places=12)
            for t in(.125,.25,.5,.75,.875):
                self.assertAlmostEqual(reference.easing(family,'out',t),1-reference.easing(family,'in',1-t),places=12)
        self.assertEqual(reference.easing('quadratic','in',.25),.0625)
        self.assertEqual(reference.easing('quadratic','out',.25),.4375)
        self.assertEqual(reference.easing('quadratic','in_out',.25),.125)
        self.assertEqual(reference.easing('exponential','in',.5),.03125)
        self.assertEqual(reference.easing('back','in',.5),-.375)
        self.assertEqual(reference.easing('back','out',.5),1.375)
        self.assertAlmostEqual(reference.easing('elastic','in',.5),-math.sqrt(2)/64,places=12)
        for t in(4/11,8/11,.9,1):self.assertAlmostEqual(reference.bounce_out(t),1,places=12)
        for t,minimum in((6/11,.7),(179/220,.91),(.95,.973)):
            self.assertAlmostEqual(reference.bounce_out(t),minimum,places=12)

    def test_window_and_factor_first_interpolation_anchors(self):
        w=reference.word
        for model,edges in((530,0),(531,.08),(532,0),(533,0)):
            outputs=reference.reference_words(model,(w(0),w(.5)))
            self.assertAlmostEqual(reference.value(outputs[0]),edges,places=7)
            self.assertEqual(outputs[1],w(1))
            self.assertAlmostEqual(reference.value(reference.reference_words(model,(w(1),w(1)))[0]),edges,places=7)
        self.assertEqual(reference.reference_words(534,(w(.25),w(.75))),(w(-.5),w(-.5)))
        self.assertEqual(reference.reference_words(535,(w(0),w(1))),(w(-1),w(-1)))
        self.assertEqual(reference.ABSOLUTE_TOLERANCES[535],1e-3)
        case=next(c for c in json.loads((DIRECTORY/'catalog.json').read_bytes())['cases']if c['model']==535)
        self.assertIn('Taylor cosT8',case['scope']);self.assertIn('no asserted universal accuracy guarantee',case['scope'])

    def test_small_integer_arithmetic_uses_truncating_remainders_and_no_overflow_claim(self):
        w=reference.word
        self.assertEqual(reference.reference_words(536,(w(-8),w(7))),(w(-1),w(-1)))
        self.assertEqual(reference.reference_words(537,(w(-8),w(7))),(w(-56),w(-56)))
        self.assertEqual(reference.reference_words(538,(w(-7),w(3))),(w(-1),w(3)))
        self.assertEqual(reference.reference_words(538,(w(7),w(-3))),(w(1),w(-3)))
        self.assertEqual(reference.reference_words(539,(w(15),w(15))),(w(30),w(30)))
        for model in(534,536,537,538,539):self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],0)

    def test_frozen_vectors_cover_endpoints_and_adjacent_bounce_cut_words(self):
        self.assertEqual(len(reference.MODELS),40);self.assertEqual(len(reference.PHASE_WORDS),32)
        phase=set(reference.PHASE_WORDS);self.assertIn(reference.word(0),phase);self.assertIn(reference.word(1),phase)
        for cut in(4/11,8/11,.9):
            center=reference.word(cut);self.assertTrue({center-1,center,center+1}<=phase)
        for model in reference.MODELS:
            inputs=reference.case_input_words(model);outputs=reference.reference_words(model,inputs)
            self.assertEqual(len(inputs),512);self.assertEqual(len(outputs),512)
            self.assertTrue(all(math.isfinite(reference.value(w))for w in outputs))
            if model<536:
                self.assertEqual(set(inputs[0::2]),phase);self.assertEqual(set(inputs[1::2]),phase)
            if model==538:self.assertTrue(all(reference.value(w)!=0 for w in inputs))

    def test_forty_exact_scalar_calls_have_original_codebox_only_fixtures(self):
        cases=json.loads((DIRECTORY/'catalog.json').read_bytes())['cases'];self.assertEqual(len(cases),40)
        self.assertEqual(len({c['exact_name']for c in cases}),40)
        registry={r['id']:r for r in json.loads((ROOT/'site/data/inventory.json').read_bytes())['spellings']}
        for case in cases:
            with self.subTest(case=case['id']):
                self.assertIn('codebox:'+case['exact_name'],registry)
                self.assertEqual(case['surface'],'codebox');self.assertEqual(case['syntax'],'call')
                self.assertEqual(case['maximum_absolute_error'],reference.ABSOLUTE_TOLERANCES[case['model']])
                patch=json.loads((DIRECTORY/case['patch']).read_bytes())['patcher'];boxes={b['box']['id']:b['box']for b in patch['boxes']}
                self.assertEqual(len(boxes),5);self.assertEqual({b['text']for b in boxes.values()},{'in~ 1','in~ 2','codebox~','out~ 1','out~ 2'})
                code=boxes['program']['rnbo_extra_attributes']['code']
                self.assertEqual(code.count(case['exact_name']+'('),2)
                self.assertEqual(len(patch['lines']),4);self.assertTrue(case['reference_sources'])
                if case['model']in(534,535):self.assertIn('(in1, -1, 1)',code);self.assertIn('(in2, 1, -1)',code)
        self.assertFalse({'rect','twist','xfademul','ease','easelistinterp'}&{c['exact_name']for c in cases})

    def test_nonfinite_shapes_domains_divisors_and_large_integer_inputs_reject(self):
        w=reference.word
        for model,inputs in((True,(0,0)),(499,(0,0)),(540,(0,0)),(500,()),(500,(0,)),(500,(True,0)),
                           (500,(0x7f800000,0)),(500,(w(-.1),w(.5))),(500,(w(1.1),w(.5))),
                           (536,(w(9),w(1))),(538,(w(1),w(0))),(539,(w(-1),w(1))),(537,(w(1.5),w(1)))):
            with self.subTest(model=model,inputs=inputs),self.assertRaises(ValueError):reference.reference_words(model,inputs)
        for frames in(True,0,16385):
            with self.assertRaises(ValueError):reference.input_words(frames)
        with self.assertRaises(ValueError):reference.case_input_words(499)


if __name__=='__main__':unittest.main()
