// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {canonicalPorts,subjects} from './stage_max_export_parity.mjs';
const fake={parseBoxText:t=>({xamclass:t.split(' ')[0],attributes:{}}),createObject:(name,attrs)=>({name,attrs}),getObjectDescription:o=>({classname:o.name,inputs:o.name==='in~'?[]:o.name==='gen~'?[{},{}]:[{}],outputs:o.name==='out~'?[]:o.name==='gen~'?[{type:'signal'},{type:'signal'}]:[{type:'signal'}]})};
test('canonical staging preserves original patch semantics without mutating its source',()=>{
 const raw={classnamespace:'rnbo',boxes:[{box:{id:'a',maxclass:'newobj',text:'in~ 1'}},{box:{id:'z',maxclass:'newobj',text:'out~ 1'}}],lines:[{patchline:{source:['a',0],destination:['z',0],order:0}}]};const before=structuredClone(raw),out=canonicalPorts(raw,fake);assert.deepEqual(raw,before);assert.equal(out.boxes[0].box.text,'in~ 1');assert.deepEqual(out.lines,[{patchline:{source:['obj-1',0],destination:['obj-2',0],order:0}}]);assert.equal(out.boxes[0].box.numinlets,0);assert.equal(out.boxes[1].box.numoutlets,0);
});
test('native Gen remains a graph with no inserted executable expr or custom lowerer',()=>{
 const source=JSON.parse(fs.readFileSync(new URL('../tests/fixtures/smoke/gen-visual-core/one-sample-history.rnbopat',import.meta.url),'utf8')).patcher;const before=structuredClone(source),out=canonicalPorts(source,fake);assert.deepEqual(source,before);const a=before.boxes.find(({box})=>box.genpatcher).box;const b=out.boxes.find(({box})=>box.genpatcher).box;assert.deepEqual(b.rnbo_extra_attributes,{exposeparams:0});assert.equal(b.text,'gen~');assert.deepEqual(b.genpatcher.patcher.boxes.map(r=>r.box.text),a.genpatcher.patcher.boxes.map(r=>r.box.text));assert.equal(JSON.stringify(b).includes('out1=in1; out2=in2;'),false);assert.equal(subjects.length,8);const code=fs.readFileSync(new URL('./stage_max_export_parity.mjs',import.meta.url),'utf8');assert.equal(code.includes('lowerVisualGen'),false);
});
