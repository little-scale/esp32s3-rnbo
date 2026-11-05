# SPDX-License-Identifier: MIT
"""Original visual Gen math/alias sources and immutable numerical contracts."""
import argparse,hashlib,json
from pathlib import Path
import reference as r
HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
SYMBOLS={'<':'lt','<=':'lte','>':'gt','>=':'gte','==':'eq','!=':'neq','<p':'ltp','<=p':'ltep','>p':'gtp','>=p':'gtep','==p':'eqp','!=p':'neqp','&&':'and','||':'or','^^':'xor','!':'not'}
def artifacts():
 out={};cases=[]
 for m,s in r.MODEL_SPECS.items():
  name=s['name'];kind=s['kind'];id=('symbol-'+SYMBOLS[name]if name in SYMBOLS else name.lower()+('-upper'if name.isupper()else'-lower')if kind=='constant'else name)
  id='visual-'+id
  nodes=[('a','in 1',0,1),('b','in 2',0,1),('op',name+' 3.5'if kind=='literal'else name,2 if kind=='binary'else 1 if kind=='unary'else 0,1),('l','out 1',1,0),('r','out 2',1,0)]
  inner=dict(patcher=dict(fileversion=1,classnamespace='dsp.gen',boxes=[dict(box=dict(id=i,maxclass='newobj',text=t,numinlets=ni,numoutlets=no,patching_rect=[30+j*80,30,100,24]))for j,(i,t,ni,no)in enumerate(nodes)],lines=[]))
  links=[('op','l',0),('b','r',0)]
  if kind in('binary','unary'):links.append(('a','op',0))
  if kind=='binary':links.append(('b','op',1))
  inner['patcher']['lines']=[dict(patchline=dict(source=[a,0],destination=[b,i]))for a,b,i in links]
  boxes=[]
  for i,t in(('left','in~ 1'),('right','in~ 2'),('gen','gen~'),('out-left','out~ 1'),('out-right','out~ 2')):
   b=dict(id=i,rnbo_uniqueid=i,maxclass='newobj',text=t,patching_rect=[30+len(boxes)*160,30,150,24])
   if i=='gen':b.update(genpatcher=inner,rnbo_extra_attributes=dict(exposeparams=0))
   boxes.append(dict(box=b))
  links=[(('left',0),('gen',0)),(('right',0),('gen',1)),(('gen',0),('out-left',0)),(('gen',1),('out-right',0))]
  raw=encoded(dict(patcher=dict(fileversion=1,classnamespace='rnbo',boxes=boxes,lines=[dict(patchline=dict(source=list(a),destination=list(b)))for a,b in links])))
  out[id+'.rnbopat']=raw
  cases.append(dict(id=id,exact_name='gen~',registry_lookup='gen~',visual_operator=name,visual_kind=kind,canonical_operation=s['operation'],source_form=name+' 3.5'if kind=='literal'else name,surface='patcher',syntax='embedded-visual-gen-maths',role='fx',model=m,patch=id+'.rnbopat',patch_sha256=sha(raw),genpatcher_sha256=sha(encoded(inner)),maximum_absolute_error=r.ABSOLUTE_TOLERANCES[m],input_domains=r.domains(m),reference_policy=r.REFERENCE_POLICIES[m],scope='Exact original visual spelling and finite-domain mathematical screen. Fully connected signal operands, output2 raw pilot; no unknown aliases, cold/default modes, state/resources or one-frame ABI claim.'))
 catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='gen-visual-math',surface='patcher',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,reference_sha256=sha((HERE/'reference.py').read_bytes()),cases=cases)
 out['catalog.json']=encoded(catalog);parent=sha(out['catalog.json']);total=(len(cases)+25)//26
 for i in range(total):
  subset=cases[i*26:(i+1)*26];out['part'+str(i+1)+'.json']=encoded({**catalog,'cases':subset,'partition':dict(index=i+1,total=total,case_count=len(subset),parent_catalog_sha256=parent)})
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 for name,raw in artifacts().items():
  p=HERE/name
  if a.check:
   if not p.is_file()or p.read_bytes()!=raw:raise SystemExit('Changed visual maths fixture: '+name)
  else:p.write_bytes(raw)
 print('Visual mathematical sources:',len(r.MODELS))
