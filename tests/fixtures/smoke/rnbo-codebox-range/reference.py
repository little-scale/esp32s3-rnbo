# SPDX-License-Identifier: MIT
"""Independent finite math for exact RNBO codebox call forms.

Limits and domains precede hardware execution. Exact dyadic range/routes use0;
ordinary math2e-6; unit converters5e-4; fast ideal screens1e-3 (not documented
accuracy guarantees). ftom explicitly models its documented default round=true,
with note-centre and quartertone frequencies, excluding halfnote ties. No Gen
policy/patcher/alias qualification is transferred. NaN/Inf/fenv are out of scope.
"""
from fractions import Fraction
import math
import struct
NAMES=('clamp','fold','wrap','scale','mix','smoothstep','phasewrap','cartopol','poltocar','interp','cond','switch','step','eqp','neqp','gtp','gtep','ltp','ltep','rdiv','rmod','rsub','fastpow','fastexp','fastsin','fastcos','fasttan','log2f','cosT8','cosT8safe','atodb','dbtoa','mtof','ftom','mstosamps','sampstoms','hztoms','mstohz','hztosamps','sampstohz','t60','t60time','triangle')
MODEL_NAMES={400+i:n for i,n in enumerate(NAMES)};MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:0 for m in MODELS};ABSOLUTE_TOLERANCES.update({m:2e-6 for m in(406,407,408,428,429,430,431,440)});ABSOLUTE_TOLERANCES.update({m:1e-3 for m in range(422,428)});ABSOLUTE_TOLERANCES.update({m:5e-4 for m in range(432,440)});ABSOLUTE_TOLERANCES[441]=5e-4
REFERENCE_POLICIES={411:'declared-boolean-selection-policy',412:'not-first-less-than-second',420:'signed-remainder-truncating-quotient',433:'default-rounded-MIDI-note',**{m:'ideal-math-approximation-screen'for m in range(422,428)}}
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def words(xs):return tuple(word(x)for x in xs)
WIDE=words((-4.,-2.,-1.5,-1.,-.75,-.5,-.25,-0.,0.,.25,.5,.75,1.,1.5,2.,4.))
NONZERO=words((-8.,-4.,-2.,-1.,-.5,-.25,-.125,-.0625,.0625,.125,.25,.5,1.,2.,4.,8.))
POSITIVE=words(n/8 for n in range(1,17))
ANGLE=words((-1.,-.875,-.75,-.625,-.5,-.375,-.25,-.125,0.,.125,.25,.375,.5,.625,.75,1.))
SMALL=words((-.5,-.4375,-.375,-.3125,-.25,-.1875,-.125,-.0625,0.,.0625,.125,.1875,.25,.3125,.375,.5))
UNIT=words((0.,.0625,.125,.1875,.25,.3125,.375,.4375,.5,.5625,.625,.75,.8125,.875,.9375,1.))
BOOLS=words((0,1,0,1,0,1,0,1,1,0,1,0,1,0,1,0))
SAFE_COS=words((-6.75,-6.5,-6.25,-6.,-.5,-.25,-.125,-0.,0.,.125,.25,.5,6.,6.25,6.5,6.75))
MIDI=words((36,48,55,57,60,60.25,61,64,67,69,69.25,70,72,76,81,84))
FREQUENCY=words(440*2**((n-69)/12)for n in(48,48.25,55,55.25,57,59.75,60,60.25,64,66.75,67,68.75,69,69.25,72,81))
MS=words((0,.125,.25,.5,1,1.5,2,5,10,20,50,100,125,250,500,1000))
SAMPLES=words((0,1,2,4,8,16,32,64,128,256,441,4410,11025,22050,33075,44100))
HZ=words((1,2,10,20,50,100,220,440,880,1000,2000,4410,5000,10000,20000,44100))
NONZERO_MS=words((.125,.25,.5,1,1.5,2,5,10,20,50,100,125,250,500,1000,2000))
NONZERO_SAMPLES=words((1,2,4,8,16,32,64,128,256,441,4410,11025,16384,22050,33075,44100))
AMPLITUDE=words((.5,.5625,.625,.6875,.75,.8125,.875,.9375,1,1.0625,1.125,1.25,1.375,1.5,1.75,2))
DB=words((-24,-21,-18,-15,-12,-9,-6,-3,-0.,0.,1,2,3,4,5,6))
DECAY=words((1,2,4,8,16,32,64,128,256,512,1000,2048,4096,8192,16384,32768))
MULTIPLIER=words((.25,.375,.5,.5625,.625,.6875,.75,.8125,.875,.90625,.9375,.953125,.96875,.9765625,.984375,.9921875))
PLANES={m:(WIDE,WIDE)for m in MODELS};PLANES.update({407:(NONZERO,NONZERO),408:(POSITIVE,ANGLE),409:(UNIT,WIDE),410:(BOOLS,WIDE),411:(BOOLS,WIDE),419:(NONZERO,NONZERO),420:(NONZERO,NONZERO),422:(POSITIVE,POSITIVE),423:(ANGLE,ANGLE),424:(SMALL,SMALL),425:(SMALL,SMALL),426:(SMALL,SMALL),427:(POSITIVE,POSITIVE),428:(ANGLE,ANGLE),429:(SAFE_COS,SAFE_COS),430:(AMPLITUDE,AMPLITUDE),431:(DB,DB),432:(MIDI,MIDI),433:(FREQUENCY,FREQUENCY),434:(MS,MS),435:(SAMPLES,SAMPLES),436:(HZ,HZ),437:(NONZERO_MS,NONZERO_MS),438:(HZ,HZ),439:(NONZERO_SAMPLES,NONZERO_SAMPLES),440:(DECAY,DECAY),441:(MULTIPLIER,MULTIPLIER),442:(UNIT,UNIT)})
DOMAINS={m:tuple((min(value(w)for w in p),max(value(w)for w in p))for p in ps)for m,ps in PLANES.items()}
def _model(m):
 if type(m)is not int or m not in MODELS:raise ValueError('Unknown codebox range model')
def input_words(frames=256):return case_input_words(400,frames)
def case_input_words(model,frames=256):
 _model(model)
 if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
 a,b=PLANES[model];return tuple(w for n in range(frames)for w in(a[n//16],b[n%16]))
def _unary(m,x):
 if m==400:return min(1.,max(-1.,x))
 if m==401:
  phase=(x+1)%4;return -1+phase if phase<=2 else 3-phase
 if m==402:return(x+1)%2-1
 if m==403:return 2*x
 if m==405:
  t=min(1.,max(0.,(x+1)/2));return t*t*(3-2*t)
 if m==406:return(x+math.pi)%(2*math.pi)-math.pi
 if m==423:return math.exp(x)
 if m==424:return math.sin(x)
 if m in(425,428,429):return math.cos(x)
 if m==426:return math.tan(x)
 if m==427:return math.log2(x)
 if m==430:return 20*math.log10(x)
 if m==431:return 10**(x/20)
 if m==432:return 440*2**((x-69)/12)
 if m==433:return math.floor(69+12*math.log2(x/440)+.5)
 if m==434:return x*44100/1000
 if m==435:return x*1000/44100
 if m in(436,437):return 1000/x
 if m in(438,439):return 44100/x
 if m==440:return 10**(-3/x)
 if m==441:return math.log(.001)/math.log(x)
 if m==442:
  p=x%1;return 2*p if p<=.5 else 2*(1-p)
 raise ValueError('Not unary')
def _binary(m,x,y):
 if m==412:return not(x<y)
 if m==413:return x if x==y else 0.
 if m==414:return x if x!=y else 0.
 if m==415:return x if x>y else 0.
 if m==416:return x if x>=y else 0.
 if m==417:return x if x<y else 0.
 if m==418:return x if x<=y else 0.
 if m==419:return Fraction(y)/Fraction(x)
 if m==420:
  r=Fraction(y)-math.trunc(Fraction(y)/Fraction(x))*Fraction(x);return float(r)if r else math.copysign(0.,y)
 if m==421:return y-x
 if m==422:return x**y
 raise ValueError('Not binary')
def reference_words(model,inputs):
 _model(model);inputs=tuple(inputs)
 if len(inputs)!=512:raise ValueError('Expected512 interleaved words')
 for n,w in enumerate(inputs):
  if type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000:raise ValueError('Expected finite words')
  lo,hi=DOMAINS[model][n%2]
  if not lo<=value(w)<=hi:raise ValueError('Outside predeclared domain')
  if model in(419,420)and value(w)==0:raise ValueError('Nonzero divisors required')
  if model in(410,411)and n%2==0 and value(w)not in(0.,1.):raise ValueError('Boolean routing control only')
 if model==407 and any(inputs[n]&0x7fffffff==0 and inputs[n+1]&0x7fffffff==0 for n in range(0,512,2)):raise ValueError('Cartesian origin excluded')
 result=[]
 for n in range(0,512,2):
  x,y=value(inputs[n]),value(inputs[n+1])
  if model==404:pair=(.75*x+.25*y,.75*y+.25*x)
  elif model==407:pair=(math.hypot(x,y),math.atan2(y,x))
  elif model==408:pair=(x*math.cos(y),x*math.sin(y))
  elif model==409:pair=((1-x)*y-x*y,-(1-x)*y+x*y)
  elif model in(410,411):pair=(y if x!=0 else-y,-y if x!=0 else y)
  elif 412<=model<=422:pair=(_binary(model,x,y),_binary(model,y,x))
  else:pair=(_unary(model,x),_unary(model,y))
  result.extend(word(z)for z in pair)
 return tuple(result)
