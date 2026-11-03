#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build an isolated, catalog-bound strict/optimized RNBO object comparator.

No device access. Both native modules must already have verified build reports.
The default inputs are the milestone-2 object qualification artifacts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

from build_rnbo_loader_test import module_input
from build_loader_spike import inventory, tree_digest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host/compiler"))
from prepare import ExportError, NUMERICAL_PROFILES, read_json, read_regular
from gen_arithmetic_contract import KIND as GEN_ARITH_KIND, FORMAT as GEN_ARITH_FORMAT, benchmark_fixture as gen_arith_fixture, verification as gen_arith_verification, admit_module as gen_arith_admit_module
from gen_history_contract import KIND as GEN_KIND, INPUT as GEN_INPUT, FORMAT as GEN_FORMAT, OPT_FORMAT as GEN_OPT_FORMAT, OPT_MODE as GEN_OPT_MODE, FIXTURES as GEN_FIXTURES, benchmark_fixture as gen_fixture, verification as gen_verification, admit_module as gen_admit_module, witness_sha256 as gen_witness_sha
from wave4_contract import KIND as WAVE4_KIND, INPUTS as WAVE4_INPUTS, benchmark_fixture as wave4_fixture, verification as wave4_verification, admit_module as wave4_admit_module

_WAVE2_IDENTITIES = {
    "biquad-response-v1": {
        "patch": "4e98b2dabc1779468c972de871acc719e909407b956d7dda86128e9cc196127d",
        "schema": "5ee44b4347d4f1d490c0ecb696d9fca49b9ece2d69635b837422dbf98ad9ea30",
        "raw_source": "3bf669da7e420a82f5c2370a4449c9ec791cdbef655b227fbb2057ab295015b5"},
    "nonlinear-chain-v1": {
        "patch": "426eace2f5d115d12b3cb61280325bff289a9ac28c9ce80652c6b466ae0aa180",
        "schema": "754c55e5f56bd5c2731847a19ed276e1ad4045849e3bcc2909acd4ec76b73ef1",
        "raw_source": "b246e2357fc3829af9d44eec0efc1aa69a82bd9157be093663005ea0eb1ea28b"}}
_BIQUAD_DEFAULTS = {"a0":.5,"a1":.25,"a2":.125,"b1":-.4,"b2":.2}
_WRAP_CASES = [('boundaries','wrap-finite-boundaries-v1'),('safe-strata','wrap-finite-safe-v1'),
               ('finite-strata','wrap-finite-strata-v1'),('zero-endpoints','wrap-finite-zero-endpoints-v1')]
_WRAP_IDENTITY = {
    'patch':'d42b66e894b6368856e3c3ef42cf402defc4103da300b2aa8bab559120393980',
    'schema':'37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570',
    'raw_source':'1c00c62a40e1c950b66f3b1c887533feb1ce7525dc384a5eb2bee87ef006a4da',
    'corrected_source':'50e01c6d9b2a854ff872b6ccbaf1c9e5077975ae36cc959d0bd1d20c69516110',
    'helper':'5120c1152ed007ac389bef310ac6e83fd6b32c3be9862d9c6615a365f30492fd'}
_WRAP_CONTRACT = {'context':'wrap-finite-stereo','input':'finite binary32 audio samples','range':[-1,1],
                  'upper_endpoint_exclusive':True,'nonfinite':'upstream route unchanged and unqualified','guard_count':2}
_POWER_KIND='nonlinear-power-modes-v1'
_POWER_NEIGHBORS={name:struct.unpack('<f',struct.pack('<I',bits))[0] for name,bits in
    [('below-two',0x3fffffff),('above-two',0x40000001),('above-quarter',0x3e800001),('below-four',0x407fffff)]}
_POWER_CASES=[{'id':name,'parameters':parameters,'events':[]} for name,parameters in
    [('square',{}),('fractional',{'exponent':.25}),('fourth',{'exponent':4})]]
_POWER_CASES += [{'id':name,'parameters':{'exponent':value},'events':[],
                 'stimulus':{'kind':'nonlinear-dense-binary32-v1'}} for name,value in
    [('dense-square',2),('dense-quarter',.25),('dense-fourth',4),('fallback-half',.5),
     ('fallback-one-half',1.5),('fallback-two-half',2.5),*_POWER_NEIGHBORS.items()]]
for _name,_initial,_schedule in [
    ('mode-switches',{},[(1,.5),(32,.25),(63,1.5),(128,4),(255,2.5),(384,2),(511,.25)]),
    ('neighbor-switches',{'exponent':.25},[(1,_POWER_NEIGHBORS['above-quarter']),(32,2),(64,_POWER_NEIGHBORS['below-two']),
       (127,_POWER_NEIGHBORS['above-two']),(256,4),(384,_POWER_NEIGHBORS['below-four']),(511,.25)])]:
    _POWER_CASES.append({'id':_name,'parameters':_initial,'events':[{'block':b,'id':'exponent','value':v,'form':'actual'} for b,v in _schedule],
                         'stimulus':{'kind':'nonlinear-dense-binary32-v1'}})
_POWER_CONTRACT={'context':'nonlinear-domains','special_exponents':[2,4,.25],'base_domain':[0,1],
    'fallback':'original-powf-with-fixnan','fixnan_retained':True,'bit_identity_claimed':False,'finite_wrap_composition':True}


def require(condition, message):
    if not condition: raise ExportError(message)


def sha(path):
    return hashlib.sha256(read_regular(path, 32*1024*1024)).hexdigest()


def c_string(value):
    require(isinstance(value, str) and "\0" not in value, "Invalid C string")
    # Every byte uses a separate literal: no hexadecimal escape continuation.
    return "".join('"\\x%02x"' % x for x in value.encode("utf-8")) or '""'


def finite(value):
    require(isinstance(value, (int,float)) and not isinstance(value, bool) and math.isfinite(value), "Expected finite number")
    return float(value)


def f32(value):
    try: result = struct.unpack("<f", struct.pack("<f", finite(value)))[0]
    except (OverflowError, struct.error) as exc: raise ExportError("Float32 value overflow") from exc
    require(math.isfinite(result), "Nonfinite Float32 value")
    return result


def c_float(value):
    return f32(value).hex() + "f"


def integer(value, minimum, maximum, name):
    require(type(value) is int and minimum <= value <= maximum, "Invalid " + name)
    return value


def stimulus_contract(fixture, case):
    if fixture["role"]=="main":
        require("stimulus" not in fixture and "stimulus" not in case, "Main cannot declare ignored external stimulus")
        return None
    base=fixture.get("stimulus");override=case.get("stimulus",{})
    require(isinstance(base,dict) and isinstance(override,dict), "FX requires explicit stimulus settings")
    wave2={"impulse-step-v1":4,"mixed-tone-v1":5,"nonlinear-grid-v1":6,'nonlinear-dense-binary32-v1':11,
           **{name:7+i for i,(_,name) in enumerate(_WRAP_CASES)},
           **{name:12+i for i,name in enumerate(WAVE4_INPUTS)}, GEN_INPUT:15}
    if base.get("kind") in wave2:
        require(set(base)=={"kind"} and set(override)<={"kind"},"Unknown wave2 stimulus settings")
        settings=base|override;require(settings.get("kind") in wave2,"Unknown wave2 stimulus kind")
        return {"kind":wave2[settings["kind"]],"settings":settings,**{k:0.0 for k in ("base","depth","rate","pilot_frequency","pilot_amplitude","excitation","level")}}
    kinds={"midi-stereo-v1":(1,{"kind","base","depth","rate","pilot_frequency","pilot_amplitude"}),
           "frequency-stereo-v1":(2,{"kind","frequency","depth","rate","pilot_frequency","pilot_amplitude"}),
           "reson-stereo-v1":(3,{"kind","excitation","level","center","depth","rate"})}
    require(base.get("kind") in kinds, "Unknown FX stimulus kind")
    kind,keys=kinds[base["kind"]]
    require(set(base)==keys and set(override)<=keys-{"kind"}, "Unknown/missing FX stimulus fields or kind override")
    settings=base|override
    numbers={key:finite(value) for key,value in settings.items() if key!="kind"}
    require(0<=numbers["rate"]<=22050 and numbers["depth"]>=0, "Invalid modulation rate/depth")
    center=numbers["base" if kind==1 else "frequency" if kind==2 else "center"]
    if kind==1:require(0<=center-numbers["depth"]<=center+numbers["depth"]<=127, "MIDI pitch stimulus outside 0..127")
    else:require(0<=(center-numbers["depth"]) and center+numbers["depth"]<=22050, "Frequency stimulus outside 0..Nyquist")
    if kind==3:
        require(center-numbers["depth"]>0 and center+numbers["depth"]<22050, "Reson center must remain inside 0..Nyquist")
        require(0<=numbers["excitation"]<=22050 and 0<=numbers["level"]<=1, "Invalid reson excitation/level")
    else:require(0<numbers["pilot_frequency"]<=22050 and 0<numbers["pilot_amplitude"]<=1, "Invalid pilot frequency/amplitude")
    return {"kind":kind,"settings":settings,"base":center,"depth":numbers["depth"],"rate":numbers["rate"],
            "pilot_frequency":numbers.get("pilot_frequency",0.0),"pilot_amplitude":numbers.get("pilot_amplitude",0.0),
            "excitation":numbers.get("excitation",0.0),"level":numbers.get("level",0.0)}


def wave2_verification(fixture,case,by_id,warmup,blocks):
    declaration=fixture['verification'];kind=declaration['kind']
    require(warmup==4 and blocks==512,"Reviewed wave2 models require four warmup blocks and512 rendered blocks")
    require(fixture.get('seed')==305419896,"Reviewed wave2 model seed differs")
    biquad=kind=='biquad-response-v1';limit=3e-6 if biquad else 2e-6
    require(declaration=={'kind':kind,'maximum_absolute_error':limit},"Unsupported wave2 verification declaration")
    require(fixture['role']=='fx' and fixture.get('family')==('biquad' if biquad else 'nonlinear'),"Unsupported wave2 verification fixture")
    semantic=({'kind':'biquad','defaults':_BIQUAD_DEFAULTS,'maximum_absolute_error':3e-6} if biquad else
              {'kind':'nonlinear','exponent_default':2,'maximum_absolute_error':2e-6})
    require(fixture.get('semantic')==semantic,"Reviewed wave2 semantic model differs")
    expected_stimulus={'kind':'impulse-step-v1' if biquad else 'nonlinear-grid-v1'}
    require(fixture.get('stimulus')==expected_stimulus and not case.get('stimulus'),"Reviewed wave2 input differs")
    require(set(case)=={'id','parameters','events'} and case['events']==[],"Reviewed wave2 cases require no events or extra settings")
    cases=({'default':{},'identity':{'a0':1,'a1':0,'a2':0,'b1':0,'b2':0},
            'slow-pole':{'a0':.05,'a1':0,'a2':0,'b1':-.95,'b2':0}} if biquad else
           {'square':{},'fractional':{'exponent':.25},'fourth':{'exponent':4}})
    require(case['id'] in cases and case['parameters']==cases[case['id']],"Unreviewed wave2 parameter case")
    # Parameter values reach the module as Float32, while these original
    # catalog coefficients deliberately remain Float64 in the truth model.
    for value in case['parameters'].values():finite(value)
    expected_schema=({'a0':(0,0,1,.5),'b2':(1,0,.8,.2),'a1':(2,-1,1,.25),
                      'a2':(3,-1,1,.125),'b1':(4,-.95,.95,-.4)} if biquad else
                     {'exponent':(0,.25,4,2)})
    require(set(by_id)==set(expected_schema),"Reviewed wave2 parameter IDs differ")
    for identity,(index,lo,hi,initial) in expected_schema.items():
        p=by_id[identity]
        require((p['index'],p['minimum'],p['maximum'],p['initialValue'],p['exponent'],p['steps'])==
                (index,lo,hi,initial,1,0),"Reviewed wave2 parameter schema differs")
    result={'kind':kind,'maximum_absolute_error':limit,'model':'fresh-float64-difference-equation' if biquad else 'float64-tanh-wrap-clip-pow',
            'rounding':'once-float32','gate':'cache-error-plus-maximum-cache-rounding-error'}
    if biquad:
        coefficients=_BIQUAD_DEFAULTS|case['parameters'];result['coefficients']=coefficients
        gain=(coefficients['a0']+coefficients['a1']+coefficients['a2'])/(1+coefficients['b1']+coefficients['b2'])
        result['dc_expected']=-.125*gain
    else:result['exponent']=finite(case['parameters'].get('exponent',2))
    return result


def wrap_finite_verification(fixture,case,by_id,warmup,blocks):
    require(fixture.get('id')=='wrap-finite-stereo' and fixture.get('family')=='wrap' and fixture.get('role')=='fx',"Unsupported raw wrap fixture")
    require(warmup==4 and blocks==512 and fixture.get('seed')==305419896,"Raw wrap requires reviewed rate/block/initial state")
    declaration=fixture['verification']
    require(declaration=={'kind':'wrap-finite-v1','maximum_absolute_error':0,'bit_exact':True} and
            declaration.get('bit_exact') is True and finite(declaration['maximum_absolute_error'])==0,"Unsupported raw wrap verification")
    require(fixture.get('semantic')=={'kind':'wrap-finite','range':[-1,1],'upper_exclusive':True,'maximum_absolute_error':0,'bit_exact':True},"Raw wrap semantic declaration differs")
    require(not by_id and fixture.get('stimulus')=={'kind':_WRAP_CASES[0][1]},"Raw wrap schema/base stimulus differs")
    expected=dict(_WRAP_CASES)
    require(set(case)=={'id','parameters','events','stimulus'} and case.get('id') in expected and
            case['parameters']=={} and case['events']==[] and case['stimulus']=={'kind':expected[case['id']]},"Unreviewed raw wrap case/stimulus")
    return {'kind':'wrap-finite-v1','maximum_absolute_error':0,'model':'exact-binary32-modulo2',
            'rounding':'exact-binary32','gate':'raw-binary32-equality','bit_exact':True}

def power_modes_verification(fixture,case,by_id,warmup,blocks):
    require(fixture.get('id')=='nonlinear-domains' and fixture.get('family')=='nonlinear' and fixture.get('role')=='fx', 'Unsupported power-mode fixture')
    require(warmup==4 and blocks==512 and fixture.get('seed')==305419896,'Power modes require reviewed audio/initial state')
    require(fixture['verification']=={'kind':_POWER_KIND,'maximum_absolute_error':2e-6},'Power-mode verification differs')
    require(fixture.get('semantic')=={'kind':'nonlinear','exponent_default':2,'maximum_absolute_error':2e-6} and
            fixture.get('stimulus')=={'kind':'nonlinear-grid-v1'},'Power-mode semantic/input contract differs')
    require(case in _POWER_CASES,'Unreviewed power-mode case or actual-event schedule')
    require(set(by_id)=={'exponent'},'Power modes require original exponent schema')
    p=by_id['exponent']
    require((p['index'],p['minimum'],p['maximum'],p['initialValue'],p['exponent'],p['steps'])==(0,.25,4,2,1,0),'Power exponent schema differs')
    for value in case['parameters'].values():finite(value)
    for event in case['events']:finite(event['value'])
    return {'kind':_POWER_KIND,'maximum_absolute_error':2e-6,'model':'float64-tanh-wrap-clip-pow-events-v1',
            'rounding':'once-float32','gate':'cache-error-plus-maximum-cache-rounding-error','initial_exponent':2.0}


def verification_contract(fixture,case,by_id,warmup,blocks=512):
    declaration=fixture.get("verification")
    if isinstance(declaration,dict) and declaration.get('kind')==GEN_ARITH_KIND:
        try:return gen_arith_verification(fixture,case,by_id,warmup,blocks)
        except ValueError as exc:raise ExportError(str(exc)) from exc
    if isinstance(declaration,dict) and declaration.get('kind')==GEN_KIND:
        try:return gen_verification(fixture,case,by_id,warmup,blocks)
        except ValueError as exc:raise ExportError(str(exc)) from exc
    if isinstance(declaration,dict) and declaration.get('kind')==WAVE4_KIND:
        try:return wave4_verification(fixture,case,by_id,warmup,blocks)
        except ValueError as exc:raise ExportError(str(exc)) from exc
    new_input=(fixture.get("stimulus",{})|case.get("stimulus",{})).get("kind") in (GEN_INPUT,*WAVE4_INPUTS,"impulse-step-v1","mixed-tone-v1","nonlinear-grid-v1","nonlinear-dense-binary32-v1",*(name for _,name in _WRAP_CASES))
    if declaration is None:
        require(not new_input,"Wave2 stimulus requires an explicit verification contract")
        return None
    if isinstance(declaration,dict) and declaration.get('kind')=='wrap-finite-v1':
        return wrap_finite_verification(fixture,case,by_id,warmup,blocks)
    if isinstance(declaration,dict) and declaration.get('kind')==_POWER_KIND:
        return power_modes_verification(fixture,case,by_id,warmup,blocks)
    if isinstance(declaration,dict) and declaration.get('kind') in _WAVE2_IDENTITIES:
        return wave2_verification(fixture,case,by_id,warmup,blocks)
    require(fixture["role"]=="fx" and fixture.get("family")=="average" and isinstance(declaration,dict),"Unsupported verification fixture")
    expected={"kind":"average-window-v1","parameter_id":"window","default_window":16,"maximum_window":64,"maximum_absolute_error":2e-6}
    average_input=(fixture.get("stimulus",{})|case.get("stimulus",{})).get("kind") in ("impulse-step-v1","mixed-tone-v1")
    require(declaration==expected and average_input,"Unsupported average verification contract/input")
    semantic=fixture.get("semantic",{})
    require(semantic.get("kind")=="average" and semantic.get("default_window")==16 and semantic.get("maximum_absolute_error")==2e-6,"Average semantic declaration differs")
    require(set(by_id)=={"window"},"Average verification requires one window parameter")
    p=by_id["window"]
    require((p["minimum"],p["maximum"],p["initialValue"],p["exponent"],p["steps"])==(1,64,16,1,0),"Unsupported average window schema")
    require(isinstance(case.get("events",[]),list) and not case.get("events",[]),"Average window events are not yet modeled")
    parameters=case.get("parameters",{})
    require(isinstance(parameters,dict) and set(parameters)<={"window"},"Unknown average parameter setting")
    value=finite(parameters.get("window",16));require(value==int(value) and 1<=value<=64,"Average window must be an integer1..64")
    window=int(value);initial=min(16,warmup*256) if window==16 else 0
    return {"kind":"average-window-v1","window":window,"initial_available":initial,"maximum_absolute_error":2e-6,
            "default_window":16,"maximum_window":64,"parameter_id":"window",
            "model":"fresh-float64-window-sum","rounding":"once-float32","gate":"cache-error-plus-maximum-cache-rounding-error"}


def configuration(args, modules):
    data = read_regular(args.catalog, 4*1024*1024)
    catalog = read_json(data, "object fixture catalog")
    require(catalog.get("sample_rate")==44100 and catalog.get("block_frames")==256, "Wrong catalog audio profile")
    matches = [f for f in catalog.get("fixtures",[]) if f.get("id")==args.fixture_id]
    require(len(matches)==1, "Fixture ID must occur exactly once")
    gen_arith = catalog.get('format') == GEN_ARITH_FORMAT
    require(gen_arith or matches[0].get('verification', {}).get('kind') != GEN_ARITH_KIND,
            'Gen arithmetic requires the original Gen arithmetic catalog format')
    gen = catalog.get('format') in (GEN_FORMAT,GEN_OPT_FORMAT)
    gen_optimized = catalog.get('format') == GEN_OPT_FORMAT
    require(gen or matches[0].get('verification', {}).get('kind') != GEN_KIND,
            'Gen history verification requires the original Gen history catalog format')
    wave4 = catalog.get('format') == 'rnbo-original-wave4-fixtures-v1'
    require(wave4 or matches[0].get('verification', {}).get('kind') != WAVE4_KIND,
            'Wave4 mathematical verification requires the original wave4 catalog format')
    if wave4:
        try:fixture=wave4_fixture(catalog,args.catalog.parent,args.fixture_id)
        except ValueError as exc:raise ExportError(str(exc)) from exc
    elif gen_arith:
        try:fixture=gen_arith_fixture(catalog,args.catalog.parent,args.fixture_id)
        except ValueError as exc:raise ExportError(str(exc)) from exc
    elif gen:
        try:fixture=gen_fixture(catalog,args.catalog.parent,args.fixture_id)
        except ValueError as exc:raise ExportError(str(exc)) from exc
    else:fixture = matches[0]
    require(re.fullmatch(r"[A-Za-z0-9_-]+", args.fixture_id), "Unsafe fixture ID")
    manifest = modules["strict"]["report"]["prepared_export"]["manifest"]
    candidate = modules["optimized"]["report"]["prepared_export"]["manifest"]
    role = fixture.get("role")
    if gen_arith:
        try:
            for module in modules.values():gen_arith_admit_module(fixture,module)
        except ValueError as exc:raise ExportError(str(exc)) from exc
        require(modules['strict']['artifact_sha256']==modules['optimized']['artifact_sha256'],
                'Initial Gen arithmetic qualification requires an identical-module control')
        require(args.rounds==3 and args.timing_exclude_blocks==32 and args.arena_bytes==4096,
                'Gen arithmetic requires reviewed rounds, timing exclusion and arena capacity')
    if gen:
        try:
            for side,module in modules.items():gen_admit_module(fixture,module,candidate=gen_optimized and side=='optimized')
        except ValueError as exc:raise ExportError(str(exc)) from exc
        require((modules['strict']['artifact_sha256']!=modules['optimized']['artifact_sha256']) if gen_optimized else
                (modules['strict']['artifact_sha256']==modules['optimized']['artifact_sha256']),
                'Gen comparison requires distinct artifacts' if gen_optimized else 'Initial Gen history qualification requires an identical-module control')
        if gen_optimized:
            for key in ('compiler','dependencies','private_support_archives','dynamic_abi','state_policy','allocation_accounting','source_files_sha256'):
                require(key in modules['strict']['report'] and modules['strict']['report'][key]==modules['optimized']['report'].get(key),
                        'Gen comparison requires a matched compiler, SDK and state policy: '+key)
            require(all(module['report'].get('imports')==[] for module in modules.values()),
                    'Gen comparison requires zero unresolved imports')
            left=modules['strict']['report']['prepared_snapshot']['prepared_files_sha256']
            right=modules['optimized']['report']['prepared_snapshot']['prepared_files_sha256']
            omitted={'rnbo_source.h','patch_config.h','rnbo_s3_gen_feedback_source.h'}
            require({k:v for k,v in left.items()if k not in omitted}=={k:v for k,v in right.items()if k not in omitted},
                    'Gen comparison changes files beyond its source and compile contract')
        require(args.rounds==3 and args.timing_exclude_blocks==32 and args.arena_bytes==65536,
                'Gen history requires the reviewed rounds, timing exclusion and arena capacity')
    if wave4:
        try:
            for module in modules.values():wave4_admit_module(fixture,module)
        except ValueError as exc:raise ExportError(str(exc)) from exc
        require(modules['strict']['artifact_sha256']==modules['optimized']['artifact_sha256'],
                'Initial wave4 qualification requires an identical-module control')
        require(all(m['numerical_profile']=='float32-strict' and m['parameter_count']==0 for m in (manifest,candidate)),
                'Wave4 control requires the strict parameter-free binary32 mode')
    require(role in ("main","fx") and manifest["role"]==candidate["role"]==role, "Catalog/module role differs")
    require(manifest["audio_inputs"]==(0 if role=="main" else 2) and manifest["audio_outputs"]==2, "Unexpected audio channel shape")
    for key in ("parameter_schema_sha256", "source_tree_sha256", "editable_source_sha256", "parameter_count", "audio_inputs", "audio_outputs"):
        require(manifest[key]==candidate[key], "Strict/optimized source or schema identity differs: " + key)
    requested_reference=getattr(args,"reference_profile","float32-strict")
    require(requested_reference in NUMERICAL_PROFILES, "Unknown reference numerical profile")
    require(manifest["numerical_profile"]==requested_reference, "Reference numerical profile differs from explicit request")
    numerical_profiles={"strict":manifest["numerical_profile"],"optimized":candidate["numerical_profile"]}
    require(all(isinstance(p,str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,96}",p) for p in numerical_profiles.values()),"Unsafe numerical profile identity")
    patch=Path(fixture["patch"])
    require(not patch.is_absolute() and ".." not in patch.parts, "Unsafe catalog patch path")
    patch=(GEN_FIXTURES if gen else args.catalog.parent)/patch
    require(sha(patch)==manifest["editable_source_sha256"], "Module source differs from catalog patch")
    require(not manifest["required_host_services"] and not candidate["required_host_services"], "Host services unsupported")
    description_path = Path(modules["strict"]["export_path"])/"description.json"
    description = read_json(read_regular(description_path, 4*1024*1024), "prepared description")
    parameters = sorted(description["parameters"], key=lambda p:p["index"])
    require(len(parameters)==manifest["parameter_count"]<=128, "Parameter count mismatch")
    by_id = {}
    for i,p in enumerate(parameters):
        require(p["index"]==i and p["paramId"] not in by_id, "Invalid parameter indices/IDs")
        require(len(p["paramId"].encode("utf-8"))<192, "Oversize parameter ID")
        lo,hi,initial = (f32(p[k]) for k in ("minimum","maximum","initialValue"))
        require(lo<=initial<=hi, "Invalid parameter bounds")
        f32(p["exponent"]);integer(p["steps"],0,0xffffffff,"parameter steps")
        by_id[p["paramId"]]=p
    blocks = integer(args.blocks or fixture["blocks"], 33, 1024, "blocks")
    warmup = integer(fixture["warmup_blocks"],0,64,"warmup")
    seed = integer(fixture["seed"],0,0xffffffff,"seed")
    require(args.timing_exclude_blocks<blocks, "Timing exclusion consumes entire pass")
    cases = fixture["cases"]
    require(isinstance(cases,list) and 1<=len(cases)<=16, "Expected 1..16 cases")
    declaration=fixture.get('verification',{})
    power_modes=isinstance(declaration,dict) and declaration.get('kind')==_POWER_KIND
    if power_modes:
        require(cases==_POWER_CASES,'Power modes require all fifteen closed cases in order')
        chain_wrap=_WRAP_CONTRACT|{'context':'nonlinear-domains','guard_count':1}
        for side,module in modules.items():
            exported=module['report']['prepared_export'];identity=exported['manifest']
            require(identity.get('correct_finite_wrap') is True and identity.get('finite_wrap_contract')==chain_wrap,'Power modes require matched finite-wrap correction')
            expected_profile='float32-strict' if side=='strict' else 'float32-scalar-powers-v1'
            require(identity['numerical_profile']==expected_profile,'Power modes require corrected strict vs public scalar-powers profile')
            if side=='optimized':require(identity.get('scalar_powers_contract')==_POWER_CONTRACT,'Power specialization contract differs')
            pins=_WAVE2_IDENTITIES['nonlinear-chain-v1']
            require(identity['editable_source_sha256']==pins['patch'] and identity['parameter_schema_sha256']==pins['schema'] and
                    exported.get('provenance',{}).get('raw_files_sha256',{}).get('rnbo_source.h')==pins['raw_source'],'Power graph/source/schema differs')
            hashes=module['report'].get('prepared_snapshot',{}).get('prepared_files_sha256',{})
            expected_source='cb3034efc572a29b2d3e9cc82e733035a12b6907b6213c9c3af9ee01ab64cbfd' if side=='strict' else 'f0774e0e80519692ad9da7b645460433b14981e6e3ec1f0ce0591042a8a607b2'
            require(hashes.get('rnbo_source.h')==expected_source and hashes.get('private_finite_wrap.h')==_WRAP_IDENTITY['helper'],'Power prepared source/helper differs')
            if side=='optimized':require(hashes.get('rnbo_s3_scalar_powers_source.h')=='b08d3f3dced35995ee28990f3e9343f37bfb5c5833dd03890187b145fd3b3821','Power Float32 compile contract differs')
    raw_wrap=isinstance(declaration,dict) and declaration.get('kind')=='wrap-finite-v1'
    if raw_wrap:
        require([case.get('id') for case in cases]==[name for name,_ in _WRAP_CASES],"Raw wrap requires all four reviewed cases in order")
        require(modules['strict']['artifact_sha256']==modules['optimized']['artifact_sha256'],"Raw wrap unsafe inputs require same corrected module control")
        for module in modules.values():
            exported=module['report']['prepared_export'];identity=exported['manifest']
            require(identity['numerical_profile']=='float32-strict' and identity.get('correct_finite_wrap') is True and
                    identity.get('finite_wrap_contract')==_WRAP_CONTRACT and identity['parameter_count']==0,"Raw wrap corrected module contract differs")
            require(identity['editable_source_sha256']==_WRAP_IDENTITY['patch'] and identity['parameter_schema_sha256']==_WRAP_IDENTITY['schema'],"Raw wrap patch/schema differs")
            require(exported.get('provenance',{}).get('raw_files_sha256',{}).get('rnbo_source.h')==_WRAP_IDENTITY['raw_source'],"Raw wrap source differs")
            hashes=module['report'].get('prepared_snapshot',{}).get('prepared_files_sha256',{})
            require(hashes.get('rnbo_source.h')==_WRAP_IDENTITY['corrected_source'] and hashes.get('private_finite_wrap.h')==_WRAP_IDENTITY['helper'],"Raw wrap corrected source/helper differs")
    reviewed=_WAVE2_IDENTITIES.get(declaration.get('kind')) if isinstance(declaration,dict) else None
    if reviewed:
        expected_cases=['default','identity','slow-pole'] if declaration['kind']=='biquad-response-v1' else ['square','fractional','fourth']
        require([case.get('id') for case in cases]==expected_cases,"Reviewed wave2 model requires all three authored cases in their original order")
        for module in modules.values():
            exported=module['report']['prepared_export'];identity=exported['manifest']
            require(identity['editable_source_sha256']==reviewed['patch'] and identity['parameter_schema_sha256']==reviewed['schema'],"Reviewed wave2 patch/schema identity differs")
            require(exported.get('provenance',{}).get('raw_files_sha256',{}).get('rnbo_source.h')==reviewed['raw_source'],"Reviewed wave2 raw source identity differs")
    events=[]; case_rows=[]; case_ids=set();stimuli=[];verifications=[]
    for case in cases:
        stimuli.append(stimulus_contract(fixture,case))
        verifications.append(verification_contract(fixture,case,by_id,warmup,blocks))
        name=case["id"];require(isinstance(name,str) and name not in case_ids,"Invalid/duplicate case ID");case_ids.add(name)
        current=[]
        require(isinstance(case.get("parameters",{}),dict), "Parameters must be a map")
        source=[{"block":0,"id":identity,"form":"actual","value":value} for identity,value in case.get("parameters",{}).items()]
        source += case.get("events",[])
        seen=set()
        for event in source:
            block=integer(event["block"],0,blocks-1,"event block");identity=event["id"]
            require(identity in by_id and (block,identity) not in seen,"Unknown/duplicate parameter event")
            seen.add((block,identity));p=by_id[identity];form=event.get("form","actual")
            require(form in ("actual","normalized"), "Unsupported event form")
            value=f32(event["value"])
            require((f32(p["minimum"])<=value<=f32(p["maximum"])) if form=="actual" else 0<=value<=1,"Event exceeds declared bounds")
            current.append({"block":block,"index":p["index"],"kind":1 if form=="actual" else 2,"value":value,"id":identity})
        require(len(current)<=256, "Too many events per case")
        # A setter may trigger work using another parameter's current value
        # (e.g. line target reads duration). Keep authored order within a block:
        # initial map iteration first, then explicit event-array order.
        current.sort(key=lambda e:e["block"])
        if power_modes or gen:
            require(all(e['kind']==1 and e['index']==0 for e in current),'Power schedule requires actual exponent events')
            wire=struct.pack('<II',0 if gen else 0x40000000,len(current))
            for e in current:wire+=struct.pack('<III',e['block'],e['index'],e['kind'])+struct.pack('<f',e['value'])
            verifications[-1]['event_schedule']=current
            verifications[-1]['event_schedule_sha256']=hashlib.sha256(wire).hexdigest()
            if gen:verifications[-1]['reset_witness_sha256']=gen_witness_sha(fixture,case)
        case_rows.append((name,len(events),len(current)));events.extend(current)
    tolerance=fixture["comparison_tolerance"]
    maximum=finite(tolerance["maximum_absolute_error"]);relative=finite(tolerance["relative_rms_level_difference"])
    require(maximum>=0 and relative>=0,"Negative comparison tolerance")
    pcm=integer(tolerance["maximum_pcm_lsb_error"],0,65535,"PCM tolerance")
    if reviewed:require(maximum<=2e-6 and pcm<=1 and relative<=1e-4,"Reviewed wave2 pair limits cannot be widened")
    if power_modes:require(maximum==2e-6 and pcm==1 and relative==1e-4,'Power pair tolerances must remain2e-6/PCM1/RMS1e-4')
    if raw_wrap:require(maximum==pcm==relative==0,"Raw wrap control requires exact pair tolerances")
    if gen:
        require((maximum,pcm,relative)==((2e-6,1,1e-4) if gen_optimized else (0,0,0)) and fixture['pcm_gain']==.25,
                'Gen history comparison/control gates and quarter-scale PCM must remain fixed')
    if gen_arith:require(maximum==pcm==relative==0 and fixture['pcm_gain']==.5,'Gen arithmetic controls require exact pair gates and half-scale PCM')
    if wave4:require(maximum==pcm==relative==0,'Wave4 control requires exact numerical/PCM/RMS pair gates')
    oracle_bytes=blocks*256*2*4 if any(verifications) else 0
    buffers=blocks*256*2*4*(2 if role=="fx" else 1)+4*256*4
    loaded=sum(m["inspection"]["loaded_bytes_upper_bound"] for m in modules.values())
    # Admission permits <=1MiB opaque context/image. Budget that full bound,
    # not an unverified guess of the current wrapper's smaller sizeof(Context).
    budget={"workspace_bytes":buffers,"oracle_cache_bytes":oracle_bytes,"arena_bytes":2*args.arena_bytes,"opaque_context_upper_bound_bytes":2*1048576,
            "loaded_images_upper_bound_bytes":loaded,"loader_heap_alignment_reserve_bytes":524288,"physical_psram_bytes":8*1048576}
    budget["required_upper_bound_bytes"]=sum(budget[k] for k in ("workspace_bytes","oracle_cache_bytes","arena_bytes","opaque_context_upper_bound_bytes","loaded_images_upper_bound_bytes","loader_heap_alignment_reserve_bytes"))
    require(budget["required_upper_bound_bytes"]<=budget["physical_psram_bytes"],"Conservative benchmark PSRAM budget exceeds 8MiB; reduce blocks/arena")
    lines=["/* Generated by tools/build_object_benchmark.py; do not edit. */", "#pragma once",
           f"#define BENCH_FIXTURE {c_string(args.fixture_id)}",f"#define BENCH_ROLE {1 if role=='main' else 2}u",
           f"#define BENCH_BLOCKS {blocks}u", f"#define BENCH_WARMUP {warmup}u",f"#define BENCH_SEED {seed}u",
           f"#define BENCH_ROUNDS {args.rounds}u",f"#define BENCH_TIMING_EXCLUDE {args.timing_exclude_blocks}u",
           f"#define BENCH_WAVE4 {1 if wave4 else 0}u", f"#define BENCH_GEN_HISTORY {1 if gen else 0}u", f"#define BENCH_GEN_FEEDBACK_F32 {1 if gen_optimized else 0}u", f"#define BENCH_GEN_ARITH {1 if gen_arith else 0}u",
           f"#define BENCH_ARENA_BYTES {args.arena_bytes}u",f"#define BENCH_HAS_ORACLE {1 if oracle_bytes else 0}u",f"#define BENCH_CASE_COUNT {len(cases)}u",f"#define BENCH_PARAMETER_COUNT {len(parameters)}u",
           f"#define BENCH_MAX_ABS {maximum.hex()}",f"#define BENCH_MAX_RELATIVE_RMS {relative.hex()}",f"#define BENCH_MAX_PCM_LSB {pcm}u",
           f"#define BENCH_STRICT_SHA256 {c_string(modules['strict']['artifact_sha256'])}",
           f"#define BENCH_OPTIMIZED_SHA256 {c_string(modules['optimized']['artifact_sha256'])}",
           f"#define BENCH_REFERENCE_PROFILE {c_string(numerical_profiles['strict'])}",
           f"#define BENCH_CANDIDATE_PROFILE {c_string(numerical_profiles['optimized'])}",
           "static const bench_parameter bench_parameters[]={"]
    for p in parameters:
        lines.append("{%s,%s,%s,%s,%s,%su}," % (c_string(p["paramId"]),c_float(p["minimum"]),c_float(p["maximum"]),c_float(p["initialValue"]),c_float(p["exponent"]),p["steps"]))
    if not parameters: lines.append('{"",0,0,0,0,0},')
    lines += ["};", "static const bench_event bench_events[]={"]
    for e in events: lines.append("{%su,%su,%su,%s},"%(e["block"],e["index"],e["kind"],c_float(e["value"])))
    if not events:lines.append("{0,0,0,0},")
    lines += ["};", "static const bench_case bench_cases[]={"]
    for name,start,count in case_rows:lines.append("{%s,%su,%su},"%(c_string(name),start,count))
    lines += ["};", "static const object_stimulus bench_stimuli[]={"]
    for stimulus in stimuli:
        if stimulus is None:lines.append("{0,0,0,0,0,0,0,0},")
        else:lines.append("{%su,%s},"%(stimulus["kind"],",".join(float(stimulus[k]).hex() for k in ("base","depth","rate","pilot_frequency","pilot_amplitude","excitation","level"))))
    lines += ["};", "static const bench_verification bench_verifications[]={"]
    for verification in verifications:
        if verification is None:lines.append("{0,0,0,0,{0,0,0,0,0},0},")
        elif verification['kind']==GEN_ARITH_KIND:
            lines.append('{8u,%su,0,0,{0,0,0,0,0},0},'%verification['model_code'])
        elif verification['kind']==GEN_KIND:
            lines.append('{7u,%su,0,%s,{0,0,0,0,0},0},'%(verification['model_code'],float(verification['maximum_absolute_error']).hex()))
        elif verification['kind']==WAVE4_KIND:
            lines.append('{6u,%su,0,0,{0,0,0,0,0},0},'%verification['model_code'])
        elif verification['kind']=='average-window-v1':
            lines.append("{1u,%su,%su,%s,{0,0,0,0,0},0},"%(verification["window"],verification["initial_available"],float(verification["maximum_absolute_error"]).hex()))
        else:
            coefficients=verification.get('coefficients',dict.fromkeys(('a0','a1','a2','b1','b2'),0))
            fields=','.join(float(coefficients[k]).hex() for k in ('a0','a1','a2','b1','b2'))
            lines.append('{%su,0,0,%s,{%s},%s},'%({'biquad-response-v1':2,'nonlinear-chain-v1':3,'wrap-finite-v1':4,_POWER_KIND:5}[verification['kind']],
                         float(verification['maximum_absolute_error']).hex(),fields,float(verification.get('exponent',verification.get('initial_exponent',0))).hex()))
    lines += ["};", ""]
    return "\n".join(lines), {"catalog_path":str(args.catalog),"catalog_sha256":hashlib.sha256(data).hexdigest(),
        "fixture":fixture,"patch_sha256":sha(patch),"blocks":blocks,"rounds":args.rounds,"timing_exclude_blocks":args.timing_exclude_blocks,
        "arena_bytes":args.arena_bytes,"events":events,"stimuli":stimuli,"verifications":verifications,"psram_budget":budget,"description_sha256":sha(description_path),
        "numerical_profiles":numerical_profiles,"event_order":"stable-block-source-order-v1",
        "parameter_schema":[{k:p[k] for k in ('paramId','index','minimum','maximum','initialValue','exponent','steps')} for p in parameters],
        "comparison_policy":{"pcm_gain":0.25 if gen else 0.5,"pcm_scale":32767,"pcm_rounding":"lrintf; symmetric saturation",
        "case_gate":"all declared tolerances per independently reset case, combined channels and rounds",
        "fx_input":"per-case declared generator; completed channel samples rounded once to Float32; interleaved little-endian input SHA before/after every pass; native/target transcendental rounding not assumed identical",
        "timing":"process callback only; excludes first N rendered blocks of each pass; events/preparation separate"}}


def sources():
    paths=[Path(__file__).resolve(),ROOT/"tools/build_rnbo_loader_test.py",ROOT/"tools/build_loader_spike.py",ROOT/"loader-spike/dependencies.json",
           ROOT/"host/compiler/build.py",ROOT/"host/compiler/prepare.py",ROOT/"host/compiler/inspect_module.py",
           ROOT/"host/compiler/gen_arithmetic_contract.py",ROOT/"host/compiler/generate_gen_arithmetic_fixtures.py",ROOT/"host/compiler/gen_history_contract.py",ROOT/"host/compiler/gen_feedback.py",ROOT/"host/compiler/wave4_contract.py",ROOT/"host/compiler/generate_object_fixtures.py",
           ROOT/"tests/fixtures/objects/wave4/recipes.json",ROOT/"tests/fixtures/objects/wave4/inputs.py",
           ROOT/"tests/fixtures/objects/wave4/models.py",ROOT/"tests/fixtures/objects/wave4/identities.json"]
    for identity in ('history-feedback','two-history-swap','three-history-rotation'):
        paths.extend(GEN_FIXTURES/(identity+suffix) for suffix in ('.rnbopat','.genexpr'))
    for directory in (ROOT/"object-benchmark", ROOT/"module-sdk", ROOT/"tests/fixtures/gen/target", ROOT/"tests/fixtures/gen/feedback-f32", ROOT/"tests/fixtures/gen/arithmetic"):
        paths.extend(p for p in sorted(directory.rglob("*")) if p.is_file() and "__pycache__" not in p.parts)
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-id",required=True)
    parser.add_argument("--catalog",type=Path,default=ROOT/"tests/fixtures/objects/catalog.json")
    parser.add_argument("--qualification-dir",type=Path,default=ROOT/"build/object-qualification/milestone-2")
    parser.add_argument("--reference-profile",choices=NUMERICAL_PROFILES,default="float32-strict",
                        help="Expected reference numerical profile; actual identities are printed and verified")
    for key in ("strict","optimized"):
        parser.add_argument(f"--{key}-module",type=Path)
        parser.add_argument(f"--{key}-export",type=Path)
    parser.add_argument("--rounds",type=int,default=3)
    parser.add_argument("--blocks",type=int)
    parser.add_argument("--timing-exclude-blocks",type=int,default=32)
    parser.add_argument("--arena-bytes",type=int,default=1048576)
    parser.add_argument("--board",choices=("amoled","xiao"),default="amoled")
    parser.add_argument("--variant",default="")
    parser.add_argument("--loader-dir",type=Path,default=ROOT/"build/vendor-loader-spike/elf_loader")
    parser.add_argument("--cmake-utilities-dir",type=Path,default=ROOT/"build/vendor-loader-spike/cmake_utilities")
    parser.add_argument("--idf-path",type=Path,default=Path(os.environ.get("IDF_PATH",str(Path.home()/"esp/esp-idf"))))
    parser.add_argument("--validate-only",action="store_true")
    args=parser.parse_args()
    require(re.fullmatch(r"[A-Za-z0-9_-]+",args.fixture_id),"Unsafe fixture ID")
    require(not args.variant or re.fullmatch(r"[A-Za-z0-9_-]+",args.variant),"Unsafe variant")
    integer(args.rounds,1,5,"rounds");integer(args.timing_exclude_blocks,0,1023,"timing exclusion");integer(args.arena_bytes,4096,1048576,"arena")
    args.catalog=args.catalog.expanduser().resolve();base=args.qualification_dir.expanduser().resolve()
    catalog=read_json(read_regular(args.catalog,4*1024*1024),"catalog")
    match=[f for f in catalog.get("fixtures",[]) if f.get("id")==args.fixture_id];require(len(match)==1,"Unknown fixture")
    modules={}
    for key,variant in (("strict","strict"),("optimized","float32-audio-v1")):
        artifact=getattr(args,key+"_module") or base/"modules"/args.fixture_id/variant/"rnbo_s3_dynamic.app.elf"
        export=getattr(args,key+"_export") or base/"prepared"/args.fixture_id/variant
        modules[key]=module_input(artifact,export,match[0]["role"])
    header,policy=configuration(args,modules)
    if args.validate_only:
        print(json.dumps({"validated":True,"policy":policy,"generated_header_sha256":hashlib.sha256(header.encode()).hexdigest()},indent=2));return 0
    lock=read_json(read_regular(ROOT/"loader-spike/dependencies.json",1024*1024),"loader dependencies")
    stage=ROOT/"build/vendor-object-benchmark";stage.mkdir(parents=True,exist_ok=True);dependencies={}
    for name,path in (("elf_loader",args.loader_dir),("cmake_utilities",args.cmake_utilities_dir)):
        path=path.expanduser().resolve();actual=inventory(path)
        require(actual==lock["components"][name]["files_sha256"],"Locked dependency differs: "+name)
        dependencies[name]={"source_tree_sha256":tree_digest(actual),"files":len(actual),"version":lock["components"][name]["version"]}
        destination=stage/name
        if destination.exists() and inventory(destination)!=actual:shutil.rmtree(destination)
        if not destination.exists():shutil.copytree(path,destination)
    idf=args.idf_path.expanduser().resolve();require((idf/"tools/idf.py").is_file(),"Supply installed IDF5.5")
    version_source=(idf/"tools/cmake/version.cmake").read_text()
    version=tuple(int(re.search(r"set\(IDF_VERSION_"+part+r" (\d+)\)",version_source).group(1)) for part in ("MAJOR","MINOR","PATCH"))
    require(version==(5,5,0),"Requires IDF5.5.0")
    environment=dict(os.environ,IDF_PATH=str(idf),IDF_COMPONENT_MANAGER="0",PYTHONDONTWRITEBYTECODE="1")
    if not environment.get("IDF_PYTHON_ENV_PATH"):
        candidates=sorted(p for p in (Path.home()/".espressif/python_env").glob("idf5.5_py*_env") if (p/"bin/python").is_file())
        require(candidates,"Set IDF_PYTHON_ENV_PATH for IDF5.5");environment["IDF_PYTHON_ENV_PATH"]=str(candidates[-1])
    project=ROOT/"object-benchmark"
    directory=ROOT/f"build/object-benchmark-{args.board}-{args.fixture_id}{'-'+args.variant if args.variant else ''}"
    if (directory/"build-report.json").exists():
        previous=read_json(read_regular(directory/"build-report.json",16*1024*1024),"existing benchmark report")
        require(previous.get("source_files_sha256")==sources() and previous.get("benchmark")==policy and previous.get("modules")==modules,
                "Existing benchmark artifacts have another identity; select a fresh --variant to preserve them")
    directory.mkdir(parents=True,exist_ok=True);config_dir=directory/"fixture-config";config_dir.mkdir(exist_ok=True)
    header_path=config_dir/"bench_config.h";header_path.write_text(header)
    definitions=["IDF_TARGET=esp32s3",f"SDKCONFIG={directory/'sdkconfig'}",
        f"SDKCONFIG_DEFAULTS={project/'sdkconfig.defaults'};{project/f'sdkconfig.{args.board}.defaults'}",
        f"OBJECT_BENCH_DEPENDENCIES_DIR={stage}",f"OBJECT_BENCH_CONFIG_DIR={config_dir}",
        f"OBJECT_BENCH_STRICT_ELF={modules['strict']['artifact_path']}",f"OBJECT_BENCH_OPTIMIZED_ELF={modules['optimized']['artifact_path']}"]
    command=["bash","-e","-c",'source "$1/export.sh" >/dev/null; shift; exec "$IDF_PYTHON_ENV_PATH/bin/python" "$IDF_PATH/tools/idf.py" "$@"',"object-benchmark",str(idf),"-B",str(directory)]
    for definition in definitions:command += ["-D",definition]
    command.append("build");before=sources()
    with (directory/"build.log").open("w") as log:
        process=subprocess.Popen(command,cwd=project,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        assert process.stdout
        for line in process.stdout:print(line,end="",flush=True);log.write(line);log.flush()
        require(process.wait()==0,f"Benchmark build failed: {directory/'build.log'}")
    require(sources()==before,"Benchmark/SDK sources changed during compilation; rebuild")
    for key,record in modules.items():
        require(module_input(Path(record["artifact_path"]),Path(record["export_path"]),match[0]["role"])==record,"Module changed during build")
    header_after,policy_after=configuration(args,modules)
    require(header_after==header and policy_after==policy and header_path.read_text()==header,"Catalog/config changed during build")
    for name in dependencies:require(inventory(stage/name)==lock["components"][name]["files_sha256"],"Dependency changed during build")
    config=(directory/"sdkconfig").read_text()
    required=["CONFIG_ELF_LOADER=y","CONFIG_ELF_LOADER_LOAD_PSRAM=y","CONFIG_ELF_LOADER_CACHE_OFFSET=y","CONFIG_HEAP_USE_HOOKS=y","CONFIG_SPIRAM_MODE_OCT=y",f"CONFIG_ESPTOOLPY_FLASHSIZE_{'16MB' if args.board=='amoled' else '8MB'}=y"]
    forbidden=["CONFIG_ELF_LOADER_LIBC_SYMBOLS=y","CONFIG_ELF_LOADER_ESPIDF_SYMBOLS=y","CONFIG_ELF_LOADER_CUSTOMER_SYMBOLS=y","CONFIG_ELF_DYNAMIC_LOAD_SHARED_OBJECT=y"]
    require(all(x in config for x in required) and not any(x in config for x in forbidden),"Resolved loader/config mismatch")
    description=read_json(read_regular(directory/"project_description.json",8*1024*1024),"project description")
    compiler=Path(description["c_compiler"]);nm=compiler.with_name(compiler.name.removesuffix("gcc")+"nm")
    hook_object=directory/"esp-idf/main/CMakeFiles/__idf_main.dir/allocation_probe.c.obj"
    undefined=subprocess.run([str(nm),"-u",str(hook_object)],check=True,capture_output=True,text=True).stdout
    require(not any(x in undefined for x in ("__atomic","malloc","calloc","realloc","printf","semaphore","spinlock")),"Unexpected helper in allocation hooks")
    artifacts={}
    for name in (description["app_elf"],description["app_bin"],"partition_table/partition-table.bin"):
        path=directory/name;artifacts[path.relative_to(ROOT).as_posix()]={"bytes":path.stat().st_size,"sha256":sha(path)}
    report={"format":"rnbo-esp32s3-object-benchmark-build","format_version":1,"board":args.board,"artifacts":artifacts,
        "modules":modules,"benchmark":policy,"generated_header_sha256":sha(header_path),"dependencies":dependencies,
        "source_files_sha256":before,"compiler":{"path":str(compiler),"version":subprocess.run([str(compiler),"--version"],check=True,capture_output=True,text=True).stdout},
        "idf_version":json.loads((directory/"config.env").read_text())["IDF_VERSION"],"idf_git_revision":description["git_revision"],
        "sdkconfig_sha256":sha(directory/"sdkconfig"),"components":description["build_components"],"compile_commands_sha256":sha(directory/"compile_commands.json"),
        "allocation_hook_undefined_symbols":undefined,"expected_pass_prefix":"RNBO_OBJECT_BENCHMARK PASS ",
        "qualification_scope":"offline core1 process callbacks; no I2S/UI/network; no full application deadline claim",
        "hardware_executed":False,"target_performance_qualified":False}
    (directory/"build-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"Build verified; no device access: {directory/'build-report.json'}");return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except (ExportError,ValueError,KeyError,OSError,subprocess.CalledProcessError) as error:
        print(f"RNBO object benchmark rejected: {error}",file=sys.stderr);raise SystemExit(1)
