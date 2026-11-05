#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original GenExpr basic execution screens and bounded compound assignments."""
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
    if model==1700:return 'History previous(0), changes(0), ordinal(0), status(1);\nn = noise();\ncount = changes + (n != previous);\nflag = status;\nif (ordinal == 31) { flag = count > 0; }\nout1 = (n >= -1) && (n <= 1); out2 = flag + 0*in1 + 0*in2;\nstatus = flag; changes = (ordinal == 31) ? 0 : count;\nprevious = n; ordinal = (ordinal+1) % 32;\n'
    screen=lambda v: f'({v} == {v}) && (abs({v}) <= 1048576) && ({v} >= 0) && ({v} == floor({v}))'
    if model<1709:
        check=f'(v == 0) || (v == 1)'if model in(1707,1708)else screen('v')
        return f'v = {name};\nout1 = ({check}) + 0*in1; out2 = in2;\n'
    if model<1712:
        prefix='size, halfsize, hop, full, offset = fftinfo();\n'
        if model==1709:return prefix+f'out1 = ({screen("size")}) + 0*in1; out2 = ({screen("halfsize")}) + 0*in2;\n'
        if model==1710:return prefix+f'out1 = ({screen("hop")}) + 0*in1; out2 = ((full == 0) || (full == 1)) + 0*in2;\n'
        return prefix+f'out1 = ({screen("offset")}) + 0*in1; out2 = in2;\n'
    if model<1722:return f'a = in1; a {name} in2;\nout1 = a; out2 = in2;\n'
    if model==1722:return 'History total(0);\nout1 = total; out2 = in2;\ntotal += in1/16;\n'
    if model==1723:return 'History polarity(1);\nout1 = polarity; out2 = in2;\npolarity *= in1;\n'
    raise ValueError('Unknown Gen execution program')

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
        identity={1700:'noise-range-variation',1722:'history-add-assign',1723:'history-multiply-assign'}.get(model)
        if identity is None:
            identity=name.lower()+'-'+('upper'if name.isupper()else'lower')if model<1709 else name if model<1712 else ('local-'+('add','multiply','subtract','divide','modulus','bitand','bitor','bitxor','shiftleft','shiftright')[model-1712]+'-assign')
        canonical='noise'if model==1700 else name.lower()if model<1709 else'fftinfo'if model<1712 else'language-compound-assignment'
        syntax='screen'if model<1712 else'compound-assignment'
        code=expression(model);patch=identity+'.rnbopat';file=identity+'.genexpr';out[patch]=encoded(graph(code));out[file]=code.encode()
        cases.append(dict(id=identity,exact_name=name,canonical_name=canonical,registry_lookup=canonical,surface='genexpr',syntax=syntax,role='fx',model=model,patch=patch,genexpr=file,
            patch_sha256=sha(out[patch]),genexpr_sha256=sha(code.encode()),maximum_absolute_error=0,
            reference_policy='declared-basic-execution-screen'if model<1712 else'independent-integer-arithmetic-or-absolute-prefix-parity',
            reference_sources=[dict(local_package_path=primary.as_posix(),sha256=primary_sha),dict(url='https://docs.cycling74.com/userguide/gen/gen_genexpr/')],
            scope=('Basic finite nonnegative integer FFT value screen, engineering bound1048576 (not a documented limit); full-spectrum flag binary. No exact default value, FFT context or transform qualification.'if 1701<=model<1712 else'Noise finite [-1,1] and at least one adjacent change per32samples; no exact sequence, statistics, seed/reset or independent-instance qualification.'if model==1700 else'Exact compound assignment form, bounded finite operands; nonnegative modulus/bitwise operands and shift0..3. History output reads old state, one update per block impulse across20callbacks. No general operator alias/constructor or all-integer-domain qualification.')))
    out['catalog.json']=encoded(dict(format='rnbo-hardware-smoke-catalog-v1',family='gen-execution-forms',surface='genexpr',sample_rate=44100,block_frames=256,
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
    print('Checked'if a.check else'Wrote',len(r.MODEL_NAMES),'Gen execution-form programs')
if __name__=='__main__':main()
