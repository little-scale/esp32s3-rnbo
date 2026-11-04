# SPDX-License-Identifier: MIT
"""Independent ASCII values, word-copy pilot and exact partition/source checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import string
import unittest

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'tests/fixtures/smoke/rnbo-character-constants'
spec=importlib.util.spec_from_file_location('rnbo_character_reference',DIRECTORY/'reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class CharacterConstantReferenceTests(unittest.TestCase):
    def test_independent_character_definitions_cover_printable_ascii_except_digits(self):
        expected=set(range(32,127))-{ord(c)for c in string.digits}
        self.assertEqual(len(reference.CHARACTERS),85)
        self.assertEqual({ord(c)for c in reference.CHARACTERS.values()},expected)
        for name,char in {'CHAR_A':'A','CHAR_a':'a','CHAR_SPACE':' ','CHAR_QUOTE':'"',
                          'CHAR_APOS':"'",'CHAR_BACKSLASH':'\\','CHAR_BACKTICK':'`',
                          'CHAR_AST':'*','CHAR_AMP':'&','CHAR_RCURLY':'}','CHAR_TILDE':'~'}.items():
            self.assertEqual(reference.CHARACTERS[name],char)

    def test_every_exact_name_has_constant_left_and_unchanged_right_words(self):
        inputs=reference.input_words()
        self.assertEqual(len(inputs),512)
        self.assertTrue({0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,
                         0x00800000,0x80800000}<=set(inputs[1::2]))
        for model,name in reference.MODEL_NAMES.items():
            with self.subTest(name=name):
                result=reference.reference_words(model,inputs)
                self.assertEqual(result[::2],(reference.word(ord(reference.CHARACTERS[name])),)*256)
                self.assertEqual(result[1::2],inputs[1::2])
                self.assertEqual(reference.ABSOLUTE_TOLERANCES[model],0)
                self.assertEqual(reference.case_input_words(model),inputs)
        self.assertEqual(reference.STRICT_ZERO_SIGN_CHANNELS,2)

    def test_upper_and_lowercase_are_distinct_numeric_values_not_aliases(self):
        models={name:model for model,name in reference.MODEL_NAMES.items()}
        for character in string.ascii_lowercase:
            upper=reference.reference_words(models['CHAR_'+character.upper()],(0,0x80000000))
            lower=reference.reference_words(models['CHAR_'+character],(0,0x80000000))
            self.assertEqual(reference.value(lower[0])-reference.value(upper[0]),32)
            self.assertEqual(upper[1],0x80000000);self.assertEqual(lower[1],0x80000000)

    def test_two_partitions_are_exact_disjoint_43_and_42_subsets(self):
        data=(DIRECTORY/'catalog.json').read_bytes();catalog=json.loads(data);cases=catalog['cases']
        self.assertEqual(len(cases),85);self.assertEqual(len({r['exact_name']for r in cases}),85)
        self.assertEqual(len({r['id'].casefold()for r in cases}),85)
        self.assertEqual(len({r['patch'].casefold()for r in cases}),85)
        collected=[]
        for index,count in ((1,43),(2,42)):
            part=json.loads((DIRECTORY/('catalog-part'+str(index)+'.json')).read_text())
            self.assertEqual(part['partition'],{'index':index,'total':2,'case_count':count,
                             'parent_catalog_sha256':hashlib.sha256(data).hexdigest()})
            self.assertEqual(len(part['cases']),count);collected+=part['cases']
            for key in catalog:
                if key!='cases':self.assertEqual(part[key],catalog[key])
        self.assertEqual(collected,cases)
        self.assertEqual([r['exact_name']for r in cases],list(reference.EXACT_NAMES))

    def test_every_original_program_uses_bare_name_and_preserved_codebox_route(self):
        cases=json.loads((DIRECTORY/'catalog.json').read_text())['cases']
        for row in cases:
            patch_data=(DIRECTORY/row['patch']).read_bytes();patch=json.loads(patch_data)['patcher']
            boxes={b['box']['id']:b['box']for b in patch['boxes']}
            with self.subTest(name=row['exact_name']):
                self.assertEqual(row['patch_sha256'],hashlib.sha256(patch_data).hexdigest())
                self.assertEqual(row['surface'],'codebox');self.assertEqual(row['syntax'],'named-value')
                self.assertEqual(row['arity'],0);self.assertEqual(row['strict_zero_sign_channels'],2)
                self.assertEqual(row['maximum_absolute_error'],0)
                self.assertEqual(row['ascii_decimal'],ord(row['ascii_character']))
                self.assertEqual(patch['classnamespace'],'rnbo')
                self.assertEqual({b['text']for b in boxes.values()},{'in~ 1','in~ 2','out~ 1','out~ 2','codebox~'})
                body='out1 = '+row['exact_name']+';\nout2 = in2;\n'
                self.assertEqual(boxes['program']['rnbo_extra_attributes']['code'],body)
                self.assertEqual((DIRECTORY/row['codebox']).read_text(),body)
                edges={(tuple(e['patchline']['source']),tuple(e['patchline']['destination']))for e in patch['lines']}
                self.assertEqual(row['codebox_inlet_names'],['in2'])
                self.assertEqual(row['codebox_pilot_inlet_ordinal'],0)
                self.assertEqual(edges,{(('right',0),('program',0)),
                                        (('program',0),('out-left',0)),(('program',1),('out-right',0))})

    def test_catalog_declares_primary_numeric_namespace_and_fixed_epoch(self):
        catalog=json.loads((DIRECTORY/'catalog.json').read_text())
        self.assertEqual((catalog['automatic_warmup_blocks'],catalog['manual_warmup_blocks'],catalog['timed_blocks']),(0,4,16))
        self.assertEqual(catalog['family'],'rnbo-character-constants')
        self.assertEqual(catalog['reference_sha256'],hashlib.sha256((DIRECTORY/'reference.py').read_bytes()).hexdigest())
        inventory={r['id']for r in json.loads((ROOT/'site/data/inventory.json').read_text())['spellings']}
        for row in catalog['cases']:
            self.assertIn('codebox:'+row['exact_name'],inventory)
            self.assertNotIn(row['exact_name'],{'CHAR_'+c for c in string.digits})
            self.assertEqual(row['reference_sources'][0]['local_package_path'],'source/operators/characterconstants.json')
            self.assertEqual(row['reference_sources'][0]['sha256'],'eb17d1aea665bcf01b03930d1c20dcf55a1c2918dc355a266254a8fe7c0652e0')

    def test_invalid_models_words_domain_and_lengths_reject(self):
        for model,inputs in ((True,(0,0)),(999,(0,0)),(1085,(0,0)),(1000,()),(1000,(0,)),
                             (1000,(True,0)),(1000,(0,0x7f800000)),(1000,(0,0x7fc00000)),
                             (1000,(0,reference.word(8))),(1000,(-1,0))):
            with self.subTest(model=model,inputs=inputs),self.assertRaises(ValueError):
                reference.reference_words(model,inputs)
        for frames in (True,0,16385):
            with self.assertRaises(ValueError):reference.input_words(frames)


if __name__=='__main__':unittest.main()
