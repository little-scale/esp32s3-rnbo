# SPDX-License-Identifier: MIT
"""Independent finite alias math, unit conversions and fresh-context contracts.

Fresh transport contract:120quarter-notes/min,480ticks/quarter,stopped,4/4.
Bare samplecount is callback origin; sampleoffset/currenttime/currentsampletime
use the executing sample. MC values use only a declared finite integer screen.
State aliases use absolute prefix/parity, not producer accumulator algorithms.
"""
from fractions import Fraction
import math
import operator
import struct
PASS=(('==p','eqp'),('!=p','neqp'),('<p','ltp'),('<=p','ltep'),('>p','gtp'),('>=p','gtep'))
CONVERSIONS=('beatstohz','beatstoms','beatstosamps','beatstoticks','hztobeats','hztoticks','mstobeats','mstoticks','sampstobeats','sampstoticks','tickstobeats','tickstohz','tickstoms','tickstosamps','tickstosamples')
NAMES=tuple(a for a,b in PASS)+('!-','!/','!%','^^','?','minus','plusequals','mulequals','+=','*=','compound-add-state','compound-multiply-state',
 'currenttime','samplecount','sampleoffset','samplerate','vectorsize','mc_channel','mc_channelcount','currentsampletime','voice','voiceindex',
 'tempo','transport','beattime','timesignature','tempoatsample','transportatsample','beattimeatsample','timesignatureatsample')+CONVERSIONS
MODEL_NAMES={1900+i:n for i,n in enumerate(NAMES)}
MODELS=frozenset(MODEL_NAMES)
CONVERSION_LIMITS={'beatstohz':2e-6,'beatstoms':0,'beatstosamps':0,'beatstoticks':0,'hztobeats':2e-6,'hztoticks':2e-3,'mstobeats':2e-9,'mstoticks':5e-7,'sampstobeats':1e-10,'sampstoticks':2e-8,'tickstobeats':2e-9,'tickstohz':2e-3,'tickstoms':1e-6,'tickstosamps':2e-5,'tickstosamples':2e-5}
ABSOLUTE_TOLERANCES={m:(2e-5 if n=='currenttime'else CONVERSION_LIMITS.get(n,0))for m,n in MODEL_NAMES.items()}
GRID=(-1.,-.75,-.5,-.25,-.125,-0.,0.,.125,.25,.375,.5,.625,.75,.875,1.,.25)
NONZERO=(-8.,-4.,-2.,-1.,-.5,-.25,-.125,-.0625,.0625,.125,.25,.5,1.,2.,4.,8.)
POS=tuple((i+1)/8 for i in range(16))
PREDICATES=(operator.eq,operator.ne,operator.lt,operator.le,operator.gt,operator.ge)
BLOCK_FRAMES=256
REFERENCE_CALL_COUNT=20

def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def name(model):
 if type(model)is not int or model not in MODELS:raise ValueError('Unknown context/alias model')
 return MODEL_NAMES[model]
def case_input_words(model,frames=256):
 n=name(model)
 if type(frames)is not int or frames!=256:raise ValueError('Expected256frames')
 grid=NONZERO if n in('!/', '!%')else POS if n in CONVERSIONS else GRID
 if n in('mulequals','*=','compound-multiply-state'):return tuple(word(v)for i in range(frames)for v in(-1 if i==0 else 1,-1 if i==31 else 1))
 return tuple(word(v)for i in range(frames)for v in(grid[i//16],grid[i%16]))
def input_words(frames=256):return case_input_words(1900,frames)
def convert(n,x):
 x=Fraction(x)
 if n in('beatstohz','hztobeats'):return 2/x
 if n=='beatstoms':return 500*x
 if n=='beatstosamps':return 22050*x
 if n=='beatstoticks':return 480*x
 if n in('hztoticks','tickstohz'):return 960/x
 if n=='mstobeats':return x/500
 if n=='mstoticks':return x*Fraction(24,25)
 if n=='sampstobeats':return x/22050
 if n=='sampstoticks':return x*Fraction(16,735)
 if n=='tickstobeats':return x/480
 if n=='tickstoms':return x*Fraction(25,24)
 if n in('tickstosamps','tickstosamples'):return x*Fraction(735,16)
 raise ValueError('Unknown unit conversion')
def reference_blocks(model,inputs,call_count=20):
 n=name(model);inputs=tuple(inputs)
 if type(call_count)is not int or not 1<=call_count<=20:raise ValueError('Expected1..20callbacks')
 if inputs!=case_input_words(model):raise ValueError('Context/alias input differs from exact authored vector')
 pairs=[tuple(map(value,inputs[i:i+2]))for i in range(0,512,2)];prefix=[[0],[0]]
 for pair in pairs:
  for ch in(0,1):prefix[ch].append(prefix[ch][-1]+pair[ch]/64)
 result=[]
 for call in range(call_count):
  block=[]
  for frame,(x,y)in enumerate(pairs):
   age=call*256+frame
   if model<1906:
    p=PREDICATES[model-1900];pair=(x*int(p(x,y)),y*int(p(y,x)))
   elif n in('!-','minus'):pair=(y-x,x-y)if n=='!-'else(x-y,y-x)
   elif n=='!/':pair=(Fraction(y)/Fraction(x),Fraction(x)/Fraction(y))
   elif n=='!%':
    rem=lambda a,b:Fraction(a)-math.trunc(Fraction(a)/Fraction(b))*Fraction(b)
    pair=(rem(y,x),rem(x,y))
   elif n=='^^':pair=(int((x!=0)!=(y!=0)),int((y!=0)!=(x!=0)))
   elif n=='?':pair=(x if x!=0 else y,y if y!=0 else x)
   elif n in('plusequals','+=','compound-add-state'):pair=tuple(call*prefix[ch][-1]+prefix[ch][frame+1]for ch in(0,1))
   elif n in('mulequals','*=','compound-multiply-state'):pair=((-1)**(call+1),(-1)**(call+int(frame>=31)))
   elif n=='currenttime':pair=(age*1000/44100,y)
   elif n=='samplecount':pair=(call*256,y)
   elif n=='sampleoffset':pair=(frame,y)
   elif n=='currentsampletime':pair=(age,y)
   elif n=='samplerate':pair=(44100,y)
   elif n=='vectorsize':pair=(256,y)
   elif n in('mc_channel','mc_channelcount'):pair=(1,y) # finite integer screen only
   elif n in('voice','voiceindex','transport','transportatsample','beattime','beattimeatsample'):pair=(0,y)
   elif n in('tempo','tempoatsample'):pair=(120,y)
   elif n in('timesignature','timesignatureatsample'):pair=(4,4)
   elif n in CONVERSIONS:pair=(convert(n,x),convert(n,y))
   else:raise AssertionError('Missing reference')
   block.extend(word(v)for v in pair)
  result.append(tuple(block))
 return tuple(result)
