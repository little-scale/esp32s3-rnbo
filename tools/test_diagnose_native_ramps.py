# SPDX-License-Identifier: MIT
import struct
import unittest

from diagnose_native_ramps import compare


class CaptureComparisonTests(unittest.TestCase):
    def test_left_tolerance_does_not_relax_the_right_pilot_or_signed_zero_policy(self):
        expected = struct.pack('<4f', 1, 0, 0, 1)
        actual = struct.pack('<4f', 1.000001, -0.0, -0.0, 1.001)
        result = compare(actual, expected, 0.00003)
        self.assertEqual(result['within_tolerance_words'], 1)
        self.assertEqual(result['outside_tolerance_words'], 2)
        self.assertEqual(result['left_zero_sign_differences'], 1)
        self.assertEqual(result['bit_differences'], 4)

    def test_partial_prefix_is_observed_without_claiming_a_complete_capture(self):
        expected = struct.pack('<4f', 1, 2, 3, 4)
        self.assertEqual(compare(expected[:8], expected, 0)['words'], 2)
        with self.assertRaises(ValueError):
            compare(expected + expected, expected, 0)
        with self.assertRaises(ValueError):
            compare(expected[:3], expected, 0)
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            compare(struct.pack('<f', float('inf')), expected, 0)
