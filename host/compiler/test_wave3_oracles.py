# SPDX-License-Identifier: MIT
"""Semantic and adversarial tests independent of generated RNBO kernels."""
import copy
import math
import unittest

from wave3_oracles import (analyse, bits, coefficient_hz, delta_reference,
                          expected_outputs, onepole_reference, parameter_planes,
                          sah_reference, slide_reference, wire32)


class StatefulWaveThreeTests(unittest.TestCase):
    def test_onepole_closed_step_impulse_and_transfer(self):
        frequency = 1000
        a = 1 - math.exp(-math.tau * frequency / 44100)
        self.assertAlmostEqual(coefficient_hz(frequency), a, places=15)
        step = onepole_reference([1] * 64, [frequency] * 64)
        impulse = onepole_reference([1] + [0] * 63, [frequency] * 64)
        for i in range(64):
            self.assertAlmostEqual(step[i], 1 - (1 - a) ** (i + 1), places=14)
            self.assertAlmostEqual(impulse[i], a * (1 - a) ** i, places=14)
        self.assertAlmostEqual(sum(impulse), step[-1], places=14)
        self.assertLess(abs(impulse[-1]), abs(impulse[0]))

    def test_onepole_clamps_and_long_mathematical_dc(self):
        for frequency in (-1000, 0, 1e-9):
            self.assertEqual(coefficient_hz(frequency), 1e-5)
        self.assertEqual(coefficient_hz(100000), .99999)
        value = onepole_reference([1] * 131072, [0] * 131072)[-1]
        self.assertAlmostEqual(value, -math.expm1(131072 * math.log1p(-1e-5)), places=14)
        # A reference must not adopt the equilibrium error of rounded,
        # separately stored Float32 feedforward/feedback coefficients.
        stored_a, stored_b = wire32(1e-5), wire32(1 - 1e-5)
        self.assertGreater(abs(1 - stored_a / (1 - stored_b)), .001)

    def test_onepole_frequency_change_retains_history(self):
        source = [1] * 256 + [0] * 256
        frequencies = [1000] * 256 + [100] * 256
        result = onepole_reference(source, frequencies)
        history = 1 - math.exp(256 * math.log1p(-coefficient_hz(1000)))
        self.assertAlmostEqual(result[256], history * (1 - coefficient_hz(100)), places=14)
        self.assertGreater(result[256], 0)

    def test_slide_direction_uses_previous_output_not_previous_input(self):
        values = slide_reference([1, .75, .25], [2] * 3, [8] * 3)
        self.assertEqual(values[:2], [.5, .625])
        self.assertEqual(values[2], .578125)
        # The second input decreases, yet remains above previous OUTPUT.
        wrong_using_input_direction = .5 + (.75 - .5) / 8
        self.assertNotEqual(values[1], wrong_using_input_direction)

    def test_slide_abs_rate_clamp_and_noninteger_rates(self):
        for rate in (-1, -.5, 0, .5, 1):
            self.assertEqual(slide_reference([.25, -.5], [rate] * 2, [rate] * 2), [.25, -.5])
        self.assertEqual(slide_reference([1] * 8, [-4] * 8, [-8] * 8),
                         slide_reference([1] * 8, [4] * 8, [8] * 8))
        result = slide_reference([1] * 4, [2.5] * 4, [8] * 4)
        for i, value in enumerate(result):
            self.assertAlmostEqual(value, 1 - .6 ** (i + 1), places=14)

    def test_delta_history_crosses_vector_boundaries(self):
        source = [0] * 255 + [1, -.5] + [0] * 255
        output = delta_reference(source)
        self.assertEqual(output[255:258], [1, -1.5, .5])
        self.assertEqual(sum(output), 0)
        self.assertEqual(delta_reference([.5, .5]), [.5, 0])

    def test_sah_requires_rising_crossing_and_holds_sustained_high(self):
        output, indices = sah_reference([1, 2, 3, 4, 5, 6], [0, .5, 1, 1, .5, 1], [.5] * 6)
        self.assertEqual(indices, [2, 5])
        self.assertEqual(output, [0, 0, 3, 3, 3, 6])

    def test_sah_threshold_change_compares_both_triggers_to_current_threshold(self):
        output, indices = sah_reference([1, 2, 3, 4], [.25] * 4, [.5, .5, 0, 0])
        self.assertEqual(indices, [])
        self.assertEqual(output, [0] * 4)
        # Raising the threshold can expose a genuine crossing that an old
        # cached "above" boolean would incorrectly suppress.
        output, indices = sah_reference([1, 2], [.25, .75], [0, .5])
        self.assertEqual(indices, [0, 1])
        self.assertEqual(output, [1, 2])

    def test_sah_initial_history_and_source_zero_sign_are_explicit(self):
        self.assertEqual(sah_reference([1], [0], [-.5])[0], [0])
        self.assertEqual(sah_reference([1], [0], [-.5], previous_trigger=-1)[0], [1])
        result, indices = sah_reference([-0.0, 1], [1, 1], [0, 0])
        self.assertEqual(indices, [0])
        self.assertEqual([bits(v) for v in result], [0x80000000, 0x80000000])

    def test_catalog_binding_keeps_stereo_histories_and_parameter_events(self):
        fixture = {'parameters': [{'id': 'cutoff', 'initial': 1000, 'minimum': -1000, 'maximum': 100000}],
                   'semantic': {'kind': 'onepole-hz', 'initial': 0, 'output_models': [
                       {'channel': 0, 'data_channel': 0, 'cutoff': {'kind': 'parameter', 'id': 'cutoff'}},
                       {'channel': 1, 'data_channel': 1, 'cutoff': {'kind': 'parameter', 'id': 'cutoff'}}]}}
        case = {'blocks': 2, 'events': [{'block': 1, 'id': 'cutoff', 'value': 100, 'form': 'actual'}]}
        inputs = ([1] * 512, [0] * 512)
        expected, _ = expected_outputs(fixture, case, inputs)
        self.assertTrue(analyse(fixture, case, inputs, expected)['passed'])
        self.assertEqual(expected[1], [0] * 512)
        wrong = (expected[0], expected[0])
        self.assertFalse(analyse(fixture, case, inputs, wrong)['passed'])
        planes = parameter_planes(fixture, case, 512)
        self.assertEqual(planes['cutoff'][255:257], [1000, 100])

    def test_exact_sah_output_rejects_wrong_hold_and_observer_words(self):
        fixture = {'parameters': [], 'semantic': {'kind': 'sah', 'held_initial': 0,
                    'previous_trigger_initial': 0, 'output_models': [
                    {'channel': 0, 'data_channel': 0, 'trigger_channel': 1, 'threshold': {'kind': 'literal', 'value': 0}},
                    {'channel': 1, 'copy_input': 0}]}}
        source = [wire32(i / 256) for i in range(256)]
        trigger = [1] * 256
        expected = ([source[0]] * 256, source)
        self.assertTrue(analyse(fixture, {'blocks': 1}, (source, trigger), expected)['passed'])
        self.assertFalse(analyse(fixture, {'blocks': 1}, (source, trigger), (source, source))['passed'])

    def test_unknown_modes_nonfinite_inputs_and_incomplete_captures_reject(self):
        for call in (lambda: onepole_reference([1], [math.nan]),
                     lambda: slide_reference([1], [1, 2], [1]),
                     lambda: delta_reference([]), lambda: sah_reference([1], [math.inf], [0])):
            with self.assertRaises(ValueError):
                call()
        fixture = {'parameters': [], 'semantic': {'kind': 'delta', 'previous_input_initial': 0,
                   'output_models': [{'channel': 0, 'data_channel': 0}, {'channel': 1, 'data_channel': 1}]}}
        with self.assertRaises(ValueError):
            expected_outputs(fixture, {'blocks': 2}, ([0] * 256, [0] * 256))
        wrong = copy.deepcopy(fixture)
        wrong['semantic']['kind'] = 'unknown'
        with self.assertRaises(ValueError):
            expected_outputs(wrong, {}, ([0] * 256, [0] * 256))


if __name__ == '__main__':
    unittest.main()
