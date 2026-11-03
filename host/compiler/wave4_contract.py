# SPDX-License-Identifier: MIT
"""Closed admission adapter for original wave4 target fixtures.

This validates source/metadata, not DSP output truth. Python and C models remain
separate implementations and their complete cache bytes must agree.
"""
from __future__ import annotations
import json
from pathlib import Path
from generate_object_fixtures import DEFAULT_RECIPES, render, canonical

KIND = 'wave4-mathematical-v1'
MODELS = ('absolute', 'minimum', 'maximum', 'subtract', 'equal', 'less',
          'sum-and-difference', 'delta-left-observer-right')
INPUTS = ('signed-grid-v1', 'dense-binary32-v1', 'vector-boundaries-v1')
IDENTITIES = DEFAULT_RECIPES.parent / 'identities.json'


def admit_module(fixture, module):
    pins = json.loads(IDENTITIES.read_text())
    expected = pins['entries'][fixture['id']]
    exported = module['report']['prepared_export']
    manifest = exported['manifest']
    snapshot = module['report'].get('prepared_snapshot', {}).get('prepared_files_sha256', {})
    raw = exported.get('provenance', {}).get('raw_files_sha256', {})
    for key in ('rnbo_version', 'numerical_profile', 'class_name', 'role',
                'audio_inputs', 'audio_outputs', 'parameter_count', 'adaptations'):
        if manifest.get(key) != pins[key]:
            raise ValueError('Wave4 strict module contract differs: ' + key)
    for key in ('editable_source_sha256', 'parameter_schema_sha256', 'source_tree_sha256'):
        if manifest.get(key) != expected[key]:
            raise ValueError('Wave4 exact graph/schema/source identity differs: ' + key)
    if (raw.get('rnbo_source.h') != expected['raw_source_sha256'] or
            snapshot.get('rnbo_source.h') != expected['prepared_source_sha256'] or
            {k: v for k, v in snapshot.items() if k.startswith('common/')} != pins['runtime_files_sha256']):
        raise ValueError('Wave4 generated header or runtime identity differs')


def benchmark_fixture(catalog, directory: Path, identity: str):
    """Return a benchmark projection only for byte-identical original graphs."""
    if catalog.get('format') != 'rnbo-original-wave4-fixtures-v1':
        raise ValueError('Not an original wave4 catalog')
    fixtures = catalog.get('fixtures')
    if type(fixtures) is not list or not fixtures:
        raise ValueError('Missing original wave4 fixtures')
    ids = [f.get('id') for f in fixtures]
    generated = render(json.loads(DEFAULT_RECIPES.read_text()), ids)
    if canonical(catalog) != generated['catalog.json']:
        raise ValueError('Wave4 catalog differs from the reviewed original recipes')
    selected = [f for f in fixtures if f['id'] == identity]
    if len(selected) != 1:
        raise ValueError('Unknown or duplicate original wave4 identity')
    original = selected[0]
    patch = directory / original['patch']
    if patch.is_symlink() or patch.read_bytes() != generated[original['patch']]:
        raise ValueError('Wave4 graph differs from its exact original spelling/program')
    model = original['semantic']['kind']
    declaration = {'kind': KIND, 'model_code': MODELS.index(model) + 1,
                   'maximum_absolute_error': 0, 'observer_channel': 1 if model == MODELS[-1] else 2}
    return {**original, 'original_cases': original['cases'], 'family': 'wave4',
            'blocks': 64, 'warmup_blocks': 4, 'seed': catalog['seed'],
            'stimulus': {'kind': INPUTS[0]}, 'verification': declaration,
            'cases': [{'id': name, 'parameters': {}, 'events': [], 'stimulus': {'kind': name}}
                      for name in INPUTS],
            'comparison_tolerance': {'maximum_absolute_error': 0,
                                    'maximum_pcm_lsb_error': 0,
                                    'relative_rms_level_difference': 0}}


def verification(fixture, case, parameters, warmup, blocks):
    model = fixture['semantic']['kind']
    code = MODELS.index(model) + 1
    observer = 1 if code == 8 else 2
    expected = {'kind': KIND, 'model_code': code, 'maximum_absolute_error': 0,
                'observer_channel': observer}
    if (parameters or warmup != 4 or blocks != 64 or fixture['verification'] != expected or
            fixture['seed'] != 305419896 or case not in fixture['cases'] or
            case != {'id': case['id'], 'parameters': {}, 'events': [], 'stimulus': {'kind': case['id']}} or
            case['id'] not in INPUTS):
        raise ValueError('Wave4 target mode/model/input contract differs')
    return {**expected, 'model': 'independent-binary32-operations-and-input-history',
            'rounding': 'once-binary32-per-output-operation',
            'gate': 'numeric-exact-plus-direct-observer-bits',
            'operation_zero_sign': 'diagnostic-only', 'initial_previous_input': 0.0}
