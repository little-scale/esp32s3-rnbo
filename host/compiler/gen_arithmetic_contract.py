# SPDX-License-Identifier: MIT
"""Exact authored GenExpr syntax admission, separate from RNBO object evidence."""
import json
from pathlib import Path
from generate_gen_arithmetic_fixtures import FORMAT, INPUT_FAMILIES, authored_files, canonical

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/'tests/fixtures/gen/arithmetic'
IDENTITIES=FIXTURES/'identities.json'
KIND='gen-arithmetic-v1'


def benchmark_fixture(catalog,directory,identity):
    generated=authored_files()
    if catalog.get('format')!=FORMAT or canonical(catalog)!=generated['catalog.json']:
        raise ValueError('Gen arithmetic catalog differs from the reviewed original syntax programs')
    selected=[f for f in catalog['fixtures'] if f['id']==identity]
    if len(selected)!=1:raise ValueError('Unknown or duplicate original Gen arithmetic identity')
    fixture=selected[0]
    for key in ('patch','genexpr'):
        path=directory/fixture[key]
        if path.is_symlink() or path.read_bytes()!=generated[fixture[key]]:
            raise ValueError('Gen arithmetic graph or exact syntax differs from the original program')
    return {**fixture,'family':'gen-arithmetic'}


def admit_module(fixture,module):
    pins=json.loads(IDENTITIES.read_bytes());expected=pins['entries'][fixture['id']]
    exported=module['report']['prepared_export'];manifest=exported['manifest']
    for key in ('rnbo_version','numerical_profile','class_name','role','audio_inputs','audio_outputs',
                'parameter_count','adaptations','sample_rate','block_frames'):
        if manifest.get(key)!=pins[key]:raise ValueError('Gen arithmetic strict module contract differs: '+key)
    for key in ('editable_source_sha256','parameter_schema_sha256','source_tree_sha256'):
        if manifest.get(key)!=expected[key]:raise ValueError('Gen arithmetic graph/schema/source identity differs: '+key)
    snapshot=module['report'].get('prepared_snapshot',{}).get('prepared_files_sha256',{})
    raw=exported.get('provenance',{}).get('raw_files_sha256',{})
    if (raw.get('rnbo_source.h')!=expected['raw_source_sha256'] or len(snapshot)!=42 or
            snapshot.get('rnbo_source.h')!=expected['prepared_source_sha256'] or
            {k:v for k,v in snapshot.items()if k.startswith('common/')}!=pins['runtime_files_sha256']):
        raise ValueError('Gen arithmetic generated source, configuration or runtime identity differs')


def verification(fixture,case,parameters,warmup,blocks):
    code=fixture['semantic']['model_code']
    declaration={'kind':KIND,'model_code':code,'maximum_absolute_error':0.0}
    if (parameters or warmup!=4 or blocks!=64 or fixture['verification']!=declaration or
            fixture['semantic']!=declaration or fixture['seed']!=0x12345678 or
            case not in fixture['cases'] or case['id'] not in INPUT_FAMILIES or
            case!={'id':case['id'],'parameters':{},'events':[],'stimulus':{'kind':case['id']}}):
        raise ValueError('Gen arithmetic target model/input/mode differs')
    return {**declaration,'observer_channel':2,'model':'independent-binary32-operations',
            'rounding':'once-binary32-per-output-operation',
            'gate':'numeric-exact-plus-signed-zero-only-operation-bits','operation_zero_sign':'diagnostic-only'}
