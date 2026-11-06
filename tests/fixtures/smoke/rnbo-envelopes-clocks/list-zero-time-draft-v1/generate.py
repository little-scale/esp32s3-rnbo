#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Authored envelope and event-clock graphs with explicit input and outlet modes."""
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
        def message(i,text):
            b=box(i,text);b['box']['maxclass']='message';boxes.append(b)
        def observe_bangs(src,outlet):
            message('one','1');node('count','accum');lines.extend((line(src,'one',outlet),line('one','count')));hold('count')
        if op in('edge','envelope'):
            node('gain','sig~');node('scaled-input','*~');lines.extend((line('armed-input','gain'),line('gain','scaled-input',inlet=1),line('input-left','scaled-input'),line('scaled-input','operator',inlet=3 if op=='envelope'else 0)))
            if op=='edge':observe_bangs('operator',s['observed_outlet'])
            else:
                lines.append(line('operator','out-left'))
                if s['reset_each_drive']:node('reset-bang','t b');node('reset-attribute','set reset');lines.extend((line('armed-input','reset-bang'),line('reset-bang','reset-attribute'),line('reset-attribute','operator')))
        elif op=='curve':
            if v=='compound':
                node('ordered-targets','t f f');node('second-target','* -0.5');node('segments','pack 0. 4. 0.25 0. 8. -0.5');lines.extend((line('armed-input','ordered-targets'),line('ordered-targets','second-target',1),line('second-target','segments',inlet=3),line('ordered-targets','segments'),line('segments','operator')))
            else:node('segment',f"pack 0. {s['duration_ms']} {s['curvature']}");lines.extend((line('armed-input','segment'),line('segment','operator')))
            lines.append(line('operator','out-left'))
        elif op=='onebang':
            node('ordered-bang','t b f');lines.extend((line('armed-input','ordered-bang'),line('ordered-bang','operator')))
            if v=='positive-rearm':
                node('positive','> 0');node('reset-if-positive','sel 1');lines.extend((line('ordered-bang','positive',1),line('positive','reset-if-positive'),line('reset-if-positive','operator',inlet=1)))
            observe_bangs('operator',s['observed_outlet'])
        elif op=='delay':node('bang','t b');lines.extend((line('armed-input','bang'),line('bang','operator')));observe_bangs('operator',0)
        elif op=='line':
            if v=='ramp':node('segment','pack 0. 12. 2.');lines.extend((line('armed-input','segment'),line('segment','operator')))
            else:lines.append(line('armed-input','operator'))
            hold('operator')
        else:lines.append(line('armed-input','operator'));hold('operator')
        raw=encoded(dict(patcher=dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,600],boxes=boxes,lines=lines)));products[identity+'.rnbopat']=raw
        reg=registry[name];canonical=reg['canonical_name'];doc='docs/refpages/rnbo/rnbo_'+name+'.maxref.xml'
        if not(PACKAGE/doc).exists():doc='docs/refpages/rnbo/rnbo_'+canonical+'.maxref.xml'
        refs=[dict(local_package_path=doc,sha256=hashlib.sha256((PACKAGE/doc).read_bytes()).hexdigest(),url=reg['reference_url'])]
        for rel in ['source/operators/'+name.removesuffix('~')+'.js','server/node_modules/@rnbo/xam/objects/'+name.removesuffix('~')+'.js']:
            if(PACKAGE/rel).is_file():refs.append(dict(local_package_path=rel,sha256=hashlib.sha256((PACKAGE/rel).read_bytes()).hexdigest(),source_kind='installed-primary-source'))
        cases.append(dict(**s,canonical_name=canonical,registry_lookup=canonical,model=model,role='fx',surface='patcher',syntax='analysis-timing-object',patch=identity+'.rnbopat',patch_sha256=hashlib.sha256(raw).hexdigest(),source_form=form,maximum_absolute_error=s['limit'],reference_policy=reference.REFERENCE_POLICIES[model],input_domain=[-9.,9.],right_pilot_bit_exact=True,signal_input='binary32(drive * varying left input)'if op in('edge','envelope')else'ordered signed drive events at intended callback boundary',hot_inlet=0,scope='Exact envelope, logical edge, bang gate or event-clock form. One arm and21 drives,20 continuous256-frame callbacks; no automatic warmup. Segment-age envelope/curve references, boundary-origin nearest-sample event-clock screen and one-block-latency edge observer. Other modes/outlets, host-time policy and within-block input events remain separate work.',reference_sources=refs))
    catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-envelopes-clocks',license='MIT',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,right_observer_bit_exact=True,scope='31 envelope and event-clock scenarios. All original sources, fixed mathematical streams, limits and timing-policy gaps are retained; 1MiB module ceiling, actual high-water recorded.',cases=cases)
    products['catalog.json']=encoded(catalog);parent=hashlib.sha256(products['catalog.json']).hexdigest()
    for part in range(1,4):
        subset=cases[(part-1)*11:part*11];products[f'part{part}.json']=encoded(dict(catalog,cases=subset,partition=dict(index=part,total=3,case_count=len(subset),parent_catalog_sha256=parent)))
    return products
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,raw in products().items():
        path=HERE/name
        if a.check:
            if not path.is_file()or path.read_bytes()!=raw:raise SystemExit('Changed generated source: '+name)
        else:path.write_bytes(raw)
