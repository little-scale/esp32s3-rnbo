#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile original portable C truth and compare all nine complete caches."""
import ctypes as C
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'tests/fixtures/gen/target'
def load(name):
    spec=importlib.util.spec_from_file_location('gen_target_'+name,TARGET/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
inputs=load('inputs');models=load('models')
class State(C.Structure):
    _fields_=[('magic',C.c_uint32),('model',C.c_uint32),('next_frame',C.c_uint32),('epoch',C.c_int64)]


class GenHistoryOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        library=Path(cls.temp.name)/'gen-history.so'
        subprocess.run(['cc','-std=c11','-O3','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-shared','-fPIC',str(ROOT/'object-benchmark/main/gen_history_oracle.c'),'-o',str(library),'-lm'],check=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.object_gen_history_oracle_init.argtypes=[C.POINTER(State),C.c_uint32,C.c_uint32];cls.lib.object_gen_history_oracle_init.restype=C.c_bool
        cls.lib.object_gen_history_oracle_reset.argtypes=[C.POINTER(State),C.c_uint32];cls.lib.object_gen_history_oracle_reset.restype=C.c_bool
        cls.lib.object_gen_history_oracle_reset_witness.argtypes=[C.POINTER(State),C.POINTER(C.c_float),C.c_uint32,C.c_uint32,C.POINTER(C.c_bool)];cls.lib.object_gen_history_oracle_reset_witness.restype=C.c_bool
        cls.lib.object_gen_history_oracle_fill.argtypes=[C.POINTER(State),C.POINTER(C.c_float),C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.c_float),C.c_uint32,C.POINTER(C.c_double)];cls.lib.object_gen_history_oracle_fill.restype=C.c_bool
        for name in ['tail_bound','evaluation_bound']:
            function=getattr(cls.lib,'object_gen_history_oracle_'+name);function.argtypes=[C.c_uint32];function.restype=C.c_double
        cls.catalog=json.loads((TARGET/'catalog.json').read_text())

    def test_all_nine_full_cache_bytes_rounding_and_cursor_match_python(self):
        frames=16384;source=inputs.generate(frames);raw=inputs.interleaved(frames)
        wire=(C.c_float*(2*frames)).from_buffer_copy(raw)
        for fixture in self.catalog['fixtures']:
            model=fixture['semantic']['model_id']
            for case in fixture['cases']:
                expected=models.expected_outputs(model,source,case['events'])
                state=State();self.assertTrue(self.lib.object_gen_history_oracle_init(C.byref(state),model,4));self.assertEqual(state.epoch,-1024)
                output=(C.c_float*(2*frames))();rounding=C.c_double(0);first=0;at=0;n=0;chunks=[1,7,255,256,509,1024]
                resets=[e['block']*256 for e in case['events']];mask=bytearray(64)
                while first<frames:
                    while at<len(resets)and resets[at]==first:
                        observable=C.c_bool(False);unchanged=bytes(state)
                        self.assertTrue(self.lib.object_gen_history_oracle_reset_witness(C.byref(state),wire,frames,first,C.byref(observable)))
                        self.assertEqual(bytes(state),unchanged)
                        if observable.value:mask[first//256]=1
                        self.assertTrue(self.lib.object_gen_history_oracle_reset(C.byref(state),first));at+=1
                    count=min(chunks[n%len(chunks)],frames-first)
                    if at<len(resets):count=min(count,resets[at]-first)
                    target=C.cast(C.byref(output,first*8),C.POINTER(C.c_float))
                    self.assertTrue(self.lib.object_gen_history_oracle_fill(C.byref(state),wire,frames,first,count,target,count*2,C.byref(rounding)),(fixture['id'],case['id'],first,count))
                    first+=count;n+=1
                self.assertEqual(bytes(output),models.cache_bytes(expected),(fixture['id'],case['id']))
                self.assertEqual(rounding.value,expected['maximum_cache_rounding_error'])
                self.assertEqual(bytes(mask),models.reset_witness_bytes(expected))
                self.assertEqual(expected['witness_minimum_separation'],8e-6)
                self.assertEqual(state.next_frame,frames)
                self.assertEqual(self.lib.object_gen_history_oracle_tail_bound(model),expected['model_tail_bound'])
                self.assertEqual(self.lib.object_gen_history_oracle_evaluation_bound(model),expected['model_evaluation_bound'])

    def test_rotation_warmup_and_reset_counterfactual_are_observable(self):
        source=inputs.generate(16384)
        expected_counts={1:[0,6,63],2:[0,0,0],3:[0,5,64]}
        for fixture in self.catalog['fixtures']:
            model=fixture['semantic']['model_id']
            for case,witnesses in zip(fixture['cases'],expected_counts[model]):
                result=models.expected_outputs(model,source,case['events'])
                self.assertEqual(result['observable_reset_count'],witnesses)
                self.assertEqual(result['scheduled_reset_count'],len(case['events']))
                if model==3 and case['id']=='continuous':self.assertEqual((result['cache'][0][0],result['cache'][1][0]),(2.0,3.0))
                if model==3 and case['id']=='retrigger-every-block':self.assertEqual((result['cache'][0][0],result['cache'][1][0]),(1.0,2.0))
                if model==3 and case['id']=='boundary-resets':
                    self.assertEqual([x['block']for x in result['reset_witnesses']if not x['observable_at_limit']],[31])

    def test_bad_input_cursor_reset_alias_and_state_reject_atomically(self):
        frames=512;wire=(C.c_float*(frames*2)).from_buffer_copy(inputs.interleaved(frames))
        for mutation in ['input','wrong-cursor','capacity','alias','invalid-epoch','rounding']:
            state=State();self.assertTrue(self.lib.object_gen_history_oracle_init(C.byref(state),1,4))
            source=(C.c_float*(frames*2)).from_buffer_copy(bytes(wire));output=(C.c_float*8)(*([42.0]*8));rounding=C.c_double(0);first=0;values=8
            if mutation=='input':source[2]=0.125
            if mutation=='wrong-cursor':first=1
            if mutation=='capacity':values=7
            if mutation=='invalid-epoch':state.epoch=-1
            if mutation=='rounding':rounding.value=-1
            target=C.cast(C.byref(source,4),C.POINTER(C.c_float))if mutation=='alias'else output
            before=bytes(state);old=bytes(output);source_before=bytes(source)
            self.assertFalse(self.lib.object_gen_history_oracle_fill(C.byref(state),source,frames,first,4,target,values,C.byref(rounding)),mutation)
            self.assertEqual(bytes(state),before);self.assertEqual(bytes(output),old);self.assertEqual(bytes(source),source_before)
        state=State();self.assertTrue(self.lib.object_gen_history_oracle_init(C.byref(state),3,4));before=bytes(state)
        for first in [1,256,16385]:
            self.assertFalse(self.lib.object_gen_history_oracle_reset(C.byref(state),first));self.assertEqual(bytes(state),before)
        self.assertTrue(self.lib.object_gen_history_oracle_reset(C.byref(state),0));self.assertTrue(self.lib.object_gen_history_oracle_reset(C.byref(state),0))
        for model,warm in [(0,4),(4,4),(1,0),(1,3),(1,5)]:
            self.assertFalse(self.lib.object_gen_history_oracle_init(C.byref(State()),model,warm))
        self.assertTrue(math.isnan(self.lib.object_gen_history_oracle_tail_bound(0)))

    def test_python_contract_and_stimulus_are_not_fitted_to_outputs(self):
        for first,count in [(0,1),(1,7),(255,257),(511,513),(16380,4)]:
            full=inputs.interleaved();self.assertEqual(inputs.interleaved(count,first_frame=first),full[first*8:(first+count)*8])
        for args in [(True,0),(0,0),(1,-1),(2,16383)]:
            with self.assertRaises(ValueError):inputs.generate(args[0],first_frame=args[1])
        source=inputs.generate(512)
        for events in [[{'block':1,'id':'reset','form':'actual','value':1.0}], [{'block':1,'id':'s3_reset','form':'normalized','value':1.0}], [{'block':1,'id':'s3_reset','form':'actual','value':0.0}], [{'block':True,'id':'s3_reset','form':'actual','value':1.0}]]:
            with self.assertRaises(ValueError):models.expected_outputs(1,source,events)
        bad=[list(p)for p in source];bad[0][0]+=1e-10
        with self.assertRaises(ValueError):models.expected_outputs(1,bad)
        # Independent high-accuracy fsum checks the ordinary binary64 model;
        # this is a truth crosscheck, not the C/Python cache implementation.
        truth=models.expected_outputs(1,source)['truth']
        for frame in [0,1,7,63,64,255,256,511]:
            history=math.fsum(math.ldexp(source[0][frame-age],-(age-1))for age in range(1,min(frame,64)+1))
            self.assertLessEqual(abs(truth[1][frame]-history),models.EVALUATION_BOUND)
            self.assertLessEqual(abs(truth[0][frame]-(source[0][frame]+0.5*history)),models.EVALUATION_BOUND)

    def test_witness_respects_prior_reset_and_rejects_invalid_cursor_without_writes(self):
        wire=(C.c_float*1024).from_buffer_copy(inputs.interleaved(512))
        state=State();self.assertTrue(self.lib.object_gen_history_oracle_init(C.byref(state),3,4))
        observed=C.c_bool(False);before=bytes(state)
        self.assertTrue(self.lib.object_gen_history_oracle_reset_witness(C.byref(state),wire,512,0,C.byref(observed)))
        self.assertTrue(observed.value);self.assertEqual(bytes(state),before)
        self.assertTrue(self.lib.object_gen_history_oracle_reset(C.byref(state),0));before=bytes(state)
        self.assertTrue(self.lib.object_gen_history_oracle_reset_witness(C.byref(state),wire,512,0,C.byref(observed)))
        self.assertFalse(observed.value);self.assertEqual(bytes(state),before)
        for first in [1,256,512]:
            observed.value=True
            self.assertFalse(self.lib.object_gen_history_oracle_reset_witness(C.byref(state),wire,512,first,C.byref(observed)))
            self.assertTrue(observed.value);self.assertEqual(bytes(state),before)
        wire[0]=float('nan');observed.value=True
        self.assertFalse(self.lib.object_gen_history_oracle_reset_witness(C.byref(state),wire,512,0,C.byref(observed)))
        self.assertTrue(observed.value);self.assertEqual(bytes(state),before)


if __name__=='__main__':unittest.main()
