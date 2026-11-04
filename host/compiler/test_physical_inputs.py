# SPDX-License-Identifier: MIT
import unittest
from physical_inputs import extract, checked_plan, gpio_for_pin


def parameter(identity, binding):
    return dict(paramId=identity, name=identity, meta={'esp32': binding})


class PhysicalInputsTests(unittest.TestCase):
    def test_defaults_and_stable_ids_survive_parameter_order(self):
        rows = [parameter('pitch-id', dict(type='analog', pin='A0')),
                parameter('gate-id', dict(type='digital', pin='D6')),
                parameter('touch-id', dict(type='touch', pin='D3'))]
        plan = extract(rows)
        self.assertEqual(checked_plan(plan), plan)
        self.assertEqual(plan['bindings'][0], dict(parameter_id='pitch-id', type='analog', pin='A0',
                         invert=False, raw_min=0, raw_max=4095, smooth_ms=10, deadband=.002))
        self.assertTrue(plan['bindings'][1]['active_low'])
        self.assertEqual(plan['bindings'][1]['pull'], 'up')
        self.assertEqual({r['parameter_id'] for r in extract(rows[::-1])['bindings']}, {'pitch-id','gate-id','touch-id'})

    def test_aliases_pin_types_and_reservations(self):
        self.assertEqual(gpio_for_pin('A0'), 1)
        self.assertEqual(gpio_for_pin('D6'), 43)
        self.assertEqual(gpio_for_pin('D10'), 9)
        for pin in ('0', 'GPIO0', 'A6', 'D11', 'GPIO19', 'D00', 'gpio1', None, 1):
            with self.subTest(pin=pin), self.assertRaises(ValueError): gpio_for_pin(pin)
        for pin in ('A2', 'D2', 'GPIO3', 'D8', 'D9', 'D10', 'GPIO7'):
            with self.subTest(pin=pin), self.assertRaises(ValueError):extract([parameter('p',dict(type='digital',pin=pin))])
        for kind in ('analog','touch'):
            with self.assertRaises(ValueError):extract([parameter('p',dict(type=kind,pin='D6'))])
        with self.assertRaisesRegex(ValueError, 'one parameter'):
            extract([parameter('a',dict(type='analog',pin='A0')),parameter('b',dict(type='digital',pin='GPIO1'))])

    def test_unknown_malformed_and_out_of_range_options_fail_closed(self):
        for change in ({'type':'pwm'}, {'pin':'A2'}, {'invert':1}, {'smooth_ms':float('nan')},
                       {'smooth_ms':-1}, {'raw_min':1.2}, {'raw_min':2000,'raw_max':1000},
                       {'raw_max':4096}, {'deadband':.11}, {'smoothing_ms':20}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                extract([parameter('p',dict(type='analog',pin='A0') | change)])
        for binding in (dict(type='digital',pin='D1',pull='floating'),dict(type='digital',pin='D1',active_low=1),
                        dict(type='digital',pin='D1',debounce_ms=.5),dict(type='touch',pin='D3',threshold=.01,hysteresis=.02)):
            with self.subTest(binding=binding), self.assertRaises(ValueError):extract([parameter('p',binding)])
        with self.assertRaisesRegex(ValueError, 'Cannot parse'):
            extract([dict(paramId='p',meta="['esp32']")])
        self.assertIsNone(extract([dict(paramId='p',meta={'other':{'label':'hello'}})]))

    def test_package_plan_must_be_canonical_bounded_and_versioned(self):
        plan = extract([parameter('p',dict(type='analog',pin='A0'))])
        for changed in (dict(plan,version=True), dict(plan,version=2), dict(plan,board='amoled'),
                        dict(plan,bindings=[]), dict(plan,bindings=plan['bindings']*2), dict(plan,extra=True)):
            with self.subTest(changed=changed), self.assertRaises(ValueError):checked_plan(changed)
        missing=dict(plan['bindings'][0]);missing.pop('smooth_ms')
        with self.assertRaisesRegex(ValueError,'canonical'):checked_plan(dict(plan,bindings=[missing]))


if __name__ == '__main__': unittest.main()
