# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import struct
import tempfile
import unittest
from voice_pe_leds import PLAN,checked_plan,extract
from package import create,parse,HEADER
from test_package import elf
from prepare import prepare,ExportError
class LEDContractTests(unittest.TestCase):
    def test_only_explicit_led_outport_is_admitted(self):
        self.assertIsNone(extract({}))
        self.assertEqual(extract({'outports':[{'tag':'led_rgb','meta':''}]}),PLAN)
        for ports in (None,{},[{'tag':'foo'}],[{'tag':'led_rgb'},{'tag':'led_rgb'}],[{'tag':'led_rgb','other':1}]):
            with self.subTest(ports=ports),self.assertRaises(ValueError):extract({'outports':ports})
        for bad in ({},dict(PLAN,version=True),dict(PLAN,version=2),dict(PLAN,board='xiao'),dict(PLAN,port='other')):
            with self.assertRaises(ValueError):checked_plan(bad)
    def test_envelope_five_handles_optional_voice_inputs_and_rejects_downgrade(self):
        meta=dict(name='LED',source_sha256='b'*64,initial_volume=0,voice_pe_leds=PLAN)
        for rate in (16000,48000):
            for controls in (False,True):
                value=dict(meta)
                if controls:value['voice_pe_inputs']={'version':1,'board':'voice-pe','bindings':[{'input':'dial','parameter_id':'x'}]}
                raw=create(elf(),value,'main',4096,sample_rate=rate);self.assertEqual(HEADER.unpack_from(raw)[2],5)
                self.assertEqual(parse(raw)['metadata'],value)
                for version in (1,4):
                    changed=bytearray(raw);struct.pack_into('<I',changed,12,version)
                    with self.assertRaises(ValueError):parse(bytes(changed))
        with self.assertRaises(ValueError):create(elf(),meta,'main',4096)
    def test_genuine_export_requires_matching_voice_profile_and_sets_capability(self):
        root=Path(__file__).resolve().parents[2]/'build/private/voice-pe-led/export-16000'
        if not root.is_dir():self.skipTest('Genuine Max LED export is required')
        with tempfile.TemporaryDirectory() as tmp:
            m=prepare(root,Path(tmp)/'yes','rnbomatic','main',profile='voice-pe-16000-256-v1')
            self.assertEqual(m['voice_pe_leds'],PLAN)
            self.assertIn('RNBO_S3_PATCH_LED_OUTPUT_VERSION 1',(Path(tmp)/'yes/patch_config.h').read_text())
            with self.assertRaises(ExportError):prepare(root,Path(tmp)/'no','rnbomatic','main')
