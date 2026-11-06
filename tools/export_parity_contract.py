# SPDX-License-Identifier: MIT
"""Closed same-version ABBA hardware contract; references stay producer-independent."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'tests/fixtures/smoke/max-export-parity'
FAMILY='max-export-parity'
CATALOG_SHA='d62ab0dc563381ed6ffb9cbabbedbd65c9708501316c9d73833637c2a25f95ba'
REFERENCE_SHA='f6b52921269c69f37434263ebe70c015c37174a96b6e2c631ffec0ef41d43748'
MODELS_SHA='fded519ebf3c68f0213f44ff497275f0e9e6b98ba8d600ece2925132e48c7ed4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(v,msg):
    if not v:raise ValueError(msg)
def catalog(value):
    canonical=lambda value:(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
    require(value.get('family')==FAMILY and sha(FOLDER/'catalog.json')==CATALOG_SHA and hashlib.sha256(canonical(value)).hexdigest()==CATALOG_SHA and sha(FOLDER/'reference.py')==REFERENCE_SHA and sha(FOLDER/'models.json')==MODELS_SHA,'Export comparison source/model/reference differs')
    rows=value['cases'];require(len(rows)==12 and len({r['id']for r in rows})==12,'Export comparison needs12 distinct ABBA contexts')
    for start in(0,4,8):
        part=rows[start:start+4]
        require(len({r['subject']for r in part})==1 and [r['export_route']for r in part]==['importer','max','max','importer']and [r['abba_position']for r in part]==[0,1,2,3],'Export comparison ABBA order differs')
    return value

def prepared_route(row,prepared,manifest):
    p=json.loads((prepared/'provenance.json').read_bytes())
    require(p['raw_files_sha256'].get('rnbo_source.h')==row['export_raw_header_sha256']and sha(prepared/'rnbo_source.h')==row['export_prepared_header_sha256'],'Export route producer header differs')
    require(manifest.get('numerical_profile')=='float32-strict'and manifest.get('parameter_count')==row['parameter_contract_count'],'Export route precision or parameter contract differs')

def plan(value):
    from collect_hardware_smoke import expected_pool,expected_stream
    c=catalog(json.loads((FOLDER/'catalog.json').read_bytes()))
    require(value.get('family')==FAMILY and value.get('catalog_sha256')==CATALOG_SHA and value.get('reference_source_sha256')==REFERENCE_SHA and value.get('surface')=='patcher'and value.get('prepare_zero_warm_blocks')==0 and value.get('warmup_blocks')==4 and value.get('timed_blocks')==16 and not value.get('compile_failures')and not value.get('admission_failures'),'Export route comparison execution policy differs')
    require([r['id']for r in value['cases']]==[r['id']for r in c['cases']],'Export comparison image order differs')
    spec=importlib.util.spec_from_file_location('export_pair_reference',FOLDER/'reference.py');reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference);pool=expected_pool(value)
    for row,source in zip(value['cases'],c['cases']):
        require(all(row.get(k)==v for k,v in source.items())and row.get('source_sha256')==source['patch_sha256']and row.get('arena_bytes')==1048576 and row.get('absolute_tolerance')==struct.unpack('<f',struct.pack('<f',source['maximum_absolute_error']))[0],'Export route source/header/arena/limit differs')
        require(row['input_words']==list(reference.case_input_words(source['model'])),'Export route input stimulus differs')
        blocks,_=expected_stream(row,True,pool);require(tuple(map(tuple,blocks))==reference.reference_blocks(source['model'],reference.case_input_words(source['model'])),'Export route original oracle differs')
        if source['parameter_contract_count']:
            parameters=row['parameters'];authored=reference.parameter_events(source['model']);require(row.get('expected_parameter_count')==2 and len(parameters)==2 and {p['id']:p for p in parameters}=={p['id']:p for p in reference.parameters()}and len(row.get('parameter_events',[]))==len(authored)==22,'Export pair event schema differs')
            for e,a in zip(row['parameter_events'],authored):
                slot=next(i for i,p in enumerate(parameters)if p['id']==a['id']);p=parameters[slot]
                require(e==dict(before_call=a['before_call'],id=a['id'],parameter_slot=slot,value_word=reference.word(a['value']),normalized_word=reference.word((a['value']-p['minimum'])/(p['maximum']-p['minimum']))),'Export pair authored event differs')
        else:require('parameters'not in row and not row.get('parameter_events')and not row.get('expected_parameter_count'),'Parameter-free Gen comparison acquired events')

MANUAL_MAX_PREPARATIONS={'206b62f0d8ea8d9a36678afdf881fa317253ecca1e76bf2a40fec97e4a557942': {'manifest_sha256': '29a8d41444f1fa506ef13cae274d8e60d44a6e79ee37b5f78595895b2e5be128', 'source_tree_sha256': 'bbd08806fcbffbf0e5f17c1be883c506c16d3b6251530e949564a954004814c0', 'editable_source_sha256': '1a7b263cfdd557be1062c6473a7081157330c4f9f12fbb4681bd9976b197bca3'}, 'a3febb50f7e90b0cfe4133dbaa79633d1b61b376a959732dc70c36758be1b435': {'manifest_sha256': 'f7c9bb8a8b6e8980e43ae3153de6baddb9ca311d7ed97e6f0ded47f6b3fe3122', 'source_tree_sha256': '25d2434fc06c1d9d94da75d4ad03d8967444d21b759bccb0353b62dfa8f3ef4b', 'editable_source_sha256': '4205d34b32de23f5e9708c3fc8b439957c26116b23f49af6c0fc8d963d2b1798'}, '4b233315d812884cf58149566bc86af45b895d139c3fb86641c3b580b75ab075': {'manifest_sha256': 'c1b7eb50e00d6be515775e1340b11994389c491c6aa584cbf6dce5437d8a30b4', 'source_tree_sha256': 'fabaf6f5e740b4404ada03dcab38bfa3dd26e9f6656ca43d4e6f13da3c04eafb', 'editable_source_sha256': '110a4236bda3833228bdfba8da5ef74f5a6d1a9e7e101246161fb8f7172bab10'}}

def validate_manual_prepared(provenance,manifest,snapshot):
    canonical=lambda value:(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
    key=hashlib.sha256(canonical(snapshot.get('prepared_files_sha256',{}))).hexdigest();proof=MANUAL_MAX_PREPARATIONS.get(key)
    require(proof is not None and manifest.get('voices')is None and manifest.get('voice_topology')=='manual-export-unspecified'and
            hashlib.sha256(canonical(manifest)).hexdigest()==proof['manifest_sha256']and manifest.get('source_tree_sha256')==proof['source_tree_sha256']and
            manifest.get('editable_source_sha256')==proof['editable_source_sha256']and provenance.get('prepared_files_sha256')==snapshot.get('prepared_files_sha256'),
            'Manual Max export must match one of the three exact same-version comparison preparations')
