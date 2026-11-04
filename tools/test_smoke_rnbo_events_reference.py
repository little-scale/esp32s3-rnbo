# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'smoke_rnbo_events', ROOT / 'tests/fixtures/smoke/rnbo-events/reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class RNBOEventsReferenceTests(unittest.TestCase):
    def test_actual_boundary_schedule_has_twenty_callbacks_ordered_duplicates_and_holds(self):
        self.assertEqual(reference.PREPARE_ZERO_WARM_BLOCKS, 0)
        self.assertEqual((reference.MANUAL_WARM_CALLS, reference.TIMED_CALLS), (4, 16))
        for model in reference.MODELS:
            with self.subTest(model=model):
                events = reference.parameter_events(model)
                self.assertEqual(len(events), 21)
                self.assertEqual(events[0], {'before_call': 0, 'id': 'drive', 'value': 1.})
                self.assertEqual([e['before_call'] for e in events], sorted(e['before_call'] for e in events))
                blocks = reference.reference_blocks(model, reference.input_words())
                self.assertEqual(len(blocks), 20)
                self.assertTrue(all(len(block) == 512 for block in blocks))
                self.assertEqual(blocks[0], reference.reference_words(model, reference.input_words()))
                self.assertEqual(blocks[6], blocks[7])  # unchanged resend
                self.assertEqual(blocks[12], blocks[13])  # no event means hold
                self.assertEqual(blocks[13], blocks[14])
                self.assertEqual(reference.ABSOLUTE_TOLERANCES[model], 0)

    def test_last_same_call_event_wins_for_math_fraction_relation_and_boolean(self):
        cases = ((158, 10, 3.), (154, 10, .75), (162, 10, .75),
                 (165, 10, 1.), (166, 10, 0.), (167, 10, 1.),
                 (156, 16, 1.), (157, 16, 0.), (169, 16, 1.), (170, 16, 0.))
        for model, call, expected in cases:
            with self.subTest(model=model, call=call):
                blocks = reference.reference_blocks(model, reference.input_words())
                self.assertEqual(set(blocks[call][::2]), {reference.word(expected)})
        self.assertEqual([e['value'] for e in reference.parameter_events(165) if e['before_call'] == 10], [3., 1., 2.])

    def test_fixed_binary_operands_rounding_signed_fraction_and_sign(self):
        first = {148: 1., 149: -1., 150: 1., 151: 1., 152: 1., 153: 2.,
                 154: 0., 155: 1., 156: 1., 157: 0., 158: 3., 159: -1.,
                 160: 2., 161: .5, 162: 1., 163: 1., 164: 2., 165: 0.,
                 166: 0., 167: 1., 168: 1., 169: 1., 170: 0.}
        for model, expected in first.items():
            with self.subTest(model=model):
                out = reference.reference_words(model, reference.input_words())
                self.assertEqual(set(out[::2]), {reference.word(expected)})
        round_blocks = reference.reference_blocks(153, reference.input_words())
        self.assertEqual(reference.value(round_blocks[1][0]), -2.)
        self.assertEqual(reference.value(round_blocks[5][0]), -2.)
        self.assertEqual(reference.value(round_blocks[3][0]), 0.)
        fract = reference.reference_blocks(154, reference.input_words())
        self.assertEqual(reference.value(fract[5][0]), -.5)
        # OR has cold0, so a zero drive must produce0, not a trivial constant1.
        self.assertEqual(reference.reference_blocks(169, reference.input_words())[2][0], 0)

    def test_right_pilot_is_raw_exact_and_left_does_not_depend_on_audio_input(self):
        inputs = reference.input_words()
        changed = tuple((0x7f7fffff if n % 2 == 0 else w) for n, w in enumerate(inputs))
        for model in (148, 153, 165, 169):
            blocks = reference.reference_blocks(model, inputs)
            self.assertEqual(blocks, reference.reference_blocks(model, changed))
            for block in blocks:
                self.assertEqual(block[1::2], inputs[1::2])
        pilot = set(inputs[1::2])
        self.assertTrue({0, 0x80000000, 1, 0x80000001, 0x00800000, 0x7f7fffff}.issubset(pilot))
        self.assertTrue(reference.PILOT_RIGHT_BIT_EXACT)

    def test_bad_shapes_models_nonfinite_and_unsorted_events_reject(self):
        for model, inputs in ((True, reference.input_words()), (171, reference.input_words()),
                              (148, (0, 0)), (148, (True,) + reference.input_words()[1:]),
                              (148, (0x7fc00000,) + reference.input_words()[1:])):
            with self.subTest(model=model), self.assertRaises(ValueError):
                reference.reference_blocks(model, inputs)
        for call_count in (True, 0, 21, .5):
            with self.assertRaises(ValueError):
                reference.reference_blocks(148, reference.input_words(), call_count)
        for frames in (True, 1, 255, 257):
            with self.assertRaises(ValueError): reference.input_words(frames)
        bad = reference.parameter_events(148)
        bad[2], bad[3] = bad[3], bad[2]
        with patch.object(reference, 'parameter_events', return_value=bad):
            with self.assertRaises(ValueError): reference.reference_blocks(148, reference.input_words())
        independent = reference.parameter_events(148)
        independent[0]['value'] = 7.
        self.assertEqual(reference.parameter_events(148)[0]['value'], 1.)


if __name__ == '__main__':
    unittest.main()
