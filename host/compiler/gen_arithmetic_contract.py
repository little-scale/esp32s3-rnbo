# SPDX-License-Identifier: MIT
"""Exact authored GenExpr syntax admission, separate from RNBO object evidence."""
import json
from pathlib import Path
from generate_gen_arithmetic_fixtures import FORMAT, INPUT_FAMILIES, authored_files, canonical
import generate_gen_logic_fixtures as logic

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/'tests/fixtures/gen/arithmetic'
IDENTITIES=FIXTURES/'identities.json'
LOGIC_IDENTITIES=ROOT/'tests/fixtures/gen/logic/identities.json'
LOGIC_FORMAT=logic.FORMAT
LOGIC_IDS=frozenset(row[0] for row in logic.RECIPES)
KIND='gen-arithmetic-v1'
ABS_FORMAT='rnbo-original-gen-abs-intrinsic-v1'
ABS_MODE='gen-abs-intrinsic-comparison-v1'
ABS_INPUT='finite-magnitude-boundaries-v1'
ABS_CATALOG_SHA='a7481d471f65f6203150e41b3870065df8e12fbb2d0fb9256a226c92791d83d5'


def benchmark_fixture(catalog,directory,identity):
    logic_mode=catalog.get('format')==LOGIC_FORMAT
    generated=logic.authored_files() if logic_mode else authored_files()
    abs_mode=catalog.get('format')==ABS_FORMAT
    import hashlib
    if ((not abs_mode and (catalog.get('format')!=(LOGIC_FORMAT if logic_mode else FORMAT) or canonical(catalog)!=generated['catalog.json'])) or
            (abs_mode and hashlib.sha256(canonical(catalog)).hexdigest()!=ABS_CATALOG_SHA)):
        raise ValueError('Gen arithmetic catalog differs from the reviewed original syntax programs')
    selected=[f for f in catalog['fixtures'] if f['id']==identity]
    if len(selected)!=1:raise ValueError('Unknown or duplicate original Gen arithmetic identity')
    fixture=selected[0]
    for key in ('patch','genexpr'):
        path=(FIXTURES if abs_mode else directory)/fixture[key]
        if path.is_symlink() or path.read_bytes()!=generated[fixture[key]]:
            raise ValueError('Gen arithmetic graph or exact syntax differs from the original program')
    return {**fixture,'family':'gen-arithmetic'}


def admit_module(fixture,module,*,candidate=False):
    logic_mode=fixture.get('id') in LOGIC_IDS
    if logic_mode:_logic_fixture(fixture)
    pins=json.loads((LOGIC_IDENTITIES if logic_mode else IDENTITIES).read_bytes());expected=pins['entries'][fixture['id']]
    from gen_abs_intrinsic import ADAPTATION, OUTPUT, CONTRACT, CONTRACT_FILE, MANIFEST_CONTRACT, sha
    exported=module['report']['prepared_export'];manifest=exported['manifest']
    profile_keys=('rnbo_version','numerical_profile','class_name','role','audio_inputs','audio_outputs',
                  'parameter_count','adaptations','sample_rate','block_frames')
    if logic_mode and canonical({k:manifest.get(k) for k in profile_keys})!=canonical({k:pins[k] for k in profile_keys}):
        raise ValueError('Gen logic typed strict profile differs')
    for key in profile_keys:
        expected_value=pins[key]+[ADAPTATION] if candidate and key=='adaptations' else pins[key]
        if manifest.get(key)!=expected_value:raise ValueError('Gen arithmetic strict module contract differs: '+key)
    for key in ('editable_source_sha256','parameter_schema_sha256','source_tree_sha256'):
        if manifest.get(key)!=expected[key]:raise ValueError('Gen arithmetic graph/schema/source identity differs: '+key)
    if candidate and (fixture.get('qualification_mode')!=ABS_MODE or fixture['id']!='abs-call' or
            manifest.get('gen_abs_intrinsic')is not True or
            canonical(manifest.get('gen_abs_intrinsic_contract'))!=canonical(MANIFEST_CONTRACT)):
        raise ValueError('Gen abs intrinsic candidate contract differs')
    snapshot=module['report'].get('prepared_snapshot',{}).get('prepared_files_sha256',{})
    raw=exported.get('provenance',{}).get('raw_files_sha256',{})
    if (raw.get('rnbo_source.h')!=expected['raw_source_sha256'] or len(snapshot)!=(43 if candidate else 42) or
            snapshot.get('rnbo_source.h')!=(OUTPUT if candidate else expected['prepared_source_sha256']) or
            {k:v for k,v in snapshot.items()if k.startswith('common/')}!=pins['runtime_files_sha256']):
        raise ValueError('Gen arithmetic generated source, configuration or runtime identity differs')
    if candidate and (snapshot.get(CONTRACT_FILE)!=sha(CONTRACT) or
            snapshot.get('patch_config.h')!='f6ac5f77e0492f986a983c1ee31e1dafe9899b0aceabe2ef591fbfa43c40cdcf'):
        raise ValueError('Gen abs intrinsic type contract/configuration differs')
    if logic_mode:
        known={'adaptations','audio_inputs','audio_outputs','block_frames','class_name','defined_int32_wrap',
            'editable_source_sha256','execution','format','format_version','midi_output_policy','midi_output_ports',
            'numerical_profile','parameter_count','parameter_schema_sha256','required_host_services','rnbo_version',
            'role','sample_rate','scheduler_time','source_tree_sha256','voice_topology','voices'}
        context={'voices':1,'voice_topology':'single-export','scheduler_time':'float64',
            'required_host_services':[],'midi_output_policy':'reject','midi_output_ports':0,
            'defined_int32_wrap':True,'execution':'static-development',
            'format':'rnbo-esp32s3-prepared-export','format_version':1}
        if (set(manifest)!=known or canonical({k:manifest.get(k) for k in context})!=canonical(context) or
                module['report'].get('imports')!=[] or
                snapshot!=expected['prepared_files_sha256'] or
                snapshot.get('source.rnbopat')!=expected['patch_sha256'] or
                snapshot.get('description.json')!=expected['description_sha256'] or
                snapshot.get('patch_config.h')!='a0d544c36042ca826ec6cd9deb332b80b68346e0986d49af73b16f7fc5486d5b'):
            raise ValueError('Gen logic normal strict file/profile/import composition differs')


def _logic_fixture(fixture):
    rows=[f for f in logic.catalog()['fixtures'] if f['id']==fixture.get('id')]
    if len(rows)!=1 or canonical(fixture)!=canonical(rows[0]|{'family':'gen-arithmetic'}):
        raise ValueError('Gen logic source, cases or exact syntax differs')


def verification(fixture,case,parameters,warmup,blocks):
    abs_mode=fixture.get('qualification_mode')==ABS_MODE
    logic_mode=fixture.get('id') in LOGIC_IDS
    if logic_mode:_logic_fixture(fixture)
    families=logic.INPUT_FAMILIES if logic_mode else (*INPUT_FAMILIES,ABS_INPUT) if abs_mode else INPUT_FAMILIES
    code=fixture['semantic']['model_code']
    declaration={'kind':KIND,'model_code':code,'maximum_absolute_error':0.0}
    if (parameters or warmup!=4 or blocks!=64 or fixture['verification']!=declaration or
            fixture['semantic']!=declaration or fixture['seed']!=0x12345678 or
            case not in fixture['cases'] or case['id'] not in families or
            case!={'id':case['id'],'parameters':{},'events':[],'stimulus':{'kind':case['id']}}):
        raise ValueError('Gen arithmetic target model/input/mode differs')
    return {**declaration,'observer_channel':2,'model':'independent-binary32-operations',
            'rounding':'once-binary32-per-output-operation',
            'gate':'raw-binary32-absolute-bits'if abs_mode else'numeric-exact-plus-signed-zero-only-operation-bits',
            'operation_zero_sign':'positive-zero-required'if abs_mode else'diagnostic-only'}
