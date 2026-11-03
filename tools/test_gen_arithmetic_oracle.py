# SPDX-License-Identifier: MIT
"""Compile independent target mathematics and compare complete cache words."""
import ctypes as C
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
inputs=load('gen_arithmetic_inputs',ROOT/'tests/fixtures/objects/wave4/inputs.py')
models=load('gen_arithmetic_models',ROOT/'tests/fixtures/gen/arithmetic/models.py')


class GenArithmeticOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        library=Path(cls.temp.name)/'gen-arithmetic.so'
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror',
                        '-shared','-fPIC',str(ROOT/'object-benchmark/main/gen_arithmetic_oracle.c'),'-o',str(library),'-lm'],check=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.object_gen_arithmetic_oracle_fill.argtypes=[C.c_uint32,C.POINTER(C.c_float),C.c_uint32,C.c_uint32,
                                                           C.c_uint32,C.POINTER(C.c_float),C.c_uint32]
        cls.lib.object_gen_arithmetic_oracle_fill.restype=C.c_bool

    def test_all_eight_models_three_full_caches_match_independent_python_bits(self):
        for kind in ('signed-grid-v1','dense-binary32-v1','vector-boundaries-v1'):
            planes=inputs.generate(kind,16384)
            source=(C.c_float*32768).from_buffer_copy(models.cache_bytes(planes))
            for model in models.MODELS:
                expected=models.cache_bytes(models.expected_outputs(model,planes))
                out=(C.c_float*32768)();start=0;n=0;chunks=(1,255,257,509,1024)
                while start<16384:
                    count=min(chunks[n%len(chunks)],16384-start)
                    destination=C.cast(C.byref(out,start*8),C.POINTER(C.c_float))
                    self.assertTrue(self.lib.object_gen_arithmetic_oracle_fill(model,source,16384,start,count,destination,count*2))
                    n+=1;start+=count
                self.assertEqual(bytes(out),expected,(kind,model))

    def test_signed_zero_and_subnormal_sum_product_reference_words(self):
        wire=struct.pack('<IIIIIIII',1,0x3f000000,0x80000001,0x3f000000,0x80000000,0,0x3f800000,0x3f800000)
        source=(C.c_float*8).from_buffer_copy(wire)
        for model,words in [(9,(0x3f000000,0x3f000000,0x3f000000,0x3f000000,0,0,0x40000000,0x40000000)),
                            (10,(0,0,0x80000000,0x80000000,0x80000000,0x80000000,0x3f800000,0x3f800000))]:
            out=(C.c_float*8)()
            self.assertTrue(self.lib.object_gen_arithmetic_oracle_fill(model,source,4,0,4,out,8))
            self.assertEqual(bytes(out),struct.pack('<8I',*words))

    def test_invalid_input_model_span_and_overlap_reject_before_any_write(self):
        for mutation in ('nan','infinity','domain','model','span','capacity','overlap'):
            source=(C.c_float*8)(.5,.25,-.5,-.25,1,0,-1,0);out=(C.c_float*8)(*([42]*8))
            model,total,first,frames,capacity=1,4,0,4,8;dest=out
            if mutation=='nan':source[7]=float('nan')
            elif mutation=='infinity':source[7]=float('inf')
            elif mutation=='domain':source[7]=1.01
            elif mutation=='model':model=7
            elif mutation=='span':first=1
            elif mutation=='capacity':capacity=7
            else:dest=C.cast(C.byref(source,4),C.POINTER(C.c_float))
            before=bytes(source),bytes(out)
            self.assertFalse(self.lib.object_gen_arithmetic_oracle_fill(model,source,total,first,frames,dest,capacity),mutation)
            self.assertEqual((bytes(source),bytes(out)),before)
        for model in (True,0,7,8,11):
            with self.assertRaises(ValueError):models.expected_outputs(model,((0.0,),(0.0,)))
        for value in (1.1,float('nan'),1e-50,True):
            with self.assertRaises(ValueError):models.expected_outputs(1,((value,),(0.0,)))


if __name__=='__main__':unittest.main()
