#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original phase/trajectory/transition member programs and immutable ledger."""
import argparse,hashlib,json
from pathlib import Path
import reference as r
HERE=Path(__file__).resolve().parent
def encoded(v):return(json.dumps(v,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def program(model):
 owner,variant=r.row(model)
 opts=('{edge:1}'if owner=='gatetotrig'and variant=='falling'else'{channels:2,posmode:1,boundmode:1,fademode:0}'if owner=='xfademul'else'')
 leftopts='{phase:0}'if owner=='phasor'else'{ramp:8}'if owner=='swanramp'else opts;rightopts='{phase:0}'if owner=='phasor'else'{ramp:16}'if owner=='swanramp'else opts
 s=f'@state left=new {owner}({leftopts}); @state right=new {owner}({rightopts});\n@state ordinal: Int=0;\n'
 if variant in('reset','set'):
  method='set(.5)'if variant=='set'else'reset()';rm='set(-.5)'if variant=='set'else'reset()'
  s+=f'if(ordinal%257==37 || ordinal%257==38 || ordinal==255 || ordinal==256){{left.{method};}}\nif(ordinal%263==91 || ordinal%263==92 || ordinal==511 || ordinal==512){{right.{rm};}}\n'
 if owner=='phasor':
  sign='-'if variant=='negative'else'';lreset='(ordinal%257==37 || ordinal%257==38 || ordinal==255 || ordinal==256)?0:-1'if variant=='input-reset'else'-1';rr='(ordinal%263==91 || ordinal%263==92 || ordinal==511 || ordinal==512)?0:-1'if variant=='input-reset'else'-1'
  s+=f'out1=left.next({sign}44100/512,{lreset})+0*in1; out2=right.next({sign}44100/1024,{rr})+0*in2;\n'
 elif owner=='train':s+='out1=left.next(512,.25,0)+0*in1; out2=right.next(1024,.5,.25)+0*in2;\n'
 elif owner=='onoff':s+='out1=left.next()+0*in1; out2=right.next()+0*in2;\n'
 elif owner=='gatetotrig':s+='out1=left.next(in1); out2=right.next(in2);\n'
 elif owner=='thresh':s+='out1=left.next(in1,.5,.5); out2=right.next(in2,.5,.5);\n'if variant=='equal'else'out1=left.next(in1,0,.5); out2=right.next(in2,.25,.75);\n'
 elif owner in('mtof','ftom'):s+='out1=left.next(in1,440); out2=right.next(in2,432);\n'
 elif owner=='ease':s+='out1=left.next(in1,0,0); out2=right.next(in2,0,0);\n'
 elif owner=='easexfade':s+='out1=left.next(in1,-1,1,0,0); out2=right.next(in2,2,-2,0,0);\n'
 elif owner=='xfademul':s+='out1=left.next(in1,0); out2=right.next(in2,1);\n'
 elif owner in('rampsmooth','bline'):
  l='ordinal%1021<333?1:(ordinal%1021<701?-.5:.25)';rr='ordinal%1031<347?-1:(ordinal%1031<739?.5:-.25)'
  if owner=='rampsmooth':s+=f'out1=left.next({l},8,8)+0*in1; out2=right.next({rr},16,16)+0*in2;\n'
  else:s+=f'let a=left.next({l},8); let b=right.next({rr},16); out1=a[0]+0*in1; out2=b[0]+0*in2;\n'
 elif owner=='swanramp':s+='out1=left.next(in1,ordinal%73==19); out2=right.next(in2,ordinal%91==31);\n'
 return s+'ordinal+=1;\n'
def graph(code):
 boxes=[]
 for i,(identity,text)in enumerate((('left','in~ 1'),('right','in~ 2'),('code','codebox~'),('out-left','out~ 1'),('out-right','out~ 2'))):
  b=dict(id=identity,rnbo_uniqueid=identity,maxclass='newobj',text=text,patching_rect=[30+i*170,30,150,24])
  if identity=='code':b['rnbo_extra_attributes']={'code':code}
  boxes.append({'box':b})
 links=[(('left',0),('code',0)),(('right',0),('code',1)),(('code',0),('out-left',0)),(('code',1),('out-right',0))]
 return {'patcher':dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,300],boxes=boxes,lines=[{'patchline':dict(source=list(a),destination=list(b))}for a,b in links])}
def artifacts():
 out={};cases=[]
 for model in sorted(r.MODELS):
  owner,variant=r.row(model);method=variant if variant in('reset','set')else'next';identity=owner+'-'+variant;code=program(model);patch=identity+'.rnbopat';file=identity+'.rnbo';out[patch]=encoded(graph(code));out[file]=code.encode();ctor=variant=='constructor'
  cases.append(dict(id=identity,exact_name=owner if ctor else owner+'.'+method+'()',canonical_name=owner,registry_lookup=owner if ctor else'codebox-member:'+owner+'.'+method,owner=owner,member=method,variant=variant,surface='codebox',syntax='constructor-call'if ctor else'stateful-member-call',role='fx',model=model,patch=patch,codebox=file,patch_sha256=sha(out[patch]),codebox_sha256=sha(out[file]),maximum_absolute_error=r.ABSOLUTE_TOLERANCES[model],reference_policy='independent-motion-trajectory-transition-or-octave-contract',reference_sources=[dict(url='https://rnbo.cycling74.com/codebox/ref/'+owner)],scope='Exact two-instance constructor/member/options source only;20 continuous256-frame callbacks with predeclared per-channel reset/set schedules. Current/pre-increment dyadic phase, post-increment8/16-step ramp, zero reset state, last-input difference switch-ramp and documented threshold/edge contracts. Octave-only440/432Hz tuning; bline observes only first tuple output. Constructor scenarios explicitly bind owners; member cases do not imply aliases/other APIs. No Gen/patcher/one-frame-call/event/nonfinite/arbitrary-option qualification.'))
 catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-codebox-motion-members',surface='codebox',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,requested_module_max_arena_bytes=2097152,reference_sha256=sha((HERE/'reference.py').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),license='MIT; original programs and independent bounded contracts',cases=cases);out['catalog.json']=encoded(catalog)
 for index,(a,b)in enumerate(((0,18),(18,len(cases))),1):out[f'part{index}.json']=encoded(dict(catalog,cases=cases[a:b],partition=dict(index=index,total=2,case_count=b-a,parent_catalog_sha256=sha(out['catalog.json']))))
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 for name,data in artifacts().items():
  target=HERE/name
  if a.check:
   if not target.is_file()or target.read_bytes()!=data:raise SystemExit('Fixture differs: '+name)
  else:target.write_bytes(data)
 print('Checked'if a.check else'Wrote',len(r.ROWS),'motion-member sources')
