# SPDX-License-Identifier: MIT
"""Independent RNBO codebox state mathematics across20 full-vector calls.

Fresh constructor/default state0; no SDK warm vectors; four compared manual
warm callbacks plus sixteen timed callbacks. No reset is inserted at256frames.
Definitions derive from RNBO primary references, not emitted kernels. Counter
increment-before-output, downsample capture ordinal0, strict-opposite-nonzero
crossings (initial0 no crossing), and completed-window/held zero-count reports
are DECLARED boundary policies where primary prose is less specific. Preserve
any discrepancy rather than fitting the policy after output. Slide/DC use ideal
Float64 model history, then round each reported result once to binary32.
"""
import math
import struct
BLOCK_FRAMES=256
PREPARE_ZERO_WARM_BLOCKS=0
MANUAL_WARM_CALLS=4
TIMED_CALLS=16
REFERENCE_CALL_COUNT=20
MODEL_NAMES={500:'history-read-then-write',501:'change',502:'latch',503:'sah-threshold0/half',504:'slide2/4',505:'dcblock-half/threequarters',506:'accum-reset0',507:'counter7/5-increment-before-output',508:'deltaclip',509:'downsamp3/5-firstcapture0',510:'zerox-strict-opposite-nonzero',511:'zerox-count-window7/5-heldreport'}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:2e-6 if m in(504,505)else 0 for m in MODELS}
REFERENCE_POLICIES={507:'declared-increment-before-output',509:'declared-first-capture-phase0',510:'declared-strict-opposite-nonzero-crossings',511:'declared-completed-window-held-report'}
LEFT=(0.,.25,.25,-.5,-.5,-0.,1.,1.,-1.,-1.,.5,.5,0.,.125,.125,.75)
RIGHT=(0.,1.,1.,-0.,-1.,-1.,.5,.5,0.,.25,-.25,-.25,-1.,1.,1.,1.)
CROSS_LEFT=(.25,.5,-.5,-.25,.75,-.75,1.,-1.,.125,.25,.5,-.5,.75,.5,-.25,-.5)
CROSS_RIGHT=(.5,-.5,.25,-.25,1.,.75,-.75,-1.,.25,.5,-.5,-.25,.125,-.125,.25,-.25)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def _model(m):
 if type(m)is not int or m not in MODELS:raise ValueError('Unknown RNBO state model')
def input_words(frames=256):
 if type(frames)is not int or frames!=BLOCK_FRAMES:raise ValueError('Expected256frames')
 return tuple(word(x)for n in range(frames)for x in(LEFT[n%16],RIGHT[n%16]))
def case_input_words(model,frames=256):
 _model(model);input_words(frames)
 if model==507:return tuple(word(1.)for _ in range(2*frames))
 if model in(510,511):return tuple(word(x)for n in range(frames)for x in(CROSS_LEFT[n%16],CROSS_RIGHT[n%16]))
 return input_words(frames)
def reference_blocks(model,inputs,call_count=20):
 _model(model)
 if type(call_count)is not int or not 1<=call_count<=REFERENCE_CALL_COUNT:raise ValueError('Expected1..20calls')
 inputs=tuple(inputs)
 if len(inputs)!=512 or any(type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000 or not -1<=value(w)<=1 for w in inputs):raise ValueError('Expected512 finite bounded stereo words')
 if model==507 and any(w!=word(1.)for w in inputs):raise ValueError('Counter reference requires authored unit increments on both lanes')
 vector=tuple(value(w)for w in inputs);previous=[0.,0.];previous_control=[0.,0.];state=[0.,0.];crossing_count=[0,0];blocks=[]
 for call in range(call_count):
  output=[]
  for frame in range(BLOCK_FRAMES):
   n=call*BLOCK_FRAMES+frame
   for ch in range(2):
    x=vector[2*frame+ch];control=vector[2*frame+1-ch]
    if model==500:result=previous[ch];previous[ch]=x
    elif model==501:
     result=1. if x>previous[ch]else-1. if x<previous[ch]else 0.;previous[ch]=x
    elif model==502:
     if control!=0:state[ch]=x
     result=state[ch]
    elif model==503:
     threshold=0. if ch==0 else .5
     if previous_control[ch]<=threshold<control:state[ch]=x
     previous_control[ch]=control;result=state[ch]
    elif model==504:
     up,down=(2.,4.)if ch==0 else(4.,2.);state[ch]+=(x-state[ch])/(up if x>state[ch]else down);result=state[ch]
    elif model==505:
     result=x-previous[ch]+(.5 if ch==0 else .75)*state[ch];previous[ch]=x;state[ch]=result
    elif model==506:state[ch]+=x/1024;result=state[ch]
    elif model==507:result=(n+1)%(7 if ch==0 else 5)
    elif model==508:
     lo,hi=(-.125,.25)if ch==0 else(-.25,.125);state[ch]+=max(lo,min(hi,x-state[ch]));result=state[ch]
    elif model==509:
     if n%(3 if ch==0 else 5)==0:state[ch]=x
     result=state[ch]
    elif model in(510,511):
     crossing=(x<0<previous[ch])or(x>0>previous[ch]);previous[ch]=x
     if model==510:result=float(crossing)
     else:
      crossing_count[ch]+=int(crossing);window=7 if ch==0 else 5
      if(n+1)%window==0:state[ch]=float(crossing_count[ch]);crossing_count[ch]=0
      result=state[ch]
    output.append(word(result))
  blocks.append(tuple(output))
 return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
