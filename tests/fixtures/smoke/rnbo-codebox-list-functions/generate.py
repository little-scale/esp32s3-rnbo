#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original call sources for documented flat functions and dotted registry names."""
import argparse
import hashlib
import json
from pathlib import Path
import reference as r
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
SCORE='''function score(values:list):number {
    let total = 100*values.length;
    for (let i:Int=0; i<values.length; i++) { total += (i+1)*values[i]; }
    return total;
}
'''

def program(model):
    name,op,syntax=r.row(model)
    prefix=SCORE+'let a:list = [in1,2,3,2,5];\nlet b:list = [in2,2,9];\n'
    if op in('len','median','sum'):body=f'out1={name}(a); out2=in2;'
    elif op in('delace','ecils','filter','slice','sort'):
        args='a'if op=='delace'else'a,b'if op=='filter'else'a,in2'if op in('ecils','slice')else'a,(in2<3 ? -1 : 1)'
        if op=='sort':prefix=SCORE+'let a:list=[in1,10,30,20,50];\n'
        body=f'let result={name}({args}); out1=score(result[0])+0*in1; out2=score(result[1])+0*in2;'
    elif op=='listcompare':body=f'let same:list=[in2,2,3,2,5]; let result={name}(a,same); out1=result[0]+0*in1; out2=score(result[1])+0*in2;'
    elif op=='listswapelements':body=f'{name}(a,0,4); out1=score(a); out2=in2;'
    elif op=='listscramble':
        prefix='let a:list=[in1,10,30,20,50];\n'
        body='''let result=listscramble(a);
let shuffled:list=result[0]; let indices:list=result[1];
let bad=0; let total=0;
for (let i:Int=0; i<shuffled.length && i<indices.length && i<5; i++) {
    let raw=indices[i];
    let inRange=(raw==0 || raw==1 || raw==2 || raw==3 || raw==4);
    let wanted=raw==0 ? in1 : raw==1 ? 10 : raw==2 ? 30 : raw==3 ? 20 : 50;
    bad += (inRange && shuffled[i]==wanted) ? 0 : 1;
    for (let j:Int=0; j<i; j++) { bad += indices[j]==raw ? 1 : 0; }
    total+=shuffled[i];
}
out1=total; out2=((bad==0 && shuffled.length==5 && indices.length==5) ? 1 : 0)+0*in2;'''
    else:
        args='a,b'if op in('join','lace','union','listsect')else'a,[4,0,2,1]'if op=='indexmap'else'a,[0,4]'if op=='swap'else'a,in2'if op=='rot'else'a'
        body=f'let result:list={name}({args}); out1=score(result); out2=in2;'
    return prefix+body+'\n'

def graph(code):
    boxes=[]
    for n,(identity,text)in enumerate((('left','in~ 1'),('right','in~ 2'),('program','codebox~'),('out-left','out~ 1'),('out-right','out~ 2'))):
        b=dict(id=identity,rnbo_uniqueid=identity,maxclass='newobj',text=text,patching_rect=[30+n*170,30,150,24])
        if identity=='program':b['rnbo_extra_attributes']={'code':code}
        boxes.append({'box':b})
    links=[(('left',0),('program',0)),(('right',0),('program',1)),(('program',0),('out-left',0)),(('program',1),('out-right',0))]
    return {'patcher':dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,300],boxes=boxes,lines=[{'patchline':dict(source=list(a),destination=list(b))}for a,b in links])}

def artifacts(package):
    inventory={}
    for row in json.loads((ROOT/'site/data/inventory.json').read_bytes())['rows']:
        if row.get('registry')=='codebox':
            for spelling in [row['name']]+row.get('aliases',[]):inventory[spelling]=dict(row,canonical_name=row['name'])
    outputs={};cases=[]
    for model in sorted(r.MODELS):
        name,op,syntax=r.row(model);entry=inventory[name];flat='list'+op if op in r.OPERATIONS else name
        identity=name.replace('.','-')+'-call';code=program(model);patch=identity+'.rnbopat';file=identity+'.rnbo'
        outputs[patch]=encoded(graph(code));outputs[file]=code.encode()
        upstream=Path('source/operators')/(flat+'.js')
        cases.append(dict(id=identity,exact_name=name,canonical_name=entry.get('canonical_name',name),registry_lookup=flat,
            surface='codebox',syntax='flat-call'if syntax=='flat'else'dotted-member-call',role='fx',model=model,patch=patch,codebox=file,
            patch_sha256=sha(outputs[patch]),codebox_sha256=sha(code.encode()),maximum_absolute_error=0,
            reference_policy='independent-bounded-list-algebra'if op!='listscramble'else'permutation-and-position-map-invariants',
            reference_sources=[dict(local_package_path=upstream.as_posix(),sha256=sha((package/upstream).read_bytes())),dict(url=entry['reference_url'])],
            scope='Exact authored codebox call form, bounded sample-dependent lists with maximum10cells. Two outputs fingerprint documented list values/indices or scalar plus pilot. No event-patcher, method, alias, arbitrary capacity, random-quality or optimisation claim.'))
    outputs['catalog.json']=encoded(dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-codebox-list-functions',surface='codebox',sample_rate=44100,block_frames=256,
        automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,requested_module_max_arena_bytes=4096,
        reference_sha256=sha((HERE/'reference.py').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),license='MIT; original bounded programs and independent references',cases=cases))
    return outputs

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--rnbo-package',type=Path,default=Path.home()/'Documents/Max 9/Packages/RNBO');a=p.parse_args()
    for name,data in artifacts(a.rnbo_package).items():
        p=HERE/name
        if a.check:
            if not p.is_file()or p.read_bytes()!=data:raise SystemExit('Fixture differs: '+name)
        else:p.write_bytes(data)
    print('Checked'if a.check else'Wrote',len(r.MODELS),'list function sources')
if __name__=='__main__':main()
