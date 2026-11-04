# SPDX-License-Identifier: MIT
"""Finite GenExpr range/route/math references; no DSP/output capture dependency."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1];DIRECTORY=ROOT/'tests/fixtures/smoke/gen-range'
spec=importlib.util.spec_from_file_location('gen_range_reference',DIRECTORY/'reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class GenRangeReferenceTests(unittest.TestCase):
    def test_range_endpoints_fold_reflection_unclamped_scale_and_dyadic_interpolation(self):
        w=reference.word
        values=(-4,-3,-2,-1,0,1,2,3,4)
        for x,wrapped,folded in zip(values,(0,-1,0,-1,0,-1,0,-1,0),(0,1,0,-1,0,1,0,-1,0)):
            self.assertEqual(reference.reference_words(351,(w(x),w(x))),(w(wrapped),)*2)
            self.assertEqual(reference.reference_words(350,(w(x),w(x))),(w(folded),)*2)
        self.assertEqual(reference.reference_words(352,(w(-4),w(4))),(w(-1),w(1)))
        self.assertEqual(reference.reference_words(353,(w(-4),w(4))),(w(-1),w(1)))
        self.assertEqual(reference.reference_words(354,(w(-4),w(4))),(w(-8),w(8)))
        self.assertEqual(reference.reference_words(355,(w(-4),w(4))),(w(-2),w(2)))
        self.assertEqual(reference.reference_words(356,(w(-.5),w(.5))),(w(.15625),w(.84375)))
        self.assertEqual(reference.reference_words(376,(w(.25),w(.75))),(w(-.5),w(-.5)))
        phase=tuple(reference.value(v)for v in reference.reference_words(357,(w(-4),w(4))))
        self.assertAlmostEqual(phase[0],2*math.pi-4,places=6);self.assertAlmostEqual(phase[1],4-2*math.pi,places=6)

    def test_two_coordinate_outputs_and_integer_choice_routing_are_observed(self):
        w=reference.word
        self.assertEqual(reference.reference_words(358,(w(1),w(-1))),(w(math.sqrt(2)),w(-math.pi/4)))
        self.assertEqual(reference.reference_words(359,(w(2),w(0))),(w(2),w(0)))
        for choice in(-2,0,1,2,4):
            selected=(2.,-2.)if choice==1 else(-2.,2.)if choice>=2 else(0.,0.)
            gated=(2.,0.)if choice==1 else(0.,2.)if choice>=2 else(0.,0.)
            self.assertEqual(reference.reference_words(360,(w(choice),w(2))),tuple(w(x)for x in selected))
            self.assertEqual(reference.reference_words(361,(w(choice),w(2))),tuple(w(x)for x in gated))
        with self.assertRaises(ValueError):reference.reference_words(360,(w(.5),w(1)))
        self.assertEqual(reference.reference_words(375,(w(.25),w(.25))),(w(.5),w(1)))
        self.assertEqual(reference.reference_words(375,(w(1),w(1))),(w(0),w(0)))

    def test_frequency_time_decibels_and_t60_have_explicit_units(self):
        w=reference.word
        self.assertEqual(reference.reference_words(367,(w(69),w(81))),(w(440),w(880)))
        quarter=w(440*2**(.25/12))
        self.assertEqual(reference.reference_words(368,(w(440),quarter)),(w(69),w(69.25)))
        self.assertEqual(reference.reference_words(369,(w(1),w(1000))),(w(44.1),w(44100)))
        self.assertEqual(reference.reference_words(370,(w(441),w(44100))),(w(10),w(1000)))
        self.assertEqual(reference.reference_words(371,(w(1),w(2))),(w(0),0x40c0a8c1))
        self.assertEqual(reference.reference_words(372,(w(0),w(-20))),(w(1),w(.1)))
        self.assertEqual(reference.reference_words(373,(w(1),w(2))),(w(.001),w(math.sqrt(.001))))
        time=reference.value(reference.reference_words(374,(w(.5),w(.5)))[0])
        self.assertAlmostEqual(time,math.log(.001)/math.log(.5),places=5)
        self.assertLess(time,10)

    def test_every_frozen_vector_and_limit_is_finite_and_fast_ideals_are_not_fitted(self):
        self.assertEqual(len(reference.MODELS),30)
        for model in reference.MODELS:
            inputs=reference.case_input_words(model);outputs=reference.reference_words(model,inputs)
            self.assertEqual(len(inputs),512);self.assertEqual(len(outputs),512)
            self.assertTrue(all(math.isfinite(reference.value(w))for w in outputs))
        for model in range(362,367):self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],1e-3)
        for model in(367,368,369,370,374):self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],5e-4)
        for model in(350,351,352,353,354,355,356,360,361,376,377,378,379):self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],0)
        w=reference.word
        self.assertEqual(reference.reference_words(362,(w(.5),w(2))),(w(.25),w(math.sqrt(2))))
        self.assertEqual(reference.reference_words(363,(w(0),w(1))),(w(1),w(math.e)))
        self.assertEqual(reference.reference_words(364,(w(0),w(.5))),(w(0),w(math.sin(.5))))
        self.assertEqual(reference.reference_words(365,(w(0),w(.5))),(w(1),w(math.cos(.5))))
        for model in(377,378):self.assertEqual(reference.reference_words(model,(0x80000000,0)),(0x80000000,0))
        self.assertEqual(reference.reference_words(379,(0x80000000,0)),(0,0))

    def test_thirty_original_genexpr_sources_are_bound_and_aliases_are_distinct(self):
        catalog=json.loads((DIRECTORY/'catalog.json').read_bytes());cases=catalog['cases']
        self.assertEqual(catalog['family'],'gen-range');self.assertEqual(len(cases),30)
        self.assertEqual(len({c['exact_name']for c in cases}),30)
        self.assertNotIn('switch',{c['exact_name']for c in cases});self.assertNotIn('?',{c['exact_name']for c in cases})
        registry={r['exact_name']for r in json.loads((ROOT/'site/data/gen-inventory.json').read_bytes())['RNBO_GenExpr_registry_entries']}
        for case in cases:
            self.assertIn(case['exact_name'],registry);self.assertEqual(case['surface'],'genexpr')
            self.assertEqual(case['maximum_absolute_error'],reference.ABSOLUTE_TOLERANCES[case['model']])
            code=(DIRECTORY/case['genexpr']).read_text();patch=json.loads((DIRECTORY/case['patch']).read_bytes())['patcher']
            gen=[b['box']for b in patch['boxes']if b['box']['text']=='gen~'];self.assertEqual(len(gen),1)
            self.assertEqual(gen[0]['rnbo_extra_attributes']['expr'],code)
            self.assertNotIn('codebox~',{b['box']['text']for b in patch['boxes']})
            if 362<=case['model']<=366:self.assertIn('not a documented',case['scope'])
        gate=next(c for c in cases if c['exact_name']=='gate')
        self.assertEqual((DIRECTORY/gate['genexpr']).read_text(),'out1, out2 = gate(in1, in2, choices=2);\n')

    def test_invalid_shapes_nonfinite_words_and_out_of_domain_inputs_reject(self):
        w=reference.word
        for model,inputs in((True,(0,0)),(349,(0,0)),(380,(0,0)),(350,()),(350,(0,)),(350,(True,0)),
                           (350,(0x7f800000,0)),(350,(0xffc00000,0)),(350,(-1,0)),
                           (368,(w(0),w(440))),(374,(w(0),w(1))),(373,(w(0),w(1))),
                           (362,(w(-1),w(.5))),(375,(w(-1),w(0)))):
            with self.subTest(model=model,inputs=inputs),self.assertRaises(ValueError):reference.reference_words(model,inputs)
        for frames in(True,0,16385):
            with self.assertRaises(ValueError):reference.input_words(frames)
        with self.assertRaises(ValueError):reference.case_input_words(349)


if __name__=='__main__':unittest.main()
