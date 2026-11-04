# SPDX-License-Identifier: MIT
"""Predeclared finite scalar RNBO shaping references, independent of DSP output.

Easing equations follow the pinned named primary definitions, not an assumed
Penner variant: back is cubic-minus-sine; elastic has6.5pi oscillation; bounce
is described here by four independent parabolic vertex segments. In/out forms
use mathematical reflection/composition. Windows use their ideal equations.
Cosine interpolation's primary implementation uses a Taylor cosine, so its
ideal-cosine1e-3 gate is explicitly screening, not an accuracy guarantee.
Small integer operands exclude overflow and zero divisors. No list/resources,
stateful ease class, arbitrary integer domain or nonfinite claim is made.
"""
import math
import struct

FAMILIES=('quadratic','cubic','quartic','quintic','sine','exponential','circular','back','bounce','elastic')
MODES=('in','out','in_out')
MODEL_NAMES={500+3*i+j:'ease_'+mode+'_'+family for i,family in enumerate(FAMILIES)for j,mode in enumerate(MODES)}
MODEL_NAMES.update({530:'hann',531:'hamming',532:'blackman',533:'welch',534:'linearinterp',535:'cosineinterp',
                    536:'iadd',537:'imul',538:'imod',539:'uint32_add'})
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={model:2e-6 for model in MODELS}
ABSOLUTE_TOLERANCES.update({534:0,535:1e-3,536:0,537:0,538:0,539:0})


def word(value):return struct.unpack('<I',struct.pack('<f',value))[0]
def value(bits):return struct.unpack('<f',struct.pack('<I',bits))[0]
base=(0,.03125,.0625,.125,.1875,.25,.3125,.375,.4375,.5,.5625,.625,.6875,.75,.8125,.875,.9375,.96875,1,.1,.2,.3,.4)
phase_words={word(t)for t in base}
for cut in(4/11,8/11,.9):
    center=word(cut);phase_words.update((center-1,center,center+1))
PHASE_WORDS=tuple(sorted(phase_words))
SIGNED=tuple(word(n)for n in range(-8,8))
NONZERO=tuple(word(n)for n in(*range(-8,0),*range(1,9)))
UNSIGNED=tuple(word(n)for n in range(16))


def _model(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown scalar shaping model')


def input_words(frames=256):return case_input_words(500,frames)


def case_input_words(model,frames=256):
    _model(model)
    if type(frames)is not int or not 1<=frames<=16384:raise ValueError('Invalid functional vector length')
    if model>=536:
        points=NONZERO if model==538 else UNSIGNED if model==539 else SIGNED
        return tuple(w for n in range(frames)for w in(points[(n//16)%16],points[n%16]))
    return tuple(w for n in range(frames)for w in(PHASE_WORDS[n%len(PHASE_WORDS)],PHASE_WORDS[(n+11)%len(PHASE_WORDS)]))


def bounce_out(t):
    # Independent vertex form: first rise, then parabolas with minima.7,.91,.973.
    if t<4/11:return(11*t/4)**2
    if t<8/11:return .7+.3*((t-6/11)/(2/11))**2
    if t<.9:return .91+.09*((t-179/220)/(19/220))**2
    return .973+.027*((t-.95)/.05)**2


def ease_in(family,t):
    if family in('quadratic','cubic','quartic','quintic'):return t**{'quadratic':2,'cubic':3,'quartic':4,'quintic':5}[family]
    if family=='sine':return 1-math.cos(math.pi*t/2)
    if family=='exponential':return 0. if t==0 else 2**(10*(t-1))
    if family=='circular':return 1-math.sqrt(max(0.,1-t*t))
    if family=='back':return t**3-t*math.sin(math.pi*t)
    if family=='bounce':return 1-bounce_out(1-t)
    if family=='elastic':return math.sin(6.5*math.pi*t)*2**(10*(t-1))
    raise ValueError('Unknown easing family')


def easing(family,mode,t):
    if mode=='in':return ease_in(family,t)
    if mode=='out':return 1-ease_in(family,1-t)
    return ease_in(family,2*t)/2 if t<.5 else 1-ease_in(family,2-2*t)/2


def reference_words(model,inputs):
    _model(model);inputs=tuple(inputs)
    if not inputs or len(inputs)%2 or len(inputs)>32768:raise ValueError('Expected bounded stereo words')
    for w in inputs:
        if type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000:raise ValueError('Finite binary32 inputs required')
        t=value(w)
        if model<536:
            if not 0<=t<=1:raise ValueError('Normalized phase domain0..1 required')
        elif t!=math.trunc(t)or not(-8<=t<=8 if model in(536,537,538)else 0<=t<=15)or(model==538 and t==0):
            raise ValueError('Small exact integer operands/nonzero divisors required')
    def scalar(t,lane):
        if model<530:
            family=FAMILIES[(model-500)//3];mode=MODES[(model-500)%3];return easing(family,mode,t)
        if model==530:return .5*(1-math.cos(2*math.pi*t))
        if model==531:return .54-.46*math.cos(2*math.pi*t)
        if model==532:return .42-.5*math.cos(2*math.pi*t)+.08*math.cos(4*math.pi*t)
        if model==533:return 1-(2*t-1)**2
        if model==534:return -1+2*t if lane==0 else 1-2*t
        if model==535:return -math.cos(math.pi*t)if lane==0 else math.cos(math.pi*t)
        raise ValueError('Not a scalar phase model')
    result=[]
    for n in range(0,len(inputs),2):
        a,b=(value(w)for w in inputs[n:n+2])
        if model in(536,539):pair=(int(a)+int(b),int(b)+int(a))
        elif model==537:pair=(int(a)*int(b),int(b)*int(a))
        elif model==538:pair=(int(a)-math.trunc(a/b)*int(b),int(b)-math.trunc(b/a)*int(a))
        else:pair=(scalar(a,0),scalar(b,1))
        result.extend(word(x)for x in pair)
    return tuple(result)
