# SPDX-License-Identifier: MIT
"""Independent finite math: interpolation bases, fades, coordinates and shaping.

No generated-DSP evaluation or captured outputs construct this oracle. Scalar
polynomials are expressed as Lagrange/Hermite/B-spline bases; trigonometric and
logarithmic references are ideal binary64 math rounded once to binary32. Limits
are fixed before compilation. Constructor and inlet forms remain distinct.
"""
import math
import struct
BLOCK_FRAMES=256
PREPARE_ZERO_WARM_BLOCKS=0
REFERENCE_CALL_COUNT=20
PILOT_RIGHT_BIT_EXACT=True
C4=(-.5,.25,1.25,-.75)
C6=(-1.,.5,-.25,1.25,-.75,2.)
SPECS=[]
def add(identity,name,args='',operation=None,variant='default',outlet=0,tolerance=2e-6):
    SPECS.append(dict(id=identity.replace('.','p'),exact_name=name,fixed_arguments=args,operation=operation or name.removesuffix('~'),variant=variant,observed_outlet=outlet,limit=tolerance))
for y,label in((.75,'positive-y'),(-.75,'negative-y')):
    for out in(0,1):add('cartopol-'+label+'-out'+str(out),'cartopol',str(y),variant=label,outlet=out)
for out in(0,1):add('poltocar-out'+str(out),'poltocar',outlet=out)
for mode in('cosine','cubic','fastcubic','spline','spline6'):
    pts=(.25,1.25)if mode=='cosine'else C6 if mode=='spline6'else C4
    add(mode+'interp-event',mode+'interp',' '.join(map(str,pts)),operation='interpolation',variant=mode,tolerance=1e-3 if mode=='cosine'else 2e-6)
for name in('interp','interp~'):
    for mode in('linear','cosine','cubic','fastcubic','spline','spline6'):
        pts=(.25,1.25)if mode in('linear','cosine')else C6 if mode=='spline6'else C4
        add(name.replace('~','-signal')+'-'+mode,name,' '.join(map(str,pts))+' @mode '+mode,operation='interpolation',variant=mode,tolerance=1e-3 if mode=='cosine'else 2e-6)
    add(name.replace('~','-signal')+'-spline6-inlets',name,'@mode spline6',operation='interpolation',variant='spline6-inlets')
for slope in(2.,.75):add('kink-slope'+str(slope),'kink',str(slope),variant=str(slope))
for q in(.25,.75):add('mix-weight'+str(q),'mix',str(q)+' -0.5',variant=str(q),tolerance=0)
add('mix-moving-weight','mix',variant='moving-weight',tolerance=0)
for name in('pan','pan~'):
    for mode in('lin','eqpower','cos'):
        for out in(0,1):add(name.replace('~','-signal')+'-'+mode+'-out'+str(out),name,'2 @inputs 1 @fademode '+mode+' @boundmode clip @positionmode phase',variant=mode,outlet=out,tolerance=0 if mode=='lin'else 2e-6)
for name in('xfade','xfade~'):
    for mode in('lin','eqpower','cos'):add(name.replace('~','-signal')+'-'+mode,name,'2 @fademode '+mode+' @boundmode clip @positionmode phase',variant=mode,tolerance=0 if mode=='lin'else 2e-6)
add('phasewrap-wide','phasewrap')
for q in(4,8):add('quantize-q'+str(q),'quantize',str(q),variant=str(q),tolerance=0)
for v in('rising','falling'):add('smoothstep-'+v,'smoothstep',variant=v,tolerance=0)
add('t60-decay','t60');add('t60time-duration','t60time',tolerance=1e-4)
for name in('trapezoid','trapezoid~'):
    for args,v in(('.25 .75','plateau'),('.5 .5','triangle')):add(name.replace('~','-signal')+'-'+v,name,args,variant=v,tolerance=0)
for name in('pan','pan~'):add(name.replace('~','-signal')+'-three-wrap',name,'3 @inputs 1 @fademode lin @boundmode wrap @positionmode phase',variant='three-wrap',outlet=2,tolerance=0)
for name in('xfade','xfade~'):add(name.replace('~','-signal')+'-three-wrap',name,'3 @fademode lin @boundmode wrap @positionmode phase',variant='three-wrap',tolerance=0)
MODEL_SPECS={3000+i:s for i,s in enumerate(SPECS)}
MODEL_NAMES={m:s['id']for m,s in MODEL_SPECS.items()}
MODELS=frozenset(MODEL_SPECS)
ABSOLUTE_TOLERANCES={m:s['limit']for m,s in MODEL_SPECS.items()}
REFERENCE_POLICIES={m:'ideal-cosine-screen'if s['variant']=='cosine'else'independent-finite-maths-and-fade-contract'for m,s in MODEL_SPECS.items()}
_CALLS=(0,1,2,3,4,5,6,7,8,9,10,10,10,11,12,15,16,16,17,18,19)
_PHASES=(0.,.25,.5,.75,1.,.125,.875,.875,.0625,.9375,.5,.25,.75,.75,.375,.625,0.,1.,.5,.1875,.8125)
PILOT_WORDS=(0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff)
LEFT=tuple((i-8)/64 for i in range(16))
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def spec(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown mixing/shaping model')
    return MODEL_SPECS[model]
def parameters():return[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0),dict(id='arm',minimum=0.,maximum=1.,initial=0.,exponent=1.,steps=0)]
def drive_events(model):spec(model);return[dict(before_call=c,id='drive',value=x)for c,x in zip(_CALLS,_PHASES)]
def parameter_events(model):return[dict(before_call=0,id='arm',value=1.)]+drive_events(model)
def input_words(frames=256):
    if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
    return tuple(w for i in range(frames)for w in(word(LEFT[i//16]),PILOT_WORDS[i%16]))
def case_input_words(model,frames=256):spec(model);return input_words(frames)
def hermite(t,x,y,m0,m1):return(2*t**3-3*t*t+1)*x+(t**3-2*t*t+t)*m0+(-2*t**3+3*t*t)*y+(t**3-t*t)*m1
def bspline5(x):return sum((-1)**k*math.comb(6,k)*max(x+3-k,0.)**5 for k in range(7))/120
def interpolate(mode,t):
    if mode=='linear':return .25+t
    if mode=='cosine':return .25+.5*(1-math.cos(math.pi*t))
    if mode=='cubic':
        nodes=(-1,0,1,2)
        return sum(v*math.prod((t-nodes[j])/(nodes[i]-nodes[j])for j in range(4)if j!=i)for i,v in enumerate(C4))
    if mode in('spline','fastcubic'):
        a,b,c,d=C4;f=.5 if mode=='spline'else 1
        return hermite(t,b,c,f*(c-a),f*(d-b))
    if mode in('spline6','spline6-inlets'):return sum(v*bspline5(t-pos)for v,pos in zip(C6,(-2,-1,0,1,2,3)))
    raise ValueError('Unknown interpolation mode')
def gain(position,channel,count,mode,wrap=False):
    p=position*(count-1)
    if wrap:
        p=p%count
        if channel==0 and p>=count-1:p-=count
    else:p=min(count-1,max(0.,p))
    d=abs(p-channel)
    if d>=1:return 0.
    if mode=='lin':return 1-d
    if mode=='eqpower':return math.sqrt(1-d)
    if mode=='cos':return math.cos(math.pi*d/2)
    raise ValueError('Unknown fade mode')
def operation(s,t):
    if not math.isfinite(t)or not 0<=t<=1:raise ValueError('Phase outside unit domain')
    op=s['operation'];v=s['variant'];out=s['observed_outlet']
    if op=='cartopol':
        x=4*t-2;y=.75 if v=='positive-y'else-.75
        return math.hypot(x,y)if out==0 else math.atan2(y,x)
    if op=='poltocar':return .75*(math.cos(4*t-2)if out==0 else math.sin(4*t-2))
    if op=='interpolation':return interpolate(v,t)
    if op=='kink':
        slope=float(v);cross=.5/slope
        return slope*t if t<=cross else .5+.5*(t-cross)/(1-cross)
    if op=='mix':
        if v=='moving-weight':return .75*(1-t)-.5*t
        q=float(v);return(4*t-2)*(1-q)-.5*q
    if op in('pan','xfade'):
        wrap=v=='three-wrap';count=3 if wrap else 2;mode='lin'if wrap else v;p=4*t-1 if wrap else t
        return .75*gain(p,out,count,mode,wrap)if op=='pan'else sum(a*gain(p,i,count,mode,wrap)for i,a in enumerate((.75,-.5,.25)[:count]))
    if op=='phasewrap':return(16*t-8+math.pi)%(2*math.pi)-math.pi
    if op=='quantize':q=int(v);return math.floor((4*t-2)*q+.5)/q
    if op=='smoothstep':
        a,b=(.25,.75)if v=='rising'else(.75,.25);x=min(1.,max(0.,(t-a)/(b-a)));return x*x*(3-2*x)
    if op=='t60':return 10**(-3/(1+1024*t))
    if op=='t60time':return math.log(.001)/math.log(.25+.625*t)
    if op=='trapezoid':
        phase=t%1;up,down=(.25,.75)if v=='plateau'else(.5,.5)
        return phase/up if phase<up else(1-phase)/(1-down)if phase>down else 1.
    raise ValueError('Missing maths contract')
def reference_blocks(model,inputs,call_count=20):
    s=spec(model);inputs=tuple(inputs)
    if type(call_count)is not int or not 1<=call_count<=20 or inputs!=input_words():raise ValueError('Unexpected input/count')
    es=parameter_events(model)
    if es!=[dict(before_call=0,id='arm',value=1.)]+drive_events(model):raise ValueError('Unexpected arm/drive schedule')
    es=es[1:];current=0.;index=0;blocks=[]
    for call in range(call_count):
        while index<len(es)and es[index]['before_call']==call:current=value(word(es[index]['value']));index+=1
        block=[]
        for i in range(256):
            t=min(1.,max(0.,value(word(current+value(inputs[2*i])))))if s['exact_name'].endswith('~')else current
            block.extend((word(operation(s,t)),inputs[2*i+1]))
        blocks.append(tuple(block))
    return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
