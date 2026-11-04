# SPDX-License-Identifier: MIT
from decimal import localcontext
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('dbtoa_comparison_reference', HERE/'reference.py')
reference = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(reference)


class DbtoaComparisonReferenceTests(unittest.TestCase):
    def test_all_frozen_vectors_and_expected_words_reproduce_independently(self):
        authored, _ = reference.corpus()
        self.assertEqual(len(set(w for words in authored.values() for w in words)), 705)
        for model, name in reference.MODEL_CASES.items():
            inputs = reference.case_input_words(model)
            expected = reference.reference_words(inputs, 120)
            with self.subTest(model=model):
                self.assertEqual(inputs, authored[name])
                self.assertEqual(len(inputs), 512)
                self.assertEqual(expected, reference.reference_words(inputs, 80))
                self.assertEqual(struct.pack('<512I', *expected),
                                 (HERE/'vectors'/(name+'.expected.f32')).read_bytes())

    def test_catalog_has_exact_matched_vector_round_abba_order(self):
        catalog = json.loads((HERE/'catalog.json').read_text())
        cases = catalog['cases']; self.assertEqual(len(cases), 48)
        self.assertEqual(len({row['id'] for row in cases}), 48)
        digest = hashlib.sha256((HERE/'dbtoa-signal.rnbopat').read_bytes()).hexdigest()
        for model in range(900, 904):
            rows = [row for row in cases if row['model'] == model]
            self.assertEqual(len(rows), 12)
            for round in range(3):
                group = rows[round*4:round*4+4]
                self.assertEqual([r['comparison_phase'] for r in group], ['A','B','B','A'])
                self.assertEqual([r['comparison_order'] for r in group], [0,1,2,3])
                self.assertTrue(all(r['comparison_round'] == round for r in group))
                self.assertEqual([r['numerical_profile'] for r in group],
                                 ['float32-strict','float32-dbtoa-v1','float32-dbtoa-v1','float32-strict'])
            self.assertTrue(all(row['patch_sha256'] == digest and row['exact_name'] == 'dbtoa~'
                                and row['maximum_absolute_error'] == 2e-6 for row in rows))

    def test_zero_endpoint_subnormal_and_monotonic_math(self):
        for bits in (0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000):
            self.assertEqual(reference.reference_word(bits), 0x3f800000)
        self.assertEqual(reference.reference_word(reference.word(-24)), 0x3d813856)
        self.assertEqual(reference.reference_word(reference.word(6)), 0x3fff64c1)
        expected = [reference.reference_word(reference.word(-24+k/16)) for k in range(481)]
        self.assertEqual(expected, sorted(expected))

    def test_nearest_even_is_not_a_binary64_double_round(self):
        with localcontext() as context:
            context.prec = 200
            for low in (0,1,0x007fffff,0x3f800000,0x3f800001):
                midpoint = (reference.exact(low)+reference.exact(low+1))/2
                self.assertEqual(reference.round_decimal(midpoint), low if low % 2 == 0 else low+1)

    def test_domain_and_fixed_vector_guards(self):
        for model, frames in ((True,256),(904,256),(900,255),(900,True)):
            with self.assertRaises(ValueError): reference.case_input_words(model,frames)
        for bits in (0x7f800000,0x7fc00000,reference.word(-24)+1,reference.word(6)+1):
            with self.assertRaises(ValueError): reference.reference_word(bits)
        with self.assertRaises(ValueError): reference.reference_words((0,0))

    def test_changed_bits_are_diagnostic_and_nonfinite_never_passes(self):
        self.assertEqual(reference.ulp_distance_positive(0x3d813855,0x3d813856),1)
        self.assertEqual(reference.ulp_distance_positive(0x3fff64c3,0x3fff64c1),2)
        for bits in (0,0x7f800000,0x7fc00000):
            with self.assertRaises(ValueError): reference.ulp_distance_positive(bits,0x3f800000)


if __name__ == '__main__':
    unittest.main()
