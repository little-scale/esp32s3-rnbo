# SPDX-License-Identifier: MIT
"""Closed syntax identities and actual benchmark output-analysis probes."""
import argparse
import copy
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from build_object_benchmark import configuration, ExportError
from generate_gen_arithmetic_fixtures import authored_files
from gen_arithmetic_contract import IDENTITIES

ROOT=Path(__file__).resolve().parents[1]


class GenArithmeticBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        for name,data in authored_files().items():(self.directory/name).write_bytes(data)
        self.catalog=json.loads((self.directory/'catalog.json').read_bytes())
        self.pins=json.loads(IDENTITIES.read_bytes())
        (self.directory/'description.json').write_text('{"parameters":[]}')
        self.select('abs-call')

    def select(self,identity):
        pins=self.pins;entry=pins['entries'][identity]
        manifest={k:pins[k]for k in ('rnbo_version','numerical_profile','class_name','role','audio_inputs','audio_outputs',
                                     'parameter_count','adaptations','sample_rate','block_frames')}
        manifest.update({k:entry[k]for k in ('editable_source_sha256','parameter_schema_sha256','source_tree_sha256')},required_host_services=[])
        files=pins['runtime_files_sha256']|{'rnbo_source.h':entry['prepared_source_sha256'],
            'patch_config.h':'c'*64,'source.rnbopat':entry['editable_source_sha256'],
            'description.json':'d'*64,'generator.json':'e'*64,'RNBO-runtime-LICENSE':'f'*64}
        report={'prepared_export':{'manifest':manifest,'provenance':{'raw_files_sha256':{'rnbo_source.h':entry['raw_source_sha256']}}},
                'prepared_snapshot':{'prepared_files_sha256':files}}
        module={'report':report,'export_path':str(self.directory),'artifact_sha256':'a'*64,
                'inspection':{'loaded_bytes_upper_bound':40000}}
        self.modules={k:copy.deepcopy(module)for k in ('strict','optimized')}
        self.args=argparse.Namespace(catalog=self.directory/'catalog.json',fixture_id=identity,blocks=None,rounds=3,
                                     timing_exclude_blocks=32,arena_bytes=4096)

    def generate(self):
        self.args.catalog.write_text(json.dumps(self.catalog));return configuration(self.args,self.modules)

    def test_all_fifteen_exact_syntax_contexts_keep_models_and_no_alias_inheritance(self):
        seen=set()
        for fixture in self.catalog['fixtures']:
            self.select(fixture['id']);header,policy=self.generate()
            self.assertIn('#define BENCH_GEN_ARITH 1u',header)
            self.assertEqual([v['kind']for v in policy['verifications']],['gen-arithmetic-v1']*3)
            self.assertEqual([s['kind']for s in policy['stimuli']],[12,13,14])
            self.assertEqual(policy['events'],[]);self.assertEqual(policy['parameter_schema'],[])
            self.assertEqual(policy['comparison_policy']['pcm_gain'],.5)
            self.assertFalse(policy['fixture']['aliases_inherit_qualification'])
            self.assertEqual(policy['fixture']['source'],fixture['source'])
            seen.add(policy['verifications'][0]['model_code'])
        self.assertEqual(seen,{1,2,3,4,5,6,9,10})

    def test_changed_syntax_model_ports_catalog_and_nonidentical_control_reject(self):
        for change in ('model','syntax','inventory','ports','events','boolean-zero'):
            original=copy.deepcopy(self.catalog);f=self.catalog['fixtures'][0]
            if change=='model':f['semantic']['model_code']=2
            elif change=='syntax':f['source']['syntax']='infix'
            elif change=='inventory':f['exact_entries']=['rnbo-genexpr:minimum']
            elif change=='ports':f['audio_inputs']=0
            elif change=='events':f['cases'][0]['events']=[{'block':0,'id':'reset','value':1}]
            else:f['comparison_tolerance']['maximum_absolute_error']=False
            with self.assertRaisesRegex(ExportError,'reviewed original syntax'):self.generate()
            self.catalog=original
        self.modules['optimized']['artifact_sha256']='b'*64
        with self.assertRaisesRegex(ExportError,'identical-module'):self.generate()
        self.modules['optimized']['artifact_sha256']='a'*64
        (self.directory/'abs-call.genexpr').write_text('out1 = in1; out2 = in2;')
        with self.assertRaisesRegex(ExportError,'exact syntax'):self.generate()

    def test_unreviewed_execution_shape_source_runtime_and_schema_reject(self):
        for key,value in [('rounds',1),('blocks',128),('timing_exclude_blocks',0),('arena_bytes',8192)]:
            old=getattr(self.args,key);setattr(self.args,key,value)
            with self.assertRaises(ExportError):self.generate()
            setattr(self.args,key,old)
        for key in ('raw','prepared','runtime','schema'):
            original=copy.deepcopy(self.modules);r=self.modules['strict']['report']
            if key=='raw':r['prepared_export']['provenance']['raw_files_sha256']['rnbo_source.h']='0'*64
            elif key=='schema':r['prepared_export']['manifest']['parameter_schema_sha256']='0'*64
            else:r['prepared_snapshot']['prepared_files_sha256']['rnbo_source.h'if key=='prepared'else'common/RNBO_Types.h']='0'*64
            with self.assertRaises(ExportError):self.generate()
            self.modules=original

    def test_actual_run_pass_separates_zero_sign_diagnostics_from_numeric_errors(self):
        source=(ROOT/'object-benchmark/main/benchmark.c').read_text()
        declarations=[re.search(r'typedef struct \{[^}]*\} '+name+r';',source,re.S)[0]
                      for name in ('profile_metrics','compare_metrics','semantic_metrics')]
        function=source[source.index('static void run_pass('):source.index('static void worker(')]
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
#define BENCH_ROLE 2
#define RNBO_S3_FX 2
#define RNBO_S3_BLOCK_FRAMES 256
#define BENCH_BLOCKS 64
#define BENCH_WARMUP 4
#define BENCH_SEED 0x12345678u
typedef struct{uint64_t position;}object_image;
typedef struct{unsigned ignored;}bench_case;
'''+ '\n'.join(declarations)+r'''
static float reference[32768],oracle_cache[32768],planar[4][256];
static float *outputs[2]={planar[0],planar[1]},*inputs[2]={planar[2],planar[3]};
static struct{unsigned kind,window;double maximum_error;}verification={OBJECT_GEN_ARITH_KIND,1,0},*active_verification=&verification;
static object_stimulus stimulus,*active_stimulus=&stimulus;
static uint64_t dc_sample_checks,semantic_sample_checks,pilot_sample_checks,oracle_bit_sample_checks,oracle_bit_differences;
static uint64_t wave4_bit_sample_checks,wave4_bit_differences,wave4_zero_sign_differences,observer_bit_sample_checks,observer_bit_differences;
static uint64_t gen_arith_bit_sample_checks,gen_arith_bit_differences,gen_arith_zero_sign_differences;
static uint8_t reset_witness_mask[64];static int64_t benchmark_started;static double dc_expected;static bool numeric;
static int64_t esp_timer_get_time(void){return 1;}
static void vTaskDelay(int ticks){(void)ticks;}
static void object_image_prepare(object_image *image,unsigned warmup,unsigned seed){assert(warmup==4&&seed==BENCH_SEED);image->position=0;}
static void verify_parameters(object_image *image){(void)image;}
static void collect(object_image *image,profile_metrics *metrics){(void)image;(void)metrics;}
static void object_image_destroy_context(object_image *image){(void)image;}
static void dispatch(object_image *image,const bench_case *test,unsigned block,profile_metrics *metrics){(void)image;(void)test;(void)block;(void)metrics;}
static int16_t pcm(float value){return(int16_t)lrintf(value*.5f*32767.f);}
static void step(object_image *image,unsigned block,profile_metrics *metrics,bool measured){
 (void)metrics;(void)measured;
 for(unsigned i=0;i<256;++i)for(unsigned c=0;c<2;++c)outputs[c][i]=oracle_cache[((size_t)block*256+i)*2+c];
 if(block==0)outputs[0][0]=numeric?nextafterf(0.f,1.f):-0.f;
 image->position+=256;
}
'''+function+r'''
int main(void){
 for(unsigned trial=0;trial<2;++trial){
  numeric=trial!=0;object_image image={0};bench_case test={0};compare_metrics comparison={0};double squares[2]={0};
  profile_metrics metrics={0};semantic_metrics semantic={0},dc={0};
  run_pass(&image,0,&test,true,&comparison,squares,&metrics,&semantic,&dc);
  assert(semantic.samples==32768 && semantic.bit_different==1);
  assert(semantic.observer_samples==0 && observer_bit_sample_checks==0);
  if(numeric)assert(semantic.max_abs>0 && semantic.zero_sign_different==0);
  else assert(semantic.max_abs==0 && semantic.zero_sign_different==1);
 }
 assert(gen_arith_bit_sample_checks==65536 && gen_arith_bit_differences==2 && gen_arith_zero_sign_differences==1);
}
'''
        path=self.directory/'run-pass-gen-arithmetic.c';binary=path.with_suffix('');path.write_text(program)
        subprocess.run(['cc','-std=c11','-O2','-fno-fast-math','-ffp-contract=off','-UNDEBUG',
                        '-I'+str(ROOT/'object-benchmark/main'),str(path),'-o',str(binary),'-lm'],check=True)
        subprocess.run([str(binary)],check=True,timeout=10)


if __name__=='__main__':unittest.main()
