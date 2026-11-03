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


# Frozen original wave4 metadata identities; no generated DSP bodies.
WAVE4_KIND='wave4-mathematical-v1'
WAVE4_MODELS=('absolute','minimum','maximum','subtract','equal','less','sum-and-difference','delta-left-observer-right')
WAVE4_INPUTS={'signed-grid-v1':12,'dense-binary32-v1':13,'vector-boundaries-v1':14}
WAVE4_IDENTITIES={
  "absolute-signal-stereo": {
    "model_code": 1,
    "original_fixture": "4cac13d6fd218c772281576fa710b0d2a97d11e5f260e1ac1af3e7df2bb13a3f",
    "patch": "da3625938474de6cc902b3518375559f1b01dc287a4df0f1686dbf0ad4305764",
    "source": "1035315dd9e3273df51041727eabb0f236b62cb944f3c8a12f9fdff27ea9c0e0",
    "source_tree": "e1bf2c87d1b1675d593683b56bf3590f9023b6bbe492f3c994db7b9700377d57"
  },
  "codebox-arithmetic": {
    "model_code": 7,
    "original_fixture": "0630421697799a936e75abf456c4f673d930b0571f5608d45e88ae50cccb3f2c",
    "patch": "107e5667d49089e4a276bebdbcccba1040f42f74274b6d868bfb5aea1ccfe80b",
    "source": "a179ffd02af10c4ba02c38be9d4a252b9be2b92fc76feaef8c9dd733d2bc45a6",
    "source_tree": "70039fb9c620e53ed929acf208a360afaa616e55b34a832b15282b5ff14617c9"
  },
  "codebox-delta-state": {
    "model_code": 8,
    "original_fixture": "bc256464b3f4ef5cdc2f14bcdb7305d5e077f2ea7d79fa2fb2f08de8fed13136",
    "patch": "1d0f85909f72dac741f8f1ab40634e4990da306ab088f66a4cc87d9a50015f75",
    "source": "8cb5a2989432c755840959b5b1acd6eb9f16638094a387c04b18bff4b0ea3827",
    "source_tree": "5000cd55d1247ceffc56fde83e4da1aab4bfd34949ed28e007b2a8719bea873d"
  },
  "equal-alias-signal": {
    "model_code": 5,
    "original_fixture": "6a99218ae9e117497adc8a31ccdbed6a0548ee527a289989b9d3fff379129cf6",
    "patch": "c3d4b15149d98652cd79da3fef0686ed7ab547d8e8de38593eb80df41fa680d1",
    "source": "8cab03d9e755c9733459869f420d6c28617160988561b10e6ddef79fa2ab98e3",
    "source_tree": "0a7cd26d7e7e512477384df4aea3fb6bbe81d978306239679218315191731bbd"
  },
  "equal-canonical-signal": {
    "model_code": 5,
    "original_fixture": "2c57f47b3caa1690d2c94874756e9da3d35fc593f92a989cafe690e581f6ec74",
    "patch": "1f6b762d970ac0438dc13b4168cb2723487d5ae7af55d1ab920d110c27f79114",
    "source": "8cab03d9e755c9733459869f420d6c28617160988561b10e6ddef79fa2ab98e3",
    "source_tree": "34d7fcaa8a3d2c89b425f5fe287b17fe28402ace0291089259b6a136d1b38e2c"
  },
  "less-alias-signal": {
    "model_code": 6,
    "original_fixture": "189ca2b5b47e9a759dfa82120e45f9cc5a3d403b15c3f570d6b70e505c32333f",
    "patch": "2c17f11cc2bdaf8ecc730b0c18a74f234ea4fa7243c0d1da5b6573601d7b1864",
    "source": "cf646ac2c294dbb203814ee96eb22bc17ca4721dc02f4a2862db79767f7e5980",
    "source_tree": "55b0469916809fa46eb57020e1aa2f1ac12ff5b49ea2846d7de53fbb9de82a63"
  },
  "less-canonical-signal": {
    "model_code": 6,
    "original_fixture": "74305eeb9afee6dee54473ade346dae22b8a1b70e9cf4b7a33ecbbb2d319b7aa",
    "patch": "e7820bc2b39c13804c1ad284f5afc08c1a637e559d93c97a9c36afad6b19346f",
    "source": "cf646ac2c294dbb203814ee96eb22bc17ca4721dc02f4a2862db79767f7e5980",
    "source_tree": "db511bfdab8b92015709ccbbbe03689277e203c075477c31694490b7c0b394a6"
  },
  "maximum-alias-signal": {
    "model_code": 3,
    "original_fixture": "133e4e259c8d226178b5af7c34e687486aa71f7d37e5fe347be97600d19ccd0e",
    "patch": "6b065ec92da9bf71b7668a67a53023e9d4aed5894a3fbd0b31327295817db6b6",
    "source": "7b6367d6cc00e272600d6e670fc772e6eef02e7ce316afb39494acfe5519119c",
    "source_tree": "2a969be6f7fb12ad01a6a19ea50f3c4413163613426c7d2b6e01bf5c95a5bac7"
  },
  "maximum-canonical-signal": {
    "model_code": 3,
    "original_fixture": "3663829e1c37ea478d197996da225275d91894ec82b75bc76e832f3d8de6c386",
    "patch": "74afaafcf651995b00309bf1bc3c60c4596eaa98730395716941a472210592ad",
    "source": "7b6367d6cc00e272600d6e670fc772e6eef02e7ce316afb39494acfe5519119c",
    "source_tree": "92d976df549ca005c92ce584336128d311f4b68b58080b5ec8a78573ea0dc45a"
  },
  "minimum-alias-signal": {
    "model_code": 2,
    "original_fixture": "5904e7240494302d4a2ce81d4fb1e0933d4d4f15d9722b605b6ee4a9a5c6ff3d",
    "patch": "516a939cf542a60f0a9566e72c246d49bd6e58b005c5f03baf232898b2331efe",
    "source": "641bd05f02cb043b0259c4a10e91346a26ee07975207d7e7d4bde45001a88468",
    "source_tree": "54efedfb1572e655312bb4b4261009bb6cafab07b19cc572f17e1fd7722c59da"
  },
  "minimum-canonical-signal": {
    "model_code": 2,
    "original_fixture": "bd182c7cb0e5953613d2da93d6671c25848f5a6ab6c999086da43107d845da47",
    "patch": "36bd71ae615de1f129e929d27cb5f1602ba8a41cb02a5dcb6e1ecb3628bad013",
    "source": "641bd05f02cb043b0259c4a10e91346a26ee07975207d7e7d4bde45001a88468",
    "source_tree": "0af0eb09122b832b240ddfd832ff28e9ee5c6bd7518637d6516b81ce375d5c6f"
  },
  "subtract-alias-signal": {
    "model_code": 4,
    "original_fixture": "694d5d16a31e6193603ea315e7ac7e0ed0fac5789d55ced03e21a7d0f94cbd47",
    "patch": "bf1f2beb9fd24ac80507d0b4291b3a664d11fad527efeb9d27dd59bf5a85409f",
    "source": "13e34e2fc89cbb750ad42d02a6903dc07ecea9456fcd7d12c4a706ce8078811b",
    "source_tree": "feedef57dc4f4d18506c85b1b94acb6df474f5244e277e128360d1f408c2e376"
  },
  "subtract-canonical-signal": {
    "model_code": 4,
    "original_fixture": "e605e72ecf02da3ba6f1cc978ba3bfb14c597ff27464ffd003b705ded8e13bfd",
    "patch": "59ab8fbc18fce82db8d05d83f037e59f93984558be1c679391c92098668e4221",
    "source": "13e34e2fc89cbb750ad42d02a6903dc07ecea9456fcd7d12c4a706ce8078811b",
    "source_tree": "3bcb4f2da0017d62fb0070a4b942b63e309c51dd144dbc0b8f8d729dac975cc8"
  }
}
WAVE4_SCHEMA='37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570'
WAVE4_RUNTIME='fd4ec5b019f6fc34ae4982636b116e38293233f598061de5480737ae1e849c5d'
WAVE4_ADAPTATIONS=['rnbo-1.4.4-list-copy-bounds-v1','rnbo-1.4.4-list-move-inline-storage-v1','rnbo-1.4.4-list-cross-capacity-assignment-v1','rnbo-1.4.4-nested-clock-target-v1','rnbo-1.4.4-defined-imul-v1']

def wave4_declaration(fixture):
    identity=fixture.get('id');require(type(identity)is str and identity in WAVE4_IDENTITIES,'Unknown exact wave4 fixture')
    pin=WAVE4_IDENTITIES[identity]
    extras={'original_cases','family','blocks','warmup_blocks','seed','stimulus','verification','comparison_tolerance'}
    original={k:v for k,v in fixture.items()if k not in extras};original['cases']=fixture.get('original_cases')
    try: original_sha=hashlib.sha256((json.dumps(original,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()).hexdigest()
    except (TypeError,ValueError):original_sha=None
    require(original_sha==pin['original_fixture'],'Wave4 original source/surface/domain/model metadata differs')
    require(fixture.get('family')=='wave4' and fixture.get('role')=='fx' and fixture.get('blocks')==64 and
            fixture.get('warmup_blocks')==4 and fixture.get('seed')==305419896,'Wave4 audio/initial state differs')
    require(fixture.get('stimulus')=={'kind':'signed-grid-v1'},'Wave4 base stimulus differs')
    cases=[{'id':name,'parameters':{},'events':[],'stimulus':{'kind':name}}for name in WAVE4_INPUTS]
    require(same_declaration(fixture.get('cases'),cases),'Wave4 requires all three original inputs in order without events')
    require(same_declaration(fixture.get('comparison_tolerance'),{'maximum_absolute_error':0,'maximum_pcm_lsb_error':0,'relative_rms_level_difference':0}),'Wave4 pair tolerances must remain zero')
    expected={'kind':WAVE4_KIND,'model_code':pin['model_code'],'maximum_absolute_error':0,
              'observer_channel':1 if pin['model_code']==8 else 2}
    require(same_declaration(fixture.get('verification'),expected),'Wave4 verification model differs')
    return expected


def wave4_verification(fixture,case):
    expected=wave4_declaration(fixture)
    require(any(same_declaration(case,c)for c in fixture['cases']),'Unknown wave4 case')
    return {**expected,'model':'independent-binary32-operations-and-input-history',
            'rounding':'once-binary32-per-output-operation','gate':'numeric-exact-plus-direct-observer-bits',
            'operation_zero_sign':'diagnostic-only','initial_previous_input':0.0}


def wave4_identity(build,fixture,plan):
    wave4_declaration(fixture);pin=WAVE4_IDENTITIES[fixture['id']]
    require(type(plan.get('blocks'))is int and plan['blocks']==64 and type(plan.get('rounds'))is int and plan['rounds']==3,
            'Wave4 requires64 blocks and three rounds')
    require(plan.get('parameter_schema')==[] and plan.get('events')==[],'Wave4 parameters/events are unmodeled')
    require(plan.get('patch_sha256')==pin['patch'],'Wave4 patch identity differs')
    require(build['modules']['strict']['artifact_sha256']==build['modules']['optimized']['artifact_sha256'],
            'Wave4 initial qualification requires same-artifact control')
    for module in build['modules'].values():
        export=module['report']['prepared_export'];manifest=export['manifest'];provenance=export.get('provenance',{})
        require(manifest.get('editable_source_sha256')==pin['patch'] and manifest.get('parameter_schema_sha256')==WAVE4_SCHEMA and
                manifest.get('source_tree_sha256')==pin['source_tree'],
                'Wave4 exact source/empty parameter schema differs')
        require(type(manifest.get('parameter_count'))is int and manifest['parameter_count']==0 and
                manifest.get('role')=='fx' and manifest.get('audio_inputs')==manifest.get('audio_outputs')==2 and
                manifest.get('sample_rate')==44100 and manifest.get('block_frames')==256 and
                manifest.get('numerical_profile')=='float32-strict' and manifest.get('scheduler_time')=='float64' and
                manifest.get('rnbo_version')=='1.4.4' and manifest.get('class_name')=='rnbos3patch' and
                manifest.get('voices')==1 and manifest.get('voice_topology')=='single-export' and
                manifest.get('required_host_services')==[] and manifest.get('midi_output_ports')==0,
                'Wave4 strict module/ABI profile differs')
        require(manifest.get('adaptations')==WAVE4_ADAPTATIONS,'Wave4 requires only normal strict runtime fixes')
        require(provenance.get('raw_files_sha256',{}).get('rnbo_source.h')==pin['source'],'Wave4 raw generated source differs')
        snapshot=module['report'].get('prepared_snapshot',{}).get('prepared_files_sha256',{})
        require(snapshot.get('rnbo_source.h')==pin['source'],'Wave4 strict prepared source differs')
        runtime={k:v for k,v in snapshot.items()if k.startswith('common/')}
        require(len(runtime)==36 and hashlib.sha256((json.dumps(runtime,sort_keys=True,indent=2)+'\n').encode()).hexdigest()==WAVE4_RUNTIME,
                'Wave4 normal fixed runtime differs')


@lru_cache(maxsize=3)
def wave4_input_bytes(kind,blocks=64):
    require(type(kind)is int and kind in WAVE4_INPUTS.values() and type(blocks)is int and blocks==64,'Unknown wave4 input/span')
    grid=((0,0x80000000),(0xbf800000,0x3f800000),(0x3f800000,0xbf800000),(0x3f000000,0x3f000000),
          (0xbf000000,0xbf000000),(0x3f7fffff,0x3f800000),(1,0),(0x80000001,0),(0x3f000001,0x3f000000),
          (0x3effffff,0x3f000000),(0x80000000,0),(0x3f800000,0x3f800000))
    result=bytearray();state=305419896
    for n in range(blocks*256):
        if kind==12:a,b=grid[(n//17)%12]
        elif kind==13:
            words=[]
            for _ in range(2):
                state=(1664525*state+1013904223)&0xffffffff
                words.append((state&0x807fffff)|(((state>>24)%127)<<23))
            a,b=words
            if n%17==0:b=a
            if n%31==0:b=a^0x80000000
        else:
            cycle=n%1024
            a=(0x3f400000 if (n//1024)%2==0 else 0xbf400000)if cycle in (0,255,256,511,512)else 0x3e800000 if cycle>=768 else 0
            b=0xbf000000 if 256<=cycle<512 else 0x3f000000 if 512<=cycle<768 else 0x80000000
        result.extend(struct.pack('<II',a,b))
    return bytes(result)


@lru_cache(maxsize=24)
def wave4_oracle_bytes(model,kind,blocks=64):
    require(type(model)is int and 1<=model<=8,'Unknown wave4 operation')
    data=wave4_input_bytes(kind,blocks);result=bytearray();previous=0.0
    def wire(v):return struct.pack('<f',v)
    for x,y in struct.iter_unpack('<ff',data):
        if model==1:a,b=abs(x),abs(y)
        elif model==2:a,b=(x if x<=y else y),(y if y<=x else x)
        elif model==3:a,b=(x if x>=y else y),(y if y>=x else x)
        elif model==4:a,b=x-y,y-x
        elif model==5:a=b=float(x==y)
        elif model==6:a,b=float(x<y),float(y<x)
        elif model==7:a,b=x+y,x-y
        else:a,b=x-previous,y;previous=x
        result.extend(wire(a));result.extend(wire(b))
    return bytes(result)


def wave4_cache_hashes(model,kind,blocks=64):
    return hashlib.sha256(wave4_input_bytes(kind,blocks)).hexdigest(),hashlib.sha256(wave4_oracle_bytes(model,kind,blocks)).hexdigest()


# Exact authored GenExpr programs only; this is not visual-Gen admission.
GEN_KIND='gen-history-v1'
GEN_INPUT='gen-history-dyadic-v1'
GEN_FEEDBACK_MODE='float32-feedback-comparison-v1'
GEN_FEEDBACK_PROFILE='float32-gen-feedback-v1'
GEN_FEEDBACK_CATALOG_SHA='122febbdbe2ffacf7192b5b232134611b82457fe40fe496881ebb1598ecb5773'
GEN_FEEDBACK_PIN={
    'source':'db07a01a185f2bad594acba9f110f8c198dec9668fb3516112573d32752d7220',
    'compile_contract':'99d6282834c2fe1e5337c491a19add3fb2d715124ac71f53d11962eb40b8ee3d',
    'config':'846d7f320d28dbefa68954a2e91e49c939a385546df5bfda7b47cb1dc6f304a4',
    'reference_config':'a0d544c36042ca826ec6cd9deb332b80b68346e0986d49af73b16f7fc5486d5b',
    'input_method':'c5392d96adb31def884394dc0e286faa9ab9530e422e384d0aee44d5a94be685',
    'prepared_method':'7ac1c56f80f1b0f23a15f2ebf4b9cd4f4c63a7b6c2471a1daab9cd13210e88c5',
    'input_map':'7cb084216600dab080984923569ddc45c2e6b8b3a73d8371877fc976069044b2',
    'transformer':'fb40788acd39bf4d7ffb4e73f2f4ac89ef2ba6b3aa1701569dccc3643a03a0e9'}
GEN_FEEDBACK_CONTRACT={'version':1,'context':'history-feedback','coefficient':.5,'operation':'binary32-multiply-then-add',
    'state_storage':'unchanged-binary32','scheduler_time':'unchanged-binary64','bit_identity_claimed':False,
    'signed_zero_identity_claimed':False,'nonfinite_qualified':False,'floating_environment_equivalence_claimed':False,
    'input_domain':{'finite':True,'absolute_maximum':.5},'state_initial_and_reset':0.,'state_absolute_bound':1.,
    'contraction':'disabled','qualification_scope':'original bounded history-feedback program and independently verified input/reset cases'}
GEN_MODELS={'history-feedback':1,'two-history-swap':2,'three-history-rotation':3}
GEN_SCHEMA=[{'paramId':'s3_reset','index':0,'minimum':0,'maximum':1,'initialValue':0,'exponent':1,'steps':0}]
GEN_IDENTITIES={
  "history-feedback": {
    "description": "5fa1adde1e70050d79dbc296a932a21b4a7efb4c8ecbd7176e9910b5de513270",
    "patch": "cc73307e6aaad1f7f3636c28e7d79baffe15eae9d59ac14bdef64dafbae6990e",
    "schema": "e968307f614911ee7e3f596ac1165fcb8073c2a1555e25fb2055dbe4aae50cb4",
    "source": "e8ea80fd692baaf54345587d8b0908b990b6c5524bbac6c52677364a60f02721",
    "source_tree": "672febb73b9738e8811350e6c3e11fd99c028b77d096ac60333f752a33f96e72"
  },
  "three-history-rotation": {
    "description": "5fa1adde1e70050d79dbc296a932a21b4a7efb4c8ecbd7176e9910b5de513270",
    "patch": "8352cd42553f02d5fe542c390d60665249ff0b0e71914dc011cb2c40d86b64f4",
    "schema": "e968307f614911ee7e3f596ac1165fcb8073c2a1555e25fb2055dbe4aae50cb4",
    "source": "34afd9a45255114d571b2469a71775e06e74caebd8d7bcb017714b8926a58d37",
    "source_tree": "8121c406780a12f687714baf0b9b64bcd040d46c9d619dcdfd538a1983634c87"
  },
  "two-history-swap": {
    "description": "5fa1adde1e70050d79dbc296a932a21b4a7efb4c8ecbd7176e9910b5de513270",
    "patch": "8302cae732b243f6198c12b690a3e479ab179983c249e028784c336cc67571aa",
    "schema": "e968307f614911ee7e3f596ac1165fcb8073c2a1555e25fb2055dbe4aae50cb4",
    "source": "ef6643c08ce20b36d5ce9f3bd6386c8f159cfc35ec1772e16aa0010ad1fbe115",
    "source_tree": "06b686c93aa4fc2025b8d7f10a4bbb4da2d610a0ef8730c52a4d75c70f8842b2"
  }
}


def gen_cases():
    return [{'id':name,'parameters':{},'events':[
        {'block':block,'id':'s3_reset','form':'actual','value':1.0} for block in blocks]}
        for name,blocks in (('continuous',()),('boundary-resets',(1,2,7,31,32,63)),
                            ('retrigger-every-block',range(64)))]


def gen_events(case):
    return [{'block':e['block'],'index':0,'kind':1,'value':1.0,'id':'s3_reset'} for e in case['events']]


def gen_schedule_sha(events):
    """Zero initial parameter word, then explicit LE event words, no padding."""
    wire=struct.pack('<II',0,len(events))
    for event in events:
        bits=struct.unpack('<I',struct.pack('<f',event['value']))[0]
        wire+=struct.pack('<IIII',event['block'],event['index'],event['kind'],bits)
    return hashlib.sha256(wire).hexdigest()


@lru_cache(maxsize=1)
def gen_input_bytes():
    values=(.25,-.125,.5,0.,-.25,.125,-.5)
    return b''.join(struct.pack('<ff',values[n%7],values[(n+3)%7])for n in range(16384))


@lru_cache(maxsize=9)
def gen_cache_data(model,case_id):
    """Fresh fsum input convolution or integer phase, never a DSP recurrence."""
    require(type(model)is int and model in (1,2,3),'Unknown Gen history model')
    case=next((c for c in gen_cases()if c['id']==case_id),None)
    require(case is not None,'Unknown Gen reset program')
    left=[x for x,_ in struct.iter_unpack('<ff',gen_input_bytes())]
    reset_blocks={e['block']for e in case['events']};epoch=-1024;mask=bytearray(64);cache=bytearray();rounding=0.
    def truth(n,anchor):
        if model!=1:
            phase=(n-anchor)%model
            return float(1+phase),float(1+(phase+1)%model)
        history=math.fsum(math.ldexp(left[n-age],1-age)for age in range(1,min(64,n-max(0,anchor))+1))
        return left[n]+.5*history,history
    def rounded(pair):return struct.unpack('<ff',struct.pack('<ff',*pair))
    for n in range(16384):
        if n%256==0 and n//256 in reset_blocks:
            before=rounded(truth(n,epoch));after=rounded(truth(n,n))
            mask[n//256]=int(max(abs(a-b)for a,b in zip(before,after))>8e-6)
            epoch=n
        pair=truth(n,epoch);wire=struct.pack('<ff',*pair);cache.extend(wire)
        rounding=max(rounding,*(abs(a-b)for a,b in zip(pair,struct.unpack('<ff',wire))))
    return bytes(cache),bytes(mask),rounding


def gen_verification(fixture,case):
    identity=fixture.get('id');require(identity in GEN_MODELS,'Unknown exact Gen history fixture')
    comparison=fixture.get('qualification_mode')==GEN_FEEDBACK_MODE
    require('qualification_mode'not in fixture or comparison and identity=='history-feedback','Unknown or unreviewed Gen qualification mode')
    code=GEN_MODELS[identity];tail=2**-64 if code==1 else 0.;evaluation=2**-45 if code==1 else 0.
    expected={'arena_bytes':65536,'audio_inputs':2,'audio_outputs':2,'blocks':64,'cases':gen_cases(),
        'comparison_tolerance':{'maximum_absolute_error':0.,'maximum_pcm_lsb_error':0,'relative_rms_level_difference':0.},
        'id':identity,'patch':identity+'.rnbopat','pcm_gain':.25,'role':'fx','family':'gen-history','seed':305419896,
        'semantic':{'initial_epoch':-1024,'kind':GEN_KIND,'maximum_absolute_error':2e-6,
            'model_evaluation_bound':evaluation,'model_id':code,'model_tail_bound':tail,
            'rounding':'once-float32','witness_minimum_separation':8e-6},
        'stimulus':{'kind':GEN_INPUT},'verification':{'kind':GEN_KIND,'maximum_absolute_error':2e-6,'model_code':code},
        'warmup_blocks':4}
    if comparison:
        expected['qualification_mode']=GEN_FEEDBACK_MODE
        expected['comparison_tolerance']={'maximum_absolute_error':2e-6,'maximum_pcm_lsb_error':1,'relative_rms_level_difference':1e-4}
    require(same_declaration(fixture,expected),'Gen requires the exact authored source/model/reset program contract')
    require(any(same_declaration(case,c)for c in gen_cases()),'Unknown Gen reset case')
    events=gen_events(case);_,mask,_=gen_cache_data(code,case['id'])
    return {**expected['verification'],'model':'fresh-float64-input-convolution-or-integer-cycle',
        'rounding':'once-float32','gate':'cache-error-plus-maximum-cache-rounding-error-plus-model-bounds',
        'initial_epoch_frames':-1024,'event_schedule':events,'event_schedule_sha256':gen_schedule_sha(events),
        'reset_witness_sha256':hashlib.sha256(mask).hexdigest(),'witness_minimum_separation':8e-6,
        'model_tail_bound':tail,'model_evaluation_bound':evaluation}


def gen_identity(build,fixture,plan):
    gen_verification(fixture,fixture['cases'][0]);pin=GEN_IDENTITIES.get(fixture['id'])
    require(pin is not None,'Gen generated source identity is not frozen')
    comparison=fixture.get('qualification_mode')==GEN_FEEDBACK_MODE
    if comparison:
        require(plan.get('catalog_sha256')==GEN_FEEDBACK_CATALOG_SHA,'Gen feedback comparison catalog differs')
    require(same_declaration(plan.get('parameter_schema'),GEN_SCHEMA),'Gen reset parameter schema differs')
    require(same_declaration(plan.get('events'),[e for c in gen_cases()for e in gen_events(c)]),'Gen actual reset event table differs')
    require(type(plan.get('blocks'))is int and plan['blocks']==64 and type(plan.get('rounds'))is int and plan['rounds']==3 and
            type(plan.get('timing_exclude_blocks'))is int and plan['timing_exclude_blocks']==32 and
            type(plan.get('arena_bytes'))is int and plan['arena_bytes']==65536 and
            plan.get('comparison_policy',{}).get('pcm_gain')==.25 and plan.get('event_order')=='stable-block-source-order-v1',
            'Gen block/round/arena/timing/PCM gain differs')
    require(plan.get('patch_sha256')==pin['patch'] and plan.get('description_sha256')==pin['description'],'Gen patch/description differs')
    equal=build['modules']['strict']['artifact_sha256']==build['modules']['optimized']['artifact_sha256']
    require(not equal if comparison else equal,'Gen comparison/control image identity differs')
    for profile,module in build['modules'].items():
        require(profile in ('strict','optimized'),'Unknown Gen module slot')
        candidate=comparison and profile=='optimized'
        report=module['report'];export=report['prepared_export'];manifest=export['manifest'];provenance=export.get('provenance',{})
        require(manifest.get('editable_source_sha256')==pin['patch'] and manifest.get('parameter_schema_sha256')==pin['schema'] and
                manifest.get('source_tree_sha256')==pin['source_tree'],'Gen exact graph/schema differs')
        require(same_declaration({k:manifest.get(k)for k in ('parameter_count','role','audio_inputs','audio_outputs','sample_rate','block_frames',
                'numerical_profile','scheduler_time','rnbo_version','class_name','voices','voice_topology','required_host_services','midi_output_ports','adaptations')},
                {'parameter_count':1,'role':'fx','audio_inputs':2,'audio_outputs':2,'sample_rate':44100,'block_frames':256,
                 'numerical_profile':GEN_FEEDBACK_PROFILE if candidate else 'float32-strict','scheduler_time':'float64','rnbo_version':'1.4.4','class_name':'rnbos3patch',
                 'voices':1,'voice_topology':'single-export','required_host_services':[],'midi_output_ports':0,
                 'adaptations':WAVE4_ADAPTATIONS+(['rnbo-1.4.4-float32-gen-feedback-v1']if candidate else [])}),
                'Gen strict generated module/ABI profile differs')
        require(provenance.get('raw_files_sha256',{}).get('rnbo_source.h')==pin['source'],'Gen raw generated source differs')
        snapshot=report.get('prepared_snapshot',{}).get('prepared_files_sha256',{})
        require(snapshot.get('rnbo_source.h')==(GEN_FEEDBACK_PIN['source']if candidate else pin['source']),'Gen prepared source differs')
        runtime={k:v for k,v in snapshot.items()if k.startswith('common/')}
        require(len(runtime)==36 and hashlib.sha256((json.dumps(runtime,sort_keys=True,indent=2)+'\n').encode()).hexdigest()==WAVE4_RUNTIME,
                'Gen normal fixed runtime differs')
        if comparison:
            require(report.get('imports')==[],'Gen comparison requires zero-import modules')
            require(snapshot==provenance.get('prepared_files_sha256'),'Gen comparison prepared snapshot/provenance differs')
            require(snapshot.get('patch_config.h')==GEN_FEEDBACK_PIN['config'if candidate else'reference_config'],'Gen comparison compile config differs')
            name='rnbo-1.4.4-float32-gen-feedback-v1'
            records=[a for a in provenance.get('adaptations',[])if a.get('name')==name]
            if candidate:
                require(manifest.get('base_numerical_profile')=='float32-strict'and
                        manifest.get('numerical_identity')=='changed-rounding-float32-gen-feedback-v1'and
                        same_declaration(manifest.get('gen_feedback_contract'),GEN_FEEDBACK_CONTRACT),'Gen feedback numerical profile contract differs')
                require(snapshot.get('rnbo_s3_gen_feedback_source.h')==GEN_FEEDBACK_PIN['compile_contract']and len(records)==1,'Gen feedback type contract/adaptation missing')
                adaptation=records[0]
                expected={'name':name,'file':'rnbo_source.h','method':'gen_01_perform','input_sha256':pin['source'],
                    'prepared_sha256':GEN_FEEDBACK_PIN['source'],'input_method_sha256':GEN_FEEDBACK_PIN['input_method'],
                    'prepared_method_sha256':GEN_FEEDBACK_PIN['prepared_method'],'inserted_bytes':1,'inverse_byte_identity':True,
                    'runtime_tree_sha256':WAVE4_RUNTIME,'editable_source_sha256':pin['patch'],'description_file_sha256':pin['description'],
                    'compile_contract_file':'rnbo_s3_gen_feedback_source.h','compile_contract_sha256':GEN_FEEDBACK_PIN['compile_contract'],
                    'changed_rounding':True,'bit_identity_claimed':False,'scheduler_time_unchanged':True,'transformer_sha256':GEN_FEEDBACK_PIN['transformer']}
                expected['input_map_sha256']=GEN_FEEDBACK_PIN['input_map']
                require(all(same_declaration(adaptation.get(k),v)for k,v in expected.items()),'Gen feedback exact one-literal/inverse proof differs')
            else:
                require(not records and not any(k in manifest for k in ('gen_feedback_contract','base_numerical_profile','numerical_identity'))and
                        'rnbo_s3_gen_feedback_source.h'not in snapshot,'Gen reference must remain original strict source')
    if comparison:
        left,right=(build['modules'][p]['report']for p in ('strict','optimized'))
        for field in ('compiler','dependencies','private_support_archives','dynamic_abi','state_policy','allocation_accounting'):
            require(isinstance(left.get(field),dict)and left[field]and left[field]==right.get(field),'Gen pair compiler/SDK/archive/state contract differs')
        sdk=lambda r:{k:v for k,v in r.get('source_files_sha256',{}).items()if k.startswith('module-sdk/')}
        require('module-sdk/dynamic/rnbo_s3_dynamic.cpp'in sdk(left)and sdk(left)==sdk(right),'Gen pair SDK sources differ')
        files=lambda r:r['prepared_snapshot']['prepared_files_sha256']
        lhs,rhs=files(left),files(right);extra='rnbo_s3_gen_feedback_source.h'
        require(set(rhs)==set(lhs)|{extra}and all(rhs[k]==v for k,v in lhs.items()if k not in ('rnbo_source.h','patch_config.h')),
                'Gen feedback changes unreviewed prepared files')


GEN_ARITH_KIND='gen-arithmetic-v1'
GEN_ABS_MODE='gen-abs-intrinsic-comparison-v1'
GEN_ABS_BOUNDARIES='finite-magnitude-boundaries-v1'
GEN_ABS_PIN={
    'catalog':'a7481d471f65f6203150e41b3870065df8e12fbb2d0fb9256a226c92791d83d5',
    'source':'3df5fb401c1d1e04470e318f3aa1f4704ff38d17845ece0f7dacf74defa93943',
    'contract_file':'rnbo_s3_gen_abs_source.h',
    'compile_contract':'9d7729ee5494685f5af4d94a6cd776bf630b933ed2069a1fc62afb74475d044b',
    'config':'f6ac5f77e0492f986a983c1ee31e1dafe9899b0aceabe2ef591fbfa43c40cdcf',
    'reference_config':'a0d544c36042ca826ec6cd9deb332b80b68346e0986d49af73b16f7fc5486d5b',
    'input_map':'ccccfd54d10f46b83705c7b315e27fd4e83b5ae3dccb525f1a65ceb863c2d8f4',
    'input_method':'2177cbb70c6451d2e2367c48bc1d7c63c9b3569a2459286873b9739c7c9aee4a',
    'prepared_method':'78cfc29273918e63b0490c42b59272ae0f44be267fcdb8b7179cd02400ae3176',
    'transformer':'c013826b069504ce222ac340d1e52b36a02d25fe5c331f05011c877554921871'}
GEN_ABS_CONTRACT={'version':1,'context':'abs-call','operation':'explicit-binary32-absolute-builtin',
    'input_domain':'finite-binary32','finite_bit_identity_claimed':True,'zero_sign':'negative-zero-maps-to-positive-zero',
    'state_and_layout':'unchanged','scheduler_time':'unchanged-binary64','math_runtime':'unchanged',
    'nonfinite_qualified':False,'floating_environment_equivalence_claimed':False,
    'errno_identity_claimed':False,'floating_trap_identity_claimed':False}
GEN_ARITH_MODELS={'abs-call':1,'min-call':2,'minimum-call':2,'max-call':3,'maximum-call':3,
    'sub-call':4,'subtract-infix':4,'eq-call':5,'equal-infix':5,'lt-call':6,'less-infix':6,
    'add-call':9,'add-infix':9,'mul-call':10,'mul-infix':10}
GEN_ARITH_IDENTITIES={
  "abs-call": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "71e3fcc0535c5808b8cb1ff7543e02b2116562f928b0e90f86f90d137f21646e",
    "patch": "c2878ab82152020b8a26f006c96e22b7a4837ecfe9005ca9768bcaf9bbba39c6",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "86cb0539073bef4bccb2352681eac0c051c0890731e42d3744beeec71397220d",
    "source_tree": "0d24c3f6067cd25889e322e2194a263392936c6c6d972dabdff34b26f6ae122b"
  },
  "add-call": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "2e03829df2aca4f7504139d95b90306e1fbfe1a2477c418335fc16c86553d89f",
    "patch": "20da67e975649c83bdb209f90e7547078184cdbf16e0ea5e5c561a80d1c486ca",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "fe18b78ecd90f1b6b27020773a4f5c39d8caa74914b76e8298501b175a2abda6",
    "source_tree": "a206515db9c3d36afd67125790b0502e4d6df0fa9158dffb56a0afbc6661ce2b"
  },
  "add-infix": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "628a310d600c263c14cfee13b80eb5449df505c00802ec98123aa356bf3dc173",
    "patch": "6aa63780a1cbf56831b5132c32c9056c0aae9cc871d8986d643ac13370407dca",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "fe18b78ecd90f1b6b27020773a4f5c39d8caa74914b76e8298501b175a2abda6",
    "source_tree": "77aaaa750154fe1d17deb23c3ebb1647cd821716365c359448beef54a287b409"
  },
  "eq-call": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "3983df5571c87a98546c944de42fee3a4d65c128284322c9bf7a2eebd01cff85",
    "patch": "dbbbb2036fcaf8e2964bf657eeee01a9adc3a259b3a6d6b5e1f1f1af0d526115",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "c118d1806ce20e5d5cc2c5154f910a8f44a5f976d070d7ff044dd03750ccf014",
    "source_tree": "0a9c0e183a25a3a18280edd1a87a709e303626ece9064d905ec7dcff4b0857a3"
  },
  "equal-infix": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "4eeae0cc7851e43a90c49c4fc973a99538c4520ddbbee49bbf14376bedcd98e3",
    "patch": "c888c4b7b3024f72e1460e243812028c74654fc43fee209e05b36b2be9567c3a",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "c118d1806ce20e5d5cc2c5154f910a8f44a5f976d070d7ff044dd03750ccf014",
    "source_tree": "43b8e5fe6d5864ccafd7f0a2aec3f8876e2aa18ffd822f91a799eef4e2d9828b"
  },
  "less-infix": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "de195d2b73978fef32ccbe9a38a1fc95f85e2f00a4499f57b06089cba0ecd15d",
    "patch": "effbdcfd741225b48519ee2b4947b7a669376a8b920ab75391cd3245ee35f2cb",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "2b0fd61747c1529d5255808419e59676f012b66853ba13f8ac8ec600277e5f6f",
    "source_tree": "5fdef3e3bd1b864ec53cc09583445f86405b2a8f5cda9e0d6ad683ed83c741c8"
  },
  "lt-call": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "a2300c304105f5f90bdadd4597b40ad7d841080e3395e25ebb7234cfca463449",
    "patch": "ea93cf36febdf6927af6400d1680d8acfdcefdc8f80714c2f293109ab084e56b",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "2b0fd61747c1529d5255808419e59676f012b66853ba13f8ac8ec600277e5f6f",
    "source_tree": "c0f90c3340fc0362de71a3b64f110084515ce6a6fe91f91d83218570cacd5424"
  },
  "max-call": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "babb19ecf92dd68bf081ec87f9765bd5c786c2ff7a2e0402fe937575cf1bda6d",
    "patch": "f331c0d547491254bb3f39921194943db205225192ca51ffe3e912ac0a721f57",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "ab4a9b12770267d8a4b69cbaec660bfc167088880a53c93194b59ffaac663f9b",
    "source_tree": "b3994ef8578969684466ce1062b6beda7b81e3770d30f0af06d9213dee405969"
  },
  "maximum-call": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "f36d02f1f61fe40afb6b9e73b796252bc2e2146dc985a4ce50651179c5fb24df",
    "patch": "d8eb69ee640e9e13b48d85a24845895f922af0979fa3a0352952d0fd94b8611c",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "ab4a9b12770267d8a4b69cbaec660bfc167088880a53c93194b59ffaac663f9b",
    "source_tree": "aa36141f268b72c348cd22378fd482a13144a508fef770f5ef1b4770d2ad4550"
  },
  "min-call": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "dd30dd2760276d302c5f9394ece17c81f5d89c391ebcd953d5faee0ce6bbb589",
    "patch": "ae15329737cdb0cc73fc680952427a8ca2c223039b6e60e59a9fa155e993bfb0",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "1d843100b53839881b4072bd9d8d58a8de254562ae1d18dcef717bdadf76c7d7",
    "source_tree": "629dfe6182a9d5b25b196811b02d3ca3522120600f7162fd35c0e37afff11fed"
  },
  "minimum-call": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "5c5ba2f06ff0635370592ca9ae32007842f0461378277374fb7ab55550f69189",
    "patch": "034f7ad3090217e5193313dc8a9d52e8440ad43fdbaa2babffa239285f758084",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "1d843100b53839881b4072bd9d8d58a8de254562ae1d18dcef717bdadf76c7d7",
    "source_tree": "6025d37d7b87c3e0f818853f5c9a166a73cb88ad69453e15edb8fbef08353845"
  },
  "mul-call": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "b2ad47540e08411e539df5772396eb913cfe7c27958f05057245336d2e09a535",
    "patch": "17204c076425bfa2e9382195b2b8803e35e6b02ce2a45ffb0f683c42f6cfa2f2",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "316ace992e3b52aa0f5ce31cf124f273ff8aabd1da8215772bd8c072418c8bc6",
    "source_tree": "65d1c391c0182ca49d05f81f055f83d8c89a916000ccf6363df03b81f3975bca"
  },
  "mul-infix": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "0b4f1a0fa4ce7dfe83c3ef43b4d15d2a32c4052acb4c315ce53ba73fe1ee151d",
    "patch": "5e9a5931929537b1c8c84508d90517e1af808bc5c6bbb52e3655704d5916fc98",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "316ace992e3b52aa0f5ce31cf124f273ff8aabd1da8215772bd8c072418c8bc6",
    "source_tree": "98a7eacc787353066efd9055f74c6c850db2d19269c4ca57401bc7340bdea903"
  },
  "sub-call": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "6e63f326258526c6cf227105477f667a6e0bb0c6bc5eb71d1c6d5868dffa70a1",
    "patch": "a8335ab43dc772c370b70ab968eee7fbc3bfebd455c685ef4b985290fe3a8fb1",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "53a2edab494f0d57e898fdbef6f4d42d3736650f57e40c12c1e04acfdfb40bc8",
    "source_tree": "8a4ac9da57ca0ebeaef73f481388de8317b930f8f2d0110a3e6dd6d98f1d75e2"
  },
  "subtract-infix": {
    "description": "85f7eb91241d01e0d3fd4711a2811b586021e92c8a0c3980389cb7c4b73e0314",
    "fixture": "288ee313daf5ac77d9fce7a08d36b44f7e212d035b68b16d4f67ea3d1c8b6a42",
    "patch": "7e3ccc0b037f3140ca19bfb7ac49e22f66d116e247142f23b9c76f1a2f1bc852",
    "schema": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "source": "53a2edab494f0d57e898fdbef6f4d42d3736650f57e40c12c1e04acfdfb40bc8",
    "source_tree": "e574eb24a5134beb377c95cc169ada0ccaeef307ba2735cc8dda08d941dcb7a5"
  }
}


def gen_arith_verification(fixture,case):
    identity=fixture.get('id');require(identity in GEN_ARITH_MODELS,'Unknown exact Gen arithmetic fixture')
    pin=GEN_ARITH_IDENTITIES.get(identity);require(pin is not None,'Gen arithmetic source identity is not frozen')
    comparison=fixture.get('qualification_mode')==GEN_ABS_MODE
    require('qualification_mode'not in fixture or comparison and identity=='abs-call','Unknown Gen arithmetic comparison mode/context')
    original={k:v for k,v in fixture.items()if k not in ('family','qualification_mode')}
    if comparison:
        boundary={'id':GEN_ABS_BOUNDARIES,'parameters':{},'events':[],'stimulus':{'kind':GEN_ABS_BOUNDARIES}}
        require(isinstance(original.get('cases'),list)and len(original['cases'])==4 and
                same_declaration(original['cases'][-1],boundary),'Gen abs comparison requires the exact fourth finite boundary case')
        original['cases']=original['cases'][:3]
    try:original_sha=hashlib.sha256((json.dumps(original,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()).hexdigest()
    except (TypeError,ValueError):original_sha=None
    require(original_sha==pin['fixture'],'Gen arithmetic original source/surface/domain/cases differ')
    require(fixture.get('family')=='gen-arithmetic'and fixture.get('role')=='fx','Gen arithmetic family/role differs')
    expected={'kind':GEN_ARITH_KIND,'model_code':GEN_ARITH_MODELS[identity],'maximum_absolute_error':0.}
    require(same_declaration(fixture.get('semantic'),expected)and same_declaration(fixture.get('verification'),expected),
            'Gen arithmetic model declaration differs')
    require(any(same_declaration(case,c)for c in fixture['cases']),'Unknown Gen arithmetic case')
    return {**expected,'observer_channel':2,'model':'independent-binary32-operations',
        'rounding':'once-binary32-per-output-operation',
        'gate':'raw-binary32-absolute-bits'if comparison else'numeric-exact-plus-signed-zero-only-operation-bits',
        'operation_zero_sign':'positive-zero-required'if comparison else'diagnostic-only'}


def gen_arith_identity(build,fixture,plan):
    gen_arith_verification(fixture,fixture['cases'][0]);pin=GEN_ARITH_IDENTITIES[fixture['id']]
    comparison=fixture.get('qualification_mode')==GEN_ABS_MODE
    if comparison:
        require(GEN_ABS_PIN['transformer']is not None,'Gen abs intrinsic identity is not frozen')
        require(plan.get('catalog_sha256')==GEN_ABS_PIN['catalog'],'Gen abs intrinsic catalog differs')
    require(same_declaration(plan.get('parameter_schema'),[])and same_declaration(plan.get('events'),[]),'Gen arithmetic parameters/events are unqualified')
    require(type(plan.get('blocks'))is int and plan['blocks']==64 and type(plan.get('rounds'))is int and plan['rounds']==3 and
            type(plan.get('timing_exclude_blocks'))is int and plan['timing_exclude_blocks']==32 and
            type(plan.get('arena_bytes'))is int and plan['arena_bytes']==4096 and plan.get('comparison_policy',{}).get('pcm_gain')==.5,
            'Gen arithmetic blocks/rounds/timing/arena/gain differ')
    require(plan.get('patch_sha256')==pin['patch']and plan.get('description_sha256')==pin['description'],'Gen arithmetic patch/description differs')
    same_image=build['modules']['strict']['artifact_sha256']==build['modules']['optimized']['artifact_sha256']
    require(not same_image if comparison else same_image,'Gen arithmetic comparison/control image identity differs')
    for profile,module in build['modules'].items():
        require(profile in ('strict','optimized'),'Unknown Gen arithmetic module slot')
        candidate=comparison and profile=='optimized'
        report=module['report'];manifest=report['prepared_export']['manifest'];provenance=report['prepared_export'].get('provenance',{})
        require(manifest.get('editable_source_sha256')==pin['patch']and manifest.get('parameter_schema_sha256')==pin['schema']and
                manifest.get('source_tree_sha256')==pin['source_tree'],'Gen arithmetic exact graph/schema/source differs')
        require(same_declaration({k:manifest.get(k)for k in ('parameter_count','role','audio_inputs','audio_outputs','sample_rate','block_frames',
            'numerical_profile','scheduler_time','rnbo_version','class_name','voices','voice_topology','required_host_services','midi_output_ports','adaptations')},
            {'parameter_count':0,'role':'fx','audio_inputs':2,'audio_outputs':2,'sample_rate':44100,'block_frames':256,
             'numerical_profile':'float32-strict','scheduler_time':'float64','rnbo_version':'1.4.4','class_name':'rnbos3patch',
             'voices':1,'voice_topology':'single-export','required_host_services':[],'midi_output_ports':0,
             'adaptations':WAVE4_ADAPTATIONS+(['rnbo-1.4.4-gen-abs-intrinsic-v1']if candidate else [])}),
            'Gen arithmetic strict ABI/profile differs')
        require(report.get('imports')==[],'Gen arithmetic module has unapproved imports')
        require(provenance.get('raw_files_sha256',{}).get('rnbo_source.h')==pin['source'],'Gen arithmetic raw source differs')
        files=report.get('prepared_snapshot',{}).get('prepared_files_sha256',{})
        require(files.get('rnbo_source.h')==(GEN_ABS_PIN['source']if candidate else pin['source']),'Gen arithmetic prepared source differs')
        runtime={k:v for k,v in files.items()if k.startswith('common/')}
        require(len(runtime)==36 and hashlib.sha256((json.dumps(runtime,sort_keys=True,indent=2)+'\n').encode()).hexdigest()==WAVE4_RUNTIME,
                'Gen arithmetic fixed runtime differs')
        expected_files=set(runtime)|{'RNBO-runtime-LICENSE','description.json','generator.json','patch_config.h','rnbo_source.h','source.rnbopat'}
        if candidate:expected_files.add(GEN_ABS_PIN['contract_file'])
        require(set(files)==expected_files and
                files.get('description.json')==pin['description']and files.get('source.rnbopat')==pin['patch']and
                files.get('patch_config.h')==(GEN_ABS_PIN['config']if candidate else GEN_ABS_PIN['reference_config']),
                'Gen arithmetic normal strict file/config composition differs')
        if comparison:
            require(files==provenance.get('prepared_files_sha256'),'Gen abs snapshot/provenance differs')
            records=[a for a in provenance.get('adaptations',[])if a.get('name')=='rnbo-1.4.4-gen-abs-intrinsic-v1']
            if candidate:
                require(manifest.get('gen_abs_intrinsic')is True and same_declaration(manifest.get('gen_abs_intrinsic_contract'),GEN_ABS_CONTRACT),
                        'Gen abs finite-bit identity contract differs')
                require(not any(k in manifest for k in ('base_numerical_profile','numerical_identity')),
                        'Gen abs intrinsic must remain the strict finite-bit-identity option')
                require(files.get(GEN_ABS_PIN['contract_file'])==GEN_ABS_PIN['compile_contract']and len(records)==1,'Gen abs type contract/adaptation missing')
                expected={'name':'rnbo-1.4.4-gen-abs-intrinsic-v1','file':'rnbo_source.h','method':'gen_01_perform',
                    'input_sha256':pin['source'],'prepared_sha256':GEN_ABS_PIN['source'],'input_map_sha256':GEN_ABS_PIN['input_map'],
                    'input_method_sha256':GEN_ABS_PIN['input_method'],'prepared_method_sha256':GEN_ABS_PIN['prepared_method'],
                    'callee_replacements':2,'inverse_byte_identity':True,'finite_bit_identity_claimed':True,
                    'editable_source_sha256':pin['patch'],'description_file_sha256':pin['description'],'runtime_tree_sha256':WAVE4_RUNTIME,
                    'compile_contract_file':GEN_ABS_PIN['contract_file'],'compile_contract_sha256':GEN_ABS_PIN['compile_contract'],
                    'scheduler_time_unchanged':True,'transformer_sha256':GEN_ABS_PIN['transformer']}
                require(all(same_declaration(records[0].get(k),v)for k,v in expected.items()),'Gen abs exact two-callee/inverse proof differs')
            else:
                require(not records and not any(k in manifest for k in ('gen_abs_intrinsic','gen_abs_intrinsic_contract')),
                        'Gen abs reference must remain default strict')
    if comparison:
        left,right=(build['modules'][p]['report']for p in ('strict','optimized'))
        for field in ('compiler','dependencies','private_support_archives','dynamic_abi','state_policy','allocation_accounting'):
            require(isinstance(left.get(field),dict)and left[field]and left[field]==right.get(field),'Gen abs toolchain/ABI/archive/state contract differs')
        sdk=lambda r:{k:v for k,v in r.get('source_files_sha256',{}).items()if k.startswith('module-sdk/')}
        require('module-sdk/dynamic/rnbo_s3_dynamic.cpp'in sdk(left)and sdk(left)==sdk(right),'Gen abs module SDK sources differ')
        require(left.get('source_files_sha256')==right.get('source_files_sha256')and
                left['source_files_sha256'].get('host/compiler/gen_abs_intrinsic.py')==GEN_ABS_PIN['transformer'],
                'Gen abs current compiler/helper source epochs differ')
        lhs=left['prepared_snapshot']['prepared_files_sha256'];rhs=right['prepared_snapshot']['prepared_files_sha256']
        require(set(rhs)==set(lhs)|{GEN_ABS_PIN['contract_file']}and
                all(rhs[k]==v for k,v in lhs.items()if k not in ('rnbo_source.h','patch_config.h')),'Gen abs changed unreviewed prepared files')


@lru_cache(maxsize=4,typed=True)
def gen_arith_input_bytes(kind):
    require(type(kind)is int and kind in (12,13,14,16),'Unknown Gen arithmetic input family')
    if kind!=16:return wave4_input_bytes(kind,64)
    magnitudes=(0,1,2,0x3fffff,0x400000,0x7ffffe,0x7fffff,0x800000,0x800001,
                0xffffff,0x1000000,0x3e800000,0x3effffff,0x3f000000,0x3f000001,0x3f7ffffe,0x3f7fffff,0x3f800000)
    result=bytearray()
    for frame in range(16384):
        for lane in (frame,frame+17):result.extend(struct.pack('<I',magnitudes[(lane//2)%18]|((lane&1)<<31)))
    return bytes(result)


@lru_cache(maxsize=25,typed=True)
def gen_arith_oracle_bytes(model,kind):
    """Independent binary64 arithmetic over exact binary32 operands, once rounded.

    A product has at most48 significant bits and remains normal in binary64
    even for two binary32 subnormals. No generated Gen/RNBO kernel is imported.
    """
    require(type(model)is int and model in (1,2,3,4,5,6,9,10),'Unknown Gen arithmetic operation')
    data=gen_arith_input_bytes(kind);result=bytearray()
    for x,y in struct.iter_unpack('<ff',data):
        if model==1:a,b=abs(x),abs(y)
        elif model==2:a,b=(x if x<=y else y),(y if y<=x else x)
        elif model==3:a,b=(x if x>=y else y),(y if y>=x else x)
        elif model==4:a,b=x-y,y-x
        elif model==5:a=b=float(x==y)
        elif model==6:a,b=float(x<y),float(y<x)
        elif model==9:a,b=x+y,y+x
        else:a,b=x*y,y*x
        result.extend(struct.pack('<ff',a,b))
    return bytes(result)


def declared_stimulus(fixture,case):
    wave2={'impulse-step-v1':4,'mixed-tone-v1':5,'nonlinear-grid-v1':6,POWER_DENSE:11,GEN_INPUT:15,GEN_ABS_BOUNDARIES:16,**WRAP_STIMULI,**WAVE4_INPUTS}
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
        require(kind not in ('impulse-step-v1','mixed-tone-v1','nonlinear-grid-v1',POWER_DENSE,GEN_INPUT,GEN_ABS_BOUNDARIES,*WRAP_STIMULI,*WAVE4_INPUTS),'Missing explicit verification contract')
        return None
    if isinstance(declaration,dict) and declaration.get('kind')==GEN_KIND:
        return gen_verification(fixture,case)
    if isinstance(declaration,dict) and declaration.get('kind')==GEN_ARITH_KIND:
        return gen_arith_verification(fixture,case)
    if isinstance(declaration,dict) and declaration.get('kind')==WAVE4_KIND:
        return wave4_verification(fixture,case)
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
    expected_count=5 if kind=='biquad-response-v1' else 0 if kind in ('wrap-finite-v1',WAVE4_KIND,GEN_ARITH_KIND) else 1
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
    wave4=fixture.get('verification',{}).get('kind')==WAVE4_KIND
    gen=fixture.get('verification',{}).get('kind')==GEN_KIND
    gen_arith=fixture.get('verification',{}).get('kind')==GEN_ARITH_KIND
    if new_model:wave2_identity(build,fixture,plan)
    if exact_wrap:wrap_identity(build,fixture,plan)
    if powers:power_identity(build,fixture,plan)
    if wave4:wave4_identity(build,fixture,plan)
    if gen:gen_identity(build,fixture,plan)
    if gen_arith:gen_arith_identity(build,fixture,plan)
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
        if exact_wrap or powers or wave4 or gen or gen_arith:
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
        if wave4:
            expected_input,expected_oracle=wave4_cache_hashes(verification['model_code'],expected['kind'],plan['blocks'])
            require(record['input_sha256']==expected_input,'Wave4 deterministic input SHA differs')
        if gen:
            expected_input=hashlib.sha256(gen_input_bytes()).hexdigest()
            cache,mask,cache_rounding=gen_cache_data(verification['model_code'],case['id'])
            expected_oracle=hashlib.sha256(cache).hexdigest()
            require(record['input_sha256']==expected_input,'Gen deterministic input SHA differs')
        if gen_arith:
            expected_input=hashlib.sha256(gen_arith_input_bytes(expected['kind'])).hexdigest()
            expected_oracle=hashlib.sha256(gen_arith_oracle_bytes(verification['model_code'],expected['kind'])).hexdigest()
            require(record['input_sha256']==expected_input,'Gen arithmetic deterministic input SHA differs')
        evidence[case['id']]={**record,'declared_settings':expected['settings']}
        if exact_wrap:evidence[case['id']]['distinct_input_coverage']=wrap_input_coverage(expected['kind'],plan['blocks'])
        if powers:evidence[case['id']]['distinct_input_coverage']=coverage
        if verification:
            candidates=[r for r in oracle_records if r.get('fixture')==name and r.get('case')==case['id']]
            require(len(candidates)==1,'Missing or duplicate ORACLE case');oracle=candidates[0]
            if verification['kind'] in WAVE2_ORACLES or exact_wrap or powers or wave4 or gen or gen_arith:
                keys={'fixture','case','oracle_sha256','oracle_bytes','layout','oracle_kind','max_abs_tolerance','max_cache_rounding_error','model','rounding'}
                if gen:keys.update(('model_code','initial_epoch_frames','event_schedule_sha256','reset_witness_sha256',
                                   'witness_minimum_separation','model_tail_bound','model_evaluation_bound'))
                elif wave4 or gen_arith:keys.update(('model_code','observer_channel'))
                elif powers:keys.update(('initial_exponent','event_schedule_sha256'))
                elif not exact_wrap:keys.update(verification['coefficients'] if verification['kind']=='biquad-response-v1' else ('exponent',))
                require(set(oracle)==keys,'Unknown or missing oracle metadata')
            digest(oracle.get('oracle_sha256'),'Malformed oracle SHA256')
            require(type(oracle.get('oracle_bytes')) is int and oracle['oracle_bytes']==plan['blocks']*256*2*4,'Oracle byte coverage differs')
            require(oracle.get('layout')=='float32_stereo_interleaved_le' and oracle.get('oracle_kind')==verification['kind'],'Oracle layout/model kind differs')
            if verification['kind']=='average-window-v1':
                require(oracle.get('window')==verification['window'] and oracle.get('initial_available')==verification['initial_available'],'Oracle history/window differs')
            elif exact_wrap:
                require(oracle['oracle_sha256']==expected_oracle,'Finite wrap independent oracle SHA differs')
            elif wave4:
                require(oracle['oracle_sha256']==expected_oracle,'Wave4 independent oracle SHA differs')
                require(same_declaration(oracle.get('model_code'),verification['model_code']) and
                        same_declaration(oracle.get('observer_channel'),verification['observer_channel']),
                        'Wave4 oracle operation/observer differs')
            elif gen:
                require(oracle['oracle_sha256']==expected_oracle,'Gen independent oracle SHA differs')
                for key in ('model_code','initial_epoch_frames','event_schedule_sha256','reset_witness_sha256',
                            'witness_minimum_separation','model_tail_bound','model_evaluation_bound'):
                    require(same_declaration(oracle.get(key),verification[key]),'Gen oracle reset/model metadata differs: '+key)
            elif gen_arith:
                require(oracle['oracle_sha256']==expected_oracle,'Gen arithmetic independent oracle SHA differs')
                require(same_declaration(oracle.get('model_code'),verification['model_code'])and
                        same_declaration(oracle.get('observer_channel'),2),'Gen arithmetic operation/no-observer contract differs')
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
            if exact_wrap or wave4 or gen_arith:require(error==0,'Exact oracle must have zero cache rounding error')
            if gen:require(same_declaration(error,cache_rounding),'Gen oracle cache rounding differs from independently regenerated truth')
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
        stem='gen_arithmetic_oracle'if gen_arith else 'gen_history_oracle' if gen else 'wave4_oracle' if wave4 else 'wave2_oracle' if new_model or exact_wrap or powers else 'average_oracle'
        provenance['oracle_source_sha256']={key:digest(sources.get(key),'Missing oracle source identity') for key in (f'object-benchmark/main/{stem}.c',f'object-benchmark/main/{stem}.h')}
        provenance['verification_contract']=fixture['verification'];provenance['psram_budget']=oracle_memory_budget(build,plan)
        if gen_arith:
            provenance['generation']='Three deterministic integer/binary32 input families; complete INPUT SHA independently regenerated on host.'
            provenance['oracle']='Independent binary64 arithmetic/comparisons over binary32 operands, rounded once per output operation. Product has at most48 significant bits, including binary32 underflow inputs. Complete canonical ORACLE SHA independently regenerated; min/max choose the first operand on ties.'
            provenance['semantic_gate']='Numerical output/model error and cache-rounding error must be zero. Operation raw-bit differences may only change zero sign; identical-image pair raw bits must match.'
            provenance['limit']='Only these exact authored GenExpr call/infix contexts, finite binary32 inputs in[-1,1],64 fixed256-frame vectors, four warmups and three rounds. No RNBO, alias/canonical, visual Gen, other overload/resource/event, nonfinite or fenv transfer.'
            provenance['pilot']='No direct observer; both output channels are the declared arithmetic operations.'
            provenance['parameter_schema']=plan['parameter_schema'];provenance['events']=plan['events'];provenance['pcm_gain']=.5
            provenance['surface_identity']={key:fixture[key]for key in ('source','exact_entries','aliases_inherit_qualification')}
            if fixture.get('qualification_mode')==GEN_ABS_MODE:
                provenance['qualification_mode']=GEN_ABS_MODE
                provenance['generation']='Four fixed input families, including36 signed finite boundary words repeated with an independent17-frame right-lane offset; full INPUT SHA independently regenerated.'
                provenance['semantic_gate']='Every output binary32 word must equal the independent canonical absolute-value cache, including positive zero. Numeric/cache-rounding error and all operation/pair bit differences must be zero.'
                provenance['limit']='Only the exact abs-call GenExpr source and reviewed two-callee intrinsic substitution,64 fixed256-frame vectors/four zero warmups/three rounds. Finite-bit identity only; no errno, trapping/fenv, nonfinite, other abs types or Gen-family transfer.'
        elif gen:
            provenance['generation']='Seven exact dyadic binary32 input values with independently shifted right plane; complete INPUT SHA regenerated on host.'
            provenance['oracle']='Fresh independent fsum of at most64 weighted source inputs, or integer two/three-state phase; no generated recurrence. Both cached channel hashes independently regenerated.'
            provenance['semantic_gate']='Output/cache error plus once-binary32 cache rounding plus independently declared tail and model-evaluation bounds must stay within2e-6.'
            provenance['limit']='Three exact authored GenExpr History programs;64 fixed256-frame vectors, four zero warmups and three rounds. Fixed module ABI only; no visual Gen, arbitrary history/operator, fenv or family transfer.'
            provenance['pilot']='No passthrough observer. Reset witness checks compare first output pair only at independently observable reset boundaries; period2 swap has no observable block-edge reset witness.'
            provenance['parameter_schema']=plan['parameter_schema'];provenance['events']=plan['events'];provenance['pcm_gain']=.25
            if fixture.get('qualification_mode')==GEN_FEEDBACK_MODE:
                provenance['qualification_mode']=GEN_FEEDBACK_MODE
                provenance['limit']='Only the exact authored feedback GenExpr graph and reviewed Float32-literal profile;64 fixed256-frame vectors, four zero warmups and three rounds. No visual Gen, arbitrary operators, resources, nonfinite or fenv transfer.'
                provenance['rounding_scope']='Reference retains original mixed arithmetic; candidate uses the reviewed Float32 feedback literal. Pair bits and signed-zero differences are diagnostics, with unchanged2e-6/PCM1/RMS1e-4 numerical gates; no universal bit identity.'
        elif wave4:
            provenance['generation']='Deterministic integer/binary32 programs; complete INPUT SHA independently regenerated on host.'
            provenance['oracle']='Independent host binary64 mathematical operations rounded once to binary32, min/max first-operand ties and explicit zero-initialized previous-input delta state. Complete oracle bytes independently hashed; no generated kernel imported.'
            provenance['semantic_gate']='Numerical output/model error and cache-rounding error must both be zero. Operation bit differences may only change zero sign; the delta right-plane observer must preserve every input bit.'
            provenance['limit']='Thirteen exact authored source contexts, finite binary32 inputs in[-1,1],64 blocks/four warmups/three rounds only. No alias, arbitrary-domain, nonfinite, fenv, explicit-reset or family-wide transfer.'
            provenance['pilot']='Delta right-plane observer checked raw-bit exactly; other channels use the independent mathematical model.'
            provenance['parameter_schema']=plan['parameter_schema'];provenance['events']=plan['events']
            provenance['surface_identity']={key:fixture[key]for key in ('surface','source','exact_entries','aliases_inherit_qualification')}
        elif exact_wrap:
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
    wave4_mode=fixture.get('verification',{}).get('kind')==WAVE4_KIND
    gen_mode=fixture.get('verification',{}).get('kind')==GEN_KIND
    gen_arith_mode=fixture.get('verification',{}).get('kind')==GEN_ARITH_KIND
    require(len(rounding_records)==(len(fixture['cases']) if power_mode or wave4_mode or gen_mode or gen_arith_mode else 0),
            'Incomplete or unexpected pair rounding diagnostics')
    gen_arith_prefix='RNBO_OBJECT_BENCHMARK CASE_GEN_ARITH_BITS '
    gen_arith_records=[fields(line.strip(),gen_arith_prefix)for line in lines if line.strip().startswith(gen_arith_prefix)]
    require(len(gen_arith_records)==(2*len(fixture['cases'])if gen_arith_mode else 0),'Incomplete or unexpected Gen arithmetic bit measurements')
    gen_arith_fields={'gen_arith_bit_sample_checks','gen_arith_bit_differences','gen_arith_zero_sign_differences'}
    gen_arith_present=gen_arith_fields&passed.keys()
    require(len(gen_arith_present)==3 if gen_arith_mode else len(gen_arith_present)in (0,3),'Missing or partial Gen arithmetic PASS counters')
    gen_arith_totals=dict.fromkeys(gen_arith_fields,0)
    for key in gen_arith_fields:
        value=passed.get(key,0);require(type(value)is int and value>=0,'Invalid Gen arithmetic PASS counter')
        if not gen_arith_mode:require(value==0,'Other fixtures cannot claim Gen arithmetic counters')
    if gen_arith_mode:
        require(passed['gen_arith_bit_sample_checks']==expected_samples*len(fixture['cases'])*2,'Gen arithmetic PASS sample coverage differs')
    gen_prefix='RNBO_OBJECT_BENCHMARK CASE_GEN_RESET '
    gen_records=[fields(line.strip(),gen_prefix)for line in lines if line.strip().startswith(gen_prefix)]
    require(len(gen_records)==(2*len(fixture['cases'])if gen_mode else 0),'Incomplete or unexpected Gen reset witnesses')
    gen_fields={'gen_reset_events','gen_reset_witness_events','gen_reset_witness_sample_checks','gen_reset_witness_differences'}
    require((gen_fields|{'pcm_gain'})<=passed.keys() if gen_mode else not (gen_fields|{'pcm_gain'})&passed.keys(),
            'Missing or unexpected Gen PASS reset/gain metadata')
    gen_totals=dict.fromkeys(gen_fields,0)
    if gen_mode:
        require(all(type(passed[k])is int and passed[k]>=0 for k in gen_fields),'Invalid Gen PASS reset count type')
        require(type(passed['pcm_gain'])in (int,float) and passed['pcm_gain']==.25,'Gen PCM gain differs')
    wave4_prefix='RNBO_OBJECT_BENCHMARK CASE_WAVE4_BITS '
    wave4_records=[fields(line.strip(),wave4_prefix)for line in lines if line.strip().startswith(wave4_prefix)]
    require(len(wave4_records)==(2*len(fixture['cases'])if wave4_mode else 0),'Incomplete or unexpected wave4 bit measurements')
    wave4_fields={'wave4_bit_sample_checks','wave4_bit_differences','wave4_zero_sign_differences',
                 'observer_bit_sample_checks','observer_bit_differences'}
    present=wave4_fields&passed.keys()
    require(len(present)==5 if wave4_mode else len(present)in (0,5),'Missing or incomplete PASS wave4 counter schema')
    wave4_totals=dict.fromkeys(wave4_fields,0)
    for key in wave4_fields:
        value=passed.get(key,0);require(type(value)is int and value>=0,'Invalid PASS wave4 counter')
        if not wave4_mode:require(value==0,'Legacy fixture cannot claim wave4 counters')
    if wave4_mode:
        expected_observer=expected_samples*len(fixture['cases']) if fixture['verification']['model_code']==8 else 0
        require(passed['wave4_bit_sample_checks']==expected_samples*len(fixture['cases'])*2 and
                passed['observer_bit_sample_checks']==expected_observer,'Wave4 PASS sample coverage differs')
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
        semantics={};dc={};bit_comparison={};wave4_comparison={};gen_resets={};gen_arith_comparison={}
        if inputs.get(declared['id'],{}).get('oracle'):
            oracle=inputs[declared['id']]['oracle'];limit=oracle['max_abs_tolerance']
            for profile in ('strict','optimized'):
                matches=[r for r in semantic_records if r.get('fixture')==name and r.get('case')==declared['id'] and r.get('profile')==profile]
                require(len(matches)==1,'Missing or duplicate semantic profile');value=matches[0]
                require(value.get('semantic_kind')==oracle['verification']['kind'] and value.get('oracle_sha256')==oracle['oracle_sha256'],'Semantic oracle identity differs')
                require(type(value.get('samples')) is int and value['samples']==expected_samples and value.get('max_abs_tolerance')==limit,'Semantic sample coverage/tolerance differs')
                error=value.get('max_abs');require(type(error) in (int,float) and error>=0,'Invalid semantic error')
                bound=error+oracle['max_cache_rounding_error']
                if gen_mode:bound=bound+oracle['model_tail_bound']+oracle['model_evaluation_bound']
                require(value.get('max_model_error_bound')==bound and bound<=limit,'Semantic average exceeds unchanged model limit')
                semantics[profile]=value
                if gen_arith_mode:
                    require(set(value)=={'fixture','case','profile','semantic_kind','samples','max_abs',
                            'max_model_error_bound','max_abs_tolerance','oracle_sha256'},'Unknown or missing Gen arithmetic semantic metadata')
                    matches=[r for r in gen_arith_records if r.get('fixture')==name and r.get('case')==declared['id']and r.get('profile')==profile]
                    require(len(matches)==1,'Missing or duplicate Gen arithmetic bit profile');record=matches[0]
                    require(set(record)=={'fixture','case','profile','oracle_sha256','samples','bit_different','zero_sign_different'},
                            'Unknown or missing Gen arithmetic bit metadata')
                    require(record['oracle_sha256']==oracle['oracle_sha256'],'Gen arithmetic bit oracle differs')
                    require(all(type(record[k])is int for k in ('samples','bit_different','zero_sign_different')),
                            'Invalid Gen arithmetic bit count type')
                    require(record['samples']==expected_samples and 0<=record['bit_different']==record['zero_sign_different']<=expected_samples,
                            'Gen arithmetic bit differences must be zero-sign changes only')
                    if fixture.get('qualification_mode')==GEN_ABS_MODE:
                        require(record['bit_different']==record['zero_sign_different']==0,'Gen abs intrinsic requires exact canonical positive-zero output bits')
                    gen_arith_comparison[profile]=record
                    for counter,field in (('gen_arith_bit_sample_checks','samples'),('gen_arith_bit_differences','bit_different'),
                                          ('gen_arith_zero_sign_differences','zero_sign_different')):
                        gen_arith_totals[counter]+=record[field]
                if gen_mode:
                    require(set(value)=={'fixture','case','profile','semantic_kind','samples','max_abs',
                            'max_model_error_bound','max_abs_tolerance','oracle_sha256'},'Unknown or missing Gen semantic metadata')
                    matches=[r for r in gen_records if r.get('fixture')==name and r.get('case')==declared['id'] and r.get('profile')==profile]
                    require(len(matches)==1,'Missing or duplicate Gen reset profile');record=matches[0]
                    require(set(record)=={'fixture','case','profile','oracle_sha256','event_schedule_sha256','reset_witness_sha256',
                            'reset_events','witness_events','witness_sample_checks','witness_differences','max_abs','max_abs_tolerance'},
                            'Unknown or missing Gen reset metadata')
                    for key in ('oracle_sha256','event_schedule_sha256','reset_witness_sha256'):
                        require(record[key]==oracle[key],'Gen reset witness identity differs')
                    code=oracle['model_code'];_,mask,_=gen_cache_data(code,declared['id'])
                    events=len(declared['events'])*plan['rounds'];witnesses=sum(mask)*plan['rounds']
                    require(all(type(record[k])is int for k in ('reset_events','witness_events','witness_sample_checks','witness_differences')),
                            'Invalid Gen reset count type')
                    require(record['reset_events']==events and record['witness_events']==witnesses and
                            record['witness_sample_checks']==2*witnesses and record['witness_differences']==0,
                            'Gen reset witness coverage/differences differ')
                    maximum=record['max_abs']
                    require(type(maximum)in (int,float) and math.isfinite(maximum) and 0<=maximum<=2e-6 and
                            (witnesses>0 or maximum==0) and record['max_abs_tolerance']==2e-6,'Gen reset witness error exceeds fixed gate')
                    gen_resets[profile]=record
                    for counter,field in (('gen_reset_events','reset_events'),('gen_reset_witness_events','witness_events'),
                                          ('gen_reset_witness_sample_checks','witness_sample_checks'),('gen_reset_witness_differences','witness_differences')):
                        gen_totals[counter]+=record[field]
                if oracle['verification']['kind']==WAVE4_KIND:
                    require(set(value)=={'fixture','case','profile','semantic_kind','samples','max_abs',
                            'max_model_error_bound','max_abs_tolerance','oracle_sha256'},'Unknown or missing wave4 semantic metadata')
                    matches=[r for r in wave4_records if r.get('fixture')==name and r.get('case')==declared['id'] and r.get('profile')==profile]
                    require(len(matches)==1,'Missing or duplicate wave4 bit profile');record=matches[0]
                    require(set(record)=={'fixture','case','profile','oracle_sha256','samples','bit_different',
                            'zero_sign_different','observer_samples','observer_bit_different'},'Unknown or missing wave4 bit metadata')
                    require(record.get('oracle_sha256')==oracle['oracle_sha256'],'Wave4 bit oracle identity differs')
                    require(all(type(record[k])is int for k in ('samples','bit_different','zero_sign_different','observer_samples','observer_bit_different')),
                            'Invalid wave4 bit count type')
                    require(record['samples']==expected_samples and 0<=record['bit_different']==record['zero_sign_different']<=expected_samples,
                            'Wave4 operation bit differences must be only zero-sign changes')
                    observer_samples=expected_samples//2 if oracle['verification']['observer_channel']==1 else 0
                    require(record['observer_samples']==observer_samples and record['observer_bit_different']==0,
                            'Wave4 direct observer bit gate/coverage differs')
                    wave4_comparison[profile]=record
                    for counter,field in (('wave4_bit_sample_checks','samples'),('wave4_bit_differences','bit_different'),
                                          ('wave4_zero_sign_differences','zero_sign_different'),
                                          ('observer_bit_sample_checks','observer_samples'),('observer_bit_differences','observer_bit_different')):
                        wave4_totals[counter]+=record[field]
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
        if wave4_comparison:cases[-1]['wave4_bit_comparison']=wave4_comparison
        if gen_resets:cases[-1]['gen_reset_comparison']=gen_resets
        if gen_arith_comparison:cases[-1]['gen_arith_bit_comparison']=gen_arith_comparison
        if power_mode or wave4_mode or gen_mode or gen_arith_mode:
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
            if wave4_mode or gen_arith_mode or gen_mode and fixture.get('qualification_mode')!=GEN_FEEDBACK_MODE:
                require(record['float_bit_different']==record['zero_sign_different']==0,'Same-artifact pair must preserve all output bits')
            if gen_mode and fixture.get('qualification_mode')==GEN_FEEDBACK_MODE:
                require((case['max_abs']>0)==(record['float_bit_different']>record['zero_sign_different']),
                        'Gen pair numerical and raw-bit diagnostics contradict')
            cases[-1]['rounding_comparison']=record
    if wave4_mode:
        require(all(passed[k]==total for k,total in wave4_totals.items()),'Wave4 per-case/PASS bit totals differ')
    if gen_mode:
        require(all(passed[k]==total for k,total in gen_totals.items()),'Gen per-case/PASS reset totals differ')
    if gen_arith_mode:
        require(all(passed[k]==total for k,total in gen_arith_totals.items()),'Gen arithmetic per-case/PASS bit totals differ')
    require(passed['compared_samples']==expected_samples*len(cases),'Total sample count differs')
    return {**(binding or {}),**({'qualification_mode':fixture['qualification_mode']}if 'qualification_mode'in fixture else {}),
            'fixture':name,'family':fixture['family'],'role':fixture['role'],
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
