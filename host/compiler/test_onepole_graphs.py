# SPDX-License-Identifier: MIT
"""Fresh original graphs, whole-map authority and per-instance source guards."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from build import verify_prepared
from prepare import cpp_code_mask, prepare
from regenerated_export import RegeneratedGraph, regenerate
from onepole_graphs import CONTRACT, HELPER_SHA256, MAX_SOURCE_BYTES, OPTIONS, method, scan, sha, transform

ROOT=Path(__file__).resolve().parents[2]
HELPER=(ROOT/'host/compiler/onepole_stable.h').read_bytes()

def options(role='fx'):
    return {**copy.deepcopy(OPTIONS),'role':role,'audio_inputs':2 if role=='fx'else 0}

def graph(objects,cords):
    boxes=[]
    for i,item in enumerate(objects):
        name,text,*extra=item
        box={'id':name,'maxclass':'newobj','text':text,'rnbo_uniqueid':name,
             'patching_rect':[20+i%4*240,25+i//4*80,220,22]}
        if extra:box['rnbo_extra_attributes']=extra[0]
        boxes.append({'box':box})
    return {'patcher':{'fileversion':1,'classnamespace':'rnbo','rect':[0,0,1024,720],
       'boxes':boxes,'lines':[{'patchline':{'source':[s,o],'destination':[d,i]}}for s,o,d,i in cords]}}

def fixtures():
    return {
      'fx':('fx',graph([('data','in~ 1'),('frequency','in~ 2'),
          ('cut','param onepole_tilde_01_b1 500 @min -1000 @max 100000'),
          ('scalar','onepole~'),('fixed','onepole~ 0.05'),
          ('attribute','onepole~',{'freqInHz':1234.5}),('signal','onepole~'),
          ('ol','out~ 1'),('or','out~ 2')],
          [('data',0,'scalar',0),('cut',0,'scalar',1),('scalar',0,'fixed',0),
           ('fixed',0,'attribute',0),('attribute',0,'ol',0),('data',0,'signal',0),
           ('frequency',0,'signal',1),('signal',0,'or',0)])),
      'main':('main',graph([('osc','cycle~ 440'),('cut','param cutoff 700 @min 0 @max 100000'),
          ('filter','onepole~'),('ol','out~ 1'),('or','out~ 2')],
          [('osc',0,'filter',0),('cut',0,'filter',1),('filter',0,'ol',0),('osc',0,'or',0)])),
      'same-wire':('fx',graph([('data','in~ 1'),('other','in~ 2'),('filter','onepole~'),
          ('ol','out~ 1'),('or','out~ 2')],[('data',0,'filter',0),('data',0,'filter',1),
          ('filter',0,'ol',0),('other',0,'or',0)])),
      'scalar-data':('fx',graph([('unused1','in~ 1'),('unused2','in~ 2'),
          ('data','param data 0.5 @min -1 @max 1'),('filter','onepole~ 1000'),
          ('ol','out~ 1'),('or','out~ 2')],[('data',0,'filter',0),('filter',0,'ol',0),('filter',0,'or',0)])),
      'linear':('fx',graph([('a','in~ 1'),('b','in~ 2'),('filter','onepole_lin~ 0.5'),
          ('ol','out~ 1'),('or','out~ 2')],[('a',0,'filter',0),('filter',0,'ol',0),('b',0,'or',0)]))}


class InputTests(unittest.TestCase):
    def test_typed_options_maps_and_nonissued_authority_fail_without_io(self):
        good=options()
        bad=[dict(good,sample_rate=44100.),dict(good,apply_fixes=1),dict(good,role='other'),
             dict(good,audio_inputs=0),dict(good,other_optimizations=['other']),dict(good,extra=False)]
        with mock.patch('subprocess.run',side_effect=AssertionError('transform cannot run tools')):
            for value in bad:
                with self.subTest(options=value),self.assertRaises(ValueError):
                    transform({}, {},value,code_mask=cpp_code_mask,helper=HELPER,regenerated=None)
            for authority in (None,{}, {'record':{}},object.__new__(RegeneratedGraph)):
                with self.subTest(authority=type(authority)),self.assertRaises(ValueError):
                    transform({}, {},good,code_mask=cpp_code_mask,helper=HELPER,regenerated=authority)

    def test_bounded_malformed_methods_and_sources_reject_cleanly(self):
        for source in (None,'text',bytearray(b'text'),b'',b' '* (MAX_SOURCE_BYTES+1),b'void fake(){}'):
            with self.subTest(kind=type(source)),self.assertRaises(ValueError):scan(source)
        for source in ('void f(', 'void f(){', 'void f();', 'void f(){}\nvoid f(){}',
                       'void f(){'+'{'*129+'}'*130):
            with self.subTest(source=source[:40]),self.assertRaises(ValueError):method(source,'f')


class FreshGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name);cls.data={}
        for name,(role,source) in fixtures().items():
            patch=cls.root/(name+'.rnbopat');patch.write_text(json.dumps(source))
            raw=cls.root/(name+'-raw')
            try:result=subprocess.run(['node',str(ROOT/'host/export/export.mjs'),str(patch),'--out',str(raw)],capture_output=True,text=True)
            except FileNotFoundError:raise unittest.SkipTest('Node and authorised RNBO1.4.4 required')
            if result.returncode and 'Set --rnbo-dir or RNBO_DIR'in result.stderr:raise unittest.SkipTest('Authorised RNBO1.4.4 unavailable')
            if result.returncode:raise AssertionError(result.stderr)
            prepared=cls.root/(name+'-normal');prepare(raw,prepared,'rnbos3patch',role)
            files={n:(prepared/n).read_bytes()for n in verify_prepared(prepared)[2]['prepared_files_sha256']}
            certificate=regenerate(files,role)if name in ('fx','main','same-wire')else None
            cls.data[name]=(role,files,certificate,raw)

    def apply(self,name='fx'):
        role,files,certificate,_=self.data[name]
        return transform(files,json.loads(files['description.json']),options(role),
                         code_mask=cpp_code_mask,helper=HELPER,regenerated=certificate)

    def test_actual_main_multi_mode_and_read_alias_envelopes(self):
        counts={'fx':4,'main':1,'same-wire':1}
        for name in counts:
            role,files,certificate,_=self.data[name]
            before=copy.deepcopy(files)
            with mock.patch('subprocess.run',side_effect=AssertionError('pure transform launches no tools')):
                candidate,record=self.apply(name)
            self.assertEqual(files,before);self.assertEqual(len(candidate),43)
            self.assertEqual(record['instance_count'],counts[name]);self.assertEqual(candidate['onepole_stable.h'],HELPER)
            for key,data in files.items():
                if key!='rnbo_source.h':self.assertEqual(candidate[key],data)
            self.assertTrue(record['source_inverse_byte_identity'])
            self.assertFalse(record['baseline_bit_identity_claimed']);self.assertFalse(record['target_cpu_gain_claimed'])
            self.assertTrue(certificate.matches(files,role));self.assertFalse(certificate.matches(files,'main'if role=='fx'else'fx'))
        self.assertTrue(self.apply('same-wire')[1]['instances'][0]['read_only_data_frequency_alias'])
        instances=self.apply('fx')[1]['instances']
        self.assertEqual({x['mode']for x in instances},{'fixed','scalar','signal'})
        literals={x['details'].get('literal')for x in instances}
        self.assertIn('1234.5',literals)
        self.assertTrue(any(x['details'].get('fixed_cache_predicate_repeats')for x in instances))

    def test_identifier_edits_preserve_actual_parameter_name_string(self):
        _,files,_,_=self.data['fx'];candidate,_=self.apply()
        literal=b'"onepole_tilde_01_b1"'
        self.assertIn(literal,files['rnbo_source.h']);self.assertEqual(candidate['rnbo_source.h'].count(literal),files['rnbo_source.h'].count(literal))
        self.assertNotIn(b'"onepole_tilde_01_correction"',candidate['rnbo_source.h'])
        self.assertEqual(candidate['description.json'],files['description.json'])

    def test_unknown_scalar_data_and_linear_forms_are_not_inherited(self):
        for name in ('scalar-data','linear'):
            with self.subTest(name=name),self.assertRaises(ValueError):scan(self.data[name][1]['rnbo_source.h'])

    def test_field_alias_type_cache_reset_and_caller_mutations_reject(self):
        raw=self.data['fx'][1]['rnbo_source.h'].decode();prefix=scan(raw.encode())[0]['prefix']
        # Select a real scalar instance for its by-value frequency cache route.
        scalar=next(x for x in scan(raw.encode())if x['mode']=='scalar')['prefix']
        changes=[(f'number {prefix}_b1;',f'double {prefix}_b1;'),
          (f'this->{prefix}_b1 = 0;',f'this->{prefix}_b1 = 1;'),
          (f'__{scalar}_freq = freqInHz;',f'__{scalar}_freq = freqInHz + 1;'),
          (f'__{prefix}_b1 * __{prefix}_lastY',f'0.99 * __{prefix}_lastY'),
          ('void startup() {',f'void startup() {{\n auto &alias=this->{prefix}_b1;'),
          ('void startup() {',f'void startup() {{\n auto ptr=&rnbos3patch<ENGINE>::{prefix}_b1;'),
          ('void startup() {',f'void startup() {{\n this->{prefix}_reset();')]
        for old,new in changes:
            self.assertIn(old,raw);changed=raw.replace(old,new,1).encode()
            with self.subTest(old=old),self.assertRaises(ValueError):scan(changed)
        call=next(x for x in scan(raw.encode())if x['mode']=='signal')
        old='this->'+call['prefix']+'_perform('+', '.join(call['call_args'])+');'
        self.assertIn(old,raw)
        for new in (old.replace(', 256);',', 1);'),old.replace(call['call_args'][2],call['call_args'][0])):
            with self.subTest(call=new),self.assertRaises(ValueError):scan(raw.replace(old,new,1).encode())

    def test_metadata_configuration_and_manual_alias_are_fresh_authority_gates(self):
        role,files,certificate,_=self.data['fx']
        for name in ('description.json','patch_config.h','generator.json','rnbo_source.h'):
            changed=dict(files)
            if name=='rnbo_source.h':
                source=changed[name].decode();source=source.replace('    RNBO_ASSERT(n == 256);','    RNBO_ASSERT(n == 256);\n static_cast<unsigned char*>(static_cast<void*>(this))[128]=255;',1)
                changed[name]=source.encode();self.assertNotEqual(changed[name],files[name])
                # Explicitly prove local scanning alone is not ownership authority.
                self.assertEqual(len(scan(changed[name])),4)
            else:changed[name]+=b'\n'
            self.assertFalse(certificate.matches(changed,role))
            before=copy.deepcopy(changed)
            with self.subTest(file=name),self.assertRaisesRegex(ValueError,'regeneration'):
                transform(changed,json.loads(changed['description.json']),options(role),code_mask=cpp_code_mask,helper=HELPER,regenerated=certificate)
            self.assertEqual(before,changed)

    def test_wrong_description_helper_runtime_masks_and_repeated_maps_reject(self):
        role,files,certificate,_=self.data['fx'];description=json.loads(files['description.json'])
        wrong=copy.deepcopy(description);wrong['parameters'][0]['initialValue']+=1
        with self.assertRaises(ValueError):transform(files,wrong,options(role),code_mask=cpp_code_mask,helper=HELPER,regenerated=certificate)
        for helper in (bytearray(HELPER),HELPER+b'\n'):
            with self.assertRaises(ValueError):transform(files,description,options(role),code_mask=cpp_code_mask,helper=helper,regenerated=certificate)
        for mask in (lambda _:None,lambda _:'',lambda s:' '*len(s)):
            with self.assertRaises(ValueError):transform(files,description,options(role),code_mask=mask,helper=HELPER,regenerated=certificate)
        candidate,_=self.apply()
        with self.assertRaises(ValueError):transform(candidate,description,options(role),code_mask=cpp_code_mask,helper=HELPER,regenerated=certificate)
        changed=dict(files);changed['common/RNBO_Types.h']+=b'\n'
        with self.assertRaises(ValueError):transform(changed,description,options(role),code_mask=cpp_code_mask,helper=HELPER,regenerated=certificate)

    def test_actual_production_wrapper_compiles_transformed_graphs(self):
        compiler=shutil.which('c++')
        if not compiler:self.skipTest('C++ compiler required')
        for name in ('fx','main','same-wire'):
            candidate,_=self.apply(name)
            with tempfile.TemporaryDirectory()as directory:
                root=Path(directory)
                for key,data in candidate.items():p=root/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
                result=subprocess.run([compiler,'-std=c++17','-fsyntax-only','-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing','-I'+str(ROOT/'module-sdk/include'),'-I'+str(ROOT/'module-sdk/dynamic'),'-I'+str(root),'-I'+str(root/'common'),str(ROOT/'module-sdk/dynamic/rnbo_s3_dynamic.cpp')],capture_output=True,text=True)
                with self.subTest(name=name):self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
