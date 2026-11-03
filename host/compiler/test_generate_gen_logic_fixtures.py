# SPDX-License-Identifier: MIT
"""Public source reconstruction and distinct exact grammar identities."""
from pathlib import Path
import tempfile
import unittest
import generate_gen_logic_fixtures as fixtures

ROOT=Path(__file__).resolve().parents[2]


class GenLogicFixtureTests(unittest.TestCase):
    def test_all_original_source_files_are_reproducible_and_have_no_execution_claim(self):
        files=fixtures.authored_files()
        for name,data in files.items():
            self.assertEqual((ROOT/fixtures.FIXTURE_ROOT/name).read_bytes(),data,name)
        self.assertEqual(len(fixtures.RECIPES),21)
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'fresh';report=fixtures.generate(output)
            self.assertFalse(report['DSP_execution_qualified'])
            self.assertFalse(report['hardware_executed'])
            self.assertEqual({p.name:p.read_bytes() for p in output.iterdir()},files)
            with self.assertRaises(ValueError):fixtures.generate(output)

    def test_ternary_grammar_and_prefix_are_separate_from_registry_lookup(self):
        rows={row['id']:row for row in fixtures.recipe_catalog()['recipes']}
        self.assertEqual(rows['conditional-infix']['source']['exact_name'],'?:')
        self.assertEqual(rows['conditional-infix']['source']['inventory_id'],'rnbo-genexpr:?')
        self.assertNotEqual(fixtures.expression('switch-call'),fixtures.expression('conditional-infix'))
        self.assertEqual(fixtures.expression('not-prefix'),'out1 = !in1;\nout2 = !in2;\n')
        self.assertTrue(all(row['aliases_inherit_qualification'] is False for row in rows.values()))
        for unknown in (True,None,'!=','missing','../neq-call'):
            with self.assertRaises(ValueError):fixtures.expression(unknown)


if __name__=='__main__':unittest.main()
