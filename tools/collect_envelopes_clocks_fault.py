#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect two exact isolated envelope/clock faults; no completed output claims."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from build_hardware_smoke import envelopes_clocks_catalog
from collect_hardware_smoke import envelopes_clocks_plan,fields
from prepare import canonical
ROOT=Path(__file__).resolve().parents[1]
def require(v,msg):
    if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def collect(build_dir,run_dir):
    bp=build_dir/'build-report.json';rp=run_dir/'hardware-smoke.json';lp=run_dir/'test-serial.log'
    build=json.loads(bp.read_bytes());run=json.loads(rp.read_bytes());plan=build['plan'];index=plan.get('partition',{}).get('index')
    require(type(index)is int and index in(4,5),'Envelope/clock fault requires a singleton partition')
    catalog=json.loads((ROOT/f'tests/fixtures/smoke/rnbo-envelopes-clocks/part{index}.json').read_bytes());envelopes_clocks_catalog(catalog);envelopes_clocks_plan(plan)
    require(len(plan['cases'])==1 and not plan.get('compile_failures')and not plan.get('admission_failures'),'Fault ledger requires one original compiled source')
    source=catalog['cases'][0];case=plan['cases'][0];curve=index==4
    require(source['id']==('curve-compound'if curve else'line-ramp')and hashlib.sha256(canonical(plan)).hexdigest()==build['plan_sha256'],'Fault source/plan differs')
    require(run.get('format')=='rnbo-hardware-smoke-run-v1'and run.get('result')=='failed'and run.get('flash_attempted')is True and run.get('left_installed')is True and run.get('complete_fault_line')is True and run.get('done_line')is None and run.get('case_lines')==[]and run.get('test_build_report_sha256')==sha(bp)and run.get('serial_log_sha256')==sha(lp),'Fault must not claim completed output comparisons')
    elf=[v['sha256']for k,v in build['artifacts'].items()if k.endswith('.elf')];require(len(elf)==1 and run.get('test_elf_sha256')==elf[0],'Fault firmware differs')
    lines=lp.read_text().splitlines();starts=[fields(s,'RNBO_SMOKE START ')for s in lines if s.startswith('RNBO_SMOKE START ')]
    require(len(starts)==1 and starts[0].get('plan_sha256')==build['plan_sha256']and starts[0].get('cases')=='1','Fault startup plan differs')
    events=[fields(s,'RNBO_SMOKE EVENT ')for s in lines if s.startswith('RNBO_SMOKE EVENT ')];prefix=13 if curve else 16;call=10 if curve else 13
    require(len(events)==prefix,'Successful action prefix differs');actions=case['parameter_events'];resolved={}
    for ordinal,event in enumerate(events):
        a=actions[ordinal]
        require(event.get('case_id')==source['id']and event.get('ordinal')==str(ordinal)and event.get('before_call')==str(a['before_call'])and event.get('parameter_slot')==str(a['parameter_slot'])and event.get('value_word')==event.get('actual_word')==f"{a['value_word']:08x}"and event.get('normalized_word')==f"{a['normalized_word']:08x}"and re.fullmatch('[0-9]+',event.get('event_us',''))is not None,'Successful action/readback differs')
        slot=a['parameter_slot'];abi=int(event.get('resolved_index','-1'));require(abi in(0,1)and resolved.get(slot,abi)==abi,'Resolved index changed');resolved[slot]=abi
    require(len(resolved)==2 and len(set(resolved.values()))==2,'Both distinct parameter IDs must be resolved')
    label='RNBO_SMOKE EVENT_RESULT 'if curve else'RNBO_SMOKE PROCESS_RESULT '
    faults=[fields(s,label)for s in lines if s.startswith(label)];other='RNBO_SMOKE PROCESS_RESULT 'if curve else'RNBO_SMOKE EVENT_RESULT '
    require(len(faults)==1 and not any(s.startswith(other)for s in lines),'Fault stage differs');fault=faults[0]
    require(fault.get('case_id')==source['id']and fault.get('before_call')==str(call)and fault.get('status')=='-4'and fault.get('statistics_status')=='0'and fault.get('invalid_samples')=='0','Fault status/time/statistics differs')
    require(re.fullmatch('[0-9]+',fault.get('elapsed_us',''))is not None,'Fault elapsed time missing')
    if curve:
        action=actions[13]
        require(fault.get('ordinal')=='13'and fault.get('parameter_slot')==str(action['parameter_slot'])and case['parameters'][action['parameter_slot']]['id']=='drive'and fault.get('value_word')==f"{action['value_word']:08x}"=='3f800000'and fault.get('readback_status')=='0'and fault.get('platform_errors')=='0'and re.fullmatch('[0-9]+',fault.get('late_platform_allocations',''))is not None and int(fault['late_platform_allocations'])>0,'Compound curve allocation fault differs')
        condition='condition=result==RNBO_S3_OK && elapsed>=0 && readback==RNBO_S3_OK'
    else:
        require(fault.get('platform_errors')=='1'and fault.get('late_platform_allocations')=='0','Line processing error differs');condition='condition=result==RNBO_S3_OK && elapsed>=0'
    require(any(': FAIL 'in s and condition in s for s in lines)and not any(s.startswith(('RNBO_SMOKE CASE ','RNBO_SMOKE DONE '))for s in lines),'Fault must stop before completed output/finalisation')
    return dict(format='rnbo-envelopes-clocks-target-fault-v1',board='xiao',device_label='xiao-test-device-01',partition=index,case_id=source['id'],exact_name=source['exact_name'],source_sha256=source['patch_sha256'],module_sha256=case['module_sha256'],firmware_elf_sha256=elf[0],plan_sha256=build['plan_sha256'],build_report_sha256=sha(bp),hardware_report_sha256=sha(rp),serial_log_sha256=sha(lp),collector_source_sha256=sha(Path(__file__)),hardware_attempted=True,arm_observed=True,successful_events=prefix,before_call=call,fault_stage='event'if curve else'process',fault_event=13 if curve else None,status=-4,statistics_status=0,platform_errors=int(fault['platform_errors']),invalid_samples=0,late_platform_allocations=int(fault['late_platform_allocations']),fault_elapsed_us=int(fault['elapsed_us']),callbacks_completed_before_fault=call,output_words_checked=0,finalization_checked=False,raw_right_capture_checked=False,numeric_pass_claimed=False,full_qualification_claimed=False,scope='Original compound curve retargeting or timed line source. Successful action/readback prefix and exact fault stage are retained. No completed output stream, numerical pass, finalisation pass, steady-state CPU or optimisation saving is claimed.')
def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.write_text(json.dumps(collect(a.build,a.run),indent=2,sort_keys=True)+'\n');print('Envelope/clock hardware fault recorded')
if __name__=='__main__':main()
