# SPDX-License-Identifier: MIT
import importlib.util
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'smoke_gen_stateful', ROOT / 'tests/fixtures/smoke/gen-stateful/reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def vector(left, right):
    return tuple(reference.word(x) for _ in range(256) for x in (left, right))


class GenStatefulReferenceTests(unittest.TestCase):
    def test_epoch_twenty_continuous_fixed256_blocks_and_finite_domains(self):
        self.assertEqual(reference.PREPARE_ZERO_WARM_BLOCKS, 0)
        self.assertEqual((reference.MANUAL_WARM_CALLS, reference.TIMED_CALLS), (4, 16))
        for model in reference.MODELS:
            with self.subTest(model=model):
                inputs = reference.case_input_words(model)
                outputs = reference.reference_blocks(model, inputs)
                self.assertEqual(len(outputs), 20)
                self.assertTrue(all(len(block) == 512 for block in outputs))
                self.assertTrue(all(math.isfinite(reference.value(w)) for block in outputs for w in block))
                self.assertEqual(outputs[0], reference.reference_words(model, inputs))
                if model == 113:
                    self.assertLess(max(abs(reference.value(w)) for block in outputs for w in block), 8)

    def test_delta_and_change_use_the_previous_input_not_previous_output(self):
        inputs = list(vector(0, 0))
        inputs[:8] = [reference.word(x) for x in (.25, -.5, .25, -.5, -.5, .25, -.5, .25)]
        out = reference.reference_words(104, inputs)
        self.assertEqual(tuple(reference.value(w) for w in out[:8]), (.25, -.5, 0., 0., -.75, .75, 0., 0.))
        out = reference.reference_words(105, inputs)
        self.assertEqual(tuple(reference.value(w) for w in out[:8]), (1., -1., 0., 0., -1., 1., 0., 0.))

    def test_latch_and_sah_distinguish_negative_controls_and_rising_crossings(self):
        inputs = list(vector(0, 0))
        # left data .25/.5/.75/1 with control -1/+1/+1/0
        inputs[:8] = [reference.word(x) for x in (.25, -1., .5, 1., .75, 1., 1., 0.)]
        latch = reference.reference_words(106, inputs)
        sah = reference.reference_words(108, inputs)
        self.assertEqual(tuple(reference.value(w) for w in latch[:8:2]), (.25, .5, .75, .75))
        self.assertEqual(tuple(reference.value(w) for w in sah[:8:2]), (0., .5, .5, .5))
        half = reference.reference_words(109, vector(.5, .5))
        self.assertEqual(half, (0,) * 512)  # equality is not an upward crossing

    def test_signal_threshold_uses_current_threshold_and_raw_previous_control(self):
        inputs = list(vector(0, 0))
        # Control stays .5 while its threshold drops .75 -> .25: no control crossing.
        # Then control rises .5 ->1 against current threshold .75: a valid crossing.
        inputs[:6] = [reference.word(x) for x in (.75, .5, .25, .5, .75, 1.)]
        out = reference.reference_words(110, inputs)
        self.assertEqual(tuple(reference.value(w) for w in out[:6:2]), (0., 0., .75))

    def test_ideal_slide_dcblock_and_accumulator_landmarks(self):
        w = reference.word
        self.assertEqual(reference.reference_words(111, vector(1, -1))[:6],
                         tuple(w(x) for x in (.5, -.25, .75, -.4375, .875, -.578125)))
        self.assertEqual(reference.reference_words(112, vector(1, -1))[:6],
                         tuple(w(x) for x in (.25, -.5, .4375, -.75, .578125, -.875)))
        dc = reference.reference_words(107, vector(1, 0))
        self.assertEqual(dc[:6], (w(1), 0, w(.9997), 0, w(.9997 ** 2), 0))
        accum = reference.reference_blocks(113, vector(1. / 1024, -1. / 1024), 2)
        self.assertEqual(accum[0][:2], (w(1. / 1024), w(-1. / 1024)))
        self.assertEqual(accum[0][-2:], (w(.25), w(-.25)))
        self.assertEqual(accum[1][:2], (w(.25 + 1. / 1024), w(-.25 - 1. / 1024)))

    def test_counter_literal_periods_and_all_persistence_witnesses(self):
        counter = reference.reference_blocks(114, vector(0, 0), 2)
        self.assertEqual(tuple(reference.value(w) for w in counter[0][:14:2]), (1, 2, 3, 4, 5, 6, 0))
        self.assertEqual(tuple(reference.value(w) for w in counter[0][1:11:2]), (1, 2, 3, 4, 0))
        self.assertEqual(tuple(reference.value(w) for w in counter[1][:2]), (5, 2))
        for model in (104, 105, 106, 108, 109, 110, 113, 114):
            with self.subTest(model=model):
                blocks = reference.reference_blocks(model, reference.case_input_words(model), 2)
                self.assertNotEqual(blocks[1], blocks[0], 'A reset at256 must be distinguishable')
                self.assertNotEqual(blocks[1][:2], blocks[0][:2])

    def test_invalid_domains_shapes_models_and_call_counts_reject(self):
        for model, inputs in ((True, vector(0, 0)), (115, vector(0, 0)),
                              (104, (0, 0)), (104, vector(2, 0)),
                              (113, vector(.25, 0)), (104, (True,) + vector(0, 0)[1:]),
                              (104, (0x7fc00000,) + vector(0, 0)[1:])):
            with self.subTest(model=model), self.assertRaises(ValueError):
                reference.reference_blocks(model, inputs)
        for count in (True, 0, 21, 1.5):
            with self.assertRaises(ValueError):
                reference.reference_blocks(104, vector(0, 0), count)
        for frames in (1, 255, 257, True):
            with self.assertRaises(ValueError):
                reference.input_words(frames)


if __name__ == '__main__':
    unittest.main()
