#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Authored signal-analysis and timing graphs; exact modes remain separate."""
import argparse,hashlib,json
from pathlib import Path
import reference
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
PACKAGE=Path('/Users/a1106632/Documents/Max 9/Packages/RNBO')
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def box(i,text):return dict(box=dict(id=i,rnbo_uniqueid=i,maxclass='newobj',text=text,patching_rect=[30,30,300,24]))
def line(src,dst,outlet=0,inlet=0):return dict(patchline=dict(source=[src,outlet],destination=[dst,inlet]))
def products():
    registry={r['name']:r for r in json.loads((ROOT/'site/data/status.json').read_bytes())['objects']if r['surface']=='patcher'};products={};cases=[]
    for model,s in reference.MODEL_SPECS.items():
        identity=s['id'];name=s['exact_name'];op=s['operation'];v=s['variant'];form=name+(' '+s['fixed_arguments']if s['fixed_arguments']else'')
        boxes=[box('input-left','in~ 1'),box('pilot','in~ 2'),box('drive','param drive 0 @min -8 @max 8 @exponent 1 @steps 0'),box('arm','param arm 0 @min 0 @max 1 @exponent 1 @steps 0'),box('armed-input','gate 1 0'),box('out-left','out~ 1'),box('out-right','out~ 2'),box('operator',form)]
        lines=[line('drive','armed-input',inlet=1),line('arm','armed-input'),line('pilot','out-right')]
        def node(i,text):boxes.append(box(i,text));return i
        def hold(src):node('observed-hold','sig~');lines.extend((line(src,'observed-hold'),line('observed-hold','out-left')))
        if op=='report':
            node('report-before-gain','t f b');node('gain','sig~');node('scaled-input','*~');lines.extend((line('armed-input','report-before-gain'),line('report-before-gain','gain'),line('report-before-gain','operator',1),line('gain','scaled-input',inlet=1),line('input-left','scaled-input'),line('scaled-input','operator')));hold('operator')
        elif op=='threshold'and name.endswith('~'):
            node('gain','sig~');node('shifted-input','+~');lines.extend((line('armed-input','gain'),line('gain','shifted-input',inlet=1),line('input-left','shifted-input'),line('shifted-input','operator'),line('operator','out-left')))
        elif op=='clock'and v.endswith('-signal'):lines.append(line('operator','out-left'))
        elif op=='elapsed':
            lines.append(line('operator','out-left'))
            if v=='reset':node('reset-bang','t b');lines.extend((line('armed-input','reset-bang'),line('reset-bang','operator')))
        elif op=='clock':node('sample-bang','t b');lines.extend((line('armed-input','sample-bang'),line('sample-bang','operator')));hold('operator')
        else:lines.append(line('armed-input','operator'));hold('operator')
        raw=encoded(dict(patcher=dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,600],boxes=boxes,lines=lines)));products[identity+'.rnbopat']=raw
        reg=registry[name];canonical=reg['canonical_name'];doc='docs/refpages/rnbo/rnbo_'+name+'.maxref.xml'
        if not(PACKAGE/doc).exists():doc='docs/refpages/rnbo/rnbo_'+canonical+'.maxref.xml'
        refs=[dict(local_package_path=doc,sha256=hashlib.sha256((PACKAGE/doc).read_bytes()).hexdigest(),url=reg['reference_url'])]
        for rel in ['source/operators/'+name.removesuffix('~')+'.js','server/node_modules/@rnbo/xam/objects/'+name.removesuffix('~')+'.js']:
            if(PACKAGE/rel).is_file():refs.append(dict(local_package_path=rel,sha256=hashlib.sha256((PACKAGE/rel).read_bytes()).hexdigest(),source_kind='installed-primary-source'))
        cases.append(dict(**s,canonical_name=canonical,registry_lookup=canonical,model=model,role='fx',surface='patcher',syntax='analysis-timing-object',patch=identity+'.rnbopat',patch_sha256=hashlib.sha256(raw).hexdigest(),source_form=form,maximum_absolute_error=s['limit'],reference_policy=reference.REFERENCE_POLICIES[model],input_domain=[-9.,9.],right_pilot_bit_exact=True,signal_input='binary32(drive * varying left input)'if op=='report'else'binary32(drive + varying left input)'if op=='threshold'and name.endswith('~')else'ordered drive events or elapsed sample ordinals',hot_inlet=0,scope='Exact manual-report, finite window, threshold or clock form. One arm and21 drives; fresh0-warm state then20 continuous256-frame callbacks. Intended report is visible in next rendered block; manual reports observe all samples since prior bang, snapshot observes prior final sample. Clock origin0, per-sample signal ordinals; reset elapsed starts0 on next sample. Other modes/transport origins and periodic reporting remain separate work.',reference_sources=refs))
    catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-analysis-timing',license='MIT',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,right_observer_bit_exact=True,scope='23 explicit event/signal analysis and sample-clock scenarios; 1MiB module ceiling admits averaging buffers; actual high-water recorded.',cases=cases)
    products['catalog.json']=encoded(catalog);parent=hashlib.sha256(products['catalog.json']).hexdigest()
    for part in range(1,3):
        subset=cases[(part-1)*12:part*12];products[f'part{part}.json']=encoded(dict(catalog,cases=subset,partition=dict(index=part,total=2,case_count=len(subset),parent_catalog_sha256=parent)))
    return products
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,raw in products().items():
        path=HERE/name
        if a.check:
            if not path.is_file()or path.read_bytes()!=raw:raise SystemExit('Changed generated source: '+name)
        else:path.write_bytes(raw)
