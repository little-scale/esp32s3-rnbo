# SPDX-License-Identifier: MIT
"""Explicit admission, type contracts and one-character source inverse."""
import copy
import json
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest
from gen_feedback import PROFILE, CONTRACT, CONTRACT_FILE, MANIFEST_CONTRACT, SOURCE, OUTPUT, transform
from prepare import ExportError, prepare, cpp_code_mask
from build import verify_prepared

ROOT = Path(__file__).resolve().parents[2]


class GenFeedbackInputTests(unittest.TestCase):
    def test_incompatible_modes_reject_without_creating_output(self):
        options = [('role', 'main'), ('class_name', 'other'), ('apply_fixes', False),
                   ('apply_fixes', 1), ('midi_output_policy', 'discard'), ('filter_delay_max_ms', 40)]
        options += [(name, True) for name in ('float32_delay_storage', 'omit_unused_mtof_table',
            'hoist_cycle_conversions', 'compact_average_history', 'float32_pink_output',
            'correct_finite_wrap', 'exact_audio_delay44100', 'hoist_filter_durations',
            'hoist_train_reciprocal', 'bounded_line_ramps', 'float32_onepole_clamp', 'stable_onepole')]
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            for key, value in options:
                arguments = dict(class_name='rnbos3patch', role='fx', numerical_profile=PROFILE)
                arguments[key] = value
                with self.subTest(key=key), self.assertRaises(ExportError):
                    prepare(directory/'absent', directory/'output', **arguments)
                self.assertFalse((directory/'output').exists())

    def test_compile_contract_rejects_wrong_types_abi_flags_and_excess_precision(self):
        compiler = shutil.which('c++')
        if not compiler: self.skipTest('C++ compiler unavailable')
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            (directory/CONTRACT_FILE).write_bytes(CONTRACT)
            variants = [('float','float','float','double','1','0',[],None,True),
                        ('double','float','float','double','1','0',[],None,False),
                        ('float','double','float','double','1','0',[],None,False),
                        ('float','float','double','double','1','0',[],None,False),
                        ('float','float','float','float','1','0',[],None,False),
                        ('float','float','float','double',None,'0',[],None,False),
                        ('float','float','float','double','1',None,[],None,False),
                        ('float','float','float','double','2','0',[],None,False),
                        ('float','float','float','double','1','1',[],None,False),
                        ('float','float','float','double','1','0',['-ffast-math'],None,False),
                        ('float','float','float','double','1','0',['-ffinite-math-only'],None,False),
                        ('float','float','float','double','1','0',[],2,False)]
            for number, sample, output, clock, major, minor, flags, evaluation, good in variants:
                (directory/'rnbo_source.h').write_text('namespace RNBO { using number='+number+';using Sample='+sample+
                    ';using SampleValue='+output+';using MillisecondTime='+clock+';}\n')
                macros = '\n'.join('#define '+key+' '+value for key,value in
                    [('RNBO_S3_ABI_MAJOR',major),('RNBO_S3_ABI_MINOR',minor)] if value is not None)
                if evaluation is not None:
                    macros += '\n#include <float.h>\n#undef FLT_EVAL_METHOD\n#define FLT_EVAL_METHOD '+str(evaluation)
                (directory/'types.cpp').write_text(macros+'\n#include "'+CONTRACT_FILE+'"\n')
                result = subprocess.run([compiler,'-std=c++17','-fsyntax-only',*flags,str(directory/'types.cpp')],capture_output=True,text=True)
                with self.subTest(types=(number,sample,output,clock),abi=(major,minor),flags=flags,evaluation=evaluation):
                    self.assertEqual(result.returncode == 0, good, result.stderr)


class GenFeedbackPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name); cls.raw = cls.directory/'raw'
        try:
            result = subprocess.run(['node',str(ROOT/'archive/importer/integer-ui/export.mjs'),str(ROOT/'tests/fixtures/gen/history-feedback.rnbopat'),
                                     '--out',str(cls.raw)],capture_output=True,text=True)
        except FileNotFoundError: raise unittest.SkipTest('Node and licensed RNBO frontend required')
        if result.returncode and 'Set --rnbo-dir or RNBO_DIR' in result.stderr:
            raise unittest.SkipTest('Licensed RNBO frontend unavailable')
        if result.returncode: raise AssertionError(result.stderr)
        cls.strict = cls.directory/'strict'
        prepare(cls.raw,cls.strict,'rnbos3patch','fx')
        cls.files = {name:(cls.strict/name).read_bytes() for name in verify_prepared(cls.strict)[2]['prepared_files_sha256'] if name != 'patch_config.h'}
        cls.description = json.loads(cls.files['description.json'])

    def test_exact_producer_epochs_and_unknown_metadata_remain_closed(self):
        import gen_feedback as module
        for stamp,expected in (
                ('56fb9edda0184c282b64f9ba66ab70817866cb981fa5aee4b3050e804bac3065',module.INPUT_MAP),
                ('4af4ee869ca842cd9ffbd0421367b46f491767c203971d3c83fff4e89fd3ce5e',module.INTEGER_UI_INPUT_MAP)):
            files=dict(self.files);generator=json.loads(files['generator.json'])
            generator['patcher_adapter_sha256']=stamp
            files['generator.json']=(json.dumps(generator,indent=2)+'\n').encode()
            before=copy.deepcopy(files)
            changed,record=transform(files,self.description,code_mask=cpp_code_mask)
            self.assertEqual(files,before)
            self.assertEqual(record['input_map_sha256'],expected)
            self.assertEqual(module.sha(changed['rnbo_source.h']),OUTPUT)
            for key,value in (('patcher_adapter_sha256','f'*64),('adapter_sha256','0'*64),
                              ('generated_sha256','0'*64),('voices',2),('class_name','other'),('unknown',False)):
                bad=dict(files);metadata=dict(generator);metadata[key]=value
                bad['generator.json']=(json.dumps(metadata,indent=2)+'\n').encode()
                before=copy.deepcopy(bad)
                with self.subTest(stamp=stamp,key=key),self.assertRaises(ValueError):
                    transform(bad,self.description,code_mask=cpp_code_mask)
                self.assertEqual(bad,before)

    def test_fresh_public_profile_changes_only_literal_configuration_and_type_contract(self):
        output = self.directory/'candidate'
        manifest = prepare(self.raw,output,'rnbos3patch','fx',numerical_profile=PROFILE)
        provenance, _, snapshot = verify_prepared(output)
        self.assertEqual(manifest['gen_feedback_contract'], MANIFEST_CONTRACT)
        self.assertEqual(manifest['base_numerical_profile'],'float32-strict')
        self.assertEqual(manifest['scheduler_time'],'float64')
        self.assertEqual(snapshot['prepared_files_sha256']['rnbo_source.h'],OUTPUT)
        old = (self.strict/'rnbo_source.h').read_bytes(); new = (output/'rnbo_source.h').read_bytes()
        self.assertEqual(new.replace(b'0.5f * __gen_01_z_value',b'0.5 * __gen_01_z_value'),old)
        self.assertEqual(len(new),len(old)+1)
        self.assertEqual((output/CONTRACT_FILE).read_bytes(),CONTRACT)
        for name, data in self.files.items():
            if name != 'rnbo_source.h': self.assertEqual((output/name).read_bytes(),data,name)
        self.assertEqual(provenance['adaptations'][-1]['input_sha256'],SOURCE)
        self.assertTrue(provenance['adaptations'][-1]['inverse_byte_identity'])
        self.assertIn(CONTRACT_FILE,(output/'patch_config.h').read_text())

    def test_pure_transform_rejects_unknown_or_repeated_maps_atomically(self):
        baseline = dict(self.files)
        for mutation in ('source','runtime','graph','metadata','missing','extra','mutable','repeat'):
            files = dict(baseline)
            if mutation == 'missing': files.pop('source.rnbopat')
            elif mutation == 'extra': files['extra.h'] = b''
            elif mutation == 'mutable': files['rnbo_source.h'] = bytearray(files['rnbo_source.h'])
            elif mutation == 'repeat': files = transform(files,self.description,code_mask=cpp_code_mask)[0]
            else:
                key = {'source':'rnbo_source.h','runtime':'common/RNBO_Types.h','graph':'source.rnbopat','metadata':'generator.json'}[mutation]
                files[key] += b'\n'
            before = copy.deepcopy(files)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                transform(files,self.description,code_mask=cpp_code_mask)
            self.assertEqual(files,before)
        for description in ({},self.description|{'numInputChannels':0}):
            with self.assertRaises(ValueError): transform(baseline,description,code_mask=cpp_code_mask)

    def test_unknown_raw_files_and_symbolic_links_reject_without_output(self):
        for link in (False,True):
            raw = self.directory/('linked-raw' if link else 'extra-raw'); shutil.copytree(self.raw,raw)
            extra = raw/'extra.h'
            if link: extra.symlink_to(raw/'rnbo_source.h')
            else: extra.write_text('unknown source')
            output = raw.parent/(raw.name+'-output')
            with self.assertRaises(ExportError): prepare(raw,output,'rnbos3patch','fx',numerical_profile=PROFILE)
            self.assertFalse(output.exists())


if __name__ == '__main__': unittest.main()
