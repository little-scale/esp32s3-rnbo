# SPDX-License-Identifier: MIT
import array
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import wave

from host.studio.trial import compare_audio, device_check

spec=importlib.util.spec_from_file_location('rnbo_trial_server',Path(__file__).with_name('server.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


class TrialReviewTests(unittest.TestCase):
    def capture(self, stem, values, pcm):
        stem.with_suffix('.f32').write_bytes(array.array('f',values).tobytes())
        with wave.open(str(stem.with_suffix('.wav')),'wb') as wav:
            wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(44100)
            wav.writeframes(array.array('h',pcm).tobytes())

    def test_native_observations_keep_failed_diagnostics_and_never_promote(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=(Path(tmp)/n for n in ('reference','candidate'))
            self.capture(a,[.25,-.25,.5,-.5],[4096,-4096,8192,-8192])
            self.capture(b,[.25+1/16384,-.25,.5,-.5],[4097,-4096,8192,-8192])
            r=compare_audio(a,b,frames=2)
            self.assertEqual(r['max_absolute_error'],1/16384)
            self.assertEqual(r['max_pcm_difference_lsb'],1)
            self.assertFalse(r['diagnostic_sample_limit_pass'])
            self.assertTrue(r['diagnostic_pcm_limit_pass'])
            self.assertEqual(r['qualification'],'unverified')
            self.assertFalse(r['promotes_reviewed_catalog'])
            self.assertEqual(r['differing_float_values'],1)
            b.with_suffix('.f32').write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError,'dimensions'):compare_audio(a,b,frames=2)

    def test_nonfinite_capture_is_not_a_successful_output_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=(Path(tmp)/n for n in ('reference','candidate'))
            self.capture(a,[0,0],[0,0]);self.capture(b,[float('nan'),0],[0,0])
            with self.assertRaisesRegex(ValueError,'finite'):compare_audio(a,b,frames=1)

    def test_device_smoke_records_cpu_and_omits_network_credentials(self):
        snapshot={'device':dict(rate=44100,block_frames=256,render_us=1000,peak_us=5000,
            board='xiao',generation=2,main={'package_sha256':'a'*64},wifi={'ssid':'private','password':'private'},device_id='private')}
        r=device_check(snapshot)
        self.assertAlmostEqual(r['audio_cpu_percent'],17.2265625)
        self.assertTrue(r['unusual_cpu'])
        self.assertFalse(r['output_capture_checked'] or r['promotes_reviewed_catalog'])
        self.assertNotIn('private',json.dumps(r))

    def test_trial_report_is_bound_to_the_package_and_cannot_supply_arbitrary_files(self):
        studio=s.Studio(bridge=object());identity='a'*32
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'prepared').mkdir();audit=b'{"methods": []}'
            (root/'prepared/float32-trial-audit.json').write_bytes(audit)
            sha=hashlib.sha256(audit).hexdigest()
            review=dict(transform_audit_sha256=sha,transform=json.loads(audit),qualification='unverified')
            (root/'trial-review.json').write_text(json.dumps(review))
            studio.jobs[identity]={'id':identity,'result':{'trial_report_available':True,'float32_trial':{'audit_sha256':sha}},'_build':root/'patch.rnbopkg'}
            self.assertEqual(studio.trial_report(identity),review)
            review['transform']['methods']=['tampered'];(root/'trial-review.json').write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,'match'):studio.trial_report(identity)
            studio.jobs[identity]['result']['trial_report_available']=False
            with self.assertRaisesRegex(ValueError,'No detailed'):studio.trial_report(identity)


if __name__=='__main__':unittest.main()
