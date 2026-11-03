# SPDX-License-Identifier: MIT
"""Closed admission for the three original Gen history target programs.

These pins bind authored graphs and exported modules; numerical truth is
computed separately in the Python and target-C history models.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/gen'
TARGET = FIXTURES / 'target'
IDENTITIES = TARGET / 'identities.json'
KIND = 'gen-history-v1'
INPUT = 'gen-history-dyadic-v1'
FORMAT = 'rnbo-original-gen-history-target-v1'
CATALOG_SHA256 = '0cc8b831ae41fed2725a4f4ebcbcc2529318ae9c4f5e761b15ab7f948e283b9b'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def benchmark_fixture(catalog, directory: Path, identity: str):
    if catalog.get('format') != FORMAT or hashlib.sha256(canonical(catalog)).hexdigest() != CATALOG_SHA256:
        raise ValueError('Gen history catalog differs from the reviewed original programs and schedules')
    selected = [f for f in catalog['fixtures'] if f['id'] == identity]
    if len(selected) != 1:
        raise ValueError('Unknown or duplicate Gen history identity')
    fixture = selected[0]
    pins = json.loads(IDENTITIES.read_text())['entries'][identity]
    patch = FIXTURES / fixture['patch']
    expression = FIXTURES / (identity + '.genexpr')
    if (patch.is_symlink() or expression.is_symlink() or
            hashlib.sha256(patch.read_bytes()).hexdigest() != pins['editable_source_sha256'] or
            hashlib.sha256(expression.read_bytes()).hexdigest() != pins['genexpr_sha256']):
        raise ValueError('Gen history graph or GenExpr differs from its exact original program')
    return {**fixture, 'family': 'gen-history'}


def admit_module(fixture, module):
    pins = json.loads(IDENTITIES.read_text())
    expected = pins['entries'][fixture['id']]
    exported = module['report']['prepared_export']
    manifest = exported['manifest']
    for key in ('rnbo_version', 'numerical_profile', 'class_name', 'role',
                'audio_inputs', 'audio_outputs', 'parameter_count', 'adaptations'):
        if manifest.get(key) != pins[key]:
            raise ValueError('Gen history strict module contract differs: ' + key)
    for key in ('editable_source_sha256', 'parameter_schema_sha256', 'source_tree_sha256'):
        if manifest.get(key) != expected[key]:
            raise ValueError('Gen history exact graph/schema/source identity differs: ' + key)
    raw = exported.get('provenance', {}).get('raw_files_sha256', {})
    snapshot = module['report'].get('prepared_snapshot', {}).get('prepared_files_sha256', {})
    if (raw.get('rnbo_source.h') != expected['raw_source_sha256'] or
            snapshot.get('rnbo_source.h') != expected['prepared_source_sha256'] or
            {k: v for k, v in snapshot.items() if k.startswith('common/')} != pins['runtime_files_sha256']):
        raise ValueError('Gen history generated header or runtime identity differs')


def verification(fixture, case, parameters, warmup, blocks):
    code = fixture['semantic']['model_id']
    declaration = {'kind': KIND, 'model_code': code, 'maximum_absolute_error': 2e-6}
    if (warmup != 4 or blocks != 64 or fixture['verification'] != declaration or
            fixture['seed'] != 0x12345678 or case not in fixture['cases'] or
            set(parameters) != {'s3_reset'}):
        raise ValueError('Gen history target mode/model/input contract differs')
    p = parameters['s3_reset']
    if (p['index'], p['minimum'], p['maximum'], p['initialValue'], p['exponent'], p['steps']) != (0, 0, 1, 0, 1, 0):
        raise ValueError('Gen history reset parameter schema differs')
    return {**declaration, 'model': 'fresh-float64-input-convolution-or-integer-cycle',
            'rounding': 'once-float32',
            'gate': 'cache-error-plus-maximum-cache-rounding-error-plus-model-bounds',
            'initial_epoch_frames': -1024, 'witness_minimum_separation': 8e-6,
            **{key: fixture['semantic'][key] for key in ('model_tail_bound', 'model_evaluation_bound')}}


def witness_sha256(fixture, case):
    modules = []
    for name in ('inputs', 'models'):
        spec = importlib.util.spec_from_file_location('gen_target_' + name, TARGET / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    inputs, models = modules
    result = models.expected_outputs(fixture['semantic']['model_id'], inputs.generate(64 * 256), case['events'])
    return hashlib.sha256(models.reset_witness_bytes(result)).hexdigest()
