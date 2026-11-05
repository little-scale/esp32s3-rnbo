#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate exact member scenarios and two fixed18-source hardware partitions."""
import argparse
import hashlib
import json
from pathlib import Path
import reference as ref
HERE=Path(__file__).resolve().parent

def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()

def program(model):
    owner,method=ref.row(model)
    code=f'@state left = new {owner}();\n@state right = new {owner}();\n'
    if method!='next':
        code+='@state sampleIndex: Int = 0;\n'
        code+=f'if(sampleIndex%257==37 || sampleIndex%257==38 || sampleIndex==255 || sampleIndex==256){{left.{method}();}}\n'
        code+=f'if(sampleIndex%263==91 || sampleIndex%263==92 || sampleIndex==511 || sampleIndex==512){{right.{method}();}}\n'
    calls={
      'delta':('in1','in2'),'change':('in1','in2'),'latch':('in1,in2','in2,in1'),
      'sah':('in1,in2,0','in2,in1,.5'),'slide':('in1,2,4','in2,4,2'),
      'dcblock':('in1,.5','in2,.75'),'accum':('in1/1024,0','in2/1024,0'),
      'counter':('in1,0,7','in2,0,5'),'deltaclip':('in1,-.125,.25','in2,-.25,.125'),
      'downsamp':('in1,3','in2,5'),'zerox':('in1','in2'),'zerox_count':('in1,7','in2,5'),
      'onepole':('in1,1000','in2,2000'),'onepole_lin':('in1,.25','in2,.5'),
      'biquad':('in1,.5,.25,.125,-.25,.125','in2,.5,.25,.125,-.25,.125'),
      'elapsed':('','')}
    if owner=='history':code+='out1=left; out2=right; left=in1; right=in2;\n'
    elif owner=='counter':code+='let a=left.next('+calls[owner][0]+'); let b=right.next('+calls[owner][1]+'); out1=a[0]; out2=b[0];\n'
    else:code+='out1=left.next('+calls[owner][0]+')+0*in1; out2=right.next('+calls[owner][1]+')+0*in2;\n'
    if method!='next':code+='sampleIndex+=1;\n'
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
        owner,method=ref.row(model);identity=owner+'-'+method;code=program(model);patch=identity+'.rnbopat';file=identity+'.rnbo'
        outputs[patch]=encoded(graph(code));outputs[file]=code.encode()
        cases.append(dict(id=identity,exact_name=owner+'.'+method+'()',canonical_name=owner,registry_lookup='codebox-member:'+owner+'.'+method,
          owner=owner,member=method,surface='codebox',syntax='stateful-member-call',role='fx',model=model,patch=patch,codebox=file,
          patch_sha256=sha(outputs[patch]),codebox_sha256=sha(code.encode()),maximum_absolute_error=ref.ABSOLUTE_TOLERANCES[model],
          reference_policy='independent-recurrence-and-declared-default-reset-phase',reference_sources=[dict(url='https://rnbo.cycling74.com/codebox/ref/'+owner+'#methods')],
          scope='Exact authored member and finite parameters. Two instances,20continuous256-frame callbacks; reset/clear uses separate per-channel schedules including consecutive and host-boundary calls. No alias, return-value claim for reset/clear, arbitrary options, all counter tuple outputs, resources or Gen qualification.'))
    catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-codebox-members',surface='codebox',sample_rate=44100,block_frames=256,
      automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,requested_module_max_arena_bytes=4096,
      reference_sha256=sha((HERE/'reference.py').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),
      license='MIT; original sources and independent bounded references',cases=cases)
    outputs['catalog.json']=encoded(catalog)
    for index in (1,2):
        part=dict(catalog,cases=cases[(index-1)*18:index*18],partition=dict(index=index,total=2,case_count=18,parent_catalog_sha256=sha(outputs['catalog.json'])))
        outputs['part'+str(index)+'.json']=encoded(part)
    return outputs

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,data in artifacts().items():
        target=HERE/name
        if a.check:
            if not target.is_file()or target.read_bytes()!=data:raise SystemExit('Fixture differs: '+name)
        else:target.write_bytes(data)
    print('Checked'if a.check else'Wrote',len(ref.ROWS),'member programs in two18-source partitions')
if __name__=='__main__':main()
