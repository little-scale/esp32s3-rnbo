# SPDX-License-Identifier: MIT
"""Closed exact-source logic admission and four-family device configuration."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest
from build_object_benchmark import configuration,ExportError
from generate_gen_logic_fixtures import authored_files
from gen_arithmetic_contract import LOGIC_IDENTITIES


class GenLogicBenchmarkTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.directory=Path(temp.name)
        for name,data in authored_files().items():(self.directory/name).write_bytes(data)
        (self.directory/'description.json').write_text('{"parameters":[]}')
        self.catalog=json.loads((self.directory/'catalog.json').read_bytes())
        self.pins=json.loads(LOGIC_IDENTITIES.read_bytes())
        self.select('neq-call')

    def select(self,identity):
        pins=self.pins;entry=pins['entries'][identity]
        manifest={k:pins[k] for k in ('rnbo_version','numerical_profile','class_name','role',
            'audio_inputs','audio_outputs','parameter_count','adaptations','sample_rate','block_frames')}
        manifest.update({k:entry[k] for k in ('editable_source_sha256','parameter_schema_sha256','source_tree_sha256')},
            voices=1,voice_topology='single-export',scheduler_time='float64',required_host_services=[],
            midi_output_policy='reject',midi_output_ports=0,defined_int32_wrap=True,
            execution='static-development',format='rnbo-esp32s3-prepared-export',format_version=1)
        report={'prepared_export':{'manifest':manifest,'provenance':{
            'raw_files_sha256':{'rnbo_source.h':entry['raw_source_sha256']}}},
            'prepared_snapshot':{'prepared_files_sha256':entry['prepared_files_sha256']},'imports':[]}
        module={'report':report,'artifact_sha256':'a'*64,'export_path':str(self.directory),
            'inspection':{'loaded_bytes_upper_bound':40000}}
        self.modules={key:copy.deepcopy(module) for key in ('strict','optimized')}
        self.args=argparse.Namespace(catalog=self.directory/'catalog.json',fixture_id=identity,
            blocks=None,rounds=3,timing_exclude_blocks=32,arena_bytes=4096)

    def configure(self):
        self.args.catalog.write_text(json.dumps(self.catalog))
        return configuration(self.args,self.modules)

    def test_all_exact_forms_have_independent_identity_and_four_input_caches(self):
        models=set()
        for fixture in self.catalog['fixtures']:
            self.select(fixture['id']);header,policy=self.configure()
            self.assertIn('#define BENCH_GEN_LOGIC 1u',header)
            self.assertIn('#define BENCH_GEN_ABS_INTRINSIC 0u',header)
            self.assertEqual([s['kind'] for s in policy['stimuli']],[12,13,14,16])
            self.assertEqual(policy['events'],[])
            self.assertEqual(policy['parameter_schema'],[])
            self.assertEqual(policy['fixture']['source'],fixture['source'])
            self.assertFalse(policy['fixture']['aliases_inherit_qualification'])
            self.assertEqual({v['gate'] for v in policy['verifications']},
                {'numeric-exact-plus-signed-zero-only-operation-bits'})
            models.add(policy['verifications'][0]['model_code'])
        self.assertEqual(models,set(range(11,23)))

    def test_changed_graph_grammar_source_model_or_truth_domain_reject(self):
        for mutation in ('model','syntax','inventory','events','domain','extra-case'):
            original=copy.deepcopy(self.catalog);fixture=self.catalog['fixtures'][0]
            if mutation=='model':fixture['semantic']['model_code']=12
            elif mutation=='syntax':fixture['source']['syntax']='prefix'
            elif mutation=='inventory':fixture['exact_entries']=['rnbo-genexpr:==']
            elif mutation=='events':fixture['cases'][0]['events']=[{'block':1,'id':'x','value':1}]
            elif mutation=='domain':fixture['domain']['minimum']=-2
            else:fixture['cases'].append(copy.deepcopy(fixture['cases'][0]))
            with self.subTest(mutation=mutation),self.assertRaises(ExportError):self.configure()
            self.catalog=original
        path=self.directory/'neq-call.genexpr';path.write_text('out1 = in1;out2 = in2;')
        with self.assertRaisesRegex(ExportError,'exact syntax'):self.configure()

    def test_full_prepared_metadata_profile_imports_and_same_image_control_required(self):
        for mutation in ('generator','license','runtime','config','source','clock','extra-profile','imports',
                         'different-image','boolean-count','float-rate','float-block'):
            original=copy.deepcopy(self.modules);report=self.modules['optimized']['report']
            files=report['prepared_snapshot']['prepared_files_sha256'];manifest=report['prepared_export']['manifest']
            if mutation in ('generator','license','runtime','config','source'):
                key={'generator':'generator.json','license':'RNBO-runtime-LICENSE','runtime':'common/RNBO_Types.h',
                    'config':'patch_config.h','source':'rnbo_source.h'}[mutation]
                files[key]='0'*64
            elif mutation=='clock':manifest['scheduler_time']='float32'
            elif mutation=='extra-profile':manifest['gen_abs_intrinsic']=False
            elif mutation=='imports':report['imports']=['fabsf']
            elif mutation=='boolean-count':manifest['parameter_count']=False
            elif mutation=='float-rate':manifest['sample_rate']=44100.0
            elif mutation=='float-block':manifest['block_frames']=256.0
            else:self.modules['optimized']['artifact_sha256']='b'*64
            with self.subTest(mutation=mutation),self.assertRaises(ExportError):self.configure()
            self.modules=original


if __name__=='__main__':unittest.main()
