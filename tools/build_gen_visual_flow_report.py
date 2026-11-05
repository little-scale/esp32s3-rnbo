#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Visual-flow source ledger with output, compile, memory and CPU scopes separate."""
import argparse,hashlib,html,json
from pathlib import Path
from build_object_status import checked_short_smoke,checked_visual_flow_rejection
ROOT=Path(__file__).resolve().parents[1]
BASELINE_CPU_CONTEXTS=162
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def record():return dict(id='patcher:gen~',spelling='gen~',surface='patcher',working_state='partial',board_evidence=True)
def products():
 folder=ROOT/'tests/fixtures/smoke/gen-visual-flow';catalog=json.loads((folder/'catalog.json').read_bytes());observations={};sources=[]
 for i in(1,2,3):
  source=f'evidence/xiao-smoke-gen-visual-flow-part{i}.json';sources.append(source);data=json.loads((ROOT/source).read_bytes())
  if data.get('family')!='gen-visual-flow'or data.get('partition',{}).get('index')!=i or data.get('admission_failures'):raise ValueError('Wrong visual-flow target ledger')
  for key in('cases','compile_failures'):
   for j,c in enumerate(data[key]):
    if c['id']in observations:raise ValueError('Repeated visual-flow source')
    item=dict(source=source,selector=f'/{key}/{j}');(checked_short_smoke if key=='cases'else checked_visual_flow_rejection)(record(),item,data);observations[c['id']]=(c,key,source,j)
 if set(observations)!={s['id']for s in catalog['cases']}:raise ValueError('Incomplete42-source visual-flow ledger')
 restoration=json.loads((ROOT/'evidence/xiao-smoke-gen-visual-flow-player-restoration.json').read_bytes())
 if(restoration.get('test_result_sources')!=sources or restoration.get('test_result_sha256')!=hashlib.sha256(b''.join((ROOT/p).read_bytes()for p in sources)).hexdigest()or not all(restoration.get(k)is True for k in('audio_frames_advanced','package_identity_preserved','parameter_controls_restored'))or restoration.get('package_sha256_before')!=restoration.get('package_sha256_after')or not restoration.get('fault_counters')or any(restoration['fault_counters'].values())):raise ValueError('Visual-flow restoration must bind all target results and original controls')
 rows=[]
 for s in catalog['cases']:
  c,key,source,j=observations[s['id']];executed=key=='cases'
  rows.append(dict(id='genvisual:'+s['visual_operator'],name=s['visual_operator'],case=s['id'],variant=s['variant'],observed_outlet=s['observed_outlet'],operator_outputs=s['operator_outputs'],source='tests/fixtures/smoke/gen-visual-flow/'+s['patch'],source_sha256=s['patch_sha256'],source_form=s['source_form'],evidence=source,selector=f'/{key}/{j}',status=c['status'],hardware_executed=executed,optimisation='unassessed',cpu_time_saved_percent=None,median_us=c.get('median_us'),peak_us=c.get('peak_us'),callback_cpu_percent=c['median_us']*44100/2560000 if executed else None,cpu_review_reasons=c.get('cpu_review_reasons',[]),absolute_tolerance=c.get('absolute_tolerance'),max_absolute_error=c.get('max_absolute_error'),numeric_mismatches=c.get('numeric_mismatches'),within_tolerance_differences=c.get('within_tolerance_differences'),zero_sign_differences=c.get('zero_sign_differences'),samples_checked=c.get('samples_checked',0),right_pilot_bit_exact=c.get('right_pilot_bit_exact'),arena_capacity=c.get('arena_capacity',4096)if executed else None,arena_high_water=c.get('arena_high_water'),finalization_checked=executed,full_qualification_claimed=False,aliases_inherit_status=False))
 completed=[r for r in rows if r['hardware_executed']];names=sorted({r['name']for r in rows})
 summary=dict(source_scenarios=len(rows),exact_spellings=len(names),target_completed=len(completed),passed=sum(r['status']=='pass'for r in rows),outside_screen=sum(r['status']=='output_mismatch'for r in rows),target_compile_failures=sum(r['status']=='compile_failed'for r in rows),output_words=sum(r['samples_checked']for r in completed),numeric_mismatches=sum(r['numeric_mismatches']for r in completed),within_tolerance_differences=sum(r['within_tolerance_differences']for r in completed),zero_sign_differences=sum(r['zero_sign_differences']for r in completed),cpu_review=sum(bool(r['cpu_review_reasons'])for r in completed))
 objects=[dict(name=n,scenario_count=sum(r['name']==n for r in rows),status='unverified'if all(not r['hardware_executed']for r in rows if r['name']==n)else'board'if all(r['status']=='pass'for r in rows if r['name']==n)else'partial',optimisation='unassessed',cpu_time_saved_percent=None,aliases_inherit_status=False)for n in names]
 paths=sources+['tests/fixtures/smoke/gen-visual-flow/catalog.json','tests/fixtures/smoke/gen-visual-flow/reference.py','tests/fixtures/smoke/gen-visual-flow/qualified_lowerer.mjs','evidence/gen-visual-flow-native.json','evidence/gen-visual-flow-builds.json','evidence/gen-visual-flow-initial-attempts.json','evidence/xiao-smoke-gen-visual-flow-player-restoration.json'];inputs={p:dict(bytes=len((ROOT/p).read_bytes()),sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest())for p in paths}
 report=dict(format='rnbo-gen-visual-flow-status-v1',scope='All42 exact visual sources across33 spellings. Forty complete target outputs and two C++ failures; mtof has an explicit1MiB arena. Earlier visual/GenExpr/RNBO scopes remain separate.',sample_rate=44100,block_frames=256,summary=summary,cpu_review_queue_before=BASELINE_CPU_CONTEXTS,cpu_review_queue_after=BASELINE_CPU_CONTEXTS+summary['cpu_review'],inputs=inputs,objects=objects,cases=rows)
 lines=['# Visual Gen range, state and multiple-output checks','',f"The batch covers **{summary['source_scenarios']} scenarios across {summary['exact_spellings']} exact visual spellings**. **{summary['passed']} pass**, **{summary['outside_screen']} retains an outside-screen result**, and **{summary['target_compile_failures']} fail target C++ compilation**. The **{summary['target_completed']} completed XIAO runs check {summary['output_words']:,} output words**, with exact independently hashed right captures and no nonfinite outputs. There are {summary['within_tolerance_differences']:,} within-limit differences and {summary['zero_sign_differences']:,} observational left zero-sign differences. **{summary['cpu_review']} callbacks** join CPU review, now **{report['cpu_review_queue_after']}**.",'',
 'The production importer now lowers fully connected range/conversion and implicit stateful calls, and routes multiple outputs from a single call. Counter has three outputs; cartopol/poltocar have two. A selected output may feed a history. Missing/extra/stale ports, unknown options, disconnected operands and algebraic cycles still fail closed. Historical core/maths snapshots retain their identities: all122 earlier graph lowerings are unchanged. The new flow snapshot is separately immutable.','',
 'Each source is an original embedded dsp.gen graph, without authored/cached GenExpr. Four manual warm and sixteen timed256-frame callbacks run continuously at44,100Hz, with zero automatic warmup or host resets between blocks. Authored signal reset inputs remain active in their own cases. Stateful inputs change per sample, and late controls/data differ from the next block\'s first values, exposing incorrect block resets. This checks sample-by-sample state within the fixed256-frame module ABI, not a one-frame I²S deadline.','',
 '| Exact visual spelling | Scenario / outlet | Output screen | Callback CPU | Median / peak µs | Review |','| --- | --- | --- | ---: | ---: | --- |']
 for c in rows:
  name=html.escape(c['name']).replace('|','&#124;');label={'pass':'Pass','output_mismatch':'Outside screen','compile_failed':'C++ failure'}[c['status']];cpu='—'if c['median_us']is None else f"{c['callback_cpu_percent']:.2f}%";timing='—'if c['median_us']is None else f"{c['median_us']:g} / {c['peak_us']}";review='Queued'if c['cpu_review_reasons']else'—'
  lines.append(f"| [<code>{name}</code>](../{c['source']}) | {c['case']} / {c['observed_outlet']} | {label} | {cpu} | {timing} | {review} |")
 lines+=['','## Compatibility and memory findings','',
 '**Modulo:** both original `mod` and `%` graphs export and prepare but fail C++ compilation with an undefined `safemod` helper, on native and target compilers. Their original source/lowering and compiler-log identities remain visible. Neither has target execution, output, callback CPU or finalisation evidence.','',
 '**Fractional ftom:** the original fractional-note reference is retained. Its two quarter-tone test inputs differ by0.25 notes in native and XIAO execution. This is a scoped rounding-policy finding, not an ESP32-only failure. No rounded replacement oracle or wider tolerance is introduced.','']
 for c in rows:
  if c['status']=='output_mismatch':lines.append(f"- `{c['case']}`: {c['numeric_mismatches']:,} outside-screen words, maximum error {c['max_absolute_error']:.12g}, fixed limit {c['absolute_tolerance']:.9g}.")
 mtof=next(r for r in rows if r['name']=='mtof')
 lines+=['',f"**Mtof storage:** the unchanged source completes with an explicit **{mtof['arena_capacity']:,}-byte arena**, using **{mtof['arena_high_water']:,} bytes**. Generated initialization allocates a65,536-sample lookup buffer, although the selected processing branch computes the exponential directly. The earlier native4KiB arena attempt aborts before output; it is retained separately and was not run on target. The extra storage is a future optimisation candidate, not a measured saving. Other completed sources use4KiB arenas.",'',
 '**Declared policies:** counter retains the earlier increment-before-output screen, now separately tested at all three visual outlets with max7 and reset0. Other increments, reset/initial-value policies and limits remain unqualified. `fixnan` and `isnan` only receive finite inputs; no NaN-repair guarantee is claimed. Exact input words define the finite vectors; interval metadata describes the values before their binary32 conversion.','',
 'The initial port draft omitted explicit scale exponent and MIDI tuning inputs. Those three graphs were corrected against primary Gen references before native/device execution; all42 intended reference streams and limits are unchanged. The draft sources/lowerer are archived without qualification. Native exact-difference counters and per-source maximum errors are separate from target outside-limit counts.','',
 '## Performance and remaining scope','']
 for c in rows:
  if c['cpu_review_reasons']:lines.append(f"- `{c['case']}`: median {c['median_us']:g}µs, peak {c['peak_us']}µs, **{c['callback_cpu_percent']:.2f}%** of the256-frame period.")
 lines+=['',
 'These are complete compiled callbacks including the raw pilot, not isolated opcode costs, total chip CPU or optimisation gains. A callback above100% cannot meet this block period in the measured form; the offline smoke image does not run I²S/UI/Wi-Fi. All completed images finalise and pass runtime allocation/memory gates. Limits and precision are unchanged; optimisation is unassessed.','',
 'The normal player, original Main and controls are restored; frames advance and runtime faults remain zero. This separate visual report adds no RNBO inventory rows: the table stays at1056 scoped outcomes. Other visual operators/attributes, parameters, resources, resets, nested/file/codebox forms, wider domains and remaining RNBO/GenExpr qualification keep the full goal active.','',
 'Evidence: [machine-readable report](../evidence/gen-visual-flow-status.json), [native](../evidence/gen-visual-flow-native.json), [build ledger](../evidence/gen-visual-flow-builds.json), [initial attempts](../evidence/gen-visual-flow-initial-attempts.json), [restoration](../evidence/xiao-smoke-gen-visual-flow-player-restoration.json).','']
 text='\n'.join(lines)
 for a,b in [('all122','all 122'),('timed256','timed 256'),('at44,100Hz','at 44,100 Hz'),('fixed256','fixed 256'),('by0.25','by 0.25'),('a65,536','a 65,536'),('native4KiB','native 4 KiB'),('use4KiB','use 4 KiB'),('max7','max 7'),('reset0','reset 0'),('all42','all 42'),('the256','the 256'),('above100%','above 100%'),('at1056','at 1056')]:text=text.replace(a,b)
 return{'evidence/gen-visual-flow-status.json':encoded(report),'docs/gen-visual-flow.md':text.encode()}
def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 for path,raw in products().items():
  out=ROOT/path
  if a.check:
   if not out.is_file()or out.read_bytes()!=raw:raise SystemExit('Stale visual-flow report: '+path)
  else:out.write_bytes(raw)
 print('Visual-flow report checked'if a.check else'Visual-flow report written')
if __name__=='__main__':main()
