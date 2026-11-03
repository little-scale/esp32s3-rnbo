# SPDX-License-Identifier: MIT
"""Independent model tests, including observations the former slope gate misses."""
import copy
from fractions import Fraction
import math
import struct
import unittest

from line_timing_oracle import analyse, duration, float32, reference, round_positive_fraction, word


def event(block, identity, value):
    return {"block": block, "id": identity, "value": value}


def capture(left, right):
    return b"".join(struct.pack("<ff", a, b) for a, b in zip(left, right))


def ramp_case(milliseconds=10, target=1, blocks=4):
    return {"blocks": blocks, "events": [event(0, "milliseconds", milliseconds), event(0, "target", target)]}


class LineTimingOracleTests(unittest.TestCase):
    def test_fraction_rounding_checks_even_ties_and_subnormal_halfway(self):
        one = Fraction(1)
        ulp = Fraction(1, 1 << 23)
        self.assertEqual(round_positive_fraction(one + ulp / 2), 1.0)
        self.assertEqual(word(round_positive_fraction(one + 3 * ulp / 2)), word(1.0) + 2)
        self.assertEqual(word(round_positive_fraction(Fraction(1, 1 << 150))), 0)
        self.assertEqual(word(round_positive_fraction(Fraction(3, 1 << 150))), 2)
        for sign in (-1, 1):
            near = one + ulp / 2 + sign * Fraction(1, 1 << 100)
            self.assertEqual(word(round_positive_fraction(near)), word(1.0) + (sign > 0))

    def test_reviewed_duration_conversion_and_zero_policy(self):
        for milliseconds in (0, -0.0, 2**-149, .5 / 44.1, 1 / 44.1, 1.5 / 44.1, 1, 5, 10, 40, 100):
            with self.subTest(milliseconds=milliseconds):
                samples, audit = duration(milliseconds)
                self.assertTrue(audit["conversion_agrees"])
                self.assertGreater(samples, 0)
        self.assertEqual(duration(0)[0], 1)
        self.assertEqual(duration(-0.0)[1]["rational_duration_bits"], "80000000")
        self.assertLess(duration(2**-149)[0], 1)

    def test_exact_linear_truth_passes_and_double_duration_fails(self):
        case = ramp_case()
        right = [1] * 1024
        truth = [min(i / 441, 1) for i in range(1024)]
        result = analyse(case, capture(truth, right))
        self.assertTrue(result["passed"])
        self.assertEqual(result["cycles"][0]["endpoints"][0]["observed_settled_frame"], 441)
        wrong = [min(i / 882, 1) for i in range(1024)]
        self.assertFalse(analyse(case, capture(wrong, right))["passed"])

    def test_first_sample_policy_is_explicit_and_not_fitted_to_shifted_audio(self):
        case = ramp_case()
        shifted = [min((i + 1) / 441, 1) for i in range(1024)]
        result = analyse(case, capture(shifted, [1] * 1024))
        self.assertFalse(result["passed"])
        self.assertEqual(result["cycles"][0]["first_failure"]["frame"], 0)

    def test_cold_duration_and_same_block_hot_inlet_order_are_observable(self):
        case = ramp_case()
        case["events"] += [event(1, "target", -.5), event(1, "milliseconds", 5)]
        left = [i / 441 if i < 256 else max(-.5, 256 / 441 + (-.5 - 256 / 441) * (i - 256) / 441)
                for i in range(1024)]
        right = [1 if i < 256 else -.5 for i in range(1024)]
        self.assertTrue(analyse(case, capture(left, right))["passed"])
        reversed_order = copy.deepcopy(case)
        reversed_order["events"][-2:] = list(reversed(reversed_order["events"][-2:]))
        self.assertFalse(analyse(reversed_order, capture(left, right))["passed"])
        cold_only = ramp_case()
        cold_only["events"].append(event(1, "milliseconds", 5))
        self.assertTrue(analyse(cold_only, capture([min(i / 441, 1) for i in range(1024)], [1] * 1024))["passed"])

    def test_repeated_target_restarts_from_the_mathematical_boundary_value(self):
        case = ramp_case(10)
        case["events"].append(event(1, "target", 1))
        truth = [i / 441 if i < 256 else min(1, 256 / 441 + (1 - 256 / 441) * (i - 256) / 441)
                 for i in range(1024)]
        self.assertTrue(analyse(case, capture(truth, [1] * 1024))["passed"])
        self.assertFalse(analyse(case, capture([min(i / 441, 1) for i in range(1024)], [1] * 1024))["passed"])

    def test_coincident_targets_do_not_advance_mathematical_time(self):
        case = ramp_case(0)
        case["events"] += [event(0, "target", -.5), event(0, "target", .25)]
        truth = [0] + [.25] * 1023
        self.assertTrue(analyse(case, capture(truth, [.25] * 1024))["passed"])
        case["events"][0]["value"] = 2**-149
        self.assertTrue(analyse(case, capture(truth, [.25] * 1024))["passed"])

    def test_silent_prefix_cannot_change_the_reference_or_hide_time_quantisation(self):
        early = ramp_case(1)
        late = copy.deepcopy(early)
        late.update(prefix_blocks=(1 << 26) // 256, warmup_blocks=4)
        late["absolute_first_capture_sample"] = ((1 << 26) // 256 + 4) * 256
        self.assertEqual(reference(early), reference(late))
        samples = duration(1)[0]
        truth = [min(i / samples, 1) for i in range(1024)]
        self.assertTrue(analyse(late, capture(truth, [1] * 1024))["passed"])
        # An absolute-time rounding bug can terminate early. It is not added
        # to the model's error budget just because the stream is older.
        wrong = [i / samples if i < 40 else 1 for i in range(1024)]
        self.assertFalse(analyse(late, capture(wrong, [1] * 1024))["passed"])

    def test_observer_requires_exact_words_and_every_lifecycle_is_checked(self):
        case = ramp_case(0, -0.0)
        raw = capture([0] * 1024, [-0.0] * 1024)
        self.assertTrue(analyse(case, raw)["passed"])
        self.assertFalse(analyse(case, capture([0] * 1024, [0] * 1024))["passed"])
        case["lifecycles"] = 2
        wrong = capture([math.nan] + [0] * 1023, [-0.0] * 1024)
        result = analyse(case, raw + wrong)
        self.assertTrue(result["cycles"][0]["passed"])
        self.assertFalse(result["cycles"][1]["passed"])

    def test_tiny_ramp_output_cannot_qualify_early_clock_timing(self):
        tiny = struct.unpack('<f', struct.pack('<I', 1))[0]
        case = ramp_case(10, tiny)
        result = analyse(case, capture([tiny] * 1024, [tiny] * 1024))
        self.assertTrue(result['passed'])
        self.assertFalse(result['internal_completion_clock_qualified'])
        endpoint = result['cycles'][0]['endpoints'][0]
        self.assertFalse(endpoint['early_timing_qualified'])
        self.assertTrue(endpoint['late_target_hold_passed'])
        late = capture([0] * 450 + [tiny] * 574, [tiny] * 1024)
        self.assertFalse(analyse(case, late)['passed'])
        large = analyse(ramp_case(), capture([1] * 1024, [1] * 1024))
        self.assertFalse(large['passed'])
        self.assertTrue(large['cycles'][0]['endpoints'][0]['early_timing_qualified'])

    def test_invalid_inputs_missing_words_and_widened_gates_reject(self):
        case = ramp_case()
        for value in (True, None, math.inf, math.nan, 10**1000):
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                float32(value)
        for bad in ({"blocks": True}, {"prefix_blocks": -1}, {"warmup_blocks": 65},
                    {"events": [event(1, "target", 1), event(0, "target", 0)]},
                    {"events": [event(0, "unknown", 1)]},
                    {"events": [event(0, "milliseconds", 101)]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                reference(case | bad)
        with self.assertRaises(ValueError):
            analyse(case, b"")
        raw = capture([min(i / 441, 1) for i in range(1024)], [1] * 1024)
        for options in ({"maximum_absolute_error": 3e-5}, {"endpoint_allowance": 2}):
            with self.assertRaises(ValueError):
                analyse(case, raw, **options)


if __name__ == "__main__":
    unittest.main()
