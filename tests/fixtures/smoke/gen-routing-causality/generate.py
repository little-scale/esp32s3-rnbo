#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original closed routing-form probes and causal GenExpr state programs."""
import argparse,hashlib,json
from pathlib import Path
import reference as r
HERE=Path(__file__).resolve().parent
REGISTRY_SHA='ea19a20e4ed03e31d5a41413db9489f3812a9c73c46217eef268fcbc9ffb9a54'
def encoded(v):return(json.dumps(v,indent=2,sort_keys=True)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def program(model):
 n=r.name(model)
 if n=='in-call':return 'out1=in(index=1)+0*in1; out2=in(index=2)+0*in2;\n'
 if n=='out-call':return 'a=out(in1,index=1); b=out(in2,index=2); out1=a; out2=b;\n'
 if n=='gen-call':return 'out1=gen(in1,in2); out2=in2;\n'
 if n=='expr-call':return 'out1=expr(in1,in2,code="in1+in2"); out2=in2;\n'
 if n in('send-call','s-call','receive-call','r-call'):
  sender='s'if n=='s-call'else'send';receiver='r'if n=='r-call'else'receive'
  return f'{sender}(in1,name="localbus"); out1={receiver}(name="localbus"); out2=in2;\n'
 if n=='setparam-symbol':return 'Param gain(.25); setparam(gain,in1); out1=gain; out2=in2;\n'
 if n=='setparam-name':return 'Param gain(.25); setparam(in1,name="gain"); out1=gain; out2=in2;\n'
 if n=='lexical-ports':return 'out1=in1; out2=in2;\n'
 if n=='local-variable-copy':return 'a=in1; b=a; a=in2; out1=b; out2=a;\n'
 if n=='history-chain3':return 'History a(.25),b(-.5),c(.75),d(-.25),e(.5),f(-.75);\nout1=c; out2=f; c=b; b=a; a=in1; f=e; e=d; d=in2;\n'
 if n=='history-fanout':return 'History held(.25); old=held; out1=old+in1; out2=2*old-in2; held=in1/2+in2/4;\n'
 if n=='history-cross-feedback':return 'History left(.25),right(-.5); a=left; b=right; out1=a; out2=b; left=in1+.5*b; right=in2+.25*a;\n'
 if n=='history-read-twice':return 'History held(.25); a=held; out1=a+held; out2=held-in2; held=in1;\n'
 if n=='history-conditional-update':return 'History held(.25); out1=held; out2=in2; if(in2>0){held=in1;}\n'
 if n=='history-conditional-tail':return 'History held(.25); out1=held; if(in2>0){held=in1;} out2=in2;\n'
 if n=='history-conditional-ternary':return 'History held(.25); out1=held; out2=in2; held=(in2>0)?in1:held;\n'
 if n=='history-impulse-age':return 'History age(0); out1=(age%257==255)+0*in1; out2=(age%263==0)+0*in2; age=age+1;\n'
 if n=='history-reset-before-read':return 'History held(.5); if(in2>0){held=0;} out1=held; out2=in2; held=in1;\n'
 if n=='history-rotate-temporaries':return 'History a(1),b(2),c(4); olda=a; oldb=b; oldc=c; out1=olda+0*in1; out2=oldb+0*in2; a=oldb; b=oldc; c=olda;\n'
 if n=='history-rotate-imperative':return 'History a(1),b(2),c(4); a=b; b=c; c=a; out1=a+0*in1; out2=b+0*in2;\n'
 if n=='history-feedback-convolution':return 'History left(0),right(0); a=in1+.25*left; b=in2+.25*right; out1=a; out2=b; left=a; right=b;\n'
 if n=='function-history-independent':return 'filter(x){History held(0); old=held; held=x+.5*old; return old;}\nout1=filter(in1); out2=filter(in2);\n'
 if n=='loop-history-feedback':return 'History held(0); v=held; for(i=0;i<3;i+=1){v=.5*v+.125*in1;} out1=v; out2=in2; held=v;\n'
 raise AssertionError('Missing original program')
def graph(code):
 boxes=[]
 for i,(identity,text)in enumerate((('left','in~ 1'),('right','in~ 2'),('gen','gen~'),('out-left','out~ 1'),('out-right','out~ 2'))):
  b=dict(id=identity,rnbo_uniqueid=identity,maxclass='newobj',text=text,patching_rect=[30+i*170,30,150,24])
  if identity=='gen':b['rnbo_extra_attributes']={'expr':code,'geninlets':2,'genoutlets':2}
  boxes.append({'box':b})
 links=[(('left',0),('gen',0)),(('right',0),('gen',1)),(('gen',0),('out-left',0)),(('gen',1),('out-right',0))]
 return {'patcher':dict(fileversion=1,classnamespace='rnbo',rect=[0,0,1000,300],boxes=boxes,lines=[{'patchline':dict(source=list(a),destination=list(b))}for a,b in links])}
def artifacts():
 out={};cases=[]
 for model,n in r.MODEL_NAMES.items():
  lookup=('setparam'if n.startswith('setparam-')else n.split('-')[0])if model<2210 else'language:'+n;exact=lookup if model<2210 else n;code=program(model);patch=n+'.rnbopat';file=n+'.genexpr';out[patch]=encoded(graph(code));out[file]=code.encode()
  cases.append(dict(id=n,exact_name=exact,canonical_name=exact,registry_lookup=lookup,surface='genexpr',syntax='exploratory-function-call'if model<2210 else'causal-state-program',role='fx',model=model,patch=patch,genexpr=file,patch_sha256=sha(out[patch]),genexpr_sha256=sha(out[file]),maximum_absolute_error=r.ABSOLUTE_TOLERANCES[model],reference_policy='independent-routing-hypothesis-delays-permutations-last-update-or-finite-convolution',reference_sources=[dict(url='https://docs.cycling74.com/userguide/gen/gen_genexpr/'),dict(url='https://docs.cycling74.com/reference/gen_common_history/'),dict(local_package_path='server/node_modules/@rnbo/genexpr_js/operators.json',sha256=REGISTRY_SHA)],scope='Exact original GenExpr program/function spelling only; graph-oriented registry membership does not establish a callable GenExpr API. Routing function forms are exploratory closed routes, not visual/subpatcher qualification. Causal programs use old-state delays/fanout, last conditional update, explicit three-state permutations, bounded impulse convolution or declared imperative/read-after-write hypotheses. Twenty continuous fixed256-frame callbacks, no host/sample-offset events, external resources, visual Gen, aliases, arbitrary programs or one-frame production-call qualification.'))
 catalog=dict(format='rnbo-hardware-smoke-catalog-v1',family='gen-routing-causality',surface='genexpr',sample_rate=44100,block_frames=256,automatic_warmup_blocks=0,manual_warmup_blocks=4,timed_blocks=16,requested_module_max_arena_bytes=4096,reference_sha256=sha((HERE/'reference.py').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),license='MIT; original source and independent bounded references',cases=cases);out['catalog.json']=encoded(catalog)
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 for name,data in artifacts().items():
  target=HERE/name
  if a.check:
   if not target.is_file()or target.read_bytes()!=data:raise SystemExit('Fixture differs: '+name)
  else:target.write_bytes(data)
 print('Checked'if a.check else'Wrote',len(r.NAMES),'Gen routing/causal sources')
