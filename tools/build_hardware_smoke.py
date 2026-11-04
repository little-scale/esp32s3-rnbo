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
from inspect_module import inspect_module
from prepare import canonical,ExportError,read_json,read_regular,validate_description
from build_loader_spike import inventory,tree_digest


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_bytes(canonical(value))


def reference_path(catalog):
    family=catalog.get('family')
    if family not in ('gen-numeric','gen-math','gen-stateful','rnbo-stateless','rnbo-numeric','rnbo-functions','rnbo-constants','rnbo-events','rnbo-events-extra','rnbo-codebox','rnbo-codebox-constants'):
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


def prepare_plan(catalog_path,modules_path):
    catalog=read_json(read_regular(catalog_path,1024*1024),'smoke catalog')
    batch=read_json(read_regular(modules_path,8*1024*1024),'smoke modules')
    if (catalog.get('format')!='rnbo-hardware-smoke-catalog-v1' or
            catalog.get('sample_rate')!=44100 or catalog.get('block_frames')!=256 or
            batch.get('format')!='rnbo-smoke-modules-v1' or not batch.get('cache_control_whole_ELF_equal')):
        raise ExportError('Unsupported smoke catalog or unchecked module cache')
    reference_source=reference_path(catalog)
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
        module=modules[identity]
        patch=catalog_path.parent/row['patch']
        source_bytes=read_regular(patch,1024*1024)
        source_hash=hashlib.sha256(source_bytes).hexdigest()
        expression_info={}
        if catalog['family']in('rnbo-codebox','rnbo-codebox-constants'):
            expression_info['codebox_source_sha256']=checked_codebox_source(row,source_bytes)
            if 'codebox'in row and hashlib.sha256(read_regular(catalog_path.parent/row['codebox'],65536)).hexdigest()!=expression_info['codebox_source_sha256']:
                raise ExportError('Standalone and embedded codebox programs differ')
        if 'genexpr' in row:
            expression_info['genexpr_sha256']=hashlib.sha256(
                read_regular(catalog_path.parent/row['genexpr'],65536)).hexdigest()
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
        if manifest.get('editable_source_sha256')!=source_hash:
            raise ExportError('Prepared module does not match authored patch: '+identity)
        prepared=Path(module['prepared']['path'])
        if verify_prepared(prepared)[2]!=module['prepared']['snapshot']:
            raise ExportError('Prepared module changed: '+identity)
        if module['status']!='built':
            failures.append({'id':identity,'status':module['status'],'source_sha256':source_hash,
                **expression_info,'compile_log_sha256':module.get('compile_log_sha256'),
                'detail':'See module compiler log; not executed'})
            if catalog['family'] in ('gen-math','gen-stateful','rnbo-functions','rnbo-constants','rnbo-events','rnbo-events-extra','rnbo-codebox','rnbo-codebox-constants'):
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
        else:expected=checked_words(reference.reference_words(row['model'],vector))
        expected_hash=hashlib.sha256(struct.pack('<512I',*expected)).hexdigest()
        case={**row,'module_sha256':module['artifact']['sha256'],'module_bytes':len(data),
            'source_sha256':source_hash,**expression_info,
            'expected_words_sha256':expected_hash,'expected':expected}
        arena=module.get('arena_bytes_ceiling',4096)
        if type(arena)is not int or not 4096<=arena<=1048576:
            raise ExportError('Unsupported module arena tier: '+identity)
        if arena!=4096:case['arena_bytes']=arena
        if hasattr(reference,'case_input_words'):
            case.update(input_words=vector,input_words_sha256=hashlib.sha256(struct.pack('<512I',*vector)).hexdigest(),
                absolute_tolerance=absolute_tolerance(reference,row['model']))
        if streams is not None:
            case.update(expected_blocks=streams,expected_stream_sha256=hashlib.sha256(
                struct.pack('<10240I',*(w for block in streams for w in block))).hexdigest())
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
    if catalog['family']in('rnbo-codebox','rnbo-codebox-constants'):
        plan.update(family=catalog['family'],surface='codebox')
    elif catalog['family'] in ('rnbo-stateless','rnbo-numeric','rnbo-functions','rnbo-constants','rnbo-events','rnbo-events-extra'):
        plan.update(family=catalog['family'],surface='patcher')
        if catalog['family']=='rnbo-functions':plan['prepare_zero_warm_blocks']=0
        elif catalog['family']in('rnbo-events','rnbo-events-extra'):
            pool,refs=block_pool(cases)
            plan.update(prepare_zero_warm_blocks=0,expected_block_storage='shared-512-word-pool',
                expected_reference_unique_blocks=len(pool),expected_block_pool=pool,
                expected_stream_policy='Fresh prepared controls; ordered actual-value events before each full256-frame callback, no within-block event offsets')
            for case,indices in zip(cases,refs):
                case['expected_block_indices']=indices
                del case['expected_blocks']
    elif catalog['family']=='gen-math':
        plan.update(family='gen-math',surface='genexpr',prepare_zero_warm_blocks=0)
    elif catalog['family']=='gen-stateful':
        plan.update(family='gen-stateful',surface='genexpr',prepare_zero_warm_blocks=0,
            expected_stream_policy='Fresh prepared state, no automatic zero warmup; four checked manual warmups then sixteen timed callbacks without resets')
        if any('expected_blocks'not in c for c in cases):
            raise ExportError('Stateful cases require a continuous twenty-block reference')
    if hasattr(reference,'case_input_words'):
        plan['input_vector_policy']='per-case; top-level input hash identifies fallback vector only'
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
        lines.append('{.id=%s,.sha=%s,.reference_policy=%s,.payload_start=smoke_payload_%d_start,.payload_end=smoke_payload_%d_end,%s.expected={%s}},'%(
            json.dumps(row['id']),json.dumps(row['module_sha256']),json.dumps(policy),index,index,extra,words(row['expected'])))
    return '\n'.join(lines+['};','']),digest


def sources(catalog):
    data=json.loads(catalog.read_bytes())
    paths=[Path(__file__).resolve(),ROOT/'tools/build_smoke_modules.py',catalog,
        reference_path(data)]
    paths.extend(p for p in (ROOT/'hardware-smoke').rglob('*') if p.is_file())
    paths.extend(ROOT/'object-benchmark/main'/name for name in
        ('module_host.c','module_host.h','allocation_probe.c','allocation_probe.h','bench_check.h','mapped_range.h'))
    paths.extend(ROOT/'module-sdk/include'/name for name in ('rnbo_s3_module.h','rnbo_s3_dynamic.h'))
    for row in data['cases']:
        paths.extend(catalog.parent/row[key] for key in ('patch','genexpr','codebox') if key in row)
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
