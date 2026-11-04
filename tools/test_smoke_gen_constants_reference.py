# SPDX-License-Identifier: MIT
"""Independent GenExpr constant words and separately authored bare-value fixtures."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1];DIRECTORY=ROOT/'tests/fixtures/smoke/gen-constants'
spec=importlib.util.spec_from_file_location('gen_constants_reference',DIRECTORY/'reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class GenConstantsReferenceTests(unittest.TestCase):
    def test_independent_known_binary32_math_and_audio_config_values(self):
        expected={400:0x40490fdb,401:0x3fc90fdb,402:0x40c90fdb,403:0x402df854,404:0x3ea2f983,
                  405:0x3fcf1bbd,406:0x3f3504f3,407:0x3fb504f3,408:0x3c8efa35,409:0x42652ee1,
                  410:0x3f317218,411:0x40135d8e,412:0x3fb8aa3b,413:0x3ede5bd9,
                  414:0x472c4400,415:0x43800000}
        for model,bits in expected.items():
            with self.subTest(model=model):self.assertEqual(reference.reference_words(model,(0,0)),(bits,bits))
        self.assertEqual(reference.RATE,44100);self.assertEqual(reference.BLOCK_FRAMES,256)
        self.assertEqual(reference.VALUES[415],256) # Audio configuration, never fitted to inner lowering.

    def test_thirty_two_exact_gen_names_are_separately_authored_bare_values(self):
        catalog=json.loads((DIRECTORY/'catalog.json').read_bytes());cases=catalog['cases']
        self.assertEqual(catalog['family'],'gen-constants');self.assertEqual(len(cases),32)
        self.assertEqual(len({c['exact_name']for c in cases}),32);self.assertEqual(len({c['patch']for c in cases}),32)
        registry={r['exact_name']:r for r in json.loads((ROOT/'site/data/gen-inventory.json').read_bytes())['RNBO_GenExpr_registry_entries']}
        self.assertNotIn('PI_OVER_2',registry);self.assertNotIn('PI_OVER_4',registry)
        for case in cases:
            with self.subTest(case=case['id']):
                self.assertEqual(case['surface'],'genexpr');self.assertEqual(case['syntax'],'named-value')
                self.assertEqual(case['canonical_name'],registry[case['exact_name']]['canonical'])
                self.assertEqual(case['arity'],0);self.assertEqual(case['signal_inputs_per_instance'],0)
                source=(DIRECTORY/case['genexpr']).read_text()
                self.assertEqual(source,'out1 = '+case['exact_name']+';\nout2 = '+case['exact_name']+';\n')
                patch=json.loads((DIRECTORY/case['patch']).read_bytes())['patcher'];boxes={b['box']['id']:b['box']for b in patch['boxes']}
                self.assertEqual(len(boxes),5);self.assertEqual({b['text']for b in boxes.values()},{'in~ 1','in~ 2','gen~','out~ 1','out~ 2'})
                self.assertEqual(boxes['gen']['rnbo_extra_attributes']['expr'],source)
                self.assertEqual(len(patch['lines']),2);self.assertTrue(all(l['patchline']['source'][0]=='gen'for l in patch['lines']))
                self.assertTrue(case['reference_sources'])

    def test_math_alias_and_configuration_pairs_have_distinct_original_sources(self):
        cases=json.loads((DIRECTORY/'catalog.json').read_bytes())['cases']
        for model in reference.MODELS:
            pair=[c for c in cases if c['model']==model]
            self.assertEqual(len(pair),2);self.assertNotEqual(pair[0]['patch'],pair[1]['patch'])
            self.assertNotEqual(pair[0]['genexpr'],pair[1]['genexpr'])
            self.assertEqual(pair[0]['canonical_name'],pair[1]['canonical_name'])
        self.assertEqual({c['exact_name']for c in cases if c['model']==414},{'SAMPLERATE','samplerate'})
        self.assertEqual({c['exact_name']for c in cases if c['model']==415},{'VECTORSIZE','vectorsize'})

    def test_all_frozen_constant_outputs_are_finite_ignore_inputs_and_predeclare_exact_gate(self):
        self.assertEqual(len(reference.MODELS),16);inputs=reference.input_words()
        self.assertEqual(len(inputs),512);self.assertIn(0,inputs);self.assertIn(0x80000000,inputs)
        for model in reference.MODELS:
            with self.subTest(model=model):
                self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],0)
                pair=reference.reference_words(model,(0x7f7fffff,0xff7fffff))
                self.assertEqual(reference.reference_words(model,inputs),pair*256)
                self.assertTrue(all(math.isfinite(reference.value(w))for w in pair))
                self.assertEqual(reference.case_input_words(model),inputs)

    def test_invalid_models_nonfinite_words_and_vector_shapes_reject(self):
        for model,inputs in((True,(0,0)),(399,(0,0)),(416,(0,0)),(400,()),(400,(0,)),
                           (400,(True,0)),(400,(0x7f800000,0)),(400,(0xffc00000,0)),(400,(-1,0))):
            with self.subTest(model=model,inputs=inputs),self.assertRaises(ValueError):reference.reference_words(model,inputs)
        for frames in(True,0,16385):
            with self.assertRaises(ValueError):reference.input_words(frames)
        with self.assertRaises(ValueError):reference.case_input_words(399)


if __name__=='__main__':unittest.main()
