# SPDX-License-Identifier: MIT
"""Ensure a changed export cannot receive a successful reviewed build report."""
from pathlib import Path
import os
import shutil
import tempfile
import unittest
from unittest import mock

from build import build
from prepare import ExportError, prepare


class BuildIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        cls.fixture = Path(os.environ.get("RNBO_S3_TEST_EXPORT", root / "build/exports/sine"))
        if not (cls.fixture / "rnbo_source.h").is_file():
            raise unittest.SkipTest("Generate examples/sine with host/export/export.mjs first")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        original = self.root / "raw"
        shutil.copytree(self.fixture, original)
        self.prepared = self.root / "prepared"
        self.build_dir = self.root / "build"
        prepare(original, self.prepared, "rnbos3patch", "main")

    def tearDown(self):
        self.temporary.cleanup()

    def mutate(self):
        path = self.prepared / "rnbo_source.h"
        path.write_bytes(path.read_bytes() + b"\n// concurrent source edit\n")

    def test_changed_export_rejected_before_compiler_runs(self):
        self.mutate()
        with mock.patch("build.subprocess.run") as run:
            with self.assertRaisesRegex(ExportError, "changed after review"):
                build(self.prepared, self.build_dir)
            run.assert_not_called()

    def test_export_change_during_compilation_rejects_report(self):
        calls = []
        def compilation(command, **kwargs):
            calls.append(command)
            if "--build" in command:
                self.mutate()
        with mock.patch("build.subprocess.run", side_effect=compilation):
            with self.assertRaisesRegex(ExportError, "changed after review"):
                build(self.prepared, self.build_dir)
        self.assertEqual(len(calls), 2)
        self.assertFalse((self.build_dir / "host-build.json").exists())


if __name__ == "__main__":
    unittest.main()
