# SPDX-License-Identifier: MIT
"""Independent binary32 constants for a short autonomous RNBO stereo check.

Mathematical values come from Python's independent Float64 mathematics and are
rounded once to binary32. The fixed wrapper configuration is44100Hz/256frames.
The sig~ fixture checks its explicitly authored initial values (.25,-.5), not
message updates, impulses, arbitrary numeric storage or within-block events.
Declared FX inputs vary but all tested operators intentionally ignore them.
"""
import math
import struct

RATE=44100
BLOCK_FRAMES=256
MODEL_NAMES={200:'pi-over-two',201:'pi-over-four',202:'e',203:'inverse-pi',
             204:'golden-ratio',205:'pi',206:'sqrt-one-half',207:'sqrt-two',
             208:'two-pi',209:'sig-initial-stereo',210:'configured-sample-rate',211:'configured-vector-size'}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={model:0 for model in MODELS}
VALUES={200:math.pi/2,201:math.pi/4,202:math.e,203:1/math.pi,204:(1+math.sqrt(5))/2,
        205:math.pi,206:math.sqrt(.5),207:math.sqrt(2),208:2*math.pi,210:RATE,211:BLOCK_FRAMES}


def word(value):
    return struct.unpack('<I',struct.pack('<f',value))[0]


def value(bits):
    return struct.unpack('<f',struct.pack('<I',bits))[0]


WORDS=tuple(word(x)for x in(-4.,-2.,-1.5,-1.,-.75,-.5,-.25,-0.,0.,.25,.5,.75,1.,1.5,2.,4.))


def _model(model):
    if type(model)is not int or model not in MODELS:
        raise ValueError('Unknown autonomous constant model')


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
    pair=(word(.25),word(-.5))if model==209 else(word(VALUES[model]),)*2
    return pair*(len(inputs)//2)
