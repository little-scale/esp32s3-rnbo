#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original graphs with independently supplied control points and raw pilot."""
import argparse
import hashlib
import json
from pathlib import Path
import reference
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
PACKAGE=Path('/Users/a1106632/Documents/Max 9/Packages/RNBO')
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def box(i,text):return dict(box=dict(id=i,rnbo_uniqueid=i,maxclass='newobj',text=text,patching_rect=[30,30,300,24]))
def message(i,text):b=box(i,text);b['box']['maxclass']='message';return b
def line(src,dst,outlet=0,inlet=0):return dict(patchline=dict(source=[src,outlet],destination=[dst,inlet]))
def products():
    registry={r['name']:r for r in json.loads((ROOT/'site/data/status.json').read_bytes())['objects']if r['surface']=='patcher'};products={};cases=[]
    for model,s in reference.MODEL_SPECS.items():
        identity=s['id'];name=s['exact_name'];op=s['operation'];v=s['variant'];out=s['observed_outlet'];signal=name.endswith('~');suffix='~'if signal else''
        form=name+(' '+s['fixed_arguments']if s['fixed_arguments']else'')
        boxes=[box('input-left','in~ 1'),box('pilot','in~ 2'),box('drive','param drive 0 @min -8 @max 8 @exponent 1 @steps 0'),box('arm','param arm 0 @min 0 @max 1 @exponent 1 @steps 0'),box('arm-order','t f b'),box('armed-input','gate 1 0'),box('held','sig~'),box('out-left','out~ 1'),box('out-right','out~ 2'),box('operator',form)]
        lines=[line('drive','armed-input',inlet=1),line('arm','arm-order'),line('arm-order','armed-input'),line('pilot','out-right')]
        source='armed-input'
        if signal:
            boxes.extend((box('offset','+~'),box('phase','clip~ 0 1')));lines.extend((line('armed-input','held'),line('held','offset',inlet=1),line('input-left','offset'),line('offset','phase')));source='phase';lines.append(line('operator','out-left',out))
        else:lines.extend((line('operator','held',out),line('held','out-left')))
        def node(i,text,src=None,outlet=0):
            boxes.append(box(i,text))
            if src is not None:lines.append(line(src,i,outlet))
            return i
        def seed(i,value,inlet):
            if signal and op in('pan','xfade'):
                # These amplitude ports require signals; number messages do not drive them.
                boxes.append(box(i,'sig~ '+str(value)));lines.append(line(i,'operator',inlet=inlet))
            else:
                boxes.append(message(i,str(value)));lines.extend((line('arm-order',i,1),line(i,'operator',inlet=inlet)))
        def transform(src,scale,offset,prefix='scaled'):
            a=node(prefix+'-multiply','*'+suffix+' '+str(scale),src);return node(prefix+'-offset','+'+suffix+' '+str(offset),a)
        def hot_constant(control,control_inlet,value):
            if signal:
                lines.append(line(control,'operator',inlet=control_inlet));seed('constant-hot',value,0)
            else:
                node('right-before-hot','t b f',control);lines.append(line('right-before-hot','operator',1,control_inlet));boxes.append(message('constant-hot',str(value)));lines.extend((line('right-before-hot','constant-hot'),line('constant-hot','operator')))
        if op=='interpolation':
            lines.append(line(source,'operator'))
            if v=='spline6-inlets':
                for i,point in enumerate(reference.C6,1):seed('point-'+str(i),point,i)
        elif op=='cartopol':lines.append(line(transform(source,4,-2),'operator'))
        elif op=='poltocar':hot_constant(transform(source,4,-2),1,.75)
        elif op in('pan','xfade'):
            position=transform(source,4,-1)if v=='three-wrap'else source
            hot_constant(position,1 if op=='pan'else(3 if v=='three-wrap'else 2),.75)
            if op=='xfade':
                seed('input-two',-.5,1)
                if v=='three-wrap':seed('input-three',.25,2)
        elif op=='mix':
            if v=='moving-weight':hot_constant(source,2,.75);seed('input-two',-.5,1)
            else:lines.append(line(transform(source,4,-2),'operator'))
        elif op=='phasewrap':lines.append(line(transform(source,16,-8),'operator'))
        elif op=='quantize':lines.append(line(transform(source,4,-2),'operator'))
        elif op=='smoothstep':
            a,b=(.25,.75)if v=='rising'else(.75,.25);seed('edge-two',b,1);hot_constant(source,2,a)
        elif op=='t60':lines.append(line(transform(source,1024,1),'operator'))
        elif op=='t60time':lines.append(line(transform(source,.625,.25),'operator'))
        else:lines.append(line(source,'operator'))
        raw=encoded(dict(patcher=dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,600],boxes=boxes,lines=lines)));products[identity+'.rnbopat']=raw
        reg=registry[name];canonical=reg['canonical_name'];doc='docs/refpages/rnbo/rnbo_'+name+'.maxref.xml'
        if not(PACKAGE/doc).exists():doc='docs/refpages/rnbo/rnbo_'+canonical+'.maxref.xml'
        refs=[dict(local_package_path=doc,sha256=hashlib.sha256((PACKAGE/doc).read_bytes()).hexdigest(),url=reg['reference_url'])]
        extras=['help/rnbo_'+name+'.maxhelp','source/operators/'+op+'.js']
        if name in('interp','interp~'):extras.append('server/node_modules/@rnbo/xam/objects/interp.js')
        if op in('pan','xfade'):extras+=['source/operators/xfademul.js','server/node_modules/@rnbo/xam/objects/'+op+'.js']
        for rel in extras:
            if(PACKAGE/rel).is_file():refs.append(dict(local_package_path=rel,sha256=hashlib.sha256((PACKAGE/rel).read_bytes()).hexdigest(),source_kind='installed-primary-source-or-help'))
        cases.append(dict(**s,canonical_name=canonical,registry_lookup=canonical,model=model,role='fx',surface='patcher',syntax='signal-mixing-shaping-object'if signal else'armed-mixing-shaping-object',patch=identity+'.rnbopat',patch_sha256=hashlib.sha256(raw).hexdigest(),source_form=form,maximum_absolute_error=s['limit'],reference_policy=reference.REFERENCE_POLICIES[model],input_domain=[0.,1.],right_pilot_bit_exact=True,signal_input='clip(binary32(current drive + varying left input),0,1)'if signal else'ordered actual drive events',hot_inlet=0,scope='Exact finite maths/mixing form, selected output and explicit constructor/inlet mode. One arm and21 drives; signal phases vary within blocks. Ideal equations and predetermined limits, independently captured raw right lane. No alias, auxiliary-object or complete-domain inheritance.',reference_sources=refs))
    catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-mixing-shaping',license='MIT',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,right_observer_bit_exact=True,scope='63 event/signal scenarios across22 exact spellings: coordinate outputs, interpolation modes, panning/crossfade curves, shaping and decay math.',cases=cases)
    products['catalog.json']=encoded(catalog);parent=hashlib.sha256(products['catalog.json']).hexdigest()
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
