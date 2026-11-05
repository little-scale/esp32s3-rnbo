// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import test from 'node:test';
import {fileURLToPath} from 'node:url';
import {lowerVisualGen} from './gen_visual.mjs';
import {describeFlatPatcher} from './patcher.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const directory=path.join(root,'tests/fixtures/smoke/gen-visual-core');
const catalog=JSON.parse(fs.readFileSync(path.join(directory,'catalog.json')));
function source(name='identity'){return JSON.parse(fs.readFileSync(path.join(directory,name+'.rnbopat'))).patcher;}
const inner=s=>s.boxes.find(({box})=>box.id==='gen').box.genpatcher;
test('original embedded graphs lower without mutating source and report dense ports',()=>{
 for(const row of catalog.cases){const p=source(row.id),original=structuredClone(p);const r=lowerVisualGen(inner(p));assert.deepEqual(p,original);assert.equal(r.geninlets,2);assert.equal(r.genoutlets,2);assert.ok(r.expression.includes('out1 ='));assert.ok(!JSON.stringify(p).includes('"expr"'));}
});
test('negative-zero source literals retain their sign in lowered code',()=>{
 for(const literal of ['-0','-0.0','-0e12']){
  const p=inner(source('gain-half'));p.patcher.boxes.find(({box})=>box.id==='op').box.text='* '+literal;
  assert.match(lowerVisualGen(p).expression,/\* -0\.0;/);
 }
 const p=inner(source('unconnected-history'));p.patcher.boxes.find(({box})=>box.id==='h').box.text='history hold -0';
 assert.match(lowerVisualGen(p).expression,/History hold\(-0\.0\);/);
});
test('history reads precede arithmetic and simultaneous next-state commits',()=>{
 const r=lowerVisualGen(inner(source('three-state-rotation')));assert.equal(r.history_count,3);
 for(const name of ['first','second','third']){const declaration=r.expression.indexOf(`History ${name}(`);const read=r.expression.indexOf(`= ${name};`);const write=r.expression.lastIndexOf(`${name} =`);assert.ok(declaration>=0&&read>declaration&&write>r.expression.indexOf('out2 ='));}
 assert.match(lowerVisualGen(inner(source('two-sample-history'))).expression,/History hold\(0.25\);/);
});
test('missing/doubled/ranged connections and algebraic loops reject',()=>{
 const mutations=[g=>g.lines.pop(),g=>g.lines.push(structuredClone(g.lines[0])),g=>g.lines[0].patchline.source[1]=1,
  g=>g.lines[0].patchline.destination[1]=8,g=>g.lines[0].patchline.source[0]='absent',
  g=>g.boxes[0].box.text='in 0',g=>g.boxes[0].box.text='in 3',g=>g.boxes[0].box.numinlets=1];
 for(const f of mutations){const g=inner(source()).patcher;f(g);assert.throws(()=>lowerVisualGen({patcher:g}));}
 const s=inner(source('add'));s.patcher.lines=s.patcher.lines.filter(x=>x.patchline.destination[0]!=='op');s.patcher.lines.push({patchline:{source:['op',0],destination:['op',0]}},{patchline:{source:['a',0],destination:['op',1]}});assert.throws(()=>lowerVisualGen(s),/algebraic cycle/);
});
test('unsupported/default/resource/codebox forms fail closed',()=>{
 for(const text of ['param p 1','delay 32','codebox','expr in1','* 1 2','abs 1','history h NaN','history vg_n0 1']){
  const g=inner(source('gain-half'));g.patcher.boxes.find(({box})=>box.id==='op').box.text=text;
  assert.throws(()=>lowerVisualGen(g));
 }
 const extra=inner(source('gain-half'));extra.patcher.boxes[0].box.saved_object_attributes={mode:1};assert.throws(()=>lowerVisualGen(extra),/attributes/);
 const g=inner(source('cross-feedback'));g.patcher.boxes.find(({box})=>box.id==='h1').box.text='history first 0';assert.throws(()=>lowerVisualGen(g),/history names/);
});
const pkg=process.env.RNBO_DIR??path.join(os.homedir(),'Documents/Max 9/Packages/RNBO');
const available=fs.existsSync(path.join(pkg,'server/node_modules/@rnbo/xam'));
if (available)process.env.RNBO_DIR=pkg;
const require=createRequire(import.meta.url);const xam=available?require(path.join(pkg,'server/node_modules/@rnbo/xam')):null;
test('installed licensed frontend admits original embedded core graphs',{skip:!available},()=>{
 for(const row of catalog.cases){const p=source(row.id);const described=describeFlatPatcher(p,xam);const gen=described.boxes.find(({box})=>box.id==='gen').box;assert.equal(gen.rnboinfo.inputs.length,2);assert.equal(gen.rnboinfo.outputs.length,2);assert.equal(gen.rnbo_visual_gen.policy,'embedded-visual-gen-core-v1');assert.deepEqual(p,source(row.id));}
});
test('stale GenExpr/file/options cannot override embedded visual source',{skip:!available},()=>{
 for(const extra of [{expr:'out1=0;'}, {file:'a.gendsp'}, {exposeparams:1}, {title:'unimplemented'}, []]){const p=source();p.boxes.find(({box})=>box.id==='gen').box.rnbo_extra_attributes=extra;assert.throws(()=>describeFlatPatcher(p,xam));}
 const p=source();p.boxes[0].box.genpatcher=inner(source());assert.throws(()=>describeFlatPatcher(p,xam));
});
