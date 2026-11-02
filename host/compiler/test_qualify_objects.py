# SPDX-License-Identifier: MIT
"""Negative checks for original object qualification measurements."""
import array
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import wave

from qualify_objects import channels,compare,semantic_checks,stimulus


class ObjectMeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog=Path(__file__).resolve().parents[2]/"tests/fixtures/objects/catalog.json"
        cls.fixtures={f["id"]:f for f in json.loads(catalog.read_text())["fixtures"]}
        cls.fx_fixtures={f["id"]:f for f in json.loads(catalog.with_name("catalog-fx.json").read_text())["fixtures"]}

    def test_stereo_float_bounds_and_finiteness(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"audio.f32"
            path.write_bytes(struct.pack("<ffff",1,2,3,4))
            self.assertEqual(channels(path,2),([1,3],[2,4]))
            with self.assertRaisesRegex(ValueError,"Truncated"):channels(path,3)
            path.write_bytes(struct.pack("<ff",math.nan,0))
            with self.assertRaisesRegex(ValueError,"Non-finite"):channels(path,1)

    def test_mtof_known_a440_and_wrong_tuning(self):
        fixture=self.fixtures["mtof-varying"];settings={"parameters":{"depth":0}}
        left=[69/128]*128;right=[440/2048]*128
        result=semantic_checks(fixture,settings,(left,right))
        self.assertEqual(result["analytic_maximum_absolute_error"],0)
        with self.assertRaisesRegex(ValueError,"mtof analytic"):
            semantic_checks(fixture,settings,(left,[480/2048]*128))

    def test_mtof_varying_case_rejects_cached_input(self):
        fixture=self.fixtures["mtof-varying"]
        with self.assertRaisesRegex(ValueError,"mostly cached"):
            semantic_checks(fixture,{"parameters":{}},([69/128]*128,[440/2048]*128))

    def test_cycle_uses_phase_and_detects_wrong_waveform(self):
        fixture=self.fixtures["cycle-scalar"];phase=[i/512 for i in range(512)]
        cosine=[math.cos(2*math.pi*p) for p in phase]
        semantic_checks(fixture,{"parameters":{}},(cosine,phase))
        with self.assertRaisesRegex(ValueError,"phase/table"):
            semantic_checks(fixture,{"parameters":{}},([0]*512,phase))

    def test_saw_rejects_a_sine_with_correct_frequency(self):
        fixture=self.fixtures["saw-signal"];n=8192
        phase=[(i*440/44100)%1 for i in range(n)]
        sine=[.1*math.sin(2*math.pi*p) for p in phase]
        with self.assertRaisesRegex(ValueError,"harmonic"):
            semantic_checks(fixture,{"parameters":{}},(sine,phase))

    def test_stateful_silence_allows_decay_but_rejects_nondecaying_tail(self):
        fixture=self.fixtures["reson-modulated"];settings={"parameters":{"level":0}}
        semantic_checks(fixture,settings,([0]*8192,[.1]*4096+[0]*4096))
        with self.assertRaisesRegex(ValueError,"did not decay"):
            semantic_checks(fixture,settings,([0]*8192,[.1]*8192))

    def test_pcm_and_float_limits_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            paths=[]
            for name,word in (("a",0),("b",2)):
                path=Path(directory)/(name+".wav");paths.append(path)
                with wave.open(str(path),"wb") as stream:
                    stream.setparams((2,2,44100,0,"NONE","not compressed"))
                    stream.writeframes(struct.pack("<hh",word,word))
            result=compare(([0],[0]),([0],[0]),*paths,{"maximum_absolute_error":0,"maximum_pcm_lsb_error":1,"relative_rms_level_difference":0})
            self.assertFalse(result["passed"])
            self.assertEqual(result["maximum_pcm_lsb_error"],2)

    def test_unknown_semantic_kind_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"Unknown object semantic"):
            semantic_checks({"semantic":{"kind":"typo"}},{"parameters":{}},([0],[0]))

    def test_wrong_pcm_rate_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"wrong.wav"
            with wave.open(str(path),"wb") as stream:
                stream.setparams((2,2,48000,0,"NONE","not compressed"))
                stream.writeframes(struct.pack("<hh",0,0))
            with self.assertRaisesRegex(ValueError,"PCM rate/frame"):
                compare(([0],[0]),([0],[0]),path,path,{"maximum_absolute_error":0,"maximum_pcm_lsb_error":0,"relative_rms_level_difference":0})

    def test_fx_midi_stimulus_has_meaningful_pitch_and_disjoint_pilot(self):
        fixture=self.fx_fixtures["mtof-fx"]
        left,right=stimulus(fixture,{"stimulus":{}},44100)
        self.assertEqual(left[0],60)
        self.assertGreater(min(left),47.9)
        self.assertLess(max(left),72.1)
        self.assertGreater(max(left)-min(left),11)
        self.assertLessEqual(max(map(abs,right)),.125)
        self.assertEqual((left,right),stimulus(fixture,{"stimulus":{}},44100))

    def test_fx_mtof_checks_exact_external_input_and_pilot(self):
        fixture=self.fx_fixtures["mtof-fx"];case={"parameters":{},"stimulus":{"depth":0}}
        inputs=([69]*128,[.125]*128)
        semantic_checks(fixture,case,([.125]*128,[440/2048]*128),inputs)
        with self.assertRaisesRegex(ValueError,"analytic/pilot"):
            semantic_checks(fixture,case,([0]*128,[440/2048]*128),inputs)

    def test_unknown_stimulus_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"Unknown external stimulus"):
            stimulus({"stimulus":{"kind":"typo"}},{},1)

    def test_local_compiled_fx_probe_rejects_bad_input_sizes_and_nan(self):
        root=Path(__file__).resolve().parents[2]
        probe=root/"build/object-qualification/fx-1/native/mtof-fx/strict/fx_probe"
        if not probe.is_file():self.skipTest("Build the local FX fixture probe first")
        valid=struct.pack("<ff",60,.125)*256
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"input.f32";out=Path(directory)/"output.wav"
            for payload in (valid[:-1],valid+b"x",struct.pack("<f",math.nan)+valid[4:]):
                path.write_bytes(payload)
                result=subprocess.run([str(probe),"--input-float",str(path),"--output",str(out),"--blocks","1","--warmup","0"],capture_output=True)
                self.assertNotEqual(result.returncode,0)
            path.write_bytes(valid)
            result=subprocess.run([str(probe),"--input-float",str(path),"--output",str(out),"--blocks","1","--warmup","0"],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=="__main__":unittest.main()
