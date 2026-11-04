# SPDX-License-Identifier: MIT
"""Independent bounded list algebra and five-cell circular array references.

No target-derived values. Each list starts fresh per sample. Array expectations
use absolute sample age and explicit initializer values, not a replayed index
state. Inputs and outputs are exactly representable in binary32; integer writes
use truncation within representable range, without overflow assumptions.
"""
import math
import struct

METHODS=('push','pop','shift','concat','fill','unshift','splice','slice','includes','indexOf','reverse')
ARRAYS=('FixedInt8Array','FixedUint8Array','FixedInt16Array','FixedUint16Array','FixedInt32Array','FixedUint32Array','FixedFloat32Array','FixedFloat64Array','FixedBigInt64Array','FixedBigUint64Array','FixedSampleArray','FixedNumberArray','FixedIntArray','FixedFloatArray','FixedDoubleArray','FixedUIntArray','FixedTimeArray')
MODEL_NAMES={1000+i:n for i,n in enumerate(METHODS+ARRAYS)}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:0 for m in MODELS}
BLOCK_FRAMES=256
REFERENCE_CALL_COUNT=20
BASE=(1.,2.,3.,2.,5.)

def word(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def unsigned(name):return 'Uint' in name or 'UInt' in name

def case_input_words(model,frames=256):
    if type(model)is not int or model not in MODELS or frames!=256:raise ValueError('Unknown bounded container vector')
    name=MODEL_NAMES[model];out=[]
    for n in range(frames):
        x=n%7 if model<1011 else n%32 if unsigned(name) else (n%32-16)/4
        out.extend((word(x),word((n*5+3)%7)))
    return tuple(out)

def input_words(frames=256):return case_input_words(1000,frames)
def checksum(a):return sum((i+1)*v for i,v in enumerate(a))
def list_result(name,x,y):
    # First cell depends on this sample, preventing vector-level literal hoisting.
    base=(x,2.,3.,2.,5.)
    if name=='push':return 6,checksum((*base,y))
    if name=='pop':return 5,checksum(base[:-1])
    if name=='shift':return x,checksum(base[1:])
    if name=='concat':return checksum((*base,x,y)),checksum(base)
    if name=='fill':return 15*x,15*x
    if name=='unshift':return 6,checksum((y,*base))
    if name=='splice':return 2+2*3,checksum((x,x,2,5))
    if name=='slice':return checksum((2,3,2)),checksum(base)
    if name=='includes':return float(y in base),checksum(base)
    if name=='indexOf':return next((i for i,v in enumerate(base)if v==y),-1),checksum(base)
    if name=='reverse':return checksum(base[::-1]),checksum(base[::-1])
    raise ValueError('Unknown list method')

def reference_blocks(model,inputs,call_count=20):
    if type(model)is not int or model not in MODELS or type(call_count)is not int or not 1<=call_count<=20:
        raise ValueError('Unknown container model/count')
    inputs=tuple(inputs)
    if inputs!=case_input_words(model):raise ValueError('Container inputs differ from predeclared exact vector')
    name=MODEL_NAMES[model];blocks=[]
    def written(n):
        x=value(inputs[2*(n%256)])
        return math.trunc(x) if model>=1011 and 'Float'not in name and name not in('FixedSampleArray','FixedNumberArray','FixedDoubleArray','FixedTimeArray') else x
    for call in range(call_count):
        out=[]
        for frame in range(256):
            n=256*call+frame;x,y=map(value,inputs[2*frame:2*frame+2])
            if model<1011:pair=list_result(name,x,y)
            else:pair=written(n),float(n+2) if n<4 else written(n-4)
            out.extend(word(v)for v in pair)
        blocks.append(tuple(out))
    return tuple(blocks)
