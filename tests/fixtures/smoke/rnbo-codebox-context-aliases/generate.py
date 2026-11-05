#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original exact alias/context programs; no outcome or precision inheritance."""
import argparse
import hashlib
import json
from pathlib import Path
import reference as r
HERE=Path(__file__).resolve().parent
BARE={'currenttime','samplecount','sampleoffset','samplerate','vectorsize','mc_channel','mc_channelcount'}
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def program(model):
 n=r.name(model)
 if model<1906 or n in('!-','!/','!%','^^'):return f'out1=in1 {n} in2; out2=in2 {n} in1;\n'
 if n=='?':return 'out1=in1 ? in1 : in2; out2=in2 ? in2 : in1;\n'
 if n=='minus':return 'out1=minus(in1,in2); out2=minus(in2,in1);\n'
 if n in('plusequals','mulequals','+=','*='):
  divisor='/64'if n in('plusequals','+=')else''
  return f'@state left=new {n}(); @state right=new {n}();\nout1=left.next(in1{divisor},0); out2=right.next(in2{divisor},0);\n'
 if n.startswith('compound-'):
  add=n=='compound-add-state';initial=0 if add else 1;op='+='if add else'*=';divisor='/64'if add else''
  return f'@state left={initial}; @state right={initial};\nleft{op}in1{divisor}; right{op}in2{divisor}; out1=left; out2=right;\n'
 if n in('mc_channel','mc_channelcount'):return f'let v={n}; out1=(v==v && v>=0 && v<=64 && floor(v)==v)+0*in1; out2=in2;\n'
 if n in BARE:return f'out1={n}+0*in1; out2=in2;\n'
 call=n+'(0)'if n.endswith('atsample')else n+'()'
 if n.startswith('timesignature'):return f'let meter={call}; out1=meter[0]+0*in1; out2=meter[1]+0*in2;\n'
 if n in r.CONVERSIONS:return f'out1={n}(in1); out2={n}(in2);\n'
 return f'out1={call}+0*in1; out2=in2;\n'
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
 ids={1900:'pass-equal-alias',1901:'pass-not-equal-alias',1902:'pass-less-alias',1903:'pass-less-equal-alias',1904:'pass-greater-alias',1905:'pass-greater-equal-alias',1906:'reverse-subtract-alias',1907:'reverse-divide-alias',1908:'reverse-modulus-alias',1909:'xor-alias',1910:'ternary-alias',1914:'add-alias-constructor',1915:'multiply-alias-constructor'}
 for model,n in r.MODEL_NAMES.items():
  identity=ids.get(model,n);code=program(model);file=identity+'.rnbo';patch=identity+'.rnbopat';out[file]=code.encode();out[patch]=encoded(graph(code))
  canonical=dict(r.PASS).get(n,{'!-':'rsub','!/':'rdiv','!%':'rmod','^^':'xor','?':'cond','minus':'sub','plusequals':'accum','+=':'accum','*=':'mulequals','voiceindex':'voice','tickstosamples':'tickstosamps'}.get(n,n))
  syntax='compound-assignment'if n.startswith('compound-')else'constructor-alias'if n in('plusequals','mulequals','+=','*=')else'infix'if model<1911 else'named-value'if n in BARE else'call'
  lookup='language:'+n if n.startswith('compound-')else n
  cases.append(dict(id=identity,exact_name=n,canonical_name=canonical,registry_lookup=lookup,surface='codebox',syntax=syntax,role='fx',model=model,patch=patch,codebox=file,patch_sha256=sha(out[patch]),codebox_sha256=sha(code.encode()),maximum_absolute_error=r.ABSOLUTE_TOLERANCES[model],
    reference_policy='bounded-finite-integer-context-screen'if n in('mc_channel','mc_channelcount')else'independent-alias-math-unit-ratios-or-fresh-context-time',reference_sources=[dict(url='https://rnbo.cycling74.com/codebox/ref/'+canonical)],
    scope='Exact authored codebox spelling/form, bounded finite vector; bare names and calls remain distinct. Fresh stopped120BPM/4-4/480PPQ defaults,44100Hz/256frames; no host transport/MIDI clock or tempo/meter events. Per-sample currenttime/offset and callback-origin samplecount are explicit expectations, not fitted to producer output. Non-MC queries use only a nonnegative integer screen0..64, no exact MC semantics. Prefix/parity forms use two independent state variables/instances. Compound language forms do not qualify registered stateful constructor aliases. No arbitrary domains/options, aliases, patcher or Gen inheritance.'))
 catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='rnbo-codebox-context-aliases',surface='codebox',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,requested_module_max_arena_bytes=4096,
   reference_sha256=sha((HERE/'reference.py').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),license='MIT; original sources and independent finite references',cases=cases)
 out['catalog.json']=encoded(catalog)
 for index,(a,b)in enumerate(((0,26),(26,len(cases))),1):out[f'part{index}.json']=encoded(dict(catalog,cases=cases[a:b],partition=dict(index=index,total=2,case_count=b-a,parent_catalog_sha256=sha(out['catalog.json']))))
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 for name,data in artifacts().items():
  target=HERE/name
  if a.check:
   if not target.is_file()or target.read_bytes()!=data:raise SystemExit('Fixture differs: '+name)
  else:target.write_bytes(data)
 print('Checked'if a.check else'Wrote',len(r.MODELS),'context/alias programs in two partitions')
