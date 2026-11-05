# SPDX-License-Identifier: MIT
"""Exact native event-rejection proof for the separately target-probed rotation.

This is not a general permission to omit failed tests. The original graph stays
in the full source ledger, and its isolated target fault has a separate receipt.
The harness file/pin is versioned; new formats require a new source and pin.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
ROOT=Path(__file__).resolve().parents[1]
NATIVE_EVENT_HARNESS='tests/native/smoke_event_routing_test.cpp'
NATIVE_EVENT_HARNESS_SHA='332ad2ef98cee87b0ab560ab51493bb2f095751e4c860b7fb6289b02fcabb098'
FAULT_RESULT=dict(samples=0,event_status=-4,fault_call=0,fault_event=1,event_parameter_slot=0,platform_errors=1,
                  invalid_samples=0,late_platform_allocations=0,late_cpp_allocations=0)
def require(test,message):
    if not test:raise ValueError(message)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def proof_bytes(item):
    require(type(item)is dict and set(item)=={'path','bytes','sha256'},'Malformed native event proof receipt')
    p=Path(item['path']);require(p.is_file()and not p.is_symlink(),'Native event proof must be a regular file')
    raw=p.read_bytes();require(len(raw)<=1048576 and type(item['bytes'])is int and item['bytes']==len(raw)and item['sha256']==digest(raw),
                               'Native event proof bytes differ')
    return raw
def native_event_rejection(module,row,reference):
    require(row['id']=='list-rotate-right'and row['exact_name']=='list.rot'and row['fixed_arguments']=='1',
            'Native event exclusion is restricted to the original positive rotation')
    proof=module.get('native_event_preflight',{});require(proof.get('returncode')==3,'Native event probe did not return its structured fault status')
    harness=proof_bytes(proof.get('harness'))
    require(digest(harness)==NATIVE_EVENT_HARNESS_SHA and digest((ROOT/NATIVE_EVENT_HARNESS).read_bytes())==NATIVE_EVENT_HARNESS_SHA,
            'Native event harness identity differs')
    raw=proof_bytes(proof.get('run_log'));result=json.loads(raw)
    require(result==FAULT_RESULT and all(type(v)is int for v in result.values()),'Native event fault stage/result differs')
    m=row['model'];inputs=reference.case_input_words(m);blocks=reference.reference_blocks(m,inputs);events=reference.parameter_events(m)
    expected_inputs=struct.pack('<512I',*inputs);expected_words=struct.pack('<10240I',*(w for b in blocks for w in b))
    expected_events=struct.pack('<66I',*(w for e in events for w in(e['before_call'],0 if e['id']=='drive'else 1,reference.word(e['value']))))
    require(proof_bytes(proof.get('inputs'))==expected_inputs and proof_bytes(proof.get('expected'))==expected_words and
            proof_bytes(proof.get('events'))==expected_events,'Native event input/reference/arm sequence differs')
    return dict(status='native_event_preflight_failed',stage='native-event-preflight',returncode=3,
        failure_log_sha256=digest(raw),native_harness_sha256=NATIVE_EVENT_HARNESS_SHA,native_event_status=-4,
        native_fault_call=0,native_fault_event=1,native_samples_checked=0,hardware_executed_in_batch=False,
        detail='Original positive rotation faults in its first drive event; the isolated XIAO event-fault probe is published separately. No output comparison or callback CPU is claimed here.')
def checked_rejection_record(failure):
    require(failure.get('status')=='native_event_preflight_failed'and failure.get('id')=='list-rotate-right'and
        failure.get('stage')=='native-event-preflight'and failure.get('returncode')==3 and failure.get('native_event_status')==-4 and
        failure.get('native_fault_call')==0 and failure.get('native_fault_event')==1 and failure.get('native_samples_checked')==0 and
        failure.get('hardware_executed_in_batch')is False and failure.get('native_harness_sha256')==NATIVE_EVENT_HARNESS_SHA and
        type(failure.get('failure_log_sha256'))is str and re.fullmatch('[0-9a-f]{64}',failure['failure_log_sha256']),
        'Native event failure must remain distinct from target output comparison')
