// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),client=require('./rnbo-studio-client.js');
const script=await fs.readFile(new URL('./rnbo-studio.js',import.meta.url),'utf8');
function graph() {
  const p={firstobject:null,parentpatcher:null};
  const a={maxclass:'param',boxtext:'param note 39 @min 0 @max 60',rect:[10,20,180,42],varname:'note'};
  const b={maxclass:'out~',boxtext:'out~ 1',rect:[10,100,80,122],varname:''};
  a.nextobject=b;b.nextobject=null;p.firstobject=a;
  const cord={srcobject:a,dstobject:b,srcoutlet:0,dstinlet:0};
  a.patchcords={inputs:[],outputs:[cord]};b.patchcords={inputs:[cord],outputs:[]};
  return {p,a,b};
}
function runtime() {
  const sent=[],g=graph(),r={maxclass:'rnbo~',varname:'instrument',valid:true,nextobject:null,
    getattr:name=>({dumpoutlet:1,exportstatus:'idle',title:'Embedded',exposevoiceparams:0}[name]),
    subpatcher:()=>g.p,message:(...args)=>sent.push(['rnbo',...args])};
  const parent={firstobject:r,parentpatcher:null};
  const context={jsarguments:['rnbo-studio.js','instrument'],patcher:{parentpatcher:parent},
    outlet:(...args)=>sent.push(args),Task:function(fn){this.cancel=()=>{};this.schedule=()=>{};},
    Dict:function(name){this.name=name;this.parse=value=>JSON.parse(value);},Date,Math};
  vm.createContext(context);vm.runInContext(script,context);
  return {context,sent,g,r,parent};
}

test('live drawing reads boxes and cords without mutating or externalising the patch',()=>{
  const {context,g}=runtime();const before=g.a.rect.slice();
  const drawing=JSON.parse(JSON.stringify(context.captureDrawing(g.p)));
  assert.equal(drawing.patcher.boxes[0].box.text,'param note 39 @min 0 @max 60');
  assert.deepEqual(drawing.patcher.boxes[0].box.patching_rect,[10,20,170,22]);
  assert.deepEqual(drawing.patcher.lines[0].patchline,{source:['live-1',0],destination:['live-2',0]});
  assert.deepEqual(g.a.rect,before);assert.equal(g.a.varname,'note');
});

test('target selection requires an explicit name when a parent has multiple RNBO objects',()=>{
  const {context,r,parent}=runtime();const second={...r,varname:'other'};r.nextobject=second;
  assert.equal(context.locateTarget(parent,'instrument'),r);
  assert.throws(()=>context.locateTarget(parent,''),/Multiple/);
  assert.throws(()=>context.locateTarget(parent,'absent'),/No rnbo/);
});

test('only an armed active then successful export can submit; errors and changed drawings stop it',()=>{
  const {context:c,sent,g}=runtime();c.node_ready();c.bang();
  const command=sent.find(x=>x[1]==='prepare');const request=JSON.parse(command[2]);
  c.exportstatus('success');assert.equal(sent.filter(x=>x[1]==='export_success').length,0);
  c.prepared(request.requestId,'{}');c.exportstatus('success');
  assert.equal(sent.filter(x=>x[1]==='export_success').length,0);
  c.exportstatus('active');c.exportstatus('success');c.exportstatus('success');
  assert.equal(sent.filter(x=>x[1]==='export_success').length,1);
  c.build_ready(request.requestId,'a'.repeat(32),'http://127.0.0.1:8788/?job='+ 'a'.repeat(32),'/tmp/package');
  c.bang();const again=JSON.parse(sent.filter(x=>x[1]==='prepare').at(-1)[2]);
  c.prepared(again.requestId,'{}');c.exportstatus('active');g.a.rect=[20,20,190,42];c.exportstatus('success');
  assert.match(sent.at(-1)[2],/drawing changed/);
  assert.equal(sent.filter(x=>x[1]==='export_success').length,1);
  c.bang();const failed=JSON.parse(sent.filter(x=>x[1]==='prepare').at(-1)[2]);c.prepared(failed.requestId,'{}');c.exportstatus('error');
  assert.equal(sent.filter(x=>x[1]==='export_success').length,1);
});

test('fresh export directories, strict generated settings, bounded files, and no stale submission',async()=>{
  const temp=await fs.mkdtemp(path.join(os.tmpdir(),'rnbo-max-test-'));
  try {
    const value={requestId:'one',name:'Live',visual_patch:{patcher:{boxes:[],lines:[]}}};
    const a=await client.prepare(value,temp),b=await client.prepare({...value,requestId:'two'},temp);
    assert.notEqual(a.directory,b.directory);
    assert.equal(a.config.minimal_export,true);assert.equal(a.config.fixedblocksize,256);
    assert.equal(a.config.fixedsamplerate,44100);assert.equal(a.config.polyphony,'linked');
    assert.equal(a.config.postexportcommand,'');
    let calls=0;await assert.rejects(client.submit(a,8788,async()=>{++calls;}));assert.equal(calls,0);
    await fs.mkdir(path.join(a.config.output_path,'common'),{recursive:true});
    for(const file of ['rnbo_source.h','description.json','common/RNBO_Version.h'])await fs.writeFile(path.join(a.config.output_path,file),'original bytes');
    const sent=[];
    const result=await client.submit(a,8788,async(port,url,body,token)=>{
      sent.push({port,url,body,token});return url==='/api/status'?{csrf:'private-session'}:{job:{id:'a'.repeat(32),state:'queued'}};
    });
    assert.equal(result.url,'http://127.0.0.1:8788/?job='+'a'.repeat(32));
    assert.equal(sent[1].token,'private-session');assert.equal(sent[1].body.visual_patch,value.visual_patch);
    assert.equal(Buffer.from(sent[1].body.export_files.find(f=>f.path==='rnbo_source.h').data_base64,'base64').toString(),'original bytes');
    await fs.symlink('/tmp',path.join(a.config.output_path,'linked'));await assert.rejects(client.readExport(a.config.output_path),/Linked/);
    await assert.rejects(client.prepare({...value,initial_volume:101},temp),/volume/);
  }finally{await fs.rm(temp,{recursive:true,force:true});}
});

test('Node does not release a pending export when a duplicate prepare arrives',async()=>{
  const handlers=new Map(),sent=[];client.attach({addHandler:(n,f)=>handlers.set(n,f),outlet:(...args)=>sent.push(args)});
  const value={requestId:'first',name:'Live',visual_patch:{patcher:{boxes:[],lines:[]}}};
  await handlers.get('prepare')(JSON.stringify(value));const prepared=sent.find(x=>x[0]==='prepared');assert.ok(prepared);
  await handlers.get('prepare')(JSON.stringify({...value,requestId:'second'}));
  await handlers.get('prepare')(JSON.stringify({...value,requestId:'third'}));
  assert.equal(sent.filter(x=>x[0]==='prepared').length,1);
  assert.equal(sent.filter(x=>x[0]==='build_error').length,2);
  handlers.get('abort')('first');
  const cfg=JSON.parse(prepared[2]);await fs.rm(path.dirname(cfg.output_path),{recursive:true,force:true});
});

test('missing drawing geometry falls back without blocking native export',async()=>{
  const {context:c,sent,g}=runtime();c.node_ready();g.a.rect=[0,0,0,0];c.build();
  const request=JSON.parse(sent.find(x=>x[1]==='prepare')[2]);
  assert.equal(request.visual_patch,null);
  assert.ok(sent.some(x=>x[1]==='drawing_unavailable'));
  assert.equal(client.settings(request).visual_patch,null);
});

test('read-only RNBO status polling can complete an export without a dump-outlet notification',()=>{
  const {context:c,sent,r}=runtime();let exportState='idle';
  const original=r.getattr;r.getattr=name=>name==='exportstatus'?exportState:original(name);
  c.node_ready();c.bang();const request=JSON.parse(sent.find(x=>x[1]==='prepare')[2]);
  r.message=()=>{exportState='active';};c.prepared(request.requestId,'{}');
  exportState='success';c.pollExport();c.pollExport();
  assert.equal(sent.filter(x=>x[1]==='export_success').length,1);
});
