#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate original local Data/indexed GenExpr fixtures, without DSP changes."""
import argparse
import hashlib
import json
from pathlib import Path
import reference

HERE=Path(__file__).resolve().parent
READ_OPTIONS='channels=1, index="samples", interp="none", boundmode="ignore", channelmode="ignore"'
WRITE_OPTIONS='index="samples", boundmode="ignore", channelmode="ignore"'
ROWS=(('data-dimensions','Data','data','declaration'),('dim-local','dim','dim','call'),
      ('channels-local','channels','channels','call'),('peek-ring-read-before-write','peek','peek','call'),
      ('poke-write-readback','poke','poke','call'),('nearest-initialized-samples','nearest','nearest','call'),
      ('sample-initialized-linear','sample','sample','call'),
      ('data-seven-sample-feedback','Data','data','declaration-with-feedback-calls'))


def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()


def initialization(table):
    lines=['History initialized(0);','if (initialized == 0) {']
    for ch in(0,1):
        for index in range(7):
            v=format(table[ch][index],'.12g')
            lines.append(f'    poke(memory, {v}, {index}, {ch}, 0, {WRITE_OPTIONS});')
    lines.extend(('    initialized = 1;','}'))
    return lines


def expression(model):
    lines=['Data memory(7, 2);']
    if model==950:lines+=['out1 = dim(memory) + 0*in1;','out2 = channels(memory) + 0*in2;']
    elif model==951:lines+=['out1 = dim(memory) + 0*in1;','out2 = in2;']
    elif model==952:lines+=['out1 = channels(memory) + 0*in1;','out2 = in2;']
    else:
        table=reference.TABLE if model in(955,956)else((0.,)*7,(0.,)*7)
        lines+=initialization(table)
        if model in(953,954,957):
            lines+=['History cursor(0);','nextIndex = cursor >= 6 ? 0 : cursor + 1;']
            if model in(953,957):
                lines +=[f'oldLeft, indexLeft = peek(memory, cursor, 0, {READ_OPTIONS});',
                         f'oldRight, indexRight = peek(memory, cursor, 1, {READ_OPTIONS});']
            if model==953:
                lines+=['out1 = oldLeft;','out2 = oldRight;',
                        f'poke(memory, in1, cursor, 0, 0, {WRITE_OPTIONS});',
                        f'poke(memory, in2, cursor, 1, 0, {WRITE_OPTIONS});']
            elif model==954:
                lines +=[f'poke(memory, in1, cursor, 0, 0, {WRITE_OPTIONS});',
                         f'poke(memory, in2, cursor, 1, 0, {WRITE_OPTIONS});',
                         f'currentLeft, indexLeft = peek(memory, cursor, 0, {READ_OPTIONS});',
                         f'nextRight, indexRight = peek(memory, nextIndex, 1, {READ_OPTIONS});',
                         'out1 = currentLeft;','out2 = nextRight;']
            else:
                lines+=['nextLeft = in1 + 0.5*oldLeft;','nextRight = in2 + 0.25*oldRight;',
                        'out1 = nextLeft;','out2 = nextRight;',
                        f'poke(memory, nextLeft, cursor, 0, 0, {WRITE_OPTIONS});',
                        f'poke(memory, nextRight, cursor, 1, 0, {WRITE_OPTIONS});']
            lines+=['cursor = nextIndex;']
        else:
            function='nearest'if model==955 else'sample'
            interp='none'if model==955 else'linear'
            options=f'channels=1, index="samples", interp="{interp}", boundmode="clamp", channelmode="ignore"'
            lines +=[f'valueLeft, indexLeft = {function}(memory, in1, 0, {options});',
                     f'valueRight, indexRight = {function}(memory, in2, 1, {options});',
                     'out1 = valueLeft;','out2 = valueRight;']
    return'\n'.join(lines)+'\n'


def graph(code):
    boxes=[]
    for n,(identity,text)in enumerate((('left','in~ 1'),('right','in~ 2'),('gen','gen~'),
                                      ('out-left','out~ 1'),('out-right','out~ 2'))):
        b={'id':identity,'rnbo_uniqueid':identity,'maxclass':'newobj','text':text,
           'patching_rect':[30+n*170,30,150,24]}
        if identity=='gen':b['rnbo_extra_attributes']={'expr':code,'geninlets':2,'genoutlets':2}
        boxes.append({'box':b})
    links=[(('left',0),('gen',0)),(('right',0),('gen',1)),(('gen',0),('out-left',0)),(('gen',1),('out-right',0))]
    return{'patcher':{'fileversion':1,'classnamespace':'rnbo','rect':[0,0,1000,300],
                      'boxes':boxes,'lines':[{'patchline':{'source':list(a),'destination':list(b)}}for a,b in links]}}


def artifacts(package):
    primary=Path('server/node_modules/@rnbo/genexpr_js/operators.json')
    lowering=Path('server/node_modules/@rnbo/genexpr_js/genbo.js')
    outputs={};cases=[]
    for model,(identity,owner,lookup,syntax)in enumerate(ROWS,950):
        code=expression(model);patch=identity+'.rnbopat';genexpr=identity+'.genexpr'
        outputs[patch]=encoded(graph(code));outputs[genexpr]=code.encode()
        inputs=reference.case_input_words(model)
        cases.append({'id':identity,'exact_name':owner,'canonical_name':lookup,'registry_lookup':lookup,
            'surface':'genexpr','owner_kind':'declaration'if owner=='Data'else'function-call',
            'syntax':syntax,'role':'fx','model':model,'patch':patch,'genexpr':genexpr,
            'genexpr_sha256':sha(code.encode()),'patch_sha256':sha(outputs[patch]),
            'maximum_absolute_error':reference.ABSOLUTE_TOLERANCES[model],
            'input_domains':[[min(reference.value(w)for w in inputs[ch::2]),max(reference.value(w)for w in inputs[ch::2])]for ch in(0,1)],
            'reference_policy':'independent-local-array-FIFO-or-convolution',
            'reference_sources':[{'local_package_path':p.as_posix(),'sha256':sha((package/p).read_bytes())}for p in(primary,lowering)],
            'scope':'Exact original GenExpr source and explicit sample-index/channel modes; Data declaration is not a standalone lowercase data(...) call. History/init/poke/peek helpers do not inherit independent owner qualification. Twenty continuous fixed256 callbacks, no external Buffer and no storage conversion.'})
    outputs['catalog.json']=encoded({'format':'rnbo-hardware-smoke-catalog-v1','family':'gen-data-indexed',
        'surface':'genexpr','sample_rate':44100,'block_frames':256,'automatic_warmup_blocks':0,
        'manual_warmup_blocks':4,'timed_blocks':16,'requested_module_max_arena_bytes':4096,
        'reference_sha256':sha((HERE/'reference.py').read_bytes()),'generator_sha256':sha(Path(__file__).read_bytes()),
        'license':'MIT; original source and independent mathematical references','cases':cases,
        'storage_policy':'Preserve original local Data allocation/type; no external Buffer, narrowing profile, or unverified storage-layout assumption.',
        'producer_storage_view':'SampleBuffer<SampleValue>; ordinary Float32 target ABI gives Float32 cells, distinct from generic Gen64-bit prose.',
        'scope':'Eight local Data/indexed-storage scenarios; sample values observed, auxiliary returned read indices unobserved. Parser/prepare failures retained. No Gen visual, standalone alias, full-domain, variable-block ABI or optimisation gain claim.'})
    return outputs


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--rnbo-package',type=Path,default=Path.home()/'Documents/Max 9/Packages/RNBO')
    args=p.parse_args()
    for name,data in artifacts(args.rnbo_package).items():
        file=HERE/name
        if args.check:
            if not file.is_file()or file.read_bytes()!=data:raise SystemExit('Generated source differs: '+name)
        else:file.write_bytes(data)
    print(('Checked'if args.check else'Wrote')+' eight original local Gen Data programs and catalog')


if __name__=='__main__':main()
