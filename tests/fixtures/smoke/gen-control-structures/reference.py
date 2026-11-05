# SPDX-License-Identifier: MIT
"""Predeclared Gen finite selection, declarations and sample-state references.

Pass comparators multiply the first operand by the predicate (primary metadata).
Loop results use polynomial sums; delay and branch state use absolute sample
age/prefix counts, not generated algorithms. No within-block host event claim.
"""
import struct
import operator

PAIRS=(('eqp','==p'),('neqp','!=p'),('ltp','<p'),('ltep','<=p'),('gtp','>p'),('gtep','>=p'))
NAMES=tuple(n for pair in PAIRS for n in pair)+('param','Param','elapsed','ELAPSED','voice','VOICE','constant','history',
 'function-tuple','function-history','for-bounded','while-bounded','for-break-continue','if-history')
MODEL_NAMES={1100+i:name for i,name in enumerate(NAMES)}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:0 for m in MODELS}
BLOCK_FRAMES=256
REFERENCE_CALL_COUNT=20
GRID=(-1.,-.875,-.75,-.625,-.5,-.375,-.25,-0.,0.,.125,.25,.375,.5,.625,.75,1.)
PREDICATES=(operator.eq,operator.ne,operator.lt,operator.le,operator.gt,operator.ge)

def word(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def case_input_words(model,frames=256):
    if type(model)is not int or model not in MODELS or type(frames)is not int or frames!=256:raise ValueError('Unknown Gen control vector')
    result=[]
    for n in range(frames):
        x=(n//16)%6 if model in(1122,1123,1124)else GRID[n//16]
        y=GRID[n%16]
        result.extend((word(x),word(y)))
    return tuple(result)
def input_words(frames=256):return case_input_words(1100,frames)

def reference_blocks(model,inputs,call_count=20):
    if type(model)is not int or model not in MODELS or type(call_count)is not int or not 1<=call_count<=20:
        raise ValueError('Unknown Gen control model/count')
    inputs=tuple(inputs)
    if inputs!=case_input_words(model):raise ValueError('Gen control inputs differ from predeclared exact vector')
    pairs=[tuple(map(value,inputs[i:i+2]))for i in range(0,512,2)]
    prefix=[0]
    for x,y in pairs:prefix.append(prefix[-1]+int(x>0)-int(x<0))
    blocks=[]
    for call in range(call_count):
        output=[]
        for frame,(x,y)in enumerate(pairs):
            n=call*256+frame
            if model<1112:
                p=PREDICATES[(model-1100)//2];pair=(x*int(p(x,y)),y*int(p(y,x)))
            elif model in(1112,1113):pair=(.25*x,.25*y)
            elif model in(1114,1115):pair=(n,y)
            elif model in(1116,1117):pair=(1,y)  # documented non-polyphonic value
            elif model==1118:pair=(.375,-.625)
            elif model in(1119,1121):
                if n==0:pair=(.25,-.5)if model==1119 else(.25,.25)
                else:pair=pairs[(n-1)%256]
            elif model==1120:pair=(x+2*y,x-2*y)
            elif model==1122:pair=(x*(x+1)/2*y,y)
            elif model==1123:pair=(x*(x-1)*(2*x-1)/6*y,y)
            elif model==1124:pair=((x*(x+1)/2-(3 if x>2 else 0))*y,y)
            elif model==1125:pair=(call*prefix[-1]+prefix[frame],y)
            else:raise AssertionError('Missing reference')
            output.extend(word(v)for v in pair)
        blocks.append(tuple(output))
    return tuple(blocks)
