#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate the exact documented list methods and installed fixed-array names."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import reference as ref
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()

def program(model):
    name=ref.MODEL_NAMES[model]
    if model>=1011:
        return f'''@state memory = new {name}([1, 2, 3, 4, 5]);
@state cursor: Int = 0;
memory[cursor] = in1;
out1 = memory[cursor];
let next: Int = (cursor + 1) % 5;
out2 = memory[next] + 0*in2;
cursor = next;
'''
    operation={
        'push':'let result = a.push(in2); out1 = result; out2 = score(a);',
        'pop':'let result = a.pop(); out1 = result; out2 = score(a);',
        'shift':'let result = a.shift(); out1 = result; out2 = score(a);',
        'concat':'let result: list = a.concat([in1, in2]); out1 = score(result); out2 = score(a);',
        'fill':'let result: list = a.fill(in1); out1 = score(result); out2 = score(a);',
        'unshift':'let result = a.unshift(in2); out1 = result; out2 = score(a);',
        'splice':'let result: list = a.splice(1, 2, in1); out1 = score(result); out2 = score(a);',
        'slice':'let result: list = a.slice(1, 4); out1 = score(result); out2 = score(a);',
        'includes':'out1 = a.includes(in2); out2 = score(a);',
        'indexOf':'out1 = a.indexOf(in2); out2 = score(a);',
        'reverse':'let result: list = a.reverse(); out1 = score(result); out2 = score(a);'}[name]
    operation=re.sub(r'out([12]) = ([^;]+);',lambda m:f'out{m[1]} = ({m[2]}) + 0*in{m[1]};',operation)
    return '''function score(values: list): number {
    let total = 0;
    for (let i: Int = 0; i < values.length; i++) { total += (i + 1) * values[i]; }
    return total;
}
let a: list = [in1, 2, 3, 2, 5];
'''+operation+'\n'

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
    inv=json.loads((ROOT/'site/data/inventory.json').read_bytes())['supplemental_codebox_surface']
    names={row['name']:row for k in ('documented_list_methods','fixed_array_constructors') for row in inv[k]}
    for model,name in ref.MODEL_NAMES.items():
        identity=('list-'+name.lower())if model<1011 else name.lower()+'-stateful'
        code=program(model);patch=identity+'.rnbopat';file=identity+'.rnbo'
        outputs[patch]=encoded(graph(code));outputs[file]=code.encode();entry=names[name]
        cases.append(dict(id=identity,exact_name=('list.'+name+'()' if model<1011 else name),canonical_name=name,registry_lookup=entry['id'],
            surface='codebox',syntax='list-member-call'if model<1011 else'fixed-array-constructor',role='fx',
            model=model,patch=patch,codebox=file,patch_sha256=sha(outputs[patch]),codebox_sha256=sha(code.encode()),
            maximum_absolute_error=0,reference_policy='independent-bounded-list-algebra-or-absolute-sample-age',
            reference_sources=[dict(url=entry['reference_url'])],
            scope='Exact member/constructor on the codebox surface, bounded values and indices. List return/mutation or five-cell persistent array read/write over20continuouscallbacks. No alias, overflow, arbitrary dimensions or growth qualification.'))
    outputs['catalog.json']=encoded(dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-codebox-containers',surface='codebox',
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
    print('Checked'if a.check else'Wrote',len(ref.MODEL_NAMES),'container programs')
if __name__=='__main__':main()
