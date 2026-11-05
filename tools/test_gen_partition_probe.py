# SPDX-License-Identifier: MIT
"""Partition/event semantics and evidence counters must not imply a player ABI."""
import collections,copy,hashlib,json,math,struct,unittest
from pathlib import Path
import build_gen_partition_probe as builder
import collect_gen_partition_probe as collector
ROOT=builder.ROOT
r=builder.load_reference()
class GenPartitionProbeTests(unittest.TestCase):
 def target(self):return json.loads((ROOT/'evidence/xiao-gen-direct-partitions.json').read_text())
 def raw_case(self,row):
  d={k:str(row[k])for k in('id','model','stimulus','repeat','status','calls','resets','prepares','context_bytes','numeric_mismatches','within_tolerance_differences','bit_differences','zero_sign_differences','process_allocations','process_frees','event_allocations','event_frees','guard_checks','unchanged_input_words','capture_sha256')}
  d.update(nominal=str(row['nominal_partition']),samples='8192',partition_compared_words=str(row['partition_compared_words']),partition_bit_differences=str(row['partition_bit_differences']),cycles=str(row['process_elapsed_cycles']),max_call_cycles=str(row['maximum_call_cycles']),max_error_bits=struct.pack('<d',row['maximum_absolute_error'])[::-1].hex(),first_numeric_word=str(2**32-1 if row['first_numeric_word']is None else row['first_numeric_word']),first_actual='00000000',first_expected='00000000',histogram=','.join(f'{k}:{v}'for k,v in sorted(row['call_size_histogram'].items(),key=lambda v:int(v[0]))));return d
 def test_chunks_never_cross_control_boundaries_or_lose_frames(self):
  events=set(r.RESETS+r.PREPARES)
  for p in r.PARTITIONS:
   chunks=r.chunks(p);self.assertEqual(sum(n for _,n in chunks),4096);self.assertTrue(events<={at for at,_ in chunks});self.assertTrue(all(0<n<=256 and not any(at<e<at+n for e in events)for at,n in chunks));self.assertEqual(chunks[-1][0]+chunks[-1][1],4096)
  self.assertEqual(len(r.chunks(1)),4096);self.assertEqual(collections.Counter(n for _,n in r.chunks(256)),{256:13,1:1,20:1,71:1,182:1,239:1,255:1})
  with self.assertRaises(ValueError):r.chunks(True)
 def test_three_history_seeds_and_prepare_continuity_are_observable(self):
  words=r.expected_words(3,'dyadic');self.assertEqual(words[:6],tuple(r.word(v)for v in(1,2,2,3,3,1)))
  self.assertEqual(words[2*256:2*258],tuple(r.word(v)for v in(2,3,3,1)))
  for event in r.RESETS:self.assertEqual(words[2*event:2*event+2],(r.word(1),r.word(2)))
  # A false reset on every callback changes an odd-period history stream.
  wrong=[];inputs=r.input_words('dyadic')
  for at,count in r.chunks(256):
   for n in range(at,at+count):wrong.extend(r.word(v)for v in r.truth_at(3,n,at,inputs))
  self.assertNotEqual(tuple(wrong),words)
 def test_independent_convolution_agrees_with_scalar_recurrence_in_declared_domain(self):
  for stimulus in('dyadic','boundary-impulses'):
   inputs=r.input_words(stimulus);expected=r.expected_words(1,stimulus);state=0
   for n in range(4096):
    if n in r.RESETS:state=0
    y=r.value(inputs[2*n])+.5*state;self.assertAlmostEqual(r.value(expected[2*n]),y,delta=1e-7);self.assertAlmostEqual(r.value(expected[2*n+1]),state,delta=1e-7);state=y
 def test_impulses_surround_each_host_boundary_and_reset_witnesses_are_honest(self):
  v=r.input_words('boundary-impulses')
  for boundary in range(256,4096,256):
   self.assertEqual([r.value(v[2*n])for n in(boundary-1,boundary,boundary+1)],[-.5,.25,.125])
  witnesses=[r.reset_witnesses(m,s)for m,_ in r.PROGRAMS for s in('dyadic','boundary-impulses')];self.assertEqual(sum(sum(v['observable_at_limit']for v in w)for w in witnesses),18);self.assertTrue(all(sum(v['observable_at_limit']for v in w)>=2 for w in witnesses));self.assertTrue(any(not v['observable_at_limit']for w in witnesses for v in w))
 def test_catalog_binds_exact_graphs_and_variable_direct_route(self):
  c=builder.catalog();self.assertFalse(c['module_abi']);self.assertFalse(c['player_abi_changed']);self.assertEqual(c['producer_fixedblocksize'],0);self.assertEqual(c['instances_per_program_stimulus'],13);self.assertEqual(hashlib.sha256((builder.FIXTURE/'catalog.json').read_bytes()).hexdigest(),builder.CATALOG_SHA)
  for p in c['programs']:
   self.assertEqual(hashlib.sha256((ROOT/p['patch']).read_bytes()).hexdigest(),p['patch_sha256']);self.assertEqual(hashlib.sha256((ROOT/p['genexpr']).read_bytes()).hexdigest(),p['genexpr_sha256'])
 def test_all78_published_records_validate_against_schedule(self):
  rows=self.target()['cases'];self.assertEqual(len(rows),78)
  for row,expected in zip(rows,collector.case_order()):
   actual=collector.checked_case(self.raw_case(row),expected,hardware=True);self.assertEqual(actual['normalized_CPU_percent'],row['normalized_CPU_percent']);self.assertEqual(row['capture_sha256'],row['native_capture_sha256']);self.assertEqual(actual['partition_bit_differences'],0)
 def test_invalid_spans_guards_clock_and_outcome_cannot_be_promoted(self):
  row=self.target()['cases'][0];raw=self.raw_case(row);expected=collector.case_order()[0]
  for key,value in(('samples','8191'),('calls','4095'),('guard_checks','0'),('unchanged_input_words','8191'),('resets','3'),('prepares','0'),('cycles','0'),('nominal','256'),('histogram','256:16'),('partition_compared_words','8192'),('status','output_mismatch'),('capture_sha256','none'),('context_bytes','65537')):
   with self.subTest(key=key):
    bad=dict(raw,**{key:value})
    with self.assertRaises(ValueError):collector.checked_case(bad,expected,hardware=True)
 def test_published_summary_preserves_rounding_heap_delta_and_scope(self):
  d=self.target();s=d['summary'];self.assertEqual(s['passed'],78);self.assertEqual(s['numeric_output_words_checked'],638976);self.assertEqual(s['partition_compared_words'],589824);self.assertEqual(s['partition_bit_differences'],0);self.assertEqual(s['within_declared_tolerance'],62036);self.assertEqual(s['native_target_identical_captures'],78);self.assertEqual(s['reset_actions'],312);self.assertEqual(s['force_prepare_actions'],156);self.assertEqual(s['observable_reset_actions'],234)
  self.assertFalse(d['module_abi_variable_blocks_qualified']);self.assertFalse(d['player_abi_changed']);self.assertFalse(d['visual_Gen_qualified']);self.assertFalse(d['all_Gen_operators_qualified'])
  self.assertEqual(d['memory']['psram_before'],d['memory']['psram_after']);self.assertEqual(d['memory']['internal_after']-d['memory']['internal_before'],-288);self.assertTrue(d['memory']['follow_up_required']);self.assertEqual(d['memory']['process_allocations'],0);self.assertEqual(d['memory']['event_allocations'],0)
 def test_cpu_is_elapsed_direct_route_cost_not_optimisation_gain(self):
  d=self.target();self.assertEqual(len(d['partition_performance']),36);self.assertEqual(len(d['cpu_review_backlog']),8);self.assertFalse(d['clock']['overhead_subtracted'])
  for row in d['cases']:self.assertIsNone(row['CPU_time_saved_percent']);self.assertAlmostEqual(row['normalized_CPU_percent'],row['process_elapsed_cycles']*44100/(4096*240000000)*100)
  self.assertTrue(all(v['median_normalized_CPU_percent']>10 for v in d['cpu_review_backlog']))
if __name__=='__main__':unittest.main()
