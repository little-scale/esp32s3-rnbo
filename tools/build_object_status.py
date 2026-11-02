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
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PRIMARY_GROUPS={
    'patcher:mtof~':'mtof-fx-audio-v1',
    'patcher:reson~':'reson-fx-audio-v1',
    'patcher:cycle~':'cycle-scalar-hoist-strict',
    'patcher:comb~':'filters-scalar-v2-storage',
    'patcher:allpass~':'filters-scalar-v2-storage',
    'patcher:pink~':'pink-float32-output',
    'patcher:average~':'average-compact-history',
    'patcher:pow~':'scalar-powers-private'}
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
        if measure['CPU_savings_claimed']:
            require(not same,'An identical-artifact control cannot claim a gain')
            expected=100*(1-b/a)
            require(abs(number(measure['cpu_time_saved_percent'])-expected)<1e-10,'Incorrect saved-time percentage')
        else:require(measure['cpu_time_saved_percent'] is None,'Controls must have no saved-time percentage')
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


def public_sources(record,coverage,root):
    result={}
    for item in record.get('qualification',[])+record.get('optimisations',[]):
        source=item.get('source')
        if not source or not source.startswith(('docs/','evidence/')) or not (root/source).is_file():continue
        label=Path(source).stem.replace('-',' ')
        result[source]={'label':label,'url':PUBLIC_BASE+source}
    return list(result.values())


def make_status(inventory,coverage,root=ROOT):
    require(coverage['format']=='curated-RNBO-exact-spelling-status-mapping-v1','Unknown coverage format')
    require(coverage['merge_policy']['patcher_aliases_inherit'] is False and coverage['merge_policy']['codebox_inherits'] is False,'Coverage must not propagate through aliases')
    rows=inventory_rows(inventory);measurements=checked_measurements(coverage,root)
    seen=set()
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
        row['board_evidence']=working in ('board','in_patch','partial')
        options=record.get('optimisations',[])
        row['optimisation']={'status':opt,'label':OPT_LABELS[opt],
                             'short':next((o['flag'] for o in options if o.get('flag') and o.get('state')==opt),''),
                             'detail':' '.join(o['note'] for o in options)}
        row['sources']=public_sources(record,coverage,root)
        group=PRIMARY_GROUPS.get(identity)
        if group:
            selected=[m for m in measurements.values() if m['group_id']==group and m['case']=='aggregate']
            require(len(selected)==1,'Missing primary aggregate: '+identity)
            m=selected[0]
            require(m['id'] in record['cpu_measurement_ids'] and identity in m['primary_objects'],'Incorrect optimisation attribution')
            require(m['CPU_savings_claimed'] and not m['same_artifact_control'],'A primary result must be a paired optimisation')
            require(m['optimization_state'] in ('available','experimental'),'Unadmitted measurement state')
            percent=100*(1-m['candidate_process_us']/m['reference_process_us'])
            cases=[c for c in measurements.values() if c['group_id']==group and c['case']!='aggregate']
            case_text='; '.join(f"{c['case']}: {c['cpu_time_saved_percent']:.1f}%" for c in cases)
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
                      'coverage_public_revision':coverage['verified_public_revision']['sha'],
                      'measurement_count':len(measurements),'exact_coverage_entries':len(seen),
                      'primary_policy':'Representative matched aggregates, not best-case selection: explicit-input FX for mtof/reson, strict scalar hoist for cycle, combined filter/storage fixture, exact compact-average and pink-output fixtures, private scalar-powers fixture. Other results remain linked in source evidence.'}}


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
