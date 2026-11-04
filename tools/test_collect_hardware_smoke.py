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

    def test_largest_declared_tolerance_allows_its_binary32_rounding(self):
        tolerance=struct.unpack('<f',struct.pack('<f',.001))[0]
        data=self.record(bit_mismatches='20',within_tolerance_differences='20',
            max_absolute_error='.0008',absolute_tolerance=str(tolerance))
        self.assertEqual(output_metrics(data,{'absolute_tolerance':tolerance},'a'*64)['status'],'pass')
        with self.assertRaises(ValueError):
            output_metrics(dict(data,absolute_tolerance='.0011'),{'absolute_tolerance':.0011},'a'*64)

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
        event_text=''.join('RNBO_SMOKE EVENT '+' '.join(k+'='+v for k,v in event.items())+'\n'for event in getattr(self,'events',[]))
        case_text='RNBO_SMOKE CASE '+' '.join(k+'='+v for k,v in self.data.items())+'\n'
        serial=(case_text+event_text if getattr(self,'events_after_case',False)else event_text+case_text)+done+'\n'
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

    def test_signal_constant_family_uses_parameter_free_patcher_route(self):
        self.constant();self.plan.update(family='rnbo-constants',surface='patcher')
        result=self.result()
        self.assertEqual(result['family'],'rnbo-constants')
        self.assertEqual(result['surface'],'patcher')
        self.assertNotIn('parameter_events',result['cases'][0])

    def test_codebox_family_carries_program_identity_and_rejects_wrong_surface(self):
        self.constant();self.expected['codebox_source_sha256']='f'*64
        for family in ('rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range'):
            self.plan.update(family=family,surface='codebox')
            result=self.result()
            self.assertEqual(result['family'],family)
            self.assertEqual(result['surface'],'codebox')
            self.assertEqual(result['cases'][0]['codebox_source_sha256'],'f'*64)
            self.plan['surface']='patcher'
            with self.assertRaises(ValueError):self.result()
        self.plan['surface']='codebox';self.expected['codebox_source_sha256']='bad'
        with self.assertRaises(ValueError):self.result()

    def test_gen_range_domain_rejects_unrecorded_zero_preroll_or_surface_swap(self):
        self.constant()
        for family in ('gen-range','gen-constants'):
            self.plan.update(family=family,surface='genexpr')
            self.assertEqual(self.result()['family'],family)
        self.plan['prepare_zero_warm_blocks']=4
        with self.assertRaises(ValueError):self.result()
        self.plan['prepare_zero_warm_blocks']=0;self.plan['surface']='patcher'
        with self.assertRaises(ValueError):self.result()

    def test_historical_constant_record_keeps_its_public_shape(self):
        self.constant();self.data.pop('first_mismatch_call');self.data.pop('expected_block_count')
        result=self.result();case=result['cases'][0]
        self.assertNotIn('first_mismatch_call',case);self.assertNotIn('expected_block_count',case)
        self.assertNotIn('expected_stream_sha256',case);self.assertNotIn('expected_stream_policy',result)


class SmokeBoundaryParameterTests(unittest.TestCase):
    """Saved records bind actual event observations without replaying any DSP."""
    save=SmokeStatefulStreamTests.save
    result=SmokeStatefulStreamTests.result

    def setUp(self):
        SmokeStatefulStreamTests.setUp(self)
        SmokeStatefulStreamTests.passing(self)
        self.plan.update(family='rnbo-events',surface='patcher',expected_block_storage='shared-512-word-pool')
        self.expected.update(exact_name='abs~',syntax='signal-object',registry_lookup='abs~',
            expected_parameter_count=2,parameter_schema_sha256='f'*64,absolute_tolerance=0,
            strict_zero_sign_channels=2,
            parameters=[{'id':name,'minimum':-8.,'maximum':8.,'initial':0.,'exponent':1.,'steps':0}for name in ('drive','beta')])
        actions=[];self.events=[]
        for ordinal,(call,slot,value,elapsed)in enumerate(((0,0,.25,2),(0,1,-.5,3),(19,0,-0.,5),(19,0,0.,7))):
            value_word=struct.unpack('<I',struct.pack('<f',value))[0]
            normalized_word=struct.unpack('<I',struct.pack('<f',(value+8.)/16.))[0]
            actions.append({'before_call':call,'id':('drive','beta')[slot],'parameter_slot':slot,
                            'value_word':value_word,'normalized_word':normalized_word})
            self.events.append({'case_id':self.expected['id'],'ordinal':str(ordinal),'before_call':str(call),
                'parameter_slot':str(slot),'resolved_index':str(1-slot),'value_word':f'{value_word:08x}',
                'actual_word':f'{0x80000000 if ordinal==3 else value_word:08x}',
                'normalized_word':f'{normalized_word:08x}','event_us':str(elapsed)})
        self.expected['parameter_events']=actions
        self.plan['expected_block_pool']=self.expected.pop('expected_blocks')
        self.plan['expected_reference_unique_blocks']=20
        self.expected['expected_block_indices']=list(range(20))
        self.data.update(parameter_count='2',parameter_events_applied='4',event_total_us='17',event_peak_us='7',
                         strict_zero_sign_mismatches='0')

    def test_extra_event_family_keeps_the_same_strict_event_contract(self):
        self.plan['family']='rnbo-events-extra'
        result=self.result()
        self.assertEqual(result['family'],'rnbo-events-extra')
        self.assertEqual(result['cases'][0]['parameter_events_applied'],4)
        self.events[0]['actual_word']='3e800001'
        with self.assertRaises(ValueError):self.result()

    def test_actual_order_readbacks_schema_and_separate_event_cost_are_retained(self):
        result=self.result();case=result['cases'][0]
        self.assertEqual(result['family'],'rnbo-events');self.assertEqual(result['surface'],'patcher')
        self.assertEqual(result['expected_block_storage'],'shared-512-word-pool')
        self.assertEqual(result['expected_reference_unique_blocks'],20)
        self.assertEqual(case['parameter_schema_sha256'],'f'*64);self.assertEqual(case['parameter_count'],2)
        self.assertEqual(case['parameter_events_applied'],4);self.assertEqual(case['event_total_us'],17)
        self.assertEqual(case['event_peak_us'],7);self.assertEqual(case['mean_us'],40.)
        self.assertEqual([e['resolved_index']for e in case['parameter_events']],[1,0,1,1])
        self.assertEqual([e['before_call']for e in case['parameter_events']],[0,0,19,19])
        self.assertTrue(case['parameter_events'][-1]['actual_zero_sign_difference'])
        self.assertEqual(case['parameter_events'][-1]['value_word'],0)
        self.assertEqual(case['parameter_events'][-1]['actual_word'],0x80000000)
        self.assertIn('no within-block event offsets',case['parameter_event_scope'])
        self.assertIn('not isolated opcode cost',case['event_timing_scope'])
        self.assertEqual(case['strict_zero_sign_channels'],2);self.assertEqual(case['strict_zero_sign_mismatches'],0)

    def test_event_order_words_resolution_readbacks_and_case_totals_are_bound(self):
        originals=copy.deepcopy((self.expected,self.events,self.data))
        for mutation in ('order','ordinal','case','call','slot','requested','actual','normalized','index-range','index-changed',
                         'index-collision','duration','sum','peak','count','parameter-count','missing','extra','trailing','extra-key'):
            with self.subTest(mutation=mutation):
                self.expected,self.events,self.data=copy.deepcopy(originals);self.plan['cases']=[self.expected]
                self.events_after_case=False
                if mutation=='order':self.events[0],self.events[1]=self.events[1],self.events[0]
                elif mutation=='ordinal':self.events[1]['ordinal']='0'
                elif mutation=='case':self.events[0]['case_id']='another-case'
                elif mutation=='call':self.events[0]['before_call']='1'
                elif mutation=='slot':self.events[0]['parameter_slot']='1'
                elif mutation=='requested':self.events[0]['value_word']='3e800001'
                elif mutation=='actual':self.events[0]['actual_word']='3e800001'
                elif mutation=='normalized':self.events[0]['normalized_word']='3f040001'
                elif mutation=='index-range':self.events[0]['resolved_index']='2'
                elif mutation=='index-changed':self.events[-1]['resolved_index']='0'
                elif mutation=='index-collision':self.events[1]['resolved_index']='1'
                elif mutation=='duration':self.events[0]['event_us']='-1'
                elif mutation=='sum':self.data['event_total_us']='18'
                elif mutation=='peak':self.data['event_peak_us']='8'
                elif mutation=='count':self.data['parameter_events_applied']='3'
                elif mutation=='parameter-count':self.data['parameter_count']='1'
                elif mutation=='missing':self.events.pop()
                elif mutation=='extra':self.events.append(copy.deepcopy(self.events[-1]))
                elif mutation=='trailing':self.events_after_case=True
                else:self.events[0]['unbound']='field'
                with self.assertRaises(ValueError):self.result()

    def test_parameter_contract_actions_and_fresh_stream_scope_are_closed(self):
        originals=copy.deepcopy((self.expected,self.plan))
        for mutation in ('schema','count-bool','duplicate-id','bounds','exponent','steps','normalized-model','action-id',
                         'action-slot','action-order','strict-mask','tolerance','warmup','surface','storage','missing-policy'):
            with self.subTest(mutation=mutation):
                self.expected,self.plan=copy.deepcopy(originals);self.plan['cases']=[self.expected]
                if mutation=='schema':self.expected['parameter_schema_sha256']='not-a-hash'
                elif mutation=='count-bool':self.expected['expected_parameter_count']=True
                elif mutation=='duplicate-id':self.expected['parameters'][1]['id']='drive'
                elif mutation=='bounds':self.expected['parameters'][0]['maximum']=-9.
                elif mutation=='exponent':self.expected['parameters'][0]['exponent']=2.
                elif mutation=='steps':self.expected['parameters'][0]['steps']=1
                elif mutation=='normalized-model':self.expected['parameter_events'][0]['normalized_word']+=1
                elif mutation=='action-id':self.expected['parameter_events'][0]['id']='lookalike'
                elif mutation=='action-slot':self.expected['parameter_events'][0]['parameter_slot']=True
                elif mutation=='action-order':self.expected['parameter_events'][0]['before_call']=19
                elif mutation=='strict-mask':self.expected['strict_zero_sign_channels']=0
                elif mutation=='tolerance':self.expected['absolute_tolerance']=1e-6
                elif mutation=='warmup':self.plan['prepare_zero_warm_blocks']=4
                elif mutation=='surface':self.plan['surface']='genexpr'
                elif mutation=='storage':self.plan['expected_block_storage']='flat'
                else:self.plan.pop('expected_stream_policy')
                with self.assertRaises(ValueError):self.result()

    def strict_zero_failure(self):
        self.plan['expected_block_pool'][6][17]=0
        self.rehash_stream()
        self.data.update(status='output_mismatch',bit_mismatches='1',numeric_mismatches='1',
            strict_zero_sign_mismatches='1',first_mismatch_call='6',first_mismatch_word='17',
            first_actual='80000000',first_expected='00000000',max_absolute_error='0')

    def test_strict_right_zero_is_a_numeric_failure_with_raw_witness_not_finite_error(self):
        self.strict_zero_failure();case=self.result()['cases'][0]
        self.assertEqual(case['numeric_mismatches'],1);self.assertEqual(case['strict_zero_sign_mismatches'],1)
        self.assertEqual(case['zero_sign_differences'],0);self.assertEqual(case['within_tolerance_differences'],0)
        self.assertEqual(case['max_absolute_error'],0);self.assertEqual(case['first_mismatch_call'],6)
        self.assertEqual(case['witness'],{'first_actual':'80000000','first_expected':'00000000'})
        originals=copy.deepcopy((self.expected,self.data,self.plan))
        for mutation in ('unmasked-left','missing-subtype','zero-subtype','too-many','nonfinite-overlap','phantom-finite'):
            with self.subTest(mutation=mutation):
                self.expected,self.data,self.plan=copy.deepcopy(originals);self.plan['cases']=[self.expected]
                if mutation=='unmasked-left':
                    self.plan['expected_block_pool'][6][16]=0;self.data['first_mismatch_word']='16'
                    self.rehash_stream()
                elif mutation=='missing-subtype':self.data.pop('strict_zero_sign_mismatches')
                elif mutation=='zero-subtype':self.data['strict_zero_sign_mismatches']='0'
                elif mutation=='too-many':self.data['strict_zero_sign_mismatches']='2'
                elif mutation=='nonfinite-overlap':self.data['nonfinite_outputs']='1'
                else:self.data.update(numeric_mismatches='2',bit_mismatches='2')
                with self.assertRaises(ValueError):self.result()

    def rehash_stream(self):
        self.expected['expected_stream_sha256']=hashlib.sha256(b''.join(
            struct.pack('<512I',*self.plan['expected_block_pool'][index])for index in self.expected['expected_block_indices'])).hexdigest()

    def test_compact_pool_indices_count_words_and_stream_identity_are_bound(self):
        original=copy.deepcopy((self.expected,self.plan))
        for mutation in ('missing-index','short-index','negative-index','index-bool','index-float','index-outside',
                         'wrong-first','wrong-later','missing-pool','pool-count','pool-count-bool','pool-shape',
                         'pool-word-bool','pool-word-nonfinite','duplicate-pool','stream-hash','mixed-flat'):
            with self.subTest(mutation=mutation):
                self.expected,self.plan=copy.deepcopy(original);self.plan['cases']=[self.expected]
                if mutation=='missing-index':self.expected.pop('expected_block_indices')
                elif mutation=='short-index':self.expected['expected_block_indices'].pop()
                elif mutation=='negative-index':self.expected['expected_block_indices'][6]=-1
                elif mutation=='index-bool':self.expected['expected_block_indices'][6]=True
                elif mutation=='index-float':self.expected['expected_block_indices'][6]=6.
                elif mutation=='index-outside':self.expected['expected_block_indices'][6]=20
                elif mutation=='wrong-first':self.expected['expected_block_indices'][0]=1
                elif mutation=='wrong-later':self.expected['expected_block_indices'][6]=7
                elif mutation=='missing-pool':self.plan.pop('expected_block_pool')
                elif mutation=='pool-count':self.plan['expected_reference_unique_blocks']=19
                elif mutation=='pool-count-bool':self.plan['expected_reference_unique_blocks']=True
                elif mutation=='pool-shape':self.plan['expected_block_pool'][6].pop()
                elif mutation=='pool-word-bool':self.plan['expected_block_pool'][6][17]=True
                elif mutation=='pool-word-nonfinite':self.plan['expected_block_pool'][6][17]=0x7f800000
                elif mutation=='duplicate-pool':self.plan['expected_block_pool'][6]=copy.deepcopy(self.plan['expected_block_pool'][5])
                elif mutation=='stream-hash':self.expected['expected_stream_sha256']='0'*64
                else:self.expected['expected_blocks']=copy.deepcopy(self.plan['expected_block_pool'])
                with self.assertRaises(ValueError):self.result()

    def test_new_zero_parameter_case_fields_do_not_change_historical_public_shape(self):
        SmokeStatefulStreamTests.setUp(self)
        self.events=[]
        baseline=self.result()['cases'][0]
        self.data.update(parameter_count='0',parameter_events_applied='0',event_total_us='0',event_peak_us='0',strict_zero_sign_mismatches='0')
        self.assertEqual(self.result()['cases'][0],baseline)
        self.data['parameter_events_applied']='1'
        with self.assertRaises(ValueError):self.result()


if __name__=='__main__':unittest.main()
