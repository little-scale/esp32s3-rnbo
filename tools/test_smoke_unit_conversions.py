# SPDX-License-Identifier: MIT
"""Independent unit landmarks, source/tempo guards and raw-observer mutations."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import build_hardware_smoke as builder
import collect_hardware_smoke as collector
import build_object_status as publisher
import build_unit_conversion_report as report

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'tests/fixtures/smoke/rnbo-unit-conversions'
spec=importlib.util.spec_from_file_location('unit_reference',HERE/'reference.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class UnitConversionTests(unittest.TestCase):
    def test_independent_physical_unit_landmarks(self):
        for n,x,y in(('beatstohz',1,2),('beatstoms',1,500),('beatstosamps',1,22050),('beatstoticks',1,480),
                    ('hztobeats',2,1),('hztoms',2,500),('hztosamps',2,22050),('hztoticks',2,480),
                    ('mstobeats',500,1),('mstohz',500,2),('mstosamps',1000,44100),('mstoticks',500,480),
                    ('sampstobeats',22050,1),('sampstohz',22050,2),('sampstoms',44100,1000),('sampstoticks',22050,480),
                    ('tickstobeats',480,1),('tickstohz',480,2),('tickstoms',480,500),('tickstosamps',480,22050),('tickstosamples',480,22050)):
            self.assertEqual(r.operation(n,x),y,n)
            if n+'~'in r.SIGNAL_NAMES:self.assertEqual(r.operation(n+'~',x),y,n)
    def test_inverse_pairs_and_signs(self):
        for a,b in(('beatstohz','hztobeats'),('beatstoms','mstobeats'),('beatstosamps','sampstobeats'),
                    ('beatstoticks','tickstobeats'),('hztoms','mstohz'),('hztosamps','sampstohz'),
                    ('hztoticks','tickstohz'),('mstosamps','sampstoms'),('mstoticks','tickstoms'),('sampstoticks','tickstosamps')):
            for x in(-8,-.125,.125,8):self.assertEqual(r.operation(b,r.operation(a,x)),x,(a,b,x))
    def test_signals_vary_inside_blocks_and_events_hold(self):
        for m,n in r.MODEL_NAMES.items():
            bs=r.reference_blocks(m,r.input_words());es=r.parameter_events(m)
            self.assertEqual(len(es),21);self.assertEqual(len(bs),20)
            self.assertEqual(bs[6],bs[7]);self.assertEqual(bs[12],bs[13]);self.assertEqual(bs[13],bs[14])
            for b in bs:
                self.assertEqual(b[1::2],r.input_words()[1::2])
                self.assertEqual(len(set(b[::2]))>1,n.endswith('~'))
            # Last of three ordered actions beforecall10 is observed.
            x=es[12]['value']+(r.value(r.input_words()[0])if n.endswith('~')else 0)
            self.assertEqual(bs[10][0],r.word(r.operation(n,x)))
    def test_fixed_sources_and_predeclared_unit_limits(self):
        full=json.loads((HERE/'catalog.json').read_bytes());combined=[]
        self.assertEqual(len(full['cases']),36)
        for i in(1,2):
            c=json.loads((HERE/f'part{i}.json').read_bytes());builder.unit_conversion_catalog(c);combined+=c['cases']
            changed=copy.deepcopy(c);changed['cases'][0]['transport_contract']['tempo_bpm']=100
            with self.assertRaises(ValueError):builder.unit_conversion_catalog(changed)
        self.assertEqual(full['cases'],combined)
        self.assertEqual(builder.sha(HERE/'reference.py'),builder.UNIT_CONVERSION_REFERENCE_SHA)
        self.assertEqual(len({x['id'].casefold()for x in combined}),36)
        self.assertEqual(max(r.ABSOLUTE_TOLERANCES.values()),.008)
        for c in combined:self.assertEqual(builder.sha(HERE/c['patch']),c['patch_sha256'])
    def _plan(self,i):
        cat=json.loads((HERE/f'part{i}.json').read_bytes());rows=[]
        for src in cat['cases']:
            row=copy.deepcopy(src);m=src['model'];inputs=r.input_words();bs=r.reference_blocks(m,inputs)
            row.update(source_sha256=src['patch_sha256'],absolute_tolerance=builder.float32(src['maximum_absolute_error']),input_words=list(inputs),expected=list(bs[0]),
                expected_blocks=[list(b)for b in bs],expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(w for b in bs for w in b))).hexdigest(),
                expected_parameter_count=1,parameters=[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0)],
                parameter_events=[dict(before_call=e['before_call'],id='drive',parameter_slot=0,value_word=r.word(e['value']),normalized_word=r.word((e['value']+8)/16))for e in r.parameter_events(m)])
            rows.append(row)
        pool,indices=builder.block_pool(rows)
        for row,refs in zip(rows,indices):row['expected_block_indices']=refs;del row['expected_blocks']
        return dict(family='rnbo-unit-conversions',catalog_sha256=builder.UNIT_CONVERSION_PARTITIONS[i],reference_source_sha256=builder.UNIT_CONVERSION_REFERENCE_SHA,
            surface='patcher',partition=cat['partition'],prepare_zero_warm_blocks=0,warmup_blocks=4,timed_blocks=16,
            expected_block_storage='shared-512-word-pool',expected_reference_unique_blocks=len(pool),expected_block_pool=[list(b)for b in pool],cases=rows)
    def test_collector_rejects_changed_units_transport_source_and_event_order(self):
        for i in(1,2):
            p=self._plan(i);collector.unit_conversion_plan(p)
            for change in(lambda q:q['cases'][0]['transport_contract'].update(tempo_bpm=100),
                          lambda q:q['cases'][0].update(absolute_tolerance=.008),
                          lambda q:q['cases'][0]['parameter_events'][0].update(value_word=r.word(7.)),
                          lambda q:q['cases'][0].update(source_sha256='0'*64),
                          lambda q:q['expected_block_pool'][0].__setitem__(0,r.word(1.)),
                          lambda q:q.update(prepare_zero_warm_blocks=1),lambda q:q['cases'].pop()):
                changed=copy.deepcopy(p);change(changed)
                with self.assertRaises(ValueError):collector.unit_conversion_plan(changed)
    def test_generated_ceiling_is_scoped_and_does_not_change_case_limits(self):
        p=self._plan(1)
        for row in p['cases']:
            row.update(module_bytes=1,module_sha256='0'*64,expected_words_sha256='0'*64,input_words_sha256='0'*64,strict_zero_sign_channels=2)
        p['prepare_zero_warm_blocks']=0
        header,_=builder.generate_header(p,r.input_words())
        self.assertIn('SMOKE_ABSOLUTE_TOLERANCE_CEILING 0x1.0624dep-7f',header)
        self.assertEqual([c['absolute_tolerance']for c in p['cases']],[builder.float32(c['maximum_absolute_error'])for c in p['cases']])
        p['family']='rnbo-events-math'
        header,_=builder.generate_header(p,r.input_words())
        self.assertNotIn('SMOKE_ABSOLUTE_TOLERANCE_CEILING',header)
    def test_right_capture_is_independent_of_large_sample_unit_limit(self):
        bs=[list(b)for b in r.reference_blocks(2606,r.input_words())]
        digest=lambda b:hashlib.sha256(b''.join(struct.pack('<256I',*v[1::2])for v in b)).hexdigest()
        self.assertTrue(collector.right_pilot_observation(dict(right_output_sha256=digest(bs)),bs)['right_pilot_bit_exact'])
        for index in(1,3,5,31):
            changed=copy.deepcopy(bs);changed[-1][index]^=1
            with self.assertRaises(ValueError):collector.right_pilot_observation(dict(right_output_sha256=digest(changed)),bs)
    def test_invalid_models_inputs_counts_and_reciprocal_zero(self):
        for m,inputs,calls in((True,r.input_words(),20),(2599,r.input_words(),20),(2600,(0,0),20),(2600,r.input_words(),0),(2600,r.input_words(),True)):
            with self.assertRaises(ValueError):r.reference_blocks(m,inputs,calls)
        for n in r.RECIPROCAL:
            with self.assertRaises(ZeroDivisionError):r.operation(n,0)
    def test_published_exact_spelling_transport_oracle_and_raw_observer(self):
        for i in(1,2):
            source=f'evidence/xiao-smoke-rnbo-unit-conversions-part{i}.json';data=json.loads((ROOT/source).read_bytes())
            for j,c in enumerate(data['cases']):
                record=dict(surface='patcher',id='patcher:'+c['exact_name'],spelling=c['exact_name'])
                item=dict(selector='/cases/'+str(j),source=source)
                self.assertEqual(publisher.checked_short_smoke(record,item,data)['status'],c['status'])
            record=dict(surface='patcher',id='patcher:'+data['cases'][0]['exact_name'],spelling=data['cases'][0]['exact_name'])
            for key,value in(('absolute_tolerance',.0005),('source_sha256','0'*64),('right_output_sha256','0'*64),
                              ('expected_stream_sha256','0'*64),('transport_contract',dict(tempo_bpm=100)),('right_pilot_bit_exact',False)):
                changed=copy.deepcopy(data);changed['cases'][0][key]=value
                with self.assertRaises(ValueError):publisher.checked_short_smoke(record,dict(selector='/cases/0',source=source),changed)
    def test_report_remains_complete_and_restoration_is_bound(self):
        products=report.products();summary=json.loads(products['evidence/rnbo-unit-conversions-status.json'])['summary']
        self.assertEqual(summary['executed'],36);self.assertEqual(summary['output_words'],368640)
        self.assertEqual(summary['parameter_events'],756)
        original=Path.read_bytes
        def changed_read(path):
            raw=original(path)
            if path.name=='xiao-smoke-rnbo-unit-conversions-player-restoration.json':
                data=json.loads(raw);data['test_result_sha256']='0'*64;return json.dumps(data).encode()
            return raw
        with patch.object(Path,'read_bytes',changed_read):
            with self.assertRaises(ValueError):report.products()
