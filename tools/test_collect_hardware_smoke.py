# SPDX-License-Identifier: MIT
import unittest
import struct
from collect_hardware_smoke import cpu_metrics,fields,output_metrics


class SmokeCpuReviewTests(unittest.TestCase):
    def test_steady_work_and_spikes_are_distinguished(self):
        self.assertEqual(cpu_metrics([50]*16),(50.,50.,50,[]))
        self.assertEqual(cpu_metrics([50]*15+[500]),(50.,78.125,500,['peak_spike']))
        self.assertEqual(cpu_metrics([600]*16),(600.,600.,600,['median_budget']))

    def test_incomplete_or_invalid_observations_reject(self):
        for times in ([50]*15,[True]*16,[-1]*16):
            with self.assertRaises(ValueError):cpu_metrics(times)
        with self.assertRaises(ValueError):fields('RNBO_SMOKE CASE id=a id=b','RNBO_SMOKE CASE ')


class SmokeOutputPolicyTests(unittest.TestCase):
    def record(self,**changes):
        data=dict(samples='10240',bit_mismatches='0',zero_sign_differences='0',status='pass',finalized='1',
            numeric_mismatches='0',within_tolerance_differences='0',nonfinite_outputs='0',
            max_absolute_error='0',absolute_tolerance='0',input_words_sha256='a'*64)
        data.update(changes)
        return data

    def test_approximate_pass_retains_all_raw_word_differences(self):
        data=self.record(bit_mismatches='20',within_tolerance_differences='20',
            max_absolute_error='1e-7',absolute_tolerance='2e-6')
        result=output_metrics(data,{'absolute_tolerance':2e-6,'input_words_sha256':'a'*64},'b'*64)
        self.assertEqual(result['status'],'pass');self.assertEqual(result['bit_mismatches'],20)
        self.assertEqual(result['numeric_mismatches'],0)

    def test_nonfinite_values_are_failures_without_infinite_error_summaries(self):
        data=self.record(status='output_mismatch',bit_mismatches='20',numeric_mismatches='20',nonfinite_outputs='20')
        self.assertEqual(output_metrics(data,{},'a'*64)['nonfinite_outputs'],20)
        for field,value in [('max_absolute_error','inf'),('nonfinite_outputs','21')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                output_metrics(dict(data,**{field:value}),{},'a'*64)

    def test_binary_log_fields_preserve_errors_without_decimal_formatting(self):
        tolerance=struct.unpack('<f',struct.pack('<f',2e-6))[0]
        data=self.record(bit_mismatches='20',within_tolerance_differences='20',
            max_absolute_error_bits='3e80000000000000',absolute_tolerance_bits='360637bd')
        # 0x3e80000000000000 is exact2^-23, and 0x360637bd is binary32(2e-6).
        result=output_metrics(data,{'absolute_tolerance':tolerance},'a'*64)
        self.assertEqual(result['max_absolute_error'],2**-23)
        self.assertEqual(result['absolute_tolerance'],tolerance)
        with self.assertRaises(ValueError):output_metrics(dict(data,max_absolute_error_bits='xyz'),{},'a'*64)

    def test_input_identity_tolerance_and_counter_partition_are_bound(self):
        original=self.record()
        for change in ({'input_words_sha256':'b'*64},{'absolute_tolerance':'2e-6'},
                {'within_tolerance_differences':'1'},{'max_absolute_error':'nan'},
                {'status':'output_mismatch'},{'max_absolute_error':'1e-7'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                output_metrics(dict(original,**change),{},'a'*64)

    def test_zero_sign_diagnostic_and_legacy_gate_remain_exact(self):
        data=self.record(bit_mismatches='20',zero_sign_differences='20')
        self.assertEqual(output_metrics(data,{},'a'*64)['status'],'pass')
        legacy={k:data[k]for k in ('samples','bit_mismatches','zero_sign_differences','status','finalized')}
        self.assertEqual(output_metrics(legacy,{},'a'*64)['status'],'pass')
        for expected in ({'absolute_tolerance':1e-6},{'input_words':(0,)*512}):
            with self.assertRaises(ValueError):output_metrics(legacy,expected,'a'*64)


if __name__=='__main__':unittest.main()
