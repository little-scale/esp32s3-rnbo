# SPDX-License-Identifier: MIT
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from build_hardware_smoke import ExportError,block_pool,canonical,parameter_case,reference_path,checked_codebox_source,routing_contract


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

    def test_extra_reference_is_explicit_and_unknown_families_reject(self):
        expected=Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-events-extra/reference.py'
        self.assertEqual(reference_path({'family':'rnbo-events-extra'}),expected)
        self.assertEqual(reference_path({'family':'rnbo-constants'}),expected.parent.parent/'rnbo-constants/reference.py')
        for family in ('rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-signal-range','rnbo-signal-stateful','rnbo-signal-routing','gen-range','gen-constants'):
            self.assertEqual(reference_path({'family':family}),expected.parent.parent/family/'reference.py')
        for family in ('../rnbo-events-extra','rnbo-events-other','rnbo-signal-routing-other',''):
            with self.assertRaises(ExportError):reference_path({'family':family})

    def test_signal_routing_source_route_does_not_admit_other_surfaces_or_controls(self):
        row={'surface':'patcher','role':'fx','syntax':'signal-object'}
        routing_contract(row)
        for field,value in (('surface','genexpr'),('surface','codebox'),('role','main'),
                            ('syntax','call'),('genexpr','source.genexpr'),('codebox','source.rnbo')):
            with self.subTest(field=field),self.assertRaises(ExportError):
                routing_contract(dict(row,**{field:value}))

    def test_codebox_source_rejects_surface_substitution_and_audio_bypasses(self):
        path=Path(__file__).resolve().parents[1]/'tests/fixtures/objects/wave4/codebox-arithmetic.rnbopat'
        patch=json.loads(path.read_bytes());row={'surface':'codebox'}
        code=patch['patcher']['boxes'][2]['box']['rnbo_extra_attributes']['code']
        expected=hashlib.sha256(code.encode()).hexdigest()
        self.assertEqual(checked_codebox_source(row,json.dumps(patch)),expected)
        for mutation in ('gen','empty','bypass','disabled','extra','wrong-surface'):
            candidate=copy.deepcopy(patch);case=dict(row)
            if mutation=='gen':candidate['patcher']['boxes'][2]['box']['text']='gen~'
            elif mutation=='empty':candidate['patcher']['boxes'][2]['box']['rnbo_extra_attributes']['code']=''
            elif mutation=='bypass':candidate['patcher']['lines'][2]['patchline']['source']=['left',0]
            elif mutation=='disabled':candidate['patcher']['lines'][2]['patchline']['disabled']=1
            elif mutation=='extra':candidate['patcher']['boxes'].append(copy.deepcopy(candidate['patcher']['boxes'][0]))
            else:case['surface']='patcher'
            with self.subTest(mutation=mutation),self.assertRaises(ExportError):
                checked_codebox_source(case,json.dumps(candidate))
        # Autonomous constants use the same explicit output route with no input wires.
        patch['patcher']['lines']=patch['patcher']['lines'][2:]
        self.assertEqual(checked_codebox_source(row,json.dumps(patch)),expected)

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
