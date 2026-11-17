import unittest
from remote_parameters import extract,checked_plan
from package import create,parse
from test_package import elf
class RemoteParametersTests(unittest.TestCase):
    def parameter(self,**extra):return dict(paramId='cutoff',minimum=20,maximum=20000,steps=0,**extra)
    def test_plain_export_unchanged(self):self.assertIsNone(extract([self.parameter()]))
    def test_alias_normalized_and_direction(self):
        p=self.parameter(meta={'osc':{'addr':'/cutoff','norm':True},'esp32':{'type':'touchscreen','axis':'x'}})
        plan=extract([p]);self.assertEqual(plan['parameters'][0]['osc'],dict(address='/cutoff',normalized=True))
        p['meta']['osc']['out']=True;self.assertIsNone(extract([p]))
        p['meta']['osc']['in']=True;self.assertIsNotNone(extract([p]))
    def test_enums_hidden_and_invalid(self):
        p=dict(paramId='mode',minimum=0,maximum=2,steps=3,enumValues=['a','b','c'],visible=False)
        plan=extract([p]);self.assertEqual(plan['parameters'][0]['enum_values'],['a','b','c']);self.assertIs(plan['parameters'][0]['visible'],False)
        for labels in (['a','a','c'],['a','b'],['']):
            with self.subTest(labels=labels),self.assertRaises(ValueError):extract([dict(p,enumValues=labels)])
        for alias in ('/rnbo/inst/0/params/x','/a*','/a/','/a b',None):
            with self.subTest(alias=alias),self.assertRaises(ValueError):extract([self.parameter(meta={'osc':{'addr':alias}})])
    def test_duplicate_and_malformed(self):
        with self.assertRaises(ValueError):extract([self.parameter(meta={'osc':'/same'}),dict(paramId='other',meta={'osc':'/same'})])
        for plan in ({},dict(version=True,parameters=[]),dict(version=1,parameters=[{'parameter_id':'x'}])):
            with self.assertRaises(ValueError):checked_plan(plan)
    def test_large_native_enum_remains_buildable_but_is_not_network_exposed(self):
        p=dict(paramId='mode',minimum=0,maximum=39,steps=40,enumValues=[str(i) for i in range(40)])
        self.assertEqual(extract([p])['parameters'],[dict(parameter_id='mode',visible=False)])
    def test_optional_package_schema_keeps_audio_envelope(self):
        meta=dict(name='OSC',source_sha256='a'*64,initial_volume=0,remote_parameters=extract([self.parameter(meta={'osc':'/cutoff'})]))
        self.assertEqual(parse(create(elf(),meta,'main',4096))['metadata'],meta)
