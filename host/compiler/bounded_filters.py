# SPDX-License-Identifier: MIT
"""Opt-in RNBO1.4.4 comb/allpass capacity cap, retaining double ring storage.

This is an explicit change to supported delay ranges. It neither infers graph
bounds nor changes RNBO's millisecond conversion, interpolation, or precision.
"""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
import re

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?[fF]?"
_KERNELS = {
    "comb": "5600c4574dfcccba3ba06c4167b567be8a9fcaab10e8b5e6d349300effc49684",
    "allpass": "5c0cf5f957d605a73890d2ec9ec190a1aca06807ca1e3f471a8b7b9f4ef3eccf",
}
_BUFFER_METHODS = {
    "calcSizeInSamples": "67244cc8661bd672d1f76684596d103f35502914b69dcf41064e828de120b192",
    "init": "0ace37d70c73b2b13302608a573cd053a040ec50effaa817629b14ac797726c5",
    "reset": "a1b668961166379e1b5a81583ce488689224cae68224ac5426393a0014a113cb",
}


def _method(masked: str, name: str) -> tuple[int, int]:
    matches = list(re.finditer(r"\b(?:void|number|array\s*<\s*Index\s*,\s*2\s*>)\s+" + re.escape(name) + r"\s*\([^{};]*\)\s*\{", masked))
    if len(matches) != 1:
        raise ValueError(f"bounded filters: expected one generated method {name}")
    match = matches[0]
    cursor = match.end(); depth = 1
    while cursor < len(masked) and depth:
        if masked[cursor] == "{": depth += 1
        elif masked[cursor] == "}": depth -= 1
        cursor += 1
    if depth:
        raise ValueError(f"bounded filters: unterminated generated method {name}")
    return match.start(), cursor


def _kernel_fingerprint(body: str, name: str) -> str:
    """Normalize only generated names and source-controlled scalar arguments.

    Full remaining algorithm/signature must match a reviewed generated kernel.
    Arbitrary expressions are not accepted as scalar or signal input forms.
    """
    kind = name.split("_", 1)[0]
    compact = re.sub(r"\s+", "", body).replace(name, "FILTER")
    compact = re.sub(r"RNBO_UNUSED\((?:n|delayTime|gain|ffGain|fbGain)\);", "", compact)
    for parameter in ("delayTime", "gain", "ffGain", "fbGain"):
        compact = compact.replace(f"constSample*RNBO_RESTRICT{parameter}", f"number{parameter}")
        value = rf"(?:{_NUMBER}|{parameter}(?:\[\(Index\)i\])?)"
        if parameter != "delayTime" or kind == "comb":
            compact = re.sub(rf"(number__{parameter}=){value};", rf"\1SOURCE;", compact)
    if kind == "allpass":
        value = rf"(?:{_NUMBER}|delayTime(?:\[\(Index\)i\])?)"
        compact = re.sub(rf"this->mstosamps\({value}\)", "this->mstosamps(SOURCE)", compact)
    return hashlib.sha256(compact.encode()).hexdigest()


def bound_filter_delays(source: bytes, maximum_ms: float, *, code_mask) -> tuple[bytes, dict]:
    if type(maximum_ms) not in (int, float) or not math.isfinite(maximum_ms) or not 0 < maximum_ms <= 1000:
        raise ValueError("filter-delay-max-ms must be positive, finite, and at most1000")
    text = source.decode(); masked = code_mask(text)
    names = re.findall(r"\bvoid\s+((?:comb|allpass)_tilde_\d+)_perform\s*\(", masked)
    if not names or len(set(names)) != len(names):
        raise ValueError("bounded filters: no unique supported comb/allpass kernels were found")
    # Two additional samples cover conversion and fractional interpolation before
    # retaining the generated nextpoweroftwo allocation path.
    maximum_samples = math.ceil(maximum_ms * 44.1) + 2
    frames = 1 << (maximum_samples - 1).bit_length()
    cap = format(float(maximum_ms), ".17g")
    if "." not in cap and "e" not in cap: cap += ".0"
    changes = []; replacements = []
    for name in names:
        kind = name.split("_", 1)[0]
        start, end = _method(masked, name + "_perform")
        body = masked[start:end]
        fingerprint = _kernel_fingerprint(body, name)
        if fingerprint != _KERNELS[kind]:
            raise ValueError(f"bounded filters: unsupported RNBO1.4.4 {name} kernel ({fingerprint})")
        if kind == "comb":
            conversions = list(re.finditer(r"this->mstosamps\(\s*(__delayTime)\s*\)", body))
        else:
            value = rf"(?:{_NUMBER}|delayTime(?:\s*\[\s*\(Index\)\s*i\s*\])?)"
            conversions = list(re.finditer(rf"this->mstosamps\(\s*({value})\s*\)", body))
        if len(conversions) != 1 or len(re.findall(r"\bmstosamps\s*\(", body)) != 1:
            raise ValueError(f"bounded filters: changed delay conversion in {name}")
        conversion = conversions[0]
        argument_start, argument_end = start + conversion.start(1), start + conversion.end(1)
        argument = text[argument_start:argument_end]
        replacements.append((argument_start, argument_end, f"({argument} > {cap} ? {cap} : {argument})"))
        buffers = []
        for side in ("feedForward", "feedBack"):
            prefix = name + "_" + side
            for suffix, expected_hash in _BUFFER_METHODS.items():
                method_start, method_end = _method(masked, prefix + "_" + suffix)
                normalized = re.sub(r"\s+", "", masked[method_start:method_end]).replace(prefix, "BUFFER")
                if hashlib.sha256(normalized.encode()).hexdigest() != expected_hash:
                    raise ValueError(f"bounded filters: changed buffer {suffix} path for {prefix}")
            size_start, size_end = _method(masked, prefix + "_evaluateSizeExpr")
            size_body = masked[size_start:size_end]
            expected = (f"number{prefix}_evaluateSizeExpr(numbersamplerate,numbervectorsize)"
                        "{RNBO_UNUSED(vectorsize);RNBO_UNUSED(samplerate);return44100;}")
            if re.sub(r"\s+", "", size_body) != expected:
                raise ValueError(f"bounded filters: changed fixed-rate size expression for {prefix}")
            for expression in (f"new Float64Buffer(this->{prefix}_bufferobj)", f"Float64BufferRef {prefix}_buffer;"):
                if masked.count(expression) != 1:
                    raise ValueError(f"bounded filters: changed Float64 buffer ownership for {prefix}")
            size_match = re.search(r"\breturn\s+(44100)\s*;", size_body)
            replacements.append((size_start + size_match.start(1), size_start + size_match.end(1), str(maximum_samples)))
            buffers.append({"name": prefix, "storage_type": "Float64Buffer", "sample_bytes": 8,
                            "original_requested_samples": 44100, "original_frames": 65536,
                            "maximum_samples_with_margin": maximum_samples,
                            "frames": frames, "data_bytes": frames * 8})
        changes.append({"object": name, "mode": "explicit maximum", "maximum_ms": maximum_ms,
                        "kernel_sha256": fingerprint, "buffers": buffers})
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    prepared = text.encode()
    return prepared, {"name": "rnbo-1.4.4-filter-delay-cap-v1", "file": "rnbo_source.h",
                      "input_sha256": hashlib.sha256(source).hexdigest(),
                      "prepared_sha256": hashlib.sha256(prepared).hexdigest(),
                      "transformer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "maximum_ms": maximum_ms, "sample_rate": 44100,
                      "conversion": "original mstosamps(MillisecondTime), unchanged",
                      "storage": "Float64Buffer<double>, unchanged",
                      "interpolation": "original generated reader, unchanged",
                      "numerical_change": "Explicit delay input cap; smaller ring indices may change fractional rounding",
                      "objects": changes,
                      "buffer_data_bytes": sum(buffer["data_bytes"] for change in changes for buffer in change["buffers"])}
