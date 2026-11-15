# SPDX-License-Identifier: MIT
"""Real Max message output, actual module wrapper and private arena; no USB."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class LEDWrapperTests(unittest.TestCase):
    def test_genuine_export_all_formats_and_no_late_allocations(self):
        prepared=ROOT/'build/private/voice-pe-led/prepared-v2-16000'
        if not (prepared/'rnbo_source.h').is_file():self.skipTest('Export/prepare the genuine Voice PE LED fixture first')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            flags=[os.environ.get('CXX','c++'),'-std=c++17','-O2','-fno-builtin','-fno-exceptions','-fno-rtti',
                '-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing','-UNDEBUG','-DRNBO_S3_SAMPLE_RATE=16000u',
                *['-I'+str(p) for p in (ROOT/'module-sdk/include',ROOT/'module-sdk/dynamic',prepared,prepared/'common')]]
            subprocess.run([*flags,'-Dmain=rnbo_test_module_entry','-c',str(ROOT/'module-sdk/dynamic/rnbo_s3_dynamic.cpp'),'-o',str(out/'wrapper.o')],check=True,capture_output=True)
            subprocess.run([*flags,str(ROOT/'tests/dynamic/led_wrapper_test.cpp'),str(out/'wrapper.o'),str(ROOT/'module-sdk/dynamic/arena.cpp'),'-o',str(out/'test')],check=True,capture_output=True)
            result=subprocess.run([str(out/'test')],check=True,capture_output=True,text=True,timeout=10)
            self.assertIn('zero late allocations',result.stdout)
