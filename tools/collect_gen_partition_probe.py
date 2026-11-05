#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify direct variable-frame Gen evidence, separate from the module ABI."""
import argparse,collections,hashlib,importlib.util,json,math,statistics,struct
from pathlib import Path
from build_gen_partition_probe import ROOT,FIXTURE,CATALOG_SHA,catalog,load_reference,sha,encoded,require,files

def fields(line,kind):
 prefix='RNBO_SMOKE '+kind+' ';require(line.startswith(prefix),'Unexpected probe line');parts=[v.split('=',1)for v in line[len(prefix):].split()];require(all(len(v)==2 for v in parts)and len({v[0]for v in parts})==len(parts),'Malformed or repeated probe fields');return dict(parts)
def integer(d,k,ceiling=2**64-1):
 v=d.get(k,'');require(v.isascii()and v.isdigit(),'Missing unsigned field '+k);v=int(v);require(0<=v<=ceiling,'Out-of-range field '+k);return v
def fingerprint(s):return type(s)is str and len(s)==64 and all(c in'0123456789abcdef'for c in s)
def case_order():
 r=load_reference();return[(model,name,stimulus,repeat,partition)for model,name in r.PROGRAMS for stimulus in('dyadic','boundary-impulses')for repeat,partition in r.render_cases()]
def checked_case(d,expected,*,hardware):
 r=load_reference();model,name,stimulus,repeat,partition=expected;identity=f'{name}-{stimulus}-r{repeat}-p{partition}'
 require(d.get('id')==identity and integer(d,'model',3)==model and d.get('stimulus')==stimulus and integer(d,'repeat',2)==repeat and integer(d,'nominal',256)==partition,'Direct-probe case identity/order differs')
 require(integer(d,'samples')==8192 and integer(d,'partition_compared_words')==(8192 if repeat else 0),'Direct-probe comparison span differs')
 histogram=dict(sorted(collections.Counter(n for _,n in r.chunks(partition)).items()));text=','.join(f'{n}:{v}'for n,v in histogram.items());calls=sum(histogram.values())
 require(d.get('histogram')==text and integer(d,'calls')==calls and integer(d,'guard_checks')==calls and integer(d,'unchanged_input_words')==8192,'Call/guard/input histogram differs from independent schedule')
 require(integer(d,'resets')==4 and integer(d,'prepares')==2 and 0<integer(d,'context_bytes')<=65536,'Lifecycle/event/context counts differ')
 numeric,within,bits,zeros,partition_bits=(integer(d,k,8192)for k in('numeric_mismatches','within_tolerance_differences','bit_differences','zero_sign_differences','partition_bit_differences'))
 require(numeric+within+zeros==bits and partition_bits<=(8192 if repeat else 0),'Numeric/partition comparison counters differ')
 require(len(d.get('max_error_bits',''))==16,'Missing exact error representation');maximum=struct.unpack('<d',struct.pack('<Q',int(d['max_error_bits'],16)))[0];limit=2e-6 if model==1 else 0
 require(math.isfinite(maximum)and maximum>=0 and(maximum>limit if numeric else maximum<=limit)and(not within or limit>0),'Numeric error does not match frozen comparison policy')
 first=integer(d,'first_numeric_word',2**32-1)
 require((first==2**32-1 and not numeric)or(numeric and first<8192),'First numeric mismatch witness differs')
 cycles,peak=integer(d,'cycles'),integer(d,'max_call_cycles');require((0<peak<=cycles)if hardware else cycles==peak==0,'Timing fields differ from execution route')
 for k in('process_allocations','process_frees','event_allocations','event_frees'):integer(d,k,2**32-1)
 status='output_mismatch'if numeric or partition_bits else'pass';require(d.get('status')==status,'Outcome contradicts comparison counts')
 if hardware:require(fingerprint(d.get('capture_sha256')),'Missing target capture fingerprint')
 result={k:integer(d,k)for k in('calls','resets','prepares','context_bytes','numeric_mismatches','within_tolerance_differences','bit_differences','zero_sign_differences','partition_bit_differences','process_allocations','process_frees','event_allocations','event_frees','guard_checks','unchanged_input_words')}
 result.update(id=identity,model=model,program=name,stimulus=stimulus,repeat=repeat,nominal_partition=partition,samples_checked=8192,partition_compared_words=8192 if repeat else 0,call_size_histogram={str(n):v for n,v in histogram.items()},maximum_absolute_error=maximum,absolute_tolerance=limit,status=status,capture_sha256=d.get('capture_sha256'),first_numeric_word=None if first==2**32-1 else first)
 if numeric:
  expected_word=r.expected_words(model,stimulus)[first];require(int(d['first_expected'],16)==expected_word,'Mismatch expected word differs from oracle');actual=struct.unpack('<f',struct.pack('<I',int(d['first_actual'],16)))[0];require(math.isfinite(actual)and abs(actual-r.value(expected_word))>limit,'First observed mismatch is inside limit');result.update(first_actual_bits=d['first_actual'],first_expected_bits=d['first_expected'])
 if hardware:result.update(process_elapsed_cycles=cycles,maximum_call_cycles=peak,process_elapsed_us=cycles/240,maximum_call_us=peak/240,normalized_CPU_percent=100*cycles/(4096*240e6/44100),CPU_time_saved_percent=None)
 return result

def native_records(build,plan_sha):
 r=load_reference();directory=build/'native';report=json.loads((directory/'report.json').read_text());require(report.get('plan_sha256')==plan_sha and report.get('CPU_measured')is False and report.get('heap_allocations_observed')is False and report.get('hardware')is False,'Native report scope differs');require(sha(directory/'compile.log')==report['compile_log_sha256']and sha(directory/'run.log')==report['run_log_sha256']and files(directory/'captures')==report['captures_sha256'],'Native capture/log hashes differ')
 lines=[l for l in (directory/'run.log').read_text().splitlines()if l.startswith('RNBO_SMOKE CASE ')];require(len(lines)==78,'Native cohort is incomplete');result=[];baselines={}
 for line,expected in zip(lines,case_order()):
  row=checked_case(fields(line,'CASE'),expected,hardware=False);raw=(directory/'captures'/(row['id']+'.u32')).read_bytes();require(len(raw)==32768,'Native capture size differs');actual=struct.unpack('<8192I',raw);truth=r.expected_words(row['model'],row['stimulus']);errors=[abs(r.value(a)-r.value(b))for a,b in zip(actual,truth)];numeric=sum(e>row['absolute_tolerance']for e in errors);bits=sum(a!=b for a,b in zip(actual,truth));zeros=sum(a!=b and(a&0x7fffffff)==(b&0x7fffffff)==0 for a,b in zip(actual,truth));within=bits-numeric-zeros
  require(all(math.isfinite(r.value(a))for a in actual)and(numeric,bits,zeros,within,max(errors))==(row['numeric_mismatches'],row['bit_differences'],row['zero_sign_differences'],row['within_tolerance_differences'],row['maximum_absolute_error']),'Native full capture contradicts independent model or counters')
  key=(row['model'],row['stimulus'])
  if row['repeat']==0:baselines[key]=actual
  else:require(sum(a!=b for a,b in zip(actual,baselines[key]))==row['partition_bit_differences'],'Native partition counter differs from full capture')
  row['capture_sha256']=hashlib.sha256(raw).hexdigest();row['allocation_observation']='Not observed in host preflight; placeholder zero counters are not allocation measurements';result.append(row)
 return result,report

def collect(build,run):
 from run_hardware_test import artifacts
 c=catalog();r=load_reference();artifact=artifacts(build,'xiao');b=artifact['report'];require(b.get('family')=='gen-direct-partitions'and b.get('execution_route')=='direct-variable-producer'and b.get('module_abi')is False,'Expected direct variable-producer build, not a module ABI build')
 plan=json.loads((build/'probe-plan.json').read_text());plan_sha=hashlib.sha256(encoded(plan)).hexdigest();require(plan==b['plan']and plan_sha==b['plan_sha256']and plan.get('catalog_sha256')==CATALOG_SHA and plan.get('catalog')==c and plan.get('reference_source_sha256')==sha(FIXTURE/'reference.py'),'Frozen direct-probe plan differs')
 for row in plan['program_stimuli']:
  require(row['input_words_sha256']==hashlib.sha256(struct.pack('<8192I',*r.input_words(row['stimulus']))).hexdigest()and row['expected_stream_sha256']==hashlib.sha256(struct.pack('<8192I',*r.expected_words(row['model'],row['stimulus']))).hexdigest()and row['reset_witnesses']==r.reset_witnesses(row['model'],row['stimulus']),'Direct model/cache/witness differs')
 require(files(build/'probe-config')==b['configuration_files_sha256'],'Compiled probe configuration differs')
 for path,h in b['source_files_sha256'].items():require(sha(ROOT/path)==h,'Probe source differs after compilation: '+path)
 h=json.loads((run/'hardware-smoke.json').read_text());serial=(run/'test-serial.log').read_text();require(h.get('result')=='completed'and h.get('error')is None and h.get('test_build_report_sha256')==sha(build/'build-report.json')and h.get('test_elf_sha256')==artifact['elf_sha256']and h.get('serial_log_sha256')==sha(run/'test-serial.log'),'Incomplete or different hardware run')
 lines=serial.splitlines();starts=[l for l in lines if l.startswith('RNBO_SMOKE START ')];done=[l for l in lines if l.startswith('RNBO_SMOKE DONE ')];require(len(starts)==len(done)==1 and h.get('done_line')==done[0],'Missing unique start/completion');start=fields(starts[0],'START');completion=fields(done[0],'DONE')
 for d in(start,completion):require(d.get('firmware_elf_sha256')==artifact['elf_sha256']and d.get('plan_sha256')==plan_sha and integer(d,'cases')==78 and d.get('route')=='direct-variable-producer'and d.get('module_abi')=='0','Hardware identity/route differs')
 require(integer(start,'cpu_hz')==240000000 and start.get('allocation_monitor')=='task-heap-hooks','Target cycle clock/allocation observer differs');overhead=integer(start,'clock_empty_median_cycles',240000000)
 caches=[fields(l,'CACHE')for l in lines if l.startswith('RNBO_SMOKE CACHE ')];require(len(caches)==6,'Hardware cache receipts are incomplete')
 for cache,row in zip(caches,plan['program_stimuli']):require(integer(cache,'model',3)==row['model']and cache.get('stimulus')==row['stimulus']and cache.get('input_sha256')==row['input_words_sha256']and cache.get('expected_sha256')==row['expected_stream_sha256'],'Hardware input/reference cache digest differs')
 raw_cases=[l for l in lines if l.startswith('RNBO_SMOKE CASE ')];require(raw_cases==h.get('case_lines')and len(raw_cases)==78,'Hardware CASE ledger differs')
 native,native_report=native_records(build,plan_sha);native_byid={v['id']:v for v in native};rows=[];baselines={}
 for line,expected in zip(raw_cases,case_order()):
  row=checked_case(fields(line,'CASE'),expected,hardware=True);key=(row['model'],row['stimulus']);peer=native_byid[row['id']];row['native_capture_sha256']=peer['capture_sha256'];row['native_target_capture_identical']=row['capture_sha256']==peer['capture_sha256']
  if row['repeat']==0:baselines[key]=row['capture_sha256']
  else:require((row['capture_sha256']==baselines[key])==(row['partition_bit_differences']==0),'Target partition bits and capture hash contradict each other')
  rows.append(row)
 passed=sum(v['status']=='pass'for v in rows);require(integer(completion,'passed')==passed and integer(completion,'mismatched')==78-passed and integer(completion,'constructions')==integer(completion,'destructions')==78,'Hardware completion totals differ')
 for key in('process_allocations','process_frees'):require(integer(completion,key)==sum(v[key]for v in rows),'Completion allocator totals differ')
 groups=[];cpu_review=[]
 for model,name in r.PROGRAMS:
  for stimulus in c['stimuli']:
   for partition in r.PARTITIONS:
    cases=[v for v in rows if(v['model'],v['stimulus'],v['nominal_partition'])==(model,stimulus,partition)];expected_count=3 if partition==1 else 2;require(len(cases)==expected_count,'Partition repetitions differ');cpu=statistics.median(v['normalized_CPU_percent']for v in cases);item=dict(id=f'{name}-{stimulus}-p{partition}',program=name,stimulus=stimulus,nominal_partition=partition,render_count=expected_count,frames_per_render=4096,median_normalized_CPU_percent=cpu,minimum_normalized_CPU_percent=min(v['normalized_CPU_percent']for v in cases),maximum_normalized_CPU_percent=max(v['normalized_CPU_percent']for v in cases),maximum_call_us=max(v['maximum_call_us']for v in cases),CPU_time_saved_percent=None,review_cpu_budget=cpu>10)
    groups.append(item)
    if cpu>10:cpu_review.append(dict(id=item['id'],median_normalized_CPU_percent=cpu,reason='direct-producer-aggregate-render-budget',status='pending-future-optimisation-review',scope='Two4096-frame elapsed-process-cycle renders, or three for nominal1. Expected small-call dispatch overhead is included; no isolated Gen opcode or optimisation gain.'))
 native_public=dict(format='rnbo-gen-direct-partition-native-results-v1',scope='Same direct variable-frame producer/harness and all78 full host captures checked against independent references and one-frame baselines. No host CPU or heap-allocation observation.',plan_sha256=plan_sha,compile_log_sha256=native_report['compile_log_sha256'],run_log_sha256=native_report['run_log_sha256'],cases=native)
 target=dict(format='rnbo-gen-direct-partition-hardware-results-v1',board='xiao',device_label='xiao-test-device-01',execution_route='direct-variable-producer',module_abi_variable_blocks_qualified=False,player_abi_changed=False,visual_Gen_qualified=False,all_Gen_operators_qualified=False,scope=c['scope'],catalog_sha256=CATALOG_SHA,reference_source_sha256=sha(FIXTURE/'reference.py'),plan_sha256=plan_sha,build_report_sha256=sha(build/'build-report.json'),hardware_report_sha256=sha(run/'hardware-smoke.json'),firmware_elf_sha256=artifact['elf_sha256'],serial_log_sha256=sha(run/'test-serial.log'),collector_source_sha256=sha(Path(__file__)),programs=[dict(p,generated_source_sha256=plan['exports'][p['id']]['generator']['generated_sha256'],runtime_file_map_sha256=hashlib.sha256(encoded({k:v for k,v in plan['exports'][p['id']]['files_sha256'].items()if k.startswith('common/')})).hexdigest())for p in c['programs']],program_stimuli=plan['program_stimuli'],clock=dict(cpu_hz=240000000,empty_bracket_median_cycles=overhead,overhead_subtracted=False,scope='Elapsed core-cycle brackets around process only, including counter-call overhead and possible interruption/preemption; input/oracle/guard/capture/control work excluded. Empty read-pair calibration is in the main translation unit and does not remove cross-unit wrapper overhead. Direct static producer, not loaded player performance.'),cases=rows,partition_performance=groups,cpu_review_backlog=cpu_review,cpu_review_policy='Budget only: median aggregate process-cycle CPU exceeds10%; two4096-frame renders per nominal partition, three for1. Mixed-size maxima do not qualify isolated spikes; no per-call median/optimisation gain.',memory=dict(process_allocations=sum(v['process_allocations']for v in rows),process_frees=sum(v['process_frees']for v in rows),event_allocations=sum(v['event_allocations']for v in rows),event_frees=sum(v['event_frees']for v in rows),psram_before=integer(completion,'psram_before'),psram_after=integer(completion,'psram_after'),internal_before=integer(completion,'internal_before'),internal_after=integer(completion,'internal_after'),allocator='Original RNBO runtime heap allocator; no module arena/high-water claim',follow_up_required=integer(completion,'internal_after')!=integer(completion,'internal_before')or integer(completion,'psram_after')!=integer(completion,'psram_before'),follow_up=f"Internal free-memory delta={integer(completion,'internal_after')-integer(completion,'internal_before')} bytes across78 constructions/destructions; lifecycle/first-use retention not isolated. Process/reset/prepare observations exclude constructor/destructor allocations; do not claim unchanged total heaps."),summary=dict(executed=78,passed=passed,output_mismatches=78-passed,numeric_output_words_checked=sum(v['samples_checked']for v in rows),partition_compared_words=sum(v['partition_compared_words']for v in rows),outside_declared_tolerance=sum(v['numeric_mismatches']for v in rows),within_declared_tolerance=sum(v['within_tolerance_differences']for v in rows),zero_sign_differences=sum(v['zero_sign_differences']for v in rows),partition_bit_differences=sum(v['partition_bit_differences']for v in rows),native_target_identical_captures=sum(v['native_target_capture_identical']for v in rows),constructed_instances=78,destroyed_instances=78,reset_actions=sum(v['resets']for v in rows),force_prepare_actions=sum(v['prepares']for v in rows),observable_reset_actions=13*sum(sum(w['observable_at_limit']for w in p['reset_witnesses'])for p in plan['program_stimuli']),cpu_review_contexts=len(cpu_review)))
 return target,native_public

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-dir',type=Path,required=True);p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--native-out',type=Path,required=True);a=p.parse_args();target,native=collect(a.build_dir.resolve(),a.run_dir.resolve());a.out.write_bytes(encoded(target));a.native_out.write_bytes(encoded(native));print(json.dumps(target['summary'],sort_keys=True))
if __name__=='__main__':main()
