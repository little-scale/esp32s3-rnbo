#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Embed a batch of admitted modules into one short hardware-functionality run."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host/compiler'))
from build import verify_prepared
from build_smoke_modules import (validate_manifest,validate_dbtoa_prepared,DBTOA_PROFILE,
                                DBTOA_CATALOG_SHA,DBTOA_REFERENCE_SHA,DBTOA_PATCH,
                                validate_smoke_prepared,gen_delay_catalog,GEN_DELAY_ADAPTATION,
                                GEN_DELAY_PROOFS,GEN_DELAY_REFERENCE_PROOFS,GEN_DELAY_REFERENCE_SHA)
from inspect_module import inspect_module
from prepare import canonical,ExportError,read_json,read_regular,validate_description
from build_loader_spike import inventory,tree_digest


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_bytes(canonical(value))


CHARACTER_FAMILY='rnbo-character-constants'
CHARACTER_CATALOG_SHA='27a6a6729ae43c1e5ffd43790badfdc8d82bf222f074f1e58eb1c97b15711b4b'
CHARACTER_REFERENCE_SHA='20f268ae5dfd17fc5307d5bffcc1c0f32d2641534760b4e0693240859b57a3e9'
CHARACTER_PARTITIONS={1:'76178ac972c5f58a77d20f45d1438fb8ed79ed47e4aee597102bf94983d12e2b',
                      2:'7e3fca609c25f2d358f1592f78e347a2bc4537f11a505a241f1f87abe2c6fd29'}
GEN_DATA_FAMILY='gen-data-indexed'
GEN_DATA_CATALOG_SHA='ea5a4fffcd130f140ffe3e4728fd66f5a8c437d535ad5ca398c817bc27c01f2a'
GEN_DATA_REFERENCE_SHA='aa4f5a7505cd853ea17accb4f0c691b7a6c3057fbe2f4d04cc517b68a44125a7'
CONTAINER_FAMILY='rnbo-codebox-containers'
CONTAINER_CATALOG_SHA='c68ab57a23461a465e063b5f5236ddab74a6ac75fed805d2e3e28ad2545f0551'
CONTAINER_REFERENCE_SHA='02f78c4c5d52e01c7ee7fd71da8afec1239423eb89f0abd396b7e960b6b59640'
GEN_CONTROL_FAMILY='gen-control-structures'
GEN_CONTROL_CATALOG_SHA='bf8c4a7582e2ad9c35c36de431a0815f41ff2c5d98a9a5e70902204b5d8f6a3f'
GEN_CONTROL_REFERENCE_SHA='19717b7c849829c9b5fc6c413e33711755c95382c1e84edaca2a3517d8d37815'
LIST_FUNCTION_FAMILY='rnbo-codebox-list-functions'
LIST_FUNCTION_CATALOG_SHA='85227b9328fa2f533e9b415cb388c39a53574f8695d697ab15b89e6e912981b3'
LIST_FUNCTION_REFERENCE_SHA='039e1aaa9ca582188e179bec7cf717fb56a2a76f7457c8b6f1af257ed4d78b23'


STRUCTURE_FAMILY='rnbo-codebox-structures'
STRUCTURE_CATALOG_SHA='c2f6d0189f9ddcddc47d82275ac7bfe33f17d93f3293794a0c9613d0831dec73'
STRUCTURE_REFERENCE_SHA='acf6851ab4761707e14d9c5d0a55ff69fc7d2c9b87472c6ce6b3a22da29fe779'


def structure_catalog(catalog):
    if (catalog.get('family')!=STRUCTURE_FAMILY or
            hashlib.sha256(canonical(catalog)).hexdigest()!=STRUCTURE_CATALOG_SHA):
        raise ExportError('Codebox structures require the exact24 authored language/lifecycle sources')


def list_function_catalog(catalog):
    if (catalog.get('family')!=LIST_FUNCTION_FAMILY or
            hashlib.sha256(canonical(catalog)).hexdigest()!=LIST_FUNCTION_CATALOG_SHA):
        raise ExportError('List-function checks require the exact34 authored flat/dotted call sources')


def gen_control_catalog(catalog):
    if (catalog.get('family')!=GEN_CONTROL_FAMILY or
            hashlib.sha256(canonical(catalog)).hexdigest()!=GEN_CONTROL_CATALOG_SHA):
        raise ExportError('Gen control checks require the exact26 authored comparison/declaration/structure sources')


def container_catalog(catalog):
    if (catalog.get('family')!=CONTAINER_FAMILY or
            hashlib.sha256(canonical(catalog)).hexdigest()!=CONTAINER_CATALOG_SHA):
        raise ExportError('Container checks require the exact28 authored member/constructor programs')


def gen_data_catalog(catalog):
    if (catalog.get('family')!=GEN_DATA_FAMILY or
            hashlib.sha256(canonical(catalog)).hexdigest()!=GEN_DATA_CATALOG_SHA):
        raise ExportError('Gen indexed data requires the exact eight original declaration/function scenarios')
    return {key:catalog[key]for key in ('producer_storage_view','storage_policy')}


def character_catalog(catalog):
    """Only the two reviewed source partitions, not arbitrary constant programs."""
    index=catalog.get('partition',{}).get('index')
    if (catalog.get('family')!=CHARACTER_FAMILY or type(index)is not int or index not in CHARACTER_PARTITIONS or
            hashlib.sha256(canonical(catalog)).hexdigest()!=CHARACTER_PARTITIONS[index]):
        raise ExportError('Character constants require the exact corrected43/42 source partitions')
    parent=ROOT/'tests/fixtures/smoke/rnbo-character-constants/catalog.json'
    if sha(parent)!=CHARACTER_CATALOG_SHA:
        raise ExportError('Original full character catalog changed')
    return catalog['partition']


def checked_character_source(row,source):
    """Sparse codebox input name in2 is physical ordinal0, without input holes."""
    if (row.get('surface')!='codebox' or row.get('syntax')!='named-value' or row.get('role')!='fx' or
            row.get('codebox_inlet_names')!=['in2'] or type(row.get('codebox_pilot_inlet_ordinal'))is not int or
            row['codebox_pilot_inlet_ordinal']!=0 or type(row.get('strict_zero_sign_channels'))is not int or
            row['strict_zero_sign_channels']!=2 or type(row.get('raw_pilot_channel'))is not int or
            row['raw_pilot_channel']!=1 or hashlib.sha256(source).hexdigest()!=row.get('patch_sha256')):
        raise ExportError('Character source requires its exact codebox/right-word pilot contract')
    try:
        patch=json.loads(source)['patcher'];boxes=[entry['box']for entry in patch['boxes']]
        texts=[box.get('text')for box in boxes];ids={box['text']:box['id']for box in boxes}
        program=next(box for box in boxes if box.get('text')=='codebox~')
        code=program['rnbo_extra_attributes']['code'];links=[entry['patchline']for entry in patch['lines']]
        edges={(tuple(link['source']),tuple(link['destination']))for link in links}
        expected={((ids['in~ 2'],0),(ids['codebox~'],0)),
                  ((ids['codebox~'],0),(ids['out~ 1'],0)),((ids['codebox~'],1),(ids['out~ 2'],0))}
    except (KeyError,TypeError,ValueError,StopIteration):
        raise ExportError('Malformed character codebox graph')
    if (patch.get('classnamespace')!='rnbo' or len(boxes)!=5 or
            set(texts)!={'in~ 1','in~ 2','out~ 1','out~ 2','codebox~'} or len(set(ids.values()))!=5 or
            any(box.get('maxclass')!='newobj'or box.get('patcher')for box in boxes) or
            code!=f"out1 = {row['exact_name']};\nout2 = in2;\n" or
            len(links)!=3 or edges!=expected or any(link.get('disabled')for link in links)):
        raise ExportError('Character graph requires its exact five-box three-edge route')
    return hashlib.sha256(code.encode()).hexdigest()


def reference_path(catalog):
    family=catalog.get('family')
    if family==CHARACTER_FAMILY:return ROOT/'tests/fixtures/smoke/rnbo-character-constants/reference.py'
    if family=='dbtoa-f32-comparison':return ROOT/'tests/fixtures/smoke/dbtoa-f32-comparison/reference.py'
    if family not in ('gen-numeric','gen-math','gen-stateful','gen-state-boundaries','gen-data-indexed','gen-control-structures','gen-range','gen-constants','rnbo-stateless','rnbo-numeric','rnbo-functions','rnbo-constants','rnbo-signal-range','rnbo-signal-stateful','rnbo-signal-state-followup','rnbo-signal-routing','rnbo-events','rnbo-events-extra','rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-list-functions','rnbo-character-constants'):
        raise ExportError('Unsupported smoke reference family')
    return ROOT/'tests/fixtures/smoke'/family/'reference.py'


def checked_codebox_source(row,source):
    """Bind the new surface to an authored RNBO codebox~, never Gen/patcher ops."""
    if row.get('surface')!='codebox':
        raise ExportError('Codebox smoke requires an explicit codebox case surface')
    try:
        patch=json.loads(source)['patcher']
        boxes=[entry['box']for entry in patch['boxes']]
        texts=[box.get('text')for box in boxes]
        program=next(box for box in boxes if box.get('text')=='codebox~')
        code=program.get('rnbo_extra_attributes',{}).get('code')
    except (KeyError,TypeError,ValueError,StopIteration):
        raise ExportError('Codebox smoke needs an authored flat RNBO codebox graph')
    if (patch.get('classnamespace')!='rnbo' or len(boxes)!=5 or
            any(type(text)is not str for text in texts)or
            set(texts)!={'in~ 1','in~ 2','out~ 1','out~ 2','codebox~'} or
            any(box.get('maxclass')!='newobj'or box.get('patcher') for box in boxes) or
            type(code)is not str or not code.strip()or '\0'in code or len(code)>65536):
        raise ExportError('Codebox smoke requires one explicit program and plain stereo I/O')
    try:
        ids={box['text']:box['id']for box in boxes}
        links=[entry['patchline']for entry in patch['lines']]
        edges={(tuple(link['source']),tuple(link['destination']))for link in links}
        outputs={((ids['codebox~'],lane),(ids['out~ '+str(lane+1)],0))for lane in(0,1)}
        inputs={((ids['in~ '+str(lane+1)],0),(ids['codebox~'],lane))for lane in(0,1)}
    except (KeyError,TypeError,ValueError):
        raise ExportError('Codebox smoke has malformed authored connections')
    if (len(edges)!=len(links)or any(link.get('disabled')for link in links)or
            edges not in(outputs,outputs|inputs)):
        raise ExportError('Codebox output must flow through the program without bypasses')
    return hashlib.sha256(code.encode('utf-8')).hexdigest()



def checked_words(words):
    words=tuple(words)
    if len(words)!=512 or any(type(w)is not int or not 0<=w<=0xffffffff or
            (w&0x7f800000)==0x7f800000 for w in words):
        raise ExportError('Smoke vectors require 512 finite binary32 words')
    return words


def absolute_tolerance(reference,model):
    value=getattr(reference,'ABSOLUTE_TOLERANCES',{}).get(model,0)
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1e-3:
        raise ExportError('Invalid predeclared absolute error tolerance')
    return struct.unpack('<f',struct.pack('<f',value))[0]


def float32(value):
    if type(value)not in(int,float) or not math.isfinite(value):
        raise ExportError('Expected a finite numeric parameter value')
    result=struct.unpack('<f',struct.pack('<f',value))[0]
    if not math.isfinite(result):raise ExportError('Parameter value exceeds binary32')
    return result


def parameter_case(prepared,manifest,reference,model):
    raw=validate_description(read_json(read_regular(prepared/'description.json',1024*1024),'parameter description'),'fx','reject')
    schema=[{k:p.get(k)for k in ('paramId','index','name','displayName','unit','minimum','maximum','initialValue','exponent','steps')}for p in raw]
    if not 1<=len(raw)<=32 or len(raw)!=manifest['parameter_count'] or hashlib.sha256(canonical(schema)).hexdigest()!=manifest['parameter_schema_sha256']:
        raise ExportError('Prepared parameter schema/count differs')
    parameters=[]
    for p in raw:
        if not re.fullmatch('[A-Za-z0-9_.-]+',p['paramId']) or p['exponent']!=1 or p['steps']!=0:
            raise ExportError('Boundary smoke supports token IDs and linear unstepped numeric controls')
        parameters.append({'id':p['paramId'],'minimum':float32(p['minimum']),'maximum':float32(p['maximum']),
            'initial':float32(p['initialValue']),'exponent':float32(p['exponent']),'steps':p['steps']})
    slots={p['id']:i for i,p in enumerate(parameters)};events=[]
    for action in reference.parameter_events(model):
        call=action.get('before_call');identity=action.get('id');value=float32(action.get('value'))
        if type(call)is not int or not 0<=call<20 or identity not in slots or(events and call<events[-1]['before_call']):
            raise ExportError('Invalid or unordered boundary parameter action')
        parameter=parameters[slots[identity]]
        if not parameter['minimum']<=value<=parameter['maximum']:
            raise ExportError('Boundary parameter value is outside its admitted range')
        normalized=float32((value-parameter['minimum'])/(parameter['maximum']-parameter['minimum']))
        events.append({'before_call':call,'id':identity,'parameter_slot':slots[identity],
            'value_word':struct.unpack('<I',struct.pack('<f',value))[0],
            'normalized_word':struct.unpack('<I',struct.pack('<f',normalized))[0]})
    if not events or len(events)>128:raise ExportError('Boundary smoke requires one to128 authored actions')
    return {'expected_parameter_count':len(parameters),'parameters':parameters,
        'parameter_schema_sha256':manifest['parameter_schema_sha256'],'parameter_events':events,
        'strict_zero_sign_channels':2}


def block_pool(cases):
    blocks=[];indices={};refs=[]
    for case in cases:
        row=[]
        for block in case['expected_blocks']:
            key=tuple(block)
            if key not in indices:indices[key]=len(blocks);blocks.append(key)
            row.append(indices[key])
        refs.append(row)
    return blocks,refs


def routing_contract(row,manifest=None):
    """The routing batch uses ordinary, parameter-free signal patchers only."""
    if (row.get('surface')!='patcher' or row.get('role')!='fx' or
            row.get('syntax')!='signal-object' or 'genexpr'in row or 'codebox'in row):
        raise ExportError('Signal routing requires its own ordinary FX signal-object source')
    if manifest is not None:
        validate_manifest(manifest)
        if manifest['parameter_count']!=0:
            raise ExportError('Signal routing requires zero parameters')


def comparison_contract(catalog,batch):
    """Bind root's repeated ABBA rows to both unmodified compiler batches."""
    if hashlib.sha256(canonical(catalog)).hexdigest()!=DBTOA_CATALOG_SHA:
        raise ExportError('dbtoa comparison requires the exact four-vector three-round ABBA catalog')
    reports=batch.get('comparison_source_reports',{})
    if type(reports)is not dict or set(reports)!={'A','B'}:
        raise ExportError('dbtoa comparison needs both original source batch reports')
    originals={}
    for phase,expected in (('A','float32-strict'),('B',DBTOA_PROFILE)):
        binding=reports[phase];path=Path(binding['path'])
        raw=read_regular(path,8*1024*1024)
        if hashlib.sha256(raw).hexdigest()!=binding.get('sha256'):
            raise ExportError('dbtoa original compiler batch changed')
        source=read_json(raw,'dbtoa source batch')
        if (source.get('format')!='rnbo-smoke-modules-v1' or source.get('cache_control_whole_ELF_equal')is not True or
                source.get('source_cache_and_prepared_before_after_unchanged')is not True or
                source.get('max_arena_bytes')!=1048576 or source.get('cache_control_max_arena_bytes')!=4096 or
                len(source.get('modules',[]))!=1 or source['modules'][0].get('status')!='built' or
                source['modules'][0]['prepared']['manifest'].get('numerical_profile')!=expected):
            raise ExportError('dbtoa compiler batch profile/cache/arena differs')
        originals[phase]=source
    for field in ('source_files_sha256','compiler','private_support_archives','cache_inputs_sha256'):
        if not originals['A'].get(field) or originals['A'].get(field)!=originals['B'].get(field):
            raise ExportError('dbtoa compiler/SDK/archive/cache cohorts differ')
    modules={r['id']:r for r in batch['modules']}
    for row in catalog['cases']:
        source=originals[row['comparison_phase']]['modules'][0]
        if canonical(modules[row['id']])!=canonical(source|{'id':row['id']}):
            raise ExportError('dbtoa merged module row differs from its original compiler batch')
    return reports


def prepare_plan(catalog_path,modules_path):
    catalog=read_json(read_regular(catalog_path,1024*1024),'smoke catalog')
    batch=read_json(read_regular(modules_path,8*1024*1024),'smoke modules')
    if (catalog.get('format')!='rnbo-hardware-smoke-catalog-v1' or
            catalog.get('sample_rate')!=44100 or catalog.get('block_frames')!=256 or
            batch.get('format')!='rnbo-smoke-modules-v1' or not batch.get('cache_control_whole_ELF_equal')):
        raise ExportError('Unsupported smoke catalog or unchecked module cache')
    reference_source=reference_path(catalog)
    structures=catalog.get('family')==STRUCTURE_FAMILY
    if structures:
        structure_catalog(catalog)
        if sha(reference_source)!=STRUCTURE_REFERENCE_SHA:
            raise ExportError('Codebox structure independent reference changed')
    list_functions=catalog.get('family')==LIST_FUNCTION_FAMILY
    if list_functions:
        list_function_catalog(catalog)
        if sha(reference_source)!=LIST_FUNCTION_REFERENCE_SHA:
            raise ExportError('List function independent reference changed')
    gen_control=catalog.get('family')==GEN_CONTROL_FAMILY
    if gen_control:
        gen_control_catalog(catalog)
        if sha(reference_source)!=GEN_CONTROL_REFERENCE_SHA:
            raise ExportError('Gen control independent reference changed')
    containers=catalog.get('family')==CONTAINER_FAMILY
    if containers:
        container_catalog(catalog)
        if sha(reference_source)!=CONTAINER_REFERENCE_SHA:
            raise ExportError('Container independent reference changed')
    gen_data=catalog.get('family')==GEN_DATA_FAMILY
    if gen_data:
        storage_labels=gen_data_catalog(catalog)
        if sha(reference_source)!=GEN_DATA_REFERENCE_SHA:
            raise ExportError('Gen local data independent reference changed')
    character=catalog.get('family')==CHARACTER_FAMILY
    if character:
        character_partition=character_catalog(catalog)
        if sha(reference_source)!=CHARACTER_REFERENCE_SHA:
            raise ExportError('Character independent reference changed')
    delay_rerun=gen_delay_catalog(catalog)
    source_root=reference_source.parent if delay_rerun is not None else catalog_path.parent
    if delay_rerun is not None and (sha(reference_source)!=GEN_DELAY_REFERENCE_SHA or
            sha(catalog_path)!=hashlib.sha256(canonical(delay_rerun)).hexdigest()):
        raise ExportError('Original Gen Delay reference or canonical rerun catalog changed')
    comparison=catalog.get('family')=='dbtoa-f32-comparison'
    if comparison:
        comparison_reports=comparison_contract(catalog,batch)
        if sha(reference_source)!=DBTOA_REFERENCE_SHA:raise ExportError('dbtoa mathematical reference changed')
    spec=importlib.util.spec_from_file_location('smoke_reference',reference_source)
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    inputs=checked_words(reference.input_words(256))
    modules={r['id']:r for r in batch['modules']}
    if len(modules)!=len(batch['modules']) or set(modules)!={r['id']for r in catalog['cases']}:
        raise ExportError('Module batch and source catalog identities differ')
    cases=[];failures=[];admission_failures=[];payloads=[]
    for row in catalog['cases']:
        identity=row['id']
        if not re.fullmatch('[A-Za-z0-9_-]+',identity):raise ExportError('Unsafe smoke identity')
        if catalog['family']in('rnbo-signal-routing','rnbo-signal-state-followup'):routing_contract(row)
        module=modules[identity]
        patch=source_root/row['patch']
        source_bytes=read_regular(patch,1024*1024)
        source_hash=hashlib.sha256(source_bytes).hexdigest()
        expression_info={}
        if catalog['family']in('rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-list-functions','rnbo-character-constants'):
            expression_info['codebox_source_sha256']=(checked_character_source(row,source_bytes)if character
                                                       else checked_codebox_source(row,source_bytes))
            if 'codebox'in row and hashlib.sha256(read_regular(catalog_path.parent/row['codebox'],65536)).hexdigest()!=expression_info['codebox_source_sha256']:
                raise ExportError('Standalone and embedded codebox programs differ')
            if (containers or list_functions or structures) and (source_hash!=row['patch_sha256'] or expression_info['codebox_source_sha256']!=row['codebox_sha256']):
                raise ExportError('Container/list-function authored source changed')
        if 'genexpr' in row:
            expression_info['genexpr_sha256']=hashlib.sha256(
                read_regular(source_root/row['genexpr'],65536)).hexdigest()
        if gen_control and (source_hash!=row['patch_sha256'] or expression_info.get('genexpr_sha256')!=row['genexpr_sha256']):
            raise ExportError('Gen control authored source changed')
        if module['status']=='native_preflight_failed':
            if not list_functions:raise ExportError('Native exclusion requires its reviewed list-function family')
            preflight=module.get('native_preflight',{})
            log=preflight.get('run_log',{});raw=read_regular(Path(log['path']),65536)
            result=read_json(raw,'native preflight output')
            if (preflight.get('returncode')!=3 or type(result.get('process_status'))is not int or
                    result['process_status']>=0 or type(result.get('fault_call'))is not int or
                    not 0<=result['fault_call']<20 or result.get('samples')!=result['fault_call']*512 or
                    sha(ROOT/'tests/native/smoke_stream_test.cpp')!=preflight.get('harness_sha256') or
                    hashlib.sha256(raw).hexdigest()!=log.get('sha256') or len(raw)!=log.get('bytes')):
                raise ExportError('Native preflight fault/log/harness identity differs')
            _,native_manifest,native_snapshot=verify_prepared(Path(module['prepared']['path']))
            if (native_manifest.get('editable_source_sha256')!=source_hash or
                    native_snapshot!=module['prepared']['snapshot']):
                raise ExportError('Native-rejected module prepared source differs')
            vector=checked_words(reference.case_input_words(row['model'],256))
            expected=checked_words(reference.reference_words(row['model'],vector))
            if (preflight.get('input_words_sha256')!=hashlib.sha256(struct.pack('<512I',*vector)).hexdigest() or
                    preflight.get('expected_stream_sha256')!=hashlib.sha256(struct.pack('<10240I',*(expected*20))).hexdigest()):
                raise ExportError('Native preflight vector/reference differs')
            admission_failures.append({**{k:row[k]for k in ('id','exact_name','syntax','registry_lookup')},
                'status':'native_preflight_failed','stage':'native-preflight','returncode':3,
                'source_sha256':source_hash,**expression_info,'failure_log_sha256':log['sha256'],
                'native_harness_sha256':preflight['harness_sha256'],'native_process_status':result['process_status'],
                'native_fault_call':result['fault_call'],'native_samples_checked':result['samples'],
                'detail':'Native module process faulted; target module compiled but is not embedded or executed in this hardware batch'})
            continue
        if module['status'] in ('export_failed','prepare_failed'):
            stage='export' if module['status']=='export_failed' else 'prepare'
            if (module.get('source_sha256')!=source_hash or type(module.get('returncode'))is not int or
                    module['returncode']==0 or module.get('artifact') or module.get('prepared')):
                raise ExportError('Malformed pre-compilation failure: '+identity)
            log=module.get('failure_log',{})
            log_data=read_regular(Path(log['path']),8*1024*1024)
            if len(log_data)!=log['bytes'] or hashlib.sha256(log_data).hexdigest()!=log['sha256']:
                raise ExportError('Pre-compilation failure log changed: '+identity)
            admission_failures.append({**{k:row[k]for k in ('id','exact_name','syntax','registry_lookup')},
                'status':module['status'],'stage':stage,'returncode':module['returncode'],
                'source_sha256':source_hash,**expression_info,'failure_log_sha256':log['sha256'],
                'detail':stage.capitalize()+' rejected this source; not compiled or executed'})
            continue
        manifest=module.get('prepared',{}).get('manifest',{})
        if character or gen_data or containers or gen_control or list_functions or structures:
            validate_manifest(manifest)
            if manifest['parameter_count']!=0:
                raise ExportError('This smoke family requires the strict parameter-free FX profile')
        if delay_rerun is None and GEN_DELAY_ADAPTATION in manifest.get('adaptations',[]):
            raise ExportError('Repaired Gen Delay modules require the exact marked two-case rerun')
        if comparison and manifest.get('numerical_profile')!=row['numerical_profile']:
            raise ExportError('dbtoa phase label differs from actual prepared profile')
        if not comparison and manifest.get('numerical_profile')==DBTOA_PROFILE:
            raise ExportError('dbtoa candidate requires its explicit comparison family')
        if catalog['family']in('rnbo-signal-routing','rnbo-signal-state-followup'):routing_contract(row,manifest)
        if manifest.get('editable_source_sha256')!=source_hash:
            raise ExportError('Prepared module does not match authored patch: '+identity)
        prepared=Path(module['prepared']['path'])
        provenance,actual_manifest,actual_snapshot=verify_prepared(prepared)
        if actual_snapshot!=module['prepared']['snapshot']:
            raise ExportError('Prepared module changed: '+identity)
        if delay_rerun is None and GEN_DELAY_ADAPTATION in actual_manifest.get('adaptations',[]):
            raise ExportError('Actual repaired Gen Delay requires its marked two-case rerun')
        if delay_rerun is not None:
            repair=validate_smoke_prepared(provenance,actual_manifest,actual_snapshot)
            if (actual_manifest!=manifest or repair!=GEN_DELAY_PROOFS.get(identity) or
                    module.get('gen_delay_fix_contract')!=repair or module.get('status')!='built'):
                raise ExportError('Gen Delay rerun requires both exact repaired module exports')
        if (catalog['family']in('rnbo-signal-routing','rnbo-signal-state-followup')or character or gen_data or containers or gen_control or list_functions or structures)and actual_manifest!=manifest:
            raise ExportError('Signal routing module manifest differs from prepared files: '+identity)
        if comparison:
            if actual_manifest!=manifest or source_hash!=DBTOA_PATCH:
                raise ExportError('dbtoa prepared manifest/graph differs from comparison source')
            profile_proof=validate_dbtoa_prepared(provenance,actual_manifest,actual_snapshot)
        if module['status']!='built':
            failures.append({'id':identity,'status':module['status'],'source_sha256':source_hash,
                **expression_info,'compile_log_sha256':module.get('compile_log_sha256'),
                'detail':'See module compiler log; not executed'})
            if catalog['family'] in ('gen-math','gen-stateful','gen-state-boundaries','gen-data-indexed','gen-control-structures','gen-range','gen-constants','rnbo-functions','rnbo-constants','rnbo-signal-range','rnbo-signal-stateful','rnbo-signal-state-followup','rnbo-signal-routing','rnbo-events','rnbo-events-extra','rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-list-functions','rnbo-character-constants'):
                failures[-1].update({k:row[k]for k in ('exact_name','syntax','registry_lookup')})
            continue
        artifact=Path(module['artifact']['path']);data=read_regular(artifact,524288)
        if hashlib.sha256(data).hexdigest()!=module['artifact']['sha256'] or len(data)!=module['artifact']['bytes']:
            raise ExportError('Module artifact changed: '+identity)
        inspection=inspect_module(data,allowed_imports=set())
        if inspection['imports']:raise ExportError('Smoke module imports are not empty')
        vector=checked_words(reference.case_input_words(row['model'],256)) if hasattr(reference,'case_input_words') else inputs
        streams=None
        if hasattr(reference,'reference_blocks'):
            streams=tuple(checked_words(block)for block in reference.reference_blocks(row['model'],vector,call_count=20))
            if len(streams)!=20:raise ExportError('Stateful reference must supply twenty checked callback blocks')
            expected=streams[0]
        else:expected=checked_words(reference.reference_words(vector)if comparison else reference.reference_words(row['model'],vector))
        expected_hash=hashlib.sha256(struct.pack('<512I',*expected)).hexdigest()
        case={**row,'module_sha256':module['artifact']['sha256'],'module_bytes':len(data),
            'source_sha256':source_hash,**expression_info,
            'expected_words_sha256':expected_hash,'expected':expected}
        if comparison:case['module_profile_contract']=profile_proof
        if delay_rerun is not None:case['gen_delay_fix_contract']=repair
        arena=module.get('arena_bytes_ceiling',4096)
        if type(arena)is not int or arena not in(4096,1048576,2097152):
            raise ExportError('Unsupported module arena tier: '+identity)
        if arena!=4096:case['arena_bytes']=arena
        if hasattr(reference,'case_input_words'):
            case.update(input_words=vector,input_words_sha256=hashlib.sha256(struct.pack('<512I',*vector)).hexdigest(),
                absolute_tolerance=absolute_tolerance(reference,row['model']))
        if character and (arena!=4096 or case.get('absolute_tolerance')!=0 or
                type(getattr(reference,'STRICT_ZERO_SIGN_CHANNELS',None))is not int or
                reference.STRICT_ZERO_SIGN_CHANNELS!=2 or row['strict_zero_sign_channels']!=2 or
                hasattr(reference,'reference_blocks')):
            raise ExportError('Character constants require exact constant blocks and raw right-word mask2')
        if comparison and (arena!=1048576 or case.get('absolute_tolerance')!=float32(2e-6) or
                any(not -24<=struct.unpack('<f',struct.pack('<I',word))[0]<=6 for word in vector)):
            raise ExportError('dbtoa comparison arena/input/error domain differs')
        if catalog['family']in('rnbo-signal-routing','rnbo-signal-state-followup')and case.get('absolute_tolerance',0)>2e-6:
            raise ExportError('Signal routing supports exact or at most2e-6 absolute error')
        if streams is not None:
            case.update(expected_blocks=streams,expected_stream_sha256=hashlib.sha256(
                struct.pack('<10240I',*(w for block in streams for w in block))).hexdigest())
        if gen_data and (arena!=4096 or row.get('surface')!='genexpr' or row.get('role')!='fx' or
                row.get('owner_kind')not in('declaration','function-call')or streams is None or
                case.get('absolute_tolerance',0)>2e-6 or 'strict_zero_sign_channels'in case):
            raise ExportError('Gen local data requires original storage and twenty continuous numeric references')
        if delay_rerun is not None and (arena!=4096 or any(case.get(key)!=value for key,value in
                GEN_DELAY_REFERENCE_PROOFS[identity].items())):
            raise ExportError('Gen Delay rerun arena or original twenty-block reference changed')
        if manifest['parameter_count']:
            if catalog['family']not in('rnbo-events','rnbo-events-extra') or not hasattr(reference,'parameter_events'):
                raise ExportError('Parameterized exports require the boundary-event reference route')
            case.update(parameter_case(prepared,manifest,reference,row['model']))
        cases.append(case)
        payloads.append(artifact)
    pooled=catalog['family']in('rnbo-events','rnbo-events-extra')
    if pooled and any(c.get('absolute_tolerance',0)!=0 for c in cases):
        raise ExportError('Boundary-event references require zero absolute tolerance')
    if pooled and any('expected_blocks'not in c or not c.get('expected_parameter_count')for c in cases):
        raise ExportError('Boundary-event cases need parameters and twenty-block references')
    stream_bytes=4*sum(len(block)for c in cases for block in c.get('expected_blocks',()))
    if pooled:stream_bytes=4*512*len(block_pool(cases)[0])+4*20*len(cases)
    reference_bytes=stream_bytes+4*(len(inputs)+sum(len(c['expected'])+len(c.get('input_words',()))for c in cases))
    if not cases or sum(p.stat().st_size for p in payloads)+reference_bytes>2*1024*1024:
        raise ExportError('Empty or oversized module/reference batch; split the catalog')
    plan={'format':'rnbo-hardware-smoke-plan-v1','catalog_sha256':sha(catalog_path),
        'module_batch_sha256':sha(modules_path),'reference_source_sha256':sha(reference_source),
        'sample_rate':44100,'block_frames':256,'warmup_blocks':4,'timed_blocks':16,
        'input_words_sha256':hashlib.sha256(struct.pack('<512I',*inputs)).hexdigest(),
        'cases':cases,'compile_failures':failures,
        'scope':'Short functional vector and callback timing; not comprehensive qualification or an optimisation comparison'}
    if comparison:
        plan.update(family='dbtoa-f32-comparison',surface='patcher',prepare_zero_warm_blocks=0,
                    comparison_order='vector-outer-round-middle-ABBA-inner-v1',
                    comparison_source_reports=comparison_reports,
                    profile_comparison_scope='Complete bounded stereo FX callbacks; no direct target A/B sample comparison')
    elif character:
        plan.update(family=CHARACTER_FAMILY,surface='codebox',prepare_zero_warm_blocks=0,
                    partition=character_partition,strict_zero_sign_channels=2,raw_pilot_channel=1)
    elif catalog['family']in('rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-list-functions','rnbo-character-constants'):
        plan.update(family=catalog['family'],surface='codebox')
        if catalog['family']in('rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-list-functions','rnbo-character-constants'):plan['prepare_zero_warm_blocks']=0
        if catalog['family']in('rnbo-codebox-stateful','rnbo-codebox-filters','rnbo-codebox-containers','rnbo-codebox-structures'):
            plan['expected_stream_policy']='Fresh prepared codebox state; twenty continuous256-frame callbacks without resets'
            if any('expected_blocks'not in c for c in cases):
                raise ExportError('Stateful codebox cases require twenty continuous reference blocks')
    elif catalog['family'] in ('rnbo-stateless','rnbo-numeric','rnbo-functions','rnbo-constants','rnbo-signal-range','rnbo-signal-stateful','rnbo-signal-state-followup','rnbo-signal-routing','rnbo-events','rnbo-events-extra'):
        plan.update(family=catalog['family'],surface='patcher')
        if catalog['family']in('rnbo-functions','rnbo-signal-range','rnbo-signal-stateful','rnbo-signal-state-followup','rnbo-signal-routing'):plan['prepare_zero_warm_blocks']=0
        if catalog['family']in('rnbo-signal-stateful','rnbo-signal-state-followup'):
            plan['expected_stream_policy']='Fresh prepared signal state; twenty continuous256-frame callbacks without resets'
            if any('expected_blocks'not in c for c in cases):
                raise ExportError('Stateful signal cases require twenty continuous reference blocks')
        elif catalog['family']in('rnbo-events','rnbo-events-extra'):
            pool,refs=block_pool(cases)
            plan.update(prepare_zero_warm_blocks=0,expected_block_storage='shared-512-word-pool',
                expected_reference_unique_blocks=len(pool),expected_block_pool=pool,
                expected_stream_policy='Fresh prepared controls; ordered actual-value events before each full256-frame callback, no within-block event offsets')
            for case,indices in zip(cases,refs):
                case['expected_block_indices']=indices
                del case['expected_blocks']
    elif catalog['family']in('gen-range','gen-constants'):
        plan.update(family=catalog['family'],surface='genexpr',prepare_zero_warm_blocks=0)
    elif catalog['family']=='gen-math':
        plan.update(family='gen-math',surface='genexpr',prepare_zero_warm_blocks=0)
    elif catalog['family']in('gen-stateful','gen-state-boundaries','gen-data-indexed','gen-control-structures'):
        plan.update(family=catalog['family'],surface='genexpr',prepare_zero_warm_blocks=0,
            expected_stream_policy='Fresh prepared state, no automatic zero warmup; four checked manual warmups then sixteen timed callbacks without resets')
        if any('expected_blocks'not in c for c in cases):
            raise ExportError('Stateful cases require a continuous twenty-block reference')
    if hasattr(reference,'case_input_words'):
        plan['input_vector_policy']='per-case; top-level input hash identifies fallback vector only'
    if delay_rerun is not None:plan['rerun']=delay_rerun['rerun']
    if gen_data:plan.update(storage_labels)
    if admission_failures:plan['admission_failures']=admission_failures
    return plan,inputs,payloads


def generate_header(plan,inputs):
    digest=hashlib.sha256(canonical(plan)).hexdigest()
    words=lambda data:','.join('0x%08xu'%w for w in data)
    lines=['/* SPDX-License-Identifier: MIT */','#pragma once',
        '#define SMOKE_CASE_COUNT %du'%len(plan['cases']),'#define SMOKE_ARENA_BYTES 4096u',
        '#define SMOKE_SEED 305419896u','#define SMOKE_PLAN_SHA256 '+json.dumps(digest),
        'static const uint32_t smoke_inputs[512]={'+words(inputs)+'};']
    if 'prepare_zero_warm_blocks' in plan:
        lines.append('#define SMOKE_PREPARE_WARM_BLOCKS %du'%plan['prepare_zero_warm_blocks'])
    pooled=plan.get('expected_block_storage')=='shared-512-word-pool'
    if pooled:
        pool=plan['expected_block_pool'];refs=[c['expected_block_indices']for c in plan['cases']]
        if len(pool)!=plan['expected_reference_unique_blocks']:raise ExportError('Expected block pool size differs')
        for index,block in enumerate(pool):
            lines.append('static const uint32_t smoke_reference_block_%d[512]={%s};'%(index,words(block)))
    for index,row in enumerate(plan['cases']):
        if 'input_words' in row:
            lines.append('static const uint32_t smoke_case_inputs_%d[512]={%s};'%(index,words(row['input_words'])))
        if 'expected_blocks' in row and not pooled:
            lines.append('static const uint32_t smoke_expected_blocks_%d[10240]={%s};'%(
                index,words(w for block in row['expected_blocks']for w in block)))
        elif pooled:
            lines.append('static const uint32_t *const smoke_expected_refs_%d[20]={%s};'%(
                index,','.join('smoke_reference_block_%d'%i for i in refs[index])))
        if 'parameters' in row:
            lines.append('static const smoke_parameter_contract smoke_parameters_%d[]={%s};'%(
                index,','.join('{.id=%s,%s.steps=%du}'%(json.dumps(p['id']),''.join('.%s=%sf,'%(k,float(p[k]).hex())for k in ('minimum','maximum','initial','exponent')),p['steps'])for p in row['parameters'])))
            lines.append('static const smoke_parameter_action smoke_actions_%d[]={%s};'%(
                index,','.join('{.before_call=%du,.parameter_slot=%du,.value_word=0x%08xu}'%(e['before_call'],e['parameter_slot'],e['value_word'])for e in row['parameter_events'])))
    lines.append('static const smoke_case smoke_cases[SMOKE_CASE_COUNT]={')
    for index,row in enumerate(plan['cases']):
        policy='observational-signed-fraction' if row['model']==28 or row.get('reference_policy') in ('signed-fraction-convention','observational-signed-fraction') else 'documented-basic'
        extra=''
        if 'input_words' in row:
            tolerance=row['absolute_tolerance']
            if tolerance:policy='mathematical-approximation'
            extra='.input_words=smoke_case_inputs_%d,.absolute_tolerance=%sf,'%(index,float(tolerance).hex())
        if 'expected_blocks' in row and not pooled:
            extra+='.expected_blocks=smoke_expected_blocks_%d,'%index
        elif pooled:extra+='.expected_block_refs=smoke_expected_refs_%d,'%index
        if 'arena_bytes' in row:extra+='.arena_bytes=%du,'%row['arena_bytes']
        if 'parameters' in row:
            extra+='.expected_parameter_count=%du,.parameters=smoke_parameters_%d,.parameter_event_count=%du,.parameter_events=smoke_actions_%d,.strict_zero_sign_channels=%du,'%(
                row['expected_parameter_count'],index,len(row['parameter_events']),index,row['strict_zero_sign_channels'])
        if plan.get('family')==CHARACTER_FAMILY:
            if (type(row.get('strict_zero_sign_channels'))is not int or row['strict_zero_sign_channels']!=2 or
                    'parameters'in row):
                raise ExportError('Character header requires parameter-free right-word mask2')
            extra+='.strict_zero_sign_channels=2u,'
        lines.append('{.id=%s,.sha=%s,.reference_policy=%s,.payload_start=smoke_payload_%d_start,.payload_end=smoke_payload_%d_end,%s.expected={%s}},'%(
            json.dumps(row['id']),json.dumps(row['module_sha256']),json.dumps(policy),index,index,extra,words(row['expected'])))
    return '\n'.join(lines+['};','']),digest


def sources(catalog):
    data=json.loads(catalog.read_bytes())
    delay_rerun=gen_delay_catalog(data)
    source_root=reference_path(data).parent if delay_rerun is not None else catalog.parent
    paths=[Path(__file__).resolve(),ROOT/'tools/build_smoke_modules.py',catalog,
        reference_path(data)]
    if delay_rerun is not None:paths.append(source_root/'catalog.json')
    paths.extend(p for p in (ROOT/'hardware-smoke').rglob('*') if p.is_file())
    paths.extend(ROOT/'object-benchmark/main'/name for name in
        ('module_host.c','module_host.h','allocation_probe.c','allocation_probe.h','bench_check.h','mapped_range.h'))
    paths.extend(ROOT/'module-sdk/include'/name for name in ('rnbo_s3_module.h','rnbo_s3_dynamic.h'))
    for row in data['cases']:
        paths.extend(source_root/row[key] for key in ('patch','genexpr','codebox') if key in row)
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths)) if '__pycache__'not in p.parts}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',type=Path,default=ROOT/'tests/fixtures/smoke/gen-numeric/catalog.json')
    parser.add_argument('--modules-report',required=True,type=Path)
    parser.add_argument('--build-dir',required=True,type=Path)
    parser.add_argument('--idf-path',type=Path,default=Path.home()/'esp/esp-idf')
    parser.add_argument('--dependencies-dir',type=Path,default=ROOT/'build/vendor-object-benchmark')
    parser.add_argument('--cache-build-dir',type=Path,help='Reusable SDK build cache; completed batch artifacts are copied to --build-dir')
    parser.add_argument('--validate-only',action='store_true')
    parser.add_argument('--resume-incomplete',action='store_true',help='Reuse an unfinished SDK build with the identical smoke plan; preserve previous logs')
    args=parser.parse_args();catalog=args.catalog.resolve();out=args.build_dir.resolve()
    plan,inputs,payloads=prepare_plan(catalog,args.modules_report.resolve())
    header,digest=generate_header(plan,inputs)
    if out.exists():
        if not args.resume_incomplete or (out/'build-report.json').exists():
            raise ExportError('Choose a fresh build directory or resume an unfinished build')
        if canonical(json.loads((out/'smoke-plan.json').read_bytes()))!=canonical(plan):
            raise ExportError('Cannot resume a different smoke plan')
    if args.validate_only:print(json.dumps({'cases':len(payloads),'compile_failures':len(plan['compile_failures']),'admission_failures':len(plan.get('admission_failures',[])),'plan_sha256':digest}));return
    out.mkdir(parents=True,exist_ok=True);config=out/'smoke-config';config.mkdir(exist_ok=True)
    cache=args.cache_build_dir.resolve() if args.cache_build_dir else out
    cache.mkdir(parents=True,exist_ok=True)
    if(out/'build.log').exists():
        index=1
        while(out/f'build-attempt-{index:03d}.log').exists():index+=1
        (out/'build.log').rename(out/f'build-attempt-{index:03d}.log')
    (config/'smoke_cases.h').write_text(header)
    (config/'modules.cmake').write_text('set(SMOKE_MODULE_FILES\n'+''.join('  '+json.dumps(str(p))+'\n' for p in payloads)+')\n')
    save(out/'smoke-plan.json',plan)
    lock=json.loads((ROOT/'loader-spike/dependencies.json').read_bytes());deps={}
    for name in ('elf_loader','cmake_utilities'):
        path=args.dependencies_dir.resolve()/name;actual=inventory(path)
        if actual!=lock['components'][name]['files_sha256']:raise ExportError('Loader dependency differs: '+name)
        deps[name]={'sha256':tree_digest(actual),'version':lock['components'][name]['version']}
    idf=args.idf_path.resolve();environment=dict(os.environ,IDF_PATH=str(idf),IDF_COMPONENT_MANAGER='0',PYTHONDONTWRITEBYTECODE='1')
    if not environment.get('IDF_PYTHON_ENV_PATH'):
        candidates=sorted(p for p in (Path.home()/'.espressif/python_env').glob('idf5.5_py*_env') if(p/'bin/python').is_file())
        if not candidates:raise ExportError('Installed ESP-IDF5.5 Python environment required')
        environment['IDF_PYTHON_ENV_PATH']=str(candidates[-1])
    definitions=['IDF_TARGET=esp32s3','SDKCONFIG='+str(cache/'sdkconfig'),
        'SDKCONFIG_DEFAULTS='+str(ROOT/'hardware-smoke/sdkconfig.defaults')+';'+str(ROOT/'hardware-smoke/sdkconfig.xiao.defaults'),
        'SMOKE_DEPENDENCIES_DIR='+str(args.dependencies_dir.resolve()),'SMOKE_CONFIG_DIR='+str(config),
        'SMOKE_MODULES_CMAKE='+str(config/'modules.cmake')]
    command=['bash','-e','-c','source "$1/export.sh" >/dev/null; shift; exec "$IDF_PYTHON_ENV_PATH/bin/python" "$IDF_PATH/tools/idf.py" "$@"',
        'hardware-smoke',str(idf),'-B',str(cache)]
    for definition in definitions:command+=['-D',definition]
    command+=['build'];before=sources(catalog)
    with(out/'build.log').open('w')as log:
        result=subprocess.run(command,cwd=ROOT/'hardware-smoke',env=environment,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise ExportError('Smoke firmware build failed; inspect '+str(out/'build.log'))
    if sources(catalog)!=before:raise ExportError('Smoke sources changed during compilation')
    after,_,_=prepare_plan(catalog,args.modules_report.resolve())
    if after!=plan:raise ExportError('Smoke inputs/modules changed during compilation')
    description=json.loads((cache/'project_description.json').read_bytes())
    config_text=(cache/'sdkconfig').read_text()
    required=('CONFIG_ELF_LOADER=y','CONFIG_ELF_LOADER_LOAD_PSRAM=y','CONFIG_ELF_LOADER_CACHE_OFFSET=y',
        'CONFIG_HEAP_USE_HOOKS=y','CONFIG_SPIRAM_MODE_OCT=y','CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y',
        'CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_240=y')
    forbidden=('CONFIG_ELF_LOADER_LIBC_SYMBOLS=y','CONFIG_ELF_LOADER_ESPIDF_SYMBOLS=y',
        'CONFIG_ELF_LOADER_CUSTOMER_SYMBOLS=y','CONFIG_ELF_DYNAMIC_LOAD_SHARED_OBJECT=y')
    if not all(x in config_text for x in required) or any(x in config_text for x in forbidden):
        raise ExportError('Resolved smoke firmware configuration differs')
    artifacts={}
    for name in (description['app_elf'],description['app_bin'],'partition_table/partition-table.bin'):
        path=out/name
        if cache!=out:
            path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(cache/name,path)
        artifacts[str(path.relative_to(ROOT))]={'bytes':path.stat().st_size,'sha256':sha(path)}
    if cache!=out:
        for name in ('sdkconfig','project_description.json','compile_commands.json'):
            shutil.copy2(cache/name,out/name)
    report={'format':'rnbo-hardware-smoke-build-v1','board':'xiao','artifacts':artifacts,
        'plan_sha256':digest,'plan':plan,'header_sha256':sha(config/'smoke_cases.h'),
        'dependencies':deps,'source_files_sha256':before,'command':command,
        'hardware_executed':False,'optimisation_comparison':False}
    save(out/'build-report.json',report)
    print(json.dumps({'build_report':str(out/'build-report.json'),'cases':len(payloads),'plan_sha256':digest}))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,ExportError)as exc:raise SystemExit(str(exc))
