#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original exact-source Gen comparison/logic fixtures; generation is not execution."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from generate_gen_arithmetic_fixtures import (
    canonical,digest,graph as arithmetic_graph,NORMAL_ADAPTATIONS,
    REGISTRY_SHA256,RUNTIME_SHA256,
)

FORMAT='rnbo-original-gen-logic-fixtures-v1'
FIXTURE_ROOT='tests/fixtures/gen/logic'
INPUT_FAMILIES=('signed-grid-v1','dense-binary32-v1','vector-boundaries-v1',
                'finite-magnitude-boundaries-v1')
# id, exact syntax token(s), syntax, registry canonical, arity, independent model.
RECIPES=(
    ('neq-call','neq','call','neq',2,11),
    ('not-equal-infix','!=','infix','neq',2,11),
    ('gt-call','gt','call','gt',2,12),
    ('greater-infix','>','infix','gt',2,12),
    ('gte-call','gte','call','gte',2,13),
    ('greater-equal-infix','>=','infix','gte',2,13),
    ('lte-call','lte','call','lte',2,14),
    ('less-equal-infix','<=','infix','lte',2,14),
    ('and-call','and','call','and',2,15),
    ('and-infix','&&','infix','and',2,15),
    ('or-call','or','call','or',2,16),
    ('or-infix','||','infix','or',2,16),
    ('xor-call','xor','call','xor',2,17),
    ('xor-infix','^^','infix','xor',2,17),
    ('not-call','not','call','not',1,18),
    ('not-prefix','!','prefix','not',1,18),
    ('bool-call','bool','call','bool',1,19),
    ('step-call','step','call','step',2,20),
    ('sign-call','sign','call','sign',1,21),
    ('switch-call','switch','call','switch',3,22),
    ('conditional-infix','?:','conditional','switch',3,22),
)
# Filled from the independently reviewed, actual RNBO 1.4.4 producer cohort.
EXPECTED_RAW_SOURCES={'and-call': '8cfc4b5a29a0828edcf10e15e1bfafdee387782cda2792c395a3c6c34c4a045b',
 'and-infix': '8cfc4b5a29a0828edcf10e15e1bfafdee387782cda2792c395a3c6c34c4a045b',
 'bool-call': '76f584b84b824b5d0ed0124440f7dfc7713e207dc730a65e9de57e494a6d9c75',
 'conditional-infix': '9fd89b8c0821baf9ec65ad6c4397f2b7aee1944300dd03e49029532e84168047',
 'greater-equal-infix': '6d0e035f82008dd85d6407b9272d42fbcf32c2741caad048c5dff86e1d59024b',
 'greater-infix': 'a88d72afb382297019f6bc05b06ca34a35b0cc01de54acc0b488c12bd7265bcf',
 'gt-call': 'a88d72afb382297019f6bc05b06ca34a35b0cc01de54acc0b488c12bd7265bcf',
 'gte-call': '6d0e035f82008dd85d6407b9272d42fbcf32c2741caad048c5dff86e1d59024b',
 'less-equal-infix': 'b97b5ffba5bb498c5f4ac2c8e68a371cdc51c80d1c4985f4e93fe88bb8dbe3ea',
 'lte-call': 'b97b5ffba5bb498c5f4ac2c8e68a371cdc51c80d1c4985f4e93fe88bb8dbe3ea',
 'neq-call': '446c4f1242559638b540b7cb4abc2cd3fa184a95cd689159ca0b09502b67a8ba',
 'not-call': '88a962bea508ac9f50c8272dbbb6ada8284123d400120e7b4557a405011c203e',
 'not-equal-infix': '446c4f1242559638b540b7cb4abc2cd3fa184a95cd689159ca0b09502b67a8ba',
 'not-prefix': '9a699c88bbbedc06c49bbc901c6b4e7a9255e40cd1a8c8b189a1b02314297bf4',
 'or-call': 'ccfc86741b63175358426ea237e1aad730cb8be561dfc0629e20072443f4243b',
 'or-infix': 'ccfc86741b63175358426ea237e1aad730cb8be561dfc0629e20072443f4243b',
 'sign-call': 'c66807e6b24f1be638cda82f38f4f155b94ebc055c217ea134aaeb29165ce387',
 'step-call': '210acebe7c33bdee5c1a8ec524f7771c1cf03d39cf61d2ab6cb39a1f91b73ded',
 'switch-call': 'a7dd6b19d370b70666133a1eaa08fee95cfe8db2221098383e7d6ddeefa37c2f',
 'xor-call': 'e1d182ccec7246a0adf1d2f3132db9234add5b187e56c646b0aacb2d36b2fa9e',
 'xor-infix': '351874a59f6e3ac35f35e60a6c69b7faa3de751cbbe7a6ee2c79f5d1f96f1621'}


def expression(identity):
    rows=[r for r in RECIPES if r[0]==identity and type(identity)is str]
    if len(rows)!=1:raise ValueError('Unknown original Gen logic fixture')
    _,name,syntax,_,arity,_=rows[0]
    if syntax=='conditional':return 'out1 = in1 ? in2 : -in2;\nout2 = in2 ? in1 : -in1;\n'
    if syntax=='prefix':return f'out1 = {name}in1;\nout2 = {name}in2;\n'
    if syntax=='infix':return f'out1 = in1 {name} in2;\nout2 = in2 {name} in1;\n'
    if arity==3:return 'out1 = switch(in1, in2, -in2);\nout2 = switch(in2, in1, -in1);\n'
    if arity==1:return f'out1 = {name}(in1);\nout2 = {name}(in2);\n'
    return f'out1 = {name}(in1, in2);\nout2 = {name}(in2, in1);\n'


def graph(identity):
    result=arithmetic_graph('abs-call')
    result['patcher']['boxes'][2]['box']['rnbo_extra_attributes']['expr']=expression(identity)
    return result


def recipe_catalog():
    rows=[]
    for identity,name,syntax,canonical_name,arity,model in RECIPES:
        lookup='?' if syntax=='conditional' else name
        rows.append({'id':identity,'patch':identity+'.rnbopat','genexpr':identity+'.genexpr',
            'source':{'surface':'genexpr','exact_name':name,'syntax':syntax,
                'inventory_id':'rnbo-genexpr:'+lookup,'registry_lookup':lookup,
                'canonical':canonical_name,'arity':arity},
            'model_code':model,'aliases_inherit_qualification':False})
    return {'format':'rnbo-original-gen-logic-recipes-v1','format_version':1,'license':'MIT',
        'scope':'Original syntax forms; aliases and ternary grammar have separate authored identities.',
        'primary_registry':{'version':'1.4.4','sha256':REGISTRY_SHA256,
            'local_package_path':'server/node_modules/@rnbo/genexpr_js/operators.json'},'recipes':rows}


def catalog():
    fixtures=[]
    for row in recipe_catalog()['recipes']:
        declaration={'kind':'gen-arithmetic-v1','model_code':row['model_code'],'maximum_absolute_error':0.0}
        fixtures.append({key:row[key] for key in ('id','patch','genexpr','source','aliases_inherit_qualification')}|{
            'surface':'genexpr','exact_entries':[row['source']['inventory_id']],
            'role':'fx','audio_inputs':2,'audio_outputs':2,'blocks':64,'warmup_blocks':4,
            'rounds':3,'seed':0x12345678,'arena_bytes':4096,'pcm_gain':0.5,
            'domain':{'finite':True,'input_type':'binary32','minimum':-1.0,'maximum':1.0,
                'zero_sign':'numeric-equality-with-separate-bit-observation'},
            'stimulus':{'kind':INPUT_FAMILIES[0]},
            'cases':[{'id':kind,'parameters':{},'events':[],'stimulus':{'kind':kind}} for kind in INPUT_FAMILIES],
            'semantic':dict(declaration),'verification':dict(declaration),
            'comparison_tolerance':{'maximum_absolute_error':0.0,'maximum_pcm_lsb_error':0,
                'relative_rms_level_difference':0.0}})
    return {'format':FORMAT,'format_version':1,'license':'MIT','fixture_root':FIXTURE_ROOT,
        'sample_rate':44100,'block_frames':256,
        'scope':'21 original GenExpr comparison/logic forms. Pending and failed outcomes do not become passes.',
        'event_order':'No parameters or events.','performance_gain_claimed':False,'fixtures':fixtures}


def authored_files():
    result={'recipes.json':canonical(recipe_catalog()),'catalog.json':canonical(catalog())}
    for identity,*_ in RECIPES:
        result[identity+'.genexpr']=expression(identity).encode()
        result[identity+'.rnbopat']=canonical(graph(identity))
    return result


def identities(prepared_root):
    from build import verify_prepared
    if not isinstance(prepared_root,Path) or prepared_root.is_symlink():
        raise ValueError('Use a regular directory of prepared Gen logic exports')
    expected={'rnbo_version':'1.4.4','numerical_profile':'float32-strict','class_name':'rnbos3patch',
        'role':'fx','audio_inputs':2,'audio_outputs':2,'parameter_count':0,
        'adaptations':list(NORMAL_ADAPTATIONS),'sample_rate':44100,'block_frames':256}
    context={'voices':1,'voice_topology':'single-export','scheduler_time':'float64',
        'required_host_services':[],'midi_output_policy':'reject','midi_output_ports':0,
        'defined_int32_wrap':True,'execution':'static-development',
        'format':'rnbo-esp32s3-prepared-export','format_version':1}
    known=set(expected)|set(context)|{'editable_source_sha256','parameter_schema_sha256','source_tree_sha256'}
    authored=authored_files();entries={};runtime=None
    for identity,_,_,canonical_name,_,_ in RECIPES:
        directory=prepared_root/identity
        if directory.is_symlink():raise ValueError('Linked prepared directory is not admitted')
        provenance,manifest,snapshot=verify_prepared(directory)
        if (set(manifest)!=known or
                canonical({k:manifest.get(k) for k in expected|context})!=canonical(expected|context)):
            raise ValueError('Prepared Gen logic ABI/profile differs')
        files=snapshot['prepared_files_sha256'];raw=provenance['raw_files_sha256']
        patch=authored[identity+'.rnbopat']
        source=EXPECTED_RAW_SOURCES.get(identity)
        if (source is None or len(files)!=42 or (directory/'source.rnbopat').read_bytes()!=patch or
                manifest['editable_source_sha256']!=digest(patch) or raw.get('rnbo_source.h')!=source or
                files.get('rnbo_source.h')!=source or manifest.get('required_host_services')!=[] or
                manifest.get('midi_output_policy')!='reject'):
            raise ValueError('Prepared Gen logic original source, graph or resources differ')
        common={k:v for k,v in files.items() if k.startswith('common/')}
        if len(common)!=36 or digest(canonical(common))!=RUNTIME_SHA256 or runtime is not None and runtime!=common:
            raise ValueError('Gen logic normal runtime differs')
        runtime=common
        entries[identity]={'editable_source_sha256':digest(patch),'patch_sha256':digest(patch),
            'genexpr_sha256':digest(authored[identity+'.genexpr']),
            'parameter_schema_sha256':manifest['parameter_schema_sha256'],
            'source_tree_sha256':manifest['source_tree_sha256'],'raw_source_sha256':source,
            'prepared_source_sha256':source,'description_sha256':files['description.json'],
            'prepared_files_sha256':files}
    return expected|{'runtime_files_sha256':runtime,'entries':entries}


def generate(output,*,prepared_root=None):
    if not isinstance(output,Path) or output.is_symlink() or output.exists():
        raise ValueError('Choose a fresh regular output directory')
    files=authored_files()
    if prepared_root is not None:files['identities.json']=canonical(identities(prepared_root))
    output=output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.gen-logic-',dir=output.parent))
    try:
        for name,data in files.items():(temporary/name).write_bytes(data)
        if output.exists() or output.is_symlink():raise ValueError('Output created concurrently')
        os.rename(temporary,output)
    finally:
        if temporary.exists():shutil.rmtree(temporary)
    return {'output':str(output),'authored_fixtures':len(RECIPES),
        'identities':prepared_root is not None,'DSP_execution_qualified':False,'hardware_executed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--prepared-root',type=Path)
    args=parser.parse_args()
    try:print(json.dumps(generate(args.out,prepared_root=args.prepared_root)))
    except (ValueError,OSError) as exc:parser.exit(1,str(exc)+'\n')
