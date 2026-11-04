# SPDX-License-Identifier: MIT
"""Independent RNBO SIGNAL-object state math, not codebox/Gen qualification.

Fresh default state; SDKwarm0 followed by4manual+16timed compared callbacks.
State carries across20 repeated256-frame input blocks. Downsample first capture
ordinal0 and periodN, strict-opposite-nonzero crossings/initial0, and completed
zero-count window with held reports are declared boundary policies where primary
prose is less precise. Keep discrepancies without fitting output. Ideal DC,
slide, ramps and fresh-fsum windows are Float64 truth, rounded once per output.
"""
import math
import struct
BLOCK_FRAMES=256
PREPARE_ZERO_WARM_BLOCKS=0
MANUAL_WARM_CALLS=4
TIMED_CALLS=16
REFERENCE_CALL_COUNT=20
MODEL_NAMES={700:'accumulator-reset0',701:'change',702:'latch',703:'dcblock-half/threequarters',704:'deltaclip',705:'downsamp3/5-declaredphase',706:'rampsmooth4/8',707:'positive-gate-trigger',708:'zerox-strictsigns',709:'zerox-count7/5',710:'absolute-average8/16',711:'RMS-average8/16',712:'delta',713:'samplehold-threshold0/half',714:'slide2/4'}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:2e-6 if m in(703,706,710,711,714)else 0 for m in MODELS}
REFERENCE_POLICIES={705:'declared-first-capture-phase0',706:'declared-linear-ramp-first-sample-step',708:'declared-strict-opposite-nonzero-crossings',709:'declared-completed-window-held-report',710:'fresh-available-history-count-current-sample',711:'fresh-available-history-count-current-sample',713:'raw-previous-control-current-threshold'}
LEFT=(0.,.25,.25,-.5,-.5,-0.,1.,1.,-1.,-1.,.5,.5,0.,.125,.125,.75)
RIGHT=(0.,1.,1.,-0.,-1.,-1.,.5,.5,0.,.25,-.25,-.25,-1.,1.,1.,1.)
CROSS_LEFT=(.25,.5,-.5,-.25,.75,-.75,1.,-1.,.125,.25,.5,-.5,.75,.5,-.25,-.5)
CROSS_RIGHT=(.5,-.5,.25,-.25,1.,.75,-.75,-1.,.25,.5,-.5,-.25,.125,-.125,.25,-.25)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def _model(m):
 if type(m)is not int or m not in MODELS:raise ValueError('Unknown signal state model')
def input_words(frames=256):
 if type(frames)is not int or frames!=BLOCK_FRAMES:raise ValueError('Expected256frames')
 return tuple(word(x)for n in range(frames)for x in(LEFT[n%16],RIGHT[n%16]))
def case_input_words(model,frames=256):
 _model(model);inputs=input_words(frames)
 if model==700:return tuple(word(value(w)/1024)for w in inputs)
 if model in(708,709):return tuple(word(x)for n in range(frames)for x in(CROSS_LEFT[n%16],CROSS_RIGHT[n%16]))
 if model==707:return tuple(word(x)for n in range(frames)for x in((.25 if n%16==0 else LEFT[n%16]),(.5 if n%16==0 else RIGHT[n%16])))
 return inputs
def reference_blocks(model,inputs,call_count=20):
 _model(model)
 if type(call_count)is not int or not 1<=call_count<=REFERENCE_CALL_COUNT:raise ValueError('Expected1..20calls')
 inputs=tuple(inputs);bound=1/1024 if model==700 else 1.
 if len(inputs)!=512 or any(type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000 or not -bound<=value(w)<=bound for w in inputs):raise ValueError('Expected512 finite bounded stereo words')
 vector=tuple(value(w)for w in inputs);previous=[0.,0.];previous_control=[0.,0.];state=[0.,0.];crossing_count=[0,0];target=[0.,0.];increment=[0.,0.];remaining=[0,0];history=[[],[]];blocks=[]
 for call in range(call_count):
  output=[]
  for frame in range(BLOCK_FRAMES):
   n=call*BLOCK_FRAMES+frame
   for ch in range(2):
    x=vector[2*frame+ch];control=vector[2*frame+1-ch]
    if model==700:state[ch]+=x;result=state[ch]
    elif model==701:result=1. if x>previous[ch]else-1. if x<previous[ch]else 0.;previous[ch]=x
    elif model==702:
     if control!=0:state[ch]=x
     result=state[ch]
    elif model==703:result=x-previous[ch]+(.5 if ch==0 else .75)*state[ch];previous[ch]=x;state[ch]=result
    elif model==704:
     lo,hi=(-.125,.25)if ch==0 else(-.25,.125);state[ch]+=max(lo,min(hi,x-state[ch]));result=state[ch]
    elif model==705:
     if n%(3 if ch==0 else 5)==0:state[ch]=x
     result=state[ch]
    elif model==706:
     if x!=target[ch]:
      target[ch]=x;remaining[ch]=(4 if ch==0 else 8)if x>state[ch]else(8 if ch==0 else 4);increment[ch]=(x-state[ch])/remaining[ch]
     if remaining[ch]>0:
      state[ch]+=increment[ch];remaining[ch]-=1
      if remaining[ch]==0:state[ch]=target[ch]
     result=state[ch]
    elif model==707:result=float(previous[ch]<=0<x);previous[ch]=x
    elif model in(708,709):
     crossing=(x<0<previous[ch])or(x>0>previous[ch]);previous[ch]=x
     if model==708:result=float(crossing)
     else:
      crossing_count[ch]+=int(crossing);window=7 if ch==0 else 5
      if(n+1)%window==0:state[ch]=float(crossing_count[ch]);crossing_count[ch]=0
      result=state[ch]
    elif model in(710,711):
     history[ch].append(abs(x)if model==710 else x*x);window=8 if ch==0 else 16;available=history[ch][max(0,len(history[ch])-window):];result=math.fsum(available)/len(available)
     if model==711:result=math.sqrt(result)
    elif model==712:result=x-previous[ch];previous[ch]=x
    elif model==713:
     threshold=0. if ch==0 else .5
     if previous_control[ch]<=threshold<control:state[ch]=x
     previous_control[ch]=control;result=state[ch]
    elif model==714:
     up,down=(2.,4.)if ch==0 else(4.,2.);state[ch]+=(x-state[ch])/(up if x>state[ch]else down);result=state[ch]
    output.append(word(result))
  blocks.append(tuple(output))
 return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
