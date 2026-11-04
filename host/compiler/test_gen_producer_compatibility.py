# SPDX-License-Identifier: MIT
"""Exact old/current producer identities without rewriting historical evidence."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import gen_arithmetic_contract as arithmetic
import gen_history_contract as history
import generate_gen_logic_fixtures as logic
import wave4_contract as wave4
from prepare import prepare
from build import verify_prepared

ROOT = Path(__file__).resolve().parents[2]


def sources():
    return ((history.IDENTITIES, history.INTEGER_UI_IDENTITIES, history.admit_module,
             json.loads((history.TARGET / 'catalog.json').read_bytes())['fixtures'], 'gen-history'),
            (arithmetic.LOGIC_IDENTITIES, arithmetic.LOGIC_INTEGER_UI_IDENTITIES, arithmetic.admit_module,
             logic.catalog()['fixtures'], 'gen-arithmetic'),
            (wave4.IDENTITIES, wave4.INTEGER_UI_IDENTITIES, wave4.admit_module,
             json.loads((wave4.DEFAULT_RECIPES.parent/'catalog.json').read_bytes())['fixtures'], 'wave4'))


def module_for(pins, identity):
    entry = pins['entries'][identity]
    keys = ('rnbo_version', 'numerical_profile', 'class_name', 'role', 'audio_inputs',
            'audio_outputs', 'parameter_count', 'adaptations')
    manifest = {key: copy.deepcopy(pins[key]) for key in keys}
    manifest.update(sample_rate=44100, block_frames=256, voices=1, voice_topology='single-export',
                    scheduler_time='float64', required_host_services=[], midi_output_policy='reject',
                    midi_output_ports=0, defined_int32_wrap=True, execution='static-development',
                    format='rnbo-esp32s3-prepared-export', format_version=1)
    manifest.update({key: entry[key] for key in ('editable_source_sha256', 'parameter_schema_sha256', 'source_tree_sha256')})
    snapshot = entry.get('prepared_files_sha256', pins['runtime_files_sha256'] |
                         {'rnbo_source.h': entry['prepared_source_sha256']})
    return {'report': {'prepared_export': {'manifest': manifest,
                       'provenance': {'raw_files_sha256': {'rnbo_source.h': entry['raw_source_sha256']}}},
                       'prepared_snapshot': {'prepared_files_sha256': copy.deepcopy(snapshot)}, 'imports': []}}


class ProducerIdentityTests(unittest.TestCase):
    def test_current_identity_files_preserve_all_historical_graph_runtime_and_profile_pins(self):
        for old_path, new_path, _, _, _ in sources():
            old, new = (json.loads(path.read_bytes()) for path in (old_path, new_path))
            self.assertEqual({k:v for k,v in old.items() if k!='entries'},
                             {k:v for k,v in new.items() if k!='entries'})
            self.assertEqual(set(old['entries']), set(new['entries']))
            for identity, entry in new['entries'].items():
                previous = old['entries'][identity]
                self.assertNotEqual(entry['source_tree_sha256'], previous['source_tree_sha256'])
                self.assertEqual({k:v for k,v in previous.items() if k not in ('source_tree_sha256','prepared_files_sha256')},
                                 {k:v for k,v in entry.items() if k not in ('source_tree_sha256','prepared_files_sha256')})
                files = entry['prepared_files_sha256']
                self.assertEqual(len(files), 42)
                self.assertEqual({k:v for k,v in files.items() if k.startswith('common/')}, new['runtime_files_sha256'])
                if 'prepared_files_sha256' in previous:
                    self.assertEqual([k for k in files if files[k]!=previous['prepared_files_sha256'][k]], ['generator.json'])
        from collect_object_benchmarks import GEN_INTEGER_UI_IDENTITIES
        from prepare import canonical, digest
        self.assertEqual(len(GEN_INTEGER_UI_IDENTITIES), 39)
        for path in (history.INTEGER_UI_IDENTITIES, arithmetic.INTEGER_UI_IDENTITIES,
                     arithmetic.LOGIC_INTEGER_UI_IDENTITIES):
            for identity, entry in json.loads(path.read_bytes())['entries'].items():
                pin=GEN_INTEGER_UI_IDENTITIES[identity]
                self.assertEqual(pin['source_tree'], entry['source_tree_sha256'])
                expected=(digest(canonical(entry['prepared_files_sha256'])) if 'prepared_files_sha256' in entry
                          else arithmetic.INTEGER_UI_FILE_MAPS[identity])
                self.assertEqual(pin['prepared_map'], expected)
        from collect_object_benchmarks import WAVE4_INTEGER_UI_IDENTITIES
        self.assertEqual(len(WAVE4_INTEGER_UI_IDENTITIES), 13)
        for identity,entry in json.loads(wave4.INTEGER_UI_IDENTITIES.read_bytes())['entries'].items():
            self.assertEqual(WAVE4_INTEGER_UI_IDENTITIES[identity],
                             {'source_tree':entry['source_tree_sha256'],
                              'prepared_map':digest(canonical(entry['prepared_files_sha256']))})

    def test_both_exact_epochs_admit_and_unknown_current_files_and_source_trees_reject(self):
        for old_path, new_path, admit, fixtures, family in sources():
            for path in (old_path, new_path):
                pins = json.loads(path.read_bytes())
                for fixture in fixtures:
                    original = module_for(pins, fixture['id'])
                    admit(fixture | {'family': family}, original)
                    if path == old_path:
                        continue
                    for key in ('generator.json', 'description.json', 'patch_config.h'):
                        bad = copy.deepcopy(original)
                        bad['report']['prepared_snapshot']['prepared_files_sha256'][key] = 'f'*64
                        with self.subTest(identity=fixture['id'],key=key), self.assertRaises(ValueError):
                            admit(fixture | {'family': family}, bad)
                    bad = copy.deepcopy(original)
                    bad['report']['prepared_export']['manifest']['source_tree_sha256'] = 'f'*64
                    with self.assertRaises(ValueError):
                        admit(fixture | {'family': family}, bad)

    def test_identity_selection_does_not_turn_unknown_profiles_into_admitted_modules(self):
        for _, new_path, admit, fixtures, family in sources():
            pins = json.loads(new_path.read_bytes())
            fixture = fixtures[0] | {'family': family}
            module = module_for(pins, fixture['id'])
            module['report']['prepared_export']['manifest']['numerical_profile'] = 'float32-auto-v1'
            with self.assertRaises(ValueError):
                admit(fixture, module)


class FreshProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('node'):
            raise unittest.SkipTest('Node and licensed RNBO1.4.4 frontend required')
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        for identity, relative in (('history-feedback', 'tests/fixtures/gen/history-feedback.rnbopat'),
                                   ('gt-call', 'tests/fixtures/gen/logic/gt-call.rnbopat'),
                                   ('abs-call', 'tests/fixtures/gen/arithmetic/abs-call.rnbopat'),
                                   ('absolute-signal-stereo', 'tests/fixtures/objects/wave4/absolute-signal-stereo.rnbopat')):
            raw = cls.root / (identity + '-raw')
            result = subprocess.run(['node', str(ROOT / 'host/export/export.mjs'), str(ROOT / relative),
                                     '--out', str(raw)], capture_output=True, text=True)
            if result.returncode and 'Set --rnbo-dir or RNBO_DIR' in result.stderr:
                raise unittest.SkipTest('Licensed RNBO frontend unavailable')
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            prepare(raw, cls.root / identity, 'rnbos3patch', 'fx')

    def test_actual_fresh_default_strict_prepared_maps_match_current_closed_identities(self):
        for identity, current_path, fixture, admit in (
                ('history-feedback', history.INTEGER_UI_IDENTITIES,
                 json.loads((history.TARGET / 'catalog.json').read_bytes())['fixtures'][0], history.admit_module),
                ('gt-call', arithmetic.LOGIC_INTEGER_UI_IDENTITIES,
                 next(f for f in logic.catalog()['fixtures'] if f['id']=='gt-call') | {'family':'gen-arithmetic'}, arithmetic.admit_module),
                ('absolute-signal-stereo',wave4.INTEGER_UI_IDENTITIES,
                 {'id':'absolute-signal-stereo'},wave4.admit_module)):
            provenance, manifest, snapshot = verify_prepared(self.root / identity)
            self.assertEqual(manifest['numerical_profile'], 'float32-strict')
            entry = json.loads(current_path.read_bytes())['entries'][identity]
            self.assertEqual(snapshot['prepared_files_sha256'], entry['prepared_files_sha256'])
            module = {'report': {'prepared_export': {'manifest':manifest,'provenance':provenance},
                                'prepared_snapshot':snapshot,'imports':[]}}
            admit(fixture, module)

    def test_actual_current_feedback_profile_inverts_to_exact_current_normal_map(self):
        from gen_feedback import PROFILE
        output = self.root / 'feedback-profile'
        prepare(self.root / 'history-feedback-raw', output, 'rnbos3patch', 'fx', numerical_profile=PROFILE)
        provenance, manifest, snapshot = verify_prepared(output)
        fixture = json.loads((history.FIXTURES / 'feedback-f32/catalog.json').read_bytes())['fixtures'][0]
        module = {'report': {'prepared_export': {'manifest':manifest,'provenance':provenance},
                            'prepared_snapshot':snapshot,'imports':[]}}
        history.admit_module(fixture, module, candidate=True)
        bad = copy.deepcopy(module)
        bad['report']['prepared_snapshot']['prepared_files_sha256']['generator.json'] = 'f'*64
        with self.assertRaises(ValueError):
            history.admit_module(fixture, bad, candidate=True)

    def collector_fixture(self, identity, *, comparison=False):
        import test_collect_object_benchmarks as tests
        cls=(tests.GenHistoryObservationTests if identity=='history-feedback' else
             tests.Wave4ObservationTests if identity=='absolute-signal-stereo' else tests.GenArithmeticObservationTests)
        rig=cls();rig.setUp();self.addCleanup(rig.doCleanups)
        if comparison:
            if identity=='history-feedback':rig.feedback_comparison()
            else:rig.intrinsic_comparison()
        elif identity=='history-feedback':rig.fixture(identity)
        elif identity=='absolute-signal-stereo':rig.fixture(identity)
        else:rig.fixture(identity,logic=identity=='gt-call')
        return rig

    def bind_actual(self, rig, identity, candidate=None):
        for side in ('strict','optimized'):
            directory=candidate if side=='optimized' and candidate is not None else self.root/identity
            provenance, manifest, snapshot=verify_prepared(directory)
            report=rig.report['modules'][side]['report']
            report.update(prepared_export={'manifest':manifest,'provenance':provenance},
                          prepared_snapshot=snapshot,imports=[])

    def test_collector_current_normal_maps_are_exact_and_unknown_metadata_rejects(self):
        from collect_object_benchmarks import gen_identity,gen_arith_identity,wave4_identity
        for identity in ('history-feedback','gt-call','abs-call','absolute-signal-stereo'):
            rig=self.collector_fixture(identity);self.bind_actual(rig,identity)
            check=(gen_identity if identity=='history-feedback' else
                   wave4_identity if identity=='absolute-signal-stereo' else gen_arith_identity)
            plan=rig.report['benchmark'];check(rig.report,plan['fixture'],plan)
            for key in ('generator.json','patch_config.h','description.json'):
                bad=copy.deepcopy(rig.report)
                bad['modules']['optimized']['report']['prepared_snapshot']['prepared_files_sha256'][key]='f'*64
                with self.subTest(identity=identity,key=key),self.assertRaises(ValueError):
                    check(bad,plan['fixture'],plan)

    def test_collector_current_candidate_helper_and_input_map_tuples_are_closed(self):
        from collect_object_benchmarks import (gen_identity,gen_arith_identity,GEN_FEEDBACK_PIN,GEN_ABS_PIN)
        for identity,options,check,helper,old in (
                ('history-feedback',{'numerical_profile':'float32-gen-feedback-v1'},gen_identity,'gen_feedback.py',GEN_FEEDBACK_PIN),
                ('abs-call',{'gen_abs_intrinsic':True},gen_arith_identity,'gen_abs_intrinsic.py',GEN_ABS_PIN)):
            directory=self.root/(identity+'-collector-candidate')
            prepare(self.root/(identity+'-raw'),directory,'rnbos3patch','fx',**options)
            rig=self.collector_fixture(identity,comparison=True);self.bind_actual(rig,identity,directory)
            adaptation=rig.report['modules']['optimized']['report']['prepared_export']['provenance']['adaptations'][-1]
            for side in ('strict','optimized'):
                rig.report['modules'][side]['report']['source_files_sha256']['host/compiler/'+helper]=adaptation['transformer_sha256']
            plan=rig.report['benchmark'];check(rig.report,plan['fixture'],plan)
            for field,value in (('input_map_sha256',old['input_map']),('transformer_sha256',old['transformer']),
                                ('input_map_sha256','f'*64),('transformer_sha256','f'*64)):
                bad=copy.deepcopy(rig.report)
                bad['modules']['optimized']['report']['prepared_export']['provenance']['adaptations'][-1][field]=value
                with self.subTest(identity=identity,field=field,value=value),self.assertRaises(ValueError):
                    check(bad,plan['fixture'],plan)


if __name__ == '__main__':
    unittest.main()
