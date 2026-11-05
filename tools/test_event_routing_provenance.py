# SPDX-License-Identifier: MIT
"""Bounded fault-line capture and exact native-event exclusion proofs."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import event_routing_provenance as proof
import run_hardware_smoke as runner
ROOT=Path(__file__).resolve().parents[1]
class Connection:
    def __init__(self,first,tail):self.first=first;self.tail=tail;self.drained=False
    @property
    def in_waiting(self):return len(self.first)
    def read(self,n):v=self.first;self.first=b'';return v
    def read_until(self,terminator,size):self.drained=True;return self.tail
class RoutingProofTests(unittest.TestCase):
    def test_fault_drain_retains_full_line_and_still_rejects_done(self):
        for first in(b'E (1) bench: FAIL ',b'RNBO_SMOKE DONE firmware_elf_sha256='+b'a'*64+b'\nE (1) bench: FAIL '):
            c=Connection(first,b'file=smoke.c condition=event\n');raw=bytearray()
            with self.assertRaises(RuntimeError):runner.collect_serial(c,'a'*64,2,raw,[],complete_fault_line=True)
            self.assertTrue(c.drained);self.assertTrue(raw.endswith(b'condition=event\n'))
    def test_default_capture_retains_original_fail_fast_policy(self):
        c=Connection(b'E (1) bench: FAIL ',b'condition=event\n');raw=bytearray()
        with self.assertRaises(RuntimeError):runner.collect_serial(c,'a'*64,2,raw,[])
        self.assertFalse(c.drained);self.assertEqual(raw,b'E (1) bench: FAIL ')
    def _proof(self,directory):
        f=ROOT/'tests/fixtures/smoke/rnbo-event-routing';spec=importlib.util.spec_from_file_location('routing_fault_ref',f/'reference.py')
        r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
        row=next(s for s in json.loads((f/'catalog.json').read_bytes())['cases']if s['id']=='list-rotate-right');m=row['model']
        ins=r.input_words();bs=r.reference_blocks(m,ins);es=r.parameter_events(m)
        raw={'run_log':json.dumps(proof.FAULT_RESULT).encode(),'inputs':struct.pack('<512I',*ins),
             'expected':struct.pack('<10240I',*(w for b in bs for w in b)),
             'events':struct.pack('<66I',*(w for e in es for w in(e['before_call'],0 if e['id']=='drive'else 1,r.word(e['value'])))),
             'harness':(ROOT/proof.NATIVE_EVENT_HARNESS).read_bytes()}
        p={'returncode':3}
        for key,b in raw.items():
            path=directory/key;path.write_bytes(b);p[key]=dict(path=str(path),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
        return dict(native_event_preflight=p),row,r
    def test_only_exact_original_event_fault_can_be_excluded(self):
        with tempfile.TemporaryDirectory()as d:
            module,row,r=self._proof(Path(d));result=proof.native_event_rejection(module,row,r);proof.checked_rejection_record(dict(result,id=row['id']))
            for change in(lambda p:p['native_event_preflight'].update(returncode=-6),
                          lambda p:p['native_event_preflight']['harness'].update(sha256='0'*64),
                          lambda p:p['native_event_preflight']['inputs'].update(bytes=1)):
                changed=copy.deepcopy(module);change(changed)
                with self.assertRaises(ValueError):proof.native_event_rejection(changed,row,r)
            with self.assertRaises(ValueError):proof.native_event_rejection(module,dict(row,id='other'),r)
            with self.assertRaises(ValueError):proof.checked_rejection_record(dict(result,id=row['id'],native_samples_checked=512))
