# SPDX-License-Identifier: MIT
"""Independent finite pointwise references for selected RNBO codebox APIs.

Complex results expose both components. Interpolation conventions are explicit:
4-point Lagrange, full-neighbor-slope Hermite, half-slope Catmull-Rom, and centered
6-point quintic B-spline basis. Control points are asymmetric. Safe/integer
checks use bounded exact operands and documented zero guards, not arbitrary
conversion/overflow domains. ease/easexfade fix the primary In_quadratic enum7
and syncupdate0, making the selected next() output pointwise despite internal
history bookkeeping. xfademul uses default2-channel phase/wrap/equal-power.
Other state/update/reset policies, oscillators and curve tables are excluded.
"""
import math
import struct

NAMES=('boxtotri','kink','quantize','rint','safediv','safemod','safepow','safesqrt','uint32_rshift','uint32_trunc',
       'complex_conj','complex_divide','complex_exp','complex_multiply','cubicinterp','fastcubicinterp','splineinterp',
       'spline6interp','number_max','xfademul','ease','easexfade')
MODEL_NAMES={700+i:name for i,name in enumerate(NAMES)}
MODELS=frozenset(MODEL_NAMES)
EXACT={'boxtotri','quantize','rint','safediv','safemod','safepow','safesqrt','uint32_rshift','uint32_trunc','complex_conj','complex_multiply','number_max','ease','easexfade'}
ABSOLUTE_TOLERANCES={m:0 if n in EXACT else 2e-6 for m,n in MODEL_NAMES.items()}
C4=((-0.5,0.25,1.25,-0.75),(0.75,-1,0.5,1.5))
C6=((-1,0.5,-0.25,1.25,-0.75,2),(0.75,-1.5,0.25,-0.5,1.5,-0.25))


def word(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def words(xs):return tuple(word(x)for x in xs)
UNIT=words((0,.0625,.125,.1875,.25,.3125,.375,.4375,.5,.5625,.625,.75,.8125,.875,.9375,1))
WIDE=words((-4,-2,-1.5,-1,-.75,-.5,-.25,-0.,0.,.25,.5,.75,1,1.5,2,4))
INTEGERS=words(range(-8,8))
ROUND=words((-3.5,-3,-2.5,-2,-1.5,-1,-.5,-0.,0.,.5,1,1.5,2,2.5,3,3.5))
SQUARES=words((-4,-1,-.25,-0.,0.,.0625,.25,1,2.25,4,6.25,9,12.25,16,25,36))
UINTEGER=words((0,1,2,3,4,7,8,15,16,31,32,63,64,127,255,1023))
UFRACTION=words((0,.125,.25,.5,.75,1,1.25,1.5,1.75,2,2.5,3,3.75,7.5,15.75,31.875))
SMALL=words((-1,-.875,-.75,-.625,-.5,-.375,-.25,-.125,0,.125,.25,.375,.5,.625,.75,1))
QUANT=words((-1,-.875,-.625,-.375,-.1875,-.125,-.0625,-0.,0.,.0625,.125,.1875,.375,.625,.875,1))
PLANES={m:(UNIT,UNIT)for m in MODELS}
for m,name in MODEL_NAMES.items():
 if name in('safediv','safepow','complex_conj','complex_divide','complex_multiply','number_max'):PLANES[m]=(WIDE,WIDE)
 elif name=='safemod':PLANES[m]=(INTEGERS,INTEGERS)
 elif name=='safesqrt':PLANES[m]=(SQUARES,SQUARES)
 elif name=='rint':PLANES[m]=(ROUND,ROUND)
 elif name=='uint32_rshift':PLANES[m]=(UINTEGER,UINTEGER)
 elif name=='uint32_trunc':PLANES[m]=(UFRACTION,UFRACTION)
 elif name=='complex_exp':PLANES[m]=(SMALL,SMALL)
 elif name=='quantize':PLANES[m]=(QUANT,QUANT)
DOMAINS={m:tuple((min(value(w)for w in p),max(value(w)for w in p))for p in planes)for m,planes in PLANES.items()}


def _model(m):
 if type(m)is not int or m not in MODELS:raise ValueError('Unknown codebox misc model')


def input_words(frames=256):return case_input_words(700,frames)


def case_input_words(model,frames=256):
 _model(model)
 if type(frames)is not int or not 1<=frames<=16384:raise ValueError('Invalid vector length')
 a,b=PLANES[model]
 return tuple(w for n in range(frames)for w in(a[(n//16)%16],b[n%16]))


def hermite(t,x,y,m0,m1):
 return(2*t**3-3*t*t+1)*x+(t**3-2*t*t+t)*m0+(-2*t**3+3*t*t)*y+(t**3-t*t)*m1


def interpolate(name,t,points):
 w,x,y,z=points
 if name=='cubicinterp':
  nodes=(-1,0,1,2)
  return sum(v*math.prod((t-nodes[j])/(nodes[i]-nodes[j])for j in range(4)if j!=i)for i,v in enumerate(points))
 factor=.5 if name=='splineinterp'else 1.
 return hermite(t,x,y,factor*(y-w),factor*(z-x))


def quintic_bspline(z):
 return sum((-1)**k*math.comb(6,k)*max(z+3-k,0.)**5 for k in range(7))/math.factorial(5)


def spline6(t,points):
 return sum(v*quintic_bspline(t-position)for v,position in zip(points,(-2,-1,0,1,2,3)))


def reference_words(model,inputs):
 _model(model);name=MODEL_NAMES[model];inputs=tuple(inputs)
 if not inputs or len(inputs)%2 or len(inputs)>32768:raise ValueError('Expected bounded stereo words')
 for i,w in enumerate(inputs):
  if type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000:raise ValueError('Finite binary32 input words required')
  lo,hi=DOMAINS[model][i%2]
  if not lo<=value(w)<=hi:raise ValueError('Input exceeds selected finite domain')
  if name in('safemod','uint32_rshift')and value(w)!=math.trunc(value(w)):raise ValueError('Exact small integer inputs required')
 if name=='number_max':return(0x7f7fffff,)*len(inputs)
 def scalar(x,lane):
  if name=='boxtotri':return min(1.,(1-abs(2*x-1))/(.5 if lane==0 else 1.))
  if name=='kink':
   slope=2. if lane==0 else .75;cross=.5/slope
   return x*slope if x<=cross else .5+(x-cross)*.5/(1-cross)
  if name=='quantize':
   q=4 if lane==0 else 8;return math.floor(x*q+.5)/q
  if name=='rint':return round(x)
  if name=='safepow':return x**(2 if lane==0 else 4)
  if name=='safesqrt':return math.sqrt(x)if x>0 else 0.
  if name=='uint32_rshift':return int(x)>>(2 if lane==0 else 3)
  if name=='uint32_trunc':return math.trunc(x)
  if name in('cubicinterp','fastcubicinterp','splineinterp'):return interpolate(name,x,C4[lane])
  if name=='spline6interp':return spline6(x,C6[lane])
  if name=='xfademul':return math.sqrt(1-x)if lane==0 else math.sqrt(x)
  if name=='ease':return x*x
  if name=='easexfade':return -1+2*x*x if lane==0 else 1-2*x*x
  raise ValueError('Not a scalar model')
 result=[]
 for i in range(0,len(inputs),2):
  x,y=(value(w)for w in inputs[i:i+2])
  if name=='safediv':pair=(0. if y==0 else x/y,0. if x==0 else y/x)
  elif name=='safemod':pair=(0 if y==0 else int(x)-math.trunc(x/y)*int(y),0 if x==0 else int(y)-math.trunc(y/x)*int(x))
  elif name=='complex_conj':result.extend((inputs[i],inputs[i+1]^0x80000000));continue
  elif name=='complex_divide':
   z=complex(x,y)/complex(1,.5);pair=(z.real,z.imag)
  elif name=='complex_multiply':
   z=complex(x,y)*complex(1.25,-.5);pair=(z.real,z.imag)
  elif name=='complex_exp':
   magnitude=math.exp(x);pair=(magnitude*math.cos(y),magnitude*math.sin(y))
  else:pair=(scalar(x,0),scalar(y,1))
  result.extend(word(v)for v in pair)
 return tuple(result)
