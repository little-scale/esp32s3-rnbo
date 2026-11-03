# SPDX-License-Identifier: MIT
"""Independent binary32 mathematics for original Gen arithmetic programs.

This does not parse or execute generated DSP. Binary64 represents both inputs
and their at-most48-bit product exactly before one binary32 output rounding.
Numerical equality is required; operation zero-sign bits remain diagnostics.
"""
import math
import struct

MODELS = {1:'absolute',2:'minimum',3:'maximum',4:'subtract',5:'equal',6:'less',9:'sum',10:'product'}


def f32(value):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('Expected a finite number')
    return struct.unpack('<f',struct.pack('<f',value))[0]


def expected_outputs(model,planes):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown Gen arithmetic model')
    if type(planes) not in (list,tuple) or len(planes)!=2:
        raise ValueError('Expected two planes')
    left,right=tuple(planes[0]),tuple(planes[1])
    if len(left)!=len(right) or not 1<=len(left)<=16384:
        raise ValueError('Invalid input span')
    for plane in (left,right):
        for x in plane:
            if type(x) is not float or not math.isfinite(x) or not -1<=x<=1 or f32(x)!=x:
                raise ValueError('Input must be a finite binary32 wire in [-1,1]')
    def op(x,y):
        if model==1:return abs(x)
        if model==2:return min(x,y)
        if model==3:return max(x,y)
        if model==4:return f32(x-y)
        if model==5:return float(x==y)
        if model==6:return float(x<y)
        if model==9:return f32(x+y)
        return f32(x*y)
    return (tuple(op(a,b) for a,b in zip(left,right)),tuple(op(b,a) for a,b in zip(left,right)))


def cache_bytes(planes):
    return b''.join(struct.pack('<ff',a,b) for a,b in zip(*planes))
