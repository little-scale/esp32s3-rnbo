#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Armed extended-list fixtures with explicit storage order and bounded observers."""
import argparse
import hashlib
import json
from pathlib import Path
import reference
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
PACKAGE=Path('/Users/a1106632/Documents/Max 9/Packages/RNBO')
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def box(i,text,kind='newobj'):return dict(box=dict(id=i,rnbo_uniqueid=i,maxclass=kind,text=text,patching_rect=[30,30,280,24]))
def line(src,dst,outlet=0,inlet=0):return dict(patchline=dict(source=[src,outlet],destination=[dst,inlet]))
def chain(boxes,lines,src,prefix,texts,dst,inlet=0,outlet=0):
    for i,t in enumerate(texts):
        identity=prefix+str(i);boxes.append(box(identity,t));lines.append(line(src,identity,outlet));src=identity;outlet=0
    lines.append(line(src,dst,outlet,inlet))
def list_observer(boxes,lines,src,outlet,accumulate=False):
    boxes.extend((box('observe-order','t l l'),box('observe-length','list.len'),box('observe-length-scale','* 32768'),
                  box('observe-pad','append 0 0 0 0 0'),box('observe-unpack','unpack 0 0 0 0 0'),box('observe-final','+')))
    lines.extend((line(src,'observe-order',outlet),line('observe-order','observe-length',1),line('observe-length','observe-length-scale'),
                  line('observe-length-scale','observe-final',inlet=1),line('observe-order','observe-pad'),line('observe-pad','observe-unpack')))
    for i in range(4):boxes.append(box('observe-sum'+str(i),'+'))
    for i in range(1,5):
        target='observe-sum'+str(min(i,3))
        chain(boxes,lines,'observe-unpack','observe-weight'+str(i)+'-', ['* '+str(8**i)],target,inlet=1 if i==4 else 0,outlet=i)
    # Rightmost values fill cold sums before unpack emits its leftmost digit.
    lines.extend((line('observe-sum3','observe-sum2',inlet=1),line('observe-sum2','observe-sum1',inlet=1),
                  line('observe-sum1','observe-sum0',inlet=1),line('observe-unpack','observe-sum0'),
                  line('observe-sum0','observe-final')))
    if accumulate:
        boxes.append(box('observe-accumulate','accum'));lines.extend((line('observe-final','observe-accumulate'),line('observe-accumulate','held')))
    else:lines.append(line('observe-final','held'))
def input_list(boxes,lines,dst,tagged=False):
    boxes.append(box('list-order','t f f f'));lines.append(line('armed-input','list-order'))
    chain(boxes,lines,'list-order','crumb-', ['fract','* 8'],dst,inlet=2,outlet=2)
    chain(boxes,lines,'list-order','middle-', ['floor','* -1','+ 7']if tagged else['floor'],dst,inlet=1,outlet=1)
    chain(boxes,lines,'list-order','first-', ['floor']if tagged else['floor','* -1','+ 7'],dst)
def products():
    registry={r['name']:r for r in json.loads((ROOT/'site/data/status.json').read_bytes())['objects']if r['surface']=='patcher'}
    products={};cases=[]
    for model,s in reference.MODEL_SPECS.items():
        identity=s['id'];n=s['exact_name'];v=s['variant'];out=s['observed_outlet'];args=s['fixed_arguments'];kind=s['output_kind'];form=n+(' '+args if args else'')
        boxes=[box('input-unused','in~ 1'),box('pilot','in~ 2'),box('drive','param drive 0 @min -8 @max 8 @exponent 1 @steps 0'),box('arm','param arm 0 @min 0 @max 1 @exponent 1 @steps 0'),box('arm-order','t f f'),box('armed-input','gate 1 0'),box('held','sig~'),box('out-left','out~ 1'),box('out-right','out~ 2'),box('operator',form)]
        lines=[line('drive','armed-input',inlet=1),line('arm','arm-order'),line('arm-order','armed-input'),line('pilot','out-right'),line('held','out-left')]
        if n in('list.group','list.stream'):chain(boxes,lines,'armed-input','stream-digit-', ['fract','* 8'],'operator')
        elif n in('list.compare','list.lookup'):
            boxes.extend((box('make-list','pack 0 0'),box('list-order','t f f')));lines.append(line('armed-input','list-order'))
            chain(boxes,lines,'list-order','pair-right-', ['fract','* 8']+(['% 2']if n=='list.lookup'else[]),'make-list',inlet=1,outlet=1)
            chain(boxes,lines,'list-order','pair-left-', ['floor']+(['% 2']if n=='list.lookup'else[]),'make-list')
            lines.append(line('make-list','operator'))
        else:
            boxes.append(box('make-list','pack 0 0 0'));input_list(boxes,lines,'make-list')
            if n in('list.queue','list.stack')or n=='list.reg'and v=='cold-store-bang':
                boxes.append(box('store-before-pop','t b l'));lines.extend((line('make-list','store-before-pop'),line('store-before-pop','operator',1,1 if n=='list.reg'else 0),line('store-before-pop','operator')))
            else:lines.append(line('make-list','operator'))
        if kind in('list','code-sum'):list_observer(boxes,lines,'operator',out,kind=='code-sum')
        else:lines.append(line('operator','held',out))
        raw=encoded(dict(patcher=dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,600],boxes=boxes,lines=lines)));products[identity+'.rnbopat']=raw
        canonical=registry[n]['canonical_name'];doc='docs/refpages/rnbo/rnbo_'+n+'.maxref.xml';helpfile='help/rnbo_'+n+'.maxhelp'
        refs=[dict(local_package_path=doc,sha256=hashlib.sha256((PACKAGE/doc).read_bytes()).hexdigest(),url=registry[n]['reference_url'])]
        if(PACKAGE/helpfile).exists():refs.append(dict(local_package_path=helpfile,sha256=hashlib.sha256((PACKAGE/helpfile).read_bytes()).hexdigest(),source_kind='installed-primary-help'))
        cases.append(dict(**s,canonical_name=canonical,registry_lookup=canonical,model=model,role='fx',surface='patcher',syntax='armed-extended-list-object',patch=identity+'.rnbopat',patch_sha256=hashlib.sha256(raw).hexdigest(),source_form=form,maximum_absolute_error=0,reference_policy=reference.REFERENCE_POLICIES[model],input_domain=[0.,3.875],right_pilot_bit_exact=True,list_observer='length*32768+sum(item[i]*8**i),0..5 items in0..7'+('; accumulated emission-code sum; not lossless event-order encoding'if kind=='code-sum'else'')if kind in('list','code-sum')else'held scalar',scope='Exact armed finite list/storage form; one arm then21 drive actions with repeated identical lists. Code-sums verify emission sums, not arbitrary event order. Auxiliary objects gain no inherited qualification.',reference_sources=refs))
    catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-list-extended',license='MIT',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,right_observer_bit_exact=True,scope='28 armed scenarios across17 exact spellings; bounded lists, repeated inputs, explicit storage-before-bang and raw right capture.',cases=cases)
    products['catalog.json']=encoded(catalog);parent=hashlib.sha256(products['catalog.json']).hexdigest()
    for part in(1,2):
        subset=cases[(part-1)*14:part*14];products[f'part{part}.json']=encoded(dict(catalog,cases=subset,partition=dict(index=part,total=2,case_count=len(subset),parent_catalog_sha256=parent)))
    return products
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,raw in products().items():
        path=HERE/name
        if a.check:
            if not path.is_file()or path.read_bytes()!=raw:raise SystemExit('Changed generated source: '+name)
        else:path.write_bytes(raw)
