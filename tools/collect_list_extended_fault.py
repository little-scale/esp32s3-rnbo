#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect isolated FIFO/LIFO capacity-growth event faults without output passes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from build_hardware_smoke import list_extended_catalog
from collect_hardware_smoke import fields, list_extended_plan
from prepare import canonical
ROOT=Path(__file__).resolve().parents[1]
def require(v,msg):
    if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def collect(build_dir,run_dir):
    bp=build_dir/'build-report.json';rp=run_dir/'hardware-smoke.json';lp=run_dir/'test-serial.log'
    build=json.loads(bp.read_bytes());run=json.loads(rp.read_bytes());plan=build['plan'];index=plan.get('partition',{}).get('index')
    require(type(index)is int and index in(3,4,5,6),'Growth probe requires a singleton fault partition')
    catalog=json.loads((ROOT/f'tests/fixtures/smoke/rnbo-list-extended/part{index}.json').read_bytes());list_extended_catalog(catalog);list_extended_plan(plan)
    require(len(plan['cases'])==1 and not plan.get('compile_failures')and not plan.get('admission_failures'),'Growth probe must retain one compiled original source')
    source=catalog['cases'][0];case=plan['cases'][0]
    require(source['exact_name']in('list.queue','list.stack')and source['variant']=='default'and hashlib.sha256(canonical(plan)).hexdigest()==build['plan_sha256'],'Growth probe source/plan differs')
    require(run.get('format')=='rnbo-hardware-smoke-run-v1'and run.get('result')=='failed'and run.get('flash_attempted')is True and run.get('left_installed')is True and run.get('complete_fault_line')is True and run.get('done_line')is None and run.get('case_lines')==[]and run.get('test_build_report_sha256')==sha(bp)and run.get('serial_log_sha256')==sha(lp),'Growth fault must not claim completed output comparisons')
    elf=[v['sha256']for k,v in build['artifacts'].items()if k.endswith('.elf')];require(len(elf)==1 and run.get('test_elf_sha256')==elf[0],'Probe firmware differs')
    lines=lp.read_text().splitlines();starts=[fields(s,'RNBO_SMOKE START ')for s in lines if s.startswith('RNBO_SMOKE START ')]
    require(len(starts)==1 and starts[0].get('firmware_elf_sha256')==elf[0]and starts[0].get('plan_sha256')==build['plan_sha256']and starts[0].get('cases')=='1','Probe startup must bind the flashed plan')
    events=[fields(s,'RNBO_SMOKE EVENT ')for s in lines if s.startswith('RNBO_SMOKE EVENT ')];faults=[fields(s,'RNBO_SMOKE EVENT_RESULT ')for s in lines if s.startswith('RNBO_SMOKE EVENT_RESULT ')]
    actions=case['parameter_events'];require(len(actions)==22 and len(events)==8 and len(faults)==1,'Growth event prefix/fault count differs')
    for ordinal,event in enumerate(events):
        a=actions[ordinal]
        require(event.get('case_id')==source['id']and event.get('ordinal')==str(ordinal)and event.get('before_call')==str(a['before_call'])and event.get('parameter_slot')==str(a['parameter_slot'])and event.get('value_word')==event.get('actual_word')==f"{a['value_word']:08x}"and event.get('normalized_word')==f"{a['normalized_word']:08x}"and re.fullmatch('[0-9]+',event.get('event_us',''))is not None,'Successful event/readback prefix differs')
    fault=faults[0];a=actions[8]
    require(a['before_call']==7 and case['parameters'][a['parameter_slot']]['id']=='drive'and fault.get('case_id')==source['id']and fault.get('ordinal')=='8'and fault.get('before_call')=='7'and fault.get('parameter_slot')==str(a['parameter_slot'])and fault.get('value_word')==f"{a['value_word']:08x}"and fault.get('status')=='-4'and fault.get('readback_status')==fault.get('statistics_status')=='0'and fault.get('platform_errors')==fault.get('invalid_samples')=='0','Growth event fault stage/statistics differs')
    require(re.fullmatch('[0-9]+',fault.get('elapsed_us',''))is not None and re.fullmatch('[0-9]+',fault.get('late_platform_allocations',''))is not None and int(fault['late_platform_allocations'])>0,'Growth fault must retain observed late allocation')
    require(any(': FAIL 'in s and 'condition=result==RNBO_S3_OK && elapsed>=0 && readback==RNBO_S3_OK'in s for s in lines)and not any(s.startswith(('RNBO_SMOKE CASE ','RNBO_SMOKE DONE '))for s in lines),'Probe must stop at original event fault')
    return dict(format='rnbo-list-extended-target-fault-v1',board='xiao',device_label='xiao-test-device-01',partition=index,case_id=source['id'],exact_name=source['exact_name'],observed_outlet=source['observed_outlet'],source_sha256=source['patch_sha256'],module_sha256=case['module_sha256'],firmware_elf_sha256=elf[0],plan_sha256=build['plan_sha256'],build_report_sha256=sha(bp),hardware_report_sha256=sha(rp),serial_log_sha256=sha(lp),collector_source_sha256=sha(Path(__file__)),hardware_attempted=True,arm_observed=True,successful_events=8,before_call=7,fault_event=8,value_word=f"{a['value_word']:08x}",event_status=-4,readback_status=0,event_elapsed_us=int(fault['elapsed_us']),statistics_status=0,platform_errors=0,invalid_samples=0,late_platform_allocations=int(fault['late_platform_allocations']),callbacks_executed_before_fault=7,output_words_checked=0,finalization_checked=False,raw_right_capture_checked=False,numeric_pass_claimed=False,full_qualification_claimed=False,scope='Original growing FIFO/LIFO source: push three items, pop one per drive. Eighth drive faults with positive late-platform-allocation statistics. Seven callbacks run before the fault; no complete output capture or numerical/finalization pass is claimed. Separate bounded push-three/pop-three controls are not substituted for this source.')
def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.write_text(json.dumps(collect(a.build,a.run),indent=2,sort_keys=True)+'\n');print('Original FIFO/LIFO target growth fault recorded')
if __name__=='__main__':main()
