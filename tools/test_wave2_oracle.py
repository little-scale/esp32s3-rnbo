#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Portable native proof for the independent target wave2 reference caches."""
import array
import ctypes as C
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/'tests/fixtures/objects/wave2/catalog.json').read_text())
FIXTURES=[next(f for f in CATALOG['fixtures'] if f['id']==name)
          for name in ('biquad-response','nonlinear-domains')]
COEFFICIENTS=((.5,.25,.125,-.4,.2),(1,0,0,0,0),(.05,0,0,-.95,0))
EXPONENTS=(2,.25,4)

class State(C.Structure):
    _fields_=[(x,C.c_uint32) for x in ('magic','kind','case_index','next_frame')]+[
        ('coefficients',C.c_double*5)]+[(x,C.c_double*2) for x in ('x1','x2','y1','y2')]

def inputs(kind,frames):
    if kind==2:
        return ([1. if i==0 else -.5 if i==4096 else 0. for i in range(frames)],
                [.25 if i<8192 else -.125 for i in range(frames)])
    return ([(-4,-2,-1,-.5,0,.5,1,2,4)[(i//64)%9] for i in range(frames)],
            [(-3,-2,-1,-.5,0,.25,.5,1,1.5,2,3)[(i//64)%11] for i in range(frames)])

def truth(kind,selected,source):
    result=[[],[]]
    if kind==2:
        a0,a1,a2,b1,b2=COEFFICIENTS[selected]
        for c,channel in enumerate(source):
            x1=x2=y1=y2=0.
            for x in channel:
                y=a0*x+a1*x1+a2*x2-b1*y1-b2*y2
                result[c].append(y);x2=x1;x1=x;y2=y1;y1=y
    else:
        result[0]=[math.tanh(x) for x in source[0]]
        result[1]=[max(0,min(1,x-2*math.floor((x+1)/2)))**EXPONENTS[selected] for x in source[1]]
    return result

def interleave(channels):return array.array('f',(x for pair in zip(*channels) for x in pair))
def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]

class Wave2OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.directory=Path(cls.temp.name)
        library=cls.directory/'wave2.dylib'
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror',
            '-shared','-fPIC',str(ROOT/'object-benchmark/main/wave2_oracle.c'),'-o',str(library),'-lm'],check=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.object_wave2_oracle_init.argtypes=[C.POINTER(State),C.c_uint32,C.POINTER(C.c_double),C.c_double,C.c_uint32]
        cls.lib.object_wave2_oracle_fill.argtypes=[C.POINTER(State),C.POINTER(C.c_float),C.c_uint32,C.c_uint32,
            C.c_uint32,C.POINTER(C.c_float),C.c_uint32,C.POINTER(C.c_double)]
        cls.lib.object_wave2_oracle_step.argtypes=[C.POINTER(State),C.POINTER(C.c_float),C.POINTER(C.c_double)]
        cls.lib.object_wave2_biquad_dc_gain.argtypes=[C.POINTER(State),C.POINTER(C.c_double)]
        for name in ('object_wave2_oracle_init','object_wave2_oracle_fill','object_wave2_oracle_step','object_wave2_biquad_dc_gain'):
            getattr(cls.lib,name).restype=C.c_bool
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def init(self,kind,selected):
        state=State();values=(C.c_double*5)(*(COEFFICIENTS[selected] if kind==2 else (0,)*5))
        self.assertTrue(self.lib.object_wave2_oracle_init(C.byref(state),kind,values,0 if kind==2 else EXPONENTS[selected],4))
        return state
    def fill(self,kind,selected,source,chunks):
        values=interleave(source);input=(C.c_float*len(values))(*values)
        total=len(source[0]);out=(C.c_float*(total*2))();state=self.init(kind,selected);rounding=C.c_double(0)
        first=index=0
        while first<total:
            frames=min(chunks[index%len(chunks)],total-first)
            ptr=C.cast(C.byref(out,first*8),C.POINTER(C.c_float))
            self.assertTrue(self.lib.object_wave2_oracle_fill(C.byref(state),input,total,first,frames,ptr,2*frames,C.byref(rounding)))
            first+=frames;index+=1
        self.assertEqual(state.next_frame,total)
        return out,rounding.value,state
    def test_six_original_cases_match_float64_python_model_and_rounding_bound(self):
        for kind in (2,3):
            source=inputs(kind,512*256)
            for selected in range(3):
                with self.subTest(kind=kind,selected=selected):
                    expected=truth(kind,selected,source);rounded=interleave(expected)
                    out,error,state=self.fill(kind,selected,source,[256])
                    self.assertEqual(bytes(out),rounded.tobytes())
                    maximum=max(abs(x-f32(x)) for channel in expected for x in channel)
                    self.assertAlmostEqual(error,maximum,delta=1e-15)
                    for chunks in ([1],[63,257,4096,7],[8191,8192,8193]):
                        other,other_error,_=self.fill(kind,selected,source,chunks)
                        self.assertEqual(bytes(out),bytes(other));self.assertEqual(error,other_error)
                    if kind==2:
                        self.assertEqual(tuple(state.coefficients),COEFFICIENTS[selected])
                        dc=C.c_double();self.assertTrue(self.lib.object_wave2_biquad_dc_gain(C.byref(state),C.byref(dc)))
                        a0,a1,a2,b1,b2=COEFFICIENTS[selected]
                        self.assertEqual(-.125*dc.value,-.125*((a0+a1+a2)/(1+b1+b2)))
                        self.assertLess(abs(sum(out[-2047::2])/1024-(-.125*dc.value)),3e-6)
    def test_raw_float64_steps_match_python_and_zero_warmup(self):
        for kind in (2,3):
            source=inputs(kind,16384)
            for selected in range(3):
                state=self.init(kind,selected);expected=truth(kind,selected,source)
                output=(C.c_double*2)()
                for n,pair in enumerate(zip(*source)):
                    self.assertTrue(self.lib.object_wave2_oracle_step(C.byref(state),(C.c_float*2)(*pair),output))
                    self.assertAlmostEqual(output[0],expected[0][n],delta=1e-15)
                    self.assertAlmostEqual(output[1],expected[1][n],delta=1e-15)
                warm=self.init(kind,selected)
                for _ in range(1024):
                    self.assertTrue(self.lib.object_wave2_oracle_step(C.byref(warm),(C.c_float*2)(0,0),output))
                    self.assertEqual(tuple(output),(0,0))
    def test_init_rejects_unknown_kind_coefficients_exponents_and_warmup(self):
        state=State();state.magic=123;before=bytes(state)
        zero=(C.c_double*5)(0,0,0,0,0);default=(C.c_double*5)(*COEFFICIENTS[0])
        for kind,coefficients,exponent,warmup in [(0,default,0,4),(1,default,0,4),(4,default,0,4),
            (2,default,0,0),(2,default,0,5),(2,default,2,4),(2,zero,0,4),
            (3,default,2,4),(3,zero,.5,4),(3,zero,float('nan'),4)]:
            self.assertFalse(self.lib.object_wave2_oracle_init(C.byref(state),kind,coefficients,exponent,warmup))
            self.assertEqual(bytes(state),before)
        # Canonicalizing the mathematical coefficients to Float32 changes truth.
        rounded=(C.c_double*5)(*(f32(x) for x in COEFFICIENTS[0]))
        self.assertFalse(self.lib.object_wave2_oracle_init(C.byref(state),2,rounded,0,4))
        self.assertFalse(self.lib.object_wave2_oracle_init(None,2,default,0,4))
        self.assertFalse(self.lib.object_wave2_oracle_init(C.byref(state),2,None,0,4))
    def test_invalid_range_state_capacity_and_nonfinite_input_do_not_advance(self):
        state=self.init(2,0);before=bytes(state)
        input=(C.c_float*128)();out=(C.c_float*128)(*([42]*128));rounding=C.c_double(0)
        for total,first,frames,capacity in [(64,1,1,2),(64,0,0,2),(64,63,2,4),(64,0,2,3),(262145,0,1,2)]:
            self.assertFalse(self.lib.object_wave2_oracle_fill(C.byref(state),input,total,first,frames,out,capacity,C.byref(rounding)))
            self.assertEqual(bytes(state),before)
        for bad in (float('nan'),float('inf'),1.01):
            input[100]=bad
            self.assertFalse(self.lib.object_wave2_oracle_fill(C.byref(state),input,64,0,64,out,128,C.byref(rounding)))
            self.assertEqual(bytes(state),before);self.assertTrue(all(x==42 for x in out))
        for bad in (float('nan'),float('inf'),-1):
            self.assertFalse(self.lib.object_wave2_oracle_fill(C.byref(state),input,64,0,1,out,2,C.byref(C.c_double(bad))))
        state.magic=0
        self.assertFalse(self.lib.object_wave2_oracle_step(C.byref(state),(C.c_float*2)(0,0),(C.c_double*2)()))
        nonlinear=self.init(3,1);before=bytes(nonlinear)
        for left,right in [(4.01,0),(0,3.01),(float('nan'),0),(0,float('inf'))]:
            self.assertFalse(self.lib.object_wave2_oracle_step(C.byref(nonlinear),(C.c_float*2)(left,right),(C.c_double*2)()))
            self.assertEqual(bytes(nonlinear),before)
    def test_numerical_error_is_charged_inside_unchanged_limits(self):
        for kind,limit in ((2,3e-6),(3,2e-6)):
            cache,error,_=self.fill(kind,0,inputs(kind,16384),[256])
            wrong=list(cache);wrong[0]+=1e-4
            self.assertGreater(max(abs(a-b) for a,b in zip(cache,wrong))+error,limit)
        # Clipping1.5 before wrapping would incorrectly output1 instead of0.
        self.assertEqual(max(0,min(1,1.5-2*math.floor((1.5+1)/2)))**2,0)
        self.assertEqual(max(0,min(1,1.5))**2,1)
    def test_available_original_native_renders_pass_same_semantic_limits(self):
        base=ROOT/'build/object-qualification/wave2-final/renders'
        if not base.exists():self.skipTest('Optional local original RNBO render evidence unavailable')
        for kind,fixture,limit in ((2,FIXTURES[0],3e-6),(3,FIXTURES[1],2e-6)):
            source=inputs(kind,512*256)
            for selected,case in enumerate(fixture['cases']):
                path=base/fixture['id']/'float32-strict'/(case['id']+'.f32')
                if not path.exists():self.skipTest('Optional local original RNBO render unavailable')
                actual=array.array('f');actual.frombytes(path.read_bytes())
                cache,error,_=self.fill(kind,selected,source,[256])
                self.assertEqual(len(actual),len(cache))
                self.assertLessEqual(max(abs(a-b) for a,b in zip(actual,cache))+error,limit)
    def test_real_run_pass_uses_final1024_mean_and_one_dc_check_per_profile_round(self):
        source=(ROOT/'object-benchmark/main/benchmark.c').read_text()
        begin=source.index('static void run_pass(');end=source.index('\nstatic void worker(',begin)
        function=source[begin:end]
        declarations=[]
        for name in ('profile_metrics','compare_metrics','semantic_metrics'):
            match=re.search(r'typedef struct \{[^}]*\} '+name+r';',source,re.S)
            self.assertIsNotNone(match);declarations.append(match[0])
        program=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <math.h>
#include <stddef.h>
#include "stimulus.h"
#include "wave2_oracle.h"
#define CHECK(x) assert(x)
#define BENCH_ROLE 1
#define RNBO_S3_FX 1
#define RNBO_S3_BLOCK_FRAMES 256
#define BENCH_BLOCKS 512
#define BENCH_WARMUP 4
#define BENCH_SEED 0x12345678u
typedef struct { uint64_t position; } object_image;
typedef struct { unsigned ignored; } bench_case;
'''+'\n'.join(declarations)+r'''
static float reference[BENCH_BLOCKS*512],oracle_cache[BENCH_BLOCKS*512];
static float planar[4][256],*outputs[2]={planar[0],planar[1]},*inputs[2]={planar[2],planar[3]};
static struct { unsigned kind; } verification={OBJECT_WAVE2_BIQUAD},*active_verification=&verification;
static object_stimulus stimulus,*active_stimulus=&stimulus;
static uint64_t dc_sample_checks,semantic_sample_checks,pilot_sample_checks;
static uint64_t oracle_bit_sample_checks,oracle_bit_differences;
static int64_t benchmark_started;
static double dc_expected=-.125;
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
 image->position+=256;
}
'''+function+r'''
int main(void){
 for(unsigned n=0;n<BENCH_BLOCKS*256;++n){
  oracle_cache[2*n]=0;oracle_cache[2*n+1]=-.125f;
  if(n>=BENCH_BLOCKS*256-1024)oracle_cache[2*n+1]+=(n&1)?0x1p-10f:-0x1p-10f;
 }
 assert(fabs((double)oracle_cache[BENCH_BLOCKS*512-1]-dc_expected)>3e-6);
 object_image image={0};bench_case test={0};compare_metrics comparison={0};double squares[2]={0};
 profile_metrics metrics[2]={{0}};semantic_metrics semantic[2]={{0}},dc[2]={{0}};
 for(unsigned round=0;round<3;++round)for(unsigned p=0;p<2;++p)
  run_pass(&image,p,&test,p==0,&comparison,squares,&metrics[p],&semantic[p],&dc[p]);
 assert(dc_sample_checks==6&&dc[0].samples==3&&dc[1].samples==3);
 assert(dc[0].max_abs==0&&dc[1].max_abs==0&&comparison.max_abs==0);
 assert(semantic_sample_checks==3u*2u*BENCH_BLOCKS*512u&&pilot_sample_checks==0);
}
'''
        path=self.directory/'run-pass.c';binary=self.directory/'run-pass';path.write_text(program)
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-UNDEBUG',
            '-I'+str(ROOT/'object-benchmark/main'),str(path),'-o',str(binary),'-lm'],check=True)
        subprocess.run([str(binary)],check=True)
    def test_ubsan_maximum_size_and_partial_chunk_stress(self):
        program=r'''
#include "wave2_oracle.h"
#include "stimulus.h"
#include <assert.h>
#include <math.h>
#include <stdlib.h>
int main(void){
 const unsigned total=OBJECT_WAVE2_MAX_FRAMES;
 float *input=calloc(total*2,sizeof(float)),*output=calloc(total*2,sizeof(float));assert(input&&output);
 const double coefficients[3][5]={{.5,.25,.125,-.4,.2},{1,0,0,0,0},{.05,0,0,-.95,0}};
 const double zero[5]={0},exponents[3]={2,.25,4};const unsigned chunks[]={1,63,64,255,256,257,4095,8193};
 for(unsigned kind=2;kind<=3;++kind){
  object_stimulus stimulus={.kind=kind==2?4:6};assert(object_stimulus_fill(&stimulus,0,total,input));
  for(unsigned selected=0;selected<3;++selected){
   object_wave2_oracle state;double rounding=0;
   assert(object_wave2_oracle_init(&state,kind,kind==2?coefficients[selected]:zero,kind==2?0:exponents[selected],4));
   unsigned first=0,index=0;
   while(first<total){unsigned frames=chunks[index++%8];if(frames>total-first)frames=total-first;
    assert(object_wave2_oracle_fill(&state,input,total,first,frames,output+2*first,2*frames,&rounding));first+=frames;}
   assert(state.next_frame==total&&rounding<=0x1p-24);
   for(unsigned n=0;n<total*2;++n)assert(isfinite(output[n]));
   assert(!object_wave2_oracle_fill(&state,input,total,total,1,output,2,&rounding));
  }
 }
 free(input);free(output);
}
'''
        path=self.directory/'sanitizer.c';binary=self.directory/'sanitizer';path.write_text(program)
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-UNDEBUG',
            '-fsanitize=undefined,float-cast-overflow','-fno-sanitize-recover=all',
            '-I'+str(ROOT/'object-benchmark/main'),str(path),str(ROOT/'object-benchmark/main/wave2_oracle.c'),
            str(ROOT/'object-benchmark/main/stimulus.c'),'-o',str(binary),'-lm'],check=True)
        subprocess.run([str(binary)],check=True,timeout=20)

if __name__=='__main__':unittest.main()
