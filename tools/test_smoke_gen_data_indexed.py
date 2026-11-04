# SPDX-License-Identifier: MIT
"""Fresh local-array streams and declaration ownership, without devices."""
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
BASE=ROOT/'tests/fixtures/smoke/gen-data-indexed'
canonical=builder.canonical
digest=lambda value:hashlib.sha256(canonical(value)).hexdigest()


class GenDataSmokeGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=json.loads((BASE/'catalog.json').read_bytes())
        spec=importlib.util.spec_from_file_location('local_data_original_reference',BASE/'reference.py')
        reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
        cases=[]
        for source in cls.catalog['cases']:
            words=list(reference.case_input_words(source['model']))
            blocks=[list(block)for block in reference.reference_blocks(source['model'],words,call_count=20)]
            cases.append(dict(source,module_sha256='d'*64,source_sha256=source['patch_sha256'],
                input_words=words,input_words_sha256=hashlib.sha256(struct.pack('<512I',*words)).hexdigest(),
                expected=blocks[0],expected_blocks=blocks,expected_stream_sha256=hashlib.sha256(
                    struct.pack('<10240I',*(word for block in blocks for word in block))).hexdigest(),
                absolute_tolerance=struct.unpack('<f',struct.pack('<f',source['maximum_absolute_error']))[0]))
        cls.plan={'family':builder.GEN_DATA_FAMILY,'surface':'genexpr','cases':cases,'compile_failures':[],
            'catalog_sha256':builder.GEN_DATA_CATALOG_SHA,'reference_source_sha256':builder.GEN_DATA_REFERENCE_SHA,
            'prepare_zero_warm_blocks':0,'warmup_blocks':4,'timed_blocks':16,
            'expected_stream_policy':'Fresh state; four checked manual warmups and sixteen timed callbacks',
            'input_words_sha256':cases[0]['input_words_sha256'],**builder.gen_data_catalog(cls.catalog)}

    def test_catalog_is_exact_and_data_is_a_declaration_owner(self):
        self.assertIn('Float32',builder.gen_data_catalog(self.catalog)['producer_storage_view'])
        for mutation in ('name','kind','storage','limit','family'):
            bad=copy.deepcopy(self.catalog)
            if mutation=='name':bad['cases'][0]['exact_name']='data'
            elif mutation=='kind':bad['cases'][0]['owner_kind']='function-call'
            elif mutation=='storage':bad['producer_storage_view']='Gen64 storage'
            elif mutation=='limit':bad['cases'][-1]['maximum_absolute_error']=1e-3
            else:bad['family']='gen-stateful'
            with self.subTest(mutation=mutation),self.assertRaises(builder.ExportError):builder.gen_data_catalog(bad)

    def test_collector_requires_fresh_full_streams_and_original_storage_scope(self):
        collector.gen_data_plan(self.plan)
        for mutation in ('name','kind','storage','reference','source','surface','warmup','stream','hash','limit','pilot'):
            bad=copy.deepcopy(self.plan);row=bad['cases'][0]
            if mutation=='name':row['exact_name']='data'
            elif mutation=='kind':row['owner_kind']='function-call'
            elif mutation=='storage':bad['storage_policy']='narrow cells'
            elif mutation=='reference':bad['reference_source_sha256']='0'*64
            elif mutation=='source':row['genexpr_sha256']='0'*64
            elif mutation=='surface':bad['surface']='patcher'
            elif mutation=='warmup':bad['prepare_zero_warm_blocks']=4
            elif mutation=='stream':row.pop('expected_blocks')
            elif mutation=='hash':row['expected_blocks'][19][511]^=1
            elif mutation=='limit':row['absolute_tolerance']=1e-3
            else:row['strict_zero_sign_channels']=2
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):collector.gen_data_plan(bad)

    def test_saved_result_keeps_declaration_ownership_and_backend_storage_labels(self):
        lines=[]
        for row in self.plan['cases']:
            data={'id':row['id'],'module_sha256':row['module_sha256'],'status':'pass','samples':'10240',
                'bit_mismatches':'0','zero_sign_differences':'0','numeric_mismatches':'0',
                'within_tolerance_differences':'0','nonfinite_outputs':'0','max_absolute_error':'0',
                'absolute_tolerance':str(row['absolute_tolerance']),'input_words_sha256':row['input_words_sha256'],
                'first_mismatch_word':str(0xffffffff),'first_mismatch_call':str(0xffffffff),
                'expected_block_count':'20','mean_us':'40','median_us':'40','peak_us':'40',
                'times_us':','.join(['40']*16),'review_cpu':'0','cpu_reasons':'none',
                'context_bytes':'128','arena_high_water':'128','finalized':'1','prepare_zero_warm_blocks':'0'}
            lines.append('RNBO_SMOKE CASE '+' '.join(key+'='+value for key,value in data.items()))
        plan_sha=digest(self.plan);done=f"RNBO_SMOKE DONE firmware_elf_sha256={'a'*64} plan_sha256={plan_sha} cases=8 passed=8 mismatched=0 cpu_review=0 images=8 finalized_images=8"
        serial=('\n'.join(lines+[done])+'\n').encode()
        with tempfile.TemporaryDirectory()as temp:
            base=Path(temp);build=base/'build';run=base/'run';build.mkdir();run.mkdir()
            report={'format':'rnbo-hardware-smoke-build-v1','board':'xiao','plan':self.plan,
                'plan_sha256':plan_sha,'artifacts':{'app.elf':{'sha256':'a'*64}}}
            (build/'build-report.json').write_bytes(canonical(report));(run/'test-serial.log').write_bytes(serial)
            receipt={'format':'rnbo-hardware-smoke-run-v1','board':'xiao','result':'completed','left_installed':True,
                'test_build_report_sha256':digest(report),'serial_log_sha256':hashlib.sha256(serial).hexdigest(),
                'done_line':done,'test_elf_sha256':'a'*64}
            (run/'hardware-smoke.json').write_bytes(canonical(receipt))
            result=collector.collect(build,run)
            self.assertEqual(result['family'],builder.GEN_DATA_FAMILY)
            self.assertEqual(result['cases'][0]['exact_name'],'Data')
            self.assertEqual(result['cases'][0]['owner_kind'],'declaration')
            self.assertEqual(result['cases'][-1]['owner_kind'],'declaration')
            self.assertEqual(result['producer_storage_view'],self.catalog['producer_storage_view'])
            self.assertNotIn('strict_zero_sign_channels',result)
            self.assertTrue(all(row['expected_block_count']==20 for row in result['cases']))

    def test_optional_actual_eight_modules_and_prior_plan_header_replays(self):
        from test_smoke_character_constants import CharacterSmokeGuards
        CharacterSmokeGuards().test_optional_actual_partitions_and_previous_plan_headers()
        for part in (1,2):
            report=ROOT/f'build/hardware-smoke-rnbo-character-constants-v2-part{part}/build-report.json'
            if not report.is_file():continue
            previous=json.loads(report.read_bytes())
            current,words,_=builder.prepare_plan(ROOT/f'tests/fixtures/smoke/rnbo-character-constants/catalog-part{part}.json',
                ROOT/f'build/hardware/rnbo-character-constants-smoke-modules-v2-part{part}/batch-report.json')
            self.assertEqual(canonical(current),canonical(previous['plan']))
            header,_=builder.generate_header(current,words)
            self.assertEqual(hashlib.sha256(header.encode()).hexdigest(),previous['header_sha256'])
        batch=ROOT/'build/hardware/gen-data-indexed-smoke-modules-v1/batch-report.json'
        if batch.is_file():
            current,_,_=builder.prepare_plan(BASE/'catalog.json',batch)
            collector.gen_data_plan(json.loads(canonical(current)))
            self.assertEqual(len(current['cases']),8)


if __name__=='__main__':unittest.main()
