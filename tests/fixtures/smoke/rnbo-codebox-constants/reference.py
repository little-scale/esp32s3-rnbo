# SPDX-License-Identifier: MIT
"""Independent finite RNBO codebox constant references; no GenExpr substitution.

The named-value syntax is authored separately for every exact spelling. Ideal
Float64 mathematical constants are rounded once to binary32. CHAR_0..CHAR_9
are numeric ASCII codes48..57, not digit values0..9 or string-valued globals.
Both output lanes hold the selected constant and ignore varying declared input.
No runtime clock/channel query, nonfinite value or full syntax claim is made.
"""
import math
import struct

MODEL_NAMES={250:'pi-over-two',251:'pi-over-four',252:'e',253:'inverse-pi',254:'golden-ratio',
             255:'pi',256:'sqrt-one-half',257:'sqrt-two',258:'two-pi',259:'pi-over180',
             260:'180-over-pi',261:'natural-log-two',262:'natural-log-ten',263:'log-two-e',264:'log-ten-e'}
MODEL_NAMES.update({265+n:'ascii-digit-'+str(n)for n in range(10)})
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={model:0 for model in MODELS}
VALUES={250:math.pi/2,251:math.pi/4,252:math.e,253:1/math.pi,254:(1+math.sqrt(5))/2,
        255:math.pi,256:math.sqrt(.5),257:math.sqrt(2),258:2*math.pi,259:math.pi/180,
        260:180/math.pi,261:math.log(2),262:math.log(10),263:1/math.log(2),264:1/math.log(10)}
VALUES.update({265+n:ord(str(n))for n in range(10)})


def word(value):
    return struct.unpack('<I',struct.pack('<f',value))[0]


def value(bits):
    return struct.unpack('<f',struct.pack('<I',bits))[0]


WORDS=tuple(word(x)for x in(-4.,-2.,-1.5,-1.,-.75,-.5,-.25,-0.,0.,.25,.5,.75,1.,1.5,2.,4.))


def _model(model):
    if type(model)is not int or model not in MODELS:
        raise ValueError('Unknown codebox numeric constant model')


def input_words(frames=256):
    if type(frames)is not int or not 1<=frames<=16384:
        raise ValueError('Invalid functional vector length')
    return tuple(w for frame in range(frames)for w in(WORDS[(frame//16)%16],WORDS[frame%16]))


def case_input_words(model,frames=256):
    _model(model)
    return input_words(frames)


def reference_words(model,inputs):
    _model(model);inputs=tuple(inputs)
    if not inputs or len(inputs)%2 or len(inputs)>32768:
        raise ValueError('Expected bounded interleaved stereo words')
    if any(type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000 for w in inputs):
        raise ValueError('Expected finite binary32 input words')
    return(word(VALUES[model]),)*len(inputs)
