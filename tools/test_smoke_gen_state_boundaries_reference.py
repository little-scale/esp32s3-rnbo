# SPDX-License-Identifier: MIT
"""Portable stream, boundary and original Gen source-contract checks."""
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT/'tests/fixtures/smoke/gen-state-boundaries'
spec = importlib.util.spec_from_file_location('gen_state_boundaries_reference',DIRECTORY/'reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class GenStateBoundariesReferenceTests(unittest.TestCase):
    def blocks(self, model, count=20):
        return reference.reference_blocks(model,reference.case_input_words(model),count)

    def test_exact_phasor_periods_and_reset_order_cross_callback_boundary(self):
        w = reference.word
        blocks = self.blocks(820,5)
        for call,block in enumerate(blocks):
            for frame in (0,1,127,255):
                n = call*256+frame
                self.assertEqual(block[2*frame],w(float(Fraction(3*n,1024) % 1)))
                self.assertEqual(block[2*frame+1],w(float(Fraction(5*n,2048) % 1)))
        self.assertEqual(blocks[1][:2],(w(.75),w(.625)))
        self.assertNotEqual(blocks[0],blocks[1])
        reset = self.blocks(821,2)
        self.assertEqual(reset[0][:6],(w(.125),w(.375),w(.125),w(.375+5/2048),
                                      w(.125+3/1024),w(.375+10/2048)))
        self.assertEqual(reset[0][510],w(.125))
        self.assertEqual(reset[1][:2],(w(.125+3/1024),w(.375)))

    def test_train_odd_periods_and_wrapped_onset_with_width_endpoints(self):
        w = reference.word
        fixed = self.blocks(822,2)
        self.assertEqual(tuple(reference.value(fixed[0][2*n]) for n in range(8)),(1,1,1,1,0,0,0,1))
        self.assertEqual(fixed[1][:2],(w(0),w(1)))
        variable = self.blocks(823,2)
        vector = reference.case_input_words(823)
        for call,block in enumerate(variable):
            for frame in range(256):
                for ch,period in enumerate((7,11)):
                    width = Fraction(reference.value(vector[2*frame+ch]))
                    phase = (Fraction((256*call+frame) % period,period)-Fraction(1,4)) % 1
                    self.assertEqual(block[2*frame+ch],w(float(phase < width)))

    def test_rate_time_multiplier_division_unwraps_and_carries_period_512(self):
        w = reference.word
        for call,block in enumerate(self.blocks(824,3)):
            for frame in range(256):
                n = 256*call+frame
                self.assertEqual(block[2*frame],w(float(Fraction(n,512) % 1)))
                self.assertEqual(block[2*frame+1],w(float(Fraction(n,512) % 1)))
        self.assertEqual(self.blocks(824,2)[1][:2],(w(.5),w(.5)))

    def test_nonzero_multiplication_post_reset_is_not_a_trivial_zero_model(self):
        w = reference.word
        blocks = self.blocks(825,2)
        self.assertEqual(blocks[0][:8],(w(1),w(1),w(.5),w(2),w(-.5),w(-2),w(.5),w(2)))
        for call,block in enumerate(blocks):
            for frame in (0,17,127,255):
                self.assertEqual(block[2*frame:2*frame+2],(w(1),w(1)))
            self.assertTrue(all(abs(reference.value(v)) <= 2 for v in block))
        self.assertGreater(len(set(blocks[0])),4)

    def test_delay_fifo_reads_previous_sample_and_feedback_uses_closed_convolution(self):
        inputs = reference.case_input_words(826)
        blocks = self.blocks(826,2)
        self.assertEqual(blocks[0][:2],(0,0))
        for call,block in enumerate(blocks):
            for frame in range(256):
                for ch,delay in enumerate((1,3)):
                    n = call*256+frame-delay
                    expected = 0 if n < 0 else inputs[2*(n % 256)+ch]
                    self.assertEqual(block[2*frame+ch],expected)
        self.assertNotEqual(blocks[1][0],blocks[0][0])
        impulse = [0]*512
        impulse[0] = reference.word(.25)
        feedback = reference.reference_blocks(827,impulse,1)[0]
        self.assertEqual(feedback[0],reference.word(.25))
        self.assertEqual(feedback[6],reference.word(.125))
        self.assertEqual(feedback[12],reference.word(.0625))
        self.assertEqual(feedback[2],0)
        self.assertEqual(feedback[384],0)  # term64 omitted, bounded by the predeclared tail
        self.assertEqual(reference.FEEDBACK_TAIL_BOUND,2**-65)

    def test_all_eight_complete_streams_limits_and_source_hashes(self):
        catalog = json.loads((DIRECTORY/'catalog.json').read_bytes())
        self.assertEqual(catalog['family'],'gen-state-boundaries')
        self.assertEqual(catalog['automatic_warmup_blocks'],0)
        self.assertEqual(catalog['reference_sha256'],hashlib.sha256((DIRECTORY/'reference.py').read_bytes()).hexdigest())
        self.assertEqual(catalog['generator_sha256'],hashlib.sha256((DIRECTORY/'generate.py').read_bytes()).hexdigest())
        self.assertEqual(len(catalog['cases']),8)
        spec = importlib.util.spec_from_file_location('gen_state_boundary_generator',DIRECTORY/'generate.py')
        generator = importlib.util.module_from_spec(spec)
        previous = sys.modules.get('reference')
        try:
            sys.modules['reference'] = reference
            spec.loader.exec_module(generator)
        finally:
            if previous is None: sys.modules.pop('reference',None)
            else: sys.modules['reference'] = previous
        for case in catalog['cases']:
            model = case['model']
            inputs = reference.case_input_words(model)
            blocks = reference.reference_blocks(model,inputs)
            self.assertEqual(len(blocks),20)
            self.assertTrue(all(len(b)==512 for b in blocks))
            self.assertTrue(all(math.isfinite(reference.value(w)) for b in blocks for w in b))
            self.assertEqual(reference.reference_words(model,inputs),blocks[0])
            self.assertEqual(case['maximum_absolute_error'],2e-6 if model==827 else 0)
            source = (DIRECTORY/case['genexpr']).read_bytes()
            patch = (DIRECTORY/case['patch']).read_bytes()
            self.assertEqual(case['genexpr_sha256'],hashlib.sha256(source).hexdigest())
            self.assertEqual(case['patch_sha256'],hashlib.sha256(patch).hexdigest())
            self.assertEqual(json.loads(patch),generator.graph(source.decode()))
            graph = json.loads(patch)['patcher']
            self.assertEqual({b['box']['text'] for b in graph['boxes']},
                             {'in~ 1','in~ 2','gen~','out~ 1','out~ 2'})
        sources = {c['id']:(DIRECTORY/c['genexpr']).read_text() for c in catalog['cases']}
        self.assertIn('init=1, min=1, resetmode="post"',sources['mulequals-nonzero-init-post-reset'])
        self.assertIn('read(1, interp="none")',sources['delay-one-and-three-samples'])
        self.assertLess(sources['delay-one-and-three-samples'].index('.read('),
                        sources['delay-one-and-three-samples'].index('.write('))

    def test_reject_invalid_shapes_nonfinite_choices_and_domains(self):
        w = reference.word
        for model in (True,819,828):
            with self.assertRaises(ValueError): reference.case_input_words(model)
        for frames in (True,0,255,257):
            with self.assertRaises(ValueError): reference.input_words(frames)
        for count in (True,0,21):
            with self.assertRaises(ValueError): self.blocks(820,count)
        for model,index,bad in ((821,0,w(.25)),(823,1,w(2)),(824,0,w(1)),
                                (825,0,0),(825,1,w(.5)),(826,0,w(.5)),(827,0,0x7f800000)):
            inputs = list(reference.case_input_words(model));inputs[index] = bad
            with self.subTest(model=model),self.assertRaises(ValueError):
                reference.reference_blocks(model,inputs)
        for inputs in ((),(0,),[0]*511,[0]*511+[True]):
            with self.assertRaises(ValueError): reference.reference_blocks(820,inputs)


if __name__ == '__main__':
    unittest.main()
