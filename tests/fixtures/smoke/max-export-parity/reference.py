# SPDX-License-Identifier: MIT
"""Reuse original independent references for matched export-route observations."""
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
SPECS={int(k):v for k,v in json.loads((HERE/'models.json').read_bytes()).items()}
MODELS=frozenset(SPECS)
ABSOLUTE_TOLERANCES={m:s['tolerance']for m,s in SPECS.items()}
REFERENCE_POLICIES={m:'original-independent-reference-matched-export-route-v1'for m in SPECS}
PREPARE_ZERO_WARM_BLOCKS=0
REFERENCE_CALL_COUNT=20
PILOT_RIGHT_BIT_EXACT=True
_cache={}
def original(model):
 if type(model)is not int or model not in MODELS:raise ValueError('Unknown export-route model')
 s=SPECS[model];path=ROOT/s['reference']
 if hashlib.sha256(path.read_bytes()).hexdigest()!=s['reference_sha256']:raise ValueError('Original reference changed')
 if s['reference']not in _cache:
  spec=importlib.util.spec_from_file_location('parity_reference_'+str(model),path);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);_cache[s['reference']]=v
 return s,_cache[s['reference']]
def parameters():return[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0),dict(id='arm',minimum=0.,maximum=1.,initial=0.,exponent=1.,steps=0)]
def input_words(frames=256):return case_input_words(3500,frames)
def case_input_words(model,frames=256):
 s,r=original(model);return r.case_input_words(s['original_model'],frames)if hasattr(r,'case_input_words')else r.input_words(frames)
def parameter_events(model):
 s,r=original(model);return r.parameter_events(s['original_model'])if s['parameters']else[]
def reference_blocks(model,inputs,call_count=20):
 s,r=original(model);return r.reference_blocks(s['original_model'],inputs,call_count)
def reference_words(model,inputs):return reference_blocks(model,inputs,1)[0]

def word(x):return struct.unpack('<I',struct.pack('<f',float(x)))[0]
