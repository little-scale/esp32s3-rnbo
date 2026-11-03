#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent binary32 input/cache and exact-bit dispatch regression tests.

This tests the target's representative grid, not all finite binary32 words.
The separate private mathematical proof exhausts the full finite domain.
"""
import array
import ctypes as C
from fractions import Fraction
import hashlib
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
FRAMES=512*256
MAGNITUDES=(0,1,0x7fffff,0x800000,0x3f7fffff,0x3f800000,0x3f800001,
    0x40000000,0x40400000,0x4b7fffff,0x4b800000,0x4b800001,0x4bffffff,
    0x4c000000,0x4c000001,0x4effffff,0x4f000000,0x4f000001,0x4f7fffff,
    0x4f800000,0x4f800001,0x7f7fffff)
MANTISSAS=(0,1,2,0x3fffff,0x400000,0x7ffffd,0x7ffffe,0x7fffff)

class Stimulus(C.Structure):
    _fields_=[('kind',C.c_uint32)]+[(name,C.c_double) for name in
        ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')]

def input_word(kind,frame,channel):
    if kind in (7,10):
        index=frame+(13 if kind==7 else 7)*channel
        return ((index%2)<<31)|MAGNITUDES[(index//2)%(22 if kind==7 else 9)]
    index=frame+2039*channel
    lane=index%16
    return ((lane//8)<<31)|(((index//16)%(151 if kind==8 else 255))<<23)|MANTISSAS[lane%8]

def exact_truth(word):
    """Rational arithmetic oracle, independent of the C packing algorithm."""
    magnitude=word&0x7fffffff
    if magnitude>=0x7f800000:raise ValueError('Nonfinite')
    if not magnitude:return word  # Preserve input signed zero.
    exponent=magnitude>>23
    mantissa=magnitude&0x7fffff
    significand=mantissa if not exponent else mantissa+(1<<23)
    shift=-149 if not exponent else exponent-150
    value=Fraction(significand<<max(shift,0),1<<max(-shift,0))
    if word>>31:value=-value
    # Half-open [-1,1), with exact even-integer zeros canonicalized positive.
    result=value-2*((value+1)//2)
    return struct.unpack('<I',struct.pack('<f',float(result)))[0]

class WrapFiniteOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.directory=Path(cls.temp.name)
        library=cls.directory/'wrap.dylib'
        subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
            str(ROOT/'object-benchmark/main/stimulus.c'),str(ROOT/'object-benchmark/main/wave2_oracle.c'),
            '-o',str(library),'-lm'],check=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.object_stimulus_fill.argtypes=[C.POINTER(Stimulus),C.c_uint32,C.c_uint32,C.POINTER(C.c_float)]
        cls.lib.object_wrap_finite_oracle_word.argtypes=[C.c_uint32,C.POINTER(C.c_uint32)]
        cls.lib.object_wrap_finite_oracle_fill.argtypes=[C.POINTER(C.c_float),C.c_uint32,C.c_uint32,
            C.c_uint32,C.POINTER(C.c_float),C.c_uint32]
        for name in ('object_stimulus_fill','object_wrap_finite_oracle_word','object_wrap_finite_oracle_fill'):
            getattr(cls.lib,name).restype=C.c_bool
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def fill(self,kind,frames=FRAMES):
        source=(C.c_float*(frames*2))()
        self.assertTrue(self.lib.object_stimulus_fill(C.byref(Stimulus(kind=kind)),0,frames,source))
        return source
    def test_four_complete_input_caches_and_chunk_boundaries_match_independent_words(self):
        for kind in range(7,11):
            with self.subTest(kind=kind):
                source=self.fill(kind)
                expected=array.array('I',(input_word(kind,f,c) for f in range(FRAMES) for c in range(2)))
                self.assertEqual(bytes(source),expected.tobytes())
                other=(C.c_float*(FRAMES*2))();first=index=0;chunks=(1,63,64,255,256,257,4095,8193)
                while first<FRAMES:
                    frames=min(chunks[index%len(chunks)],FRAMES-first)
                    pointer=C.cast(C.byref(other,first*8),C.POINTER(C.c_float))
                    self.assertTrue(self.lib.object_stimulus_fill(C.byref(Stimulus(kind=kind)),first,frames,pointer))
                    first+=frames;index+=1
                self.assertEqual(bytes(source),bytes(other))
                self.assertEqual(hashlib.sha256(bytes(source)).digest(),hashlib.sha256(expected.tobytes()).digest())
    def test_distinct_coverage_is_4080_values_not_repeated_target_check_count(self):
        union=set()
        for kind,count in ((7,44),(8,2416),(9,4080),(10,18)):
            values=[{input_word(kind,f,c) for f in range(FRAMES)} for c in range(2)]
            self.assertEqual(len(values[0]),count);self.assertEqual(values[0],values[1])
            self.assertTrue(all((word&0x7fffffff)<0x7f800000 for word in values[0]));union.update(values[0])
        self.assertEqual(len(union),4080)
        self.assertEqual({(word>>23)&255 for word in union},set(range(255)))
        self.assertEqual({word&0x7fffff for word in union},set(MANTISSAS))
        self.assertEqual({word>>31 for word in union},{0,1})
    def test_all_distinct_words_match_exact_fraction_oracle_including_negative_zero(self):
        values={input_word(9,f,c) for f in range(4080) for c in range(2)}
        values.update(sign|m for sign in (0,0x80000000) for m in MAGNITUDES)
        for word in sorted(values):
            actual=C.c_uint32(0xdeadbeef)
            self.assertTrue(self.lib.object_wrap_finite_oracle_word(word,C.byref(actual)))
            self.assertEqual(actual.value,exact_truth(word),hex(word))
        self.assertEqual(exact_truth(0x80000000),0x80000000)
        self.assertEqual(exact_truth(0x3f800000),0xbf800000)
        self.assertEqual(exact_truth(0xbf800000),0xbf800000)
        self.assertEqual(exact_truth(0x7f7fffff),0)
    def test_cache_chunks_are_bit_exact_and_invalid_inputs_do_not_write(self):
        source=self.fill(9);output=(C.c_float*(FRAMES*2))();first=index=0;chunks=(1,63,257,4095,8193)
        while first<FRAMES:
            frames=min(chunks[index%len(chunks)],FRAMES-first)
            pointer=C.cast(C.byref(output,first*8),C.POINTER(C.c_float))
            self.assertTrue(self.lib.object_wrap_finite_oracle_fill(source,FRAMES,first,frames,pointer,frames*2))
            first+=frames;index+=1
        oracle={word:exact_truth(word) for word in {input_word(9,f,0) for f in range(4080)}}
        expected=array.array('I',(oracle[input_word(9,f,c)] for f in range(FRAMES) for c in range(2)))
        self.assertEqual(bytes(output),expected.tobytes())
        sentinel=(C.c_float*16)(*([42]*16));before=bytes(sentinel)
        for total,first,frames,capacity in ((0,0,1,2),(FRAMES+1,0,1,2),(8,0,0,2),(8,9,1,2),(8,7,2,4),(8,0,2,3)):
            # A frame total larger than FRAMES remains allowed up to the public1024-block limit.
            if total==FRAMES+1:total=1024*256+1
            self.assertFalse(self.lib.object_wrap_finite_oracle_fill(source,total,first,frames,sentinel,capacity))
            self.assertEqual(bytes(sentinel),before)
        for word in (0x7f800000,0xff800000,0x7fc00000,0xffc00001):
            result=C.c_uint32(123)
            self.assertFalse(self.lib.object_wrap_finite_oracle_word(word,C.byref(result)))
            self.assertEqual(result.value,123)
            bad=(C.c_uint32*16)();bad[15]=word
            self.assertFalse(self.lib.object_wrap_finite_oracle_fill(C.cast(bad,C.POINTER(C.c_float)),8,0,8,sentinel,16))
            self.assertEqual(bytes(sentinel),before)
    def test_real_run_pass_detects_negative_zero_bit_error_when_numeric_error_is_zero(self):
        source=(ROOT/'object-benchmark/main/benchmark.c').read_text()
        begin=source.index('static void run_pass(');end=source.index('\nstatic void worker(',begin)
        declarations=[]
        for name in ('profile_metrics','compare_metrics','semantic_metrics'):
            declarations.append(re.search(r'typedef struct \{[^}]*\} '+name+r';',source,re.S)[0])
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
#include "gen_arithmetic_oracle.h"
#define CHECK(x) assert(x)
#define BENCH_ROLE 1
#define RNBO_S3_FX 1
#define RNBO_S3_BLOCK_FRAMES 256
#define BENCH_BLOCKS 512
#define BENCH_WARMUP 4
#define BENCH_SEED 0x12345678u
#define BENCH_GEN_ARITH 0
typedef struct { uint64_t position; } object_image;
typedef struct { unsigned ignored; } bench_case;
'''+ '\n'.join(declarations)+r'''
static float reference[BENCH_BLOCKS*512],oracle_cache[BENCH_BLOCKS*512];
static float planar[4][256],*outputs[2]={planar[0],planar[1]},*inputs[2]={planar[2],planar[3]};
static struct { unsigned kind,window; double maximum_error; } verification={OBJECT_WAVE2_WRAP_FINITE,0,0},*active_verification=&verification;
static object_stimulus stimulus,*active_stimulus=&stimulus;
static uint64_t dc_sample_checks,semantic_sample_checks,pilot_sample_checks;
static uint64_t oracle_bit_sample_checks,oracle_bit_differences;
static uint64_t wave4_bit_sample_checks,wave4_bit_differences,wave4_zero_sign_differences,observer_bit_sample_checks,observer_bit_differences;
static uint64_t gen_arith_bit_sample_checks,gen_arith_bit_differences,gen_arith_zero_sign_differences;
static uint8_t reset_witness_mask[64];
static int64_t benchmark_started;
static double dc_expected;
static bool corrupt;
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
 for(unsigned i=0;i<256;++i)for(unsigned c=0;c<2;++c)
  outputs[c][i]=corrupt?0.f:oracle_cache[((size_t)block*256+i)*2+c];
 image->position+=256;
}
'''+source[begin:end]+r'''
int main(void){
 uint32_t negative_zero=0x80000000u;
 for(unsigned n=0;n<BENCH_BLOCKS*512;++n)__builtin_memcpy(oracle_cache+n,&negative_zero,4);
 object_image image={0};bench_case test={0};compare_metrics comparison={0};double squares[2]={0};
 profile_metrics metrics[2]={{0}};semantic_metrics semantic[2]={{0}},dc[2]={{0}};
 run_pass(&image,0,&test,true,&comparison,squares,&metrics[0],&semantic[0],&dc[0]);
 assert(semantic[0].bit_different==0&&oracle_bit_differences==0);
 corrupt=true;
 run_pass(&image,1,&test,false,&comparison,squares,&metrics[1],&semantic[1],&dc[1]);
 assert(semantic[1].max_abs==0&&comparison.max_abs==0&&comparison.pcm_different==0);
 assert(semantic[1].bit_different==BENCH_BLOCKS*512u&&oracle_bit_differences==BENCH_BLOCKS*512u);
 assert(oracle_bit_sample_checks==2u*BENCH_BLOCKS*512u&&semantic_sample_checks==oracle_bit_sample_checks);
 assert(dc_sample_checks==0&&pilot_sample_checks==0);
}
'''
        self.compile_run('run-pass-bits',program,False)
    def compile_run(self,name,program,sanitize):
        path=self.directory/(name+'.c');binary=self.directory/name;path.write_text(program)
        command=['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-UNDEBUG',
            '-I'+str(ROOT/'object-benchmark/main'),str(path)]
        if sanitize:command+=['-fsanitize=undefined,float-cast-overflow','-fno-sanitize-recover=all',
            str(ROOT/'object-benchmark/main/wave2_oracle.c')]
        subprocess.run(command+['-o',str(binary),'-lm'],check=True)
        subprocess.run([str(binary)],check=True,timeout=20)
    def test_ubsan_scalar_and_maximum_cache_stress(self):
        program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include "wave2_oracle.h"
#include "wave4_oracle.h"
#include "gen_history_oracle.h"
#include "gen_arithmetic_oracle.h"
int main(void){
 uint32_t random=123456789u,result;
 for(unsigned n=0;n<1000000;++n){
  random=random*1664525u+1013904223u;
  bool finite=(random&0x7fffffffu)<0x7f800000u;
  assert(object_wrap_finite_oracle_word(random,&result)==finite);
  if(finite)assert((result&0x7fffffffu)<=0x3f800000u);
 }
 unsigned frames=OBJECT_WAVE2_MAX_FRAMES;
 float *input=calloc(frames*2,sizeof(float)),*out=calloc(frames*2,sizeof(float));assert(input&&out);
 for(unsigned first=0;first<frames;){unsigned count=frames-first<257?frames-first:257;
  assert(object_wrap_finite_oracle_fill(input,frames,first,count,out+first*2,count*2));first+=count;}
 free(input);free(out);
}
'''
        self.compile_run('ubsan-wrap',program,True)

if __name__=='__main__':unittest.main()
