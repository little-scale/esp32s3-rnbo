# SPDX-License-Identifier: MIT
"""Independent constant bits and exact original fixture spelling checks; no RNBO/device."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'tests/fixtures/smoke/rnbo-constants'
spec=importlib.util.spec_from_file_location('rnbo_constants_reference',DIRECTORY/'reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class RNBOConstantsReferenceTests(unittest.TestCase):
    def test_mathematical_constants_round_to_independent_known_binary32_words(self):
        # Standard nearest binary32 encodings; neither generated RNBO output nor
        # a producer constant table supplies these expected values.
        words={200:0x3fc90fdb,201:0x3f490fdb,202:0x402df854,203:0x3ea2f983,
               204:0x3fcf1bbd,205:0x40490fdb,206:0x3f3504f3,207:0x3fb504f3,208:0x40c90fdb}
        for model,bits in words.items():
            with self.subTest(model=model):self.assertEqual(reference.reference_words(model,(0,0)),(bits,bits))
        self.assertEqual(reference.RATE,44100);self.assertEqual(reference.BLOCK_FRAMES,256)
        self.assertEqual(reference.reference_words(210,(0,0)),(0x472c4400,)*2)
        self.assertEqual(reference.reference_words(211,(0,0)),(0x43800000,)*2)
        self.assertEqual(reference.reference_words(209,(0,0)),(0x3e800000,0xbf000000))

    def test_all_models_are_autonomous_finite_and_predeclare_exact_tolerance(self):
        inputs=reference.input_words();self.assertEqual(len(inputs),512)
        self.assertIn(0,inputs);self.assertIn(0x80000000,inputs)
        self.assertEqual(set(reference.ABSOLUTE_TOLERANCES),set(reference.MODELS))
        for model in reference.MODELS:
            with self.subTest(model=model):
                self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],0)
                output=reference.reference_words(model,inputs)
                pair=reference.reference_words(model,(0x7f7fffff,0xff7fffff))
                self.assertEqual(output,pair*256)
                self.assertTrue(all(math.isfinite(reference.value(w))for w in output))
                self.assertEqual(reference.case_input_words(model),inputs)

    def test_twenty_one_exact_authored_spellings_and_stereo_initial_mode(self):
        catalog=json.loads((DIRECTORY/'catalog.json').read_bytes());cases=catalog['cases']
        self.assertEqual(catalog['family'],'rnbo-constants');self.assertEqual(len(cases),21)
        self.assertEqual(len({c['id']for c in cases}),21);self.assertEqual(len({c['exact_name']for c in cases}),21)
        registry={r['id']:r for r in json.loads((ROOT/'site/data/inventory.json').read_bytes())['spellings']}
        for case in cases:
            with self.subTest(case=case['id']):
                self.assertIn('patcher:'+case['exact_name'],registry)
                self.assertEqual(case['surface'],'patcher');self.assertEqual(case['signal_inputs_per_instance'],0)
                self.assertEqual(case['maximum_absolute_error'],0)
                patch=json.loads((DIRECTORY/case['patch']).read_bytes())['patcher']
                boxes={b['box']['id']:b['box']for b in patch['boxes']}
                self.assertEqual(boxes['left']['text'],'in~ 1');self.assertEqual(boxes['right']['text'],'in~ 2')
                suffixes=(' 0.25',' -0.5')if case['model']==209 else('','')
                self.assertEqual(boxes['operator-left']['text'],case['exact_name']+suffixes[0])
                self.assertEqual(boxes['operator-right']['text'],case['exact_name']+suffixes[1])
                self.assertEqual(len(patch['lines']),2)
                self.assertTrue(all(line['patchline']['source'][0].startswith('operator-')for line in patch['lines']))
                self.assertTrue(case['reference_sources'])
        sig=next(c for c in cases if c['exact_name']=='sig~')
        self.assertEqual(sig['initial_values'],[.25,-.5]);self.assertIn('initial values only',sig['scope'])

    def test_aliases_have_separate_fixtures_without_inheriting_execution(self):
        cases=json.loads((DIRECTORY/'catalog.json').read_bytes())['cases'];byname={c['exact_name']:c for c in cases}
        for lower,upper in(('e~','E~'),('halfpi~','HALFPI~'),('invpi~','INVPI~'),('phi~','PHI~'),
                          ('pi~','PI~'),('sqrt1_2~','SQRT1_2~'),('sqrt2~','SQRT2~'),('twopi~','TWOPI~')):
            self.assertNotEqual(byname[lower]['patch'],byname[upper]['patch'])
            self.assertEqual(byname[lower]['model'],byname[upper]['model'])
            self.assertEqual(byname[lower]['canonical_name'],byname[upper]['canonical_name'])

    def test_invalid_models_nonfinite_words_and_vector_shapes_reject(self):
        for model,inputs in((True,(0,0)),(199,(0,0)),(212,(0,0)),(205,()),(205,(0,)),
                           (205,(True,0)),(205,(0x7f800000,0)),(205,(0xffc00000,0)),(205,(-1,0))):
            with self.subTest(model=model,inputs=inputs),self.assertRaises(ValueError):reference.reference_words(model,inputs)
        for frames in(True,0,16385):
            with self.assertRaises(ValueError):reference.input_words(frames)
        with self.assertRaises(ValueError):reference.case_input_words(199)


if __name__=='__main__':unittest.main()
