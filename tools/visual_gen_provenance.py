# SPDX-License-Identifier: MIT
"""Resolve only immutable qualified visual lowerers or an explicit build source.

Historical target receipts must remain verifiable after production changes.
Snapshots contain original MIT adapter code, never licensed generated DSP.
"""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[1]
QUALIFIED_LOWERERS={
    'tests/fixtures/smoke/gen-visual-flow/qualified_lowerer.mjs':'d1a72d560a0f4a74df1b73753c7f7b3ffc6a5e8bdc92deca87f42194ca65ba7c',
    'tests/fixtures/smoke/gen-visual-math/qualified_lowerer.mjs':'fc40fc0223b68234e513fdb0392dcd08f20eb7dc52f314e8e8a3e48c20c3abdf',
    'tests/fixtures/smoke/gen-visual-core/qualified_lowerer.mjs':'e97b4f34550992030f58dc2ca32913a2749eadbf50ce786a58572492414f53ec',
}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def resolve_lowerer(proof,*,allow_current=False):
    if type(proof)is not dict:raise ValueError('Visual Gen proof must be an object')
    digest=proof.get('adapter_sha256')
    for relative,expected in QUALIFIED_LOWERERS.items():
        path=ROOT/relative
        if digest==expected:
            if sha(path)!=expected:raise ValueError('Qualified visual lowerer snapshot changed')
            return path
    current=ROOT/'host/export/gen_visual.mjs'
    if allow_current and digest==sha(current):return current
    raise ValueError('Visual Gen receipt has no matching qualified lowerer source')
