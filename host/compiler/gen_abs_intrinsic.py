# SPDX-License-Identifier: MIT
"""Default-off, exact-source Float32 abs implementation selection.

The two callee tokens change; the original mathematical operation and every
runtime, clock, state and interface byte remain outside the transformation.
"""
import hashlib
import json
from pathlib import Path
from bounded_filters import _method

ADAPTATION='rnbo-1.4.4-gen-abs-intrinsic-v1'
SOURCE='86cb0539073bef4bccb2352681eac0c051c0890731e42d3744beeec71397220d'
OUTPUT='3df5fb401c1d1e04470e318f3aa1f4704ff38d17845ece0f7dacf74defa93943'
INPUT_MAP='ccccfd54d10f46b83705c7b315e27fd4e83b5ae3dccb525f1a65ceb863c2d8f4'
# Exact current producer epoch; the other40 input files are unchanged.
INTEGER_UI_INPUT_MAP='df798de518f675e8148afc28be3a28537e310fe70ece17883c353f0bac13c324'
GRAPH='c2878ab82152020b8a26f006c96e22b7a4837ecfe9005ca9768bcaf9bbba39c6'
DESCRIPTION='85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314'
RUNTIME='fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d'
CONTRACT_FILE='rnbo_s3_gen_abs_source.h'
CONTRACT=b'''/* SPDX-License-Identifier: MIT */
#pragma once
#include <float.h>
#include <type_traits>
#include "rnbo_source.h"
#if !defined(__GNUC__) && !defined(__clang__)
#error "Gen abs intrinsic requires the reviewed GNU-compatible builtin"
#endif
#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__)
#error "Gen abs intrinsic requires strict floating arithmetic"
#endif
#if !defined(RNBO_S3_ABI_MAJOR) || !defined(RNBO_S3_ABI_MINOR) || RNBO_S3_ABI_MAJOR != 1u || RNBO_S3_ABI_MINOR != 0u
#error "Gen abs intrinsic requires reviewed ABI 1.0"
#endif
static_assert(FLT_RADIX==2 && FLT_MANT_DIG==24 && FLT_MAX_EXP==128 &&
              FLT_EVAL_METHOD==0 && sizeof(float)==4,
              "Gen abs requires binary32 without excess evaluation precision");
static_assert(std::is_same<RNBO::number,float>::value &&
              std::is_same<RNBO::Sample,float>::value &&
              std::is_same<RNBO::SampleValue,float>::value &&
              std::is_same<decltype(__builtin_fabsf(RNBO::number{})),float>::value,
              "Gen abs input, operation and output must remain Float32");
static_assert(std::is_same<RNBO::MillisecondTime,double>::value && sizeof(double)==8,
              "Gen abs does not narrow the scheduler clock");
'''
MANIFEST_CONTRACT={
    'version':1,'context':'abs-call','operation':'explicit-binary32-absolute-builtin',
    'input_domain':'finite-binary32','finite_bit_identity_claimed':True,
    'zero_sign':'negative-zero-maps-to-positive-zero',
    'state_and_layout':'unchanged','scheduler_time':'unchanged-binary64','math_runtime':'unchanged',
    'nonfinite_qualified':False,'floating_environment_equivalence_claimed':False,
    'errno_identity_claimed':False,'floating_trap_identity_claimed':False,
}


def sha(value):return hashlib.sha256(value).hexdigest()
def canonical(value):return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()


def transform(files,description,*,code_mask):
    def require(ok,message):
        if not ok:raise ValueError('Gen abs intrinsic: '+message)
    require(type(files)is dict and all(type(k)is str and type(v)is bytes for k,v in files.items()),'immutable source map required')
    input_map=sha(canonical({k:sha(v)for k,v in files.items()}))
    require(len(files)==41 and input_map in (INPUT_MAP,INTEGER_UI_INPUT_MAP),
            'unknown source/graph/runtime/metadata composition or repeated application')
    source=files['rnbo_source.h'];stored=files['description.json']
    require(sha(source)==SOURCE and sha(files['source.rnbopat'])==GRAPH and sha(stored)==DESCRIPTION,'original source identity differs')
    require(type(description)is dict and canonical(description)==canonical(json.loads(stored)),'description object differs')
    runtime={k:sha(v)for k,v in sorted(files.items())if k.startswith('common/')}
    require(len(runtime)==36 and sha(canonical(runtime))==RUNTIME,'normal runtime/types differ')
    text=source.decode();masked=code_mask(text)
    require(type(masked)is str and len(masked)==len(text),'invalid lexical mask')
    start,stop=_method(masked,'gen_01_perform');old=text[start:stop]
    require(old.count('rnbo_abs(')==masked[start:stop].count('rnbo_abs(')==2,'unknown or hidden Gen abs calls')
    new=old.replace('rnbo_abs(','__builtin_fabsf(')
    changed=(text[:start]+new+text[stop:]).encode()
    require(sha(changed)==OUTPUT and changed.replace(new.encode(),old.encode())==source,'prepared source or two-token inverse differs')
    result=dict(files);result.update({'rnbo_source.h':changed,CONTRACT_FILE:CONTRACT})
    return result,{'name':ADAPTATION,'file':'rnbo_source.h','method':'gen_01_perform',
        'input_sha256':SOURCE,'prepared_sha256':OUTPUT,'input_map_sha256':input_map,
        'editable_source_sha256':GRAPH,'description_file_sha256':DESCRIPTION,'runtime_tree_sha256':RUNTIME,
        'input_method_sha256':sha(old.encode()),'prepared_method_sha256':sha(new.encode()),
        'callee_replacements':2,'inverse_byte_identity':True,'finite_bit_identity_claimed':True,
        'compile_contract_file':CONTRACT_FILE,'compile_contract_sha256':sha(CONTRACT),
        'scheduler_time_unchanged':True,'transformer_sha256':sha(Path(__file__).read_bytes())}
