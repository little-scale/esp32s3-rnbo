# SPDX-License-Identifier: MIT
"""Complete per-instance stable-onepole envelope for freshly regenerated graphs.

The issuer owns provenance. This scanner is deliberately not arbitrary-C++
alias analysis, graph-wide input-domain proof or full-family qualification.
"""
from collections import Counter
import hashlib,json,math,re,struct
from prepare import cpp_code_mask
from stable_onepole import CONTRACT, HELPER_SHA256, RUNTIME
from regenerated_export import RegeneratedGraph

sha=lambda b:hashlib.sha256(b).hexdigest()
def canonical(v):return(json.dumps(v,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()
def require(ok,message):
 if not ok:raise ValueError(message)
NUM=r'-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?'


MAX_SOURCE_BYTES = 8*1024*1024
MAX_METHOD_DEPTH = 128

def _balanced(mask, opening, left, right):
 require(opening < len(mask) and mask[opening]==left,'missing method delimiter')
 depth=1;cursor=opening+1
 while cursor<len(mask) and depth:
  if mask[cursor]==left:depth+=1
  elif mask[cursor]==right:depth-=1
  require(depth<=MAX_METHOD_DEPTH,'method nesting is not admitted')
  cursor+=1
 require(depth==0,'unterminated method')
 return cursor

def method(source,name,*,mask=None,index=None):
 if mask is None:mask=cpp_code_mask(source)
 matches=index.get(name,[]) if index is not None else list(re.finditer(r'\bvoid\s+'+re.escape(name)+r'\s*\(',mask))
 require(len(matches)==1,'missing/ambiguous method '+name);m=matches[0]
 opening=mask.index('(',m.start());cursor=_balanced(mask,opening,'(',')')
 while cursor<len(mask) and mask[cursor].isspace():cursor+=1
 require(cursor<len(mask) and mask[cursor]=='{','unknown method declaration '+name)
 end=_balanced(mask,cursor,'{','}')
 return m.start(),end,source[m.start():end]


def norm(text,prefix):
 masked=cpp_code_mask(text)
 masked=re.sub(r'\bRNBO_RESTRICT\b','',masked)
 def renamed(match):
  token=match[0]
  if token.startswith('__'+prefix+'_'):return '__P'+token[len(prefix)+2:]
  if token.startswith(prefix+'_'):return 'P'+token[len(prefix):]
  return token
 masked=re.sub(r'\b[A-Za-z_][A-Za-z0-9_]*\b',renamed,masked)
 return re.sub(r'\s+','',masked)



def kernel(source,prefix,*,mask=None,index=None):
 start,end,text=method(source,prefix+'_perform',mask=mask,index=index);n=norm(text,prefix)
 require(n.startswith('voidP_perform(constSample*x,'),'scalar/unknown data mode')
 details={'restrict_tokens_in_original':text.count('RNBO_RESTRICT')}
 if 'RNBO_UNUSED(freqInHz);'in n:
  mode='fixed';m=re.search(r'if\(__P_freq!=('+NUM+r')\|\|\(bool\)\(__P_needsUpdate\)\)',n);require(m is not None,'fixed condition differs');literal=m[1]
  require('__P_freq='+literal+';'in n,'fixed cache assignment differs')
  value=float(literal);require(math.isfinite(value),'nonfinite fixed literal')
  try:wire=struct.unpack('<f',struct.pack('<f',value))[0]
  except OverflowError:raise ValueError('fixed literal not finite Float32')
  require(math.isfinite(wire),'fixed literal not finite Float32')
  c=re.search(r'__P_a0=1-rnbo_exp\((\(number\))?('+NUM+r')/44100\);',n);require(c is not None,'fixed coefficient expression differs')
  numerator=float(c[2]);require(numerator==-float('6.283185307179586')*value,'fixed folded coefficient/frequency relationship differs')
  require(bool(c[1])==(numerator>=0),'unexpected fixed constant cast form')
  n=n[:c.start()]+'__P_a0=GEN_COEFFICIENT;'+n[c.end():]
  n=n.replace('__P_freq!='+literal,'__P_freq!=FIXED_LITERAL').replace('__P_freq='+literal+';','__P_freq=FIXED_LITERAL;')
  details.update(literal=literal,wire_float32=wire,constant_cast=bool(c[1]),fixed_cache_predicate_repeats=(wire!=value))
 elif n.startswith('voidP_perform(constSample*x,numberfreqInHz,'):
  mode='scalar'
 elif n.startswith('voidP_perform(constSample*x,constSample*freqInHz,'):
  mode='signal'
 else:raise ValueError('unknown frequency signature')
 return mode,sha(n.encode()),details,(start,end,text)


# Reviewed RNBO1.4.4 complete templates; no generated bodies are vendored.
MODELS = {'fixed': {'dspsetup': 'bbb173080c5e1a95eb15ad065d587e95ba2da41cf3ee3071483d4d8dd1dd8fca', 'identifier_counts': {'P_a0': 5, 'P_b1': 5, 'P_dspsetup': 2, 'P_freq': 4, 'P_freqInHz': 3, 'P_lastY': 5, 'P_needsUpdate': 5, 'P_perform': 2, 'P_reset': 2, 'P_setupDone': 4, 'P_x': 2, '__P_a0': 9, '__P_b1': 4, '__P_freq': 4, '__P_lastY': 5, '__P_needsUpdate': 4}, 'perform': '3e3332a3a8d9c3dd5cd8e76f7e3b448145db4c346d1da720506706213e3d8bd0', 'reset': '9cefef9dcbe72454ede2e7e6cb6b60646401ef658ddd1183719257c9aa91ee94'}, 'scalar': {'dspsetup': 'bbb173080c5e1a95eb15ad065d587e95ba2da41cf3ee3071483d4d8dd1dd8fca', 'identifier_counts': {'P_a0': 5, 'P_b1': 5, 'P_dspsetup': 2, 'P_freq': 4, 'P_freqInHz': 4, 'P_freqInHz_set': 2, 'P_lastY': 5, 'P_needsUpdate': 5, 'P_perform': 2, 'P_reset': 2, 'P_setupDone': 4, 'P_x': 2, '__P_a0': 9, '__P_b1': 4, '__P_freq': 4, '__P_lastY': 5, '__P_needsUpdate': 4}, 'perform': '11be40ee3e690087d17edaa9f008a8f8d251e020c4e5bc30ea68142e3eebb357', 'reset': '9cefef9dcbe72454ede2e7e6cb6b60646401ef658ddd1183719257c9aa91ee94'}, 'signal': {'dspsetup': 'bbb173080c5e1a95eb15ad065d587e95ba2da41cf3ee3071483d4d8dd1dd8fca', 'identifier_counts': {'P_a0': 5, 'P_b1': 5, 'P_dspsetup': 2, 'P_freq': 4, 'P_freqInHz': 2, 'P_lastY': 5, 'P_needsUpdate': 5, 'P_perform': 2, 'P_reset': 2, 'P_setupDone': 4, 'P_x': 2, '__P_a0': 9, '__P_b1': 4, '__P_freq': 4, '__P_lastY': 5, '__P_needsUpdate': 4}, 'perform': 'fd2d8d4a3ba8be90eb52d47fb5b5f2516e2feb122b13a4206be75987f08b6a30', 'reset': '9cefef9dcbe72454ede2e7e6cb6b60646401ef658ddd1183719257c9aa91ee94'}}


def scan(source):
 """Inspect complete per-instance forms; freshness/ownership are separate gates."""
 return _scan(source, cpp_code_mask)

def _scan(source, code_mask):
 require(type(source) is bytes and 0 < len(source) <= MAX_SOURCE_BYTES, 'bounded immutable source bytes required')
 text=source.decode();mask=code_mask(text)
 require(type(mask) is str and len(mask)==len(text), 'invalid C++ lexical mask')
 require('onepole_lin_tilde_'not in mask,'linear coefficient family requires its own admission')
 index={}
 for definition in re.finditer(r'\bvoid\s+(process|assign_defaults|onepole_tilde_[0-9]+_[A-Za-z0-9_]+)\s*\(',mask):
  index.setdefault(definition[1],[]).append(definition)
 prefixes=[name[:-8] for name in index if name.endswith('_perform') and name.startswith('onepole_tilde_')]
 require(prefixes and len(prefixes)<=2048,'no bounded unique Hz perform instances')
 process_start,process_end,_=method(text,'process',mask=mask,index=index)
 defaults_start,defaults_end,_=method(text,'assign_defaults',mask=mask,index=index)
 defaults=Counter(re.findall(r'\b(onepole_tilde_[0-9]+)_(x|freq|needsUpdate|lastY|a0|b1|setupDone)\s*=\s*(0|false)\s*;',mask[defaults_start:defaults_end]))
 identifiers={}
 for occurrence in re.finditer(r'\b((?:__)?(onepole_tilde_[0-9]+)_[A-Za-z0-9_]+)\b',mask):
  identifiers.setdefault(occurrence[2],Counter())[occurrence[1].replace(occurrence[2],'P')]+=1
 declarations={}
 for declaration in re.finditer(r'(?m)^[ \t]*(number|bool) (onepole_tilde_[0-9]+)_([A-Za-z0-9_]+);',mask):
  declarations.setdefault(declaration[2],Counter())[(declaration[3],declaration[1])]+=1
 setter_calls=Counter(re.findall(r'this\s*->\s*(onepole_tilde_[0-9]+)_freqInHz_set\s*\(',mask))
 render_calls={}
 for call in re.finditer(r'this\s*->\s*(onepole_tilde_[0-9]+)_perform\s*\(([^;]+)\);',mask):
  render_calls.setdefault(call[1],[]).append(call)
 result=[]
 for prefix in prefixes:
  mode,fingerprint,details,span=kernel(text,prefix,mask=mask,index=index);require(fingerprint==MODELS[mode]['perform'],'whole perform template differs')
  require(sha(norm(method(text,prefix+'_reset',mask=mask,index=index)[2],prefix).encode())==MODELS[mode]['reset'],'reset differs')
  require(sha(norm(method(text,prefix+'_dspsetup',mask=mask,index=index)[2],prefix).encode())==MODELS[mode]['dspsetup'],'dspsetup differs')
  for field in ('x','freqInHz','freq','lastY','a0','b1'):
   require(declarations.get(prefix,{}).get((field,'number'),0)==1,'ordinary number state declaration differs')
  for field in ('needsUpdate','setupDone'):
   require(declarations.get(prefix,{}).get((field,'bool'),0)==1,'ordinary boolean state declaration differs')
  for field,value in [('x','0'),('freq','0'),('needsUpdate','false'),('lastY','0'),('a0','0'),('b1','0'),('setupDone','false')]:
   require(defaults.get((prefix,field,value),0)==1,'initial/default state differs')
  counts=identifiers.get(prefix,Counter());expected=dict(MODELS[mode]['identifier_counts'])
  if mode=='scalar':
   setter=method(text,prefix+'_freqInHz_set',mask=mask,index=index)[2]
   require(norm(setter,prefix)=='voidP_freqInHz_set(numberv){this->P_freqInHz=v;}','setter has side effects')
   setter_count=counts.get('P_freqInHz_set',0);require(setter_count>=2,'setter route absent')
   require(setter_calls.get(prefix,0)==setter_count-1,'setter alias/noncall use')
   expected['P_freqInHz_set']=setter_count
  require(dict(counts)==expected,'extra/missing state, method, alias or external reference')
  require(not any(key in counts for key in ('P_correction','__P_correction')),'correction name collision')
  # All admitted render calls use ordinary known 256-frame planes; no opaque
  # pointer expression or address of a private scalar state word is admitted.
  calls=render_calls.get(prefix,[]);require(len(calls)==1,'render call count differs');call=calls[0]
  require(process_start<call.start()<process_end,'render call outside process')
  args=[re.sub(r'\s+','',arg)for arg in call[2].split(',')];require(len(args)==4 and args[3]=='256','render call shape/size differs')
  ptr=r'(?:in[0-9]+|out[0-9]+|this->signals\[[0-9]+\]|this->zeroBuffer|this->dummyBuffer)'
  require(re.fullmatch(ptr,args[0])and re.fullmatch(ptr,args[2]),'unreviewed data/output pointer expression')
  require(args[0]!=args[2]and(mode!='signal'or args[1]!=args[2]),'writable plane alias needs separate proof')
  if mode=='signal':require(re.fullmatch(ptr,args[1]),'unreviewed frequency pointer')
  else:require(args[1]=='this->'+prefix+'_freqInHz','scalar frequency source differs')
  result.append({'prefix':prefix,'mode':mode,'perform_span':[span[0],span[1]],'perform_sha256_normalised':fingerprint,'details':details,'call_args':args,'read_only_data_frequency_alias':mode=='signal'and args[0]==args[1],'family_identifiers':dict(counts),'state_b1_code_uses':counts['P_b1']+counts['__P_b1']})
 return result


OPTIONS = {'rnbo_version':'1.4.4','apply_fixes':True,'sample_rate':44100,'block_frames':256,
 'audio_outputs':2,'numerical_profile':'float32-strict','filter_delay_max_ms':None,
 'float32_delay_storage':False,'required_host_services':[],'other_optimizations':[]}

def transform(files, description, options, *, code_mask, helper, regenerated):
 """Pure source transform; only process-issued whole-map regeneration is authority."""
 require(type(options) is dict and set(options)==set(OPTIONS)|{'role','audio_inputs'}, 'unknown/missing option')
 for key, expected in OPTIONS.items():
  require(type(options[key]) is type(expected) and options[key]==expected, 'unsupported '+key)
 require(type(options['role']) is str and options['role'] in ('main','fx'), 'unknown role')
 require(type(options['audio_inputs']) is int and options['audio_inputs']==(0 if options['role']=='main' else 2), 'role/input topology differs')
 require(type(regenerated) is RegeneratedGraph, 'process-issued regeneration required')
 require(type(files) is dict and all(type(k) is str and type(v) is bytes for k,v in files.items()),'immutable map required')
 require(type(helper) is bytes and sha(helper)==HELPER_SHA256,'unknown helper')
 require(len(files)==42,'unknown/repeated file set')
 runtime={n:sha(data)for n,data in sorted(files.items())if n.startswith('common/')};require(len(runtime)==36 and sha(canonical(runtime))==RUNTIME,'unknown runtime')
 require(regenerated.matches(files, options['role'], class_name='rnbos3patch'), 'whole normal map does not match fresh regeneration')
 require('description.json' in files and type(description) is dict, 'missing description')
 try: same=canonical(description)==canonical(json.loads(files['description.json']))
 except (TypeError,ValueError,UnicodeError): same=False
 require(same,'description object differs')
 source=files['rnbo_source.h'];text=source.decode();instances=_scan(source,code_mask)
 record=regenerated.record
 require(type(record) is dict and type(record.get('inspection')) is dict, 'missing graph inspection')
 objects=record['inspection'].get('objects')
 require(type(objects) is list and all(type(o) is dict for o in objects), 'missing inspected objects')
 expected=sum(o.get('surface')=='onepole~' for o in objects)
 require(len(instances)==expected and expected>0, 'unrecognised/missing/generated onepole instance')
 # Journal disjoint snippets, not a full source copy for every instance.
 # Perform bodies are small and nonoverlapping. Remaining renames are the
 # declaration/default/reset words outside those bodies, selected from code.
 mask=code_mask(text);word_spans={}
 for match in re.finditer(r'\b((?:__)?(onepole_tilde_[0-9]+)_b1)\b',mask):
  word_spans.setdefault(match[2],[]).append(match)
 edits=[]
 for instance in instances:
  prefix=instance['prefix'];start,end=instance['perform_span'];old_method=text[start:end]
  spans=word_spans.get(prefix,[]);require(len(spans)==9,'word use mismatch')
  changed_method=old_method
  inside=[m for m in spans if start<=m.start()<end]
  require(len(inside)==6,'perform/state reference ownership differs')
  for m in reversed(inside):
   a,b=m.start()-start,m.end()-start
   changed_method=changed_method[:a]+m[0].replace('_b1','_correction')+changed_method[b:]
  local='__'+prefix
  old=f'            {local}_correction = 1 - {local}_a0;\n'
  require(changed_method.count(old)==1,'complement differs');changed_method=changed_method.replace(old,'')
  expression=re.compile(r'            '+local+r'_a0 = 1 - rnbo_exp\([^\n]+\);\n            '+local+r'_a0 = \([^\n]+\);')
  found=list(expression.finditer(changed_method));require(len(found)==1,'coefficient pair differs')
  m=found[0];changed_method=changed_method[:m.start()]+f'            {local}_a0 = ::rnbo_s3_onepole::coefficient({local}_freq);'+changed_method[m.end():]
  old=f'        {local}_lastY = {local}_a0 * x[(Index)i] + {local}_correction * {local}_lastY;'
  new=f'        ::rnbo_s3_onepole::step(x[(Index)i], {local}_a0, {local}_lastY, {local}_correction);'
  require(changed_method.count(old)==1,'recurrence differs');changed_method=changed_method.replace(old,new)
  edits.append((start,end,old_method,changed_method))
  for m in spans:
   if not start<=m.start()<end:
    edits.append((m.start(),m.end(),m[0],m[0].replace('_b1','_correction')))
 edits.sort();parts=[];journal=[];cursor=0;output_position=0
 for start,end,old,new in edits:
  require(cursor<=start<=end and text[start:end]==old,'overlapping/stale source edit')
  unchanged=text[cursor:start];parts.extend((unchanged,new));output_position+=len(unchanged)
  journal.append((output_position,old,new));output_position+=len(new);cursor=end
 parts.append(text[cursor:]);changed=''.join(parts)
 inverse=[];cursor=0
 for at,old,new in journal:
  require(changed[at:at+len(new)]==new,'inverse snippet differs')
  inverse.extend((changed[cursor:at],old));cursor=at+len(new)
 inverse.append(changed[cursor:]);require(''.join(inverse)==text,'complete source inverse differs')
 anchor='#include RNBO_LIB_INCLUDE(RNBO_AudioSignal.h)\n';require(changed.count(anchor)==1,'include context differs')
 output=dict(files);output['rnbo_source.h']=changed.replace(anchor,anchor+CONTRACT).encode();output['onepole_stable.h']=helper
 return output,{'name':'rnbo-1.4.4-stable-onepole-graphs-v1','file':'rnbo_source.h','context':'regenerated-per-instance-envelope',
  'instances':instances,'instance_count':len(instances),'source_inverse_byte_identity':True,
  'input_sha256':sha(source),'prepared_sha256':sha(output['rnbo_source.h']),
  'assertion_removed_source_sha256':sha(changed.encode()),'inline_contract_sha256':sha(CONTRACT.encode()),
  'helper_sha256':HELPER_SHA256,'runtime_tree_sha256':RUNTIME,'input_files':42,'output_files':43,
  'regenerated':json.loads(canonical(record)),'options':json.loads(canonical(options)),
  'experimental':True,'correctness_profile':'stable-onepole-v1','baseline_bit_identity_claimed':False,
  'added_state_members':0,'coefficient_scale_bits':'b9156592','target_cpu_gain_claimed':False,
  'finite_output_proof_scope':'finite binary32 data/frequency and finite owned state; nearest-even, no contraction, gradual underflow, nontrapping execution',
  'ownership':'exclusive opaque ABI callbacks; independent state and writable planes; no direct C++ state mutation or state restoration',
  'floating_environment_equivalence_claimed':False,'nan_payload_equivalence_claimed':False,
  'fixed_fractional_cache_predicates_preserved':True,
  'double_free_all_DSP_claimed':False,'scheduler_time_unchanged':'binary64; no clock edits'}
