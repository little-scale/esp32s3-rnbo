#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Publish every authored maths/mixing source, retaining mode-specific gaps."""
import argparse
import hashlib
import json
from pathlib import Path
from build_object_status import checked_short_smoke
ROOT=Path(__file__).resolve().parents[1]
BASELINE_CPU_CONTEXTS=157
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def products():
    folder=ROOT/'tests/fixtures/smoke/rnbo-mixing-shaping';catalog=json.loads((folder/'catalog.json').read_bytes());observations={};sources=[]
    for i in range(1,5):
        source=f'evidence/xiao-smoke-rnbo-mixing-shaping-part{i}.json';sources.append(source);data=json.loads((ROOT/source).read_bytes())
        if data.get('family')!='rnbo-mixing-shaping'or data.get('partition',{}).get('index')!=i or data.get('compile_failures')or data.get('admission_failures'):raise ValueError('Wrong maths/mixing partition')
        for j,c in enumerate(data['cases']):
            if c['id']in observations or c.get('nonfinite_outputs')!=0:raise ValueError('Repeated/nonfinite maths case')
            checked_short_smoke(dict(id='patcher:'+c['exact_name'],spelling=c['exact_name'],surface='patcher'),dict(source=source,selector=f'/cases/{j}'),data);observations[c['id']]=(c,source,j)
    if set(observations)!={s['id']for s in catalog['cases']}:raise ValueError('Incomplete 63-source maths ledger')
    restoration=json.loads((ROOT/'evidence/xiao-smoke-rnbo-mixing-shaping-player-restoration.json').read_bytes())
    if (restoration.get('test_result_sources')!=sources or restoration.get('test_result_sha256')!=hashlib.sha256(b''.join((ROOT/p).read_bytes()for p in sources)).hexdigest()or not all(restoration.get(k)is True for k in('audio_frames_advanced','package_identity_preserved','parameter_controls_restored'))or restoration.get('package_sha256_before')!=restoration.get('package_sha256_after')or not restoration.get('fault_counters')or any(restoration['fault_counters'].values())):raise ValueError('Maths restoration must bind all tests and original controls')
    rows=[]
    for s in catalog['cases']:
        c,source,j=observations[s['id']]
        rows.append(dict(case=s['id'],id='patcher:'+s['exact_name'],name=s['exact_name'],source='tests/fixtures/smoke/rnbo-mixing-shaping/'+s['patch'],source_sha256=s['patch_sha256'],source_form=s['source_form'],variant=s['variant'],observed_outlet=s['observed_outlet'],signal_input=s['signal_input'],status=c['status'],evidence=source,selector=f'/cases/{j}',median_us=c['median_us'],peak_us=c['peak_us'],callback_cpu_percent=c['median_us']*44100/2560000,setter_total_us=c['event_total_us'],setter_peak_us=c['event_peak_us'],cpu_review_reasons=c['cpu_review_reasons'],samples_checked=c['samples_checked'],numeric_mismatches=c['numeric_mismatches'],max_absolute_error=c['max_absolute_error'],absolute_tolerance=c['absolute_tolerance'],within_tolerance_differences=c['within_tolerance_differences'],zero_sign_differences=c['zero_sign_differences'],right_pilot_bit_exact=c['right_pilot_bit_exact'],optimisation='unassessed',cpu_time_saved_percent=None,full_qualification_claimed=False,aliases_inherit_status=False))
    names=sorted({r['name']for r in rows});summary=dict(source_scenarios=len(rows),exact_spellings=len(names),target_completed=len(rows),passed=sum(r['status']=='pass'for r in rows),outside_screen=sum(r['status']=='output_mismatch'for r in rows),output_words=sum(r['samples_checked']for r in rows),completed_control_actions=sum(observations[r['case']][0]['parameter_events_applied']for r in rows),numeric_mismatches=sum(r['numeric_mismatches']for r in rows),within_tolerance_differences=sum(r['within_tolerance_differences']for r in rows),zero_sign_differences=sum(r['zero_sign_differences']for r in rows),cpu_review=sum(bool(r['cpu_review_reasons'])for r in rows))
    objects=[dict(name=n,scenario_count=sum(r['name']==n for r in rows),status='board'if all(r['status']=='pass'for r in rows if r['name']==n)else'partial',optimisation='unassessed',cpu_time_saved_percent=None,aliases_inherit_status=False)for n in names]
    paths=sources+['tests/fixtures/smoke/rnbo-mixing-shaping/catalog.json','tests/fixtures/smoke/rnbo-mixing-shaping/reference.py','evidence/rnbo-mixing-shaping-native.json','evidence/rnbo-mixing-shaping-builds.json','evidence/rnbo-mixing-shaping-initial-fixtures.json','evidence/xiao-smoke-rnbo-mixing-shaping-player-restoration.json'];inputs={p:dict(bytes=len((ROOT/p).read_bytes()),sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest())for p in paths}
    report=dict(format='rnbo-mixing-shaping-status-v1',scope='All 63 event/signal sources across 22 exact spellings. Modes/outlets and constructor/inlet forms stay distinct; no aliases, auxiliary-object or complete-domain inheritance.',sample_rate=44100,block_frames=256,summary=summary,cpu_review_queue_before=BASELINE_CPU_CONTEXTS,cpu_review_queue_after=BASELINE_CPU_CONTEXTS+summary['cpu_review'],objects=objects,cases=rows,inputs=inputs)
    lines=['# RNBO maths, interpolation and mixing checks','',f"The batch covers **{summary['source_scenarios']} scenarios across {summary['exact_spellings']} exact spellings**. **{summary['passed']} pass** their fixed output screens and **{summary['outside_screen']} retain outside-screen results**, across **{summary['output_words']:,} output words and {summary['completed_control_actions']:,} control actions**. All raw right captures match and no nonfinite output occurs. There are {summary['within_tolerance_differences']:,} within-limit differences and {summary['zero_sign_differences']:,} observational left zero-sign differences. **{summary['cpu_review']} new callback contexts** enter review, bringing the queue to **{report['cpu_review_queue_after']}**.",'',
        'One arm action precedes 21 ordered unit-phase drives, with repeats, same-callback updates and quiet holds. Each source runs four manual warm and sixteen timed full 256-frame callbacks at 44,100 Hz, with zero automatic warm callbacks. Signal forms use `clip(binary32(drive + varying left input),0,1)`, so their inputs vary inside blocks. The independent raw right pilot includes signed zero, subnormals and finite extrema. Actual and normalised parameter values are read back by resolved parameter ID.','',
        'References use independent Lagrange, Hermite, centered quintic B-spline, ideal trigonometric/logarithmic and piecewise shaping equations. Asymmetric control points distinguish interpolation modes. Limits were fixed before compilation: exact dyadic forms 0, normal maths 2e-6, t60time 1e-4 samples, cosine interpolation ideal-screen 1e-3. Ordinary fade cosines retain 2e-6. These screens are not universal accuracy guarantees. Constructor and inlet forms keep the same intended control points and expected streams.','',
        '| Exact spelling | Scenario | Outcome | Median / peak µs | Callback CPU | Setter total / peak µs |','| --- | --- | --- | ---: | ---: | ---: |']
    for c in rows:
        label='Pass'if c['status']=='pass'else'Outside screen'
        lines.append(f"| [`{c['name']}`](../{c['source']}) | {c['case']} | {label} | {c['median_us']:g} / {c['peak_us']} | {c['callback_cpu_percent']:.2f}% | {c['setter_total_us']} / {c['setter_peak_us']} |")
    lines+=['','## Compatibility and fixture findings','',
        'The **six-point generic `interp` and `interp~` constructor forms** retain their original intended six control points. The installed primary constructor code assigns the fifth/sixth arguments to earlier point attributes and omits some intended later-point assignments. The authored inlet-driven controls set all six point inputs explicitly and remain separate. Native and hardware results are recorded independently; no captured output replaces the mathematical oracle and no tolerance is relaxed.','']
    for c in rows:
        if c['status']=='output_mismatch':lines.append(f"- `{c['case']}`: {c['numeric_mismatches']:,} outside-screen words, maximum error {c['max_absolute_error']:.17g}, original limit {c['absolute_tolerance']:.9g}.")
    lines+=['',
        'The original native preflight also found eleven all/mostly-zero pan~/xfade~ amplitude results. Those graphs used number messages at amplitude ports documented as signal-only. The corrected fixtures supply explicit `sig~` amplitudes. **Only those eleven graph inputs change; all 63 expected streams, all limits and the other 52 compiled modules stay unchanged.** Original graphs, catalogs, reference/generator and native observations are archived. These initial differences are fixture mistakes, not eleven object failures. No original hardware attempt was made with those graphs.','',
        '## Performance and remaining scope','',
        'Complete callback time includes the compiled maths context and pilot. Signal interpolation/fades execute inside the callback; event maths and observation run in setter/routing work, timed separately across 22 actions including arming. Setter/callback numbers are not isolated opcode costs, total chip CPU or measured optimisation gains. Threshold-crossing contexts remain in the CPU review queue; optimisation is unassessed.','']
    for c in rows:
        if c['cpu_review_reasons']:lines.append(f"- `{c['case']}`: median {c['median_us']:g}µs, peak {c['peak_us']}µs, callback CPU {c['callback_cpu_percent']:.2f}%; {'; '.join(c['cpu_review_reasons'])}.")
    lines+=['',
        'All 63 images finalise and pass allocation/memory gates. The normal player, saved Main and live controls are restored; frames advance and runtime faults remain zero. No new listening/audio-capture or loaded-player deadline claim is made. Other domains, singularities/nonfinite values, inlet dynamics, constructor/options combinations, other RNBO/Gen forms and complete sample-by-sample qualification remain open. The full goal stays active.','',
        'Evidence: [machine-readable report](../evidence/rnbo-mixing-shaping-status.json), [native](../evidence/rnbo-mixing-shaping-native.json), [build ledger](../evidence/rnbo-mixing-shaping-builds.json), [initial fixture findings](../evidence/rnbo-mixing-shaping-initial-fixtures.json), [player restoration](../evidence/xiao-smoke-rnbo-mixing-shaping-player-restoration.json).','']
    return{'evidence/rnbo-mixing-shaping-status.json':encoded(report),'docs/rnbo-mixing-shaping.md':'\n'.join(lines).encode()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for path,b in products().items():
        out=ROOT/path
        if a.check:
            if not out.is_file()or out.read_bytes()!=b:raise SystemExit('Stale maths/mixing report: '+path)
        else:out.write_bytes(b)
    print('Maths/mixing report checked'if a.check else'Maths/mixing report written')
if __name__=='__main__':main()
