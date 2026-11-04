# SPDX-License-Identifier: MIT
"""Original syntax/source fidelity, atomic generation and real licensed exports."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import generate_gen_arithmetic_fixtures as fixtures
from prepare import prepare
from build import verify_prepared

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'tests/fixtures/gen/arithmetic'
# Independent snapshots of the18-program source study's admitted15 programs.
PATCH_HASHES = {
 'abs-call':'c2878ab82152020b8a26f006c96e22b7a4837ecfe9005ca9768bcaf9bbba39c6',
 'min-call':'ae15329737cdb0cc73fc680952427a8ca2c223039b6e60e59a9fa155e993bfb0',
 'minimum-call':'034f7ad3090217e5193313dc8a9d52e8440ad43fdbaa2babffa239285f758084',
 'max-call':'f331c0d547491254bb3f39921194943db205225192ca51ffe3e912ac0a721f57',
 'maximum-call':'d8eb69ee640e9e13b48d85a24845895f922af0979fa3a0352952d0fd94b8611c',
 'sub-call':'a8335ab43dc772c370b70ab968eee7fbc3bfebd455c685ef4b985290fe3a8fb1',
 'subtract-infix':'7e3ccc0b037f3140ca19bfb7ac49e22f66d116e247142f23b9c76f1a2f1bc852',
 'eq-call':'dbbbb2036fcaf8e2964bf657eeee01a9adc3a259b3a6d6b5e1f1f1af0d526115',
 'equal-infix':'c888c4b7b3024f72e1460e243812028c74654fc43fee209e05b36b2be9567c3a',
 'lt-call':'ea93cf36febdf6927af6400d1680d8acfdcefdc8f80714c2f293109ab084e56b',
 'less-infix':'effbdcfd741225b48519ee2b4947b7a669376a8b920ab75391cd3245ee35f2cb',
 'add-call':'20da67e975649c83bdb209f90e7547078184cdbf16e0ea5e5c561a80d1c486ca',
 'add-infix':'6aa63780a1cbf56831b5132c32c9056c0aae9cc871d8986d643ac13370407dca',
 'mul-call':'17204c076425bfa2e9382195b2b8803e35e6b02ce2a45ffb0f683c42f6cfa2f2',
 'mul-infix':'5e9a5931929537b1c8c84508d90517e1af808bc5c6bbb52e3655704d5916fc98',
}


class GeneratorTests(unittest.TestCase):
    def test_each_exact_spelling_and_surface_has_its_own_source_identity(self):
        rows = fixtures.recipe_catalog()['recipes']
        self.assertEqual({r['source']['exact_name'] for r in rows},
            {'abs','min','minimum','max','maximum','sub','-','eq','==','lt','<','add','+','mul','*'})
        self.assertEqual(len(rows),15)
        self.assertEqual(len({r['id'] for r in rows}),15)
        for row in rows:
            self.assertEqual(row['source']['surface'],'genexpr')
            self.assertEqual(row['source']['inventory_id'],'rnbo-genexpr:'+row['source']['exact_name'])
            self.assertIs(row['aliases_inherit_qualification'],False)
        models = {r['source']['exact_name']:r['model_code'] for r in rows}
        self.assertEqual(models,{'abs':1,'min':2,'minimum':2,'max':3,'maximum':3,
            'sub':4,'-':4,'eq':5,'==':5,'lt':6,'<':6,'add':9,'+':9,'mul':10,'*':10})

    def test_authored_sources_reproduce_independent_study_and_public_bytes(self):
        files = fixtures.authored_files()
        self.assertEqual(len(files),32)
        for identity, expected in PATCH_HASHES.items():
            self.assertEqual(fixtures.digest(files[identity+'.rnbopat']),expected,identity)
            self.assertEqual(files[identity+'.rnbopat'],(PUBLIC/(identity+'.rnbopat')).read_bytes())
            self.assertEqual(files[identity+'.genexpr'],(PUBLIC/(identity+'.genexpr')).read_bytes())
            graph = json.loads(files[identity+'.rnbopat'])['patcher']
            boxes = {r['box']['id']:r['box'] for r in graph['boxes']}
            self.assertEqual(len(boxes),5)
            self.assertEqual(boxes['gen']['rnbo_extra_attributes'],
                {'expr':files[identity+'.genexpr'].decode(),'geninlets':2,'genoutlets':2})
            self.assertEqual([r['patchline'] for r in graph['lines']],
                [{'source':['left',0],'destination':['gen',0]},
                 {'source':['right',0],'destination':['gen',1]},
                 {'source':['gen',0],'destination':['ol',0]},
                 {'source':['gen',1],'destination':['or',0]}])
        self.assertEqual(files['catalog.json'],(PUBLIC/'catalog.json').read_bytes())
        self.assertEqual(files['recipes.json'],(PUBLIC/'recipes.json').read_bytes())

    def test_target_cases_preserve_closed_domains_controls_and_no_execution_claim(self):
        for f in fixtures.catalog()['fixtures']:
            self.assertEqual((f['blocks'],f['warmup_blocks'],f['rounds'],f['seed'],f['arena_bytes'],f['pcm_gain']),
                             (64,4,3,0x12345678,4096,0.5))
            self.assertEqual((f['role'],f['audio_inputs'],f['audio_outputs']),('fx',2,2))
            self.assertEqual((f['domain']['minimum'],f['domain']['maximum']),(-1.0,1.0))
            self.assertEqual(f['semantic'],f['verification'])
            self.assertEqual(f['semantic']['maximum_absolute_error'],0.0)
            self.assertEqual(f['comparison_tolerance'],{'maximum_absolute_error':0.0,
                'maximum_pcm_lsb_error':0,'relative_rms_level_difference':0.0})
            self.assertEqual(f['cases'],[{'id':k,'parameters':{},'events':[],'stimulus':{'kind':k}}
                                        for k in fixtures.INPUT_FAMILIES])

    def test_unknown_or_unsupported_call_syntax_and_nonstring_ids_reject(self):
        for identity in ('subtract-call','equal-call','less-call','ABS-call','../abs-call',True,0,None,[]):
            with self.subTest(identity=identity),self.assertRaises(ValueError):
                fixtures.graph(identity)

    def test_generation_is_fresh_and_missing_identity_inputs_leave_no_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);out=base/'authored'
            report=fixtures.generate(out)
            self.assertFalse(report['DSP_execution_qualified'])
            self.assertEqual({p.name:p.read_bytes() for p in out.iterdir()},fixtures.authored_files())
            sentinel=out/'models.py';sentinel.write_text('preserve external owner')
            before={p.name:p.read_bytes() for p in out.iterdir()}
            with self.assertRaises(ValueError):fixtures.generate(out)
            self.assertEqual({p.name:p.read_bytes() for p in out.iterdir()},before)
            missing=base/'missing-prepared';missing.mkdir()
            with self.assertRaises(ValueError):fixtures.generate(base/'rejected',prepared_root=missing)
            self.assertFalse((base/'rejected').exists())


class LicensedExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('node'):raise unittest.SkipTest('Node and licensed RNBO1.4.4 frontend required')
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.base=Path(cls.temp.name);cls.prepared=cls.base/'prepared'
        def export(identity):
            raw=cls.base/'raw'/identity
            result=subprocess.run(['node',str(ROOT/'host/export/export.mjs'),str(PUBLIC/(identity+'.rnbopat')),
                '--out',str(raw)],cwd=ROOT,capture_output=True,text=True)
            if result.returncode and 'Set --rnbo-dir or RNBO_DIR' in result.stderr:
                raise unittest.SkipTest('Licensed RNBO1.4.4 frontend unavailable')
            if result.returncode:raise AssertionError(result.stdout+result.stderr)
            prepare(raw,cls.prepared/identity,'rnbos3patch','fx')
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(export,PATCH_HASHES))

    def test_fresh_public_exports_reproduce_all_derived_identity_pins(self):
        current=PUBLIC/'identities.integer-ui-v1.json'
        derived=fixtures.identities(self.prepared)
        self.assertEqual(derived,json.loads(current.read_bytes()))
        historical=json.loads((PUBLIC/'identities.json').read_bytes())
        self.assertEqual({k:v for k,v in derived.items() if k!='entries'},
                         {k:v for k,v in historical.items() if k!='entries'})
        for identity,entry in derived['entries'].items():
            self.assertEqual([k for k in entry if entry[k]!=historical['entries'][identity][k]],
                             ['source_tree_sha256'])
        out=self.base/'cli-fixtures'
        result=subprocess.run([sys.executable,str(ROOT/'host/compiler/generate_gen_arithmetic_fixtures.py'),
            '--out',str(out),'--prepared-root',str(self.prepared)],capture_output=True,text=True,cwd=ROOT)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((out/'identities.json').read_bytes(),current.read_bytes())
        for name,data in fixtures.authored_files().items():self.assertEqual((out/name).read_bytes(),data)

    def test_fresh_current_epoch_admission_requires_every_prepared_file(self):
        from gen_arithmetic_contract import admit_module
        for fixture in fixtures.catalog()['fixtures']:
            directory=self.prepared/fixture['id']
            provenance,manifest,snapshot=verify_prepared(directory)
            module={'report':{'prepared_export':{'manifest':manifest,'provenance':provenance},
                              'prepared_snapshot':snapshot}}
            admit_module(fixture,module)
            for key in ('generator.json','patch_config.h','RNBO-runtime-LICENSE'):
                changed=copy.deepcopy(module)
                changed['report']['prepared_snapshot']['prepared_files_sha256'][key]='0'*64
                with self.subTest(identity=fixture['id'],key=key),self.assertRaises(ValueError):
                    admit_module(fixture,changed)
            changed=copy.deepcopy(module)
            changed['report']['prepared_export']['manifest']['source_tree_sha256']='f'*64
            with self.assertRaises(ValueError):admit_module(fixture,changed)

    def test_rehashed_wrong_ports_booleans_optional_profiles_and_runtime_reject(self):
        for mutation in ('audio_inputs','boolean_channels','optional_profile','source','runtime'):
            with self.subTest(mutation=mutation):
                parent=self.base/('bad-'+mutation);directory=parent/'abs-call'
                shutil.copytree(self.prepared/'abs-call',directory)
                provenance=json.loads((directory/'provenance.json').read_bytes())
                manifest=json.loads((directory/'manifest.json').read_bytes())
                if mutation=='audio_inputs':manifest['audio_inputs']=1
                elif mutation=='boolean_channels':manifest['audio_inputs']=True
                elif mutation=='optional_profile':manifest['float32_onepole_clamp']=False
                else:
                    name='rnbo_source.h' if mutation=='source' else 'common/RNBO_Types.h'
                    path=directory/name;path.write_bytes(path.read_bytes()+b'\n')
                    provenance['prepared_files_sha256'][name]=fixtures.digest(path.read_bytes())
                provenance['manifest_sha256']=fixtures.digest(fixtures.canonical(manifest))
                (directory/'manifest.json').write_bytes(fixtures.canonical(manifest))
                (directory/'provenance.json').write_bytes(fixtures.canonical(provenance))
                verify_prepared(directory) # Rejection must be semantic, beyond simple file integrity.
                with self.assertRaisesRegex(ValueError,'outside|Unexpected|source differs|runtime tree differs'):
                    fixtures.generate(parent/'output',prepared_root=parent)
                self.assertFalse((parent/'output').exists())


if __name__=='__main__':unittest.main()
