# SPDX-License-Identifier: MIT
"""Optional Float32 output scaling for one reviewed authored16-row pink graph.

Whole-source, description and runtime pins establish the bounded state context;
a perform-method fingerprint alone would not establish the row count or writers.
No shared seed, scheduler, integer or buffer implementation is changed.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

_SOURCE = "45b50dab69cedcd4d732ed2fab28178021cb7e6adf0ddd718754a2dce70f6f3d"
_OUTPUT = "7372566a3620815d7c7db0e3cf5f8acfd27bdb62ab903f19c828379784eb9758"
_DESCRIPTION = "a6f6553e8e39b9b69adb2662fc3eb6be28ea1961ffe905733f555da43aa1d256"
_RUNTIME = "fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d"
_OLD = b"out1[(Index)i] = sum / (tmp * __pink_tilde_01_numRows) * 2. - 1.;"
_NEW = b"out1[(Index)i] = sum / (tmp * __pink_tilde_01_numRows) * 2.f - 1.f;"


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _canonical(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+"\n").encode()


def float32_pink_output(files: dict[str,bytes], description: dict) -> tuple[dict[str,bytes],dict]:
    """Copy the file map and suffix exactly two literals after normal fixes.

    The pinned graph has a fixed white seed and one16-row pink object. Its
    history starts at zero and receives only masked23-bit nonnegative values.
    This proves the tested normalisation sum domain0..17*(2**23-1). Reject any
    source/runtime/description change, including already transformed input.
    """
    if not isinstance(files,dict) or any(not isinstance(k,str) or not isinstance(v,bytes) for k,v in files.items()):
        raise ValueError("pink output: expected immutable byte files")
    source=files.get("rnbo_source.h")
    if source is None or _sha(source)!=_SOURCE:
        raise ValueError("pink output: unknown, partial or already transformed authored16-row context")
    stored=files.get("description.json")
    if stored is None or _sha(stored)!=_DESCRIPTION:
        raise ValueError("pink output: unknown authored description bytes")
    if not isinstance(description,dict):
        raise ValueError("pink output: expected authored description")
    try:
        matches=_canonical(description)==_canonical(json.loads(stored))
    except (ValueError,TypeError,UnicodeError) as exc:
        raise ValueError("pink output: invalid authored description") from exc
    if not matches:
        raise ValueError("pink output: mismatched description and source context")
    runtime={name:_sha(data) for name,data in sorted(files.items()) if name.startswith("common/")}
    if _sha(_canonical(runtime))!=_RUNTIME:
        raise ValueError("pink output: unreviewed runtime; normal list/clock and defined-integer fixes must precede scaling")
    if source.count(_OLD)!=1:
        raise ValueError("pink output: missing unique reviewed output expression")
    prepared=source.replace(_OLD,_NEW)
    if _sha(prepared)!=_OUTPUT or prepared.replace(_NEW,_OLD)!=source:
        raise ValueError("pink output: transformed source or inverse proof differs")
    updated=dict(files);updated["rnbo_source.h"]=prepared
    return updated,{
        "name":"rnbo-1.4.4-float32-pink-output-authored16-v1","file":"rnbo_source.h",
        "input_sha256":_SOURCE,"prepared_sha256":_OUTPUT,
        "description_file_sha256":_DESCRIPTION,"runtime_tree_sha256":_RUNTIME,
        "transformer_sha256":_sha(Path(__file__).read_bytes()),
        "literal_suffix_count":2,"inverse_byte_identity":True,
        "admission":"Exact authored noise-colour graph and corrected RNBO1.4.4 runtime; fixed16-row state and all callers pinned",
        "normalization_sum_domain":{"minimum":0,"maximum":142606319,"exhaustive_native_words":142606320},
        "evidence":"evidence/noise-float32-normalisation.json",
        "unchanged":"Float32 division; all integer RNG, white noise, row history, seeding, clocks and class layout",
        "numerical_scope":"Bit preservation in the reviewed bounded algorithm and tested target workload; no arbitrary Float32-expression equivalence claim"}
