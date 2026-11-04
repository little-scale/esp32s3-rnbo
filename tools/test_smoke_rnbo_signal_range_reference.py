# SPDX-License-Identifier: MIT
"""Independent finite references and actual-port source contracts for RNBO signals."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1];DIRECTORY=ROOT/'tests/fixtures/smoke/rnbo-signal-range'
spec=importlib.util.spec_from_file_location('rnbo_signal_range_reference',DIRECTORY/'reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
ID={name:model for model,name in reference.MODEL_NAMES.items()}


class RNBOSignalRangeReferenceTests(unittest.TestCase):
    def evaluate(self,name,a,b):
        return reference.reference_words(ID[name],(reference.word(a),reference.word(b)))

    def test_exact_ranges_passing_comparisons_and_documented_step_are_not_fitted(self):
        w=reference.word
        self.assertEqual(self.evaluate('clamp~',-4,4),(w(-1),w(1)))
        self.assertEqual(self.evaluate('fold~',-3,3),(w(1),w(-1)))
        self.assertEqual(self.evaluate('mix~',-4,4),(w(-2),w(2)))
        self.assertEqual(self.evaluate('cond~',-1,0),(w(1),w(-1)))
        self.assertEqual(self.evaluate('eqp~',-2,-2),(w(-2),w(-2)))
        self.assertEqual(self.evaluate('neqp~',-2,1),(w(-2),w(1)))
        self.assertEqual(self.evaluate('gtp~',2,1),(w(2),w(0)))
        self.assertEqual(self.evaluate('gtep~',1,1),(w(1),w(1)))
        self.assertEqual(self.evaluate('ltp~',-2,1),(w(-2),w(0)))
        self.assertEqual(self.evaluate('ltep~',-2,-2),(w(-2),w(-2)))
        self.assertEqual(self.evaluate('step~',-1,1),(w(0),w(1)))
        self.assertEqual(self.evaluate('step~',-0.,0.),(w(1),w(1)))
        case=next(c for c in json.loads((DIRECTORY/'catalog.json').read_bytes())['cases']if c['exact_name']=='step~')
        self.assertIn('not(in1<in2)',case['scope']);self.assertIn('not a fitted oracle',case['scope'])

    def test_coordinate_returns_smoothstep_edges_interpolation_and_windows(self):
        w=reference.word
        self.assertEqual(self.evaluate('cartopol~',1,-1),(w(math.sqrt(2)),w(-math.pi/4)))
        self.assertEqual(self.evaluate('poltocar~',2,0),(w(2),w(0)))
        self.assertEqual(self.evaluate('smoothstep~',-.5,.5),(w(.15625),w(.84375)))
        self.assertEqual(self.evaluate('linearinterp~',.25,.75),(w(-.5),w(-.5)))
        self.assertEqual(self.evaluate('cosineinterp~',0,1),(w(-1),w(-1)))
        for name,edge in(('hann~',0),('hamming~',.08),('blackman~',0),('welch~',0)):
            pair=self.evaluate(name,0,.5)
            self.assertAlmostEqual(reference.value(pair[0]),edge,places=7);self.assertEqual(pair[1],w(1))

    def test_decay_samples_and_source_specific_shapes_and_quantization(self):
        w=reference.word
        self.assertEqual(self.evaluate('t60~',1,2),(w(.001),w(math.sqrt(.001))))
        outputs=self.evaluate('t60time~',.125,.5)
        self.assertAlmostEqual(reference.value(outputs[0]),math.log(.001)/math.log(.125),places=6)
        self.assertAlmostEqual(reference.value(outputs[1]),math.log(.001)/math.log(.5),places=5)
        self.assertLess(reference.value(outputs[1]),10)
        self.assertEqual(self.evaluate('triangle~',.25,.25),(w(.5),w(1)))
        self.assertEqual(self.evaluate('triangle~',1,1),(w(0),w(0)))
        self.assertEqual(self.evaluate('boxtotri~',.125,.125),(w(.5),w(.25)))
        self.assertEqual(self.evaluate('kink~',.25,.75),(w(.5),w(.625)))
        self.assertEqual(self.evaluate('quantize~',-.125,.0625),(w(0),w(.125)))

    def test_all_predeclared_vectors_constants_and_limits_are_finite(self):
        self.assertEqual(len(reference.MODELS),37)
        for model,name in reference.MODEL_NAMES.items():
            inputs=reference.case_input_words(model);outputs=reference.reference_words(model,inputs)
            self.assertEqual(len(inputs),512);self.assertEqual(len(outputs),512)
            self.assertTrue(all(math.isfinite(reference.value(w))for w in outputs))
            if name in reference.APPROX:self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],1e-3)
            elif name in reference.EXACT or name in reference.CONSTANTS:self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],0)
            else:self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],2e-6)
        for names,bits in((('ln2~','LN2~'),0x3f317218),(('ln10~','LN10~'),0x40135d8e),
                           (('log2e~','LOG2E~'),0x3fb8aa3b),(('log10e~','LOG10E~'),0x3ede5bd9)):
            for name in names:self.assertEqual(self.evaluate(name,0,0),(bits,bits))

    def test_original_patcher_ports_literals_and_two_output_operators_are_explicit(self):
        catalog=json.loads((DIRECTORY/'catalog.json').read_bytes());cases=catalog['cases']
        self.assertEqual(catalog['family'],'rnbo-signal-range');self.assertEqual(len(cases),37)
        self.assertEqual(len({c['exact_name']for c in cases}),37)
        registry={r['id']for r in json.loads((ROOT/'site/data/inventory.json').read_bytes())['spellings']}
        for case in cases:
            self.assertEqual(case['surface'],'patcher');self.assertIn('patcher:'+case['exact_name'],registry)
            self.assertEqual(case['maximum_absolute_error'],reference.ABSOLUTE_TOLERANCES[case['model']])
            patch=json.loads((DIRECTORY/case['patch']).read_bytes())['patcher'];boxes={b['box']['id']:b['box']for b in patch['boxes']}
            lines={(tuple(l['patchline']['source']),tuple(l['patchline']['destination']))for l in patch['lines']}
            self.assertFalse(any(b['text']in('codebox~','gen~')for b in boxes.values()))
            if case['exact_name']in('cartopol~','poltocar~'):
                self.assertNotIn('operator-right',boxes)
                self.assertIn((('operator-left',0),('out-left',0)),lines)
                self.assertIn((('operator-left',1),('out-right',0)),lines)
            elif case['exact_name']=='smoothstep~':
                self.assertEqual(boxes['fixed-low']['text'],'sig~ -1')
                self.assertEqual(boxes['operator-left']['text'],'smoothstep~ 1')
                self.assertIn((('fixed-low',0),('operator-left',0)),lines)
                self.assertIn((('left',0),('operator-left',2)),lines)
                self.assertIn((('right',0),('operator-right',2)),lines)
            elif case['exact_name']in reference.CONSTANTS:
                self.assertEqual(len(lines),2)
            self.assertTrue(case['reference_sources'])
        self.assertFalse({'wrap~','clip~','tri~','gate~','selector~'}&{c['exact_name']for c in cases})

    def test_invalid_models_shapes_nonfinite_and_outside_domains_reject(self):
        w=reference.word
        for model,inputs in((True,(0,0)),(599,(0,0)),(637,(0,0)),(600,()),(600,(0,)),(600,(True,0)),
                           (600,(0x7f800000,0)),(ID['triangle~'],(w(-1),w(0))),
                           (ID['t60~'],(w(0),w(1))),(ID['t60time~'],(w(1),w(.5))),
                           (ID['fastpow~'],(w(-1),w(.5)))):
            with self.subTest(model=model,inputs=inputs),self.assertRaises(ValueError):reference.reference_words(model,inputs)
        for frames in(True,0,16385):
            with self.assertRaises(ValueError):reference.input_words(frames)
        with self.assertRaises(ValueError):reference.case_input_words(599)


if __name__=='__main__':unittest.main()
