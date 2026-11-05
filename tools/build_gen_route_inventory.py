#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit authored registry routes, keeping source coverage separate from execution."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=Path('evidence/gen-registry-route-coverage.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def build(root=ROOT):
 inventory_path=root/'site/data/gen-inventory.json';inventory=json.loads(inventory_path.read_text());entries=inventory['RNBO_GenExpr_registry_entries'];names={v['exact_name']for v in entries};assert len(names)==len(entries)==212
 evidence=[];inputs={'site/data/gen-inventory.json':sha(inventory_path)}
 for p in sorted((root/'evidence').glob('xiao-smoke-gen*.json')):
  d=json.loads(p.read_text())
  if d.get('format')!='rnbo-hardware-smoke-results-v1'or d.get('surface')!='genexpr':continue
  path=p.relative_to(root).as_posix();inputs[path]=sha(p)
  for section in('cases','compile_failures','admission_failures'):
   for index,row in enumerate(d.get(section,[])):
    evidence.append((path,section,index,row))
 scenarios={n:[]for n in names}
 catalogs=list(sorted((root/'tests/fixtures/smoke').glob('gen-*/catalog.json')))+list(sorted((root/'tests/fixtures/gen').glob('*/recipes.json')))
 for p in catalogs:
  catalog=json.loads(p.read_text());path=p.relative_to(root).as_posix();inputs[path]=sha(p);recipes='recipes'in catalog
  for row in catalog.get('recipes'if recipes else'cases',[]):
   source=row.get('source',{})if recipes else row;exact=source.get('exact_name');lookup=exact if exact in names else source.get('registry_lookup')
   if lookup not in names:continue
   patch=p.parent/row['patch'];code=p.parent/row['genexpr'];raw=json.loads(patch.read_text());boxes=[v['box']for v in raw['patcher']['boxes']if v['box'].get('text')=='gen~'];assert len(boxes)==1 and boxes[0]['rnbo_extra_attributes']['expr'].encode()==code.read_bytes(),str(patch)
   patch_sha=sha(patch);code_sha=sha(code)
   if row.get('patch_sha256'):assert row['patch_sha256']==patch_sha
   if row.get('genexpr_sha256'):assert row['genexpr_sha256']==code_sha
   if recipes:assert source.get('inventory_id')=='rnbo-genexpr:'+lookup
   observed=[]
   for ev,section,index,result in evidence:
    if result.get('id')!=row['id']or result.get('source_sha256')!=patch_sha:continue
    if result.get('genexpr_sha256')is not None:assert result['genexpr_sha256']==code_sha
    assert result.get('registry_lookup',source.get('registry_lookup',lookup))==source.get('registry_lookup',lookup)
    if result.get('exact_name')is not None:assert result['exact_name']==source.get('exact_name')
    if section=='cases':
     assert result['status']in('pass','output_mismatch')and result['finalized']is True
     observation=dict(status=result['status'],samples_checked=result['samples_checked'],median_us=result['median_us'],peak_us=result['peak_us'],cpu_review_reasons=result['cpu_review_reasons'],full_qualification_claimed=False)
    else:observation=dict(status=result['status'],hardware_executed=False)
    observation.update(evidence=ev,selector=f'/{section}/{index}',evidence_sha256=inputs[ev]);observed.append(observation)
   scenarios[lookup].append(dict(id=row['id'],catalog=path,catalog_sha256=inputs[path],patch=patch.relative_to(root).as_posix(),source_sha256=patch_sha,genexpr=code.relative_to(root).as_posix(),genexpr_sha256=code_sha,authored_exact_name=source.get('exact_name'),syntax=source.get('syntax'),binding='recipe exact inventory id'if recipes else'exact authored registry name'if exact in names else'explicit catalog registry lookup; see authored spelling/form',scope=row.get('scope','Original dedicated qualification recipe; this audit matches only short-smoke receipts. See its separate long qualification record.'),matched_short_smoke_observations=observed))
 rows=[]
 for entry in sorted(entries,key=lambda v:v['exact_name']):
  items=scenarios[entry['exact_name']];observed=[v for s in items for v in s['matched_short_smoke_observations']]
  rows.append(dict(id=entry['id'],exact_name=entry['exact_name'],is_alias=entry['is_alias'],canonical=entry['canonical'],aliases_inherit_qualification=False,source_scenarios=items,has_authored_source_scenario=bool(items),has_matched_short_smoke_hardware_pass=any(v['status']=='pass'for v in observed),has_matched_short_smoke_output_mismatch=any(v['status']=='output_mismatch'for v in observed),has_matched_short_smoke_rejection=any(v['status']not in('pass','output_mismatch')for v in observed),all_modes_qualified=False,visual_Gen_qualified=False))
 summary={key:sum(v[key]for v in rows)for key in('has_authored_source_scenario','has_matched_short_smoke_hardware_pass','has_matched_short_smoke_output_mismatch','has_matched_short_smoke_rejection')};summary['registry_entries']=len(rows);summary['without_authored_source_scenarios']=[v['exact_name']for v in rows if not v['has_authored_source_scenario']]
 return dict(format='rnbo-gen-registry-route-audit-v1',scope='Source-route audit of212 exact RNBO1.4.4 GenExpr registry entries, not212 hardware passes or complete Gen coverage. Matched observations include only published short-smoke receipts with exact case/source identity; dedicated long qualification results remain separate. A source may be a declaration or an exploratory function form of a graph-oriented entry. Failed forms do not reject other APIs/visual Gen. No alias, RNBO, visual, mode/domain, one-frame ABI or optimisation inheritance.',rnbo_version='1.4.4',registry_source_sha256=entries[0]['source_sha256'],input_sha256=inputs,summary=summary,entries=rows)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args();value=build();raw=encoded(value);out=ROOT/OUTPUT
 if a.check:
  if not out.is_file()or out.read_bytes()!=raw:raise SystemExit('Gen route audit differs; regenerate it after new source/evidence publication')
 else:out.write_bytes(raw)
 print(json.dumps(value['summary'],sort_keys=True))
if __name__=='__main__':main()
