# SPDX-License-Identifier: MIT
"""Independent event windows, hysteresis and sample-clock expectations.

Expected values derive from finite stimulus, window definitions and elapsed
sample ordinals. No generated code or captured output constructs this oracle.
All limits and report/reset conventions are fixed before export or execution.
"""
import math
import struct
BLOCK_FRAMES=256
PREPARE_ZERO_WARM_BLOCKS=0
REFERENCE_CALL_COUNT=20
PILOT_RIGHT_BIT_EXACT=True
SPECS=[]
def add(identity,name,args='',operation=None,variant='default',limit=0):
    SPECS.append(dict(id=identity,exact_name=name,fixed_arguments=args,operation=operation or name.removesuffix('~'),variant=variant,observed_outlet=0,limit=limit))
add('avg-manual','avg~',operation='report',variant='mean-absolute',limit=2e-6)
add('peakamp-manual','peakamp~','0',operation='report',variant='peak')
add('snapshot-manual','snapshot~','0',operation='report',variant='last')
for name in('thresh','thresh~'):
    for args,v in(('-0.25 0.25','hysteresis'),('0 0','equal-zero'),('0.25 0.25','equal-positive')):
        add(name.replace('~','-signal')+'-'+v,name,args,operation='threshold',variant=v)
add('zerox-events','zerox')
for window in(2,3,7):add('zerox-count-'+str(window),'zerox_count',str(window),variant=str(window))
for name in('average','average_absolute','average_rms'):add(name+'-seven',name,'7',operation='average',variant=name,limit=2e-6)
add('samplecount-signal','samplecount~',operation='clock',variant='samples-signal')
for name in('currentsampletime','currentsampletime~','currenttime','currenttime~'):
    add(name.replace('~','-signal'),name,operation='clock',variant=('samples'if name.startswith('currentsample')else'milliseconds')+('-signal'if name.endswith('~')else'-event'),limit=0 if name.startswith('currentsample')else 2e-5)
for v in('free','reset'):add('elapsed-'+v,'elapsed~',operation='elapsed',variant=v)
MODEL_SPECS={3300+i:s for i,s in enumerate(SPECS)}
MODELS=frozenset(MODEL_SPECS)
MODEL_NAMES={m:s['id']for m,s in MODEL_SPECS.items()}
ABSOLUTE_TOLERANCES={m:s['limit']for m,s in MODEL_SPECS.items()}
REFERENCE_POLICIES={m:'independent-event-windows-hysteresis-and-sample-ordinals-v1'for m in MODELS}
_CALLS=(0,1,2,3,4,5,6,7,8,9,10,10,10,11,12,15,16,16,17,18,19)
_DRIVES=(1.,-2.,0.,.5,-.5,-1.5,2.,2.,-8.,8.,3.,2.,1.,1.,1.5,-0.,0.,1.,-1.,.75,-.75)
LEFT=(0.,.25,-.25,.5,-.5,.75,-.75,1.,-1.,.25,-.25,0.,.5,-.5,.125,-.125)
PILOT_WORDS=(0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def spec(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown analysis/timing model')
    return MODEL_SPECS[model]
def parameters():return[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0),dict(id='arm',minimum=0.,maximum=1.,initial=0.,exponent=1.,steps=0)]
def parameter_events(model):spec(model);return[dict(before_call=0,id='arm',value=1.)]+[dict(before_call=c,id='drive',value=x)for c,x in zip(_CALLS,_DRIVES)]
def input_words(frames=256):
    if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
    return tuple(w for i in range(frames)for w in(word(LEFT[i%16]),PILOT_WORDS[i%16]))
def case_input_words(model,frames=256):spec(model);return input_words(frames)
def reference_blocks(model,inputs,call_count=20):
    s=spec(model);op=s['operation'];v=s['variant'];inputs=tuple(inputs)
    if inputs!=input_words()or type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Invalid stimulus/callback count')
    events=parameter_events(model)
    if len(events)!=22 or events[0]!=dict(before_call=0,id='arm',value=1.):raise ValueError('Missing initial arm')
    last=-1
    for e in events[1:]:
        if set(e)!={'before_call','id','value'}or type(e['before_call'])is not int or not last<=e['before_call']<20 or e['id']!='drive'or type(e['value'])is not float or not math.isfinite(e['value'])or not -8<=e['value']<=8:raise ValueError('Invalid drive schedule')
        last=e['before_call']
    cursor=0;current=0.;held=0.;window=[];negative=False;crossings=0;count=0;last_count=0;above=False;elapsed=0;blocks=[]
    def threshold(x):
        nonlocal above
        lo,hi=map(float,s['fixed_arguments'].split())
        if above:
            if x<lo if lo==hi else x<=lo:above=False
        elif x>=hi:above=True
        return float(above)
    for call in range(call_count):
        while cursor<len(events)and events[cursor]['before_call']==call:
            e=events[cursor];cursor+=1
            if e['id']=='arm':continue
            x=value(word(e['value']))
            if op=='report':
                held=(sum(abs(a)for a in window)/len(window)if window else 0.)if v=='mean-absolute'else max((abs(a)for a in window),default=0.)if v=='peak'else(window[-1]if window else held)
                if v!='last':window=[]
            elif op=='threshold'and not s['exact_name'].endswith('~'):held=threshold(x)
            elif op in('zerox','zerox_count'):
                change=(x<0)!=negative;negative=x<0
                if op=='zerox':held=float(change)
                else:
                    crossings+=change;count+=1
                    if count==int(v):last_count=crossings;count=crossings=0
                    held=float(last_count)
            elif op=='average':
                window.append(x);window=window[-7:]
                held=sum(window)/len(window)if v=='average'else sum(abs(a)for a in window)/len(window)if v=='average_absolute'else math.sqrt(sum(a*a for a in window)/len(window))
            elif op=='clock'and v.endswith('-event'):held=call*256*(1000/44100 if v.startswith('milliseconds')else 1)
            elif op=='elapsed'and v=='reset':elapsed=0
            current=x
        block=[]
        for i in range(256):
            x=value(word(current*value(inputs[2*i])))
            if op=='report':window.append(x);y=held
            elif op=='threshold'and s['exact_name'].endswith('~'):y=threshold(value(word(current+value(inputs[2*i]))))
            elif op=='clock'and v.endswith('-signal'):y=(call*256+i)*(1000/44100 if v.startswith('milliseconds')else 1)
            elif op=='elapsed':y=elapsed;elapsed+=1
            else:y=held
            block.extend((word(y),inputs[2*i+1]))
        blocks.append(tuple(block))
    return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
