#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record short functional outcomes and CPU follow-ups, without implying full qualification."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
TOLERANCE_CEILING=struct.unpack('<f',struct.pack('<f',.001))[0]
sys.path.insert(0,str(ROOT/'host/compiler'))
from prepare import canonical
from build_smoke_modules import (DBTOA_PROFILE_PROOFS,DBTOA_CATALOG_SHA,DBTOA_REFERENCE_SHA,
                                gen_delay_catalog,GEN_DELAY_RERUN,GEN_DELAY_REFERENCE_SHA,
                                GEN_DELAY_PROOFS,GEN_DELAY_REFERENCE_PROOFS)
from build_hardware_smoke import (CHARACTER_FAMILY,CHARACTER_PARTITIONS,CHARACTER_REFERENCE_SHA,
                                 character_catalog,GEN_DATA_FAMILY,GEN_DATA_CATALOG_SHA,
                                 GEN_DATA_REFERENCE_SHA,gen_data_catalog)
from build_hardware_smoke import (MOTION_MEMBER_FAMILY,MOTION_MEMBER_CATALOG_SHA,
                                 MOTION_MEMBER_REFERENCE_SHA,MOTION_MEMBER_PARTITIONS,motion_member_catalog)
from build_hardware_smoke import (CONTEXT_ALIAS_FAMILY,CONTEXT_ALIAS_CATALOG_SHA,
                                 CONTEXT_ALIAS_REFERENCE_SHA,CONTEXT_ALIAS_PARTITIONS,context_alias_catalog)
from build_hardware_smoke import (ANALYSIS_MEMBER_FAMILY,ANALYSIS_MEMBER_CATALOG_SHA,
                                 ANALYSIS_MEMBER_REFERENCE_SHA,analysis_member_catalog)
from build_hardware_smoke import (DELAY_MEMBER_FAMILY,DELAY_MEMBER_CATALOG_SHA,
                                 DELAY_MEMBER_REFERENCE_SHA,delay_member_catalog)
from build_hardware_smoke import (MEMBER_FAMILY,MEMBER_CATALOG_SHA,MEMBER_REFERENCE_SHA,
                                 MEMBER_PARTITIONS,member_catalog)
from build_hardware_smoke import (STRUCTURE_FAMILY,STRUCTURE_CATALOG_SHA,
                                 STRUCTURE_REFERENCE_SHA,structure_catalog)
from build_hardware_smoke import (CONTAINER_FAMILY,CONTAINER_CATALOG_SHA,
                                 CONTAINER_REFERENCE_SHA,container_catalog)
from build_hardware_smoke import (GEN_EXT_FAMILY,GEN_EXT_CATALOG_SHA,GEN_EXT_REFERENCE_SHA,
                                 GEN_EXT_PARTITIONS,gen_extended_catalog)
from build_hardware_smoke import (GEN_EXEC_FAMILY,GEN_EXEC_CATALOG_SHA,
                                 GEN_EXEC_REFERENCE_SHA,gen_execution_catalog)
from build_hardware_smoke import (GEN_CAUSAL_FAMILY,GEN_CAUSAL_CATALOG_SHA,
                                 GEN_CAUSAL_REFERENCE_SHA,gen_causal_catalog)
from build_hardware_smoke import (GEN_CONTROL_FAMILY,GEN_CONTROL_CATALOG_SHA,
                                 GEN_CONTROL_REFERENCE_SHA,gen_control_catalog)
from build_hardware_smoke import (LIST_FUNCTION_FAMILY,LIST_FUNCTION_CATALOG_SHA,
                                 LIST_FUNCTION_REFERENCE_SHA,list_function_catalog)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(test,message):
    if not test:raise ValueError(message)


def decimal(data,key):
    value=data.get(key)
    require(type(value)is str and re.fullmatch('[0-9]+',value)is not None,'Missing or invalid decimal field: '+key)
    return int(value)


def word(data,key):
    value=data.get(key)
    require(type(value)is str and re.fullmatch('[0-9a-f]{8}',value)is not None,'Missing or invalid binary32 word: '+key)
    return int(value,16)


def same_numeric_word(actual,expected):
    return actual==expected or ((actual|expected)&0x7fffffff)==0


def fields(line,prefix):
    require(line.startswith(prefix),'Wrong smoke record type')
    result={}
    for token in line[len(prefix):].strip().split():
        pair=token.split('=',1)
        require(len(pair)==2 and pair[0] not in result,'Malformed smoke fields')
        result[pair[0]]=pair[1]
    return result


def cpu_metrics(times):
    require(len(times)==16 and all(type(t)is int and 0<=t<=1000000000 for t in times),
        'Invalid callback observations')
    med=statistics.median(times);mean=sum(times)/len(times);peak=max(times)
    high=med>.1*256*1000000/44100;spike=peak>max(3*med,med+100)
    reasons=(["median_budget"]if high else[])+(["peak_spike"]if spike else[])
    return med,mean,peak,reasons


def output_metrics(data,expected,common_input_sha,*,tolerance_ceiling=TOLERANCE_CEILING):
    bits=int(data['bit_mismatches']);zeros=int(data['zero_sign_differences']);samples=int(data['samples'])
    require(samples==20*512 and 0<=zeros<=bits<=samples,'Output comparison counts differ')
    metrics={'samples_checked':samples,'bit_mismatches':bits,'zero_sign_differences':zeros}
    mask=expected.get('strict_zero_sign_channels',0)
    require(type(mask)is int and 0<=mask<=3,'Invalid strict zero-sign channel mask')
    strict=decimal(data,'strict_zero_sign_mismatches')if 'strict_zero_sign_mismatches'in data else 0
    require(not strict or mask,'Strict zero-sign failures lack a declared channel mask')
    if mask:
        require('strict_zero_sign_mismatches'in data and 'numeric_mismatches'in data,
                'Strict zero-sign channel requires its numeric subtype record')
        metrics['strict_zero_sign_mismatches']=strict
    numeric=bits-zeros
    if 'numeric_mismatches' in data:
        numeric=int(data['numeric_mismatches']);within=int(data['within_tolerance_differences'])
        nonfinite=int(data['nonfinite_outputs'])
        if 'max_absolute_error_bits' in data:
            require(re.fullmatch('[0-9a-f]{16}',data['max_absolute_error_bits']) and
                    re.fullmatch('[0-9a-f]{8}',data['absolute_tolerance_bits']),
                    'Malformed binary error/tolerance record')
            error=struct.unpack('<d',struct.pack('<Q',int(data['max_absolute_error_bits'],16)))[0]
            tolerance=struct.unpack('<f',struct.pack('<I',int(data['absolute_tolerance_bits'],16)))[0]
        else:
            error=float(data['max_absolute_error']);tolerance=float(data['absolute_tolerance'])
        require(0<=nonfinite<=numeric<=bits and 0<=strict<=numeric-nonfinite and 0<=within<=bits and numeric+within+zeros==bits,
            'Numerical comparison counters differ')
        require(math.isfinite(tolerance) and 0<=tolerance<=tolerance_ceiling and tolerance==expected.get('absolute_tolerance',0) and
                math.isfinite(error) and error>=0 and (within==0 or tolerance>0),
                'Predeclared error tolerance or observed error differs')
        require((numeric>0 or error<=tolerance) and (numeric==nonfinite+strict or error>tolerance),
                'Numerical status contradicts the largest finite error')
        require(data['input_words_sha256']==expected.get('input_words_sha256',common_input_sha),
                'Device input vector differs from the prepared case')
        metrics.update(numeric_mismatches=numeric,within_tolerance_differences=within,nonfinite_outputs=nonfinite,
            max_absolute_error=error,absolute_tolerance=tolerance,input_words_sha256=data['input_words_sha256'])
    else:require(not strict and expected.get('absolute_tolerance',0)==0 and 'input_words' not in expected,
        'Per-case vector/tolerance requires the new device comparison record')
    status='pass' if numeric==0 else 'output_mismatch'
    require(data['status']==status and int(data['finalized'])==1,'Output/finalization status differs')
    return dict(metrics,status=status)


def valid_expected_block(block):
    return type(block)is list and len(block)==512 and all(type(w)is int and 0<=w<=0xffffffff and
        (w&0x7f800000)!=0x7f800000 for w in block)


def expected_pool(plan):
    pool=plan.get('expected_block_pool');count=plan.get('expected_reference_unique_blocks')
    require(type(pool)is list and type(count)is int and 1<=count==len(pool)and all(valid_expected_block(block)for block in pool),
            'Invalid expected block pool/count')
    require(len({tuple(block)for block in pool})==count,'Expected block pool is not deduplicated')
    return pool


def expected_stream(expected,stateful=False,pool=None):
    """Bind the fresh-constructor twenty-call reference as little-endian words."""
    require(valid_expected_block(expected.get('expected')),'Invalid legacy expected block')
    indices=expected.get('expected_block_indices')
    if indices is not None or pool is not None:
        require(stateful and pool is not None and 'expected_blocks'not in expected and type(indices)is list and len(indices)==20 and
                all(type(index)is int and 0<=index<len(pool)for index in indices),'Invalid compact expected block indices')
        blocks=[pool[index]for index in indices]
    else:blocks=expected.get('expected_blocks')
    if blocks is None:
        require(not stateful and 'expected_stream_sha256'not in expected,'Stateful expected stream is missing')
        return None,None
    require(stateful and type(blocks)is list and len(blocks)==20 and all(valid_expected_block(block)for block in blocks),
            'Stateful reference requires twenty finite 512-word blocks')
    require(expected['expected']==blocks[0],'Legacy expected block differs from stream block0')
    fingerprint=hashlib.sha256(b''.join(struct.pack('<512I',*block)for block in blocks)).hexdigest()
    require(expected.get('expected_stream_sha256')==fingerprint,'Expected stream hash differs from its twenty blocks')
    return blocks,fingerprint


def mismatch_witness(data,expected,status,output,blocks=None,stream_sha=None):
    def decimal(key):
        value=data.get(key)
        require(type(value)is str and re.fullmatch('[0-9]+',value)is not None,'Missing or invalid mismatch field: '+key)
        return int(value)
    first=decimal('first_mismatch_word');keys={'first_mismatch_call','expected_block_count'}
    present=keys.intersection(data);extra={}
    require(not present or present==keys,'Mismatch call/block-count fields must be atomic')
    require(blocks is None or present==keys,'Stateful mismatch call/block count missing')
    call=None
    if present:
        call=decimal('first_mismatch_call');count=decimal('expected_block_count')
        require(count==(20 if blocks is not None else 1),'Device expected block count differs')
        extra.update(first_mismatch_call=None if call==0xffffffff else call,expected_block_count=count)
    if stream_sha is not None:extra['expected_stream_sha256']=stream_sha
    if 'expected_stream_sha256'in data:
        require(stream_sha is not None and data['expected_stream_sha256']==stream_sha,'Device expected stream hash differs')
    if status=='output_mismatch':
        require(0<=first<512 and(call is None or 0<=call<20),'Missing or out-of-range output mismatch witness')
        target_word=(blocks[call]if blocks is not None else expected['expected'])[first]
        require(all(re.fullmatch('[0-9a-f]{8}',data.get(key,''))for key in ('first_actual','first_expected'))and
                int(data['first_expected'],16)==target_word,'Mismatch witness differs from its call-specific reference')
        actual_word=int(data['first_actual'],16)
        require(actual_word!=target_word,'Output mismatch witness is an unchanged word')
        strict_zero=((actual_word|target_word)&0x7fffffff)==0
        if strict_zero:
            require(expected.get('strict_zero_sign_channels',0)&(1<<(first%2)) and
                    output.get('strict_zero_sign_mismatches',0)>0,
                    'Output mismatch witness is only an allowed zero sign')
        actual=struct.unpack('<f',struct.pack('<I',actual_word))[0]
        target=struct.unpack('<f',struct.pack('<I',target_word))[0]
        if strict_zero:pass
        elif math.isfinite(actual):
            require(abs(actual-target)>expected.get('absolute_tolerance',0),
                    'Mismatch witness is within the predeclared error tolerance')
            if 'max_absolute_error'in output:require(output['max_absolute_error']>=abs(actual-target),'Maximum error omits the mismatch witness')
        else:require(output.get('nonfinite_outputs',1)>0,'Nonfinite witness count differs')
    else:
        require(first==0xffffffff and(call is None or call==0xffffffff),'Passing case has a mismatch witness')
    return first,extra


def parameter_observations(expected,data,events,enabled=False,*,allow_tolerance=False):
    """Bind actual TimeNow boundary actions; these are not sample-offset events."""
    counters={'parameter_count','parameter_events_applied','event_total_us','event_peak_us'}
    present=counters.intersection(data)
    if not enabled:
        require(not events and 'parameters'not in expected,'Unexpected parameter event records')
        require(not present or present==counters,'Parameter CASE counters must be atomic')
        require(all(decimal(data,key)==0 for key in present),'Unbound parameter CASE counters are nonzero')
        return {}
    require(present==counters,'Parameter CASE counters are missing')
    count=expected.get('expected_parameter_count');parameters=expected.get('parameters');actions=expected.get('parameter_events')
    require(type(count)is int and 1<=count<=32 and type(parameters)is list and len(parameters)==count,
            'Parameter contract count differs')
    require(type(expected.get('parameter_schema_sha256'))is str and
            re.fullmatch('[0-9a-f]{64}',expected['parameter_schema_sha256'])is not None,'Invalid parameter schema identity')
    require(type(actions)is list and 1<=len(actions)<=128 and len(events)==len(actions),'Parameter event count differs')
    require(type(expected.get('strict_zero_sign_channels'))is int and expected['strict_zero_sign_channels']==2 and
            type(expected.get('absolute_tolerance',0))in(int,float)and
            (0<=expected.get('absolute_tolerance',0)<=TOLERANCE_CEILING if allow_tolerance else expected.get('absolute_tolerance',0)==0),
            'Boundary parameter scenario requires strict right observer and zero tolerance')
    identities=set()
    for parameter in parameters:
        require(type(parameter)is dict and set(parameter)=={'id','minimum','maximum','initial','exponent','steps'},'Invalid parameter contract')
        identity=parameter['id']
        require(type(identity)is str and re.fullmatch('[A-Za-z0-9_.-]{1,191}',identity)is not None and identity not in identities,
                'Parameter ID is invalid or repeated')
        identities.add(identity)
        for key in ('minimum','maximum','initial','exponent'):
            value=parameter[key]
            require(type(value)in(int,float)and math.isfinite(value)and abs(value)<=3.4028234663852886e38 and
                    struct.unpack('<f',struct.pack('<f',value))[0]==value,'Parameter contract must contain finite binary32 values')
        require(parameter['minimum']<parameter['maximum']and parameter['minimum']<=parameter['initial']<=parameter['maximum']and
                parameter['exponent']==1 and type(parameter['steps'])is int and parameter['steps']==0,
                'Boundary parameters must be linear and unstepped')
    result=[];resolved={};used_indices={};last_call=0;total=0;peak=0
    event_keys={'case_id','ordinal','before_call','parameter_slot','resolved_index','value_word','actual_word','normalized_word','event_us'}
    for ordinal,(action,event)in enumerate(zip(actions,events)):
        require(type(action)is dict and set(action)=={'before_call','id','parameter_slot','value_word','normalized_word'},'Invalid parameter action')
        call=action['before_call'];slot=action['parameter_slot']
        require(type(call)is int and last_call<=call<20 and type(slot)is int and 0<=slot<count and
                action['id']==parameters[slot]['id'],'Parameter action order/ID/slot differs')
        last_call=call
        for key in ('value_word','normalized_word'):
            require(type(action[key])is int and 0<=action[key]<=0xffffffff and
                    (action[key]&0x7f800000)!=0x7f800000,'Parameter action word is invalid')
        value=struct.unpack('<f',struct.pack('<I',action['value_word']))[0];parameter=parameters[slot]
        require(parameter['minimum']<=value<=parameter['maximum'],'Parameter action is outside declared bounds')
        normalized=(value-parameter['minimum'])/(parameter['maximum']-parameter['minimum'])
        normalized_word=struct.unpack('<I',struct.pack('<f',normalized))[0]
        require(action['normalized_word']==normalized_word,'Authored normalized word differs from independent affine conversion')
        require(set(event)==event_keys and event['case_id']==expected['id']and decimal(event,'ordinal')==ordinal and
                decimal(event,'before_call')==call and decimal(event,'parameter_slot')==slot,
                'Parameter event case/order/action differs')
        index=decimal(event,'resolved_index')
        require(index<count and resolved.get(slot,index)==index and used_indices.get(index,slot)==slot,'Parameter runtime ID resolution differs')
        resolved[slot]=index;used_indices[index]=slot
        actual=word(event,'actual_word');observed_normalized=word(event,'normalized_word')
        require(word(event,'value_word')==action['value_word']and same_numeric_word(actual,action['value_word'])and
                same_numeric_word(observed_normalized,normalized_word),'Parameter value/readback differs')
        elapsed=decimal(event,'event_us');require(elapsed<=1000000000,'Invalid parameter event duration')
        total+=elapsed;peak=max(peak,elapsed)
        result.append({'ordinal':ordinal,'before_call':call,'id':action['id'],'parameter_slot':slot,'resolved_index':index,
                       'value_word':action['value_word'],'actual_word':actual,'normalized_word':observed_normalized,
                       'expected_normalized_word':normalized_word,'event_us':elapsed,
                       'actual_zero_sign_difference':actual!=action['value_word'],
                       'normalized_zero_sign_difference':observed_normalized!=normalized_word})
    require(decimal(data,'parameter_count')==count and decimal(data,'parameter_events_applied')==len(actions)and
            decimal(data,'event_total_us')==total and decimal(data,'event_peak_us')==peak,'Parameter CASE totals differ from actual events')
    return {'parameter_count':count,'parameter_schema_sha256':expected['parameter_schema_sha256'],'parameters':parameters,
            'parameter_events':result,'parameter_events_applied':len(result),'event_total_us':total,'event_peak_us':peak,
            'parameter_event_scope':'Actual TimeNow controls before full256-frame callbacks; no within-block event offsets',
            'event_timing_scope':'Wrapper/setter/routing callback only; readbacks and logging excluded, not isolated opcode cost'}


def dbtoa_comparison_plan(plan):
    path=ROOT/'tests/fixtures/smoke/dbtoa-f32-comparison/catalog.json'
    require(sha(path)==DBTOA_CATALOG_SHA and plan.get('catalog_sha256')==DBTOA_CATALOG_SHA and
            plan.get('reference_source_sha256')==DBTOA_REFERENCE_SHA and plan.get('surface')=='patcher'and
            type(plan.get('prepare_zero_warm_blocks'))is int and plan['prepare_zero_warm_blocks']==0 and
            plan.get('comparison_order')=='vector-outer-round-middle-ABBA-inner-v1',
            'dbtoa comparison source/profile policy differs')
    original=json.loads(path.read_bytes())['cases'];cases=plan.get('cases',[])
    require(len(cases)==len(original)==48,'dbtoa comparison requires all48 ABBA cases')
    hashes={'A':set(),'B':set()}
    for expected,row in zip(original,cases):
        phase=expected['comparison_phase']
        require(canonical({k:row.get(k)for k in expected})==canonical(expected)and
                canonical(row.get('module_profile_contract'))==canonical(DBTOA_PROFILE_PROOFS[phase])and
                row.get('arena_bytes')==1048576 and
                row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',2e-6))[0]and
                not any(k in row for k in ('expected_blocks','expected_parameter_count','parameter_events')),
                'dbtoa phase/source/profile/map/arena declaration differs')
        hashes[phase].add(row['module_sha256'])
    require(all(len(v)==1 for v in hashes.values())and hashes['A']!=hashes['B'],
            'dbtoa comparison requires one distinct actual module per profile')
    for offset in range(0,48,4):
        group=cases[offset:offset+4]
        require(len({row['input_words_sha256']for row in group})==1 and
                len({row['expected_words_sha256']for row in group})==1,
                'dbtoa ABBA inputs or ideal caches differ within a group')


def dbtoa_comparison_times(records):
    groups=[]
    for offset in range(0,len(records),4):
        group=records[offset:offset+4]
        a=sum(sum(row['times_us'])for row in (group[0],group[3]))
        b=sum(sum(row['times_us'])for row in (group[1],group[2]))
        groups.append({'model':group[0]['model'],'comparison_round':group[0]['comparison_round'],
            'reference_process_us':a,'candidate_process_us':b,'timed_callbacks_per_profile':32,
            'callback_time_saved_percent':100*(a-b)/a if a else None,
            'all_accuracy_checks_passed':all(row['status']=='pass'for row in group)})
    a=sum(g['reference_process_us']for g in groups);b=sum(g['candidate_process_us']for g in groups)
    return {'groups':groups,'reference_process_us':a,'candidate_process_us':b,
        'timed_callbacks_per_profile':32*len(groups),'callback_time_saved_percent':100*(a-b)/a if a else None,
        'all_accuracy_checks_passed':all(g['all_accuracy_checks_passed']for g in groups),
        'direct_target_pairwise_outputs_checked':False,'universal_bit_identity_claimed':False,
        'scope':'Matched ABBA complete stereo FX process callbacks; preparation/events/copy/I2S/network excluded'}


def gen_delay_rerun_plan(plan):
    """An additive rerun of two source forms, never replacement of the old batch."""
    original=json.loads((ROOT/'tests/fixtures/smoke/gen-state-boundaries/catalog.json').read_bytes())
    catalog=dict(original,cases=original['cases'][-2:],rerun=GEN_DELAY_RERUN)
    gen_delay_catalog(catalog)
    require(plan.get('rerun')==GEN_DELAY_RERUN and plan.get('family')=='gen-state-boundaries'and
        plan.get('surface')=='genexpr'and type(plan.get('prepare_zero_warm_blocks'))is int and
        plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
        plan.get('catalog_sha256')==hashlib.sha256(canonical(catalog)).hexdigest()and
        plan.get('reference_source_sha256')==GEN_DELAY_REFERENCE_SHA and
        plan.get('compile_failures')==[]and not plan.get('admission_failures'),
        'Gen Delay rerun catalog/reference/epoch differs')
    require([row.get('id')for row in plan['cases']]==list(GEN_DELAY_REFERENCE_PROOFS),
        'Gen Delay rerun requires exactly the two original programs')
    for row,source in zip(plan['cases'],catalog['cases']):
        identity=source['id'];pins=GEN_DELAY_REFERENCE_PROOFS[identity]
        require(canonical({key:row.get(key)for key in source})==canonical(source)and
            row.get('source_sha256')==source['patch_sha256']and
            row.get('gen_delay_fix_contract')==GEN_DELAY_PROOFS.get(identity)and
            GEN_DELAY_PROOFS.get(identity)is not None and
            row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',source['maximum_absolute_error']))[0]and
            type(row.get('arena_bytes',4096))is int and row.get('arena_bytes',4096)==4096 and
            not any(key in row for key in ('parameters','expected_parameter_count','parameter_events','expected_block_indices'))and
            all(row.get(key)==value for key,value in pins.items())and
            plan.get('input_words_sha256')==pins['input_words_sha256']and
            valid_expected_block(row.get('input_words'))and
            hashlib.sha256(struct.pack('<512I',*row['input_words'])).hexdigest()==pins['input_words_sha256'],
            'Gen Delay rerun source/fixed map/original reference differs')
        expected_stream(row,True)


def character_plan(plan):
    """Bind both corrected source partitions and raw finite right-pilot words."""
    part=plan.get('partition',{});index=part.get('index')
    require(type(index)is int and index in CHARACTER_PARTITIONS,'Unknown character partition')
    path=ROOT/f'tests/fixtures/smoke/rnbo-character-constants/catalog-part{index}.json'
    catalog=json.loads(path.read_bytes());character_catalog(catalog)
    require(plan.get('catalog_sha256')==CHARACTER_PARTITIONS[index]and part==catalog['partition']and
        plan.get('family')==CHARACTER_FAMILY and plan.get('surface')=='codebox'and
        type(plan.get('prepare_zero_warm_blocks'))is int and plan['prepare_zero_warm_blocks']==0 and
        plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
        type(plan.get('strict_zero_sign_channels'))is int and plan['strict_zero_sign_channels']==2 and
        type(plan.get('raw_pilot_channel'))is int and plan['raw_pilot_channel']==1 and
        plan.get('reference_source_sha256')==CHARACTER_REFERENCE_SHA and
        not plan.get('admission_failures'),'Character source/reference/partition/pilot contract differs')
    originals={r['id']:r for r in catalog['cases']}
    cases=plan.get('cases',[]);failures=plan.get('compile_failures',[])
    ids=[r.get('id')for r in cases];failed=[r.get('id')for r in failures]
    require(len(set(ids+failed))==len(ids+failed)==len(originals)and set(ids+failed)==set(originals)and
        ids==[key for key in originals if key in ids]and failed==[key for key in originals if key in failed],
        'Character partition rows are missing, duplicated or reordered')
    input_sha='22e8e8d05d7b92004c936477e1064653d080291c82f0d3e83562a5cbcaa8efd4'
    require(plan.get('input_words_sha256')==input_sha,'Character pilot input changed')
    for row in cases:
        original=originals[row['id']]
        require(canonical({k:row.get(k)for k in original})==canonical(original)and
            row.get('source_sha256')==original['patch_sha256']and
            row.get('codebox_source_sha256')==hashlib.sha256(
                f"out1 = {original['exact_name']};\nout2 = in2;\n".encode()).hexdigest()and
            type(row.get('strict_zero_sign_channels'))is int and row['strict_zero_sign_channels']==2 and
            type(row.get('raw_pilot_channel'))is int and row['raw_pilot_channel']==1 and
            row.get('absolute_tolerance')==0 and type(row.get('absolute_tolerance'))in(int,float)and
            type(row.get('arena_bytes',4096))is int and row.get('arena_bytes',4096)==4096 and
            not any(k in row for k in ('parameters','parameter_events','expected_blocks','expected_block_indices'))and
            valid_expected_block(row.get('input_words'))and row.get('input_words_sha256')==input_sha and
            hashlib.sha256(struct.pack('<512I',*row['input_words'])).hexdigest()==input_sha,
            'Character source/zero-sign/finite-input contract differs')
        value=struct.unpack('<I',struct.pack('<f',ord(original['ascii_character'])))[0]
        expected=[word for frame in range(256)for word in (value,row['input_words'][2*frame+1])]
        require(row.get('expected')==expected and row.get('expected_words_sha256')==
                hashlib.sha256(struct.pack('<512I',*expected)).hexdigest(),
                'Character ASCII/right-word cache differs')
    for row in failures:
        original=originals[row['id']]
        require(row.get('source_sha256')==original['patch_sha256']and
            all(row.get(k)==original[k]for k in ('exact_name','syntax','registry_lookup')),
            'Character compiler rejection source differs')


def gen_data_plan(plan):
    path=ROOT/'tests/fixtures/smoke/gen-data-indexed/catalog.json'
    catalog=json.loads(path.read_bytes());labels=gen_data_catalog(catalog)
    require(plan.get('family')==GEN_DATA_FAMILY and plan.get('surface')=='genexpr'and
        plan.get('catalog_sha256')==GEN_DATA_CATALOG_SHA and
        plan.get('reference_source_sha256')==GEN_DATA_REFERENCE_SHA and
        type(plan.get('prepare_zero_warm_blocks'))is int and plan['prepare_zero_warm_blocks']==0 and
        plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
        all(plan.get(key)==value for key,value in labels.items())and
        plan.get('compile_failures')==[]and not plan.get('admission_failures')and
        [row.get('id')for row in plan['cases']]==[row['id']for row in catalog['cases']],
        'Gen data source/reference/fresh-state/storage contract differs')
    for row,source in zip(plan['cases'],catalog['cases']):
        require(canonical({key:row.get(key)for key in source})==canonical(source)and
            row.get('source_sha256')==source['patch_sha256']and
            row.get('genexpr_sha256')==source['genexpr_sha256']and
            row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',source['maximum_absolute_error']))[0]and
            type(row.get('arena_bytes',4096))is int and row.get('arena_bytes',4096)==4096 and
            not any(key in row for key in ('parameters','parameter_events','strict_zero_sign_channels')),
            'Gen data declaration/function/source or numeric scope differs')
        expected_stream(row,True)


def container_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/rnbo-codebox-containers'
    catalog=json.loads((directory/'catalog.json').read_bytes());container_catalog(catalog)
    require(plan.get('catalog_sha256')==CONTAINER_CATALOG_SHA and
            plan.get('reference_source_sha256')==CONTAINER_REFERENCE_SHA and
            sha(directory/'reference.py')==CONTAINER_REFERENCE_SHA and
            plan.get('surface')=='codebox' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0,'Container source/surface/constructor epoch differs')
    authored={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(authored) and {r['id']for r in observed}==set(authored),'Container case ledger differs')
    for row in observed:
        original=authored[row['id']]
        require(row['source_sha256']==original['patch_sha256'] and
                row['codebox_source_sha256']==original['codebox_sha256'] and
                all(row.get(k)==original[k]for k in ('exact_name','syntax','registry_lookup')),
                'Container source or surface identity differs')
    spec=importlib.util.spec_from_file_location('container_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        original=authored[row['id']];model=original['model']
        require(all(row.get(k)==v for k,v in original.items()) and row.get('absolute_tolerance')==0,
                'Container declaration or exact numerical limit differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Container vector differs from independent source')
        blocks,_=expected_stream(row,True)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Container reference stream differs from independent source')


def structure_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/rnbo-codebox-structures'
    catalog=json.loads((directory/'catalog.json').read_bytes());structure_catalog(catalog)
    require(plan.get('catalog_sha256')==STRUCTURE_CATALOG_SHA and
            plan.get('reference_source_sha256')==STRUCTURE_REFERENCE_SHA and
            sha(directory/'reference.py')==STRUCTURE_REFERENCE_SHA and
            plan.get('surface')=='codebox' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16,
            'Codebox structure source/surface/constructor epoch differs')
    authored={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(authored) and {r['id']for r in observed}==set(authored),'Codebox structure case ledger differs')
    for row in observed:
        original=authored[row['id']]
        require(row['source_sha256']==original['patch_sha256'] and
                row['codebox_source_sha256']==original['codebox_sha256'] and
                all(row.get(k)==original[k]for k in ('exact_name','syntax','registry_lookup')),
                'Codebox structure source or surface identity differs')
    spec=importlib.util.spec_from_file_location('structure_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        original=authored[row['id']];model=original['model']
        require(all(row.get(k)==v for k,v in original.items()) and row.get('absolute_tolerance')==0 and
                not any(k in row for k in ('parameters','parameter_events','strict_zero_sign_channels')),
                'Codebox structure declaration or exact numerical limit differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Codebox structure vector differs from independent source')
        blocks,_=expected_stream(row,True)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Codebox structure reference stream differs from independent source')


def delay_member_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/rnbo-codebox-delay-members'
    catalog=json.loads((directory/'catalog.json').read_bytes());delay_member_catalog(catalog)
    require(plan.get('catalog_sha256')==DELAY_MEMBER_CATALOG_SHA and
            plan.get('reference_source_sha256')==DELAY_MEMBER_REFERENCE_SHA and
            sha(directory/'reference.py')==DELAY_MEMBER_REFERENCE_SHA and
            plan.get('surface')=='codebox' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
            plan.get('expected_stream_policy')=='Fresh prepared resource member state; twenty continuous256-frame callbacks with only authored in-program clear/reset calls',
            'Delay member source/surface/constructor epoch differs')
    authored={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(authored) and {r['id']for r in observed}==set(authored),'Delay member case ledger differs')
    for row in observed:
        original=authored[row['id']]
        require(row['source_sha256']==original['patch_sha256'] and
                row['codebox_source_sha256']==original['codebox_sha256'] and
                all(row.get(k)==original[k]for k in ('exact_name','syntax','registry_lookup')),
                'Delay member source or surface identity differs')
    spec=importlib.util.spec_from_file_location('delay_member_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        original=authored[row['id']];model=original['model']
        require(all(row.get(k)==v for k,v in original.items()) and row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',original['maximum_absolute_error']))[0] and row.get('arena_bytes')==2097152 and
                not any(k in row for k in ('parameters','parameter_events','strict_zero_sign_channels')),
                'Delay member declaration or exact numerical limit differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Delay member vector differs from independent source')
        blocks,_=expected_stream(row,True)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Delay member reference stream differs from independent source')


def analysis_member_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/rnbo-codebox-analysis-members'
    catalog=json.loads((directory/'catalog.json').read_bytes());analysis_member_catalog(catalog)
    require(plan.get('catalog_sha256')==ANALYSIS_MEMBER_CATALOG_SHA and
            plan.get('reference_source_sha256')==ANALYSIS_MEMBER_REFERENCE_SHA and
            sha(directory/'reference.py')==ANALYSIS_MEMBER_REFERENCE_SHA and
            plan.get('surface')=='codebox' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
            plan.get('expected_stream_policy')=='Fresh prepared analysis/resource member state; twenty continuous256-frame callbacks with only authored reset/seed/window-change actions',
            'Analysis member source/surface/constructor epoch differs')
    authored={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(authored) and {r['id']for r in observed}==set(authored),'Analysis member case ledger differs')
    for row in observed:
        original=authored[row['id']]
        require(row['source_sha256']==original['patch_sha256'] and
                row['codebox_source_sha256']==original['codebox_sha256'] and
                all(row.get(k)==original[k]for k in ('exact_name','syntax','registry_lookup')),
                'Analysis member source or surface identity differs')
    spec=importlib.util.spec_from_file_location('analysis_member_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        original=authored[row['id']];model=original['model']
        require(all(row.get(k)==v for k,v in original.items()) and row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',original['maximum_absolute_error']))[0] and row.get('arena_bytes')==2097152 and
                not any(k in row for k in ('parameters','parameter_events','strict_zero_sign_channels')),
                'Analysis member declaration or exact numerical limit differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Analysis member vector differs from independent source')
        blocks,_=expected_stream(row,True)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Analysis member reference stream differs from independent source')


def motion_member_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/rnbo-codebox-motion-members'
    index=plan.get('partition',{}).get('index')
    require(type(index)is int and index in MOTION_MEMBER_PARTITIONS,'Invalid context/alias partition')
    catalog=json.loads((directory/f'part{index}.json').read_bytes());partition=motion_member_catalog(catalog)
    require(plan.get('partition')==partition,'Motion member partition receipt differs')
    require(plan.get('catalog_sha256')==MOTION_MEMBER_PARTITIONS[index] and
            plan.get('reference_source_sha256')==MOTION_MEMBER_REFERENCE_SHA and
            sha(directory/'reference.py')==MOTION_MEMBER_REFERENCE_SHA and
            plan.get('surface')=='codebox' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
            plan.get('expected_stream_policy')=='Fresh prepared motion member state; twenty continuous256-frame callbacks with only authored reset/set/input-reset actions',
            'Motion member source/surface/constructor epoch differs')
    require(plan.get('expected_block_storage')=='shared-512-word-pool','Motion member references require lossless shared blocks')
    pool=expected_pool(plan)
    authored={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(authored) and {r['id']for r in observed}==set(authored),'Motion member case ledger differs')
    for row in observed:
        original=authored[row['id']]
        require(row['source_sha256']==original['patch_sha256'] and
                row['codebox_source_sha256']==original['codebox_sha256'] and
                all(row.get(k)==original[k]for k in ('exact_name','syntax','registry_lookup')),
                'Motion member source or surface identity differs')
    spec=importlib.util.spec_from_file_location('motion_member_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        original=authored[row['id']];model=original['model']
        require(all(row.get(k)==v for k,v in original.items()) and row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',original['maximum_absolute_error']))[0] and row.get('arena_bytes')==2097152 and
                not any(k in row for k in ('parameters','parameter_events','strict_zero_sign_channels')),
                'Motion member declaration or exact numerical limit differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Motion member vector differs from independent source')
        blocks,_=expected_stream(row,True,pool)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Motion member reference stream differs from independent source')


def context_alias_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/rnbo-codebox-context-aliases'
    index=plan.get('partition',{}).get('index')
    require(type(index)is int and index in CONTEXT_ALIAS_PARTITIONS,'Invalid context/alias partition')
    catalog=json.loads((directory/f'part{index}.json').read_bytes());partition=context_alias_catalog(catalog)
    require(plan.get('partition')==partition,'Context/alias partition receipt differs')
    require(plan.get('catalog_sha256')==CONTEXT_ALIAS_PARTITIONS[index] and
            plan.get('reference_source_sha256')==CONTEXT_ALIAS_REFERENCE_SHA and
            sha(directory/'reference.py')==CONTEXT_ALIAS_REFERENCE_SHA and
            plan.get('surface')=='codebox' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
            plan.get('expected_stream_policy')=='Fresh prepared codebox state; twenty continuous256-frame callbacks without resets',
            'Context/alias source/surface/constructor epoch differs')
    require(plan.get('expected_block_storage')=='shared-512-word-pool','Context/alias references require lossless shared blocks')
    pool=expected_pool(plan)
    authored={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(authored) and {r['id']for r in observed}==set(authored),'Context/alias case ledger differs')
    for row in observed:
        original=authored[row['id']]
        require(row['source_sha256']==original['patch_sha256'] and
                row['codebox_source_sha256']==original['codebox_sha256'] and
                all(row.get(k)==original[k]for k in ('exact_name','syntax','registry_lookup')),
                'Context/alias source or surface identity differs')
    spec=importlib.util.spec_from_file_location('context_alias_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        original=authored[row['id']];model=original['model']
        require(all(row.get(k)==v for k,v in original.items()) and row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',original['maximum_absolute_error']))[0] and row.get('arena_bytes',4096)==4096 and
                not any(k in row for k in ('parameters','parameter_events','strict_zero_sign_channels')),
                'Context/alias declaration or exact numerical limit differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Context/alias vector differs from independent source')
        blocks,_=expected_stream(row,True,pool)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Context/alias reference stream differs from independent source')


def member_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/rnbo-codebox-members'
    index=plan.get('partition',{}).get('index')
    require(type(index)is int and index in MEMBER_PARTITIONS,'Invalid member partition')
    catalog=json.loads((directory/('part'+str(index)+'.json')).read_bytes());partition=member_catalog(catalog)
    require(plan.get('partition')==partition,'Member partition receipt differs')
    require(plan.get('catalog_sha256')==MEMBER_PARTITIONS[index] and
            plan.get('reference_source_sha256')==MEMBER_REFERENCE_SHA and
            sha(directory/'reference.py')==MEMBER_REFERENCE_SHA and
            plan.get('surface')=='codebox' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
            plan.get('expected_stream_policy')=='Fresh prepared member state; twenty continuous256-frame callbacks with only authored in-program member reset/clear calls',
            'Stateful member source/surface/constructor epoch or explicit reset policy differs')
    authored={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(authored) and {r['id']for r in observed}==set(authored),'Stateful member case ledger differs')
    for row in observed:
        original=authored[row['id']]
        require(row['source_sha256']==original['patch_sha256'] and
                row['codebox_source_sha256']==original['codebox_sha256'] and
                all(row.get(k)==original[k]for k in ('exact_name','syntax','registry_lookup')),
                'Stateful member source or surface identity differs')
    spec=importlib.util.spec_from_file_location('member_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        original=authored[row['id']];model=original['model']
        require(all(row.get(k)==v for k,v in original.items()) and row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',original['maximum_absolute_error']))[0] and
                not any(k in row for k in ('parameters','parameter_events','strict_zero_sign_channels')),
                'Stateful member declaration or exact numerical limit differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Stateful member vector differs from independent source')
        blocks,_=expected_stream(row,True)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Stateful member reference stream differs from independent source')


def gen_control_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/gen-control-structures'
    catalog=json.loads((directory/'catalog.json').read_bytes());gen_control_catalog(catalog)
    require(plan.get('catalog_sha256')==GEN_CONTROL_CATALOG_SHA and
            plan.get('reference_source_sha256')==GEN_CONTROL_REFERENCE_SHA and
            sha(directory/'reference.py')==GEN_CONTROL_REFERENCE_SHA and
            plan.get('surface')=='genexpr' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16,
            'Gen control source/surface/fresh-state policy differs')
    originals={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(originals) and {r['id']for r in observed}==set(originals),'Gen control case ledger differs')
    for row in observed:
        source=originals[row['id']]
        require(row.get('source_sha256')==source['patch_sha256'] and
                row.get('genexpr_sha256')==source['genexpr_sha256'] and
                all(row.get(k)==source[k]for k in ('exact_name','syntax','registry_lookup')),
                'Gen control source or exact language form differs')
    spec=importlib.util.spec_from_file_location('gen_control_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        source=originals[row['id']];model=source['model']
        require(all(row.get(k)==v for k,v in source.items()) and row.get('absolute_tolerance')==0 and
                not any(k in row for k in ('parameter_events','parameters','strict_zero_sign_channels')),
                'Gen control declaration/limits or default-only parameter scope differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Gen control vector differs from independent source')
        blocks,_=expected_stream(row,True)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Gen control expected stream differs from independent source')


def gen_causal_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/gen-routing-causality'
    catalog=json.loads((directory/'catalog.json').read_bytes());gen_causal_catalog(catalog)
    require(plan.get('catalog_sha256')==GEN_CAUSAL_CATALOG_SHA and
            plan.get('reference_source_sha256')==GEN_CAUSAL_REFERENCE_SHA and
            sha(directory/'reference.py')==GEN_CAUSAL_REFERENCE_SHA and
            plan.get('surface')=='genexpr' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
            plan.get('expected_stream_policy')=='Fresh prepared state, no automatic zero warmup; four checked manual warmups then sixteen timed callbacks without resets',
            'Gen routing/causal source/surface/fresh-state policy differs')
    originals={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(originals) and {r['id']for r in observed}==set(originals),'Gen routing/causal case ledger differs')
    for row in observed:
        source=originals[row['id']]
        require(row.get('source_sha256')==source['patch_sha256'] and
                row.get('genexpr_sha256')==source['genexpr_sha256'] and
                all(row.get(k)==source[k]for k in ('exact_name','syntax','registry_lookup')),
                'Gen routing/causal source or exact language form differs')
    spec=importlib.util.spec_from_file_location('gen_causal_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        source=originals[row['id']];model=source['model']
        require(all(row.get(k)==v for k,v in source.items()) and row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',source['maximum_absolute_error']))[0] and row.get('arena_bytes',4096)==4096 and
                not any(k in row for k in ('parameter_events','parameters','strict_zero_sign_channels')),
                'Gen routing/causal declaration/limits or default-only parameter scope differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Gen routing/causal vector differs from independent source')
        blocks,_=expected_stream(row,True)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Gen routing/causal expected stream differs from independent source')


def gen_execution_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/gen-execution-forms'
    catalog=json.loads((directory/'catalog.json').read_bytes());gen_execution_catalog(catalog)
    require(plan.get('catalog_sha256')==GEN_EXEC_CATALOG_SHA and
            plan.get('reference_source_sha256')==GEN_EXEC_REFERENCE_SHA and
            sha(directory/'reference.py')==GEN_EXEC_REFERENCE_SHA and
            plan.get('surface')=='genexpr' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16,
            'Gen execution source/surface/fresh-state policy differs')
    originals={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(originals) and {r['id']for r in observed}==set(originals),'Gen execution case ledger differs')
    for row in observed:
        source=originals[row['id']]
        require(row.get('source_sha256')==source['patch_sha256'] and
                row.get('genexpr_sha256')==source['genexpr_sha256'] and
                all(row.get(k)==source[k]for k in ('exact_name','syntax','registry_lookup')),
                'Gen execution source or exact language form differs')
    spec=importlib.util.spec_from_file_location('gen_execution_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        source=originals[row['id']];model=source['model']
        require(all(row.get(k)==v for k,v in source.items()) and row.get('absolute_tolerance')==0 and
                not any(k in row for k in ('parameter_events','parameters','strict_zero_sign_channels')),
                'Gen execution declaration/limits or default-only parameter scope differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Gen execution vector differs from independent source')
        blocks,_=expected_stream(row,True)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Gen execution expected stream differs from independent source')


def gen_extended_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/gen-data-extended'
    index=plan.get('partition',{}).get('index')
    require(type(index)is int and index in GEN_EXT_PARTITIONS,'Invalid extended Gen partition')
    catalog=json.loads((directory/f'part{index}.json').read_bytes());partition=gen_extended_catalog(catalog)
    require(plan.get('partition')==partition and all(plan.get(k)==catalog[k]for k in ('storage_policy','producer_storage_view')),'Extended Gen partition/storage scope differs')
    require(plan.get('catalog_sha256')==GEN_EXT_PARTITIONS[index] and
            plan.get('reference_source_sha256')==GEN_EXT_REFERENCE_SHA and
            sha(directory/'reference.py')==GEN_EXT_REFERENCE_SHA and
            plan.get('surface')=='genexpr' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
            plan.get('expected_stream_policy')=='Fresh prepared state, no automatic zero warmup; four checked manual warmups then sixteen timed callbacks without resets',
            'Extended Gen data source/surface/fresh-state policy differs')
    originals={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(originals) and {r['id']for r in observed}==set(originals),'Extended Gen data case ledger differs')
    for row in observed:
        source=originals[row['id']]
        require(row.get('source_sha256')==source['patch_sha256'] and
                row.get('genexpr_sha256')==source['genexpr_sha256'] and
                all(row.get(k)==source[k]for k in ('exact_name','syntax','registry_lookup')),
                'Extended Gen data source or exact language form differs')
    spec=importlib.util.spec_from_file_location('gen_extended_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        source=originals[row['id']];model=source['model']
        require(all(row.get(k)==v for k,v in source.items()) and row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',source['maximum_absolute_error']))[0] and row.get('arena_bytes')==2097152 and
                not any(k in row for k in ('parameter_events','parameters','strict_zero_sign_channels')),
                'Extended Gen data declaration/limits or default-only parameter scope differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs),'Extended Gen data vector differs from independent source')
        blocks,_=expected_stream(row,True)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),
                'Extended Gen data expected stream differs from independent source')


def list_function_plan(plan):
    directory=ROOT/'tests/fixtures/smoke/rnbo-codebox-list-functions'
    catalog=json.loads((directory/'catalog.json').read_bytes());list_function_catalog(catalog)
    require(plan.get('catalog_sha256')==LIST_FUNCTION_CATALOG_SHA and
            plan.get('reference_source_sha256')==LIST_FUNCTION_REFERENCE_SHA and
            sha(directory/'reference.py')==LIST_FUNCTION_REFERENCE_SHA and
            plan.get('surface')=='codebox' and type(plan.get('prepare_zero_warm_blocks'))is int and
            plan['prepare_zero_warm_blocks']==0 and plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16,
            'List-function source/surface/fresh-list policy differs')
    originals={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(originals) and {r['id']for r in observed}==set(originals),'List-function case ledger differs')
    for row in observed:
        source=originals[row['id']]
        require(row.get('source_sha256')==source['patch_sha256'] and row.get('codebox_source_sha256')==source['codebox_sha256'] and
                all(row.get(k)==source[k]for k in ('exact_name','syntax','registry_lookup')),'List-function exact call/source differs')
        if row.get('status')=='native_preflight_failed':
            require(row.get('stage')=='native-preflight' and row.get('returncode')==3 and
                    type(row.get('native_process_status'))is int and row['native_process_status']<0 and
                    type(row.get('native_fault_call'))is int and 0<=row['native_fault_call']<20 and
                    row.get('native_samples_checked')==row['native_fault_call']*512 and
                    all(type(row.get(k))is str and re.fullmatch('[0-9a-f]{64}',row[k]) for k in ('native_harness_sha256','failure_log_sha256')),
                    'Native list-function fault must remain separate from hardware execution')
    spec=importlib.util.spec_from_file_location('list_function_independent_reference',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    for row in plan['cases']:
        source=originals[row['id']];model=source['model']
        require(all(row.get(k)==v for k,v in source.items()) and row.get('absolute_tolerance')==0 and
                not any(k in row for k in ('parameter_events','parameters','expected_blocks','expected_stream_sha256')),
                'List-function declaration/zero tolerance or pointwise reference policy differs')
        inputs=reference.case_input_words(model)
        require(row.get('input_words')==list(inputs) and row.get('expected')==list(reference.reference_words(model,inputs)),
                'List-function vector/output differs from independent reference')


def event_range_plan(plan):
    from build_hardware_smoke import EVENT_RANGE_FAMILY,EVENT_RANGE_CATALOG_SHA,EVENT_RANGE_REFERENCE_SHA,event_range_catalog
    directory=ROOT/'tests/fixtures/smoke/rnbo-events-ranges'
    catalog=json.loads((directory/'catalog.json').read_bytes());event_range_catalog(catalog)
    require(plan.get('catalog_sha256')==EVENT_RANGE_CATALOG_SHA and
            plan.get('reference_source_sha256')==EVENT_RANGE_REFERENCE_SHA and
            sha(directory/'reference.py')==EVENT_RANGE_REFERENCE_SHA and plan.get('surface')=='patcher' and
            type(plan.get('prepare_zero_warm_blocks'))is int and plan['prepare_zero_warm_blocks']==0 and
            plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
            plan.get('expected_block_storage')=='shared-512-word-pool', 'Event-range source/fresh-control policy differs')
    originals={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(originals)and {r['id']for r in observed}==set(originals),'Event-range case ledger differs')
    for row in observed:
        source=originals[row['id']]
        require(row.get('source_sha256')==source['patch_sha256'] and
                all(row.get(k)==source[k]for k in ('exact_name','syntax','registry_lookup')), 'Event-range exact spelling/source differs')
    spec=importlib.util.spec_from_file_location('event_range_independent',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    pool=expected_pool(plan)
    for row in plan['cases']:
        source=originals[row['id']];model=source['model'];inputs=reference.case_input_words(model)
        require(all(row.get(k)==v for k,v in source.items()) and row.get('absolute_tolerance')==0 and
                row.get('input_words')==list(inputs),'Event-range source/domain/tolerance differs')
        blocks,_=expected_stream(row,True,pool)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),'Event-range reference stream differs')
        authored=reference.parameter_events(model);observed=row.get('parameter_events',[])
        require(len(authored)==len(observed)==21 and row.get('expected_parameter_count')==1 and
                row.get('parameters')==[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0)],
                'Event-range parameter contract differs')
        for expected,actual in zip(authored,observed):
            require(actual==dict(before_call=expected['before_call'],id='drive',parameter_slot=0,
                    value_word=reference.word(expected['value']),normalized_word=reference.word((expected['value']+8)/16)),
                    'Event-range authored action differs')


def event_math_plan(plan):
    from build_hardware_smoke import EVENT_MATH_FAMILY,EVENT_MATH_CATALOG_SHA,EVENT_MATH_REFERENCE_SHA,EVENT_MATH_PARTITIONS,event_math_catalog
    directory=ROOT/'tests/fixtures/smoke/rnbo-events-math'
    partition=plan.get('partition',{});index=partition.get('index');require(type(index)is int and index in(1,2),'Invalid event-math partition')
    catalog=json.loads((directory/('part'+str(index)+'.json')).read_bytes());event_math_catalog(catalog)
    require(partition==catalog['partition'],'Event-math partition differs')
    require(plan.get('catalog_sha256')==EVENT_MATH_PARTITIONS[index] and
            plan.get('reference_source_sha256')==EVENT_MATH_REFERENCE_SHA and
            sha(directory/'reference.py')==EVENT_MATH_REFERENCE_SHA and plan.get('surface')=='patcher' and
            type(plan.get('prepare_zero_warm_blocks'))is int and plan['prepare_zero_warm_blocks']==0 and
            plan.get('warmup_blocks')==4 and plan.get('timed_blocks')==16 and
            plan.get('expected_block_storage')=='shared-512-word-pool', 'Event-range source/fresh-control policy differs')
    originals={r['id']:r for r in catalog['cases']}
    observed=plan['cases']+plan.get('compile_failures',[])+plan.get('admission_failures',[])
    require(len(observed)==len(originals)and {r['id']for r in observed}==set(originals),'Event-range case ledger differs')
    for row in observed:
        source=originals[row['id']]
        require(row.get('source_sha256')==source['patch_sha256'] and
                all(row.get(k)==source[k]for k in ('exact_name','syntax','registry_lookup')), 'Event-range exact spelling/source differs')
    spec=importlib.util.spec_from_file_location('event_range_independent',directory/'reference.py')
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    pool=expected_pool(plan)
    for row in plan['cases']:
        source=originals[row['id']];model=source['model'];inputs=reference.case_input_words(model)
        require(all(row.get(k)==v for k,v in source.items()) and row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',source['maximum_absolute_error']))[0] and
                row.get('input_words')==list(inputs),'Event-range source/domain/tolerance differs')
        blocks,_=expected_stream(row,True,pool)
        require(tuple(tuple(b)for b in blocks)==reference.reference_blocks(model,inputs),'Event-range reference stream differs')
        authored=reference.parameter_events(model);observed=row.get('parameter_events',[])
        require(len(authored)==len(observed)==21 and row.get('expected_parameter_count')==1 and
                row.get('parameters')==[dict(id='drive',minimum=-8.,maximum=8.,initial=0.,exponent=1.,steps=0)],
                'Event-range parameter contract differs')
        for expected,actual in zip(authored,observed):
            require(actual==dict(before_call=expected['before_call'],id='drive',parameter_slot=0,
                    value_word=reference.word(expected['value']),normalized_word=reference.word((expected['value']+8)/16)),
                    'Event-range authored action differs')


def right_pilot_observation(data,blocks):
    require(type(blocks)is list and len(blocks)==20,'Raw right capture requires twenty reference blocks')
    expected=hashlib.sha256(b''.join(struct.pack('<256I',*b[1::2])for b in blocks)).hexdigest()
    observed=data.get('right_output_sha256')
    require(type(observed)is str and re.fullmatch('[0-9a-f]{64}',observed)is not None and observed==expected,
            'Raw right-lane output differs; mathematical tolerance cannot qualify this observer')
    return dict(right_pilot_bit_exact=True,right_output_sha256=observed,expected_right_output_sha256=expected)


def collect(build_dir,run_dir):
    build_path=build_dir/'build-report.json';run_path=run_dir/'hardware-smoke.json'
    build=json.loads(build_path.read_bytes());run=json.loads(run_path.read_bytes())
    require(build['format']=='rnbo-hardware-smoke-build-v1' and build['board']=='xiao','Wrong smoke build')
    require(run['format']=='rnbo-hardware-smoke-run-v1' and run['board']=='xiao' and
        run['result']=='completed' and run['left_installed'] is True,'Smoke batch did not complete')
    plan=build['plan'];require(hashlib.sha256(canonical(plan)).hexdigest()==build['plan_sha256'],'Smoke plan changed')
    if plan.get('family')=='rnbo-events-math':event_math_plan(plan)
    if plan.get('family')=='rnbo-events-ranges':event_range_plan(plan)
    if plan.get('family')==CONTAINER_FAMILY:container_plan(plan)
    if plan.get('family')==STRUCTURE_FAMILY:structure_plan(plan)
    if plan.get('family')==MEMBER_FAMILY:member_plan(plan)
    if plan.get('family')==DELAY_MEMBER_FAMILY:delay_member_plan(plan)
    if plan.get('family')==ANALYSIS_MEMBER_FAMILY:analysis_member_plan(plan)
    if plan.get('family')==MOTION_MEMBER_FAMILY:motion_member_plan(plan)
    if plan.get('family')==CONTEXT_ALIAS_FAMILY:context_alias_plan(plan)
    if plan.get('family')==GEN_CONTROL_FAMILY:gen_control_plan(plan)
    if plan.get('family')==GEN_CAUSAL_FAMILY:gen_causal_plan(plan)
    if plan.get('family')==GEN_EXEC_FAMILY:gen_execution_plan(plan)
    if plan.get('family')==GEN_EXT_FAMILY:gen_extended_plan(plan)
    if plan.get('family')==LIST_FUNCTION_FAMILY:list_function_plan(plan)
    comparison=plan.get('family')=='dbtoa-f32-comparison'
    if comparison:dbtoa_comparison_plan(plan)
    character=plan.get('family')==CHARACTER_FAMILY
    if character:character_plan(plan)
    gen_data=plan.get('family')==GEN_DATA_FAMILY
    if gen_data:gen_data_plan(plan)
    delay_rerun='rerun'in plan
    if delay_rerun:gen_delay_rerun_plan(plan)
    else:require(not any('gen_delay_fix_contract'in row for row in plan['cases']),
                 'Repaired Gen Delay requires its marked original two-case rerun')
    if plan.get('family')in('rnbo-signal-range','rnbo-signal-stateful','rnbo-signal-state-followup','rnbo-signal-routing'):
        require(plan.get('surface')=='patcher'and type(plan.get('prepare_zero_warm_blocks'))is int and
                plan['prepare_zero_warm_blocks']==0,'Signal range domains require zero automatic preparation blocks')
    if plan.get('family')in('rnbo-signal-routing','rnbo-signal-state-followup'):
        require(all(case.get('surface')=='patcher'and case.get('role')=='fx'and
                    case.get('syntax')=='signal-object'and
                    not any(key in case for key in ('genexpr','codebox','expected_parameter_count','parameter_events'))and
                    type(case.get('absolute_tolerance',0))in(int,float)and
                    0<=case.get('absolute_tolerance',0)<=2e-6 for case in plan['cases']),
                'Signal routing requires parameter-free signal sources and its declared accuracy limit')
    if plan.get('family')in('rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-codebox-analysis-members','rnbo-codebox-motion-members','rnbo-codebox-context-aliases','rnbo-codebox-list-functions','rnbo-character-constants','gen-range','gen-constants'):
        require(type(plan.get('prepare_zero_warm_blocks'))is int and plan['prepare_zero_warm_blocks']==0 and
                plan.get('surface')==('genexpr'if plan['family']in('gen-range','gen-constants')else'codebox'),
                'New numeric domains require zero automatic preparation blocks')
    event_family=plan.get('family')in('rnbo-events','rnbo-events-extra','rnbo-events-ranges','rnbo-events-math')
    stateful=plan.get('family')in('gen-stateful','gen-state-boundaries','gen-data-indexed','gen-control-structures','gen-execution-forms','gen-routing-causality','gen-data-extended','rnbo-codebox-stateful','rnbo-codebox-filters','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-codebox-analysis-members','rnbo-codebox-motion-members','rnbo-codebox-context-aliases','rnbo-signal-stateful','rnbo-signal-state-followup')or event_family
    if stateful:
        require(plan.get('surface')==('patcher'if event_family or plan['family']in('rnbo-signal-stateful','rnbo-signal-state-followup')else('codebox'if plan['family']in('rnbo-codebox-stateful','rnbo-codebox-filters','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-codebox-analysis-members','rnbo-codebox-motion-members','rnbo-codebox-context-aliases')else'genexpr'))and type(plan.get('prepare_zero_warm_blocks'))is int and
                plan['prepare_zero_warm_blocks']==0 and 'expected_stream_policy'in plan,
                'Stateful reference requires fresh zero-preparation constructor epoch and stream policy')
    pool=None
    if event_family or plan.get('family')in(CONTEXT_ALIAS_FAMILY,MOTION_MEMBER_FAMILY):
        require(plan.get('expected_block_storage')=='shared-512-word-pool','Boundary expected block storage differs')
        pool=expected_pool(plan)
    # Runner field names are checked against its saved receipt and actual log.
    log_path=run_dir/'test-serial.log';raw=log_path.read_bytes();text=raw.decode('utf-8','strict')
    require(run['test_build_report_sha256']==sha(build_path) and run['serial_log_sha256']==sha(log_path),
        'Smoke build or saved serial log differs from runner receipt')
    lines=text.splitlines();case_lines=[line for line in lines if line.startswith('RNBO_SMOKE CASE ')]
    event_groups=[];pending_events=[]
    for line in lines:
        if line.startswith('RNBO_SMOKE EVENT '):pending_events.append(fields(line,'RNBO_SMOKE EVENT '))
        elif line.startswith('RNBO_SMOKE CASE '):event_groups.append(pending_events);pending_events=[]
    require(not pending_events,'Unbound trailing parameter events')
    done_lines=[line for line in lines if line.startswith('RNBO_SMOKE DONE ')]
    require(len(done_lines)==1 and len(case_lines)==len(plan['cases']),'Incomplete smoke records')
    require(done_lines[0]==run['done_line'],'Runner/log completion differs')
    done=fields(done_lines[0],'RNBO_SMOKE DONE ')
    require(done['plan_sha256']==build['plan_sha256'],'Device used another smoke plan')
    elfs=[v['sha256']for k,v in build['artifacts'].items()if k.endswith('.elf')]
    require(len(elfs)==1 and done['firmware_elf_sha256']==elfs[0]==run['test_elf_sha256'],'Smoke firmware identity differs')
    records=[];cpu=[]
    for line,expected,events in zip(case_lines,plan['cases'],event_groups):
        data=fields(line,'RNBO_SMOKE CASE ')
        require(data['id']==expected['id'] and data['module_sha256']==expected['module_sha256'],'Smoke module identity/order differs')
        times=[int(t)for t in data['times_us'].split(',')]
        med,mean,peak,reasons=cpu_metrics(times)
        require(abs(float(data['median_us'])-med)<1e-5 and abs(float(data['mean_us'])-mean)<1e-5 and
                int(data['peak_us'])==peak,'Callback metrics differ from raw times')
        output=output_metrics(data,expected,plan['input_words_sha256'],tolerance_ceiling=struct.unpack('<f',struct.pack('<f',2e-3))[0]if plan.get('family')==CONTEXT_ALIAS_FAMILY else TOLERANCE_CEILING);status=output['status']
        blocks,stream_sha=expected_stream(expected,stateful,pool)
        first,witness_metadata=mismatch_witness(data,expected,status,output,blocks,stream_sha)
        parameters=parameter_observations(expected,data,events,event_family,allow_tolerance=plan.get('family')=='rnbo-events-math')
        if plan.get('family')=='rnbo-events-math':parameters.update(right_pilot_observation(data,blocks))
        require(data['review_cpu']==str(int(bool(reasons))) and data['cpu_reasons']==(','.join(reasons)if reasons else'none'),
                'CPU review flags differ from observations')
        record={k:expected[k]for k in ('id','exact_name','syntax','registry_lookup','reference_policy','module_sha256','source_sha256')}
        if comparison:
            record.update({k:expected[k]for k in ('model','numerical_profile','comparison_phase','comparison_round','comparison_order')})
        if delay_rerun:record['gen_delay_fix_contract']=expected['gen_delay_fix_contract']
        if character:record.update({k:expected[k]for k in ('model','ascii_decimal','raw_pilot_channel',
                                                         'codebox_inlet_names','codebox_pilot_inlet_ordinal')})
        if gen_data:record['owner_kind']=expected['owner_kind']
        if plan.get('family')in(CONTEXT_ALIAS_FAMILY,MOTION_MEMBER_FAMILY):
            record.update({k:expected[k]for k in ('model','scope')})
        if plan.get('family')==MOTION_MEMBER_FAMILY:
            record.update({k:expected[k]for k in ('owner','member','variant')})
        if plan.get('family')==ANALYSIS_MEMBER_FAMILY:
            record.update({k:expected[k]for k in ('owner','member','variant','model','scope')})
        if plan.get('family')in(GEN_CONTROL_FAMILY,GEN_EXEC_FAMILY,GEN_CAUSAL_FAMILY,GEN_EXT_FAMILY):
            record.update({k:expected[k]for k in ('model','genexpr_sha256','scope')})
        if plan.get('family')in('rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-codebox-analysis-members','rnbo-codebox-motion-members','rnbo-codebox-context-aliases','rnbo-codebox-list-functions','rnbo-character-constants'):
            code_sha=expected.get('codebox_source_sha256')
            require(type(code_sha)is str and re.fullmatch('[0-9a-f]{64}',code_sha),'Codebox source identity is missing')
            record['codebox_source_sha256']=code_sha
        record.update(**output,
            mean_us=mean,median_us=med,peak_us=peak,times_us=times,cpu_review_reasons=reasons,
            context_bytes=int(data['context_bytes']),arena_high_water=int(data['arena_high_water']),
            finalized=True,first_mismatch_word=None if first==0xffffffff else first)
        record.update(witness_metadata)
        record.update(parameters)
        if 'strict_zero_sign_channels'in expected:record['strict_zero_sign_channels']=expected['strict_zero_sign_channels']
        if 'arena_bytes' in expected:
            require(int(data['arena_capacity'])==expected['arena_bytes'] and
                0<=int(data['arena_high_water'])<=expected['arena_bytes'],'Device arena tier differs from the plan')
            record['arena_capacity']=expected['arena_bytes']
        if first!=0xffffffff:record['witness']={k:data[k]for k in ('first_actual','first_expected')}
        records.append(record)
        if reasons:cpu.append({'id':record['id'],'median_us':med,'peak_us':peak,'reasons':reasons,'status':'pending-future-optimisation-review'})
    require(int(done['cases'])==len(records) and int(done['passed'])==sum(r['status']=='pass'for r in records) and
            int(done['mismatched'])==sum(r['status']=='output_mismatch'for r in records) and
            int(done['cpu_review'])==len(cpu) and int(done['images'])==int(done['finalized_images'])==len(records),
            'Smoke completion totals differ')
    result={'format':'rnbo-hardware-smoke-results-v1','board':'xiao','device_label':'xiao-test-device-01',
        'test_level':'short-functional-hardware-check',
        'scope':'Short hardware functionality check, not full mode/domain qualification; no optimisation comparison',
        'firmware_elf_sha256':elfs[0],'plan_sha256':build['plan_sha256'],
        'input_words_sha256':plan['input_words_sha256'],
        'reference_source_sha256':plan['reference_source_sha256'],
        'collector_source_sha256':sha(Path(__file__)),
        'build_report_sha256':sha(build_path),'hardware_report_sha256':sha(run_path),'serial_log_sha256':sha(log_path),
        'left_smoke_firmware_installed':True,'cases':records,'compile_failures':plan['compile_failures'],
        'cpu_review_backlog':cpu,'summary':{'executed':len(records),'passed':int(done['passed']),
            'output_mismatches':int(done['mismatched']),'compile_failures':len(plan['compile_failures']),
            'cpu_review':len(cpu)},'full_qualification_claimed':False,
        'cpu_review_policy':{'timed_callbacks':16,'high_median_block_fraction':0.1,
            'peak_threshold':'greater than max(3*median, median+100us)',
            'action':'Record for future investigation/optimisation; do not automatically change DSP'}}
    if comparison:
        result.update(family='dbtoa-f32-comparison',surface='patcher',
                      scope='Explicit bounded changed-rounding numerical and matched ABBA callback comparison; no general object or bit-identity qualification',
                      numerical_comparison='Each profile versus the fixed independent mathematical cache',
                      profile_comparison=dbtoa_comparison_times(records))
    elif plan.get('family')=='rnbo-events-math':
        result.update(family=plan['family'],surface='patcher',partition=plan['partition'])
    elif plan.get('family') in ('rnbo-stateless','rnbo-numeric','rnbo-functions','rnbo-constants','rnbo-signal-range','rnbo-signal-stateful','rnbo-signal-state-followup','rnbo-signal-routing','rnbo-events','rnbo-events-extra','rnbo-events-ranges','rnbo-events-math') and plan.get('surface')=='patcher':
        result.update(family=plan['family'],surface='patcher')
    elif plan.get('family')in('rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-codebox-analysis-members','rnbo-codebox-motion-members','rnbo-codebox-context-aliases','rnbo-codebox-list-functions','rnbo-character-constants'):
        require(plan.get('surface')=='codebox','Codebox family requires its own surface')
        result.update(family=plan['family'],surface='codebox')
    elif plan.get('family')in('gen-math','gen-stateful','gen-state-boundaries','gen-data-indexed','gen-control-structures','gen-execution-forms','gen-routing-causality','gen-data-extended','gen-range','gen-constants')and plan.get('surface')=='genexpr':
        result.update(family=plan['family'],surface='genexpr')
    if plan.get('family')in(CONTEXT_ALIAS_FAMILY,MOTION_MEMBER_FAMILY):result['partition']=plan['partition']
    if 'input_vector_policy' in plan:result['input_vector_policy']=plan['input_vector_policy']
    if 'expected_stream_policy'in plan:result['expected_stream_policy']=plan['expected_stream_policy']
    if character:
        result.update(partition=plan['partition'],strict_zero_sign_channels=2,raw_pilot_channel=1,
            scope='Exact bare RNBO codebox ASCII named values and finite raw right-word pilot; no call/patcher/Gen qualification')
    if plan.get('family')==MEMBER_FAMILY:result['partition']=plan['partition']
    if plan.get('family')==GEN_EXT_FAMILY:
        result.update({key:plan[key]for key in ('partition','producer_storage_view','storage_policy')})
    if gen_data:
        result.update({key:plan[key]for key in ('producer_storage_view','storage_policy')})
        result['scope']='Eight local Data/indexed-storage source scenarios with original backend-default Float32 storage; Data declaration and function owners remain distinct, no standalone alias or Gen64 storage equivalence'
    if delay_rerun:
        result['rerun']=plan['rerun']
        result['scope']='Additive rerun of two original Delay declaration/read/write programs after the pinned bool-clamp repair; previous outcomes retained, no standalone method qualification'
    if event_family or plan.get('family')in(CONTEXT_ALIAS_FAMILY,MOTION_MEMBER_FAMILY):
        result['expected_block_storage']=plan['expected_block_storage']
        result['expected_reference_unique_blocks']=len(pool)
    if 'prepare_zero_warm_blocks' in plan:
        require(all(fields(line,'RNBO_SMOKE CASE ')['prepare_zero_warm_blocks']==str(plan['prepare_zero_warm_blocks'])
                    for line in case_lines),'Device preparation warmup differs from the plan')
        result['prepare_zero_warm_blocks']=plan['prepare_zero_warm_blocks']
    if 'admission_failures' in plan:
        result['admission_failures']=plan['admission_failures']
        result['summary']['admission_failures']=len(plan['admission_failures'])
        if plan.get('family')==LIST_FUNCTION_FAMILY:
            result['summary']['native_preflight_failures']=sum(r.get('stage')=='native-preflight'for r in plan['admission_failures'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.exists():raise SystemExit('Use a fresh result file')
    try:
        result=collect(args.build,args.run);args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_bytes(canonical(result));print(json.dumps(result['summary']))
    except (ValueError,KeyError,OSError)as exc:raise SystemExit(str(exc))
