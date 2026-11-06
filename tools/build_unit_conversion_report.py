#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Source-bound event/signal unit output screens and whole-callback costs."""
import argparse
import hashlib
import json
from pathlib import Path
from build_object_status import checked_short_smoke
ROOT=Path(__file__).resolve().parents[1]
BASELINE_CPU_CONTEXTS=156
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def products():
    folder=ROOT/'tests/fixtures/smoke/rnbo-unit-conversions'
    catalog=json.loads((folder/'catalog.json').read_bytes());cases={};inputs={}
    paths=['tests/fixtures/smoke/rnbo-unit-conversions/catalog.json','tests/fixtures/smoke/rnbo-unit-conversions/reference.py',
           'evidence/rnbo-unit-conversions-native.json','evidence/rnbo-unit-conversions-builds.json',
           'evidence/rnbo-unit-conversions-attempts.json','evidence/xiao-smoke-rnbo-unit-conversions-player-restoration.json']
    for i in(1,2):
        source=f'evidence/xiao-smoke-rnbo-unit-conversions-part{i}.json';paths.append(source);data=json.loads((ROOT/source).read_bytes())
        if data.get('family')!='rnbo-unit-conversions'or data.get('partition',{}).get('index')!=i:raise ValueError('Wrong unit partition')
        for j,c in enumerate(data['cases']):
            if c['id']in cases:raise ValueError('Repeated unit source')
            if c.get('nonfinite_outputs')!=0:raise ValueError('Unit report requires finite outputs')
            checked_short_smoke(dict(id='patcher:'+c['exact_name'],surface='patcher',spelling=c['exact_name']),dict(source=source,selector=f'/cases/{j}'),data)
            cases[c['id']]=(c,source,j)
    if set(cases)!={x['id']for x in catalog['cases']}:raise ValueError('Unit source ledger is incomplete')
    restoration=json.loads((ROOT/'evidence/xiao-smoke-rnbo-unit-conversions-player-restoration.json').read_bytes())
    result_sources=[f'evidence/xiao-smoke-rnbo-unit-conversions-part{i}.json'for i in(1,2)]
    if (restoration.get('test_result_sources')!=result_sources or restoration.get('test_result_sha256')!=hashlib.sha256(b''.join((ROOT/p).read_bytes()for p in result_sources)).hexdigest()
        or not all(restoration.get(k)is True for k in('audio_frames_advanced','package_identity_preserved','parameter_controls_restored'))
        or restoration.get('package_sha256_before')!=restoration.get('package_sha256_after')or not restoration.get('fault_counters')or any(restoration['fault_counters'].values())):
        raise ValueError('Unit player restoration does not bind these results and saved controls')
    rows=[]
    for s in catalog['cases']:
        c,source,j=cases[s['id']]
        rows.append(dict(id='patcher:'+c['exact_name'],name=c['exact_name'],source='tests/fixtures/smoke/rnbo-unit-conversions/'+s['patch'],source_sha256=s['patch_sha256'],
            evidence=source,selector=f'/cases/{j}',status=c['status'],optimisation='unassessed',cpu_time_saved_percent=None,
            median_us=c['median_us'],peak_us=c['peak_us'],callback_cpu_percent=c['median_us']*44100/2560000,
            setter_total_us=c['event_total_us'],setter_peak_us=c['event_peak_us'],cpu_review_reasons=c['cpu_review_reasons'],
            absolute_tolerance=c['absolute_tolerance'],max_absolute_error=c['max_absolute_error'],numeric_mismatches=c['numeric_mismatches'],
            within_tolerance_differences=c['within_tolerance_differences'],zero_sign_differences=c['zero_sign_differences'],samples_checked=c['samples_checked'],
            right_pilot_bit_exact=c['right_pilot_bit_exact'],input_domain=s['input_domain'],full_qualification_claimed=False,aliases_inherit_status=False))
    summary=dict(executed=len(rows),passed=sum(c['status']=='pass'for c in rows),outside_screen=sum(c['status']=='output_mismatch'for c in rows),
                 output_words=sum(c['samples_checked']for c in rows),parameter_events=len(rows)*21,cpu_review=sum(bool(c['cpu_review_reasons'])for c in rows),
                 numeric_mismatches=sum(c['numeric_mismatches']for c in rows),within_tolerance_differences=sum(c['within_tolerance_differences']for c in rows),
                 zero_sign_differences=sum(c['zero_sign_differences']for c in rows))
    for p in paths:
        b=(ROOT/p).read_bytes();inputs[p]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
    report=dict(format='rnbo-unit-conversion-status-v1',scope='Exact authored numeric event and signal forms, fixed stopped120BPM/480PPQ/4-4 transport at44100Hz; no transport-event, zero-reciprocal, reset or arbitrary-mode qualification.',
        sample_rate=44100,block_frames=256,cpu_review_queue_before=BASELINE_CPU_CONTEXTS,cpu_review_queue_after=BASELINE_CPU_CONTEXTS+summary['cpu_review'],inputs=inputs,summary=summary,objects=rows)
    lines=['# RNBO event and signal unit conversions','',
        f"The XIAO executes **{summary['executed']} exact spellings**: **{summary['passed']} pass** their predeclared rational output screen and **{summary['outside_screen']} retains a numerical difference**. The batch checks **{summary['output_words']:,} output words** and **{summary['parameter_events']} ordered parameter actions**. Every raw right-channel capture matches; no nonfinite output occurs. The CPU review queue reaches **{BASELINE_CPU_CONTEXTS+summary['cpu_review']}**, with {summary['cpu_review']} added by this batch.",'',
        'The 21 numeric-event forms use `param → conversion → sig~`. The 15 signal forms use `in~ 1 +~ sig~(param) → conversion~`, with 16 distinct left-input levels inside each block. Four manual warm callbacks and sixteen timed callbacks are all checked; there are no automatic warm callbacks. Repeats, held values and three ordered actions before one callback are included. Actual and normalised readbacks are checked. No source spelling inherits another spelling’s result.','',
        'References use exact rational dimensional conversions at **44,100 Hz, 120 BPM, 480 ticks per quarter note and stopped 4/4 transport**, rounded once to binary32 at the output. Reciprocal inputs exclude zero. Other linear forms include negative inputs. The separate right pilot covers signed zeros, finite extrema and subnormals; its 5,120 captured words per case are hashed independently of left-channel tolerance.','',
        'Limits are fixed in output units before compilation: the largest is 0.008 **samples**, less than 0.2 microseconds at this sample rate. The existing event families retain their original ceilings. The initial hardware harness stopped before its seventh case because it still had the old 0.001 ceiling; the corrected generated header permits this new family’s declared limits. No per-object limit or expected output changed. Original attempt hashes are retained.','',
        '| Exact spelling | Output screen | Optimisation | CPU saved | Median / peak µs | Callback CPU | Review |',
        '| --- | --- | --- | --- | ---: | ---: | --- |']
    for c in rows:
        label='Pass'if c['status']=='pass'else'Outside screen';flag='Queued'if c['cpu_review_reasons']else'—'
        lines.append(f"| [`{c['name']}`](../{c['source']}) | {label} | Unassessed | — | {c['median_us']:g} / {c['peak_us']} | {c['callback_cpu_percent']:.2f}% | {flag} |")
    lines+=['','## Numerical differences','',
        f"There are {summary['within_tolerance_differences']:,} within-limit output differences, {summary['zero_sign_differences']:,} observational left zero-sign differences and {summary['numeric_mismatches']:,} outside-limit output words. Right-channel zero signs remain strict. Native preflight independently executes all 36 sources and retains its own numerical counts.",'']
    for c in rows:
        if c['status']!='pass':lines.append(f"- `{c['name']}`: {c['numeric_mismatches']} words exceed the original {c['absolute_tolerance']:g} limit; maximum error {c['max_absolute_error']:.17g} output units. Compilation, execution, parameter readbacks and the raw pilot still pass. The native preflight also records this rounding difference; no ESP-specific cause is inferred.")
    lines+=['','## Performance scope and next work','',
        'Callback timing includes the complete compiled FX graph, dispatch, signal addition where authored, and the right pilot. Event forms calculate in their setter/routing path; its 21-action total and peak are recorded separately in the JSON report. Neither measurement is an isolated opcode cost or a matched optimisation gain. Flagged contexts are recorded for later investigation; functional coverage continues first.','',
        'All images finalise and allocation/memory checks pass. The normal player, saved Main and live controls are restored; USB audio-frame progress and zero fault counters are checked. This offline timing firmware runs without I²S, UI or Wi-Fi and does not establish a loaded-player deadline. Changed tempo/transport, reset/constructor options, zero/nonfinite reciprocal inputs, MIDI clock and other domains remain unqualified. The full RNBO/Gen goal remains active.','',
        'Evidence: [part 1](../evidence/xiao-smoke-rnbo-unit-conversions-part1.json), [part 2](../evidence/xiao-smoke-rnbo-unit-conversions-part2.json), [native preflight](../evidence/rnbo-unit-conversions-native.json), [build ledger](../evidence/rnbo-unit-conversions-builds.json), [initial attempt](../evidence/rnbo-unit-conversions-attempts.json), [player restoration](../evidence/xiao-smoke-rnbo-unit-conversions-player-restoration.json), [machine-readable report](../evidence/rnbo-unit-conversions-status.json).','']
    return{'evidence/rnbo-unit-conversions-status.json':encoded(report),'docs/rnbo-unit-conversions.md':'\n'.join(lines).encode()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for path,b in products().items():
        if path.startswith('docs/') and path.endswith('.md'):
            title, rest = b.decode().split('\n', 1)
            b = (title + '\n\n> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.\n\n' + rest.lstrip('\n')).encode()
        out=ROOT/path
        if a.check:
            if not out.is_file()or out.read_bytes()!=b:raise SystemExit('Stale unit report: '+path)
        else:out.write_bytes(b)
    print('Unit conversion report checked'if a.check else'Unit conversion report written')
if __name__=='__main__':main()
