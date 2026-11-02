# SPDX-License-Identifier: MIT
"""Reject incomplete or internally inconsistent target evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from collect_object_benchmarks import collect,fields,sha

class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.build=self.root/'build';self.run=self.root/'run'
        self.build.mkdir();self.run.mkdir()
        fixture={'id':'unit','family':'unit','role':'main','warmup_blocks':4,'seed':1,'cases':[{'id':'default'}],
                 'comparison_tolerance':{'maximum_absolute_error':0.001,'maximum_pcm_lsb_error':1,'relative_rms_level_difference':0.01}}
        report={'benchmark':{'fixture':fixture,'rounds':3,'blocks':2,'timing_exclude_blocks':0},
                'modules':{'strict':{'artifact_sha256':'a'*64},'optimized':{'artifact_sha256':'b'*64}}}
        (self.build/'build-report.json').write_text(json.dumps(report))
        self.lines=['RNBO_OBJECT_BENCHMARK CASE fixture=unit case=default samples=3072 max_abs=0 rms_error=0 relative_rms=0 pcm_different=0 max_pcm_lsb=0',
            'RNBO_OBJECT_BENCHMARK CASE_PROFILE fixture=unit case=default profile=strict timed_blocks=6 process_us=120 peak_us=25',
            'RNBO_OBJECT_BENCHMARK CASE_PROFILE fixture=unit case=default profile=optimized timed_blocks=6 process_us=60 peak_us=15',
            'RNBO_OBJECT_BENCHMARK PASS fixture=unit firmware_elf_sha256='+('c'*64)+' strict_module_sha256='+('a'*64)+' optimized_module_sha256='+('b'*64)+
            ' host_heap_allocations=0 host_heap_frees=0 local_late_allocations=0 psram_before=123 psram_after=123 internal_before=42 internal_after=42 images=4 finalized_images=4 cases=1 rounds=3 blocks_per_pass=2 timing_exclude=0 warmup=4 seed=1 compared_samples=3072']
        self.seal()
    def seal(self):
        log=self.run/'test-serial.log';log.write_text('\n'.join(self.lines)+'\n')
        (self.run/'hardware-test.json').write_text(json.dumps({'result':'passed','restoration':{'result':'restored'},
            'test_build_report_sha256':sha(self.build/'build-report.json'),'serial_log_sha256':sha(log),
            'pass_line':self.lines[-1],'test_elf_sha256':'c'*64}))
    def test_observed_case_cost_and_identity(self):
        result=collect(self.build,self.run)
        self.assertEqual(result['cases'][0]['observed_speed_ratio'],2)
        self.assertEqual(result['cases'][0]['observed_process_reduction_percent'],50)
        self.assertFalse(result['identical_artifact_control'])
    def test_stale_log_cannot_receive_sealed_report(self):
        with (self.run/'test-serial.log').open('a') as f:f.write('changed\n')
        with self.assertRaisesRegex(ValueError,'Serial log changed'):collect(self.build,self.run)
    def test_declared_pass_does_not_override_failed_case(self):
        self.lines[0]=self.lines[0].replace('max_abs=0','max_abs=0.2');self.seal()
        with self.assertRaisesRegex(ValueError,'output limits'):collect(self.build,self.run)
    def test_missing_profile_rejected_even_with_pass(self):
        self.lines.pop(1);self.seal()
        with self.assertRaisesRegex(ValueError,'Incomplete case'):collect(self.build,self.run)
    def test_nonfinite_and_duplicate_fields_rejected(self):
        for value in ('process_us=nan','process_us=1 process_us=2'):
            with self.assertRaises(ValueError):fields('TEST '+value,'TEST ')
    def test_changed_build_report_rejected(self):
        with (self.build/'build-report.json').open('a') as f:f.write(' ')
        with self.assertRaisesRegex(ValueError,'Build report changed'):collect(self.build,self.run)

if __name__=='__main__':unittest.main()
