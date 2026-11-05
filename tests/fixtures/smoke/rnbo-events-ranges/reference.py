# SPDX-License-Identifier: MIT
"""Independent dyadic boundary-event references; never evaluated DSP source.

Twenty fixed256-frame callbacks, zero automatic warmup, four manual warm calls,
then sixteen timed calls. Every event updates the state, including duplicate
updates before a callback. Right audio is an immutable bit-exact observer.
Range bounds are[-1,1]; wrap uses a half-open interval and fold a closed interval.
Triangle and box-to-triangle use only phases[0,1], duty.5 and shape1 respectively.
Delta remembers the previous EVENT, not the previous callback or audio sample.
"""
import math
import struct

BLOCK_FRAMES=256
PREPARE_ZERO_WARM_BLOCKS=0
MANUAL_WARM_CALLS=4
TIMED_CALLS=16
REFERENCE_CALL_COUNT=20
PARAMETER_ID='drive'
PARAMETER_DEFAULT=0.
PARAMETER_RANGE=(-8.,8.)
PILOT_RIGHT_BIT_EXACT=True
MODEL_NAMES={196:'equal-pass2',197:'not-equal-pass2',198:'less-pass2',199:'less-equal-pass2',
             200:'greater-pass2',201:'greater-equal-pass2',202:'clamp-minus1-plus1',
             203:'wrap-minus1-plus1',204:'fold-minus1-plus1',205:'conditional-plus2-minus2',
             206:'linear-interpolation-minus1-plus1',207:'box-to-triangle-shape1',
             208:'triangle-duty-half',209:'event-delta'}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:0 for m in MODELS}
REFERENCE_POLICIES={m:'documented-event-dyadic'for m in MODELS}
REFERENCE_POLICIES[203]='half-open-wrap-interval'
REFERENCE_POLICIES[204]='closed-fold-interval'
REFERENCE_POLICIES[209]='previous-event-not-previous-callback'

def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
LEFT_WORDS=tuple(word(x)for x in(-1.,-.75,-.5,-.25,-.125,-0.,0.,.125,.25,.5,.75,1.,.375,-.375,.625,-.625))
PILOT_WORDS=(0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,
             0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff)
_SCHEDULE=((0,1.),(1,-2.),(2,0.),(3,.5),(4,-.5),(5,-1.5),(6,2.),(7,2.),(8,-8.),(9,8.),
           (10,3.),(10,2.),(10,1.),(11,1.),(12,1.5),(15,-0.),(16,0.),(16,1.),(17,-1.),(18,.75),(19,-.75))

def _model(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown event-range model')

def input_words(frames=256):
    if type(frames)is not int or frames!=256:raise ValueError('Expected256 frames')
    return tuple(w for n in range(frames)for w in(LEFT_WORDS[(n//16)%16],PILOT_WORDS[n%16]))

def case_input_words(model,frames=256):
    _model(model);return input_words(frames)

def parameter_events(model):
    _model(model)
    replacement=iter((3.,1.,2.)if model in(196,197,199,200)else(1.,3.,2.)if model==201 else(3.,2.,1.))
    events=[]
    for call,x in _SCHEDULE:
        if call==10:x=next(replacement)
        if model in(206,207,208):x=.5+x/16  # exact dyadic phases; includes0,.5,1
        events.append({'before_call':call,'id':'drive','value':x})
    return events

def _operation(model,x,previous):
    if model in range(196,202):
        condition={196:x==2,197:x!=2,198:x<2,199:x<=2,200:x>2,201:x>=2}[model]
        return x if condition else 0.
    if model==202:return min(1.,max(-1.,x))
    if model==203:return (x+1)%2-1
    if model==204:
        phase=(x+1)%4
        return -1+phase if phase<=2 else 3-phase
    if model==205:return 2. if x!=0 else -2.
    if model==206:return -1+2*x
    if model in(207,208):return 1-abs(2*x-1)
    if model==209:return x-previous
    raise ValueError('Unknown operation')

def reference_blocks(model,inputs,call_count=20):
    _model(model)
    if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Invalid callback count')
    inputs=tuple(inputs)
    if len(inputs)!=512 or any(type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000 for w in inputs):
        raise ValueError('Expected512 finite binary32 input words')
    events=parameter_events(model);last=-1
    for e in events:
        if (set(e)!={'before_call','id','value'}or type(e['before_call'])is not int or not last<=e['before_call']<20
            or e['id']!='drive'or type(e['value'])is not float or not math.isfinite(e['value'])or not -8<=e['value']<=8):
            raise ValueError('Invalid ordered actual-parameter schedule')
        last=e['before_call']
    if len(events)!=21 or events[0]['before_call']!=0:raise ValueError('Expected21 events starting beforecall0')
    previous=0.;held=0.;index=0;blocks=[]
    for call in range(call_count):
        while index<len(events)and events[index]['before_call']==call:
            x=value(word(events[index]['value']));held=_operation(model,x,previous);previous=x;index+=1
        blocks.append(tuple(w for right in inputs[1::2]for w in(word(held),right)))
    return tuple(blocks)

def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
