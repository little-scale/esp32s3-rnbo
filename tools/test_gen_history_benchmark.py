# SPDX-License-Identifier: MIT
"""Admission and actual benchmark preparation/witness negative probes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest
from build_object_benchmark import configuration, ExportError
from gen_history_contract import TARGET, IDENTITIES, witness_sha256

ROOT = Path(__file__).resolve().parents[1]


class GenHistoryBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.catalog = json.loads((TARGET / 'catalog.json').read_text())
        self.pins = json.loads(IDENTITIES.read_text())
        self.select('history-feedback')

    def select(self, identity):
        pins = self.pins; entry = pins['entries'][identity]
        manifest = {k: pins[k] for k in ('rnbo_version', 'numerical_profile', 'class_name', 'role',
                                        'audio_inputs', 'audio_outputs', 'parameter_count', 'adaptations')}
        manifest.update({k: entry[k] for k in ('editable_source_sha256', 'parameter_schema_sha256', 'source_tree_sha256')}, required_host_services=[])
        parameter = {'paramId': 's3_reset', 'index': 0, 'minimum': 0, 'maximum': 1,
                     'initialValue': 0, 'exponent': 1, 'steps': 0}
        (self.directory / 'description.json').write_text(json.dumps({'parameters': [parameter]}))
        report = {'prepared_export': {'manifest': manifest, 'provenance': {'raw_files_sha256': {'rnbo_source.h': entry['raw_source_sha256']}}},
                  'prepared_snapshot': {'prepared_files_sha256': pins['runtime_files_sha256'] | {'rnbo_source.h': entry['prepared_source_sha256']}}}
        module = {'report': report, 'export_path': str(self.directory), 'artifact_sha256': 'a' * 64,
                  'inspection': {'loaded_bytes_upper_bound': 40000}}
        self.modules = {key: copy.deepcopy(module) for key in ('strict', 'optimized')}
        self.args = argparse.Namespace(catalog=self.directory / 'catalog.json', fixture_id=identity,
                                      blocks=None, rounds=3, timing_exclude_blocks=32, arena_bytes=65536)

    def generate(self):
        self.args.catalog.write_text(json.dumps(self.catalog))
        return configuration(self.args, self.modules)

    def test_three_source_bound_controls_have_exact_gates_and_all_reset_schedules(self):
        for fixture in self.catalog['fixtures']:
            self.select(fixture['id']); header, policy = self.generate()
            self.assertIn('#define BENCH_GEN_HISTORY 1u', header)
            self.assertEqual([s['kind'] for s in policy['stimuli']], [15] * 3)
            self.assertEqual(policy['comparison_policy']['pcm_gain'], .25)
            self.assertEqual(policy['blocks'], 64)
            self.assertEqual(len(policy['events']), 70)
            for case, verification in zip(fixture['cases'], policy['verifications']):
                wire = struct.pack('<II', 0, len(case['events']))
                for e in case['events']: wire += struct.pack('<IIIf', e['block'], 0, 1, 1.0)
                self.assertEqual(verification['event_schedule_sha256'], hashlib.sha256(wire).hexdigest())
                self.assertEqual(verification['reset_witness_sha256'], witness_sha256(fixture, case))
                self.assertEqual(verification['initial_epoch_frames'], -1024)
                self.assertEqual(verification['maximum_absolute_error'], 2e-6)

    def test_changed_catalog_and_runtime_identities_reject(self):
        for change in ('reset-value', 'reset-time', 'gain', 'model', 'false-limit', 'extra-case'):
            original = copy.deepcopy(self.catalog); f = self.catalog['fixtures'][0]
            if change == 'reset-value': f['cases'][1]['events'][0]['value'] = 0.0
            elif change == 'reset-time': f['cases'][1]['events'][0]['block'] = 0
            elif change == 'gain': f['pcm_gain'] = .5
            elif change == 'model': f['verification']['model_code'] = 2
            elif change == 'false-limit': f['comparison_tolerance']['maximum_absolute_error'] = False
            else: f['cases'].append(copy.deepcopy(f['cases'][0]))
            with self.assertRaisesRegex(ExportError, 'reviewed original programs'): self.generate()
            self.catalog = original
        for key in ('raw', 'prepared', 'runtime', 'schema'):
            original = copy.deepcopy(self.modules); report = self.modules['strict']['report']
            if key == 'raw': report['prepared_export']['provenance']['raw_files_sha256']['rnbo_source.h'] = '0' * 64
            elif key == 'prepared': report['prepared_snapshot']['prepared_files_sha256']['rnbo_source.h'] = '0' * 64
            elif key == 'runtime': report['prepared_snapshot']['prepared_files_sha256']['common/RNBO_List.h'] = '0' * 64
            else: report['prepared_export']['manifest']['parameter_schema_sha256'] = '0' * 64
            with self.assertRaises(ExportError): self.generate()
            self.modules = original

    def test_unreviewed_execution_shape_control_and_reset_schema_reject(self):
        for key, value in [('rounds', 1), ('blocks', 128), ('arena_bytes', 4096), ('timing_exclude_blocks', 0)]:
            original = getattr(self.args, key); setattr(self.args, key, value)
            with self.assertRaises(ExportError): self.generate()
            setattr(self.args, key, original)
        self.modules['optimized']['artifact_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ExportError, 'identical-module'): self.generate()
        self.modules['optimized']['artifact_sha256'] = 'a' * 64
        p = json.loads((self.directory / 'description.json').read_text()); p['parameters'][0]['paramId'] = 'reset'
        (self.directory / 'description.json').write_text(json.dumps(p))
        with self.assertRaisesRegex(ExportError, 'mode/model/input'): self.generate()

    def test_production_preparation_and_run_pass_detect_an_ignored_rotation_reset(self):
        self.select('three-history-rotation'); header, policy = self.generate()
        source = (ROOT / 'object-benchmark/main/benchmark.c').read_text()
        declarations = [re.search(r'typedef struct \{[^}]*\} ' + name + r';', source, re.S)[0]
                        for name in ('bench_event', 'bench_case', 'bench_parameter', 'bench_verification',
                                     'profile_metrics', 'compare_metrics', 'semantic_metrics')]
        (self.directory / 'bench_config.h').write_text(header)
        # Use production preparation, schedule fingerprint and run_pass. The
        # fake DSP deliberately ignores the event while counting its dispatch.
        helpers = source[source.index('static void put_u32le('):source.index('static int16_t pcm(')]
        pcm = source[source.index('static int16_t pcm('):source.index('static void verify_parameters(')]
        preparation = source[source.index('static void prepare_stimulus('):source.index('static void excitation(')]
        run_pass = source[source.index('static void run_pass('):source.index('static void worker(')]
        program = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "stimulus.h"
#include "average_oracle.h"
#include "wave2_oracle.h"
#include "wave4_oracle.h"
#include "gen_history_oracle.h"
#define CHECK(x) assert(x)
#define RNBO_S3_BLOCK_FRAMES 256
#define RNBO_S3_FX 2
''' + '\n'.join(declarations) + r'''
#include "bench_config.h"
typedef struct {uint64_t position;unsigned phase;} object_image;
static float reference[BENCH_BLOCKS*512],stimulus_cache[BENCH_BLOCKS*512],oracle_storage[BENCH_BLOCKS*512],*oracle_cache=oracle_storage;
static float planar[4][256],*outputs[2]={planar[0],planar[1]},*inputs[2]={planar[2],planar[3]};
static const bench_verification *active_verification;static const object_stimulus *active_stimulus;
static double oracle_rounding_error,dc_expected;static int64_t benchmark_started;
static char event_schedule_sha[65],reset_witness_sha[65];static uint8_t reset_witness_mask[64];
static uint32_t reset_witness_count;
static uint64_t dc_sample_checks,semantic_sample_checks,pilot_sample_checks,oracle_bit_sample_checks,oracle_bit_differences;
static uint64_t wave4_bit_sample_checks,wave4_bit_differences,wave4_zero_sign_differences,observer_bit_sample_checks,observer_bit_differences;
static void digest_hex(const uint8_t *bytes,size_t count,char out[65]){(void)bytes;(void)count;memset(out,'0',64);out[64]=0;}
static int64_t esp_timer_get_time(void){return 1;}
static void vTaskDelay(int ticks){(void)ticks;}
''' + helpers + pcm + preparation + r'''
static void object_image_prepare(object_image *image,unsigned warmup,unsigned seed){assert(warmup==4&&seed==BENCH_SEED);image->position=0;image->phase=1024%3;}
static void verify_parameters(object_image *image){(void)image;}
static void collect(object_image *image,profile_metrics *metrics){(void)image;(void)metrics;}
static void object_image_destroy_context(object_image *image){(void)image;}
static void dispatch(object_image *image,const bench_case *test,unsigned block,profile_metrics *metrics){
 (void)image;for(unsigned n=0;n<test->event_count;++n)if(bench_events[test->event_begin+n].block==block)++metrics->events;
}
static void step(object_image *image,unsigned block,profile_metrics *metrics,bool measured){
 (void)block;(void)metrics;(void)measured;
 for(unsigned i=0;i<256;++i){outputs[0][i]=(float)(1+image->phase);outputs[1][i]=(float)(1+(image->phase+1)%3);image->phase=(image->phase+1)%3;}
 image->position+=256;
}
''' + run_pass + r'''
int main(void){
 char input_sha[65],oracle_sha[65];prepare_stimulus(2,input_sha,oracle_sha);
 assert(reset_witness_count==64 && oracle_cache[0]==1 && oracle_cache[1]==2);
 for(unsigned b=0;b<64;++b)assert(reset_witness_mask[b]==1);
 assert(oracle_rounding_error==0 && stimulus_cache[0]==.25f && stimulus_cache[1]==0.f);
 assert(pcm(3.f)==24575 && pcm(-3.f)==-24575);
 object_image image={0};compare_metrics comparison={0};double squares[2]={0};
 profile_metrics metrics={0};semantic_metrics semantic={0},dc={0};
 run_pass(&image,0,&bench_cases[2],true,&comparison,squares,&metrics,&semantic,&dc);
 assert(metrics.events==64 && semantic.witness_samples==128);
 assert(semantic.witness_differences>0 && semantic.witness_max_abs>=1 && semantic.max_abs>=1);
 prepare_stimulus(0,input_sha,oracle_sha);
 assert(reset_witness_count==0 && oracle_cache[0]==2 && oracle_cache[1]==3);
 memset(&metrics,0,sizeof metrics);memset(&semantic,0,sizeof semantic);
 run_pass(&image,0,&bench_cases[0],true,&comparison,squares,&metrics,&semantic,&dc);
 assert(semantic.max_abs==0 && semantic.witness_samples==0 && metrics.events==0);
}
'''
        path = self.directory / 'gen-production-negative.c'; binary = path.with_suffix('')
        path.write_text(program)
        subprocess.run(['cc', '-std=c11', '-O2', '-fno-fast-math', '-ffp-contract=off', '-UNDEBUG',
                        '-I' + str(self.directory), '-I' + str(ROOT / 'object-benchmark/main'), str(path),
                        *[str(ROOT / 'object-benchmark/main' / name) for name in
                          ('stimulus.c', 'average_oracle.c', 'wave2_oracle.c', 'wave4_oracle.c', 'gen_history_oracle.c')],
                        '-o', str(binary), '-lm'], check=True)
        subprocess.run([str(binary)], check=True, timeout=10)


if __name__ == '__main__': unittest.main()
