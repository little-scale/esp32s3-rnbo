#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the public status table from a complete inventory and audited evidence.

Offline and deterministic: no RNBO installation, network, hardware or credentials
are needed. Exact spelling+surface is the join key; aliases inherit no status.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import struct
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PRIMARY_GROUPS={
    'patcher:dbtoa~':'dbtoa-float32-signal-v1',
    'patcher:mtof~':'mtof-fx-audio-v1',
    'patcher:reson~':'reson-fx-audio-v1',
    'patcher:cycle~':'cycle-scalar-hoist-strict',
    'patcher:comb~':'filters-scalar-v2-storage',
    'patcher:allpass~':'filters-scalar-v2-storage',
    'patcher:pink~':'pink-float32-output',
    'patcher:average~':'average-compact-history',
    'patcher:pow~':'scalar-powers-composed-original',
    'patcher:train~':'train-scalar-reciprocal-private',
    'patcher:wrap~':'finite-wrap-correction-bounded'}
WORKING_LABELS={'board':'Board verified','in_patch':'In a verified patch','native':'Native tests only',
                'partial':'Partial / known gaps','unverified':'Not yet verified','not_applicable':'Host / editor context'}
OPT_LABELS={'available':'Yes — available','experimental':'Experimental','none':'No measured change','unassessed':'Not assessed'}
PUBLIC_BASE='https://github.com/little-scale/esp32s3-rnbo/blob/main/'


def require(condition,message):
    if not condition:raise ValueError(message)


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def canonical(value):return (json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()


def pointer(value,selector):
    require(isinstance(selector,str) and selector.startswith('/'),'Expected an explicit JSON pointer')
    for part in selector.split('/')[1:]:
        part=part.replace('~1','/').replace('~0','~')
        value=value[int(part)] if isinstance(value,list) else value[part]
    return value


def number(value):
    require(type(value) in (int,float) and math.isfinite(value),'Expected a finite numeric measurement')
    return value


def checked_measurements(coverage,root):
    cache={};result={};groups={g['id']:g for g in coverage['measurement_groups']}
    for measure in coverage['measurements']:
        require(measure['id'] not in result,'Duplicate measurement ID')
        source=measure['source'];path=(root/source).resolve()
        require(source.startswith('evidence/') and '..' not in Path(source).parts and path.is_relative_to(root.resolve()) and path.is_file() and not (root/source).is_symlink(),'Measurement must reference public evidence')
        entry=coverage['sources'].get(source)
        require(entry is not None and digest(path)==entry['sha256'],'Evidence changed after status audit: '+source)
        if source not in cache:cache[source]=load(path)
        group=groups[measure['group_id']]
        require(source==group['source'] and measure['fixture']==group['fixture'],'Measurement group differs')
        admission_source=group.get('compiler_admission_source')
        if admission_source:
            admission_path=(root/admission_source).resolve()
            require(admission_source.startswith('evidence/') and '..' not in Path(admission_source).parts and
                    admission_path.is_relative_to(root.resolve()) and admission_path.is_file() and
                    not (root/admission_source).is_symlink(),'Compiler admission must reference public evidence')
            entry=coverage['sources'].get(admission_source)
            require(entry is not None and digest(admission_path)==entry['sha256'],'Compiler admission evidence changed')
            if admission_source not in cache:cache[admission_source]=load(admission_path)
            admission=cache[admission_source];identity=admission.get('module_identity',{})
            require(admission.get('compiler_admission') is True and admission.get('default_enabled') is False and
                    admission.get('option')==group.get('equivalent_public_option') and
                    identity.get('sha256')==measure['candidate_module_sha256'] and
                    identity.get('complete_ELF_bytes_equal_public_guarded_prototype_and_physical_original') is True,
                    'Compiler admission does not reproduce the measured image/option')
            reference_identity=admission.get('reference_identity')
            if reference_identity is not None:
                require(isinstance(reference_identity,dict) and
                        reference_identity.get('sha256')==measure['reference_module_sha256'] and
                        reference_identity.get('full_bytes_equal_current_runtime_private_and_physical_original') is True,
                        'Compiler admission reference differs from the measured image')
        fixture=pointer(cache[source],group['source_selector']);passed=fixture['pass']
        require(passed['strict_module_sha256']==measure['reference_module_sha256'] and
                passed['optimized_module_sha256']==measure['candidate_module_sha256'],'Module identity differs from measured evidence')
        for field,selector in measure['selectors'].items():
            require(pointer(cache[source],selector)==measure[field],'Timing selector differs: '+measure['id']+' '+field)
            number(measure[field])
        a=number(measure['reference_process_us']);b=number(measure['candidate_process_us'])
        require(a>0 and b>0,'Nonpositive process timing')
        require(measure['reference_timed_vectors']==measure['candidate_timed_vectors'] and measure['reference_timed_vectors']>0,'Unmatched timing coverage')
        same=measure['reference_module_sha256']==measure['candidate_module_sha256']
        require(same==measure['same_artifact_control'],'Artifact-control declaration differs')
        compared=measure.get('cpu_time_change_measured',measure['CPU_savings_claimed'])
        require(type(compared) is bool,'Expected explicit timing comparison status')
        if compared:
            require(not same,'An identical-artifact control cannot claim a gain')
            expected=100*(1-b/a)
            require(abs(number(measure['cpu_time_saved_percent'])-expected)<1e-10,'Incorrect saved-time percentage')
            if 'cpu_time_change_measured' in measure:
                require(type(measure['CPU_savings_claimed']) is bool and measure['CPU_savings_claimed']==(expected>0),'Saving claim differs from the signed measured change')
        else:require(measure['CPU_savings_claimed'] is False and measure['cpu_time_saved_percent'] is None,'Controls must have no savings claim or saved-time percentage')
        result[measure['id']]=measure
    return result


def base_row(identity,name,surface,category,reference=None,**extra):
    return {'id':identity,'name':name,'surface':surface,'category':category,'reference_url':reference,
            'aliases':[],'is_alias':False,'canonical_name':name,'board_evidence':False,
            'working':{'status':'unverified','label':WORKING_LABELS['unverified'],
                       'detail':'No qualifying result is recorded for this exact spelling and surface. Alias metadata does not transfer verification.'},
            'optimisation':{'status':'unassessed','label':OPT_LABELS['unassessed'],'detail':''},
            'performance':None,'sources':[],**extra}


def inventory_rows(inventory):
    require(inventory['contains_proprietary_implementation_bodies'] is False,'Inventory must contain metadata only')
    groups={row['id']:row for row in inventory['rows']};rows={}
    for spelling in inventory['spellings']:
        group=groups[spelling['canonical_id']];identity=spelling['id']
        require(identity not in rows,'Duplicate inventory spelling')
        rows[identity]=base_row(identity,spelling['name'],spelling['registry'],group['category'],spelling['reference_url'],
                               canonical_name=group['name'],aliases=group['aliases'],is_alias=spelling['is_alias'],inventory_group=group['id'])
    require(len(rows)==inventory['counts']['core_exact_spellings_installed1_4_4']==1209,'Incomplete core spelling inventory')
    supplemental=inventory['supplemental_codebox_surface']
    for entry in supplemental['stateful_public_members']:
        rows[entry['id']]=base_row(entry['id'],entry['owner']+'.'+entry['name']+'()','codebox','Stateful member',entry['reference_url'])
    for entry in supplemental['documented_list_methods']:
        rows[entry['id']]=base_row(entry['id'],'list.'+entry['name']+'()','codebox','List method',entry['reference_url'])
    for entry in supplemental['fixed_array_constructors']:
        rows[entry['id']]=base_row(entry['id'],entry['name'],'codebox','Fixed array constructor',entry['reference_url'])
        if entry.get('publication')=='installed_recognized_type_not_listed_in_official_guide':
            rows[entry['id']]['working']['detail']='Recognized by the installed RNBO 1.4.4 type registry, but not listed in the official fixed-array guide. Compiler admission and output behavior remain unverified.'
    for entry in supplemental['documented_lifecycle_functions']:
        rows[entry['id']]=base_row(entry['id'],entry['name']+'()','codebox','Lifecycle hook',entry['reference_url'])
    for entry in inventory['reference_only_rows']:
        rows[entry['id']]=base_row(entry['id'],entry['name'],'codebox','Reference only',entry['reference_url'])
        rows[entry['id']]['working']['detail']=entry['note']+' Its version and compiler coverage remain unverified.'
    distinct=inventory['excluded_or_distinct_surfaces']
    for entry in distinct['max_host_objects']:
        rows[entry['id']]=base_row(entry['id'],entry['name'],'host','Max host wrapper',entry['reference_url'])
        rows[entry['id']]['working']={'status':'not_applicable','label':WORKING_LABELS['not_applicable'],'detail':entry['note']}
    for entry in distinct['max_serialization_classes']:
        identity='serialization-class:'+entry['name']
        rows[identity]=base_row(identity,entry['name'],'host','Saved editor class')
        rows[identity]['working']={'status':'not_applicable','label':WORKING_LABELS['not_applicable'],'detail':entry['meaning']+' This is not an additional DSP operator.'}
    return rows


def checked_boundary_events(case,data):
    """Validate collected boundary-control observations, without importing tooling."""
    valid_sha=lambda value:type(value)is str and re.fullmatch('[0-9a-f]{64}',value)is not None
    require(type(data.get('prepare_zero_warm_blocks'))is int and data['prepare_zero_warm_blocks']==0 and
            data.get('expected_block_storage')=='shared-512-word-pool'and type(data.get('expected_stream_policy'))is str and
            type(case.get('expected_block_count'))is int and case['expected_block_count']==20 and valid_sha(case.get('expected_stream_sha256')),
            'Boundary smoke requires its fresh twenty-block reference')
    count=case.get('parameter_count');parameters=case.get('parameters');events=case.get('parameter_events')
    require(type(count)is int and 1<=count<=32 and type(parameters)is list and len(parameters)==count and
            valid_sha(case.get('parameter_schema_sha256')),'Boundary parameter schema/count differs')
    identities=set()
    for parameter in parameters:
        require(type(parameter)is dict and set(parameter)=={'id','minimum','maximum','initial','exponent','steps'},'Invalid boundary parameter contract')
        identity=parameter['id']
        require(type(identity)is str and re.fullmatch('[A-Za-z0-9_.-]{1,191}',identity)is not None and identity not in identities,
                'Boundary parameter ID differs')
        identities.add(identity)
        minimum,maximum,initial,exponent=(number(parameter[k])for k in ('minimum','maximum','initial','exponent'))
        require(all(abs(v)<=3.4028234663852886e38 and struct.unpack('<f',struct.pack('<f',v))[0]==v for v in (minimum,maximum,initial,exponent)),
                'Boundary parameter contract must be binary32')
        require(minimum<maximum and minimum<=initial<=maximum and exponent==1 and type(parameter['steps'])is int and parameter['steps']==0,
                'Boundary parameter must be linear and unstepped')
    require(type(events)is list and len(events)==21 and type(case.get('parameter_events_applied'))is int and case['parameter_events_applied']==21,
            'Boundary smoke requires twenty-one observed actions')
    resolved={};indices={};last_call=0;total=0;peak=0
    event_keys={'ordinal','before_call','id','parameter_slot','resolved_index','value_word','actual_word','normalized_word',
                'expected_normalized_word','event_us','actual_zero_sign_difference','normalized_zero_sign_difference'}
    same_word=lambda a,b:a==b or ((a|b)&0x7fffffff)==0
    for ordinal,event in enumerate(events):
        require(type(event)is dict and set(event)==event_keys,'Boundary event fields differ')
        require(type(event['ordinal'])is int and event['ordinal']==ordinal and type(event['before_call'])is int and
                last_call<=event['before_call']<20,'Boundary action order/call differs')
        last_call=event['before_call'];slot=event['parameter_slot'];index=event['resolved_index']
        require(type(slot)is int and 0<=slot<count and event['id']==parameters[slot]['id']and type(index)is int and 0<=index<count and
                resolved.get(slot,index)==index and indices.get(index,slot)==slot,'Boundary parameter slot/ID resolution differs')
        resolved[slot]=index;indices[index]=slot
        for key in ('value_word','actual_word','normalized_word','expected_normalized_word'):
            require(type(event[key])is int and 0<=event[key]<=0xffffffff and(event[key]&0x7f800000)!=0x7f800000,'Boundary parameter word is invalid')
        value=struct.unpack('<f',struct.pack('<I',event['value_word']))[0];parameter=parameters[slot]
        require(parameter['minimum']<=value<=parameter['maximum'],'Boundary parameter value exceeds bounds')
        expected_normalized=struct.unpack('<I',struct.pack('<f',(value-parameter['minimum'])/(parameter['maximum']-parameter['minimum'])))[0]
        require(event['expected_normalized_word']==expected_normalized and same_word(event['actual_word'],event['value_word'])and
                same_word(event['normalized_word'],expected_normalized),'Boundary actual/normalized readback differs')
        for flag,actual,expected in (('actual_zero_sign_difference',event['actual_word'],event['value_word']),
                                     ('normalized_zero_sign_difference',event['normalized_word'],expected_normalized)):
            require(type(event[flag])is bool and event[flag]==(actual!=expected),'Boundary readback zero-sign diagnostic differs')
        require(type(event['event_us'])is int and 0<=event['event_us']<=1000000000,'Boundary event duration differs')
        total+=event['event_us'];peak=max(peak,event['event_us'])
    require(type(case.get('event_total_us'))is int and case['event_total_us']==total and type(case.get('event_peak_us'))is int and
            case['event_peak_us']==peak,'Boundary event timing totals differ')
    require(case.get('parameter_event_scope')=='Actual TimeNow controls before full256-frame callbacks; no within-block event offsets'and
            case.get('event_timing_scope')=='Wrapper/setter/routing callback only; readbacks and logging excluded, not isolated opcode cost',
            'Boundary event scope differs')
    return {key:case[key]for key in ('parameter_count','parameter_schema_sha256','parameter_events_applied','event_total_us','event_peak_us',
            'expected_block_count','expected_stream_sha256','strict_zero_sign_channels','strict_zero_sign_mismatches','parameter_event_scope','event_timing_scope')}


def container_identity(case):
    """Supplemental list members and types retain their own inventory IDs."""
    identity=case.get('registry_lookup','');name=case.get('exact_name','')
    members={'push','pop','shift','concat','fill','unshift','splice','slice','includes','indexOf','reverse'}
    constructors={'FixedInt8Array','FixedUint8Array','FixedInt16Array','FixedUint16Array','FixedInt32Array',
                  'FixedUint32Array','FixedFloat32Array','FixedFloat64Array','FixedBigInt64Array','FixedBigUint64Array',
                  'FixedSampleArray','FixedNumberArray','FixedIntArray','FixedFloatArray','FixedDoubleArray','FixedUIntArray','FixedTimeArray'}
    if identity.startswith('codebox-list-member:'):
        member=identity.split(':',1)[1]
        require(member in members and name=='list.'+member+'()'and case.get('syntax')=='list-member-call',
                'Container list member identity differs')
    else:
        require(identity=='codebox-constructor:'+name and name in constructors and
                case.get('syntax')=='fixed-array-constructor','Container constructor identity differs')
    return identity


def lifecycle_identity(case):
    """Only the three exact documented hooks join existing inventory rows."""
    identity=case.get('registry_lookup');name=case.get('exact_name')
    require(name in ('init()','startup()','dspsetup()') and
            identity=='codebox-hook:'+name[:-2] and case.get('syntax')=='lifecycle-hook',
            'Lifecycle hook identity differs')
    return identity


def stateful_member_identity(case):
    """Exact member calls retain owner-specific supplemental IDs."""
    identity=case.get('registry_lookup','');name=case.get('exact_name','')
    require(type(identity)is str and identity.startswith('codebox-member:'),'Missing stateful member identity')
    member=identity.split(':',1)[1];parts=member.split('.')
    owners={'delta','change','latch','sah','slide','dcblock','accum','counter','deltaclip',
            'downsamp','zerox','zerox_count','onepole','onepole_lin','biquad','elapsed'}
    allowed=(len(parts)==2 and ((parts[0]in owners and parts[1]in('next','reset'))or
             (parts[0]in('onepole','onepole_lin','biquad')and parts[1]=='clear')or member=='history.reset'))
    require(allowed and name==member+'()'and case.get('syntax')=='stateful-member-call','Stateful member identity differs')
    return identity


def delay_member_identity(case):
    identity=case.get('registry_lookup','');name=case.get('exact_name','')
    allowed={'delay':{'next','clear','reset','read','write','step','size'},
             'comb':{'next','clear','reset'},'allpass':{'next','clear','reset'}}
    require(type(identity)is str and identity.startswith('codebox-member:'),'Missing delay member identity')
    member=identity.split(':',1)[1];parts=member.split('.')
    require(len(parts)==2 and parts[0]in allowed and parts[1]in allowed[parts[0]]and
            name==member+'()'and case.get('syntax')=='stateful-member-call','Delay member identity differs')
    return identity


def checked_short_smoke(record,item,data):
    """A short exact-spelling hardware observation, with no gain attribution."""
    codebox=data.get('family')in('rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-codebox-list-functions','rnbo-character-constants')
    surface='codebox'if codebox else'patcher'
    require(data.get('format')=='rnbo-hardware-smoke-results-v1' and data.get('board')=='xiao' and
            data.get('family') in ('rnbo-stateless','rnbo-numeric','rnbo-functions','rnbo-constants','rnbo-signal-range','rnbo-signal-stateful','rnbo-signal-state-followup','rnbo-signal-routing','rnbo-events','rnbo-events-extra','rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-codebox-list-functions','rnbo-character-constants') and data.get('surface')==surface and
            data.get('test_level')=='short-functional-hardware-check' and data.get('full_qualification_claimed') is False,
            'Short smoke board/surface/test scope differs')
    if data.get('family')in('rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-codebox-list-functions','rnbo-character-constants'):
        require(type(data.get('prepare_zero_warm_blocks'))is int and data['prepare_zero_warm_blocks']==0,
                'Codebox numeric domains require zero automatic preparation blocks')
    if data.get('family')in('rnbo-signal-range','rnbo-signal-stateful','rnbo-signal-state-followup','rnbo-signal-routing'):
        require(type(data.get('prepare_zero_warm_blocks'))is int and data['prepare_zero_warm_blocks']==0,
                'Signal range domains require zero automatic preparation blocks')
    selector=item.get('selector','')
    require(type(selector)is str and selector.startswith('/cases/') and selector[7:].isdigit(),'Short smoke selector must name an executed case')
    cases=data.get('cases');require(type(cases)is list and int(selector[7:])<len(cases),'Short smoke selector is outside executed cases')
    case=pointer(data,selector)
    expected_id=container_identity(case) if data.get('family')=='rnbo-codebox-containers' else lifecycle_identity(case) if data.get('family')=='rnbo-codebox-structures' else stateful_member_identity(case) if data.get('family')=='rnbo-codebox-members' else delay_member_identity(case) if data.get('family')=='rnbo-codebox-delay-members' else surface+':'+case.get('exact_name','')
    require(record['surface']==surface and record['id']==expected_id and
            record['spelling']==case.get('exact_name'),'Short smoke exact spelling/surface differs')
    require(case.get('status') in ('pass','output_mismatch') and case.get('finalized') is True and
            type(case.get('samples_checked')) is int and case['samples_checked']==10240,
            'Short smoke case did not complete the declared scenario')
    bits,zeros=case.get('bit_mismatches'),case.get('zero_sign_differences')
    require(type(bits)is int and type(zeros)is int and 0<=zeros<=bits<=case['samples_checked'],
            'Short smoke output status/counters differ')
    code_fields={}
    if codebox:
        code_sha=case.get('codebox_source_sha256')
        require(type(code_sha)is str and len(code_sha)==64 and all(c in '0123456789abcdef'for c in code_sha),
                'Codebox smoke requires an authored program identity')
        code_fields['codebox_source_sha256']=code_sha
    stream_fields={}
    if data.get('family')in('rnbo-codebox-stateful','rnbo-codebox-filters','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-signal-stateful','rnbo-signal-state-followup'):
        policy=('Fresh prepared signal state; twenty continuous256-frame callbacks without resets'if data['family']in('rnbo-signal-stateful','rnbo-signal-state-followup')else
                'Fresh prepared member state; twenty continuous256-frame callbacks with only authored in-program member reset/clear calls'if data['family']=='rnbo-codebox-members'else
                'Fresh prepared resource member state; twenty continuous256-frame callbacks with only authored in-program clear/reset calls'if data['family']=='rnbo-codebox-delay-members'else
                'Fresh prepared codebox state; twenty continuous256-frame callbacks without resets')
        stream_sha=case.get('expected_stream_sha256')
        require(type(case.get('expected_block_count'))is int and case['expected_block_count']==20 and
                type(stream_sha)is str and len(stream_sha)==64 and all(c in '0123456789abcdef'for c in stream_sha)and
                data.get('expected_stream_policy')==policy,
                'Stateful codebox requires its full continuous reference stream')
        stream_fields={'expected_block_count':20,'expected_stream_sha256':stream_sha,
                       'expected_stream_policy':data['expected_stream_policy']}
    numeric_keys={'numeric_mismatches','within_tolerance_differences','nonfinite_outputs',
                  'max_absolute_error','absolute_tolerance','input_words_sha256'}
    present=numeric_keys.intersection(case);numeric={}
    boundary=data.get('family')in('rnbo-events','rnbo-events-extra');event_fields={};strict=0
    character=data.get('family')=='rnbo-character-constants'
    if character:
        partition=data.get('partition',{});index=partition.get('index')
        require(type(index)is int and index in(1,2) and type(partition.get('total'))is int and partition['total']==2 and
                type(partition.get('case_count'))is int and partition['case_count']==len(cases)==(43 if index==1 else 42) and
                type(partition.get('parent_catalog_sha256'))is str and
                re.fullmatch('[0-9a-f]{64}',partition['parent_catalog_sha256'])is not None,
                'Character constant partition is invalid')
        require(case.get('syntax')=='named-value' and case['exact_name'].startswith('CHAR_')and
                type(case.get('ascii_decimal'))is int and 32<=case['ascii_decimal']<=126 and
                case.get('codebox_inlet_names')==['in2']and
                type(case.get('codebox_pilot_inlet_ordinal'))is int and case['codebox_pilot_inlet_ordinal']==0,
                'Character constant requires its bare-value and single-pilot source form')
        require(type(data.get('strict_zero_sign_channels'))is int and data['strict_zero_sign_channels']==2 and
                type(data.get('raw_pilot_channel'))is int and data['raw_pilot_channel']==1 and
                type(case.get('strict_zero_sign_channels'))is int and case['strict_zero_sign_channels']==2 and
                type(case.get('raw_pilot_channel'))is int and case['raw_pilot_channel']==1 and
                type(case.get('strict_zero_sign_mismatches'))is int and case['strict_zero_sign_mismatches']>=0,
                'Character constant requires a strict right pilot')
        strict=case['strict_zero_sign_mismatches']
        event_fields={key:case[key]for key in('strict_zero_sign_channels','strict_zero_sign_mismatches','raw_pilot_channel')}
    if boundary:
        require(type(case.get('strict_zero_sign_channels'))is int and case['strict_zero_sign_channels']==2 and
                type(case.get('strict_zero_sign_mismatches'))is int and case['strict_zero_sign_mismatches']>=0,
                'Boundary smoke requires strict right zero signs')
        strict=case['strict_zero_sign_mismatches']
        event_fields=checked_boundary_events(case,data)
    require((not present or present==numeric_keys)and(data.get('family')not in('rnbo-numeric','rnbo-functions','rnbo-constants','rnbo-signal-range','rnbo-signal-stateful','rnbo-signal-state-followup','rnbo-signal-routing','rnbo-events','rnbo-events-extra','rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-codebox-list-functions','rnbo-character-constants')or present==numeric_keys),
            'Short numeric smoke fields must be complete')
    if present:
        mismatches,within,nonfinite=(case[key]for key in ('numeric_mismatches','within_tolerance_differences','nonfinite_outputs'))
        require(all(type(v)is int and v>=0 for v in (mismatches,within,nonfinite))and
                mismatches==bits-zeros-within and nonfinite+strict<=mismatches,
                'Short numeric smoke mismatch categories differ')
        tolerance=number(case['absolute_tolerance']);maximum=number(case['max_absolute_error'])
        # Float32(1e-3) is slightly greater than decimal1e-3. Only this
        # new unit-aware/approximation family may use that larger ceiling.
        maximum_tolerance=0.0010000000474974513 if data['family']in('rnbo-functions','rnbo-signal-range','rnbo-codebox-range','rnbo-codebox-shaping','rnbo-codebox-misc')else 2e-6
        require(0<=tolerance<=maximum_tolerance and maximum>=0 and(not within or tolerance>0),
                'Short numeric smoke tolerance/error is invalid')
        require((mismatches==0 and maximum<=tolerance)or
                (mismatches>0 and(mismatches==nonfinite+strict or maximum>tolerance)),
                'Short numeric smoke finite error contradicts its gate')
        input_sha=case['input_words_sha256']
        require(type(input_sha)is str and len(input_sha)==64 and all(c in '0123456789abcdef'for c in input_sha),
                'Short numeric smoke input identity is invalid')
        numeric={key:case[key]for key in numeric_keys}
        if boundary or character:require(tolerance==0,'Boundary/character smoke requires zero absolute tolerance')
    else:mismatches=bits-zeros
    require((case['status']=='pass')==(mismatches==0),'Short smoke output status/counters differ')
    times=case.get('times_us')
    require(type(times)is list and len(times)==16 and all(type(t)is int and t>=0 for t in times),
            'Short smoke requires sixteen raw callback times')
    ordered=sorted(times);mean=number(case.get('mean_us'));median=number(case.get('median_us'));peak=number(case.get('peak_us'))
    require(abs(mean-sum(times)/16)<=1e-6 and median==(ordered[7]+ordered[8])/2 and peak==max(times),
            'Short smoke absolute timing summary differs')
    require(type(case.get('context_bytes'))is int and case['context_bytes']>0 and
            type(case.get('arena_high_water'))is int and case['arena_high_water']>=0,
            'Short smoke resource observation is invalid')
    resource={}
    require(data['family']!='rnbo-functions'or 'arena_capacity'in case,'Function smoke must report reserved arena capacity')
    if 'arena_capacity'in case:
        capacity=case['arena_capacity']
        require(type(capacity)is int and capacity>0 and case['arena_high_water']<=capacity,
                'Short smoke arena high-water exceeds its reserved capacity')
        resource={'arena_capacity':capacity,'arena_high_water':case['arena_high_water']}
    reasons=case.get('cpu_review_reasons');expected=[]
    if median>.1*256000000/44100:expected.append('median_budget')
    if peak>max(3*median,median+100):expected.append('peak_spike')
    require(reasons==expected,'Short smoke CPU review reasons differ')
    return {**numeric,**resource,**event_fields,**code_fields,**stream_fields,'case':case['id'],'status':case['status'],'reference_policy':case.get('reference_policy'),
            'mean_us':mean,'median_us':median,'peak_us':peak,'cpu_review_reasons':reasons,
            'samples_checked':case['samples_checked'],'test_level':'short-functional-hardware-check',
            'full_qualification_claimed':False,'cpu_time_saved_percent':None,
            'evidence_url':PUBLIC_BASE+item['source']}


def checked_codebox_build_failure(record,item,data):
    """Keep a rejected exact codebox form visible without hardware qualification."""
    require(data.get('format')=='rnbo-hardware-smoke-results-v1'and
            data.get('family')in('rnbo-codebox','rnbo-codebox-constants','rnbo-codebox-numeric','rnbo-codebox-range','rnbo-codebox-stateful','rnbo-codebox-shaping','rnbo-codebox-filters','rnbo-codebox-misc','rnbo-codebox-containers','rnbo-codebox-structures','rnbo-codebox-members','rnbo-codebox-delay-members','rnbo-codebox-list-functions','rnbo-character-constants')and data.get('surface')=='codebox',
            'Codebox build failure requires its own source surface')
    selector=item.get('selector','');parts=selector.split('/')if type(selector)is str else[]
    require(len(parts)==3 and parts[0]==''and parts[1]in('compile_failures','admission_failures')and parts[2].isdigit(),
            'Codebox build failure selector differs')
    failure=pointer(data,selector)
    expected_id=container_identity(failure) if data.get('family')=='rnbo-codebox-containers' else lifecycle_identity(failure) if data.get('family')=='rnbo-codebox-structures' else stateful_member_identity(failure) if data.get('family')=='rnbo-codebox-members' else delay_member_identity(failure) if data.get('family')=='rnbo-codebox-delay-members' else 'codebox:'+failure.get('exact_name','')
    require(record.get('surface')=='codebox'and record.get('id')==expected_id and
            record.get('spelling')==failure.get('exact_name')and record.get('working_state')=='unverified'and
            record.get('board_evidence')is False and not record.get('cpu_measurement_ids')and
            record.get('optimisation_state')=='unassessed'and not record.get('optimisations'),
            'Build rejection must not qualify device execution or optimisation')
    native=data.get('family')=='rnbo-codebox-list-functions'and failure.get('status')=='native_preflight_failed'
    if native:
        require(parts[1]=='admission_failures' and failure.get('stage')=='native-preflight' and
                failure.get('returncode')==3 and type(failure.get('native_process_status'))is int and
                failure['native_process_status']<0 and type(failure.get('native_fault_call'))is int and
                0<=failure['native_fault_call']<20 and failure.get('native_samples_checked')==failure['native_fault_call']*512,
                'Native fault must not claim target execution')
    require(native or failure.get('status')==('compile_failed'if parts[1]=='compile_failures'else'export_failed'),
            'Codebox rejection stage differs')
    for key in ('source_sha256','codebox_source_sha256',
                'compile_log_sha256'if parts[1]=='compile_failures'else'failure_log_sha256'):
        digest=failure.get(key)
        require(type(digest)is str and len(digest)==64 and all(c in '0123456789abcdef'for c in digest),
                'Codebox rejected source/log identity is missing')


def public_sources(record,coverage,root,evidence_cache=None):
    if evidence_cache is None:evidence_cache={}
    result={}
    for item in record.get('qualification',[])+record.get('optimisations',[]):
        source=item.get('source')
        if source and source.startswith('evidence/'):
            path=(root/source).resolve()
            require('..' not in Path(source).parts and path.is_relative_to(root.resolve()) and
                    path.is_file() and not (root/source).is_symlink(),'Qualification evidence must be a public regular file')
            entry=coverage['sources'].get(source)
            require(entry is not None and digest(path)==entry['sha256'],'Qualification evidence changed: '+source)
            if item.get('evidence_kind')=='rnbo-codebox-build-failure':
                if source not in evidence_cache:evidence_cache[source]=load(path)
                checked_codebox_build_failure(record,item,evidence_cache[source])
            if item.get('evidence_kind')=='xiao-rnbo-short-smoke':
                if source not in evidence_cache:evidence_cache[source]=load(path)
                checked_short_smoke(record,item,evidence_cache[source])
            if item.get('evidence_kind')=='xiao-wave4-model-output':
                if source not in evidence_cache:evidence_cache[source]=load(path)
                data=evidence_cache[source];observation=pointer(data,item['selector'])
                require(data.get('format')=='rnbo-xiao-wave4-hardware-observations' and
                        data.get('Gen_qualification_claimed') is False and
                        observation.get('independent_on_device_oracle') is True and
                        record['id'] in observation['exact_surface']['exact_entries'] and
                        observation['exact_surface']['surface']==record['surface'],
                        'XIAO qualification selector differs from the exact source/surface')
                passed=observation['collected']['pass'];aggregate=data['target_aggregate']
                require(observation['collected']['board']=='xiao' and passed['semantic_sample_checks']>0 and
                        passed['wave4_bit_sample_checks']==passed['semantic_sample_checks'] and
                        passed['wave4_bit_differences']==passed['observer_bit_differences']==0 and
                        aggregate['maximum_numerical_model_error']==0 and
                        aggregate['all_restorations_verified'] is True and
                        observation['CPU_savings_claimed'] is False and observation['cpu_time_saved_percent'] is None,
                        'XIAO scoped output-model or recovery evidence differs')
        if not source or not source.startswith(('docs/','evidence/')) or not (root/source).is_file():continue
        label=Path(source).stem.replace('-',' ')
        label+=' — documentation' if source.startswith('docs/') else ' — evidence'
        result[source]={'label':label,'url':PUBLIC_BASE+source}
    return list(result.values())


def checked_experimental_compiler_option(option,coverage,root):
    source=option['compiler_admission_source'];path=(root/source).resolve()
    require(source.startswith('evidence/') and '..' not in Path(source).parts and
            path.is_relative_to(root.resolve()) and path.is_file() and not (root/source).is_symlink(),
            'Experimental compiler admission must reference public evidence')
    entry=coverage['sources'].get(source)
    require(entry is not None and digest(path)==entry['sha256'],'Experimental compiler admission evidence changed')
    admission=load(path)
    require(isinstance(option.get('flag'),str) and option['flag'].startswith('--') and
            option['state']=='experimental' and admission.get('compiler_admission') is True and
            admission.get('default_enabled') is False and admission.get('experimental') is True and
            admission.get('target_execution') is False and admission.get('option')==option.get('flag'),
            'Experimental compiler admission scope or option differs')
    for label,field in (('module_identity','candidate_module_sha256'),('reference_identity','reference_module_sha256')):
        identity=admission.get(label,{})
        expected=option.get(field)
        require(isinstance(identity,dict) and isinstance(expected,str) and len(expected)==64 and all(c in '0123456789abcdef' for c in expected) and
                identity.get('sha256')==expected and identity.get('complete_ELF_bytes_equal_public_and_private_prototype') is True,
                'Experimental compiler admission module identity differs')


def make_status(inventory,coverage,root=ROOT):
    require(coverage['format']=='curated-RNBO-exact-spelling-status-mapping-v1','Unknown coverage format')
    require(coverage['merge_policy']['patcher_aliases_inherit'] is False and coverage['merge_policy']['codebox_inherits'] is False,'Coverage must not propagate through aliases')
    rows=inventory_rows(inventory);measurements=checked_measurements(coverage,root)
    seen=set();qualification_cache={}
    for record in coverage['objects']:
        identity=record['id'];require(identity in rows and identity not in seen,'Unknown or repeated coverage identity: '+identity);seen.add(identity)
        row=rows[identity];require(row['name']==record['spelling'],'Coverage spelling differs')
        require(record['aliases_inherit_status'] is False,'Alias inheritance is forbidden')
        working=record['working_state'];opt=record['optimisation_state']
        require(working in WORKING_LABELS and opt in OPT_LABELS,'Unknown status')
        gaps=record.get('known_gaps',[])
        detail=record['working_note']
        conditions=[item['conditions'] for item in record.get('qualification',[]) if item.get('conditions')]
        if conditions:detail+=' '+ ' '.join(conditions)
        if gaps:detail+=' Remaining scope: '+' '.join(gaps)
        row['working']={'status':working,'label':WORKING_LABELS[working],'detail':detail,
                        'short':'Tested modes only' if working=='board' else 'Composition coverage' if working=='in_patch' else 'Open scope / accuracy checks' if working=='partial' else 'Not a board qualification'}
        if working=='partial':
            require(type(record.get('board_evidence')) is bool,'Partial qualification requires explicit board-evidence location')
            require(not record['board_evidence'] or any(q.get('level','').startswith('S3-') for q in record.get('qualification',[])),
                    'Native-only partial qualification cannot claim board evidence')
            row['board_evidence']=record['board_evidence']
        else:row['board_evidence']=working in ('board','in_patch')
        options=record.get('optimisations',[])
        for option in options:
            if option.get('compiler_admission_source'):
                checked_experimental_compiler_option(option,coverage,root)
        row['optimisation']={'status':opt,'label':OPT_LABELS[opt],
                             'short':next((o['flag'] for o in options if o.get('flag') and o.get('state')==opt),''),
                             'detail':' '.join(o['note'] for o in options)}
        row['sources']=public_sources(record,coverage,root,qualification_cache)
        smoke=[checked_short_smoke(record,item,qualification_cache[item['source']])
               for item in record.get('qualification',[])if item.get('evidence_kind')=='xiao-rnbo-short-smoke']
        if smoke:
            row['hardware_smoke']=smoke
            for observation in smoke:
                row['working']['detail']+=f" Short XIAO check ({observation['status']}): one repeated stereo vector; mean {observation['mean_us']:.2f}µs, median {observation['median_us']:.2f}µs, peak {observation['peak_us']:.0f}µs."
                if 'absolute_tolerance'in observation:
                    row['working']['detail']+=f" Declared absolute tolerance {observation['absolute_tolerance']:.9g}; maximum finite error {observation['max_absolute_error']:.9g}; within-tolerance differences {observation['within_tolerance_differences']}; numeric mismatches {observation['numeric_mismatches']}; nonfinite outputs {observation['nonfinite_outputs']}."
                if 'arena_capacity'in observation:
                    row['working']['detail']+=f" Arena reserved {observation['arena_capacity']:,} bytes; observed high-water {observation['arena_high_water']:,} bytes."
                if 'parameter_events_applied'in observation:
                    row['working']['detail']+=f" {observation['parameter_events_applied']} parameter events with actual/normalized readbacks; setter/routing total {observation['event_total_us']}µs, peak {observation['event_peak_us']}µs, separate from callback times. Controls apply before full 256-frame callbacks; no within-block timing or isolated-opcode cost is claimed. Right pilot zero signs are strict ({observation['strict_zero_sign_mismatches']} mismatches)."
                if observation['cpu_review_reasons']:row['working']['detail']+=' Callback timing flagged for later review.'
        if record.get('working_test_level')=='short-functional-hardware-check':
            require(smoke and working in ('board','partial'),'Short smoke label requires a bound hardware scenario')
            require((working=='board' and all(item['status']=='pass'for item in smoke))or
                    (working=='partial' and any(item['status']=='output_mismatch'for item in smoke)),
                    'Short smoke working label differs from observed output status')
            row['working']['label']='Short hardware check' if working=='board' else 'Short check / known gaps'
            row['working']['short']='One short hardware scenario' if working=='board' else 'Short hardware mismatch'
            row['working']['test_level']='short-functional-hardware-check'
        group=PRIMARY_GROUPS.get(identity)
        if group:
            selected=[m for m in measurements.values() if m['group_id']==group and m['case']=='aggregate']
            require(len(selected)==1,'Missing primary aggregate: '+identity)
            m=selected[0]
            require(m['id'] in record['cpu_measurement_ids'] and identity in m['primary_objects'],'Incorrect optimisation attribution')
            require(m.get('cpu_time_change_measured',m['CPU_savings_claimed']) and not m['same_artifact_control'],'A primary result must be a paired change')
            require(m['optimization_state'] in ('available','experimental'),'Unadmitted measurement state')
            percent=100*(1-m['candidate_process_us']/m['reference_process_us'])
            cases=[c for c in measurements.values() if c['group_id']==group and c['case']!='aggregate']
            case_text='; '.join(f"{c['case']}: {c['cpu_time_saved_percent']:.1f}%"
                               if c['cpu_time_saved_percent'] is not None else f"{c['case']}: control (no gain claimed)"
                               for c in cases)
            row['performance']={'percent':percent,'label':f'{percent:.1f}%',
                'phase':m['optimization_state'],'scope':'Combined filter fixture' if identity in ('patcher:comb~','patcher:allpass~') else 'Scalar cycle fixture' if identity=='patcher:cycle~' else 'Whole test patch',
                'measurement_id':m['id'],'detail':f"{m['attribution']} Reference: {m['reference_profile']}; candidate: {m['candidate_profile']}. Aggregate matched process times: {m['reference_process_us']:,}→{m['candidate_process_us']:,}µs over {m['reference_timed_vectors']:,} vectors per profile. Cases: {case_text}.",
                'evidence_url':PUBLIC_BASE+m['source']}
            if not any(s['url']==PUBLIC_BASE+m['source'] for s in row['sources']):row['sources'].append({'label':'Measured timing evidence','url':PUBLIC_BASE+m['source']})
    snapshot=datetime.strptime(coverage['snapshot_date'],'%Y-%m-%d')
    return {'schema_version':1,'rnbo_version':inventory['rnbo_version'],
        'evidence_updated':f'{snapshot.day} {snapshot:%b %Y}',
        'inventory_summary':'1,209 registered spellings, plus registry/guide codebox members, types and hooks. Host/editor context is listed separately.',
        'scope_note':'Pinned to RNBO 1.4.4. The 974 core groups expand to 1,209 registered spellings; 238 registry/guide member/type/hook entries, one unversioned reference-only entry and 7 host/editor entries are additionally shown. Two array types are recognized locally but absent from the official guide; their details flag this. Internal compiler helpers, arbitrary user-defined names, custom packages and full Gen/language grammar are separate. Listing a name does not establish compiler admission or complete mode coverage.',
        'inventory_sources':[{'label':'RNBO object reference','url':'https://rnbo.cycling74.com/objects?v=1.4.4'},
                             {'label':'Codebox reference','url':'https://rnbo.cycling74.com/codebox'},
                             {'label':'Inventory provenance','url':PUBLIC_BASE+'site/data/inventory.json'}],
        'objects':sorted(rows.values(),key=lambda r:(r['name'].lower(),r['surface'],r['id'])),
        'provenance':{'inventory_canonical_sha256':hashlib.sha256(canonical(inventory)).hexdigest(),
                      'coverage_canonical_sha256':hashlib.sha256(canonical(coverage)).hexdigest(),
                      'initial_coverage_public_revision':coverage['verified_public_revision']['sha'],
                      'later_evidence_policy':'Later additions are included with this snapshot and individually bound to public evidence content hashes; the initial revision identifies the original audited source set.',
                      'measurement_count':len(measurements),'exact_coverage_entries':len(seen),
                      'primary_policy':'Representative matched aggregates, not best-case selection: explicit-input FX for mtof/reson, strict scalar hoist for cycle, combined filter/storage fixture, exact compact-average and pink-output fixtures, composed scalar powers on the original three-case grid, all12 private train workloads including bypass controls, and the bounded nonlinear callback for the finite-wrap correction. Expanded power workloads remain separately linked. Negative percentages record extra CPU time. Other results remain linked in source evidence.'}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Fail when the committed status table is stale')
    parser.add_argument('--out',type=Path,default=ROOT/'site/data/status.json')
    args=parser.parse_args()
    data=make_status(load(ROOT/'site/data/inventory.json'),load(ROOT/'site/data/coverage.json'))
    data['provenance']['inventory_source_sha256']=digest(ROOT/'site/data/inventory.json')
    data['provenance']['coverage_source_sha256']=digest(ROOT/'site/data/coverage.json')
    data['provenance']['generator_sha256']=digest(Path(__file__))
    encoded=canonical(data)
    if args.check:require(args.out.is_file() and args.out.read_bytes()==encoded,'Status table is stale; run tools/build_object_status.py')
    else:args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_bytes(encoded)
    print(json.dumps({'objects':len(data['objects']),'covered_exact_spellings':data['provenance']['exact_coverage_entries'],'output':str(args.out)}))


if __name__=='__main__':main()
