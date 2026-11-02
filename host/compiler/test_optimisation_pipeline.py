# SPDX-License-Identifier: MIT
"""Exercise production preparation ordering, metadata and resource ABI gates."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from prepare import ExportError, prepare

ROOT = Path(__file__).resolve().parents[2]


class OptimisationPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wave = ROOT / "build/object-qualification/wave2-final/exports"
        cls.drone = ROOT / "build/user-patches/3sawsDrone3/export"
        if not all((p / "rnbo_source.h").is_file() for p in (cls.wave / "average-window", cls.wave / "noise-colour", cls.drone)):
            raise unittest.SkipTest("Generate the authorized local object and drone exports first")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_drone_hoist_and_table_omission_reproduce_measured_source(self):
        out = self.base / "drone"
        manifest = prepare(self.drone, out, "rnbos3patch", "main", filter_delay_max_ms=40,
                           float32_delay_storage=True, numerical_profile="float32-audio-v1",
                           omit_unused_mtof_table=True, hoist_cycle_conversions=True)
        self.assertEqual(hashlib.sha256((out / "rnbo_source.h").read_bytes()).hexdigest(),
                         "6eef8b7c2333914d41f7bef5134ccc6863754755b4002a7201f4f66a0fa42b2d")
        self.assertTrue(manifest["hoist_cycle_conversions"] and manifest["defined_int32_wrap"])
        self.assertIn("rnbo_defined_i32_from_u32", (out / "common/RNBO_Math.h").read_text())
        provenance = json.loads((out / "provenance.json").read_text())
        self.assertEqual(sum(x.get("hoisted_conversion_count", 0) for x in provenance["adaptations"]), 6)

    def compact(self, name="compact"):
        out = self.base / name
        manifest = prepare(self.wave / "average-window", out, "rnbos3patch", "fx", compact_average_history=True)
        return out, manifest

    def test_compact_history_runs_before_math_fix_and_keeps_exact_output_source(self):
        out, manifest = self.compact()
        self.assertEqual(hashlib.sha256((out / "rnbo_source.h").read_bytes()).hexdigest(),
                         "c843b9f0a14a53e8c792c6e7a857bb9dda2d7df488c3282db4a0b16f36023ab0")
        self.assertTrue(manifest["compact_average_history"] and manifest["requires_opaque_dataref_abi"])
        self.assertIn("average_history", manifest["modified_internal_resource_semantics"])
        provenance = json.loads((out / "provenance.json").read_text())
        names = [x["name"] for x in provenance["adaptations"]]
        self.assertLess(names.index("rnbo-1.4.4-compact-average-authored64-v1"), names.index("rnbo-1.4.4-defined-imul-v1"))

    def test_compact_config_rejects_missing_and_future_resource_abis(self):
        compiler = shutil.which("c++")
        if not compiler: self.skipTest("C++ compiler required for ABI gate check")
        out, _ = self.compact(); config = (out / "patch_config.h").read_text()
        for version, expected in ((None, False), ((1, 0), True), ((1, 1), False), ((2, 0), False)):
            prefix = "" if version is None else f"#define RNBO_S3_ABI_MAJOR {version[0]}u\n#define RNBO_S3_ABI_MINOR {version[1]}u\n"
            result = subprocess.run([compiler, "-x", "c++", "-fsyntax-only", "-"], input=prefix + config, capture_output=True, text=True)
            self.assertEqual(result.returncode == 0, expected, version)

    def test_pink_wrap_is_default_and_reference_mode_preserves_original(self):
        out = self.base / "noise"; reference = self.base / "reference"
        manifest = prepare(self.wave / "noise-colour", out, "rnbos3patch", "main")
        plain = prepare(self.wave / "noise-colour", reference, "rnbos3patch", "main", apply_fixes=False)
        self.assertTrue(manifest["defined_int32_wrap"])
        self.assertIn("rnbo-1.4.4-defined-pink-affine-v1", manifest["adaptations"])
        self.assertEqual(plain["adaptations"], [])
        self.assertNotIn("defined_int32_wrap", plain)
        for file in ("rnbo_source.h", "common/RNBO_Math.h"):
            self.assertEqual((reference / file).read_bytes(), (self.wave / "noise-colour" / file).read_bytes())

    def test_unknown_compact_context_and_nonboolean_flags_leave_no_output(self):
        for kwargs in ({"compact_average_history": True}, {"compact_average_history": 1}, {"hoist_cycle_conversions": 1}):
            out = self.base / "rejected"
            with self.assertRaises(ExportError):
                prepare(self.wave / "noise-colour", out, "rnbos3patch", "main", **kwargs)
            self.assertFalse(out.exists())


if __name__ == "__main__": unittest.main()
