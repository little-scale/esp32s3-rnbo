# SPDX-License-Identifier: MIT
"""Corrected sparse-inlet source admission and enforced raw pilot, no devices."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

import build_hardware_smoke as builder
import collect_hardware_smoke as collector

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'tests/fixtures/smoke/rnbo-character-constants'
canonical=builder.canonical
digest=lambda value:hashlib.sha256(canonical(value)).hexdigest()


def catalog(part=1):return json.loads((BASE/f'catalog-part{part}.json').read_bytes())


def reference():
    spec=importlib.util.spec_from_file_location('independent_character_reference',BASE/'reference.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def plan(part=1):
    source=catalog(part);ref=reference();inputs=list(ref.input_words());cases=[]
    for row in source['cases']:
        expected=list(ref.reference_words(row['model'],inputs))
        cases.append(dict(row,module_sha256='d'*64,source_sha256=row['patch_sha256'],
            codebox_source_sha256=hashlib.sha256((BASE/row['codebox']).read_bytes()).hexdigest(),
            input_words=inputs,input_words_sha256=hashlib.sha256(struct.pack('<512I',*inputs)).hexdigest(),
            expected=expected,expected_words_sha256=hashlib.sha256(struct.pack('<512I',*expected)).hexdigest(),
            absolute_tolerance=0))
    return {'family':builder.CHARACTER_FAMILY,'surface':'codebox','partition':source['partition'],
        'catalog_sha256':digest(source),'reference_source_sha256':builder.CHARACTER_REFERENCE_SHA,
        'prepare_zero_warm_blocks':0,'warmup_blocks':4,'timed_blocks':16,
        'strict_zero_sign_channels':2,'raw_pilot_channel':1,'cases':cases,'compile_failures':[],
        'input_words_sha256':cases[0]['input_words_sha256']}


class CharacterSmokeGuards(unittest.TestCase):
    def test_only_corrected_original_43_and_42_partitions_are_accepted(self):
        for part in (1,2):self.assertEqual(builder.character_catalog(catalog(part))['case_count'],44-part)
        with self.assertRaises(builder.ExportError):builder.character_catalog(json.loads((BASE/'catalog.json').read_bytes()))
        for mutation in ('row','order','mask','pilot','partition','family'):
            bad=catalog()
            if mutation=='row':bad['cases'][0]['exact_name']='CHAR_0'
            elif mutation=='order':bad['cases'].reverse()
            elif mutation=='mask':bad['strict_zero_sign_channels']=0
            elif mutation=='pilot':bad['cases'][0]['raw_pilot_channel']=0
            elif mutation=='partition':bad['partition']['index']=True
            else:bad['family']='rnbo-codebox-constants'
            with self.subTest(mutation=mutation),self.assertRaises(builder.ExportError):builder.character_catalog(bad)

    def test_sparse_named_input_maps_only_to_physical_ordinal_zero(self):
        row=catalog()['cases'][0];data=(BASE/row['patch']).read_bytes()
        expected=hashlib.sha256((BASE/row['codebox']).read_bytes()).hexdigest()
        self.assertEqual(builder.checked_character_source(row,data),expected)
        # The old generic surface guard remains closed to this new route.
        with self.assertRaises(builder.ExportError):builder.checked_codebox_source(row,data)
        for mutation in ('old-hole','unused-input-wire','bypass','disabled','body','surface','mask','ordinal'):
            source=json.loads(data);candidate=copy.deepcopy(row)
            if mutation=='old-hole':source['patcher']['lines'][0]['patchline']['destination'][1]=1
            elif mutation=='unused-input-wire':source['patcher']['lines'].append({'patchline':{'source':['left',0],'destination':['program',0]}})
            elif mutation=='bypass':source['patcher']['lines'][2]['patchline']['source']=['right',0]
            elif mutation=='disabled':source['patcher']['lines'][0]['patchline']['disabled']=1
            elif mutation=='body':source['patcher']['boxes'][2]['box']['rnbo_extra_attributes']['code']='out1 = CHAR_A;\nout2 = in1;\n'
            elif mutation=='surface':candidate['surface']='genexpr'
            elif mutation=='mask':candidate['strict_zero_sign_channels']=True
            else:candidate['codebox_pilot_inlet_ordinal']=1
            raw=canonical(source);candidate['patch_sha256']=hashlib.sha256(raw).hexdigest()
            with self.subTest(mutation=mutation),self.assertRaises(builder.ExportError):builder.checked_character_source(candidate,raw)

    def test_parameter_free_header_emits_the_real_worker_mask(self):
        value=plan();collector.character_plan(value)
        header,_=builder.generate_header(value,reference().input_words())
        self.assertEqual(header.count('.strict_zero_sign_channels=2u,'),43)
        self.assertNotIn('.expected_parameter_count=',header)
        for mask in (None,0,1,True):
            bad=copy.deepcopy(value)
            if mask is None:bad['cases'][0].pop('strict_zero_sign_channels')
            else:bad['cases'][0]['strict_zero_sign_channels']=mask
            with self.subTest(mask=mask),self.assertRaises(builder.ExportError):builder.generate_header(bad,reference().input_words())

    def test_collector_requires_the_partition_mask_and_exact_input_cache(self):
        for part in (1,2):collector.character_plan(plan(part))
        for mutation in ('mask','row-mask','pilot','source','body','cache','input','tolerance','warmup','partition','missing'):
            bad=plan();row=bad['cases'][0]
            if mutation=='mask':bad['strict_zero_sign_channels']=0
            elif mutation=='row-mask':row['strict_zero_sign_channels']=0
            elif mutation=='pilot':row['raw_pilot_channel']=0
            elif mutation=='source':row['source_sha256']='0'*64
            elif mutation=='body':row['codebox_source_sha256']='0'*64
            elif mutation=='cache':row['expected'][15]=0;row['expected_words_sha256']=hashlib.sha256(struct.pack('<512I',*row['expected'])).hexdigest()
            elif mutation=='input':row['input_words']=row['input_words'].copy();row['input_words'][15]=0
            elif mutation=='tolerance':row['absolute_tolerance']=1e-6
            elif mutation=='warmup':bad['prepare_zero_warm_blocks']=4
            elif mutation=='partition':bad['partition']['case_count']=42
            else:bad['cases'].pop()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):collector.character_plan(bad)

    def test_raw_negative_zero_pilot_mutation_is_a_failure_in_saved_receipt(self):
        value=plan();lines=[]
        for index,row in enumerate(value['cases']):
            data={'id':row['id'],'module_sha256':row['module_sha256'],'status':'pass','samples':'10240',
                'bit_mismatches':'0','zero_sign_differences':'0','numeric_mismatches':'0','within_tolerance_differences':'0',
                'strict_zero_sign_mismatches':'0','nonfinite_outputs':'0','max_absolute_error':'0','absolute_tolerance':'0',
                'input_words_sha256':row['input_words_sha256'],'first_mismatch_word':str(0xffffffff),
                'first_mismatch_call':str(0xffffffff),'expected_block_count':'1','mean_us':'40','median_us':'40',
                'peak_us':'40','times_us':','.join(['40']*16),'review_cpu':'0','cpu_reasons':'none',
                'context_bytes':'128','arena_high_water':'0','finalized':'1','prepare_zero_warm_blocks':'0'}
            if index==0:data.update(status='output_mismatch',bit_mismatches='1',numeric_mismatches='1',
                strict_zero_sign_mismatches='1',first_mismatch_word='15',first_mismatch_call='0',
                first_actual='00000000',first_expected='80000000')
            lines.append('RNBO_SMOKE CASE '+' '.join(k+'='+v for k,v in data.items()))
        sha=digest(value);done=f"RNBO_SMOKE DONE firmware_elf_sha256={'a'*64} plan_sha256={sha} cases=43 passed=42 mismatched=1 cpu_review=0 images=43 finalized_images=43"
        serial=('\n'.join(lines+[done])+'\n').encode()
        with tempfile.TemporaryDirectory()as temp:
            base=Path(temp);build=base/'build';run=base/'run';build.mkdir();run.mkdir()
            report={'format':'rnbo-hardware-smoke-build-v1','board':'xiao','plan':value,'plan_sha256':sha,
                    'artifacts':{'app.elf':{'sha256':'a'*64}}}
            (build/'build-report.json').write_bytes(canonical(report));(run/'test-serial.log').write_bytes(serial)
            receipt={'format':'rnbo-hardware-smoke-run-v1','board':'xiao','result':'completed','left_installed':True,
                'test_build_report_sha256':digest(report),'serial_log_sha256':hashlib.sha256(serial).hexdigest(),
                'done_line':done,'test_elf_sha256':'a'*64}
            (run/'hardware-smoke.json').write_bytes(canonical(receipt))
            result=collector.collect(build,run)
            self.assertEqual(result['summary']['output_mismatches'],1)
            self.assertEqual(result['cases'][0]['strict_zero_sign_mismatches'],1)
            self.assertEqual(result['cases'][0]['status'],'output_mismatch')
            self.assertEqual(result['raw_pilot_channel'],1)
            self.assertEqual(result['partition'],value['partition'])

    def test_optional_actual_partitions_and_previous_plan_headers(self):
        from test_smoke_gen_delay import GenDelayPreparedTests
        # Reuse the saved-data assertion; this does not rerun any DSP.
        GenDelayPreparedTests().test_actual_prior_gen_delay_and_dbtoa_plan_headers_replay_unchanged()
        state=ROOT/'build/hardware-smoke-rnbo-signal-state-followup-v1/build-report.json'
        if state.is_file():
            previous=json.loads(state.read_bytes())
            current,inputs,_=builder.prepare_plan(ROOT/'tests/fixtures/smoke/rnbo-signal-state-followup/catalog.json',
                ROOT/'build/hardware/rnbo-signal-state-followup-smoke-modules-v1/batch-report.json')
            self.assertEqual(canonical(current),canonical(previous['plan']))
            header,_=builder.generate_header(current,inputs)
            self.assertEqual(hashlib.sha256(header.encode()).hexdigest(),previous['header_sha256'])
        for part in (1,2):
            batch=ROOT/f'build/hardware/rnbo-character-constants-smoke-modules-v2-part{part}/batch-report.json'
            if not batch.is_file():continue
            current,_,_=builder.prepare_plan(BASE/f'catalog-part{part}.json',batch)
            collector.character_plan(json.loads(canonical(current)))
            self.assertEqual(len(current['cases']),44-part)


if __name__=='__main__':unittest.main()
