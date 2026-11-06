#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Publish every list-extension source outcome, including isolated growth faults."""
import argparse
import hashlib
import json
from pathlib import Path
from build_object_status import checked_short_smoke,checked_list_target_fault
ROOT=Path(__file__).resolve().parents[1]
BASELINE_CPU_CONTEXTS=157
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def fault_record(c):return dict(id='patcher:'+c['exact_name'],spelling=c['exact_name'],surface='patcher',working_state='partial',board_evidence=True,cpu_measurement_ids=[],optimisation_state='unassessed',optimisations=[])
def products():
    folder=ROOT/'tests/fixtures/smoke/rnbo-list-extended';catalog=json.loads((folder/'catalog.json').read_bytes());observations={};sources=[]
    for i in(1,2):
        source=f'evidence/xiao-smoke-rnbo-list-extended-part{i}.json';sources.append(source);data=json.loads((ROOT/source).read_bytes())
        if data.get('family')!='rnbo-list-extended'or data.get('partition',{}).get('index')!=i or data.get('compile_failures')or data.get('admission_failures'):raise ValueError('Wrong completed list partition')
        for j,c in enumerate(data['cases']):
            if c['id']in observations:raise ValueError('Repeated list source')
            checked_short_smoke(dict(id='patcher:'+c['exact_name'],spelling=c['exact_name'],surface='patcher'),dict(source=source,selector=f'/cases/{j}'),data)
            observations[c['id']]=(c,source,f'/cases/{j}')
    completed_sources=sources[:]
    for i in range(3,7):
        source=f'evidence/xiao-list-extended-growth-fault-part{i}.json';sources.append(source);c=json.loads((ROOT/source).read_bytes());checked_list_target_fault(fault_record(c),dict(source=source,selector='/'),c)
        if c['case_id']in observations:raise ValueError('Repeated list fault')
        observations[c['case_id']]=(c,source,'/')
    if set(observations)!={s['id']for s in catalog['cases']}:raise ValueError('Incomplete 32-source list ledger')
    restoration=json.loads((ROOT/'evidence/xiao-smoke-rnbo-list-extended-player-restoration.json').read_bytes())
    if (restoration.get('test_result_sources')!=sources or restoration.get('test_result_sha256')!=hashlib.sha256(b''.join((ROOT/p).read_bytes()for p in sources)).hexdigest()or
        not all(restoration.get(k)is True for k in('audio_frames_advanced','package_identity_preserved','parameter_controls_restored'))or
        restoration.get('package_sha256_before')!=restoration.get('package_sha256_after')or not restoration.get('fault_counters')or any(restoration['fault_counters'].values())):raise ValueError('List restoration must bind all completed tests, faults and saved controls')
    rows=[]
    for s in catalog['cases']:
        c,source,selector=observations[s['id']];fault=selector=='/';status='event_fault'if fault else c['status']
        rows.append(dict(case=s['id'],id='patcher:'+s['exact_name'],name=s['exact_name'],source='tests/fixtures/smoke/rnbo-list-extended/'+s['patch'],source_sha256=s['patch_sha256'],source_form=s['source_form'],variant=s['variant'],observed_outlet=s['observed_outlet'],output_kind=s['output_kind'],status=status,evidence=source,selector=selector,median_us=c.get('median_us'),peak_us=c.get('peak_us'),callback_cpu_percent=None if fault else c['median_us']*44100/2560000,setter_total_us=c.get('event_total_us'),setter_peak_us=c.get('event_peak_us'),cpu_review_reasons=c.get('cpu_review_reasons',[]),samples_checked=c.get('samples_checked',0),numeric_mismatches=c.get('numeric_mismatches'),max_absolute_error=c.get('max_absolute_error'),within_tolerance_differences=c.get('within_tolerance_differences'),zero_sign_differences=c.get('zero_sign_differences'),right_pilot_bit_exact=c.get('right_pilot_bit_exact'),late_platform_allocations=c.get('late_platform_allocations')if fault else None,event_fault_elapsed_us=c.get('event_elapsed_us')if fault else None,optimisation='unassessed',cpu_time_saved_percent=None,full_qualification_claimed=False,aliases_inherit_status=False))
    completed=[r for r in rows if r['status']!='event_fault'];names=sorted({r['name']for r in rows})
    summary=dict(source_scenarios=len(rows),exact_spellings=len(names),target_completed=len(completed),passed=sum(r['status']=='pass'for r in rows),outside_screen=sum(r['status']=='output_mismatch'for r in rows),event_faults=sum(r['status']=='event_fault'for r in rows),output_words=sum(r['samples_checked']for r in completed),completed_control_actions=sum(observations[r['case']][0]['parameter_events_applied']for r in completed),numeric_mismatches=sum(r['numeric_mismatches']for r in completed),within_tolerance_differences=sum(r['within_tolerance_differences']for r in completed),zero_sign_differences=sum(r['zero_sign_differences']for r in completed),cpu_review=sum(bool(r['cpu_review_reasons'])for r in completed))
    objects=[dict(name=n,scenario_count=sum(r['name']==n for r in rows),status='board'if all(r['status']=='pass'for r in rows if r['name']==n)else'partial',optimisation='unassessed',cpu_time_saved_percent=None,aliases_inherit_status=False)for n in names]
    paths=sources+['tests/fixtures/smoke/rnbo-list-extended/catalog.json','tests/fixtures/smoke/rnbo-list-extended/reference.py','evidence/rnbo-list-extended-native.json','evidence/rnbo-list-extended-builds.json','evidence/xiao-smoke-rnbo-list-extended-player-restoration.json']
    inputs={p:dict(bytes=len((ROOT/p).read_bytes()),sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest())for p in paths}
    report=dict(format='rnbo-list-extended-status-v1',scope='All32 sources across17 exact spellings;28 complete target output checks and4 isolated capacity-growth event faults. A union policy difference is retained. No alias/surface inheritance or complete-object qualification.',sample_rate=44100,block_frames=256,summary=summary,cpu_review_queue_before=BASELINE_CPU_CONTEXTS,cpu_review_queue_after=BASELINE_CPU_CONTEXTS+summary['cpu_review'],objects=objects,cases=rows,inputs=inputs)
    lines=['# RNBO extended list and storage checks','',f"The batch covers **{summary['source_scenarios']} scenarios across {summary['exact_spellings']} exact spellings**. **{summary['passed']} complete output checks pass**, **{summary['outside_screen']} retains a union-policy difference**, and **{summary['event_faults']} growing FIFO/LIFO scenarios fault in target events**. The completed checks cover **{summary['output_words']:,} output words** and **{summary['completed_control_actions']:,} control actions**. All completed raw right captures match; no nonfinite output occurs. The CPU queue reaches **{report['cpu_review_queue_after']}**, with {summary['cpu_review']} new callback flags.",'','One arm action opens a startup gate, then 21 ordered drives encode an integer tag and fractional digit. Repeated identical lists exercise suppression/comparison; three drives share callback 10 and two share callback 16. Four manual warm and sixteen timed full 256-frame callbacks are checked at 44,100 Hz, with zero automatic warm callbacks. Parameters are resolved by ID with actual and normalised readbacks. All numerical limits are zero.','',
        'List code `length*32768 + sum(item[i]*8**i)` is exact for up to five digits in 0…7 and distinguishes lengths and trailing zeros. Iteration, funnel and changed-list emission observers accumulate bounded code sums below 2^24. Those sums check emitted content totals and suppression; they do not encode arbitrary event order without collisions. Storage-before-bang order is explicit. Auxiliary objects gain no inherited qualification.','',
        '| Exact spelling | Scenario | Outcome | Median / peak µs | Callback CPU | Setter total / peak µs |','| --- | --- | --- | ---: | ---: | ---: |']
    for c in rows:
        timing='—'if c['median_us']is None else f"{c['median_us']:g} / {c['peak_us']}";cpu='—'if c['callback_cpu_percent']is None else f"{c['callback_cpu_percent']:.2f}%";setter='—'if c['setter_total_us']is None else f"{c['setter_total_us']} / {c['setter_peak_us']}"
        label={'pass':'Pass','output_mismatch':'Policy difference','event_fault':'Growth event fault'}[c['status']]
        lines.append(f"| [`{c['name']}`](../{c['source']}) | {c['case']} | {label} | {timing} | {cpu} | {setter} |")
    lines+=['','## Findings and limits','',
        '**Growing queues/stacks:** the original scenarios push three values and pop one on each drive. Both observed outlets of each object fault on drive eight, before callback seven, with `RNBO_S3_FAULT` (-4) and positive late-platform-allocation statistics. Seven callbacks execute first, but these aborted probes make no completed output, raw-capture or finalisation claim. Four separately authored controls push three and pop three, keeping storage bounded; their normal output checks remain separate from the growth faults. Native preflight finds the same fault stage. These are capacity-growth compatibility gaps to investigate, not callback CPU measurements.','',
        '**Union policy:** the installed help says right-list items already present in the left list are omitted. This screen preserves duplicates already inside the left list. The reference XML also describes duplicate removal more broadly. The unchanged screen retains the measured difference in both native and XIAO execution; it is a documented-policy ambiguity to resolve, not proof of an ESP32-only numerical defect. No output-derived oracle replacement or tolerance change is made.','']
    for c in completed:
        if c['status']=='output_mismatch':lines.append(f"- `{c['case']}`: {c['numeric_mismatches']:,} outside-screen words, maximum code difference {c['max_absolute_error']:.17g}, original limit 0.")
    lines+=['','Event/routing/observer work is measured in setters separately from callbacks rendering held outputs and the raw pilot. The table reports complete fixture costs, not isolated object costs or optimisation gains. All completed images finalise and pass memory/allocation gates. The normal player, saved Main and controls are restored after all probes, with frame progress and zero runtime faults checked.','',
        'Other list lengths/types, reset modes, empty/invalid indexing, larger storage, random list operations, other RNBO/Gen forms and complete sample-by-sample qualification remain open. The full goal stays active.','',
        'Evidence: [machine-readable report](../evidence/rnbo-list-extended-status.json), [native preflight](../evidence/rnbo-list-extended-native.json), [build ledger](../evidence/rnbo-list-extended-builds.json), [player restoration](../evidence/xiao-smoke-rnbo-list-extended-player-restoration.json).','']
    return{'evidence/rnbo-list-extended-status.json':encoded(report),'docs/rnbo-list-extended.md':'\n'.join(lines).encode()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for path,b in products().items():
        if path.startswith('docs/') and path.endswith('.md'):
            title, rest = b.decode().split('\n', 1)
            b = (title + '\n\n> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.\n\n' + rest.lstrip('\n')).encode()
        out=ROOT/path
        if a.check:
            if not out.is_file()or out.read_bytes()!=b:raise SystemExit('Stale list report: '+path)
        else:out.write_bytes(b)
    print('Extended-list report checked'if a.check else'Extended-list report written')
if __name__=='__main__':main()
