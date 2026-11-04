# SPDX-License-Identifier: MIT
"""Portable independent small-array math and exact authored Gen API contracts."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'tests/fixtures/smoke/gen-data-indexed'
spec=importlib.util.spec_from_file_location('gen_data_indexed_reference',DIRECTORY/'reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class GenDataIndexedReferenceTests(unittest.TestCase):
    def blocks(self,model,count=20):
        return reference.reference_blocks(model,reference.case_input_words(model),count)

    def test_dimensions_and_channel_queries_are_metadata_with_explicit_pilots(self):
        w=reference.word
        self.assertEqual(self.blocks(950,1)[0],(w(7),w(2))*256)
        for model,constant in((951,7),(952,2)):
            block=self.blocks(model,1)[0]
            self.assertEqual(set(block[::2]),{w(constant)})
            self.assertEqual(block[1::2],reference.case_input_words(model)[1::2])

    def test_peek_read_before_write_is_exact_seven_sample_fifo_across_blocks(self):
        inputs=reference.case_input_words(953)
        for call,block in enumerate(self.blocks(953,3)):
            for frame in range(256):
                n=call*256+frame
                for ch in(0,1):
                    self.assertEqual(block[2*frame+ch],0 if n<7 else inputs[2*((n-7)%256)+ch])
        self.assertNotEqual(self.blocks(953,2)[0][:2],self.blocks(953,2)[1][:2])

    def test_poke_write_readback_observes_current_left_and_six_sample_right(self):
        inputs=reference.case_input_words(954)
        for call,block in enumerate(self.blocks(954,3)):
            self.assertEqual(block[::2],inputs[::2])
            for frame in range(256):
                n=call*256+frame
                expected=0 if n<6 else inputs[2*((n-6)%256)+1]
                self.assertEqual(block[2*frame+1],expected)
        self.assertIn(0x80000000,self.blocks(954,1)[0][::2])

    def test_asymmetric_nearest_table_and_fractional_linear_queries(self):
        w=reference.word
        nearest=self.blocks(955,1)[0]
        self.assertEqual(nearest[:2],(w(-.75),w(.25)))
        self.assertEqual(set(nearest[::2]),set(map(w,reference.TABLE[0])))
        self.assertEqual(set(nearest[1::2]),set(map(w,reference.TABLE[1])))
        linear=self.blocks(956,1)[0]
        self.assertEqual(linear[:4],(w(-.75),w(-.625),w(-.53125),w(.5)))
        inputs=reference.case_input_words(956)
        for n in range(256):
            for ch in(0,1):
                q=reference.value(inputs[2*n+ch]);lower=int(q);t=q-lower
                a=reference.TABLE[ch][lower];b=reference.TABLE[ch][min(lower+1,6)]
                self.assertEqual(linear[2*n+ch],w(a+t*(b-a)))

    def test_feedback_is_fresh_input_convolution_with_separate_tail_bounds(self):
        w=reference.word
        impulse=[0]*512;impulse[0]=w(.25);impulse[1]=w(.25)
        block=reference.reference_blocks(957,impulse,1)[0]
        self.assertEqual(block[:2],(w(.25),w(.25)))
        self.assertEqual(block[14:16],(w(.125),w(.0625)))
        self.assertEqual(block[28:30],(w(.0625),w(.015625)))
        self.assertEqual(block[2:14],(0,)*12)
        self.assertEqual(reference.FEEDBACK_TAIL_BOUNDS,(2**-65,2**-128/3))
        blocks=self.blocks(957,2)
        self.assertNotEqual(blocks[0][:2],blocks[1][:2])

    def test_all_eight_twenty_block_streams_sources_hashes_and_initialization_once(self):
        catalog=json.loads((DIRECTORY/'catalog.json').read_bytes())
        self.assertEqual(catalog['family'],'gen-data-indexed')
        self.assertEqual(len(catalog['cases']),8)
        self.assertEqual(catalog['automatic_warmup_blocks'],0)
        self.assertEqual(catalog['reference_sha256'],hashlib.sha256((DIRECTORY/'reference.py').read_bytes()).hexdigest())
        self.assertEqual(catalog['generator_sha256'],hashlib.sha256((DIRECTORY/'generate.py').read_bytes()).hexdigest())
        spec=importlib.util.spec_from_file_location('gen_data_indexed_generator',DIRECTORY/'generate.py')
        generator=importlib.util.module_from_spec(spec);old=sys.modules.get('reference')
        try:
            sys.modules['reference']=reference;spec.loader.exec_module(generator)
        finally:
            if old is None:sys.modules.pop('reference',None)
            else:sys.modules['reference']=old
        for case in catalog['cases']:
            model=case['model'];inputs=reference.case_input_words(model)
            blocks=reference.reference_blocks(model,inputs)
            self.assertEqual(len(blocks),20)
            self.assertTrue(all(len(b)==512 for b in blocks))
            self.assertTrue(all(math.isfinite(reference.value(w))for b in blocks for w in b))
            self.assertEqual(reference.reference_words(model,inputs),blocks[0])
            self.assertEqual(case['maximum_absolute_error'],2e-6 if model in(956,957)else 0)
            code=(DIRECTORY/case['genexpr']).read_text()
            self.assertEqual(code,generator.expression(model))
            self.assertEqual(case['genexpr_sha256'],hashlib.sha256(code.encode()).hexdigest())
            patch=(DIRECTORY/case['patch']).read_bytes()
            self.assertEqual(case['patch_sha256'],hashlib.sha256(patch).hexdigest())
            self.assertEqual(json.loads(patch),generator.graph(code))
            self.assertTrue(code.startswith('Data memory(7, 2);\n'))
            self.assertNotIn('Buffer ',code)
            if model>=953:
                self.assertEqual(code.count('if (initialized == 0)'),1)
                start=code.index('if (initialized == 0)')
                finish=code.index('    initialized = 1;',start)
                self.assertEqual(code[start:finish].count('poke(memory,'),14)
            if model in(953,954,957):
                self.assertEqual(code.count('History cursor(0);'),1)
                self.assertIn('cursor = nextIndex;',code)
        data_cases=[c for c in catalog['cases']if c['exact_name']=='Data']
        self.assertEqual(len(data_cases),2)
        self.assertTrue(all(c['owner_kind']=='declaration'and c['registry_lookup']=='data'for c in data_cases))

    def test_invalid_shapes_types_index_units_and_domains_reject(self):
        for model in(True,949,958):
            with self.assertRaises(ValueError):reference.case_input_words(model)
        for frames in(True,0,255,257):
            with self.assertRaises(ValueError):reference.input_words(frames)
        for count in(True,0,21):
            with self.assertRaises(ValueError):self.blocks(953,count)
        for model,bad in((953,reference.word(.5)),(955,reference.word(6.5)),
                          (955,reference.word(.5)),(956,reference.word(.125)),
                          (956,reference.word(-.25)),(957,0x7f800000)):
            inputs=list(reference.case_input_words(model));inputs[0]=bad
            with self.subTest(model=model),self.assertRaises(ValueError):reference.reference_blocks(model,inputs)
        for inputs in((),(0,),[0]*511,[0]*511+[True]):
            with self.assertRaises(ValueError):reference.reference_blocks(953,inputs)


if __name__=='__main__':unittest.main()
