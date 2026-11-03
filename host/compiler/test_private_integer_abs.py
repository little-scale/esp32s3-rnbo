# SPDX-License-Identifier: MIT
"""Check private integer arithmetic against an independent widened magnitude."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PrivateIntegerAbsTests(unittest.TestCase):
    def test_representable_magnitudes_and_explicit_min_extension(self):
        compiler = shutil.which('c++')
        if not compiler:
            self.skipTest('A C++ compiler is needed for the private integer primitive')
        with tempfile.TemporaryDirectory() as name:
            for mode, flags in (('release', ['-O3']), ('ubsan', ['-O2', '-fsanitize=undefined', '-fno-sanitize-recover=undefined'])):
                with self.subTest(mode=mode):
                    binary = Path(name) / mode
                    result = subprocess.run([compiler, '-std=c++17', '-fno-builtin', *flags,
                        '-I'+str(ROOT/'module-sdk/dynamic'), str(ROOT/'tests/native/integer_abs.cpp'), '-o', str(binary)],
                        capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    result = subprocess.run([str(binary)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, '')
                    record = json.loads(result.stdout)
                    self.assertEqual(record['checked_inputs'], 131260)
                    self.assertEqual(record['signed_min_extension'], -2147483648)


if __name__ == '__main__':
    unittest.main()
