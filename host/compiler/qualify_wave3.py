#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the fixed stateful RNBO native qualification, computer only.

An authorised local RNBO1.4.4 package, Node and a Clang/GCC C/C++ toolchain are
required. No hardware is accessed. Exit0 means all gates pass,1 means retained
qualification failures, and2 means an input/setup/integrity error. Reports and
captures are kept, including when the independent accuracy gates fail.
Default: all45 strict cases. --onepole-only explicitly selects15 original
cases; --stable-onepole applies the optional profile only to onepole forms.
"""
from __future__ import annotations
import argparse
import array
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import threading

from build import verify_prepared
from prepare import canonical, prepare

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/'tests/fixtures/objects/wave3'
CATALOG=FIXTURES/'catalog.json'
NATIVE=FIXTURES/'native'
CATALOG_SHA256='62ae485b86743b1b603a70a153d90f2cfc59fcc300727acb37ce6be2164e09ba'
ORIGINAL_PROBE_SHA256='e3abed2915a9b68256d062df5d8c269e32a56f2f297febcb53f48e23c0c15af2'
ORIGINAL_INPUTS_SHA256='1ce42cf7f7edf60f2bb945cc5723376c9c84f34de6f1dcc5a9c690f5774e1e11'
SDK_SOURCES=('module-sdk/dynamic/rnbo_s3_dynamic.cpp','module-sdk/dynamic/arena.cpp',
 'module-sdk/dynamic/arena.hpp','module-sdk/dynamic/lifecycle.hpp',
 'module-sdk/include/rnbo_s3_module.h','module-sdk/include/rnbo_s3_dynamic.h',
 'firmware/components/pcm_output/pcm_output.c','firmware/components/pcm_output/include/pcm_output.h')
PRINT_LOCK=threading.Lock()

class QualificationError(ValueError):pass

def require(ok,message):
    if not ok:raise QualificationError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(data):return hashlib.sha256(data).hexdigest()
def save(path,data):
    require(not path.exists(),f'Report already exists: {path}')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(data))
def emit(data):
    with PRINT_LOCK:print(json.dumps(data),flush=True)
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    require(spec is not None and spec.loader is not None,f'Cannot import {path}')
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def validate_output(path):
    out=path.resolve();build=(ROOT/'build').resolve()
    require(out!=build and build in out.parents,'Choose a fresh output directory below this repository\'s build/ directory')
    require(not out.exists(),f'Output already exists; choose a new directory: {out}')
    return out

def load_catalog(data=None):
    raw=CATALOG.read_bytes()if data is None else data
    require(isinstance(raw,bytes)and digest(raw)==CATALOG_SHA256,'The fixed wave3 catalogue changed; review its inputs, gates and qualification before updating this driver')
    catalog=json.loads(raw)
    require(len(catalog['fixtures'])==10 and sum(len(f['cases'])for f in catalog['fixtures'])==45,'Expected10authoredforms/45cases')
    return catalog

def select_catalog(catalog, *, onepole_only=False):
    """Explicit selection only; never silently hide other known failures."""
    require(type(onepole_only)is bool,'onepole-only must be a boolean')
    result=copy.deepcopy(catalog)
    if onepole_only:
        result['fixtures']=[f for f in result['fixtures']if f['object_spelling']=='onepole~']
        require({f['id']for f in result['fixtures']}=={'onepole-fixed-stereo','onepole-scalar-stereo','onepole-signal-cutoff'}and
                len(result['fixtures'])==3 and sum(len(f['cases'])for f in result['fixtures'])==15,
                'Expected the three reviewed onepole forms and15 original programs')
    return result

def run_logged(command,path):
    with path.open('w')as log:
        subprocess.run(command,cwd=ROOT,check=True,stdout=log,stderr=subprocess.STDOUT)

def audit_readbacks(trace,plan):
    """Check the authored command order and every subsequent actual readback."""
    initial=[f'{struct.unpack("<I",struct.pack("<f",p["initialValue"]))[0]:08x}'for p in plan['parameter_schema']]
    at=0;counts={'event_readback_records':0,'block_readback_records':0}
    for cycle in range(plan['lifecycles']):
        state=list(initial);event=0
        for block in range(plan['blocks']):
            while event<len(plan['events'])and plan['events'][event]['block']==block:
                require(at<len(trace),'Missing command readback');row=trace[at];expected=plan['events'][event];at+=1
                require(row['kind']=='event'and row['cycle']==cycle and row['block']==block and row['order']==event,'Command source order changed')
                require(row['id']==expected['id']and row['index']==expected['index']and row['requested_bits']==expected['value_bits']and row['result']==0,'Command identity/value/result mismatch')
                state[expected['index']]=expected['value_bits'];require(row['actual_bits']==state,'Command actual readback mismatch')
                require(row['position']==block*256 and row['blocks']==block,'Command advanced the sample clock')
                check_normalized(row,len(state));counts['event_readback_records']+=1;event+=1
            require(at<len(trace),'Missing vector readback');row=trace[at];at+=1
            require(row['kind']=='block'and row['cycle']==cycle and row['block']==block and row['result']==0,'Vector order/result mismatch')
            require(row['actual_bits']==state and row['position']==(block+1)*256 and row['blocks']==block+1,'Vector actual readback/sample clock mismatch')
            check_normalized(row,len(state));counts['block_readback_records']+=1
        require(event==len(plan['events']),'Not all authored commands were executed')
    require(at==len(trace),'Unexpected extra trace records')
    return counts

def check_normalized(row,count):
    require(len(row['normalized_bits'])==count,'Normalized readback count mismatch')
    for bits in row['normalized_bits']:
        value=struct.unpack('<f',struct.pack('<I',int(bits,16)))[0]
        require(math.isfinite(value)and 0<=value<=1,'Invalid normalized readback')

def audit_case_protocol(record,plan,out):
    try:
        trace=[json.loads(line)for line in(out/record['files']['.trace.jsonl']['path']).read_text().splitlines()]
        counts=audit_readbacks(trace,plan)
        for cycle in record['statistics']['cycles']:
            require(cycle['completed']and cycle['captured_blocks']==plan['blocks']and cycle['blocks']==plan['blocks']and cycle['position']==plan['blocks']*256 and cycle['events_applied']==len(plan['events'])and cycle['panic_silent'],'Incomplete lifecycle/panic check')
            require(all(cycle[k]==0 for k in('late_platform','late_cpp','total_late','errors','invalid_samples','faulted','bootstrap_attempts','pcm_nonfinite','pcm_clipped')),'Fault, late allocation or PCM error')
        return {'passed':True,'lifecycle_runs':len(record['statistics']['cycles']),**counts}
    except (QualificationError,KeyError,ValueError,TypeError,OverflowError,struct.error)as exc:
        return {'passed':False,'error':str(exc)}

def export_fixture(fixture,out,node,rnbo_dir,*,stable_onepole=False):
    id=fixture['id'];raw=out/'raw'/id;prepared=out/'prepared'/id;log=out/'logs'/(id+'-export.log')
    command=[node,str(ROOT/'archive/importer/export.mjs'),str(FIXTURES/fixture['patch']),'--out',str(raw)]
    if rnbo_dir is not None:command+=['--rnbo-dir',str(rnbo_dir)]
    run_logged(command,log)
    apply_stable=stable_onepole and fixture['object_spelling']=='onepole~'
    prepare(raw,prepared,'rnbos3patch','fx',stable_onepole=apply_stable) # Other object forms remain strict.
    provenance,manifest,snapshot=verify_prepared(prepared)
    require(manifest['numerical_profile']=='float32-strict'and manifest['audio_inputs']==manifest['audio_outputs']==2,'Unreviewed prepared mode')
    require(manifest.get('stable_onepole',False)is apply_stable,'Requested onepole profile was not applied exactly')
    emit({'stage':'prepared','fixture':id,'stable_onepole':apply_stable})
    return id,{'command':command,'requested_stable_onepole':apply_stable,'manifest':manifest,'snapshot':snapshot,'raw_files_sha256':provenance['raw_files_sha256']}

def make_plans(catalog,exports,out,inputs):
    records=[];cache={};wire_plans=[]
    for f in catalog['fixtures']:
        id=f['id'];description=json.loads((out/'prepared'/id/'description.json').read_text())
        schema=sorted(description['parameters'],key=lambda p:p['index']);indices={p['paramId']:p['index']for p in schema}
        require(set(indices)=={p['id']for p in f['parameters']}and len(schema)<=8,'Parameter schema changed')
        for case in f['cases']:
            frames=case['blocks']*256;key=json.dumps({'input':case['input'],'frames':frames},sort_keys=True);name=digest(key.encode())[:20]
            if name not in cache:
                data=inputs.fill(case['input'],frames);path=out/'inputs'/(name+'.f32');path.write_bytes(data)
                cache[name]={'path':str(path.relative_to(out)),'sha256':digest(data),'frames':frames,'channels':2,'spec':case['input']}
            record={'fixture':id,'case':case['id'],'input_id':name,**cache[name]};records.append(record)
            events=[]
            for order,e in enumerate(case['events']):
                require(e.get('form')=='actual','Only reviewed actual boundary events are admitted')
                value=struct.unpack('<f',struct.pack('<f',e['value']))[0];index=indices[e['id']];parameter=schema[index]
                require(parameter['minimum']<=value<=parameter['maximum'],'Event outside authored parameter bounds')
                raw=struct.unpack('<I',struct.pack('<f',value))[0];events.append({**e,'order':order,'index':index,'value':value,'value_bits':f'{raw:08x}'})
            require(all(events[i]['block']<=events[i+1]['block']for i in range(len(events)-1)),'Events must retain declared block/source order')
            plan=out/'plans'/(id+'--'+case['id']+'.bin')
            header=struct.pack('<8I',0x57563331,1,case['blocks'],case['warmup_blocks'],f['seed'],len(events),case['lifecycles'],len(schema))
            plan.write_bytes(header+b''.join(struct.pack('<3I',e['block'],e['index'],int(e['value_bits'],16))for e in events))
            wire_plans.append({'fixture_id':id,'id':case['id'],'blocks':case['blocks'],'warmup_blocks':case['warmup_blocks'],'lifecycles':case['lifecycles'],'parameter_schema':schema,'events':events,'plan_file':str(plan.relative_to(out)),'plan_sha256':sha(plan),'input_file':record['path'],'input_sha256':record['sha256'],'input_spec':case['input']})
    save(out/'input-index.json',{'format':'wave3-authoritative-input-cache-v1','records':records})
    save(out/'plans.json',{'format':'wave3-stateful-actual-wire-plans-v1','catalog_sha256':CATALOG_SHA256,'plans':wire_plans})
    return wire_plans,{str((out/p['path']).relative_to(out)):p['sha256']for p in cache.values()}

def compile_and_run(pair,fixtures,plans,out,cc,cxx,oracle):
    id,mode=pair;fixture=fixtures[id];prepared=out/'prepared'/id;directory=out/'native'/id/mode;directory.mkdir(parents=True,exist_ok=False)
    opts=['-O3']if mode=='O3'else['-O2','-fsanitize=undefined,signed-integer-overflow,float-cast-overflow','-fno-sanitize-recover=all']
    common=['-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing']
    flags=[cxx,'-std=c++17',*opts,*common,'-fno-exceptions','-fno-rtti','-fno-builtin','-UNDEBUG',
        '-DRNBO_S3_DYNAMIC_MAX_ARENA_BYTES=4096u','-I'+str(ROOT/'module-sdk/include'),'-I'+str(ROOT/'module-sdk/dynamic'),
        '-I'+str(ROOT/'firmware/components/pcm_output/include'),'-I'+str(prepared),'-I'+str(prepared/'common')]
    commands=[[cc,'-std=c11',*opts,*common,'-I'+str(ROOT/'firmware/components/pcm_output/include'),'-c',str(ROOT/'firmware/components/pcm_output/pcm_output.c'),'-o',str(directory/'pcm.o')],
        [*flags,'-Dmain=rnbo_native_entry','-c',str(ROOT/'module-sdk/dynamic/rnbo_s3_dynamic.cpp'),'-o',str(directory/'wrapper.o')],
        [*flags,str(NATIVE/'probe.cpp'),str(directory/'wrapper.o'),str(ROOT/'module-sdk/dynamic/arena.cpp'),str(directory/'pcm.o'),'-o',str(directory/'probe')]]
    # support.cpp/lifecycle.cpp deliberately are NOT native link inputs. Native
    # host libc/libm resolution cannot establish target imports/ELF lifecycle.
    run_logged(commands[0],directory/'pcm-build.log');run_logged(commands[1],directory/'wrapper-build.log');run_logged(commands[2],directory/'probe-build.log')
    binary=directory/'probe';binary_before=sha(binary);result={'fixture':id,'object_spelling':fixture['object_spelling'],'mode':mode,'commands':commands,'binary_sha256':binary_before,'cases':{}}
    for case in fixture['cases']:
        plan=next(p for p in plans if p['fixture_id']==id and p['id']==case['id']);prefix=directory/case['id'];input=out/plan['input_file']
        require(sha(input)==plan['input_sha256']and sha(out/plan['plan_file'])==plan['plan_sha256'],'Input/plan changed before execution')
        command=[str(binary),str(out/plan['plan_file']),str(input),str(prefix)]
        ran=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=90)
        (directory/(case['id']+'.stdout')).write_text(ran.stdout);(directory/(case['id']+'.stderr')).write_text(ran.stderr)
        record={'command':command,'returncode':ran.returncode,'stderr':ran.stderr,'input_sha256':plan['input_sha256'],'plan_sha256':plan['plan_sha256']}
        if ran.returncode==0:
            stats=json.loads(ran.stdout);record['statistics']=stats;record['completed']=all(c['completed']for c in stats['cycles'])
            record['files']={suffix:{'path':str(Path(str(prefix)+suffix).relative_to(out)),'sha256':sha(str(prefix)+suffix)}for suffix in('.f32','.pcm16','.trace.jsonl')}
            if record['completed']:
                source=array.array('f');source.frombytes(input.read_bytes());actual=array.array('f');actual.frombytes((out/record['files']['.f32']['path']).read_bytes());frames=case['blocks']*256
                require(len(actual)==frames*2*case['lifecycles'],'Incomplete Float32 output')
                wire_case={**case,'events':plan['events']};record['independent_accuracy']=[oracle.analyse(fixture,wire_case,(source[::2],source[1::2]),(actual[cycle*frames*2:(cycle+1)*frames*2:2],actual[cycle*frames*2+1:(cycle+1)*frames*2:2]))for cycle in range(case['lifecycles'])]
                record['protocol']=audit_case_protocol(record,plan,out)
        result['cases'][case['id']]=record
        emit({'stage':'case','fixture':id,'mode':mode,'case':case['id'],'healthy':record.get('completed',False),'accuracy_pass':all(x['passed']for x in record.get('independent_accuracy',[{'passed':False}]))})
    require(sha(binary)==binary_before,'Executable changed during qualification')
    result['binary_unchanged_after_execution']=True;save(directory/'build-and-case-report.json',result);return id+'--'+mode,result

def compare_results(catalog,builds,out):
    comparisons=[];reconstruction=[]
    for fixture in catalog['fixtures']:
        id=fixture['id']
        for case in fixture['cases']:
            a=builds[id+'--O3']['cases'][case['id']];b=builds[id+'--UBSan']['cases'][case['id']]
            row={'fixture':id,'id':case['id'],'returncodes_equal':a['returncode']==b['returncode'],'completed':a.get('completed',False)and b.get('completed',False)}
            if a['returncode']==b['returncode']==0:
                accuracy_evaluated=row['completed']and all(len(r.get('independent_accuracy',[]))==case['lifecycles']for r in(a,b))
                row.update(statistics_exact=a['statistics']==b['statistics'],files_byte_identical={s:a['files'][s]['sha256']==b['files'][s]['sha256']for s in a['files']},captured_channel_words=sum(c['captured_blocks']for c in a['statistics']['cycles'])*512,accuracy_evaluated=accuracy_evaluated,accuracy_pass=accuracy_evaluated and all(x['passed']for r in(a,b)for x in r['independent_accuracy']))
                for mode,item in(('O3',a),('UBSan',b)):
                    if item['completed']:
                        same={}
                        for suffix in('.f32','.pcm16'):
                            data=(out/item['files'][suffix]['path']).read_bytes();half=len(data)//2;same[suffix]=data[:half]==data[half:]
                        x,y=item['statistics']['cycles'];reconstruction.append({'fixture':id,'id':case['id'],'mode':mode,'output_bytes_equal':same,'statistics_equal':{k:v for k,v in x.items()if k!='cycle'}=={k:v for k,v in y.items()if k!='cycle'}})
            comparisons.append(row)
    return comparisons,reconstruction

def qualify(output,rnbo_dir=None,*,stable_onepole=False,onepole_only=False):
    require(type(stable_onepole)is bool and type(onepole_only)is bool,'Profile and selection options must be booleans')
    out=validate_output(output);catalog=select_catalog(load_catalog(),onepole_only=onepole_only)
    require(sys.byteorder=='little'and struct.calcsize('f')==4,'Native capture requires a little-endian Float32 host')
    require(sha(NATIVE/'probe.cpp')==ORIGINAL_PROBE_SHA256 and sha(NATIVE/'inputs.py')==ORIGINAL_INPUTS_SHA256,'Reviewed native probe/input generator changed; review before updating this driver')
    node=shutil.which('node');cc=shutil.which('cc');cxx=shutil.which('c++')
    require(node and cc and cxx,'Install Node and a Clang/GCC C/C++ toolchain first')
    out.mkdir(parents=True,exist_ok=False)
    report={'format':'rnbo-wave3-computer-qualification-v1','hardware_executed':False,'target_performance_measured':False,'elf_lifecycle_tested':False,'qualification_passed':False,'catalog_sha256':CATALOG_SHA256,'python_version':sys.version,'scope':f"Fixed{len(catalog['fixtures'])}authoredpatcherforms/{sum(len(f['cases'])for f in catalog['fixtures'])}cases; no alias/codebox/explicitoperator-reset qualification",
        'selection':{'onepole_only':onepole_only,'fixtures':[f['id']for f in catalog['fixtures']],'case_programs':sum(len(f['cases'])for f in catalog['fixtures'])},
        'optional_onepole_profile':'stable-onepole-v1'if stable_onepole else None,
        'profile_scope':'Stable profile applies only to the three onepole forms; all other selected objects retain strict preparation',
        'native_support_policy':'Actual production dynamic wrapper and arena, host libc/libm; support.cpp/lifecycle.cpp NOT linked; constructor/finalizer counters are explicit native stubs, not ELF lifecycle proof'}
    try:
        for name in('logs','inputs','plans'):(out/name).mkdir()
        paths=[Path(__file__),CATALOG,NATIVE/'probe.cpp',NATIVE/'inputs.py',ROOT/'archive/importer/export.mjs',ROOT/'archive/importer/patcher.mjs']+[FIXTURES/f['patch']for f in catalog['fixtures']]+[ROOT/n for n in SDK_SOURCES]
        paths+=sorted(p for p in (ROOT/'host/compiler').iterdir()if p.suffix in('.py','.h')and not p.name.startswith('test_'))
        paths=sorted(set(paths));before={str(p.relative_to(ROOT)):sha(p)for p in paths};report['source_files_sha256']=before
        for name in before:
            dest=out/'sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        tool_before={p:sha(p)for p in(node,cc,cxx)};report['tools']={p:{'sha256':tool_before[p],'version':subprocess.check_output([p,'--version'],text=True)}for p in tool_before}
        inputs=load_module('wave3_inputs_'+digest(str(out).encode())[:12],out/'sources'/str((NATIVE/'inputs.py').relative_to(ROOT)))
        oracle=load_module('wave3_oracle_'+digest(str(out).encode())[:12],out/'sources/host/compiler/wave3_oracles.py')
        report['oracle_sha256']=sha(out/'sources/host/compiler/wave3_oracles.py')
        with ThreadPoolExecutor(2)as pool:exports=dict(pool.map(lambda f:export_fixture(f,out,node,rnbo_dir,stable_onepole=stable_onepole),catalog['fixtures']))
        report['exports']=exports;plans,vectors=make_plans(catalog,exports,out,inputs);report['input_vectors_sha256']=vectors
        snapshots={id:verify_prepared(out/'prepared'/id)[2]for id in exports};fixtures={f['id']:f for f in catalog['fixtures']}
        with ThreadPoolExecutor(2)as pool:builds=dict(pool.map(lambda p:compile_and_run(p,fixtures,plans,out,cc,cxx,oracle),[(id,mode)for id in fixtures for mode in('O3','UBSan')]))
        report['builds']=builds;comparisons,reconstruction=compare_results(catalog,builds,out);report.update(comparisons=comparisons,reconstruction=reconstruction)
        require(before=={str(p.relative_to(ROOT)):sha(p)for p in paths},'Source files changed during qualification')
        require(tool_before=={p:sha(p)for p in tool_before},'Compiler/Node binary changed during qualification')
        require(vectors=={p:sha(out/p)for p in vectors},'Input vector changed during qualification')
        require(all(sha(out/p['plan_file'])==p['plan_sha256']for p in plans),'Event vector changed during qualification')
        require(all(sha(out/f['path'])==f['sha256']for b in builds.values()for c in b['cases'].values()for f in c.get('files',{}).values()),'Capture changed after execution')
        require(snapshots=={id:verify_prepared(out/'prepared'/id)[2]for id in snapshots},'Prepared export changed during qualification')
        report['before_after_hashes_verified']=True
        health=all(x['completed']for x in comparisons)and all(not c['stderr']and c.get('protocol',{}).get('passed',False)for b in builds.values()for c in b['cases'].values())
        compatibility=all(x.get('statistics_exact',False)and all(x.get('files_byte_identical',{}).values())for x in comparisons)and all(x['statistics_equal']and all(x['output_bytes_equal'].values())for x in reconstruction)
        accuracy=all(x.get('accuracy_pass',False)for x in comparisons)
        report.update(health_passed=health,compatibility_passed=compatibility,independent_accuracy_passed=accuracy,qualification_passed=health and compatibility and accuracy,status='passed'if health and compatibility and accuracy else'retained_qualification_failures',failed_accuracy_cases=[{'fixture':x['fixture'],'id':x['id']}for x in comparisons if not x.get('accuracy_pass',False)],paired_channel_words=sum(x.get('captured_channel_words',0)for x in comparisons))
        report['protocol_counts']={k:sum(c.get('protocol',{}).get(k,0)for b in builds.values()for c in b['cases'].values())for k in('lifecycle_runs','event_readback_records','block_readback_records')}
    except Exception as exc:
        report.update(status='setup_or_integrity_error',error=type(exc).__name__+': '+str(exc));save(out/'report.json',report);raise QualificationError(f'{exc}; partial report retained at {out/"report.json"}')from exc
    report['artifacts']={str(p.relative_to(out)):{'bytes':p.stat().st_size,'sha256':sha(p)}for p in sorted(out.rglob('*'))if p.is_file()and '__pycache__'not in p.parts and p.name!='report.json'}
    save(out/'report.json',report);return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True,help='Fresh directory below build/; never overwrites an existing run')
    parser.add_argument('--rnbo-dir',type=Path,help='Authorised local RNBO1.4.4 package; otherwise use exporter discovery/RNBO_DIR')
    parser.add_argument('--onepole-only',action='store_true',help='Explicitly select the three onepole graphs/15 original cases; other known failures are outside this selected run')
    parser.add_argument('--stable-onepole',action='store_true',help='Apply the experimental stable profile to selected onepole graphs; other objects stay strict')
    args=parser.parse_args()
    try:report=qualify(args.out,args.rnbo_dir,stable_onepole=args.stable_onepole,onepole_only=args.onepole_only)
    except (QualificationError,OSError,subprocess.SubprocessError)as exc:parser.exit(2,f'Qualification setup rejected: {exc}\n')
    print(json.dumps({'report':str(args.out.resolve()/'report.json'),'status':report['status'],'selection':report['selection'],'optional_onepole_profile':report['optional_onepole_profile'],'health_passed':report['health_passed'],'compatibility_passed':report['compatibility_passed'],'independent_accuracy_passed':report['independent_accuracy_passed'],'failed_accuracy_cases':report['failed_accuracy_cases']}))
    raise SystemExit(0 if report['qualification_passed']else 1)
if __name__=='__main__':main()
