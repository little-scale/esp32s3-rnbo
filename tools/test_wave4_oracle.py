#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile target input/oracle C and compare complete bytes to Python truth."""
import array
import ctypes as C
import hashlib
import importlib.util
import re
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

    def test_actual_run_pass_counts_wrong_observer_zero_bits_with_zero_numeric_error(self):
        source=(ROOT/'object-benchmark/main/benchmark.c').read_text()
        begin=source.index('static void run_pass(');end=source.index('\nstatic void worker(',begin)
        function=source[begin:end]
        declarations=[re.search(r'typedef struct \{[^}]*\} '+name+r';',source,re.S)[0]
                      for name in ('profile_metrics','compare_metrics','semantic_metrics')]
        program=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <math.h>
#include <stddef.h>
#include "stimulus.h"
#include "wave2_oracle.h"
#include "wave4_oracle.h"
#include "gen_history_oracle.h"
#define CHECK(x) assert(x)
#define BENCH_ROLE 2
#define RNBO_S3_FX 2
#define RNBO_S3_BLOCK_FRAMES 256
#define BENCH_BLOCKS 64
#define BENCH_WARMUP 4
#define BENCH_SEED 0x12345678u
typedef struct { uint64_t position; } object_image;
typedef struct { unsigned ignored; } bench_case;
'''+ '\n'.join(declarations)+r'''
static float reference[BENCH_BLOCKS*512],oracle_cache[BENCH_BLOCKS*512];
static float planar[4][256],*outputs[2]={planar[0],planar[1]},*inputs[2]={planar[2],planar[3]};
static struct { unsigned kind,window; double maximum_error; } verification={OBJECT_WAVE4_KIND,OBJECT_WAVE4_DELTA,0},*active_verification=&verification;
static object_stimulus stimulus,*active_stimulus=&stimulus;
static uint64_t dc_sample_checks,semantic_sample_checks,pilot_sample_checks,oracle_bit_sample_checks,oracle_bit_differences;
static uint64_t wave4_bit_sample_checks,wave4_bit_differences,wave4_zero_sign_differences,observer_bit_sample_checks,observer_bit_differences;
static uint8_t reset_witness_mask[64];
static int64_t benchmark_started;static double dc_expected;
static int64_t esp_timer_get_time(void){return 1;}
static void vTaskDelay(int ticks){(void)ticks;}
static void object_image_prepare(object_image *image,unsigned warmup,unsigned seed){assert(warmup==4&&seed==BENCH_SEED);image->position=0;}
static void verify_parameters(object_image *image){(void)image;}
static void dispatch(object_image *image,const bench_case *test,unsigned block,profile_metrics *metrics){(void)image;(void)test;(void)block;(void)metrics;}
static void collect(object_image *image,profile_metrics *metrics){(void)image;(void)metrics;}
static void object_image_destroy_context(object_image *image){(void)image;}
static int16_t pcm(float value){return(int16_t)lrintf(value*.5f*32767.f);}
static void step(object_image *image,unsigned block,profile_metrics *metrics,bool measured){
 (void)metrics;(void)measured;
 for(unsigned i=0;i<256;++i)for(unsigned c=0;c<2;++c)outputs[c][i]=oracle_cache[((size_t)block*256+i)*2+c];
 /* Wrong unchanged observer: -0 becomes +0. Numeric comparison cannot see it. */
 if(block==0)outputs[1][0]=0.0f;
 image->position+=256;
}
'''+function+r'''
int main(void){
 for(unsigned n=0;n<BENCH_BLOCKS*256;++n){oracle_cache[2*n]=0;oracle_cache[2*n+1]=-0.0f;}
 object_image image={0};bench_case test={0};compare_metrics comparison={0};double squares[2]={0};
 profile_metrics metrics={0};semantic_metrics semantic={0},dc={0};
 run_pass(&image,0,&test,true,&comparison,squares,&metrics,&semantic,&dc);
 assert(semantic.max_abs==0 && semantic.samples==BENCH_BLOCKS*512u);
 assert(semantic.bit_different==1 && semantic.zero_sign_different==1);
 assert(semantic.observer_samples==BENCH_BLOCKS*256u && semantic.observer_bit_different==1);
 assert(observer_bit_sample_checks==semantic.observer_samples && observer_bit_differences==1);
 assert(wave4_bit_sample_checks==semantic.samples && wave4_bit_differences==1 && wave4_zero_sign_differences==1);
}
'''
        directory=Path(self.temp.name);path=directory/'run-pass-observer.c';binary=directory/'run-pass-observer'
        path.write_text(program)
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-UNDEBUG',
                        '-I'+str(ROOT/'object-benchmark/main'),str(path),'-o',str(binary),'-lm'],check=True)
        subprocess.run([str(binary)],check=True,timeout=10)

    def test_model_and_warmup_admission_are_closed(self):
        for model,warmup in ((0,4),(9,4),(8,0),(8,3),(8,5)):
            state=State();self.assertFalse(self.lib.object_wave4_oracle_init(C.byref(state),model,warmup))

if __name__=='__main__':unittest.main()
