# SPDX-License-Identifier: MIT
"""Independent bounded twenty-block signal-state equations and ideal screens.

One-pole is the ideal first-order difference equation, evaluated in Float64
and rounded only for emitted comparison words, not a target Float32 replay.
Counters use integer count/carry mathematics with reset-held stop semantics.
Normalize uses a running absolute peak with the primary stored floor RN32(1e-6).
On/off toggles once per callback, first output1 from initially false state.
Up/down is deferred until a meaningful independent transient contract exists.
"""
import math
import struct

BLOCK_FRAMES = 256
REFERENCE_CALL_COUNT = 20
MODEL_NAMES = {900:'onepole-linear-fixed',901:'onepole-linear-signal-cutoff',
               902:'onoff-block-toggle',903:'counter-count-and-flag',
               904:'counter-count-and-carry-count',905:'normalize-fixed-max',
               906:'normalize-signal-max'}
MODELS = frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES = {m:2e-6 if m in(900,901) else 0 for m in MODELS}


def word(x):
    return struct.unpack('<I',struct.pack('<f',x))[0]


def value(w):
    return struct.unpack('<f',struct.pack('<I',w))[0]


NORMALIZE_INITIAL_PEAK = value(word(1e-6))
DATA = (0.,.0625,-.125,.25,-.25,.125,-0.,-.5,
        .25,-.0625,.5,-.125,.125,-1.,1.,.0625)
SMALL = tuple(x/4 for x in DATA)


def _model(model):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown RNBO signal-state-followup model')


def input_words(frames=256):
    return case_input_words(900,frames)


def case_input_words(model,frames=256):
    _model(model)
    if type(frames) is not int or frames != BLOCK_FRAMES:
        raise ValueError('Signal-state references require256-frame vectors')
    words = []
    for n in range(frames):
        if model == 901:
            pair = (SMALL[n%16],.25 if (n//31)%2==0 else .5)
        elif model in(903,904):
            pair = ((1.,1.,0.,1.,1.,0.,0.,1.)[n%8],float(n in(31,129)))
        elif model == 906:
            pair = (DATA[n%16],(.25,.5,.75,1.)[(n//7)%4])
        else:
            source = SMALL if model in(900,902) else DATA
            pair = (source[n%16],source[(n*3+1)%16])
        words.extend(word(x) for x in pair)
    return tuple(words)


def _inputs(model,inputs):
    inputs = tuple(inputs)
    if len(inputs) != 512:
        raise ValueError('Expected one interleaved256-frame input vector')
    for i,w in enumerate(inputs):
        if type(w) is not int or not 0 <= w <= 0xffffffff or (w&0x7f800000)==0x7f800000:
            raise ValueError('Finite binary32 inputs required')
        x=value(w)
        if model in(903,904):valid=x in(0.,1.)
        elif model==901 and i%2:valid=x in(.25,.5)
        elif model==906 and i%2:valid=x in(.25,.5,.75,1.)
        else:valid=abs(x) <= (.25 if model in(900,901,902) else 1)
        if not valid:raise ValueError('Input exceeds the predeclared scenario domain')
    return inputs


def reference_blocks(model,inputs,call_count=20):
    _model(model)
    if type(call_count) is not int or not 1 <= call_count <= REFERENCE_CALL_COUNT:
        raise ValueError('Invalid continuous callback count')
    inputs=_inputs(model,inputs)
    data=tuple(value(w) for w in inputs)
    filter_state=[0.,0.]
    running_peak=[NORMALIZE_INITIAL_PEAK,NORMALIZE_INITIAL_PEAK]
    count=0;carry_count=0
    blocks=[]
    for call in range(call_count):
        block=[]
        for frame in range(BLOCK_FRAMES):
            x,y=data[2*frame:2*frame+2]
            if model==900:
                for ch,(sample,alpha) in enumerate(((x,.25),(y,.5))):
                    filter_state[ch]=alpha*sample+(1-alpha)*filter_state[ch]
                pair=filter_state
            elif model==901:
                filter_state[0]=y*x+(1-y)*filter_state[0]
                pair=(filter_state[0],y)
            elif model==902:
                pair=(float(call%2==0),)*2
            elif model in(903,904):
                flag=0
                if y!=0:
                    count=0;carry_count=0
                else:
                    count+=int(x)
                    if count>=7:
                        count-=7;carry_count+=1;flag=1
                pair=(count,flag if model==903 else carry_count)
            elif model==905:
                pair=[]
                for ch,(sample,maximum) in enumerate(((x,.5),(y,1.))):
                    running_peak[ch]=max(running_peak[ch],abs(sample))
                    pair.append(sample*maximum/running_peak[ch])
            elif model==906:
                running_peak[0]=max(running_peak[0],abs(x))
                pair=(x*y/running_peak[0],y)
            else:
                raise AssertionError('Unreachable model')
            block.extend(word(v) for v in pair)
        blocks.append(tuple(block))
    return tuple(blocks)


def reference_words(model,inputs):
    return reference_blocks(model,inputs,1)[0]
