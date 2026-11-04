# SPDX-License-Identifier: MIT
"""Portable signal-state equations, boundary witnesses and original graphs."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'tests/fixtures/smoke/rnbo-signal-state-followup'
spec=importlib.util.spec_from_file_location('signal_state_followup_reference',DIRECTORY/'reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class RNBOSignalStateFollowupReferenceTests(unittest.TestCase):
    def blocks(self,model,count=20):
        return reference.reference_blocks(model,reference.case_input_words(model),count)

    def test_linear_filter_ideal_impulse_and_cross_callback_state(self):
        w=reference.word
        impulse=[0]*512;impulse[0]=w(.25);impulse[1]=w(.25)
        block=reference.reference_blocks(900,impulse,1)[0]
        for n in range(32):
            self.assertEqual(block[2*n],w(.25*.25*.75**n))
            self.assertEqual(block[2*n+1],w(.5*.25*.5**n))
        fixed=self.blocks(900,2)
        self.assertEqual(fixed[0][:4],(w(0),w(.0078125),w(.00390625),w(-.02734375)))
        self.assertNotEqual(fixed[1][:2],fixed[0][:2])
        dynamic=self.blocks(901,2)
        self.assertEqual(dynamic[0][:4],(w(0),w(.25),w(.00390625),w(.25)))
        self.assertEqual(dynamic[0][63],w(.5))
        for block in dynamic:
            self.assertEqual(block[1::2],reference.case_input_words(901)[1::2])

    def test_onoff_is_callback_constant_first_one_then_alternating(self):
        blocks=self.blocks(902)
        for call,block in enumerate(blocks):
            self.assertEqual(set(block),{reference.word(1 if call%2==0 else 0)})
        self.assertEqual(blocks[0],blocks[2])
        self.assertNotEqual(blocks[0],blocks[1])

    def test_all_counter_outputs_from_integer_prefix_sum_since_last_reset(self):
        vector=reference.case_input_words(903)
        self.assertEqual(vector,reference.case_input_words(904))
        count_flag=self.blocks(903)
        count_carry=self.blocks(904)
        total=0
        for n in range(5120):
            frame=n%256;call=n//256
            inc=int(reference.value(vector[2*frame]))
            reset=reference.value(vector[2*frame+1])!=0
            if reset:total=0
            else:total+=inc
            expected_count=total%7
            expected_carry=total//7
            expected_flag=int(not reset and inc!=0 and total!=0 and total%7==0)
            self.assertEqual(count_flag[call][2*frame],reference.word(expected_count))
            self.assertEqual(count_carry[call][2*frame],reference.word(expected_count))
            self.assertEqual(count_flag[call][2*frame+1],reference.word(expected_flag))
            self.assertEqual(count_carry[call][2*frame+1],reference.word(expected_carry))
        self.assertEqual(count_flag[0][:2],(reference.word(1),reference.word(0)))
        self.assertEqual(count_flag[0][18:20],(reference.word(0),reference.word(1)))
        for blocks in(count_flag,count_carry):
            for frame in(31,129):self.assertEqual(blocks[0][2*frame:2*frame+2],(0,0))
        self.assertNotEqual(count_flag[0][:2],count_flag[1][:2])

    def test_running_normalization_peak_updates_and_signal_max_pilot(self):
        w=reference.word
        fixed=self.blocks(905,2)
        self.assertEqual(fixed[0][:6],(w(0),w(1),w(.5),w(-1),w(-.5),w(-1)))
        self.assertEqual(fixed[0][26],w(-.5))
        self.assertEqual(fixed[1][2],w(.03125))
        self.assertNotEqual(fixed[0][2],fixed[1][2])
        dynamic=self.blocks(906,2)
        self.assertEqual(dynamic[0][:4],(w(0),w(.25),w(.25),w(.25)))
        for block in dynamic:
            self.assertEqual(block[1::2],reference.case_input_words(906)[1::2])
        zeros=[0x80000000,0]*256
        result=reference.reference_blocks(905,zeros,1)[0]
        self.assertEqual(result,tuple(zeros))

    def test_seven_full_streams_predeclared_limits_and_deferred_updown(self):
        catalog=json.loads((DIRECTORY/'catalog.json').read_bytes())
        self.assertEqual(len(catalog['cases']),7)
        self.assertEqual(catalog['automatic_warmup_blocks'],0)
        self.assertEqual(catalog['reference_sha256'],hashlib.sha256((DIRECTORY/'reference.py').read_bytes()).hexdigest())
        self.assertEqual(catalog['generator_sha256'],hashlib.sha256((DIRECTORY/'generate.py').read_bytes()).hexdigest())
        self.assertEqual(catalog['deferred_reference_design'][0]['exact_name'],'updown~')
        self.assertEqual(catalog['deferred_reference_design'][0]['status'],'reference-design-pending')
        self.assertNotIn('updown~',{c['exact_name']for c in catalog['cases']})
        for case in catalog['cases']:
            model=case['model'];inputs=reference.case_input_words(model)
            blocks=reference.reference_blocks(model,inputs)
            self.assertEqual(len(blocks),20)
            self.assertTrue(all(len(block)==512 for block in blocks))
            self.assertTrue(all(math.isfinite(reference.value(w))for block in blocks for w in block))
            self.assertEqual(reference.reference_words(model,inputs),blocks[0])
            self.assertEqual(case['maximum_absolute_error'],2e-6 if model in(900,901)else 0)
            self.assertEqual(case['patch_sha256'],hashlib.sha256((DIRECTORY/case['patch']).read_bytes()).hexdigest())

    def test_actual_ports_literal_controls_and_three_counter_outlets(self):
        spec=importlib.util.spec_from_file_location('signal_state_followup_generator',DIRECTORY/'generate.py')
        generator=importlib.util.module_from_spec(spec)
        old=sys.modules.get('reference')
        try:
            sys.modules['reference']=reference;spec.loader.exec_module(generator)
        finally:
            if old is None:sys.modules.pop('reference',None)
            else:sys.modules['reference']=old
        inventory={r['id']for r in json.loads((ROOT/'site/data/inventory.json').read_bytes())['spellings']}
        counter_outlets=set()
        for case in json.loads((DIRECTORY/'catalog.json').read_bytes())['cases']:
            self.assertIn('patcher:'+case['exact_name'],inventory)
            patch=json.loads((DIRECTORY/case['patch']).read_bytes())
            self.assertEqual(patch,generator.graph(case['model']))
            boxes={r['box']['id']:r['box']for r in patch['patcher']['boxes']}
            links={(tuple(r['patchline']['source']),tuple(r['patchline']['destination']))for r in patch['patcher']['lines']}
            self.assertEqual({b['maxclass']for b in boxes.values()},{'newobj'})
            if case['model']in(903,904):
                self.assertEqual(boxes['operator']['text'],'counter~ 0 7')
                self.assertIn((('right',0),('operator',1)),links)
                counter_outlets.update(s[1]for s,d in links if s[0]=='operator')
            elif case['model']in(900,905):
                self.assertIn((('fixed-0',0),('operator-0',1)),links)
                self.assertIn((('fixed-1',0),('operator-1',1)),links)
            elif case['model']in(901,906):
                self.assertIn((('right',0),('operator',1)),links)
                self.assertIn((('right',0),('out-right',0)),links)
            elif case['model']==902:
                self.assertEqual(len(links),2)
        self.assertEqual(counter_outlets,{0,1,2})

    def test_invalid_models_shapes_word_types_and_domains_reject(self):
        for model in(True,899,907):
            with self.assertRaises(ValueError):reference.case_input_words(model)
        for frames in(True,0,255,257):
            with self.assertRaises(ValueError):reference.input_words(frames)
        for count in(True,0,21):
            with self.assertRaises(ValueError):self.blocks(900,count)
        for model,index,bad in((900,0,0x7f800000),(901,1,reference.word(.75)),
                              (903,0,reference.word(.5)),(904,1,reference.word(-1)),
                              (905,0,reference.word(2)),(906,1,reference.word(0))):
            vector=list(reference.case_input_words(model));vector[index]=bad
            with self.subTest(model=model),self.assertRaises(ValueError):reference.reference_blocks(model,vector)
        for vector in((),(0,),[0]*511,[0]*511+[True]):
            with self.assertRaises(ValueError):reference.reference_blocks(900,vector)


if __name__=='__main__':unittest.main()
