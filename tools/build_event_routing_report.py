#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Complete routing source ledger: output checks, compile gaps and target fault."""
import argparse
import hashlib
import json
from pathlib import Path
from build_object_status import checked_short_smoke,checked_routing_rejection,checked_routing_target_fault
ROOT=Path(__file__).resolve().parents[1]
BASELINE_CPU_CONTEXTS=157
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def record_for(case):return dict(id='patcher:'+case['exact_name'],spelling=case['exact_name'],surface='patcher',working_state='partial',board_evidence=True,cpu_measurement_ids=[],optimisation_state='unassessed',optimisations=[])
def products():
    folder=ROOT/'tests/fixtures/smoke/rnbo-event-routing';catalog=json.loads((folder/'catalog.json').read_bytes());observations={};paths=[]
    sources=[f'evidence/xiao-smoke-rnbo-event-routing-part{i}.json'for i in range(1,5)]
    for source in sources:
        data=json.loads((ROOT/source).read_bytes());paths.append(source)
        if data.get('family')!='rnbo-event-routing':raise ValueError('Wrong routing result family')
        for key in('cases','compile_failures','admission_failures'):
            for j,c in enumerate(data.get(key,[])):
                if c['id']in observations:raise ValueError('Repeated routing source result')
                item=dict(source=source,selector=f'/{key}/{j}');record=record_for(c)
                (checked_short_smoke if key=='cases'else checked_routing_rejection)(record,item,data)
                if key=='cases'and c['nonfinite_outputs']!=0:raise ValueError('Routing report requires finite outputs')
                observations[c['id']]=(c,key,source,j)
    if set(observations)!={s['id']for s in catalog['cases']}:raise ValueError('Incomplete routing source ledger')
    probe_source='evidence/xiao-event-routing-rotation-fault.json';probe=json.loads((ROOT/probe_source).read_bytes())
    checked_routing_target_fault(record_for(dict(exact_name='list.rot')),dict(source=probe_source,selector='/'),probe)
    restoration=json.loads((ROOT/'evidence/xiao-smoke-rnbo-event-routing-player-restoration.json').read_bytes())
    if (restoration.get('test_result_sources')!=sources+[probe_source]or restoration.get('test_result_sha256')!=hashlib.sha256(b''.join((ROOT/p).read_bytes()for p in sources+[probe_source])).hexdigest()
        or not all(restoration.get(k)is True for k in('audio_frames_advanced','package_identity_preserved','parameter_controls_restored'))
        or restoration.get('package_sha256_before')!=restoration.get('package_sha256_after')or not restoration.get('fault_counters')or any(restoration['fault_counters'].values())):
        raise ValueError('Routing restoration does not bind all batches, fault probe and saved controls')
    rows=[]
    for s in catalog['cases']:
        c,key,source,j=observations[s['id']];status=c['status']if key=='cases'else'compile_failed'if key=='compile_failures'else'event_fault'
        rows.append(dict(case=s['id'],id='patcher:'+s['exact_name'],name=s['exact_name'],variant=s['variant'],source='tests/fixtures/smoke/rnbo-event-routing/'+s['patch'],source_sha256=s['patch_sha256'],
            source_form=s['source_form'],output_kind=s['output_kind'],observed_outlet=s['observed_outlet'],status=status,evidence=source,selector=f'/{key}/{j}',
            target_fault_evidence=probe_source if status=='event_fault'else None,optimisation='unassessed',cpu_time_saved_percent=None,
            median_us=c.get('median_us'),peak_us=c.get('peak_us'),callback_cpu_percent=c['median_us']*44100/2560000 if key=='cases'else None,
            setter_total_us=c.get('event_total_us'),setter_peak_us=c.get('event_peak_us'),cpu_review_reasons=c.get('cpu_review_reasons',[]),
            samples_checked=c.get('samples_checked',0),numeric_mismatches=c.get('numeric_mismatches'),right_pilot_bit_exact=c.get('right_pilot_bit_exact'),
            full_qualification_claimed=False,aliases_inherit_status=False))
    completed=[c for c,key,_,_ in observations.values()if key=='cases'];names=sorted({r['name']for r in rows})
    summary=dict(source_scenarios=len(rows),exact_spellings=len(names),target_completed=len(completed),target_output_passes=sum(c['status']=='pass'for c in completed),
        target_output_mismatches=sum(c['status']=='output_mismatch'for c in completed),target_event_faults=1,target_compile_failures=sum(c['status']=='compile_failed'for c in rows),
        target_attempted_sources=len(completed)+1,output_words=sum(c['samples_checked']for c in completed),completed_control_actions=sum(c['parameter_events_applied']for c in completed),
        numeric_mismatches=sum(c['numeric_mismatches']for c in completed),within_tolerance_differences=sum(c['within_tolerance_differences']for c in completed),
        zero_sign_differences=sum(c['zero_sign_differences']for c in completed),cpu_review=sum(bool(c['cpu_review_reasons'])for c in completed))
    objects=[dict(name=n,scenario_count=sum(r['name']==n for r in rows),status='board'if all(r['status']=='pass'for r in rows if r['name']==n)else'partial',
                  aliases_inherit_status=False,optimisation='unassessed',cpu_time_saved_percent=None)for n in names]
    paths+=['tests/fixtures/smoke/rnbo-event-routing/catalog.json','tests/fixtures/smoke/rnbo-event-routing/reference.py',
        'tests/fixtures/smoke/rnbo-event-routing/unobserved-no-match-v1/catalog.json','tests/fixtures/smoke/rnbo-event-routing/unobserved-no-match-v1/reference.py',
        'evidence/rnbo-event-routing-native.json','evidence/rnbo-event-routing-builds.json','evidence/rnbo-event-routing-initial-screens.json',
        'evidence/xiao-smoke-rnbo-event-routing-player-restoration.json',probe_source]
    inputs={p:dict(bytes=len((ROOT/p).read_bytes()),sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest())for p in paths}
    report=dict(format='rnbo-event-routing-status-v1',scope='All62 original armed scenarios,58 complete target output checks,one separately observed target event fault and three target C++ failures. No omitted source or inherited alias/surface status.',
        sample_rate=44100,block_frames=256,summary=summary,cpu_review_queue_before=BASELINE_CPU_CONTEXTS,cpu_review_queue_after=BASELINE_CPU_CONTEXTS+summary['cpu_review'],inputs=inputs,objects=objects,cases=rows)
    lines=['# RNBO numeric and list routing checks','',
        f"The full source ledger contains **{summary['source_scenarios']} scenarios across {summary['exact_spellings']} exact spellings**. **{summary['target_output_passes']} complete their XIAO output checks**, **one original positive-rotation case faults in a target event**, and **three literal-message forms fail target C++ compilation**. The completed cases check **{summary['output_words']:,} output words** and **{summary['completed_control_actions']:,} control actions**. Every completed right-channel capture matches; no nonfinite output or outside-limit word occurs. The CPU review queue reaches **{BASELINE_CPU_CONTEXTS+summary['cpu_review']}**, with {summary['cpu_review']} new callback flags.",'',
        'This is functionality coverage with explicit gaps, not 62 hardware passes or full mode qualification. Each alias has its own source. `pak` is checked through a non-left inlet as well as all inputs; `routepass` retains the selector while `route` removes it. The sources cover all gate outlets, switch inputs/closed state, split/select routes, swap outlet order, packing/unpacking, list rotations/slices/extraction/replacement/sorting/intersection and message-box controls.','',
        'One arm action opens an initially closed input gate, followed by 21 drive actions with repeats and ordered same-callback updates. The drive encodes an integer tag 0…3 and an independent 3-bit fractional payload. Lists are deliberately unsorted and include duplicates. Actual and normalised parameter readbacks are checked by ID. Four manual warm and sixteen timed 256-frame callbacks are all compared, with no automatic warm callbacks. All numeric limits are zero.','',
        'List output uses `length × 32768 + Σ(item[i] × 8ⁱ)`. For up to five items in 0…7 this is injective, distinguishes trailing zeros and list length, and is exact in binary32. Numeric and emitted-bang-count outputs are checked directly. A separately hashed raw right pilot includes signed zeros, subnormals and finite extrema. The five message controls pass native checks; only the two shorter controls compile for XIAO. Five-element lists are also checked through other target list transformations.','',
        '| Exact spelling | Scenario | Outcome | Median / peak µs | Callback CPU | Setter total / peak µs |',
        '| --- | --- | --- | ---: | ---: | ---: |']
    for c in rows:
        label={'pass':'Pass','output_mismatch':'Outside screen','compile_failed':'C++ failure','event_fault':'Target event fault'}[c['status']]
        timing=f"{c['median_us']:g} / {c['peak_us']}"if c['median_us']is not None else'—';cpu=f"{c['callback_cpu_percent']:.2f}%"if c['callback_cpu_percent']is not None else'—'
        setter=f"{c['setter_total_us']} / {c['setter_peak_us']}"if c['setter_total_us']is not None else'—'
        lines.append(f"| [`{c['name']}`](../{c['source']}) | {c['case']} | {label} | {timing} | {cpu} | {setter} |")
    lines+=['','## Compatibility gaps','',
        '- **`list.rot 1`:** the original source is tested alone on XIAO. Arming succeeds; the first drive event (0.125) returns `RNBO_S3_FAULT` (-4), while parameter readback succeeds. Native preflight records the same event stage/status. No output callback completes, so no numerical pass, raw-right result, normal callback CPU or finalisation/memory claim is made for this source. Its fault is separate from the passing negative rotation. The cause still needs investigation.','',
        '- **Three longer literal-message forms:** `[0 0 0]`, `[1 2 3 0]` and `[7 0 1 4 5]` reach a target compiler array-bounds error in the RNBO variadic list constructor. The original warnings are not disabled. They execute correctly in native preflight, which does not qualify target execution or prove the target diagnostic is harmless. Two shorter literal controls pass XIAO output checks.','',
        'The initially flagged `list.sect` and `list.sub` comparisons were **fixture observation mistakes**: the original graphs watched only the data outlet and assumed an empty list would arrive on no match. The documented intersection no-match bang and sub-list zero-count outlet are now observed explicitly to supply code 0. Only those two observation graphs change. **All 62 expected streams and all zero-error limits remain unchanged.** Original graphs/catalogs, native observations and three initial hardware partitions are archived; their two initial comparison differences are not object defects.','',
        '## Performance and remaining work','',
        'List/routing work runs in setters; their totals and peaks cover all 22 actions, including arming and observer work. The timed audio callback mainly renders the held code/scalar and raw pilot. These are whole compiled contexts, not isolated operation costs or matched optimisation gains. Optimisation remains unassessed; no saving percentage is claimed. The fault response timing is a separate single failed event and is not normal callback CPU.','',
        'All 58 completed images finalise and pass allocation/memory gates. The fault probe aborts at the recorded event check and makes no finalisation claim. The normal player, saved Main and controls are restored afterwards; USB audio-frame progress and zero runtime faults are checked. Other lengths/types/options, larger or negative list domains, within-block host offsets and remaining RNBO/Gen forms keep the full qualification goal active.','',
        'Evidence: [machine-readable report](../evidence/rnbo-event-routing-status.json), [native](../evidence/rnbo-event-routing-native.json), [build ledger](../evidence/rnbo-event-routing-builds.json), [target fault](../evidence/xiao-event-routing-rotation-fault.json), [initial observation screens](../evidence/rnbo-event-routing-initial-screens.json), [restoration](../evidence/xiao-smoke-rnbo-event-routing-player-restoration.json).','']
    return{'evidence/rnbo-event-routing-status.json':encoded(report),'docs/rnbo-event-routing.md':'\n'.join(lines).encode()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    for path,b in products().items():
        if path.startswith('docs/') and path.endswith('.md'):
            title, rest = b.decode().split('\n', 1)
            b = (title + '\n\n> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.\n\n' + rest.lstrip('\n')).encode()
        out=ROOT/path
        if a.check:
            if not out.is_file()or out.read_bytes()!=b:raise SystemExit('Stale routing report: '+path)
        else:out.write_bytes(b)
    print('Routing report checked'if a.check else'Routing report written')
if __name__=='__main__':main()
