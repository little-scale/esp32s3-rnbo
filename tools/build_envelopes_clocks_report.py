#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Publish all31 envelope/clock sources, including isolated target faults."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from build_object_status import checked_short_smoke,checked_envelopes_clocks_fault
ROOT=Path(__file__).resolve().parents[1]
def encoded(v):return(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def products():
    folder=ROOT/'tests/fixtures/smoke/rnbo-envelopes-clocks';cat=json.loads((folder/'catalog.json').read_bytes());found={};sources=[]
    for i in range(1,6):
        path=f'evidence/xiao-smoke-rnbo-envelopes-clocks-part{i}.json';sources.append(path);d=json.loads((ROOT/path).read_bytes())
        if i<4:
            if d.get('family')!='rnbo-envelopes-clocks'or d.get('partition',{}).get('index')!=i or d.get('compile_failures')or d.get('admission_failures'):raise ValueError('Wrong envelope/clock partition')
            for j,c in enumerate(d['cases']):
                checked_short_smoke(dict(id='patcher:'+c['exact_name'],spelling=c['exact_name'],surface='patcher'),dict(source=path,selector=f'/cases/{j}'),d)
                if c['id']in found or c['nonfinite_outputs']!=0:raise ValueError('Repeated/nonfinite source')
                found[c['id']]=(c,path,f'/cases/{j}')
        else:
            rec=dict(id='patcher:'+d['exact_name'],spelling=d['exact_name'],surface='patcher',working_state='partial',board_evidence=True,optimisation_state='unassessed',optimisations=[],cpu_measurement_ids=[])
            checked_envelopes_clocks_fault(rec,dict(source=path),d)
            if d['case_id']in found:raise ValueError('Repeated fault')
            found[d['case_id']]=(d,path,None)
    if set(found)!={r['id']for r in cat['cases']}:raise ValueError('Incomplete31-source ledger')
    restoration=json.loads((ROOT/'evidence/xiao-smoke-rnbo-envelopes-clocks-player-restoration.json').read_bytes())
    if restoration.get('test_result_sources')!=sources or restoration.get('test_result_sha256')!=hashlib.sha256(b''.join((ROOT/p).read_bytes()for p in sources)).hexdigest()or not all(restoration.get(k)is True for k in('audio_frames_advanced','package_identity_preserved','parameter_controls_restored'))or restoration.get('package_sha256_before')!=restoration.get('package_sha256_after')or not restoration.get('fault_counters')or any(restoration['fault_counters'].values()):raise ValueError('Restoration must bind all five completed/fault receipts')
    native=json.loads((ROOT/'evidence/rnbo-envelopes-clocks-native.json').read_bytes())
    if native['catalog_sha256']!=hashlib.sha256((folder/'catalog.json').read_bytes()).hexdigest()or native['reference_sha256']!=hashlib.sha256((folder/'reference.py').read_bytes()).hexdigest()or {r['id']for r in native['cases']}!=set(found):raise ValueError('Native source ledger differs')
    rows=[]
    for s in cat['cases']:
        c,path,selector=found[s['id']];n=next(r for r in native['cases']if r['id']==s['id']);fault=selector is None
        if n['source_sha256']!=s['patch_sha256']or struct.pack('<f',n['absolute_tolerance'])!=struct.pack('<f',s['maximum_absolute_error']):raise ValueError('Native original source/limit differs')
        row=dict(case=s['id'],id='patcher:'+s['exact_name'],name=s['exact_name'],source='tests/fixtures/smoke/rnbo-envelopes-clocks/'+s['patch'],source_sha256=s['patch_sha256'],source_form=s['source_form'],variant=s['variant'],observed_outlet=s['observed_outlet'],evidence=path,selector=selector,optimisation='unassessed',cpu_time_saved_percent=None,full_qualification_claimed=False,aliases_inherit_status=False)
        if fault:
            if n['status']!='native_fault'or n['fault']['fault_call']!=c['before_call']:raise ValueError('Native/target fault stage differs')
            row.update(status=c['fault_stage']+'_fault',fault_stage=c['fault_stage'],before_call=c['before_call'],successful_events=c['successful_events'],platform_errors=c['platform_errors'],late_platform_allocations=c['late_platform_allocations'],complete_output=False,output_words_checked=0,finalization_checked=False,cpu_review_reasons=[],median_us=None,peak_us=None,callback_cpu_percent=None)
        else:
            if n['status']!='native_executed'or n['numeric_mismatches']!=c['numeric_mismatches']:raise ValueError('Native/target outside-screen counts differ')
            row.update({k:c[k]for k in('status','median_us','peak_us','cpu_review_reasons','samples_checked','numeric_mismatches','max_absolute_error','absolute_tolerance','within_tolerance_differences','zero_sign_differences','right_pilot_bit_exact','arena_capacity','arena_high_water')});row.update(complete_output=True,callback_cpu_percent=c['median_us']*44100/2560000,setter_total_us=c['event_total_us'],setter_peak_us=c['event_peak_us'])
        rows.append(row)
    complete=[r for r in rows if r['complete_output']];names=sorted({r['name']for r in rows});summary=dict(source_scenarios=len(rows),exact_spellings=len(names),target_completed=len(complete),target_faults=len(rows)-len(complete),passed=sum(r['status']=='pass'for r in complete),outside_screen=sum(r['status']=='output_mismatch'for r in complete),output_words=sum(r['samples_checked']for r in complete),completed_control_actions=len(complete)*22,numeric_mismatches=sum(r['numeric_mismatches']for r in complete),within_tolerance_differences=sum(r['within_tolerance_differences']for r in complete),zero_sign_differences=sum(r['zero_sign_differences']for r in complete),cpu_review=sum(bool(r['cpu_review_reasons'])for r in complete))
    objects=[dict(name=n,scenario_count=sum(r['name']==n for r in rows),status='board'if all(r['status']=='pass'for r in rows if r['name']==n)else'partial',optimisation='unassessed',cpu_time_saved_percent=None,aliases_inherit_status=False)for n in names]
    paths=sources+['tests/fixtures/smoke/rnbo-envelopes-clocks/catalog.json','tests/fixtures/smoke/rnbo-envelopes-clocks/reference.py','evidence/rnbo-envelopes-clocks-native.json','evidence/rnbo-envelopes-clocks-builds.json','evidence/rnbo-envelopes-clocks-initial-fixture.json','evidence/xiao-smoke-rnbo-envelopes-clocks-player-restoration.json'];inputs={p:dict(bytes=len((ROOT/p).read_bytes()),sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest())for p in paths}
    report=dict(format='rnbo-envelopes-clocks-status-v1',scope='All31 original sources:29 completed captures,8 timing-policy screen gaps and2 isolated target faults. Only selected outlets and authored modes are covered; original references/limits stay fixed. No alias or complete-object qualification inheritance.',sample_rate=44100,block_frames=256,summary=summary,cpu_review_queue_before=164,cpu_review_queue_after=164+summary['cpu_review'],objects=objects,cases=rows,inputs=inputs)
    lines=['# RNBO envelopes, logical edges and event clocks','',f"The batch retains **{summary['source_scenarios']} scenarios across {summary['exact_spellings']} exact spellings**. **{summary['passed']} pass**, **{summary['outside_screen']} retain timing-screen differences**, and **{summary['target_faults']} fault on target**. The **{summary['target_completed']} completed runs check {summary['output_words']:,} output words and {summary['completed_control_actions']:,} control actions**. Raw right captures match throughout completed runs, with no nonfinite outputs. There are {summary['within_tolerance_differences']:,} within-limit differences and {summary['zero_sign_differences']:,} observational left zero-sign differences. No new CPU flag triggers; the review queue stays **{report['cpu_review_queue_after']}**.",'',
        'Every source uses one arm and 21 ordered signed drive events, including repeats, same-callback updates and quiet holds. There are four manual warm plus sixteen timed 256-frame callbacks at 44,100 Hz, and zero automatic warm callbacks. The signal stimulus varies every sixteen samples and includes zero, positive and negative levels. The independent raw right pilot includes signed zero, subnormals and finite extrema.','',
        'Logical references count events or sign transitions independently. Envelope references evaluate segment age in closed form, including the primary implementation\'s one-step attack/release transition and minimum one-sample durations. Curve references use an independent normalized exponential basis and the installed argument-to-curvature mapping. Limits are fixed before execution: logical/delayed values exact, envelopes/event line 2e-5, signal curves 3e-5. All original expected streams and limits remain unchanged.','',
        'The event-clock screen asks for deadlines relative to the intended next callback boundary, rounded to the nearest sample. The edge observer asks for one-block latency with original within-block offsets retained. These are explicit timing-policy probes. Their differences do not by themselves establish eight broken arithmetic objects; host-time origin and signal-to-event delivery need separate interpretation.','',
        '| Object | Scenario | Outcome | Median / peak µs | Callback CPU |','| --- | --- | --- | ---: | ---: |']
    for r in rows:
        timing='—'if not r['complete_output']else f"{r['median_us']:g} / {r['peak_us']}";cpu='—'if not r['complete_output']else f"{r['callback_cpu_percent']:.2f}%";label='Pass'if r['status']=='pass'else'Timing screen differs'if r['status']=='output_mismatch'else r['fault_stage']+' fault'
        lines.append(f"| [`{r['name']}`](../{r['source']}) | {r['case']} | {label} | {timing} | {cpu} |")
    lines+=['','## Compatibility findings','',
        '- All six selected `env2~` signal cases pass: minimum/short/long attack-release, held gates, signed amplitudes and the selected reset sequence. The completion bang is not observed by these signal-outlet cases.',
        '- Five single-segment `curve~` cases pass, including direct assignment and positive/negative/steep curve shapes. The compound retargeting source faults at **event 13 before callback 10**, with **one late platform allocation**. Ten callbacks complete before the fault; it has no completed output/finalisation or steady-state CPU claim.',
        '- Event `line` direct assignment passes. The original 12ms/2ms-grain ramp source faults during **callback 13**, with **one platform error and zero late allocations**. Its sixteen successful parameter actions and thirteen preceding callbacks are retained. The specific platform-error cause remains unproven.',
        '- Both `edge~` selected bang outlets and all four `delay`/two `pipe` cases retain timing-screen differences on native and target runs. Deferred signal-event delivery, observer offsets and the current host-time boundary contract remain investigations. Expected deadlines and limits were not adjusted to captured outputs.',
        '- `onoff`, both event `gatetotrig` directions and all six `onebang` initial/rearm/outlet cases pass. No status transfers to aliases, signal variants or auxiliary observers.','']
    for r in complete:
        if r['status']=='output_mismatch':lines.append(f"- `{r['case']}`: {r['numeric_mismatches']:,} outside-screen words; maximum error {r['max_absolute_error']:.9g}; original limit {r['absolute_tolerance']:.9g}.")
    lines+=['','## Initial fixture and execution scope','',
        'The first immediate-curve graph supplied a zero-time list, selecting a one-sample ramp rather than a direct scalar assignment. Native preflight retained its sixteen differing words. That single graph is corrected before hardware; all 31 original goldens/limits and the other 30 graphs/modules remain unchanged. Original graphs, initial native results and the rejected existing-directory correction attempt are retained. This is one fixture mistake, separate from the compound-curve and line faults.','',
        'Completed callbacks measure 70–361µs median (1.21–6.22%), peak367µs. Setter/routing timing is separate across22 actions. These offline complete-context costs exclude I²S/UI/Wi-Fi work and are not isolated opcode costs or optimisation gains. Failed probes make no complete callback performance claim.','',
        'All29 completed images finalise and pass allocation/memory gates. Fault probes terminate at their original failure, with no substitute source or shortened passing schedule. Normal player, saved Main and live controls are restored; frames advance and reported runtime faults are zero. Other durations, dynamic inlet settings, completion outlets, scheduler/transport contracts, RNBO/Gen forms and complete qualification remain active work. A same-version direct Max-export comparison is separate work; no claim is made here that changing export routes fixes these findings.','',
        'Evidence: [machine-readable report](../evidence/rnbo-envelopes-clocks-status.json), [native](../evidence/rnbo-envelopes-clocks-native.json), [initial fixture](../evidence/rnbo-envelopes-clocks-initial-fixture.json), [build ledger](../evidence/rnbo-envelopes-clocks-builds.json), [restoration](../evidence/xiao-smoke-rnbo-envelopes-clocks-player-restoration.json).','']
    return{'evidence/rnbo-envelopes-clocks-status.json':encoded(report),'docs/rnbo-envelopes-clocks.md':'\n'.join(lines).encode()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,data in products().items():
        if name.startswith('docs/') and name.endswith('.md'):
            title, rest = data.decode().split('\n', 1)
            data = (title + '\n\n> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.\n\n' + rest.lstrip('\n')).encode()
        p=ROOT/name
        if a.check:
            if not p.is_file()or p.read_bytes()!=data:raise SystemExit('Stale envelope/clock report: '+name)
        else:p.write_bytes(data)
    print('Envelope/clock report checked'if a.check else'Envelope/clock report written')
if __name__=='__main__':main()
