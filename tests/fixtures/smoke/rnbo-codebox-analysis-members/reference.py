# SPDX-License-Identifier: MIT
"""Independent window sums, absolute-age cosines and declared noise screens.

No generated running-sum, table lookup or random algorithm is an oracle.
Startup and a changed window start a fresh available-sample epoch. A reset pulse
is isolated, while explicit reset() schedules include consecutive calls.
Oscillator phase is the current/old phase before the next sample increment.
"""
import math
import struct
AVERAGES=('average','average_absolute','average_rms')
VARIANTS=('next','reset','input-reset','window-change')
ROWS=tuple((o,v)for o in AVERAGES for v in VARIANTS)+(('cycle','next'),('cycle','reset'),('cycle','phase-output'),('cycle','phase-index'),('noise','next'),('noise','reset'),('noise','seed'))+tuple((o,'window-change-named-list')for o in AVERAGES)
MODEL_NAMES={1800+i:o+'-'+v for i,(o,v)in enumerate(ROWS)}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:0 if 1816<=m<=1818 else 2e-6 for m in MODELS}
GRID=(-1.,-.75,-.5,-.25,-.125,-0.,0.,.125,.25,.375,.5,.625,.75,.875,1.,.25)
BLOCK_FRAMES=256
REFERENCE_CALL_COUNT=20

def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def row(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown analysis-member model')
    return ROWS[model-1800]
def reset_at(n,ch):return n%(257 if ch==0 else 263)in((37,38)if ch==0 else(91,92))or n in((255,256)if ch==0 else(511,512))
def pulse_at(n,ch):return n%(257 if ch==0 else 263)==(37 if ch==0 else 91)or n==(255 if ch==0 else 511)
def window_at(n,ch,changing):return ((8,5,3)if ch==0 else(16,7,4))[(n//(73 if ch==0 else 91))%3]if changing else(8 if ch==0 else 16)
def case_input_words(model,frames=256):
    row(model)
    if type(frames)is not int or frames!=256:raise ValueError('Expected256 frames')
    return tuple(word(v)for n in range(frames)for v in(GRID[(n//16+n%16)%16],GRID[(n*5+3)%16]))
def input_words(frames=256):return case_input_words(1800,frames)
def reference_blocks(model,inputs,call_count=20):
    owner,variant=row(model)
    if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Expected1..20 calls')
    inputs=tuple(inputs)
    if inputs!=case_input_words(model):raise ValueError('Analysis-member vector differs from authored finite words')
    pairs=[tuple(map(value,inputs[i:i+2]))for i in range(0,512,2)]
    epochs=[0,0];windows=[None,None];blocks=[]
    for call in range(call_count):
        output=[]
        for frame,(x,y)in enumerate(pairs):
            age=call*256+frame
            if owner=='noise':result=(1,1)
            elif owner=='cycle':
                if variant=='reset':
                    for ch in(0,1):
                        if reset_at(age,ch):epochs[ch]=age
                if variant=='phase-index':result=(math.cos(2*math.pi*x),math.cos(2*math.pi*y))
                elif variant=='phase-output':result=((age%512)/512,(age%1024)/1024)
                else:result=tuple(math.cos(2*math.pi*((age-epochs[ch])/(512 if ch==0 else 1024)+(0 if ch==0 else .25)))for ch in(0,1))
            else:
                values=[]
                for ch in(0,1):
                    w=window_at(age,ch,variant.startswith('window-change'))
                    if w!=windows[ch]or(variant=='reset'and reset_at(age,ch))or(variant=='input-reset'and pulse_at(age,ch)):epochs[ch]=age
                    windows[ch]=w;start=max(epochs[ch],age-w+1)
                    samples=[pairs[k%256][ch]for k in range(start,age+1)]
                    if owner=='average_absolute':samples=[abs(v)for v in samples]
                    if owner=='average_rms':samples=[v*v for v in samples]
                    v=math.fsum(samples)/len(samples)
                    values.append(math.sqrt(v)if owner=='average_rms'else v)
                result=tuple(values)
            output.extend(word(v)for v in result)
        blocks.append(tuple(output))
    return tuple(blocks)
