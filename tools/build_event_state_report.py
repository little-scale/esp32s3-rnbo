#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Publish exact state scenarios, retaining startup-fixture corrections separately."""
import argparse
import hashlib
import json
from pathlib import Path
from build_object_status import checked_short_smoke
ROOT=Path(__file__).resolve().parents[1]
BASELINE_CPU_CONTEXTS=157
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def products():
    folder=ROOT/'tests/fixtures/smoke/rnbo-event-state';catalog=json.loads((folder/'catalog.json').read_bytes());cases={};inputs={}
    paths=['tests/fixtures/smoke/rnbo-event-state/catalog.json','tests/fixtures/smoke/rnbo-event-state/reference.py',
           'tests/fixtures/smoke/rnbo-event-state/startup-exposed-v1/catalog.json','tests/fixtures/smoke/rnbo-event-state/startup-exposed-v1/reference.py',
           'evidence/rnbo-event-state-native.json','evidence/rnbo-event-state-builds.json','evidence/rnbo-event-state-startup-attempt.json',
           'evidence/xiao-smoke-rnbo-event-state-player-restoration.json']
    sources=[f'evidence/xiao-smoke-rnbo-event-state-part{i}.json'for i in(1,2)]
    for i,source in enumerate(sources,1):
        paths.append(source);data=json.loads((ROOT/source).read_bytes())
        if data.get('family')!='rnbo-event-state'or data.get('partition',{}).get('index')!=i:raise ValueError('Wrong event-state partition')
        for j,c in enumerate(data['cases']):
            if c['id']in cases or c.get('nonfinite_outputs')!=0:raise ValueError('Repeated or nonfinite event-state case')
            checked_short_smoke(dict(id='patcher:'+c['exact_name'],surface='patcher',spelling=c['exact_name']),dict(source=source,selector=f'/cases/{j}'),data)
            cases[c['id']]=(c,source,j)
    if set(cases)!={s['id']for s in catalog['cases']}:raise ValueError('Event-state source ledger is incomplete')
    restoration=json.loads((ROOT/'evidence/xiao-smoke-rnbo-event-state-player-restoration.json').read_bytes())
    if (restoration.get('test_result_sources')!=sources or restoration.get('test_result_sha256')!=hashlib.sha256(b''.join((ROOT/p).read_bytes()for p in sources)).hexdigest()
        or not all(restoration.get(k)is True for k in('audio_frames_advanced','package_identity_preserved','parameter_controls_restored'))
        or restoration.get('package_sha256_before')!=restoration.get('package_sha256_after')or not restoration.get('fault_counters')or any(restoration['fault_counters'].values())):
        raise ValueError('Event-state restoration does not bind these results and saved controls')
    rows=[]
    for s in catalog['cases']:
        c,source,j=cases[s['id']]
        rows.append(dict(case=c['id'],id='patcher:'+c['exact_name'],name=c['exact_name'],variant=s['variant'],observed_outlet=s['observed_outlet'],
            source='tests/fixtures/smoke/rnbo-event-state/'+s['patch'],source_sha256=s['patch_sha256'],evidence=source,selector=f'/cases/{j}',
            status=c['status'],optimisation='unassessed',cpu_time_saved_percent=None,median_us=c['median_us'],peak_us=c['peak_us'],
            callback_cpu_percent=c['median_us']*44100/2560000,setter_total_us=c['event_total_us'],setter_peak_us=c['event_peak_us'],
            cpu_review_reasons=c['cpu_review_reasons'],absolute_tolerance=c['absolute_tolerance'],max_absolute_error=c['max_absolute_error'],
            numeric_mismatches=c['numeric_mismatches'],within_tolerance_differences=c['within_tolerance_differences'],zero_sign_differences=c['zero_sign_differences'],
            samples_checked=c['samples_checked'],right_pilot_bit_exact=c['right_pilot_bit_exact'],parameter_events=c['parameter_events_applied'],
            full_qualification_claimed=False,aliases_inherit_status=False))
    names=sorted({r['name']for r in rows});summary=dict(executed=len(rows),exact_spellings=len(names),passed=sum(c['status']=='pass'for c in rows),
        outside_screen=sum(c['status']=='output_mismatch'for c in rows),output_words=sum(c['samples_checked']for c in rows),
        parameter_events=sum(c['parameter_events']for c in rows),drive_events=len(rows)*21,arm_events=len(rows),
        cpu_review=sum(bool(c['cpu_review_reasons'])for c in rows),numeric_mismatches=sum(c['numeric_mismatches']for c in rows),
        within_tolerance_differences=sum(c['within_tolerance_differences']for c in rows),zero_sign_differences=sum(c['zero_sign_differences']for c in rows))
    for p in paths:
        b=(ROOT/p).read_bytes();inputs[p]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
    report=dict(format='rnbo-event-state-status-v1',scope='36 armed source scenarios across15 exact numeric-event spellings; no auxiliary-object, signal, codebox or Gen inheritance.',
        sample_rate=44100,block_frames=256,cpu_review_queue_before=BASELINE_CPU_CONTEXTS,cpu_review_queue_after=BASELINE_CPU_CONTEXTS+summary['cpu_review'],inputs=inputs,summary=summary,cases=rows)
    lines=['# RNBO ordered event-state checks','',
        f"The XIAO executes **{summary['executed']} scenarios across {summary['exact_spellings']} exact spellings**: **{summary['passed']} pass** their fixed output screens; **{summary['outside_screen']} retain outside-screen differences**. The batch checks **{summary['output_words']:,} output words**, **{summary['drive_events']} drive events** and **{summary['arm_events']} arm actions**. Every raw right-channel capture matches and no nonfinite output occurs. The CPU review queue remains at {BASELINE_CPU_CONTEXTS} before this batch and reaches **{BASELINE_CPU_CONTEXTS+summary['cpu_review']}** afterwards.",'',
        'The sources cover additive/multiplicative prefixes and neutral resets, closed/open/switched latches, changed-value sums and zero/nonzero transition counts, four bounded counter directions/ranges and immediate/next resets, all peak/trough numeric outlets, asymmetric slide/rampsmooth state, sample-and-hold threshold edges, and right-before-left trigger ordering. Each alias has its own authored graphs and executions. Only these forms and domains are qualified.','',
        'Each graph has two parameters: `drive` (-8…8, initial 0) and `arm` (0…1, initial 0). A closed `gate 1 0` blocks startup drive notifications. The first controlled action sets arm to 1; its right-to-left trigger seeds counter/peak/trough cold inputs before opening the gate. The following 21 drive actions include repeats, held callbacks and three ordered changes before callback 10. This makes the initial state explicit and independent of startup notification order. All actual/normalised readbacks are checked by parameter ID. Auxiliary gate/observer objects gain no inferred qualification.','',
        'References use independent prefix sums/products, bounded index sequences, event-change/edge predicates and exact rational smoothing trajectories. Only slide/rampsmooth allow a predeclared 2e-6 absolute output difference; all other numeric limits are zero. Additive resets use hot input 0, multiplicative resets use hot input 1, so reset/input precedence cannot obscure reset-state checks. Counter reset-next values include values outside its bounds, as documented. Four manual warm callbacks and sixteen timed callbacks are all checked, with no automatic warmup. The right pilot has a separate hash over 5,120 raw words, including signed zeros, subnormals and finite extrema.','',
        '| Exact spelling | Scenario | Outlet | Output screen | Median / peak µs | Callback CPU | Setter total / peak µs |',
        '| --- | --- | ---: | --- | ---: | ---: | ---: |']
    for c in rows:
        label='Pass'if c['status']=='pass'else'Outside screen'
        lines.append(f"| [`{c['name']}`](../{c['source']}) | {c['variant']} | {c['observed_outlet']} | {label} | {c['median_us']:g} / {c['peak_us']} | {c['callback_cpu_percent']:.2f}% | {c['setter_total_us']} / {c['setter_peak_us']} |")
    lines+=['','## Numerical and startup findings','',
        f"There are {summary['within_tolerance_differences']:,} within-limit numeric differences, {summary['zero_sign_differences']:,} observational left zero-sign differences and {summary['numeric_mismatches']:,} outside-limit words. The right observer remains strict. Native preflight has its own separate counts.",'',
        'The first native-only fixtures omitted the startup parameter event: the initial drive=0 advanced counters and zeroed product accumulators before the measured sequence. Six of 36 original screens consequently differed. Those original sources, references and native results are archived in `startup-exposed-v1` and the startup-attempt receipt. They are fixture-initialisation findings, not six hardware object failures. No original fixture was flashed. The corrected sources add explicit arming and synchronous cold seeding; **all 36 expected output streams and all numerical limits remain unchanged**. No captured outputs were substituted for expectations.','']
    for c in rows:
        if c['status']!='pass':lines.append(f"- `{c['name']}` / `{c['variant']}`: {c['numeric_mismatches']} outside-limit words, maximum error {c['max_absolute_error']:.17g}, original limit {c['absolute_tolerance']:g}.")
    lines+=['','## Performance scope and remaining qualification','',
        'The state operations execute in the event setter/routing path; its total and peak cover all 22 actions, including arming, and are not isolated opcode timings. The timed audio callback mainly renders the held output and right pilot. Callback CPU is callback time divided by the 256-frame period, not total chip CPU. Optimisation remains unassessed and no percentage saving is claimed. Any threshold-crossing callback is retained in the CPU review queue.','',
        'All images finalise and allocation/memory gates pass. The normal player, saved Main and live controls are restored; USB frame progress and zero runtime faults are checked. There is no new audio capture or loaded-player deadline claim. Other reset/constructor modes, counter carry outlets, lists, bang/data types beyond authored forms, signal/codebox/Gen counterparts and within-block host event offsets remain unqualified. The full RNBO/Gen goal remains active.','',
        'Evidence: [part 1](../evidence/xiao-smoke-rnbo-event-state-part1.json), [part 2](../evidence/xiao-smoke-rnbo-event-state-part2.json), [native preflight](../evidence/rnbo-event-state-native.json), [build ledger](../evidence/rnbo-event-state-builds.json), [original startup attempt](../evidence/rnbo-event-state-startup-attempt.json), [player restoration](../evidence/xiao-smoke-rnbo-event-state-player-restoration.json), [machine-readable report](../evidence/rnbo-event-state-status.json).','']
    return{'evidence/rnbo-event-state-status.json':encoded(report),'docs/rnbo-event-state.md':'\n'.join(lines).encode()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for path,b in products().items():
        out=ROOT/path
        if a.check:
            if not out.is_file()or out.read_bytes()!=b:raise SystemExit('Stale event-state report: '+path)
        else:out.write_bytes(b)
    print('Event-state report checked'if a.check else'Event-state report written')
if __name__=='__main__':main()
