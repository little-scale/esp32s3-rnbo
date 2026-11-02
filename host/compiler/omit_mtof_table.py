# SPDX-License-Identifier: MIT
"""Opt-in omission of an unread RNBO1.4.4 internal mtof lookup payload.

This targets the current opaque module C ABI. It does not preserve generic
RNBO DataRef resource inspection or its initialization notification semantics.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re

from bounded_filters import _method

_DATAREF_SHA256 = "8cb2268c647a304d2b25db6db00ff1d5ce4200eff1859923ac0377c737adc684"
_EXP_KERNELS = {
    "2f8791609dc4d4cdfaa6553c95b9ce0a1df62b44170a98135b923a863c979d94",  # strict
    "ec3147b06b463e75f3845113466ee90a75ca1e16313e73d19a99ec030f1598e4",  # audio-v1
}
_FILL_SHA256 = "24950c124ae33f43a3c15ba0cb3e81c4b2d996316163ecd94e72c20607bbc3b0"
_TABLE = "RNBODefaultMtofLookupTable256"
_ENGINES = {"cd714121e628806ae7e6cdc82d1e3229d1704820b24839767c6bdd9ad3ea2b27",
            "41dc877005dc978fdcba56816c80f0c2dbe4734306fb4090e7a3606fb3dd5759"}
_CALLBACKS = {"d50eed48819cf2ba3ba763bc81d36ace274a9a5ee0588d7fe3eff49a11af7257",  # FX
              "1127fa08ddfb10bf28881102eeef3656992a788fae4952e255264480d8ecb2a6",  # Main fixture
              "8767b576bfcb754c3b0c1c76e117860c737992d26fa096c5a06673b2efbf6818"}  # drone
_CLOCKS = {
    "updateTime": {"c347560feb5c798e58ee61f8ea310fcea172272a00f6d796e49af9832ca1427c",
                   "b6d167dd99d67401565b48e735c7d9fe669916961dc7b6f54732897f6b80fd73"},
    "processInternalEvents": {"e320b279749df7bdd1835fe65c3622751d15fb7ea16deeadcc85421ae5b58d16"},
    "getPatcherTime": {"1ae500def59a5c7e79204af39b6b7bb659644b83621551e5be72154c73e5cb08"},
    "msToSamps": {"655ce4561aa87454ddf76f63284c5a9a9041539d73e543027e288d9ee62c2b59"},
    "sampsToMs": {"7fb63319238622418921312b4a96a70a130e5bec926436236718740f6972c363"},
}


def omit_mtof_table(source: bytes, dataref_runtime: bytes, minimal_engine_runtime: bytes, *, code_mask) -> tuple[bytes, dict]:
    if hashlib.sha256(dataref_runtime).hexdigest() != _DATAREF_SHA256:
        raise ValueError("omit mtof table: zero-size allocation requires the reviewed RNBO1.4.4 DataRef runtime")
    engine_hash = hashlib.sha256(minimal_engine_runtime).hexdigest()
    if engine_hash not in _ENGINES:
        raise ValueError("omit mtof table: unreviewed MinimalEngine event runtime")
    text = source.decode(); masked = code_mask(text)
    start,end = _method(masked,"processDataViewUpdate")
    callback_hash = hashlib.sha256(re.sub(r"\s+","",masked[start:end]).encode()).hexdigest()
    if callback_hash not in _CALLBACKS:
        raise ValueError("omit mtof table: unreviewed full DataView callback")
    for name,expected in _CLOCKS.items():
        observed = []
        for match in re.finditer(r"\b(?:void|number|MillisecondTime)\s+"+name+r"\s*\([^{};]*\)\s*(?:const\s*)?\{",masked):
            cursor = match.end();depth = 1
            while cursor < len(masked) and depth:
                if masked[cursor] == "{": depth += 1
                elif masked[cursor] == "}": depth -= 1
                cursor += 1
            if depth: raise ValueError("omit mtof table: unterminated time helper")
            observed.append(hashlib.sha256(re.sub(r"\s+","",masked[match.start():cursor]).encode()).hexdigest())
        if len(observed) != len(expected) or set(observed) != expected:
            raise ValueError(f"omit mtof table: unreviewed time helper {name}")
    positions = [i for i,c in enumerate(masked) if not c.isspace()]
    compact = "".join(masked[i] for i in positions)
    approved = []; edits = []; objects = []

    def one(pattern, label):
        matches = list(re.finditer(pattern,compact))
        if len(matches) != 1:
            raise ValueError(f"omit mtof table: expected one reviewed {label}")
        match = matches[0]
        approved.append((positions[match.start()],positions[match.end()-1]+1))
        return match

    names = re.findall(r"\bSampleBufferRef\s+(mtof_tilde_\d+_innerMtoF_buffer)\s*;",masked)
    if not names or len(names) != len(set(names)):
        raise ValueError("omit mtof table: no unique supported internal mtof views found")
    # No generated caller may obtain an anonymous alias through the indexed
    # resource API. Its sole allowed occurrence is the method definition.
    if (len(re.findall(r"\bgetDataRef\b",masked)) != 1 or
            len(re.findall(r"\bDataRef\s*\*\s*getDataRef\s*\(\s*DataRefIndex\s+index\s*\)\s*\{",masked)) != 1):
        raise ValueError("omit mtof table: indexed DataRef alias/call is unsupported")
    start,end = _method(masked,"fill"+_TABLE)
    if hashlib.sha256(re.sub(r"\s+","",masked[start:end]).encode()).hexdigest() != _FILL_SHA256:
        raise ValueError("omit mtof table: changed default table filler")
    table = re.escape(_TABLE)
    index_match = one(r"this->"+table+r"->setIndex\((\d+)\);","table index")
    index = index_match[1]
    # Preserve the generated resource index, name, type, views and callback
    # branches. File/tag metadata must retain the known internal defaults.
    for field,value in (("name",'"'+_TABLE+'"'),("file",'""'),("tag",'"buffer~"')):
        # Locate the declaration as CODE before inspecting the raw string.
        # A comment/quoted fake declaration must not supply a trusted literal.
        declaration = r"\bstatic\s+constexpr\s+auto&\s+"+field+index+r"\s*="
        matches = list(re.finditer(declaration,masked))
        if len(matches) != 1:
            raise ValueError(f"omit mtof table: changed internal {field} metadata")
        end = masked.find(";",matches[0].end())
        if end < 0 or text[matches[0].end():end].strip() != value:
            raise ValueError(f"omit mtof table: changed internal {field} metadata literal")
    one(r"DataRef"+table+r";","table declaration")
    one(r"this->"+table+r"=initDataRef\(this->"+table+r",this->dataRefStrings->name"+index+
        r",true,this->dataRefStrings->file"+index+r",this->dataRefStrings->tag"+index+r"\);","internal table ownership")
    one(r"case"+index+r":\{returnaddressOf\(this->"+table+r"\);break;\}","indexed table metadata")
    refreshes = []
    for name in names:
        prefix = name.removesuffix("_innerMtoF_buffer")
        start,end = _method(masked,prefix+"_innerMtoF_next")
        fingerprint = hashlib.sha256(re.sub(r"\s+","",masked[start:end]).replace(prefix,"OBJECT").encode()).hexdigest()
        if fingerprint not in _EXP_KERNELS:
            raise ValueError(f"omit mtof table: {prefix} is not a reviewed direct-exponential kernel")
        n = re.escape(name)
        one(r"SampleBufferRef"+n+r";",name+" declaration")
        one(r"this->"+n+r"=newSampleBuffer\(this->"+table+r"\);",name+" constructor")
        refresh = "this->"+name+"=reInitDataView(this->"+name+",this->"+_TABLE+");"
        one(re.escape(refresh),name+" refresh")
        refreshes.append(refresh)
        request = one(r"this->"+n+r"->requestSize\((65536),1\);",name+" initial capacity")
        edits.append((positions[request.start(1)],positions[request.end(1)-1]+1,"0"))
        one(r"this->"+n+r"->setSampleRate\(this->sr\);",name+" rate")
        one(r"this->"+n+r"=this->"+n+r"->allocateIfNeeded\(\);",name+" allocation")
        objects.append({"view":name,"direct_exp_kernel_sha256":fingerprint})
    one(re.escape("if(index=="+index+"){"+"".join(refreshes)+"}"),"DataView refresh branch")
    branch = ("if(this->"+_TABLE+"->hasRequestedSize()){if(this->"+_TABLE+"->wantsFill())"
              "this->fill"+_TABLE+"(this->"+_TABLE+");this->getEngine()->sendDataRefUpdated("+index+");}")
    one(re.escape(branch),"table allocation/fill/notification branch")
    # Account for EVERY direct table/view symbol use. A sample read, arbitrary
    # alias, extra constructor, resize or new metadata route fails closed.
    for symbol in [*names,_TABLE]:
        for match in re.finditer(r"\b"+re.escape(symbol)+r"\b",masked):
            if not any(a <= match.start() and match.end() <= b for a,b in approved):
                raise ValueError(f"omit mtof table: unreviewed resource/view reference {symbol}")
    for start,end,value in sorted(edits,reverse=True): text = text[:start]+value+text[end:]
    prepared = text.encode()
    return prepared,{"name":"rnbo-1.4.4-omit-unread-mtof-table-v1","file":"rnbo_source.h",
                     "input_sha256":hashlib.sha256(source).hexdigest(),"prepared_sha256":hashlib.sha256(prepared).hexdigest(),
                     "transformer_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     "dataref_runtime_sha256":_DATAREF_SHA256,"objects":objects,
                     "minimal_engine_runtime_sha256":engine_hash,"data_view_callback_sha256":callback_hash,
                     "time_helpers_sha256":{name:sorted(values) for name,values in _CLOCKS.items()},
                     "resource":_TABLE,"resource_index":int(index),"request_count":len(edits),
                     "original_frames":65536,"prepared_frames":0,"payload_bytes_saved":262144,
                     "preserved":"resource index/name/type, view declarations/constructors, direct-exp algorithms and scheduler code",
                     "changed":"no payload allocation/fill and no initialization DataRefUpdate notification for this resource",
                     "scope":"requires opaque module C ABI; generic RNBO DataRef inspection/resource-event equivalence is not preserved"}
