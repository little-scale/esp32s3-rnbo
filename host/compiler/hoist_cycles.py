# SPDX-License-Identifier: MIT
"""Opt-in loop-invariant conversions for reviewed RNBO1.4.4 cycles.

Preparation calls this helper only when requested. It moves unchanged
original macro expressions; it adds no alternative numeric implementation.
Only whole reviewed method forms are recognized. Signal-rate inputs are
explicitly recorded as unchanged, and unknown forms fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from bounded_filters import _method

_RUNTIME_SHA256 = {
    "RNBO_AudioSignal.h": "2e410fc0485d40e31fbc084ca8bd2c0f7511bd6983d34e3c6a5451c3a1642dc0",
    "RNBO_Types.h": "b3a1a4566588a04c843138c2823b7e0645999a8cae2a7f8582f594fd1328fe1b",
}


@dataclass(frozen=True)
class _Form:
    frequency: str  # scalar, fixed, or signal
    operand: str  # exact token spelling for fixed-frequency forms
    phase: str  # scalar, zero, or signal
    phase_scale: str


# Complete normalized signatures/bodies, not a whitelist of operator names.
# The three drone fingerprints cover five generated object instances.
_FORMS = {
    "1dbcc6178f4628491e85c1a2c54289819d118cd5ff26ab44fda7acefe8390cc5":
        _Form("scalar", "frequency", "scalar", "4294967296.0"),
    "94e35f0962c9b416221e9b3cfbab256207c3050dfb4aaea2c29707956f23e85e":
        _Form("scalar", "frequency", "scalar", "4294967296.0f"),
    "c095e1677b68b1f5b50ed0f6ad90aa0a81d04a9c83842d97283a4c6ccbf135e2":
        _Form("fixed", "0.009f", "scalar", "4294967296.0f"),
    "a4530a21b2391d6b6ddef71fefa449352f5b5a8d0437c379a9e4465b9b456e47":
        _Form("scalar", "frequency", "zero", ""),
    "58bbccd64b184272ad1cf673a5c694264ac67892e3d6c9a11b52a0aaa67f67e9":
        _Form("fixed", "0.01f", "zero", ""),
    # Both inlets vary per sample in these exact forms. Neither expression
    # moves. Recording this distinction prevents scalar/array inference.
    "c03a2b0162de919fabb245f42f427d24da87c7afa21113ee0fecb70beec03649":
        _Form("signal", "frequency", "signal", "4294967296.0"),
    "be11ed3aba7947f4180af596d76d3e6956c8ad20938df6a6e9e65434d2957727":
        _Form("signal", "frequency", "signal", "4294967296.0f"),
}
_METHOD = r"cycle_[A-Za-z0-9_]+_perform"
_LOOP = r"\bfor\s*\(\s*i\s*=\s*0\s*;\s*i\s*<\s*256\s*;\s*i\+\+\s*\)\s*\{"
_PHASE_LOCAL = "rnbo_s3_hoisted_phase"
_FREQUENCY_LOCAL = "rnbo_s3_hoisted_pincr"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _one(pattern: str, text: str, label: str):
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError(f"hoist cycles: expected one reviewed {label}")
    return matches[0]


def _without_spans(text: str, spans: list[tuple[int, int]]) -> str:
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + text[end:]
    return text


def _expression(body: str, masked: str, operand: str, scale: str):
    pattern = (r"\buint32_trunc\s*\(\s*" + operand + r"\s*\*\s*" + scale + r"\s*\)")
    match = _one(pattern, masked, "conversion expression")
    return match, body[match.start():match.end()]


def hoist_cycles(source: bytes, audio_signal_runtime: bytes, types_runtime: bytes,
                 *, code_mask) -> tuple[bytes, dict]:
    """Return candidate source and a fully hashed transformation/skip record.

    RNBO's Float32 module ABI and exclusive fixed-256 callback contract remain
    required. Every original Int64 conversion, literal and rounding point is
    retained. This is source-invariance admission, not a target timing claim.
    """
    for name, data in (("RNBO_AudioSignal.h", audio_signal_runtime),
                       ("RNBO_Types.h", types_runtime)):
        if _sha(data) != _RUNTIME_SHA256[name]:
            raise ValueError(f"hoist cycles: unreviewed macro/type runtime {name}")
    text = source.decode()
    masked = code_mask(text)
    names = re.findall(r"\bvoid\s+(" + _METHOD + r")\s*\(", masked)
    if len(names) != len(set(names)):
        raise ValueError("hoist cycles: duplicate generated cycle method")
    replacements = []
    records = []
    changed_spans = []
    changed_names = []
    for name in names:
        prefix_match = re.fullmatch(r"(cycle_tilde_\d+)_perform", name)
        if not prefix_match:
            raise ValueError(f"hoist cycles: unsupported generated name {name}")
        prefix = prefix_match[1]
        start, end = _method(masked, name)
        body, mask = text[start:end], masked[start:end]
        normalized = re.sub(r"\s+", "", mask).replace(prefix, "OBJECT")
        fingerprint = _sha(normalized.encode())
        form = _FORMS.get(fingerprint)
        if form is None:
            raise ValueError(f"hoist cycles: unsupported RNBO1.4.4 cycle method {name} ({fingerprint})")
        loop = _one(_LOOP, mask, "fixed-256 sample loop")
        _one(r"\bauto\s+__" + re.escape(prefix) + r"_f2i\s*=\s*this->" +
             re.escape(prefix) + r"_f2i\s*;", mask[:loop.start()], "existing cached f2i")
        if re.search(r"\b(?:" + _PHASE_LOCAL + "|" + _FREQUENCY_LOCAL + r")\b", mask):
            raise ValueError("hoist cycles: local cache name collision")
        record = {"method": name, "kernel_sha256": fingerprint,
                  "frequency_input": form.frequency, "phase_input": form.phase,
                  "hoisted": [], "skipped": [], "original_phase_branch_retained": False}
        if form.frequency == "signal" or form.phase == "signal":
            # Only the reviewed both-signal layouts reach this branch. A mixed
            # scalar/signal layout needs its own full-method review.
            if form.frequency != "signal" or form.phase != "signal":
                raise ValueError("hoist cycles: unreviewed mixed inlet layout")
            for inlet in ("frequency", "phase_offset"):
                record["skipped"].append({"inlet": inlet,
                    "reason": "per-sample signal; conversion stays in sample loop"})
            records.append(record)
            continue

        phase_raw = None
        condition_raw = None
        edits = []
        if form.phase == "scalar":
            match, phase_raw = _expression(body, mask, r"phase_offset", re.escape(form.phase_scale))
            condition = _one(r"\bif\s*\(\s*(phase_offset\s*!=\s*0\s*\|\|\s*0\s*==\s*2)\s*\)\s*\{",
                             mask, "original scalar phase condition")
            condition_raw = body[condition.start(1):condition.end(1)]
            if match.start() < loop.end() or condition.start() < loop.end():
                raise ValueError("hoist cycles: phase expression is not in reviewed loop")
            edits.append((match.start(), match.end(), _PHASE_LOCAL))
            record["hoisted"].append({"inlet": "phase_offset", "expression": phase_raw,
                                      "condition": condition_raw})
            record["original_phase_branch_retained"] = True
        elif form.phase != "zero":
            raise ValueError("hoist cycles: unreviewed phase input")
        frequency_match, frequency_raw = _expression(
            body, mask, re.escape(form.operand), re.escape("__" + prefix + "_f2i"))
        if frequency_match.start() < loop.end():
            raise ValueError("hoist cycles: frequency expression is not in reviewed loop")
        edits.append((frequency_match.start(), frequency_match.end(), _FREQUENCY_LOCAL))
        record["hoisted"].append({"inlet": "frequency", "expression": frequency_raw,
                                  "uses_existing_cached_f2i": True})
        changed = body
        for a, b, replacement in sorted(edits, reverse=True):
            changed = changed[:a] + replacement + changed[b:]
        # Inserting at the original `for` token keeps its leading indentation
        # and every original loop/condition byte. Raw expression spellings are
        # copied verbatim, including strict/v2 suffix and whitespace choices.
        prelude = ""
        if phase_raw is not None:
            prelude += (f"UInt32 {_PHASE_LOCAL} = 0;\n"
                        f"    if ({condition_raw}) {{\n"
                        f"        {_PHASE_LOCAL} = {phase_raw};\n"
                        "    }\n    ")
        prelude += f"const UInt32 {_FREQUENCY_LOCAL} = (UInt32)({frequency_raw});\n\n    "
        # Both replacements follow the loop token, so its source offset holds.
        changed = changed[:loop.start()] + prelude + changed[loop.start():]
        inverse = changed.replace(prelude, "", 1)
        for _, _, local in edits:
            original = phase_raw if local == _PHASE_LOCAL else frequency_raw
            if inverse.count(local) != 1:
                raise ValueError("hoist cycles: ambiguous inverse cache reference")
            inverse = inverse.replace(local, original, 1)
        if inverse != body:
            raise ValueError("hoist cycles: exact method inverse proof failed")
        record["source_inverse_verified"] = True
        records.append(record)
        replacements.append((start, end, changed))
        changed_spans.append((start, end))
        changed_names.append(name)
    for start, end, body in sorted(replacements, reverse=True):
        text = text[:start] + body + text[end:]
    final_mask = code_mask(text)
    final_spans = [_method(final_mask, name) for name in changed_names]
    if _without_spans(source.decode(), changed_spans) != _without_spans(text, final_spans):
        raise ValueError("hoist cycles: source outside changed methods differs")
    prepared = text.encode()
    return prepared, {
        "name": "rnbo-1.4.4-hoist-cycle-conversions-v1", "file": "rnbo_source.h",
        "input_sha256": _sha(source), "prepared_sha256": _sha(prepared),
        "transformer_sha256": _sha(Path(__file__).read_bytes()),
        "runtime_sha256": dict(_RUNTIME_SHA256), "methods": records,
        "hoisted_conversion_count": sum(len(m["hoisted"]) for m in records),
        "skipped_conversion_count": sum(len(m["skipped"]) for m in records),
        "changed_method_count": len(changed_names), "no_cycle_methods": not names,
        "outside_changed_methods_identical": True, "requires_float32_module_abi": True,
        "unchanged": "Original macro, expressions/literals, rounding, integer phase, lookup/interpolation, original loop phase branch and all other source/runtime bytes",
        "scope": "Only exact reviewed scalar/fixed inputs under exclusive fixed-256 module callbacks; no fenv observation or target cost claim",
    }
