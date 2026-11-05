#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original event/signal unit graphs; primary local reference hashes retained."""
import argparse
import hashlib
import json
from pathlib import Path
import reference
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
DOCS=Path('/Users/a1106632/Documents/Max 9/Packages/RNBO/docs/refpages/rnbo')
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def line(src,dst,inlet=0):return dict(patchline=dict(source=[src,0],destination=[dst,inlet]))
def products():
    template=json.loads((HERE.parent/'rnbo-events/add-event.rnbopat').read_bytes())
    registry={r['name']:r for r in json.loads((ROOT/'site/data/status.json').read_bytes())['objects']if r['surface']=='patcher'}
    result={};cases=[]
    for model,name in reference.MODEL_NAMES.items():
        signal=name.endswith('~');identity=name.removesuffix('~')+('-signal'if signal else'-event')
        patch=json.loads(json.dumps(template));p=patch['patcher'];boxes={b['box']['id']:b['box']for b in p['boxes']}
        boxes['operator']['text']=name
        if signal:
            boxes['input-unused']['id']='input-left';boxes['input-unused']['rnbo_uniqueid']='input-left'
            p['boxes'].append(dict(box=dict(id='offset',rnbo_uniqueid='offset',maxclass='newobj',text='+~',patching_rect=[30,90,100,24])))
            p['lines']=[line('drive','held'),line('input-left','offset'),line('held','offset',1),line('offset','operator'),line('operator','out-left'),line('pilot','out-right')]
        raw=encoded(patch);result[identity+'.rnbopat']=raw
        canonical=registry[name]['canonical_name'];relative='docs/refpages/rnbo/rnbo_'+canonical+'.maxref.xml'
        cases.append(dict(id=identity,exact_name=name,canonical_name=canonical,registry_lookup=canonical,model=model,
            role='fx',surface='patcher',syntax='signal-unit-object'if signal else'numeric-event-object',patch=identity+'.rnbopat',
            patch_sha256=hashlib.sha256(raw).hexdigest(),source_form=name,fixed_arguments='',hot_inlet=0,observed_outlet=0,declared_outputs=1,
            maximum_absolute_error=reference.ABSOLUTE_TOLERANCES[model],reference_policy=reference.REFERENCE_POLICIES[model],
            input_domain=reference.domain(name),right_pilot_bit_exact=True,
            transport_contract=dict(tempo_bpm=120,ticks_per_quarter=480,running=False,time_signature=[4,4]),
            signal_input='binary32(current drive + varying left input)'if signal else'ordered actual drive events',
            scope='Exact spelling; default fixed transport;21 ordered boundary actions; signal forms also vary within blocks. Zero reciprocal inputs and changed transport excluded.',
            reference_sources=[dict(local_package_path=relative,sha256=hashlib.sha256((DOCS/Path(relative).name).read_bytes()).hexdigest(),url=registry[name]['reference_url'])]))
    catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-unit-conversions',license='MIT',sample_rate=44100,block_frames=256,
        automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,right_observer_bit_exact=True,
        scope='21event and15signal unit spellings; rational references at44100Hz/120BPM/480PPQ, raw independent right capture.',cases=cases)
    result['catalog.json']=encoded(catalog);parent=hashlib.sha256(result['catalog.json']).hexdigest()
    for part in(1,2):
        subset={**catalog,'cases':cases[(part-1)*18:part*18],'partition':dict(index=part,total=2,case_count=18,parent_catalog_sha256=parent)}
        result['part'+str(part)+'.json']=encoded(subset)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,raw in products().items():
        path=HERE/name
        if a.check:
            if not path.is_file()or path.read_bytes()!=raw:raise SystemExit('Changed generated source: '+name)
        else:path.write_bytes(raw)
