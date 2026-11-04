# SPDX-License-Identifier: MIT
import importlib.util
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'smoke_rnbo_functions', ROOT / 'tests/fixtures/smoke/rnbo-functions/reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class RNBOFunctionsReferenceTests(unittest.TestCase):
    def test_all_predeclared_vectors_are_finite_and_tolerances_are_unit_aware(self):
        self.assertEqual(set(reference.CASE_WORDS), set(reference.MODELS))
        self.assertEqual(set(reference.DOMAINS), set(reference.MODELS))
        for model in reference.MODELS:
            with self.subTest(model=model):
                inputs = reference.case_input_words(model)
                outputs = reference.reference_words(model, inputs)
                self.assertEqual(len(inputs), 512)
                self.assertEqual(len(outputs), 512)
                self.assertTrue(all(math.isfinite(reference.value(w)) for w in outputs))
                if model not in (131, 133, 134, 137, 138, 139, 140, 141, 142):
                    self.assertLessEqual(max(abs(reference.value(w)) for w in outputs), 8)
        self.assertEqual(reference.ABSOLUTE_TOLERANCES[133], 5e-4)
        self.assertEqual(reference.ABSOLUTE_TOLERANCES[134], 0)
        self.assertEqual(reference.ABSOLUTE_TOLERANCES[143], 1e-3)
        self.assertEqual(reference.ABSOLUTE_TOLERANCES[131], 0)
        for model in (137, 138, 139, 140, 141, 142):
            self.assertEqual(reference.ABSOLUTE_TOLERANCES[model], 5e-4)

    def test_musical_reference_notes_octaves_and_default_integer_rounding(self):
        w = reference.word
        self.assertEqual(reference.reference_words(133, (w(57), w(69), w(81), w(69))),
                         (w(220), w(440), w(880), w(440)))
        self.assertEqual(reference.reference_words(134, (w(220), w(440), w(880), w(440))),
                         (w(57), w(69), w(81), w(69)))
        fq = tuple(w(440 * 2 ** ((n - 69) / 12)) for n in (68.75, 69.25))
        self.assertEqual(reference.reference_words(134, fq), (w(69), w(69)))

    def test_amplitude_decibels_reference_is_unity_not_legacy_offset(self):
        w = reference.word
        self.assertEqual(reference.reference_words(135, (w(1), w(1))), (0, 0))
        outputs = reference.reference_words(135, (w(.5), w(2)))
        self.assertEqual(outputs, (0xc0c0a8c1, 0x40c0a8c1))
        self.assertEqual(reference.reference_words(136, (w(0), w(-0.))), (w(1), w(1)))
        out = reference.reference_words(136, (w(-20), w(6)))
        self.assertEqual(out[0], w(.1))
        self.assertAlmostEqual(reference.value(out[1]), 1.9952623, places=6)

    def test_time_frequency_sample_units_use_fixed44100Hz(self):
        w = reference.word
        self.assertEqual(reference.RATE, 44100)
        self.assertEqual(reference.reference_words(137, (w(0), w(.125))), (0, w(5.5125)))
        self.assertEqual(reference.reference_words(138, (w(0), w(256))), (0, w(256000 / 44100)))
        self.assertEqual(reference.reference_words(137, (w(1), w(1000))), (w(44.1), w(44100)))
        self.assertEqual(reference.reference_words(138, (w(441), w(44100))), (w(10), w(1000)))
        for model in (139, 140):
            self.assertEqual(reference.reference_words(model, (w(125), w(1000))), (w(8), w(1)))
        for model in (141, 142):
            self.assertEqual(reference.reference_words(model, (w(5512.5), w(44100))), (w(8), w(1)))
            self.assertEqual(reference.reference_words(model, (w(1), w(441))), (w(44100), w(100)))
        self.assertEqual(reference.reference_words(140, (w(1), w(1000))), (w(1000), w(1)))

    def test_angles_constants_binary_order_and_fast_or_taylor_ideal_policy(self):
        w = reference.word
        self.assertEqual(reference.reference_words(122, (w(1), w(-1))), (0x4016cbe4, 0xbf490fdb))
        self.assertEqual(reference.reference_words(128, (w(3), w(4))), (w(5), w(5)))
        self.assertEqual(reference.reference_words(130, (w(180), w(-90))), (0x40490fdb, 0xbfc90fdb))
        self.assertEqual(reference.reference_words(131, (w(-1), w(1))), (0x42652ee1,) * 2)
        self.assertEqual(reference.reference_words(132, (w(-1), w(1))), (0x3c8efa35,) * 2)
        for model, ideal in ((143, 115), (144, 116), (145, 117), (146, 116)):
            inputs = reference.case_input_words(model)
            self.assertEqual(reference.reference_words(model, inputs), reference.reference_words(ideal, inputs))
        wrapped = reference.reference_words(147, (w(6.5), w(-6.5)))
        self.assertEqual(wrapped[0], wrapped[1])
        self.assertIn('not-fast-accuracy-promise', reference.REFERENCE_POLICIES[143])

    def test_outside_smoke_domains_are_not_silently_clipped_to_make_truth(self):
        w = reference.word
        cases = ((122, (0, w(1))), (126, (w(.5), w(1))), (127, (w(1), 0)),
                 (129, (w(1), 0)), (133, (w(-12), w(69))), (134, (0, w(440))),
                 (135, (0, w(1))), (139, (0, w(1000))), (141, (0, w(44100))),
                 (147, (w(3), 0)), (115, (0x7f800000, 0)), (115, (True, 0)),
                 (True, (0, 0)))
        for model, inputs in cases:
            with self.subTest(model=model, inputs=inputs), self.assertRaises(ValueError):
                reference.reference_words(model, inputs)
        for frames in (True, 0, 16385):
            with self.assertRaises(ValueError): reference.input_words(frames)
        with self.assertRaises(ValueError): reference.case_input_words(148)
        with self.assertRaises(ValueError): reference.reference_words(115, (0,))


if __name__ == '__main__':
    unittest.main()
