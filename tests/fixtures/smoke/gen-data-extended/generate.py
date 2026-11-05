#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original extended Gen table, sample access and declaration source cases."""
import argparse
import hashlib
import json
from pathlib import Path
import reference as ref
HERE=Path(__file__).resolve().parent
WRITE='index="samples", boundmode="ignore", channelmode="ignore"'
READ='channels=1, index="samples", interp="none", boundmode="ignore", channelmode="ignore"'

def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()

def initialize(zero=False):
    lines=['History initialized(0);','if(initialized==0){']
    for ch in(0,1):
        for i in range(8):lines.append(f'poke(memory,{0 if zero else ref.TABLE[ch][i]},{i},{ch},0,{WRITE});')
    lines+=['initialized=1;','}'];return lines

def expression(model):
    identity=ref.name(model)
    if model in(1605,1606,1630):
        mode='phase'if model==1605 else'freq'
        return f'a,ia=cycle(in1,index="{mode}"); b,ib=cycle(in2,index="{mode}"); out1=a; out2=b;\n'
    if model in(1625,1626):
        lines=['Delay line(16);']
        if model==1625:lines+=['a=read(line,2);','line.write(in1);']
        else:lines+=['a=line.read(2);','write(line,in1);']
        return'\n'.join(lines+['out1=a;out2=in2;'])+'\n'
    if model in(1627,1628):
        declaration='Buffer'if model==1627 else'buffer'
        return f'{declaration} memory("external"); out1=dim(memory)+0*in1; out2=channels(memory)+0*in2;\n'
    if model==1629:return'data memory(8,2); out1=dim(memory)+0*in1; out2=channels(memory)+0*in2;\n'
    lines=['Data memory(8,2);']+initialize(1609<=model<=1612)
    options='channels=1, interp="linear", boundmode="clamp", channelmode="ignore"'
    if model in(1600,1601,1602,1603,1604):
        function='wave'if model<=1602 else'lookup'
        index='phase'if model==1601 else'lookup'if model==1603 else'samples'
        opts=options+(', index="'+index+'"'if model!=1602 else'')
        for ch,inp,var in((0,'in1','a'),(1,'in2','b')):
            args=inp+',1,6,'+str(ch)if model==1602 else inp+','+str(ch)
            lines.append(f'{var},i{var}={function}(memory,{args},{opts});')
        lines+=['out1=a;out2=b;']
    elif model in(1607,1608):
        a='memory,in1'if model==1607 else'in1,name="memory"'
        b='memory,in2'if model==1607 else'in2,name="memory"'
        lines+=[f'a,ia=cycle({a},index="phase");',f'b,ib=cycle({b},index="phase");','out1=a;out2=b;']
    elif 1609<=model<=1612:
        if model in(1609,1612):
            lines+=['coordinate='+('in2'if model==1609 else'8*in2')+';','lo=floor(coordinate);','hi=(lo+1)%8;',f'poke(memory,0,lo,0,0,{WRITE});',f'poke(memory,0,hi,0,0,{WRITE});']
            position='in2';index='samples'if model==1609 else'phase';overdub='0';mode='mix'
        else:lines+=['lo=2;hi=3;'];position='2.25';index='samples';overdub='1'if model==1610 else'.5';mode='accum'if model==1610 else'mix'
        lines +=[f'splat(memory,in1,{position},0,{overdub},index="{index}",boundmode="wrap",channelmode="ignore",overdubmode="{mode}");',
                   f'a,ia=peek(memory,lo,0,{READ});',f'b,ib=peek(memory,hi,0,{READ});','out1=a;out2=b+0*in2;']
    elif 1613<=model<=1617:
        mode=identity.split('-')[-1]
        opts=f'channels=1,index="samples",interp="none",boundmode="{mode}",channelmode="ignore"'
        lines +=[f'a,ia=peek(memory,in1,0,{opts});',f'b,ib=peek(memory,in2,1,{opts});','out1=a;out2=b;']
    elif 1618<=model<=1622:
        mode=identity.split('-')[-1]
        lines +=[f'a,ia=peek(memory,in1,in2,channels=1,index="samples",interp="none",boundmode="ignore",channelmode="{mode}");','out1=a;out2=in2;']
    elif model==1623:lines +=[f'a,ia=peek(memory,in1,0,{READ});','out1=a;out2=ia+0*in2;']
    elif model==1624:lines +=['a,ia=sample(memory,in1,0,channels=1,index="phase",interp="linear",boundmode="wrap",channelmode="ignore");','out1=a;out2=ia+0*in2;']
    else:raise AssertionError('Missing extended Gen source')
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


def artifacts():
    outputs={};cases=[]
    for model,identity in ref.MODEL_NAMES.items():
        exact=('Buffer'if model==1627 else'buffer'if model==1628 else'data'if model==1629 else identity.split('-')[0])
        code=expression(model);patch=identity+'.rnbopat';file=identity+'.genexpr'
        outputs[patch]=encoded(graph(code));outputs[file]=code.encode()
        cases.append(dict(id=identity,exact_name=exact,canonical_name=exact.lower(),registry_lookup=exact.lower(),surface='genexpr',
          syntax='declaration'if model in(1627,1628,1629)else'call',owner_kind='declaration'if model in(1627,1628,1629)else'function-call',role='fx',
          model=model,patch=patch,genexpr=file,patch_sha256=sha(outputs[patch]),genexpr_sha256=sha(code.encode()),
          maximum_absolute_error=ref.ABSOLUTE_TOLERANCES[model],reference_policy='independent-table-interpolation-prefix-sum-and-declared-boundary-phase',
          reference_sources=[dict(url='https://docs.cycling74.com/reference/gen_dsp_'+('delay'if exact in('read','write')else exact.lower())+'/'),
            dict(local_package_path='server/node_modules/@rnbo/genexpr_js/operators.json',sha256='ea19a20e4ed03e31d5a41413db9489f3812a9c73c46217eef268fcbc9ffb9a54')],
          scope='Exact GenExpr source/form, eight-cell local tables initialized explicitly where used, finite indices/channels and20continuousfixed256callbacks. Original Float32 Data storage retained. Empty external Buffer declaration only; no real external resource binding, visual Gen, aliases, arbitrary modes/parameters or optimisation gain.'))
    catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='gen-data-extended',surface='genexpr',sample_rate=44100,block_frames=256,
      automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,requested_module_max_arena_bytes=2097152,
      reference_sha256=sha((HERE/'reference.py').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),
      license='MIT; original sources and independent references',cases=cases,
      producer_storage_view='Original local Data SampleBuffer<SampleValue>, Float32 target cells; no storage conversion',
      storage_policy='Preserve producer data/storage;2MiB test arena ceiling only, not actual measured use')
    outputs['catalog.json']=encoded(catalog)
    for i,partition_cases in ((1,cases[:15]+[cases[30]]),(2,cases[15:30])):
        outputs[f'part{i}.json']=encoded(dict(catalog,cases=partition_cases,partition=dict(index=i,total=2,case_count=len(partition_cases),parent_catalog_sha256=sha(outputs['catalog.json']))))
    return outputs

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
    for name,data in artifacts().items():
        target=HERE/name
        if args.check:
            if not target.is_file()or target.read_bytes()!=data:raise SystemExit('Fixture differs: '+name)
        else:target.write_bytes(data)
    print('Checked'if args.check else'Wrote',len(ref.NAMES),'extended Gen data programs')
if __name__=='__main__':main()
