# SPDX-License-Identifier: MIT
"""Explicit changed-rounding Float32 profile for one original Gen program.

Only a literal suffix changes. Whole-source, graph, metadata and normal-runtime
pins prevent this from becoming a general GenExpr or C++ literal rewriter.
"""
import hashlib
import json
from pathlib import Path
from bounded_filters import _method

PROFILE = 'float32-gen-feedback-v1'
ADAPTATION = 'rnbo-1.4.4-' + PROFILE
SOURCE = 'e8ea80fd692baaf54345587d8b0908b990b6c5524bbac6c52677364a60f02721'
OUTPUT = 'db07a01a185f2bad594acba9f110f8c198dec9668fb3516112573d32752d7220'
INPUT_MAP = '7cb084216600dab080984923569ddc45c2e6b8b3a73d8371877fc976069044b2'
DESCRIPTION = '5fa1adde1e70050d79dbc296a932a21b4a7efb4c8ecbd7176e9910b5de513270'
RUNTIME = 'fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d'
GRAPH = 'cc73307e6aaad1f7f3636c28e7d79baffe15eae9d59ac14bdef64dafbae6990e'
METHOD = 'gen_01_perform'
CONTRACT_FILE = 'rnbo_s3_gen_feedback_source.h'
CONTRACT = b'''/* SPDX-License-Identifier: MIT */
#pragma once
#include <float.h>
#include <type_traits>
#include "rnbo_source.h"
#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__)
#error "Gen feedback profile requires strict floating arithmetic"
#endif
#if !defined(RNBO_S3_ABI_MAJOR) || !defined(RNBO_S3_ABI_MINOR) || RNBO_S3_ABI_MAJOR != 1u || RNBO_S3_ABI_MINOR != 0u
#error "Gen feedback profile requires reviewed module ABI 1.0"
#endif
static_assert(FLT_RADIX == 2 && FLT_MANT_DIG == 24 && FLT_MAX_EXP == 128 && FLT_EVAL_METHOD == 0,
              "Gen feedback requires binary32 float");
static_assert(std::is_same<RNBO::number,float>::value &&
              std::is_same<RNBO::Sample,float>::value &&
              std::is_same<RNBO::SampleValue,float>::value && sizeof(float) == 4,
              "Gen history, inputs and outputs must remain binary32");
static_assert(std::is_same<decltype(RNBO::number{} + 0.5f * RNBO::number{}),float>::value,
              "Gen feedback expression must use Float32 intermediates");
static_assert(std::is_same<RNBO::MillisecondTime,double>::value && sizeof(double) == 8,
              "Gen feedback does not change the scheduler clock");
'''
MANIFEST_CONTRACT = {
    'version': 1, 'context': 'history-feedback', 'coefficient': 0.5,
    'operation': 'binary32-multiply-then-add', 'contraction': 'disabled',
    'input_domain': {'finite': True, 'absolute_maximum': 0.5},
    'state_initial_and_reset': 0.0, 'state_absolute_bound': 1.0,
    'state_storage': 'unchanged-binary32', 'scheduler_time': 'unchanged-binary64',
    'bit_identity_claimed': False, 'signed_zero_identity_claimed': False,
    'floating_environment_equivalence_claimed': False, 'nonfinite_qualified': False,
    'qualification_scope': 'original bounded history-feedback program and independently verified input/reset cases',
}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode()


def transform(files, description, *, code_mask):
    """Return a new immutable file map; reject unknown contexts atomically."""
    def require(ok, message):
        if not ok: raise ValueError('Gen feedback Float32: ' + message)
    require(type(files) is dict and all(type(k) is str and type(v) is bytes for k,v in files.items()),
            'immutable source map required')
    require(len(files) == 41 and sha(canonical({k: sha(v) for k,v in files.items()})) == INPUT_MAP,
            'unknown graph/source/metadata/runtime composition or repeated application')
    source = files['rnbo_source.h']
    require(sha(source) == SOURCE and sha(files['source.rnbopat']) == GRAPH and
            sha(files['description.json']) == DESCRIPTION, 'original source/graph/description differs')
    require(type(description) is dict and canonical(description) == canonical(json.loads(files['description.json'])),
            'description object differs')
    runtime = {k: sha(v) for k,v in sorted(files.items()) if k.startswith('common/')}
    require(len(runtime) == 36 and sha(canonical(runtime)) == RUNTIME, 'normal runtime or type fixes differ')
    text = source.decode(); masked = code_mask(text)
    require(type(masked) is str and len(masked) == len(text), 'invalid lexical mask')
    start, stop = _method(masked, METHOD)
    old = '0.5 * __gen_01_z_value'; new = '0.5f * __gen_01_z_value'
    body = text[start:stop]
    require(masked[start:stop].count(old) == body.count(old) == text.count(old) == 1,
            'unknown or hidden feedback literal/caller')
    updated_body = body.replace(old, new)
    changed = (text[:start] + updated_body + text[stop:]).encode()
    require(sha(changed) == OUTPUT and changed.replace(new.encode(), old.encode()) == source,
            'prepared source or one-character inverse differs')
    result = dict(files)
    result.update({'rnbo_source.h': changed, CONTRACT_FILE: CONTRACT})
    return result, {
        'name': ADAPTATION, 'file': 'rnbo_source.h', 'method': METHOD,
        'input_sha256': SOURCE, 'prepared_sha256': OUTPUT, 'input_map_sha256': INPUT_MAP,
        'description_file_sha256': DESCRIPTION, 'editable_source_sha256': GRAPH,
        'runtime_tree_sha256': RUNTIME, 'inverse_byte_identity': True, 'inserted_bytes': 1,
        'input_method_sha256': sha(body.encode()), 'prepared_method_sha256': sha(updated_body.encode()),
        'compile_contract_file': CONTRACT_FILE, 'compile_contract_sha256': sha(CONTRACT),
        'changed_rounding': True, 'bit_identity_claimed': False, 'scheduler_time_unchanged': True,
        'transformer_sha256': sha(Path(__file__).read_bytes()),
    }
