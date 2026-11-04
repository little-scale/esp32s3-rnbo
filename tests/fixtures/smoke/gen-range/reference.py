# SPDX-License-Identifier: MIT
"""Independent finite GenExpr range/route/math smoke references.

All vectors and limits are declared before execution. Exact dyadic ranges and
routes use zero tolerance; ordinary transcendental math uses2e-6, fast ideal
comparisons1e-3 (screening, not an accuracy promise), unit converters5e-4.
Coordinates use Cartesian(x,y) and polar(radius,radians). Gate/selector choices
are integers. T60 is amplitude decay to.001 in a number of samples. fixnan and
isnan are exercised on finite inputs only; this is not NaN-repair qualification.
"""
import math
import struct

RATE=44100
NAMES=('fold','wrap','clamp','clip','scale','mix','smoothstep','phasewrap','cartopol','poltocar',
       'selector','gate','fastpow','fastexp','fastsin','fastcos','fasttan','mtof','ftom',
       'mstosamps','sampstoms','atodb','dbtoa','t60','t60time','triangle','interp','pass','fixnan','isnan')
MODEL_NAMES={350+i:name for i,name in enumerate(NAMES)}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={model:0 for model in MODELS}
ABSOLUTE_TOLERANCES.update({m:2e-6 for m in(357,358,359,371,372,373,375)})
ABSOLUTE_TOLERANCES.update({m:1e-3 for m in range(362,367)})
ABSOLUTE_TOLERANCES.update({m:5e-4 for m in(367,368,369,370,374)})


def word(value):return struct.unpack('<I',struct.pack('<f',value))[0]
def value(bits):return struct.unpack('<f',struct.pack('<I',bits))[0]
def words(values):return tuple(word(x)for x in values)
WIDE=words((-4.,-2.,-1.5,-1.,-.75,-.5,-.25,-0.,0.,.25,.5,.75,1.,1.5,2.,4.))
NONZERO=words((-2.,-1.5,-1.,-.75,-.5,-.25,-.125,-.0625,.0625,.125,.25,.5,.75,1.,1.5,2.))
POSITIVE=words(n/8 for n in range(1,17))
ANGLE=words((-1.,-.875,-.75,-.625,-.5,-.375,-.25,-.125,0.,.125,.25,.375,.5,.625,.75,1.))
SMALL=words((-.5,-.4375,-.375,-.3125,-.25,-.1875,-.125,-.0625,0.,.0625,.125,.1875,.25,.3125,.375,.5))
UNIT=words((0.,.0625,.125,.1875,.25,.3125,.375,.4375,.5,.5625,.625,.75,.8125,.875,.9375,1.))
CHOICES=words((-2,-1,0,1,2,3,4,0,1,2,3,4,-1,0,1,2))
MIDI=words((36,48,55,57,60,60.25,61,64,67,69,69.25,70,72,76,81,84))
FREQUENCY=words(440*2**((n-69)/12)for n in(48,48.25,55,55.25,57,59.75,60,60.25,64,66.75,67,68.75,69,69.25,72,81))
MILLISECONDS=words((0,.125,.25,.5,1,1.5,2,5,10,20,50,100,125,250,500,1000))
SAMPLES=words((0,1,2,4,8,16,32,64,128,256,441,4410,11025,22050,33075,44100))
AMPLITUDE=words((.5,.5625,.625,.6875,.75,.8125,.875,.9375,1,1.0625,1.125,1.25,1.375,1.5,1.75,2))
DECIBELS=words((-24,-21,-18,-15,-12,-9,-6,-3,-0.,0.,1,2,3,4,5,6))
DECAY_TIME=words((1,2,4,8,16,32,64,128,256,512,1000,2048,4096,8192,16384,32768))
MULTIPLIER=words((.25,.375,.5,.5625,.625,.6875,.75,.8125,.875,.90625,.9375,.953125,.96875,.9765625,.984375,.9921875))
PLANES={model:(WIDE,WIDE)for model in MODELS}
PLANES.update({358:(NONZERO,NONZERO),359:(POSITIVE,ANGLE),360:(CHOICES,WIDE),361:(CHOICES,WIDE),
 362:(POSITIVE,POSITIVE),363:(ANGLE,ANGLE),**{m:(SMALL,SMALL)for m in(364,365,366)},
 367:(MIDI,MIDI),368:(FREQUENCY,FREQUENCY),369:(MILLISECONDS,MILLISECONDS),370:(SAMPLES,SAMPLES),
 371:(AMPLITUDE,AMPLITUDE),372:(DECIBELS,DECIBELS),373:(DECAY_TIME,DECAY_TIME),374:(MULTIPLIER,MULTIPLIER),
 375:(UNIT,UNIT),376:(UNIT,UNIT)})
DOMAINS={model:tuple((min(value(w)for w in plane),max(value(w)for w in plane))for plane in planes)for model,planes in PLANES.items()}


def _model(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown Gen range model')


def input_words(frames=256):return case_input_words(350,frames)


def case_input_words(model,frames=256):
    _model(model)
    if type(frames)is not int or not 1<=frames<=16384:raise ValueError('Invalid vector length')
    left,right=PLANES[model]
    return tuple(w for n in range(frames)for w in(left[(n//16)%16],right[n%16]))


def reference_words(model,inputs):
    _model(model);inputs=tuple(inputs)
    if not inputs or len(inputs)%2 or len(inputs)>32768:raise ValueError('Expected bounded stereo input words')
    for n,w in enumerate(inputs):
        if type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000:raise ValueError('Expected finite binary32 words')
        lo,hi=DOMAINS[model][n%2]
        if not lo<=value(w)<=hi:raise ValueError('Input outside predeclared smoke domain')
        if model in(360,361)and n%2==0 and value(w)!=math.trunc(value(w)):raise ValueError('Integer route choices required')
    def unary(x):
        if model==350:
            t=(x+1)%4;return -1+t if t<=2 else 3-t
        if model==351:return (x+1)%2-1
        if model in(352,353):return max(-1.,min(1.,x))
        if model==354:return 2*x
        if model==356:
            t=max(0.,min(1.,(x+1)/2));return t*t*(3-2*t)
        if model==357:return (x+math.pi)%(2*math.pi)-math.pi
        if model==363:return math.exp(x)
        if model==364:return math.sin(x)
        if model==365:return math.cos(x)
        if model==366:return math.tan(x)
        if model==367:return 440*2**((x-69)/12)
        if model==368:return 69+12*math.log2(x/440)
        if model==369:return x*RATE/1000
        if model==370:return x*1000/RATE
        if model==371:return 20*math.log10(x)
        if model==372:return 10**(x/20)
        if model==373:return 10**(-3/x)
        if model==374:return math.log(.001)/math.log(x)
        if model==379:return 0.
        raise ValueError('Not a unary model')
    result=[]
    for n in range(0,len(inputs),2):
        a,b=inputs[n:n+2];x,y=value(a),value(b)
        if model==355:pair=(.75*x+.25*y,.75*y+.25*x)
        elif model==358:pair=(math.hypot(x,y),math.atan2(y,x))
        elif model==359:pair=(x*math.cos(y),x*math.sin(y))
        elif model==360:pair=(y if x==1 else -y if x>=2 else 0.,-y if x==1 else y if x>=2 else 0.)
        elif model==361:pair=(y if x==1 else 0.,y if x>=2 else 0.)
        elif model==362:pair=(x**y,y**x)
        elif model==375:
            def triangle(p,duty):
                p=p%1;return p/duty if p<=duty else(1-p)/(1-duty)
            pair=(triangle(x,.5),triangle(y,.25))
        elif model==376:pair=(-1+2*x,1-2*y)
        elif model in(377,378):result.extend((a,b));continue
        else:pair=(unary(x),unary(y))
        result.extend(word(z)for z in pair)
    return tuple(result)
