# SPDX-License-Identifier: MIT
"""Opt-in for ONE proved authored64-sample average~ caller context.

Not integrated by default. This is an exact-source memory transformation, not
a generic average~ cap, accuracy correction, or complete C++ alias analysis.
The caller must enforce opaque module C ABI1.0 in its manifest/build config.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

_SOURCE_SHA256 = "0a1cf2b553c451b0253e3af83568888ffff1b37e7519e7cc3c9364da46393b74"
_OUTPUT_SHA256 = "c843b9f0a14a53e8c792c6e7a857bb9dda2d7df488c3282db4a0b16f36023ab0"
_DESCRIPTION_SHA256 = "5dc3e3114110aed6c24fd6feae8eae9de6d38f85b825f4c8129da90c9170297e"
_DESCRIPTION_FILE_SHA256 = "002ecf48438cd76aa0f9a466ce1ded649a90fad38ab3d6658a1fc20732e22046"
_SCHEMA_SHA256 = "0ede2e020ff26cc89e0572aca56bca88fccb641b679ba13b7901f399c4e4bbb0"
_RUNTIME_TREE_SHA256 = "8ffddb34437300f9b259ad246e174e9d89c77f9b3f498cb5388186b3b5827c2a"
_METHODS = {
    "average_tilde_01_init": "694306ce006a070b5a4bd0b8afbe15474ee5f33d3f73b4efaa9528e3171badd0",
    "average_tilde_01_dspsetup": "ab01ce42df00c2da529af387adaa964d13dec71510ea88af85ef487404e88d82",
    "average_tilde_01_perform": "221cecfc8009158ba9da1e2883ec71ede0fde5fb21d8b12d811088c8380be002",
    "average_tilde_01_setwindowsize": "e81677c3c25aa7a5e495ab0b2fd97f1bdcbdbd2bb97033573a4442df037d9d20",
    "average_tilde_01_doReset": "42ed246837f85837fa0618904feef6d49f6f13e5831ac7dce9e57891042335a6",
    "average_tilde_01_windowSize_set": "a4c15d15eb726c216d6298cca50a27f95866c5e2543514b449f7b957c4adbe75",
    "average_tilde_02_init": "74a670883ed4f07eff04750e6ff5f211bce9044fffd828ea084b1ef2278646e3",
    "average_tilde_02_dspsetup": "17c29f134893be12104dbac223d279d7021d84ef9da1147b461415fe05d05c97",
    "average_tilde_02_perform": "d88ffb5c654481227cb0a73701623cf0efc86f9ce439000ea330366d7b184776",
    "average_tilde_02_setwindowsize": "9fb5554e07862e5df6f707ffd0e4e0cc0bdd55070a391803d3e44565fe0bbe7a",
    "average_tilde_02_doReset": "67edf4a14370ecc740fad1a022442d933f07bfa0ff038d6732b9a40db64a652b",
    "average_tilde_02_windowSize_set": "30027ffeec12daacd5aef795ddb6cb0a337538cc53164151c6d8193d6fe9989b",
    "getDataRef": "76135835ccafa7042783c8b944049491df3e01d5e3dd1319dbbd5b910ae6be68",
    "processDataViewUpdate": "00cdebfa4b0f739bda588db360bde2c7002106e7519968574c46f36e6092b2ec",
    "initialize": "a7f4c4af6601031fc080a8dcf76a0cd2a53bcad158ca768edc1990ceb443c891",
    "setParameterValue": "c172c0a2a07e65037cdda638a820ea8202ddf990e3b94d06f1e0ca4109d9c573",
    "param_01_value_set": "2f4d09c56d55d2e029b790a8ad465c89ca69a4ca959f4dbe5bd7b0bb2c220c1f",
    "allocateDataRefs": "8872e8d028ec1e1ad73b06ade1b0b5d84dc0818f2a138c6bbe7040bf3ace90e1",
    "param_01_value_constrain": "7833f710727be3adbfb2f7c31c3702a6f5310f26cfeb71e64621e5d553a5edc0",
}
_EVIDENCE = {
    "build/research/average-window/audit.json": "b49a61ef683ae7f455d60472873bdffafd5a0d5ddfeac794c90712e162f3b701",
    "build/research/average-window/comparison.json": "abca28b5a4a2fa126b618d0d8932e8f499bfa1249f1b05e6b1e0a28ae09464ee",
    "build/research/average-window/lifecycle.json": "f4d8850f7a340191283a21126971a6c080f02a7709d14aebc838704d1443c786",
}


def _sha(value): return hashlib.sha256(value).hexdigest()


def _canonical(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+"\n").encode()


def _span(masked,name):
    matches=list(re.finditer(r"\b(?:void|number|DataRef\s*\*)\s+"+re.escape(name)+r"\s*\([^{};]*\)\s*(?:const\s*)?\{",masked))
    if len(matches)!=1:raise ValueError(f"compact average: unknown method context {name}")
    match=matches[0];cursor=match.end();depth=1
    while cursor<len(masked) and depth:
        if masked[cursor]=="{":depth+=1
        elif masked[cursor]=="}":depth-=1
        cursor+=1
    if depth:raise ValueError("compact average: unterminated method")
    return match.start(),cursor


def compact_average(files: dict[str,bytes], description: dict, code_mask) -> tuple[dict[str,bytes],list[dict]]:
    """Return a fresh file map and audit records; the input map is untouched.

    Initial scope is deliberately just the sealed original two-channel graph
    whose only window caller is a clamped numeric parameter1..64 (default16).
    Caller manifest/config integration MUST enforce opaque C ABI1.0. Resource
    indices/notifications remain, while history type and size deliberately differ.
    """
    if not isinstance(files,dict) or any(not isinstance(k,str) or not isinstance(v,bytes) for k,v in files.items()):
        raise ValueError("compact average: expected immutable byte files")
    source=files.get("rnbo_source.h")
    if source is None or _sha(source)!=_SOURCE_SHA256:
        raise ValueError("compact average: unknown, partial, or already transformed authored context")
    if not isinstance(description,dict) or _sha(_canonical(description))!=_DESCRIPTION_SHA256:
        raise ValueError("compact average: unreviewed parameter/service description")
    if not isinstance(files.get("description.json"),bytes) or _sha(files["description.json"])!=_DESCRIPTION_FILE_SHA256:
        raise ValueError("compact average: unreviewed description file bytes")
    try:stored=json.loads(files["description.json"])
    except (KeyError,UnicodeError,json.JSONDecodeError) as exc:
        raise ValueError("compact average: missing/invalid description file") from exc
    if _sha(_canonical(stored))!=_DESCRIPTION_SHA256:
        raise ValueError("compact average: file/description context mismatch")
    schema=[{key:p.get(key) for key in ("paramId","index","name","displayName","unit","minimum","maximum","initialValue","exponent","steps")} for p in description["parameters"]]
    if _sha(_canonical(schema))!=_SCHEMA_SHA256:
        raise ValueError("compact average: unknown authored window bounds")
    runtime={name:_sha(data) for name,data in sorted(files.items()) if name.startswith("common/")}
    if _sha(_canonical(runtime))!=_RUNTIME_TREE_SHA256:
        raise ValueError("compact average: unreviewed runtime tree; reviewed correctness fixes must precede this candidate")
    text=source.decode();masked=code_mask(text)
    if not isinstance(masked,str) or len(masked)!=len(text):raise ValueError("compact average: invalid code mask")
    spans={name:_span(masked,name) for name in _METHODS}
    for name,(start,end) in spans.items():
        if _sha(re.sub(r"\s+","",masked[start:end]).encode())!=_METHODS[name]:
            raise ValueError(f"compact average: changed reviewed method {name}")
    callgraph={};edits=[];resources=[]
    for index in (1,2):
        prefix=f"average_tilde_{index:02d}"
        for target,owners in ((prefix+"_windowSize_set",["param_01_value_set"]),
                              (prefix+"_setwindowsize",[prefix+"_perform"]),
                              (prefix+"_doReset",[prefix+"_init",prefix+"_perform"])):
            observed=set()
            for call in re.finditer(r"\bthis->"+re.escape(target)+r"\s*\(",masked):
                found=[name for name in owners if spans[name][0]<=call.start()<spans[name][1]]
                if len(found)!=1:raise ValueError("compact average: unreviewed window/reset caller")
                observed.add(found[0])
            if observed!=set(owners):raise ValueError("compact average: incomplete caller proof")
            callgraph[target]=sorted(observed)
        for suffix in ("init","dspsetup"):
            start,end=spans[prefix+"_"+suffix];body=text[start:end]
            if suffix=="init":
                needle=f"this->{prefix}_buffer->requestSize(this->sr + 1, 1);"
                if body.count(needle)!=1:raise ValueError("compact average: initial capacity changed")
                body=body.replace(needle,f"this->{prefix}_buffer->requestSize(65, 1);")
            else:
                condition=f"if (44100 > this->{prefix}_buffer->getSize())";growth=f"this->{prefix}_buffer->setSize(44100 + 1);"
                if body.count(condition)!=1 or body.count(growth)!=1:raise ValueError("compact average: DSP regrowth changed")
                body=body.replace(condition,f"if (65 > this->{prefix}_buffer->getSize())").replace(growth,f"this->{prefix}_buffer->setSize(65);")
            edits.append((start,end,body))
        resources.append({"view":prefix+"_buffer","maximum_window_samples":64,"before_frames":44101,"after_frames":65,
                          "before_type":"Float64Buffer<double>","after_type":"Float32Buffer<float>",
                          "before_payload_bytes":352808,"after_payload_bytes":260})
    for start,end,body in sorted(edits,reverse=True):text=text[:start]+body+text[end:]
    for index in (1,2):
        prefix=f"average_tilde_{index:02d}"
        for token in (f"new Float64Buffer(this->{prefix}_bufferobj)",f"Float64BufferRef {prefix}_buffer;"):
            if text.count(token)!=1:raise ValueError("compact average: unreviewed history constructor/reference pair")
            text=text.replace(token,token.replace("Float64","Float32"))
    prepared=text.encode()
    if _sha(prepared)!=_OUTPUT_SHA256:raise ValueError("compact average: unexpected transformed source")
    updated=dict(files);updated["rnbo_source.h"]=prepared
    return updated,[{"name":"rnbo-1.4.4-compact-average-authored64-v1","file":"rnbo_source.h",
        "input_sha256":_SOURCE_SHA256,"prepared_sha256":_OUTPUT_SHA256,"runtime_tree_sha256":_RUNTIME_TREE_SHA256,
        "transformer_sha256":_sha(Path(__file__).read_bytes()),
        "description_sha256":_DESCRIPTION_SHA256,"parameter_schema_sha256":_SCHEMA_SHA256,
        "method_code_sha256":dict(_METHODS),"callgraph":callgraph,"resources":resources,"payload_bytes_saved":705096,
        "requires_opaque_dataref_abi":{"major":1,"minor":0},
        "resource_semantics":"history type/size differ; resource indices and positive allocation/update notification branches retained",
        "unchanged":"accumulator arithmetic, available-history/reset policy, scalar window semantics, clocks and scheduler",
        "accuracy":"known strict running-sum oracle limitation remains; no accuracy correction or universal bit-identity claim",
        "evidence_sha256":dict(_EVIDENCE),"evidence_comparisons":39,"evidence_workloads":13,
        "observed_native_high_water_bytes":{"static_platform_reference":705632,"static_platform_compact":544,
            "dynamic_total_reference":705824,"dynamic_total_compact":736,"dynamic_compact_capacity_tested":4096,
            "pointer_bits":64,"hardware_qualified":False},
        "observed_native_high_water_bytes_saved":705088}]
