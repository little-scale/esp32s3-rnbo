# SPDX-License-Identifier: MIT
"""Predeclared finite RNBO signal ranges/routes/window/function references.

Models follow actual patcher inlet roles, not similarly named codebox/Gen calls.
The documented step digest is not(in1<in2); its threshold is fixed0 here, and
producer disagreement stays a mismatch. Cosineinterp/fast functions use explicit
ideal1e-3 screening, not an accuracy promise. T60 time is samples; its coefficient
domain0.125..0.5 limits output to about10samples for the fixed2e-6 gate.
Quantize uses declared upward half ties; only value outlets of tuple operators
are connected as specified. No within-block controls/stateful oscillator claim.
"""
import math
import struct

NAMES=('clamp~','fold~','phasewrap~','smoothstep~','mix~','cond~','eqp~','neqp~','gtp~','gtep~','ltp~','ltep~','step~',
       'cartopol~','poltocar~','linearinterp~','cosineinterp~','fastpow~','fastexp~','hann~','hamming~','blackman~','welch~',
       'ln2~','LN2~','ln10~','LN10~','log2e~','LOG2E~','log10e~','LOG10E~','t60~','t60time~','triangle~','boxtotri~','kink~','quantize~')
MODEL_NAMES={600+i:name for i,name in enumerate(NAMES)}
MODELS=frozenset(MODEL_NAMES)
EXACT={'clamp~','fold~','smoothstep~','mix~','cond~','eqp~','neqp~','gtp~','gtep~','ltp~','ltep~','step~','linearinterp~','boxtotri~','quantize~'}
CONSTANTS={'ln2~':math.log(2),'LN2~':math.log(2),'ln10~':math.log(10),'LN10~':math.log(10),
           'log2e~':1/math.log(2),'LOG2E~':1/math.log(2),'log10e~':1/math.log(10),'LOG10E~':1/math.log(10)}
APPROX={'cosineinterp~','fastpow~','fastexp~'}
ABSOLUTE_TOLERANCES={m:0 if n in EXACT or n in CONSTANTS else 1e-3 if n in APPROX else 2e-6 for m,n in MODEL_NAMES.items()}


def word(v):return struct.unpack('<I',struct.pack('<f',v))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def words(xs):return tuple(word(v)for v in xs)
WIDE=words((-4,-2,-1.5,-1,-.75,-.5,-.25,-0.,0.,.25,.5,.75,1,1.5,2,4))
UNIT=words((0,.0625,.125,.1875,.25,.3125,.375,.4375,.5,.5625,.625,.75,.8125,.875,.9375,1))
NONZERO=words((-2,-1.5,-1,-.75,-.5,-.25,-.125,-.0625,.0625,.125,.25,.5,.75,1,1.5,2))
POSITIVE=words(n/8 for n in range(1,17))
ANGLE=words((-1,-.875,-.75,-.625,-.5,-.375,-.25,-.125,0,.125,.25,.375,.5,.625,.75,1))
TIMES=words((1,2,4,8,16,32,64,128,256,512,1000,2048,4096,8192,16384,32768))
COEFFICIENTS=words((.125,.15625,.1875,.21875,.25,.265625,.28125,.296875,.3125,.34375,.375,.40625,.4375,.453125,.46875,.5))
QUANTIZED=words((-1,-.875,-.625,-.375,-.1875,-.125,-.0625,-0.,0.,.0625,.125,.1875,.375,.625,.875,1))
PLANES={m:(WIDE,WIDE)for m in MODELS}
for m,n in MODEL_NAMES.items():
 if n in('linearinterp~','cosineinterp~','hann~','hamming~','blackman~','welch~','triangle~','boxtotri~','kink~'):PLANES[m]=(UNIT,UNIT)
 elif n=='cartopol~':PLANES[m]=(NONZERO,NONZERO)
 elif n=='poltocar~':PLANES[m]=(POSITIVE,ANGLE)
 elif n=='fastpow~':PLANES[m]=(POSITIVE,POSITIVE)
 elif n=='fastexp~':PLANES[m]=(ANGLE,ANGLE)
 elif n=='t60~':PLANES[m]=(TIMES,TIMES)
 elif n=='t60time~':PLANES[m]=(COEFFICIENTS,COEFFICIENTS)
 elif n=='quantize~':PLANES[m]=(QUANTIZED,QUANTIZED)
DOMAINS={m:tuple((min(value(w)for w in p),max(value(w)for w in p))for p in planes)for m,planes in PLANES.items()}


def _model(m):
 if type(m)is not int or m not in MODELS:raise ValueError('Unknown RNBO signal-range model')


def input_words(frames=256):return case_input_words(600,frames)


def case_input_words(model,frames=256):
 _model(model)
 if type(frames)is not int or not 1<=frames<=16384:raise ValueError('Invalid vector length')
 left,right=PLANES[model]
 return tuple(w for n in range(frames)for w in(left[(n//16)%16],right[n%16]))


def reference_words(model,inputs):
 _model(model);inputs=tuple(inputs);name=MODEL_NAMES[model]
 if not inputs or len(inputs)%2 or len(inputs)>32768:raise ValueError('Expected bounded stereo words')
 for i,w in enumerate(inputs):
  if type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000:raise ValueError('Finite binary32 inputs required')
  lo,hi=DOMAINS[model][i%2]
  if not lo<=value(w)<=hi:raise ValueError('Input exceeds predeclared scenario domain')
 if name in CONSTANTS:return(word(CONSTANTS[name]),)*len(inputs)
 def scalar(x,lane):
  if name=='clamp~':return max(-1.,min(1.,x))
  if name=='fold~':
   p=(x+1)%4;return -1+p if p<=2 else 3-p
  if name=='phasewrap~':return(x+math.pi)%(2*math.pi)-math.pi
  if name=='smoothstep~':
   t=max(0.,min(1.,(x+1)/2));return t*t*(3-2*t)
  if name=='cond~':return 1. if x!=0 else -1.
  if name=='step~':return float(x>=0)
  if name=='linearinterp~':return -1+2*x if lane==0 else 1-2*x
  if name=='cosineinterp~':return -math.cos(math.pi*x)if lane==0 else math.cos(math.pi*x)
  if name=='fastexp~':return math.exp(x)
  if name=='hann~':return .5*(1-math.cos(2*math.pi*x))
  if name=='hamming~':return .54-.46*math.cos(2*math.pi*x)
  if name=='blackman~':return .42-.5*math.cos(2*math.pi*x)+.08*math.cos(4*math.pi*x)
  if name=='welch~':return 1-(2*x-1)**2
  if name=='t60~':return 10**(-3/x)
  if name=='t60time~':return math.log(.001)/math.log(x)
  if name=='triangle~':
   p=x%1;duty=.5 if lane==0 else .25;return p/duty if p<=duty else(1-p)/(1-duty)
  if name=='boxtotri~':return min(1.,(1-abs(2*x-1))/(.5 if lane==0 else 1.))
  if name=='kink~':
   slope=2. if lane==0 else .75;cross=.5/slope
   return x*slope if x<=cross else .5+(x-cross)*.5/(1-cross)
  if name=='quantize~':
   q=4 if lane==0 else 8;return math.floor(x*q+.5)/q
  raise ValueError('Not a unary model')
 predicates={'eqp~':lambda x,y:x==y,'neqp~':lambda x,y:x!=y,'gtp~':lambda x,y:x>y,
             'gtep~':lambda x,y:x>=y,'ltp~':lambda x,y:x<y,'ltep~':lambda x,y:x<=y}
 result=[]
 for i in range(0,len(inputs),2):
  x,y=(value(w)for w in inputs[i:i+2])
  if name in predicates:
   p=predicates[name];pair=(x if p(x,y)else 0.,y if p(y,x)else 0.)
  elif name=='mix~':pair=(.75*x+.25*y,.75*y+.25*x)
  elif name=='cartopol~':pair=(math.hypot(x,y),math.atan2(y,x))
  elif name=='poltocar~':pair=(x*math.cos(y),x*math.sin(y))
  elif name=='fastpow~':pair=(x**y,y**x)
  else:pair=(scalar(x,0),scalar(y,1))
  result.extend(word(v)for v in pair)
 return tuple(result)
