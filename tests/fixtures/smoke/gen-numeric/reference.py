# SPDX-License-Identifier: MIT
"""Short independent functional vectors; no generated DSP is evaluated here."""
from fractions import Fraction
import math
import struct

MAGNITUDES=(0,1,2,0x003fffff,0x00400000,0x007ffffe,0x007fffff,0x00800000,0x00800001,
    0x3e7fffff,0x3e800000,0x3e800001,0x3effffff,0x3f000000,0x3f000001,
    0x3f7fffff,0x3f800000,0x3f800001,0x3fbfffff,0x3fc00000,0x3fc00001,
    0x3fffffff,0x40000000,0x40000001,0x407fffff,0x40800000,0x40800001,
    0x4a7fffff,0x4a800000,0x4a800001,0x4affffff,0x4b000000,0x4b000001,
    0x4b7fffff,0x4b800000,0x4b800001,0x4effffff)
WORDS=(*MAGNITUDES,*(word|0x80000000 for word in MAGNITUDES),0xcf000000)
MODELS=frozenset(range(23,35))


def value(word):
    return struct.unpack('<f',struct.pack('<I',word))[0]


def word(value):
    return struct.unpack('<I',struct.pack('<f',value))[0]


def input_words(frames=256):
    if type(frames)is not int or not 1<=frames<=16384:
        raise ValueError('Invalid functional vector length')
    return tuple(w for n in range(frames) for w in (WORDS[n%75],WORDS[(n+29)%75]))


def _nearest_away(x,base):
    quotient=Fraction(x)/Fraction(base)
    magnitude=abs(quotient)
    integral=(2*magnitude.numerator+magnitude.denominator)//(2*magnitude.denominator)
    return float((-integral if quotient<0 else integral)*Fraction(base))


def reference_words(model,source):
    if type(model)is not int or model not in MODELS:
        raise ValueError('Unknown functional model')
    source=tuple(source)
    if not source or len(source)%2:raise ValueError('Expected stereo input words')
    for w in source:
        if (type(w)is not int or not 0<=w<=0xffffffff or (w&0x7f800000)==0x7f800000 or
                not -2147483648<=value(w)<=2147483520):
            raise ValueError('Input is outside the common finite Int32-safe domain')
    def operation(a,b):
        x,y=value(a),value(b)
        if model==29:return a^0x80000000
        if model==32:return a
        subnormal=(a&0x7f800000)==0 and (a&0x007fffff)!=0
        if model==33:return 0x3f800000 if subnormal else 0
        if model==34:return 0 if subnormal else a
        if model==23:result=float(math.floor(x))
        elif model==24:result=float(math.ceil(x))
        elif model in (25,31):result=float(math.trunc(x))
        elif model in (26,27):result=_nearest_away(x,1 if model==26 else Fraction(1,2))
        elif model==28:result=x-math.trunc(x)  # explicitly signed fraction convention
        else:result=abs(x-y)
        return 0 if result==0 else word(result)
    return tuple(w for n in range(0,len(source),2)
        for w in (operation(source[n],source[n+1]),operation(source[n+1],source[n])))
