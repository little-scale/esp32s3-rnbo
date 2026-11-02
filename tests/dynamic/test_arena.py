"""Compile and exercise the actual private module allocator on the host."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PrivateAllocatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="rnbo-private-arena-")
        cls.executable = Path(cls.temporary.name) / "arena-test"
        subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O2", "-fno-builtin", "-fno-exceptions",
                        "-I", str(ROOT / "module-sdk/dynamic"), str(ROOT / "tests/dynamic/arena_test.cpp"),
                        str(ROOT / "module-sdk/dynamic/arena.cpp"), "-o", str(cls.executable)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_absolute_alignment_and_both_late_allocation_routes(self):
        subprocess.run([str(self.executable)], check=True, timeout=5)

    def test_no_bootstrap_or_firmware_heap_fallback_on_invalid_allocation(self):
        for case in ("bootstrap", "exhaustion", "invalid-alignment", "foreign-pointer"):
            with self.subTest(case=case):
                result = subprocess.run([str(self.executable), case], cwd=self.temporary.name, capture_output=True, timeout=5)
                self.assertLess(result.returncode, 0, "invalid module allocation returned instead of trapping")


if __name__ == "__main__": unittest.main()
