# SPDX-License-Identifier: MIT
"""Independent bounded list/routing contracts, never generated DSP evaluation.

Exact list observer: length*8**5 + sum(item[i]*8**i). For0..5 items in0..7
this is injective, preserves trailing zeros, and stays exact in binary32.
Drive packs a tag0..3 and an independent3-bit crumb in its fractional part.
An explicit arm prevents startup defaults from contaminating event counts.
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
for n in('append','prepend'):add(n+'-two-values',n,'4 5')
add('join-two-inputs','join','2');add('list-join-two-values','list.join','4 5')
add('list-reverse','list.rev')
for shift in(-1,1):add('list-rotate-'+('left'if shift<0 else'right'),'list.rot',str(shift),variant='left'if shift<0 else'right')
for n in('list.slice','list.ecils'):
    for out in(0,1):add(n.replace('.','-')+'-out'+str(out),n,'1',out)
for out in(0,1):add('list-sub-out'+str(out),'list.sub','1 @base 0',out,'list'if out==0 else'scalar')
add('list-intersection','list.sect','1 4');add('list-swap-zero-two','list.swap','0 2')
for direction in(1,-1):add('list-sort-'+('ascending'if direction==1 else'descending'),'list.sort',str(direction),variant='ascending'if direction==1 else'descending')
for n in('list.median','list.sum','list.len'):add(n.replace('.','-'),n,kind='scalar')
add('list-nth-element','list.nth','2',kind='scalar');add('list-nth-replacement','list.nth','2 6',1,variant='replacement')
for n in('list.mth','list.index'):
    for out in(0,1):add(n.replace('.','-')+'-out'+str(out),n,'1',out,'scalar'if out==0 else'list')
add('pak-all-inputs','pak','0 0 0');add('pak-cold-input','pak','0 0 0',variant='cold-only')
for out in(0,1,2):add('unpack-out'+str(out),'unpack','0 0 0',out,'scalar')
for out in(0,1,2):add('unjoin-single-out'+str(out),'unjoin','2 1',out,'scalar'if out<2 else'list',variant='single')
for out in(0,1):add('unjoin-pair-out'+str(out),'unjoin','1 2',out,variant='pair')
CONTROL_LISTS=((0,),(0,0),(0,0,0),(1,2,3,0),(7,0,1,4,5))
for i,items in enumerate(CONTROL_LISTS,1):add('message-observer-'+str(i),'message',' '.join(map(str,items)),variant='control'+str(i))
for n in('route','routepass'):
    for out in(0,1,2):add(n+'-out'+str(out),n,'1 2',out,variant='tagged')
for out in(0,1,2):add('gate-out'+str(out),'gate','3 0',out,'scalar')
add('switch-three-inputs','switch','3',kind='scalar')
for out in(0,1):add('split-out'+str(out),'split','1 2',out,'scalar')
for n in('select','sel'):
    for out in(0,1,2):add(n+'-out'+str(out),n,'1 2',out,'count')
for out in(0,1):add('swap-out'+str(out),'swap','0',out,'scalar')
add('swap-right-before-left','swap','0',kind='scalar',variant='order')
MODEL_SPECS={2800+i:dict(s,operation=s['exact_name'])for i,s in enumerate(SPECS)}
MODEL_NAMES={m:s['id']for m,s in MODEL_SPECS.items()}
MODELS=frozenset(MODEL_SPECS)
ABSOLUTE_TOLERANCES={m:0 for m in MODELS}
REFERENCE_POLICIES={m:'documented-bounded-list-and-event-routing'for m in MODELS}
_CALLS=(0,1,2,3,4,5,6,7,8,9,10,10,10,11,12,15,16,16,17,18,19)
_TAGS=(0,1,2,3,2,0,1,1,3,0,0,1,2,2,3,1,0,2,3,0,1)
PILOT_WORDS=(0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,
             0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff)
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def spec(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown event-routing model')
    return MODEL_SPECS[model]
def parameters():
    return[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0),
           dict(id='arm',minimum=0.,maximum=1.,initial=0.,exponent=1.,steps=0)]
def drive_events(model):
    spec(model)
    return[dict(before_call=c,id='drive',value=float(t+((3*i+1)%8)/8))for i,(c,t)in enumerate(zip(_CALLS,_TAGS))]
def parameter_events(model):return[dict(before_call=0,id='arm',value=1.)]+drive_events(model)
def input_words(frames=256):
    if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
    return tuple(w for i in range(frames)for w in(word((i//16-8)/8),PILOT_WORDS[i%16]))
def case_input_words(model,frames=256):spec(model);return input_words(frames)
def encode(items):
    if type(items)not in(list,tuple)or len(items)>5 or any(type(x)is not int or not 0<=x<8 for x in items):
        raise ValueError('Observer requires0..5 digits in0..7')
    return len(items)*32768+sum(x*(8**i)for i,x in enumerate(items))
def decode(code):
    if type(code)is not int or not 0<=code<=196607:raise ValueError('Invalid list code')
    size,digits=divmod(code,32768)
    if size>5 or digits>=8**size:raise ValueError('Noncanonical list code')
    result=[]
    for _ in range(size):digits,digit=divmod(digits,8);result.append(digit)
    return tuple(result)
def input_list(x,tagged=False):
    tag=math.floor(x);crumb=int((x-tag)*8)
    if not 0<=tag<4 or not 0<=crumb<8:raise ValueError('Drive outside tag/crumb domain')
    return[tag,7-tag,crumb]if tagged else[7-tag,tag,crumb]
def operation(s,x):
    n=s['exact_name'];out=s['observed_outlet'];v=s['variant'];tag=math.floor(x);crumb=int((x-tag)*8)
    items=input_list(x,n in('route','routepass'))
    if n=='message':return list(CONTROL_LISTS[int(v.removeprefix('control'))-1])
    if n in('append','join','list.join'):return items+[4,5]
    if n=='prepend':return[4,5]+items
    if n=='list.rev':return items[::-1]
    if n=='list.rot':return items[1:]+items[:1]if v=='left'else items[-1:]+items[:-1]
    if n=='list.slice':return items[:1]if out==0 else items[1:]
    if n=='list.ecils':return items[:-1]if out==0 else items[-1:]
    if n=='list.sub':
        indexes=[i for i,a in enumerate(items)if a==1]
        return indexes if out==0 else len(indexes)
    if n=='list.sect':return[a for a in items if a in(1,4)]
    if n=='list.swap':return[items[2],items[1],items[0]]
    if n=='list.sort':return sorted(items,reverse=v=='descending')
    if n=='list.median':return sorted(items)[1]
    if n=='list.sum':return sum(items)
    if n=='list.len':return len(items)
    if n=='list.nth':return items[1]if out==0 else[items[0],6,items[2]]
    if n in('list.mth','list.index'):return items[1]if out==0 else[items[0],items[2]]
    if n=='pak':return[0,crumb,0]if v=='cold-only'else items
    if n=='unpack':return items[out]
    if n=='unjoin':return(items[out]if out<2 else items[2:])if v=='single'else(items[:2]if out==0 else items[2:])
    if n in('route','routepass'):
        selected=0 if tag==1 else 1 if tag==2 else 2
        if selected!=out:return None
        return items if n=='routepass'or out==2 else items[1:]
    if n=='gate':return x+4 if tag==out+1 else None
    if n=='switch':return x+3+tag if tag else None
    if n=='split':return x if (1<=x<=2)==(out==0)else None
    if n in('select','sel'):
        selected=0 if tag==1 else 1 if tag==2 else 2
        return 1 if out==selected else None
    if n=='swap':return 7-tag-crumb if v=='order'else 7-tag if out==0 else crumb
    raise ValueError('Missing routing contract')
def reference_blocks(model,inputs,call_count=20):
    s=spec(model);inputs=tuple(inputs)
    if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Invalid callback count')
    if inputs!=input_words():raise ValueError('Input differs from authored finite vector')
    es=parameter_events(model)
    if es!=[dict(before_call=0,id='arm',value=1.)]+drive_events(model):raise ValueError('Arm/drive sequence differs')
    es=es[1:]
    if len(es)!=21 or any(e['id']!='drive'or type(e['value'])is not float or not 0<=e['value']<4 or
        type(e['before_call'])is not int or not 0<=e['before_call']<20 for e in es)or any(a['before_call']>b['before_call']for a,b in zip(es,es[1:])):
        raise ValueError('Invalid ordered drive schedule')
    held=0;index=0;blocks=[]
    for c in range(call_count):
        while index<len(es)and es[index]['before_call']==c:
            result=operation(s,value(word(es[index]['value'])))
            if result is not None:
                if s['output_kind']=='count':held+=result
                else:held=encode(result)if s['output_kind']=='list'else result
            index+=1
        blocks.append(tuple(w for right in inputs[1::2]for w in(word(held),right)))
    return tuple(blocks)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
