# SPDX-License-Identifier: MIT
"""Portable independent reference and original-source contracts; no hardware."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT/'tests/fixtures/smoke/rnbo-signal-routing'
spec = importlib.util.spec_from_file_location('rnbo_signal_routing_reference', DIRECTORY/'reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
ID = {name: model for model, name in reference.MODEL_NAMES.items()}


class RNBOSignalRoutingReferenceTests(unittest.TestCase):
    def evaluate(self, name, x, y):
        return reference.reference_words(ID[name], (reference.word(x), reference.word(y)))

    def test_gate_two_outlets_and_selector_all_three_choices(self):
        w = reference.word
        for control, gate, select in ((0, (0,0), (0,-2)), (1, (-2,0), (-2,-2)),
                                      (2, (0,-2), (2,-2))):
            self.assertEqual(self.evaluate('gate~', control, -2), tuple(map(w, gate)))
            self.assertEqual(self.evaluate('selector~', control, -2), tuple(map(w, select)))
        self.assertEqual(self.evaluate('gate~', -0., 1), (0,0))
        for name in ('gate~','selector~'):
            words = reference.case_input_words(ID[name])
            pairs = {(reference.value(words[n]), reference.value(words[n+1]))
                     for n in range(0,512,2)}
            self.assertEqual({p[0] for p in pairs}, {0,1,2})
            self.assertEqual(len(pairs), 45)  # fifteen numeric data values, both zero signs

    def test_local_buses_retain_all_input_words_and_aliases_have_separate_models(self):
        inputs = reference.case_input_words(ID['send~'])
        self.assertIn(0x80000000, inputs)
        for name in reference.BUSES:
            self.assertEqual(reference.reference_words(ID[name], inputs), inputs)
        self.assertEqual(len(set(ID.values())),20)
        self.assertEqual(len({ID[name] for name in reference.BUSES}),4)

    def test_symbolic_comparisons_return_left_operand_and_boolean_aliases(self):
        w = reference.word
        expected = {'==p~':(-2,-2), '!=p~':(0,0), '>p~':(0,0),
                    '>=p~':(-2,-2), '<p~':(0,0), '<=p~':(-2,-2),
                    'equals~':(1,1), 'lessthan~':(0,0), 'minus~':(0,0)}
        for name, pair in expected.items():
            self.assertEqual(self.evaluate(name,-2,-2),tuple(map(w,pair)))
        self.assertEqual(self.evaluate('>p~',2,-1),(w(2),w(0)))
        self.assertEqual(self.evaluate('<p~',2,-1),(w(0),w(-1)))
        self.assertEqual(self.evaluate('minus~',2,-1),(w(3),w(-3)))
        self.assertEqual(self.evaluate('lessthan~',2,-1),(w(0),w(1)))
        self.assertEqual(self.evaluate('?~',-0.,-1),(w(-1),w(-1)))
        self.assertEqual(self.evaluate('?~',1,0),(w(1),w(1)))

    def test_asymmetric_interpolation_conventions_and_independent_basis_identities(self):
        # Endpoint constraints and exact reproduction of a cubic for Lagrange.
        for name in ('cubicinterp~','fastcubicinterp~','splineinterp~'):
            for points in reference.C4:
                self.assertAlmostEqual(reference.interpolate(name,0,points),points[1],places=14)
                self.assertAlmostEqual(reference.interpolate(name,1,points),points[2],places=14)
        polynomial = lambda x: 2*x**3-3*x*x+.5*x-1
        points = tuple(polynomial(x) for x in (-1,0,1,2))
        for t in (0,.125,.5,.875,1):
            self.assertAlmostEqual(reference.interpolate('cubicinterp~',t,points),polynomial(t),places=13)
        # Full/half neighbor slopes give distinct quarter-phase predictions.
        self.assertEqual(reference.interpolate('fastcubicinterp~',.25,reference.C4[0]), .69921875)
        self.assertEqual(reference.interpolate('splineinterp~',.25,reference.C4[0]), .552734375)
        weights = (1/120,13/60,11/20,13/60,1/120,0)
        for i, expected in enumerate(weights):
            impulse = tuple(float(j == i) for j in range(6))
            self.assertAlmostEqual(reference.spline6(0,impulse),expected,places=13)
        for t in (0,.125,.5,.875,1):
            self.assertAlmostEqual(reference.spline6(t,(1,)*6),1,places=12)
        self.assertNotEqual(reference.spline6(0,reference.C6[0]),reference.C6[0][2])

    def test_all_twenty_predeclared_vectors_outputs_limits_and_hash_bindings(self):
        catalog = json.loads((DIRECTORY/'catalog.json').read_bytes())
        cases = catalog['cases']
        self.assertEqual(len(cases),20)
        self.assertEqual(tuple(c['exact_name'] for c in cases),reference.NAMES)
        self.assertEqual(catalog['reference_sha256'],hashlib.sha256((DIRECTORY/'reference.py').read_bytes()).hexdigest())
        self.assertEqual(catalog['generator_sha256'],hashlib.sha256((DIRECTORY/'generate.py').read_bytes()).hexdigest())
        inventory = {r['id'] for r in json.loads((ROOT/'site/data/inventory.json').read_bytes())['spellings']}
        for case in cases:
            model,name = case['model'],case['exact_name']
            inputs = reference.case_input_words(model)
            outputs = reference.reference_words(model,inputs)
            self.assertEqual(len(inputs),512)
            self.assertEqual(len(outputs),512)
            self.assertTrue(all(math.isfinite(reference.value(w)) for w in outputs))
            self.assertIn('patcher:'+name,inventory)
            self.assertEqual(case['maximum_absolute_error'],2e-6 if name in reference.INTERPOLATORS else 0)
            self.assertEqual(case['patch_sha256'],hashlib.sha256((DIRECTORY/case['patch']).read_bytes()).hexdigest())
            self.assertTrue(case['reference_sources'])
        for name in reference.INTERPOLATORS:
            values = reference.case_input_words(ID[name])
            self.assertEqual(set(values[::2]),set(reference.PHASE))
            self.assertEqual(set(values[1::2]),set(reference.PHASE))

    def test_original_graph_sources_routes_literals_and_generator_are_consistent(self):
        spec = importlib.util.spec_from_file_location('signal_routing_generator',DIRECTORY/'generate.py')
        generator = importlib.util.module_from_spec(spec)
        old_reference = sys.modules.get('reference')
        try:
            sys.modules['reference'] = reference
            spec.loader.exec_module(generator)
        finally:
            if old_reference is None: sys.modules.pop('reference',None)
            else: sys.modules['reference'] = old_reference
        for case in json.loads((DIRECTORY/'catalog.json').read_bytes())['cases']:
            name = case['exact_name']
            patch = json.loads((DIRECTORY/case['patch']).read_bytes())
            self.assertEqual(patch,generator.graph(name))
            patch = patch['patcher']
            boxes = {r['box']['id']:r['box'] for r in patch['boxes']}
            lines = {(tuple(r['patchline']['source']),tuple(r['patchline']['destination'])) for r in patch['lines']}
            self.assertEqual(len(lines),len(patch['lines']))
            self.assertEqual({b['maxclass'] for b in boxes.values()},{'newobj'})
            self.assertFalse(any(b['text'] in ('gen~','codebox~') for b in boxes.values()))
            if name == 'gate~':
                self.assertEqual(boxes['operator']['text'],'gate~ 2 0 0')
                self.assertIn((('operator',1),('out-right',0)),lines)
            elif name == 'selector~':
                self.assertIn((('negated-data',0),('operator',2)),lines)
                self.assertIn((('right',0),('out-right',0)),lines)
            elif name in reference.BUSES:
                self.assertEqual(len(lines),4)
                for lane in (0,1):
                    sender = boxes['sender-'+str(lane)]['text'].split()
                    receiver = boxes['receiver-'+str(lane)]['text'].split()
                    self.assertEqual(sender[1],receiver[1])
                    self.assertTrue(name in (sender[0],receiver[0]))
                self.assertNotEqual(boxes['sender-0']['text'].split()[1],boxes['sender-1']['text'].split()[1])

    def test_invalid_models_words_router_choices_and_phase_domains_reject(self):
        w = reference.word
        for model,inputs in ((True,(0,0)),(799,(0,0)),(820,(0,0)),(800,()),
                             (800,(0,)),(800,(True,0)),(800,(0x7f800000,0)),
                             (800,(w(3),w(0))),(801,(w(.5),w(0))),
                             (806,(w(-.1),w(0))),(809,(w(1.1),w(0))),
                             (802,(w(4.1),w(0)))):
            with self.subTest(model=model,inputs=inputs),self.assertRaises(ValueError):
                reference.reference_words(model,inputs)
        for frames in (True,0,16385):
            with self.assertRaises(ValueError): reference.input_words(frames)


if __name__ == '__main__':
    unittest.main()
