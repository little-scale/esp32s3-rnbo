# SPDX-License-Identifier: MIT
import importlib.util
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'smoke_rnbo_numeric', ROOT / 'tests/fixtures/smoke/rnbo-numeric/reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class NumericReferenceTests(unittest.TestCase):
    def test_case_vectors_are_finite_and_match_predeclared_exact_or_bounded_tolerance(self):
        for model in reference.MODELS:
            with self.subTest(model=model):
                inputs = reference.case_input_words(model, 256)
                expected = reference.reference_words(model, inputs)
                self.assertEqual(len(inputs), 512)
                self.assertEqual(len(expected), 512)
                self.assertTrue(all(math.isfinite(reference.value(w)) for w in expected))
                self.assertEqual(reference.ABSOLUTE_TOLERANCES[model], 2e-6 if model >= 66 else 0)
                if model >= 66:
                    self.assertLessEqual(max(abs(reference.value(w)) for w in expected), 8)
        self.assertIn(0xcf000000, reference.WORDS)
        self.assertIn(0x4effffff, reference.WORDS)
        self.assertIn(1, reference.WORDS)
        self.assertIn(0x80000001, reference.WORDS)

    def test_division_and_remainders_use_correct_direction_and_signed_quotient(self):
        inputs = (reference.word(-1.5), reference.word(.5))
        self.assertEqual(reference.reference_words(51, inputs), (reference.word(-3.), reference.word(-1. / 3)))
        self.assertEqual(reference.reference_words(52, inputs), (reference.word(-1. / 3), reference.word(-3.)))
        self.assertEqual(reference.reference_words(53, inputs), (0x80000000, reference.word(.5)))
        self.assertEqual(reference.reference_words(54, inputs), (reference.word(.5), 0x80000000))
        pairs = set(zip(reference.case_input_words(51)[::2], reference.case_input_words(51)[1::2]))
        self.assertEqual(pairs, {(a, b) for a in reference.DIVISORS for b in reference.DIVISORS})

    def test_halfway_neighbors_are_rounded_as_real_values_without_float_intermediate_bias(self):
        inputs = (0x3effffff, 0xbeffffff, 0x3f000000, 0xbf000000,
                  0x3f000001, 0xbf000001, 0x3fc00000, 0xbfc00000)
        self.assertEqual(reference.reference_words(58, inputs),
                         (0, 0x80000000, 0x3f800000, 0xbf800000, 0x3f800000, 0xbf800000, 0x40000000, 0xc0000000))
        self.assertEqual(reference.reference_words(59, (0xbfc00000, 0x3fc00000)), (0xbf000000, 0x3f000000))
        self.assertEqual(reference.reference_words(65, (0xcf000000, 0x4effffff)), (0xcf000000, 0x4effffff))
        self.assertEqual(reference.reference_words(55, (1, 0x80000001)), (0, 0xbf800000))
        self.assertEqual(reference.reference_words(56, (1, 0x80000001)), (0x3f800000, 0))

    def test_denormal_and_finite_only_nan_contracts_preserve_distinctions(self):
        inputs = (0, 0x80000000, 1, 0x807fffff, 0x00800000, 0x80800000)
        self.assertEqual(reference.reference_words(61, inputs), (0,) * 6)
        self.assertEqual(reference.reference_words(62, inputs), inputs)
        self.assertEqual(reference.reference_words(63, inputs), (0, 0, 0x3f800000, 0x3f800000, 0, 0))
        self.assertEqual(reference.reference_words(64, inputs), (0, 0x80000000, 0, 0, 0x00800000, 0x80800000))
        self.assertEqual(reference.reference_words(60, inputs), (0, 0x80000000, 0x3f800000, 0xbf800000, 0x3f800000, 0xbf800000))

    def test_transcendental_landmarks_and_swapped_power_exponents(self):
        w = reference.word
        self.assertEqual(reference.reference_words(66, (w(.25), w(4))), (w(.5), w(2)))
        self.assertEqual(reference.reference_words(67, (w(-.125), w(3.375))), (w(-.5), w(1.5)))
        self.assertEqual(reference.reference_words(68, (w(0), w(1))), (w(1), 0x402df854))
        self.assertEqual(reference.reference_words(69, (w(-2), w(2))), (w(.25), w(4)))
        self.assertEqual(reference.reference_words(70, (w(0), w(1))), (w(0), 0x3fdbf0a9))
        self.assertEqual(reference.reference_words(71, (w(1), w(1))), (0, 0))
        self.assertEqual(reference.reference_words(72, (w(.125), w(4))), (w(-3), w(2)))
        self.assertEqual(reference.reference_words(73, (w(1), w(1))), (0, 0))
        self.assertEqual(reference.reference_words(74, (w(0), w(1))), (0, 0x3f317218))
        self.assertEqual(reference.reference_words(75, (w(.5), w(2))), (w(.25), 0x3fb504f3))

    def test_invalid_or_unsafe_domains_reject_instead_of_manufacturing_finite_truth(self):
        for model, inputs in ((51, (0, 0)), (65, (0x4f000000, 0)), (66, (0xbf800000, 0)),
                              (68, (reference.word(4), 0)), (71, (0, 0)), (74, (reference.word(-1), 0)),
                              (75, (reference.word(-1), reference.word(2))), (55, (0x7fc00000, 0)),
                              (55, (True, 0)), (True, (0, 0))):
            with self.subTest(model=model, inputs=inputs), self.assertRaises(ValueError):
                reference.reference_words(model, inputs)
        for frames in (True, 0, 16385):
            with self.assertRaises(ValueError):
                reference.input_words(frames)
        with self.assertRaises(ValueError):
            reference.case_input_words(76)
        with self.assertRaises(ValueError):
            reference.reference_words(55, (0,))


if __name__ == '__main__':
    unittest.main()
