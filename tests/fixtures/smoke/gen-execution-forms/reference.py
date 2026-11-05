# SPDX-License-Identifier: MIT
"""Predeclared bounded grammar models and basic execution screens.

FFT/noise flags are screens only, not independent numeric FFT or RNG oracles.
No noise sequence, FFT default numeric constant, distribution or pfft context
is qualified. Compound state uses absolute sample-age prefix/parity formulas.
"""
import struct
NAMES=('noise','FFTSIZE','fftsize','FFTOFFSET','fftoffset','FFTHOP','ffthop','FFTFULLSPECT','fftfullspect',
       'fftinfo-size','fftinfo-hop-flag','fftinfo-offset',
       '+=','*=','-=','/=','%=','&=','|=','^=','<<=','>>=','history-+=','history-*=')
MODEL_NAMES={1700+i:n for i,n in enumerate(NAMES)}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:0 for m in MODELS}
BLOCK_FRAMES=256
REFERENCE_CALL_COUNT=20

def word(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def case_input_words(model,frames=256):
    if type(model)is not int or model not in MODELS or type(frames)is not int or frames!=256:raise ValueError('Unknown Gen execution vector')
    result=[]
    for n in range(frames):
        x=n//16-8;y=n%16+1
        if model==1716 or model>=1717 and model<=1721:x=n//16  # nonnegative modulus/bitwise domain
        if model in(1720,1721):y=n%4
        if model==1722:x=1 if n==0 else 0
        if model==1723:x=-1 if n==0 else 1
        result.extend((word(x),word(y)))
    return tuple(result)
def input_words(frames=256):return case_input_words(1700,frames)

def reference_blocks(model,inputs,call_count=20):
    if type(model)is not int or model not in MODELS or type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Unknown Gen execution model/count')
    inputs=tuple(inputs)
    if inputs!=case_input_words(model):raise ValueError('Gen execution inputs differ from exact authored vector')
    pairs=[tuple(map(value,inputs[i:i+2]))for i in range(0,512,2)]
    blocks=[]
    for call in range(call_count):
        output=[]
        for frame,(x,y)in enumerate(pairs):
            age=call*256+frame
            if model==1700:pair=(1,1)  # finite/range and short-window variation flags
            elif model<1712:pair=(1,1)if model in(1709,1710)else(1,y)
            elif model==1712:pair=(x+y,y)
            elif model==1713:pair=(x*y,y)
            elif model==1714:pair=(x-y,y)
            elif model==1715:pair=(x/y,y)
            elif model==1716:pair=(x%y,y)
            elif model==1717:pair=(int(x)&int(y),y)
            elif model==1718:pair=(int(x)|int(y),y)
            elif model==1719:pair=(int(x)^int(y),y)
            elif model==1720:pair=(int(x)<<int(y),y)
            elif model==1721:pair=(int(x)>>int(y),y)
            elif model==1722:pair=(((age+255)//256)/16,y)
            elif model==1723:pair=((-1)**((age+255)//256),y)
            else:raise AssertionError('Missing reference')
            output.extend(word(v)for v in pair)
        blocks.append(tuple(output))
    return tuple(blocks)
