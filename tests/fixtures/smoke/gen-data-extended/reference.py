# SPDX-License-Identifier: MIT
"""Independent Gen local table, index, phase and weighted-write contracts.

Eight-cell phase periods, inclusive lookup endpoints, sample-age oscillator
phase and per-neighbor splat weights are predeclared conventions where prose
does not fully resolve boundaries. Float32 producer storage stays unchanged;
models use ideal sums/recurrences and one binary32 observation conversion.
"""
import math
import struct

NAMES=('wave-samples','wave-phase','wave-section','lookup-signal','lookup-samples',
 'cycle-phase','cycle-frequency','cycle-local-positional','cycle-local-name',
 'splat-isolated','splat-accum','splat-mix-half','splat-phase',
 'peek-bound-ignore','peek-bound-wrap','peek-bound-clamp','peek-bound-fold','peek-bound-mirror',
 'peek-channel-ignore','peek-channel-wrap','peek-channel-clamp','peek-channel-fold','peek-channel-mirror',
 'peek-return-index','sample-return-index','read-global-delay','write-global-delay',
 'Buffer-external','buffer-lowercase','data-lowercase','cycle-frequency-long-period')
MODEL_NAMES={1600+i:name for i,name in enumerate(NAMES)}
MODELS=frozenset(MODEL_NAMES)
TABLE=((-0.75,0.125,1.,-0.5,0.25,0.875,-0.125,0.625),
       (0.5,-1.,0.25,0.75,-0.25,0.125,1.,-0.875))
DATA=(0.,.125,-.0625,.25,-.125,-0.,.0625,-.25,0.,-.125,.25,.125,-.25,.0625,-.0625,.125)
ABSOLUTE_TOLERANCES={m:2e-6 if m in(1602,1603,1605,1606,1607,1608,1611,1624,1630)else 0 for m in MODELS}

def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def name(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown extended Gen data model')
    return MODEL_NAMES[model]
def case_input_words(model,frames=256):
    name(model)
    if type(frames)is not int or frames!=256:raise ValueError('Extended Gen data vector requires256frames')
    result=[]
    for n in range(frames):
        if model in(1600,1604,1623):pair=((n%29)/4,((n*7+3)%29)/4)
        elif model in(1601,1605,1607,1608,1624):pair=((n%11-1)/8,((n*3+2)%11-1)/8)
        elif model==1602:pair=((n%17)/16,((n*7+3)%17)/16)
        elif model==1603:pair=(-1+(n%33)/16,-1+((n*7+3)%33)/16)
        elif model==1606:pair=(5512.5,-2756.25)
        elif model==1630:pair=(86.1328125,-43.06640625)
        elif model in(1609,1610,1611):pair=(DATA[n%16],((n*5+3)%28)/4)
        elif model==1612:pair=(DATA[n%16],((n*5+3)%32)/32)
        elif 1613<=model<=1617:pair=(n%16-4,(n*5+3)%16-4)
        elif 1618<=model<=1622:pair=(n%8,(n//8)%7-2)
        else:pair=(DATA[n%16],DATA[(n*5+3)%16])
        result.extend(word(v)for v in pair)
    return tuple(result)
def input_words(frames=256):return case_input_words(1600,frames)

def bounded(k,length,mode):
    if mode=='ignore':return k if 0<=k<length else None
    if mode=='clamp':return max(0,min(length-1,k))
    if mode=='wrap':return k%length
    if mode=='fold':
        q=k%(2*(length-1));return q if q<length else 2*(length-1)-q
    if mode=='mirror':
        q=k%(2*length);return q if q<length else 2*length-1-q
    raise ValueError('Unknown boundary policy')
def table_sample(ch,index,mode='clamp',linear=True):
    lo=math.floor(index);fraction=index-lo
    def at(i):
        k=bounded(i,8,mode);return 0. if k is None else TABLE[ch][k]
    return at(lo)*(1-fraction)+at(lo+1)*fraction if linear else at(lo)

def reference_blocks(model,inputs,call_count=20):
    identity=name(model)
    if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Extended Gen data requires1..20calls')
    inputs=tuple(inputs)
    if inputs!=case_input_words(model):raise ValueError('Extended Gen data vector differs from authored domain')
    pairs=[tuple(map(value,inputs[i:i+2]))for i in range(0,512,2)]
    prefix=[0.]
    for x,y in pairs:prefix.append(prefix[-1]+x)
    smoothed=[0.,0.];blocks=[]
    for call in range(call_count):
        block=[]
        for frame,(x,y)in enumerate(pairs):
            n=call*256+frame
            if model in(1600,1604):pair=(table_sample(0,x),table_sample(1,y))
            elif model in(1601,1607,1608):pair=(table_sample(0,8*x,'wrap'),table_sample(1,8*y,'wrap'))
            elif model==1602:pair=(table_sample(0,1+5*x),table_sample(1,1+5*y))
            elif model==1603:pair=(table_sample(0,7*(x+1)/2),table_sample(1,7*(y+1)/2))
            elif model==1605:pair=(math.cos(2*math.pi*x),math.cos(2*math.pi*y))
            elif model==1606:pair=(math.cos(2*math.pi*(n%8)/8),math.cos(2*math.pi*(-n%16)/16))
            elif model==1630:pair=(math.cos(2*math.pi*(n%512)/512),math.cos(2*math.pi*(-n%1024)/1024))
            elif model in(1609,1612):
                coordinate=y if model==1609 else 8*y
                f=coordinate-math.floor(coordinate);pair=((1-f)*x,f*x)
            elif model==1610:
                total=call*prefix[-1]+prefix[frame+1];pair=(.75*total,.25*total)
            elif model==1611:
                for ch,w in enumerate((.75,.25)):smoothed[ch]+=.5*w*(x-smoothed[ch])
                pair=tuple(smoothed)
            elif 1613<=model<=1617:
                mode=identity.split('-')[-1];pair=(table_sample(0,x,mode,False),table_sample(1,y,mode,False))
            elif 1618<=model<=1622:
                mode=identity.split('-')[-1];ch=bounded(int(y),2,mode)
                pair=(0. if ch is None else TABLE[ch][int(x)],y)
            elif model==1623:pair=(table_sample(0,x,linear=False),x)
            elif model==1624:pair=(table_sample(0,8*x,'wrap'),8*x)
            elif model in(1625,1626):pair=(0. if n<2 else pairs[(n-2)%256][0],y)
            elif model in(1627,1628):pair=(0.,0.)  # empty external binding only, normally rejected by admission
            elif model==1629:pair=(8.,2.)
            else:raise AssertionError('Missing extended Gen data reference')
            block.extend(word(v)for v in pair)
        blocks.append(tuple(block))
    return tuple(blocks)
