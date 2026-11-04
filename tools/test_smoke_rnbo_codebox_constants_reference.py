# SPDX-License-Identifier: MIT
"""Portable independent constant bits and exact RNBO-codebox source checks."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'tests/fixtures/smoke/rnbo-codebox-constants'
spec=importlib.util.spec_from_file_location('rnbo_codebox_constants_reference',DIRECTORY/'reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class RNBOCodeboxConstantsReferenceTests(unittest.TestCase):
    def test_ideal_mathematical_constants_have_known_nearest_binary32_words(self):
        expected={250:0x3fc90fdb,251:0x3f490fdb,252:0x402df854,253:0x3ea2f983,254:0x3fcf1bbd,
                  255:0x40490fdb,256:0x3f3504f3,257:0x3fb504f3,258:0x40c90fdb,259:0x3c8efa35,
                  260:0x42652ee1,261:0x3f317218,262:0x40135d8e,263:0x3fb8aa3b,264:0x3ede5bd9}
        for model,bits in expected.items():
            with self.subTest(model=model):self.assertEqual(reference.reference_words(model,(0,0)),(bits,bits))

    def test_character_constants_are_numeric_ascii_codes_not_numeric_digits(self):
        catalog=json.loads((DIRECTORY/'catalog.json').read_bytes());characters=[c for c in catalog['cases']if c['exact_name'].startswith('CHAR_')]
        self.assertEqual(len(characters),10)
        for n in range(10):
            case=next(c for c in characters if c['exact_name']=='CHAR_'+str(n))
            output=reference.reference_words(case['model'],(0,0))
            self.assertEqual(tuple(reference.value(w)for w in output),(float(48+n),)*2)
            self.assertNotEqual(output,(reference.word(n),)*2)
            self.assertTrue(any(r['local_package_path']=='source/operators/characterconstants.json'and
                r['sha256']=='eb17d1aea665bcf01b03930d1c20dcf55a1c2918dc355a266254a8fe7c0652e0'for r in case['reference_sources']))

    def test_forty_independent_named_value_fixtures_are_codebox_not_genexpr(self):
        cases=json.loads((DIRECTORY/'catalog.json').read_bytes())['cases']
        self.assertEqual(len(cases),40);self.assertEqual(len({c['exact_name']for c in cases}),40)
        self.assertEqual(len({c['patch']for c in cases}),40)
        registry={r['id']:r for r in json.loads((ROOT/'site/data/inventory.json').read_bytes())['spellings']}
        for case in cases:
            with self.subTest(case=case['id']):
                self.assertEqual(case['surface'],'codebox');self.assertEqual(case['syntax'],'named-value')
                self.assertEqual(case['arity'],0);self.assertEqual(case['signal_inputs_per_instance'],0)
                self.assertIn('codebox:'+case['exact_name'],registry)
                patch=json.loads((DIRECTORY/case['patch']).read_bytes())['patcher']
                boxes={b['box']['id']:b['box']for b in patch['boxes']}
                self.assertEqual(len(boxes),5)
                self.assertEqual({b['text']for b in boxes.values()},{'in~ 1','in~ 2','codebox~','out~ 1','out~ 2'})
                code=boxes['program']['rnbo_extra_attributes']['code']
                self.assertEqual(code,'out1 = '+case['exact_name']+';\nout2 = '+case['exact_name']+';\n')
                self.assertEqual(len(patch['lines']),2)
                self.assertEqual({tuple(l['patchline']['destination'])for l in patch['lines']},{('out-left',0),('out-right',0)})
                self.assertTrue(all(l['patchline']['source'][0]=='program'for l in patch['lines']))
                self.assertTrue(case['reference_sources'])

    def test_all_twenty_five_models_ignore_inputs_and_keep_zero_tolerance(self):
        self.assertEqual(len(reference.MODELS),25)
        inputs=reference.input_words();self.assertEqual(len(inputs),512)
        self.assertIn(0,inputs);self.assertIn(0x80000000,inputs)
        for model in reference.MODELS:
            with self.subTest(model=model):
                self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],0)
                pair=reference.reference_words(model,(0x7f7fffff,0xff7fffff))
                self.assertEqual(reference.reference_words(model,inputs),pair*256)
                self.assertTrue(all(math.isfinite(reference.value(w))for w in pair))
                self.assertEqual(reference.case_input_words(model),inputs)

    def test_invalid_models_nonfinite_words_and_vector_shapes_reject(self):
        for model,inputs in((True,(0,0)),(249,(0,0)),(275,(0,0)),(255,()),(255,(0,)),
                           (255,(True,0)),(255,(0x7f800000,0)),(255,(0xffc00000,0)),(255,(-1,0))):
            with self.subTest(model=model,inputs=inputs),self.assertRaises(ValueError):reference.reference_words(model,inputs)
        for frames in(True,0,16385):
            with self.assertRaises(ValueError):reference.input_words(frames)
        with self.assertRaises(ValueError):reference.case_input_words(249)


if __name__=='__main__':unittest.main()
