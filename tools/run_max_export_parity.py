#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare official Max Minimal exports and the local importer on the same inputs.

Both routes use the same compiler, module wrapper, Float32 switch, arena and
independent original references. Raw outputs are captured outside processing.
This is a native comparison: no ESP32 timing or hardware qualification is inferred.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
PACKAGE=Path('/Users/a1106632/Documents/Max 9/Packages/RNBO')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(v):return(json.dumps(v,indent=2,sort_keys=True)+'\n').encode()
def record(p):return dict(bytes=p.stat().st_size,sha256=sha(p))
def reference(row):
 p=ROOT/row['reference'];assert sha(p)==row['reference_sha256'];s=importlib.util.spec_from_file_location('reference_'+row['id'].replace('-','_'),p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def work(base,row,route):
    source=ROOT/row['source'];assert sha(source)==row['source_sha256'];ref=reference(row);model=row['model'];d=base/'native'/route/row['id'];d.mkdir(parents=True)
    raw=base/'importer-raw'/row['id']if route=='importer'else Path(row['max_export']);prepared=base/'prepared'/route/row['id']
    def command(name,cmd):
        p=d/(name+'.log')
        with p.open('wb')as f:r=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        return r.returncode,p
    if route=='importer':
        rc,log=command('export',['node',str(ROOT/'archive/importer/export.mjs'),str(source),'--out',str(raw)])
        if rc:return dict(id=row['id'],route=route,status='export_failed',returncode=rc,log=record(log))
    else:
        assert (raw/'rnbo_source.h').is_file()and (raw/'description.json').is_file()and (raw/'common/RNBO_Version.h').is_file()
        # Packaging provenance only; generated header/common bytes remain untouched.
        assert not(raw/'source.rnbopat').exists()and not(raw/'RNBO-runtime-LICENSE').exists()
        shutil.copy2(source,raw/'source.rnbopat');shutil.copy2(PACKAGE/'source/rnbo/LICENSE',raw/'RNBO-runtime-LICENSE')
    rc,log=command('prepare',[sys.executable,str(ROOT/'host/compiler/prepare.py'),'--export',str(raw),'--out',str(prepared),'--class-name','rnbos3patch','--role','fx'])
    if rc:return dict(id=row['id'],route=route,status='prepare_failed',returncode=rc,log=record(log),raw_header=record(raw/'rnbo_source.h'))
    manifest=json.loads((prepared/'manifest.json').read_bytes());assert manifest['numerical_profile']=='float32-strict'and manifest['sample_rate']==44100 and manifest['block_frames']==256
    events=ref.parameter_events(model)if hasattr(ref,'parameter_events')else[];assert len(events)in(0,22)
    inputs=ref.case_input_words(model)if hasattr(ref,'case_input_words')else ref.input_words();blocks=ref.reference_blocks(model,inputs);expected=tuple(w for b in blocks for w in b);assert len(inputs)==512 and len(expected)==10240
    (d/'inputs.u32').write_bytes(struct.pack('<512I',*inputs));(d/'expected.u32').write_bytes(struct.pack('<10240I',*expected))
    if events:(d/'events.u32').write_bytes(struct.pack('<66I',*(w for e in events for w in(e['before_call'],0 if e['id']=='drive'else 1,ref.word(e['value'])))))
    harness=ROOT/'tests/native'/('export_parity_event_test.cpp'if events else'export_parity_signal_test.cpp')
    rc,log=command('compile',['c++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing','-I'+str(ROOT/'module-sdk/include'),'-I'+str(prepared),'-I'+str(prepared/'common'),str(harness),str(ROOT/'module-sdk/wrapper/rnbo_s3_static.cpp'),'-o',str(d/'test')])
    tolerance=getattr(ref,'ABSOLUTE_TOLERANCES',{}).get(model,row['maximum_absolute_error']);tolerance=struct.unpack('<f',struct.pack('<f',tolerance))[0]
    out=dict(id=row['id'],route=route,raw_header=record(raw/'rnbo_source.h'),prepared_header=record(prepared/'rnbo_source.h'),prepared_manifest=record(prepared/'manifest.json'),source_sha256=row['source_sha256'],expected_stream_sha256=sha(d/'expected.u32'),input_sha256=sha(d/'inputs.u32'),absolute_tolerance=tolerance,harness=record(harness),arena_capacity=1048576)
    if rc:return dict(out,status='compile_failed',returncode=rc,compile_log=record(log))
    cmd=[str(d/'test'),str(d/'inputs.u32'),str(d/'expected.u32')]+([str(d/'events.u32'),str(tolerance),str(d/'output.u32')]if events else['1048576',str(d/'output.u32')])
    try:r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=30)
    except subprocess.TimeoutExpired:return dict(out,status='native_timeout')
    (d/'run.log').write_bytes(r.stdout+r.stderr)
    out.update(returncode=r.returncode,run_log=record(d/'run.log'),status='native_completed'if r.returncode==0 else'native_fault')
    try:out['diagnostic']=json.loads(r.stdout)
    except (ValueError,TypeError):out['diagnostic']=None
    if(d/'output.u32').exists():
        data=(d/'output.u32').read_bytes();assert len(data)%4==0;words=struct.unpack('<'+str(len(data)//4)+'I',data);outside=within=zeros=0;maximum=0.;nonfinite=0
        for i,(actual,wanted)in enumerate(zip(words,expected)):
            a=struct.unpack('<f',struct.pack('<I',actual))[0];b=struct.unpack('<f',struct.pack('<I',wanted))[0]
            if not math.isfinite(a):nonfinite+=1;continue
            if actual==wanted:continue
            if i%2==0 and((actual|wanted)&0x7fffffff)==0:zeros+=1;continue
            error=abs(float(a)-b);maximum=max(maximum,error)
            if i%2==0 and error<=tolerance:within+=1
            else:outside+=1
        out.update(capture=record(d/'output.u32'),captured_words=len(words),complete_output=len(words)==10240,oracle_outside_words=outside,oracle_within_words=within,observational_left_zero_sign_words=zeros,nonfinite_outputs=nonfinite,max_absolute_error=maximum)
        if out['status']=='native_completed':assert len(words)==10240 and nonfinite==0
    return out

def run(base):
 base=base.resolve();stage=json.loads((base/'stage.json').read_bytes());assert sha(Path(stage['max_wrapper']))==stage['max_wrapper_sha256'];assert stage['rnbo_version']=='1.4.4'
 if(base/'native').exists()or(base/'prepared').exists()or(base/'importer-raw').exists():raise ValueError('Run output already exists; stage a new comparison')
 missing=[r['id']for r in stage['cases']if not(Path(r['max_export'])/'rnbo_source.h').is_file()]
 if missing:raise ValueError('Max exports are not complete: '+', '.join(missing))
 rows=[]
 with ThreadPoolExecutor(max_workers=4)as pool:
    for f in as_completed([pool.submit(work,base,row,route)for row in stage['cases']for route in('importer','max')]):
        v=f.result();rows.append(v);print(json.dumps({k:v.get(k)for k in('id','route','status','captured_words','oracle_outside_words')}),flush=True)
 pairs=[]
 for subject in stage['cases']:
    a=next(r for r in rows if r['id']==subject['id']and r['route']=='importer');b=next(r for r in rows if r['id']==subject['id']and r['route']=='max');pair=dict(id=subject['id'],native_gen=subject['native_gen'],importer_status=a['status'],max_status=b['status'],raw_header_byte_identical=a.get('raw_header')==b.get('raw_header'),cpu_savings_claimed=False,hardware_parity_claimed=False)
    ap=base/'native/importer'/subject['id']/'output.u32';bp=base/'native/max'/subject['id']/'output.u32'
    if ap.is_file()and bp.is_file():
        ad=ap.read_bytes();bd=bp.read_bytes();n=min(len(ad),len(bd))//4;aw=struct.unpack('<'+str(n)+'I',ad[:n*4]);bw=struct.unpack('<'+str(n)+'I',bd[:n*4]);numeric=zero=0;maximum=0.
        for x,y in zip(aw,bw):
            if x==y:continue
            if ((x|y)&0x7fffffff)==0:zero+=1;continue
            numeric+=1;xf=struct.unpack('<f',struct.pack('<I',x))[0];yf=struct.unpack('<f',struct.pack('<I',y))[0];maximum=max(maximum,abs(float(xf)-yf))
        pair.update(compared_words=n,matching_capture_lengths=len(ad)==len(bd),bit_identical=ad==bd,numeric_differences=numeric,zero_sign_differences=zero,maximum_route_difference=maximum,complete_output_pair=a.get('complete_output')is True and b.get('complete_output')is True)
    if a['status']=='native_fault'and b['status']=='native_fault':pair['same_fault_diagnostic']=a['diagnostic']==b['diagnostic']
    pairs.append(pair)
 result=dict(format='rnbo-max-export-parity-native-v1',scope='Eight same-version source graphs, two export routes, the same Float32 wrapper/compiler/arena and independently supplied stimuli. Header and complete or partial capture agreement are separate from oracle correctness. Faults/rejections retained; no target CPU or hardware parity claimed.',stage=record(base/'stage.json'),stage_tool=record(ROOT/'tools/stage_max_export_parity.mjs'),runner=record(Path(__file__)),settings=stage['settings'],max_version=stage['max_version'],rnbo_version=stage['rnbo_version'],routes=rows,pairs=pairs)
 (base/'native-comparison.json').write_bytes(encoded(result));print(json.dumps(dict(pairs=len(pairs),complete_pairs=sum(r.get('complete_output_pair')is True for r in pairs),same_headers=sum(r['raw_header_byte_identical']for r in pairs))))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);a=p.parse_args();run(a.stage)
