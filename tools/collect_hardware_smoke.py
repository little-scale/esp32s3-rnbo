#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record short functional outcomes and CPU follow-ups, without implying full qualification."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import struct
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


def output_metrics(data,expected,common_input_sha):
    bits=int(data['bit_mismatches']);zeros=int(data['zero_sign_differences']);samples=int(data['samples'])
    require(samples==20*512 and 0<=zeros<=bits<=samples,'Output comparison counts differ')
    metrics={'samples_checked':samples,'bit_mismatches':bits,'zero_sign_differences':zeros}
    numeric=bits-zeros
    if 'numeric_mismatches' in data:
        numeric=int(data['numeric_mismatches']);within=int(data['within_tolerance_differences'])
        nonfinite=int(data['nonfinite_outputs'])
        if 'max_absolute_error_bits' in data:
            require(re.fullmatch('[0-9a-f]{16}',data['max_absolute_error_bits']) and
                    re.fullmatch('[0-9a-f]{8}',data['absolute_tolerance_bits']),
                    'Malformed binary error/tolerance record')
            error=struct.unpack('<d',struct.pack('<Q',int(data['max_absolute_error_bits'],16)))[0]
            tolerance=struct.unpack('<f',struct.pack('<I',int(data['absolute_tolerance_bits'],16)))[0]
        else:
            error=float(data['max_absolute_error']);tolerance=float(data['absolute_tolerance'])
        require(0<=nonfinite<=numeric<=bits and 0<=within<=bits and numeric+within+zeros==bits,
            'Numerical comparison counters differ')
        require(math.isfinite(tolerance) and 0<=tolerance<=.001 and tolerance==expected.get('absolute_tolerance',0) and
                math.isfinite(error) and error>=0 and (within==0 or tolerance>0),
                'Predeclared error tolerance or observed error differs')
        require((numeric>0 or error<=tolerance) and (numeric==nonfinite or error>tolerance),
                'Numerical status contradicts the largest finite error')
        require(data['input_words_sha256']==expected.get('input_words_sha256',common_input_sha),
                'Device input vector differs from the prepared case')
        metrics.update(numeric_mismatches=numeric,within_tolerance_differences=within,nonfinite_outputs=nonfinite,
            max_absolute_error=error,absolute_tolerance=tolerance,input_words_sha256=data['input_words_sha256'])
    else:require(expected.get('absolute_tolerance',0)==0 and 'input_words' not in expected,
        'Per-case vector/tolerance requires the new device comparison record')
    status='pass' if numeric==0 else 'output_mismatch'
    require(data['status']==status and int(data['finalized'])==1,'Output/finalization status differs')
    return dict(metrics,status=status)


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
        output=output_metrics(data,expected,plan['input_words_sha256']);status=output['status']
        first=int(data['first_mismatch_word'])
        if status=='output_mismatch':
            require(0<=first<512,'Missing output mismatch witness')
            require(re.fullmatch('[0-9a-f]{8}',data['first_actual']) and
                    int(data['first_expected'],16)==expected['expected'][first],'Mismatch witness differs from reference')
            require(int(data['first_actual'],16)!=int(data['first_expected'],16) and
                ((int(data['first_actual'],16)|int(data['first_expected'],16))&0x7fffffff)!=0,
                'Output mismatch witness is only an allowed zero sign or unchanged word')
            actual=struct.unpack('<f',bytes.fromhex(data['first_actual'])[::-1])[0]
            target=struct.unpack('<f',struct.pack('<I',expected['expected'][first]))[0]
            if math.isfinite(actual):
                require(abs(actual-target)>expected.get('absolute_tolerance',0),
                    'Mismatch witness is within the predeclared error tolerance')
                if 'max_absolute_error' in output:
                    require(output['max_absolute_error']>=abs(actual-target),'Maximum error omits the mismatch witness')
            else:require(output.get('nonfinite_outputs',1)>0,'Nonfinite witness count differs')
        else:require(first==0xffffffff,'Passing case has a nonzero-value mismatch witness')
        require(data['review_cpu']==str(int(bool(reasons))) and data['cpu_reasons']==(','.join(reasons)if reasons else'none'),
                'CPU review flags differ from observations')
        record={k:expected[k]for k in ('id','exact_name','syntax','registry_lookup','reference_policy','module_sha256','source_sha256')}
        record.update(**output,
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
    result={'format':'rnbo-hardware-smoke-results-v1','board':'xiao','device_label':'xiao-test-device-01',
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
    if plan.get('family') in ('rnbo-stateless','rnbo-numeric') and plan.get('surface')=='patcher':
        result.update(family=plan['family'],surface='patcher')
    elif plan.get('family')=='gen-math' and plan.get('surface')=='genexpr':
        result.update(family='gen-math',surface='genexpr')
    if 'input_vector_policy' in plan:result['input_vector_policy']=plan['input_vector_policy']
    if 'prepare_zero_warm_blocks' in plan:
        require(all(fields(line,'RNBO_SMOKE CASE ')['prepare_zero_warm_blocks']==str(plan['prepare_zero_warm_blocks'])
                    for line in case_lines),'Device preparation warmup differs from the plan')
        result['prepare_zero_warm_blocks']=plan['prepare_zero_warm_blocks']
    if 'admission_failures' in plan:
        result['admission_failures']=plan['admission_failures']
        result['summary']['admission_failures']=len(plan['admission_failures'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.exists():raise SystemExit('Use a fresh result file')
    try:
        result=collect(args.build,args.run);args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_bytes(canonical(result));print(json.dumps(result['summary']))
    except (ValueError,KeyError,OSError)as exc:raise SystemExit(str(exc))
