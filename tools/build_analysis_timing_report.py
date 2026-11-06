#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Publish every authored analysis/timing source, retaining mode-specific gaps."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from build_object_status import checked_short_smoke
ROOT=Path(__file__).resolve().parents[1]
BASELINE_CPU_CONTEXTS=164
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def products():
    folder=ROOT/'tests/fixtures/smoke/rnbo-analysis-timing';catalog=json.loads((folder/'catalog.json').read_bytes());observations={};sources=[]
    for i in range(1,3):
        source=f'evidence/xiao-smoke-rnbo-analysis-timing-part{i}.json';sources.append(source);data=json.loads((ROOT/source).read_bytes())
        if data.get('family')!='rnbo-analysis-timing'or data.get('partition',{}).get('index')!=i or data.get('compile_failures')or data.get('admission_failures'):raise ValueError('Wrong analysis/timing partition')
        for j,c in enumerate(data['cases']):
            if c['id']in observations or c.get('nonfinite_outputs')!=0:raise ValueError('Repeated/nonfinite analysis case')
            checked_short_smoke(dict(id='patcher:'+c['exact_name'],spelling=c['exact_name'],surface='patcher'),dict(source=source,selector=f'/cases/{j}'),data);observations[c['id']]=(c,source,j)
    if set(observations)!={s['id']for s in catalog['cases']}:raise ValueError('Incomplete 23-source analysis ledger')
    restoration=json.loads((ROOT/'evidence/xiao-smoke-rnbo-analysis-timing-player-restoration.json').read_bytes())
    if (restoration.get('test_result_sources')!=sources or restoration.get('test_result_sha256')!=hashlib.sha256(b''.join((ROOT/p).read_bytes()for p in sources)).hexdigest()or not all(restoration.get(k)is True for k in('audio_frames_advanced','package_identity_preserved','parameter_controls_restored'))or restoration.get('package_sha256_before')!=restoration.get('package_sha256_after')or not restoration.get('fault_counters')or any(restoration['fault_counters'].values())):raise ValueError('Analysis restoration must bind all tests and original controls')
    rows=[]
    for s in catalog['cases']:
        c,source,j=observations[s['id']]
        rows.append(dict(case=s['id'],id='patcher:'+s['exact_name'],name=s['exact_name'],source='tests/fixtures/smoke/rnbo-analysis-timing/'+s['patch'],source_sha256=s['patch_sha256'],source_form=s['source_form'],variant=s['variant'],observed_outlet=s['observed_outlet'],signal_input=s['signal_input'],status=c['status'],evidence=source,selector=f'/cases/{j}',median_us=c['median_us'],peak_us=c['peak_us'],callback_cpu_percent=c['median_us']*44100/2560000,setter_total_us=c['event_total_us'],setter_peak_us=c['event_peak_us'],cpu_review_reasons=c['cpu_review_reasons'],samples_checked=c['samples_checked'],numeric_mismatches=c['numeric_mismatches'],max_absolute_error=c['max_absolute_error'],absolute_tolerance=c['absolute_tolerance'],within_tolerance_differences=c['within_tolerance_differences'],zero_sign_differences=c['zero_sign_differences'],right_pilot_bit_exact=c['right_pilot_bit_exact'],arena_capacity=c['arena_capacity'],arena_high_water=c['arena_high_water'],optimisation='unassessed',cpu_time_saved_percent=None,full_qualification_claimed=False,aliases_inherit_status=False))
    names=sorted({r['name']for r in rows});summary=dict(source_scenarios=len(rows),exact_spellings=len(names),target_completed=len(rows),passed=sum(r['status']=='pass'for r in rows),outside_screen=sum(r['status']=='output_mismatch'for r in rows),output_words=sum(r['samples_checked']for r in rows),completed_control_actions=sum(observations[r['case']][0]['parameter_events_applied']for r in rows),numeric_mismatches=sum(r['numeric_mismatches']for r in rows),within_tolerance_differences=sum(r['within_tolerance_differences']for r in rows),zero_sign_differences=sum(r['zero_sign_differences']for r in rows),cpu_review=sum(bool(r['cpu_review_reasons'])for r in rows))
    objects=[dict(name=n,scenario_count=sum(r['name']==n for r in rows),status='board'if all(r['status']=='pass'for r in rows if r['name']==n)else'partial',optimisation='unassessed',cpu_time_saved_percent=None,aliases_inherit_status=False)for n in names]
    paths=sources+['tests/fixtures/smoke/rnbo-analysis-timing/catalog.json','tests/fixtures/smoke/rnbo-analysis-timing/reference.py','evidence/rnbo-analysis-timing-native.json','evidence/rnbo-analysis-timing-builds.json','evidence/xiao-smoke-rnbo-analysis-timing-player-restoration.json'];inputs={p:dict(bytes=len((ROOT/p).read_bytes()),sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest())for p in paths}
    report=dict(format='rnbo-analysis-timing-status-v1',scope='All 23 event/signal sources across 16 exact spellings. Reports, thresholds, windows and clock policies stay distinct; no aliases, auxiliary-object or complete-domain inheritance.',sample_rate=44100,block_frames=256,summary=summary,cpu_review_queue_before=BASELINE_CPU_CONTEXTS,cpu_review_queue_after=BASELINE_CPU_CONTEXTS+summary['cpu_review'],objects=objects,cases=rows,inputs=inputs)
    native=json.loads((ROOT/'evidence/rnbo-analysis-timing-native.json').read_bytes())
    if native['catalog_sha256']!=hashlib.sha256((folder/'catalog.json').read_bytes()).hexdigest()or native['reference_sha256']!=hashlib.sha256((folder/'reference.py').read_bytes()).hexdigest()or {v['id']for v in native['cases']}!={v['case']for v in rows}:raise ValueError('Native source ledger differs')
    for row in rows:
        n=next(n for n in native['cases']if n['id']==row['case'])
        if n['source_sha256']!=row['source_sha256']or struct.pack('<f',n['absolute_tolerance'])!=struct.pack('<f',row['absolute_tolerance'])or n['numeric_mismatches']!=row['numeric_mismatches']:raise ValueError('Native/target source, limits or outside-screen counts differ')
    lines=['# RNBO signal-analysis and sample-clock checks','',f"The batch covers **{summary['source_scenarios']} scenarios across {summary['exact_spellings']} exact spellings**. **{summary['passed']} pass**, and **{summary['outside_screen']} retain report/clock timing differences** against the original screen. Checks cover **{summary['output_words']:,} output words and {summary['completed_control_actions']:,} control actions**. All raw right captures match, and no nonfinite or zero-sign differences occur. There are {summary['within_tolerance_differences']:,} within-limit differences. No new callback CPU flag triggers; **{report['cpu_review_queue_after']} contexts** remain queued.",'',
        'One arm precedes 21 ordered signed drive events, including repeated values, three updates before one callback, and quiet holds. Every source runs four manual warm and sixteen timed full 256-frame callbacks at 44,100 Hz, with zero automatic warm callbacks. Signal inputs vary every sample within blocks. The right pilot independently checks signed zero, subnormals and finite extrema. Parameter IDs, actual values and normalised readbacks are checked.','',
        'References use independent mean/absolute/RMS window definitions, sign changes, threshold hysteresis and elapsed sample ordinals. Averages begin with the populated partial window. Zero is nonnegative for crossing detection. Equal thresholds reset strictly below the threshold; unequal thresholds reset at or below the low threshold. Seven-value event averages, 2/3/7-event crossing windows and manual reports remain distinct. Empty mean/peak report windows produce zero; snapshot retains the previous last sample.','',
        'The timing screen deliberately asks for a report to be visible in the first rendered block after a bang, for signal clocks to advance each sample from origin zero, and for event clocks to reflect the next callback boundary. Limits were fixed before compilation: exact dyadic/state/ordinal checks 0, means/RMS 2e-6, millisecond clocks 2e-5 ms. All 23 original expected streams and limits remain unchanged. These particular latency/origin requirements require the interpretation below; full compatibility remains unproven for the four differing forms.','',
        '| Exact spelling | Scenario | Outcome | Median / peak µs | Callback CPU | Arena high-water bytes |','| --- | --- | --- | ---: | ---: | ---: |']
    for c in rows:
        label='Pass'if c['status']=='pass'else'Timing screen differs'
        lines.append(f"| [`{c['name']}`](../{c['source']}) | {c['case']} | {label} | {c['median_us']:g} / {c['peak_us']} | {c['callback_cpu_percent']:.2f}% | {c['arena_high_water']:,} |")
    lines+=['','## Retained report and clock-policy findings','',
        'The same four screens differ in native and XIAO runs. These observations bind the authored observer and module call ordering. They do not establish four DSP defects or an ESP32-only difference.','',
        '- `avg~`: the manual-report screen expects the previous sample window to be visible in the immediately following rendered block. The exported scheduling path queues its held report at the end of that block, so the `sig~` observer receives a deferred report. Qualification of this latency contract remains open; the mean-absolute equation and original numerical limits are not substituted with captured outputs.',
        '- `currentsampletime~`: the screen expects an ordinal increment at every sample. The exported expression instead writes the current block sample counter plus the host event offset throughout the block. `samplecount~` passes the separate continuously incrementing signal screen, and event `currentsampletime` passes the boundary screen.',
        '- `currenttime` and `currenttime~`: these screens expect origin-zero sample-position milliseconds. The exported path observes the host block-time field; event delivery before the next process call can observe the preceding block time, and the signal value follows block time rather than each sample. Host-application absolute time, scheduled within-block offsets and alternate report observers remain separate tests.','']
    for c in rows:
        if c['status']=='output_mismatch':lines.append(f"- `{c['case']}`: {c['numeric_mismatches']:,} outside-screen words, maximum error {c['max_absolute_error']:.17g}, original limit {c['absolute_tolerance']:.9g}.")
    lines+=['','## Performance and resource follow-up','',
        'Complete callback time includes the compiled fixture and raw pilot; event setters/routing are separately timed across 22 actions. These are offline callback costs without I²S/UI/Wi-Fi work. No isolated opcode cost, whole-chip CPU percentage, loaded-player deadline guarantee or optimisation saving is claimed.','',
        'All three seven-value event averages pass, but each consumes **352,880 arena bytes** in the explicit **1 MiB ceiling**. The installed primary operator allocates a sample-rate-sized Float64 buffer, even for the selected small event window. A bounded event-rate storage implementation is a memory optimisation candidate; numerical equivalence, dynamic window/reset behaviour and real-time allocation policy must be checked before changing it. A 4 KiB resource configuration is not qualified by these runs.','',
        'All 23 images finalise and pass allocation/memory gates. Normal player, saved Main and live controls are restored; frames advance and runtime faults remain zero. Other window sizes, dynamic windows/resets, periodic reporting, absolute/transport origins, within-block events, other RNBO/Gen forms and complete sample-by-sample qualification remain open. The full goal stays active.','',
        'Evidence: [machine-readable report](../evidence/rnbo-analysis-timing-status.json), [native](../evidence/rnbo-analysis-timing-native.json), [build ledger](../evidence/rnbo-analysis-timing-builds.json), [player restoration](../evidence/xiao-smoke-rnbo-analysis-timing-player-restoration.json).','']
    return{'evidence/rnbo-analysis-timing-status.json':encoded(report),'docs/rnbo-analysis-timing.md':'\n'.join(lines).encode()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for path,b in products().items():
        if path.startswith('docs/') and path.endswith('.md'):
            title, rest = b.decode().split('\n', 1)
            b = (title + '\n\n> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.\n\n' + rest.lstrip('\n')).encode()
        out=ROOT/path
        if a.check:
            if not out.is_file()or out.read_bytes()!=b:raise SystemExit('Stale analysis/timing report: '+path)
        else:out.write_bytes(b)
    print('Analysis/timing report checked'if a.check else'Analysis/timing report written')
if __name__=='__main__':main()
