# SPDX-License-Identifier: MIT
"""Guarded stable Float32 onepole update in three reviewed RNBO1.4.4 FX forms.

The source/data interpretation and rounding deliberately change. Original
input maps, callers, state ownership and Float64 scheduler code are pinned.
The independent helper is original adapter code; no generated body is vendored.
"""
import hashlib
import json
import re

HELPER_SHA256 = '38dab5881581200a254f619d84e92b9bb1b77a958737eadbfed651937d6cda7c'
RUNTIME = 'fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d'
CONTEXTS = {
 'onepole-fixed-stereo': {'source':'b1e3616bc55dd1124288136e4456fe487adf24b7c90e04523d41cc489f657c61','description':'85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314','patch':'165243833244cfc7be886ddd73b69dacb70c7096000b2a4b32aac1218e0f266c','file_map':'1328820f84015ffb3e09cc354f955ce5c892a0483ec53bf9d65c222a3aa392ed','instances':2},
 'onepole-scalar-stereo': {'source':'e90e695aec96abb63ed29873817e432701e062dc104b3bdaff9ebe19e26aab0b','description':'6ae479eda282ebb6b87f1a752da07b78d4d3669adcb336d82e57d76edf821e71','patch':'93af0c651e74cceb5d2b72594e3f10d10ad1ee5be53b79f1b86090990431f4a8','file_map':'346695c46acdd4b3803b7f3cb580ef87493fd919858ffa52109b352faa9ba5d6','instances':2},
 'onepole-signal-cutoff': {'source':'95a093ab048cabd77d057c877f7e49e33ec74a8e29a58007c2efc08f552b8096','description':'85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314','patch':'4fb35c91af67ba8f4fa3fd712ae804b7687448736fcd699e3f65811638f00386','file_map':'efea3ab531a08e0c70acbc02b14886cf6b1f60c5a858ec6926ac6004661591a5','instances':1},
}
# Exact alternative42-file maps after the GenExpr-aware importer changed only
# generator.json's patcher_adapter_sha256. Historical CONTEXTS pins remain valid.
GENEXPR_FILE_MAPS = {
 'onepole-fixed-stereo':'eb177eeb6f6f1c7030399d4f6e05701169051523b55913660c5618a7494a3543',
 'onepole-scalar-stereo':'4f2a342cd98c00d649c5d6952a5541caf4f50e0cbea7329da89774675bc55802',
 'onepole-signal-cutoff':'9eaf9fcf96bacfc93f5e90a08783ded3d610028623b9db4a65d4188168855421',
}
# Exact current producer maps; all other41 files equal the retained inputs.
INTEGER_UI_FILE_MAPS = {'onepole-fixed-stereo': 'f6dc8334efe8e2c9259cdaff8302eb3062c29b1365d0d9de0b6a52b1dbb50786', 'onepole-scalar-stereo': '546cdb18c0d3f65830b0e87a19f7d98ed2b312ab73c4881c218627a819db22c3', 'onepole-signal-cutoff': 'd934896fde203454f54754bdbb57cab4dffcb41e33949850d8524469fe5f2bb7'}

OPTIONS = {'rnbo_version':'1.4.4','apply_fixes':True,'role':'fx','sample_rate':44100,'block_frames':256,
           'audio_inputs':2,'audio_outputs':2,'numerical_profile':'float32-strict','filter_delay_max_ms':None,
           'float32_delay_storage':False,'required_host_services':[],'other_optimizations':[]}
CONTRACT = '''/* Experimental stable onepole: actual types/ABI only, not runtime rounding or ownership. */
#include "onepole_stable.h"
#include <type_traits>
static_assert(::std::is_same<RNBO::number, float>::value &&
              ::std::is_same<RNBO::Sample, float>::value &&
              ::std::is_same<RNBO::SampleValue, float>::value,
              "Stable onepole requires ordinary Float32 RNBO audio and state");
static_assert(::std::is_same<RNBO::MillisecondTime, double>::value && sizeof(double) == 8 &&
              ::std::numeric_limits<double>::is_iec559 && ::std::numeric_limits<double>::digits == 53,
              "Stable onepole retains binary64 scheduler time");
#if !defined(RNBO_S3_ABI_MAJOR) || !defined(RNBO_S3_ABI_MINOR) || RNBO_S3_ABI_MAJOR != 1u || RNBO_S3_ABI_MINOR != 0u
#error "Stable onepole is reviewed with opaque SDK ABI revision1.0"
#endif
#if !defined(RNBO_FIXEDLISTSIZE) || RNBO_FIXEDLISTSIZE != 16
#error "Stable onepole requires the reviewed fixed-list capacity16"
#endif
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()


def require(ok, message):
    if not ok:
        raise ValueError('stable-onepole: '+message)


def transform(files, description, options, *, code_mask, helper):
    """Return a new immutable byte map and audit record; perform no I/O."""
    require(isinstance(files,dict) and all(isinstance(n,str) and isinstance(v,bytes) for n,v in files.items()),'immutable byte source map required')
    require(isinstance(options,dict) and set(options)==set(OPTIONS),'unknown/missing option')
    for key,expected in OPTIONS.items():
        require(type(options[key]) is type(expected) and options[key]==expected,'unsupported '+key)
    require(isinstance(helper,bytes) and sha(helper)==HELPER_SHA256,'unreviewed helper implementation')
    source=files.get('rnbo_source.h');require(isinstance(source,bytes),'missing source')
    selected=[(name,pins) for name,pins in CONTEXTS.items() if sha(source)==pins['source']]
    require(len(selected)==1,'unknown/partial/repeated source')
    name,pins=selected[0];stored=files.get('description.json')
    require(isinstance(stored,bytes) and sha(stored)==pins['description'],'description differs')
    try:
        same=isinstance(description,dict) and canonical(description)==canonical(json.loads(stored))
    except (ValueError,TypeError,UnicodeError):
        same=False
    require(same,'description object differs')
    require(sha(files.get('source.rnbopat',b''))==pins['patch'],'authored graph differs')
    inventory={n:sha(data) for n,data in sorted(files.items())}
    runtime={n:h for n,h in inventory.items() if n.startswith('common/')}
    require(len(runtime)==36 and sha(canonical(runtime))==RUNTIME,'runtime/types/normal fixes differ')
    input_map=sha(canonical(inventory))
    require(len(files)==42 and input_map in (pins['file_map'],GENEXPR_FILE_MAPS[name],INTEGER_UI_FILE_MAPS[name]),'source/config/caller composition differs')
    text=source.decode();masked=code_mask(text)
    require(isinstance(masked,str) and len(masked)==len(text),'invalid C++ lexical mask')
    instances=re.findall(r'    number (onepole_tilde_\d+)_b1;',masked)
    require(len(instances)==pins['instances'] and len(set(instances))==len(instances),'state inventory differs')
    edits=[];changed=text;state=[]
    for prefix in instances:
        pattern=re.compile(r'\b(?:__)?'+prefix+r'_b1\b')
        require(len(list(pattern.finditer(code_mask(changed))))==9,'feedback state references differ')
        renamed=pattern.sub(lambda m:m[0].replace('_b1','_correction'),changed)
        # Complete source identity was checked above; all nine matched names
        # are the private declaration/default/reset/cache/store/update/recurrence.
        edits.append(('rename',changed,renamed));changed=renamed
        local='__'+prefix
        complement=f'            {local}_correction = 1 - {local}_a0;\n'
        require(changed.count(complement)==1,'coefficient-complement write differs')
        at=changed.index(complement);changed=changed[:at]+changed[at+len(complement):]
        edits.append(('remove',at,complement))
        expression=re.compile(r'            '+local+r'_a0 = 1 - rnbo_exp\([^\n]+\);\n            '+local+r'_a0 = \([^\n]+\);')
        matches=list(expression.finditer(changed));require(len(matches)==1,'coefficient/update context differs')
        old=matches[0][0];new=f'            {local}_a0 = ::rnbo_s3_onepole::coefficient({local}_freq);'
        changed=changed.replace(old,new);edits.append(('replace',old,new))
        old=f'        {local}_lastY = {local}_a0 * x[(Index)i] + {local}_correction * {local}_lastY;'
        new=f'        ::rnbo_s3_onepole::step(x[(Index)i], {local}_a0, {local}_lastY, {local}_correction);'
        require(changed.count(old)==1,'recurrence differs')
        changed=changed.replace(old,new);edits.append(('replace',old,new))
        state.append({'instance':prefix,'old_feedback_word':prefix+'_b1','correction_word':prefix+'_correction','initial_and_reset':0,'history_preserved_across_controls_and_vectors':True})
    # Undo every edit at the original offsets before adding compile-only guards.
    restored=changed
    for edit in reversed(edits):
        if edit[0]=='replace':
            _,old,new=edit;require(restored.count(new)==1,'replacement inverse differs');restored=restored.replace(new,old)
        elif edit[0]=='remove':
            _,at,value=edit;restored=restored[:at]+value+restored[at:]
        else:
            _,old,new=edit;require(restored==new,'rename inverse differs');restored=old
    require(restored==text,'complete source inverse differs')
    anchor='#include RNBO_LIB_INCLUDE(RNBO_AudioSignal.h)\n'
    require(changed.count(anchor)==1,'global include context differs')
    candidate=changed.replace(anchor,anchor+CONTRACT)
    require(candidate.replace(CONTRACT,'')==changed,'compile contract inverse differs')
    result=dict(files);result['rnbo_source.h']=candidate.encode();result['onepole_stable.h']=helper
    return result,{'name':'rnbo-1.4.4-stable-onepole-v1','file':'rnbo_source.h','context':name,
        'input_sha256':sha(source),'prepared_sha256':sha(result['rnbo_source.h']),
        'assertion_removed_source_sha256':sha(changed.encode()),'inline_contract_sha256':sha(CONTRACT.encode()),
        'helper_sha256':HELPER_SHA256,'whole_input_map_sha256':input_map,'runtime_tree_sha256':RUNTIME,
        'source_inverse_byte_identity':True,'assertion_removal_byte_identity':True,'input_files':42,'output_files':43,
        'state_reuse':state,'added_state_members':0,'float32_audio_coefficient_and_fallback':True,
        'coefficient_scale_bits':'b9156592','sample_rate':44100,'block_frames':256,
        'experimental':True,'correctness_profile':'stable-onepole-v1','baseline_bit_identity_claimed':False,
        'finite_output_proof_scope':'finite binary32 data/frequency and initially finite private state; IEEE gradual underflow, strict noncontracted nearest-even, nontrapping execution',
        'accuracy_scope':'independent declared native programs, not a universal absolute-error bound at arbitrary amplitudes',
        'ownership':'exclusive opaque ABI callbacks; independent private state words and input/output planes; no direct C++ state mutation, external aliases or concurrent prepare',
        'scheduler_time_unchanged':'binary64; complete source inverse preserves all unrelated code',
        'floating_environment_equivalence_claimed':False,'nan_payload_equivalence_claimed':False,
        'target_cpu_gain_claimed':False,'options':json.loads(canonical(options))}
