# SPDX-License-Identifier: MIT
"""Independent finite comparison/logic models, without generated DSP input.

Step follows the documented first >= second rule. Sign's reference zero is
canonical +0; output zero signs remain separately recorded diagnostics.
"""
import math
import struct

MODELS = {11:'not-equal',12:'greater',13:'greater-equal',14:'less-equal',
          15:'logical-and',16:'logical-or',17:'logical-xor',18:'logical-not',
          19:'boolean',20:'documented-step',21:'sign',22:'conditional-selection'}


def expected_outputs(model,planes):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown Gen logic model')
    if type(planes) not in (list,tuple) or len(planes)!=2:
        raise ValueError('Expected two input planes')
    left,right=tuple(planes[0]),tuple(planes[1])
    if len(left)!=len(right) or not 1<=len(left)<=16384:
        raise ValueError('Invalid input span')
    for plane in (left,right):
        for value in plane:
            if (type(value) is not float or not math.isfinite(value) or not -1<=value<=1 or
                    struct.unpack('<f',struct.pack('<f',value))[0]!=value):
                raise ValueError('Input must be an exact finite binary32 wire in [-1,1]')
    def op(x,y):
        if model==11:return float(x!=y)
        if model==12:return float(x>y)
        if model==13:return float(x>=y)
        if model==14:return float(x<=y)
        if model==15:return float(x!=0 and y!=0)
        if model==16:return float(x!=0 or y!=0)
        if model==17:return float((x!=0)!=(y!=0))
        if model==18:return float(x==0)
        if model==19:return float(x!=0)
        if model==20:return float(x>=y)
        if model==21:return 1. if x>0 else -1. if x<0 else 0.
        return y if x!=0 else -y
    return (tuple(op(a,b) for a,b in zip(left,right)),
            tuple(op(b,a) for a,b in zip(left,right)))


def cache_bytes(planes):
    return b''.join(struct.pack('<ff',a,b) for a,b in zip(*planes))
