# SPDX-License-Identifier: MIT
"""Independent finite binary32 math for RNBO codebox~, not GenExpr.

One fixed input block is repeated. All operations are stateless, so preparation
warm4/manual warm4 do not alter the expected twenty callback blocks. Division
and signed remainder use nonzero powers of two on BOTH input lanes. Left uses
(a,b), right uses(b,a); unary forms operate independently per lane. Numeric zero
sign is diagnostic on operation outputs. No NaN/Inf, arbitrary state or aliases
outside each exact authored spelling are qualified by this reference.
"""
from fractions import Fraction
import math
import struct

MODEL_NAMES={220:'absolute',221:'absolute-difference',222:'negate',223:'pass',
 224:'add',225:'subtract',226:'multiply',227:'divide',228:'signed-remainder',
 229:'minimum',230:'maximum',231:'equal',232:'not-equal',233:'greater',
 234:'greater-or-equal',235:'less',236:'less-or-equal',237:'logical-and',
 238:'logical-or',239:'logical-xor',240:'logical-not'}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={model:0 for model in MODELS}
REFERENCE_POLICIES={228:'signed-remainder-truncating-quotient'}
VALUES=(-4.,-2.,-1.5,-1.,-.75,-.5,-.25,-0.,0.,.25,.5,.75,1.,1.5,2.,4.)
NONZERO=(-8.,-4.,-2.,-1.,-.5,-.25,-.125,-.0625,.0625,.125,.25,.5,1.,2.,4.,8.)
UNARY=frozenset((220,222,223,240))

def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def _model(model):
 if type(model)is not int or model not in MODELS:raise ValueError('Unknown RNBO codebox model')
def _frames(frames):
 if type(frames)is not int or frames!=256:raise ValueError('Expected256 frames')
def input_words(frames=256):
 _frames(frames)
 return tuple(word(x)for n in range(frames)for x in(VALUES[n//16],VALUES[n%16]))
def case_input_words(model,frames=256):
 _model(model);_frames(frames)
 if model in(227,228):return tuple(word(x)for n in range(frames)for x in(NONZERO[n//16],NONZERO[n%16]))
 return input_words(frames)
def _op(model,a,b):
 if model==220:return abs(a)
 if model==221:return abs(a-b)
 if model==222:return -a
 if model==223:return a
 if model==224:return a+b
 if model==225:return a-b
 if model==226:return a*b
 if model==227:
  if b==0:raise ValueError('Zero divisor outside reviewed domain')
  return Fraction(a)/Fraction(b)
 if model==228:
  if b==0:raise ValueError('Zero divisor outside reviewed domain')
  result=Fraction(a)-math.trunc(Fraction(a)/Fraction(b))*Fraction(b)
  return float(result)if result else math.copysign(0.,a)
 if model==229:return a if a<=b else b
 if model==230:return a if a>=b else b
 if model==231:return a==b
 if model==232:return a!=b
 if model==233:return a>b
 if model==234:return a>=b
 if model==235:return a<b
 if model==236:return a<=b
 if model==237:return(a!=0)and(b!=0)
 if model==238:return(a!=0)or(b!=0)
 if model==239:return(a!=0)!=(b!=0)
 if model==240:return a==0
 raise ValueError('Unknown operation')
def reference_words(model,inputs):
 _model(model);inputs=tuple(inputs)
 if len(inputs)!=512 or any(type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000 for w in inputs):raise ValueError('Expected512 finite binary32 words')
 output=[]
 for i in range(0,512,2):
  a,b=value(inputs[i]),value(inputs[i+1])
  if abs(a)>8 or abs(b)>8:raise ValueError('Input outside reviewed finite range')
  output.extend((word(_op(model,a,b)),word(_op(model,b,a))))
 return tuple(output)
