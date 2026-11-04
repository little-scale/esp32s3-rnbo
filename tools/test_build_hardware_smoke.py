# SPDX-License-Identifier: MIT
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from build_hardware_smoke import ExportError,block_pool,canonical,parameter_case


class BoundaryPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.prepared=Path(self.temp.name)
        self.parameter={'paramId':'drive','index':0,'name':'drive','displayName':'drive','unit':'',
            'minimum':-8,'maximum':8,'initialValue':0,'exponent':1,'steps':0,'type':'ParameterTypeNumber'}
        self.actions=[{'before_call':0,'id':'drive','value':1},
            {'before_call':10,'id':'drive','value':3},{'before_call':10,'id':'drive','value':-2},
            {'before_call':19,'id':'drive','value':-.5}]

    def plan(self,parameter=None,actions=None,wrong_hash=False):
        parameter=parameter or self.parameter
        description={'numInputChannels':2,'numOutputChannels':2,'numMidiInputPorts':0,'numMidiOutputPorts':0,
            'numParameters':1,'parameters':[parameter]}
        (self.prepared/'description.json').write_text(json.dumps(description))
        keys=('paramId','index','name','displayName','unit','minimum','maximum','initialValue','exponent','steps')
        digest=hashlib.sha256(canonical([{k:parameter.get(k)for k in keys}])).hexdigest()
        manifest={'parameter_count':1,'parameter_schema_sha256':'0'*64 if wrong_hash else digest}
        reference=SimpleNamespace(parameter_events=lambda model:self.actions if actions is None else actions)
        return parameter_case(self.prepared,manifest,reference,148)

    def test_actions_preserve_order_slots_and_independent_normalization(self):
        result=self.plan();events=result['parameter_events']
        self.assertEqual([e['before_call']for e in events],[0,10,10,19])
        self.assertEqual([e['value_word']for e in events],[0x3f800000,0x40400000,0xc0000000,0xbf000000])
        self.assertEqual(events[0]['normalized_word'],0x3f100000) # (1+8)/16
        self.assertTrue(all(e['parameter_slot']==0 for e in events))
        self.assertEqual(result['strict_zero_sign_channels'],2)

    def test_schema_drift_unknown_ids_order_and_bounds_reject(self):
        with self.assertRaises(ExportError):self.plan(wrong_hash=True)
        for changes in ({'before_call':True},{'before_call':20},{'id':'unknown'},{'value':9},{'value':float('nan')}):
            actions=copy.deepcopy(self.actions);actions[-1].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ExportError):self.plan(actions=actions)
        with self.assertRaises(ExportError):self.plan(actions=list(reversed(self.actions)))
        with self.assertRaises(ExportError):self.plan(actions=[])
        parameter=dict(self.parameter,exponent=2)
        with self.assertRaises(ExportError):self.plan(parameter=parameter)

    def test_block_pool_deduplicates_whole_words_and_preserves_call_selection(self):
        positive=[0]*512;negative=positive.copy();negative[1]=0x80000000
        cases=[{'expected_blocks':[positive,negative]*10},{'expected_blocks':[negative,positive]*10}]
        blocks,refs=block_pool(cases)
        self.assertEqual(len(blocks),2)
        for case,indices in zip(cases,refs):
            self.assertEqual([list(blocks[i])for i in indices],case['expected_blocks'])
        self.assertNotEqual(refs[0][0],refs[0][1]) # negative-zero observer bits are not merged


if __name__=='__main__':unittest.main()
