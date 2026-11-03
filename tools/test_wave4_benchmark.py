# SPDX-License-Identifier: MIT
"""Admission checks for exact wave4 spellings, kernels and target modes."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest
from build_object_benchmark import configuration, ExportError
from wave4_contract import DEFAULT_RECIPES, IDENTITIES
from generate_object_fixtures import render

class Wave4AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        for name,data in render(json.loads(DEFAULT_RECIPES.read_text())).items():
            (self.directory/name).write_bytes(data)
        (self.directory/'description.json').write_text('{"parameters":[]}')
        self.catalog=json.loads((self.directory/'catalog.json').read_text())
        self.pins=json.loads(IDENTITIES.read_text())
        self.select(self.catalog['fixtures'][0]['id'])
    def select(self,identity):
        pins=self.pins;entry=pins['entries'][identity]
        manifest={k:pins[k] for k in ('rnbo_version','numerical_profile','class_name','role','audio_inputs','audio_outputs','parameter_count','adaptations')}
        manifest.update({k:entry[k] for k in ('editable_source_sha256','parameter_schema_sha256','source_tree_sha256')},required_host_services=[])
        report={'prepared_export':{'manifest':manifest,'provenance':{'raw_files_sha256':{'rnbo_source.h':entry['raw_source_sha256']}}},
                'prepared_snapshot':{'prepared_files_sha256':pins['runtime_files_sha256']|{'rnbo_source.h':entry['prepared_source_sha256']}}}
        module={'report':report,'export_path':str(self.directory),'artifact_sha256':'a'*64,'inspection':{'loaded_bytes_upper_bound':40000}}
        self.modules={key:copy.deepcopy(module) for key in ('strict','optimized')}
        self.args=argparse.Namespace(catalog=self.directory/'catalog.json',fixture_id=identity,blocks=None,rounds=3,timing_exclude_blocks=32,arena_bytes=4096)
    def generate(self):
        self.args.catalog.write_text(json.dumps(self.catalog));return configuration(self.args,self.modules)
    def test_all_thirteen_exact_fixtures_have_explicit_model_input_and_zero_gates(self):
        seen=set()
        for fixture in self.catalog['fixtures']:
            self.select(fixture['id']);header,policy=self.generate()
            self.assertIn('#define BENCH_WAVE4 1u',header)
            self.assertEqual([s['kind'] for s in policy['stimuli']],[12,13,14])
            self.assertEqual({v['kind'] for v in policy['verifications']},{'wave4-mathematical-v1'})
            self.assertEqual({v['maximum_absolute_error'] for v in policy['verifications']},{0})
            self.assertEqual(policy['events'],[])
            self.assertEqual(policy['blocks'],64)
            self.assertEqual(policy['fixture']['exact_entries'],fixture['exact_entries'])
            self.assertEqual(policy['psram_budget']['oracle_cache_bytes'],64*256*2*4)
            seen.add(policy['verifications'][0]['model_code'])
        self.assertEqual(seen,set(range(1,9)))
    def test_alias_and_codebox_labels_cannot_borrow_a_different_source(self):
        self.select('minimum-alias-signal')
        self.modules['strict']['report']['prepared_export']['manifest']['editable_source_sha256']=self.pins['entries']['minimum-canonical-signal']['editable_source_sha256']
        with self.assertRaisesRegex(ExportError,'exact graph/schema/source'):self.generate()
    def test_catalog_model_ports_domain_and_history_changes_are_not_admitted(self):
        for change in ('model','ports','domain','warmup','events','boolean-tolerance'):
            original=copy.deepcopy(self.catalog);f=self.catalog['fixtures'][0]
            if change=='model':f['semantic']['kind']='minimum'
            elif change=='ports':f['source']['arity']=2
            elif change=='domain':f['domain']['maximum']=2.0
            elif change=='warmup':f['cases'][0]['warmup_blocks']=0
            elif change=='boolean-tolerance':f['semantic']['maximum_absolute_error']=False
            else:f['cases'][0]['events']=[{'block':0}]
            with self.assertRaisesRegex(ExportError,'reviewed original recipes'):self.generate()
            self.catalog=original
    def test_raw_prepared_runtime_and_schema_identity_changes_reject(self):
        for change in ('raw','prepared','runtime','schema'):
            original=copy.deepcopy(self.modules);r=self.modules['strict']['report']
            if change=='raw':r['prepared_export']['provenance']['raw_files_sha256']['rnbo_source.h']='0'*64
            elif change=='prepared':r['prepared_snapshot']['prepared_files_sha256']['rnbo_source.h']='0'*64
            elif change=='runtime':r['prepared_snapshot']['prepared_files_sha256']['common/RNBO_List.h']='0'*64
            else:r['prepared_export']['manifest']['parameter_schema_sha256']='0'*64
            with self.assertRaises(ExportError):self.generate()
            self.modules=original
    def test_changed_graph_and_nonidentical_control_reject(self):
        self.modules['optimized']['artifact_sha256']='b'*64
        with self.assertRaisesRegex(ExportError,'identical-module'):self.generate()
        self.modules['optimized']['artifact_sha256']='a'*64
        (self.directory/(self.args.fixture_id+'.rnbopat')).write_text('{}')
        with self.assertRaisesRegex(ExportError,'exact original spelling'):self.generate()
    def test_wave4_verification_cannot_bypass_original_catalog_admission(self):
        from wave4_contract import benchmark_fixture
        projected=benchmark_fixture(self.catalog,self.directory,self.args.fixture_id)
        self.catalog={'sample_rate':44100,'block_frames':256,'fixtures':[projected]}
        with self.assertRaisesRegex(ExportError,'original wave4 catalog format'):self.generate()

    def test_unmodeled_longer_blocks_and_nonzero_parameters_reject(self):
        self.args.blocks=128
        with self.assertRaisesRegex(ExportError,'mode/model/input'):self.generate()
        self.args.blocks=None
        for module in self.modules.values():module['report']['prepared_export']['manifest']['parameter_count']=1
        with self.assertRaisesRegex(ExportError,'parameter_count'):self.generate()

if __name__=='__main__':unittest.main()
