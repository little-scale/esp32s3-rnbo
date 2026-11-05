#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original fully wired visual Gen range/state/multiple-outlet graphs."""
import argparse,hashlib,json
from pathlib import Path
import reference as r
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
MAX_GEN=Path('/Applications/Max.app/Contents/Resources/C74/packages/Gen')
RNBO=Path('/Users/a1106632/Documents/Max 9/Packages/RNBO')
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def artifacts():
 result={};cases=[];inventory=json.loads((ROOT/'site/data/gen-inventory.json').read_bytes())
 refs={x['exact_name']:x for x in inventory['max_reference_entries']if x['domain']in('gen-common','gen-dsp')}
 for m,s in r.MODEL_SPECS.items():
  name=s['name'];identity='visual-'+s['id'];nodes=[('a','in 1',0,1),('b','in 2',0,1),('op',name,len(s['bindings']),s['operator_outputs']),('l','out 1',1,0),('r','out 2',1,0)];links=[('op',s['observed_outlet'],'l',0),('b',0,'r',0)]
  for i,b in enumerate(s['bindings']):
   if b in('a','b'):src=b
   elif b=='negative-b':src='minus-b';nodes.append((src,'neg',1,1));links.append(('b',0,src,0))
   else:src='fixed-'+str(i);nodes.append((src,'constant '+str(b),0,1))
   links.append((src,0,'op',i))
  inner=dict(patcher=dict(fileversion=1,classnamespace='dsp.gen',boxes=[dict(box=dict(id=i,maxclass='newobj',text=t,numinlets=ni,numoutlets=no,patching_rect=[30+j*80,30,100,24]))for j,(i,t,ni,no)in enumerate(nodes)],lines=[dict(patchline=dict(source=[a,o],destination=[b,i]))for a,o,b,i in links]))
  boxes=[]
  for i,t in(('left','in~ 1'),('right','in~ 2'),('gen','gen~'),('out-left','out~ 1'),('out-right','out~ 2')):
   b=dict(id=i,rnbo_uniqueid=i,maxclass='newobj',text=t,patching_rect=[30+len(boxes)*160,30,150,24])
   if i=='gen':b.update(genpatcher=inner,rnbo_extra_attributes=dict(exposeparams=0))
   boxes.append(dict(box=b))
  routes=[(('left',0),('gen',0)),(('right',0),('gen',1)),(('gen',0),('out-left',0)),(('gen',1),('out-right',0))]
  raw=encoded(dict(patcher=dict(fileversion=1,classnamespace='rnbo',boxes=boxes,lines=[dict(patchline=dict(source=list(a),destination=list(b)))for a,b in routes])));result[identity+'.rnbopat']=raw
  primary=refs['mod'if name=='%'else name];rel='/'.join(primary['source_path'].split('/')[2:]);path=MAX_GEN/rel;references=[dict(local_package_path=primary['source_path'],sha256=sha(path.read_bytes()),url=primary['reference_url'])]
  registry=RNBO/'server/node_modules/@rnbo/genexpr_js/operators.json';references.append(dict(local_package_path='RNBO/server/node_modules/@rnbo/genexpr_js/operators.json',sha256=sha(registry.read_bytes()),source_kind='installed-primary-registry'))
  cases.append(dict(id=identity,exact_name='gen~',registry_lookup='gen~',visual_operator=name,visual_kind=s['kind'],canonical_operation='mod'if name=='%'else name,source_form=name,variant=s['variant'],observed_outlet=s['observed_outlet'],operator_outputs=s['operator_outputs'],input_bindings=s['bindings'],surface='patcher',syntax='embedded-visual-gen-flow',role='fx',model=m,patch=identity+'.rnbopat',patch_sha256=sha(raw),genpatcher_sha256=sha(encoded(inner)),maximum_absolute_error=r.ABSOLUTE_TOLERANCES[m],input_domains=r.domains(m),reference_policy=r.REFERENCE_POLICIES[m],scope='Exact original fully wired visual spelling, selected outlet and finite-domain/continuous sample-state screen. Twenty uninterrupted256-frame callbacks, zero automatic warmup. Counter retains declared increment-before-output policy; finite fixnan/isnan only. No reset-at-block-boundary, inherited alias/GenExpr qualification or one-frame production ABI claim.',reference_sources=references))
 catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='gen-visual-flow',surface='patcher',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,reference_sha256=sha((HERE/'reference.py').read_bytes()),cases=cases);result['catalog.json']=encoded(catalog);parent=sha(result['catalog.json']);total=(len(cases)+13)//14
 for i in range(total):
  subset=cases[i*14:(i+1)*14];result['part'+str(i+1)+'.json']=encoded(dict(catalog,cases=subset,partition=dict(index=i+1,total=total,case_count=len(subset),parent_catalog_sha256=parent)))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 for name,raw in artifacts().items():
  path=HERE/name
  if a.check:
   if not path.is_file()or path.read_bytes()!=raw:raise SystemExit('Changed visual flow source: '+name)
  else:path.write_bytes(raw)
 print('Visual flow sources:',len(r.MODELS))
