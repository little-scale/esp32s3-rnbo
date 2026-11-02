#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Seal observed per-fixture target results with build/log identities.

Reports whole-fixture process timings. Main fixtures include their excitation
objects; declared FX generators are outside the process timer. Neither scope
establishes a universal isolated-operator or application deadline bound.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct


# Initial oracle admission is deliberately limited to the original authored
# graphs, schemas and cases. These are fingerprints, never generated DSP bodies.
WAVE2_ORACLES = {
    'biquad-response-v1': {
        'family':'biquad', 'stimulus':'impulse-step-v1', 'limit':3e-6,
        'patch':'4e98b2dabc1779468c972de871acc719e909407b956d7dda86128e9cc196127d',
        'schema':'5ee44b4347d4f1d490c0ecb696d9fca49b9ece2d69635b837422dbf98ad9ea30',
        'raw_source':'3bf669da7e420a82f5c2370a4449c9ec791cdbef655b227fbb2057ab295015b5',
        'parameters':[
            {'paramId':'a0','index':0,'minimum':0,'maximum':1,'initialValue':.5,'exponent':1,'steps':0},
            {'paramId':'b2','index':1,'minimum':0,'maximum':.8,'initialValue':.2,'exponent':1,'steps':0},
            {'paramId':'a1','index':2,'minimum':-1,'maximum':1,'initialValue':.25,'exponent':1,'steps':0},
            {'paramId':'a2','index':3,'minimum':-1,'maximum':1,'initialValue':.125,'exponent':1,'steps':0},
            {'paramId':'b1','index':4,'minimum':-.95,'maximum':.95,'initialValue':-.4,'exponent':1,'steps':0}],
        'defaults':{'a0':.5,'a1':.25,'a2':.125,'b1':-.4,'b2':.2},
        'cases':[
            {'id':'default','parameters':{},'events':[]},
            {'id':'identity','parameters':{'a0':1,'a1':0,'a2':0,'b1':0,'b2':0},'events':[]},
            {'id':'slow-pole','parameters':{'a0':.05,'a1':0,'a2':0,'b1':-.95,'b2':0},'events':[]}],
        'model':'fresh-float64-difference-equation'},
    'nonlinear-chain-v1': {
        'family':'nonlinear', 'stimulus':'nonlinear-grid-v1', 'limit':2e-6,
        'patch':'426eace2f5d115d12b3cb61280325bff289a9ac28c9ce80652c6b466ae0aa180',
        'schema':'754c55e5f56bd5c2731847a19ed276e1ad4045849e3bcc2909acd4ec76b73ef1',
        'raw_source':'b246e2357fc3829af9d44eec0efc1aa69a82bd9157be093663005ea0eb1ea28b',
        'parameters':[{'paramId':'exponent','index':0,'minimum':.25,'maximum':4,'initialValue':2,'exponent':1,'steps':0}],
        'cases':[
            {'id':'square','parameters':{},'events':[]},
            {'id':'fractional','parameters':{'exponent':.25},'events':[]},
            {'id':'fourth','parameters':{'exponent':4},'events':[]}],
        'model':'float64-tanh-wrap-clip-pow'}
}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def fields(line,prefix):
    require(line.startswith(prefix),'Unexpected measurement prefix')
    result={}
    for item in line[len(prefix):].strip().split():
        key,sep,value=item.partition('=')
        require(sep and key not in result,'Malformed or duplicate measurement field')
        if not key.endswith('sha256'):
            try:value=int(value)
            except ValueError:
                try:value=float(value)
                except ValueError:pass
        if isinstance(value,float):require(math.isfinite(value),'Nonfinite measurement')
        result[key]=value
    return result


def digest(value,message):
    require(isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value),message)
    return value


def same_declaration(actual,expected):
    """JSON equality with finite numeric values; bool must not impersonate0/1."""
    if type(expected) in (int,float):
        return type(actual) in (int,float) and math.isfinite(actual) and actual==expected
    if isinstance(expected,dict):
        return isinstance(actual,dict) and actual.keys()==expected.keys() and all(same_declaration(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):
        return isinstance(actual,list) and len(actual)==len(expected) and all(same_declaration(a,b) for a,b in zip(actual,expected))
    return type(actual) is type(expected) and actual==expected


def wave2_verification(fixture,case):
    declaration=fixture['verification'];kind=declaration['kind'];contract=WAVE2_ORACLES[kind]
    require(fixture.get('role')=='fx' and fixture.get('family')==contract['family'],'Oracle fixture family/role differs')
    require(same_declaration(declaration,{'kind':kind,'maximum_absolute_error':contract['limit']}),'Oracle verification declaration differs')
    require(same_declaration(fixture.get('cases'),contract['cases']),'Oracle requires the exact three authored cases without events')
    require(same_declaration(fixture.get('warmup_blocks'),4) and same_declaration(fixture.get('seed'),305419896),'Oracle warmup/seed differs')
    require(same_declaration(fixture.get('stimulus'),{'kind':contract['stimulus']}),'Oracle stimulus differs')
    semantic={'kind':contract['family'],'maximum_absolute_error':contract['limit']}
    semantic.update({'defaults':contract['defaults']} if kind=='biquad-response-v1' else {'exponent_default':2})
    require(same_declaration(fixture.get('semantic'),semantic),'Oracle semantic declaration differs')
    require(any(same_declaration(case,c) for c in contract['cases']),'Unknown oracle case')
    result={'kind':kind,'maximum_absolute_error':contract['limit'],'model':contract['model'],
            'rounding':'once-float32','gate':'cache-error-plus-maximum-cache-rounding-error'}
    if kind=='biquad-response-v1':
        coefficients=contract['defaults']|case['parameters'];result['coefficients']=coefficients
        gain=(coefficients['a0']+coefficients['a1']+coefficients['a2'])/(1+coefficients['b1']+coefficients['b2'])
        result['dc_expected']=-.125*gain
    else:result['exponent']=case['parameters'].get('exponent',2)
    return result


def wave2_identity(build,fixture,plan):
    """Independently bind the model to its graph/schema and emitted events."""
    kind=fixture['verification']['kind'];contract=WAVE2_ORACLES[kind]
    require(type(plan.get('blocks')) is int and plan['blocks']==512,'Oracle first scope requires512 blocks')
    require(type(plan.get('rounds')) is int and 1<=plan['rounds']<=5,'Invalid oracle round count')
    require(same_declaration(plan.get('parameter_schema'),contract['parameters']),'Oracle parameter projection differs')
    require(plan.get('patch_sha256')==contract['patch'],'Oracle patch identity differs')
    for module in build['modules'].values():
        export=module['report']['prepared_export'];manifest=export['manifest']
        require(manifest.get('editable_source_sha256')==contract['patch'] and manifest.get('parameter_schema_sha256')==contract['schema'],'Oracle source/schema identity differs')
        require(type(manifest.get('parameter_count')) is int and manifest['parameter_count']==len(contract['parameters']),'Oracle module parameter count differs')
        require(manifest.get('sample_rate')==44100 and manifest.get('block_frames')==256,'Oracle module audio profile differs')
        require(export.get('provenance',{}).get('raw_files_sha256',{}).get('rnbo_source.h')==contract['raw_source'],'Oracle raw generated source identity differs')
    tolerance=fixture['comparison_tolerance']
    for key,maximum in (('maximum_absolute_error',2e-6),('relative_rms_level_difference',1e-4)):
        value=tolerance.get(key);require(type(value) in (int,float) and math.isfinite(value) and 0<=value<=maximum,'Oracle pair tolerance widened or invalid')
    value=tolerance.get('maximum_pcm_lsb_error');require(type(value) is int and 0<=value<=1,'Oracle PCM tolerance widened or invalid')
    events=plan.get('events');require(isinstance(events,list),'Missing oracle event table')
    schema={p['paramId']:p for p in contract['parameters']};position=0
    for case in fixture['cases']:
        parameters=case['parameters'];chunk=events[position:position+len(parameters)];position+=len(parameters)
        require(len(chunk)==len(parameters),'Incomplete oracle event table')
        seen=set()
        for event in chunk:
            require(isinstance(event,dict) and set(event)=={'block','index','kind','value','id'},'Unknown oracle event metadata')
            identity=event['id'];require(isinstance(identity,str) and identity in parameters and identity not in seen,'Unknown/duplicate oracle event')
            seen.add(identity);rounded=struct.unpack('<f',struct.pack('<f',parameters[identity]))[0]
            expected={'block':0,'index':schema[identity]['index'],'kind':1,'value':rounded,'id':identity}
            require(same_declaration(event,expected),'Oracle parameter event differs')
    require(position==len(events),'Unexpected oracle parameter events')


def declared_stimulus(fixture,case):
    wave2={'impulse-step-v1':4,'mixed-tone-v1':5,'nonlinear-grid-v1':6}
    base=fixture.get('stimulus');override=case.get('stimulus',{})
    require(isinstance(base,dict) and isinstance(override,dict),'FX stimulus declaration missing')
    if base.get('kind') in wave2:
        require(set(base)=={'kind'} and set(override)<={'kind'},'Unknown wave2 stimulus fields')
        settings=base|override;require(settings.get('kind') in wave2,'Unknown wave2 stimulus kind')
        return {'kind':wave2[settings['kind']],'settings':settings,**{k:0.0 for k in ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')}}
    contracts={
        'midi-stereo-v1':(1,{'kind','base','depth','rate','pilot_frequency','pilot_amplitude'}),
        'frequency-stereo-v1':(2,{'kind','frequency','depth','rate','pilot_frequency','pilot_amplitude'}),
        'reson-stereo-v1':(3,{'kind','excitation','level','center','depth','rate'})}
    base=fixture.get('stimulus');override=case.get('stimulus',{})
    require(isinstance(base,dict) and isinstance(override,dict),'FX stimulus declaration missing')
    require(base.get('kind') in contracts,'Unknown FX stimulus contract')
    kind,keys=contracts[base['kind']]
    require(set(base)==keys and set(override)<=keys-{'kind'},'Unknown/missing FX stimulus fields or kind override')
    settings=base|override
    for key,value in settings.items():
        if key!='kind':require(type(value) in (int,float) and math.isfinite(value),'Nonfinite or invalid declared stimulus value')
    return {'kind':kind,'settings':settings,
            'base':settings['base' if kind==1 else 'frequency' if kind==2 else 'center'],
            'depth':settings['depth'],'rate':settings['rate'],
            'pilot_frequency':settings.get('pilot_frequency',0.0),'pilot_amplitude':settings.get('pilot_amplitude',0.0),
            'excitation':settings.get('excitation',0.0),'level':settings.get('level',0.0)}


def declared_verification(fixture,case):
    declaration=fixture.get('verification')
    kind=(fixture.get('stimulus',{})|case.get('stimulus',{})).get('kind')
    if declaration is None:
        require(kind not in ('impulse-step-v1','mixed-tone-v1','nonlinear-grid-v1'),'Missing explicit verification contract')
        return None
    if isinstance(declaration,dict) and declaration.get('kind') in WAVE2_ORACLES:
        return wave2_verification(fixture,case)
    expected={'kind':'average-window-v1','parameter_id':'window','default_window':16,'maximum_window':64,'maximum_absolute_error':2e-6}
    require(fixture.get('role')=='fx' and fixture.get('family')=='average' and declaration==expected,'Unsupported average verification contract')
    require(kind in ('impulse-step-v1','mixed-tone-v1'),'Average verification has unmodeled input')
    semantic=fixture.get('semantic',{})
    require(semantic.get('kind')=='average' and semantic.get('default_window')==16 and semantic.get('maximum_absolute_error')==2e-6,'Average semantic declaration differs')
    require(isinstance(case.get('events',[]),list) and not case.get('events',[]),'Average events are not modeled')
    parameters=case.get('parameters',{})
    require(isinstance(parameters,dict) and set(parameters)<={'window'},'Unknown average parameter')
    n=parameters.get('window',16)
    require(type(n) in (int,float) and math.isfinite(n) and n==int(n) and 1<=n<=64,'Average window must be integer1..64')
    n=int(n);initial=min(16,fixture['warmup_blocks']*256) if n==16 else 0
    return {'kind':'average-window-v1','window':n,'initial_available':initial,'maximum_absolute_error':2e-6,
            'default_window':16,'maximum_window':64,'parameter_id':'window','model':'fresh-float64-window-sum',
            'rounding':'once-float32','gate':'cache-error-plus-maximum-cache-rounding-error'}


def oracle_memory_budget(build,plan):
    budget=plan.get('psram_budget');require(isinstance(budget,dict),'Missing oracle PSRAM budget')
    blocks=plan['blocks'];arena=plan.get('arena_bytes');require(type(arena) is int and 4096<=arena<=1048576,'Invalid selected arena budget')
    expected_count=5 if plan['fixture'].get('verification',{}).get('kind')=='biquad-response-v1' else 1
    require(all(build['modules'][p]['report']['prepared_export']['manifest'].get('parameter_count')==expected_count for p in ('strict','optimized')),'Oracle module parameter count differs')
    loaded=sum(build['modules'][p]['inspection']['loaded_bytes_upper_bound'] for p in ('strict','optimized'))
    expected={'workspace_bytes':blocks*256*2*4*2+4*256*4,'oracle_cache_bytes':blocks*256*2*4,
              'arena_bytes':2*arena,'opaque_context_upper_bound_bytes':2*1048576,'loaded_images_upper_bound_bytes':loaded,
              'loader_heap_alignment_reserve_bytes':524288,'physical_psram_bytes':8*1048576}
    expected['required_upper_bound_bytes']=sum(expected[k] for k in expected if k!='physical_psram_bytes')
    require(budget==expected and expected['required_upper_bound_bytes']<=expected['physical_psram_bytes'],'Oracle PSRAM budget differs or exceeds capacity')
    return budget


def input_evidence(build,fixture,plan,passed,lines,expected_samples):
    name=fixture['id'];role=fixture['role'];case_count=len(fixture['cases'])
    prefix='RNBO_OBJECT_BENCHMARK INPUT ';oracle_prefix='RNBO_OBJECT_BENCHMARK ORACLE '
    records=[fields(line.strip(),prefix) for line in lines if line.strip().startswith(prefix)]
    oracle_records=[fields(line.strip(),oracle_prefix) for line in lines if line.strip().startswith(oracle_prefix)]
    evidence={}
    if role=='main':
        require(not records and not oracle_records,'Main fixture cannot claim external INPUT/oracle evidence')
        require('stimulus' not in fixture and 'verification' not in fixture and all('stimulus' not in c for c in fixture['cases']),'Main fixture declares ignored stimulus')
        require('stimuli' not in plan or plan['stimuli']==[None]*case_count,'Main plan declares external stimulus')
        require('verifications' not in plan or plan['verifications']==[None]*case_count,'Main plan declares oracle')
        require(all(passed.get(k,0)==0 for k in ('input_cases','input_rechecks','pilot_sample_checks','oracle_cases','oracle_rechecks','semantic_sample_checks','dc_sample_checks')),'Main fixture has unexpected FX input counters')
        return evidence,None
    require(len(records)==case_count,'Incomplete FX INPUT evidence')
    verifications=[declared_verification(fixture,c) for c in fixture['cases']]
    new_model=fixture.get('verification',{}).get('kind') in WAVE2_ORACLES
    if new_model:wave2_identity(build,fixture,plan)
    oracle_count=sum(v is not None for v in verifications);pilot_count=case_count-oracle_count
    expected_counts={'input_cases':case_count,'input_rechecks':case_count*plan['rounds']*3,'pilot_sample_checks':expected_samples*pilot_count,
                     'oracle_cases':oracle_count,'oracle_rechecks':oracle_count*plan['rounds']*3,'semantic_sample_checks':expected_samples*oracle_count*2}
    for key,expected in expected_counts.items():
        value=passed.get(key,0) if not oracle_count and key in ('oracle_cases','oracle_rechecks','semantic_sample_checks') else passed.get(key)
        require(type(value) is int and value==expected,'FX input/pilot coverage differs: '+key)
    require(len(oracle_records)==oracle_count,'Incomplete average ORACLE evidence')
    require('verifications' not in plan and not oracle_count or same_declaration(plan.get('verifications'),verifications),'Compiled verification differs from declaration')
    require(isinstance(plan.get('stimuli'),list) and len(plan['stimuli'])==case_count,'Compiled stimulus plan missing')
    for index,case in enumerate(fixture['cases']):
        expected=declared_stimulus(fixture,case);verification=verifications[index]
        require(plan['stimuli'][index]==expected,'Compiled stimulus differs from catalog/case declaration')
        found=[r for r in records if r.get('fixture')==name and r.get('case')==case['id']]
        require(len(found)==1,'Missing or duplicate FX INPUT case')
        record=found[0];digest(record.get('input_sha256'),'Malformed target input SHA256')
        require(type(record.get('input_bytes')) is int and record['input_bytes']==plan['blocks']*256*2*4,'FX input byte coverage differs')
        require(record.get('layout')=='float32_stereo_interleaved_le','FX input layout differs')
        require(type(record.get('stimulus_kind')) is int and record['stimulus_kind']==expected['kind'],'FX input stimulus kind differs')
        evidence[case['id']]={**record,'declared_settings':expected['settings']}
        if verification:
            candidates=[r for r in oracle_records if r.get('fixture')==name and r.get('case')==case['id']]
            require(len(candidates)==1,'Missing or duplicate ORACLE case');oracle=candidates[0]
            if verification['kind'] in WAVE2_ORACLES:
                keys={'fixture','case','oracle_sha256','oracle_bytes','layout','oracle_kind','max_abs_tolerance','max_cache_rounding_error','model','rounding'}
                keys.update(verification['coefficients'] if verification['kind']=='biquad-response-v1' else ('exponent',))
                require(set(oracle)==keys,'Unknown or missing oracle metadata')
            digest(oracle.get('oracle_sha256'),'Malformed oracle SHA256')
            require(type(oracle.get('oracle_bytes')) is int and oracle['oracle_bytes']==plan['blocks']*256*2*4,'Oracle byte coverage differs')
            require(oracle.get('layout')=='float32_stereo_interleaved_le' and oracle.get('oracle_kind')==verification['kind'],'Oracle layout/model kind differs')
            if verification['kind']=='average-window-v1':
                require(oracle.get('window')==verification['window'] and oracle.get('initial_available')==verification['initial_available'],'Oracle history/window differs')
            elif verification['kind']=='biquad-response-v1':
                require(same_declaration({key:oracle.get(key) for key in verification['coefficients']},verification['coefficients']),'Oracle Float64 coefficients differ')
            else:
                require(same_declaration(oracle.get('exponent'),verification['exponent']),'Oracle exponent differs')
            require(oracle.get('max_abs_tolerance')==verification['maximum_absolute_error'],'Oracle tolerance differs')
            require(oracle.get('model')==verification['model'] and oracle.get('rounding')==verification['rounding'],'Oracle precision/model differs')
            error=oracle.get('max_cache_rounding_error');require(type(error) in (int,float) and 0<=error<=2**-24,'Invalid oracle cache rounding error')
            evidence[case['id']]['oracle']={**oracle,'verification':verification}
    source_names=('object-benchmark/main/stimulus.c','object-benchmark/main/stimulus.h');sources=build.get('source_files_sha256',{})
    generator={key:digest(sources.get(key),'Missing generator source identity') for key in source_names}
    provenance={'catalog_path':plan.get('catalog_path'),'catalog_sha256':digest(plan.get('catalog_sha256'),'Missing stimulus catalog identity'),
                'patch_sha256':digest(plan.get('patch_sha256'),'Missing fixture patch identity'),
                'generator_source_sha256':generator,'sample_rate':44100,'block_frames':256,
                'sample_time':'Zero-based rendered frame n/44100 after zero-input warmup',
                'generation':'Float64 sine/arithmetic; round each completed channel sample once to Float32',
                'timing':'Generator/oracle precomputation and cache copy excluded from process timers',
                'rechecks':'Cached INPUT and declared ORACLE SHA before/after every pass; shared adjacent-pass checkpoint',
                'pilot':('Every output reference/pilot sample equals its declared input channel' if pilot_count else
                         'No pilot samples; both output channels use the declared mathematical oracle' if new_model else
                         'No pilot samples; both output channels use the declared average oracle'),
                'limit':'Target SHA fingerprints actual cached input; host/target transcendental byte identity is not assumed'}
    require(isinstance(provenance['catalog_path'],str) and provenance['catalog_path'],'Missing stimulus catalog path')
    if oracle_count:
        stem='wave2_oracle' if new_model else 'average_oracle'
        provenance['oracle_source_sha256']={key:digest(sources.get(key),'Missing oracle source identity') for key in (f'object-benchmark/main/{stem}.c',f'object-benchmark/main/{stem}.h')}
        provenance['verification_contract']=fixture['verification'];provenance['psram_budget']=oracle_memory_budget(build,plan)
        if new_model:
            provenance['oracle']='Original catalog Float64 model over actual Float32 input; once Float32 cache rounding. Native/target libm byte identity is not assumed.'
            provenance['semantic_gate']='Maximum output/cache error plus maximum cache/model rounding error must stay within the unchanged declared semantic limit.'
            provenance['parameter_schema']=plan['parameter_schema']
            provenance['events']=plan['events']
        else:
            provenance['oracle']='Fresh Float64 window sum over actual Float32 input; once Float32 cache rounding. fsum bit identity is not claimed.'
            provenance['semantic_gate']='Maximum output/cache error plus maximum cache/model rounding error must be <= declared2e-6'
    return evidence,provenance


def collect(build_dir,run_dir):
    build_path=build_dir/'build-report.json';run_path=run_dir/'hardware-test.json';log=run_dir/'test-serial.log'
    build=json.loads(build_path.read_text());run=json.loads(run_path.read_text())
    require(run['result']=='passed' and run['restoration']['result']=='restored','Test or instrument recovery did not pass')
    require(sha(build_path)==run['test_build_report_sha256'],'Build report changed after hardware test')
    require(sha(log)==run['serial_log_sha256'],'Serial log changed after hardware test')
    lines=log.read_text().splitlines();prefix='RNBO_OBJECT_BENCHMARK PASS '
    matches=[line.strip() for line in lines if line.strip().startswith(prefix)]
    require(matches==[run['pass_line']],'Expected exactly the verified complete PASS line')
    passed=fields(matches[0],prefix);plan=build['benchmark'];fixture=plan['fixture'];name=fixture['id']
    require(passed['fixture']==name and passed['firmware_elf_sha256']==run['test_elf_sha256'],'Fixture or firmware identity differs')
    role=fixture['role'];require(role in ('main','fx'),'Unknown fixture role')
    for profile,field in (('strict','strict_module_sha256'),('optimized','optimized_module_sha256')):
        require(passed[field]==build['modules'][profile]['artifact_sha256'],'Native module identity differs')
        manifest=build['modules'][profile]['report']['prepared_export']['manifest']
        require(manifest['role']==role and manifest['audio_inputs']==(2 if role=='fx' else 0) and manifest['audio_outputs']==2,'Module role/channel declaration differs')
    numerical_profiles={p:build['modules'][p]['report']['prepared_export']['manifest']['numerical_profile'] for p in ('strict','optimized')}
    prefix_profiles='RNBO_OBJECT_BENCHMARK NUMERICAL_PROFILES '
    profile_lines=[fields(line.strip(),prefix_profiles) for line in lines if line.strip().startswith(prefix_profiles)]
    if 'numerical_profiles' in plan:
        require(plan['numerical_profiles']==numerical_profiles,'Build numerical profiles differ from module manifests')
        require(profile_lines==[{'fixture':name,'reference':numerical_profiles['strict'],'candidate':numerical_profiles['optimized']}],
                'Missing or inconsistent numerical profile record')
    else:
        require(not profile_lines and numerical_profiles['strict']=='float32-strict','Legacy reference must be float32-strict')
    for field in ('host_heap_allocations','host_heap_frees','local_late_allocations'):
        require(passed[field]==0,'Unexpected running allocation')
    require(passed['psram_before']==passed['psram_after'] and passed['internal_after']>=passed['internal_before'],'Module memory did not recover')
    require(passed['images']==passed['finalized_images']==4,'Missing image finalization')
    require(passed['cases']==len(fixture['cases']) and passed['rounds']==plan['rounds'] and passed['blocks_per_pass']==plan['blocks'],'Measurement plan differs')
    require(passed['timing_exclude']==plan['timing_exclude_blocks'],'Timing exclusion differs')
    require(passed['warmup']==fixture['warmup_blocks'] and passed['seed']==fixture['seed'],'Initial state differs')
    expected_blocks=plan['rounds']*(plan['blocks']-plan['timing_exclude_blocks'])
    expected_samples=plan['rounds']*plan['blocks']*512
    inputs,stimulus_provenance=input_evidence(build,fixture,plan,passed,lines,expected_samples)
    cases=[]
    case_lines=[fields(line.strip(),'RNBO_OBJECT_BENCHMARK CASE ') for line in lines if line.strip().startswith('RNBO_OBJECT_BENCHMARK CASE ')]
    timing_lines=[fields(line.strip(),'RNBO_OBJECT_BENCHMARK CASE_PROFILE ') for line in lines if line.strip().startswith('RNBO_OBJECT_BENCHMARK CASE_PROFILE ')]
    require(len(case_lines)==len(fixture['cases']) and len(timing_lines)==2*len(case_lines),'Incomplete case measurements')
    semantic_prefix='RNBO_OBJECT_BENCHMARK CASE_SEMANTIC '
    semantic_records=[fields(line.strip(),semantic_prefix) for line in lines if line.strip().startswith(semantic_prefix)]
    expected_semantic_cases=sum('oracle' in value for value in inputs.values())
    require(len(semantic_records)==2*expected_semantic_cases,'Incomplete semantic measurements')
    dc_prefix='RNBO_OBJECT_BENCHMARK CASE_DC '
    dc_records=[fields(line.strip(),dc_prefix) for line in lines if line.strip().startswith(dc_prefix)]
    dc_cases=sum(value.get('oracle',{}).get('verification',{}).get('kind')=='biquad-response-v1' for value in inputs.values())
    require(len(dc_records)==2*dc_cases,'Incomplete or unexpected DC measurements')
    dc_count=passed.get('dc_sample_checks',0)
    require(type(dc_count) is int and dc_count==dc_cases*plan['rounds']*2,'DC sample coverage differs')
    tolerance=fixture['comparison_tolerance']
    for declared in fixture['cases']:
        records=[c for c in case_lines if c['case']==declared['id'] and c['fixture']==name]
        require(len(records)==1,'Missing or duplicate case')
        case=records[0];require(case['samples']==expected_samples,'Case sample count differs')
        require(0<=case['max_abs']<=tolerance['maximum_absolute_error'] and
                0<=case['max_pcm_lsb']<=tolerance['maximum_pcm_lsb_error'] and
                0<=case['relative_rms']<=tolerance['relative_rms_level_difference'],'Case exceeds declared output limits')
        timings={}
        for profile in ('strict','optimized'):
            values=[t for t in timing_lines if t['case']==declared['id'] and t['fixture']==name and t['profile']==profile]
            require(len(values)==1,'Missing or duplicate profile timing')
            value=values[0];require(value['timed_blocks']==expected_blocks and value['process_us']>0,'Invalid timing coverage')
            timings[profile]={**value,'numerical_profile':numerical_profiles[profile],'mean_process_us':value['process_us']/value['timed_blocks']}
        semantics={};dc={}
        if inputs.get(declared['id'],{}).get('oracle'):
            oracle=inputs[declared['id']]['oracle'];limit=oracle['max_abs_tolerance']
            for profile in ('strict','optimized'):
                matches=[r for r in semantic_records if r.get('fixture')==name and r.get('case')==declared['id'] and r.get('profile')==profile]
                require(len(matches)==1,'Missing or duplicate semantic profile');value=matches[0]
                require(value.get('semantic_kind')==oracle['verification']['kind'] and value.get('oracle_sha256')==oracle['oracle_sha256'],'Semantic oracle identity differs')
                require(type(value.get('samples')) is int and value['samples']==expected_samples and value.get('max_abs_tolerance')==limit,'Semantic sample coverage/tolerance differs')
                error=value.get('max_abs');require(type(error) in (int,float) and error>=0,'Invalid semantic error')
                bound=error+oracle['max_cache_rounding_error']
                require(value.get('max_model_error_bound')==bound and bound<=limit,'Semantic average exceeds unchanged model limit')
                semantics[profile]=value
                if oracle['verification']['kind']=='biquad-response-v1':
                    found=[r for r in dc_records if r.get('fixture')==name and r.get('case')==declared['id'] and r.get('profile')==profile]
                    require(len(found)==1,'Missing or duplicate DC profile');record=found[0]
                    require(set(record)=={'fixture','case','profile','expected','max_abs','samples','mean_frames','max_abs_tolerance','oracle_sha256'},'Unknown or missing DC metadata')
                    require(type(record.get('samples')) is int and record['samples']==plan['rounds'],'DC round coverage differs')
                    require(type(record.get('mean_frames')) is int and record['mean_frames']==1024,'DC mean window differs')
                    require(same_declaration(record.get('expected'),oracle['verification']['dc_expected']),'DC expected value differs')
                    require(record.get('max_abs_tolerance')==3e-6,'DC tolerance differs')
                    error=record.get('max_abs');require(type(error) in (int,float) and 0<=error<=3e-6,'DC error exceeds unchanged model limit')
                    require(record.get('oracle_sha256')==oracle['oracle_sha256'],'DC oracle identity differs')
                    dc[profile]=record
        reference=timings['strict']['mean_process_us'];candidate=timings['optimized']['mean_process_us']
        cases.append({'case':declared['id'],'declared_case':declared,'input':inputs.get(declared['id']),'semantic_comparison':semantics,'output_comparison':case,'profiles':timings,
                      'observed_speed_ratio':reference/candidate,'observed_process_reduction_percent':100*(1-candidate/reference)})
        if dc:cases[-1]['dc_comparison']=dc
    require(passed['compared_samples']==expected_samples*len(cases),'Total sample count differs')
    return {'fixture':name,'family':fixture['family'],'role':fixture['role'],
            'numerical_profiles':numerical_profiles,
            'identical_artifact_control':passed['strict_module_sha256']==passed['optimized_module_sha256'],
            'scope':('Complete authored Main fixture including excitation; process callback only, no I2S/UI/network.' if role=='main' else
                     'Complete authored FX fixture with declared external signals; process callback only, generator/cache copy excluded; no I2S/UI/network.'),
            'stimulus_provenance':stimulus_provenance,
            'build_report':str(build_path),'build_report_sha256':sha(build_path),
            'hardware_report':str(run_path),'hardware_report_sha256':sha(run_path),
            'serial_log':str(log),'serial_log_sha256':sha(log),'pass':passed,'cases':cases}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='append',nargs=2,metavar=('BUILD_DIR','RUN_DIR'),required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();require(not args.out.exists(),'Choose a fresh output file')
    results=[collect(Path(b).resolve(),Path(r).resolve()) for b,r in args.run]
    require(len({r['fixture'] for r in results})==len(results),'Duplicate fixture')
    report={'format':'rnbo-object-target-observations','format_version':1,'collector_sha256':sha(Path(__file__)),
            'fixtures':results,'claim':'Observed workload comparisons; no universal numerical or worst-case timing bound'}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'report':str(args.out.resolve()),'fixtures':len(results)}))


if __name__=='__main__':main()
