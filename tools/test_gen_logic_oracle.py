# SPDX-License-Identifier: MIT
"""Compare complete target oracle caches with independent Python truth."""
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
inputs=load('logic_wave_inputs',ROOT/'tests/fixtures/objects/wave4/inputs.py')
edges=load('logic_boundary_inputs',ROOT/'tests/fixtures/gen/abs-intrinsic/inputs.py')
models=load('logic_math_models',ROOT/'tests/fixtures/gen/logic/models.py')


class GenLogicOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        library=Path(cls.temp.name)/'gen-logic.so'
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off',
                        '-Wall','-Wextra','-Werror','-shared','-fPIC',
                        str(ROOT/'object-benchmark/main/gen_arithmetic_oracle.c'),
                        '-o',str(library),'-lm'],check=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.object_gen_arithmetic_oracle_fill.argtypes=[C.c_uint32,C.POINTER(C.c_float),
            C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.c_float),C.c_uint32]
        cls.lib.object_gen_arithmetic_oracle_fill.restype=C.c_bool

    def test_all_twelve_models_four_complete_caches_in_irregular_chunks(self):
        families=('signed-grid-v1','dense-binary32-v1','vector-boundaries-v1','boundaries')
        for family in families:
            planes=edges.generate(16384) if family=='boundaries' else inputs.generate(family,16384)
            source=(C.c_float*32768).from_buffer_copy(models.cache_bytes(planes))
            for model in models.MODELS:
                output=(C.c_float*32768)();first=0;index=0
                while first<16384:
                    count=min((1,255,257,509,1024)[index%5],16384-first)
                    pointer=C.cast(C.byref(output,first*8),C.POINTER(C.c_float))
                    self.assertTrue(self.lib.object_gen_arithmetic_oracle_fill(
                        model,source,16384,first,count,pointer,count*2))
                    first+=count;index+=1
                self.assertEqual(bytes(output),models.cache_bytes(models.expected_outputs(model,planes)),(family,model))

    def test_zero_subnormal_truth_step_order_and_selected_payload_bits(self):
        tiny=struct.unpack('<f',struct.pack('<I',1))[0]
        planes=((0.,-0.,tiny,-tiny,1.,-1.),(-0.,tiny,0.,-tiny,-1.,1.))
        self.assertEqual(models.expected_outputs(20,planes)[0],(1.,0.,1.,1.,1.,0.))
        self.assertEqual(models.expected_outputs(19,planes)[0],(0.,0.,1.,1.,1.,1.))
        self.assertEqual(models.expected_outputs(17,planes)[0],(0.,1.,1.,0.,0.,0.))
        words=struct.unpack('<12I',models.cache_bytes(models.expected_outputs(22,planes)))
        self.assertEqual(words[:6],(0,0x80000000,0x80000001,0x80000000,0,0x80000001))

    def test_invalid_models_and_inputs_reject(self):
        for model in (True,0,7,8,10,23):
            with self.assertRaises(ValueError):models.expected_outputs(model,((0.,),(0.,)))
        for value in (True,1,1.1,1e-50,float('nan'),float('inf')):
            with self.assertRaises(ValueError):models.expected_outputs(11,((value,),(0.,)))
        for model in (0,7,8,23):
            source=(C.c_float*2)(0.,0.);output=(C.c_float*2)(42.,42.)
            self.assertFalse(self.lib.object_gen_arithmetic_oracle_fill(model,source,1,0,1,output,2))
            self.assertEqual(tuple(output),(42.,42.))


if __name__=='__main__':unittest.main()
