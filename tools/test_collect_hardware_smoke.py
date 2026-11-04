# SPDX-License-Identifier: MIT
import unittest
import struct
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from collect_hardware_smoke import cpu_metrics,fields,output_metrics,collect,canonical


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


class SmokeStatefulStreamTests(unittest.TestCase):
    """Synthetic saved receipts exercise call-index binding, never a device."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.build=self.root/'build';self.run=self.root/'run'
        self.build.mkdir();self.run.mkdir()
        word=lambda value:struct.unpack('<I',struct.pack('<f',value))[0]
        self.blocks=[[word(call)]*512 for call in range(20)]
        fingerprint=hashlib.sha256(b''.join(struct.pack('<512I',*b)for b in self.blocks)).hexdigest()
        self.expected={'id':'synthetic-sequence','exact_name':'History','syntax':'call','registry_lookup':'History',
            'reference_policy':'synthetic-call-index-reference','module_sha256':'d'*64,'source_sha256':'e'*64,
            'expected':copy.deepcopy(self.blocks[0]),'expected_blocks':copy.deepcopy(self.blocks),'expected_stream_sha256':fingerprint}
        self.plan={'family':'gen-stateful','surface':'genexpr','prepare_zero_warm_blocks':0,
            'expected_stream_policy':'fresh constructor then four manual warm and sixteen timed calls',
            'input_words_sha256':'b'*64,'reference_source_sha256':'c'*64,'cases':[self.expected],'compile_failures':[]}
        self.data={'id':'synthetic-sequence','module_sha256':'d'*64,'status':'output_mismatch','samples':'10240',
            'bit_mismatches':'1','zero_sign_differences':'0','numeric_mismatches':'1','within_tolerance_differences':'0',
            'nonfinite_outputs':'0','max_absolute_error':'3','absolute_tolerance':'0','input_words_sha256':'b'*64,
            'first_mismatch_word':'17','first_mismatch_call':'6','expected_block_count':'20',
            'first_actual':'41100000','first_expected':'40c00000',
            'mean_us':'40','median_us':'40','peak_us':'40','times_us':','.join(['40']*16),
            'review_cpu':'0','cpu_reasons':'none','context_bytes':'128','arena_high_water':'0','finalized':'1',
            'prepare_zero_warm_blocks':'0'}

    def save(self):
        plan_sha=hashlib.sha256(canonical(self.plan)).hexdigest()
        passed=int(self.data['status']=='pass')
        done='RNBO_SMOKE DONE '+f"firmware_elf_sha256={'a'*64} plan_sha256={plan_sha} cases=1 passed={passed} mismatched={1-passed} cpu_review=0 images=1 finalized_images=1"
        serial='RNBO_SMOKE CASE '+' '.join(k+'='+v for k,v in self.data.items())+'\n'+done+'\n'
        build={'format':'rnbo-hardware-smoke-build-v1','board':'xiao','plan':self.plan,'plan_sha256':plan_sha,
               'artifacts':{'app.elf':{'sha256':'a'*64}}}
        (self.build/'build-report.json').write_bytes(canonical(build));(self.run/'test-serial.log').write_text(serial)
        receipt={'format':'rnbo-hardware-smoke-run-v1','board':'xiao','result':'completed','left_installed':True,
            'test_build_report_sha256':hashlib.sha256((self.build/'build-report.json').read_bytes()).hexdigest(),
            'serial_log_sha256':hashlib.sha256(serial.encode()).hexdigest(),'done_line':done,'test_elf_sha256':'a'*64}
        (self.run/'hardware-smoke.json').write_bytes(canonical(receipt))

    def result(self):
        self.save();return collect(self.build,self.run)

    def test_later_call_witness_uses_its_actual_expected_block(self):
        value=self.result();case=value['cases'][0]
        self.assertEqual(case['first_mismatch_call'],6);self.assertEqual(case['first_mismatch_word'],17)
        self.assertEqual(case['witness']['first_expected'],'40c00000')
        self.assertEqual(case['expected_stream_sha256'],self.expected['expected_stream_sha256'])
        self.assertEqual(case['expected_block_count'],20);self.assertEqual(value['family'],'gen-stateful')
        self.assertEqual(value['expected_stream_policy'],self.plan['expected_stream_policy'])
        # A self-consistent old block0 witness must still fail the stream gate.
        self.data.update(first_expected='00000000',max_absolute_error='9')
        with self.assertRaisesRegex(ValueError,'call-specific reference'):self.result()

    def test_stateful_call_count_and_witness_fields_are_mandatory(self):
        original=copy.deepcopy(self.data)
        for mutation in ('call-missing','count-missing','both-missing','call-range','count','word-range'):
            with self.subTest(mutation=mutation):
                self.data=copy.deepcopy(original)
                if mutation=='call-missing':self.data.pop('first_mismatch_call')
                elif mutation=='count-missing':self.data.pop('expected_block_count')
                elif mutation=='both-missing':self.data.pop('first_mismatch_call');self.data.pop('expected_block_count')
                elif mutation=='call-range':self.data['first_mismatch_call']='20'
                elif mutation=='count':self.data['expected_block_count']='1'
                else:self.data['first_mismatch_word']='512'
                with self.assertRaises(ValueError):self.result()

    def test_stream_hash_shape_first_block_and_constructor_epoch_are_bound(self):
        original=copy.deepcopy(self.expected)
        for mutation in ('hash','shape','legacy-block','bool-word','warmup','policy'):
            with self.subTest(mutation=mutation):
                self.expected=copy.deepcopy(original);self.plan['cases']=[self.expected]
                self.plan['prepare_zero_warm_blocks']=0;self.plan['expected_stream_policy']='fresh constructor'
                if mutation=='hash':self.expected['expected_stream_sha256']='0'*64
                elif mutation=='shape':self.expected['expected_blocks'].pop()
                elif mutation=='legacy-block':self.expected['expected'][17]=1
                elif mutation=='bool-word':self.expected['expected_blocks'][6][17]=True
                elif mutation=='warmup':self.plan['prepare_zero_warm_blocks']=4
                else:self.plan.pop('expected_stream_policy')
                with self.assertRaises(ValueError):self.result()

    def passing(self):
        self.data.update(status='pass',bit_mismatches='0',numeric_mismatches='0',max_absolute_error='0',
            first_mismatch_word=str(0xffffffff),first_mismatch_call=str(0xffffffff))

    def test_passing_stream_has_no_witness_but_keeps_reference_identity(self):
        self.passing();case=self.result()['cases'][0]
        self.assertIsNone(case['first_mismatch_call']);self.assertIsNone(case['first_mismatch_word'])
        self.assertEqual(case['expected_stream_sha256'],self.expected['expected_stream_sha256'])
        self.data['first_mismatch_call']='0'
        with self.assertRaisesRegex(ValueError,'Passing case'):self.result()

    def constant(self):
        self.plan['family']='gen-math';self.plan.pop('expected_stream_policy')
        self.expected.pop('expected_blocks');self.expected.pop('expected_stream_sha256')
        self.data.update(expected_block_count='1',first_expected='00000000',max_absolute_error='9')

    def test_new_constant_record_can_report_call_without_changing_reference(self):
        self.constant();case=self.result()['cases'][0]
        self.assertEqual(case['first_mismatch_call'],6);self.assertEqual(case['expected_block_count'],1)
        self.assertNotIn('expected_stream_sha256',case)

    def test_historical_constant_record_keeps_its_public_shape(self):
        self.constant();self.data.pop('first_mismatch_call');self.data.pop('expected_block_count')
        result=self.result();case=result['cases'][0]
        self.assertNotIn('first_mismatch_call',case);self.assertNotIn('expected_block_count',case)
        self.assertNotIn('expected_stream_sha256',case);self.assertNotIn('expected_stream_policy',result)


if __name__=='__main__':unittest.main()
