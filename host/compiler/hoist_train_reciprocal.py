# SPDX-License-Identifier: MIT
"""Closed RNBO1.4.4 scalar train reciprocal hoist; all other forms reject.

The42-file input includes normal runtime fixes and baseline patch_config.h.
Only the reciprocal location changes. Width endpoint bypasses, Double floor,
phase/pulse state, phasor and clocks keep their original evaluation order.
"""
import hashlib
import json
import re
from bounded_filters import _method

SOURCE='bfc417a0c8df062822bd4e47aa1d307ad5faa4606791545727a31b06681cfbd1'
DESCRIPTION='9290e3fc349df001d703058cac6cf6e9118e3f9c7243525febdda15e98aff1b0'
PATCH='b1ffdf24e21d4d725950100c999a4adfb3bf59d05369c8c7a05e1b65e9f60142'
RUNTIME='fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d'
FILE_MAP='d208f80a6fdfffa17aabd392c443ddd485469ac6e8c6403cdc90c67eb35181b7'
UNGUARDED_SOURCE='8a736c464fd12717b150b25dc554251aae10f6dc9039b8cca79aa8b9012c011e'
OPTIONS={'rnbo_version':'1.4.4','apply_fixes':True,'role':'main','sample_rate':44100,'block_frames':256,
         'audio_inputs':0,'audio_outputs':2,'numerical_profile':'float32-strict','filter_delay_max_ms':None,
         'float32_delay_storage':False,'required_host_services':[],'other_optimizations':[]}
GUARDED_SOURCE='81ad822dcd0278494d3943627fdb254bd6679fd96f83ed5d5878d3a5ad684571'
METHODS={'process': '83af1558bef1e38b7f8282985974155c81a1d49bda85233385db8b740a715f88',
 'prepareToProcess': '5712c65d9ddf62894fabbedb73ef71d7edf01995faad389aa82c62a815f9ecee',
 'phasor_01_perform': '0fc96b6bb86618b28754a4ad98fbbd782c4674748b3047c9af84fc23fa4de9ec',
 'phasor_01_ph_next': 'dca50643f2456c45293aac74b7519ee17d25079b7f164b785b4e1ca41826ffef',
 'phasor_01_ph_dspsetup': 'fd59d2b1f0202f5e5e897802014de05c5a6f69be2db3ea3624b9654a50a5e5ba',
 'phasor_01_ph_reset': '759e7abc2441de462b9207073d420aa912e4f627f0faccb49e8fc40fd9cfb05d',
 'phasor_01_dspsetup': '8012f968acbec9d2a587b88616c9ffecff20b8d88873e9253aa4629d3afe591f',
 'train_tilde_01_perform': '4415e10c1812e3b40787f68aa467602e8c8428ab4b2dee604bf85f686d3acb0f',
 'train_tilde_01_interval_set': 'becf46d48268e27aa42bfcc57d5a0bcb63b0a8e389fa2316cf2b6571329da147',
 'train_tilde_01_width_set': '43c6b94445f671e6ae78ff8568c73cf7ec4f5d1c5ccb212241dd249e13a790a6',
 'train_tilde_01_reset': 'd875f2cd1fa467ca86ceb5b870177b2194660b95ada397ff2244409d92391c95',
 'train_tilde_01_dspsetup': '06d51e8c2c03fb89329f5f6572d356a8cb1d930aec4767be6921169de1ca9907',
 'maximum': '41f4db0a555010bb799eb7d432f1ff022318c7a7d5e3a27e289d4829e129d481',
 'assign_defaults': '7d2361f87f47fa82fc2a82d3c2db5fb27959685020b9c7f877f0148699595ad6',
 'param_02_value_set': '46e085875b461fdee269031a11bed2f4c214484e5ce5a1082d4ade1c641e5b4e',
 'param_03_value_set': '9e57b820e4b8d86d3f179ec5516784dea66689b2a8aecad18aaf4c037de785b0',
 'param_01_value_set': '0c6b5a6f758fddb00f39796465f64815a11f6e748e2f0afe78aa95dd9f52401e'}
CONTRACT="""/* PRIVATE train reciprocal hoist compile contract; no emitted operations. */
#include <float.h>
#include <limits>
#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ > 0)
#error "Train reciprocal hoist requires strict floating-point compilation"
#endif
#if FLT_RADIX != 2 || FLT_MANT_DIG != 24 || FLT_MAX_EXP != 128 || FLT_MIN_EXP != -125 || FLT_EVAL_METHOD != 0
#error "Train reciprocal hoist requires binary32 without extended evaluation"
#endif
#if DBL_MANT_DIG != 53 || DBL_MAX_EXP != 1024 || DBL_MIN_EXP != -1021
#error "Train reciprocal hoist retains IEEE binary64 duration and clock arithmetic"
#endif
static_assert(sizeof(float)==4 && sizeof(RNBO::number)==4 && sizeof(RNBO::Sample)==4 &&
              sizeof(RNBO::SampleValue)==4 && std::numeric_limits<RNBO::number>::is_iec559 &&
              std::numeric_limits<RNBO::number>::digits==24 && std::numeric_limits<RNBO::Sample>::is_iec559 &&
              std::numeric_limits<RNBO::Sample>::digits==24 && std::numeric_limits<RNBO::SampleValue>::is_iec559 &&
              std::numeric_limits<RNBO::SampleValue>::digits==24, "Train reciprocal hoist requires binary32 RNBO samples");
static_assert(sizeof(double)==8 && sizeof(RNBO::MillisecondTime)==8 &&
              std::numeric_limits<double>::is_iec559 && std::numeric_limits<RNBO::MillisecondTime>::is_iec559 &&
              std::numeric_limits<RNBO::MillisecondTime>::digits==53 &&
              std::numeric_limits<RNBO::MillisecondTime>::max_exponent==1024 &&
              std::numeric_limits<RNBO::MillisecondTime>::min_exponent==-1021, "Train reciprocal hoist retains binary64 scheduler time");
"""

def sha(value):return hashlib.sha256(value).hexdigest()
def canonical(value):return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()
def require(ok,message):
    if not ok:raise ValueError('hoist-train-reciprocal: '+message)
def method_sha(masked,name):
    a,b=_method(masked,name)
    return sha(re.sub(r'\s+','',masked[a:b]).encode())

def transform(files,description,options,*,code_mask):
    """Return a new byte map and audit record, without I/O or caller mutation."""
    require(isinstance(files,dict) and all(isinstance(n,str) and isinstance(v,bytes) for n,v in files.items()),'immutable byte source map required')
    require(isinstance(options,dict) and set(options)==set(OPTIONS),'unknown/missing API option')
    for name,expected in OPTIONS.items():
        actual=options[name]
        require(type(actual) is type(expected) and actual==expected,'unsupported '+name)
    source=files.get('rnbo_source.h');stored=files.get('description.json')
    require(isinstance(source,bytes) and sha(source)==SOURCE,'unknown/partial/repeated train source')
    require(isinstance(stored,bytes) and sha(stored)==DESCRIPTION,'unreviewed description')
    try:matches=isinstance(description,dict) and canonical(description)==canonical(json.loads(stored))
    except (ValueError,TypeError,UnicodeError):matches=False
    require(matches,'description object differs')
    require(sha(files.get('source.rnbopat',b''))==PATCH,'authored phase-pulse graph differs')
    inventory={name:sha(data) for name,data in sorted(files.items())}
    runtime={name:value for name,value in inventory.items() if name.startswith('common/')}
    require(len(runtime)==36 and sha(canonical(runtime))==RUNTIME,'runtime/types/normal fixes differ')
    require(len(files)==42 and sha(canonical(inventory))==FILE_MAP,'unknown file/config/source composition')
    text=source.decode();masked=code_mask(text)
    require(isinstance(masked,str) and len(masked)==len(text),'invalid C++ lexical mask')
    require(len(re.findall(r'\btrain_tilde_01_perform\b',masked))==2,'only one scalar caller and definition admitted')
    for name,pin in METHODS.items():require(method_sha(masked,name)==pin,'method/caller/state differs: '+name)
    require(re.search(r'\bDataRefIndex\s+getNumDataRefs\(\)\s+const\s*{\s*return 0;\s*}',masked) is not None,'no external resources admitted')
    require(len(re.findall(r'\bnumber\s+sr\s*;',masked))==1,'SR storage differs')
    require(re.findall(r'(?<![\w])(?:this->)?sr\s*=(?!=)\s*([^;]+);',masked)==['sampleRate','44100'],'SR writes differ')
    require(not re.search(r'&\s*(?:this->)?(?:sr|train_tilde_01_(?:interval|width|phase|value))\b',masked),'private state alias differs')
    a,b=_method(masked,'train_tilde_01_perform');old=text[a:b]
    require(re.search(r'\bnumber\s+interval\s*,\s*number\s+width\s*,\s*number\s+pulsephase\s*,',old) is not None,'scalar control signature differs')
    loop='    for (i = 0; i < 256; i++) {'
    copy='        number __interval = interval;\n'
    clamp='            __interval = this->maximum(__interval, 1.);\n'
    divide='            number pincr = (number)1 / __interval;'
    for token in (loop,copy,clamp,divide):require(old.count(token)==1,'reciprocal loop context differs')
    require(old.count('rnbo_floor(1. + __train_tilde_01_phase - p2)')==1,'original Double floor differs')
    # Preserve the original active-branch predicate, including its complement.
    # This avoids introducing a division into width0/1 bypasses.
    cache=('    number __train_tilde_01_invariant_pincr = 0;\n'
           '    if (!(width <= 0.) && !(width >= 1.)) {\n'
           '        number __interval = interval;\n'
           '        __interval = this->maximum(__interval, 1.);\n'
           '        __train_tilde_01_invariant_pincr = (number)1 / __interval;\n'
           '    }\n\n')
    cached_use='            number pincr = __train_tilde_01_invariant_pincr;'
    new=old.replace(copy,'').replace(clamp,'').replace(divide,cached_use).replace(loop,cache+loop)
    restored=new.replace(cache,'').replace(loop,loop+'\n'+copy).replace('            number p1',clamp+'            number p1').replace(cached_use,divide)
    restored=restored.replace(copy+'\n\n',copy+'\n')
    require(restored==old,'complete method inverse differs')
    changed=text[:a]+new+text[b:]
    require(changed.replace(new,old)==text and sha(changed.encode())==UNGUARDED_SOURCE,'historical source inverse differs')
    anchor='#include RNBO_LIB_INCLUDE(RNBO_AudioSignal.h)\n'
    require(changed.count(anchor)==1,'RNBO include anchor differs')
    guarded=changed.replace(anchor,anchor+CONTRACT)
    require(guarded.replace(CONTRACT,'')==changed and sha(guarded.encode())==GUARDED_SOURCE,'compile assertion/source identity differs')
    result=dict(files);result['rnbo_source.h']=guarded.encode()
    return result,{'name':'rnbo-1.4.4-hoist-train-reciprocal-v1','file':'rnbo_source.h','input_sha256':SOURCE,
        'prepared_sha256':GUARDED_SOURCE,'assertion_removed_source_sha256':UNGUARDED_SOURCE,
        'inline_contract_sha256':sha(CONTRACT.encode()),'whole_input_map_sha256':FILE_MAP,'input_file_count':42,
        'description_file_sha256':DESCRIPTION,'authored_patch_sha256':PATCH,'runtime_tree_sha256':RUNTIME,
        'method_pins':dict(METHODS),'source_inverse_byte_identity':True,'assertion_removal_byte_identity':True,
        'active_width_reciprocal_once_per_vector':True,'width_endpoints_remain_division_free':True,
        'original_double_floor_state_and_clocks_unchanged':True,'options':json.loads(canonical(options)),
        'ownership':'Exclusive opaque callbacks; no private state aliases, concurrent callbacks/prepare or external resource replacement',
        'rounding_assumption':'Runtime nearest/even; compile assertions do not establish runtime mode',
        'floating_environment_equivalence_claimed':False,'nan_payload_equivalence_claimed':False,
        'retained_limitations':['Inherited maximum-period/near-full-width warm-start full-window duty failure remains unchanged; stationary suffix proof is separate','No signal controls, pulsephase/reset/sync/transport modes or generic train/phasor family qualification'],
        'production_available':True,'hardware_executed':False}
