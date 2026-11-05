# SPDX-License-Identifier: MIT
"""Independent dyadic arithmetic/delay/permutation/finite-convolution references.

No graph traversal or lowered expressions are evaluated here. History reference
is previous-sample signal state; coupled feedback uses powers of a 2x2 matrix
with A**2=I/8. Only the declared callback stream and finite domains are checked.
"""
import struct
NAMES=('identity','swap','add','subtract','multiply','divide','gain-half','offset-quarter','subtract-half','divide-two','negate','absolute',
       'one-sample-history','two-sample-history','two-state-swap','history-fanout','feedback-half','cross-feedback','history-read-twice','unconnected-history','three-state-rotation')
MODEL_NAMES={2300+i:n for i,n in enumerate(NAMES)};MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:2e-6 if n in('feedback-half','cross-feedback')else 0 for m,n in MODEL_NAMES.items()}
PREPARE_ZERO_WARM_BLOCKS=0
LEFT=(0.,.25,.25,-.5,-.5,-0.,1.,1.,-1.,-1.,.5,.5,0.,.125,.125,.75)
RIGHT=(0.,1.,1.,-0.,-1.,-1.,.5,.5,0.,.25,-.25,-.25,-1.,1.,1.,1.)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def name(model):
 if type(model)is not int or model not in MODELS:raise ValueError('Unknown visual Gen model')
 return MODEL_NAMES[model]
def input_words(frames=256):return case_input_words(2300,frames)
def case_input_words(model,frames=256):
 n=name(model)
 if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
 return tuple(word(x)for i in range(frames)for x in(LEFT[i%16],(.25,.5,1.,2.)[i%4]if n=='divide'else RIGHT[i%16]))
def reference_blocks(model,inputs,call_count=20):
 identity=name(model);inputs=tuple(inputs)
 if inputs!=case_input_words(model):raise ValueError('Visual Gen source-domain vector differs')
 if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Expected1..20calls')
 def x(n,ch):return value(inputs[2*(n%256)+ch])
 def past(n,ch,initial=.25):return initial if n<0 else x(n,ch)
 def convolution(n,ch):return sum(.5**k*x(n-k,ch)for k in range(min(n+1,64)))
 def coupled(n,ch):
  total=.125**(n//2)*((.25 if ch==0 else-.5)if n%2==0 else(-.25 if ch==0 else .0625))if n<64 else 0.
  for k in range(min(n,64)):
   scale=.125**(k//2);total+=scale*(x(n-1-k,ch)if k%2==0 else(.5*x(n-1-k,1)if ch==0 else .25*x(n-1-k,0)))
  return total
 blocks=[]
 for call in range(call_count):
  block=[]
  for i in range(256):
   n=call*256+i;a=x(n,0);b=x(n,1)
   if identity=='identity':pair=(a,b)
   elif identity=='swap':pair=(b,a)
   elif identity=='add':pair=(a+b,b)
   elif identity=='subtract':pair=(a-b,b)
   elif identity=='multiply':pair=(a*b,b)
   elif identity=='divide':pair=(a/b,b)
   elif identity=='gain-half':pair=(a*.5,b)
   elif identity=='offset-quarter':pair=(a+.25,b)
   elif identity=='subtract-half':pair=(a-.5,b)
   elif identity=='divide-two':pair=(a/2,b)
   elif identity=='negate':pair=(-a,b)
   elif identity=='absolute':pair=(abs(a),b)
   elif identity=='one-sample-history':pair=(past(n-1,0),b)
   elif identity=='two-sample-history':pair=(past(n-2,0,.5)if n==0 else past(n-2,0,.25),b)
   elif identity=='two-state-swap':pair=((.25,-.5)if n%2==0 else(-.5,.25))
   elif identity=='history-fanout':pair=(a+past(n-1,0),b-past(n-1,0))
   elif identity=='feedback-half':pair=(convolution(n,0),b)
   elif identity=='cross-feedback':pair=(coupled(n,0),coupled(n,1))
   elif identity=='history-read-twice':pair=(2*past(n-1,0),b-past(n-1,0))
   elif identity=='unconnected-history':pair=(.25,b)
   elif identity=='three-state-rotation':pair=((1.,2.,4.)[n%3],(2.,4.,1.)[n%3])
   else:raise AssertionError('Missing visual Gen reference')
   block.extend(word(v)for v in pair)
  blocks.append(tuple(block))
 return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
