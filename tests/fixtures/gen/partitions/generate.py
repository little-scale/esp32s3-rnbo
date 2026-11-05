#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze three original graphs and the direct variable-frame experiment."""
import argparse,hashlib,json
from pathlib import Path
import reference as r
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def artifact():
 programs=[]
 for model,name in r.PROGRAMS:
  patch=HERE.parent/(name+'.rnbopat');code=HERE.parent/(name+'.genexpr');raw=json.loads(patch.read_text());box=next(v['box']for v in raw['patcher']['boxes']if v['box'].get('text')=='gen~');assert box['rnbo_extra_attributes']['expr'].encode()==code.read_bytes()
  programs.append(dict(model=model,id=name,patch=patch.relative_to(ROOT).as_posix(),genexpr=code.relative_to(ROOT).as_posix(),patch_sha256=sha(patch),genexpr_sha256=sha(code),class_name='genpartition'+str(model)))
 return dict(format='rnbo-gen-direct-partition-catalog-v1',execution_route='direct-variable-producer',module_abi=False,player_abi_changed=False,gen_surface='GenExpr',visual_Gen_qualified=False,sample_rate=r.RATE,frames_per_instance=r.FRAMES,maximum_block_frames=r.MAX_BLOCK,producer_fixedblocksize=0,automatic_warmup_blocks=0,nominal_partitions=list(r.PARTITIONS),mixed_partition_pattern=list(r.MIXED),reset_before_samples=list(r.RESETS),force_prepare_before_samples=list(r.PREPARES),instances_per_program_stimulus=13,stimuli=['dyadic','boundary-impulses'],absolute_tolerance=r.LIMIT,reference_sha256=sha(HERE/'reference.py'),generator_sha256=sha(Path(__file__).resolve()),programs=programs,scope='Three exact original GenExpr history graphs, two bounded stimuli, three fresh1-frame renders plus reconstructed2/7/255/256/mixed renders; each nominal partition clips at fixed absolute reset/prepare positions. Direct variable-frame generated producer only, no production module ABI, player audio throughput, visual Gen, external resources, all operators, nonfinite domains or optimisation gain.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();raw=(json.dumps(artifact(),sort_keys=True,indent=2)+'\n').encode();target=HERE/'catalog.json'
 if a.check:
  if not target.is_file()or target.read_bytes()!=raw:raise SystemExit('Direct partition catalog changed')
 else:target.write_bytes(raw)
 print('Checked'if a.check else'Wrote','3 direct-partition programs')
