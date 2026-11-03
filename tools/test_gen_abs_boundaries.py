# SPDX-License-Identifier: MIT
"""Full target boundary-input cache and finite magnitude-bit truth."""
import ctypes as C
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gen_abs_inputs',ROOT/'tests/fixtures/gen/abs-intrinsic/inputs.py')
inputs=importlib.util.module_from_spec(spec);spec.loader.exec_module(inputs)
class Stimulus(C.Structure):
    _fields_=[('kind',C.c_uint32)]+[(k,C.c_double)for k in ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')]


class GenAbsBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        path=Path(cls.temp.name)/'abs.so'
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror',
                        '-shared','-fPIC',str(ROOT/'object-benchmark/main/stimulus.c'),
                        str(ROOT/'object-benchmark/main/gen_arithmetic_oracle.c'),'-o',str(path),'-lm'],check=True)
        cls.lib=C.CDLL(str(path));cls.lib.object_stimulus_fill.argtypes=[C.POINTER(Stimulus),C.c_uint32,C.c_uint32,C.POINTER(C.c_float)]
        cls.lib.object_stimulus_fill.restype=C.c_bool
        cls.lib.object_gen_arithmetic_oracle_fill.argtypes=[C.c_uint32,C.POINTER(C.c_float),C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.c_float),C.c_uint32]
        cls.lib.object_gen_arithmetic_oracle_fill.restype=C.c_bool

    def test_complete_target_input_and_abs_reference_match_independent_magnitude_bits(self):
        source=(C.c_float*32768)();out=(C.c_float*32768)()
        self.assertTrue(self.lib.object_stimulus_fill(C.byref(Stimulus(16)),0,16384,source))
        self.assertEqual(bytes(source),inputs.interleaved())
        self.assertTrue(self.lib.object_gen_arithmetic_oracle_fill(1,source,16384,0,16384,out,32768))
        expected=b''.join(struct.pack('<I',word&0x7fffffff)for (word,)in struct.iter_unpack('<I',bytes(source)))
        self.assertEqual(bytes(out),expected)
        words=set(w for w, in struct.iter_unpack('<I',bytes(source)))
        for magnitude in (0,1,0x7fffff,0x800000,0x800001,0x3f800000):
            self.assertIn(magnitude,words);self.assertIn(magnitude|0x80000000,words)

    def test_boundary_seeking_matches_canonical_words_without_float_reconstruction(self):
        for first,count in ((0,1),(1,35),(35,257),(255,513),(16380,4),(262140,4)):
            actual=(C.c_float*(2*count))()
            self.assertTrue(self.lib.object_stimulus_fill(C.byref(Stimulus(16)),first,count,actual))
            self.assertEqual(bytes(actual),inputs.interleaved(count,first_frame=first))
        for frames,first in ((True,0),(1,True),(0,0),(2,262143),(1,-1)):
            with self.assertRaises(ValueError):inputs.interleaved(frames,first_frame=first)


if __name__=='__main__':unittest.main()
