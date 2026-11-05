# SPDX-License-Identifier: MIT
"""Independent routing hypotheses and absolute-age causal state contracts.

Graph-oriented function forms are exploratory closed routes, not claims that
patcher metadata establishes a public GenExpr function API. Histories use
absolute delays, last-update indices, permutations and finite convolutions.
"""
import struct
NAMES=('in-call','out-call','gen-call','expr-call','send-call','s-call','receive-call','r-call','setparam-symbol','setparam-name',
 'lexical-ports','local-variable-copy','history-chain3','history-fanout','history-cross-feedback','history-read-twice','history-conditional-update','history-impulse-age','history-reset-before-read','history-rotate-temporaries','history-rotate-imperative','history-feedback-convolution','function-history-independent','loop-history-feedback','history-conditional-tail','history-conditional-ternary')
MODEL_NAMES={2200+i:n for i,n in enumerate(NAMES)};MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:2e-6 if n in('history-cross-feedback','history-feedback-convolution','function-history-independent','loop-history-feedback','history-conditional-tail','history-conditional-ternary')else 0 for m,n in MODEL_NAMES.items()}
LEFT=(0.,.25,.25,-.5,-.5,-0.,1.,1.,-1.,-1.,.5,.5,0.,.125,.125,.75)
RIGHT=(0.,1.,1.,-0.,-1.,-1.,.5,.5,0.,.25,-.25,-.25,-1.,1.,1.,1.)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def name(model):
 if type(model)is not int or model not in MODELS:raise ValueError('Unknown Gen routing/causality model')
 return MODEL_NAMES[model]
def input_words(frames=256):return case_input_words(2200,frames)
def case_input_words(model,frames=256):
 name(model)
 if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
 return tuple(word(x)for f in range(frames)for x in(LEFT[f%16],RIGHT[f%16]))
def reference_blocks(model,inputs,call_count=20):
 identity=name(model);inputs=tuple(inputs)
 if inputs!=case_input_words(model):raise ValueError('Gen routing/causal input differs')
 if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Expected1..20calls')
 def x(n,ch):return value(inputs[2*(n%256)+ch])
 def previous(n,ch,initial=0):return initial if n==0 else x(n-1,ch)
 def convolution(n,ch,a,gain=1):return sum(gain*a**k*x(n-k,ch)for k in range(min(n+1,64)))if n>=0 else 0
 def coupled(n,ch):
  # A=[[0,1/2],[1/4,0]], A**2=I/8. State h[n] is
  # A**n*h[0] + sum(A**k * input[n-1-k]); tail <2**-90.
  total=0
  if n<64:total=(.125**(n//2))*((.25 if ch==0 else -.5)if n%2==0 else(-.25 if ch==0 else .0625))
  for k in range(min(n,64)):
   coefficient=.125**(k//2)
   total+=coefficient*(x(n-1-k,ch)if k%2==0 else(.5 if ch==0 else .25)*x(n-1-k,1-ch))
  return total
 result=[]
 for call in range(call_count):
  block=[]
  for f in range(256):
   n=call*256+f;a=x(n,0);b=x(n,1)
   if identity=='expr-call':pair=(a+b,b)
   elif identity in('in-call','out-call','gen-call','send-call','s-call','receive-call','r-call','setparam-symbol','setparam-name','lexical-ports','local-variable-copy'):pair=(a,b)
   elif identity=='history-chain3':pair=((.75,-.5,.25)[n]if n<3 else x(n-3,0),(-.75,.5,-.25)[n]if n<3 else x(n-3,1))
   elif identity=='history-fanout':
    held=.25 if n==0 else x(n-1,0)/2+x(n-1,1)/4;pair=(held+a,2*held-b)
   elif identity=='history-cross-feedback':pair=(coupled(n,0),coupled(n,1))
   elif identity=='history-read-twice':held=previous(n,0,.25);pair=(2*held,held-b)
   elif identity in('history-conditional-update','history-conditional-tail','history-conditional-ternary'):
    recent=next((j for j in range(n-1,max(-1,n-65),-1)if x(j,1)>0),None);pair=(.25 if recent is None else x(recent,0),b)
   elif identity=='history-impulse-age':pair=(int(n%257==255),int(n%263==0))
   elif identity=='history-reset-before-read':pair=(0 if b>0 else previous(n,0,.5),b)
   elif identity=='history-rotate-temporaries':pair=((1,2,4)[n%3],(2,4,1)[n%3])
   elif identity=='history-rotate-imperative':pair=(2,4)if n%2==0 else(4,2)
   elif identity=='history-feedback-convolution':pair=(convolution(n,0,.25),convolution(n,1,.25))
   elif identity=='function-history-independent':pair=(convolution(n-1,0,.5),convolution(n-1,1,.5))
   elif identity=='loop-history-feedback':pair=(convolution(n,0,.125,7/32),b)
   else:raise AssertionError('Missing causal contract')
   block.extend(word(v)for v in pair)
  result.append(tuple(block))
 return tuple(result)
