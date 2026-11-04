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
from prepare import canonical,ExportError,read_json,read_regular
from build_loader_spike import inventory,tree_digest


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_bytes(canonical(value))


def reference_path(catalog):
    family=catalog.get('family')
    if family not in ('gen-numeric','rnbo-stateless','rnbo-numeric'):
        raise ExportError('Unsupported smoke reference family')
    return ROOT/'tests/fixtures/smoke'/family/'reference.py'


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
    cases=[];failures=[];payloads=[]
    for row in catalog['cases']:
        identity=row['id']
        if not re.fullmatch('[A-Za-z0-9_-]+',identity):raise ExportError('Unsafe smoke identity')
        module=modules[identity]
        patch=catalog_path.parent/row['patch']
        source_hash=hashlib.sha256(read_regular(patch,1024*1024)).hexdigest()
        expression_info={}
        if 'genexpr' in row:
            expression_info['genexpr_sha256']=hashlib.sha256(
                read_regular(catalog_path.parent/row['genexpr'],65536)).hexdigest()
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
            continue
        artifact=Path(module['artifact']['path']);data=read_regular(artifact,524288)
        if hashlib.sha256(data).hexdigest()!=module['artifact']['sha256'] or len(data)!=module['artifact']['bytes']:
            raise ExportError('Module artifact changed: '+identity)
        inspection=inspect_module(data,allowed_imports=set())
        if inspection['imports']:raise ExportError('Smoke module imports are not empty')
        vector=checked_words(reference.case_input_words(row['model'],256)) if hasattr(reference,'case_input_words') else inputs
        expected=checked_words(reference.reference_words(row['model'],vector))
        expected_hash=hashlib.sha256(struct.pack('<512I',*expected)).hexdigest()
        case={**row,'module_sha256':module['artifact']['sha256'],'module_bytes':len(data),
            'source_sha256':source_hash,**expression_info,
            'expected_words_sha256':expected_hash,'expected':expected}
        if hasattr(reference,'case_input_words'):
            case.update(input_words=vector,input_words_sha256=hashlib.sha256(struct.pack('<512I',*vector)).hexdigest(),
                absolute_tolerance=absolute_tolerance(reference,row['model']))
        cases.append(case)
        payloads.append(artifact)
    if not cases or sum(p.stat().st_size for p in payloads)>2*1024*1024:
        raise ExportError('Empty or oversized smoke batch; split the catalog')
    plan={'format':'rnbo-hardware-smoke-plan-v1','catalog_sha256':sha(catalog_path),
        'module_batch_sha256':sha(modules_path),'reference_source_sha256':sha(reference_source),
        'sample_rate':44100,'block_frames':256,'warmup_blocks':4,'timed_blocks':16,
        'input_words_sha256':hashlib.sha256(struct.pack('<512I',*inputs)).hexdigest(),
        'cases':cases,'compile_failures':failures,
        'scope':'Short functional vector and callback timing; not comprehensive qualification or an optimisation comparison'}
    if catalog['family'] in ('rnbo-stateless','rnbo-numeric'):
        plan.update(family=catalog['family'],surface='patcher')
    if hasattr(reference,'case_input_words'):
        plan['input_vector_policy']='per-case; top-level input hash identifies fallback vector only'
    return plan,inputs,payloads


def generate_header(plan,inputs):
    digest=hashlib.sha256(canonical(plan)).hexdigest()
    words=lambda data:','.join('0x%08xu'%w for w in data)
    lines=['/* SPDX-License-Identifier: MIT */','#pragma once',
        '#define SMOKE_CASE_COUNT %du'%len(plan['cases']),'#define SMOKE_ARENA_BYTES 4096u',
        '#define SMOKE_SEED 305419896u','#define SMOKE_PLAN_SHA256 '+json.dumps(digest),
        'static const uint32_t smoke_inputs[512]={'+words(inputs)+'};']
    for index,row in enumerate(plan['cases']):
        if 'input_words' in row:
            lines.append('static const uint32_t smoke_case_inputs_%d[512]={%s};'%(index,words(row['input_words'])))
    lines.append('static const smoke_case smoke_cases[SMOKE_CASE_COUNT]={')
    for index,row in enumerate(plan['cases']):
        policy='observational-signed-fraction' if row['model']==28 or row.get('reference_policy') in ('signed-fraction-convention','observational-signed-fraction') else 'documented-basic'
        extra=''
        if 'input_words' in row:
            tolerance=row['absolute_tolerance']
            if tolerance:policy='mathematical-approximation'
            extra='.input_words=smoke_case_inputs_%d,.absolute_tolerance=%sf,'%(index,float(tolerance).hex())
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
        paths.extend(catalog.parent/row[key] for key in ('patch','genexpr') if key in row)
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
    if args.validate_only:print(json.dumps({'cases':len(payloads),'compile_failures':len(plan['compile_failures']),'plan_sha256':digest}));return
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
