# SPDX-License-Identifier: MIT
"""Independent finite GenExpr named constants under the44100Hz/256frame ABI.

Math values are computed independently and rounded once to binary32. Config
queries are checked against the declared surrounding audio configuration only.
Each exact name has its own original bare-value source. No RNBO codebox/patcher,
zero-argument-call, FFT/voice/elapsed, other config or alias execution is inferred.
"""
import math
import struct

RATE=44100
BLOCK_FRAMES=256
MODEL_NAMES={400:'pi',401:'half-pi',402:'two-pi',403:'e',404:'inverse-pi',405:'golden-ratio',
             406:'sqrt-one-half',407:'sqrt-two',408:'pi-over180',409:'180-over-pi',410:'natural-log-two',
             411:'natural-log-ten',412:'log-two-e',413:'log-ten-e',414:'configured-sample-rate',415:'configured-vector-size'}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={model:0 for model in MODELS}
VALUES={400:math.pi,401:math.pi/2,402:math.pi*2,403:math.e,404:1/math.pi,405:(1+math.sqrt(5))/2,
        406:math.sqrt(.5),407:math.sqrt(2),408:math.pi/180,409:180/math.pi,410:math.log(2),
        411:math.log(10),412:1/math.log(2),413:1/math.log(10),414:RATE,415:BLOCK_FRAMES}


def word(value):return struct.unpack('<I',struct.pack('<f',value))[0]
def value(bits):return struct.unpack('<f',struct.pack('<I',bits))[0]
WORDS=tuple(word(x)for x in(-4.,-2.,-1.5,-1.,-.75,-.5,-.25,-0.,0.,.25,.5,.75,1.,1.5,2.,4.))


def _model(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown Gen named-constant model')


def input_words(frames=256):
    if type(frames)is not int or not 1<=frames<=16384:raise ValueError('Invalid functional vector length')
    return tuple(w for frame in range(frames)for w in(WORDS[(frame//16)%16],WORDS[frame%16]))


def case_input_words(model,frames=256):
    _model(model)
    return input_words(frames)


def reference_words(model,inputs):
    _model(model);inputs=tuple(inputs)
    if not inputs or len(inputs)%2 or len(inputs)>32768:raise ValueError('Expected bounded interleaved stereo words')
    if any(type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000 for w in inputs):
        raise ValueError('Expected finite binary32 input words')
    return(word(VALUES[model]),)*len(inputs)
