#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect the original positive-rotation fault without claiming an output pass."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from build_hardware_smoke import event_routing_catalog
from collect_hardware_smoke import fields
from prepare import canonical
ROOT=Path(__file__).resolve().parents[1]
def require(v,msg):
    if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def collect(build_dir,run_dir):
    bp=build_dir/'build-report.json';rp=run_dir/'hardware-smoke.json';lp=run_dir/'test-serial.log'
    build=json.loads(bp.read_bytes());run=json.loads(rp.read_bytes());plan=build['plan']
    catalog=json.loads((ROOT/'tests/fixtures/smoke/rnbo-event-routing/part0.json').read_bytes());event_routing_catalog(catalog)
    require(plan.get('family')=='rnbo-event-routing'and plan.get('partition')==catalog['partition']and len(plan['cases'])==1,
            'Rotation probe requires its exact singleton source')
    source=catalog['cases'][0];case=plan['cases'][0]
    require(all(case.get(k)==v for k,v in source.items())and case.get('source_sha256')==source['patch_sha256']and
            hashlib.sha256(canonical(plan)).hexdigest()==build['plan_sha256'],'Rotation probe source/plan differs')
    require(plan.get('reference_source_sha256')==sha(ROOT/'tests/fixtures/smoke/rnbo-event-routing/unobserved-no-match-v1/reference.py'),
            'Original rotation probe must retain its frozen reference identity')
    require(run.get('format')=='rnbo-hardware-smoke-run-v1'and run.get('result')=='failed'and run.get('flash_attempted')is True and
            run.get('left_installed')is True and run.get('complete_fault_line')is True and run.get('done_line')is None and
            run.get('case_lines')==[]and run.get('test_build_report_sha256')==sha(bp)and run.get('serial_log_sha256')==sha(lp),
            'Rotation probe must retain its target fault, not a completed comparison')
    elf=[v['sha256']for k,v in build['artifacts'].items()if k.endswith('.elf')];require(len(elf)==1 and run.get('test_elf_sha256')==elf[0],'Probe firmware differs')
    lines=lp.read_text().splitlines();start=[fields(s,'RNBO_SMOKE START ')for s in lines if s.startswith('RNBO_SMOKE START ')]
    require(len(start)==1 and start[0].get('firmware_elf_sha256')==elf[0]and start[0].get('plan_sha256')==build['plan_sha256']and
            start[0].get('cases')=='1','Probe startup does not bind the flashed plan')
    events=[fields(s,'RNBO_SMOKE EVENT ')for s in lines if s.startswith('RNBO_SMOKE EVENT ')]
    rejected=[fields(s,'RNBO_SMOKE EVENT_RESULT ')for s in lines if s.startswith('RNBO_SMOKE EVENT_RESULT ')]
    require(len(events)==len(rejected)==1,'Probe event prefix/rejection differs')
    arm=events[0];fault=rejected[0];actions=case['parameter_events'];require(len(actions)==22,'Probe action count differs')
    require(arm.get('case_id')==source['id']and arm.get('ordinal')=='0'and arm.get('before_call')=='0'and
            int(arm['parameter_slot'])==actions[0]['parameter_slot']and case['parameters'][actions[0]['parameter_slot']]['id']=='arm'and
            arm.get('value_word')==arm.get('actual_word')==arm.get('normalized_word')=='3f800000','Probe did not arm successfully')
    require(fault.get('case_id')==source['id']and fault.get('ordinal')=='1'and fault.get('before_call')=='0'and
            int(fault['parameter_slot'])==actions[1]['parameter_slot']and case['parameters'][actions[1]['parameter_slot']]['id']=='drive'and
            fault.get('value_word')=='3e000000'and fault.get('status')=='-4'and fault.get('readback_status')=='0'and
            re.fullmatch('[0-9]+',fault.get('elapsed_us',''))is not None,'Probe target event result differs')
    require(any(': FAIL 'in s and 'condition=result==RNBO_S3_OK && elapsed>=0 && readback==RNBO_S3_OK'in s for s in lines)and
            not any(s.startswith(('RNBO_SMOKE CASE ','RNBO_SMOKE DONE '))for s in lines),'Probe must stop at the original event fault')
    return dict(format='rnbo-event-routing-target-fault-v1',board='xiao',device_label='xiao-test-device-01',case_id=source['id'],exact_name=source['exact_name'],
        source_sha256=source['patch_sha256'],module_sha256=case['module_sha256'],firmware_elf_sha256=elf[0],plan_sha256=build['plan_sha256'],
        build_report_sha256=sha(bp),hardware_report_sha256=sha(rp),serial_log_sha256=sha(lp),collector_source_sha256=sha(Path(__file__)),
        hardware_attempted=True,arm_observed=True,before_call=0,fault_event=1,value_word='3e000000',event_status=-4,readback_status=0,
        event_elapsed_us=int(fault['elapsed_us']),output_words_checked=0,completed_callbacks=0,finalization_checked=False,raw_right_capture_checked=False,
        numeric_pass_claimed=False,full_qualification_claimed=False,scope='Original positive list.rot source enters the first measured drive event on XIAO and returns RNBO_S3_FAULT; no audio callback or output comparison completes. Native fault, target fault and normal batch results are separate.')
def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=collect(a.build,a.run);a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print('Original positive-rotation target event fault recorded')
if __name__=='__main__':main()
