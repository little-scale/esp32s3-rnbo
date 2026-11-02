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


def declared_stimulus(fixture,case):
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


def input_evidence(build,fixture,plan,passed,lines,expected_samples):
    name=fixture['id'];role=fixture['role'];case_count=len(fixture['cases'])
    prefix='RNBO_OBJECT_BENCHMARK INPUT '
    records=[fields(line.strip(),prefix) for line in lines if line.strip().startswith(prefix)]
    evidence={}
    if role=='main':
        require(not records,'Main fixture cannot claim external INPUT evidence')
        require('stimulus' not in fixture and all('stimulus' not in c for c in fixture['cases']),'Main fixture declares ignored stimulus')
        require('stimuli' not in plan or plan['stimuli']==[None]*case_count,'Main plan declares external stimulus')
        require(all(passed.get(k,0)==0 for k in ('input_cases','input_rechecks','pilot_sample_checks')),'Main fixture has unexpected FX input counters')
        return evidence,None
    require(len(records)==case_count,'Incomplete FX INPUT evidence')
    for key,expected in (('input_cases',case_count),('input_rechecks',case_count*plan['rounds']*3),
                         ('pilot_sample_checks',expected_samples*case_count)):
        require(type(passed.get(key)) is int and passed[key]==expected,'FX input/pilot coverage differs: '+key)
    require(isinstance(plan.get('stimuli'),list) and len(plan['stimuli'])==case_count,'Compiled stimulus plan missing')
    for index,case in enumerate(fixture['cases']):
        expected=declared_stimulus(fixture,case)
        require(plan['stimuli'][index]==expected,'Compiled stimulus differs from catalog/case declaration')
        found=[r for r in records if r.get('fixture')==name and r.get('case')==case['id']]
        require(len(found)==1,'Missing or duplicate FX INPUT case')
        record=found[0];digest(record.get('input_sha256'),'Malformed target input SHA256')
        require(type(record.get('input_bytes')) is int and record['input_bytes']==plan['blocks']*256*2*4,'FX input byte coverage differs')
        require(record.get('layout')=='float32_stereo_interleaved_le','FX input layout differs')
        require(type(record.get('stimulus_kind')) is int and record['stimulus_kind']==expected['kind'],'FX input stimulus kind differs')
        evidence[case['id']]={**record,'declared_settings':expected['settings']}
    source_names=('object-benchmark/main/stimulus.c','object-benchmark/main/stimulus.h')
    sources=build.get('source_files_sha256',{})
    generator={key:digest(sources.get(key),'Missing generator source identity') for key in source_names}
    provenance={'catalog_path':plan.get('catalog_path'),'catalog_sha256':digest(plan.get('catalog_sha256'),'Missing stimulus catalog identity'),
                'patch_sha256':digest(plan.get('patch_sha256'),'Missing fixture patch identity'),
                'generator_source_sha256':generator,'sample_rate':44100,'block_frames':256,
                'sample_time':'Zero-based rendered frame n/44100 after zero-input warmup',
                'generation':'Float64 sine and arithmetic; round each completed channel sample once to Float32',
                'timing':'Generator/cache copy excluded from process callback timers',
                'rechecks':'Cached INPUT SHA before/after every strict and optimized pass; shared adjacent-pass checkpoint',
                'pilot':'Every rendered output reference/pilot sample equals its declared input channel',
                'limit':'Target SHA fingerprints actual cached input; host/target transcendental byte identity is not assumed'}
    require(isinstance(provenance['catalog_path'],str) and provenance['catalog_path'],'Missing stimulus catalog path')
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
        reference=timings['strict']['mean_process_us'];candidate=timings['optimized']['mean_process_us']
        cases.append({'case':declared['id'],'declared_case':declared,'input':inputs.get(declared['id']),'output_comparison':case,'profiles':timings,
                      'observed_speed_ratio':reference/candidate,'observed_process_reduction_percent':100*(1-candidate/reference)})
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
