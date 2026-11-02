# SPDX-License-Identifier: MIT
"""The optional delay cap must leave precision and conversion intact or stop."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

from bounded_filters import bound_filter_delays
from prepare import cpp_code_mask, prepare

ROOT = Path(__file__).resolve().parents[2]


class BoundedFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export = Path(os.environ.get("RNBO_S3_FILTER_TEST_EXPORT", ROOT / "build/user-patches/3sawsDrone3/export"))
        if not (cls.export / "rnbo_source.h").is_file():
            raise unittest.SkipTest("Export the authorized local3sawsDrone3 patch or set RNBO_S3_FILTER_TEST_EXPORT")
        cls.source = (cls.export / "rnbo_source.h").read_bytes()

    def adapt(self, source=None, cap=40):
        return bound_filter_delays(self.source if source is None else source, cap, code_mask=cpp_code_mask)

    def test_two_double_rings_per_filter_and_only_cap_and_capacity_change(self):
        adapted, change = self.adapt()
        self.assertEqual(change["maximum_ms"], 40)
        self.assertEqual(change["input_sha256"], hashlib.sha256(self.source).hexdigest())
        restored = adapted
        for item in change["objects"]:
            self.assertEqual(len(item["buffers"]), 2)
            for buffer in item["buffers"]:
                self.assertEqual((buffer["sample_bytes"], buffer["frames"], buffer["data_bytes"]), (8, 2048, 16384))
                self.assertEqual(buffer["maximum_samples_with_margin"], 1766)
                prefix = buffer["name"].encode()
                pattern = rb"(number " + re.escape(prefix) + rb"_evaluateSizeExpr\([^)]*\)\s*\{[^}]*return )1766;"
                restored, count = re.subn(pattern, rb"\g<1>44100;", restored)
                self.assertEqual(count, 1)
        restored = restored.replace(b"(__delayTime > 40.0 ? 40.0 : __delayTime)", b"__delayTime")
        # Unlike a perceptual/numeric check, this proves every other source byte,
        # including Float64 buffers, scheduler and mstosamps, is preserved.
        self.assertEqual(restored, self.source)

    def test_changed_algorithm_storage_or_allocator_paths_fail_closed(self):
        changes = [
            (b"this->mstosamps(__delayTime)", b"(__delayTime * 44.1f)"),
            (b"number ov = tmp + ff * __ffGain + fb * __fbGain;", b"number ov = tmp + ff + fb;"),
            (b"number comb_tilde_01_feedForward_evaluateSizeExpr(number samplerate, number vectorsize) {\n    RNBO_UNUSED(vectorsize);\n    RNBO_UNUSED(samplerate);\n    return 44100;",
             b"number comb_tilde_01_feedForward_evaluateSizeExpr(number samplerate, number vectorsize) {\n    RNBO_UNUSED(vectorsize);\n    RNBO_UNUSED(samplerate);\n    return 48000;"),
            (b"nextpoweroftwo(allocatedSizeInSamples)", b"allocatedSizeInSamples + 1"),
            (b"Float64BufferRef comb_tilde_01_feedBack_buffer", b"Float32BufferRef comb_tilde_01_feedBack_buffer"),
            (b"this->comb_tilde_01_feedBack_buffer->setSize(allocatedSizeInSamples);", b"this->comb_tilde_01_feedBack_buffer->setSize(65536);"),
        ]
        for old, new in changes:
            self.assertIn(old, self.source)
            with self.subTest(change=old), self.assertRaises(ValueError):
                self.adapt(self.source.replace(old, new, 1))
        prepared, _ = self.adapt()
        with self.assertRaises(ValueError): self.adapt(prepared)

    def test_invalid_caps_and_missing_filters_are_rejected(self):
        for cap in (0, -1, float("nan"), float("inf"), 1000.001, True, "40"):
            with self.subTest(cap=cap), self.assertRaises(ValueError): self.adapt(cap=cap)
        with self.assertRaises(ValueError): self.adapt(b"void process() {}")

    def test_comments_and_literals_cannot_supply_a_missing_kernel_or_buffer(self):
        prefix = (b'// void comb_tilde_99_perform() {}\n'
                  b'const char *s=R"x(void comb_tilde_98_perform(){ return 44100; })x";\n')
        adapted, change = self.adapt(prefix + self.source)
        self.assertTrue(adapted.startswith(prefix))
        self.assertEqual(len(change["objects"]), 2)
        # A removed real declaration cannot be replaced by identical comment text.
        old = b"Float64BufferRef comb_tilde_01_feedBack_buffer;"
        with self.assertRaises(ValueError): self.adapt(self.source.replace(old, b"/*" + old + b"*/"))

    def test_preparation_is_explicit_and_provenance_retains_original_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            strict = Path(temporary) / "strict"; bounded = Path(temporary) / "bounded"
            baseline = prepare(self.export, strict, "rnbos3patch", "main")
            capped = prepare(self.export, bounded, "rnbos3patch", "main", filter_delay_max_ms=40)
            self.assertNotIn("filter_delay_max_ms", baseline)
            self.assertEqual(capped["filter_delay_max_ms"], 40)
            self.assertEqual(baseline["source_tree_sha256"], capped["source_tree_sha256"])
            self.assertEqual((strict / "rnbo_source.h").read_bytes(), self.source)
            self.assertEqual((bounded / "originals/rnbo_source.h").read_bytes(), self.source)
            provenance = json.loads((bounded / "provenance.json").read_text())
            change = provenance["adaptations"][-1]
            self.assertEqual(change["name"], "rnbo-1.4.4-filter-delay-cap-v1")
            self.assertEqual(change["buffer_data_bytes"], 65536)
            self.assertEqual(provenance["compiler_helpers_sha256"]["bounded_filters.py"], change["transformer_sha256"])

    def test_real_fixed_scalar_signal_comb_and_allpass_variants(self):
        fixture = ROOT / "build/bounded-filter-fixtures/export/rnbo_source.h"
        if not fixture.is_file(): self.skipTest("Export the local fixed/scalar/signal filter fixture first")
        adapted, change = self.adapt(fixture.read_bytes(), cap=8)
        self.assertEqual(len(change["objects"]), 6)
        self.assertEqual(sum(len(item["buffers"]) for item in change["objects"]), 12)
        for item in change["objects"]:
            for buffer in item["buffers"]:
                self.assertEqual(buffer["maximum_samples_with_margin"], 355)
                self.assertEqual(buffer["frames"], 512)
        self.assertIn(b"this->mstosamps((16 > 8.0 ? 8.0 : 16))", adapted)
        self.assertIn(b"this->mstosamps((delayTime > 8.0 ? 8.0 : delayTime))", adapted)
        self.assertIn(b"this->mstosamps((delayTime[(Index)i] > 8.0 ? 8.0 : delayTime[(Index)i]))", adapted)


if __name__ == "__main__": unittest.main()
