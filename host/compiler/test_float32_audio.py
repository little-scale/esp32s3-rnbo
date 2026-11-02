# SPDX-License-Identifier: MIT
"""Use real local RNBO output to exercise optional storage/audio guards."""
import os
from pathlib import Path
import re
import unittest

from prepare import cpp_code_mask, float32_cycle, ExportError
from float32_delays import float32_delays
from float32_audio import float32_audio


class Float32AudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        path = Path(os.environ.get("RNBO_S3_TEST_AUDIO_EXPORT", cls.root / "build/user-patches/3sawsDrone3/prepared-cap40")) / "rnbo_source.h"
        if not path.is_file(): raise unittest.SkipTest("Prepare the local authorized cap40 patch first")
        cls.source = path.read_bytes()

    def test_storage_changes_only_six_constructor_reference_pairs(self):
        prepared, report = float32_delays(self.source, code_mask=cpp_code_mask)
        self.assertEqual(report["constructor_reference_pairs"], 6)
        self.assertEqual(report["buffer_data_bytes_saved"], 33280)
        self.assertEqual(prepared.replace(b"Float32Buffer", b"Float64Buffer"), self.source)

    def test_external_or_changed_reader_or_unpaired_ring_is_rejected(self):
        owner = re.search(rb"this->comb_tilde_01_feedForward_bufferobj = initDataRef\([\s\S]*?\);", self.source)[0]
        external = self.source.replace(owner, owner.replace(b"true,", b"false,"), 1)
        with self.assertRaises(ValueError): float32_delays(external, code_mask=cpp_code_mask)
        for old, new in ((b"Int interp)", b"Int unknown)"),
                         (b"new Float64Buffer(this->comb_tilde_01_feedForward_bufferobj)", b"new Float64Buffer(other)")):
            changed = self.source.replace(old, new, 1)
            self.assertNotEqual(changed, self.source)
            with self.subTest(old=old):
                with self.assertRaises(ValueError): float32_delays(changed, code_mask=cpp_code_mask)

    def test_minimum_two_sample_ring_resource_accounting(self):
        source = self.source.replace(b"return 1766;", b"return 1;")
        _, report = float32_delays(source, code_mask=cpp_code_mask)
        for ring in report["rings"]:
            if ring["requested_samples"] == 1:
                self.assertEqual(ring["frames"], 2)
                self.assertEqual(ring["after_data_bytes"], 8)

    def test_audio_catalog_and_scheduler_boundary(self):
        prepared, report = float32_audio(self.source, code_mask=cpp_code_mask, profile="float32-audio-v1")
        self.assertEqual(len(report["methods"]), 30)
        self.assertEqual(sum(m["local_float32_ms_to_samples"] for m in report["methods"]), 2)
        self.assertIn(b"rnbo_exp(.057762265f * (midivalue - 69.0f))", prepared)
        self.assertIn(b"number mstosamps(MillisecondTime ms) {\n    return ms * this->sr * 0.001;\n}", prepared)
        self.assertIn(b"((number)((__delayTime > 40.0f ? 40.0f : __delayTime)) * this->sr * 0.001f)", prepared)
        # Strip exactly the declared method spans independently; every byte of
        # all other source, including scheduling and setup, must be preserved.
        def outside(source):
            text = source.decode(); masked = cpp_code_mask(text); spans = []
            for method in report["methods"]:
                match = re.search(r"\b(?:void|number)\s+" + re.escape(method["method"]) + r"\s*\(", masked)
                opening = masked.index("{", match.end()); cursor = opening+1; depth = 1
                while depth:
                    if masked[cursor] == "{": depth += 1
                    if masked[cursor] == "}": depth -= 1
                    cursor += 1
                spans.append((match.start(),cursor))
            for start,end in sorted(spans,reverse=True): text = text[:start] + text[end:]
            return text
        self.assertEqual(outside(self.source), outside(prepared))

    def test_unknown_audio_constant_and_already_transformed_reject(self):
        for source in (self.source.replace(b".057762265", b".057762266"),
                       float32_audio(self.source, code_mask=cpp_code_mask, profile="float32-audio-v1")[0]):
            with self.assertRaisesRegex(ValueError, "unsupported RNBO"):
                float32_audio(source, code_mask=cpp_code_mask, profile="float32-audio-v1")

    def test_comments_strings_and_raw_strings_preserved(self):
        prefix = b'// void cycle_fake_perform() {} 0.2\nconst char *a=R"tag({ .057762265 })tag";\ndouble time=0.001;\n'
        source = prefix + self.source.replace(b"RNBO_UNUSED(n);", b'RNBO_UNUSED(n); /* } " */', 1)
        prepared, _ = float32_audio(source, code_mask=cpp_code_mask, profile="float32-audio-v1")
        self.assertTrue(prepared.startswith(prefix))
        self.assertIn(b'/* } " */', prepared)

    def test_v1_remains_strict_while_v2_admits_reviewed_fixed_and_scalar_forms(self):
        with self.assertRaises(ExportError): float32_cycle(self.source)
        _, report = float32_audio(self.source, code_mask=cpp_code_mask, profile="float32-cycle-v2")
        self.assertEqual(len(report["methods"]), 5)

    def test_real_signal_frequency_and_phase_fixture(self):
        path = self.root / "build/exports/cycle-signal/rnbo_source.h"
        if not path.is_file(): self.skipTest("Export the original cycle-signal fixture first")
        prepared, report = float32_audio(path.read_bytes(), code_mask=cpp_code_mask, profile="float32-cycle-v2")
        self.assertEqual(len(report["methods"]), 1)
        self.assertIn(b"uint32_trunc(frequency[(Index)i] *", prepared)


if __name__ == "__main__": unittest.main()
