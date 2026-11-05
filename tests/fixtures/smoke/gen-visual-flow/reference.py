# SPDX-License-Identifier: MIT
"""Independent finite range/conversion math and continuous sample-state models.

Counter explicitly retains the earlier increment-before-output screen, whose
first-value ordering is less explicit in prose. Any disagreement stays visible;
no output-derived policy replaces it. State persists over20*256 samples.
"""
import math
import struct
SPECS=[]
def add(identity,name,bindings,kind='math',variant='default',outlet=0,outputs=1,limit=0):
 SPECS.append(dict(id=identity,name=name,bindings=bindings,kind=kind,variant=variant,observed_outlet=outlet,operator_outputs=outputs,limit=limit))
for n in('delta','change','dcblock'):add(n,n,['a'],kind='state',limit=2e-6 if n=='dcblock'else 0)
add('latch','latch',['a','b'],kind='state')
for threshold,v in((0,'zero'),(.5,'half'),('a','signal')):add('sah-'+v,'sah',['a','b',threshold],kind='state',variant=v)
for up,down in((2,4),(4,2)):add(f'slide-up{up}-down{down}','slide',['a',up,down],kind='state',variant=f'{up}/{down}',limit=2e-6)
for n in('accum','plusequals'):
 for reset in(0,'b'):add(n+('-reset-signal'if reset=='b'else'-reset-zero'),n,['a',reset],kind='state',variant='signal-reset'if reset=='b'else'zero-reset')
for out in(0,1,2):add('counter-out'+str(out),'counter',[1,0,7],kind='state',variant='increment-before-output',outlet=out,outputs=3)
for n in('clamp','clip','fold','wrap'):add(n,n,['a',-1,1])
add('mix','mix',['a','b',.25]);add('smoothstep','smoothstep',[-1,1,'a']);add('scale','scale',['a',-1,1,-2,2,1]);add('interp','interp',['a','b','negative-b'])
for n in('phasewrap','pass','fixnan','isnan'):add(n,n,['a'],limit=2e-6 if n=='phasewrap'else 0)
for n in('absdiff','mod','%'):add('mod-symbol'if n=='%'else n,n,['a','b'])
add('triangle','triangle',['a',.5])
for n in('cartopol','poltocar'):
 for out in(0,1):add(n+'-out'+str(out),n,['a','b'],outlet=out,outputs=2,limit=2e-6)
for n in('mtof','ftom','atodb','dbtoa','t60','t60time'):add(n,n,['a',440]if n in('mtof','ftom')else['a'],limit=5e-4 if n in('mtof','ftom','t60time')else 2e-6)
MODEL_SPECS={3200+i:s for i,s in enumerate(SPECS)}
MODEL_NAMES={m:s['id']for m,s in MODEL_SPECS.items()};MODELS=frozenset(MODEL_SPECS)
ABSOLUTE_TOLERANCES={m:s['limit']for m,s in MODEL_SPECS.items()}
REFERENCE_POLICIES={m:'declared-counter-increment-before-output'if s['name']=='counter'else'independent-continuous-sample-state'if s['kind']=='state'else'finite-ideal-range-and-conversion-math'for m,s in MODEL_SPECS.items()}
PREPARE_ZERO_WARM_BLOCKS=0
REFERENCE_CALL_COUNT=20
PILOT_RIGHT_BIT_EXACT=True
STATE_A=(0.,.25,.25,-.5,-.5,-0.,1.,1.,-1.,-1.,.5,.5,0.,.125,.125,.75)
STATE_B=(0.,1.,1.,-0.,-1.,-1.,.5,.5,0.,.25,-.25,-.25,-1.,1.,1.,1.)
WIDE=(-4.,-2.,-1.5,-1.,-.75,-.5,-.25,-0.,0.,.25,.5,.75,1.,1.5,2.,4.)
NONZERO=(-2.,-1.5,-1.,-.75,-.5,-.25,-.125,-.0625,.0625,.125,.25,.5,.75,1.,1.5,2.)
UNIT=(0.,.0625,.125,.1875,.25,.3125,.375,.4375,.5,.5625,.625,.75,.8125,.875,.9375,1.)
POSITIVE=tuple(n/8 for n in range(1,17))
MIDI=(36.,48.,55.,57.,60.,60.25,61.,64.,67.,69.,69.25,70.,72.,76.,81.,84.)
FREQUENCY=tuple(440*2**((n-69)/12)for n in MIDI)
AMPLITUDE=(.5,.5625,.625,.6875,.75,.8125,.875,.9375,1.,1.0625,1.125,1.25,1.375,1.5,1.75,2.)
DECIBELS=(-24.,-21.,-18.,-15.,-12.,-9.,-6.,-3.,-0.,0.,1.,2.,3.,4.,5.,6.)
DECAY=(1.,2.,4.,8.,16.,32.,64.,128.,256.,512.,1000.,2048.,4096.,8192.,16384.,32768.)
MULTIPLIER=(.25,.375,.5,.5625,.625,.6875,.75,.8125,.875,.90625,.9375,.953125,.96875,.9765625,.984375,.9921875)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def spec(m):
 if type(m)is not int or m not in MODELS:raise ValueError('Unknown visual flow model')
 return MODEL_SPECS[m]
def planes(m):
 s=spec(m);n=s['name']
 if s['kind']=='state':return STATE_A,STATE_B
 a,b=WIDE,WIDE
 if n in('mod','%','cartopol'):a,b=NONZERO,NONZERO
 if n=='poltocar':a,b=POSITIVE,tuple((i-8)/8 for i in range(16))
 if n in('triangle','interp'):a=UNIT
 a={'mtof':MIDI,'ftom':FREQUENCY,'atodb':AMPLITUDE,'dbtoa':DECIBELS,'t60':DECAY,'t60time':MULTIPLIER}.get(n,a)
 return a,b
def domains(m):return[[min(p),max(p)]for p in planes(m)]
def input_words(frames=256):return case_input_words(3200,frames)
def case_input_words(m,frames=256):
 s=spec(m);a,b=planes(m)
 if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
 return tuple(word(x)for i in range(frames)for x in(a[i%16]if s['kind']=='state'else a[i//16],b[i%16]))
def stateless(s,a,b):
 n=s['name'];o=s['observed_outlet']
 if n in('clamp','clip'):return min(1.,max(-1.,a))
 if n=='fold':p=(a+1)%4;return -1+p if p<=2 else 3-p
 if n=='wrap':return(a+1)%2-1
 if n=='mix':return .75*a+.25*b
 if n=='scale':return 2*a
 if n=='smoothstep':t=min(1.,max(0.,(a+1)/2));return t*t*(3-2*t)
 if n=='interp':return(1-a)*b-a*b
 if n=='phasewrap':return(a+math.pi)%(2*math.pi)-math.pi
 if n in('pass','fixnan'):return a
 if n=='isnan':return 0.
 if n=='absdiff':return abs(a-b)
 if n in('mod','%'):return math.fmod(a,b)
 if n=='triangle':p=a%1;return 2*p if p<=.5 else 2*(1-p)
 if n=='cartopol':return math.hypot(a,b)if o==0 else math.atan2(b,a)
 if n=='poltocar':return a*(math.cos(b)if o==0 else math.sin(b))
 if n=='mtof':return 440*2**((a-69)/12)
 if n=='ftom':return 69+12*math.log2(a/440)
 if n=='atodb':return 20*math.log10(a)
 if n=='dbtoa':return 10**(a/20)
 if n=='t60':return 10**(-3/a)
 if n=='t60time':return math.log(.001)/math.log(a)
 raise ValueError('Missing math contract')
def reference_blocks(m,inputs,call_count=20):
 s=spec(m);inputs=tuple(inputs)
 if inputs!=case_input_words(m)or type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Unexpected input/count')
 prev=0.;control=0.;state=0.;blocks=[]
 for call in range(call_count):
  block=[]
  for i in range(256):
   a,b=value(inputs[2*i]),value(inputs[2*i+1]);n=s['name']
   if s['kind']!='state':y=stateless(s,a,b)
   elif n=='delta':y=a-prev;prev=a
   elif n=='change':y=float(a>prev)-float(a<prev);prev=a
   elif n=='dcblock':y=a-prev+.9997*state;prev=a;state=y
   elif n=='latch':
    if b!=0:state=a
    y=state
   elif n=='sah':
    threshold=0. if s['variant']=='zero'else .5 if s['variant']=='half'else a
    if control<=threshold<b:state=a
    control=b;y=state
   elif n=='slide':
    up,down=map(int,s['variant'].split('/'));state+=(a-state)/(up if a>state else down);y=state
   elif n in('accum','plusequals'):
    state=0. if s['variant']=='signal-reset'and b!=0 else state+a;y=state
   elif n=='counter':
    ordinal=call*256+i+1;out=s['observed_outlet'];y=ordinal%7 if out==0 else int(ordinal%7==0)if out==1 else ordinal//7
   else:raise ValueError('Missing sample state contract')
   block.extend((word(y),inputs[2*i+1]))
  blocks.append(tuple(block))
 return tuple(blocks)
def reference_words(m,inputs):return reference_blocks(m,inputs,1)[0]
