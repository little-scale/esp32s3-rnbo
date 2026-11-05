# SPDX-License-Identifier: MIT
"""Independent finite list algebra from documented input/output contracts.

No generated list algorithm is replayed. Weighted length-sensitive fingerprints
observe outputs; sorting uses unique values and permutation indices. Ecils uses
published last-N-on-right prose, even where installed metadata is inconsistent.
Scramble checks sum plus a complete distinct-index permutation/mapping invariant,
not a target-fitted random sequence or random-quality claim.
"""
import struct

OPERATIONS=('delace','ecils','filter','indexmap','join','lace','len','median','rot','slice','sort','sum','swap','thin','union')
ROWS=tuple((f'list{op}',op,'flat')for op in OPERATIONS)+tuple((f'list.{op}',op,'dot')for op in OPERATIONS)+tuple((name,name,'flat')for name in('listcompare','listsect','listswapelements','listscramble'))
MODELS=frozenset(range(1200,1200+len(ROWS)))
ABSOLUTE_TOLERANCES={m:0 for m in MODELS}
RIGHT=(-8,-5,-4,-3,-2,-1,-0.,0.,1,2,3,4,5,6,7,8)

def word(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def row(model):
    if type(model)is not int or model not in MODELS:raise ValueError('Unknown list-function model')
    return ROWS[model-1200]
def score(a):return 100*len(a)+sum((i+1)*v for i,v in enumerate(a))
def unique(a):return list(dict.fromkeys(a))
def case_input_words(model,frames=256):
    name,op,syntax=row(model)
    if type(frames)is not int or frames!=256:raise ValueError('List function vector requires256frames')
    result=[]
    for n in range(frames):
        x=(n//16)%7
        y=RIGHT[n%16] if op=='rot'else(n*5+3)%7
        result.extend((word(x),word(y)))
    return tuple(result)
def input_words(frames=256):return case_input_words(1200,frames)

def expected_pair(op,x,y):
    a=[x,2,3,2,5];b=[y,2,9]
    if op=='delace':return score(a[::2]),score(a[1::2])
    if op in('slice','ecils'):
        k=min(len(a),max(0,int(y)))
        if op=='slice':left,right=a[:k],a[k:]
        else:left,right=(a[:-k],a[-k:])if k else(a,[])
        return score(left),score(right)
    if op=='filter':
        entries=[(i,v)for i,v in enumerate(a)if v not in b]
        return score([v for i,v in entries]),score([i for i,v in entries])
    if op=='indexmap':out=[a[i]for i in(4,0,2,1)]
    elif op=='join':out=a+b
    elif op=='lace':out=[v for pair in zip(a,b)for v in pair]
    elif op=='len':return len(a),y
    elif op=='median':return sorted(a)[len(a)//2],y
    elif op=='rot':
        shift=int(y)%len(a);out=a[-shift:]+a[:-shift]if shift else a
    elif op=='sort':
        a=[x,10,30,20,50];indices=sorted(range(5),key=lambda i:a[i],reverse=y<3)
        return score([a[i]for i in indices]),score(indices)
    elif op=='sum':return sum(a),y
    elif op=='swap' or op=='listswapelements':out=[5,2,3,2,x]
    elif op=='thin':out=unique(a)
    elif op=='union':out=unique(a+b)
    elif op=='listsect':out=[v for v in a if v in b]
    elif op=='listcompare':return int(x==y),score([]if x==y else[0])
    elif op=='listscramble':return x+110,1
    else:raise ValueError('Unmodelled list function')
    return score(out),y

def reference_words(model,inputs):
    name,op,syntax=row(model);inputs=tuple(inputs)
    if inputs!=case_input_words(model):raise ValueError('List function vector differs from declared bounded source')
    result=[]
    for i in range(0,512,2):result.extend(word(v)for v in expected_pair(op,*map(value,inputs[i:i+2])))
    return tuple(result)
