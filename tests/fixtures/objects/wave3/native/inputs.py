# SPDX-License-Identifier: MIT
"""Original bounded deterministic excitation, independent of generated DSP."""
import array,math,struct
f32=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]
word=lambda x:struct.unpack('<f',struct.pack('<I',x))[0]
DATA=(.125,.25,.375,.5,.625,.75,-.125,-.25,-.375,-.5,-.625,-.75,-0.,0.)
TRIGGER=(0.,.5,.5,word(0x3f000001),.75,.75,.5,word(0x3f000001),0.,word(1),0.,-0.,-.5,-.5,0.,1.,1.,0.,-.75,.25)
FREQUENCIES=(-1000.,0.,.05,.070187,1.,20.,1000.,22050.,100000.)
RATES=(-256.,-1.,-.5,0.,word(1),.5,1.,2.,8.,256.)
def fill(spec,frames):
 kind=spec['kind'];hold=spec.get('hold_frames',1);assert type(frames)is int and frames>0 and type(hold)is int and hold>0
 out=array.array('f')
 for i in range(frames):
  if kind=='audio-impulse-v1':
   x=.75 if i==0 else -.5 if i==255 else .625 if i==256 else -.25 if i==4096 else 0.
   y=-.625 if i==7 else .5 if i==256 else -.375 if i==257 else .25 if i==8191 else 0.
  elif kind=='audio-long-dc-step-v1':
   x=.75 if i<65536 else -.5;y=-.375 if i<65536 else .625
  elif kind=='audio-step-grid-v1':
   left=(.75,-.5,.25,0.,-.75,.5);right=(-.25,.625,-.375,.125,.5,-.625)
   x=left[(i//257)%len(left)];y=right[(i//31)%len(right)]
   if i==255:x=-.75
   if i==256:x=.75
   if i==511:y=.75
   if i==512:y=-.75
  elif kind=='audio-mixed-v1':
   x=.21*math.sin(2*math.pi*137*i/44100)+.17*math.cos(2*math.pi*997*i/44100)+(.125 if i>=1024 else 0)
   y=.19*math.sin(2*math.pi*199*i/44100)-.23*math.cos(2*math.pi*613*i/44100)-(.125 if i>=2048 else 0)
  elif kind in ('onepole-signal-v1','slide-signal-v1'):
   x=(.625,-.5,.25,-.75,.5,0.)[(i//127)%6]+.0625*math.sin(2*math.pi*173*i/44100)
   values=FREQUENCIES if kind=='onepole-signal-v1'else RATES;y=values[(i//hold)%len(values)]
  elif kind=='sah-grid-v1':x=DATA[i%len(DATA)];y=TRIGGER[i%len(TRIGGER)]
  elif kind=='sah-plateau-v1':
   x=DATA[i%len(DATA)];y=.5 if i<1024 else -.5 if i<1041 else .75 if i<1100 else 0. if i<1200 else .5
  else:raise ValueError('Unknown declared wave3 stimulus '+kind)
  assert math.isfinite(x)and math.isfinite(y);out.append(f32(x));out.append(f32(y))
 return out.tobytes()
