#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Seal observed per-fixture target results with build/log identities.

Reports whole-fixture process timings. Main fixtures include their excitation
objects; declared FX generators are outside the process timer. Neither scope
establishes a universal isolated-operator or application deadline bound.
New XIAO observations require an explicit matching runner/build board and
device identity. Historical AMOLED records retain their original output shape.
"""
import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import struct


# Initial oracle admission is deliberately limited to the original authored
# graphs, schemas and cases. These are fingerprints, never generated DSP bodies.
WAVE2_ORACLES = {
    'biquad-response-v1': {
        'family':'biquad', 'stimulus':'impulse-step-v1', 'limit':3e-6,
        'patch':'4e98b2dabc1779468c972de871acc719e909407b956d7dda86128e9cc196127d',
        'schema':'5ee44b4347d4f1d490c0ecb696d9fca49b9ece2d69635b837422dbf98ad9ea30',
        'raw_source':'3bf669da7e420a82f5c2370a4449c9ec791cdbef655b227fbb2057ab295015b5',
        'parameters':[
            {'paramId':'a0','index':0,'minimum':0,'maximum':1,'initialValue':.5,'exponent':1,'steps':0},
            {'paramId':'b2','index':1,'minimum':0,'maximum':.8,'initialValue':.2,'exponent':1,'steps':0},
            {'paramId':'a1','index':2,'minimum':-1,'maximum':1,'initialValue':.25,'exponent':1,'steps':0},
            {'paramId':'a2','index':3,'minimum':-1,'maximum':1,'initialValue':.125,'exponent':1,'steps':0},
            {'paramId':'b1','index':4,'minimum':-.95,'maximum':.95,'initialValue':-.4,'exponent':1,'steps':0}],
        'defaults':{'a0':.5,'a1':.25,'a2':.125,'b1':-.4,'b2':.2},
        'cases':[
            {'id':'default','parameters':{},'events':[]},
            {'id':'identity','parameters':{'a0':1,'a1':0,'a2':0,'b1':0,'b2':0},'events':[]},
            {'id':'slow-pole','parameters':{'a0':.05,'a1':0,'a2':0,'b1':-.95,'b2':0},'events':[]}],
        'model':'fresh-float64-difference-equation'},
    'nonlinear-chain-v1': {
        'family':'nonlinear', 'stimulus':'nonlinear-grid-v1', 'limit':2e-6,
        'patch':'426eace2f5d115d12b3cb61280325bff289a9ac28c9ce80652c6b466ae0aa180',
        'schema':'754c55e5f56bd5c2731847a19ed276e1ad4045849e3bcc2909acd4ec76b73ef1',
        'raw_source':'b246e2357fc3829af9d44eec0efc1aa69a82bd9157be093663005ea0eb1ea28b',
        'parameters':[{'paramId':'exponent','index':0,'minimum':.25,'maximum':4,'initialValue':2,'exponent':1,'steps':0}],
        'cases':[
            {'id':'square','parameters':{},'events':[]},
            {'id':'fractional','parameters':{'exponent':.25},'events':[]},
            {'id':'fourth','parameters':{'exponent':4},'events':[]}],
        'model':'float64-tanh-wrap-clip-pow'}
}

# Direct outputs make both wrap primitives observable. This new verification is
# only for an identical corrected-module control; the unsafe original is never
# admitted to these unrestricted finite input grids.
WRAP_ORACLE = {
    'kind':'wrap-finite-v1', 'fixture':'wrap-finite-stereo',
    'patch':'d42b66e894b6368856e3c3ef42cf402defc4103da300b2aa8bab559120393980',
    'schema':'37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570',
    'raw_source':'1c00c62a40e1c950b66f3b1c887533feb1ce7525dc384a5eb2bee87ef006a4da',
    'prepared_source':'50e01c6d9b2a854ff872b6ccbaf1c9e5077975ae36cc959d0bd1d20c69516110',
    'description':'85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314',
    'helper':'5120c1152ed007ac389bef310ac6e83fd6b32c3be9862d9c6615a365f30492fd',
    'compile_contract':'863a960afe421dd3fe9e45485750046ba3d613410647d838853e79f4eb24efe0',
    'runtime':'fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d',
    'cases':[
        {'id':name,'parameters':{},'events':[],'stimulus':{'kind':stimulus}}
        for name,stimulus in (
            ('boundaries','wrap-finite-boundaries-v1'),
            ('safe-strata','wrap-finite-safe-v1'),
            ('finite-strata','wrap-finite-strata-v1'),
            ('zero-endpoints','wrap-finite-zero-endpoints-v1'))],
    'contract':{'context':'wrap-finite-stereo','input':'finite binary32 audio samples',
                'range':[-1,1],'upper_endpoint_exclusive':True,
                'nonfinite':'upstream route unchanged and unqualified','guard_count':2}}
WRAP_STIMULI = {case['stimulus']['kind']:7+i for i,case in enumerate(WRAP_ORACLE['cases'])}

POWER_KIND = 'nonlinear-power-modes-v1'
POWER_DENSE = 'nonlinear-dense-binary32-v1'
POWER_DESCRIPTION = '20f3ba4d3a8e8a19967fa566c59a04021d35f2bdeb49fa5095b70bed6fa24cec'
POWER_CORRECTED = 'cb3034efc572a29b2d3e9cc82e733035a12b6907b6213c9c3af9ee01ab64cbfd'
POWER_COMPOSED = 'f0774e0e80519692ad9da7b645460433b14981e6e3ec1f0ce0591042a8a607b2'
POWER_COMPILE_CONTRACT = 'b08d3f3dced35995ee28990f3e9343f37bfb5c5833dd03890187b145fd3b3821'


def power_cases():
    """Public authored cases, independent of mutable target configuration."""
    f=lambda word:struct.unpack('<f',struct.pack('<I',word))[0]
    cases=[{'id':'square','parameters':{},'events':[]},
           {'id':'fractional','parameters':{'exponent':.25},'events':[]},
           {'id':'fourth','parameters':{'exponent':4},'events':[]}]
    values=(('dense-square',2),('dense-quarter',.25),('dense-fourth',4),
            ('fallback-half',.5),('fallback-one-half',1.5),('fallback-two-half',2.5),
            ('below-two',f(0x3fffffff)),('above-two',f(0x40000001)),
            ('above-quarter',f(0x3e800001)),('below-four',f(0x407fffff)))
    for name,value in values:
        cases.append({'id':name,'parameters':{'exponent':value},'events':[],
                      'stimulus':{'kind':POWER_DENSE}})
    schedules=(('mode-switches',{},[(1,.5),(32,.25),(63,1.5),(128,4),(255,2.5),(384,2),(511,.25)]),
               ('neighbor-switches',{'exponent':.25},
                [(1,f(0x3e800001)),(32,2),(64,f(0x3fffffff)),(127,f(0x40000001)),
                 (256,4),(384,f(0x407fffff)),(511,.25)]))
    for name,parameters,events in schedules:
        cases.append({'id':name,'parameters':parameters,
                      'events':[{'block':b,'id':'exponent','value':v,'form':'actual'} for b,v in events],
                      'stimulus':{'kind':POWER_DENSE}})
    return cases


def power_events(case):
    events=[{'block':0,'id':identity,'value':value} for identity,value in case['parameters'].items()]
    events+=case['events']
    return [{'block':event['block'],'index':0,'kind':1,
             'value':struct.unpack('<f',struct.pack('<f',event['value']))[0],'id':'exponent'}
            for event in sorted(events,key=lambda event:event['block'])]


def power_schedule_sha(events):
    """Explicit LE words, never C struct bytes or a host float repr."""
    wire=struct.pack('<II',0x40000000,len(events))
    for event in events:
        bits=struct.unpack('<I',struct.pack('<f',event['value']))[0]
        wire+=struct.pack('<IIII',event['block'],event['index'],event['kind'],bits)
    return hashlib.sha256(wire).hexdigest()


def power_verification(fixture,case):
    require(fixture.get('id')=='nonlinear-domains' and fixture.get('family')=='nonlinear' and
            fixture.get('role')=='fx','Power fixture identity/family/role differs')
    require(same_declaration(fixture.get('cases'),power_cases()),'Power requires fifteen authored cases and actual event schedules')
    require(same_declaration(fixture.get('verification'),{'kind':POWER_KIND,'maximum_absolute_error':2e-6}),
            'Power verification declaration differs')
    require(same_declaration(fixture.get('semantic'),{'kind':'nonlinear','exponent_default':2,'maximum_absolute_error':2e-6}),
            'Power semantic declaration differs')
    require(same_declaration(fixture.get('stimulus'),{'kind':'nonlinear-grid-v1'}),'Power base stimulus differs')
    require(type(fixture.get('blocks')) is int and fixture['blocks']==512 and
            type(fixture.get('warmup_blocks')) is int and fixture['warmup_blocks']==4 and
            type(fixture.get('seed')) is int and fixture['seed']==305419896,'Power blocks/warmup/seed differ')
    require(any(same_declaration(case,c) for c in power_cases()),'Unknown power case')
    events=power_events(case)
    return {'kind':POWER_KIND,'maximum_absolute_error':2e-6,'model':'float64-tanh-wrap-clip-pow-events-v1',
            'rounding':'once-float32','gate':'cache-error-plus-maximum-cache-rounding-error',
            'initial_exponent':2,'event_schedule':events,'event_schedule_sha256':power_schedule_sha(events)}


def power_identity(build,fixture,plan):
    contract=WAVE2_ORACLES['nonlinear-chain-v1']
    require(type(plan.get('blocks')) is int and plan['blocks']==512 and
            type(plan.get('rounds')) is int and 1<=plan['rounds']<=5,'Power block/round coverage differs')
    require(same_declaration(plan.get('parameter_schema'),contract['parameters']),'Power parameter projection differs')
    require(plan.get('patch_sha256')==contract['patch'] and plan.get('description_sha256')==POWER_DESCRIPTION,
            'Power patch/description identity differs')
    require(same_declaration(plan.get('events'),[e for c in power_cases() for e in power_events(c)]),
            'Power actual compiled event table differs')
    require(same_declaration(fixture['comparison_tolerance'],{'maximum_absolute_error':2e-6,
            'maximum_pcm_lsb_error':1,'relative_rms_level_difference':1e-4}),'Power pair tolerances differ')
    wrap_contract={**WRAP_ORACLE['contract'],'context':'nonlinear-domains','guard_count':1}
    for profile,module in build['modules'].items():
        require(profile in ('strict','optimized'),'Unknown power module profile')
        export=module['report']['prepared_export'];manifest=export['manifest'];provenance=export.get('provenance',{})
        require(manifest.get('correct_finite_wrap') is True and
                same_declaration(manifest.get('finite_wrap_contract'),wrap_contract),'Power comparison requires the same finite-wrap correction')
        require(manifest.get('editable_source_sha256')==contract['patch'] and
                manifest.get('parameter_schema_sha256')==contract['schema'] and
                type(manifest.get('parameter_count')) is int and manifest['parameter_count']==1 and
                manifest.get('sample_rate')==44100 and manifest.get('block_frames')==256,'Power source/schema/audio profile differs')
        require(provenance.get('raw_files_sha256',{}).get('rnbo_source.h')==contract['raw_source'],'Power raw source identity differs')
        files=provenance.get('prepared_files_sha256',{})
        expected={'rnbo_source.h':POWER_CORRECTED if profile=='strict' else POWER_COMPOSED,
                  'description.json':POWER_DESCRIPTION,'private_finite_wrap.h':WRAP_ORACLE['helper'],
                  'rnbo_s3_finite_wrap_source.h':WRAP_ORACLE['compile_contract']}
        if profile=='optimized':expected['rnbo_s3_scalar_powers_source.h']=POWER_COMPILE_CONTRACT
        require(all(files.get(k)==v for k,v in expected.items()),'Power prepared source/helper/type contract differs')
        runtime={k:v for k,v in sorted(files.items()) if k.startswith('common/')}
        runtime_hash=hashlib.sha256((json.dumps(runtime,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()).hexdigest()
        require(runtime_hash==WRAP_ORACLE['runtime'],'Power actual runtime/types inventory differs')
        wrap=[a for a in provenance.get('adaptations',[]) if a.get('name')=='rnbo-1.4.4-finite-wrap-even24-v1']
        require(len(wrap)==1 and wrap[0].get('context')=='nonlinear-domains' and wrap[0].get('guard_count')==1 and
                wrap[0].get('input_sha256')==contract['raw_source'] and wrap[0].get('prepared_sha256')==POWER_CORRECTED and
                wrap[0].get('runtime_tree_sha256')==WRAP_ORACLE['runtime'],'Power correction adaptation differs')
        powers=[a for a in provenance.get('adaptations',[]) if a.get('name')=='rnbo-1.4.4-float32-scalar-powers-v1']
        if profile=='strict':
            require(manifest.get('numerical_profile')=='float32-strict' and not powers and
                    'scalar_powers_contract' not in manifest and 'rnbo_s3_scalar_powers_source.h' not in files,
                    'Power reference must contain correction only')
        else:
            expected_contract={'context':'nonlinear-domains','special_exponents':[2,4,.25],'base_domain':[0,1],
                'fallback':'original-powf-with-fixnan','fixnan_retained':True,'bit_identity_claimed':False,'finite_wrap_composition':True}
            require(manifest.get('numerical_profile')=='float32-scalar-powers-v1' and
                    manifest.get('base_numerical_profile')=='float32-strict' and
                    manifest.get('numerical_identity')=='changed-rounding-float32-scalar-powers-v1' and
                    same_declaration(manifest.get('scalar_powers_contract'),expected_contract),'Power candidate numerical contract differs')
            require(len(powers)==1 and powers[0].get('input_sha256')==POWER_CORRECTED and
                    powers[0].get('prepared_sha256')==POWER_COMPOSED and powers[0].get('finite_wrap_composition') is True and
                    powers[0].get('runtime_tree_sha256')==WRAP_ORACLE['runtime'] and
                    powers[0].get('inverse_byte_identity') is True,'Power composition adaptation differs')
    left,right=(build['modules'][p]['report'] for p in ('strict','optimized'))
    for field in ('compiler','dependencies','private_support_archives'):
        require(isinstance(left.get(field),dict) and left[field] and left[field]==right.get(field),
                'Power pair compiler/dependency/math archive identity differs')
    sdk=lambda r:{k:v for k,v in r.get('source_files_sha256',{}).items() if k.startswith('module-sdk/')}
    require('module-sdk/dynamic/rnbo_s3_dynamic.cpp' in sdk(left) and sdk(left)==sdk(right),'Power pair SDK source identity differs')


@lru_cache(maxsize=2)
def power_input_data(kind,blocks=512):
    require(kind in (6,11) and blocks==512,'Unsupported power input coverage')
    boundaries=(0,0x80000000,1,0x80000001,0x7fffff,0x807fffff,0x800000,0x80800000,
                0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f7fffff,0xbf7fffff,0x3f800000,
                0xbf800000,0x3f800001,0xbf800001,0x3fc00000,0xbfc00000,0x3fffffff,0xbfffffff,
                0x40000000,0xc0000000,0x40000001,0xc0000001,0x40400000,0xc0400000)
    left_bounds=boundaries+(0x40800000,0xc0800000)
    data=bytearray();sets=[set(),set()]
    for frame in range(blocks*256):
        if kind==6:
            values=((-4,-2,-1,-.5,0,.5,1,2,4)[(frame//64)%9],
                    (-3,-2,-1,-.5,0,.25,.5,1,1.5,2,3)[(frame//64)%11])
            words=struct.unpack('<II',struct.pack('<ff',*values))
        elif frame%16==0:
            words=(left_bounds[(frame//16)%len(left_bounds)],boundaries[((frame//16)+13)%len(boundaries)])
        else:
            hr=(frame*1664525+1013904223)&0xffffffff
            exponent=(frame//4)%127 if frame%4==0 else 127-frame%4
            hl=((frame+2039)*22695477+1)&0xffffffff
            words=((hl&0x80000000)|((124+(frame//4)%5)<<23)|(hl&0x7fffff),(exponent<<23)|(hr&0x7fffff))
        data.extend(struct.pack('<II',*words))
        for channel,word in enumerate(words):sets[channel].add(word)
    coverage={'per_channel_distinct_words':[len(s) for s in sets],
              'all_channels_union_words':len(sets[0]|sets[1]),
              'scope':'Deterministic representative finite binary32 values within left[-4,4],right[-3,3]; repeated checks are not exhaustive encodings.'}
    return hashlib.sha256(data).hexdigest(),coverage


def wrap_verification(fixture,case):
    require(fixture.get('id')==WRAP_ORACLE['fixture'] and fixture.get('family')=='wrap' and fixture.get('role')=='fx',
            'Finite wrap fixture identity/family/role differs')
    require(same_declaration(fixture.get('verification'),{'kind':'wrap-finite-v1','maximum_absolute_error':0,'bit_exact':True}),
            'Finite wrap verification declaration differs')
    require(same_declaration(fixture.get('semantic'),{'kind':'wrap-finite','range':[-1,1],
            'upper_exclusive':True,'maximum_absolute_error':0,'bit_exact':True}), 'Finite wrap semantic declaration differs')
    require(same_declaration(fixture.get('cases'),WRAP_ORACLE['cases']), 'Finite wrap requires four authored ordered cases without events')
    require(same_declaration(fixture.get('stimulus'),{'kind':'wrap-finite-boundaries-v1'}), 'Finite wrap base stimulus differs')
    require(type(fixture.get('blocks')) is int and fixture['blocks']==512 and
            type(fixture.get('warmup_blocks')) is int and fixture['warmup_blocks']==4 and
            type(fixture.get('seed')) is int and fixture['seed']==305419896, 'Finite wrap blocks/warmup/seed differ')
    require(any(same_declaration(case,c) for c in WRAP_ORACLE['cases']), 'Unknown finite wrap case')
    return {'kind':'wrap-finite-v1','maximum_absolute_error':0,'model':'exact-binary32-modulo2',
            'rounding':'exact-binary32','gate':'raw-binary32-equality','bit_exact':True}


def wrap_identity(build,fixture,plan):
    require(type(plan.get('blocks')) is int and plan['blocks']==512 and
            type(plan.get('rounds')) is int and 1<=plan['rounds']<=5, 'Finite wrap block/round coverage differs')
    require(plan.get('patch_sha256')==WRAP_ORACLE['patch'] and plan.get('description_sha256')==WRAP_ORACLE['description'],
            'Finite wrap patch/description identity differs')
    require(plan.get('parameter_schema')==[] and plan.get('events')==[], 'Finite wrap has unexpected parameters/events')
    require(same_declaration(fixture['comparison_tolerance'],{'maximum_absolute_error':0,
            'maximum_pcm_lsb_error':0,'relative_rms_level_difference':0}), 'Finite wrap pair tolerances must be zero')
    require(build['modules']['strict']['artifact_sha256']==build['modules']['optimized']['artifact_sha256'],
            'Finite wrap unrestricted grids require the same corrected ELF control')
    for module in build['modules'].values():
        export=module['report']['prepared_export'];manifest=export['manifest'];provenance=export.get('provenance',{})
        require(manifest.get('correct_finite_wrap') is True and
                same_declaration(manifest.get('finite_wrap_contract'),WRAP_ORACLE['contract']),
                'Finite wrap requires the exact corrected two-guard module contract')
        require(manifest.get('editable_source_sha256')==WRAP_ORACLE['patch'] and
                manifest.get('parameter_schema_sha256')==WRAP_ORACLE['schema'] and
                type(manifest.get('parameter_count')) is int and manifest['parameter_count']==0,
                'Finite wrap source/schema/parameter identity differs')
        require(manifest.get('numerical_profile')=='float32-strict' and manifest.get('sample_rate')==44100 and
                manifest.get('block_frames')==256, 'Finite wrap strict audio profile differs')
        require(provenance.get('raw_files_sha256',{}).get('rnbo_source.h')==WRAP_ORACLE['raw_source'],
                'Finite wrap raw source identity differs')
        expected_files={'rnbo_source.h':WRAP_ORACLE['prepared_source'],'description.json':WRAP_ORACLE['description'],
                        'private_finite_wrap.h':WRAP_ORACLE['helper'],'rnbo_s3_finite_wrap_source.h':WRAP_ORACLE['compile_contract']}
        files=provenance.get('prepared_files_sha256',{})
        require(all(files.get(name)==value for name,value in expected_files.items()), 'Finite wrap prepared source/helper/type contract differs')
        runtime={name:value for name,value in sorted(files.items()) if name.startswith('common/')}
        runtime_hash=hashlib.sha256((json.dumps(runtime,indent=2,sort_keys=True,ensure_ascii=True,allow_nan=False)+'\n').encode()).hexdigest()
        require(runtime_hash==WRAP_ORACLE['runtime'],'Finite wrap actual runtime/types inventory differs')
        adaptations=[a for a in provenance.get('adaptations',[]) if a.get('name')=='rnbo-1.4.4-finite-wrap-even24-v1']
        require(len(adaptations)==1,'Missing or duplicate finite wrap adaptation provenance')
        adaptation=adaptations[0]
        require(adaptation.get('context')=='wrap-finite-stereo' and adaptation.get('guard_count')==2 and
                adaptation.get('input_sha256')==WRAP_ORACLE['raw_source'] and
                adaptation.get('prepared_sha256')==WRAP_ORACLE['prepared_source'] and
                adaptation.get('runtime_tree_sha256')==WRAP_ORACLE['runtime'], 'Finite wrap adaptation provenance differs')


def wrap_stimulus_word(kind,frame,channel):
    """Declared integer generator; no host/target transcendental assumptions."""
    magnitudes=(0,1,0x7fffff,0x800000,0x3f7fffff,0x3f800000,0x3f800001,
                0x40000000,0x40400000,0x4b7fffff,0x4b800000,0x4b800001,
                0x4bffffff,0x4c000000,0x4c000001,0x4effffff,0x4f000000,
                0x4f000001,0x4f7fffff,0x4f800000,0x4f800001,0x7f7fffff)
    if kind in (7,10):
        i=frame+(13 if kind==7 else 7)*channel
        values=magnitudes if kind==7 else magnitudes[:9]
        return ((i&1)<<31)|values[(i//2)%len(values)]
    require(kind in (8,9),'Unknown finite wrap stimulus kind')
    i=frame+2039*channel;lane=i%16;exponent=(i//16)%(151 if kind==8 else 255)
    mantissa=(0,1,2,0x3fffff,0x400000,0x7ffffd,0x7ffffe,0x7fffff)[lane%8]
    return ((lane//8)<<31)|(exponent<<23)|mantissa


def exact_wrap_word(bits):
    """Independent host arithmetic oracle, distinct from the C integer packer.

    For1<=|x|<2^24 the binary32 value, x+1, division by2 and modulo result
    are exactly representable in binary64. Larger finite values are even;
    smaller magnitudes return original raw bits, including subnormals and-0.
    """
    magnitude=bits&0x7fffffff
    require(magnitude<0x7f800000,'Finite wrap oracle does not accept nonfinite input')
    if magnitude<0x3f800000:return bits
    if magnitude>=0x4b800000:return 0
    value=struct.unpack('<f',struct.pack('<I',bits))[0]
    wrapped=value-2*math.floor((value+1)/2)
    return struct.unpack('<I',struct.pack('<f',wrapped))[0]


@lru_cache(maxsize=8)
def wrap_cache_data(kind,blocks=512):
    require(type(blocks) is int and blocks==512 and kind in (7,8,9,10),'Unreviewed finite wrap cache scope')
    inputs=hashlib.sha256();oracle=hashlib.sha256();distinct=[set(),set()]
    for frame in range(blocks*256):
        words=[wrap_stimulus_word(kind,frame,c) for c in (0,1)]
        for c,word in enumerate(words):distinct[c].add(word)
        inputs.update(struct.pack('<II',*words));oracle.update(struct.pack('<II',*(exact_wrap_word(w) for w in words)))
    return inputs.hexdigest(),oracle.hexdigest(),tuple(frozenset(s) for s in distinct)


def wrap_cache_hashes(kind,blocks=512):
    return wrap_cache_data(kind,blocks)[:2]


def wrap_input_coverage(kind,blocks=512):
    sets=wrap_cache_data(kind,blocks)[2];words=sets[0]|sets[1]
    expected={7:44,8:2416,9:4080,10:18}[kind]
    require(len(words)==expected and all(len(s)==expected for s in sets),'Finite wrap distinct input coverage differs')
    return {'distinct_input_words':len(words),'per_channel_distinct_input_words':[len(s) for s in sets],
            'finite_exponent_fields':len({(w>>23)&255 for w in words}),'signs':len({w>>31 for w in words}),
            'mantissa_patterns':len({w&0x7fffff for w in words}),
            'sorted_distinct_words_sha256':hashlib.sha256(struct.pack('<%dI'%len(words),*sorted(words))).hexdigest(),
            'scope':'Repeated checks over this exact finite input set, not an exhaustive target Float32 domain.'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def fields(line,prefix):
    require(line.startswith(prefix),'Unexpected measurement prefix')
    result={}
    for item in line[len(prefix):].strip().split():
        key,sep,value=item.partition('=')
        require(sep and key not in result,'Malformed or duplicate measurement field')
        if not key.endswith('sha256'):
            try:value=int(value)
            except ValueError:
                try:value=float(value)
                except ValueError:pass
        if isinstance(value,float):require(math.isfinite(value),'Nonfinite measurement')
        result[key]=value
    return result


def digest(value,message):
    require(isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value),message)
    return value


def same_declaration(actual,expected):
    """JSON equality with finite numeric values; bool must not impersonate0/1."""
    if type(expected) in (int,float):
        return type(actual) in (int,float) and math.isfinite(actual) and actual==expected
    if isinstance(expected,dict):
        return isinstance(actual,dict) and actual.keys()==expected.keys() and all(same_declaration(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):
        return isinstance(actual,list) and len(actual)==len(expected) and all(same_declaration(a,b) for a,b in zip(actual,expected))
    return type(actual) is type(expected) and actual==expected


def wave2_verification(fixture,case):
    declaration=fixture['verification'];kind=declaration['kind'];contract=WAVE2_ORACLES[kind]
    require(fixture.get('role')=='fx' and fixture.get('family')==contract['family'],'Oracle fixture family/role differs')
    require(same_declaration(declaration,{'kind':kind,'maximum_absolute_error':contract['limit']}),'Oracle verification declaration differs')
    require(same_declaration(fixture.get('cases'),contract['cases']),'Oracle requires the exact three authored cases without events')
    require(same_declaration(fixture.get('warmup_blocks'),4) and same_declaration(fixture.get('seed'),305419896),'Oracle warmup/seed differs')
    require(same_declaration(fixture.get('stimulus'),{'kind':contract['stimulus']}),'Oracle stimulus differs')
    semantic={'kind':contract['family'],'maximum_absolute_error':contract['limit']}
    semantic.update({'defaults':contract['defaults']} if kind=='biquad-response-v1' else {'exponent_default':2})
    require(same_declaration(fixture.get('semantic'),semantic),'Oracle semantic declaration differs')
    require(any(same_declaration(case,c) for c in contract['cases']),'Unknown oracle case')
    result={'kind':kind,'maximum_absolute_error':contract['limit'],'model':contract['model'],
            'rounding':'once-float32','gate':'cache-error-plus-maximum-cache-rounding-error'}
    if kind=='biquad-response-v1':
        coefficients=contract['defaults']|case['parameters'];result['coefficients']=coefficients
        gain=(coefficients['a0']+coefficients['a1']+coefficients['a2'])/(1+coefficients['b1']+coefficients['b2'])
        result['dc_expected']=-.125*gain
    else:result['exponent']=case['parameters'].get('exponent',2)
    return result


def wave2_identity(build,fixture,plan):
    """Independently bind the model to its graph/schema and emitted events."""
    kind=fixture['verification']['kind'];contract=WAVE2_ORACLES[kind]
    require(type(plan.get('blocks')) is int and plan['blocks']==512,'Oracle first scope requires512 blocks')
    require(type(plan.get('rounds')) is int and 1<=plan['rounds']<=5,'Invalid oracle round count')
    require(same_declaration(plan.get('parameter_schema'),contract['parameters']),'Oracle parameter projection differs')
    require(plan.get('patch_sha256')==contract['patch'],'Oracle patch identity differs')
    for module in build['modules'].values():
        export=module['report']['prepared_export'];manifest=export['manifest']
        require(manifest.get('editable_source_sha256')==contract['patch'] and manifest.get('parameter_schema_sha256')==contract['schema'],'Oracle source/schema identity differs')
        require(type(manifest.get('parameter_count')) is int and manifest['parameter_count']==len(contract['parameters']),'Oracle module parameter count differs')
        require(manifest.get('sample_rate')==44100 and manifest.get('block_frames')==256,'Oracle module audio profile differs')
        require(export.get('provenance',{}).get('raw_files_sha256',{}).get('rnbo_source.h')==contract['raw_source'],'Oracle raw generated source identity differs')
    tolerance=fixture['comparison_tolerance']
    for key,maximum in (('maximum_absolute_error',2e-6),('relative_rms_level_difference',1e-4)):
        value=tolerance.get(key);require(type(value) in (int,float) and math.isfinite(value) and 0<=value<=maximum,'Oracle pair tolerance widened or invalid')
    value=tolerance.get('maximum_pcm_lsb_error');require(type(value) is int and 0<=value<=1,'Oracle PCM tolerance widened or invalid')
    events=plan.get('events');require(isinstance(events,list),'Missing oracle event table')
    schema={p['paramId']:p for p in contract['parameters']};position=0
    for case in fixture['cases']:
        parameters=case['parameters'];chunk=events[position:position+len(parameters)];position+=len(parameters)
        require(len(chunk)==len(parameters),'Incomplete oracle event table')
        seen=set()
        for event in chunk:
            require(isinstance(event,dict) and set(event)=={'block','index','kind','value','id'},'Unknown oracle event metadata')
            identity=event['id'];require(isinstance(identity,str) and identity in parameters and identity not in seen,'Unknown/duplicate oracle event')
            seen.add(identity);rounded=struct.unpack('<f',struct.pack('<f',parameters[identity]))[0]
            expected={'block':0,'index':schema[identity]['index'],'kind':1,'value':rounded,'id':identity}
            require(same_declaration(event,expected),'Oracle parameter event differs')
    require(position==len(events),'Unexpected oracle parameter events')


def declared_stimulus(fixture,case):
    wave2={'impulse-step-v1':4,'mixed-tone-v1':5,'nonlinear-grid-v1':6,POWER_DENSE:11,**WRAP_STIMULI}
    base=fixture.get('stimulus');override=case.get('stimulus',{})
    require(isinstance(base,dict) and isinstance(override,dict),'FX stimulus declaration missing')
    if base.get('kind') in wave2:
        require(set(base)=={'kind'} and set(override)<={'kind'},'Unknown wave2 stimulus fields')
        settings=base|override;require(settings.get('kind') in wave2,'Unknown wave2 stimulus kind')
        return {'kind':wave2[settings['kind']],'settings':settings,**{k:0.0 for k in ('base','depth','rate','pilot_frequency','pilot_amplitude','excitation','level')}}
    contracts={
        'midi-stereo-v1':(1,{'kind','base','depth','rate','pilot_frequency','pilot_amplitude'}),
        'frequency-stereo-v1':(2,{'kind','frequency','depth','rate','pilot_frequency','pilot_amplitude'}),
        'reson-stereo-v1':(3,{'kind','excitation','level','center','depth','rate'})}
    base=fixture.get('stimulus');override=case.get('stimulus',{})
    require(isinstance(base,dict) and isinstance(override,dict),'FX stimulus declaration missing')
    require(base.get('kind') in contracts,'Unknown FX stimulus contract')
    kind,keys=contracts[base['kind']]
    require(set(base)==keys and set(override)<=keys-{'kind'},'Unknown/missing FX stimulus fields or kind override')
    settings=base|override
    for key,value in settings.items():
        if key!='kind':require(type(value) in (int,float) and math.isfinite(value),'Nonfinite or invalid declared stimulus value')
    return {'kind':kind,'settings':settings,
            'base':settings['base' if kind==1 else 'frequency' if kind==2 else 'center'],
            'depth':settings['depth'],'rate':settings['rate'],
            'pilot_frequency':settings.get('pilot_frequency',0.0),'pilot_amplitude':settings.get('pilot_amplitude',0.0),
            'excitation':settings.get('excitation',0.0),'level':settings.get('level',0.0)}


def declared_verification(fixture,case):
    declaration=fixture.get('verification')
    kind=(fixture.get('stimulus',{})|case.get('stimulus',{})).get('kind')
    if declaration is None:
        require(kind not in ('impulse-step-v1','mixed-tone-v1','nonlinear-grid-v1',POWER_DENSE,*WRAP_STIMULI),'Missing explicit verification contract')
        return None
    if isinstance(declaration,dict) and declaration.get('kind')==POWER_KIND:
        return power_verification(fixture,case)
    if isinstance(declaration,dict) and declaration.get('kind')=='wrap-finite-v1':
        return wrap_verification(fixture,case)
    if isinstance(declaration,dict) and declaration.get('kind') in WAVE2_ORACLES:
        return wave2_verification(fixture,case)
    expected={'kind':'average-window-v1','parameter_id':'window','default_window':16,'maximum_window':64,'maximum_absolute_error':2e-6}
    require(fixture.get('role')=='fx' and fixture.get('family')=='average' and declaration==expected,'Unsupported average verification contract')
    require(kind in ('impulse-step-v1','mixed-tone-v1'),'Average verification has unmodeled input')
    semantic=fixture.get('semantic',{})
    require(semantic.get('kind')=='average' and semantic.get('default_window')==16 and semantic.get('maximum_absolute_error')==2e-6,'Average semantic declaration differs')
    require(isinstance(case.get('events',[]),list) and not case.get('events',[]),'Average events are not modeled')
    parameters=case.get('parameters',{})
    require(isinstance(parameters,dict) and set(parameters)<={'window'},'Unknown average parameter')
    n=parameters.get('window',16)
    require(type(n) in (int,float) and math.isfinite(n) and n==int(n) and 1<=n<=64,'Average window must be integer1..64')
    n=int(n);initial=min(16,fixture['warmup_blocks']*256) if n==16 else 0
    return {'kind':'average-window-v1','window':n,'initial_available':initial,'maximum_absolute_error':2e-6,
            'default_window':16,'maximum_window':64,'parameter_id':'window','model':'fresh-float64-window-sum',
            'rounding':'once-float32','gate':'cache-error-plus-maximum-cache-rounding-error'}


def oracle_memory_budget(build,plan):
    budget=plan.get('psram_budget');require(isinstance(budget,dict),'Missing oracle PSRAM budget')
    blocks=plan['blocks'];arena=plan.get('arena_bytes');require(type(arena) is int and 4096<=arena<=1048576,'Invalid selected arena budget')
    kind=plan['fixture'].get('verification',{}).get('kind')
    expected_count=5 if kind=='biquad-response-v1' else 0 if kind=='wrap-finite-v1' else 1
    require(all(build['modules'][p]['report']['prepared_export']['manifest'].get('parameter_count')==expected_count for p in ('strict','optimized')),'Oracle module parameter count differs')
    loaded=sum(build['modules'][p]['inspection']['loaded_bytes_upper_bound'] for p in ('strict','optimized'))
    expected={'workspace_bytes':blocks*256*2*4*2+4*256*4,'oracle_cache_bytes':blocks*256*2*4,
              'arena_bytes':2*arena,'opaque_context_upper_bound_bytes':2*1048576,'loaded_images_upper_bound_bytes':loaded,
              'loader_heap_alignment_reserve_bytes':524288,'physical_psram_bytes':8*1048576}
    expected['required_upper_bound_bytes']=sum(expected[k] for k in expected if k!='physical_psram_bytes')
    require(budget==expected and expected['required_upper_bound_bytes']<=expected['physical_psram_bytes'],'Oracle PSRAM budget differs or exceeds capacity')
    return budget


def input_evidence(build,fixture,plan,passed,lines,expected_samples):
    name=fixture['id'];role=fixture['role'];case_count=len(fixture['cases'])
    prefix='RNBO_OBJECT_BENCHMARK INPUT ';oracle_prefix='RNBO_OBJECT_BENCHMARK ORACLE '
    records=[fields(line.strip(),prefix) for line in lines if line.strip().startswith(prefix)]
    oracle_records=[fields(line.strip(),oracle_prefix) for line in lines if line.strip().startswith(oracle_prefix)]
    evidence={}
    if role=='main':
        require(not records and not oracle_records,'Main fixture cannot claim external INPUT/oracle evidence')
        require('stimulus' not in fixture and 'verification' not in fixture and all('stimulus' not in c for c in fixture['cases']),'Main fixture declares ignored stimulus')
        require('stimuli' not in plan or plan['stimuli']==[None]*case_count,'Main plan declares external stimulus')
        require('verifications' not in plan or plan['verifications']==[None]*case_count,'Main plan declares oracle')
        require(all(passed.get(k,0)==0 for k in ('input_cases','input_rechecks','pilot_sample_checks','oracle_cases','oracle_rechecks','semantic_sample_checks','dc_sample_checks','oracle_bit_sample_checks','oracle_bit_differences')),'Main fixture has unexpected FX input counters')
        return evidence,None
    require(len(records)==case_count,'Incomplete FX INPUT evidence')
    verifications=[declared_verification(fixture,c) for c in fixture['cases']]
    new_model=fixture.get('verification',{}).get('kind') in WAVE2_ORACLES
    exact_wrap=fixture.get('verification',{}).get('kind')=='wrap-finite-v1'
    powers=fixture.get('verification',{}).get('kind')==POWER_KIND
    if new_model:wave2_identity(build,fixture,plan)
    if exact_wrap:wrap_identity(build,fixture,plan)
    if powers:power_identity(build,fixture,plan)
    oracle_count=sum(v is not None for v in verifications);pilot_count=case_count-oracle_count
    expected_counts={'input_cases':case_count,'input_rechecks':case_count*plan['rounds']*3,'pilot_sample_checks':expected_samples*pilot_count,
                     'oracle_cases':oracle_count,'oracle_rechecks':oracle_count*plan['rounds']*3,'semantic_sample_checks':expected_samples*oracle_count*2}
    for key,expected in expected_counts.items():
        value=passed.get(key,0) if not oracle_count and key in ('oracle_cases','oracle_rechecks','semantic_sample_checks') else passed.get(key)
        require(type(value) is int and value==expected,'FX input/pilot coverage differs: '+key)
    require(len(oracle_records)==oracle_count,'Incomplete average ORACLE evidence')
    require('verifications' not in plan and not oracle_count or same_declaration(plan.get('verifications'),verifications),'Compiled verification differs from declaration')
    require(isinstance(plan.get('stimuli'),list) and len(plan['stimuli'])==case_count,'Compiled stimulus plan missing')
    for index,case in enumerate(fixture['cases']):
        expected=declared_stimulus(fixture,case);verification=verifications[index]
        require(plan['stimuli'][index]==expected,'Compiled stimulus differs from catalog/case declaration')
        found=[r for r in records if r.get('fixture')==name and r.get('case')==case['id']]
        require(len(found)==1,'Missing or duplicate FX INPUT case')
        record=found[0];digest(record.get('input_sha256'),'Malformed target input SHA256')
        if exact_wrap or powers:
            require(set(record)=={'fixture','case','input_sha256','input_bytes','layout','stimulus_kind'},
                    'Unknown or missing finite wrap input metadata')
        require(type(record.get('input_bytes')) is int and record['input_bytes']==plan['blocks']*256*2*4,'FX input byte coverage differs')
        require(record.get('layout')=='float32_stereo_interleaved_le','FX input layout differs')
        require(type(record.get('stimulus_kind')) is int and record['stimulus_kind']==expected['kind'],'FX input stimulus kind differs')
        if exact_wrap:
            expected_input,expected_oracle=wrap_cache_hashes(expected['kind'],plan['blocks'])
            require(record['input_sha256']==expected_input,'Finite wrap deterministic input SHA differs')
        if powers:
            expected_input,coverage=power_input_data(expected['kind'],plan['blocks'])
            require(record['input_sha256']==expected_input,'Power deterministic input SHA differs')
        evidence[case['id']]={**record,'declared_settings':expected['settings']}
        if exact_wrap:evidence[case['id']]['distinct_input_coverage']=wrap_input_coverage(expected['kind'],plan['blocks'])
        if powers:evidence[case['id']]['distinct_input_coverage']=coverage
        if verification:
            candidates=[r for r in oracle_records if r.get('fixture')==name and r.get('case')==case['id']]
            require(len(candidates)==1,'Missing or duplicate ORACLE case');oracle=candidates[0]
            if verification['kind'] in WAVE2_ORACLES or exact_wrap or powers:
                keys={'fixture','case','oracle_sha256','oracle_bytes','layout','oracle_kind','max_abs_tolerance','max_cache_rounding_error','model','rounding'}
                if powers:keys.update(('initial_exponent','event_schedule_sha256'))
                elif not exact_wrap:keys.update(verification['coefficients'] if verification['kind']=='biquad-response-v1' else ('exponent',))
                require(set(oracle)==keys,'Unknown or missing oracle metadata')
            digest(oracle.get('oracle_sha256'),'Malformed oracle SHA256')
            require(type(oracle.get('oracle_bytes')) is int and oracle['oracle_bytes']==plan['blocks']*256*2*4,'Oracle byte coverage differs')
            require(oracle.get('layout')=='float32_stereo_interleaved_le' and oracle.get('oracle_kind')==verification['kind'],'Oracle layout/model kind differs')
            if verification['kind']=='average-window-v1':
                require(oracle.get('window')==verification['window'] and oracle.get('initial_available')==verification['initial_available'],'Oracle history/window differs')
            elif exact_wrap:
                require(oracle['oracle_sha256']==expected_oracle,'Finite wrap independent oracle SHA differs')
            elif powers:
                require(same_declaration(oracle.get('initial_exponent'),verification['initial_exponent']) and
                        oracle.get('event_schedule_sha256')==verification['event_schedule_sha256'],'Power oracle initial exponent/event schedule differs')
            elif verification['kind']=='biquad-response-v1':
                require(same_declaration({key:oracle.get(key) for key in verification['coefficients']},verification['coefficients']),'Oracle Float64 coefficients differ')
            else:
                require(same_declaration(oracle.get('exponent'),verification['exponent']),'Oracle exponent differs')
            require(oracle.get('max_abs_tolerance')==verification['maximum_absolute_error'],'Oracle tolerance differs')
            require(oracle.get('model')==verification['model'] and oracle.get('rounding')==verification['rounding'],'Oracle precision/model differs')
            error=oracle.get('max_cache_rounding_error');require(type(error) in (int,float) and 0<=error<=2**-24,'Invalid oracle cache rounding error')
            if exact_wrap:require(error==0,'Finite wrap oracle must have zero cache rounding error')
            evidence[case['id']]['oracle']={**oracle,'verification':verification}
    source_names=('object-benchmark/main/stimulus.c','object-benchmark/main/stimulus.h');sources=build.get('source_files_sha256',{})
    generator={key:digest(sources.get(key),'Missing generator source identity') for key in source_names}
    provenance={'catalog_path':plan.get('catalog_path'),'catalog_sha256':digest(plan.get('catalog_sha256'),'Missing stimulus catalog identity'),
                'patch_sha256':digest(plan.get('patch_sha256'),'Missing fixture patch identity'),
                'generator_source_sha256':generator,'sample_rate':44100,'block_frames':256,
                'sample_time':'Zero-based rendered frame n/44100 after zero-input warmup',
                'generation':'Float64 sine/arithmetic; round each completed channel sample once to Float32',
                'timing':'Generator/oracle precomputation and cache copy excluded from process timers',
                'rechecks':'Cached INPUT and declared ORACLE SHA before/after every pass; shared adjacent-pass checkpoint',
                'pilot':('Every output reference/pilot sample equals its declared input channel' if pilot_count else
                         'No pilot samples; both output channels use the declared mathematical oracle' if new_model else
                         'No pilot samples; both output channels use the declared average oracle'),
                'limit':'Target SHA fingerprints actual cached input; host/target transcendental byte identity is not assumed'}
    require(isinstance(provenance['catalog_path'],str) and provenance['catalog_path'],'Missing stimulus catalog path')
    if oracle_count:
        stem='wave2_oracle' if new_model or exact_wrap or powers else 'average_oracle'
        provenance['oracle_source_sha256']={key:digest(sources.get(key),'Missing oracle source identity') for key in (f'object-benchmark/main/{stem}.c',f'object-benchmark/main/{stem}.h')}
        provenance['verification_contract']=fixture['verification'];provenance['psram_budget']=oracle_memory_budget(build,plan)
        if exact_wrap:
            provenance['generation']='Deterministic raw IEEEbinary32 finite words; exact little-endian bit copy, no transcendental or numeric input rounding.'
            provenance['oracle']='Independent host binary64 floor arithmetic over the exact below2^24 domain, raw signed-zero identity and even-integer large-value proof; target integer-bit modulo packer is separate.'
            provenance['semantic_gate']='Every output raw binary32 word equals the independently hashed oracle; numeric/cache-rounding errors and bit differences must all be zero.'
            provenance['limit']='Both cached INPUT and ORACLE SHA must equal independently regenerated complete host bytes. Finite fixed[-1,1) only; no nonfinite/fenv/general-range claim.'
            provenance['pilot']='No pilot; both direct wrap output channels are checked against the exact oracle.'
            provenance['parameter_schema']=plan['parameter_schema'];provenance['events']=plan['events']
            union=frozenset().union(*(s for stimulus in plan['stimuli'] for s in wrap_cache_data(stimulus['kind'],plan['blocks'])[2]))
            exponents={(w>>23)&255 for w in union};signs={w>>31 for w in union};mantissas={w&0x7fffff for w in union}
            require(len(union)==4080 and exponents==set(range(255)) and signs=={0,1} and len(mantissas)==8,
                    'Finite wrap total distinct input coverage differs')
            provenance['distinct_input_coverage']={'all_cases_union_words':len(union),'finite_exponent_fields':len(exponents),
                'signs':len(signs),'mantissa_patterns':len(mantissas),
                'sorted_distinct_words_sha256':hashlib.sha256(struct.pack('<%dI'%len(union),*sorted(union))).hexdigest(),
                'scope':'4080 distinct finite input words across four cases; repeated oracle check totals count executions, not distinct encodings.'}
        elif new_model or powers:
            provenance['oracle']='Original catalog Float64 model over actual Float32 input; once Float32 cache rounding. Native/target libm byte identity is not assumed.'
            provenance['semantic_gate']='Maximum output/cache error plus maximum cache/model rounding error must stay within the unchanged declared semantic limit.'
            provenance['parameter_schema']=plan['parameter_schema']
            provenance['events']=plan['events']
            if powers:
                provenance['pilot']='No pilot samples; both output channels use the declared mathematical oracle.'
                provenance['generation']='Independent complete INPUT SHA regeneration: original held dyadic grid or deterministic raw binary32 dense strata; no transcendental input generation.'
                provenance['oracle']='Fresh Float64 tanh/wrap/clip/pow per sample, replaying actual Float32 events before each block from source default2. Once Float32 cache rounding; host/target libm byte identity is not assumed.'
                provenance['rounding_scope']='Changed Float32 rounding and signed zero are diagnosed pairwise, not required bit-identical. No nonfinite, fenv, normalized-event or all-domain power claim.'
        else:
            provenance['oracle']='Fresh Float64 window sum over actual Float32 input; once Float32 cache rounding. fsum bit identity is not claimed.'
            provenance['semantic_gate']='Maximum output/cache error plus maximum cache/model rounding error must be <= declared2e-6'
    return evidence,provenance


def device_identity(value):
    """The runner accepts either exact 48-bit MAC spelling, without guesses."""
    require(type(value) is str and re.fullmatch(r'(?:[0-9a-fA-F]{12}|[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})',value) is not None,
            'Explicit board requires the exact runner device identity')
    compact=value.replace(':','').lower()
    return ':'.join(compact[i:i+2] for i in range(0,12,2))


def board_evidence(build,run):
    """Bind new observations without relabelling historical AMOLED fixtures.

    The runner performs the physical USB/backup identity checks. This collector
    checks the saved assertions and their hash-bound report; it does not access
    a device or establish that a caller-authored report is authentic.
    """
    build_board=build.get('board')
    if 'board' not in run:
        # Earlier builder versions always targeted AMOLED. Some historical
        # synthetic reports omit its board key; preserve those legacy tests
        # and evidence without adding a retrospective board/device assertion.
        require(build_board in (None,'amoled'),'XIAO evidence requires an explicit runner board')
        return None
    board=run['board']
    names={'amoled':'Waveshare AMOLED 1.8 V2','xiao':'XIAO ESP32-S3'}
    require(type(board) is str and board in names,'Unknown explicit runner board')
    require(type(build_board) is str and build_board==board,'Runner/build board identity differs')
    flash_bytes=run.get('flash_bytes')
    require(type(flash_bytes) is int and flash_bytes=={'amoled':0x1000000,'xiao':0x800000}[board],
            'Runner flash size differs from explicit board')
    require(run.get('format')=='rnbo-isolated-hardware-test' and type(run.get('format_version')) is int and
            run['format_version']==1,'Explicit board requires the hardware runner record format')
    raw_device=run.get('device_id');device=device_identity(raw_device)
    artifacts=build.get('artifacts')
    require(type(artifacts) is dict and all(type(n) is str for n in artifacts),
            'Explicit board requires build artifact identities')
    elfs=[v for n,v in artifacts.items()if Path(n).suffix=='.elf' and 'bootloader' not in Path(n).parts]
    apps=[v for n,v in artifacts.items()if Path(n).suffix=='.bin' and
          Path(n).name not in ('partition-table.bin','bootloader.bin') and
          not {'partition_table','bootloader'}.intersection(Path(n).parts)]
    require(len(elfs)==len(apps)==1,'Explicit board requires exactly one app ELF and app binary')
    for label,artifact,field in (('ELF',elfs[0],'test_elf_sha256'),('app',apps[0],'test_app_sha256')):
        require(type(artifact) is dict and type(artifact.get('bytes')) is int and artifact['bytes']>0 and
                type(artifact.get('sha256')) is str and re.fullmatch(r'[0-9a-fA-F]{64}',artifact['sha256']) is not None,
                'Invalid explicit build '+label+' artifact identity')
        reported=run.get(field)
        require(type(reported) is str and re.fullmatch(r'[0-9a-fA-F]{64}',reported) is not None and
                reported.lower()==artifact['sha256'].lower(),'Run '+label+' identity differs from build artifact')
    restoration=run.get('restoration')
    require(type(restoration) is dict,'Explicit board requires restored status metadata')
    status=restoration.get('status')
    require(type(status) is dict and status.get('board')==names[board],'Restored status board identity differs')
    if 'device_id' in status:
        restored_device=status['device_id']
        require(device_identity(restored_device)==device,
                'Restored status device identity differs')
    return {'board':board,'flash_bytes':flash_bytes,'device_id':device,
            'board_binding':{'method':'explicit-runner-and-build-report',
                'build_board':build_board,'runner_board':board,'flash_bytes':flash_bytes,
                'runner_device_id':raw_device,'restored_status_board':status['board'],
                'device_identity':'runner-verified USB/backup identity; saved record consistency checked by collector'}}


def collect(build_dir,run_dir):
    build_path=build_dir/'build-report.json';run_path=run_dir/'hardware-test.json';log=run_dir/'test-serial.log'
    build=json.loads(build_path.read_text());run=json.loads(run_path.read_text())
    require(run['result']=='passed' and run['restoration']['result']=='restored','Test or instrument recovery did not pass')
    binding=board_evidence(build,run)
    require(sha(build_path)==run['test_build_report_sha256'],'Build report changed after hardware test')
    require(sha(log)==run['serial_log_sha256'],'Serial log changed after hardware test')
    lines=log.read_text().splitlines();prefix='RNBO_OBJECT_BENCHMARK PASS '
    matches=[line.strip() for line in lines if line.strip().startswith(prefix)]
    require(matches==[run['pass_line']],'Expected exactly the verified complete PASS line')
    passed=fields(matches[0],prefix);plan=build['benchmark'];fixture=plan['fixture'];name=fixture['id']
    require(passed['fixture']==name and passed['firmware_elf_sha256']==run['test_elf_sha256'],'Fixture or firmware identity differs')
    role=fixture['role'];require(role in ('main','fx'),'Unknown fixture role')
    for profile,field in (('strict','strict_module_sha256'),('optimized','optimized_module_sha256')):
        require(passed[field]==build['modules'][profile]['artifact_sha256'],'Native module identity differs')
        manifest=build['modules'][profile]['report']['prepared_export']['manifest']
        require(manifest['role']==role and manifest['audio_inputs']==(2 if role=='fx' else 0) and manifest['audio_outputs']==2,'Module role/channel declaration differs')
    numerical_profiles={p:build['modules'][p]['report']['prepared_export']['manifest']['numerical_profile'] for p in ('strict','optimized')}
    prefix_profiles='RNBO_OBJECT_BENCHMARK NUMERICAL_PROFILES '
    profile_lines=[fields(line.strip(),prefix_profiles) for line in lines if line.strip().startswith(prefix_profiles)]
    if 'numerical_profiles' in plan:
        require(plan['numerical_profiles']==numerical_profiles,'Build numerical profiles differ from module manifests')
        require(profile_lines==[{'fixture':name,'reference':numerical_profiles['strict'],'candidate':numerical_profiles['optimized']}],
                'Missing or inconsistent numerical profile record')
    else:
        require(not profile_lines and numerical_profiles['strict']=='float32-strict','Legacy reference must be float32-strict')
    for field in ('host_heap_allocations','host_heap_frees','local_late_allocations'):
        require(passed[field]==0,'Unexpected running allocation')
    require(passed['psram_before']==passed['psram_after'] and passed['internal_after']>=passed['internal_before'],'Module memory did not recover')
    require(passed['images']==passed['finalized_images']==4,'Missing image finalization')
    require(passed['cases']==len(fixture['cases']) and passed['rounds']==plan['rounds'] and passed['blocks_per_pass']==plan['blocks'],'Measurement plan differs')
    require(passed['timing_exclude']==plan['timing_exclude_blocks'],'Timing exclusion differs')
    require(passed['warmup']==fixture['warmup_blocks'] and passed['seed']==fixture['seed'],'Initial state differs')
    expected_blocks=plan['rounds']*(plan['blocks']-plan['timing_exclude_blocks'])
    expected_samples=plan['rounds']*plan['blocks']*512
    inputs,stimulus_provenance=input_evidence(build,fixture,plan,passed,lines,expected_samples)
    cases=[]
    case_lines=[fields(line.strip(),'RNBO_OBJECT_BENCHMARK CASE ') for line in lines if line.strip().startswith('RNBO_OBJECT_BENCHMARK CASE ')]
    timing_lines=[fields(line.strip(),'RNBO_OBJECT_BENCHMARK CASE_PROFILE ') for line in lines if line.strip().startswith('RNBO_OBJECT_BENCHMARK CASE_PROFILE ')]
    require(len(case_lines)==len(fixture['cases']) and len(timing_lines)==2*len(case_lines),'Incomplete case measurements')
    semantic_prefix='RNBO_OBJECT_BENCHMARK CASE_SEMANTIC '
    semantic_records=[fields(line.strip(),semantic_prefix) for line in lines if line.strip().startswith(semantic_prefix)]
    expected_semantic_cases=sum('oracle' in value for value in inputs.values())
    require(len(semantic_records)==2*expected_semantic_cases,'Incomplete semantic measurements')
    dc_prefix='RNBO_OBJECT_BENCHMARK CASE_DC '
    dc_records=[fields(line.strip(),dc_prefix) for line in lines if line.strip().startswith(dc_prefix)]
    dc_cases=sum(value.get('oracle',{}).get('verification',{}).get('kind')=='biquad-response-v1' for value in inputs.values())
    require(len(dc_records)==2*dc_cases,'Incomplete or unexpected DC measurements')
    dc_count=passed.get('dc_sample_checks',0)
    require(type(dc_count) is int and dc_count==dc_cases*plan['rounds']*2,'DC sample coverage differs')
    bits_prefix='RNBO_OBJECT_BENCHMARK CASE_BITS '
    bit_records=[fields(line.strip(),bits_prefix) for line in lines if line.strip().startswith(bits_prefix)]
    bit_cases=sum(value.get('oracle',{}).get('verification',{}).get('kind')=='wrap-finite-v1' for value in inputs.values())
    require(len(bit_records)==2*bit_cases,'Incomplete or unexpected exact-bit measurements')
    rounding_prefix='RNBO_OBJECT_BENCHMARK CASE_ROUNDING '
    rounding_records=[fields(line.strip(),rounding_prefix) for line in lines if line.strip().startswith(rounding_prefix)]
    power_mode=fixture.get('verification',{}).get('kind')==POWER_KIND
    require(len(rounding_records)==(len(fixture['cases']) if power_mode else 0),
            'Incomplete or unexpected pair rounding diagnostics')
    bit_fields={'oracle_bit_sample_checks','oracle_bit_differences'}&passed.keys()
    require(len(bit_fields)==2 if bit_cases else len(bit_fields) in (0,2), 'Missing or incomplete PASS exact-bit counter schema')
    bit_count=passed.get('oracle_bit_sample_checks',0)
    bit_differences=passed.get('oracle_bit_differences',0)
    require(type(bit_count) is int and bit_count==expected_samples*bit_cases*2,'Exact-bit sample coverage differs')
    require(type(bit_differences) is int and bit_differences==0,'Exact-bit oracle differences are not zero')
    tolerance=fixture['comparison_tolerance']
    for declared in fixture['cases']:
        records=[c for c in case_lines if c['case']==declared['id'] and c['fixture']==name]
        require(len(records)==1,'Missing or duplicate case')
        case=records[0];require(case['samples']==expected_samples,'Case sample count differs')
        require(0<=case['max_abs']<=tolerance['maximum_absolute_error'] and
                0<=case['max_pcm_lsb']<=tolerance['maximum_pcm_lsb_error'] and
                0<=case['relative_rms']<=tolerance['relative_rms_level_difference'],'Case exceeds declared output limits')
        timings={}
        for profile in ('strict','optimized'):
            values=[t for t in timing_lines if t['case']==declared['id'] and t['fixture']==name and t['profile']==profile]
            require(len(values)==1,'Missing or duplicate profile timing')
            value=values[0];require(value['timed_blocks']==expected_blocks and value['process_us']>0,'Invalid timing coverage')
            timings[profile]={**value,'numerical_profile':numerical_profiles[profile],'mean_process_us':value['process_us']/value['timed_blocks']}
        semantics={};dc={};bit_comparison={}
        if inputs.get(declared['id'],{}).get('oracle'):
            oracle=inputs[declared['id']]['oracle'];limit=oracle['max_abs_tolerance']
            for profile in ('strict','optimized'):
                matches=[r for r in semantic_records if r.get('fixture')==name and r.get('case')==declared['id'] and r.get('profile')==profile]
                require(len(matches)==1,'Missing or duplicate semantic profile');value=matches[0]
                require(value.get('semantic_kind')==oracle['verification']['kind'] and value.get('oracle_sha256')==oracle['oracle_sha256'],'Semantic oracle identity differs')
                require(type(value.get('samples')) is int and value['samples']==expected_samples and value.get('max_abs_tolerance')==limit,'Semantic sample coverage/tolerance differs')
                error=value.get('max_abs');require(type(error) in (int,float) and error>=0,'Invalid semantic error')
                bound=error+oracle['max_cache_rounding_error']
                require(value.get('max_model_error_bound')==bound and bound<=limit,'Semantic average exceeds unchanged model limit')
                semantics[profile]=value
                if oracle['verification']['kind']=='wrap-finite-v1':
                    require(set(value)=={'fixture','case','profile','semantic_kind','samples','max_abs',
                            'max_model_error_bound','max_abs_tolerance','oracle_sha256'}, 'Unknown or missing finite wrap semantic metadata')
                    matches=[r for r in bit_records if r.get('fixture')==name and r.get('case')==declared['id'] and r.get('profile')==profile]
                    require(len(matches)==1,'Missing or duplicate exact-bit profile');record=matches[0]
                    require(set(record)=={'fixture','case','profile','oracle_sha256','samples','bit_different'}, 'Unknown or missing exact-bit metadata')
                    require(record.get('oracle_sha256')==oracle['oracle_sha256'],'Exact-bit oracle identity differs')
                    require(type(record.get('samples')) is int and record['samples']==expected_samples,'Exact-bit profile sample coverage differs')
                    require(type(record.get('bit_different')) is int and record['bit_different']==0,'Exact-bit profile has different output words')
                    bit_comparison[profile]=record
                if oracle['verification']['kind']=='biquad-response-v1':
                    found=[r for r in dc_records if r.get('fixture')==name and r.get('case')==declared['id'] and r.get('profile')==profile]
                    require(len(found)==1,'Missing or duplicate DC profile');record=found[0]
                    require(set(record)=={'fixture','case','profile','expected','max_abs','samples','mean_frames','max_abs_tolerance','oracle_sha256'},'Unknown or missing DC metadata')
                    require(type(record.get('samples')) is int and record['samples']==plan['rounds'],'DC round coverage differs')
                    require(type(record.get('mean_frames')) is int and record['mean_frames']==1024,'DC mean window differs')
                    require(same_declaration(record.get('expected'),oracle['verification']['dc_expected']),'DC expected value differs')
                    require(record.get('max_abs_tolerance')==3e-6,'DC tolerance differs')
                    error=record.get('max_abs');require(type(error) in (int,float) and 0<=error<=3e-6,'DC error exceeds unchanged model limit')
                    require(record.get('oracle_sha256')==oracle['oracle_sha256'],'DC oracle identity differs')
                    dc[profile]=record
        reference=timings['strict']['mean_process_us'];candidate=timings['optimized']['mean_process_us']
        cases.append({'case':declared['id'],'declared_case':declared,'input':inputs.get(declared['id']),'semantic_comparison':semantics,'output_comparison':case,'profiles':timings,
                      'observed_speed_ratio':reference/candidate,'observed_process_reduction_percent':100*(1-candidate/reference)})
        if dc:cases[-1]['dc_comparison']=dc
        if bit_comparison:cases[-1]['bit_comparison']=bit_comparison
        if power_mode:
            matches=[r for r in rounding_records if r.get('fixture')==name and r.get('case')==declared['id']]
            require(len(matches)==1,'Missing or duplicate pair rounding case')
            record=matches[0]
            require(set(record)=={'fixture','case','samples','float_bit_different','zero_sign_different'},
                    'Unknown or missing pair rounding metadata')
            require(type(record['samples']) is int and record['samples']==expected_samples and
                    type(record['float_bit_different']) is int and type(record['zero_sign_different']) is int and
                    0<=record['zero_sign_different']<=record['float_bit_different']<=record['samples'],
                    'Invalid pair rounding sample coverage or counts')
            if declared['id']=='dense-quarter':
                require(record['zero_sign_different']>0,'Dense quarter did not observe the expected signed-zero profile difference')
            cases[-1]['rounding_comparison']=record
    require(passed['compared_samples']==expected_samples*len(cases),'Total sample count differs')
    return {**(binding or {}),'fixture':name,'family':fixture['family'],'role':fixture['role'],
            'numerical_profiles':numerical_profiles,
            'identical_artifact_control':passed['strict_module_sha256']==passed['optimized_module_sha256'],
            'scope':('Complete authored Main fixture including excitation; process callback only, no I2S/UI/network.' if role=='main' else
                     'Complete authored FX fixture with declared external signals; process callback only, generator/cache copy excluded; no I2S/UI/network.'),
            'stimulus_provenance':stimulus_provenance,
            'build_report':str(build_path),'build_report_sha256':sha(build_path),
            'hardware_report':str(run_path),'hardware_report_sha256':sha(run_path),
            'serial_log':str(log),'serial_log_sha256':sha(log),'pass':passed,'cases':cases}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='append',nargs=2,metavar=('BUILD_DIR','RUN_DIR'),required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();require(not args.out.exists(),'Choose a fresh output file')
    results=[collect(Path(b).resolve(),Path(r).resolve()) for b,r in args.run]
    require(len({r['fixture'] for r in results})==len(results),'Duplicate fixture')
    report={'format':'rnbo-object-target-observations','format_version':1,'collector_sha256':sha(Path(__file__)),
            'fixtures':results,'claim':'Observed workload comparisons; no universal numerical or worst-case timing bound'}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'report':str(args.out.resolve()),'fixtures':len(results)}))


if __name__=='__main__':main()
