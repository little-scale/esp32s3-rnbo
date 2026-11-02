# SPDX-License-Identifier: MIT
"""Changed-rounding Float32 power specialisation in one closed RNBO context.

This is a numerical profile, not a generic pow replacement. Full original or
finite-wrap-corrected nonlinear headers, description, runtime and pow method
are pinned. Generated RNBO algorithm bodies are not vendored in this helper.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from bounded_filters import _method

_SOURCE = "b246e2357fc3829af9d44eec0efc1aa69a82bd9157be093663005ea0eb1ea28b"
_WRAPPED = "cb3034efc572a29b2d3e9cc82e733035a12b6907b6213c9c3af9ee01ab64cbfd"
_OUTPUT = "4b5477f15f11a7bb8ca66b5844a5e73b20134d219f207df72d4f74ad8676269f"
_COMPOSED = "f0774e0e80519692ad9da7b645460433b14981e6e3ec1f0ce0591042a8a607b2"
_DESCRIPTION = "20f3ba4d3a8e8a19967fa566c59a04021d35f2bdeb49fa5095b70bed6fa24cec"
_RUNTIME = "fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d"
_METHOD = "dspexpr_02_perform"
_KERNEL = "8001ff87c2031bf71367aa0bc4a6e68b815c3e67e30d87b602672e507c5262f4"
_PREPARED_KERNEL = "aba30b163cc98dfc2f5c3c8c7381a3762da141c7e4ecb8e9a66cbe67c4b5e40c"
_WRAP_SUPPORT = {
    "private_finite_wrap.h": "5120c1152ed007ac389bef310ac6e83fd6b32c3be9862d9c6615a365f30492fd",
    "rnbo_s3_finite_wrap_source.h": "863a960afe421dd3fe9e45485750046ba3d613410647d838853e79f4eb24efe0",
}
_CONTRACT_NAME = "rnbo_s3_scalar_powers_source.h"
_CONTRACT = b'''/* SPDX-License-Identifier: MIT */
#pragma once
#include <float.h>
#include "rnbo_source.h"
#if FLT_RADIX != 2 || FLT_MANT_DIG != 24 || FLT_MAX_EXP != 128
#error "Scalar power profile requires binary32 float"
#endif
static_assert(sizeof(float) == 4 && sizeof(RNBO::number) == 4 &&
              sizeof(RNBO::Sample) == 4 && sizeof(RNBO::SampleValue) == 4,
              "Scalar power profile requires binary32 RNBO samples");
'''
# Original MIT-authored specialisation, byte-identical to the reviewed private
# experiment. The historical source comment is retained for that identity.
_BODY = '''{
    RNBO_UNUSED(n);
    // PRIVATE experiment: one scalar dispatch per vector; Float32 arithmetic.
    if (in2 == 2.0f) {
        for (Index i = 0; i < 256; ++i) {
            number x = in1[i];
            out1[i] = fixnan(x * x);
        }
    } else if (in2 == 4.0f) {
        for (Index i = 0; i < 256; ++i) {
            number x = in1[i];
            number square = x * x;
            out1[i] = fixnan(square * square);
        }
    } else if (in2 == 0.25f) {
        for (Index i = 0; i < 256; ++i) {
            out1[i] = fixnan(rnbo_sqrt(rnbo_sqrt(in1[i])));
        }
    } else {
        for (Index i = 0; i < 256; ++i) {
            out1[(Index)i] = fixnan(rnbo_pow(in1[(Index)i], in2));
        }
    }
}'''


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def scalar_powers(files: dict[str, bytes], description: dict, *, code_mask,
                  finite_wrap_corrected: bool = False) -> tuple[dict[str, bytes], dict]:
    """Apply only the exact reviewed power kernel; return a new map atomically.

    Local bases are clip outputs in[0,1]. Raw whole-graph inputs retain the
    qualification's bounded finite contract; nonfinite/fenv/general pow modes
    are not admitted by this profile. Finite-wrap must run before this helper.
    """
    if not isinstance(files, dict) or any(not isinstance(k, str) or not isinstance(v, bytes)
                                          for k, v in files.items()):
        raise ValueError("scalar powers: expected immutable byte files")
    if type(finite_wrap_corrected) is not bool:
        raise ValueError("scalar powers: correction composition must be a boolean")
    source = files.get("rnbo_source.h")
    expected = _WRAPPED if finite_wrap_corrected else _SOURCE
    if source is None or _sha(source) != expected:
        raise ValueError("scalar powers: unsupported, partial or already transformed nonlinear context")
    if _CONTRACT_NAME in files:
        raise ValueError("scalar powers: compile-contract collision or repeated application")
    for name, fingerprint in _WRAP_SUPPORT.items():
        if finite_wrap_corrected:
            if name not in files or _sha(files[name]) != fingerprint:
                raise ValueError("scalar powers: unreviewed finite-wrap support/compilation context")
        elif name in files:
            raise ValueError("scalar powers: unexpected partial finite-wrap composition")
    stored = files.get("description.json")
    if stored is None or _sha(stored) != _DESCRIPTION:
        raise ValueError("scalar powers: unreviewed authored description bytes")
    try:
        equal = isinstance(description, dict) and _canonical(description) == _canonical(json.loads(stored))
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("scalar powers: invalid authored description") from exc
    if not equal:
        raise ValueError("scalar powers: description does not match the pinned source context")
    runtime = {name: _sha(data) for name, data in sorted(files.items()) if name.startswith("common/")}
    if _sha(_canonical(runtime)) != _RUNTIME:
        raise ValueError("scalar powers: unreviewed runtime/version/types; normal fixes must precede specialisation")
    text = source.decode()
    masked = code_mask(text)
    if not isinstance(masked, str) or len(masked) != len(text):
        raise ValueError("scalar powers: invalid C++ lexical mask")
    start, stop = _method(masked, _METHOD)
    old = text[start:stop]
    if _sha(re.sub(r"\s+", "", masked[start:stop]).encode()) != _KERNEL:
        raise ValueError("scalar powers: unknown pow kernel, input form, width or loop")
    new = old[:old.index("{")] + _BODY
    if _sha(re.sub(r"\s+", "", code_mask(new)).encode()) != _PREPARED_KERNEL:
        raise ValueError("scalar powers: prepared kernel differs from the reviewed specialisation")
    changed = text[:start] + new + text[stop:]
    expected_output = _COMPOSED if finite_wrap_corrected else _OUTPUT
    if _sha(changed.encode()) != expected_output or changed.replace(new, old) != text or changed.count(new) != 1:
        raise ValueError("scalar powers: transformed source or full inverse differs")
    updated = dict(files)
    updated.update({"rnbo_source.h": changed.encode(), _CONTRACT_NAME: _CONTRACT})
    return updated, {
        "name": "rnbo-1.4.4-float32-scalar-powers-v1", "file": "rnbo_source.h", "method": _METHOD,
        "input_sha256": _sha(source), "prepared_sha256": _sha(changed.encode()),
        "description_file_sha256": _DESCRIPTION, "runtime_tree_sha256": _RUNTIME,
        "kernel_sha256": _KERNEL, "prepared_kernel_sha256": _PREPARED_KERNEL,
        "input_method_sha256": _sha(old.encode()), "prepared_method_sha256": _sha(new.encode()),
        "inverse_byte_identity": True, "finite_wrap_composition": finite_wrap_corrected,
        "special_exponents": [2, 4, 0.25], "dispatch": "exact Float32 scalar equality once per256-frame vector",
        "fallback": "original fixnan(rnbo_pow(input,exponent)) for every other scalar exponent",
        "base_domain": "authored clip output[0,1]; not arbitrary pow inputs",
        "graph_qualification_domain": "bounded finite stereo inputs; original nonlinear-grid left[-4,4],right[-3,3]",
        "numerical_identity": "changed-rounding Float32 products/nested sqrt; bit, signed-zero and fenv identity not claimed",
        "bit_identity_claimed": False, "floating_exception_identity_claimed": False,
        "original_fixnan_retained": True,
        "unchanged": "original fixnan on every output, state, clocks, buffers and other processing methods",
        "historical_private_comment_retained": True,
        "compile_contract_file": _CONTRACT_NAME, "compile_contract_sha256": _sha(_CONTRACT),
        "transformer_sha256": _sha(Path(__file__).read_bytes()),
        "evidence": "evidence/nonlinear-powers.json", "composed_target_qualified": False}
