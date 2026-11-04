# SPDX-License-Identifier: MIT
"""Portable mathematical and original-source checks for codebox misc smoke."""
import importlib.util
import json
import math
from fractions import Fraction
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'tests/fixtures/smoke/rnbo-codebox-misc'
spec = importlib.util.spec_from_file_location('codebox_misc_reference', DIRECTORY / 'reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class CodeboxMiscReferenceTests(unittest.TestCase):
    def output(self, model, left, right):
        return tuple(reference.value(w) for w in reference.reference_words(
            model, (reference.word(left), reference.word(right))))

    def test_shaping_ties_and_small_safe_integer_domains(self):
        self.assertEqual(self.output(700, .25, .25), (1, .5))
        self.assertEqual(self.output(701, .25, .25), (.5, .1875))
        self.assertEqual(self.output(702, -.375, -.0625), (-.25, 0))
        self.assertEqual(self.output(703, -2.5, 3.5), (-2, 4))
        self.assertEqual(self.output(703, -.5, .5), (0, 0))
        self.assertEqual(self.output(704, -.5, .25), (-2, -.5))
        self.assertEqual(self.output(704, 0, 1), (0, 0))
        self.assertEqual(self.output(705, -7, 3), (-1, 3))
        self.assertEqual(self.output(705, 1, 0), (0, 0))
        self.assertEqual(self.output(706, -2, 1.5), (4, 5.0625))
        self.assertEqual(self.output(707, -1, 6.25), (0, 2.5))
        self.assertEqual(self.output(708, 1023, 255), (255, 31))
        self.assertEqual(self.output(709, .875, 31.875), (0, 31))

    def test_complex_components_keep_real_imaginary_order(self):
        w = reference.word
        self.assertEqual(reference.reference_words(710, (w(1.5), w(-0.))), (w(1.5), w(0.)))
        self.assertEqual(self.output(711, 1, -.5), (reference.value(w(Fraction(3, 5))), reference.value(w(Fraction(-4, 5)))))
        self.assertEqual(self.output(713, 1, 2), (2.25, 2))
        self.assertEqual(self.output(712, 0, 0), (1, 0))
        real, imaginary = self.output(712, 0, .5)
        self.assertAlmostEqual(real, math.cos(.5), delta=1e-7)
        self.assertAlmostEqual(imaginary, math.sin(.5), delta=1e-7)

    def test_asymmetric_interpolators_have_distinct_named_conventions(self):
        points = reference.C4[0]
        names = ('cubicinterp', 'fastcubicinterp', 'splineinterp')
        for name in names:
            self.assertEqual(reference.interpolate(name, 0, points), points[1])
            self.assertEqual(reference.interpolate(name, 1, points), points[2])
        values = {reference.interpolate(name, .25, points) for name in names}
        self.assertEqual(len(values), 3)
        # At t=0 the six-point quintic B-spline is a weighted average,
        # rather than an interpolating pass through the center control.
        weights = (Fraction(1, 120), Fraction(13, 60), Fraction(11, 20), Fraction(13, 60), Fraction(1, 120), 0)
        expected = sum(Fraction(x) * weight for x, weight in zip(reference.C6[0], weights))
        self.assertAlmostEqual(reference.spline6(0, reference.C6[0]), float(expected), places=12)
        self.assertNotEqual(reference.spline6(0, reference.C6[0]), reference.C6[0][2])
        for t in (0, .125, .5, .875, 1):
            self.assertAlmostEqual(reference.spline6(t, (1,) * 6), 1, places=12)

    def test_selected_class_modes_are_pointwise_and_max_is_finite_float32(self):
        self.assertEqual(self.output(719, .75, .25), (.5, .5))
        self.assertEqual(self.output(720, .25, .75), (.0625, .5625))
        self.assertEqual(self.output(721, .25, .75), (-.875, -.125))
        self.assertEqual(reference.reference_words(718, (0, 0)), (0x7f7fffff,) * 2)
        self.assertTrue(math.isfinite(reference.value(0x7f7fffff)))

    def test_twenty_two_original_sources_match_declared_api_shapes_and_vectors(self):
        cases = json.loads((DIRECTORY / 'catalog.json').read_bytes())['cases']
        registry = {r['id'] for r in json.loads((ROOT / 'site/data/inventory.json').read_bytes())['spellings']}
        self.assertEqual(len(cases), 22)
        self.assertEqual(len({c['exact_name'] for c in cases}), 22)
        for case in cases:
            with self.subTest(case=case['id']):
                self.assertIn('codebox:' + case['exact_name'], registry)
                self.assertEqual(case['surface'], 'codebox')
                self.assertEqual(case['maximum_absolute_error'], reference.ABSOLUTE_TOLERANCES[case['model']])
                patch = json.loads((DIRECTORY / case['patch']).read_bytes())['patcher']
                boxes = {b['box']['id']: b['box'] for b in patch['boxes']}
                self.assertEqual(len(boxes), 5)
                self.assertEqual({b['text'] for b in boxes.values()}, {'in~ 1', 'in~ 2', 'codebox~', 'out~ 1', 'out~ 2'})
                code = boxes['program']['rnbo_extra_attributes']['code']
                self.assertTrue(case['reference_sources'])
                if case['syntax'] == 'stateful-next':
                    self.assertIn('new ' + case['exact_name'] + '()', code)
                    self.assertIn('.next(', code)
                    if case['exact_name'] in ('ease', 'easexfade'):
                        self.assertEqual(code.count(', 7, 0)'), 2)
                if case['exact_name'].startswith('complex_'):
                    self.assertIn('out1 = result[0]', code)
                    self.assertIn('out2 = result[1]', code)
                if case['exact_name'] == 'number_max':
                    self.assertEqual(len(patch['lines']), 2)
                    self.assertTrue(all(line['patchline']['source'][0] == 'program' for line in patch['lines']))
                inputs = reference.case_input_words(case['model'])
                outputs = reference.reference_words(case['model'], inputs)
                self.assertEqual(len(inputs), 512)
                self.assertEqual(len(outputs), 512)
                self.assertTrue(all(math.isfinite(reference.value(w)) for w in outputs))
        self.assertFalse({'rect', 'twist'} & {c['exact_name'] for c in cases})

    def test_nonfinite_invalid_shapes_and_unsafe_integer_domains_reject(self):
        w = reference.word
        for model, inputs in ((True, (0, 0)), (699, (0, 0)), (722, (0, 0)), (700, ()),
                              (700, (0,)), (700, (True, 0)), (700, (0x7f800000, 0)),
                              (700, (w(-.1), w(.5))), (705, (w(1.5), w(1))),
                              (708, (w(-1), w(1))), (708, (w(1024), w(1))),
                              (709, (w(-.5), w(1)))):
            with self.subTest(model=model, inputs=inputs), self.assertRaises(ValueError):
                reference.reference_words(model, inputs)
        for frames in (True, 0, 16385):
            with self.assertRaises(ValueError):
                reference.input_words(frames)


if __name__ == '__main__':
    unittest.main()
