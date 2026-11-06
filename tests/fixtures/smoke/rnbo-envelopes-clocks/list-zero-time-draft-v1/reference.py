# SPDX-License-Identifier: MIT
"""Independent envelopes, logical transitions and scheduled value timelines.

Envelope samples use closed-form segment age, not producer accumulators.
Curves use normalized exponential bases and declared argument mapping. Event
clocks use intended callback-boundary origin and nearest-sample observation;
signal-generated edge bangs retain a one-block observer latency. Scheduling
policy differences remain results. No generated/captured outputs build goldens.
"""
import heapq
import math
import struct
BLOCK_FRAMES=256
PREPARE_ZERO_WARM_BLOCKS=0
REFERENCE_CALL_COUNT=20
PILOT_RIGHT_BIT_EXACT=True
SPECS=[]
def add(identity,name,args='',op=None,variant='default',outlet=0,limit=0,**extra):
    SPECS.append(dict(id=identity,exact_name=name,fixed_arguments=args,operation=op or name.removesuffix('~'),variant=variant,observed_outlet=outlet,limit=limit,**extra))
add('onoff-events','onoff')
for edge in('pos','neg'):add('gatetotrig-'+edge,'gatetotrig','@edge '+edge,variant=edge)
for initial in(0,1):
    for out in(0,1):add('onebang-init'+str(initial)+'-out'+str(out),'onebang',str(initial),variant='initial-'+str(initial),outlet=out)
for out in(0,1):add('onebang-rearm-out'+str(out),'onebang','0',variant='positive-rearm',outlet=out)
for out in(0,1):add('edge-out'+str(out),'edge~',variant='rising'if out==0 else'falling',outlet=out)
for label,a,r,h,reset in [('minimum',0.,0.,0,False),('short-free',.1,.2,0,False),('long-free',1.,2.,0,False),('short-held',.1,.2,1,False),('long-held',1.,2.,1,False),('held-reset',.1,.2,1,True)]:
    add('env2-'+label,'env2~',f'@attack {a} @release {r} @hold {h}',op='envelope',variant=label,limit=2e-5,attack_ms=a,release_ms=r,hold=h,reset_each_drive=reset)
for label,d,c in [('immediate',0.,0.),('gentle',8.,0.),('rising',8.,.5),('falling',8.,-.5),('steep',8.,.9),('compound',4.,.25)]:
    add('curve-'+label,'curve~','0',op='curve',variant=label,limit=3e-5,duration_ms=d,curvature=c)
for delay in(2,10):
    for all_ in(0,1):add('delay-'+str(delay)+'-all'+str(all_),'delay',f'{delay} @delayall {all_}',variant='all'if all_ else'replace',delay_ms=delay)
for delay in(2,10):add('pipe-'+str(delay),'pipe',str(delay),delay_ms=delay)
for label in('immediate','ramp'):add('line-'+label,'line','0 2',variant=label,limit=2e-5)
MODEL_SPECS={3400+i:s for i,s in enumerate(SPECS)}
MODELS=frozenset(MODEL_SPECS)
MODEL_NAMES={m:s['id']for m,s in MODEL_SPECS.items()}
ABSOLUTE_TOLERANCES={m:s['limit']for m,s in MODEL_SPECS.items()}
REFERENCE_POLICIES={m:'independent-envelope-age-and-boundary-clock-screen-v1'for m in MODELS}
_CALLS=(0,1,2,3,4,5,6,7,8,9,10,10,10,11,12,15,16,16,17,18,19)
_DRIVES=(1.,-2.,0.,.5,-.5,-1.5,2.,2.,-8.,8.,3.,2.,1.,1.,1.5,-0.,0.,1.,-1.,.75,-.75)
LEFT=(0.,.5,1.,0.,-1.,-.5,0.,.25,0.,.75,.75,0.,-.25,0.,.5,0.)
PILOT_WORDS=(0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def spec(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown envelope/clock model')
    return MODEL_SPECS[model]
def parameters():return[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0),dict(id='arm',minimum=0.,maximum=1.,initial=0.,exponent=1.,steps=0)]
def parameter_events(model):spec(model);return[dict(before_call=0,id='arm',value=1.)]+[dict(before_call=c,id='drive',value=x)for c,x in zip(_CALLS,_DRIVES)]
def input_words(frames=256):
    if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
    return tuple(w for i in range(frames)for w in(word(LEFT[i//16]),PILOT_WORDS[i%16]))
def case_input_words(model,frames=256):spec(model);return input_words(frames)
def curve_basis(t,c):
    # Installed primary shape mapping, evaluated by independent expm1 ratio.
    p=math.copysign(5.,c if c else 1.)*math.expm1((1-abs(c))/0.23)/math.expm1(1/0.23)
    return math.expm1(t/p)/math.expm1(1/p)
def envelope_at(ordinal,segment,a,r,hold):
    if segment is None:return 0.
    mode,start,amp=segment;n=ordinal-start+1
    if mode=='release':return amp*max(0.,1-n/r)
    if n<=a:return amp*n/a
    if n==math.floor(a)+1:return amp*math.floor(a)/a
    if hold:return amp
    return amp*max(0.,1-(n-a)/r)
def reference_blocks(model,inputs,call_count=20):
    s=spec(model);op=s['operation'];v=s['variant'];inputs=tuple(inputs)
    if inputs!=input_words()or type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Invalid stimulus/callback count')
    events=parameter_events(model)
    if len(events)!=22 or events[0]!=dict(before_call=0,id='arm',value=1.):raise ValueError('Missing initial arm')
    last=-1
    for e in events[1:]:
        if set(e)!={'before_call','id','value'}or type(e['before_call'])is not int or not last<=e['before_call']<20 or e['id']!='drive'or type(e['value'])is not float or not math.isfinite(e['value'])or not -8<=e['value']<=8:raise ValueError('Invalid drive schedule')
        last=e['before_call']
    cursor=0;current=0.;held=0.;previous=0.;count=0;allow=s['fixed_arguments']=='1';segment=None;out_last=0.;curve_segments=[];queue=[];serial=0;line_segment=(0.,0.,0.)
    a=max(1.,value(word(s.get('attack_ms',0.)))*44.1);r=max(1.,value(word(s.get('release_ms',0.)))*44.1)
    def schedule(t,kind,payload=0.):
        nonlocal serial
        heapq.heappush(queue,(int(math.floor(t+.5)),serial,kind,payload));serial+=1
    blocks=[]
    for call in range(call_count):
        boundary=call*256
        while cursor<len(events)and events[cursor]['before_call']==call:
            e=events[cursor];cursor+=1
            if e['id']=='arm':continue
            x=value(word(e['value']))
            if op=='onoff':count+=1;held=float(count%2)
            elif op=='gatetotrig':held=float((x>0 and previous<=0)if v=='pos'else(x<=0 and previous>0));previous=x
            elif op=='onebang':
                if v=='positive-rearm'and x>0:allow=True
                selected=0 if allow else 1;allow=False
                if selected==s['observed_outlet']:count+=1
                held=float(count)
            elif op=='envelope'and s['reset_each_drive']:segment=None
            elif op=='curve':
                curve_segments=[];start=boundary;begin=out_last
                targets=[(x,s['duration_ms'],s['curvature'])]
                if v=='compound':targets.append((-.5*x,8.,-.5))
                for target,duration,c in targets:
                    if duration==0:begin=target;held=target
                    else:
                        length=value(word(duration))*44.1;end=start+length;curve_segments.append((math.ceil(start),end,begin,target,value(word(c)),length));start=end;begin=target
                if not curve_segments:out_last=held
            elif op=='delay':
                if v=='replace':queue=[]
                schedule(boundary+s['delay_ms']*44.1,'count')
            elif op=='pipe':schedule(boundary+s['delay_ms']*44.1,'value',x)
            elif op=='line':
                if v=='immediate':held=x
                else:
                    start,begin,target=line_segment
                    begin=begin+(target-begin)*min(1.,max(0.,(boundary-start)/(12*44.1)))
                    line_segment=(boundary,begin,x);queue=[]
                    for tick in range(2,13,2):schedule(boundary+tick*44.1,'value',begin+(x-begin)*tick/12)
            current=x
        block=[]
        for i in range(256):
            ordinal=boundary+i
            while queue and queue[0][0]<=ordinal:
                _,_,kind,payload=heapq.heappop(queue)
                if kind=='count':count+=1;held=float(count)
                else:held=payload
            if op in('edge','envelope'):
                x=value(word(current*value(inputs[2*i])))
                if op=='edge':
                    selected=0 if previous==0 and x!=0 else 1 if previous!=0 and x==0 else None
                    if selected==s['observed_outlet']:schedule(ordinal+256,'count')
                    y=held
                else:
                    if previous==0 and x!=0:segment=('attack',ordinal,x)
                    elif s['hold']and previous!=0 and x==0 and segment is not None and segment[0]!='release':segment=('release',ordinal,out_last)
                    y=envelope_at(ordinal,segment,a,r,s['hold']);out_last=y
                previous=x
            elif op=='curve':
                y=held
                for start,end,begin,target,c,length in curve_segments:
                    if ordinal<start:break
                    if ordinal<end:y=begin+(target-begin)*curve_basis((ordinal-start)/length,c);break
                    y=target
                out_last=y
            else:y=held
            block.extend((word(y),inputs[2*i+1]))
        blocks.append(tuple(block))
    return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
