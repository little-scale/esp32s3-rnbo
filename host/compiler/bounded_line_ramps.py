# SPDX-License-Identifier: MIT
"""Experimental bounded scalar line correctness pass for one exact RNBO graph.

All replacement C++ below is original adapter code. Original generated methods
are read from the admitted input for the inverse; no generated body is vendored.
This changes numerical/state implementation, not the Float32 compiler mode.
"""
import hashlib
import json
import re
from bounded_filters import _method

SOURCE='5c4b6d384b614c22c59fe842173c59e545d07172b8778c776b70b68c9970cff3'
DESCRIPTION='55c7dd99e757e8b9d89ec8b3e20015637a8577bc82bb149a735003c6c4a942c0'
PATCH='178812e9bf55cb23c342cc4fe369f88be190ef431a50c80f86d33264e5dd1a34'
RUNTIME='fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d'
FILE_MAP='daf234beebf45b4b2c34549cf89e7e9f608afc64afb8a51cec5333d70b02c107'
# Exact same41 DSP/runtime/config/graph files; the GenExpr-aware importer
# changes only generator.json's patcher_adapter_sha256. Retain both whole maps.
GENEXPR_FILE_MAP='4ea3d3850bd351942b1f732eebc16497a8dc43119e186b00927f7c55550adca3'
UNGUARDED_SOURCE='1a3f2d4ad8854f2261dc31ea24ae944641ccd5c0e6c3fe89bbf470c8fc55a3f6'
OPTIONS={'rnbo_version':'1.4.4','apply_fixes':True,'role':'main','sample_rate':44100,'block_frames':256,
         'audio_inputs':0,'audio_outputs':2,'numerical_profile':'float32-strict','filter_delay_max_ms':None,
         'float32_delay_storage':False,'required_host_services':[],'other_optimizations':[]}
GUARDED_SOURCE='2065b57193bdddbd1ef8b4188c0c590eef66fe0cca529e76bbef63ba7c0ac1c9'
METHODS=[{'name': 'linetilde_01_segments_set',
  'sha256': '4f570055b7460e185f3a94935a8071ebc70df75088b1a20cb92ee41eefae8993'},
 {'name': 'pack_01_out_set',
  'sha256': '3acd10d40f03c3f268b89d4a0e259c3890b7a714b1dce0de65ef0e28d6ca2ac3'},
 {'name': 'pack_01_in1_number_set',
  'sha256': '05b58f5b21e13e833aa90aa83ac57d2940dfdb05a5cfee5b2789a43db87095d0'},
 {'name': 'pack_01_in2_set',
  'sha256': 'de91ad78494082e5f375def18da2f1ccbcc5b262dc91626c5ab4a0cbb5adf9aa'},
 {'name': 'param_01_value_set',
  'sha256': 'ab9a9273ce5e1173e87622bacbe67c4e6a192b94d9b99d119a1342367e79343d'},
 {'name': 'param_02_value_set',
  'sha256': '2381109da3f43c7e196f75d826ced336d99295f71d199df62c1307d4c1108030'},
 {'name': 'linetilde_01_perform',
  'sha256': 'b1782e3d74d27decb51517d750e4fd7eb7e40e1a739d80ce1c0a9be7b39a4990'},
 {'name': 'currentsampletime',
  'sha256': '54b8d6de8370b31f7b8ed31ae3fe222d957eac8649819f3bd6202430cb90a754'},
 {'name': 'mstosamps', 'sha256': '1405584e15832c90f88dbceca9ad1e7bd082f49a05b8b2f09726ef597505377b'},
 {'name': 'updateTime', 'sha256': 'd5eca3f43f9bedd051b519b4088522fd90260a9d84d4d1cde7298f9b0d118040'},
 {'name': 'updateTime', 'sha256': '65b3176a30e9d2b2e691513114f09a64487328ac98d51b1be56ad79d2db70755'},
 {'name': 'process', 'sha256': '7df0fdf9b8069253f3e47c5a582160ae6d94636ee6e5ce26268df5e0b13141f6'},
 {'name': 'assign_defaults',
  'sha256': '1652b4a8b832dbae82628168e9b7a69a34bc1abb71f5d5c63f5fa69fed354e7a'}]
SEGMENT="""void linetilde_01_segments_set(const LISTTYPE& v) {
    this->linetilde_01_segments = jsCreateListCopy(v);
    RNBO_ASSERT(v->length == 2);
    if (v->length != 2) return; // Only the pinned two-item pack route is reviewed.
    const UInt64 now = this->currentsampletime();
    const number initial = this->private_line_value_at(now);
    number duration = this->mstosamps(v[1]); // Preserve the original Double conversion/Float32 return.
    if (duration <= 1) duration = 1; // Discrete one-sample causal path; never divide by tiny duration.
    this->private_line_start = initial;
    this->private_line_target = v[0];
    this->private_line_duration = duration;
    this->private_line_count = (UInt32)duration;
    if (duration > (number)this->private_line_count) ++this->private_line_count;
    this->private_line_increment = duration > 1 ? (this->private_line_target - initial) / duration : 0;
    this->private_line_anchor = now;
    (void)now;
    this->private_line_active = true;
    if ((bool)this->linetilde_01_keepramp) this->linetilde_01_time_set(v[1]);
}"""
PERFORM="""void linetilde_01_perform(SampleValue * out, Index n) {
    const UInt64 now = this->audioProcessSampleCount;
    number val = this->private_line_value_at(now); // Intentional per-block numerical re-anchor.
    UInt32 remaining = this->private_line_remaining(now);
    bool completed = false;
    if (this->private_line_active && !remaining) {
        val = this->private_line_target;
        this->private_line_active = false;
        completed = true;
    }
    for (Index i = 0; i < n; ++i) {
        out[i] = val; // Original causal output-before-advance policy.
        if (this->private_line_active) {
            val += this->private_line_increment; // Float32 audio inner loop only.
            --remaining;
            if (!remaining) {
                val = this->private_line_target;
                this->private_line_active = false;
                completed = true;
            }
        }
    }
    this->linetilde_01_currentValue = val;
    if (completed) {
        this->getEngine()->scheduleClockEventWithValue(
            this, 894770446,
            this->sampsToMs((SampleIndex)(256)) + this->_currentTime, 0);
        if (!(bool)this->linetilde_01_keepramp) this->linetilde_01_time = 0;
    }
}"""
HELPERS="""number private_line_value_at(UInt64 now) {
    if (!this->private_line_active) return this->linetilde_01_currentValue;
    if (now <= this->private_line_anchor) return this->private_line_start;
    const UInt64 age = now - this->private_line_anchor;
    if (age >= (UInt64)this->private_line_count) return this->private_line_target;
    const UInt32 short_age = (UInt32)age; // Narrow only after proving age < ceil(D) <= 4410.
    return this->private_line_start + (number)short_age * this->private_line_increment;
}
UInt32 private_line_remaining(UInt64 now) {
    if (!this->private_line_active) return 0;
    if (now <= this->private_line_anchor) return this->private_line_count;
    const UInt64 age = now - this->private_line_anchor;
    if (age >= (UInt64)this->private_line_count) return 0;
    return this->private_line_count - (UInt32)age;
}
"""
FIELDS="""    bool private_line_active = false;
    UInt64 private_line_anchor = 0;
    UInt32 private_line_count = 1;
    number private_line_start = 0, private_line_target = 0;
    number private_line_duration = 1, private_line_increment = 0;
"""
DEFAULTS="""    private_line_active = false;
    private_line_anchor = 0;
    private_line_count = 1;
    private_line_start = 0;
    private_line_target = 0;
    private_line_duration = 1;
    private_line_increment = 0;
"""
CONTRACT="""/* Experimental bounded line ramps compile contract; no emitted operations. */
#include <float.h>
#include <limits>
#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ > 0)
#error "Bounded line ramps requires strict floating-point compilation"
#endif
#if FLT_RADIX != 2 || FLT_MANT_DIG != 24 || FLT_MAX_EXP != 128 || FLT_MIN_EXP != -125 || FLT_EVAL_METHOD != 0
#error "Bounded line ramps requires binary32 without extended evaluation"
#endif
#if DBL_MANT_DIG != 53 || DBL_MAX_EXP != 1024 || DBL_MIN_EXP != -1021
#error "Bounded line ramps retains IEEE binary64 duration and clock arithmetic"
#endif
static_assert(sizeof(float)==4 && sizeof(RNBO::number)==4 && sizeof(RNBO::Sample)==4 &&
              sizeof(RNBO::SampleValue)==4 && std::numeric_limits<RNBO::number>::is_iec559 &&
              std::numeric_limits<RNBO::number>::digits==24 && std::numeric_limits<RNBO::Sample>::is_iec559 &&
              std::numeric_limits<RNBO::Sample>::digits==24 && std::numeric_limits<RNBO::SampleValue>::is_iec559 &&
              std::numeric_limits<RNBO::SampleValue>::digits==24, "Bounded line ramps requires binary32 RNBO samples");
static_assert(sizeof(double)==8 && sizeof(RNBO::MillisecondTime)==8 &&
              std::numeric_limits<double>::is_iec559 && std::numeric_limits<RNBO::MillisecondTime>::is_iec559 &&
              std::numeric_limits<RNBO::MillisecondTime>::digits==53 &&
              std::numeric_limits<RNBO::MillisecondTime>::max_exponent==1024 &&
              std::numeric_limits<RNBO::MillisecondTime>::min_exponent==-1021, "Bounded line ramps retains binary64 scheduler time");
#if !defined(RNBO_S3_ABI_MAJOR) || !defined(RNBO_S3_ABI_MINOR)
#error "Bounded line ramps requires the SDK ABI header first"
#elif RNBO_S3_ABI_MAJOR != 1u || RNBO_S3_ABI_MINOR != 0u
#error "Bounded line ramps is reviewed only with SDK ABI revision1.0"
#endif
#if !defined(RNBO_FIXEDLISTSIZE) || RNBO_FIXEDLISTSIZE != 16
#error "Bounded line ramps requires the reviewed fixed-list capacity16"
#endif
static_assert(sizeof(RNBO::UInt64)==8 && std::numeric_limits<RNBO::UInt64>::is_integer &&
              !std::numeric_limits<RNBO::UInt64>::is_signed && std::numeric_limits<RNBO::UInt64>::digits==64 &&
              sizeof(RNBO::UInt32)==4 && std::numeric_limits<RNBO::UInt32>::is_integer &&
              !std::numeric_limits<RNBO::UInt32>::is_signed && std::numeric_limits<RNBO::UInt32>::digits==32,
              "Bounded line ramps requires exact unsigned64/32 timing types");
"""

def sha(value):return hashlib.sha256(value).hexdigest()
def canonical(value):return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()
def require(ok,message):
    if not ok:raise ValueError('bounded-line-ramps: '+message)
def method_hashes(text,masked,name):
    matches=re.finditer(r'\b(?:void|number|UInt64|MillisecondTime)\s+'+re.escape(name)+r'\s*\([^{};]*\)(?:\s+const)?\s*\{',masked)
    result=[]
    for match in matches:
        end=match.end();depth=1
        while depth:
            if masked[end]=='{':depth+=1
            elif masked[end]=='}':depth-=1
            end+=1
        result.append(sha(text[match.start():end].encode()))
    return result

def transform(files,description,options,*,code_mask):
    """Return a new source map and audit record; no I/O or caller mutation."""
    require(isinstance(files,dict) and all(isinstance(n,str) and isinstance(v,bytes)for n,v in files.items()),'immutable byte source map required')
    require(isinstance(options,dict) and set(options)==set(OPTIONS),'unknown/missing API option')
    for name,expected in OPTIONS.items():require(type(options[name])is type(expected)and options[name]==expected,'unsupported '+name)
    source=files.get('rnbo_source.h');stored=files.get('description.json')
    require(isinstance(source,bytes)and sha(source)==SOURCE,'unknown/partial/repeated line source')
    require(isinstance(stored,bytes)and sha(stored)==DESCRIPTION,'unreviewed description')
    try:matches=isinstance(description,dict)and canonical(description)==canonical(json.loads(stored))
    except (ValueError,TypeError,UnicodeError):matches=False
    require(matches,'description object differs')
    require(sha(files.get('source.rnbopat',b''))==PATCH,'authored line/pack graph differs')
    inventory={n:sha(v)for n,v in sorted(files.items())};runtime={n:h for n,h in inventory.items()if n.startswith('common/')}
    require(len(runtime)==36 and sha(canonical(runtime))==RUNTIME,'runtime/types/normal fixes differ')
    input_map=sha(canonical(inventory))
    require(len(files)==42 and input_map in (FILE_MAP,GENEXPR_FILE_MAP),'unknown file/config/source composition')
    text=source.decode();masked=code_mask(text)
    require(isinstance(masked,str)and len(masked)==len(text),'invalid C++ lexical mask')
    for m in METHODS:require(m['sha256']in method_hashes(text,masked,m['name']),'caller/clock/kernel differs: '+m['name'])
    require('private_line_'not in masked,'partial/repeated bounded state')
    require(len(re.findall(r'\blinetilde_01_perform\b',masked))==2,'only one reviewed scalar caller/definition admitted')
    require(re.search(r'\bDataRefIndex\s+getNumDataRefs\(\)\s+const\s*{\s*return 0;\s*}',masked)is not None,'external resources unsupported')
    require(len(re.findall(r'\bnumber\s+sr\s*;',masked))==1 and re.findall(r'(?<![\w])(?:this->)?sr\s*=(?!=)\s*([^;]+);',masked)==['sampleRate','44100'],'SR storage/writes differ')
    require(not re.search(r'&\s*(?:this->)?(?:sr|linetilde_01_(?:activeRamps|currentValue|segments))\b',masked),'private state alias differs')
    edits=[];inverse=[]
    for name,new in [('linetilde_01_segments_set',SEGMENT),('linetilde_01_perform',PERFORM)]:
        a,b=_method(masked,name);old=text[a:b];edits.append((a,b,new));inverse.append((old,new))
    a,b=_method(masked,'assign_defaults');old=text[a:b];new=old[:-1]+DEFAULTS+'}';edits.append((a,b,new));inverse.append((old,new))
    changed=text
    for a,b,new in sorted(edits,reverse=True):changed=changed[:a]+new+changed[b:]
    anchor='// member variables\n';require(changed.count(anchor)==1,'member anchor differs')
    changed=changed.replace(anchor,HELPERS+'\n'+anchor+FIELDS)
    restored=changed.replace(HELPERS+'\n'+anchor+FIELDS,anchor)
    for old,new in inverse:
        require(restored.count(new)==1,'inverse method ambiguous');restored=restored.replace(new,old)
    require(restored==text and sha(changed.encode())==UNGUARDED_SOURCE,'complete original/private B inverse differs')
    include='#include RNBO_LIB_INCLUDE(RNBO_AudioSignal.h)\n';require(changed.count(include)==1,'RNBO include anchor differs')
    guarded=changed.replace(include,include+CONTRACT)
    require(guarded.replace(CONTRACT,'')==changed and sha(guarded.encode())==GUARDED_SOURCE,'compile assertion/source identity differs')
    result=dict(files);result['rnbo_source.h']=guarded.encode()
    return result,{'name':'rnbo-1.4.4-bounded-line-ramps-v1','file':'rnbo_source.h','experimental':True,
        'correctness_profile':'bounded-line-ramps-v1','input_sha256':SOURCE,'prepared_sha256':GUARDED_SOURCE,
        'assertion_removed_source_sha256':UNGUARDED_SOURCE,'inline_contract_sha256':sha(CONTRACT.encode()),
        'description_file_sha256':DESCRIPTION,'authored_patch_sha256':PATCH,'runtime_tree_sha256':RUNTIME,
        'whole_input_map_sha256':input_map,'input_file_count':42,'method_pins':[dict(m)for m in METHODS],
        'source_inverse_byte_identity':True,'assertion_removal_byte_identity':True,
        'bounded_single_active_segment':True,'original_duration_conversion_unchanged':True,
        'correctness_changes':['UInt64 anchor with bounded UInt32 age and Float32 relative duration','D<=1 causal one-sample path without reciprocal','Replace cancelled same-block segments instead of appending dead list entries','Intentional Float32 per-block reanchor changes rounding'],
        'completion_clock':'Original callback/id/next-vector timestamp policy; no flush of already queued completions; initial zero-to-zero ramp retained',
        'ownership':'Exclusive actual boundary callbacks; no aliases, external resources or concurrent prepare; ABI revision assertions do not establish these runtime conditions',
        'abi_revision_required':[1,0],'rounding_assumption':'Runtime nearest/even; compile checks do not establish current runtime mode',
        'baseline_bit_identity_claimed':False,'floating_environment_equivalence_claimed':False,'nan_payload_equivalence_claimed':False,
        'hardware_executed':False,'target_cpu_gain_claimed':False,'options':json.loads(canonical(options))}
