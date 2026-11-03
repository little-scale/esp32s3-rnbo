#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile target input/oracle C and compare complete bytes to Python truth."""
import array
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
WAVE=ROOT/'tests/fixtures/objects/wave4'
def load(name):
    spec=importlib.util.spec_from_file_location('target_wave4_'+name,WAVE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
inputs=load('inputs');models=load('models')
KINDS=('signed-grid-v1','dense-binary32-v1','vector-boundaries-v1')
MODELS=('absolute','minimum','maximum','subtract','equal','less','sum-and-difference','delta-left-observer-right')
class Stimulus(C.Structure):
    _fields_=[('kind',C.c_uint32)]+[(x,C.c_double) for x in ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')]
class State(C.Structure):
    _fields_=[('magic',C.c_uint32),('model',C.c_uint32),('next_frame',C.c_uint32),('previous',C.c_float)]
def interleave(planes):
    values=array.array('f',(v for pair in zip(*planes) for v in pair))
    return values.tobytes()
class TargetWave4OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();directory=Path(cls.temp.name)
        library=directory/'wave4.so'
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror',
                        '-shared','-fPIC',str(ROOT/'object-benchmark/main/wave4_oracle.c'),
                        str(ROOT/'object-benchmark/main/stimulus.c'),'-o',str(library),'-lm'],check=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.object_stimulus_fill.argtypes=[C.POINTER(Stimulus),C.c_uint32,C.c_uint32,C.POINTER(C.c_float)]
        cls.lib.object_stimulus_fill.restype=C.c_bool
        cls.lib.object_wave4_oracle_init.argtypes=[C.POINTER(State),C.c_uint32,C.c_uint32]
        cls.lib.object_wave4_oracle_init.restype=C.c_bool
        cls.lib.object_wave4_oracle_fill.argtypes=[C.POINTER(State),C.POINTER(C.c_float),C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.c_float),C.c_uint32]
        cls.lib.object_wave4_oracle_fill.restype=C.c_bool
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def stimulus(self,kind,frames,start=0):
        output=(C.c_float*(frames*2))()
        self.assertTrue(self.lib.object_stimulus_fill(C.byref(Stimulus(12+KINDS.index(kind))),start,frames,output))
        return output
    def test_complete_three_target_input_caches_match_python_words_and_chunk_seeking(self):
        frames=64*256
        for kind in KINDS:
            expected=interleave(inputs.generate(kind,frames))
            actual=bytes(self.stimulus(kind,frames))
            self.assertEqual(hashlib.sha256(actual).digest(),hashlib.sha256(expected).digest(),kind)
            for first,count in ((0,1),(1,255),(255,257),(511,513),(1023,3),(16380,4),(262140,4)):
                self.assertEqual(bytes(self.stimulus(kind,count,first)),interleave(inputs.generate(kind,count,start_frame=first)),(kind,first,count))
    def test_all_eight_models_full_caches_match_python_bits_across_arbitrary_chunks(self):
        frames=64*256
        for kind in KINDS:
            source=inputs.generate(kind,frames)
            wire=(C.c_float*(frames*2)).from_buffer_copy(interleave(source))
            for code,model in enumerate(MODELS,1):
                state=State();self.assertTrue(self.lib.object_wave4_oracle_init(C.byref(state),code,4))
                output=(C.c_float*(frames*2))();first=0;n=0;chunks=(1,255,257,509,1024)
                while first<frames:
                    count=min(chunks[n%len(chunks)],frames-first)
                    target=C.cast(C.byref(output,first*8),C.POINTER(C.c_float))
                    self.assertTrue(self.lib.object_wave4_oracle_fill(C.byref(state),wire,frames,first,count,target,count*2))
                    first+=count;n+=1
                expected,previous=models.expected_outputs(model,*source)
                self.assertEqual(bytes(output),interleave(expected),(kind,model))
                self.assertEqual(state.next_frame,frames)
                self.assertEqual(struct.pack('<f',state.previous),struct.pack('<f',previous),(kind,model))
    def test_bad_domain_and_cursor_reject_without_output_or_history_changes(self):
        for bad in (float('nan'),float('inf'),2.0,-2.0):
            state=State();self.assertTrue(self.lib.object_wave4_oracle_init(C.byref(state),8,4))
            source=(C.c_float*4)(.5,.25,bad,0.0);out=(C.c_float*4)(42,42,42,42)
            old=bytes(state)
            self.assertFalse(self.lib.object_wave4_oracle_fill(C.byref(state),source,2,0,2,out,4))
            self.assertEqual(bytes(state),old);self.assertEqual(tuple(out),(42,)*4)
        source=(C.c_float*4)(0,0,0,0);out=(C.c_float*4)();state=State()
        self.assertTrue(self.lib.object_wave4_oracle_init(C.byref(state),8,4))
        for first,count,capacity in ((1,1,2),(0,3,6),(0,2,3),(0,0,0)):
            self.assertFalse(self.lib.object_wave4_oracle_fill(C.byref(state),source,2,first,count,out,capacity))
        self.assertFalse(self.lib.object_wave4_oracle_fill(C.byref(state),source,2,0,2,source,4))
    def test_model_and_warmup_admission_are_closed(self):
        for model,warmup in ((0,4),(9,4),(8,0),(8,3),(8,5)):
            state=State();self.assertFalse(self.lib.object_wave4_oracle_init(C.byref(state),model,warmup))

if __name__=='__main__':unittest.main()
