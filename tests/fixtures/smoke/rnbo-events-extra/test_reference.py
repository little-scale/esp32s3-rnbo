# SPDX-License-Identifier: MIT
"""Portable tests for the independent event definitions, without DSP execution."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('events_extra_reference',Path(__file__).with_name('reference.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class ExtraEventsReferenceTests(unittest.TestCase):
    def test_shapes_order_hold_and_raw_pilot(self):
        inputs=r.input_words()
        for model in r.MODELS:
            events=r.parameter_events(model)
            self.assertEqual(len(events),21)
            self.assertEqual(events[0],{'before_call':0,'id':'drive','value':1.})
            self.assertEqual([e['before_call']for e in events],sorted(e['before_call']for e in events))
            blocks=r.reference_blocks(model,inputs)
            self.assertEqual(len(blocks),20)
            self.assertEqual(blocks[6],blocks[7])
            self.assertEqual(blocks[12],blocks[13]);self.assertEqual(blocks[13],blocks[14])
            self.assertTrue(all(len(b)==512 and b[1::2]==inputs[1::2]for b in blocks))
            self.assertEqual(r.ABSOLUTE_TOLERANCES[model],0)
        self.assertTrue({0,0x80000000,1,0x80000001,0x00800000}.issubset(inputs[1::2]))
    def test_cold_operands_stores_step_and_last_event(self):
        first={171:1.,172:1.,173:1.,174:-1.,175:2.,176:0.,177:1.,178:0.,179:0.,180:1.,181:1.,182:1.,183:1.,184:0.,185:1.,186:1.,187:0.,188:1.,189:0.,190:1.,191:1.,192:1.,193:2.,194:0.,195:0.}
        for m,x in first.items():
            self.assertEqual(r.reference_words(m,r.input_words())[0],r.word(x))
        for m in(176,179,181,195):
            self.assertEqual(r.reference_blocks(m,r.input_words())[10][0],r.word(1.))
        self.assertEqual(r.reference_blocks(191,r.input_words())[5][0],r.word(-1.))
        self.assertEqual(r.reference_blocks(192,r.input_words())[5][0],r.word(-1.5))
        self.assertEqual(r.reference_blocks(183,r.input_words())[2][0],r.word(0.))
        for m in(179,186,195):
            commands=[e['value']for e in r.parameter_events(m)if e['before_call']==10]
            self.assertNotEqual(r._operation(m,commands[0]),r._operation(m,commands[-1]))
    def test_reverse_divisor_domain_and_remainder_sign(self):
        for m in(193,194):
            self.assertTrue(all(e['value']!=0 for e in r.parameter_events(m)))
        self.assertEqual(r.reference_blocks(193,r.input_words())[5][0],r.word(-4/3))
        self.assertEqual(r.reference_blocks(194,r.input_words())[5][0],r.word(.5))
    def test_denormal_cases_and_finite_nan_scope(self):
        for m in(189,190):
            es=r.parameter_events(m)
            self.assertEqual([r.word(e['value'])for e in es if e['before_call']in(3,4,5,8)],[1,0x80000001,0x007fffff,0x00800000])
        predicate=r.reference_blocks(189,r.input_words());fixed=r.reference_blocks(190,r.input_words())
        for n in(3,4,5):
            self.assertEqual(predicate[n][0],r.word(1.));self.assertEqual(fixed[n][0],r.word(0.))
        self.assertEqual(predicate[8][0],0);self.assertEqual(fixed[8][0],0x00800000)
        for b in r.reference_blocks(187,r.input_words()):self.assertEqual(b[0],0)
        self.assertIn('finite-only',r.REFERENCE_POLICIES[187])
    def test_invalid_input_and_schedule_fail_closed(self):
        for m,x in((True,r.input_words()),(170,r.input_words()),(171,(0,0)),(171,(0x7fc00000,)+r.input_words()[1:])):
            with self.assertRaises(ValueError):r.reference_blocks(m,x)
        for count in(True,0,21,.5):
            with self.assertRaises(ValueError):r.reference_blocks(171,r.input_words(),count)
        events=r.parameter_events(171);events[2],events[3]=events[3],events[2]
        with patch.object(r,'parameter_events',return_value=events):
            with self.assertRaises(ValueError):r.reference_blocks(171,r.input_words())

if __name__=='__main__':unittest.main()
