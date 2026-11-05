# SPDX-License-Identifier: MIT
"""Independent finite list contracts, ordered event state and raw right pilot.

The list code records length and every digit exactly for at most five digits
in 0..7. Accumulated-code scenarios check emission/suppression/chunk sums;
they do not claim a lossless encoding of an arbitrary event sequence.
"""
import math
import struct
BLOCK_FRAMES=256
PREPARE_ZERO_WARM_BLOCKS=0
REFERENCE_CALL_COUNT=20
PILOT_RIGHT_BIT_EXACT=True
SPECS=[]
def add(identity,name,args='',outlet=0,kind='list',variant='default'):
    SPECS.append(dict(id=identity,exact_name=name,fixed_arguments=args,observed_outlet=outlet,output_kind=kind,variant=variant))
for name,args in [('list.thin',''),('list.unique','1 4'),('list.union','1 4'),('list.lace','1 4')]:add(name.replace('.','-'),name,args)
for out in (0,1):
    add('list-delace-out'+str(out),'list.delace',outlet=out)
    add('list-filter-out'+str(out),'list.filter','1 4',out)
    add('list-compare-out'+str(out),'list.compare','1 4',out,'scalar' if out==0 else 'list')
add('list-change-emission-sum','list.change',kind='code-sum')
add('list-change-flag','list.change',outlet=1,kind='scalar')
for variant in ('hot','cold-store-bang'):add('list-reg-'+variant,'list.reg',variant=variant)
add('list-indexmap','list.indexmap','2 0')
add('list-lookup','list.lookup','2 5')
add('list-group-three','list.group','3')
for size in (3,-3):add('list-stream-'+('forward' if size>0 else 'reverse'),'list.stream',str(size),variant='forward' if size>0 else 'reverse')
add('list-stream-ready','list.stream','3',1,'scalar',variant='ready')
for name in ('list.queue','list.stack'):
    for out in (0,1):add(name.replace('.','-')+'-out'+str(out),name,outlet=out,kind='scalar')
for size in (1,2):add('iter-chunk'+str(size),'iter',str(size),kind='code-sum',variant='chunk'+str(size))
for offset in (0,2):add('listfunnel-offset'+str(offset),'listfunnel',str(offset),kind='code-sum',variant='offset'+str(offset))
for name in ('list.queue','list.stack'):
    for out in(0,1):add(name.replace('.','-')+'-bounded-out'+str(out),name,outlet=out,kind='scalar-sum'if out else'scalar',variant='bounded-pop-three')
MODEL_SPECS={2900+i:dict(s,operation=s['exact_name'])for i,s in enumerate(SPECS)}
MODEL_NAMES={m:s['id']for m,s in MODEL_SPECS.items()}
MODELS=frozenset(MODEL_SPECS)
ABSOLUTE_TOLERANCES={m:0 for m in MODELS}
REFERENCE_POLICIES={m:'documented-finite-list-and-ordered-storage'for m in MODELS}
_CALLS=(0,1,2,3,4,5,6,7,8,9,10,10,10,11,12,15,16,16,17,18,19)
_PAIRS=((0,0),(1,4),(1,4),(3,7),(2,2),(0,1),(1,4),(1,0),(3,3),(0,0),(0,0),(1,1),(2,2),(2,2),(3,0),(1,7),(0,4),(2,1),(3,5),(0,2),(1,4))
PILOT_WORDS=(0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def spec(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown extended-list model')
    return MODEL_SPECS[model]
def parameters():return[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0),dict(id='arm',minimum=0.,maximum=1.,initial=0.,exponent=1.,steps=0)]
def drive_events(model):
    spec(model)
    return[dict(before_call=c,id='drive',value=float(t+k/8))for c,(t,k)in zip(_CALLS,_PAIRS)]
def parameter_events(model):return[dict(before_call=0,id='arm',value=1.)]+drive_events(model)
def input_words(frames=256):
    if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
    return tuple(w for i in range(frames)for w in(word((i//16-8)/8),PILOT_WORDS[i%16]))
def case_input_words(model,frames=256):spec(model);return input_words(frames)
def encode(items):
    if type(items)not in(list,tuple)or len(items)>5 or any(type(x)is not int or not 0<=x<8 for x in items):raise ValueError('Observer requires0..5 digits in0..7')
    return len(items)*32768+sum(x*8**i for i,x in enumerate(items))
def digits(x):
    tag=math.floor(x);crumb=int((x-tag)*8)
    if not 0<=tag<4 or not 0<=crumb<8:raise ValueError('Drive outside authored domain')
    return tag,crumb

def event_outputs(model):
    s=spec(model);n=s['exact_name'];out=s['observed_outlet'];v=s['variant'];held=0;previous=None;storage=[];total=0;words=[]
    for e in drive_events(model):
        tag,k=digits(e['value']);a=[7-tag,tag,k];result=None;emissions=None
        if n=='list.thin':result=list(dict.fromkeys(a))
        elif n in('list.unique','list.filter'):
            result=[i for i,x in enumerate(a)if x not in(1,4)]if n=='list.filter'and out==1 else[x for x in a if x not in(1,4)]
        elif n=='list.union':result=a+[x for x in(1,4)if x not in a] # primary help: omit right items already in left
        elif n=='list.lace':result=[a[0],1,a[1],4]
        elif n=='list.delace':result=a[out::2]
        elif n=='list.compare':
            b=[tag,k];different=[i for i,(x,y)in enumerate(zip(b,(1,4)))if x!=y]
            result=int(not different)if out==0 else different if different else None
        elif n=='list.change':
            changed=a!=previous;previous=a
            if out==1:result=int(changed)
            elif changed:emissions=[a]
        elif n=='list.reg':result=a
        elif n=='list.indexmap':result=[a[2],a[0]]
        elif n=='list.lookup':result=[(2,5)[tag%2],(2,5)[k%2]]
        elif n=='list.group':
            storage.append(k)
            if len(storage)==3:result=storage;storage=[]
        elif n=='list.stream':
            storage.append(k);storage=storage[-3:]
            if out==1:result=int(len(storage)==3)
            elif len(storage)==3:result=storage[:]if v=='forward'else storage[::-1]
        elif n in('list.queue','list.stack'):
            storage.extend(a)
            if v=='bounded-pop-three':
                popped=[storage.pop(0 if n=='list.queue'else -1)for _ in range(3)]
                result=popped[-1]if out==0 else 6
            else:
                popped=storage.pop(0 if n=='list.queue'else -1);result=popped if out==0 else len(storage)
        elif n=='iter':
            size=int(s['fixed_arguments']);emissions=[a[i:i+size]for i in range(0,len(a),size)]
        elif n=='listfunnel':emissions=[[i+int(s['fixed_arguments']),x]for i,x in enumerate(a)]
        else:raise ValueError('Missing list contract')
        if emissions is not None:
            total+=sum(encode(x)for x in emissions);held=total
        elif result is not None:
            if s['output_kind']=='scalar-sum':total+=result;held=total
            else:held=encode(result)if s['output_kind']=='list'else result
        if not 0<=held<2**24 or int(held)!=held:raise ValueError('Observer exceeds exact binary32 integer range')
        words.append(word(held))
    return tuple(words)
def reference_blocks(model,inputs,call_count=20):
    spec(model);inputs=tuple(inputs)
    if type(call_count)is not int or not 1<=call_count<=20 or inputs!=input_words():raise ValueError('Unexpected count/input')
    es=drive_events(model);values=event_outputs(model);index=0;held=0;blocks=[]
    for c in range(call_count):
        while index<len(es)and es[index]['before_call']==c:held=values[index];index+=1
        blocks.append(tuple(w for right in inputs[1::2]for w in(held,right)))
    return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
