# SPDX-License-Identifier: MIT
"""Explicit profile admission and matched ABBA metadata, without device access."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from build_smoke_modules import (DBTOA_PROFILE,DBTOA_CONTRACT,DBTOA_PROFILE_PROOFS,validate_manifest,
                                validate_dbtoa_prepared,ExportError)
from build_hardware_smoke import comparison_contract,canonical
from collect_hardware_smoke import dbtoa_comparison_plan,dbtoa_comparison_times
from test_build_smoke_modules import manifest

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'tests/fixtures/smoke/dbtoa-f32-comparison/catalog.json'


class DBToAProfileTests(unittest.TestCase):
    def candidate(self):
        value=manifest();value.update(numerical_profile=DBTOA_PROFILE,base_numerical_profile='float32-strict',
            numerical_identity='changed-rounding-float32-dbtoa-v1',dbtoa_contract=copy.deepcopy(DBTOA_CONTRACT))
        value['adaptations'].append('rnbo-1.4.4-'+DBTOA_PROFILE)
        return value

    def test_candidate_needs_explicit_profile_and_exact_contract(self):
        value=self.candidate()
        with self.assertRaises(ExportError):validate_manifest(value)
        validate_manifest(value,numerical_profile=DBTOA_PROFILE)
        for field,replacement in (('parameter_count',1),('role','main'),('required_host_services',['dataref']),
                                  ('base_numerical_profile','float32-auto-v1'),('extra_adapter',False)):
            changed=copy.deepcopy(value);changed[field]=replacement
            with self.subTest(field=field),self.assertRaises(ExportError):
                validate_manifest(changed,numerical_profile=DBTOA_PROFILE)
        changed=copy.deepcopy(value);changed['dbtoa_contract']['bit_identity_claimed']=0
        with self.assertRaises(ExportError):validate_manifest(changed,numerical_profile=DBTOA_PROFILE)

    def test_actual_frozen_prepared_profile_maps_and_inverse_audit(self):
        from build import verify_prepared
        base=ROOT/'build/research/dbtoa-f32-profile-v1/prepared'
        if not (base/'candidate/manifest.json').is_file():self.skipTest('Optional local prepared profile cohort unavailable')
        for phase,name in (('A','reference'),('B','candidate')):
            provenance,value,snapshot=verify_prepared(base/name)
            self.assertEqual(validate_dbtoa_prepared(provenance,value,snapshot),DBTOA_PROFILE_PROOFS[phase])
            changed=copy.deepcopy(snapshot);changed['prepared_files_sha256']['generator.json']='0'*64
            with self.assertRaises(ExportError):validate_dbtoa_prepared(provenance,value,changed)
            if phase=='B':
                changed=copy.deepcopy(provenance);changed['adaptations'][-1]['whole_source_inverse_verified']=False
                with self.assertRaises(ExportError):validate_dbtoa_prepared(changed,value,snapshot)


class DBToAComparisonTests(unittest.TestCase):
    def test_actual_comparison_plan_uses_frozen_vector_only_math_api_and_preserves_gen_plan(self):
        from build_hardware_smoke import prepare_plan,generate_header
        base=ROOT/'build/hardware/dbtoa-f32-inputs-v1'
        merged=base/'merged-abba-modules.json'
        if not merged.is_file():self.skipTest('Optional local paired module cohort unavailable')
        plan,inputs,_=prepare_plan(CATALOG,merged)
        self.assertEqual(len(plan['cases']),48)
        dbtoa_comparison_plan(plan)
        self.assertEqual([r['comparison_phase']for r in plan['cases'][:4]],['A','B','B','A'])
        gen=ROOT/'build/hardware-smoke-gen-state-boundaries-v3/build-report.json'
        if gen.is_file():
            previous=json.loads(gen.read_bytes())
            current,vector,_=prepare_plan(ROOT/'tests/fixtures/smoke/gen-state-boundaries/catalog.json',
                ROOT/'build/hardware/gen-state-boundaries-smoke-modules-v3/batch-report.json')
            self.assertEqual(canonical(current),canonical(previous['plan']))
            header,_=generate_header(current,vector)
            self.assertEqual(hashlib.sha256(header.encode()).hexdigest(),previous['header_sha256'])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.catalog=json.loads(CATALOG.read_bytes());self.originals={};bindings={}
        for phase,profile in (('A','float32-strict'),('B',DBTOA_PROFILE)):
            value={'format':'rnbo-smoke-modules-v1','cache_control_whole_ELF_equal':True,
                'source_cache_and_prepared_before_after_unchanged':True,'max_arena_bytes':1048576,
                'cache_control_max_arena_bytes':4096,'modules':[{'id':'dbtoa-signal','status':'built',
                'prepared':{'manifest':{'numerical_profile':profile}}}],
                **{k:{'same':'closed-test-cohort'}for k in ('source_files_sha256','compiler','private_support_archives','cache_inputs_sha256')}}
            self.originals[phase]=value;path=self.root/(phase+'.json');path.write_bytes(canonical(value))
            bindings[phase]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        self.batch={'modules':[copy.deepcopy(self.originals[r['comparison_phase']]['modules'][0])|{'id':r['id']}
                               for r in self.catalog['cases']],'comparison_source_reports':bindings}

    def test_both_original_compiler_reports_and_all_abba_rows_are_bound(self):
        comparison_contract(self.catalog,self.batch)
        for mutation in ('catalog-phase','row-profile','missing-source','wrong-source-hash','altered-row'):
            catalog=copy.deepcopy(self.catalog);batch=copy.deepcopy(self.batch)
            if mutation=='catalog-phase':catalog['cases'][0]['comparison_phase']='B'
            elif mutation=='row-profile':batch['modules'][0]['prepared']['manifest']['numerical_profile']=DBTOA_PROFILE
            elif mutation=='missing-source':batch['comparison_source_reports'].pop('B')
            elif mutation=='wrong-source-hash':batch['comparison_source_reports']['A']['sha256']='0'*64
            else:batch['modules'][0]['unreviewed']=True
            with self.subTest(mutation=mutation),self.assertRaises(ExportError):comparison_contract(catalog,batch)

    def test_collector_requires_exact_phase_profile_source_maps_and_input_identity(self):
        from build_smoke_modules import DBTOA_CATALOG_SHA,DBTOA_REFERENCE_SHA
        cases=[copy.deepcopy(r)|{'module_profile_contract':DBTOA_PROFILE_PROOFS[r['comparison_phase']],
                'module_sha256':('a'if r['comparison_phase']=='A'else'b')*64,'arena_bytes':1048576,
                'absolute_tolerance':1.9999999949504854e-6,'input_words_sha256':'c'*64,'expected_words_sha256':'d'*64}
               for r in self.catalog['cases']]
        plan={'cases':cases,'catalog_sha256':DBTOA_CATALOG_SHA,'reference_source_sha256':DBTOA_REFERENCE_SHA,
              'surface':'patcher','prepare_zero_warm_blocks':0,'comparison_order':'vector-outer-round-middle-ABBA-inner-v1'}
        dbtoa_comparison_plan(plan)
        for key,value in (('numerical_profile','float32-auto-v1'),('comparison_round',True),
                          ('arena_bytes',4096),('input_words_sha256','f'*64),('module_sha256','b'*64)):
            bad=copy.deepcopy(plan);bad['cases'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):dbtoa_comparison_plan(bad)

    def test_abba_callback_totals_are_matched_and_signed_overhead_is_retained(self):
        records=[r|{'times_us':[100 if r['comparison_phase']=='A' else 75]*16,'status':'pass'}for r in self.catalog['cases']]
        value=dbtoa_comparison_times(records)
        self.assertEqual(value['timed_callbacks_per_profile'],384)
        self.assertEqual(value['callback_time_saved_percent'],25)
        self.assertEqual(value['reference_process_us'],38400)
        self.assertEqual(value['candidate_process_us'],28800)
        self.assertFalse(value['direct_target_pairwise_outputs_checked'])
        for row in records:
            if row['comparison_phase']=='B':row['times_us']=[125]*16
        self.assertEqual(dbtoa_comparison_times(records)['callback_time_saved_percent'],-25)


if __name__=='__main__':unittest.main()
