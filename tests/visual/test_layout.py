# SPDX-License-Identifier: MIT
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'host/visual'))
from layout import compile_layout,write_layout,WIDTH,HEIGHT,MAX_NODES,MAX_SEGMENTS


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.patch=json.loads((ROOT/'examples/sine/sine.rnbopat').read_text())
        self.description={'parameters':[{'index':0,'paramId':'frequency','name':'frequency','unit':'Hz'},
                                        {'index':1,'paramId':'level','name':'level','unit':''}]}

    def test_source_graph_preserved_and_parameters_follow_exported_identity(self):
        before=copy.deepcopy(self.patch)
        self.description['parameters'].reverse()
        for i,p in enumerate(self.description['parameters']):p['index']=i
        v=compile_layout(self.patch,self.description)
        self.assertTrue(v['available']);self.assertEqual(self.patch,before)
        self.assertEqual(len(v['nodes']),6);self.assertEqual(len(v['segments']),5)
        self.assertEqual({n['id']:n['parameter'] for n in v['nodes']}['frequency'],1)
        for n in v['nodes']:
            self.assertTrue(0<=n['x']<=WIDTH-n['width']);self.assertTrue(0<=n['y']<=HEIGHT-n['height'])
            for other in v['nodes']:
                if n is other:continue
                self.assertTrue(n['x']+n['width']<=other['x'] or other['x']+other['width']<=n['x'] or
                                n['y']+n['height']<=other['y'] or other['y']+other['height']<=n['y'])
        for s in v['segments']:
            self.assertTrue(all(0<=s[i]<[WIDTH,HEIGHT][i%2] for i in range(4)))

    def test_second_inlet_is_inferred_and_used_without_saved_port_count(self):
        v=compile_layout(self.patch,self.description)
        gain=next(n for n in v['nodes'] if n['id']=='gain')
        self.assertEqual(gain['inlets'],2)
        wire=v['segments'][2]
        self.assertEqual(wire[2],gain['x']+gain['width']-4)

    def test_dense_or_missing_source_falls_back_without_partial_circuit(self):
        for count in (MAX_NODES+1,):
            self.patch['patcher']['boxes']=[{'box':{'id':str(i),'text':'cycle~','patching_rect':[0,0,80,20]}} for i in range(count)]
            v=compile_layout(self.patch,self.description)
            self.assertFalse(v['available']);self.assertEqual(v['nodes'],[])
            self.assertEqual(len(v['parameters']),2)
        self.assertFalse(compile_layout(None,self.description)['available'])

    def test_bad_coordinates_and_unresolvable_wire_are_explicit_fallback(self):
        for value in (float('nan'),float('inf'),True,1e12):
            patch=copy.deepcopy(self.patch);patch['patcher']['boxes'][0]['box']['patching_rect'][0]=value
            self.assertFalse(compile_layout(patch,self.description)['available'])
        self.patch['patcher']['lines'][0]['patchline']['source'][0]='unknown'
        v=compile_layout(self.patch,self.description)
        self.assertFalse(v['available']);self.assertEqual(v['segments'],[])

    def test_midpoint_and_wire_budget_never_silently_drop_connections(self):
        line=self.patch['patcher']['lines'][0]['patchline']
        line['midpoints']=[200,300,220,340]
        v=compile_layout(self.patch,self.description)
        self.assertEqual(v['source_cords'][0]['midpoints'],line['midpoints'])
        self.assertEqual(len(v['segments']),7)
        line['midpoints']=[0,0]*MAX_SEGMENTS
        v=compile_layout(self.patch,self.description)
        self.assertFalse(v['available']);self.assertIn('384',v['reason'])

    def test_duplicate_ids_and_out_of_range_ports_fall_back(self):
        self.patch['patcher']['boxes'][1]['box']['id']='frequency'
        self.assertFalse(compile_layout(self.patch,self.description)['available'])
        self.patch=json.loads((ROOT/'examples/sine/sine.rnbopat').read_text())
        self.patch['patcher']['lines'][0]['patchline']['source'][1]=32
        self.assertFalse(compile_layout(self.patch,self.description)['available'])

    def test_compilation_is_deterministic_and_c_strings_are_safe(self):
        self.description['parameters'][0]['name']='Frequency"\\\n'
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);desc=temp/'description.json';desc.write_text(json.dumps(self.description))
            a=write_layout(ROOT/'examples/sine/sine.rnbopat',desc,temp/'a','Test"\\\n')
            b=write_layout(ROOT/'examples/sine/sine.rnbopat',desc,temp/'b','Test"\\\n')
            self.assertEqual(a,b)
            self.assertEqual((temp/'a/patch_layout.c').read_bytes(),(temp/'b/patch_layout.c').read_bytes())
            self.assertIn('\\042',(temp/'a/patch_layout.c').read_text())


if __name__=='__main__':unittest.main()
