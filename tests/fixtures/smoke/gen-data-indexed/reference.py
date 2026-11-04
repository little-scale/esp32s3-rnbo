# SPDX-License-Identifier: MIT
"""Independent small local-array, FIFO, metadata and interpolation references.

All content-dependent cases explicitly initialize 7x2 cells once at the first
sample. No assumption about allocator-zeroed memory or physical channel layout
enters the model. Gen API channels are zero-based; sample indices are explicit.
The full twenty-block epoch is continuous. Feedback is a fresh input convolution,
not a Float32 implementation replay. All comparisons round once to output words.
"""
import math
import struct

BLOCK_FRAMES=256
REFERENCE_CALL_COUNT=20
MODEL_NAMES={950:'data-dimensions',951:'dim-local',952:'channels-local',
             953:'peek-ring-read-before-write',954:'poke-write-readback',
             955:'nearest-initialized-samples',956:'sample-initialized-linear',
             957:'data-seven-sample-feedback'}
MODELS=frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES={m:2e-6 if m in(956,957)else 0 for m in MODELS}
TABLE=((-0.75,0.125,1.,-0.5,0.25,0.875,-0.125),
       (0.5,-1.,0.25,0.75,-0.25,0.125,1.))
DATA=(0.,.125,-.0625,.25,-.125,-0.,.0625,-.25,
      0.,-.125,.25,.125,-.25,.0625,-.0625,.125)
FEEDBACK_GAINS=(.5,.25)
FEEDBACK_TERMS=64
FEEDBACK_TAIL_BOUNDS=(2**-65,2**-128/3)


def word(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]


def _model(model):
    if type(model)is not int or model not in MODELS:
        raise ValueError('Unknown Gen local-data model')


def input_words(frames=256):return case_input_words(953,frames)


def case_input_words(model,frames=256):
    _model(model)
    if type(frames)is not int or frames!=BLOCK_FRAMES:
        raise ValueError('Gen local-data references require256-frame vectors')
    result=[]
    for n in range(frames):
        if model==955:pair=(n%7,(n*3+2)%7)
        elif model==956:pair=((n%25)/4,((n*7+3)%25)/4)
        else:pair=(DATA[n%16],DATA[(n*5+3)%16])
        result.extend(word(v)for v in pair)
    return tuple(result)


def _inputs(model,inputs):
    inputs=tuple(inputs)
    if len(inputs)!=512:raise ValueError('Expected one stereo256-frame vector')
    for w in inputs:
        if type(w)is not int or not 0<=w<=0xffffffff or(w&0x7f800000)==0x7f800000:
            raise ValueError('Finite binary32 inputs required')
        x=value(w)
        if model==955:valid=0<=x<=6 and x==math.floor(x)
        elif model==956:valid=0<=x<=6 and x*4==math.floor(x*4)
        else:valid=abs(x)<=.25
        if not valid:raise ValueError('Input exceeds predeclared data/index domain')
    return inputs


def reference_blocks(model,inputs,call_count=20):
    _model(model)
    if type(call_count)is not int or not 1<=call_count<=REFERENCE_CALL_COUNT:
        raise ValueError('Invalid continuous callback count')
    inputs=_inputs(model,inputs)
    data=tuple(value(w)for w in inputs)
    memory=[[0]*7 for _ in range(2)]  # explicit source initialization, words for exact copies
    blocks=[]
    def sample(n,ch):return 0. if n<0 else data[2*(n%256)+ch]
    for call in range(call_count):
        output=[]
        for frame in range(BLOCK_FRAMES):
            n=call*BLOCK_FRAMES+frame
            x,y=data[2*frame:2*frame+2]
            if model==950:pair=(7.,2.)
            elif model==951:
                output.extend((word(7),inputs[2*frame+1]));continue
            elif model==952:
                output.extend((word(2),inputs[2*frame+1]));continue
            elif model in(953,954):
                index=n%7
                if model==953:
                    pair_words=(memory[0][index],memory[1][index])
                    memory[0][index],memory[1][index]=inputs[2*frame:2*frame+2]
                else:
                    memory[0][index],memory[1][index]=inputs[2*frame:2*frame+2]
                    pair_words=(memory[0][index],memory[1][(index+1)%7])
                output.extend(pair_words);continue
            elif model==955:pair=(TABLE[0][int(x)],TABLE[1][int(y)])
            elif model==956:
                pair=[]
                for ch,index in enumerate((x,y)):
                    lower=math.floor(index);upper=min(lower+1,6);fraction=index-lower
                    pair.append((1-fraction)*TABLE[ch][lower]+fraction*TABLE[ch][upper])
            else:
                pair=[math.fsum(gain**k*sample(n-7*k,ch)
                       for k in range(min(FEEDBACK_TERMS,n//7+1)))
                       for ch,gain in enumerate(FEEDBACK_GAINS)]
            output.extend(word(v)for v in pair)
        blocks.append(tuple(output))
    return tuple(blocks)


def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]
