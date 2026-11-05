# SPDX-License-Identifier: MIT
"""Registry aliases and source attempts must not acquire each other's evidence."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
import build_gen_route_inventory as audit
class GenRouteInventoryTests(unittest.TestCase):
 def fixture(self,root):
  inventory=root/'site/data/gen-inventory.json';inventory.parent.mkdir(parents=True);inventory.write_bytes((audit.ROOT/'site/data/gen-inventory.json').read_bytes())
  folder=root/'tests/fixtures/smoke/gen-probe';folder.mkdir(parents=True);code=b'out1=in1; out2=in2;\n';(folder/'less.genexpr').write_bytes(code);graph={'patcher':{'boxes':[{'box':{'text':'gen~','rnbo_extra_attributes':{'expr':code.decode()}}}]}};patch=json.dumps(graph).encode();(folder/'less.rnbopat').write_bytes(patch);row=dict(id='less',exact_name='<p',registry_lookup='ltp',syntax='infix',patch='less.rnbopat',genexpr='less.genexpr',patch_sha256=hashlib.sha256(patch).hexdigest(),genexpr_sha256=hashlib.sha256(code).hexdigest());(folder/'catalog.json').write_text(json.dumps({'cases':[row]}));evidence=root/'evidence';evidence.mkdir();result=dict(id='less',exact_name='<p',registry_lookup='ltp',source_sha256=row['patch_sha256'],genexpr_sha256=row['genexpr_sha256'],status='pass',finalized=True,samples_checked=10240,median_us=10,peak_us=12,cpu_review_reasons=[]);p=evidence/'xiao-smoke-gen-probe.json';p.write_text(json.dumps(dict(format='rnbo-hardware-smoke-results-v1',surface='genexpr',cases=[result])));return folder,p
 def test_only_exact_alias_has_the_matched_observation(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);self.fixture(root);data=audit.build(root);rows={v['exact_name']:v for v in data['entries']};self.assertTrue(rows['<p']['has_matched_short_smoke_hardware_pass']);self.assertFalse(rows['ltp']['has_authored_source_scenario']);self.assertEqual(data['summary']['has_authored_source_scenario'],1);self.assertEqual(data['summary']['registry_entries'],212);self.assertFalse(rows['<p']['all_modes_qualified']);self.assertFalse(rows['<p']['visual_Gen_qualified'])
 def test_different_source_or_non_gen_surface_does_not_match(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);_,p=self.fixture(root);original=json.loads(p.read_text())
   for kind in('wrong-source','wrong-surface'):
    data=copy.deepcopy(original)
    if kind=='wrong-source':data['cases'][0]['source_sha256']='0'*64
    else:data['surface']='codebox'
    p.write_text(json.dumps(data));result=audit.build(root);self.assertEqual(result['summary']['has_authored_source_scenario'],1);self.assertEqual(result['summary']['has_matched_short_smoke_hardware_pass'],0)
 def test_standalone_and_embedded_code_must_match(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);folder,_=self.fixture(root);(folder/'less.genexpr').write_text('out1=0;out2=0;\n')
   with self.assertRaises(AssertionError):audit.build(root)
if __name__=='__main__':unittest.main()
