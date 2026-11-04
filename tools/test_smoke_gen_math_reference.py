# SPDX-License-Identifier: MIT
import importlib.util
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'smoke_gen_math', ROOT / 'tests/fixtures/smoke/gen-math/reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class GenMathReferenceTests(unittest.TestCase):
    def test_all_case_vectors_are_valid_and_approximate_outputs_are_bounded(self):
        self.assertEqual(set(reference.DOMAINS), set(reference.MODELS))
        self.assertEqual(set(reference.ABSOLUTE_TOLERANCES), set(reference.MODELS))
        self.assertEqual(len(reference.input_words()), 512)
        for model in reference.MODELS:
            with self.subTest(model=model):
                inputs = reference.case_input_words(model)
                outputs = reference.reference_words(model, inputs)
                self.assertEqual(len(inputs), 512)
                self.assertEqual(len(outputs), 512)
                self.assertTrue(all(math.isfinite(reference.value(w)) for w in outputs))
                self.assertEqual(reference.ABSOLUTE_TOLERANCES[model], 0 if model <= 80 else 2e-6)
                if model > 80:
                    self.assertLessEqual(max(abs(reference.value(w)) for w in outputs), 8)

    def test_exact_binary_operations_and_reversed_argument_order(self):
        w = reference.word
        inputs = (w(-1.5), w(.5))
        self.assertEqual(reference.reference_words(76, inputs), (w(-3.), w(-1. / 3)))
        self.assertEqual(reference.reference_words(77, inputs), (w(-1. / 3), w(-3.)))
        self.assertEqual(reference.reference_words(78, inputs), (0x80000000, w(.5)))
        self.assertEqual(reference.reference_words(79, inputs), (w(.5), 0x80000000))
        self.assertEqual(reference.reference_words(80, inputs), (w(2), w(-2)))
        pairs = set(zip(reference.case_input_words(76)[::2], reference.case_input_words(76)[1::2]))
        self.assertEqual(pairs, {(a, b) for a in reference.DIVISORS for b in reference.DIVISORS})

    def test_power_log_and_square_root_landmarks(self):
        w = reference.word
        self.assertEqual(reference.reference_words(81, (w(.25), w(4))), (w(.5), w(2)))
        self.assertEqual(reference.reference_words(82, (w(0), w(1))), (w(1), 0x402df854))
        self.assertEqual(reference.reference_words(83, (w(-2), w(2))), (w(.25), w(4)))
        self.assertEqual(reference.reference_words(84, (w(1), w(1))), (0, 0))
        self.assertEqual(reference.reference_words(85, (w(.125), w(4))), (w(-3), w(2)))
        self.assertEqual(reference.reference_words(86, (w(1), w(1))), (0, 0))
        self.assertEqual(reference.reference_words(87, (w(.5), w(2))), (w(.25), 0x3fb504f3))

    def test_trig_hyperbolic_and_inverse_landmarks(self):
        w = reference.word
        zero = (w(0), w(0))
        for model in (88, 90, 91, 92, 94, 96, 98, 100):
            self.assertEqual(reference.reference_words(model, zero), zero)
        self.assertEqual(reference.reference_words(89, zero), (w(1), w(1)))
        self.assertEqual(reference.reference_words(97, zero), (w(1), w(1)))
        self.assertEqual(reference.reference_words(93, (w(1), w(-1))), (0, 0x40490fdb))
        self.assertEqual(reference.reference_words(92, (w(1), w(-1))), (0x3fc90fdb, 0xbfc90fdb))
        self.assertEqual(reference.reference_words(99, (w(1), w(1))), zero)
        self.assertEqual(reference.reference_words(101, (w(3), w(4))), (w(5), w(5)))

    def test_atan2_quadrants_order_and_angle_units(self):
        w = reference.word
        self.assertEqual(reference.reference_words(95, (w(1), w(-1))), (0x4016cbe4, 0xbf490fdb))
        self.assertEqual(reference.reference_words(102, (w(.125), w(-.125))), (0x40e52ee1, 0xc0e52ee1))
        self.assertEqual(reference.reference_words(103, (w(180), w(-90))), (0x40490fdb, 0xbfc90fdb))
        self.assertEqual(reference.reference_words(103, (0, 0x80000000)), (0, 0x80000000))

    def test_invalid_domains_are_rejected_without_producing_finite_standins(self):
        w = reference.word
        cases = ((76, (0, w(1))), (81, (w(-1), 0)), (82, (w(4), 0)),
                 (84, (0, w(1))), (87, (w(-1), w(1))), (92, (w(2), 0)),
                 (95, (0, w(1))), (99, (w(.5), w(1))), (100, (w(1), 0)),
                 (102, (w(1), 0)), (80, (0x7f800000, 0)), (80, (True, 0)),
                 (True, (0, 0)))
        for model, inputs in cases:
            with self.subTest(model=model, inputs=inputs), self.assertRaises(ValueError):
                reference.reference_words(model, inputs)
        for frames in (True, 0, 16385):
            with self.assertRaises(ValueError):
                reference.input_words(frames)
        with self.assertRaises(ValueError):
            reference.case_input_words(104)
        with self.assertRaises(ValueError):
            reference.reference_words(80, (0,))


if __name__ == '__main__':
    unittest.main()
