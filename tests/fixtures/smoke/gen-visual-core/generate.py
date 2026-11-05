# SPDX-License-Identifier: MIT
"""Original embedded dsp.gen graphs, not supplied or cached GenExpr programs."""
import argparse,hashlib,json
from pathlib import Path
import reference as r
HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def graph(identity):
 boxes=[];links=[]
 def node(id,text,ins,outs=1):boxes.append(dict(box=dict(id=id,maxclass='newobj',text=text,numinlets=ins,numoutlets=outs,patching_rect=[30+len(boxes)*35,30,100,24])))
 def wire(a,b,slot=0):links.append(dict(patchline=dict(source=[a,0],destination=[b,slot])))
 node('a','in 1',0);node('b','in 2',0);node('l','out 1',1,0);node('r','out 2',1,0)
 if identity=='identity':wire('a','l');wire('b','r')
 elif identity=='swap':wire('b','l');wire('a','r')
 elif identity in('add','subtract','multiply','divide'):
  op=dict(add='+',subtract='-',multiply='*',divide='/')[identity];node('op',op,2);wire('a','op');wire('b','op',1);wire('op','l');wire('b','r')
 elif identity in('gain-half','offset-quarter','subtract-half','divide-two','negate','absolute'):
  op={'gain-half':'* 0.5','offset-quarter':'+ 0.25','subtract-half':'- 0.5','divide-two':'/ 2','negate':'neg','absolute':'abs'}[identity]
  node('op',op,1);wire('a','op');wire('op','l');wire('b','r')
 elif identity in('one-sample-history','two-sample-history','history-fanout','history-read-twice','unconnected-history'):
  node('h','history hold 0.25',1)
  if identity!='unconnected-history':wire('a','h')
  if identity=='two-sample-history':node('h2','history later 0.5',1);wire('h','h2');wire('h2','l');wire('b','r')
  elif identity in('history-fanout','history-read-twice'):
   node('plus','+',2);node('minus','-',2)
   wire('h','plus');wire('a'if identity=='history-fanout'else'h','plus',1);wire('b','minus');wire('h','minus',1);wire('plus','l');wire('minus','r')
  else:wire('h','l');wire('b','r')
 elif identity=='feedback-half':
  node('h','history hold 0',1);node('gain','* 0.5',1);node('sum','+',2);wire('h','gain');wire('a','sum');wire('gain','sum',1);wire('sum','h');wire('sum','l');wire('b','r')
 elif identity in('two-state-swap','three-state-rotation'):
  texts=['history first 1','history second 2','history third 4']if identity=='three-state-rotation'else['history first 0.25','history second -0.5']
  for i,text in enumerate(texts):node('h'+str(i),text,1)
  for i in range(len(texts)):wire('h'+str((i+1)%len(texts)),'h'+str(i))
  wire('h0','l');wire('h1','r')
 elif identity=='cross-feedback':
  node('h0','history first 0.25',1);node('h1','history second -0.5',1);node('g0','* 0.5',1);node('g1','* 0.25',1);node('s0','+',2);node('s1','+',2)
  wire('h1','g0');wire('h0','g1');wire('a','s0');wire('g0','s0',1);wire('b','s1');wire('g1','s1',1);wire('s0','h0');wire('s1','h1');wire('h0','l');wire('h1','r')
 else:raise ValueError('Missing visual source')
 return dict(patcher=dict(fileversion=1,classnamespace='dsp.gen',boxes=boxes,lines=links))
def artifacts():
 out={};cases=[]
 for m,n in r.MODEL_NAMES.items():
  inner=graph(n);boxes=[]
  for id,text in(('left','in~ 1'),('right','in~ 2'),('gen','gen~'),('out-left','out~ 1'),('out-right','out~ 2')):
   b=dict(id=id,rnbo_uniqueid=id,maxclass='newobj',text=text,patching_rect=[30+len(boxes)*160,30,150,24])
   if id=='gen':b.update(genpatcher=inner,rnbo_extra_attributes=dict(exposeparams=0))
   boxes.append(dict(box=b))
  links=[(('left',0),('gen',0)),(('right',0),('gen',1)),(('gen',0),('out-left',0)),(('gen',1),('out-right',0))]
  patch=dict(patcher=dict(fileversion=1,classnamespace='rnbo',boxes=boxes,lines=[dict(patchline=dict(source=list(a),destination=list(b)))for a,b in links]))
  raw=encoded(patch);out[n+'.rnbopat']=raw
  cases.append(dict(id=n,exact_name='gen~',canonical_name='gen~',registry_lookup='gen~',surface='patcher',syntax='embedded-visual-gen-core',role='fx',model=m,patch=n+'.rnbopat',patch_sha256=sha(raw),genpatcher_sha256=sha(encoded(inner)),maximum_absolute_error=r.ABSOLUTE_TOLERANCES[m],reference_policy='independent-arithmetic-delays-permutations-or-finite-convolution',scope='Original embedded dsp.gen graph through the explicit core lowerer. No authored/cached GenExpr, file resources, codebox, parameters, nested graphs, aliases, arbitrary modes or within-block host events. Twenty full callbacks; history is one-sample state.'))
 out['catalog.json']=encoded(dict(format='rnbo-hardware-smoke-catalog-v1',family='gen-visual-core',surface='patcher',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,reference_sha256=sha((HERE/'reference.py').read_bytes()),cases=cases))
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 for n,b in artifacts().items():
  file=HERE/n
  if a.check:
   if not file.is_file()or file.read_bytes()!=b:raise SystemExit('Changed fixture: '+n)
  else:file.write_bytes(b)
