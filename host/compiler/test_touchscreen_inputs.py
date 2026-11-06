# SPDX-License-Identifier: MIT
import unittest
from touchscreen_inputs import extract, checked_plan
from physical_inputs import extract as physical
from package import create, parse, HEADER
from test_package import elf


def parameter(identity, **values):
    return dict(paramId=identity, meta={'esp32':dict(type='touchscreen',**values)})


class TouchscreenTests(unittest.TestCase):
    def test_axes_stable_ids_and_multiple_destinations_are_canonical(self):
        rows=[parameter('gate',axis='pressed'),parameter('pitch',axis='x'),parameter('cutoff',axis='x',invert=True),parameter('level',axis='y')]
        plan=extract(rows);self.assertEqual(plan['board'],'amoled');self.assertEqual(plan['area'],'patch')
        self.assertEqual(checked_plan(plan),plan);self.assertIsNone(physical(rows))
        self.assertEqual(plan['bindings'][1],dict(parameter_id='pitch',axis='x',invert=False,deadband=.002))
        self.assertIsNone(extract([dict(paramId='p',meta={'esp32':dict(type='touch',pin='D3')})]))

    def test_bad_options_ids_and_noncanonical_plans_reject(self):
        for change in ({'axis':'pressure'},{'axis':[]},{'pin':'D3'},{'area':'screen'},{'invert':1},{'deadband':True},{'deadband':float('nan')},{'deadband':.11}):
            with self.subTest(change=change),self.assertRaises(ValueError):extract([parameter('x',**(dict(axis='x')|change))])
        with self.assertRaises(ValueError):extract([parameter('x',axis='x'),parameter('x',axis='y')])
        with self.assertRaises(ValueError):extract([parameter(str(i),axis='x') for i in range(17)])
        p=extract([parameter('x',axis='x')])
        for value in (dict(p,version=True),dict(p,board='xiao'),dict(p,area='screen'),dict(p,bindings=[])):
            with self.subTest(value=value),self.assertRaises(ValueError):checked_plan(value)

    def test_touchscreen_packages_require_v3_and_cannot_mix_xiao_bindings(self):
        p=extract([parameter('x',axis='x')]);m=dict(name='Touch',source_sha256='a'*64,initial_volume=50,touchscreen_inputs=p)
        raw=create(elf(),m,'main',4096);self.assertEqual(HEADER.unpack_from(raw)[2],3)
        self.assertEqual(parse(raw)['metadata']['touchscreen_inputs'],p)
        import struct
        for version in (1,2):
            bad=bytearray(raw);struct.pack_into('<I',bad,12,version)
            with self.assertRaisesRegex(ValueError,'envelope'):parse(bytes(bad))
        pins=physical([dict(paramId='a',meta={'esp32':dict(type='analog',pin='A0')})])
        with self.assertRaisesRegex(ValueError,'cannot share'):create(elf(),dict(m,physical_inputs=pins),'main',4096)
