# SPDX-License-Identifier: MIT
import math
import os
from pathlib import Path
import struct
import tempfile
import unittest

from investigate_native_delay_storage import compare, ROOT
from prepare import cpp_code_mask
from float32_delays import float32_delays


class CaptureTests(unittest.TestCase):
    def compare_bytes(self, a, b):
        with tempfile.TemporaryDirectory() as directory:
            left=Path(directory)/'left'; right=Path(directory)/'right'
            left.write_bytes(a); right.write_bytes(b)
            return compare(left,right)

    def test_metrics_and_bit_identity_are_separate(self):
        result=self.compare_bytes(struct.pack('<3f',0,1,2),struct.pack('<3f',-0.0,1,3))
        self.assertEqual(result['bit_different_words'],2)
        self.assertEqual(result['maximum_absolute_error'],1)
        self.assertAlmostEqual(result['rms_error'],math.sqrt(1/3))
        self.assertFalse(result['bit_identical'])

    def test_exact_capture_and_chunk_boundary(self):
        data=struct.pack('<f',0.25)*16385
        result=self.compare_bytes(data,data)
        self.assertEqual(result['words'],16385)
        self.assertTrue(result['bit_identical'])
        self.assertEqual(result['rms_error'],0)

    def test_incomplete_empty_or_nonfinite_never_passes(self):
        for a,b in ((b'',b''),(b'123',b'123'),(b'1234',b'12345678'),
                    (struct.pack('<f',float('nan')),struct.pack('<f',float('nan'))),
                    (struct.pack('<f',0),struct.pack('<f',float('inf')))):
            with self.subTest(a=a,b=b),self.assertRaises(ValueError):
                self.compare_bytes(a,b)


class NativeExportGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(os.environ.get('RNBO_S3_TEST_NATIVE_DELAY_EXPORT',
            ROOT/'build/private/studio/8b467cd380184d779f90fb8195aa0e1d/export'))/'rnbo_source.h'
        if not path.is_file():
            raise unittest.SkipTest('Supply the local native SawSAHArpy export; generated source is not distributed')
        cls.source=path.read_bytes()

    def test_native_delay_only_changes_constructor_and_reference(self):
        result,report=float32_delays(self.source,code_mask=cpp_code_mask)
        self.assertEqual(result.replace(b'Float32Buffer',b'Float64Buffer'),self.source)
        self.assertEqual(report['constructor_reference_pairs'],1)
        self.assertEqual(report['buffer_data_bytes_saved'],131072)
        self.assertEqual(report['rings'][0]['frames'],32768)

    def test_changed_reader_constructor_and_repeated_conversion_reject(self):
        result,_=float32_delays(self.source,code_mask=cpp_code_mask)
        for value in (result,self.source.replace(b'Int interp)',b'Int other)'),
                      self.source.replace(b'new Float64Buffer(this->delaytilde_01_del_bufferobj)',
                                          b'new Float64Buffer(other)')):
            self.assertNotEqual(value,self.source)
            with self.subTest(),self.assertRaises(ValueError):
                float32_delays(value,code_mask=cpp_code_mask)


if __name__=='__main__':
    unittest.main()
