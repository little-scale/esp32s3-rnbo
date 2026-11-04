# SPDX-License-Identifier: MIT
"""Explicit float32 DSP profiles guarded by whole RNBO1.4.4 method hashes.

Only reviewed audio methods are admitted. No generated algorithm is vendored;
the fingerprints normalize whitespace/comments and generated object prefixes.
Explicit profiles reject unknown forms and changed constants. Auto preserves
unknown matched methods byte for byte and reports why they were skipped.
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
_CATALOG_V3['lores'] = {'d7645d579512b7447249b713b998a86cd1c28e720d0f5d7dda8f982a58ebcf48'}
_PREFIX_V3 = rf"(?:{_PREFIX}|lores_\d+)"
_METHOD_NAME_V3 = rf"(?:{_METHOD_NAME}|lores_\d+_perform)"
# C++ decimal floating tokens, excluding integer, hexadecimal and suffixed
# tokens. Applying this only within a full-method hash is intentional.
_DECIMAL = re.compile(r"(?<![\w.])(?:(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)(?![\w.])")


def float32_audio(source: bytes, *, code_mask, profile: str) -> tuple[bytes, dict]:
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
