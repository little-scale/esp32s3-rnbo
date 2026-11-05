// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import {lowerVisualGen} from './gen_visual.mjs';
import {lowerVisualGen as qualifiedCore} from '../../tests/fixtures/smoke/gen-visual-core/qualified_lowerer.mjs';
import {lowerVisualGen as qualifiedMath} from '../../tests/fixtures/smoke/gen-visual-math/qualified_lowerer.mjs';
import {describeFlatPatcher} from './patcher.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const folder=path.join(root,'tests/fixtures/smoke/gen-visual-math');
const catalog=JSON.parse(fs.readFileSync(path.join(folder,'catalog.json')));
function source(row){return JSON.parse(fs.readFileSync(path.join(folder,row.patch))).patcher;}
const inner=p=>p.boxes.find(({box})=>box.id==='gen').box.genpatcher;
test('every exact source spelling lowers deterministically without source mutation',()=>{
 assert.equal(catalog.cases.length,101);assert.equal(new Set(catalog.cases.map(r=>r.id.toLowerCase())).size,101);
 for(const row of catalog.cases){const p=source(row),before=structuredClone(p),v=lowerVisualGen(inner(p));assert.deepEqual(p,before);assert.deepEqual(v,qualifiedMath(inner(p)));assert.equal(v.policy,'embedded-visual-gen-math-v1');assert.equal(v.geninlets,2);assert.equal(v.genoutlets,2);assert.ok(v.operators.includes(row.visual_operator));}
});
test('production preserves every qualified core lowering byte-for-byte',()=>{
 const core=path.join(root,'tests/fixtures/smoke/gen-visual-core');
 for(const row of JSON.parse(fs.readFileSync(path.join(core,'catalog.json'))).cases){const p=JSON.parse(fs.readFileSync(path.join(core,row.patch))).patcher;assert.deepEqual(lowerVisualGen(inner(p)),qualifiedCore(inner(p)));}
});
test('fully connected maths rejects ambiguous constructors and stale arities',()=>{
 for(const name of ['atan2','hypot','pow','sin','log']){
  const row=catalog.cases.find(r=>r.visual_operator===name),p=inner(source(row));p.patcher.boxes.find(({box})=>box.id==='op').box.text=name+' 2';
  assert.throws(()=>lowerVisualGen(p),/fully connected/);
 }
 for(const name of ['PI','constant']){const row=catalog.cases.find(r=>r.visual_operator===name),p=inner(source(row));p.patcher.boxes.find(({box})=>box.id==='op').box.text=name==='PI'?'PI 2':'constant';assert.throws(()=>lowerVisualGen(p));}
});
const pkg=process.env.RNBO_DIR??path.join(os.homedir(),'Documents/Max 9/Packages/RNBO');const available=fs.existsSync(path.join(pkg,'server/node_modules/@rnbo/xam'));
if(available)process.env.RNBO_DIR=pkg;
const require=createRequire(import.meta.url);const xam=available?require(path.join(pkg,'server/node_modules/@rnbo/xam')):null;
test('licensed RNBO frontend admits the exact visual maths graphs',{skip:!available},()=>{
 for(const row of catalog.cases){const described=describeFlatPatcher(source(row),xam),gen=described.boxes.find(({box})=>box.id==='gen').box;assert.equal(gen.rnboinfo.inputs.length,2,row.id);assert.equal(gen.rnboinfo.outputs.length,2,row.id);}
});
