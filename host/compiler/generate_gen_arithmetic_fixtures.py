#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate original exact-spelling GenExpr arithmetic fixtures, never vendor C++.

The15 spellings remain separate authored programs. Optional identities are
read from verified normal strict exports; generation is not DSP qualification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

FORMAT = 'rnbo-original-gen-arithmetic-fixtures-v1'
RECIPE_FORMAT = 'rnbo-original-gen-arithmetic-recipes-v1'
FIXTURE_ROOT = 'tests/fixtures/gen/arithmetic'
REGISTRY_SHA256 = 'ea19a20e4ed03e31d5a41413db9489f3812a9c73c46217eef268fcbc9ffb9a54'
RUNTIME_SHA256 = 'fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d'
INPUT_FAMILIES = ('signed-grid-v1', 'dense-binary32-v1', 'vector-boundaries-v1')
# id, exact spelling, syntax, registry canonical name, arity, independent model.
RECIPES = (
    ('abs-call', 'abs', 'call', 'abs', 1, 1),
    ('min-call', 'min', 'call', 'min', 2, 2),
    ('minimum-call', 'minimum', 'call', 'min', 2, 2),
    ('max-call', 'max', 'call', 'max', 2, 3),
    ('maximum-call', 'maximum', 'call', 'max', 2, 3),
    ('sub-call', 'sub', 'call', 'sub', 2, 4),
    ('subtract-infix', '-', 'infix', 'sub', 2, 4),
    ('eq-call', 'eq', 'call', 'eq', 2, 5),
    ('equal-infix', '==', 'infix', 'eq', 2, 5),
    ('lt-call', 'lt', 'call', 'lt', 2, 6),
    ('less-infix', '<', 'infix', 'lt', 2, 6),
    ('add-call', 'add', 'call', 'add', 2, 9),
    ('add-infix', '+', 'infix', 'add', 2, 9),
    ('mul-call', 'mul', 'call', 'mul', 2, 10),
    ('mul-infix', '*', 'infix', 'mul', 2, 10),
)
NORMAL_ADAPTATIONS = (
    'rnbo-1.4.4-list-copy-bounds-v1',
    'rnbo-1.4.4-list-move-inline-storage-v1',
    'rnbo-1.4.4-list-cross-capacity-assignment-v1',
    'rnbo-1.4.4-nested-clock-target-v1',
    'rnbo-1.4.4-defined-imul-v1',
)
EXPECTED_RAW_SOURCES = {
    'abs': '86cb0539073bef4bccb2352681eac0c051c0890731e42d3744beeec71397220d',
    'min': '1d843100b53839881b4072bd9d8d58a8de254562ae1d18dcef717bdadf76c7d7',
    'max': 'ab4a9b12770267d8a4b69cbaec660bfc167088880a53c93194b59ffaac663f9b',
    'sub': '53a2edab494f0d57e898fdbef6f4d42d3736650f57e40c12c1e04acfdfb40bc8',
    'eq': 'c118d1806ce20e5d5cc2c5154f910a8f44a5f976d070d7ff044dd03750ccf014',
    'lt': '2b0fd61747c1529d5255808419e59676f012b66853ba13f8ac8ec600277e5f6f',
    'add': 'fe18b78ecd90f1b6b27020773a4f5c39d8caa74914b76e8298501b175a2abda6',
    'mul': '316ace992e3b52aa0f5ce31cf124f273ff8aabd1da8215772bd8c072418c8bc6',
}


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def _recipe(identity):
    if type(identity) is not str:
        raise ValueError('Gen arithmetic fixture identity must be a known string')
    selected = [r for r in RECIPES if r[0] == identity]
    if len(selected) != 1:
        raise ValueError('Unknown original Gen arithmetic fixture')
    return selected[0]


def expression(identity):
    _, name, syntax, _, arity, _ = _recipe(identity)
    if syntax == 'infix':
        return f'out1 = in1 {name} in2;\nout2 = in2 {name} in1;\n'
    if arity == 1:
        return f'out1 = {name}(in1);\nout2 = {name}(in2);\n'
    return f'out1 = {name}(in1, in2);\nout2 = {name}(in2, in1);\n'


def graph(identity):
    def box(name, text, x):
        return {'box': {'id': name, 'maxclass': 'newobj', 'text': text,
                        'rnbo_uniqueid': name, 'patching_rect': [x, 30, 130, 22]}}
    boxes = [box('left', 'in~ 1', 20), box('right', 'in~ 2', 160),
             box('gen', 'gen~', 300), box('ol', 'out~ 1', 440), box('or', 'out~ 2', 580)]
    boxes[2]['box']['rnbo_extra_attributes'] = {'expr': expression(identity), 'geninlets': 2, 'genoutlets': 2}
    connections = ((['left', 0], ['gen', 0]), (['right', 0], ['gen', 1]),
                   (['gen', 0], ['ol', 0]), (['gen', 1], ['or', 0]))
    return {'patcher': {'classnamespace': 'rnbo', 'boxes': boxes,
                        'lines': [{'patchline': {'source': a, 'destination': b}} for a, b in connections]}}


def recipe_catalog():
    rows = []
    for identity, name, syntax, canonical_name, arity, model in RECIPES:
        rows.append({'id': identity, 'patch': identity + '.rnbopat', 'genexpr': identity + '.genexpr',
                     'source': {'surface': 'genexpr', 'exact_name': name, 'syntax': syntax,
                                'inventory_id': 'rnbo-genexpr:' + name,
                                'canonical': canonical_name, 'arity': arity},
                     'model_code': model, 'aliases_inherit_qualification': False})
    return {'format': RECIPE_FORMAT, 'format_version': 1, 'license': 'MIT',
            'scope': 'Original authored source only; aliases and syntax forms do not inherit qualification.',
            'primary_registry': {'version': '1.4.4',
                'local_package_path': 'server/node_modules/@rnbo/genexpr_js/operators.json',
                'sha256': REGISTRY_SHA256}, 'recipes': rows}


def catalog():
    fixtures = []
    for row in recipe_catalog()['recipes']:
        declaration = {'kind': 'gen-arithmetic-v1', 'model_code': row['model_code'],
                       'maximum_absolute_error': 0.0}
        fixtures.append({key: row[key] for key in ('id', 'patch', 'genexpr', 'source', 'aliases_inherit_qualification')} | {
            'surface': 'genexpr', 'exact_entries': [row['source']['inventory_id']],
            'role': 'fx', 'audio_inputs': 2, 'audio_outputs': 2, 'blocks': 64,
            'warmup_blocks': 4, 'rounds': 3, 'seed': 0x12345678, 'arena_bytes': 4096, 'pcm_gain': 0.5,
            'domain': {'finite': True, 'input_type': 'binary32', 'minimum': -1.0, 'maximum': 1.0,
                       'zero_sign': 'numeric-equality-with-separate-bit-observation'},
            'stimulus': {'kind': INPUT_FAMILIES[0]},
            'cases': [{'id': kind, 'parameters': {}, 'events': [], 'stimulus': {'kind': kind}}
                      for kind in INPUT_FAMILIES],
            'semantic': dict(declaration), 'verification': dict(declaration),
            'comparison_tolerance': {'maximum_absolute_error': 0.0,
                'maximum_pcm_lsb_error': 0, 'relative_rms_level_difference': 0.0}})
    return {'format': FORMAT, 'format_version': 1, 'license': 'MIT',
            'fixture_root': FIXTURE_ROOT, 'sample_rate': 44100, 'block_frames': 256,
            'scope': 'Fifteen exact authored GenExpr arithmetic syntax forms; execution evidence is separate.',
            'event_order': 'No parameters or events in this initial arithmetic mode.',
            'performance_gain_claimed': False, 'fixtures': fixtures}


def authored_files():
    files = {'recipes.json': canonical(recipe_catalog()), 'catalog.json': canonical(catalog())}
    for identity, *_ in RECIPES:
        files[identity + '.genexpr'] = expression(identity).encode()
        files[identity + '.rnbopat'] = canonical(graph(identity))
    return files


def identities(prepared_root: Path):
    """Derive pins only from the15 reviewed strict, fixed256 export forms."""
    from build import verify_prepared
    from prepare import ExportError
    if not isinstance(prepared_root, Path) or prepared_root.is_symlink():
        raise ValueError('Use a regular directory of prepared Gen arithmetic exports')
    expected = {'rnbo_version': '1.4.4', 'numerical_profile': 'float32-strict',
        'class_name': 'rnbos3patch', 'role': 'fx', 'audio_inputs': 2, 'audio_outputs': 2,
        'parameter_count': 0, 'adaptations': list(NORMAL_ADAPTATIONS)}
    authored = authored_files(); entries = {}; runtime = None
    for identity, _, _, canonical_name, _, _ in RECIPES:
        directory = prepared_root / identity
        if directory.is_symlink():
            raise ValueError('Prepared Gen arithmetic directories must not be symbolic links')
        try:
            provenance, manifest, snapshot = verify_prepared(directory)
        except (ExportError, OSError) as exc:
            raise ValueError('Invalid prepared Gen arithmetic export: ' + str(exc)) from exc
        context = expected | {'sample_rate':44100, 'block_frames':256, 'voices':1,
            'required_host_services':[], 'midi_output_policy':'reject', 'midi_output_ports':0,
            'scheduler_time':'float64', 'execution':'static-development',
            'voice_topology':'single-export', 'format':'rnbo-esp32s3-prepared-export', 'format_version':1}
        if canonical({k:manifest.get(k) for k in context}) != canonical(context):
            raise ValueError('Prepared export is outside the normal strict Gen arithmetic context')
        known_manifest = {'adaptations','audio_inputs','audio_outputs','block_frames','class_name',
            'defined_int32_wrap','editable_source_sha256','execution','format','format_version',
            'midi_output_policy','midi_output_ports','numerical_profile','parameter_count',
            'parameter_schema_sha256','required_host_services','rnbo_version','role','sample_rate',
            'scheduler_time','source_tree_sha256','voice_topology','voices'}
        if set(manifest) != known_manifest or manifest['defined_int32_wrap'] is not True:
            raise ValueError('Unexpected optional profile or manifest fields')
        files = snapshot['prepared_files_sha256']
        patch = authored[identity + '.rnbopat']; expr = authored[identity + '.genexpr']
        if (len(files) != 42 or (directory/'source.rnbopat').read_bytes() != patch or
                manifest['editable_source_sha256'] != digest(patch) or
                provenance['raw_files_sha256'].get('rnbo_source.h') != EXPECTED_RAW_SOURCES[canonical_name] or
                files['rnbo_source.h'] != EXPECTED_RAW_SOURCES[canonical_name]):
            raise ValueError('Prepared source differs from the exact original Gen arithmetic program')
        common = {k:v for k,v in files.items() if k.startswith('common/')}
        if len(common) != 36 or digest(canonical(common)) != RUNTIME_SHA256 or runtime is not None and common != runtime:
            raise ValueError('Gen arithmetic runtime tree differs')
        runtime = common
        entries[identity] = {'editable_source_sha256': digest(patch), 'patch_sha256': digest(patch),
            'genexpr_sha256': digest(expr), 'parameter_schema_sha256': manifest['parameter_schema_sha256'],
            'source_tree_sha256': manifest['source_tree_sha256'],
            'raw_source_sha256': provenance['raw_files_sha256']['rnbo_source.h'],
            'prepared_source_sha256': files['rnbo_source.h']}
    return {**expected, 'sample_rate': 44100, 'block_frames': 256,
            'runtime_files_sha256': runtime, 'entries': entries}


def generate(output: Path, *, prepared_root: Path | None = None):
    if not isinstance(output, Path) or output.is_symlink() or output.exists():
        raise ValueError('Choose a fresh regular output directory')
    files = authored_files()
    if prepared_root is not None:
        files['identities.json'] = canonical(identities(prepared_root))
    # Validate all identities before creating an output or temporary directory.
    output = output.resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.gen-arithmetic-', dir=output.parent))
    try:
        for name, data in files.items():
            (temporary/name).write_bytes(data)
        if output.exists() or output.is_symlink():
            raise ValueError('Output was created concurrently')
        os.rename(temporary, output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {'output': str(output), 'authored_fixtures': len(RECIPES), 'identities': prepared_root is not None,
            'DSP_execution_qualified': False, 'hardware_executed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--prepared-root', type=Path,
                        help='Optional verified15-export directory for reproducible identity pins')
    args = parser.parse_args()
    try:
        print(json.dumps(generate(args.out, prepared_root=args.prepared_root)))
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
