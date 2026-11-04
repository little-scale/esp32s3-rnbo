# SPDX-License-Identifier: MIT
"""Independent state/filter mathematics for20 fixed256-frame RNBO callbacks.

Constructor-zero state, SDKwarm0, manual4+timed16, no explicit resets. Ideal
Float64 equations/window-fsum truth, once-binary32 output rounding; no generated
running-sum implementation is an oracle. Finite filter2e-6, exact delay/triggers0.
Moving-average startup divides by available history count (including odd counts),
so these use2e-6 even though steady8/16 windows are dyadic. Rampsmooth's first-step
on the new-target sample is an explicit boundary policy. The mono resource reference copies right input words, including zeros/subnormals/
extremes; the harness applies the SAME numeric tolerance/zero-sign policy. This
is not a separately enforced raw-bit observer qualification.
"""
import math
import struct
BLOCK_FRAMES=256
PREPARE_ZERO_WARM_BLOCKS=0
MANUAL_WARM_CALLS=4
TIMED_CALLS=16
REFERENCE_CALL_COUNT=20
MODEL_NAMES={600:'delay2samples',601:'comb2samples',602:'allpass3samples',603:'biquad-dyadic',604:'onepole1000/2000Hz',605:'onepole-linear-quarter/half',606:'average8/16',607:'absolute-average8/16',608:'RMS-average8/16',609:'rampsmooth4/8',610:'positive-gate-trigger',611:'threshold-minusquarter-plusquarter'}
MODELS=frozenset(MODEL_NAMES);ABSOLUTE_TOLERANCES={m:0 if m in(600,610,611)else 2e-6 for m in MODELS}
REFERENCE_POLICIES={602:'Schroeder-allpass-negative-direct-positive-feedback',606:'fresh-available-history-count-current-sample',607:'fresh-available-history-count-current-sample',608:'fresh-available-history-count-current-sample',609:'declared-linear-ramp-first-sample-step',610:'initial0-positive-edge-default',611:'inclusive-high-and-distinct-low'}
LEFT=(0.,.25,.25,-.5,-.5,-0.,1.,1.,-1.,-1.,.5,.5,0.,.125,.125,.75)
RIGHT=(0.,1.,1.,-0.,-1.,-1.,.5,.5,0.,.25,-.25,-.25,-1.,1.,1.,1.)
PILOT_WORDS=(0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def _model(m):
 if type(m)is not int or m not in MODELS:raise ValueError('Unknown RNBO filter model')
def input_words(frames=256):
 if type(frames)is not int or frames!=BLOCK_FRAMES:raise ValueError('Expected256 frames')
 return tuple(word(x)for n in range(frames)for x in(LEFT[n%16],RIGHT[n%16]))
def case_input_words(model,frames=256):
 _model(model);input_words(frames)
 if model<603:return tuple(w for n in range(frames)for w in(word(LEFT[n%16]),PILOT_WORDS[n%16]))
 if model==610:return tuple(word(x)for n in range(frames)for x in((.25 if n%16==0 else LEFT[n%16]),(.5 if n%16==0 else RIGHT[n%16])))
 return input_words(frames)
def reference_blocks(model,inputs,call_count=20):
 _model(model)
 if type(call_count)is not int or not 1<=call_count<=REFERENCE_CALL_COUNT:raise ValueError('Expected1..20 calls')
 inputs=tuple(inputs)
 if len(inputs)!=512:raise ValueError('Expected512 stereo words')
 for i,w in enumerate(inputs):
  if type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000:raise ValueError('Finite words required')
  if not(model<603 and i%2==1)and not -1<=value(w)<=1:raise ValueError('Filter data is bounded to[-1,1]')
 vec=tuple(value(w)for w in inputs);history=[[],[]];state=[0.,0.];previous=[0.,0.];older_input=[0.,0.];older_output=[0.,0.];target=[0.,0.];increment=[0.,0.];remaining=[0,0];blocks=[]
 for call in range(call_count):
  output=[]
  for frame in range(BLOCK_FRAMES):
   n=call*BLOCK_FRAMES+frame
   for ch in range(2):
    if model<603 and ch==1:output.append(inputs[2*frame+1]);continue
    x=vec[2*frame+ch];past=history[ch]
    if model==600:result=past[n-2]if n>=2 else 0.
    elif model==601:
     xd=past[n-2]if n>=2 else 0.;yd=older_output[ch][n-2]if n>=2 else 0.
     result=.5*x+.5*xd+.25*yd
    elif model==602:
     xd=past[n-3]if n>=3 else 0.;yd=older_output[ch][n-3]if n>=3 else 0.
     result=-.5*x+xd+.5*yd
    elif model==603:
     result=.5*x+.25*previous[ch]+.125*older_input[ch]+.25*state[ch]-.125*older_output[ch];older_input[ch]=previous[ch];previous[ch]=x;older_output[ch]=state[ch];state[ch]=result
    elif model in(604,605):
     a=1-math.exp(-2*math.pi*(1000 if ch==0 else 2000)/44100)if model==604 else(.25 if ch==0 else .5);a=max(.00001,min(.99999,a));state[ch]+=a*(x-state[ch]);result=state[ch]
    elif model in(606,607,608):
     sample=abs(x)if model==607 else x*x if model==608 else x;window=8 if ch==0 else 16;past.append(sample);available=past[max(0,len(past)-window):];result=math.fsum(available)/len(available)
     if model==608:result=math.sqrt(result)
    elif model==609:
     if x!=target[ch]:
      target[ch]=x;remaining[ch]=(4 if ch==0 else 8)if x>state[ch]else(8 if ch==0 else 4);increment[ch]=(x-state[ch])/remaining[ch]
     if remaining[ch]>0:
      state[ch]+=increment[ch];remaining[ch]-=1
      if remaining[ch]==0:state[ch]=target[ch]
     result=state[ch]
    elif model==610:result=float(previous[ch]<=0<x);previous[ch]=x
    elif model==611:
     if x>=.25:state[ch]=1.
     elif x<=-.25:state[ch]=0.
     result=state[ch]
    if model in(600,601,602):
     past.append(x)
     if model in(601,602):
      if n==0:older_output[ch]=[]
      older_output[ch].append(result)
    output.append(word(result))
  blocks.append(tuple(output))
 return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
