// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
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

test('Max upload messages require a completed build and hold the lock until device completion',()=>{
  const {context:c,sent}=runtime();c.node_ready();c.upload('usb');
  assert.equal(sent.filter(x=>x[1]==='upload').length,0);
  c.build();const req=JSON.parse(sent.find(x=>x[1]==='prepare')[2]);
  c.upload('usb');assert.equal(sent.filter(x=>x[1]==='upload').length,0);
  c.build_ready(req.requestId,'a'.repeat(32),'http://127.0.0.1:8788/?job='+'a'.repeat(32),'/tmp/pkg');
  c.upload('bluetooth');c.upload('wifi','not-an-id');c.upload('usb','one','two');
  assert.equal(sent.filter(x=>x[1]==='upload').length,0);
  c.upload('usb','/dev/cu.test');const command=sent.filter(x=>x[1]==='upload').at(-1);
  assert.deepEqual(command.slice(3),['usb','/dev/cu.test']);
  c.build();c.upload('wifi');assert.equal(sent.filter(x=>x[1]==='upload').length,1);
  c.upload_done('wrong','a'.repeat(32),'usb','/dev/cu.test');assert.ok(c.current);
  c.upload_done(command[2],'a'.repeat(32),'usb','/dev/cu.test');assert.equal(c.current,null);
  c.build();c.build_error(c.current.id,'new export failed');c.upload('usb');
  assert.equal(sent.filter(x=>x[1]==='upload').length,1,'failed new build cannot upload its predecessor');
});

test('combined build/upload runs only after successful export and forwards the explicit target',()=>{
  const {context:c,sent}=runtime();c.node_ready();c.build_upload('wifi','001122aabbcc');
  const req=JSON.parse(sent.find(x=>x[1]==='prepare')[2]);
  assert.equal(sent.filter(x=>x[1]==='upload').length,0);
  c.prepared(req.requestId,'{}');c.exportstatus('active');c.exportstatus('success');
  c.build_ready(req.requestId,'a'.repeat(32),'http://127.0.0.1:8788/?job='+'a'.repeat(32),'/tmp/pkg');
  const command=sent.filter(x=>x[1]==='upload').at(-1);assert.deepEqual(command.slice(3),['wifi','001122aabbcc']);
  c.upload_error(command[2],'CPU admission failed');assert.equal(c.current,null);assert.equal(sent.at(-1)[1],'upload_failed');
  c.build_upload('usb');c.build_error(c.current.id,'compiler failed');
  assert.equal(sent.filter(x=>x[1]==='upload').length,1);
});

const artifact={id:'a'.repeat(32),sha256:'b'.repeat(64),port:8788};
const job=(state='ready',extra={})=>({id:artifact.id,state,stage:state,result:{kind:'package',package_sha256:artifact.sha256},...extra});
function uploadApi({usb=[{port:'/dev/cu.test'}],wifi=[{id:'001122aabbcc'}],initial=job(),finish=job('done'),postError=null}={}) {
  const calls=[];let posted=false;
  const call=async(port,url,body,token)=>{
    calls.push({port,url,body,token});
    if(url.startsWith('/api/job?'))return {job:posted?finish:initial};
    if(url==='/api/devices')return {devices:usb};
    if(url==='/api/wifi')return {paired:wifi};
    if(url==='/api/status')return {csrf:'private-session'};
    if(url==='/api/upload'){posted=true;if(postError)throw postError;return {job:job('uploading')};}
    throw Error('Unexpected endpoint '+url);
  };
  return {call,calls};
}

test('USB and Wi-Fi uploads use the exact ready package, selected transport and existing session API',async()=>{
  for(const transport of ['usb','wifi']) {
    const {call,calls}=uploadApi(),events=[];
    const result=await client.uploadPackage(artifact,{transport,target:''},8788,call,(...v)=>events.push(v),async()=>{});
    const posts=calls.filter(x=>x.body);
    assert.equal(posts.length,1);assert.equal(posts[0].token,'private-session');
    assert.deepEqual(posts[0].body,{id:artifact.id,transport,...(transport==='usb'?{port:'/dev/cu.test'}:{device_id:'001122aabbcc'})});
    assert.equal(result.job.state,'done');assert.equal(events[0][0],'target');
    assert.ok(calls.every(x=>!x.url.includes('install')&&!x.url.includes('setup')));
  }
});

test('missing, changed, busy, ambiguous or unpaired targets never start an upload',async()=>{
  const cases=[
    {initial:job('ready',{id:'c'.repeat(32)})},
    {initial:job('ready',{result:{kind:'package',package_sha256:'c'.repeat(64)}})},
    {initial:job('building')},{usb:[]},{usb:[{port:'one'},{port:'two'}]},
    {wifi:[],transport:'wifi'},{wifi:[{id:'001122aabbcc'},{id:'112233aabbcc'}],transport:'wifi'},
    {transport:'wifi',target:'112233aabbcc'}
  ];
  for(const value of cases) {
    const {call,calls}=uploadApi(value);
    await assert.rejects(client.uploadPackage(artifact,{transport:value.transport||'usb',target:value.target||''},8788,call));
    assert.equal(calls.filter(x=>x.url==='/api/upload').length,0);
  }
  const {call,calls}=uploadApi();
  await assert.rejects(client.uploadPackage(null,{transport:'usb'},8788,call),/Build/);
  await assert.rejects(client.uploadPackage(artifact,{transport:'usb'},9999,call),/Build/);
  assert.equal(calls.length,0);
});

test('explicit USB/Wi-Fi targets select one of several; transport failures never trigger a fallback or retry',async()=>{
  for(const value of [
    {transport:'usb',target:'two',usb:[{port:'one'},{port:'two'}]},
    {transport:'wifi',target:'112233aabbcc',wifi:[{id:'001122aabbcc'},{id:'112233aabbcc'}]}
  ]) {
    const {call}=uploadApi(value);
    assert.equal((await client.uploadPackage(artifact,value,8788,call,()=>{},async()=>{})).target,value.target);
  }
  for(const value of [
    {finish:job('ready',{error:'Candidate exceeds block budget'})},
    {finish:job('done',{result:{kind:'package',package_sha256:'c'.repeat(64)}})},
    {postError:Error('reply lost')}
  ]) {
    const {call,calls}=uploadApi(value);
    await assert.rejects(client.uploadPackage(artifact,{transport:'wifi'},8788,call,()=>{},async()=>{}));
    assert.equal(calls.filter(x=>x.url==='/api/upload').length,1);
    assert.equal(calls.filter(x=>x.url==='/api/devices').length,0,'Wi-Fi failure cannot fall back to USB');
  }
});

test('Node build-to-upload retains the verified package, rejects overlap, and clears stale builds',async()=>{
  const handlers=new Map(),sent=[],raw=Buffer.from('test package'),sha=crypto.createHash('sha256').update(raw).digest('hex');
  let releaseUpload;const pending=new Promise(resolve=>{releaseUpload=resolve;});
  const result={kind:'package',package_sha256:sha},id='d'.repeat(32);let uploaded=false;
  const call=async(port,url,body)=>{
    if(url==='/api/status')return {csrf:'token'};
    if(url==='/api/build')return {job:{id,state:'ready',result}};
    if(url.startsWith('/api/artifact'))return raw;
    if(url.startsWith('/api/job'))return {job:{id,state:uploaded?'done':'ready',result}};
    if(url==='/api/devices')return {devices:[{port:'/dev/cu.test'}]};
    if(url==='/api/upload'){await pending;uploaded=true;return {job:{id,state:'done',result}};}
    throw Error(url);
  };
  client.attach({addHandler:(n,f)=>handlers.set(n,f),outlet:(...args)=>sent.push(args)},{request:call});
  await handlers.get('prepare')(JSON.stringify({requestId:'native',name:'Live',visual_patch:null}));
  const cfg=JSON.parse(sent.find(x=>x[0]==='prepared')[2]);
  try {
    await fs.mkdir(path.join(cfg.output_path,'common'),{recursive:true});
    for(const f of ['rnbo_source.h','description.json','common/RNBO_Version.h'])await fs.writeFile(path.join(cfg.output_path,f),'native');
    await handlers.get('export_success')('native');assert.equal(sent.at(-1)[0],'build_ready');
    const uploading=handlers.get('upload')('operation','usb');
    await handlers.get('upload')('overlap','usb');assert.equal(sent.at(-1)[0],'upload_error');
    releaseUpload();await uploading;assert.equal(sent.at(-1)[0],'upload_done');
    await handlers.get('prepare')(JSON.stringify({requestId:'new',name:'Live',visual_patch:null}));
    const newCfg=JSON.parse(sent.filter(x=>x[0]==='prepared').at(-1)[2]);
    handlers.get('abort')('new');await fs.rm(path.dirname(newCfg.output_path),{recursive:true,force:true});
    await handlers.get('upload')('stale','usb');assert.equal(sent.at(-1)[0],'upload_error');assert.match(sent.at(-1)[2],/Build/);
  }finally{await fs.rm(path.dirname(cfg.output_path),{recursive:true,force:true});}
});
