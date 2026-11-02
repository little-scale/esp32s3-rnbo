# SPDX-License-Identifier: MIT
"""Admission and source-boundary checks against locally generated fixtures."""
import json
from pathlib import Path
import unittest

from bounded_filters import _method
from float32_audio import float32_audio
from prepare import cpp_code_mask


class Float32AudioV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        report = root / "build/object-qualification/remaining-2/report.json"
        if not report.is_file():
            raise unittest.SkipTest("Generate the authorized object fixtures first")
        records = json.loads(report.read_text())["fixtures"]
        cls.sources = {r["fixture"]["id"]: (Path(next(v for v in r["variants"] if v["variant"] == "strict")["prepared"]) / "rnbo_source.h").read_bytes()
                       for r in records}

    @staticmethod
    def outside(source, methods):
        text = source.decode(); masked = cpp_code_mask(text)
        spans = [_method(masked, m["method"]) for m in methods]
        for start, end in sorted(spans, reverse=True):
            text = text[:start] + text[end:]
        return text

    def test_new_forms_require_v2_and_preserve_every_other_source_byte(self):
        for name in ("cycle-scalar", "filters-fixed", "filters-scalar", "filters-signal", "arithmetic-dc"):
            with self.subTest(fixture=name):
                source = self.sources[name]
                with self.assertRaisesRegex(ValueError, "unsupported RNBO"):
                    float32_audio(source, code_mask=cpp_code_mask, profile="float32-audio-v1")
                candidate, report = float32_audio(source, code_mask=cpp_code_mask, profile="float32-audio-v2")
                self.assertEqual(self.outside(source, report["methods"]), self.outside(candidate, report["methods"]))
                self.assertEqual(sum(m["local_float32_ms_to_samples"] for m in report["methods"]), 0)
                self.assertEqual(sum(m["retained_double_ms_to_samples"] for m in report["methods"]),
                                 2 if name.startswith("filters-") else 0)

    def test_mutated_algorithm_or_coefficients_are_rejected(self):
        mutations = (("cycle-scalar", b"262143", b"262142"),
                     ("filters-fixed", b"number __fbGain = 0.7;", b"number __fbGain = 0.8;"),
                     ("filters-scalar", b"0.99", b"0.98"),
                     ("filters-signal", b"(__delayTime > 40.0", b"(__delayTime > 41.0"),
                     ("arithmetic-dc", b"in1[(Index)i] + in2", b"in1[(Index)i] - in2"))
        for name, old, new in mutations:
            with self.subTest(fixture=name):
                source = self.sources[name]; changed = source.replace(old, new, 1)
                self.assertNotEqual(source, changed)
                with self.assertRaisesRegex(ValueError, "unsupported RNBO"):
                    float32_audio(changed, code_mask=cpp_code_mask, profile="float32-audio-v2")

    def test_existing_admitted_forms_produce_identical_v1_and_v2_bytes(self):
        for name in ("cycle-fixed", "cycle-signal", "scale-linear", "delay-crossfade"):
            source = self.sources[name]
            old, _ = float32_audio(source, code_mask=cpp_code_mask, profile="float32-audio-v1")
            new, _ = float32_audio(source, code_mask=cpp_code_mask, profile="float32-audio-v2")
            self.assertEqual(old, new, name)


if __name__ == "__main__": unittest.main()
