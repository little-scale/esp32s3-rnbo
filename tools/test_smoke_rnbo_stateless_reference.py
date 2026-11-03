# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'smoke_rnbo_stateless', ROOT / 'tests/fixtures/smoke/rnbo-stateless/reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class StatelessSmokeReferenceTests(unittest.TestCase):
    def test_full_stereo_cartesian_grid_and_both_zero_encodings(self):
        inputs = reference.input_words(256)
        pairs = set(zip(inputs[::2], inputs[1::2]))
        self.assertEqual(len(reference.WORDS), 16)
        self.assertEqual(pairs, {(a, b) for a in reference.WORDS for b in reference.WORDS})
        self.assertIn((0, 0x80000000), pairs)
        self.assertIn((0x80000000, 0), pairs)
        self.assertEqual(reference.input_words(512), inputs + inputs)
        for model in reference.MODELS:
            self.assertEqual(len(reference.reference_words(model, inputs)), 512)

    def test_arithmetic_is_exact_and_reverse_subtraction_has_correct_direction(self):
        # 1.5 and -0.5: sum 1, product -0.75, reverse difference (-2, +2).
        inputs = (0x3fc00000, 0xbf000000)
        self.assertEqual(reference.reference_words(35, inputs), (0x3f800000, 0x3f800000))
        self.assertEqual(reference.reference_words(36, inputs), (0xbf400000, 0xbf400000))
        self.assertEqual(reference.reference_words(37, inputs), (0xc0000000, 0x40000000))
        self.assertEqual(reference.reference_words(38, inputs), (0x40000000, 0x40000000))
        self.assertEqual(reference.reference_words(36, (0x40800000, 0x40800000)), (0x41800000, 0x41800000))

    def test_unary_words_preserve_copy_and_negation_and_clear_only_abs_sign(self):
        inputs = (0, 0x80000000, 0x3e800000, 0xbe800000)
        self.assertEqual(reference.reference_words(41, inputs), inputs)
        self.assertEqual(reference.reference_words(39, inputs), (0x80000000, 0, 0xbe800000, 0x3e800000))
        self.assertEqual(reference.reference_words(40, inputs), (0, 0, 0x3e800000, 0x3e800000))

    def test_ordered_relations_and_signed_zero_equality(self):
        one = 0x3f800000
        inputs = (0xbf000000, 0x3e800000, 0, 0x80000000)
        self.assertEqual(reference.reference_words(42, inputs), (one, one, 0, 0))
        self.assertEqual(reference.reference_words(43, inputs), (0, one, 0, 0))
        self.assertEqual(reference.reference_words(44, inputs), (0, one, one, one))
        self.assertEqual(reference.reference_words(45, inputs), (one, 0, one, one))

    def test_nonzero_truth_tables_include_negative_inputs_and_negative_zero(self):
        one = 0x3f800000
        # neither true, both true, left true, right true
        inputs = (0, 0x80000000, 0xc0000000, 0x40000000,
                  0xbf000000, 0, 0x80000000, 0x3e800000)
        self.assertEqual(reference.reference_words(46, inputs), (0, 0, one, one, 0, 0, 0, 0))
        self.assertEqual(reference.reference_words(47, inputs), (0, 0, one, one, one, one, one, one))
        self.assertEqual(reference.reference_words(48, inputs), (0, 0, 0, 0, one, one, one, one))
        self.assertEqual(reference.reference_words(49, inputs), (one, one, 0, 0, 0, one, one, 0))
        self.assertEqual(reference.reference_words(50, inputs), (0, 0, one, one, one, 0, 0, one))

    def test_malformed_or_out_of_scope_inputs_do_not_acquire_expected_outputs(self):
        for model in (True, 35.0, 34, 51, 'add'):
            with self.subTest(model=model), self.assertRaises(ValueError):
                reference.reference_words(model, (0, 0))
        for inputs in ((), (0,), (True, 0), (-1, 0), (0x100000000, 0),
                       (0x7f800000, 0), (0x7fc00000, 0), (0x40800001, 0)):
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                reference.reference_words(35, inputs)
        for frames in (True, 0, -1, 1.5, 16385):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                reference.input_words(frames)


if __name__ == '__main__':
    unittest.main()
