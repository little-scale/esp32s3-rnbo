#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Admission tests for catalog-to-firmware configuration, no toolchain/device."""
import argparse
import copy
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from build_object_benchmark import configuration, c_string, c_float, ExportError

class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.directory=Path(self.temporary.name)
        self.catalog={"sample_rate":44100,"block_frames":256,"fixtures":[{
            "id":"test","patch":"test.rnbopat","role":"main","blocks":512,"warmup_blocks":4,"seed":305419896,
            "cases":[{"id":"first","parameters":{"frequency":440}},
                     {"id":"boundary","parameters":{},"events":[{"block":7,"id":"frequency","form":"normalized","value":1}]}],
            "comparison_tolerance":{"maximum_absolute_error":2e-6,"maximum_pcm_lsb_error":1,"relative_rms_level_difference":1e-4}}]}
        description={"parameters":[{"index":0,"paramId":"frequency","minimum":20,"maximum":10000,"initialValue":440,"exponent":1,"steps":0}]}
        (self.directory/"description.json").write_text(json.dumps(description))
        patch=self.directory/"test.rnbopat";patch.write_text("fixture-source")
        manifest={"role":"main","numerical_profile":"float32-strict","editable_source_sha256":hashlib.sha256(patch.read_bytes()).hexdigest(),"parameter_schema_sha256":"schema","source_tree_sha256":"raw",
                  "parameter_count":1,"audio_inputs":0,"audio_outputs":2,"required_host_services":[]}
        self.modules={k:{"report":{"prepared_export":{"manifest":copy.deepcopy(manifest)}},"export_path":str(self.directory),"artifact_sha256":str(i)*64} for i,k in enumerate(("strict","optimized"))}
        self.args=argparse.Namespace(catalog=self.directory/"catalog.json",fixture_id="test",blocks=None,rounds=3,timing_exclude_blocks=32,arena_bytes=1048576)
    def tearDown(self):self.temporary.cleanup()
    def generate(self):
        self.args.catalog.write_text(json.dumps(self.catalog));return configuration(self.args,self.modules)
    def test_events_and_exact_policy(self):
        header,policy=self.generate()
        self.assertIn("#define BENCH_MAX_ABS "+float(2e-6).hex(),header)
        self.assertEqual([(e["block"],e["kind"],e["value"]) for e in policy["events"]],[(0,1,440),(7,2,1)])
    def test_unimplemented_fx_stimulus_cannot_be_benchmarked_as_generic_input(self):
        self.catalog['fixtures'][0]['role']='fx'
        self.catalog['fixtures'][0]['stimulus']={'kind':'midi-stereo-v1'}
        for m in self.modules.values():m['report']['prepared_export']['manifest']['role']='fx'
        with self.assertRaisesRegex(ExportError,'Main fixtures only'):self.generate()
    def test_wrong_source(self):
        self.modules["optimized"]["report"]["prepared_export"]["manifest"]["source_tree_sha256"]="other"
        with self.assertRaises(ExportError):self.generate()
    def test_unknown_parameter(self):
        self.catalog["fixtures"][0]["cases"][0]["parameters"]={"unknown":1}
        with self.assertRaises(ExportError):self.generate()
    def test_actual_bounds(self):
        self.catalog["fixtures"][0]["cases"][0]["parameters"]["frequency"]=10001
        with self.assertRaises(ExportError):self.generate()
    def test_normalized_bounds(self):
        self.catalog["fixtures"][0]["cases"][1]["events"][0]["value"]=1.01
        with self.assertRaises(ExportError):self.generate()
    def test_duplicate_block_parameter(self):
        self.catalog["fixtures"][0]["cases"][0]["events"]=[{"block":0,"id":"frequency","value":20}]
        with self.assertRaises(ExportError):self.generate()
    def test_event_after_pass(self):
        self.catalog["fixtures"][0]["cases"][1]["events"][0]["block"]=512
        with self.assertRaises(ExportError):self.generate()
    def test_nonfinite_tolerance(self):
        self.catalog["fixtures"][0]["comparison_tolerance"]["maximum_absolute_error"]=float("nan")
        with self.assertRaises(ExportError):self.generate()
    def test_catalog_patch_identity(self):
        (self.directory/"test.rnbopat").write_text("changed")
        with self.assertRaises(ExportError):self.generate()
    def test_strict_reference_profile(self):
        self.modules["strict"]["report"]["prepared_export"]["manifest"]["numerical_profile"]="optimized"
        with self.assertRaises(ExportError):self.generate()
    def test_safe_literals(self):
        self.assertEqual(c_string('";\\\n'), '"\\x22""\\x3b""\\x5c""\\x0a"')
        self.assertTrue(c_float(.2).endswith("f"))
        with self.assertRaises(ExportError):c_float(float("inf"))

if __name__=="__main__":unittest.main()
