# SPDX-License-Identifier: MIT
"""Closed scalar-duration hoist for one reviewed strict RNBO1.4.4 graph.

This is not a general loop-invariance pass. Input is the exact42-file map after
normal runtime corrections, the40ms cap and baseline patch_config creation.
Only original declaration/Double conversion/Float32 clamp statements move.
"""
import hashlib
import json
import re
from bounded_filters import _method

SOURCE='a9ee89d6ab5b80fc7ccee0e20953640fa1347eaa9d3e42d2ac08e55163d57076'
DESCRIPTION='dcbba4108dc65eb2a3c9714826bce54c74f8014ba4df8e9c2a5fad5a2b7e9b21'
PATCH='630eacd5fe1c3dad5f5a5174da495e6ff097a8d695d21b62a759bd8904fb2359'
RUNTIME='fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d'
FILE_MAP='028365ff4bfc4431b073266c57bb6dd0495878161ded4cf1b2e7c215fd8b506e'
# Exact same41 DSP/runtime/config/graph files; the GenExpr-aware importer
# changes only generator.json's patcher_adapter_sha256. Retain both whole maps.
GENEXPR_FILE_MAP='0d609c0e56baa144774f3a220b6b2e78d70d13692d792ffbae47f066c2d23525'
# Reviewed integer-number UI importer epoch; only generator.json changed.
INTEGER_UI_FILE_MAP='f01edb8a61a955ce5a362f2c57f4ae14181c2d4ce73e29a9d1bd8fea059f9602'
UNGUARDED_SOURCE='ec1a5dc1f86af83a0152e682c85d141c40b9ce54afdaf80be813dd57c06c5ffc'
GUARDED_SOURCE='113571f43d1f92ee4890b0e5977c4464202090ec669d775618dfd242ca64be58'
OPTIONS={'rnbo_version':'1.4.4','apply_fixes':True,'role':'main','sample_rate':44100,'block_frames':256,
         'audio_inputs':0,'audio_outputs':2,'numerical_profile':'float32-strict','filter_delay_max_ms':40,
         'float32_delay_storage':False,'required_host_services':[],'other_optimizations':[]}
METHODS={'comb_tilde_01_perform': 'bcb1900009f87346372d4012353ef4c575b57d059c875397ff67107adfc51864', 'allpass_tilde_01_perform': '5103eeb1fd09044d9d641313398b29f168934c1d18df577fa50544e04437e5e3', 'mstosamps': 'c7c745c855cc7034e43152c8012dec296efbf15f1abf4a5983f3553a02bb7cc5', 'prepareToProcess': 'de9e103d4e463f152315df38605071651f8ffc2ad393408c51d561942b215f23', 'process': 'ba933ae632aefd253fa4593f30cc6dcb659c0384689e206702918d29dfea32cc', 'param_02_value_set': '743059d5042375f3509030a48bf47574f686beadb56e457330eb29808617c966', 'comb_tilde_01_delayTime_set': '6e32273054bb449cffbb28566fac19fcaa652e68addce3efb22ad440f49640df', 'allpass_tilde_01_delayTime_set': '7e62fe5be4e09828ccb6704cf8d505e3ed9df04592e15bc58bd6dbf7c30982e9'}
RINGS={'comb_tilde_01_feedForward': {'read': '7e5e18e896cfc3faced3ec20e9a5152d1a9a040c410f86f4f6ef69ba0038b74a', 'write': '682aca85c3a8790639459017021a10587967214603baec9dc8f5bf099cf36cc9', 'step': 'e48a62ffce2f1cb56b17d25ed37b1078bae1f2bd09cc3b792008ac88b122b6a0'}, 'comb_tilde_01_feedBack': {'read': '838c35859078107ffdf42732ac3ac5f066de1d8c20b4f781db217a5250f2c1eb', 'write': '30752f4e8f6f2c91687498fe6c679ca6b0f335f222a8a44cd640f37a57ec05c6', 'step': '85a1da361922c382408beb0f764af48a8196c170cad11f32b83721b800802235'}, 'allpass_tilde_01_feedForward': {'read': '63d1903b67c4511912bdfc2210556d1bf7688feef08d57987d446aaafba43570', 'write': '120524b98130af2d1d5862687b95f7a2a35a26ca262e915dca1d9b12fcbdf5f4', 'step': '738757467df1f0c11598afd057eac1ccb2f54368853db3167ab735d133157d62'}, 'allpass_tilde_01_feedBack': {'read': '49a602519d710bb5c06073f41f7917fbf6f3e18c4e501a71268a91b163725516', 'write': '9a6bab0a6c1ca8d769bfb07f192abb744899ec3d0c24a7aff0c5b282762ac62a', 'step': 'eee8cb63f441579c0e24636a2c586650e66e82cb1a5fe8fd8cfd12961ab50055'}}
CONTRACT='/* PRIVATE scalar duration hoist compile contract; no emitted operations. */\n#include <float.h>\n#include <limits>\n#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ > 0)\n#error "Scalar duration hoist requires strict floating-point compilation"\n#endif\n#if FLT_RADIX != 2 || FLT_MANT_DIG != 24 || FLT_MAX_EXP != 128 || FLT_MIN_EXP != -125 || FLT_EVAL_METHOD != 0\n#error "Scalar duration hoist requires binary32 without extended evaluation"\n#endif\n#if DBL_MANT_DIG != 53 || DBL_MAX_EXP != 1024 || DBL_MIN_EXP != -1021\n#error "Scalar duration hoist retains IEEE binary64 duration and clock arithmetic"\n#endif\nstatic_assert(sizeof(float)==4 && sizeof(RNBO::number)==4 && sizeof(RNBO::Sample)==4 &&\n              sizeof(RNBO::SampleValue)==4 && std::numeric_limits<RNBO::number>::is_iec559 &&\n              std::numeric_limits<RNBO::number>::digits==24 && std::numeric_limits<RNBO::Sample>::is_iec559 &&\n              std::numeric_limits<RNBO::Sample>::digits==24 && std::numeric_limits<RNBO::SampleValue>::is_iec559 &&\n              std::numeric_limits<RNBO::SampleValue>::digits==24, "Scalar duration hoist requires binary32 RNBO samples");\nstatic_assert(sizeof(double)==8 && sizeof(RNBO::MillisecondTime)==8 &&\n              std::numeric_limits<double>::is_iec559 && std::numeric_limits<RNBO::MillisecondTime>::is_iec559 &&\n              std::numeric_limits<RNBO::MillisecondTime>::digits==53 &&\n              std::numeric_limits<RNBO::MillisecondTime>::max_exponent==1024 &&\n              std::numeric_limits<RNBO::MillisecondTime>::min_exponent==-1021, "Scalar duration hoist retains binary64 scheduler time");\n'

def sha(value):return hashlib.sha256(value).hexdigest()
def canonical(value):return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()
def require(ok,message):
    if not ok:raise ValueError('hoist-filter-durations: '+message)
def method_sha(masked,name):
    a,b=_method(masked,name)
    return sha(re.sub(r'\s+','',masked[a:b]).encode())

def transform(files,description,options,*,code_mask):
    """Return a new byte map and audit record without I/O or caller mutation."""
    require(isinstance(files,dict) and all(isinstance(n,str) and isinstance(v,bytes) for n,v in files.items()),'immutable byte source map required')
    require(isinstance(options,dict) and set(options)==set(OPTIONS),'unknown/missing API option')
    for name,expected in OPTIONS.items():
        actual=options[name]
        if name=='filter_delay_max_ms':require(type(actual) in (int,float) and actual==40,'cap40 required')
        else:require(type(actual) is type(expected) and actual==expected,'unsupported '+name)
    source=files.get('rnbo_source.h');stored=files.get('description.json')
    require(isinstance(source,bytes) and sha(source)==SOURCE,'unknown/partial/repeated scalar source')
    require(isinstance(stored,bytes) and sha(stored)==DESCRIPTION,'unreviewed description')
    try:matches=isinstance(description,dict) and canonical(description)==canonical(json.loads(stored))
    except (ValueError,TypeError,UnicodeError):matches=False
    require(matches,'description object differs')
    require(sha(files.get('source.rnbopat',b''))==PATCH,'authored scalar graph differs')
    inventory={name:sha(data) for name,data in sorted(files.items())}
    runtime={name:value for name,value in inventory.items() if name.startswith('common/')}
    require(len(runtime)==36 and sha(canonical(runtime))==RUNTIME,'runtime/types/normal fixes differ')
    input_map=sha(canonical(inventory))
    require(len(files)==42 and input_map in (FILE_MAP,GENEXPR_FILE_MAP,INTEGER_UI_FILE_MAP),'unknown file/config/source composition')
    text=source.decode();masked=code_mask(text)
    require(isinstance(masked,str) and len(masked)==len(text),'invalid C++ lexical mask')
    require(re.findall(r'\bvoid\s+((?:comb|allpass)_tilde_\d+_perform)\s*\(',masked)==['comb_tilde_01_perform','allpass_tilde_01_perform'],'filter context differs')
    for name,pin in METHODS.items():require(method_sha(masked,name)==pin,'method/caller differs: '+name)
    require(len(re.findall(r'\bnumber\s+sr\s*;',masked))==1,'SR storage differs')
    writes=re.findall(r'(?<![\w])(?:this->)?sr\s*=(?!=)\s*([^;]+);',masked)
    require(writes==['sampleRate','44100'],'SR writes differ')
    require(not re.search(r'&\s*(?:this->)?sr\b|\bsr\s*(?:\+=|-=|\+\+|--)',masked),'SR alias/mutation')
    compact=re.sub(r'\s+','',masked)
    for prefix,helpers in RINGS.items():
        require(len(re.findall(r'this->'+prefix+r'_bufferobj=initDataRef\(this->'+prefix+r'_bufferobj,this->dataRefStrings->name\d+,true,this->dataRefStrings->file\d+,this->dataRefStrings->tag\d+\);',compact))==1,'internal DataRef ownership differs')
        require(compact.count('newFloat64Buffer(this->'+prefix+'_bufferobj)')==1 and compact.count('Float64BufferRef'+prefix+'_buffer;')==1,'Float64 view/constructor differs')
        for suffix,pin in helpers.items():require(method_sha(masked,prefix+'_'+suffix)==pin,'ring read/write/step differs')
    loop='    for (i = 0; i < 256; i++) {';edits=[];moved=[]
    for kind in ('comb','allpass'):
        name=kind+'_tilde_01_perform';a,b=_method(masked,name);body=text[a:b]
        require(body.count(loop)==1,'fixed256 loop differs')
        require(re.search(r'\bnumber\s+delayTime\s*,',body[:body.index('{')]) is not None,'duration must be copied scalar number')
        pattern=(r'        number __delayTime = delayTime;\n        __delayTime = this->mstosamps\([^\n]+\);\n        __delayTime = [^\n]+;\n' if kind=='comb' else
                 r'        auto delayTimeinSamps = this->mstosamps\([^\n]+\);\n        delayTimeinSamps = [^\n]+;\n')
        matches=list(re.finditer(pattern,body));require(len(matches)==1,'duration declaration/conversion/clamp differs')
        match=matches[0];snippet=match[0]
        require(match.start()>body.index(loop) and len(re.findall(r'\bmstosamps\s*\(',body))==1,'expected one in-loop conversion')
        changed=body[:match.start()]+body[match.end():];changed=changed.replace(loop,snippet+'\n'+loop,1)
        restored=changed.replace(snippet+'\n'+loop,loop,1)
        restored=restored[:match.start()]+snippet+restored[match.start():]
        require(restored==body,'full method inverse differs')
        edits.append((a,b,changed));moved.append({'method':name,'statement_count':3 if kind=='comb' else 2,'moved_statement_bytes_sha256':sha(snippet.encode()),'original_line':text[:a+match.start()].count('\n')+1})
    changed=text
    for a,b,value in sorted(edits,reverse=True):changed=changed[:a]+value+changed[b:]
    require(sha(changed.encode())==UNGUARDED_SOURCE,'verbatim historical hoist differs')
    anchor='#include RNBO_LIB_INCLUDE(RNBO_AudioSignal.h)\n'
    require(changed.count(anchor)==1,'RNBO include anchor differs')
    guarded=changed.replace(anchor,anchor+CONTRACT)
    require(guarded.replace(CONTRACT,'')==changed and sha(guarded.encode())==GUARDED_SOURCE,'reviewed compile contract/source differs')
    result=dict(files);result['rnbo_source.h']=guarded.encode()
    return result,{'name':'rnbo-1.4.4-hoist-filter-durations-v1','file':'rnbo_source.h','input_sha256':SOURCE,
        'prepared_sha256':GUARDED_SOURCE,'assertion_removed_source_sha256':UNGUARDED_SOURCE,
        'inline_contract_sha256':sha(CONTRACT.encode()),'whole_input_map_sha256':input_map,'input_file_count':42,
        'description_file_sha256':DESCRIPTION,'authored_patch_sha256':PATCH,'runtime_tree_sha256':RUNTIME,
        'method_pins':dict(METHODS),'ring_helper_pins':{k:dict(v) for k,v in RINGS.items()},'moved_statements':moved,
        'source_inverse_byte_identity':True,'assertion_removal_byte_identity':True,'scalar_conversions_hoisted':2,
        'double_expression_and_float32_return_unchanged':True,'state_dependent_ring_clamps_stay_per_sample':True,
        'shared_scheduler_mstosamps_unchanged':True,'options':json.loads(canonical(options)),
        'ownership':'Exclusive opaque callbacks; private internally owned Float64 rings/SR; caller audio planes do not alias private state; no external resource replacement or concurrent prepare',
        'rounding_assumption':'Runtime nearest/even; compile assertions do not establish current runtime mode',
        'floating_environment_equivalence_claimed':False,'nan_payload_equivalence_claimed':False,
        'production_available':True,'hardware_executed':False}
