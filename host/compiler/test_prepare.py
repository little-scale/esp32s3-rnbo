# SPDX-License-Identifier: MIT
"""Admission regressions using a real local RNBO export, without redistributing it.

Generate examples/sine first, then run:
  python3 -m unittest discover -s host/compiler -p 'test_*.py' -v
RNBO_S3_TEST_EXPORT may select a different raw oscillator export.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from prepare import ExportError, prepare


class AdmissionTests(unittest.TestCase):
    def test_touchscreen_metadata_survives_native_preparation(self):
        self.change_description(lambda d:d['parameters'][0].update(meta={'esp32':{'type':'touchscreen','axis':'x'}}))
        self.admit()
        manifest=json.loads((self.output/'manifest.json').read_text())
        self.assertEqual(manifest['touchscreen_inputs']['board'],'amoled')
        self.assertEqual(manifest['touchscreen_inputs']['area'],'patch')
        self.assertNotIn('physical_inputs',manifest)

    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        cls.fixture = Path(os.environ.get("RNBO_S3_TEST_EXPORT", root / "build/exports/sine"))
        if not (cls.fixture / "rnbo_source.h").is_file():
            raise unittest.SkipTest("Generate examples/sine with archive/importer/integer-ui/export.mjs first")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.original = self.root / "export"
        shutil.copytree(self.fixture, self.original)
        self.output = self.root / "prepared"

    def tearDown(self):
        self.temporary.cleanup()

    def admit(self, **kwargs):
        return prepare(self.original, self.output, "rnbos3patch", "main", **kwargs)

    def change_description(self, edit):
        p = self.original / "description.json"
        data = json.loads(p.read_text())
        edit(data)
        p.write_text(json.dumps(data))

    def rejected(self):
        with self.assertRaises(ExportError):
            self.admit()
        self.assertFalse(self.output.exists(), "Rejected exports must not leave a prepared directory")

    def test_deterministic_copy_preserves_originals_and_notices(self):
        before = {p.relative_to(self.original): p.read_bytes() for p in self.original.rglob("*") if p.is_file()}
        first = self.admit()
        second_dir = self.root / "second"
        self.assertEqual(first, prepare(self.original, second_dir, "rnbos3patch", "main"))
        for name, data in before.items():
            self.assertEqual((self.original / name).read_bytes(), data)
            if (self.output / "originals" / name).is_file():
                self.assertEqual((self.output / "originals" / name).read_bytes(), data)
        for p in self.output.rglob("*"):
            if p.is_file():
                self.assertEqual(p.read_bytes(), (second_dir / p.relative_to(self.output)).read_bytes())
        self.assertEqual((self.output / "RNBO-runtime-LICENSE").read_bytes(), before[Path("RNBO-runtime-LICENSE")])

    def test_wrong_vector_rejected(self):
        p = self.original / "rnbo_source.h"
        p.write_text(p.read_text().replace("RNBO_ASSERT(n == 256)", "RNBO_ASSERT(n == 64)"))
        self.rejected()

    def test_fx_admission_rejects_instrument(self):
        with self.assertRaisesRegex(ExportError, "requires 2 inputs"):
            prepare(self.original, self.output, "rnbos3patch", "fx")

    def test_parameter_ids_cannot_alias(self):
        self.change_description(lambda d: d["parameters"][1].update(paramId=d["parameters"][0]["paramId"]))
        self.rejected()

    def test_metadata_must_fit_the_c_abi(self):
        self.change_description(lambda d: d["parameters"][0].update(unit="h" * 32))
        self.rejected()

    def test_external_data_is_explicitly_unsupported(self):
        self.change_description(lambda d: d.update(externalDataRefs=[{"id": "sample"}]))
        self.rejected()

    def test_midi_output_requires_explicit_discard(self):
        self.change_description(lambda d: d.update(numMidiOutputPorts=1))
        self.rejected()
        manifest = self.admit(midi_output_policy="discard")
        self.assertEqual(manifest["midi_output_policy"], "discard")
        self.assertIn("#define RNBO_S3_PATCH_DISCARD_MIDI_OUTPUT 1", (self.output / "patch_config.h").read_text())

    def test_nan_default_rejected(self):
        self.change_description(lambda d: d["parameters"][0].update(initialValue=float("nan")))
        self.rejected()

    def test_double_range_cannot_overflow_float32_abi(self):
        self.change_description(lambda d: d["parameters"][0].update(maximum=1e100))
        self.rejected()

    def test_runtime_version_change_rejected(self):
        p = self.original / "common/RNBO_Version.h"
        p.write_text(p.read_text().replace("1.4.4", "1.5.0"))
        self.rejected()

    def test_changed_runtime_fix_pattern_fails_closed(self):
        p = self.original / "common/RNBO_MinimalEngine.h"
        p.write_text(p.read_text().replace("_patcher->processClockEvent(event.time", "_patcher->processClockEvent( event.time"))
        self.rejected()

    def test_symlinked_runtime_header_rejected(self):
        p = self.original / "common/RNBO_Math.h"
        p.unlink()
        p.symlink_to(self.fixture / "common/RNBO_Math.h")
        self.rejected()

    def test_duplicate_json_keys_rejected(self):
        p = self.original / "description.json"
        p.write_text(p.read_text().replace('"numInputChannels": 0', '"numInputChannels": 2, "numInputChannels": 0'))
        self.rejected()

    def test_existing_output_cannot_be_replaced(self):
        self.admit()
        marker = self.output / "preserve-me"
        marker.write_text("existing build")
        with self.assertRaises(ExportError):
            self.admit()
        self.assertEqual(marker.read_text(), "existing build")

    def test_output_alias_cannot_write_inside_original_export(self):
        link = self.root / "export-alias"
        link.symlink_to(self.original, target_is_directory=True)
        with self.assertRaises(ExportError):
            prepare(self.original, link / "generated", "rnbos3patch", "main")
        self.assertFalse((self.original / "generated").exists())

    def test_reference_route_records_no_fixes(self):
        result = self.admit(apply_fixes=False)
        self.assertEqual(result["adaptations"], [])
        for name in ("RNBO_List.h", "RNBO_MinimalEngine.h"):
            self.assertEqual((self.output / "common" / name).read_bytes(), (self.original / "common" / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
