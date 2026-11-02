#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the same portable input generator used by target, check every FX case."""
import array
import ctypes
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from build_object_benchmark import stimulus_contract
ROOT=Path(__file__).resolve().parents[1]

class Stimulus(ctypes.Structure):
    _fields_=[('kind',ctypes.c_uint32)]+[(k,ctypes.c_double) for k in ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')]

class StimulusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();lib=Path(cls.temp.name)/'stimulus.dylib'
        subprocess.run(['cc','-std=c11','-shared','-fPIC','-O2','-fno-fast-math','-ffp-contract=off',str(ROOT/'object-benchmark/main/stimulus.c'),'-lm','-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib));cls.lib.object_stimulus_fill.argtypes=[ctypes.POINTER(Stimulus),ctypes.c_uint32,ctypes.c_uint32,ctypes.POINTER(ctypes.c_float)]
        cls.lib.object_stimulus_fill.restype=ctypes.c_bool
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_all_fx_cases_match_independent_host_formula(self):
        catalog=json.loads((ROOT/'tests/fixtures/objects/catalog-fx.json').read_text());frames=512*256
        for fixture in catalog['fixtures']:
            for case in fixture['cases']:
                with self.subTest(fixture=fixture['id'],case=case['id']):
                    spec=stimulus_contract(fixture,case);fields={k:spec[k] for k,_ in Stimulus._fields_};state=Stimulus(**fields)
                    output=(ctypes.c_float*(2*frames))();self.assertTrue(self.lib.object_stimulus_fill(ctypes.byref(state),0,frames,output))
                    settings=fixture['stimulus']|case.get('stimulus',{});expected=array.array('f')
                    for i in range(frames):
                        t=i/44100
                        if settings['kind']=='reson-stereo-v1':
                            left=settings['level']*math.sin(2*math.pi*settings['excitation']*t)
                            right=settings['center']+settings['depth']*math.sin(2*math.pi*settings['rate']*t)
                        else:
                            base=settings['base'] if settings['kind']=='midi-stereo-v1' else settings['frequency']
                            left=base+settings['depth']*math.sin(2*math.pi*settings['rate']*t)
                            right=settings['pilot_amplitude']*math.sin(2*math.pi*settings['pilot_frequency']*t)
                        expected.extend((left,right))
                    self.assertEqual(bytes(output),expected.tobytes())
    def test_chunk_generation_preserves_absolute_frame_time(self):
        state=Stimulus(kind=1,base=60,depth=24,rate=20,pilot_frequency=371,pilot_amplitude=.125)
        full=(ctypes.c_float*2048)();chunked=(ctypes.c_float*2048)()
        self.assertTrue(self.lib.object_stimulus_fill(ctypes.byref(state),0,1024,full))
        for first in range(0,1024,256):
            pointer=ctypes.cast(ctypes.byref(chunked,first*2*4),ctypes.POINTER(ctypes.c_float))
            self.assertTrue(self.lib.object_stimulus_fill(ctypes.byref(state),first,256,pointer))
        self.assertEqual(bytes(full),bytes(chunked))
    def test_generator_rejects_unimplemented_kind_and_invalid_sizes(self):
        state=Stimulus(kind=99);output=(ctypes.c_float*2)()
        self.assertFalse(self.lib.object_stimulus_fill(ctypes.byref(state),0,1,output))
        state.kind=1
        self.assertFalse(self.lib.object_stimulus_fill(ctypes.byref(state),0,0,output))
        self.assertFalse(self.lib.object_stimulus_fill(ctypes.byref(state),0,262145,output))
        self.assertFalse(self.lib.object_stimulus_fill(None,0,1,output))

if __name__=='__main__':unittest.main()
