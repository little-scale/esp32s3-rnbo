# SPDX-License-Identifier: MIT
"""Explicit float32 DSP profiles guarded by whole RNBO1.4.4 method hashes.

Only reviewed audio methods are admitted. No generated algorithm is vendored;
the fingerprints normalize whitespace/comments and generated object prefixes.
Explicit profiles reject unknown forms and changed constants. Auto preserves
unknown matched methods byte for byte and reports why they were skipped.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

from bounded_filters import _method

# A separate, closed signal-only experiment. Earlier profiles and Auto do not
# inherit this kernel or its changed integer-base overload selection.
DBTOA_PROFILE = "float32-dbtoa-v1"
DBTOA_KERNEL = "ca7d30389cd8b2110fa2b3dc9f021d4718f1c5021a1c548a34e25f1ad8ec7c5b"
DBTOA_SOURCE = "36e3b6f7cfc220ff98783591bf65164aaad2661a01858409f07e331ca0d18b22"
DBTOA_INPUT_MAPS = frozenset({
    "95657ed75688f991900f420882961b7deae9522d21e0062e67aedfcab3f03657",  # original producer
    "75c2085d7b91b4b798507d87bbc6f271cd23b26e556095b0c0f5a4887780fb37",  # integer-UI producer
})
DBTOA_CONTRACT_FILE = "rnbo_s3_dbtoa_source.h"
DBTOA_CONTRACT = b'''/* SPDX-License-Identifier: MIT */
#pragma once
#include <float.h>
#include <type_traits>
#include "rnbo_source.h"
#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__)
#error "Float32 dbtoa requires strict floating arithmetic"
#endif
#if defined(RNBO_USE_APPROXIMATE_MATH) && RNBO_USE_APPROXIMATE_MATH
#error "Float32 dbtoa requires standard powf, not approximate math"
#endif
#if !defined(RNBO_S3_ABI_MAJOR) || !defined(RNBO_S3_ABI_MINOR) || RNBO_S3_ABI_MAJOR != 1u || RNBO_S3_ABI_MINOR != 0u
#error "Float32 dbtoa requires reviewed ABI 1.0"
#endif
static_assert(FLT_RADIX==2 && FLT_MANT_DIG==24 && FLT_MAX_EXP==128 &&
              FLT_EVAL_METHOD==0 && sizeof(float)==4,
              "dbtoa requires binary32 without excess evaluation precision");
static_assert(std::is_same<RNBO::number,float>::value &&
              std::is_same<RNBO::Sample,float>::value &&
              std::is_same<RNBO::SampleValue,float>::value &&
              std::is_same<decltype(RNBO::SampleValue{} * 0.05f),float>::value &&
              std::is_same<decltype(RNBO_Math::rnbo_pow(10.0f, RNBO::SampleValue{} * 0.05f)),float>::value,
              "dbtoa input, exponent product and output must remain Float32");
static_assert(std::is_same<RNBO::MillisecondTime,double>::value && sizeof(double)==8 &&
              DBL_MANT_DIG==53 && DBL_MAX_EXP==1024,
              "dbtoa does not narrow the binary64 scheduler clock");
'''
DBTOA_MANIFEST_CONTRACT = {
    "version": 1, "context": "dbtoa-signal", "input_domain_db": [-24, 6],
    "mathematical_reference": "10^(input/20)", "absolute_error_limit": 2e-6,
    "operation": "powf(10.0f, binary32(input * 0.05f))",
    "rounding": "nearest-even", "audio": "binary32", "scheduler_time": "unchanged-binary64",
    "build_requirements": ["no-fast-math", "no-excess-evaluation-precision", "fp-contract-off", "standard-math"],
    "state_layout_and_callers": "unchanged", "math_runtime": "unchanged",
    "bit_identity_claimed": False, "nonfinite_qualified": False,
    "floating_environment_equivalence_claimed": False,
    "errno_identity_claimed": False, "floating_trap_identity_claimed": False,
}


def _float32_dbtoa(source: bytes, *, code_mask) -> tuple[bytes, dict]:
    text = source.decode(); masked = code_mask(text)
    if type(masked) is not str or len(masked) != len(text):
        raise ValueError("float32-dbtoa-v1: invalid lexical mask")
    names = re.findall(r"\bvoid\s+(dspexpr_\d+_perform)\s*\(", masked)
    if not names or len(names) != len(set(names)):
        raise ValueError("float32-dbtoa-v1: no unique signal audio methods found")
    edits = []; methods = []
    for name in names:
        start, end = _method(masked, name)
        prefix = name.rsplit("_", 1)[0]
        fingerprint = hashlib.sha256(re.sub(r"\s+", "", masked[start:end]).replace(prefix, "OBJECT").encode()).hexdigest()
        if fingerprint != DBTOA_KERNEL:
            raise ValueError(f"float32-dbtoa-v1: unsupported RNBO1.4.4 signal method {name} ({fingerprint})")
        calls = list(re.finditer(r"\brnbo_pow\s*\(\s*(10)\s*,\s*in1\s*\[\s*\(\s*Index\s*\)\s*i\s*\]\s*\*\s*(0\.05)\s*\)", masked[start:end]))
        if len(calls) != 1:
            raise ValueError("float32-dbtoa-v1: expected one reviewed local pow call")
        for group, replacement in ((1, "10.0f"), (2, "0.05f")):
            a, b = calls[0].span(group)
            edits.append({"method": name, "input_span": [start + a, start + b],
                          "before": text[start + a:start + b], "after": replacement})
        methods.append({"method": name, "kernel_sha256": fingerprint, "literal_replacements": 2})
    offset = 0
    for edit in sorted(edits, key=lambda x: x["input_span"]):
        a, b = edit["input_span"]
        edit["prepared_span"] = [a + offset, a + offset + len(edit["after"])]
        offset += len(edit["after"]) - (b - a)
    result = text
    for edit in sorted(edits, key=lambda x: x["input_span"], reverse=True):
        a, b = edit["input_span"]; result = result[:a] + edit["after"] + result[b:]
    inverse = result
    for edit in sorted(edits, key=lambda x: x["prepared_span"], reverse=True):
        a, b = edit["prepared_span"]
        if inverse[a:b] != edit["after"]:
            raise ValueError("float32-dbtoa-v1: literal inverse differs")
        inverse = inverse[:a] + edit["before"] + inverse[b:]
    if inverse.encode() != source:
        raise ValueError("float32-dbtoa-v1: whole-source inverse differs")
    prepared = result.encode()
    return prepared, {"name": "rnbo-1.4.4-float32-dbtoa-v1", "file": "rnbo_source.h",
                      "input_sha256": hashlib.sha256(source).hexdigest(),
                      "prepared_sha256": hashlib.sha256(prepared).hexdigest(),
                      "transformer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "methods": methods, "literal_replacement_count": len(edits), "edits": edits,
                      "whole_source_inverse_verified": True,
                      "unchanged": "all bytes outside declared literal spans, shared runtime, scheduler, setup, state and callers",
                      "numerical_change": "Float32 exponent product and powf overload; changed rounding, not bit identity"}


def prepare_dbtoa(files: dict[str, bytes], description: dict, *, code_mask) -> tuple[dict[str, bytes], dict]:
    """Late pure-map admission after baseline config, before prepared hashes."""
    if type(files) is not dict or not all(type(k) is str and type(v) is bytes for k, v in files.items()):
        raise ValueError("float32-dbtoa-v1: immutable source map required")
    canonical = lambda value: (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()
    input_map = hashlib.sha256(canonical({k: hashlib.sha256(v).hexdigest() for k, v in files.items()})).hexdigest()
    if len(files) != 42 or input_map not in DBTOA_INPUT_MAPS:
        raise ValueError("float32-dbtoa-v1: unknown graph/runtime/config/metadata composition or repeated application")
    if type(description) is not dict or canonical(description) != canonical(json.loads(files["description.json"])):
        raise ValueError("float32-dbtoa-v1: description object differs")
    if hashlib.sha256(files["rnbo_source.h"]).hexdigest() != DBTOA_SOURCE:
        raise ValueError("float32-dbtoa-v1: source identity differs")
    source, record = _float32_dbtoa(files["rnbo_source.h"], code_mask=code_mask)
    result = dict(files)
    result["rnbo_source.h"] = source
    result[DBTOA_CONTRACT_FILE] = DBTOA_CONTRACT
    result["patch_config.h"] += ('#define RNBO_S3_PATCH_SOURCE "' + DBTOA_CONTRACT_FILE + '"\n').encode()
    record.update({"input_map_sha256": input_map, "compile_contract_file": DBTOA_CONTRACT_FILE,
                   "compile_contract_sha256": hashlib.sha256(DBTOA_CONTRACT).hexdigest(),
                   "prepared_config_sha256": hashlib.sha256(result["patch_config.h"]).hexdigest()})
    return result, record

_CYCLE = {
    "0b43f9b8b1e43065f1edaae72d9c83b444a9addd54c34745881ec955d13c5d39",  # fixed .009, phase inlet
    "9664ab9b4048a80f806601c2c47332b5177cb038ac1970da326b912f94ff7c1e",  # scalar frequency
    "35431559caa75217b2fcc8a6c62ad15d3306b88e198ba6412814bc354e56d9be",  # fixed .01
    "c03a2b0162de919fabb245f42f427d24da87c7afa21113ee0fecb70beec03649",  # signal frequency + phase
}
_CATALOG = {
    "cycle": _CYCLE,
    "saw": {"8f6e83a5cdc54fa1b755f1e30a341644af59d0a8d9e45b354feb669c574314f2"},
    "scale": {"07c50af7beca4709d863705e4cca5446bfb8a0d3b8f6c974de4f54f1a93dd272",
              "2d709eaed24130238c97a53777c9329c1a218899e965acad1064e03802833c4a",
              "2d4d55dd2e41e45f155e82a213c682e5a0ede2ee651c4bfbbaa0824f53ad0a21",
              "b817b5552906a7b01e5f624080d1a2aeac866e398b563fc7ed2eebda893db2b0"},
    "dspexpr": {"201ee75fcef187bd4e4a726197f8c3982e2823344e374e31e7826c2e0f8432a3",
                "ff25154a18e82c125b1a51bbb0d35d33cc104f65feddbb2c639d54bc858f510b",
                "42fc51b6488adfc7c4cd54fcacedb8cfb13864acee80788f016c662b43baa328"},
    "reson": {"aefdb1ab746759d7a4e6bf56110e76d8194510b94870d7564a2a533a36a303ae"},
    "comb": {"f76ae14182d9f916b568cb798ef585267048e8836a336764313fc89db185e725"},  # explicit cap40
    "delaytilde": {"4ecf0037625fdf1d4ba7a2b98145776b732933dac0e1754c74b878476f75c0f8"},
    "mtof": {"2f8791609dc4d4cdfaa6553c95b9ce0a1df62b44170a98135b923a863c979d94"},
}
# Keep v1's admission contract fixed. V2 adds independently reviewed scalar
# phase, bounded comb/allpass, and arithmetic forms from the object fixtures.
_CATALOG_V2 = {kind: set(forms) for kind, forms in _CATALOG.items()}
_CATALOG_V2["cycle"].add("1dbcc6178f4628491e85c1a2c54289819d118cd5ff26ab44fda7acefe8390cc5")
_CATALOG_V2["comb"].update({
    "c4b12e4afc5e96e32aa8f6d95eea1dd1d51aca5eb22e8649c89d3cec84ef4542",
    "9d75ec01d3f3ab5473e7ef87c4973dc9d899d40b4a7101d83a56758f2fe9e348",
    "47fd9c5b7b393e5deae3dde5408dac3986502ae5ef20a9a28b26d1e581243166",
})
_CATALOG_V2["allpass"] = {
    "be98f0a867d8027e45f9448b1c1e35abd8ac9193b28f66f4beea1d43ed8388fc",
    "40937256b1dd5e79b82582326fcae8938839c2d73edc13d2b50098ae931878b0",
    "07d2fb4ef43c20463acf1c3ebfb6735dd30a2f10756243fa94b17e9df1162ef8",
}
_CATALOG_V2["dspexpr"].update({
    "b49df46a014c8593fbf091762f70754a8849a4e261d3afbcaf7df01a42ce2e73",
    "c635d90b32a2b751d534a876cffa2598133f384ad0fcb6f8eec2927ba2db9848",
})
_PREFIX = r"(?:(?:cycle|saw|scale|reson|comb|allpass|mtof)_tilde_\d+|dspexpr_\d+|delaytilde_\d+)"
_METHOD_NAME = r"(?:(?:(?:cycle|saw|scale|reson|comb|allpass)_tilde_\d+|dspexpr_\d+|delaytilde_\d+)_perform|mtof_tilde_\d+_innerMtoF_next)"
# V3 retains both earlier catalogs and adds the exact fixed-frequency, linear
# scale, arithmetic, fixed-sample delay and lores forms reviewed in DDD. It does
# not change fixed frequencies, integer phase algorithms or filter/ring state.
_CATALOG_V3 = {kind: set(forms) for kind, forms in _CATALOG_V2.items()}
_CATALOG_V3['cycle'].update({
    'ca7240e5a82e96a66a48d11fecb975a15b594b726f96677ee6572883ad85971f',  # fixed 5 Hz
    'f08d07541d1248dedfe3bea986935331c52865d321c460f3b1050cc0836dbc9b',  # fixed 2 Hz
    '129c1044e662cf1e0ee329a7c5cb160abaec1800412d96b9a25ca6ea50f29afb',  # fixed .1 Hz
})
_CATALOG_V3['scale'].add('dc897def72abf2ae3662be09ae51cb94085a6ccd0475c6e2dffc9b93a6edf2a6')
_CATALOG_V3['dspexpr'].update({
    '0496b831c6b7e30aea7f8f145566dbd19a9848d7683938fc0dd4862a8a4d14b5',  # multiply .1
    '8c544b76552adf8544729f45ee47d61bf563a1acc13fd41471b5a780809369fc',  # multiply .99
    '9d5831719ef9b892de40dff825c8ecf2db952f850247210d497a0900f9a81268',  # multiply .7
})
_CATALOG_V3['delaytilde'].add('b25310abd87976d8cb7e2b5581a22a169b5912bee5ddf172ebf45f74279b4929')
_CATALOG_V3['lores'] = {
    'd7645d579512b7447249b713b998a86cd1c28e720d0f5d7dda8f982a58ebcf48',
    # Signal cutoff, fixed resonance .9 (EEE). Same recurrence and Float32
    # state as the reviewed zero-resonance method; retain a separate whole-
    # method fingerprint so other resonance values/algorithms still skip.
    '85d6f0eb56e7e2f1450d1d10605e2f98f8d5f5ebb2acc9af93743fd6798f519f',
}
_PREFIX_V3 = rf"(?:{_PREFIX}|lores_\d+)"
_METHOD_NAME_V3 = rf"(?:{_METHOD_NAME}|lores_\d+_perform)"
# C++ decimal floating tokens, excluding integer, hexadecimal and suffixed
# tokens. Applying this only within a full-method hash is intentional.
_DECIMAL = re.compile(r"(?<![\w.])(?:(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)(?![\w.])")


def float32_audio(source: bytes, *, code_mask, profile: str) -> tuple[bytes, dict]:
    if profile == DBTOA_PROFILE:
        return _float32_dbtoa(source, code_mask=code_mask)
    if profile not in ("float32-cycle-v2", "float32-audio-v1", "float32-audio-v2", "float32-audio-v3", "float32-auto-v1"):
        raise ValueError("Unsupported float32 audio profile")
    automatic = profile == "float32-auto-v1"
    uses_v3 = automatic or profile == "float32-audio-v3"
    catalog = _CATALOG_V3 if uses_v3 else _CATALOG_V2 if profile == "float32-audio-v2" else _CATALOG
    text = source.decode(); masked = code_mask(text)
    replacements = []; methods = []; skipped = []
    methods_pattern = _METHOD_NAME_V3 if uses_v3 else _METHOD_NAME
    pattern = r"\b(?:void|number)\s+(" + (methods_pattern if automatic or profile.startswith("float32-audio-") else r"cycle_[A-Za-z0-9_]+_perform") + r")\s*\("
    names = re.findall(pattern, masked)
    if (not names and not automatic) or len(names) != len(set(names)):
        raise ValueError(f"{profile}: no unique supported audio methods found")
    for name in names:
        prefix = re.match(_PREFIX_V3 if uses_v3 else _PREFIX, name)
        if not prefix:
            raise ValueError(f"{profile}: unsupported generated name {name}")
        prefix = prefix[0]; kind = prefix.split("_", 1)[0]
        start, end = _method(masked, name)
        body = masked[start:end]
        normalized = re.sub(r"\s+", "", body).replace(prefix, "OBJECT")
        fingerprint = hashlib.sha256(normalized.encode()).hexdigest()
        if fingerprint not in catalog.get(kind, set()):
            if automatic:
                skipped.append({"method": name, "kernel_sha256": fingerprint,
                                "reason": "unreviewed-method-fingerprint"})
                continue
            raise ValueError(f"{profile}: unsupported RNBO1.4.4 audio method {name} ({fingerprint})")
        edits = []
        for token in _DECIMAL.finditer(body):
            edits.append({"literal": token[0], "replacement": token[0] + "f"})
            replacements.append((start + token.end(), start + token.end(), "f"))
        conversions = 0
        # Newly admitted feedback-filter forms retain the original double
        # duration conversion: a float intermediate moved fractional echoes
        # beyond the fixtures' strict output limits. Preserve v1's existing
        # explicit opt-in behavior for its previously qualified comb form.
        if kind in ("comb", "allpass") and fingerprint in _CATALOG.get(kind, set()):
            # This is the audio ring's local conversion only. Leave the shared
            # mstosamps(MillisecondTime) helper and all scheduler callers alone.
            for call in re.finditer(r"this->mstosamps\s*\(", body):
                opening = call.end() - 1; cursor = opening + 1; depth = 1
                while cursor < len(body) and depth:
                    if body[cursor] == "(": depth += 1
                    elif body[cursor] == ")": depth -= 1
                    cursor += 1
                if depth: raise ValueError(f"{profile}: malformed audio conversion {name}")
                replacements.append((start + call.start(), start + opening + 1, "((number)("))
                replacements.append((start + cursor - 1, start + cursor, ") * this->sr * 0.001f)"))
                conversions += 1
            if conversions != 1:
                raise ValueError(f"{profile}: expected one local audio delay conversion in {name}")
        methods.append({"method": name, "kernel_sha256": fingerprint,
                        "literal_changes": edits, "local_float32_ms_to_samples": conversions,
                        "retained_double_ms_to_samples": kind in ("comb", "allpass") and not conversions})
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    prepared = text.encode()
    report = {"name": "rnbo-1.4.4-" + profile, "file": "rnbo_source.h",
                      "input_sha256": hashlib.sha256(source).hexdigest(),
                      "prepared_sha256": hashlib.sha256(prepared).hexdigest(),
                      "transformer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "methods": methods, "literal_suffix_count": sum(len(m["literal_changes"]) for m in methods),
                      "unchanged": "integer phase/truncation algorithms, ring interpolation, scheduler methods, double time and frame counters",
                      "numerical_change": "Audio expression rounding and expf overload selection; not a bit-identity profile"}
    if automatic:
        report.update({"matched_method_count": len(names), "eligible_method_count": len(methods),
                       "known_method_count": len(methods), "skipped_method_count": len(skipped),
                       "skipped_methods": skipped, "source_changed": prepared != source,
                       "all_double_removed_claimed": False})
    return prepared, report
