# SPDX-License-Identifier: MIT
"""Guard the optional two-coefficient cycle~ numerical transformation."""
from pathlib import Path
import os
import re
import tempfile
import unittest

from prepare import ExportError, float32_cycle, prepare


class CycleProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[2]
        cls.export_dir=Path(os.environ.get("RNBO_S3_TEST_EXPORT",root/"build/exports/sine"))
        source_path=cls.export_dir/"rnbo_source.h"
        if not source_path.is_file():
            raise unittest.SkipTest("Generate the local raw sine export first")
        source=source_path.read_bytes()
        match=re.search(rb"\bvoid\s+cycle_tilde_01_perform\s*\(",source)
        if not match:
            raise RuntimeError("Local sine fixture has no cycle_tilde_01_perform definition")
        # The local raw fixture's generated kernel contains no comments or
        # string literals. Locate its bytes independently of the production
        # fingerprint/scanner, then add adversarial constructs in each test.
        opening=source.index(b"{",match.end())
        depth=1;cursor=opening+1
        while cursor<len(source) and depth:
            if source[cursor]==ord("{"):depth+=1
            elif source[cursor]==ord("}"):depth-=1
            cursor+=1
        if depth:raise RuntimeError("Unterminated kernel in the local raw sine fixture")
        cls.local_kernel=source[match.start():cursor]

    def kernel(self):return self.local_kernel

    def test_only_two_literal_suffixes_change(self):
        raw=self.kernel()
        prepared,change=float32_cycle(raw)
        self.assertEqual(change["kernel_count"],1)
        self.assertEqual(change["literal_suffix_count"],2)
        restored=prepared.replace(b"3.81471181759574e-6f",b"3.81471181759574e-6").replace(b"0.232830643653869629e-9f",b"0.232830643653869629e-9")
        self.assertEqual(restored,raw)

    def test_comments_strings_raw_strings_and_clock_coefficients_are_untouched(self):
        prefix=(b'// void cycle_fake_perform() { } 3.81471181759574e-6\n'
                b'const char *a="void cycle_fake_perform() { 3.81471181759574e-6; }";\n'
                b'const char *b=R"tag(void cycle_fake_perform() { } \" 0.232830643653869629e-9)tag";\n'
                b'double scheduler=3.81471181759574e-6;\n')
        prepared,change=float32_cycle(prefix+self.kernel())
        self.assertTrue(prepared.startswith(prefix))
        self.assertEqual(change["kernel_count"],1)

    def test_braces_in_kernel_comments_do_not_change_scope(self):
        raw=self.kernel().replace(b"RNBO_UNUSED(n);",b"RNBO_UNUSED(n); /* } { \' \" */")
        prepared,change=float32_cycle(raw)
        self.assertIn(b'/* } { \' " */',prepared)
        self.assertEqual(change["literal_suffix_count"],2)

    def test_changed_coefficient_or_algorithm_fails_closed(self):
        for old,new in ((b"3.81471181759574e-6",b"3.8e-6"),(b"262143",b"262144"),(b"number frequency",b"const SampleValue * frequency")):
            with self.subTest(old=old):
                with self.assertRaisesRegex(ExportError,"unsupported RNBO"):
                    float32_cycle(self.kernel().replace(old,new))

    def test_already_prepared_or_missing_kernel_is_rejected(self):
        prepared,_=float32_cycle(self.kernel())
        for source in (prepared,b"double clock=3.81471181759574e-6;"):
            with self.assertRaises(ExportError):float32_cycle(source)

    def test_each_qualified_cycle_object_has_its_own_guard_and_count(self):
        second=self.kernel().replace(b"cycle_tilde_01",b"cycle_tilde_02")
        _,change=float32_cycle(self.kernel()+second)
        self.assertEqual(change["kernel_count"],2)
        self.assertEqual(change["literal_suffix_count"],4)

    def test_real_export_default_preserves_source_and_opt_preserves_original(self):
        raw=self.export_dir
        with tempfile.TemporaryDirectory() as directory:
            strict=Path(directory)/"strict";optimized=Path(directory)/"optimized"
            default=prepare(raw,strict,"rnbos3patch","main")
            opt=prepare(raw,optimized,"rnbos3patch","main",numerical_profile="float32-cycle-v1")
            self.assertEqual(default["numerical_profile"],"float32-strict")
            self.assertEqual((strict/"rnbo_source.h").read_bytes(),(raw/"rnbo_source.h").read_bytes())
            self.assertEqual((optimized/"originals/rnbo_source.h").read_bytes(),(raw/"rnbo_source.h").read_bytes())
            self.assertEqual(opt["scheduler_time"],"float64")
            self.assertEqual(default["source_tree_sha256"],opt["source_tree_sha256"])


if __name__=="__main__":unittest.main()
