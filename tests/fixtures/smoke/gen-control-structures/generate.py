#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original GenExpr comparison/declaration/structure programs, no DSP adapters."""
import argparse
import hashlib
import json
from pathlib import Path
import reference as r
HERE=Path(__file__).resolve().parent

def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()

def expression(model):
    name=r.MODEL_NAMES[model]
    if model<1112:
        if model%2==0:return f'out1 = {name}(in1, in2);\nout2 = {name}(in2, in1);\n'
        return f'out1 = in1 {name} in2;\nout2 = in2 {name} in1;\n'
    if model in(1112,1113):return f'{name} gain(0.25, min=0, max=1);\nout1 = gain*in1;\nout2 = gain*in2;\n'
    if model in(1114,1115,1116,1117):return f'out1 = {name} + 0*in1;\nout2 = in2;\n'
    if model==1118:return 'out1 = constant(0.375) + 0*in1;\nout2 = constant(-0.625) + 0*in2;\n'
    if model==1119:return 'history left(0.25); history right(-0.5);\nout1 = left; out2 = right;\nleft = in1; right = in2;\n'
    if model==1120:return 'pair(a, b) { return a+2*b, a-2*b; }\nout1, out2 = pair(in1, in2);\n'
    if model==1121:return 'cell(x) { History previous(0.25); old = previous; previous = x; return old; }\nout1 = cell(in1); out2 = cell(in2);\n'
    if model==1122:return 'sum = 0;\nfor (i=0; i<in1; i+=1) { sum += (i+1)*in2; }\nout1 = sum; out2 = in2;\n'
    if model==1123:return 'sum = 0; i = 0;\nwhile (i<in1 && i<5) { sum += i*i*in2; i+=1; }\nout1 = sum; out2 = in2;\n'
    if model==1124:return 'sum = 0;\nfor (i=0; i<5; i+=1) { if (i>=in1) { break; } if (i==2) { continue; } sum += (i+1)*in2; }\nout1 = sum; out2 = in2;\n'
    if model==1125:return 'History tally(0);\nout1 = tally; out2 = in2;\nif (in1>0) { tally = tally+1; } else if (in1<0) { tally = tally-1; }\n'
    raise ValueError('Unknown Gen control program')

def graph(code):
    boxes=[]
    for n,(identity,text)in enumerate((('left','in~ 1'),('right','in~ 2'),('gen','gen~'),('out-left','out~ 1'),('out-right','out~ 2'))):
        box=dict(id=identity,rnbo_uniqueid=identity,maxclass='newobj',text=text,patching_rect=[30+n*170,30,150,24])
        if identity=='gen':box['rnbo_extra_attributes']={'expr':code,'geninlets':2,'genoutlets':2}
        boxes.append({'box':box})
    links=[(('left',0),('gen',0)),(('right',0),('gen',1)),(('gen',0),('out-left',0)),(('gen',1),('out-right',0))]
    return {'patcher':dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,300],boxes=boxes,lines=[{'patchline':dict(source=list(a),destination=list(b))}for a,b in links])}

def artifacts(package):
    primary=Path('server/node_modules/@rnbo/genexpr_js/operators.json');primary_sha=sha((package/primary).read_bytes())
    cases=[];out={}
    for model,name in r.MODEL_NAMES.items():
        if model<1112:
            canonical=r.PAIRS[(model-1100)//2][0];identity=canonical+('-call'if model%2==0 else'-symbolic-infix');syntax='call'if model%2==0 else'infix'
        else:
            canonical=name.lower();identity={1112:'param-lowercase',1113:'param-uppercase',1114:'elapsed-lowercase',1115:'elapsed-uppercase',1116:'voice-lowercase',1117:'voice-uppercase',1118:'constant-call',1119:'history-lowercase'}.get(model,name)
            syntax='language-structure'if model>=1120 else'declaration'if model in(1112,1113,1119)else'call'if model==1118 else'named-value'
        code=expression(model);patch=identity+'.rnbopat';file=identity+'.genexpr';out[patch]=encoded(graph(code));out[file]=code.encode()
        cases.append(dict(id=identity,exact_name=name,canonical_name=canonical,registry_lookup=canonical,surface='genexpr',syntax=syntax,role='fx',model=model,patch=patch,genexpr=file,
            patch_sha256=sha(out[patch]),genexpr_sha256=sha(code.encode()),maximum_absolute_error=0,
            reference_policy='independent-Gen-predicate-polynomial-or-sample-age',
            reference_sources=[dict(local_package_path=primary.as_posix(),sha256=primary_sha),dict(url='https://docs.cycling74.com/userguide/gen/gen_genexpr/')],
            scope='Exact authored GenExpr spelling/form, finite input grid, fixed44100/256, zero automatic warmup and20continuouscallbacks. Declaration defaults only; no external parameter events, voice polyphony, reset, visual Gen, aliases or arbitrary loop-bound qualification.'))
    out['catalog.json']=encoded(dict(format='rnbo-hardware-smoke-catalog-v1',family='gen-control-structures',surface='genexpr',sample_rate=44100,block_frames=256,
        automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,requested_module_max_arena_bytes=4096,
        reference_sha256=sha((HERE/'reference.py').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),license='MIT; original source and independent bounded references',cases=cases))
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--rnbo-package',type=Path,default=Path.home()/'Documents/Max 9/Packages/RNBO');a=p.parse_args()
    for name,data in artifacts(a.rnbo_package).items():
        target=HERE/name
        if a.check:
            if not target.is_file()or target.read_bytes()!=data:raise SystemExit('Fixture differs: '+name)
        else:target.write_bytes(data)
    print('Checked'if a.check else'Wrote',len(r.MODEL_NAMES),'Gen control/structure programs')
if __name__=='__main__':main()
