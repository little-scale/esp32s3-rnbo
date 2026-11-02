# SPDX-License-Identifier: MIT
"""Defined int32 wrap adapter for exact RNBO 1.4.4 runtime forms.

Not enabled by this module: the caller must explicitly integrate the adapter.
Only rnbo_imul and the reviewed pink affine recurrence are changed. Other
arbitrary generated signed arithmetic is outside this adapter's safety claim.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re

RUNTIME_SHA256 = {
    "common/RNBO_Math.h": "bc251b20bf8b6f71575b3d779d16c99b2e91c7d0e0f534003c0458d74b609479",
    "common/RNBO_Types.h": "b3a1a4566588a04c843138c2823b7e0645999a8cae2a7f8582f594fd1328fe1b",
    "common/RNBO_AudioSignal.h": "2e410fc0485d40e31fbc084ca8bd2c0f7511bd6983d34e3c6a5451c3a1642dc0",
    "common/RNBO_Version.h": "73c10caaec39c540f867cf5376b0f3e53e464d3561be57d890841159ac36c8cf",
}
IMUL_SHA256 = "c529727b0da0708504f7f57a95cc794b19ee1c88189a448f89fec3aa69d6a657"
PINK_SHA256 = "c7536cf8d1fcae858a589092b65f3704f04a5447837f6a66083f0b0b455db6af"

# Unsigned operations reduce modulo2^32. Both signed casts are restricted to
# values <=INT32_MAX; the negative branch spans exactly INT32_MIN..-1.
_DEFINED_IMUL = """static_assert(sizeof(int32_t)==4 && sizeof(uint32_t)==4 &&
    INT32_MIN==(-INT32_MAX-1) && INT32_MAX==2147483647 &&
    UINT32_MAX==UINT32_C(4294967295), "defined wrap requires exact 32-bit types");
inline int32_t rnbo_defined_i32_from_u32(uint32_t value) {
    if (value<=static_cast<uint32_t>(INT32_MAX)) return static_cast<int32_t>(value);
    return -1-static_cast<int32_t>(UINT32_MAX-value);
}
inline int32_t rnbo_imul(int32_t x, int32_t y) {
    return rnbo_defined_i32_from_u32(static_cast<uint32_t>(x)*static_cast<uint32_t>(y));
}"""


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError("int32 wrap: " + message)


def _method(masked: str, name: str, *, inline=False) -> tuple[int, int]:
    qualifier = r"inline\s+" if inline else r""
    pattern = r"(?m)^[ \t]*" + qualifier + r"[A-Za-z_]\w*\s+" + re.escape(name) + r"\s*\([^{};]*\)\s*\{"
    matches = list(re.finditer(pattern, masked))
    _require(len(matches)==1, "expected exactly one method " + name)
    match = matches[0];cursor = match.end();depth = 1
    while cursor < len(masked) and depth:
        if masked[cursor]=="{": depth += 1
        elif masked[cursor]=="}": depth -= 1
        cursor += 1
    _require(depth==0, "unterminated method " + name)
    # Exclude leading indentation from the fingerprint, as in other adapters.
    start = match.start()
    while masked[start] in " \t": start += 1
    return start,cursor


def _edits(data: bytes, edits: list[tuple[int, int, str]]) -> tuple[bytes, list[dict]]:
    """Apply character spans but record UTF-8 byte spans; prove the exact inverse."""
    text = data.decode("utf-8")
    ordered = sorted(edits)
    end = 0;delta = 0;records = [];inverse = []
    for start,stop,replacement in ordered:
        _require(end<=start<stop<=len(text), "overlapping or invalid replacement")
        old = text[start:stop].encode("utf-8");new = replacement.encode("utf-8")
        input_start = len(text[:start].encode("utf-8"));input_end = input_start+len(old)
        output_start = input_start+delta;output_end = output_start+len(new)
        records.append({"input_span_bytes":[input_start,input_end],"prepared_span_bytes":[output_start,output_end],
                        "input_span_sha256":_hash(old),"prepared_span_sha256":_hash(new)})
        inverse.append((output_start,output_end,old));delta += len(new)-len(old);end = stop
    for start,stop,replacement in reversed(ordered): text = text[:start]+replacement+text[stop:]
    updated = text.encode("utf-8");restored = updated
    for start,stop,original in reversed(inverse): restored = restored[:start]+original+restored[stop:]
    _require(restored==data, "byte-exact inverse proof failed")
    return updated,records


def define_int32_wrap(files: dict[str, bytes], *, code_mask) -> tuple[dict[str, bytes], list[dict]]:
    """Return a copied file map and per-file audit records; never mutate input.

    Runtime headers are exact pinned originals, so unknown or already adapted
    runtimes fail closed. Pink prefixes may vary, but every complete generator
    body must match the reviewed form. Pink still uses its original systemticks
    seed policy; this adapter changes integer semantics, not random seeding.
    """
    _require(isinstance(files,dict) and callable(code_mask), "expected file map and code mask")
    for name,expected in RUNTIME_SHA256.items():
        _require(isinstance(files.get(name),bytes) and _hash(files[name])==expected,
                 "unknown/already adapted RNBO1.4.4 runtime " + name)
    _require(isinstance(files.get("rnbo_source.h"),bytes), "missing generated source")
    math_source = files["common/RNBO_Math.h"].decode("utf-8");math_mask = code_mask(math_source)
    start,end = _method(math_mask,"rnbo_imul",inline=True)
    fingerprint = _hash(re.sub(r"\s+","",math_mask[start:end]).encode())
    _require(fingerprint==IMUL_SHA256, "unknown rnbo_imul body")
    _require("rnbo_defined_i32_from_u32" not in math_mask, "already adapted helper name")
    source = files["rnbo_source.h"].decode("utf-8");masked = code_mask(source)
    # A changed naming/signature/body cannot silently leave a visible pink
    # object unadapted. Flat exports with duplicate prefixes also fail closed.
    tokens = re.findall(r"\bpink_tilde_[A-Za-z0-9_]+",masked)
    prefixes = set()
    for token in tokens:
        match = re.match(r"(pink_tilde_\d+)_",token)
        _require(match is not None,"unknown pink object naming form")
        prefixes.add(match[1])
    pink_edits = [];methods = []
    for prefix in sorted(prefixes):
        state_declarations = re.findall(r"\bIndex\s+"+re.escape(prefix)+r"_last\s*;",masked)
        _require(len(state_declarations)==1,"unknown pink Index state declaration " + prefix)
        name = prefix+"_generateRandomNumber";a,b = _method(masked,name)
        normalized = re.sub(r"\s+","",masked[a:b]).replace(prefix,"OBJECT")
        kernel = _hash(normalized.encode())
        _require(kernel==PINK_SHA256,"unknown pink affine recurrence " + name)
        replacement = f"""Index {name}() {{
    static_assert(sizeof(Index)==4 && static_cast<Index>(-1)==UINT32_MAX &&
        sizeof(number)==4 && sizeof(SampleValue)==4,
        "defined pink recurrence requires Float32 audio and uint32 Index");
    const uint32_t next = static_cast<uint32_t>(this->{prefix}_last)*UINT32_C(196314165)+UINT32_C(907633515);
    this->{prefix}_last = static_cast<Index>(::RNBO_Math::rnbo_defined_i32_from_u32(next));
    return this->{prefix}_last;
}}"""
        pink_edits.append((a,b,replacement));methods.append({"method":name,"kernel_sha256":kernel})
    # Source declarations that evade the normal object prefix must not be
    # mistaken for a no-pink fixture.
    visible_generators = re.findall(r"\b(pink[A-Za-z0-9_]*generateRandomNumber)\s*\(",masked)
    _require(set(visible_generators)=={m["method"] for m in methods}, "unreviewed pink generator naming")
    updated = dict(files);records = []
    math_bytes,math_edits = _edits(files["common/RNBO_Math.h"],[(start,end,_DEFINED_IMUL)])
    updated["common/RNBO_Math.h"] = math_bytes
    transformer_sha = _hash(Path(__file__).read_bytes())
    records.append({"name":"rnbo-1.4.4-defined-imul-v1","file":"common/RNBO_Math.h",
                    "input_sha256":_hash(files["common/RNBO_Math.h"]),"prepared_sha256":_hash(math_bytes),
                    "transformer_sha256":transformer_sha,"kernel_sha256":fingerprint,"edits":math_edits,
                    "inverse_byte_identity":True,"unchanged_outside_spans":True,
                    "runtime_guards_sha256":dict(RUNTIME_SHA256),
                    "purpose":"Defined modulo2^32 product, then signed mapping without an out-of-range signed cast",
                    "scope":"Only reviewed rnbo_imul and pink paths; no claim that all other generated signed arithmetic is defined"})
    if pink_edits:
        pink_bytes,pink_spans = _edits(files["rnbo_source.h"],pink_edits);updated["rnbo_source.h"] = pink_bytes
        records.append({"name":"rnbo-1.4.4-defined-pink-affine-v1","file":"rnbo_source.h",
                        "input_sha256":_hash(files["rnbo_source.h"]),"prepared_sha256":_hash(pink_bytes),
                        "transformer_sha256":transformer_sha,"methods":methods,"edits":pink_spans,
                        "inverse_byte_identity":True,"unchanged_outside_spans":True,
                        "purpose":"Defined uint32 affine multiply+add and signed-to-Index mapping; preserve all32 state bits",
                        "unchanged":"systemticks seed policy, row update/output arithmetic, buffers and scheduler",
                        "domain":"Compile-time guarded Float32 audio and uint32 Index; signed result represents exact int32 wrap"})
    return updated,records
