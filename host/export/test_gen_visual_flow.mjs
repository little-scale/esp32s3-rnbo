// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import {lowerVisualGen} from './gen_visual.mjs';
import {lowerVisualGen as qualified} from '../../tests/fixtures/smoke/gen-visual-flow/qualified_lowerer.mjs';
import {describeFlatPatcher} from './patcher.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const folder=path.join(root,'tests/fixtures/smoke/gen-visual-flow');
const catalog=JSON.parse(fs.readFileSync(path.join(folder,'catalog.json')));
const source=row=>JSON.parse(fs.readFileSync(path.join(folder,row.patch))).patcher;
const inner=p=>p.boxes.find(({box})=>box.id==='gen').box.genpatcher;
const row=id=>catalog.cases.find(c=>c.id===id);
test('all42 visual flow sources match the immutable lowerer without mutation',()=>{
 assert.equal(catalog.cases.length,42);assert.equal(new Set(catalog.cases.map(c=>c.visual_operator)).size,33);
 for(const c of catalog.cases){const p=source(c),before=structuredClone(p),v=lowerVisualGen(inner(p));assert.deepEqual(p,before);assert.deepEqual(v,qualified(inner(p)));assert.equal(v.policy,'embedded-visual-gen-flow-v1');assert.equal(v.geninlets,2);assert.equal(v.genoutlets,2);assert.ok(v.operators.includes(c.visual_operator));}
});
test('multiple outputs come from one call and route by actual source outlet',()=>{
 for(const [id,count,out] of [['visual-counter-out0',3,0],['visual-counter-out1',3,1],['visual-counter-out2',3,2],['visual-cartopol-out1',2,1],['visual-poltocar-out1',2,1]]){
  const v=lowerVisualGen(inner(source(row(id))));const call=v.expression.split('\n').find(s=>s.includes(' = '+(id.includes('counter')?'counter':id.includes('cartopol')?'cartopol':'poltocar')+'('));
  assert.equal(call.split(' = ')[0].split(', ').length,count);assert.equal(v.expression.split('\n').filter(s=>s.includes(' = counter(')).length,id.includes('counter')?1:0);
  assert.match(v.expression,new RegExp('out1 = vg_n2'+(out?'_o'+out:'')+';'));
 }
});
test('history can capture a selected multiple-output value',()=>{
 const g=inner(source(row('visual-counter-out2')));g.patcher.boxes.push({box:{id:'h',maxclass:'newobj',text:'history carry 0',numinlets:1,numoutlets:1}});g.patcher.lines.push({patchline:{source:['op',2],destination:['h',0]}});
 assert.match(lowerVisualGen(g).expression,/carry = vg_n2_o2;/);
});
test('bad outlets, stale arities, missing inputs and implicit options fail closed',()=>{
 for(const mutate of [g=>g.lines[0].patchline.source[1]=3,g=>g.lines[0].patchline.source[1]=-1,g=>g.lines[0].patchline.source[1]=.5,g=>g.boxes.find(x=>x.box.id==='op').box.numoutlets=1,g=>g.boxes.find(x=>x.box.id==='op').box.numinlets=2,g=>g.lines.pop(),g=>g.boxes.find(x=>x.box.id==='op').box.text='counter @init 2']){
  const g=inner(source(row('visual-counter-out2')));mutate(g.patcher);assert.throws(()=>lowerVisualGen(g));
 }
 for(const id of ['visual-scale','visual-mtof','visual-ftom']){
  const g=inner(source(row(id)));g.patcher.lines=g.patcher.lines.filter(x=>x.patchline.destination[0]!=='op'||x.patchline.destination[1]!==row(id).input_bindings.length-1);assert.throws(()=>lowerVisualGen(g),/disconnected/);
 }
});
const pkg=process.env.RNBO_DIR??path.join(os.homedir(),'Documents/Max 9/Packages/RNBO');const available=fs.existsSync(path.join(pkg,'server/node_modules/@rnbo/xam'));
if(available)process.env.RNBO_DIR=pkg;
const require=createRequire(import.meta.url);const xam=available?require(path.join(pkg,'server/node_modules/@rnbo/xam')):null;
test('licensed frontend describes all fully wired visual flow graphs',{skip:!available},()=>{
 for(const c of catalog.cases){const d=describeFlatPatcher(source(c),xam),g=d.boxes.find(({box})=>box.id==='gen').box;assert.equal(g.rnboinfo.inputs.length,2,c.id);assert.equal(g.rnboinfo.outputs.length,2,c.id);}
});
