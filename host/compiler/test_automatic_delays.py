# SPDX-License-Identifier: MIT
"""Automatic policy fallbacks and real local native-export integration."""
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

from float32_delays import automatic_float32_delays
from prepare import cpp_code_mask, prepare
from build import verify_prepared


class AutomaticFallbackTests(unittest.TestCase):
    def test_no_delays_is_a_recorded_noop(self):
        source=b'// Float64BufferRef delaytilde_01_del_buffer;\nvoid process() {}'
        result,audit=automatic_float32_delays(source,code_mask=cpp_code_mask)
        self.assertEqual(result,source)
        self.assertEqual(audit['converted'],[])
        self.assertEqual(audit['retained_float64'],[])
        self.assertEqual(audit['buffer_data_bytes_saved'],0)

    def test_unknown_ordinary_ring_retains_native_storage(self):
        source=b'Float64BufferRef delaytilde_01_del_buffer;'
        result,audit=automatic_float32_delays(source,code_mask=cpp_code_mask)
        self.assertEqual(result,source)
        self.assertEqual(len(audit['retained_float64']),1)
        self.assertIn('expected one generated method',audit['retained_float64'][0]['reason'])

    def test_comb_gen_and_external_names_are_not_automatically_rewritten(self):
        source=b'Float64BufferRef comb_tilde_01_feedBack_buffer;\nFloat64BufferRef gen_delay_buffer;\nFloat64BufferRef external;'
        result,audit=automatic_float32_delays(source,code_mask=cpp_code_mask)
        self.assertEqual(result,source)
        self.assertEqual(len(audit['retained_float64']),3)
        self.assertFalse(audit['hardware_qualified'])
        self.assertFalse(audit['target_cpu_gain_measured'])


class NativeAutomaticDelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[2]
        cls.export=Path(os.environ.get('RNBO_S3_TEST_NATIVE_DELAY_EXPORT',
            root/'build/private/studio/8b467cd380184d779f90fb8195aa0e1d/export'))
        if not (cls.export/'rnbo_source.h').is_file():
            raise unittest.SkipTest('Supply a local native SawSAHArpy export; generated source is not distributed')
        cls.source=(cls.export/'rnbo_source.h').read_bytes()

    def test_default_prepare_converts_and_explicit_reference_preserves(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            default=prepare(self.export,root/'default','rnbomatic','main')
            reference=prepare(self.export,root/'reference','rnbomatic','main',delay_storage_policy='float64')
            self.assertEqual(default['delay_storage']['buffer_data_bytes_saved'],131072)
            self.assertEqual(default['delay_storage']['policy'],'auto')
            self.assertTrue(default['float32_delay_storage'])
            self.assertNotIn('float32_delay_storage',reference)
            self.assertEqual(reference['delay_storage']['policy'],'float64')
            before=(root/'reference/rnbo_source.h').read_bytes()
            after=(root/'default/rnbo_source.h').read_bytes()
            self.assertEqual(after.replace(b'Float32Buffer',b'Float64Buffer'),before)
            self.assertEqual(default['source_tree_sha256'],reference['source_tree_sha256'])
            self.assertEqual(default['scheduler_time'],'float64')
            provenance,_,_=verify_prepared(root/'default')
            self.assertTrue(any(c['name']=='rnbo-1.4.4-auto-float32-ordinary-delays-v1' for c in provenance['adaptations']))
            self.assertEqual((self.export/'rnbo_source.h').read_bytes(),self.source)

    def test_partial_conversion_does_not_block_on_an_unknown_ring(self):
        source=self.source+b'\nFloat64BufferRef delaytilde_02_del_buffer;\n'
        result,audit=automatic_float32_delays(source,code_mask=cpp_code_mask)
        self.assertEqual(len(audit['converted']),1)
        self.assertEqual(audit['retained_float64'][0]['reference'],'delaytilde_02_del_buffer')
        self.assertIn(b'Float64BufferRef delaytilde_02_del_buffer;',result)
        self.assertEqual(result.replace(b'Float32Buffer',b'Float64Buffer'),source)

    def test_changed_reader_or_external_ownership_falls_back_unchanged(self):
        owner=re.search(rb'this->delaytilde_01_del_bufferobj = initDataRef\([\s\S]*?\);',self.source)[0]
        external=self.source.replace(owner,owner.replace(b'true,',b'false,'),1)
        for source in (external,self.source.replace(b'Int interp)',b'Int unknown)')):
            self.assertNotEqual(source,self.source)
            result,audit=automatic_float32_delays(source,code_mask=cpp_code_mask)
            self.assertEqual(result,source)
            self.assertEqual(audit['converted'],[])
            self.assertEqual(len(audit['retained_float64']),1)

    def test_repeated_policy_does_not_convert_other_buffers_or_count_savings_twice(self):
        first,audit=automatic_float32_delays(self.source,code_mask=cpp_code_mask)
        second,repeated=automatic_float32_delays(first,code_mask=cpp_code_mask)
        self.assertEqual(first,second)
        self.assertEqual(repeated['converted'],[])
        self.assertEqual(repeated['buffer_data_bytes_saved'],0)


if __name__=='__main__':
    unittest.main()
