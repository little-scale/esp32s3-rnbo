# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable Voice PE codec, framing, fades, metadata and rate admission; no USB."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import test_player_store as store
ROOT=Path(__file__).resolve().parents[1]
PORT=ROOT/'firmware/boards/voice-pe'

class VoicePortableTests(unittest.TestCase):
    def compile_run(self,sources,includes=(),libraries=(),defines=()):
        with tempfile.TemporaryDirectory() as tmp:
            executable=Path(tmp)/'test'
            command=['cc','-std=c11','-O1','-Wall','-Wextra','-Werror',
                     '-fsanitize=undefined,bounds,float-cast-overflow','-fno-sanitize-recover=all',
                     *['-D'+d for d in defines],
                     *['-I'+str(p) for p in (PORT,*includes)],*map(str,sources),*libraries,'-o',str(executable)]
            subprocess.run(command,check=True,capture_output=True)
            return subprocess.run([str(executable)],check=True,capture_output=True,text=True).stdout

    def test_codec_sequences_and_every_failure_position_at_both_rates(self):
        result=self.compile_run([ROOT/'tests/voice_pe/codec_test.c',PORT/'voice_pe_codec_sequence.c'])
        self.assertIn('16000 Hz, 0 dB',result);self.assertIn('48000 Hz, 0 dB',result)
        self.assertIn('140 initialization I/O failure positions',result)

    def test_packing_ring_mapping_and_sample_wise_transition_endpoints(self):
        result=self.compile_run([ROOT/'tests/voice_pe/format_transition_test.c',PORT/'voice_pe_format.c',PORT/'voice_pe_controls.c'],
                                [ROOT/'firmware/components/pcm_output/include'],['-lm'])
        self.assertIn('16/48k fade endpoints',result)

    def test_paused_boot_checks_are_bounded_silent_and_generation_scoped(self):
        for rate in (16000,48000):
            result=self.compile_run([ROOT/'tests/voice_pe/boot_probe_test.c',ROOT/'firmware/components/pcm_output/pcm_output.c'],
                [ROOT/'firmware/main',ROOT/'firmware/components/pcm_output/include',ROOT/'module-sdk/include'],
                ['-lm'],[f'RNBO_S3_SAMPLE_RATE={rate}u'])
            self.assertIn('bounded paused boot, stale generations, finite checks and forced-silent PCM',result)

    def test_semantic_input_plan_uses_real_c_parser(self):
        cjson=Path(os.environ.get('IDF_PATH',str(Path.home()/'esp/esp-idf')))/'components/json/cJSON'
        if not (cjson/'cJSON.c').is_file():self.skipTest('Real cJSON source from ESP-IDF is required')
        result=self.compile_run([ROOT/'tests/voice_pe/input_plan_test.c',ROOT/'firmware/components/player_inputs/player_voice_pe.c',cjson/'cJSON.c'],
                                [cjson,ROOT/'firmware/components/player_inputs/include'],['-lm'])
        self.assertIn('Voice PE source/schema/board/ID admission',result)

    def test_real_c_store_rejects_wrong_rate_before_accepting_metadata(self):
        for target in (16000,48000):
            # Reuse the actual C store harness and stubs at a different profile;
            # no inherited legacy test methods are executed by this local helper.
            kind=type('LocalVoiceStore',(store.PlayerStoreTests,),{'sample_rate':target})
            kind.setUpClass()
            try:
                instance=kind();instance.setUp()
                for source in (16000,48000,44100):
                    instance.run_native('parse',instance.fixture(store.package(rate=source)),'yes' if source==target else 'no')
                meta={'name':'Controls','source_sha256':'a'*64,'initial_volume':0,
                      'voice_pe_inputs':{'version':1,'board':'voice-pe','bindings':[{'input':'dial','parameter_id':'freq'}]}}
                instance.run_native('parse',instance.fixture(store.package(meta,rate=target,version=4)),'yes')
                instance.run_native('parse',instance.fixture(store.package(meta,rate=target,version=1)),'no')
                meta['audio_profile']='voice-pe-48000-256-v1' if target==16000 else 'voice-pe-16000-256-v1'
                instance.run_native('parse',instance.fixture(store.package(meta,rate=target,version=4)),'no')
            finally:kind.doClassCleanups()

if __name__=='__main__':unittest.main()
