# SPDX-License-Identifier: MIT
"""Predeclared bounded language contracts; no generated DSP algorithms.

Branch side effects are absolute prefix counts, loops use closed-form sums,
and lifecycle observations are scoped to one fresh initialize/prepare epoch.
No reset, sample-rate change or subsequent DSP restart is qualified here.
"""
import struct

NAMES=('declarations','typed-declarations','lexical-shadow','precedence','if-else',
 'ternary-state','logical-and-state','logical-or-state','switch','switch-fallthrough',
 'for-bounded','for-nested','for-break-continue','while-bounded','do-while-bounded',
 'function-scalar','function-list','state-delay','state-independent','param-default',
 'hook-init','hook-startup','hook-dspsetup','hook-combined')
MODEL_NAMES={1300+i:name for i,name in enumerate(NAMES)}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:0 for m in MODELS}
GRID=(-1.,-.875,-.75,-.625,-.5,-.375,-.25,-0.,0.,.125,.25,.375,.5,.625,.75,1.)

def word(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def case_input_words(model,frames=256):
    if type(model)is not int or model not in MODELS or type(frames)is not int or frames!=256:
        raise ValueError('Unknown codebox structure vector')
    return tuple(w for n in range(frames) for w in
        (word((n//16)%6 if 1308<=model<=1314 else GRID[n//16]),word(GRID[n%16])))
def input_words(frames=256):return case_input_words(1300,frames)

def reference_blocks(model,inputs,call_count=20):
    if type(model)is not int or model not in MODELS or type(call_count)is not int or not 1<=call_count<=20:
        raise ValueError('Unknown codebox structure model/count')
    inputs=tuple(inputs)
    if inputs!=case_input_words(model):raise ValueError('Structure vector differs from declared inputs')
    pairs=[tuple(map(value,inputs[i:i+2]))for i in range(0,512,2)]
    positives=[0];nonpositives=[0]
    for x,y in pairs:
        positives.append(positives[-1]+int(x>0));nonpositives.append(nonpositives[-1]+int(x<=0))
    result=[]
    for call in range(call_count):
        block=[]
        for frame,(x,y)in enumerate(pairs):
            n=call*256+frame;p=call*positives[-1]+positives[frame];q=call*nonpositives[-1]+nonpositives[frame]
            if model in (1300,1301,1315):pair=(x+2*y,x-2*y)
            elif model==1302:pair=(x+3*y,x)
            elif model==1303:pair=(x+2*y,(x+y)*2)
            elif model==1304:pair=(x+2*y if x>0 else x-2*y if x<0 else y,y)
            elif model==1305:pair=(p+int(x>0) if x>0 else q+int(x<=0),p+q+1)
            elif model==1306:pair=(int(x>0),p+int(x>0))
            elif model==1307:pair=(1,q+int(x<=0))
            elif model==1308:pair=((10,20,30,40,40,40)[int(x)]+y,y)
            elif model==1309:pair=((6,5,3,8,8,8)[int(x)]+y,y)
            elif model==1310:pair=(x*(x+1)/2*y,y)
            elif model==1311:pair=(3*x*(x+1)/2*y,y)
            elif model==1312:pair=((0,1,3,3,7,7)[int(x)]*y,y)
            elif model==1313:pair=(x*(x-1)*(2*x-1)/6*y,y)
            elif model==1314:
                k=max(1,x);pair=(k*(k+1)/2*y,y)
            elif model==1316:pair=(x+y,x-y)
            elif model==1317:pair=(.25,-.5)if n==0 else pairs[(n-1)%256]
            elif model==1318:pair=(p+.25,q-.5)
            elif model==1319:pair=(.25*x,.25*y)
            elif model in (1320,1321,1322):pair=(1+x,y)
            elif model==1323:pair=(111+x,1+y)
            else:raise AssertionError('Missing codebox structure reference')
            block.extend(word(v)for v in pair)
        result.append(tuple(block))
    return tuple(result)
