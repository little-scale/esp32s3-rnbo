# SPDX-License-Identifier: MIT
"""Exact two-program repair admission and additive saved-result classification."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import build_smoke_modules as modules
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
from test_build_smoke_modules import manifest

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'tests/fixtures/smoke/gen-state-boundaries'
digest=lambda value:hashlib.sha256(modules.canonical(value)).hexdigest()


def subset():
    original=json.loads((SOURCES/'catalog.json').read_bytes())
    return dict(original,cases=original['cases'][-2:],rerun=copy.deepcopy(modules.GEN_DELAY_RERUN))


class GenDelayPreparedTests(unittest.TestCase):
    def setUp(self):
        self.manifest=manifest();self.manifest['adaptations'].append(modules.GEN_DELAY_ADAPTATION)
        raw={'rnbo_source.h':'a'*64};self.manifest['source_tree_sha256']=digest(raw)
        files={'rnbo_source.h':'b'*64,'patch_config.h':'c'*64}
        record={'name':modules.GEN_DELAY_ADAPTATION,'whole_source_inverse_verified':True,'cast_count':2}
        self.provenance={'raw_files_sha256':raw,'prepared_files_sha256':files,'adaptations':[record]}
        self.snapshot={'prepared_files_sha256':files.copy()}
        self.pin={'prepared_map_sha256':digest(files),'raw_map_sha256':digest(raw),
                  'manifest_sha256':digest(self.manifest),'adaptation_sha256':digest(record)}

    def test_ordinary_manifest_stays_closed_and_exact_prepared_map_is_required(self):
        with self.assertRaises(modules.ExportError):modules.validate_manifest(self.manifest)
        self.assertIsNone(modules.validate_smoke_prepared({},manifest(),{}))
        with self.assertRaises(modules.ExportError):
            modules.validate_smoke_prepared(self.provenance,self.manifest,self.snapshot)
        with mock.patch.dict(modules.GEN_DELAY_PROOFS,{'synthetic-two-file-map':self.pin},clear=True):
            self.assertEqual(modules.validate_smoke_prepared(self.provenance,self.manifest,self.snapshot),self.pin)
            for mutation in ('unknown-file','source','config','raw','inverse','missing-adapter','extra-adapter',
                             'wrong-profile','parameter','manifest','duplicate-record'):
                p,m,s=copy.deepcopy((self.provenance,self.manifest,self.snapshot))
                if mutation=='unknown-file':s['prepared_files_sha256']['unknown.h']='d'*64
                elif mutation in('source','config'):
                    key='rnbo_source.h'if mutation=='source'else'patch_config.h'
                    s['prepared_files_sha256'][key]='d'*64;p['prepared_files_sha256'][key]='d'*64
                elif mutation=='raw':p['raw_files_sha256']['generator.json']='d'*64
                elif mutation=='inverse':p['adaptations'][0]['whole_source_inverse_verified']=False
                elif mutation=='missing-adapter':m['adaptations'].pop()
                elif mutation=='extra-adapter':m['adaptations'].append('unreviewed')
                elif mutation=='wrong-profile':m['numerical_profile']='float32-auto-v1'
                elif mutation=='parameter':m['parameter_count']=1
                elif mutation=='manifest':m['parameter_schema_sha256']='d'*64
                else:p['adaptations'].append(p['adaptations'][0].copy())
                with self.subTest(mutation=mutation),self.assertRaises(modules.ExportError):
                    modules.validate_smoke_prepared(p,m,s)

    def test_optional_actual_repaired_exports_match_frozen_contracts(self):
        from build import verify_prepared
        root=ROOT/'build/hardware/gen-delay-boolcast-inputs-v1/prepared'
        if not all((root/name/'manifest.json').is_file()for name in modules.GEN_DELAY_REFERENCE_PROOFS):
            self.skipTest('Optional fresh repaired local exports are unavailable')
        for identity in modules.GEN_DELAY_REFERENCE_PROOFS:
            p,m,s=verify_prepared(root/identity)
            self.assertEqual(modules.validate_smoke_prepared(p,m,s),modules.GEN_DELAY_PROOFS[identity])


class GenDelayRerunTests(unittest.TestCase):
    def test_only_the_marked_original_two_rows_are_admitted(self):
        catalog=subset();self.assertEqual(modules.gen_delay_catalog(catalog),catalog)
        original=json.loads((SOURCES/'catalog.json').read_bytes())
        self.assertIsNone(modules.gen_delay_catalog(original))
        for mutation in ('third-case','different-row','tolerance','order','rerun','extra-field','family'):
            bad=copy.deepcopy(catalog)
            if mutation=='third-case':bad['cases'].append(original['cases'][0])
            elif mutation=='different-row':bad['cases'][0]=original['cases'][0]
            elif mutation=='tolerance':bad['cases'][1]['maximum_absolute_error']=1e-3
            elif mutation=='order':bad['cases'].reverse()
            elif mutation=='rerun':bad['rerun']['original_catalog_sha256']='0'*64
            elif mutation=='extra-field':bad['accept_other_adapters']=True
            else:bad['family']='gen-stateful'
            with self.subTest(mutation=mutation),self.assertRaises(modules.ExportError):modules.gen_delay_catalog(bad)

    def test_copied_clean_manifest_cannot_hide_an_actual_repaired_export(self):
        original=json.loads((SOURCES/'catalog.json').read_bytes());rows=[]
        for source in original['cases']:
            clean=manifest();clean['editable_source_sha256']=source['patch_sha256']
            rows.append({'id':source['id'],'status':'built','prepared':{
                'path':'/unused-actual-export','manifest':clean,'snapshot':{}}})
        actual=copy.deepcopy(rows[0]['prepared']['manifest'])
        actual['adaptations'].append(modules.GEN_DELAY_ADAPTATION)
        batch={'format':'rnbo-smoke-modules-v1','cache_control_whole_ELF_equal':True,'modules':rows}
        with tempfile.TemporaryDirectory()as temp:
            path=Path(temp)/'modules.json';path.write_bytes(modules.canonical(batch))
            with mock.patch.object(builder,'verify_prepared',return_value=({},actual,{})):
                with self.assertRaisesRegex(modules.ExportError,'Actual repaired Gen Delay'):
                    builder.prepare_plan(SOURCES/'catalog.json',path)

    def test_private_subset_inventory_binds_public_original_sources(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build')as temp:
            path=Path(temp)/'catalog.json';path.write_bytes(modules.canonical(subset()))
            source_map=builder.sources(path)
            for source in subset()['cases']:
                for key in ('patch','genexpr'):
                    original=SOURCES/source[key]
                    self.assertEqual(source_map[str(original.relative_to(ROOT))],modules.sha(original))
            self.assertIn(str((SOURCES/'catalog.json').relative_to(ROOT)),source_map)

    def plan(self):
        spec=importlib.util.spec_from_file_location('gen_delay_original_reference',SOURCES/'reference.py')
        reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
        catalog=subset();cases=[]
        for row in catalog['cases']:
            words=list(reference.case_input_words(row['model']))
            blocks=[list(block)for block in reference.reference_blocks(row['model'],words,call_count=20)]
            cases.append(dict(row,source_sha256=row['patch_sha256'],module_sha256=str(len(cases)+1)*64,
                input_words=words,expected=blocks[0],expected_blocks=blocks,
                absolute_tolerance=struct.unpack('<f',struct.pack('<f',row['maximum_absolute_error']))[0],
                gen_delay_fix_contract={'synthetic-test-contract':row['id']},
                **modules.GEN_DELAY_REFERENCE_PROOFS[row['id']]))
        return {'family':'gen-state-boundaries','surface':'genexpr','prepare_zero_warm_blocks':0,
            'warmup_blocks':4,'timed_blocks':16,'rerun':catalog['rerun'],
            'expected_stream_policy':'Fresh state; twenty continuous callbacks',
            'cases':cases,'compile_failures':[],'catalog_sha256':digest(catalog),
            'reference_source_sha256':modules.GEN_DELAY_REFERENCE_SHA,
            'input_words_sha256':cases[0]['input_words_sha256']}

    def test_collector_binds_repaired_maps_and_the_original_full_streams(self):
        plan=self.plan();pins={row['id']:row['gen_delay_fix_contract']for row in plan['cases']}
        with mock.patch.dict(collector.GEN_DELAY_PROOFS,pins,clear=True):
            collector.gen_delay_rerun_plan(plan)
            for mutation in ('source','fixed-map','missing-map','model','input','stream','stream-hash',
                             'warmup','missing-row','profile-family','rerun','tolerance','parameters'):
                bad=copy.deepcopy(plan);row=bad['cases'][0]
                if mutation=='source':row['source_sha256']='0'*64
                elif mutation=='fixed-map':row['gen_delay_fix_contract']={'unknown':'map'}
                elif mutation=='missing-map':row.pop('gen_delay_fix_contract')
                elif mutation=='model':row['model']=825
                elif mutation=='input':row['input_words'][0]^=1
                elif mutation=='stream':row['expected_blocks'][19][511]^=1
                elif mutation=='stream-hash':row['expected_stream_sha256']='0'*64
                elif mutation=='warmup':bad['prepare_zero_warm_blocks']=4
                elif mutation=='missing-row':bad['cases'].pop()
                elif mutation=='profile-family':bad['family']='gen-stateful'
                elif mutation=='rerun':bad['rerun']['kind']='generic-repair'
                elif mutation=='tolerance':row['absolute_tolerance']=1e-3
                else:row['parameters']=[]
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):collector.gen_delay_rerun_plan(bad)

    def test_saved_receipt_keeps_additive_rerun_and_per_case_repair_identity(self):
        plan=self.plan();pins={row['id']:row['gen_delay_fix_contract']for row in plan['cases']}
        with tempfile.TemporaryDirectory()as temp,mock.patch.dict(collector.GEN_DELAY_PROOFS,pins,clear=True):
            root=Path(temp);build=root/'build';run=root/'run';build.mkdir();run.mkdir()
            plan_sha=digest(plan);lines=[]
            for row in plan['cases']:
                fields={'id':row['id'],'module_sha256':row['module_sha256'],'status':'pass','samples':'10240',
                    'bit_mismatches':'0','zero_sign_differences':'0','numeric_mismatches':'0','within_tolerance_differences':'0',
                    'nonfinite_outputs':'0','max_absolute_error':'0','absolute_tolerance':str(row['absolute_tolerance']),
                    'input_words_sha256':row['input_words_sha256'],'first_mismatch_word':str(0xffffffff),
                    'first_mismatch_call':str(0xffffffff),'expected_block_count':'20',
                    'mean_us':'40','median_us':'40','peak_us':'40','times_us':','.join(['40']*16),
                    'review_cpu':'0','cpu_reasons':'none','context_bytes':'128','arena_high_water':'0',
                    'finalized':'1','prepare_zero_warm_blocks':'0'}
                lines.append('RNBO_SMOKE CASE '+' '.join(k+'='+v for k,v in fields.items()))
            done=f"RNBO_SMOKE DONE firmware_elf_sha256={'a'*64} plan_sha256={plan_sha} cases=2 passed=2 mismatched=0 cpu_review=0 images=2 finalized_images=2"
            lines.append(done);serial=('\n'.join(lines)+'\n').encode()
            report={'format':'rnbo-hardware-smoke-build-v1','board':'xiao','plan':plan,'plan_sha256':plan_sha,
                    'artifacts':{'app.elf':{'sha256':'a'*64}}}
            (build/'build-report.json').write_bytes(modules.canonical(report))
            (run/'test-serial.log').write_bytes(serial)
            receipt={'format':'rnbo-hardware-smoke-run-v1','board':'xiao','result':'completed','left_installed':True,
                'test_build_report_sha256':digest(report),'serial_log_sha256':hashlib.sha256(serial).hexdigest(),
                'done_line':done,'test_elf_sha256':'a'*64}
            (run/'hardware-smoke.json').write_bytes(modules.canonical(receipt))
            result=collector.collect(build,run)
            self.assertEqual(result['rerun'],modules.GEN_DELAY_RERUN)
            self.assertEqual(result['summary']['passed'],2)
            self.assertIn('previous outcomes retained',result['scope'])
            self.assertEqual([row['gen_delay_fix_contract']for row in result['cases']],list(pins.values()))


if __name__=='__main__':unittest.main()
