#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original bounded delay, explicit member and interpolation source cases."""
import argparse
import hashlib
import json
from pathlib import Path
import reference as ref
HERE=Path(__file__).resolve().parent

def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()

def program(model):
    owner,method,mode=ref.row(model)
    numeric=model in ref.NUMERIC_ENUM_MODELS
    none='5'if numeric else '"none"'
    code='@state memory = new delay({maxdelay:16});\n'if owner=='delay'else f'@state memory = new {owner}();\n'
    if method in('clear','reset'):
        code+='@state sampleIndex: Int=0;\n'
        code+=f'if(sampleIndex%257==37 || sampleIndex%257==38 || sampleIndex==255 || sampleIndex==256){{memory.{method}();}}\n'
    if owner=='comb':code+='out1=memory.next(in1,0.045351473922902494,.5,.5,.25);\n'
    elif owner=='allpass':code+='out1=memory.next(in1,0.06802721088435375,.5);\n'
    elif method in('next','clear','reset'):code+='out1=memory.next(in1,'+('2.5'if mode=='linear-half'else'2')+');\n'
    elif method=='size':code+='out1=memory.size()+0*in1;\n'
    elif method=='write':code+='memory.write(-in1); memory.write(in1); out1=memory.read(2,'+none+'); memory.step();\n'
    elif method=='step':code+='out1=memory.read(4,'+none+'); memory.write(in1); memory.step(); memory.step();\n'
    else:
        distance='2'if mode=='integer'else'2.5'if mode in('linear','cosine','step','none')else'4.25'
        interp='none'if mode=='integer'else mode
        argument=str(ref.INTERP_ENUM[interp])if numeric else '"'+interp+'"'
        code+=f'out1=memory.read({distance},{argument}); memory.write(in1); memory.step();\n'
    code+='out2=in2;\n'
    if method in('clear','reset'):code+='sampleIndex+=1;\n'
    return code

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
    for model in sorted(ref.MODELS):
        owner,method,mode=ref.row(model);identity=owner+'-'+method+'-'+mode+('-numeric-enum'if model in ref.NUMERIC_ENUM_MODELS else'');code=program(model);patch=identity+'.rnbopat';file=identity+'.rnbo'
        outputs[patch]=encoded(graph(code));outputs[file]=code.encode()
        cases.append(dict(id=identity,exact_name=owner+'.'+method+'()',canonical_name=owner,registry_lookup='codebox-member:'+owner+'.'+method,
          owner=owner,member=method,mode=mode,enum_form='numeric'if model in ref.NUMERIC_ENUM_MODELS else'string'if method in('read','write','step')else'not-applicable',surface='codebox',syntax='stateful-member-call',role='fx',model=model,patch=patch,codebox=file,
          patch_sha256=sha(outputs[patch]),codebox_sha256=sha(code.encode()),maximum_absolute_error=ref.ABSOLUTE_TOLERANCES[model],
          reference_policy='independent-delay-recurrence-and-declared-physical-phase-interpolation',
          reference_sources=[dict(url='https://rnbo.cycling74.com/codebox/ref/'+owner+'#methods')],
          scope='Exact authored member/order/mode on one left resource with right pilot. Delay maxdelay16 samples; comb/allpass retain default storage.20continuouscallbacks, scheduled in-program clear/reset only. No aliases, reset/clear/write/step return values, arbitrary taps, full ring capacity semantics or Gen claim.'))
    outputs['catalog.json']=encoded(dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-codebox-delay-members',surface='codebox',
      sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,
      requested_module_max_arena_bytes=2097152,reference_sha256=sha((HERE/'reference.py').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),
      license='MIT; original sources and independent bounded references',cases=cases))
    return outputs

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,data in artifacts().items():
        target=HERE/name
        if a.check:
            if not target.is_file()or target.read_bytes()!=data:raise SystemExit('Fixture differs: '+name)
        else:target.write_bytes(data)
    print('Checked'if a.check else'Wrote',len(ref.ROWS),'delay member programs')
if __name__=='__main__':main()
