# SPDX-License-Identifier: MIT
"""Explicit float32 DSP profiles guarded by whole RNBO1.4.4 method hashes.

Only reviewed audio methods are admitted. No generated algorithm is vendored;
the fingerprints normalize whitespace/comments and generated object prefixes.
Unknown forms, changed constants and already transformed input fail closed.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re

from bounded_filters import _method

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
_PREFIX = r"(?:(?:cycle|saw|scale|reson|comb|allpass|mtof)_tilde_\d+|dspexpr_\d+|delaytilde_\d+)"
_METHOD_NAME = r"(?:(?:(?:cycle|saw|scale|reson|comb|allpass)_tilde_\d+|dspexpr_\d+|delaytilde_\d+)_perform|mtof_tilde_\d+_innerMtoF_next)"
# C++ decimal floating tokens, excluding integer, hexadecimal and suffixed
# tokens. Applying this only within a full-method hash is intentional.
_DECIMAL = re.compile(r"(?<![\w.])(?:(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)(?![\w.])")


def float32_audio(source: bytes, *, code_mask, profile: str) -> tuple[bytes, dict]:
    if profile not in ("float32-cycle-v2", "float32-audio-v1"):
        raise ValueError("Unsupported float32 audio profile")
    text = source.decode(); masked = code_mask(text)
    replacements = []; methods = []
    pattern = r"\b(?:void|number)\s+(" + (_METHOD_NAME if profile == "float32-audio-v1" else r"cycle_[A-Za-z0-9_]+_perform") + r")\s*\("
    names = re.findall(pattern, masked)
    if not names or len(names) != len(set(names)):
        raise ValueError(f"{profile}: no unique supported audio methods found")
    for name in names:
        prefix = re.match(_PREFIX, name)
        if not prefix:
            raise ValueError(f"{profile}: unsupported generated name {name}")
        prefix = prefix[0]; kind = prefix.split("_", 1)[0]
        start, end = _method(masked, name)
        body = masked[start:end]
        normalized = re.sub(r"\s+", "", body).replace(prefix, "OBJECT")
        fingerprint = hashlib.sha256(normalized.encode()).hexdigest()
        if fingerprint not in _CATALOG.get(kind, set()):
            raise ValueError(f"{profile}: unsupported RNBO1.4.4 audio method {name} ({fingerprint})")
        edits = []
        for token in _DECIMAL.finditer(body):
            edits.append({"literal": token[0], "replacement": token[0] + "f"})
            replacements.append((start + token.end(), start + token.end(), "f"))
        conversions = 0
        if kind in ("comb", "allpass"):
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
                        "literal_changes": edits, "local_float32_ms_to_samples": conversions})
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    prepared = text.encode()
    return prepared, {"name": "rnbo-1.4.4-" + profile, "file": "rnbo_source.h",
                      "input_sha256": hashlib.sha256(source).hexdigest(),
                      "prepared_sha256": hashlib.sha256(prepared).hexdigest(),
                      "transformer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "methods": methods, "literal_suffix_count": sum(len(m["literal_changes"]) for m in methods),
                      "unchanged": "integer phase/truncation algorithms, ring interpolation, scheduler methods, double time and frame counters",
                      "numerical_change": "Audio expression rounding and expf overload selection; not a bit-identity profile"}
