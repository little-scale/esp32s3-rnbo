#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record short functional outcomes and CPU follow-ups, without implying full qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host/compiler'))
from prepare import canonical


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(test,message):
    if not test:raise ValueError(message)


def fields(line,prefix):
    require(line.startswith(prefix),'Wrong smoke record type')
    result={}
    for token in line[len(prefix):].strip().split():
        pair=token.split('=',1)
        require(len(pair)==2 and pair[0] not in result,'Malformed smoke fields')
        result[pair[0]]=pair[1]
    return result


def cpu_metrics(times):
    require(len(times)==16 and all(type(t)is int and 0<=t<=1000000000 for t in times),
        'Invalid callback observations')
    med=statistics.median(times);mean=sum(times)/len(times);peak=max(times)
    high=med>.1*256*1000000/44100;spike=peak>max(3*med,med+100)
    reasons=(["median_budget"]if high else[])+(["peak_spike"]if spike else[])
    return med,mean,peak,reasons


def collect(build_dir,run_dir):
    build_path=build_dir/'build-report.json';run_path=run_dir/'hardware-smoke.json'
    build=json.loads(build_path.read_bytes());run=json.loads(run_path.read_bytes())
    require(build['format']=='rnbo-hardware-smoke-build-v1' and build['board']=='xiao','Wrong smoke build')
    require(run['format']=='rnbo-hardware-smoke-run-v1' and run['board']=='xiao' and
        run['result']=='completed' and run['left_installed'] is True,'Smoke batch did not complete')
    plan=build['plan'];require(hashlib.sha256(canonical(plan)).hexdigest()==build['plan_sha256'],'Smoke plan changed')
    # Runner field names are checked against its saved receipt and actual log.
    log_path=run_dir/'test-serial.log';raw=log_path.read_bytes();text=raw.decode('utf-8','strict')
    require(run['test_build_report_sha256']==sha(build_path) and run['serial_log_sha256']==sha(log_path),
        'Smoke build or saved serial log differs from runner receipt')
    lines=text.splitlines();case_lines=[line for line in lines if line.startswith('RNBO_SMOKE CASE ')]
    done_lines=[line for line in lines if line.startswith('RNBO_SMOKE DONE ')]
    require(len(done_lines)==1 and len(case_lines)==len(plan['cases']),'Incomplete smoke records')
    require(done_lines[0]==run['done_line'],'Runner/log completion differs')
    done=fields(done_lines[0],'RNBO_SMOKE DONE ')
    require(done['plan_sha256']==build['plan_sha256'],'Device used another smoke plan')
    elfs=[v['sha256']for k,v in build['artifacts'].items()if k.endswith('.elf')]
    require(len(elfs)==1 and done['firmware_elf_sha256']==elfs[0]==run['test_elf_sha256'],'Smoke firmware identity differs')
    records=[];cpu=[]
    for line,expected in zip(case_lines,plan['cases']):
        data=fields(line,'RNBO_SMOKE CASE ')
        require(data['id']==expected['id'] and data['module_sha256']==expected['module_sha256'],'Smoke module identity/order differs')
        times=[int(t)for t in data['times_us'].split(',')]
        med,mean,peak,reasons=cpu_metrics(times)
        require(abs(float(data['median_us'])-med)<1e-5 and abs(float(data['mean_us'])-mean)<1e-5 and
                int(data['peak_us'])==peak,'Callback metrics differ from raw times')
        bits=int(data['bit_mismatches']);zeros=int(data['zero_sign_differences']);samples=int(data['samples'])
        require(samples==20*512 and 0<=zeros<=bits<=samples,'Output comparison counts differ')
        status='pass'if bits==zeros else'output_mismatch'
        require(data['status']==status and int(data['finalized'])==1,'Output/finalization status differs')
        first=int(data['first_mismatch_word'])
        if status=='output_mismatch':
            require(0<=first<512,'Missing output mismatch witness')
            require(re.fullmatch('[0-9a-f]{8}',data['first_actual']) and
                    int(data['first_expected'],16)==expected['expected'][first],'Mismatch witness differs from reference')
            require(int(data['first_actual'],16)!=int(data['first_expected'],16) and
                ((int(data['first_actual'],16)|int(data['first_expected'],16))&0x7fffffff)!=0,
                'Output mismatch witness is only an allowed zero sign or unchanged word')
        else:require(first==0xffffffff,'Passing case has a nonzero-value mismatch witness')
        require(data['review_cpu']==str(int(bool(reasons))) and data['cpu_reasons']==(','.join(reasons)if reasons else'none'),
                'CPU review flags differ from observations')
        record={k:expected[k]for k in ('id','exact_name','syntax','registry_lookup','reference_policy','module_sha256','source_sha256')}
        record.update(status=status,samples_checked=samples,bit_mismatches=bits,zero_sign_differences=zeros,
            mean_us=mean,median_us=med,peak_us=peak,times_us=times,cpu_review_reasons=reasons,
            context_bytes=int(data['context_bytes']),arena_high_water=int(data['arena_high_water']),
            finalized=True,first_mismatch_word=None if first==0xffffffff else first)
        if first!=0xffffffff:record['witness']={k:data[k]for k in ('first_actual','first_expected')}
        records.append(record)
        if reasons:cpu.append({'id':record['id'],'median_us':med,'peak_us':peak,'reasons':reasons,'status':'pending-future-optimisation-review'})
    require(int(done['cases'])==len(records) and int(done['passed'])==sum(r['status']=='pass'for r in records) and
            int(done['mismatched'])==sum(r['status']=='output_mismatch'for r in records) and
            int(done['cpu_review'])==len(cpu) and int(done['images'])==int(done['finalized_images'])==len(records),
            'Smoke completion totals differ')
    return {'format':'rnbo-hardware-smoke-results-v1','board':'xiao','device_label':'xiao-test-device-01',
        'test_level':'short-functional-hardware-check',
        'scope':'Short hardware functionality check, not full mode/domain qualification; no optimisation comparison',
        'firmware_elf_sha256':elfs[0],'plan_sha256':build['plan_sha256'],
        'input_words_sha256':plan['input_words_sha256'],
        'reference_source_sha256':plan['reference_source_sha256'],
        'collector_source_sha256':sha(Path(__file__)),
        'build_report_sha256':sha(build_path),'hardware_report_sha256':sha(run_path),'serial_log_sha256':sha(log_path),
        'left_smoke_firmware_installed':True,'cases':records,'compile_failures':plan['compile_failures'],
        'cpu_review_backlog':cpu,'summary':{'executed':len(records),'passed':int(done['passed']),
            'output_mismatches':int(done['mismatched']),'compile_failures':len(plan['compile_failures']),
            'cpu_review':len(cpu)},'full_qualification_claimed':False,
        'cpu_review_policy':{'timed_callbacks':16,'high_median_block_fraction':0.1,
            'peak_threshold':'greater than max(3*median, median+100us)',
            'action':'Record for future investigation/optimisation; do not automatically change DSP'}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.exists():raise SystemExit('Use a fresh result file')
    try:
        result=collect(args.build,args.run);args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_bytes(canonical(result));print(json.dumps(result['summary']))
    except (ValueError,KeyError,OSError)as exc:raise SystemExit(str(exc))
