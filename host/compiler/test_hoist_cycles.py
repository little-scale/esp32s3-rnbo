# SPDX-License-Identifier: MIT
"""Check candidate hoists against actual local generated RNBO methods.

Generated algorithm bodies are not vendored. Positive corpus checks skip when
the original authorized fixture/export preparations have not been generated.
"""
from pathlib import Path
import re
import unittest

from bounded_filters import _method
from hoist_cycles import hoist_cycles
from prepare import cpp_code_mask

ROOT = Path(__file__).resolve().parents[2]


class RuntimeAdmissionTests(unittest.TestCase):
    def test_unknown_runtime_is_rejected_before_any_source_adaptation(self):
        with self.assertRaisesRegex(ValueError, "macro/type runtime"):
            hoist_cycles(b"", b"unknown", b"unknown", code_mask=cpp_code_mask)


class HoistCyclesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.references = {
            "strict": ROOT / "build/research/cycle-invariant-hoist/prepared/reference/float32-strict",
            "v2": ROOT / "build/research/cycle-invariant-hoist/prepared/reference/float32-audio-v2",
            "drone": ROOT / "build/user-patches/3sawsDrone3/prepared-cap40-f32audio-no-mtof-table-v2",
        }
        cls.candidates = {
            "strict": ROOT / "build/research/cycle-invariant-hoist/prepared/candidate/float32-strict",
            "v2": ROOT / "build/research/cycle-invariant-hoist/prepared/candidate/float32-audio-v2",
            "drone": ROOT / "build/research/drone-invariant-hoist/prepared/candidate",
        }
        cls.signals = [
            ROOT / "build/object-qualification/remaining-2/prepared/cycle-signal/strict",
            ROOT / "build/object-qualification/audio-v2-qualified/prepared/cycle-signal/float32-audio-v2",
        ]
        for path in [*cls.references.values(), *cls.candidates.values(), *cls.signals]:
            if not (path / "rnbo_source.h").is_file():
                raise unittest.SkipTest("Prepare the original local cycle/drone qualification corpus first")
        cls.sources = {name: (path / "rnbo_source.h").read_bytes() for name, path in cls.references.items()}
        cls.audio = (cls.references["strict"] / "common/RNBO_AudioSignal.h").read_bytes()
        cls.types = (cls.references["strict"] / "common/RNBO_Types.h").read_bytes()

    def transform(self, source):
        return hoist_cycles(source, self.audio, self.types, code_mask=cpp_code_mask)

    def test_exact_private_proof_sources_reproduced_for_both_profiles_and_drone(self):
        for name, source in self.sources.items():
            with self.subTest(name=name):
                actual, report = self.transform(source)
                self.assertEqual(actual, (self.candidates[name] / "rnbo_source.h").read_bytes())
                self.assertEqual(report["hoisted_conversion_count"], 6 if name == "drone" else 2)
                self.assertEqual(report["changed_method_count"], 5 if name == "drone" else 1)
                self.assertEqual(report["skipped_conversion_count"], 0)
                self.assertTrue(report["outside_changed_methods_identical"])

    def test_original_macro_calls_leave_loop_but_original_phase_branch_stays(self):
        for source in self.sources.values():
            actual, report = self.transform(source)
            text = actual.decode(); mask = cpp_code_mask(text)
            for method in report["methods"]:
                a, b = _method(mask, method["method"]); body = text[a:b]
                loop = re.search(r"\bfor\s*\(", cpp_code_mask(body)).start()
                self.assertEqual(body[loop:].count("uint32_trunc("), 0)
                self.assertEqual(body[:loop].count("uint32_trunc("), len(method["hoisted"]))
                if method["phase_input"] == "scalar":
                    condition = "if (phase_offset != 0 || 0 == 2)"
                    self.assertIn(condition, body[:loop]); self.assertIn(condition, body[loop:])
                self.assertNotIn("phase_trunc_f32", body)

    def test_both_signal_inputs_record_skips_and_preserve_every_source_byte(self):
        for path in self.signals:
            source = (path / "rnbo_source.h").read_bytes()
            actual, report = self.transform(source)
            self.assertEqual(actual, source)
            self.assertEqual(report["changed_method_count"], 0)
            self.assertEqual(report["hoisted_conversion_count"], 0)
            self.assertEqual(report["skipped_conversion_count"], 2)
            self.assertEqual({x["inlet"] for x in report["methods"][0]["skipped"]}, {"frequency", "phase_offset"})

    def test_unknown_mixed_scalar_signal_layouts_are_rejected(self):
        source = self.sources["strict"]
        for changed in (
            source.replace(b"number frequency,", b"const Sample * RNBO_RESTRICT frequency,", 1)
                  .replace(b"frequency * __cycle_tilde_01_f2i", b"frequency[(Index)i] * __cycle_tilde_01_f2i", 1),
            source.replace(b"number phase_offset,", b"const Sample * RNBO_RESTRICT phase_offset,", 1)
                  .replace(b"phase_offset != 0", b"phase_offset[(Index)i] != 0", 1)
                  .replace(b"phase_offset * 4294967296.0", b"phase_offset[(Index)i] * 4294967296.0", 1),
        ):
            with self.assertRaisesRegex(ValueError, "unsupported RNBO"):
                self.transform(changed)

    def test_changed_loop_limit_phase_condition_or_interpolation_is_rejected(self):
        for old, new in ((b"i < 256", b"i < 255"),
                         (b"phase_offset != 0 || 0 == 2", b"phase_offset >= 0 || 0 == 2"),
                         (b"3.81471181759574e-6", b"3.81471181759574e-5")):
            source = self.sources["strict"].replace(old, new, 1)
            self.assertNotEqual(source, self.sources["strict"])
            with self.assertRaisesRegex(ValueError, "unsupported RNBO"):
                self.transform(source)

    def test_comments_whitespace_and_literal_spelling_preserved_in_moved_expression(self):
        expression = b"phase_offset /* keep this comment */ *\n  4294967296.0"
        prefix = '// Unicode outside methods: phase π\nconst char *s="cycle_tilde_01_perform";\n'.encode()
        source = prefix + self.sources["strict"].replace(b"phase_offset * 4294967296.0", expression, 1)
        actual, report = self.transform(source)
        self.assertTrue(actual.startswith(prefix))
        self.assertIn(expression, actual)
        self.assertEqual(actual.count(b"keep this comment"), 1)
        self.assertEqual(report["methods"][0]["hoisted"][0]["expression"], b"uint32_trunc(".decode() + expression.decode() + ")")
        self.assertNotIn(b"4294967296.0f", actual)

    def test_generated_object_number_normalization_does_not_rewrite_names(self):
        source = self.sources["strict"].replace(b"cycle_tilde_01", b"cycle_tilde_99")
        actual, report = self.transform(source)
        expected = (self.candidates["strict"] / "rnbo_source.h").read_bytes().replace(b"cycle_tilde_01", b"cycle_tilde_99")
        self.assertEqual(actual, expected)
        self.assertEqual(report["methods"][0]["method"], "cycle_tilde_99_perform")

    def test_runtime_macro_and_type_pins_both_enforced(self):
        for audio, types in ((self.audio + b"\n", self.types), (self.audio, self.types + b"\n")):
            with self.assertRaisesRegex(ValueError, "macro/type runtime"):
                hoist_cycles(self.sources["strict"], audio, types, code_mask=cpp_code_mask)

    def test_duplicate_cycle_and_double_application_rejected(self):
        source = self.sources["strict"].decode(); a, b = _method(cpp_code_mask(source), "cycle_tilde_01_perform")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.transform((source + "\n" + source[a:b]).encode())
        actual, _ = self.transform(self.sources["strict"])
        with self.assertRaisesRegex(ValueError, "unsupported RNBO"):
            self.transform(actual)

    def test_source_without_cycles_is_explicit_unchanged_result(self):
        source = b'// No cycle methods\nvoid helper() { const char *s="cycle_unknown_perform"; }\n'
        actual, report = self.transform(source)
        self.assertEqual(actual, source)
        self.assertTrue(report["no_cycle_methods"])
        self.assertEqual(report["hoisted_conversion_count"], 0)


if __name__ == "__main__":
    unittest.main()
