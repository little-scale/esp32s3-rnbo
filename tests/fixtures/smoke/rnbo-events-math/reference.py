# SPDX-License-Identifier: MIT
"""Independent finite-domain mathematical screens for RNBO numeric events.

Oracles use Python double libm then a single output binary32 rounding, never
DSP source. Inputs are first rounded to binary32. Named approximations use an
explicit1e-3 absolute screen, not a universal accuracy specification. Cold2 for
atan2/hypot and cold2.5 for power are fixed. Strict raw right-lane capture hashing
is separate from the numerical output tolerance, including all signed zeros.
"""
import math
import struct
BLOCK_FRAMES=256
PREPARE_ZERO_WARM_BLOCKS=0
REFERENCE_CALL_COUNT=20
PARAMETER_ID='drive'
PARAMETER_DEFAULT=0.
PARAMETER_RANGE=(-8.,8.)
PILOT_RIGHT_BIT_EXACT=True
NAMES=('acos','acosh','asin','asinh','atan','atan2','atanh','atodb','blackman','cbrt','cos','cosh','cosT8','cosT8safe',
       'dbtoa','degrees','DEGTORAD','degtorad','exp','exp2','expm1','fastcos','fastexp','fastpow','fastsin','fasttan',
       'hamming','hann','hypot','ln','log','log10','log1p','log2','pow','radians','RADTODEG','radtodeg',
       'sin','sinh','sqrt','tan','tanh','welch')
MODEL_NAMES={210+i:name for i,name in enumerate(NAMES)}
MODELS=frozenset(MODEL_NAMES)
APPROXIMATIONS=frozenset(('cosT8','cosT8safe','fastcos','fastexp','fastpow','fastsin','fasttan'))
ABSOLUTE_TOLERANCES={m:(.001 if name in APPROXIMATIONS else 2e-5 if name=='degrees'else
                           8e-6 if name in('pow','RADTODEG','radtodeg')else 2e-6)for m,name in MODEL_NAMES.items()}
REFERENCE_POLICIES={m:('declared-mathematical-approximation-screen'if n in APPROXIMATIONS else'documented-finite-event-math')for m,n in MODEL_NAMES.items()}
_SCHEDULE=((0,1.),(1,-2.),(2,0.),(3,.5),(4,-.5),(5,-1.5),(6,2.),(7,2.),(8,-8.),(9,8.),
           (10,3.),(10,2.),(10,1.),(11,1.),(12,1.5),(15,-0.),(16,0.),(16,1.),(17,-1.),(18,.75),(19,-.75))
PILOT_WORDS=(0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,
             0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def _name(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown event-math model')
    return MODEL_NAMES[model]
def input_words(frames=256):
    if type(frames)is not int or frames!=256:raise ValueError('Expected256 frames')
    left=(-1.,-.75,-.5,-.25,-.125,-0.,0.,.125,.25,.5,.75,1.,.375,-.375,.625,-.625)
    return tuple(w for n in range(frames)for w in(word(left[(n//16)%16]),PILOT_WORDS[n%16]))
def case_input_words(model,frames=256):_name(model);return input_words(frames)
def domain(name):
    if name in('acos','asin','atanh','log1p','tan','fasttan'):return[-.5,.5]
    if name in('acosh','atodb','ln','log','log10','log2','pow','fastpow','sqrt'):return[1.,5.]
    if name in('blackman','hamming','hann','welch'):return[0.,1.]
    if name=='cosT8':return[-3.,3.]
    if name=='cosT8safe':return[-8.,8.]
    return[-2.,2.]
def parameter_events(model):
    name=_name(model);events=[]
    for call,x in _SCHEDULE:
        if name in('acos','asin','atanh','log1p','tan','fasttan'):x=x/16
        elif name in('acosh','atodb','ln','log','log10','log2','pow','fastpow','sqrt'):x=1+abs(x)/2
        elif name in('blackman','hamming','hann','welch'):x=.5+x/16
        elif name=='cosT8':x=x*3/8
        elif name=='cosT8safe':
            if call==18:x=3.
            elif call==19:x=-3.
        else:x=x/4
        events.append(dict(before_call=call,id='drive',value=x))
    return events

def operation(name,x):
    if name in('cosT8','cosT8safe','fastcos'):return math.cos(x)
    if name=='fastsin':return math.sin(x)
    if name=='fasttan':return math.tan(x)
    if name=='fastexp':return math.exp(x)
    if name in('pow','fastpow'):return math.pow(x,2.5)
    if name=='atan2':return math.atan2(x,2.)
    if name=='hypot':return math.hypot(x,2.)
    if name=='atodb':return 20*math.log10(x)
    if name=='dbtoa':return 10**(x/20)
    if name=='degrees':return x*180/math.pi
    if name=='radians':return x*math.pi/180
    if name in('degtorad','DEGTORAD'):return math.pi/180
    if name in('radtodeg','RADTODEG'):return 180/math.pi
    if name in('ln','log'):return math.log(x)
    if name=='hann':return .5-.5*math.cos(2*math.pi*x)
    if name=='hamming':return .54-.46*math.cos(2*math.pi*x)
    if name=='blackman':return .42-.5*math.cos(2*math.pi*x)+.08*math.cos(4*math.pi*x)
    if name=='welch':return 1-(2*x-1)**2
    if name in('acos','acosh','asin','asinh','atan','atanh','cbrt','cos','cosh','exp','exp2','expm1','log10','log1p','log2','sin','sinh','sqrt','tan','tanh'):
        return getattr(math,name)(x)
    raise ValueError('Unknown mathematical definition')
def reference_blocks(model,inputs,call_count=20):
    name=_name(model);inputs=tuple(inputs)
    if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Invalid callback count')
    if len(inputs)!=512 or any(type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000 for w in inputs):
        raise ValueError('Expected512 finite binary32 input words')
    events=parameter_events(model);last=-1;lo,hi=domain(name)
    for e in events:
        if (set(e)!={'before_call','id','value'}or type(e['before_call'])is not int or not last<=e['before_call']<20
            or e['id']!='drive'or type(e['value'])is not float or not math.isfinite(e['value'])or not lo<=e['value']<=hi):
            raise ValueError('Invalid ordered finite-domain schedule')
        last=e['before_call']
    if len(events)!=21 or events[0]['before_call']!=0:raise ValueError('Expected21 events starting beforecall0')
    current=0.;index=0;blocks=[]
    for call in range(call_count):
        while index<len(events)and events[index]['before_call']==call:
            current=value(word(events[index]['value']));index+=1
        held=word(operation(name,current))
        blocks.append(tuple(w for right in inputs[1::2]for w in(held,right)))
    return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
