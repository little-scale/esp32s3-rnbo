#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Publish exact visual spelling outcomes without inflating the RNBO table."""
import argparse,hashlib,html,json
from pathlib import Path
from build_object_status import checked_short_smoke
ROOT=Path(__file__).resolve().parents[1]
BASELINE_CPU_CONTEXTS=151  # Published queue immediately before this fixed batch.
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def products():
 folder=ROOT/'tests/fixtures/smoke/gen-visual-math';catalog=json.loads((folder/'catalog.json').read_bytes());cases={};inputs={}
 paths=['tests/fixtures/smoke/gen-visual-math/catalog.json','tests/fixtures/smoke/gen-visual-math/reference.py','tests/fixtures/smoke/gen-visual-math/qualified_lowerer.mjs']
 for part in range(1,5):
  source=f'evidence/xiao-smoke-gen-visual-math-part{part}.json';paths.append(source);data=json.loads((ROOT/source).read_bytes())
  if data.get('family')!='gen-visual-math' or data.get('partition',{}).get('index')!=part:raise ValueError('Wrong visual maths evidence partition')
  for index,case in enumerate(data['cases']):
   if case['id']in cases:raise ValueError('Repeated visual case')
   item=dict(source=source,selector=f'/cases/{index}');checked_short_smoke(dict(id='patcher:gen~',surface='patcher',spelling='gen~'),item,data)
   cases[case['id']]=(case,source,index)
 if set(cases)!={s['id']for s in catalog['cases']}:raise ValueError('Visual maths evidence ledger is incomplete')
 rows=[]
 for source in catalog['cases']:
  case,evidence,index=cases[source['id']];rows.append(dict(id='genvisual:'+source['visual_operator'],name=source['visual_operator'],case=source['id'],
   source='tests/fixtures/smoke/gen-visual-math/'+source['patch'],source_sha256=source['patch_sha256'],evidence=evidence,selector=f'/cases/{index}',
   status=case['status'],working_scope='Authored finite-domain mathematical output screen only',optimisation='unassessed',cpu_time_saved_percent=None,
   median_us=case['median_us'],peak_us=case['peak_us'],callback_cpu_percent=100*case['median_us']*44100/256000000,cpu_review_reasons=case['cpu_review_reasons'],
   absolute_tolerance=case['absolute_tolerance'],max_absolute_error=case['max_absolute_error'],numeric_mismatches=case['numeric_mismatches'],within_tolerance_differences=case['within_tolerance_differences'],zero_sign_differences=case['zero_sign_differences'],samples_checked=case['samples_checked'],right_pilot_bit_exact=case['right_pilot_bit_exact'],
   bit_identity_claimed=False,full_qualification_claimed=False,aliases_inherit_status=False))
 if len({r['name']for r in rows})!=len(rows):raise ValueError('Visual spellings are not distinct')
 for path in paths:
  raw=(ROOT/path).read_bytes();inputs[path]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 summary=dict(executed=len(rows),passed=sum(r['status']=='pass'for r in rows),outside_screen=sum(r['status']=='output_mismatch'for r in rows),samples_checked=sum(r['samples_checked']for r in rows),cpu_review=sum(bool(r['cpu_review_reasons'])for r in rows),within_tolerance_differences=sum(r['within_tolerance_differences']for r in rows),zero_sign_differences=sum(r['zero_sign_differences']for r in rows))
 report=dict(format='rnbo-visual-gen-operator-status-v1',scope='Exact one-operation visual source spellings in this batch; earlier visual-core graphs and GenExpr routes remain separate. No complete Gen claim or RNBO table expansion.',sample_rate=44100,block_frames=256,cpu_review_queue_before=BASELINE_CPU_CONTEXTS,cpu_review_queue_after=BASELINE_CPU_CONTEXTS+summary['cpu_review'],inputs=inputs,summary=summary,objects=rows)
 lines=['# Visual Gen operator checks','',f"This batch executes **{summary['executed']} exact visual spellings**: **{summary['passed']} pass** the declared mathematical screen and **{summary['outside_screen']} retain outside-screen differences**. It checks **{summary['samples_checked']:,} output words**; every raw right-lane capture matches. {summary['cpu_review']} complete callback contexts join the CPU queue, now{BASELINE_CPU_CONTEXTS+summary['cpu_review']}. These are scoped functionality checks, not complete operator/mode qualification.",'',
 'Each source is an original embedded `dsp.gen` graph. Aliases have separate sources and executions. The original source, lowering snapshot, finite input domains and mathematical limits are fixed before measurement. No optional DSP optimisation is applied. The production module interface stays at256 frames /44.1kHz.','',
 'The callback CPU column includes the complete compiled graph, SDK dispatch and right signal pilot. It is not an isolated opcode cost or a gain versus a matched baseline. Optimisation remains unassessed and no CPU saving is claimed. `Outside screen` describes the fixed mathematical comparison, not a failure to compile or run.','',
 '| Exact visual spelling | Output screen | Optimisation | CPU saved | Callback CPU | Review |','| --- | --- | --- | --- | ---: | --- |']
 for row in rows:
  name=html.escape(row['name']).replace('|','&#124;');label='Pass'if row['status']=='pass'else'Outside screen';review='Queued'if row['cpu_review_reasons']else'—'
  lines.append(f"| [<code>{name}</code>](../{row['source']}) | {label} | Not assessed | — | {row['callback_cpu_percent']:.2f}% | {review} |")
 lines+=['','## Numerical differences','',f"There are {summary['within_tolerance_differences']:,} within-limit differences and {summary['zero_sign_differences']:,} left signed-zero differences. All right-lane words, including zero signs, are independently hash-checked. Nonfinite outputs are zero. Limits were not widened to fit observations. Ordinary functions use2e-6 absolute error, power2e-5, radian-to-degree constants8e-6, and the named approximations a1e-3 ideal-function screen; exact arithmetic/logic/numeric cases use0.",'',
 '| Approximation | Outside-screen words | Maximum absolute error | Screen |','| --- | ---: | ---: | ---: |']
 for row in rows:
  if row['status']!='pass':lines.append(f"| `{row['name']}` | {row['numeric_mismatches']:,} | {row['max_absolute_error']:.12g} | {row['absolute_tolerance']:.9g} |")
 lines+=['','These approximation differences also appear in the native preflight. The native harness reports exact numeric differences separately; it does not count words beyond the target limits. No universal execution failure or ESP-specific defect is inferred. The signed-fraction convention is explicit; invalid domains, arbitrary cold operands, subnormals/NaNs and wider modes remain unqualified.','',
 '## CPU follow-up','', '| Visual operation | Median callback | Peak callback | Block budget |','| --- | ---: | ---: | ---: |']
 for row in rows:
  if row['cpu_review_reasons']:lines.append(f"| `{row['name']}` | {row['median_us']:g}µs | {row['peak_us']:g}µs | {row['callback_cpu_percent']:.2f}% |")
 lines+=['','These contexts cross the existing median/peak callback screen. Generated precision and math-library call choices are a future optimisation investigation; no cause or gain is established here. All101 images finalise and runtime allocation/memory checks pass. This offline firmware does not run I²S, UI or Wi-Fi, so these figures are not a loaded-player deadline guarantee.','',
 '## Evidence and scope','', '[Target1](../evidence/xiao-smoke-gen-visual-math-part1.json), [target2](../evidence/xiao-smoke-gen-visual-math-part2.json), [target3](../evidence/xiao-smoke-gen-visual-math-part3.json), [target4](../evidence/xiao-smoke-gen-visual-math-part4.json), [native preflight](../evidence/gen-visual-math-native.json), [build ledger](../evidence/gen-visual-math-builds.json), [machine-readable spelling report](../evidence/gen-visual-operator-status.json), and [player restoration](../evidence/xiao-smoke-gen-visual-math-player-restoration.json).','',
 'The [earlier core graphs](gen-visual-core.md) retain their original qualified lowerer snapshot. Historical receipts no longer depend on the current production helper. The normal player and original controls are restored after this batch, with advancing frames and zero runtime fault counters checked. The RNBO table still has936 scoped entries; this separate visual list does not add101 RNBO objects. The GenExpr212-entry route ledger also stays separate. Remaining visual operators, parameters/reset, resources, codeboxes, nested/file forms and wider domains keep the full goal active.','']
 text='\n'.join(lines)
 for a,b in [('now156','now 156'),('at256','at 256'),('/44.1','/ 44.1'),('use2e-6','use 2e-6'),('power2e-5','power 2e-5'),('constants8e-6','constants 8e-6'),('a1e-3','a 1e-3'),('use0','use 0'),('existing10%','existing 10%'),('All101','All 101'),('has936','has 936'),('add101','add 101'),('GenExpr212','GenExpr 212')]:text=text.replace(a,b)
 return {'evidence/gen-visual-operator-status.json':encoded(report),'docs/gen-visual-math.md':text.encode()}
def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 for path,raw in products().items():
  out=ROOT/path
  if a.check:
   if not out.is_file()or out.read_bytes()!=raw:raise SystemExit('Stale visual operator report: '+path)
  else:out.write_bytes(raw)
 print('Visual operator report checked'if a.check else'Visual operator report written')
if __name__=='__main__':main()
