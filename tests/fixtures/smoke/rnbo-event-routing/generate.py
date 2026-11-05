#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original armed routing/list graphs, with an injective bounded list observer."""
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
def list_observer(boxes,lines,src,outlet):
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
                  line('observe-sum0','observe-final'),line('observe-final','held')))
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
        boxes=[box('input-unused','in~ 1'),box('pilot','in~ 2'),box('drive','param drive 0 @min -8 @max 8 @exponent 1 @steps 0'),
               box('arm','param arm 0 @min 0 @max 1 @exponent 1 @steps 0'),box('arm-order','t f f'),box('armed-input','gate 1 0'),
               box('held','sig~'),box('out-left','out~ 1'),box('out-right','out~ 2')]
        lines=[line('drive','armed-input',inlet=1),line('arm','arm-order'),line('arm-order','armed-input'),line('pilot','out-right'),line('held','out-left')]
        boxes.append(box('operator',args if n=='message'else form,'message'if n=='message'else'newobj'))
        if n=='message':lines.append(line('armed-input','operator'))
        elif n=='pak':
            if v=='cold-only':chain(boxes,lines,'armed-input','pak-cold-', ['fract','* 8'],'operator',inlet=1)
            else:input_list(boxes,lines,'operator')
        elif n=='gate':
            boxes.append(box('routing-order','t f f'));lines.append(line('armed-input','routing-order'))
            chain(boxes,lines,'routing-order','gate-selector-', ['floor'],'operator',outlet=1)
            chain(boxes,lines,'routing-order','gate-data-', ['+ 4'],'operator',inlet=1)
        elif n=='switch':
            boxes.append(box('routing-order','t f f f f'));lines.append(line('armed-input','routing-order'))
            chain(boxes,lines,'routing-order','switch-selector-', ['floor'],'operator',outlet=3)
            for i in range(1,4):chain(boxes,lines,'routing-order','switch-data'+str(i)+'-', ['+ '+str(i+3)],'operator',inlet=i,outlet=3-i)
        elif n=='split':lines.append(line('armed-input','operator'))
        elif n in('select','sel'):chain(boxes,lines,'armed-input','select-tag-', ['floor'],'operator')
        elif n=='swap':
            boxes.append(box('routing-order','t f f'));lines.append(line('armed-input','routing-order'))
            chain(boxes,lines,'routing-order','swap-cold-', ['floor','* -1','+ 7'],'operator',inlet=1,outlet=1)
            chain(boxes,lines,'routing-order','swap-hot-', ['fract','* 8'],'operator')
        else:
            boxes.append(box('make-list','pack 0 0 0'));input_list(boxes,lines,'make-list',n in('route','routepass'));lines.append(line('make-list','operator'))
            if n=='join':
                boxes.append(box('join-right','4 5','message'));lines.extend((line('arm-order','join-right',1),line('join-right','operator',inlet=1)))
        if n=='swap'and v=='order':
            boxes.append(box('swap-observe-order','-'));lines.extend((line('operator','swap-observe-order',1,1),line('operator','swap-observe-order'),line('swap-observe-order','held')))
        elif kind=='list':list_observer(boxes,lines,'operator',out)
        elif kind=='count':
            boxes.extend((box('count-one','1','message'),box('count-observer','accum')))
            lines.extend((line('operator','count-one',out),line('count-one','count-observer'),line('count-observer','held')))
        else:lines.append(line('operator','held',out))
        # Empty results use documented no-match outlets, rather than assuming an
        # empty list is emitted from the data outlet. Code0 means no matches.
        if n=='list.sect':
            boxes.append(box('no-match-zero','0','message'))
            lines.extend((line('operator','no-match-zero',1),line('no-match-zero','held')))
        if n=='list.sub'and out==0:
            boxes.extend((box('no-match-select','sel 0'),box('no-match-zero','0','message')))
            lines.extend((line('operator','no-match-select',1),line('no-match-select','no-match-zero'),line('no-match-zero','held')))
        patch=dict(patcher=dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,600],boxes=boxes,lines=lines));raw=encoded(patch);products[identity+'.rnbopat']=raw
        canonical=registry[n]['canonical_name'];doc='docs/refpages/rnbo/rnbo_'+n+'.maxref.xml'
        if not(PACKAGE/doc).exists():doc='docs/refpages/rnbo/rnbo_'+canonical+'.maxref.xml'
        refs=[dict(local_package_path=doc,sha256=hashlib.sha256((PACKAGE/doc).read_bytes()).hexdigest(),url=registry[n]['reference_url'])]
        helpfile='help/rnbo_'+n+'.maxhelp'
        if(PACKAGE/helpfile).exists():refs.append(dict(local_package_path=helpfile,sha256=hashlib.sha256((PACKAGE/helpfile).read_bytes()).hexdigest(),source_kind='installed-primary-help'))
        cases.append(dict(**s,canonical_name=canonical,registry_lookup=canonical,model=model,role='fx',surface='patcher',
            syntax='message-box'if n=='message'else'armed-list-and-routing-object',patch=identity+'.rnbopat',patch_sha256=hashlib.sha256(raw).hexdigest(),source_form=args if n=='message'else form,
            maximum_absolute_error=0,reference_policy=reference.REFERENCE_POLICIES[model],input_domain=[0.,3.875],right_pilot_bit_exact=True,
            list_observer=('length*32768+sum(item[i]*8**i),0..5 items in0..7'+('; no-match code0 from outlet1'if n in('list.sect','list.sub')and out==0 else''))if kind=='list'else'held scalar or emitted-event count',
            scope='Exact armed finite numeric-list/routing form;one arm then21 drive actions. Lists use an injective bounded order/length observer; auxiliary objects gain no inherited qualification.',reference_sources=refs))
    catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-event-routing',license='MIT',sample_rate=44100,block_frames=256,
        automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,right_observer_bit_exact=True,
        scope='62 armed scenarios across30 exact spellings;independent finite routing/list contracts and lossless bounded list observer, raw right capture.',cases=cases)
    products['catalog.json']=encoded(catalog);parent=hashlib.sha256(products['catalog.json']).hexdigest()
    # The already-executed original fault probe is immutable. Its source graph
    # is unchanged by the two no-match observation fixes.
    products['part0.json']=(HERE/'unobserved-no-match-v1/part0.json').read_bytes()
    for part in range(1,5):
        subset=cases[(part-1)*16:part*16];products[f'part{part}.json']=encoded(dict(catalog,cases=subset,partition=dict(index=part,total=4,case_count=len(subset),parent_catalog_sha256=parent)))
    return products
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,raw in products().items():
        path=HERE/name
        if a.check:
            if not path.is_file()or path.read_bytes()!=raw:raise SystemExit('Changed generated source: '+name)
        else:path.write_bytes(raw)
