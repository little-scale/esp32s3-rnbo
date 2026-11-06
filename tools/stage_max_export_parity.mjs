#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Stage a native Max C++ export comparison using documented rnbo~ export messages.
// RNBO metadata describes UI ports only. Native Gen graphs remain graphs: this
// tool never imports or calls our visual Gen lowerer and never inserts GenExpr.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const encoded=d=>JSON.stringify(d,null,2)+'\n';
export const subjects=[
 ['rnbo-mixing-shaping','interp-spline6'],
 ['rnbo-mixing-shaping','interp-signal-spline6-inlets'],
 ['rnbo-envelopes-clocks','curve-gentle'],
 ['rnbo-envelopes-clocks','curve-compound'],
 ['rnbo-envelopes-clocks','line-ramp'],
 ['rnbo-envelopes-clocks','edge-out0'],
 ['gen-visual-core','one-sample-history'],
 ['gen-visual-flow','visual-mod']
];
export function canonicalPorts(raw,xam){
 const p=structuredClone(raw),rename=new Map(p.boxes.map(({box},i)=>[box.id,`obj-${i+1}`]));
 for(const {box:b}of p.boxes){
  const old=b.id;let info;
  if(b.text==='gen~'&&b.genpatcher){
   // A two-channel dummy supplies port descriptions, never executable patch input.
   info=xam.getObjectDescription(xam.createObject('gen~',{expr:'out1=in1; out2=in2;'}));
   b.rnbo_classname='gen~';b.rnbo_extra_attributes={exposeparams:0};
   const g=b.genpatcher.patcher;const gm=new Map(g.boxes.map(({box},i)=>[box.id,`obj-${i+1}`]));
   for(const {box:v}of g.boxes){v.id=gm.get(v.id);v.outlettype=Array(v.numoutlets).fill('');}
   for(const {patchline:l}of g.lines){l.source[0]=gm.get(l.source[0]);l.destination[0]=gm.get(l.destination[0]);}
  }else{
   let text=b.text;
   if(b.maxclass==='comment'||b.maxclass==='panel')continue;
   if(b.maxclass==='message')text=b.text?`message @text ${b.text}`:'message';
   const spec=xam.parseBoxText(text);if(!spec)throw Error(`No native RNBO object metadata for ${text}`);
   const obj=xam.createObject(spec.xamclass,spec.attributes);info=xam.getObjectDescription(obj);b.rnbo_classname=info.classname;
  }
  b.id=rename.get(old);b.rnbo_uniqueid=`${b.rnbo_classname}_${b.id}`;b.rnbo_serial??=p.boxes.findIndex(r=>r.box===b);
  b.rnboinfo=info;b.numinlets=info.inputs.length;b.numoutlets=info.outputs.length;b.outlettype=info.outputs.map(v=>v.type==='signal'?'signal':'');
 }
 for(const {patchline:l}of p.lines){l.source[0]=rename.get(l.source[0]);l.destination[0]=rename.get(l.destination[0]);}
 p.appversion={major:9,minor:1,revision:4,architecture:'arm64',modernui:1};return p;
}
function obj(id,maxclass,text,x,y,width=650){return{box:{id,maxclass,text,patching_rect:[x,y,width,24]}};}
function line(s,t,o=0,i=0){return{patchline:{source:[s,o],destination:[t,i]}};}
export function stage(out,pkg){
 out=path.resolve(out);pkg=fs.realpathSync(pkg);if(fs.existsSync(out))throw Error('Comparison output must be a fresh directory');
 const pi=JSON.parse(fs.readFileSync(path.join(pkg,'package-info.json'),'utf8'));if(pi.version!=='1.4.4')throw Error('First compare both routes on RNBO1.4.4; stage a separate version experiment for updates');
 process.env.RNBO_DIR=pkg;process.env.BABEL_DISABLE_CACHE='1';const require=createRequire(import.meta.url);const xam=require(path.join(pkg,'server/node_modules/@rnbo/xam'));
 const maxVersion=execFileSync('/usr/bin/python3',['-c',"import plistlib; print(plistlib.load(open('/Applications/Max.app/Contents/Info.plist','rb'))['CFBundleShortVersionString'])"],{encoding:'utf8'}).trim();
 fs.mkdirSync(path.join(out,'configs'),{recursive:true});const boxes=[obj('heading','comment','Native Max export comparison: 8 original graphs. No DAC connected. Exports run once after load.',30,20,950)],lines=[],cases=[];
 for(const [index,[family,id]]of subjects.entries()){
  const folder=path.join(root,'tests/fixtures/smoke',family),catalog=JSON.parse(fs.readFileSync(path.join(folder,'catalog.json'),'utf8'));const row=catalog.cases.find(r=>r.id===id);if(!row)throw Error('Missing original subject '+id);
  const source=path.join(folder,row.patch),bytes=fs.readFileSync(source);if(sha(bytes)!==row.patch_sha256)throw Error('Original graph changed: '+id);
  const original=JSON.parse(bytes).patcher;const graph=canonicalPorts(original,xam);const name=`parity_${index}`,configPath=path.join(out,'configs',id+'.json'),exportPath=path.join(out,'max-raw',id);
  const config={output_path:exportPath,export_name:'rnbo_source',minimal_export:true,copy_library:true,copy_dependencies:false,write_binary_file:false,classname:'rnbos3patch',fixedblocksize:256,fixedsamplerate:44100,polyphony:'disabled',exposevoiceparams:false,openexportdirectory:false,postexportcommand:'',license:true,presets:false,staterestore:false,probing:false,uimessages:false,language:0,debugbuild:false,midi:true};
  fs.writeFileSync(configPath,encoded(config));const y=70+index*140;const rnbo=obj(name,'newobj',`rnbo~ @title parity-${id} @dumpoutlet 1`,30,y,350);Object.assign(rnbo.box,{patcher:graph,autosave:1,rnboversion:pi.version,numinlets:2,numoutlets:3,outlettype:['signal','signal','list']});
  boxes.push(rnbo,obj(name+'-read','message','read '+configPath,400,y),obj(name+'-cfg','newobj','dict '+name+'_cfg',400,y+30),obj(name+'-export','message',`export cpp-export cpp-code-export ${name}_cfg`,30,y+35),obj(name+'-delay','newobj','delay '+(1500+index*5000),30,y+70,150),obj(name+'-print','newobj','print PARITY_'+id,400,y+70));
  lines.push(line('start',name+'-read'),line(name+'-read',name+'-cfg'),line('start',name+'-delay'),line(name+'-delay',name+'-export'),line(name+'-export',name),line(name,name+'-print',2));
  const rawGen=original.boxes.find(({box})=>box.genpatcher)?.box.genpatcher;
  cases.push({id,family,model:row.model,source:path.relative(root,source),source_sha256:sha(bytes),catalog_sha256:sha(fs.readFileSync(path.join(folder,'catalog.json'))),reference:path.relative(root,path.join(folder,'reference.py')),reference_sha256:sha(fs.readFileSync(path.join(folder,'reference.py'))),config:configPath,max_export:exportPath,native_gen:!!rawGen,max_staged_graph_sha256:sha(encoded(graph)),maximum_absolute_error:row.maximum_absolute_error??0,original_visual_graph_sha256:rawGen?sha(encoded(rawGen)):null});
 }
 boxes.push(obj('start','newobj','loadbang',30,1250,100));const wrapper={patcher:{fileversion:1,appversion:{major:9,minor:1,revision:4,architecture:'arm64',modernui:1},classnamespace:'box',rect:[80,70,1100,1300],boxes,lines}};const wrapperPath=path.join(out,'max-export-comparison.maxpat');fs.writeFileSync(wrapperPath,encoded(wrapper));
 const manifest={format:'rnbo-max-export-parity-stage-v1',rnbo_version:pi.version,max_version:maxVersion,settings:{sample_rate:44100,block_frames:256,class_name:'rnbos3patch',arithmetic:'same float32-strict module wrapper on both routes',automatic_warmup_blocks:0,manual_warmup_blocks:4,timed_blocks:16},stage_tool_sha256:sha(fs.readFileSync(fileURLToPath(import.meta.url))),max_wrapper:wrapperPath,max_wrapper_sha256:sha(fs.readFileSync(wrapperPath)),scope:'Canonical Max UI port metadata and bijective object-ID renaming only. Original texts/arguments, line order and Gen graph structure retained. Native Gen is exported by Max; our visual Gen lowerer is not used. Config uses the documented rnbo~ export cpp-export cpp-code-export dictionary message. No runtime output or hardware parity is claimed by staging.',cases};fs.writeFileSync(path.join(out,'stage.json'),encoded(manifest));return manifest;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const a=process.argv.slice(2);const pos=a.indexOf('--out');const packagePos=a.indexOf('--rnbo-dir');
 if(pos<0||!a[pos+1])throw Error('Usage: node tools/stage_max_export_parity.mjs --out NEW_DIR [--rnbo-dir RNBO_PACKAGE]');
 const m=stage(a[pos+1],packagePos>=0?a[packagePos+1]:'/Users/a1106632/Documents/Max 9/Packages/RNBO');console.log(JSON.stringify({cases:m.cases.length,max_wrapper:m.max_wrapper,max_version:m.max_version,rnbo_version:m.rnbo_version}));
}
