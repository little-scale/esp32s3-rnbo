# SPDX-License-Identifier: MIT
"""Independent direct-producer partition schedule and history convolution."""
import math,struct
FRAMES=4096
RATE=44100
MAX_BLOCK=256
RESETS=(513,1024,2051,3001)
PREPARES=(257,1300)
PARTITIONS=(1,2,7,255,256,0)
MIXED=(1,2,7,255,256,3,17)
PATTERN=(.25,-.125,.5,0.,-.25,.125,-.5)
LIMIT=2e-6
PROGRAMS=((1,'history-feedback'),(2,'two-history-swap'),(3,'three-history-rotation'))
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def input_words(stimulus):
 if stimulus not in('dyadic','boundary-impulses'):raise ValueError('Unknown stimulus')
 result=[]
 for n in range(FRAMES):
  pair=tuple(PATTERN[(n+ch*3)%7]for ch in(0,1))if stimulus=='dyadic'else tuple((.25 if n%256==0 else .125 if n%256==1 else -.5 if n%256==255 else 0.)*(1 if ch==0 else -1)for ch in(0,1))
  result.extend(word(v)for v in pair)
 return tuple(result)
def truth_at(model,n,epoch,inputs):
 if model not in(1,2,3)or not 0<=epoch<=n<FRAMES or len(inputs)!=FRAMES*2:raise ValueError('Invalid model/frame/epoch')
 if model==1:
  history=sum(math.ldexp(value(inputs[2*(n-age)]),-(age-1))for age in range(1,min(64,n-epoch)+1))
  return value(inputs[2*n])+.5*history,history
 return float(1+(n-epoch)%model),float(1+(n-epoch+1)%model)
def expected_words(model,stimulus):
 inputs=input_words(stimulus);epoch=0;result=[]
 for n in range(FRAMES):
  if n in RESETS:epoch=n
  result.extend(word(v)for v in truth_at(model,n,epoch,inputs))
 return tuple(result)
def reset_witnesses(model,stimulus):
 inputs=input_words(stimulus);epoch=0;result=[]
 for n in RESETS:
  before=truth_at(model,n,epoch,inputs);after=truth_at(model,n,n,inputs);separation=max(abs(a-b)for a,b in zip(before,after));result.append(dict(frame=n,maximum_pair_separation=separation,observable_at_limit=separation>4*LIMIT));epoch=n
 return result
def chunks(partition):
 if type(partition)is not int or partition not in PARTITIONS:raise ValueError('Unknown nominal partition')
 n=chunk=0;result=[]
 while n<FRAMES:
  count=partition or MIXED[chunk%len(MIXED)];chunk+=1;count=min(count,FRAMES-n)
  for event in RESETS+PREPARES:
   if event>n:count=min(count,event-n)
  result.append((n,count));n+=count
 return tuple(result)
def render_cases():
 return((0,1),)+tuple((repeat,partition)for repeat in(1,2)for partition in PARTITIONS)
