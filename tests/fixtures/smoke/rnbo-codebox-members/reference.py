# SPDX-License-Identifier: MIT
"""Bounded member stepping and explicit reset/clear reference contracts.

Reset/clear is predeclared as restoring default zero signal history and phase.
References use mathematical recurrences, not generated methods. Where primary
prose is terse, capture phase, counter ordering and reset-to-zero are declared
screening policies; discrepancies remain results rather than fitted oracles.
"""
import math
import struct

OWNERS=('delta','change','latch','sah','slide','dcblock','accum','counter',
        'deltaclip','downsamp','zerox','zerox_count','onepole','onepole_lin','biquad','elapsed')
ROWS=tuple((owner,method)for owner in OWNERS for method in('next','reset'))+tuple((owner,'clear')for owner in('onepole','onepole_lin','biquad'))+(('history','reset'),)
MODELS=frozenset(range(1400,1400+len(ROWS)))
LEFT=(0.,.25,.25,-.5,-.5,-0.,1.,1.,-1.,-1.,.5,.5,0.,.125,.125,.75)
RIGHT=(0.,1.,1.,-0.,-1.,-1.,.5,.5,0.,.25,-.25,-.25,-1.,1.,1.,1.)
ABSOLUTE_TOLERANCES={m:2e-6 if ROWS[m-1400][0]in('slide','dcblock','onepole','onepole_lin','biquad')else 0 for m in MODELS}

def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def row(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown stateful member model')
    return ROWS[model-1400]
def reset_at(n,ch):
    return n%257 in(37,38)or n in(255,256)if ch==0 else n%263 in(91,92)or n in(511,512)
def case_input_words(model,frames=256):
    owner,method=row(model)
    if type(frames)is not int or frames!=256:raise ValueError('Member vector requires256frames')
    return tuple(word(x)for n in range(frames)for x in((1.,1.)if owner=='counter'else(LEFT[n%16],RIGHT[n%16])))
def input_words(frames=256):return case_input_words(1400,frames)

def reference_blocks(model,inputs,call_count=20):
    owner,method=row(model)
    if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Member reference requires1..20calls')
    inputs=tuple(inputs)
    if inputs!=case_input_words(model):raise ValueError('Member vector differs from authored input domain')
    vec=tuple(map(value,inputs));previous=[0.,0.];control_before=[0.,0.];state=[0.,0.]
    older_input=[0.,0.];older_output=[0.,0.];age=[0,0];crossings=[0,0];blocks=[]
    for call in range(call_count):
        block=[]
        for frame in range(256):
            n=call*256+frame
            for ch in range(2):
                x=vec[2*frame+ch];control=vec[2*frame+1-ch]
                if method!='next'and reset_at(n,ch):
                    previous[ch]=control_before[ch]=state[ch]=older_input[ch]=older_output[ch]=0.
                    age[ch]=crossings[ch]=0
                if owner=='delta':result=x-previous[ch];previous[ch]=x
                elif owner=='change':result=int(x>previous[ch])-int(x<previous[ch]);previous[ch]=x
                elif owner=='latch':
                    if control!=0:state[ch]=x
                    result=state[ch]
                elif owner=='sah':
                    threshold=0. if ch==0 else .5
                    if control_before[ch]<=threshold<control:state[ch]=x
                    control_before[ch]=control;result=state[ch]
                elif owner=='slide':
                    up,down=(2.,4.)if ch==0 else(4.,2.)
                    state[ch]+=(x-state[ch])/(up if x>state[ch]else down);result=state[ch]
                elif owner=='dcblock':
                    result=x-previous[ch]+(.5 if ch==0 else .75)*state[ch];previous[ch]=x;state[ch]=result
                elif owner=='accum':state[ch]+=x/1024;result=state[ch]
                elif owner=='counter':result=(age[ch]+1)%(7 if ch==0 else 5)
                elif owner=='deltaclip':
                    lo,hi=(-.125,.25)if ch==0 else(-.25,.125)
                    state[ch]+=max(lo,min(hi,x-state[ch]));result=state[ch]
                elif owner=='downsamp':
                    if age[ch]%(3 if ch==0 else 5)==0:state[ch]=x
                    result=state[ch]
                elif owner in('zerox','zerox_count'):
                    crossed=(x<0<previous[ch])or(x>0>previous[ch]);previous[ch]=x
                    if owner=='zerox':result=int(crossed)
                    else:
                        crossings[ch]+=int(crossed)
                        if(age[ch]+1)%(7 if ch==0 else 5)==0:state[ch]=crossings[ch];crossings[ch]=0
                        result=state[ch]
                elif owner in('onepole','onepole_lin'):
                    a=(1-math.exp(-2*math.pi*(1000 if ch==0 else 2000)/44100))if owner=='onepole'else(.25 if ch==0 else .5)
                    state[ch]+=a*(x-state[ch]);result=state[ch]
                elif owner=='biquad':
                    result=.5*x+.25*previous[ch]+.125*older_input[ch]+.25*state[ch]-.125*older_output[ch]
                    older_input[ch]=previous[ch];previous[ch]=x;older_output[ch]=state[ch];state[ch]=result
                elif owner=='elapsed':result=age[ch]
                elif owner=='history':result=previous[ch];previous[ch]=x
                else:raise AssertionError('Missing member equation')
                block.append(word(result));age[ch]+=1
        blocks.append(tuple(block))
    return tuple(blocks)
