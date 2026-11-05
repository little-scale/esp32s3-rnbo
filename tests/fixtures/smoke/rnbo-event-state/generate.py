#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original event-state graphs and fixed primary reference/help provenance."""
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
def products():
    registry={r['name']:r for r in json.loads((ROOT/'site/data/status.json').read_bytes())['objects']if r['surface']=='patcher'}
    result={};cases=[]
    for model,s in reference.MODEL_SPECS.items():
        identity=s['id'];name=s['exact_name'];op=s['operation'];v=s['variant'];outlet=s['outlet'];args=''
        boxes=[box('input-unused','in~ 1'),box('pilot','in~ 2'),box('drive','param drive 0 @min -8 @max 8 @exponent 1 @steps 0'),
               box('held','sig~'),box('out-left','out~ 1'),box('out-right','out~ 2')]
        lines=[line('pilot','out-right'),line('held','out-left')]
        if op in('sum','product')and v=='neutral-reset':
            boxes.extend((box('order','t f f'),box('reset-test','== '+('0'if op=='sum'else'1'))))
            lines.extend((line('drive','order'),line('order','reset-test',1),line('reset-test','operator',inlet=1),line('order','operator')))
        elif op=='latch':
            if v in('open','closed'):args='1'if v=='open'else'0';lines.append(line('drive','operator'))
            else:
                boxes.extend((box('order','t f f'),box('control-test','> 0')))
                lines.extend((line('drive','order'),line('order','control-test',1),line('control-test','operator',inlet=1),line('order','operator')))
        elif op=='counter':
            args='0 -2 2'if v=='negative-up'else('1'if v=='down'else'2'if v=='bounce'else'0')+' 0 3'
            if v=='reset-next':
                boxes.append(box('order','t b f'));lines.extend((line('drive','order'),line('order','operator',1,2),line('order','operator')))
            elif v=='reset-now':lines.append(line('drive','operator',inlet=3))
            else:
                seed='-2'if v=='negative-up'else'0'
                boxes.append(box('seed',seed,'message'))
                lines.extend((line('arm-order','seed',1),line('seed','operator',inlet=2),line('drive','operator')))
        elif op in('peak','trough'):
            boxes.append(box('seed','0','message'))
            lines.extend((line('arm-order','seed',1),line('seed','operator',inlet=1),line('drive','operator')))
        elif op in('slide','rampsmooth'):
            args='2 4'if v=='up2-down4'else'4 8';lines.append(line('drive','operator'))
        elif op=='sah':
            args='0 0.5'if v=='threshold-half'else'0 0'
            boxes.append(box('order','t f f'));lines.extend((line('drive','order'),line('order','operator',1,1),line('order','operator')))
        elif op=='trigger':
            args='f f';boxes.extend((box('twice','* 2'),box('observe-order','-')))
            lines.extend((line('drive','operator'),line('operator','twice',1),line('twice','observe-order',inlet=1),line('operator','observe-order'),line('observe-order','held')))
        else:lines.append(line('drive','operator'))
        source_form=name+(' '+args if args else'');boxes.append(box('operator',source_form))
        if op=='change':
            boxes.append(box('count-observer','accum'));lines.extend((line('operator','count-observer',outlet),line('count-observer','held')))
        elif op!='trigger':lines.append(line('operator','held',outlet))
        # A separate host action explicitly starts the test. Default param0 must
        # never reach the tested state before this action; seed first, then open.
        for edge in lines:
            if edge['patchline']['source']==['drive',0]:edge['patchline']['source']=['armed-input',0]
        boxes.extend((box('arm','param arm 0 @min 0 @max 1 @exponent 1 @steps 0'),
                      box('arm-order','t f f'),box('armed-input','gate 1 0')))
        lines.extend((line('drive','armed-input',inlet=1),line('arm','arm-order'),line('arm-order','armed-input')))
        patch=dict(patcher=dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,600],boxes=boxes,lines=lines))
        raw=encoded(patch);result[identity+'.rnbopat']=raw;canonical=registry[name]['canonical_name'];doc='docs/refpages/rnbo/rnbo_'+canonical+'.maxref.xml';helpfile='help/rnbo_'+canonical+'.maxhelp'
        refs=[dict(local_package_path=doc,sha256=hashlib.sha256((PACKAGE/doc).read_bytes()).hexdigest(),url=registry[name]['reference_url'])]
        if(PACKAGE/helpfile).exists():refs.append(dict(local_package_path=helpfile,sha256=hashlib.sha256((PACKAGE/helpfile).read_bytes()).hexdigest(),source_kind='installed-primary-help'))
        cases.append(dict(id=identity,exact_name=name,canonical_name=canonical,registry_lookup=canonical,model=model,operation=op,variant=v,
            role='fx',surface='patcher',syntax='ordered-event-state-object',patch=identity+'.rnbopat',patch_sha256=hashlib.sha256(raw).hexdigest(),
            source_form=source_form,fixed_arguments=args,observed_outlet=outlet,maximum_absolute_error=reference.ABSOLUTE_TOLERANCES[model],
            reference_policy=reference.REFERENCE_POLICIES[model],input_domain=[-8.,8.],right_pilot_bit_exact=True,
            scope='Exact armed event-state scenario;one arm and21 drive actions, no within-block host offsets, reset modes and outlets only where authored. Change outlets use accum observers; no auxiliary-object qualification inheritance.',reference_sources=refs))
    catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-event-state',license='MIT',sample_rate=44100,block_frames=256,
        automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,right_observer_bit_exact=True,
        scope='36 original event-state scenarios across15 exact spellings; explicit arm then21 ordered drive actions, independent prefix/state references and raw right capture.',cases=cases)
    result['catalog.json']=encoded(catalog);parent=hashlib.sha256(result['catalog.json']).hexdigest()
    for part in(1,2):result[f'part{part}.json']=encoded(dict(catalog,cases=cases[(part-1)*18:part*18],partition=dict(index=part,total=2,case_count=18,parent_catalog_sha256=parent)))
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,raw in products().items():
        path=HERE/name
        if a.check:
            if not path.is_file()or path.read_bytes()!=raw:raise SystemExit('Changed generated source: '+name)
        else:path.write_bytes(raw)
