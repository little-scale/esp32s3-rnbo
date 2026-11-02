# SPDX-License-Identifier: MIT
"""Independent truth and adversarial checks for second-wave measurements."""
import json
import math
from pathlib import Path
import random
import unittest

from qualify_wave2 import average_truth,input_signal,semantics


class WaveTwoModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).resolve().parents[2]/"tests/fixtures/objects/wave2/catalog.json"
        cls.fixtures={f["id"]:f for f in json.loads(path.read_text())["fixtures"]}

    def test_average_available_history_differs_from_warmed_zero_history(self):
        self.assertEqual(average_truth([1,0,0,0],3,0),[1,.5,1/3,0])
        self.assertEqual(average_truth([1,0,0,0],3,3),[1/3,1/3,1/3,0])

    def test_average_oracle_rejects_wrong_reset_and_wrong_window(self):
        fixture=self.fixtures["average-window"];case={"parameters":{"window":64}}
        inputs=input_signal("impulse-step-v1",256)
        correct=tuple(average_truth(ch,64,0) for ch in inputs)
        self.assertTrue(semantics(fixture,case,correct,inputs)["passed"])
        delayed=tuple([0]+list(ch[:-1]) for ch in correct)
        for wrong in (tuple(average_truth(ch,64,64) for ch in inputs),tuple(average_truth(ch,16,16) for ch in inputs),delayed):
            self.assertFalse(semantics(fixture,case,wrong,inputs)["passed"])

    def test_average_error_is_recorded_without_widening_limit(self):
        fixture=self.fixtures["average-window"];case={"parameters":{}}
        inputs=input_signal("mixed-tone-v1",256)
        correct=tuple(average_truth(ch,16,16) for ch in inputs)
        biased=tuple([x+1e-5 for x in ch] for ch in correct)
        report=semantics(fixture,case,biased,inputs)
        self.assertFalse(report["passed"])
        self.assertEqual(report["declared_maximum_absolute_error"],2e-6)
        self.assertGreater(max(report["maximum_absolute_errors"]),9e-6)

    def test_biquad_identity_and_wrong_impulse_response(self):
        fixture=self.fixtures["biquad-response"];case={"parameters":{"a0":1,"a1":0,"a2":0,"b1":0,"b2":0}}
        inputs=input_signal("impulse-step-v1",4096)
        self.assertTrue(semantics(fixture,case,inputs,inputs)["passed"])
        with self.assertRaisesRegex(ValueError,"difference-equation"):
            semantics(fixture,case,([0]*4096,inputs[1]),inputs)

    def test_line_accepts_one_sample_endpoint_policy_but_rejects_double_duration(self):
        fixture=self.fixtures["line-timing"];case={"parameters":{"target":1,"milliseconds":10},"events":[]}
        target=[1]*4096;correct=[min((i+1)/441,1) for i in range(4096)]
        self.assertTrue(semantics(fixture,case,(correct,target),None)["passed"])
        wrong=[min((i+1)/882,1) for i in range(4096)]
        with self.assertRaisesRegex(ValueError,"slope"):
            semantics(fixture,case,(wrong,target),None)

    def test_phasor_rejects_a_different_rate(self):
        fixture=self.fixtures["phase-pulse"];count=8192
        phase=[(i*220/44100)%1 for i in range(count)]
        pulses=[1 if (i%441)/441<.25 else 0 for i in range(count)]
        with self.assertRaisesRegex(ValueError,"phase rate"):
            semantics(fixture,{"parameters":{}},(phase,pulses),None)

    def test_noise_rejects_zero_variance_and_white_as_pink(self):
        fixture=self.fixtures["noise-colour"];case={"parameters":{}}
        with self.assertRaisesRegex(ValueError,"zero variance"):
            semantics(fixture,case,([0]*4096,[0]*4096),None)
        generator=random.Random(12345);white=[generator.uniform(-1,1) for _ in range(32768)]
        with self.assertRaisesRegex(ValueError,"colour"):
            semantics(fixture,case,(white,white),None)

    def test_nonlinear_wrap_upper_boundary_and_fractional_power(self):
        fixture=self.fixtures["nonlinear-domains"];case={"parameters":{}}
        source=([0,0,0],[1,.5,-1.5]);correct=([0,0,0],[0,.25,.25])
        self.assertTrue(semantics(fixture,case,correct,source)["passed"])
        with self.assertRaisesRegex(ValueError,"domain"):
            semantics(fixture,case,([0,0,0],[1,.25,.25]),source)


if __name__=="__main__":unittest.main()
