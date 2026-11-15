# SPDX-License-Identifier: MIT
"""Guarded storage conversion for internal RNBO1.4.4 delay rings.

Automatic builds convert reviewed ordinary delay~ rings independently. Broader
comb/allpass conversion remains an explicit historical research option.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re

from bounded_filters import _method

_METHODS = {
    "read": "e058f2c04e0c8716c6ee5dae89aeb5412e71c7fe47bdca5d66e492cde939166d",
    "write": "ccb7e330e9f9a4eb0eeaf555eef90e89727548d704d75b53018beddaca7e84ab",
    "step": "6a9f474e90d681877dd420095df460c54dfbc654f07423ac53ab3b1281d6748b",
    "calcSizeInSamples": "67244cc8661bd672d1f76684596d103f35502914b69dcf41064e828de120b192",
    "init": "0ace37d70c73b2b13302608a573cd053a040ec50effaa817629b14ac797726c5",
    "reset": "a1b668961166379e1b5a81583ce488689224cae68224ac5426393a0014a113cb",
}
_RING = r"(?:(?:comb|allpass)_tilde_\d+_(?:feedForward|feedBack)|delaytilde_\d+_del)"


def float32_delays(source: bytes, *, code_mask, ring_names=None) -> tuple[bytes, dict]:
    text = source.decode(); masked = code_mask(text)
    names = re.findall(r"\bFloat64BufferRef\s+(" + _RING + r")_buffer\s*;", masked)
    if ring_names is not None:
        if not ring_names or any(name not in names for name in ring_names):
            raise ValueError("float32 delays: requested ring was not found")
        names = [name for name in names if name in ring_names]
    if not names or len(names) != len(set(names)):
        raise ValueError("float32 delays: no unique supported Float64 internal rings found")
    replacements = []; rings = []
    for name in names:
        for suffix, expected in _METHODS.items():
            start, end = _method(masked, name + "_" + suffix)
            normalized = re.sub(r"\s+", "", masked[start:end]).replace(name, "BUFFER")
            if hashlib.sha256(normalized.encode()).hexdigest() != expected:
                raise ValueError(f"float32 delays: unsupported {name}_{suffix} algorithm")
        # Float64Buffer must own an explicitly internal DataRef, never a user
        # data/external buffer. Check both assignments and constructor argument.
        own = re.findall(r"this->" + re.escape(name) + r"_bufferobj\s*=\s*initDataRef\(\s*this->" + re.escape(name) +
                         r"_bufferobj\s*,\s*this->dataRefStrings->\w+\s*,\s*true\s*,\s*this->dataRefStrings->\w+\s*,\s*this->dataRefStrings->\w+\s*\)\s*;", masked)
        if len(own) != 1:
            raise ValueError(f"float32 delays: {name} is not a reviewed internal DataRef")
        patterns = (r"\bnew\s+(Float64Buffer)\s*\(\s*this->" + re.escape(name) + r"_bufferobj\s*\)",
                    r"\b(Float64BufferRef)\s+" + re.escape(name) + r"_buffer\s*;")
        for pattern in patterns:
            matches = list(re.finditer(pattern, masked))
            if len(matches) != 1:
                raise ValueError(f"float32 delays: changed constructor/reference pair for {name}")
            match = matches[0]
            replacements.append((match.start(1), match.end(1), match[1].replace("64", "32")))
        start, end = _method(masked, name + "_evaluateSizeExpr")
        normalized = re.sub(r"\s+", "", masked[start:end]).replace(name, "BUFFER")
        size = re.fullmatch(r"numberBUFFER_evaluateSizeExpr\(numbersamplerate,numbervectorsize\)\{RNBO_UNUSED\(vectorsize\);RNBO_UNUSED\(samplerate\);return(\d+);\}", normalized)
        if not size or not 1 <= int(size[1]) <= 1048576:
            raise ValueError(f"float32 delays: unsupported fixed size expression for {name}")
        frames = 1 << (max(2, int(size[1])) - 1).bit_length()
        rings.append({"name": name, "requested_samples": int(size[1]), "frames": frames,
                      "before_type": "Float64Buffer<double>", "after_type": "Float32Buffer<float>",
                      "before_data_bytes": frames * 8, "after_data_bytes": frames * 4})
    for start, end, value in sorted(replacements, reverse=True):
        text = text[:start] + value + text[end:]
    prepared = text.encode()
    return prepared, {"name": "rnbo-1.4.4-float32-internal-delays-v1", "file": "rnbo_source.h",
                      "input_sha256": hashlib.sha256(source).hexdigest(),
                      "prepared_sha256": hashlib.sha256(prepared).hexdigest(),
                      "transformer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "rings": rings, "constructor_reference_pairs": len(rings),
                      "buffer_data_bytes_saved": sum(r["before_data_bytes"] - r["after_data_bytes"] for r in rings),
                      "unchanged": "ring sizes, reader/writer algorithms, external/data buffers, clocks and scheduler time"}


def automatic_float32_delays(source: bytes, *, code_mask) -> tuple[bytes, dict]:
    """Convert matching ordinary delay rings; retain and explain every fallback.

    No exception from an unrecognised form changes its source or stops unrelated
    rings from being considered. This is not a generic Float64Buffer rewrite.
    """
    masked = code_mask(source.decode())
    references = re.findall(r"\bFloat64BufferRef\s+(\w+)\s*;", masked)
    prepared = source
    converted = []; retained = []
    for reference in dict.fromkeys(references):
        match = re.fullmatch(r"(delaytilde_\d+_del)_buffer", reference)
        if not match:
            retained.append(dict(reference=reference, reason='outside reviewed ordinary delay~ scope'))
            continue
        name = match[1]
        try:
            candidate, report = float32_delays(prepared, code_mask=code_mask, ring_names=[name])
        except ValueError as error:
            retained.append(dict(reference=reference, reason=str(error)))
            continue
        prepared = candidate
        converted.extend(report['rings'])
    return prepared, dict(name='rnbo-1.4.4-auto-float32-ordinary-delays-v1',file='rnbo_source.h',
                          policy='auto', scope='reviewed internal ordinary delay~ rings',
                          input_sha256=hashlib.sha256(source).hexdigest(),
                          prepared_sha256=hashlib.sha256(prepared).hexdigest(),
                          transformer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                          converted=converted, retained_float64=retained,
                          buffer_data_bytes_saved=sum(r['before_data_bytes']-r['after_data_bytes'] for r in converted),
                          hardware_qualified=False, target_cpu_gain_measured=False,
                          unchanged='ring capacity and algorithms, other buffers, clocks and scheduler time')
