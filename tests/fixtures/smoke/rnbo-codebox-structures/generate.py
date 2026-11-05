#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original bounded codebox language and lifecycle programs."""
import argparse
import hashlib
import json
from pathlib import Path
import reference as ref
HERE=Path(__file__).resolve().parent

def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
PROGRAMS=(
 'var a = in1; let b = in2; const k = 2; a += k*b; out1 = a; out2 = in1-k*b;',
 'let a: number = in1; let b: number = in2; let k: Int = 2; out1 = a+k*b; out2 = a-k*b;',
 'let a = in1; let b = in2; { let a = 3*in2; b = in1+a; } out1 = b; out2 = a;',
 'out1 = in1+in2*2; out2 = (in1+in2)*2;',
 'if(in1>0){out1=in1+2*in2;}else if(in1<0){out1=in1-2*in2;}else{out1=in2;} out2=in2;',
 '@state a=0; @state b=0; out1=in1>0 ? (a+=1) : (b+=1); out2=a+b+0*in2;',
 '@state a=0; out1=(in1>0 && (a+=1)>0); out2=a+0*in2;',
 '@state a=0; out1=(in1>0 || (a+=1)>0); out2=a+0*in2;',
 'let a=in2; switch(in1){case 0:a+=10;break;case 1:a+=20;break;case 2:a+=30;break;default:a+=40;} out1=a; out2=in2;',
 'let a=in2; switch(in1){case 0:a+=1;case 1:a+=2;case 2:a+=3;break;default:a+=8;} out1=a; out2=in2;',
 'let a=0*in1; for(let i: Int=0;i<in1;i++){a+=(i+1)*in2;} out1=a; out2=in2;',
 'let a=0*in1; for(let i: Int=0;i<in1;i++){for(let j: Int=0;j<2;j++){a+=(i+1)*(j+1)*in2;}} out1=a; out2=in2;',
 'let a=0*in1; for(let i: Int=0;i<in1;i++){if(i==2){continue;} if(i==4){break;} a+=(i+1)*in2;} out1=a; out2=in2;',
 'let a=0*in1; let i: Int=0; while(i<in1){a+=i*i*in2;i++;} out1=a; out2=in2;',
 'let a=0*in1; let i: Int=0; do{a+=(i+1)*in2;i++;}while(i<in1); out1=a; out2=in2;',
 'function combine(a:number,b:number):number{return a+2*b;} out1=combine(in1,in2); out2=combine(in1,-in2);',
 'function combine(a:number,b:number):list{return [a+b,a-b];} let a:list=combine(in1,in2); out1=a[0]; out2=a[1];',
 '@state a=.25; @state b=-.5; out1=a; out2=b; a=in1; b=in2;',
 '@state a=.25; @state b=-.5; out1=a; out2=b; if(in1>0){a+=1;}else{b+=1;} let unused=in2;',
 '@param({min:0,max:1}) gain=.25; out1=gain*in1; out2=gain*in2;',
 '@state count=0; function init(){count+=1;} out1=count+in1; out2=in2;',
 '@state count=0; function startup(){count+=1;} out1=count+in1; out2=in2;',
 '@state count=0; function dspsetup(){count+=1;} out1=count+in1; out2=in2;',
 '@state a=0; @state b=0; @state c=0; @state seen=0; function init(){a+=1;} function startup(){b+=1;seen=a;} function dspsetup(){c+=1;} out1=100*a+10*b+c+in1; out2=seen+in2;',
)

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
    for model,name in ref.MODEL_NAMES.items():
        code=PROGRAMS[model-1300]+'\n';patch=name+'.rnbopat';file=name+'.rnbo'
        outputs[patch]=encoded(graph(code));outputs[file]=code.encode()
        cases.append(dict(id=name,exact_name=(name[5:]+'()' if name in('hook-init','hook-startup','hook-dspsetup')else name),canonical_name=name,registry_lookup=('codebox-hook:'+name[5:] if name in('hook-init','hook-startup','hook-dspsetup')else 'structure:'+name),
            surface='codebox',syntax='lifecycle-hook'if name.startswith('hook-')else'language-structure',role='fx',
            model=model,patch=patch,codebox=file,patch_sha256=sha(outputs[patch]),codebox_sha256=sha(code.encode()),
            maximum_absolute_error=0,reference_policy='independent-polynomial-prefix-count-or-fresh-lifecycle-contract',
            reference_sources=[dict(url='https://rnbo.cycling74.com/codebox')],
            scope='Exact authored bounded RNBO codebox language form; fresh initialize/prepare followed by20continuouscallbacks at44100/256. No arbitrary programs, external parameter changes, later preparation, resets, event codebox or Gen equivalence.'))
    outputs['catalog.json']=encoded(dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-codebox-structures',surface='codebox',
        sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,
        requested_module_max_arena_bytes=4096,reference_sha256=sha((HERE/'reference.py').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),
        license='MIT; original sources and independent bounded references',cases=cases))
    return outputs

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,data in artifacts().items():
        target=HERE/name
        if a.check:
            if not target.is_file()or target.read_bytes()!=data:raise SystemExit('Fixture differs: '+name)
        else:target.write_bytes(data)
    print('Checked'if a.check else'Wrote',len(ref.MODEL_NAMES),'codebox structure programs')
if __name__=='__main__':main()
