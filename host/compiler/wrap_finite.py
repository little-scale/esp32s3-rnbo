# SPDX-License-Identifier: MIT
"""Default-off, closed-context finite binary32 wrap[-1,1) correction.

The original method is retained below magnitude2**24. Above that threshold,
every finite binary32 value is an even integer, whose exact wrapped result is
+0. Unknown source/range/type/runtime forms fail closed. No generated RNBO
algorithm is stored here: complete contexts and methods are SHA256-pinned.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from bounded_filters import _method

_RUNTIME = "fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d"
_KERNEL = "e80fcaaeb2919f8ada1b07b18a923e130ae34759a3e0319a9174df6324def92f"
_HELPER = "5120c1152ed007ac389bef310ac6e83fd6b32c3be9862d9c6615a365f30492fd"
_CONTEXTS = {
    "b246e2357fc3829af9d44eec0efc1aa69a82bd9157be093663005ea0eb1ea28b": {
        "id": "nonlinear-domains",
        "description_sha256": "20f3ba4d3a8e8a19967fa566c59a04021d35f2bdeb49fa5095b70bed6fa24cec",
        "output_sha256": "cb3034efc572a29b2d3e9cc82e733035a12b6907b6213c9c3af9ee01ab64cbfd",
        "methods": ("wrap_tilde_01_perform",),
    },
    "1c00c62a40e1c950b66f3b1c887533feb1ce7525dc384a5eb2bee87ef006a4da": {
        "id": "wrap-finite-stereo",
        "description_sha256": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
        "output_sha256": "50e01c6d9b2a854ff872b6ccbaf1c9e5077975ae36cc959d0bd1d20c69516110",
        "methods": ("wrap_tilde_01_perform", "wrap_tilde_02_perform"),
    },
}
_INCLUDE_ANCHOR = '#include RNBO_LIB_INCLUDE(RNBO_AudioSignal.h)\n'
_INCLUDE = '#include "private_finite_wrap.h"\n'
_ANCHOR = "        if (range <= 0.000000001) {"
_GUARD = ("        float repaired;\n"
          "        if (private_wrap_even_large(x[(Index)i], &repaired)) {\n"
          "            out1[(Index)i] = repaired;\n"
          "            continue;\n"
          "        }\n\n")
_CONTRACT_NAME = "rnbo_s3_finite_wrap_source.h"
_CONTRACT = b'''/* SPDX-License-Identifier: MIT */
/* Compile-time width contract; no generated processing instructions. */
#pragma once
#include "rnbo_source.h"
static_assert(sizeof(float) == 4 && sizeof(RNBO::number) == 4 &&
              sizeof(RNBO::Sample) == 4 && sizeof(RNBO::SampleValue) == 4,
              "Finite wrap correction requires binary32 RNBO samples");
'''


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True,
                       allow_nan=False) + "\n").encode()


def correct_finite_wrap(files: dict[str, bytes], description: dict, *, code_mask) -> tuple[dict[str, bytes], dict]:
    """Insert only the proven even24 guard in two exact authored FX contexts.

    Must run after the normal RNBO1.4.4 runtime/defined-integer fixes. Both full
    headers, the original description, the whole runtime inventory and every
    wrap method are pinned. The new source include enforces binary32 even when
    manually compiling a prepared export. Caller-owned input is never mutated.
    """
    if not isinstance(files, dict) or any(not isinstance(k, str) or not isinstance(v, bytes)
                                          for k, v in files.items()):
        raise ValueError("finite wrap: expected immutable byte files")
    source = files.get("rnbo_source.h")
    context = _CONTEXTS.get(_sha(source)) if source is not None else None
    if context is None:
        raise ValueError("finite wrap: unknown, partial or already transformed authored context")
    for name in ("private_finite_wrap.h", _CONTRACT_NAME):
        if name in files:
            raise ValueError("finite wrap: helper/include collision or repeated application")
    stored = files.get("description.json")
    if stored is None or _sha(stored) != context["description_sha256"]:
        raise ValueError("finite wrap: unreviewed authored description bytes")
    try:
        matches = isinstance(description, dict) and _canonical(description) == _canonical(json.loads(stored))
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("finite wrap: invalid authored description") from exc
    if not matches:
        raise ValueError("finite wrap: description does not match the pinned source context")
    runtime = {name: _sha(data) for name, data in sorted(files.items()) if name.startswith("common/")}
    if _sha(_canonical(runtime)) != _RUNTIME:
        raise ValueError("finite wrap: unreviewed runtime/version/types; normal fixes must precede correction")
    helper = Path(__file__).with_suffix(".h").read_bytes()
    if _sha(helper) != _HELPER:
        raise ValueError("finite wrap: helper differs from the proven even24 implementation")
    text = source.decode()
    masked = code_mask(text)
    if not isinstance(masked, str) or len(masked) != len(text):
        raise ValueError("finite wrap: invalid C++ lexical mask")
    names = re.findall(r"\bvoid\s+(wrap_[A-Za-z0-9_]+_perform)\s*\(", masked)
    if tuple(names) != context["methods"]:
        raise ValueError("finite wrap: unexpected or duplicate generated wrap methods")
    replacements = []
    records = []
    for name in names:
        start, stop = _method(masked, name)
        body = text[start:stop]
        fingerprint = _sha(re.sub(r"\s+", "", masked[start:stop].replace(name, "wrap_tilde_01_perform")).encode())
        if fingerprint != _KERNEL:
            raise ValueError("finite wrap: unsupported range, width, loop or kernel form")
        if body.count(_ANCHOR) != 1 or masked[start:stop].count(_ANCHOR.strip()) != 1:
            raise ValueError("finite wrap: missing unique reviewed code anchor")
        changed = body.replace(_ANCHOR, _GUARD + _ANCHOR)
        if changed.replace(_GUARD, "") != body:
            raise ValueError("finite wrap: method inverse differs")
        replacements.append((start, stop, changed))
        records.append({"method": name, "kernel_sha256": fingerprint,
                        "input_method_sha256": _sha(body.encode()),
                        "prepared_method_sha256": _sha(changed.encode()),
                        "guard_count": 1})
    if text.count(_INCLUDE_ANCHOR) != 1:
        raise ValueError("finite wrap: missing unique reviewed runtime include")
    for start, stop, changed in reversed(replacements):
        text = text[:start] + changed + text[stop:]
    text = text.replace(_INCLUDE_ANCHOR, _INCLUDE_ANCHOR + _INCLUDE)
    prepared = text.encode()
    if _sha(prepared) != context["output_sha256"] or text.replace(_GUARD, "").replace(_INCLUDE, "") != source.decode():
        raise ValueError("finite wrap: transformed source or full inverse differs")
    updated = dict(files)
    updated.update({"rnbo_source.h": prepared, "private_finite_wrap.h": helper, _CONTRACT_NAME: _CONTRACT})
    return updated, {
        "name": "rnbo-1.4.4-finite-wrap-even24-v1", "file": "rnbo_source.h",
        "context": context["id"], "input_sha256": _sha(source), "prepared_sha256": _sha(prepared),
        "description_file_sha256": context["description_sha256"], "runtime_tree_sha256": _RUNTIME,
        "helper_file": "private_finite_wrap.h", "helper_sha256": _HELPER,
        "compile_contract_file": _CONTRACT_NAME, "compile_contract_sha256": _sha(_CONTRACT),
        "transformer_sha256": _sha(Path(__file__).read_bytes()), "methods": records,
        "guard_count": len(records), "inverse_byte_identity": True,
        "input_contract": "finite binary32 samples; fixed wrap[-1,1), 256 frames, RNBO1.4.4",
        "correction": "finite |x|>=2^24 is an even integer; return exact +0 before Int conversion",
        "unchanged": "all original branches/arithmetic below2^24 including input -0; all clocks, state, types and other objects",
        "nonfinite_policy": "NaN/Inf bypass the guard; upstream route remains unqualified and may have undefined conversions",
        "numerical_profile_unchanged": True, "evidence": "evidence/wrap-finite.json",
        "target_qualified": False, "cpu_gain_claimed": False}
