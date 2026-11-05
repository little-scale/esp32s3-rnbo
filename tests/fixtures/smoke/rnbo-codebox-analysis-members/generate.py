#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original member/resource programs with separately authored bounded models."""
import argparse
import hashlib
import json
from pathlib import Path
import reference as r
HERE=Path(__file__).resolve().parent

def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def program(model):
    owner,variant=r.row(model)
    option='{index:1}'if variant=='phase-index'else''
    code=f'@state left = new {owner}({option});\n@state right = new {owner}({option});\n@state ordinal: Int = 0;\n'
    if variant=='reset':
        code+='if(ordinal%257==37 || ordinal%257==38 || ordinal==255 || ordinal==256){left.reset();}\n'
        code+='if(ordinal%263==91 || ordinal%263==92 || ordinal==511 || ordinal==512){right.reset();}\n'
    if owner in r.AVERAGES:
        if variant=='window-change':code+='let wl=[8,5,3][trunc(ordinal/73)%3]; let wr=[16,7,4][trunc(ordinal/91)%3];\n'
        elif variant=='window-change-named-list':code+='let leftWindows=[8,5,3]; let rightWindows=[16,7,4]; let wl=leftWindows[trunc(ordinal/73)%3]; let wr=rightWindows[trunc(ordinal/91)%3];\n'
        else:code+='let wl=8; let wr=16;\n'
        l='ordinal%257==37 || ordinal==255'if variant=='input-reset'else'false'
        v='ordinal%263==91 || ordinal==511'if variant=='input-reset'else'false'
        code+=f'out1=left.next(in1,wl,{l}); out2=right.next(in2,wr,{v});\n'
    elif owner=='cycle':
        if variant=='phase-index':code+='let a=left.next(in1,0); let b=right.next(in2,0); out1=a[0]; out2=b[0];\n'
        else:
            code+='let a=left.next(44100/512,0); let b=right.next(44100/1024,'+('0'if variant=='phase-output'else'.25')+');\n'
            index=1 if variant=='phase-output'else 0
            code+=f'out1=a[{index}]+0*in1; out2=b[{index}]+0*in2;\n'
    else:
        code+='@state previousA=0; @state previousB=0; @state changesA=0; @state changesB=0; @state status=1;\n'
        if variant=='seed':code+='if(ordinal==0 || ordinal%257==19 || ordinal%257==20){left.seed(12345); right.seed(12345);}\n'
        code+='let a=left.next(); let b=right.next(); changesA+=(a!=previousA); changesB+=(b!=previousB);\n'
        code+='if(ordinal%32==31){status=changesA>0 && changesB>0; changesA=0; changesB=0;}\n'
        code+='out1=(a>=-1 && a<=1 && b>=-1 && b<=1)+0*in1; out2='+('status && a==b'if variant=='seed'else'status')+'+0*in2;\npreviousA=a; previousB=b;\n'
    return code+'ordinal+=1;\n'
def graph(code):
    boxes=[]
    for n,(identity,text)in enumerate((('left','in~ 1'),('right','in~ 2'),('code','codebox~'),('out-left','out~ 1'),('out-right','out~ 2'))):
        b=dict(id=identity,rnbo_uniqueid=identity,maxclass='newobj',text=text,patching_rect=[30+n*170,30,150,24])
        if identity=='code':b['rnbo_extra_attributes']={'code':code}
        boxes.append({'box':b})
    links=[(('left',0),('code',0)),(('right',0),('code',1)),(('code',0),('out-left',0)),(('code',1),('out-right',0))]
    return {'patcher':dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,300],boxes=boxes,lines=[{'patchline':dict(source=list(a),destination=list(b))}for a,b in links])}
def artifacts():
    outputs={};cases=[]
    for model in sorted(r.MODELS):
        owner,variant=r.row(model);method=variant if variant in('reset','seed')else'next';identity=owner+'-'+variant;code=program(model);patch=identity+'.rnbopat';file=identity+'.rnbo';outputs[patch]=encoded(graph(code));outputs[file]=code.encode()
        cases.append(dict(id=identity,exact_name=owner+'.'+method+'()',canonical_name=owner,registry_lookup='codebox-member:'+owner+'.'+method,owner=owner,member=method,variant=variant,
            surface='codebox',syntax='stateful-member-call',role='fx',model=model,patch=patch,codebox=file,patch_sha256=sha(outputs[patch]),codebox_sha256=sha(code.encode()),maximum_absolute_error=r.ABSOLUTE_TOLERANCES[model],
            reference_policy='basic-noise-range-variation-and-equal-seed-screen'if owner=='noise'else'independent-window-sums-or-absolute-age-cosine-current-phase',
            reference_sources=[dict(url='https://rnbo.cycling74.com/codebox/ref/'+owner)],
            scope='Two instances; exact authored member/options,20continuous256-frame callbacks, explicit per-channel reset schedules. Available-history moving means and fresh epochs on window changes; current/pre-increment oscillator phase and ideal cosine with2e-6 limit. Noise finite/range/32sample variation screen and same-seed pair equality only, not RNG sequence/distribution/independence proof. No aliases, external buffers, arbitrary modes, host events, reset return values or Gen qualification.'))
    outputs['catalog.json']=encoded(dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-codebox-analysis-members',surface='codebox',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,requested_module_max_arena_bytes=2097152,
        reference_sha256=sha((HERE/'reference.py').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),license='MIT; original sources and independent bounded references',cases=cases))
    return outputs
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,data in artifacts().items():
        target=HERE/name
        if a.check:
            if not target.is_file()or target.read_bytes()!=data:raise SystemExit('Fixture differs: '+name)
        else:target.write_bytes(data)
    print('Checked'if a.check else'Wrote',len(r.ROWS),'analysis-member programs')
