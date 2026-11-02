#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Seal observed per-fixture target results with build/log identities.

Reports whole-fixture process timings. Main fixtures include their excitation
objects; these numbers must not be presented as isolated operator timings.
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
    for profile,field in (('strict','strict_module_sha256'),('optimized','optimized_module_sha256')):
        require(passed[field]==build['modules'][profile]['artifact_sha256'],'Native module identity differs')
    for field in ('host_heap_allocations','host_heap_frees','local_late_allocations'):
        require(passed[field]==0,'Unexpected running allocation')
    require(passed['psram_before']==passed['psram_after'] and passed['internal_after']>=passed['internal_before'],'Module memory did not recover')
    require(passed['images']==passed['finalized_images']==4,'Missing image finalization')
    require(passed['cases']==len(fixture['cases']) and passed['rounds']==plan['rounds'] and passed['blocks_per_pass']==plan['blocks'],'Measurement plan differs')
    require(passed['timing_exclude']==plan['timing_exclude_blocks'],'Timing exclusion differs')
    require(passed['warmup']==fixture['warmup_blocks'] and passed['seed']==fixture['seed'],'Initial state differs')
    expected_blocks=plan['rounds']*(plan['blocks']-plan['timing_exclude_blocks'])
    expected_samples=plan['rounds']*plan['blocks']*512
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
            timings[profile]={**value,'mean_process_us':value['process_us']/value['timed_blocks']}
        reference=timings['strict']['mean_process_us'];candidate=timings['optimized']['mean_process_us']
        cases.append({'case':declared['id'],'output_comparison':case,'profiles':timings,
                      'observed_speed_ratio':reference/candidate,'observed_process_reduction_percent':100*(1-candidate/reference)})
    require(passed['compared_samples']==expected_samples*len(cases),'Total sample count differs')
    return {'fixture':name,'family':fixture['family'],'role':fixture['role'],
            'identical_artifact_control':passed['strict_module_sha256']==passed['optimized_module_sha256'],
            'scope':'Complete authored fixture; process callback only, no I2S/UI/network. Main excitation is included.',
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
