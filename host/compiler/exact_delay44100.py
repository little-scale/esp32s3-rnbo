# SPDX-License-Identifier: MIT
"""Closed pure-map admission for optional exact44100 audio conversion.

Input is the exact42-file post-normal-fix/post40ms-cap prepared source map,
excluding manifest/provenance. Algorithm/helper bytes are the target-tested
private variant; this adapter retains its inline compile-time assertions.
"""
import hashlib
import json
import re

from bounded_filters import _method

SOURCE='42db7756994ae167bfb58046af0ab559bab7d2beba7d8664dad460607255f138'
DESCRIPTION='9f6f5064cea14ce6c1498e3931320902dea441988836d080c20b1665c6359dd8'
RUNTIME='fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d'
FILE_MAP='dcf861aacea4efaa85afaa7f1d08a3c4651285558b407d3dcaa595c6ea715782'
# Exact same41 DSP/runtime/config/graph files; the GenExpr-aware importer
# changes only generator.json's patcher_adapter_sha256. Retain both whole maps.
GENEXPR_FILE_MAP='66a03d749fcaf43af015a6a249bd915439389bdfd2906ea29fc8312fbf55fed3'
# Reviewed integer-number UI importer epoch; only generator.json changed.
INTEGER_UI_FILE_MAP='090cabac7d806afb539310eb0101f0b7ee0ad8dcdffb48ba991072cae35ad0d8'
HELPER='6ec20697aad74e12995a5442c2ed2eae6f40cc3bee48f2349faa513af4df379c'
TESTED_SOURCE='86a26d933103a18a22edcbe6a6df6e48f7f21f13a330116eed5f9ae55e10bb4b'
GUARDED_SOURCE='2bbbf9c375be9745388090f65237020d095dc9b83f8ae3c6534f05aec4ad99cd'
HELPER_NAME='private_exact_delay44100.h'
OPTIONS={'rnbo_version':'1.4.4','apply_fixes':True,'role':'main','sample_rate':44100,'block_frames':256,
    'audio_inputs':0,'audio_outputs':2,'numerical_profile':'float32-strict','filter_delay_max_ms':40,
    'float32_delay_storage':False,'required_host_services':[],'other_optimizations':[]}
METHODS={
    'comb_tilde_01_perform':'6e32dbc10112f7bd4070c5420a1b8cdd3911dac49b86729ec287577c9d161d06',
    'allpass_tilde_01_perform':'c73f1aff0287f8e6b1fa715d49815e4e02682cc8c7171f54095175365db3f94e',
    'mstosamps':'c7c745c855cc7034e43152c8012dec296efbf15f1abf4a5983f3553a02bb7cc5',
    'prepareToProcess':'04c7104d9f70621616e683c47caddbbc61dc96b6570ee8a47092f28e1ff23ede',
    'comb_tilde_01_feedForward_read':'7e5e18e896cfc3faced3ec20e9a5152d1a9a040c410f86f4f6ef69ba0038b74a',
    'comb_tilde_01_feedForward_write':'682aca85c3a8790639459017021a10587967214603baec9dc8f5bf099cf36cc9',
    'comb_tilde_01_feedForward_step':'e48a62ffce2f1cb56b17d25ed37b1078bae1f2bd09cc3b792008ac88b122b6a0',
    'comb_tilde_01_feedBack_read':'838c35859078107ffdf42732ac3ac5f066de1d8c20b4f781db217a5250f2c1eb',
    'comb_tilde_01_feedBack_write':'30752f4e8f6f2c91687498fe6c679ca6b0f335f222a8a44cd640f37a57ec05c6',
    'comb_tilde_01_feedBack_step':'85a1da361922c382408beb0f764af48a8196c170cad11f32b83721b800802235',
    'allpass_tilde_01_feedForward_read':'63d1903b67c4511912bdfc2210556d1bf7688feef08d57987d446aaafba43570',
    'allpass_tilde_01_feedForward_write':'120524b98130af2d1d5862687b95f7a2a35a26ca262e915dca1d9b12fcbdf5f4',
    'allpass_tilde_01_feedForward_step':'738757467df1f0c11598afd057eac1ccb2f54368853db3167ab735d133157d62',
    'allpass_tilde_01_feedBack_read':'49a602519d710bb5c06073f41f7917fbf6f3e18c4e501a71268a91b163725516',
    'allpass_tilde_01_feedBack_write':'9a6bab0a6c1ca8d769bfb07f192abb744899ec3d0c24a7aff0c5b282762ac62a',
    'allpass_tilde_01_feedBack_step':'eee8cb63f441579c0e24636a2c586650e66e82cb1a5fe8fd8cfd12961ab50055'}
CONTRACT='''/* PRIVATE exact44100 admission compile contract; no emitted operations. */
#include <float.h>
#include <limits>
#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ > 0)
#error "Exact44100 requires strict floating-point compilation"
#endif
#if FLT_RADIX != 2 || FLT_MANT_DIG != 24 || FLT_MAX_EXP != 128 || FLT_MIN_EXP != -125 || FLT_EVAL_METHOD != 0
#error "Exact44100 requires binary32 without extended evaluation"
#endif
#if DBL_MANT_DIG != 53 || DBL_MAX_EXP != 1024 || DBL_MIN_EXP != -1021
#error "Exact44100 requires IEEE binary64 double"
#endif
static_assert(sizeof(float)==4 && sizeof(RNBO::number)==4 && sizeof(RNBO::Sample)==4 &&
              sizeof(RNBO::SampleValue)==4 && std::numeric_limits<RNBO::number>::is_iec559 &&
              std::numeric_limits<RNBO::number>::digits==24 && std::numeric_limits<RNBO::Sample>::is_iec559 &&
              std::numeric_limits<RNBO::Sample>::digits==24 && std::numeric_limits<RNBO::SampleValue>::is_iec559 &&
              std::numeric_limits<RNBO::SampleValue>::digits==24, "Exact44100 requires RNBO binary32 samples");
static_assert(sizeof(double)==8 && sizeof(RNBO::MillisecondTime)==8 &&
              std::numeric_limits<double>::is_iec559 && std::numeric_limits<RNBO::MillisecondTime>::is_iec559 &&
              std::numeric_limits<RNBO::MillisecondTime>::digits==53 &&
              std::numeric_limits<RNBO::MillisecondTime>::max_exponent==1024 &&
              std::numeric_limits<RNBO::MillisecondTime>::min_exponent==-1021, "Exact44100 retains binary64 scheduler time");
'''

def sha(value):return hashlib.sha256(value).hexdigest()
def canonical(value):return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()
def require(ok,message):
    if not ok:raise ValueError('exact-audio-delay44100: '+message)

def transform(files,description,options,helper,*,code_mask):
    """Return a new source map+proof; input maps/objects are never mutated."""
    require(isinstance(files,dict) and all(isinstance(n,str) and isinstance(v,bytes) for n,v in files.items()),'immutable byte source map required')
    require(isinstance(options,dict) and set(options)==set(OPTIONS),'unknown/missing API option')
    for name,value in OPTIONS.items():
        actual=options[name]
        if name=='filter_delay_max_ms':require(type(actual) in (int,float) and actual==40,'cap40 required')
        else:require(type(actual) is type(value) and actual==value,'unsupported '+name)
    require(isinstance(helper,bytes) and sha(helper)==HELPER,'changed proven helper')
    require(HELPER_NAME not in files,'partial/repeated helper composition')
    source=files.get('rnbo_source.h');stored=files.get('description.json')
    require(isinstance(source,bytes) and sha(source)==SOURCE,'unknown/partial/repeated source')
    require(isinstance(stored,bytes) and sha(stored)==DESCRIPTION,'unreviewed description')
    try:matches=isinstance(description,dict) and canonical(description)==canonical(json.loads(stored))
    except (ValueError,TypeError,UnicodeError):matches=False
    require(matches,'description object differs')
    inventory={name:sha(data) for name,data in sorted(files.items())}
    runtime={name:value for name,value in inventory.items() if name.startswith('common/')}
    require(len(runtime)==36 and sha(canonical(runtime))==RUNTIME,'runtime/types/normal fixes differ')
    input_map=sha(canonical(inventory))
    require(len(files)==42 and input_map in (FILE_MAP,GENEXPR_FILE_MAP,INTEGER_UI_FILE_MAP),'unknown file/config/source composition')
    text=source.decode();masked=code_mask(text)
    require(isinstance(masked,str) and len(masked)==len(text),'invalid C++ lexical mask')
    require(re.findall(r'\bvoid\s+((?:comb|allpass)_tilde_\d+_perform)\s*\(',masked)==['comb_tilde_01_perform','allpass_tilde_01_perform'],'filter context differs')
    for name,expected in METHODS.items():
        a,b=_method(masked,name);require(sha(re.sub(r'\s+','',masked[a:b]).encode())==expected,'method differs: '+name)
    require(len(re.findall(r'\bnumber\s+sr\s*;',masked))==1,'SR storage differs')
    require(re.findall(r'(?<![\w])(?:this->)?sr\s*=(?!=)\s*([^;]+);',masked)==['sampleRate','44100'],'SR writes differ')
    require(not re.search(r'&\s*(?:this->)?sr\b|\bsr\s*(?:\+=|-=|\+\+|--)',masked),'SR alias/mutation')
    compact=re.sub(r'\s+','',masked)
    rings=[]
    for kind in ('comb','allpass'):
        for side in ('feedForward','feedBack'):
            prefix=kind+'_tilde_01_'+side
            require(len(re.findall(r'this->'+prefix+r'_bufferobj=initDataRef\(this->'+prefix+r'_bufferobj,this->dataRefStrings->name\d+,true,this->dataRefStrings->file\d+,this->dataRefStrings->tag\d+\);',compact))==1,'internal DataRef ownership differs')
            require(compact.count('newFloat64Buffer(this->'+prefix+'_bufferobj)')==1 and compact.count('Float64BufferRef'+prefix+'_buffer;')==1,'Float64 ring view/constructor differs')
            rings.append(prefix)
    pairs=[('comb_tilde_01_perform','this->mstosamps((__delayTime > 40.0 ? 40.0 : __delayTime))','private_delay44100_capped40(__delayTime, this->sr)'),
           ('allpass_tilde_01_perform','this->mstosamps((delayTime[(Index)i] > 40.0 ? 40.0 : delayTime[(Index)i]))','private_delay44100_capped40(delayTime[(Index)i], this->sr)')]
    changed=text
    for method,old,new in pairs:
        a,b=_method(masked,method);body=text[a:b]
        require(body.count(old)==1 and body.index(old)>body.index('for (i = 0; i < 256; i++)'),'per-sample conversion differs')
        require('const Sample * RNBO_RESTRICT delayTime' in body[:body.index('{')],'duration is not Float32 signal input')
        require(changed.count(old)==1,'duplicate conversion')
        changed=changed.replace(old,new)
    anchor='#include RNBO_LIB_INCLUDE(RNBO_AudioSignal.h)\n';include='#include "'+HELPER_NAME+'"\n'
    require(changed.count(anchor)==1,'RNBO include anchor differs')
    tested=changed.replace(anchor,anchor+include)
    require(sha(tested.encode())==TESTED_SOURCE,'private tested source inverse differs')
    updated=tested.replace(anchor+include,anchor+include+CONTRACT)
    require(updated.count(CONTRACT)==1 and updated.replace(CONTRACT,'')==tested,'assertion removal differs')
    require(sha(updated.encode())==GUARDED_SOURCE,'guarded source differs from the reviewed admission prototype')
    inverse=tested.replace(include,'')
    for _,old,new in pairs:inverse=inverse.replace(new,old)
    require(inverse==text,'full original inverse differs')
    result=dict(files);result.update({'rnbo_source.h':updated.encode(),HELPER_NAME:helper})
    return result,{'name':'rnbo-1.4.4-exact-audio-delay44100-v1','file':'rnbo_source.h','input_sha256':SOURCE,'prepared_sha256':sha(updated.encode()),
        'assertion_removed_source_sha256':TESTED_SOURCE,'helper_sha256':HELPER,'inline_contract_sha256':sha(CONTRACT.encode()),
        'description_file_sha256':DESCRIPTION,'helper_file':HELPER_NAME,
        'runtime_tree_sha256':RUNTIME,'whole_input_map_sha256':input_map,'input_file_count':42,'method_pins':dict(METHODS),
        'source_inverse_byte_identity':True,'assertion_removal_byte_identity':True,'audio_call_substitutions':2,
        'signal_duration_stays_per_sample':True,'shared_scheduler_mstosamps_unchanged':True,
        'owned_float64_rings':rings,'options':json.loads(canonical(options)),
        'domain':'Float32 duration0..40ms at SR44100 uses exact integer conversion; faithful original capped Double fallback otherwise; nearest/even only',
        'ownership':'Opaque exclusive callbacks; input/output planes separate from private state/rings; no external resources/concurrent prepare/fenv observation',
        'rounding_assumption':'Runtime round-to-nearest/even; compile checks do not establish the current runtime mode',
        'floating_environment_equivalence_claimed':False,'nan_payload_equivalence_claimed':False,
        'production_available':True,'hardware_executed':False}
