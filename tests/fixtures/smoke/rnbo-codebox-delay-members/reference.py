# SPDX-License-Identifier: MIT
"""Predeclared delay/member recurrences and explicit interpolation policies.

Manual read-before-write-before-step uses physical delay samples. Double-step
advances two cells per input sample. Fractional kernels use mathematical
Lagrange/Hermite/B-spline definitions, not emitted RNBO code. Floor selection
for step/none and physical size16 are declared where method prose is terse.
"""
import math
import struct

ROWS=(('delay','next','integer'),('delay','clear','integer'),('delay','reset','integer'),
 ('delay','read','integer'),('delay','write','overwrite'),('delay','step','double'),('delay','size','capacity'),
 ('comb','next','integer'),('comb','clear','integer'),('comb','reset','integer'),
 ('allpass','next','integer'),('allpass','clear','integer'),('allpass','reset','integer'),
 ('delay','read','linear'),('delay','read','cosine'),('delay','read','cubic'),
 ('delay','read','fastcubic'),('delay','read','spline'),('delay','read','spline6'),
 ('delay','read','step'),('delay','read','none'),('delay','next','linear-half'))
NUMERIC_ENUM_BASES=(1503,1504,1505,1513,1514,1515,1516,1517,1518,1519,1520)
ROWS=ROWS+tuple(ROWS[m-1500]for m in NUMERIC_ENUM_BASES)
NUMERIC_ENUM_MODELS=frozenset(range(1522,1533))
INTERP_ENUM={'linear':0,'cubic':1,'spline':2,'cosine':3,'step':4,'none':5,'fastcubic':6,'spline6':7}
MODELS=frozenset(range(1500,1500+len(ROWS)))
ABSOLUTE_TOLERANCES={m:0 if ROWS[m-1500][0]=='delay'and ROWS[m-1500][2]in('integer','overwrite','double','capacity','step','none')else 2e-6 for m in MODELS}
LEFT=(.125,.25,-.5,.75,-.25,1.,-.875,.375,-1.,.625,-.125,.5,-.625,.875,-.75,0.)
RIGHT=(0.,1.,1.,-0.,-1.,-1.,.5,.5,0.,.25,-.25,-.25,-1.,1.,1.,1.)

def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def row(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown delay member model')
    return ROWS[model-1500]
def reset_at(n):return n%257 in(37,38)or n in(255,256)
def case_input_words(model,frames=256):
    row(model)
    if type(frames)is not int or frames!=256:raise ValueError('Delay member vector requires256frames')
    return tuple(word(v)for n in range(frames)for v in(LEFT[n%16],RIGHT[n%16]))
def input_words(frames=256):return case_input_words(1500,frames)

def hermite(t,x,y,m0,m1):
    return(2*t**3-3*t*t+1)*x+(t**3-2*t*t+t)*m0+(-2*t**3+3*t*t)*y+(t**3-t*t)*m1
def interpolate(mode,t,points):
    if mode=='spline6':
        def basis(z):return sum((-1)**k*math.comb(6,k)*max(z+3-k,0.)**5 for k in range(7))/120
        return sum(v*basis(t-position)for v,position in zip(points,(-2,-1,0,1,2,3)))
    w,x,y,z=points
    if mode=='cubic':
        nodes=(-1,0,1,2)
        return sum(v*math.prod((t-nodes[j])/(nodes[i]-nodes[j])for j in range(4)if j!=i)for i,v in enumerate(points))
    scale=.5 if mode=='spline'else 1.
    return hermite(t,x,y,scale*(y-w),scale*(z-x))

def reference_blocks(model,inputs,call_count=20):
    owner,method,mode=row(model)
    if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Delay member reference requires1..20calls')
    inputs=tuple(inputs)
    if inputs!=case_input_words(model):raise ValueError('Delay member vector differs from declared domain')
    values=tuple(map(value,inputs));history=[];outputs=[];blocks=[]
    for call in range(call_count):
        block=[]
        for frame in range(256):
            n=call*256+frame;x=values[2*frame]
            if method in('clear','reset')and reset_at(n):history=[];outputs=[]
            age=len(history)
            def past(k):return history[age-k]if age>=k else 0.
            if owner=='comb':
                result=.5*x+.5*past(2)+.25*(outputs[age-2]if age>=2 else 0.)
            elif owner=='allpass':
                result=-.5*x+past(3)+.5*(outputs[age-3]if age>=3 else 0.)
            elif method=='size':result=16.
            elif mode in('integer','overwrite','double'):result=past(2)
            elif mode in('linear','cosine','linear-half'):result=.5*(past(2)+past(3))
            elif mode in('step','none'):result=past(3)
            elif mode in('cubic','fastcubic','spline'):result=interpolate(mode,.75,tuple(past(k)for k in(6,5,4,3)))
            elif mode=='spline6':result=interpolate(mode,.75,tuple(past(k)for k in(7,6,5,4,3,2)))
            else:raise AssertionError('Missing delay member model')
            history.append(x);outputs.append(result)
            block.extend((word(result),inputs[2*frame+1]))
        blocks.append(tuple(block))
    return tuple(blocks)
