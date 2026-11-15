# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import struct
import tempfile
import unittest
from host.profiles import PROFILES, for_audio, checked
from package import create,parse,HEADER
from voice_pe_inputs import extract,checked_plan
from prepare import prepare,ExportError
from test_package import elf

class ProfileTests(unittest.TestCase):
    def test_explicit_profile_matrix_and_strict_types(self):
        for identity,row in PROFILES.items():
            self.assertEqual(for_audio(row['sample_rate'],256)['id'],identity)
            for board in ('xiao','amoled','voice-pe'):
                if board in row['boards']:self.assertEqual(checked(identity,board)['id'],identity)
                else:
                    with self.assertRaises(ValueError):checked(identity,board)
        for rate,frames in ((True,256),(16000,True),(22050,256),(48000,64),(16000,512)):
            with self.assertRaises(ValueError):for_audio(rate,frames)

    def test_three_package_rates_retain_header_fields_and_reject_retagging(self):
        for identity,row in PROFILES.items():
            metadata=dict(name='Rate test',source_sha256='a'*64,initial_volume=0,audio_profile=identity)
            raw=create(elf(),metadata,'main',4096,sample_rate=row['sample_rate'])
            parsed=parse(raw)
            self.assertEqual((parsed['sample_rate'],parsed['block_frames'],parsed['profile']),(row['sample_rate'],256,identity))
            for other in (16000,48000,44100):
                if other==row['sample_rate']:continue
                changed=bytearray(raw);struct.pack_into('<I',changed,24,other)
                with self.assertRaisesRegex(ValueError,'profile'):parse(bytes(changed))

    def test_voice_controls_use_envelope_four_and_never_legacy_rate(self):
        plan=extract([dict(paramId='frequency',meta={'esp32':{'type':'voice_pe','input':'dial'}})])
        self.assertEqual(checked_plan(plan),plan)
        metadata=dict(name='Controls',source_sha256='b'*64,initial_volume=0,voice_pe_inputs=plan)
        for rate in (16000,48000):
            raw=create(elf(),metadata,'main',4096,sample_rate=rate)
            self.assertEqual(HEADER.unpack_from(raw)[2],4)
            self.assertEqual(parse(raw)['metadata']['voice_pe_inputs'],plan)
            changed=bytearray(raw);struct.pack_into('<I',changed,12,1)
            with self.assertRaises(ValueError):parse(bytes(changed))
        with self.assertRaises(ValueError):create(elf(),metadata,'main',4096)

    def test_control_id_and_source_collisions_reject(self):
        valid=dict(paramId='freq',meta={'esp32':dict(type='voice_pe',input='dial')})
        with self.assertRaises(ValueError):extract([valid,valid])
        for source in ('GPIO16',None,True):
            with self.assertRaises(ValueError):extract([dict(paramId='x',meta={'esp32':dict(type='voice_pe',input=source)})])

class RealMaxRateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[2]/'build/private/voice-pe-native'
        if not all((cls.root/f'export-{r}/rnbo_source.h').is_file() for r in (16000,48000)):
            raise unittest.SkipTest('Export the two genuine local Max fixtures first')

    def test_real_export_to_profile_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            n=0
            for source in (16000,48000):
                for target in (16000,48000,44100):
                    identity=for_audio(target,256)['id'];output=Path(tmp)/str(n);n+=1
                    if source==target:
                        m=prepare(self.root/f'export-{source}',output,'rnbomatic','main',profile=identity)
                        self.assertEqual(m['sample_rate'],target)
                        self.assertIn(f'RNBO_S3_PATCH_RATE {target}',(output/'patch_config.h').read_text())
                    else:
                        with self.assertRaisesRegex(ExportError,'fixed'):
                            prepare(self.root/f'export-{source}',output,'rnbomatic','main',profile=identity)
                        self.assertFalse(output.exists())

    def test_historical_rate_specific_transforms_reject_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ExportError,'historical'):
                prepare(self.root/'export-16000',Path(tmp)/'output','rnbomatic','main',
                        profile='voice-pe-16000-256-v1',exact_audio_delay44100=True)

if __name__=='__main__':unittest.main()
