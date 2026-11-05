# SPDX-License-Identifier: MIT
"""Independent bounded phase, trajectory, hysteresis and octave contracts.

Current/pre-increment phase, post-increment ramps, zero reset history and
switch-ramp difference compensation are explicit screening policies. Unclear
producer boundaries remain mismatches; references are never fitted to outputs.
"""
from fractions import Fraction
import struct
OWNERS=('phasor','train','rampsmooth','gatetotrig','onoff','thresh','mtof','ftom','ease','easexfade','xfademul','bline','swanramp')
ROWS=tuple((o,v)for o in OWNERS for v in('next','reset'))+(('phasor','negative'),('phasor','input-reset'),('gatetotrig','falling'),('thresh','equal'),('bline','set'))+tuple((o,'constructor')for o in('phasor','train','onoff','bline','swanramp'))
MODELS=frozenset(range(2000,2000+len(ROWS)))
ABSOLUTE_TOLERANCES={m:(5e-4 if ROWS[m-2000][0]=='mtof'else 2e-5 if ROWS[m-2000][0]=='ftom'else 2e-6 if ROWS[m-2000][0]in('ease','easexfade','xfademul')else 0)for m in MODELS}
LEFT=(.25,.5,.5,0.,0.,.75,.75,.25,.25,-.25,-.25,.5,.5,0.,.25,1.)
RIGHT=(.5,.75,.75,.25,.25,1.,1.,.5,.5,0.,0.,.75,.75,.25,.5,1.)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def row(model):
 if type(model)is not int or model not in MODELS:raise ValueError('Unknown motion member model')
 return ROWS[model-2000]
def reset_at(n,ch):return n%257 in(37,38)or n in(255,256)if ch==0 else n%263 in(91,92)or n in(511,512)
def trigger_at(n,ch):return n%(73 if ch==0 else 91)==(19 if ch==0 else 31)
def target(n,ch):
 t=n%(1021 if ch==0 else 1031)
 return (1 if t<333 else -.5 if t<701 else .25)if ch==0 else(-1 if t<347 else .5 if t<739 else -.25)
def case_input_words(model,frames=256):
 owner,variant=row(model)
 if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
 pairs=[]
 for f in range(256):
  if owner=='mtof':pair=(69+12*((f%7)-3),69+12*((f//7%7)-3))
  elif owner=='ftom':pair=(440*2**((f%7)-3),432*2**((f//7%7)-3))
  elif owner=='gatetotrig':pair=(int(f%17>=7),int(f%19>=11))
  elif owner in('ease','easexfade','xfademul'):pair=((f%16)/16,(f//16)/16)
  else:pair=(LEFT[f%16],RIGHT[f%16])
  pairs.extend(map(word,pair))
 return tuple(pairs)
def input_words(frames=256):return case_input_words(2000,frames)
def reference_blocks(model,inputs,call_count=20):
 owner,variant=row(model);inputs=tuple(inputs)
 if inputs!=case_input_words(model):raise ValueError('Motion member input differs')
 if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Expected1..20calls')
 # Ideal histories are exact Fractions, rounded once per observed output.
 age=[0,0];state=[Fraction(0),Fraction(0)];oldtarget=[Fraction(0),Fraction(0)];start=[Fraction(0),Fraction(0)];ramp_age=[0,0];oldgate=[False,False];pending=[False,False];prev=[Fraction(0),Fraction(0)];correction=[Fraction(0),Fraction(0)];bridge_age=[16,16];blocks=[]
 for call in range(call_count):
  block=[]
  for f in range(256):
   n=call*256+f
   for ch in(0,1):
    x=Fraction(value(inputs[2*f+ch]));period=(512 if ch==0 else 1024)
    if variant=='reset'and reset_at(n,ch):
     age[ch]=0;state[ch]=oldtarget[ch]=start[ch]=prev[ch]=correction[ch]=Fraction(0);ramp_age[ch]=0;oldgate[ch]=pending[ch]=False;bridge_age[ch]=16
    if owner=='phasor':
     if variant=='input-reset'and reset_at(n,ch):age[ch]=0
     result=Fraction((-age[ch]if variant=='negative'else age[ch])%period,period)
    elif owner=='train':result=int((Fraction(age[ch]%period,period)-(Fraction(0)if ch==0 else Fraction(1,4)))%1<(Fraction(1,4)if ch==0 else Fraction(1,2)))
    elif owner=='onoff':result=(age[ch]+1)%2
    elif owner=='gatetotrig':
     high=x>0
     result=int(pending[ch])if variant=='falling'else int(high and not oldgate[ch])
     pending[ch]=oldgate[ch]and not high;oldgate[ch]=high
    elif owner=='thresh':
     lo=Fraction(0)if ch==0 else Fraction(1,4);hi=Fraction(1,2)if ch==0 else Fraction(3,4)
     if variant=='equal':lo=hi=Fraction(1,2)
     if x>=hi:state[ch]=1
     elif x<lo or(lo!=hi and x==lo):state[ch]=0
     result=state[ch]
    elif owner in('rampsmooth','bline'):
     steps=8 if ch==0 else 16;t=Fraction(target(n,ch))
     if variant=='set'and reset_at(n,ch):state[ch]=Fraction(1,2)if ch==0 else Fraction(-1,2);start[ch]=state[ch];ramp_age[ch]=0
     if t!=oldtarget[ch]:start[ch]=state[ch];ramp_age[ch]=0;oldtarget[ch]=t
     ramp_age[ch]=min(steps,ramp_age[ch]+1);state[ch]=start[ch]+(t-start[ch])*Fraction(ramp_age[ch],steps);result=state[ch]
    elif owner=='swanramp':
     length=8 if ch==0 else 16
     if trigger_at(n,ch):correction[ch]=prev[ch]-x;bridge_age[ch]=0
     result=x+correction[ch]*max(Fraction(0),1-Fraction(bridge_age[ch],length));bridge_age[ch]+=1;prev[ch]=x
    elif owner=='mtof':result=(440 if ch==0 else 432)*Fraction(2)**((int(x)-69)//12)
    elif owner=='ftom':
     ratio=x/(440 if ch==0 else 432);k=0
     while ratio>1:ratio/=2;k+=1
     while ratio<1:ratio*=2;k-=1
     assert ratio==1;result=69+12*k
    elif owner=='ease':result=x
    elif owner=='easexfade':result=(-1+2*x)if ch==0 else(2-4*x)
    elif owner=='xfademul':result=1-x if ch==0 else x
    else:raise AssertionError('Missing independent contract')
    block.append(word(result));age[ch]+=1
  blocks.append(tuple(block))
 return tuple(blocks)
