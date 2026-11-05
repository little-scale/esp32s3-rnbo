# SPDX-License-Identifier: MIT
"""Independent event-prefix/state contracts, with rational smoothing references.

An explicit arm blocks startup defaults and seeds counters before the21 drive
actions. Every drive action is an event, including repeats and same-call actions.
Only a callback's final held value is sampled. Accumulator reset inputs are
neutral (0 for sums,1 for products), avoiding ambiguous reset/input precedence.
No producer code or captured output constructs these expectations.
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
SPECS=[]
for n,slug in(('accum','accum'),('plusequals','plusequals'),('+=','plus-assign')):
    for variant in('prefix','neutral-reset'):SPECS.append((slug+'-'+variant,n,'sum',variant,0))
for n,slug in(('mulequals','mulequals'),('*=','multiply-assign')):
    for variant in('prefix','neutral-reset'):SPECS.append((slug+'-'+variant,n,'product',variant,0))
for variant in('closed','open','positive-control'):SPECS.append(('latch-'+variant,'latch','latch',variant,0))
for variant,outlet in(('changed-value-sum',0),('rise-count',1),('fall-count',2)):
    SPECS.append(('change-'+variant,'change','change',variant,outlet))
for variant in('up','down','bounce','negative-up','reset-next','reset-now'):
    SPECS.append(('counter-'+variant,'counter','counter',variant,0))
for n in('peak','trough'):
    for variant,outlet in(('value',0),('new-flag',1),('not-new-flag',2)):
        SPECS.append((n+'-'+variant,n,n,variant,outlet))
for n in('slide','rampsmooth'):
    for variant in('up2-down4','up4-down8'):SPECS.append((n+'-'+variant,n,n,variant,0))
for variant in('threshold-zero','threshold-half'):SPECS.append(('sah-'+variant,'sah','sah',variant,0))
for n,slug in(('t','t'),('trigger','trigger')):SPECS.append((slug+'-right-before-left',n,'trigger','right-before-left',0))
MODEL_SPECS={2700+i:dict(id=iid,exact_name=n,operation=op,variant=v,outlet=o)for i,(iid,n,op,v,o)in enumerate(SPECS)}
MODEL_NAMES={m:s['id']for m,s in MODEL_SPECS.items()}
MODELS=frozenset(MODEL_SPECS)
ABSOLUTE_TOLERANCES={m:2e-6 if s['operation']in('slide','rampsmooth')else 0 for m,s in MODEL_SPECS.items()}
REFERENCE_POLICIES={m:'documented-ordered-event-state'for m in MODELS}
_SCHEDULE=((0,1.),(1,-2.),(2,0.),(3,.5),(4,-.5),(5,-1.5),(6,2.),(7,2.),(8,-8.),(9,8.),
           (10,3.),(10,2.),(10,1.),(11,1.),(12,1.5),(15,-0.),(16,0.),(16,1.),(17,-1.),(18,.75),(19,-.75))
PILOT_WORDS=(0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,
             0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def spec(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown event-state model')
    return MODEL_SPECS[model]
def input_words(frames=256):
    if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
    return tuple(w for i in range(frames)for w in(word((i//16-8)/8),PILOT_WORDS[i%16]))
def case_input_words(model,frames=256):spec(model);return input_words(frames)
def drive_events(model):
    op=spec(model)['operation']
    return[dict(before_call=c,id='drive',value=1. if op=='product'and x==0 else x)for c,x in _SCHEDULE]
def parameters():
    return[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0),
           dict(id='arm',minimum=0.,maximum=1.,initial=0.,exponent=1.,steps=0)]
def parameter_events(model):
    return[dict(before_call=0,id='arm',value=1.)]+drive_events(model)
def event_outputs(model):
    """Independent per-event outputs; exact arithmetic except output rounding."""
    s=spec(model);op=s['operation'];variant=s['variant'];xs=[Fraction(value(word(e['value'])))for e in drive_events(model)]
    result=[];held=Fraction(0);last_x=Fraction(0);last_trigger=False;epoch=None
    for j,x in enumerate(xs):
        if op=='sum':
            start=1+max((k for k in range(j+1)if xs[k]==0),default=-1)if variant=='neutral-reset'else 0
            held=sum(xs[start:j+1],Fraction(0))
        elif op=='product':
            start=1+max((k for k in range(j+1)if xs[k]==1),default=-1)if variant=='neutral-reset'else 0
            held=math.prod(xs[start:j+1],start=Fraction(1))
        elif op=='latch':
            if variant=='open'or(variant=='positive-control'and x>0):held=x
        elif op=='change':
            if variant=='changed-value-sum':held=sum((v for k,v in enumerate(xs[:j+1])if v!=(xs[k-1]if k else 0)),Fraction(0))
            elif variant=='rise-count':held=sum(v!=0 and(xs[k-1]if k else 0)==0 for k,v in enumerate(xs[:j+1]))
            else:held=sum(v==0 and(xs[k-1]if k else 0)!=0 for k,v in enumerate(xs[:j+1]))
        elif op=='counter':
            if variant in('reset-next','reset-now'):held=x
            elif variant=='up':held=j%4
            elif variant=='negative-up':held=-2+j%5
            elif variant=='down':held=(-j)%4  # explicit reset-next0 before first clock
            elif variant=='bounce':held=3-abs(3-j%6)
        elif op in('peak','trough'):
            old=(max if op=='peak'else min)([Fraction(0)]+xs[:j]);new=x>old if op=='peak'else x<old
            if variant=='value':held=(max if op=='peak'else min)([Fraction(0)]+xs[:j+1])
            elif variant=='new-flag':held=int(new)
            else:held=int(not new)
        elif op=='slide':
            up,down=(2,4)if variant=='up2-down4'else(4,8)
            held=held+(x-held)/(up if x>held else down)
        elif op=='rampsmooth':
            up,down=(2,4)if variant=='up2-down4'else(4,8)
            if x!=last_x:
                epoch=(j,held,x,up if x>held else down)
            if epoch is not None:
                begin,origin,target,duration=epoch;age=min(j-begin+1,duration)
                held=origin+(target-origin)*age/duration
        elif op=='sah':
            trigger=x>(Fraction(1,2)if variant=='threshold-half'else 0)
            if trigger and not last_trigger:held=x
            last_trigger=trigger
        elif op=='trigger':held=-x  # right outlet sets cold2*x before hotx subtracts it
        else:raise AssertionError('Missing state contract')
        result.append(word(held));last_x=x
    return tuple(result)
def reference_blocks(model,inputs,call_count=20):
    spec(model);inputs=tuple(inputs)
    if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Invalid callback count')
    if inputs!=input_words():raise ValueError('Input differs from authored finite vector')
    es=parameter_events(model);last=-1
    for e in es:
        if (set(e)!={'before_call','id','value'}or type(e['before_call'])is not int or not last<=e['before_call']<20
            or e['id']not in('drive','arm')or type(e['value'])is not float or not math.isfinite(e['value'])or not -8<=e['value']<=8):
            raise ValueError('Invalid ordered actual-value schedule')
        last=e['before_call']
    if len(es)!=22 or es[0]!=dict(before_call=0,id='arm',value=1.)or es[1:]!=drive_events(model):
        raise ValueError('Expected explicit arm followed by21 drive events')
    values=event_outputs(model);es=es[1:];index=0;held=word(0);blocks=[]
    for c in range(call_count):
        while index<len(es)and es[index]['before_call']==c:held=values[index];index+=1
        blocks.append(tuple(w for right in inputs[1::2]for w in(held,right)))
    return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
