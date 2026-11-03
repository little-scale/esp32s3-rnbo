# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('smoke_numeric',ROOT/'tests/fixtures/smoke/gen-numeric/reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class NumericSmokeReferenceTests(unittest.TestCase):
    def test_halfway_neighbors_are_mathematical_not_intermediate_float_rounding(self):
        source=(0x3effffff,0xbeffffff,0x3f000000,0xbf000000,0x3e7fffff,0xbe7fffff)
        self.assertEqual(reference.reference_words(26,source),(0,0,0x3f800000,0xbf800000,0,0))
        self.assertEqual(reference.reference_words(27,source),(0x3f000000,0xbf000000,0x3f000000,0xbf000000,0,0))

    def test_denormal_predicate_flush_copy_and_negation_bits(self):
        source=(0,0x80000000,1,0x807fffff,0x00800000,0x80800000)
        self.assertEqual(reference.reference_words(33,source),(0,0,0x3f800000,0x3f800000,0,0))
        self.assertEqual(reference.reference_words(34,source),(0,0x80000000,0,0,0x00800000,0x80800000))
        self.assertEqual(reference.reference_words(32,source),source)
        self.assertEqual(reference.reference_words(29,source),tuple(w^0x80000000 for w in source))

    def test_wide_integer_endpoints_and_signed_fraction(self):
        source=(0xcf000000,0x4effffff,0x3fc00000,0xbfc00000)
        self.assertEqual(reference.reference_words(31,source),(0xcf000000,0x4effffff,0x3f800000,0xbf800000))
        self.assertEqual(reference.reference_words(28,source),(0,0,0x3f000000,0xbf000000))
        self.assertEqual(len(reference.WORDS),75)
        self.assertEqual(len(reference.input_words()),512)
        for model in reference.MODELS: self.assertEqual(len(reference.reference_words(model,reference.input_words())),512)

    def test_invalid_domains_and_models_reject(self):
        for source in ((0x7fc00000,0),(0x4f000000,0),(True,0)):
            with self.assertRaises(ValueError):reference.reference_words(31,source)
        with self.assertRaises(ValueError):reference.reference_words(True,(0,0))


if __name__=='__main__':unittest.main()
