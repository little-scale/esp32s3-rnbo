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
        subprocess.run(['cc','-std=c11','-shared','-fPIC','-O2','-fno-fast-math','-ffp-contract=off',str(ROOT/'object-benchmark/main/stimulus.c'),str(ROOT/'object-benchmark/main/average_oracle.c'),'-lm','-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib));cls.lib.object_stimulus_fill.argtypes=[ctypes.POINTER(Stimulus),ctypes.c_uint32,ctypes.c_uint32,ctypes.POINTER(ctypes.c_float)]
        cls.lib.object_stimulus_fill.restype=ctypes.c_bool
        cls.lib.object_average_oracle_fill.argtypes=[ctypes.POINTER(ctypes.c_float),*([ctypes.c_uint32]*5),ctypes.POINTER(ctypes.c_float),ctypes.POINTER(ctypes.c_double)]
        cls.lib.object_average_oracle_fill.restype=ctypes.c_bool
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
    def test_wave2_inputs_match_independent_host_formula(self):
        frames=512*256
        for kind in (4,5,6):
            with self.subTest(kind=kind):
                state=Stimulus(kind=kind);output=(ctypes.c_float*(2*frames))()
                self.assertTrue(self.lib.object_stimulus_fill(ctypes.byref(state),0,frames,output))
                expected=array.array('f')
                for i in range(frames):
                    if kind==4:left=1.0 if i==0 else -.5 if i==4096 else 0.;right=.25 if i<8192 else -.125
                    elif kind==5:
                        left=.2*math.sin(2*math.pi*440*i/44100)+.19*math.sin(2*math.pi*441*i/44100)
                        right=.2*math.sin(2*math.pi*660*i/44100)-.2*math.sin(2*math.pi*661*i/44100)+1e-5
                    else:
                        left=(-4,-2,-1,-.5,0,.5,1,2,4)[(i//64)%9]
                        right=(-3,-2,-1,-.5,0,.25,.5,1,1.5,2,3)[(i//64)%11]
                    expected.extend((left,right))
                self.assertEqual(bytes(output),expected.tobytes())
    def test_nonlinear_grid_chunk_boundaries_preserve_absolute_frame(self):
        frames=8193;state=Stimulus(kind=6)
        full=(ctypes.c_float*(frames*2))();chunked=(ctypes.c_float*(frames*2))()
        self.assertTrue(self.lib.object_stimulus_fill(ctypes.byref(state),0,frames,full))
        first=0
        for count in (63,1,64,127,1,256,257,4096,3328):
            pointer=ctypes.cast(ctypes.byref(chunked,first*8),ctypes.POINTER(ctypes.c_float))
            self.assertTrue(self.lib.object_stimulus_fill(ctypes.byref(state),first,count,pointer));first+=count
        self.assertEqual(first,frames);self.assertEqual(bytes(full),bytes(chunked))
    def test_average_fresh_float64_oracle_against_fsum_bound(self):
        frames=9000
        for kind in (4,5):
            state=Stimulus(kind=kind);input=(ctypes.c_float*(2*frames))()
            self.assertTrue(self.lib.object_stimulus_fill(ctypes.byref(state),0,frames,input))
            for window,initial in ((1,0),(16,16),(16,0),(63,0),(64,0)):
                with self.subTest(kind=kind,window=window,initial=initial):
                    output=(ctypes.c_float*(2*frames))();rounding=ctypes.c_double(0)
                    self.assertTrue(self.lib.object_average_oracle_fill(input,frames,0,frames,window,initial,output,ctypes.byref(rounding)))
                    maximum=0
                    for n in range(frames):
                        begin=max(0,n-window+1);denominator=min(window,initial+n+1)
                        for channel in (0,1):
                            truth=math.fsum(input[2*j+channel] for j in range(begin,n+1))/denominator
                            maximum=max(maximum,abs(output[2*n+channel]-truth))
                    self.assertLessEqual(maximum,rounding.value+1e-14)
                    self.assertLessEqual(rounding.value,2**-24)
                    # Chunked generation must use prior actual input, not reset at256.
                    chunked=(ctypes.c_float*(2*frames))();error=ctypes.c_double(0)
                    for first in range(0,frames,256):
                        count=min(256,frames-first);pointer=ctypes.cast(ctypes.byref(chunked,first*2*4),ctypes.POINTER(ctypes.c_float))
                        self.assertTrue(self.lib.object_average_oracle_fill(input,frames,first,count,window,initial,pointer,ctypes.byref(error)))
                    self.assertEqual(bytes(output),bytes(chunked));self.assertEqual(error.value,rounding.value)
    def test_oracle_initial_zero_history_and_changed_window_reset(self):
        state=Stimulus(kind=4);input=(ctypes.c_float*128)();self.assertTrue(self.lib.object_stimulus_fill(ctypes.byref(state),0,64,input))
        for window,initial,expected in ((16,16,1/16),(63,0,1),(64,0,1)):
            output=(ctypes.c_float*128)();rounding=ctypes.c_double(0)
            self.assertTrue(self.lib.object_average_oracle_fill(input,64,0,64,window,initial,output,ctypes.byref(rounding)))
            self.assertEqual(output[0],expected)
    def test_oracle_invalid_domain_fails(self):
        input=(ctypes.c_float*128)();output=(ctypes.c_float*128)();rounding=ctypes.c_double(0)
        for window,initial in ((0,0),(65,0),(16,17)):
            self.assertFalse(self.lib.object_average_oracle_fill(input,64,0,64,window,initial,output,ctypes.byref(rounding)))
        self.assertFalse(self.lib.object_average_oracle_fill(input,64,63,2,16,0,output,ctypes.byref(rounding)))
    def test_available_original_strict_cancellation_render_still_fails(self):
        base=ROOT/'build/object-qualification/wave2-final/renders/average-window/float32-strict'
        source=base/'cancellation-tones-input.f32';capture=base/'cancellation-tones.f32'
        if not source.exists() or not capture.exists():self.skipTest('Local original RNBO render is unavailable')
        values=array.array('f');values.frombytes(source.read_bytes());actual=array.array('f');actual.frombytes(capture.read_bytes())
        self.assertEqual(len(values),len(actual));frames=len(values)//2
        input=(ctypes.c_float*len(values))(*values);oracle=(ctypes.c_float*len(values))();rounding=ctypes.c_double(0)
        self.assertTrue(self.lib.object_average_oracle_fill(input,frames,0,frames,16,16,oracle,ctypes.byref(rounding)))
        bound=max(abs(a-b) for a,b in zip(actual,oracle))+rounding.value
        self.assertGreater(bound,2e-6)
    def test_generator_rejects_unimplemented_kind_and_invalid_sizes(self):
        state=Stimulus(kind=99);output=(ctypes.c_float*2)()
        self.assertFalse(self.lib.object_stimulus_fill(ctypes.byref(state),0,1,output))
        state.kind=1
        self.assertFalse(self.lib.object_stimulus_fill(ctypes.byref(state),0,0,output))
        self.assertFalse(self.lib.object_stimulus_fill(ctypes.byref(state),0,262145,output))
        self.assertFalse(self.lib.object_stimulus_fill(None,0,1,output))

if __name__=='__main__':unittest.main()
