#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate original event graphs and bind published primary-document hashes."""
import argparse
import hashlib
import json
import reference
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
DOCS=Path('/Users/a1106632/Documents/Max 9/Packages/RNBO/docs/refpages/rnbo')
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def products():
    template=json.loads((HERE.parent/'rnbo-events/add-event.rnbopat').read_bytes())
    registry={r['name']:r for r in json.loads((ROOT/'site/data/status.json').read_bytes())['objects']if r['surface']=='patcher'}
    specs=[(name,name.lower()+('-uppercase-event'if name in('DEGTORAD','RADTODEG')else'-lowercase-event'if name in('degtorad','radtodeg')else'-event'),model,'2'if name in('hypot','atan2')else'2.5'if name in('pow','fastpow')else'')for model,name in reference.MODEL_NAMES.items()]
    result={};cases=[]
    for name,identity,model,args in specs:
        patch=json.loads(json.dumps(template))
        operator=next(b['box']for b in patch['patcher']['boxes']if b['box']['id']=='operator')
        operator['text']=name+(' '+args if args else '')
        raw=encoded(patch);result[identity+'.rnbopat']=raw
        canonical=registry[name]['canonical_name'];docname='clip'if canonical=='clamp'else canonical
        relative='docs/refpages/rnbo/rnbo_'+docname+'.maxref.xml';doc=DOCS/Path(relative).name
        cases.append(dict(id=identity,exact_name=name,canonical_name=canonical,registry_lookup=canonical,model=model,
            role='fx',surface='patcher',syntax='numeric-event-object',patch=identity+'.rnbopat',patch_sha256=hashlib.sha256(raw).hexdigest(),
            source_form=operator['text'],fixed_arguments=args,hot_inlet=0,observed_outlet=0,declared_outputs=1,
            maximum_absolute_error=reference.ABSOLUTE_TOLERANCES[model],reference_policy=reference.REFERENCE_POLICIES[model],
            input_domain=reference.domain(name),right_pilot_bit_exact=True,
            scope='Ordered actual-value hot events, fixed arguments, held left output and raw right pilot; only authored domains and spelling.',
            reference_sources=[dict(local_package_path=relative,sha256=hashlib.sha256(doc.read_bytes()).hexdigest(),url=registry[name]['reference_url'])]))
    catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-events-math',license='MIT',sample_rate=44100,
        block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,right_observer_bit_exact=True,
        scope='44 finite-domain event sources,21 ordered actions, fixed cold arguments, mathematical limits and independent right-pilot hash.',cases=cases)
    result['catalog.json']=encoded(catalog)
    parent=hashlib.sha256(result['catalog.json']).hexdigest()
    for part in(1,2):
        subset={**catalog,'cases':cases[(part-1)*22:part*22],'partition':dict(index=part,total=2,case_count=22,parent_catalog_sha256=parent)}
        result['part'+str(part)+'.json']=encoded(subset)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,raw in products().items():
        path=HERE/name
        if a.check:
            if not path.is_file()or path.read_bytes()!=raw:raise SystemExit('Changed generated source: '+name)
        else:path.write_bytes(raw)
