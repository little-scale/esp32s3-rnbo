# SPDX-License-Identifier: MIT
"""Portable shell/lifecycle regressions; no IDF, generated DSP or hardware."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


class LoaderTests(unittest.TestCase):
    def test_actual_loader_partial_failure_and_cleanup_contract(self):
        compiler = shutil.which('cc')
        if not compiler:
            self.skipTest('a C compiler is needed for portable loader tests')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'loader-test'
            command = [compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                '-I', str(HERE / 'loader_stubs'), '-I', str(ROOT / 'module-sdk/include'),
                '-I', str(ROOT / 'firmware/components/player_loader/include'),
                '-I', str(ROOT / 'firmware/components/player_loader'),
                str(HERE / 'loader_host.c'), '-o', str(output)]
            compiled = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(output)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Main-only admission PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
