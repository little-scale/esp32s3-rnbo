# SPDX-License-Identifier: MIT
"""Independent rational unit conversions at44100Hz,120BPM,480ticks/quarter.

Numeric events hold their output. Signal forms add the current parameter to
the independently authored, varying left input before conversion. No generated
DSP, captured output, or producer arithmetic is used to construct expectations.
Reciprocals deliberately exclude zero; transport changes are outside this test.
"""
from fractions import Fraction
import math
import struct

BLOCK_FRAMES=256
PREPARE_ZERO_WARM_BLOCKS=0
REFERENCE_CALL_COUNT=20
PARAMETER_ID='drive'
PARAMETER_DEFAULT=0.
PARAMETER_RANGE=(-8.,8.)
PILOT_RIGHT_BIT_EXACT=True
EVENT_NAMES=('beatstohz','beatstoms','beatstosamps','beatstoticks','hztobeats','hztoms','hztosamps','hztoticks',
             'mstobeats','mstohz','mstosamps','mstoticks','sampstobeats','sampstohz','sampstoms','sampstoticks',
             'tickstobeats','tickstohz','tickstoms','tickstosamples','tickstosamps')
SIGNAL_NAMES=tuple(n+'~'for n in EVENT_NAMES if n not in('hztoms','hztosamps','mstohz','mstosamps','sampstohz','sampstoms'))
MODEL_NAMES={2600+i:n for i,n in enumerate(EVENT_NAMES+SIGNAL_NAMES)}
MODELS=frozenset(MODEL_NAMES)
RECIPROCAL=frozenset(('beatstohz','hztobeats','hztoms','hztosamps','hztoticks','mstohz','sampstohz','tickstohz'))
# Absolute limits are in each object's output units, fixed before compilation.
# The largest is0.008sample (<0.2microsecond), for reciprocal hertz/sample forms.
LIMITS={'beatstohz':2e-6,'beatstoms':0,'beatstosamps':0,'beatstoticks':0,'hztobeats':2e-6,
        'hztoms':2e-4,'hztosamps':.008,'hztoticks':2e-3,'mstobeats':2e-9,'mstohz':2e-4,
        'mstosamps':5e-5,'mstoticks':1e-6,'sampstobeats':1e-10,'sampstohz':.008,'sampstoms':2e-8,
        'sampstoticks':2e-8,'tickstobeats':2e-9,'tickstohz':2e-3,'tickstoms':1e-6,
        'tickstosamples':5e-5,'tickstosamps':5e-5}
ABSOLUTE_TOLERANCES={m:LIMITS[n.removesuffix('~')]for m,n in MODEL_NAMES.items()}
REFERENCE_POLICIES={m:'rational-unit-conversion-fixed-transport'for m in MODELS}
_SCHEDULE=((0,1.),(1,-2.),(2,0.),(3,.5),(4,-.5),(5,-1.5),(6,2.),(7,2.),(8,-8.),(9,8.),
           (10,3.),(10,2.),(10,1.),(11,1.),(12,1.5),(15,-0.),(16,0.),(16,1.),(17,-1.),(18,.75),(19,-.75))
PILOT_WORDS=(0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,
             0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff)
LEFT=tuple((i-8)/32 for i in range(16))
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def name(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown unit-conversion model')
    return MODEL_NAMES[model]
def input_words(frames=256):
    if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
    return tuple(w for i in range(frames)for w in(word(LEFT[i//16]),PILOT_WORDS[i%16]))
def case_input_words(model,frames=256):name(model);return input_words(frames)
def domain(n):
    return [.75,5.25]if n.endswith('~')and n[:-1]in RECIPROCAL else[1.,5.]if n in RECIPROCAL else[-8.25,8.25]if n.endswith('~')else[-8.,8.]
def parameter_events(model):
    reciprocal=name(model).removesuffix('~')in RECIPROCAL
    return[dict(before_call=call,id='drive',value=1+abs(x)/2 if reciprocal else x)for call,x in _SCHEDULE]
def operation(n,x):
    n=n.removesuffix('~');x=Fraction(x)
    if n in('beatstohz','hztobeats'):return 2/x
    if n=='beatstoms':return 500*x
    if n=='beatstosamps':return 22050*x
    if n=='beatstoticks':return 480*x
    if n in('hztoticks','tickstohz'):return 960/x
    if n in('hztoms','mstohz'):return 1000/x
    if n in('hztosamps','sampstohz'):return 44100/x
    if n=='mstobeats':return x/500
    if n=='mstosamps':return x*Fraction(441,10)
    if n=='mstoticks':return x*Fraction(24,25)
    if n=='sampstobeats':return x/22050
    if n=='sampstoms':return x*Fraction(10,441)
    if n=='sampstoticks':return x*Fraction(16,735)
    if n=='tickstobeats':return x/480
    if n=='tickstoms':return x*Fraction(25,24)
    if n in('tickstosamps','tickstosamples'):return x*Fraction(735,16)
    raise ValueError('Unknown unit definition')
def reference_blocks(model,inputs,call_count=20):
    n=name(model);inputs=tuple(inputs)
    if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Invalid callback count')
    if inputs!=input_words():raise ValueError('Input differs from authored finite vector')
    events=parameter_events(model);last=-1
    for e in events:
        if (set(e)!={'before_call','id','value'}or type(e['before_call'])is not int or not last<=e['before_call']<20
            or e['id']!='drive'or type(e['value'])is not float or not math.isfinite(e['value'])or not -8<=e['value']<=8):
            raise ValueError('Invalid ordered actual-value schedule')
        last=e['before_call']
    if len(events)!=21 or events[0]['before_call']!=0:raise ValueError('Expected21events starting beforecall0')
    current=0.;index=0;blocks=[];lo,hi=domain(n)
    for call in range(call_count):
        while index<len(events)and events[index]['before_call']==call:
            current=value(word(events[index]['value']));index+=1
        block=[]
        for i in range(256):
            x=value(word(current+value(inputs[2*i])))if n.endswith('~')else current
            if not lo<=x<=hi:raise ValueError('Conversion input outside declared domain')
            block.extend((word(operation(n,x)),inputs[2*i+1]))
        blocks.append(tuple(block))
    return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
