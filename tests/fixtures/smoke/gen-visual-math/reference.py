# SPDX-License-Identifier: MIT
"""Independent finite-domain maths for original visual Gen node spellings.

No compiler output or graph traversal is used to derive expected samples.
Left x scans16 dyadic values, right y scans16 per x. Output2 is a raw input2
pilot. Constant aliases have separate graph sources, never inherited status.
"""
import math
import struct
SPEC=[]
def add(name,kind,canonical=None):SPEC.append((name,kind,canonical or name))
for name,op in(('add','+'),('sub','-'),('mul','*'),('div','/')):add(name,'binary',op)
for name,symbol in(('lt','<'),('lte','<='),('gt','>'),('gte','>='),('eq','=='),('neq','!='),
                    ('ltp','<p'),('ltep','<=p'),('gtp','>p'),('gtep','>=p'),('eqp','==p'),('neqp','!=p'),
                    ('and','&&'),('or','||'),('xor','^^')):
 add(name,'binary',symbol);add(symbol,'binary',symbol)
for name in('not','!','bool'):add(name,'unary','not'if name=='!'else name)
for name in('acos','acosh','asin','asinh','atan','atanh','cos','cosh','sin','sinh','tan','tanh','exp','exp2','log','ln','log2','log10','sqrt','ceil','floor','trunc','fract','sign','fastsin','fastcos','fasttan','fastexp'):
 add(name,'unary','log'if name=='ln'else name)
for name in('pow','atan2','hypot','min','minimum','max','maximum'):add(name,'binary',{'minimum':'min','maximum':'max'}.get(name,name))
for lower,upper in(('pi','PI'),('e','E'),('twopi','TWOPI'),('halfpi','HALFPI'),('degtorad','DEGTORAD'),('radtodeg','RADTODEG'),('ln2','LN2'),('ln10','LN10'),('log2e','LOG2E'),('log10e','LOG10E'),('sqrt2','SQRT2'),('sqrt1_2','SQRT1_2'),('invpi','INVPI'),('phi','PHI')):
 add(lower,'constant',lower);add(upper,'constant',lower)
add('constant','literal','constant')
MODEL_SPECS={2400+i:dict(name=n,kind=k,operation=o)for i,(n,k,o)in enumerate(SPEC)}
MODEL_NAMES={m:s['name']for m,s in MODEL_SPECS.items()};MODELS=frozenset(MODEL_SPECS)
APPROXIMATIONS={'fastsin','fastcos','fasttan','fastexp'}
ABSOLUTE_TOLERANCES={m:(1e-3 if s['operation']in APPROXIMATIONS else 2e-5 if s['operation']=='pow'else 8e-6 if s['operation']=='radtodeg'else 2e-6 if s['kind']=='constant'or(s['kind']=='unary'and s['operation']not in('not','bool','ceil','floor','trunc','fract','sign'))or s['operation']in('hypot','atan2')else 0.)for m,s in MODEL_SPECS.items()}
REFERENCE_POLICIES={m:('signed-fraction-convention'if s['operation']=='fract'else'declared-ideal-approximation-screen'if s['operation']in APPROXIMATIONS else'independent-finite-visual-maths')for m,s in MODEL_SPECS.items()}
PREPARE_ZERO_WARM_BLOCKS=0
WIDE=(-2.,-1.5,-1.,-.75,-.5,-.25,-.125,-0.,0.,.125,.25,.5,.75,1.,1.5,2.)
NONZERO=(-2.,-1.5,-1.,-.75,-.5,-.25,-.125,-.0625,.0625,.125,.25,.5,.75,1.,1.5,2.)
SMALL=(-.5,-.4375,-.375,-.3125,-.25,-.1875,-.125,-0.,0.,.0625,.125,.1875,.25,.3125,.375,.5)
POSITIVE=(.125,.25,.5,.75,1.,1.125,1.25,1.5,1.75,2.,2.5,3.,3.5,4.,4.5,5.)
ABOVE_ONE=(1.,1.0625,1.125,1.1875,1.25,1.375,1.5,1.75,2.,2.25,2.5,3.,3.5,4.,4.5,5.)
EXPONENT=(-2.,-1.5,-1.,-.5,0.,.25,.5,.75,1.,1.25,1.5,1.75,2.,2.25,2.5,3.)
CONSTANTS={'pi':math.pi,'e':math.e,'twopi':2*math.pi,'halfpi':math.pi/2,'degtorad':math.pi/180,'radtodeg':180/math.pi,
           'ln2':math.log(2),'ln10':math.log(10),'log2e':math.log2(math.e),'log10e':math.log10(math.e),'sqrt2':math.sqrt(2),'sqrt1_2':math.sqrt(.5),'invpi':1/math.pi,'phi':(1+math.sqrt(5))/2}
def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
def value(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def spec(model):
 if type(model)is not int or model not in MODELS:raise ValueError('Unknown visual math model')
 return MODEL_SPECS[model]
def planes(model):
 s=spec(model);op=s['operation'];a,b=WIDE,WIDE
 if op=='/':b=NONZERO
 if op in('acos','asin','atanh','tan','fastsin','fastcos','fasttan'):a=SMALL
 if op in('sqrt','log','log2','log10'):a=POSITIVE
 if op=='acosh':a=ABOVE_ONE
 if op=='pow':a,b=POSITIVE,EXPONENT
 if op=='atan2':a,b=NONZERO,NONZERO
 return a,b
def domains(model):return[[min(p),max(p)]for p in planes(model)]
def input_words(frames=256):return case_input_words(2400,frames)
def case_input_words(model,frames=256):
 a,b=planes(model)
 if type(frames)is not int or frames!=256:raise ValueError('Expected256 frames')
 return tuple(word(x)for n in range(256)for x in(a[n//16],b[n%16]))
def operation(model,x,y):
 s=spec(model);op=s['operation']
 if s['kind']=='constant':return CONSTANTS[op]
 if s['kind']=='literal':return 3.5
 if op=='+':return x+y
 if op=='-':return x-y
 if op=='*':return x*y
 if op=='/':return x/y
 if op in('<','<=','>','>=','==','!=','<p','<=p','>p','>=p','==p','!=p'):
  plain=op[:-1]if op.endswith('p')else op
  truth={'<':x<y,'<=':x<=y,'>':x>y,'>=':x>=y,'==':x==y,'!=':x!=y}[plain]
  return(x if truth else 0.)if op.endswith('p')else float(truth)
 if op=='&&':return float(x!=0 and y!=0)
 if op=='||':return float(x!=0 or y!=0)
 if op=='^^':return float((x!=0)!=(y!=0))
 if op=='not':return float(x==0)
 if op=='bool':return float(x!=0)
 if op=='min':return min(x,y)
 if op=='max':return max(x,y)
 if op=='pow':return math.pow(x,y)
 if op=='atan2':return math.atan2(x,y)
 if op=='hypot':return math.hypot(x,y)
 if op=='fract':return x-math.trunc(x)  # explicit signed-fraction convention
 if op=='sign':return x if x==0 else 1. if x>0 else-1.
 if op in APPROXIMATIONS:return getattr(math,dict(fastcos='cos',fastsin='sin',fasttan='tan',fastexp='exp')[op])(x)
 if op in('acos','acosh','asin','asinh','atan','atanh','cos','cosh','sin','sinh','tan','tanh','exp','exp2','log','log2','log10','sqrt','ceil','floor','trunc'):return getattr(math,op)(x)
 raise ValueError('Unknown mathematical operation')
def reference_words(model,inputs):
 spec(model);inputs=tuple(inputs)
 if inputs!=case_input_words(model):raise ValueError('Visual maths vector differs from predeclared finite domain')
 result=[]
 for n in range(256):
  x,y=map(value,inputs[2*n:2*n+2]);result.extend((word(operation(model,x,y)),inputs[2*n+1]))
 return tuple(result)
