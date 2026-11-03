#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Portable dense-input, block-event mathematical model and pair diagnostics."""
import array
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/'tests/fixtures/objects/wave2/power-modes-target.json').read_text())
CASES=CATALOG['fixtures'][0]['cases']
FRAMES=512*256
EDGES=(0,0x80000000,1,0x80000001,0x7fffff,0x807fffff,0x800000,0x80800000,
    0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f7fffff,0xbf7fffff,0x3f800000,0xbf800000,
    0x3f800001,0xbf800001,0x3fc00000,0xbfc00000,0x3fffffff,0xbfffffff,0x40000000,0xc0000000,
    0x40000001,0xc0000001,0x40400000,0xc0400000,0x40800000,0xc0800000)
def word(frame,channel):
    if frame%16==0:return EDGES[(frame//16+(13 if channel else 0))%(28 if channel else 30)]
    if channel:
        hashed=(frame*1664525+1013904223)&0xffffffff
        exponent=127-frame%4 if frame%4 else (frame//4)%127
        return (exponent<<23)|(hashed&0x7fffff)
    hashed=((frame+2039)*22695477+1)&0xffffffff
    return (hashed&0x80000000)|((124+(frame//4)%5)<<23)|(hashed&0x7fffff)
def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]
class Stimulus(C.Structure):
    _fields_=[('kind',C.c_uint32)]+[(name,C.c_double) for name in
        ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')]
class State(C.Structure):
    _fields_=[(name,C.c_uint32) for name in ('magic','kind','case_index','next_frame')]+[
        ('coefficients',C.c_double*5)]+[(name,C.c_double*2) for name in ('x1','x2','y1','y2')]

class PowerModesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.directory=Path(cls.temp.name)
        library=cls.directory/'power.dylib'
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror',
            '-shared','-fPIC',str(ROOT/'object-benchmark/main/stimulus.c'),str(ROOT/'object-benchmark/main/wave2_oracle.c'),'-o',str(library),'-lm'],check=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.object_stimulus_fill.argtypes=[C.POINTER(Stimulus),C.c_uint32,C.c_uint32,C.POINTER(C.c_float)]
        cls.lib.object_wave2_oracle_init.argtypes=[C.POINTER(State),C.c_uint32,C.POINTER(C.c_double),C.c_double,C.c_uint32]
        cls.lib.object_wave2_oracle_set_exponent.argtypes=[C.POINTER(State),C.c_float]
        cls.lib.object_wave2_oracle_fill.argtypes=[C.POINTER(State),C.POINTER(C.c_float),C.c_uint32,C.c_uint32,
            C.c_uint32,C.POINTER(C.c_float),C.c_uint32,C.POINTER(C.c_double)]
        for name in ('object_stimulus_fill','object_wave2_oracle_init','object_wave2_oracle_set_exponent','object_wave2_oracle_fill'):
            getattr(cls.lib,name).restype=C.c_bool
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def source(self,kind):
        source=(C.c_float*(FRAMES*2))()
        self.assertTrue(self.lib.object_stimulus_fill(C.byref(Stimulus(kind=kind)),0,FRAMES,source))
        return source
    def init(self,exponent=2,kind=5):
        state=State();self.assertTrue(self.lib.object_wave2_oracle_init(C.byref(state),kind,(C.c_double*5)(),exponent,4));return state
    def test_complete_dense_cache_matches_raw_integer_contract_and_chunks(self):
        source=self.source(11);expected=array.array('I',(word(f,c) for f in range(FRAMES) for c in range(2)))
        self.assertEqual(bytes(source),expected.tobytes())
        self.assertEqual(hashlib.sha256(bytes(source)).digest(),hashlib.sha256(expected.tobytes()).digest())
        other=(C.c_float*(FRAMES*2))();first=index=0;chunks=(1,15,16,17,63,256,257,8193)
        while first<FRAMES:
            frames=min(chunks[index%len(chunks)],FRAMES-first)
            self.assertTrue(self.lib.object_stimulus_fill(C.byref(Stimulus(kind=11)),first,frames,C.cast(C.byref(other,first*8),C.POINTER(C.c_float))))
            first+=frames;index+=1
        self.assertEqual(bytes(source),bytes(other))
        self.assertTrue(all(math.isfinite(x) for x in source))
        self.assertTrue(all(-4<=source[2*f]<=4 and -3<=source[2*f+1]<=3 for f in range(FRAMES)))
        right=set(expected[1::2]);left=set(expected[::2])
        self.assertTrue(set(EDGES[:28])<=right and set(EDGES)<=left)
        self.assertGreater(len(right),100000);self.assertGreater(len(left),100000)
        self.assertTrue({0,0x80000000,1,0x80000001,0x800000,0x80800000}<=right)
    def test_all_fifteen_cases_replay_actual_float32_events_before_each_block(self):
        for selected,case in enumerate(CASES):
            with self.subTest(case=case['id']):
                source=self.source(6 if selected<3 else 11);state=self.init();rounding=C.c_double(0)
                output=(C.c_float*(FRAMES*2))();expected=array.array('f');max_rounding=0
                schedule={0:case['parameters']['exponent']} if 'exponent' in case['parameters'] else {}
                schedule.update({e['block']:e['value'] for e in case['events']});exponent=2.
                for block in range(512):
                    if block in schedule:
                        exponent=f32(schedule[block]);self.assertTrue(self.lib.object_wave2_oracle_set_exponent(C.byref(state),exponent))
                    ptr=C.cast(C.byref(output,block*256*8),C.POINTER(C.c_float))
                    self.assertTrue(self.lib.object_wave2_oracle_fill(C.byref(state),source,FRAMES,block*256,256,ptr,512,C.byref(rounding)))
                    for frame in range(block*256,(block+1)*256):
                        a=float(source[2*frame]);b=float(source[2*frame+1]);wrapped=b-2*math.floor((b+1)/2)
                        values=(math.tanh(a),math.pow(max(0,min(1,wrapped)),exponent))
                        expected.extend(values);max_rounding=max(max_rounding,*(abs(x-f32(x)) for x in values))
                self.assertEqual(bytes(output),expected.tobytes())
                self.assertEqual(state.next_frame,FRAMES);self.assertAlmostEqual(rounding.value,max_rounding,delta=1e-15)
                self.assertLessEqual(rounding.value,2**-24)
    def test_actual_event_domain_and_block_boundary_reject_without_state_change(self):
        state=self.init();before=bytes(state)
        for exponent in (float('nan'),float('inf'),0,-1,.2499999850988388,4.000000476837158):
            self.assertFalse(self.lib.object_wave2_oracle_set_exponent(C.byref(state),exponent));self.assertEqual(bytes(state),before)
        source=(C.c_float*2)();output=(C.c_float*2)();rounding=C.c_double(0)
        self.assertTrue(self.lib.object_wave2_oracle_fill(C.byref(state),source,1,0,1,output,2,C.byref(rounding)))
        before=bytes(state);self.assertFalse(self.lib.object_wave2_oracle_set_exponent(C.byref(state),.5));self.assertEqual(bytes(state),before)
        old=self.init(kind=3);self.assertFalse(self.lib.object_wave2_oracle_set_exponent(C.byref(old),.5))
        state=State();state.magic=99;before=bytes(state)
        for kind,exponent in ((3,.5),(3,1.5),(3,2.5),(5,.3),(5,float('nan')),(6,2)):
            self.assertFalse(self.lib.object_wave2_oracle_init(C.byref(state),kind,(C.c_double*5)(),exponent,4));self.assertEqual(bytes(state),before)
    def test_actual_prepare_stimulus_replays_compiled_events_and_canonical_wire_bytes(self):
        # Reuse admission fixtures, but compile the real generated tables and
        # production C preparation function. No target artifact is required.
        from test_build_object_benchmark import ConfigurationTests
        fixture=ConfigurationTests();fixture.setUp()
        try:
            fixture.power_modes();header,policy=fixture.generate()
        finally:fixture.tearDown()
        source=(ROOT/'object-benchmark/main/benchmark.c').read_text()
        types='\n'.join(re.search(r'typedef struct \{[^}]*\} '+name+r';',source,re.S)[0]
            for name in ('bench_event','bench_case','bench_parameter','bench_verification'))
        helper=source[source.index('static void put_u32le('):source.index('static int16_t pcm(')]
        function=source[source.index('static void prepare_stimulus('):source.index('static void excitation(')]
        program=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <math.h>
#include "stimulus.h"
#include "wave2_oracle.h"
#include "wave4_oracle.h"
#include "gen_history_oracle.h"
#include "gen_arithmetic_oracle.h"
#include "average_oracle.h"
#define CHECK(x) assert(x)
#define RNBO_S3_FX 2
#define RNBO_S3_BLOCK_FRAMES 256
'''+types+'\n'+header+r'''
static float source_cache[BENCH_BLOCKS*512],expected_cache[BENCH_BLOCKS*512];
static float *stimulus_cache=source_cache,*oracle_cache=expected_cache;
static const bench_verification *active_verification;static const object_stimulus *active_stimulus;
static double oracle_rounding_error,dc_expected;static char event_schedule_sha[65],reset_witness_sha[65];static int64_t benchmark_started;
static uint8_t reset_witness_mask[64];static uint32_t reset_witness_count;
static unsigned wire_size;static uint8_t wire[264];
static int64_t esp_timer_get_time(void){return 1;}
static void vTaskDelay(int ticks){(void)ticks;}
static void digest_hex(const uint8_t *bytes,size_t count,char result[65]){
 if(count<=sizeof wire){memcpy(wire,bytes,count);wire_size=(unsigned)count;}
 memset(result,'0',64);result[64]=0;
}
'''+helper+function+r'''
unsigned precompute(unsigned selected,uint8_t *bytes){
 assert(selected<BENCH_CASE_COUNT);char input[65],oracle[65];wire_size=0;
 prepare_stimulus(selected,input,oracle);assert(wire_size<=sizeof wire);memcpy(bytes,wire,wire_size);return wire_size;
}
float cached(unsigned frame,unsigned channel){assert(frame<BENCH_BLOCKS*256&&channel<2);return expected_cache[frame*2+channel];}
float excitation_sample(unsigned frame,unsigned channel){return source_cache[frame*2+channel];}
'''
        path=self.directory/'prepare.c';library=self.directory/'prepare.dylib';path.write_text(program)
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-UNDEBUG','-shared','-fPIC',
            '-I'+str(ROOT/'object-benchmark/main'),str(path),str(ROOT/'object-benchmark/main/stimulus.c'),
            str(ROOT/'object-benchmark/main/wave2_oracle.c'),str(ROOT/'object-benchmark/main/wave4_oracle.c'),str(ROOT/'object-benchmark/main/gen_history_oracle.c'),str(ROOT/'object-benchmark/main/gen_arithmetic_oracle.c'),str(ROOT/'object-benchmark/main/average_oracle.c'),'-o',str(library),'-lm'],check=True)
        lib=C.CDLL(str(library));lib.precompute.argtypes=[C.c_uint,C.POINTER(C.c_uint8)];lib.precompute.restype=C.c_uint
        for name in ('cached','excitation_sample'):
            getattr(lib,name).argtypes=[C.c_uint,C.c_uint];getattr(lib,name).restype=C.c_float
        for selected,(case,verification) in enumerate(zip(CASES,policy['verifications'])):
            wire=(C.c_uint8*264)();count=lib.precompute(selected,wire)
            self.assertEqual(hashlib.sha256(bytes(wire[:count])).hexdigest(),verification['event_schedule_sha256'])
            schedule={e['block']:e['value'] for e in verification['event_schedule']}
            frames={0,FRAMES-1}
            for block in schedule:
                frames.update(f for f in (block*256-1,block*256,block*256+1) if 0<=f<FRAMES)
            for frame in sorted(frames):
                exponent=2.
                for block in sorted(schedule):
                    if block*256>frame:break
                    exponent=schedule[block]
                a=lib.excitation_sample(frame,0);b=lib.excitation_sample(frame,1)
                expected=(f32(math.tanh(a)),f32(math.pow(max(0,min(1,b-2*math.floor((b+1)/2))),exponent)))
                self.assertEqual((lib.cached(frame,0),lib.cached(frame,1)),expected,(case['id'],frame))
    def test_native_real_run_pass_pair_diagnostics_count_rounding_and_signed_zero_without_exact_gate(self):
        source=(ROOT/'object-benchmark/main/benchmark.c').read_text();begin=source.index('static void run_pass(');end=source.index('\nstatic void worker(',begin)
        types='\n'.join(re.search(r'typedef struct \{[^}]*\} '+name+r';',source,re.S)[0] for name in ('profile_metrics','compare_metrics','semantic_metrics'))
        program=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <math.h>
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
typedef struct { unsigned ignored; } object_image;
typedef struct { unsigned ignored; } bench_case;
'''+types+r'''
static float reference[BENCH_BLOCKS*512],oracle_cache[BENCH_BLOCKS*512];
static float planar[4][256],*outputs[2]={planar[0],planar[1]},*inputs[2]={planar[2],planar[3]};
static struct { unsigned kind,window; double maximum_error; } verification={OBJECT_WAVE2_POWER_MODES,0,2e-6},*active_verification=&verification;
static object_stimulus stimulus,*active_stimulus=&stimulus;
static uint64_t dc_sample_checks,semantic_sample_checks,pilot_sample_checks,oracle_bit_sample_checks,oracle_bit_differences;
static uint64_t wave4_bit_sample_checks,wave4_bit_differences,wave4_zero_sign_differences,observer_bit_sample_checks,observer_bit_differences;
static uint64_t gen_arith_bit_sample_checks,gen_arith_bit_differences,gen_arith_zero_sign_differences;
static uint8_t reset_witness_mask[64];
static int64_t benchmark_started;static double dc_expected;static bool changed;
static int64_t esp_timer_get_time(void){return 1;}
static void vTaskDelay(int n){(void)n;}
static void object_image_prepare(object_image *p,unsigned warm,unsigned seed){(void)p;assert(warm==4&&seed==BENCH_SEED);}
static void verify_parameters(object_image *p){(void)p;}
static void dispatch(object_image *p,const bench_case *c,unsigned b,profile_metrics *m){(void)p;(void)c;(void)b;(void)m;}
static void collect(object_image *p,profile_metrics *m){(void)p;(void)m;}
static void object_image_destroy_context(object_image *p){(void)p;}
static int16_t pcm(float v){return(int16_t)lrintf(v*.5f*32767.f);}
static void step(object_image *p,unsigned b,profile_metrics *m,bool measured){
 (void)p;(void)b;(void)m;(void)measured;
 for(unsigned c=0;c<2;++c)for(unsigned i=0;i<256;++i)
  outputs[c][i]=(i&1)?(changed?nextafterf(.5f,1.f):.5f):(changed?-0.f:0.f);
}
'''+source[begin:end]+r'''
int main(void){
 for(unsigned f=0;f<BENCH_BLOCKS*256;++f)for(unsigned c=0;c<2;++c)oracle_cache[f*2+c]=(f&1)?.5f:0.f;
 object_image image={0};bench_case test={0};compare_metrics comparison={0};double squares[2]={0};
 profile_metrics metrics[2]={{0}};semantic_metrics semantic[2]={{0}},dc[2]={{0}};
 run_pass(&image,0,&test,true,&comparison,squares,&metrics[0],&semantic[0],&dc[0]);changed=true;
 run_pass(&image,1,&test,false,&comparison,squares,&metrics[1],&semantic[1],&dc[1]);
 assert(comparison.samples==BENCH_BLOCKS*512u&&comparison.float_bit_different==comparison.samples);
 assert(comparison.zero_sign_different==comparison.samples/2&&comparison.max_abs>0&&comparison.max_abs<2e-6&&comparison.pcm_different==0);
 assert(semantic[0].bit_different==0&&semantic[1].bit_different==0&&oracle_bit_sample_checks==0&&oracle_bit_differences==0);
 assert(pilot_sample_checks==0&&dc_sample_checks==0);
}
'''
        path=self.directory/'run-pass.c';binary=self.directory/'run-pass';path.write_text(program)
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-UNDEBUG','-fsanitize=undefined,float-cast-overflow',
            '-fno-sanitize-recover=all','-I'+str(ROOT/'object-benchmark/main'),str(path),'-o',str(binary),'-lm'],check=True)
        subprocess.run([str(binary)],check=True,timeout=20)

if __name__=='__main__':unittest.main()
