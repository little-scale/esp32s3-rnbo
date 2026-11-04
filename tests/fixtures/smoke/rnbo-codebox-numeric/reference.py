# SPDX-License-Identifier: MIT
"""Independent mathematical references for finite RNBO codebox numeric smoke.

Exact simple operations; fixed2e-6 absolute error on once-binary32-rounded
standard math. Domains/limits are authored before hardware output is observed.
Round means nearest integer/ties away; fract means signed x-trunc(x). Those
policies are explicit, not inferred from the exported DSP. NaN helpers receive
finite inputs only; denormal functions include signed subnormals. Operation
zero signs remain diagnostics, not numeric errors. No mode/alias inheritance.
"""
from fractions import Fraction
import math
import struct
MODEL_NAMES={300:'floor',301:'ceil',302:'trunc',303:'round',304:'fract',305:'sign',306:'boolnum',307:'isnan',308:'fixnan',309:'isdenorm',310:'fixdenorm',311:'intnum',312:'sqrt',313:'cbrt',314:'exp',315:'exp2',316:'expm1',317:'log',318:'log2',319:'log10',320:'log1p',321:'pow',322:'sin',323:'cos',324:'tan',325:'tanh',326:'asin',327:'acos',328:'atan',329:'atan2',330:'sinh',331:'cosh',332:'asinh',333:'acosh',334:'atanh',335:'hypot',336:'degrees',337:'radians'}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:0 if m<312 else 2e-6 for m in MODELS}
REFERENCE_POLICIES={303:'nearest-integer-ties-away-from-zero',304:'signed-fraction-convention',305:'sign-zero-returns-itself',307:'finite-inputs-only',308:'finite-inputs-only',309:'binary32-subnormal-predicate',310:'binary32-subnormal-to-zero'}
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
MAGNITUDES=(0,1,2,0x003fffff,0x00400000,0x007ffffe,0x007fffff,0x00800000,0x00800001,0x3e7fffff,0x3e800000,0x3e800001,0x3effffff,0x3f000000,0x3f000001,0x3f400000,0x3f7fffff,0x3f800000,0x3f800001,0x3fbfffff,0x3fc00000,0x3fc00001,0x3fffffff,0x40000000,0x40000001,0x407fffff,0x40800000,0x40800001,0x4a7fffff,0x4a800000,0x4a800001,0x4affffff,0x4b000000,0x4b000001,0x4b7fffff,0x4b800000,0x4b800001,0x4effffff)
WORDS=(*MAGNITUDES,*(w|0x80000000 for w in MAGNITUDES),0xcf000000)
GENERAL=(-4.,-3.,-2.,-1.5,-1.,-.75,-.5,-.25,-0.,0.,.25,.5,.75,1.,2.,4.)
UNIT=(-1.,-.875,-.75,-.5,-.25,-.125,-0.,0.,.125,.25,.5,.625,.75,.875,1.)
EXP=(-2.,-1.5,-1.,-.75,-.5,-.25,-.125,-0.,0.,.125,.25,.5,.75,1.,1.5,2.)
POS=(.125,.15625,.1875,.25,.3125,.375,.5,.625,.75,1.,1.25,1.5,2.,2.5,3.,4.)
DOMAINS={312:(0.,4.),313:(-4.,4.),314:(-2.,2.),315:(-2.,2.),316:(-2.,2.),317:(.125,4.),318:(.125,4.),319:(.125,4.),320:(-.75,2.),321:(.125,2.),322:(-4.,4.),323:(-4.,4.),324:(-1.,1.),325:(-4.,4.),326:(-1.,1.),327:(-1.,1.),328:(-4.,4.),329:(-4.,4.),330:(-2.,2.),331:(-2.,2.),332:(-4.,4.),333:(1.,4.),334:(-.75,.75),335:(-4.,4.),336:(-.125,.125),337:(-4.,4.)}
def _model(m):
 if type(m)is not int or m not in MODELS:raise ValueError('Unknown RNBOcodebox numeric model')
def _frames(n):
 if type(n)is not int or n!=256:raise ValueError('Expected256 frames')
def input_words(frames=256):
 _frames(frames);return tuple(w for n in range(frames)for w in(WORDS[n%len(WORDS)],WORDS[(n+29)%len(WORDS)]))
def case_input_words(model,frames=256):
 _model(model);_frames(frames)
 if model<312:return input_words(frames)
 if model==312:xs=(0.,.015625,.0625,.125,.25,.375,.5,.75,1.,1.25,1.5,2.,2.25,2.5,3.,4.)
 elif model in(314,315,316,330,331):xs=EXP
 elif model in(317,318,319):xs=POS
 elif model==320:xs=(-.75,-.5,-.25,-.125,-.0625,-0.,0.,.0625,.125,.25,.5,.75,1.,1.25,1.5,2.)
 elif model==321:xs=tuple(n/8 for n in range(1,17))
 elif model in(324,326,327):xs=UNIT
 elif model==329:xs=(-4.,-2.,-1.,-.5,-.25,.25,.5,1.,2.,4.)
 elif model==333:xs=(1.,1.015625,1.125,1.25,1.5,1.75,2.,2.25,2.5,2.75,3.,3.25,3.5,3.75,4.)
 elif model==334:xs=(-.75,-.625,-.5,-.375,-.25,-.125,-0.,0.,.125,.25,.375,.5,.625,.75)
 elif model==336:xs=tuple(n/128 for n in range(-16,17))
 else:xs=GENERAL
 return tuple(word(x)for n in range(frames)for x in(xs[(n//len(xs))%len(xs)],xs[n%len(xs)]))
def _op(m,a,b):
 x,y=value(a),value(b)
 if m==300:return word(math.floor(x))
 if m==301:return word(math.ceil(x))
 if m in(302,311):return word(math.trunc(x))
 if m==303:
  q=abs(Fraction(x));n=(2*q.numerator+q.denominator)//(2*q.denominator);return word(math.copysign(n,x))
 if m==304:
  r=Fraction(x)-math.trunc(x);return word(float(r))if r else word(math.copysign(0.,x))
 if m==305:return a if x==0 else word(1 if x>0 else-1)
 if m==306:return word(x!=0)
 if m==307:return 0
 if m==308:return a
 if m in(309,310):
  tiny=(a&0x7f800000)==0 and(a&0x007fffff)!=0
  return word(tiny)if m==309 else(0 if tiny else a)
 funcs={312:math.sqrt,313:math.cbrt,314:math.exp,315:math.exp2,316:math.expm1,317:math.log,318:math.log2,319:math.log10,320:math.log1p,322:math.sin,323:math.cos,324:math.tan,325:math.tanh,326:math.asin,327:math.acos,328:math.atan,330:math.sinh,331:math.cosh,332:math.asinh,333:math.acosh,334:math.atanh,336:math.degrees,337:math.radians}
 result=math.pow(x,y)if m==321 else math.atan2(x,y)if m==329 else math.hypot(x,y)if m==335 else funcs[m](x)
 return word(result)
def reference_words(model,inputs):
 _model(model);inputs=tuple(inputs)
 if len(inputs)!=512:raise ValueError('Expected512 stereo words')
 for w in inputs:
  if type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000 or not -2147483648<=value(w)<=2147483520:raise ValueError('Expected finite commonInt32-safe inputs')
  if model in DOMAINS and not DOMAINS[model][0]<=value(w)<=DOMAINS[model][1]:raise ValueError('Outside declared function domain')
 if model==329 and any(inputs[n]&0x7fffffff==0 and inputs[n+1]&0x7fffffff==0 for n in range(0,512,2)):raise ValueError('atan2 zero pair outside domain')
 return tuple(w for n in range(0,512,2)for w in(_op(model,inputs[n],inputs[n+1]),_op(model,inputs[n+1],inputs[n])))
