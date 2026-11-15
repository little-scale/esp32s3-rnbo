#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Author fixtures and documented Max export messages; never generate DSP here.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {canonicalPorts} from './stage_max_export_parity.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const args=process.argv.slice(2),out=path.resolve(args[0]||'build/private/voice-pe-led');
if(fs.existsSync(out))throw Error('Use a fresh staging directory');
const pkg=args[1]||'/Users/a1106632/Documents/Max 9/Packages/RNBO';
const require=createRequire(import.meta.url);process.env.RNBO_DIR=pkg;process.env.BABEL_DISABLE_CACHE='1';
const xam=require(path.join(pkg,'server/node_modules/@rnbo/xam'));
const row=(id,text,x,y)=>({box:{id,maxclass:'newobj',text,patching_rect:[x,y,480,22]}});
const line=(a,b,o=0,i=0)=>({patchline:{source:[a,o],destination:[b,i]}});
const msgs=['1 0 0','3 0 1 0','11 0 0 1',Array.from({length:36},(_,i)=>i%3===2?'0.5':'0').join(' '),'12 1 1 1','3.5 1 1 1','1 0','-1 0.5 2','0 0 0','0 0 1'];
const boxes0=[row('test','param test 0 @min 0 @max 9 @steps 10',30,30),row('sel','sel 0 1 2 3 4 5 6 7 8 9',30,75),
 row('load','loadbang',620,30),row('port','outport led_rgb',30,430),row('silence','sig~ 0',620,430),row('left','out~ 1',620,480),row('right','out~ 2',740,480)];
const wires=[line('test','sel'),line('load','m0'),line('silence','left'),line('silence','right')];
for(let i=0;i<msgs.length;i++){const m=row('m'+i,msgs[i],30+(i%2)*500,130+Math.floor(i/2)*55);m.box.maxclass='message';m.box.patching_rect[2]=460;boxes0.push(m);wires.push(line('sel','m'+i,i),line('m'+i,'port'));}
const graph=canonicalPorts({fileversion:1,classnamespace:'rnbo',rect:[100,100,1100,600],boxes:boxes0,lines:wires},xam);
fs.mkdirSync(out,{recursive:true});const boxes=[],lines=[];
for(const [index,rate] of [48000,16000].entries()){
  const id='v'+rate,config=path.join(out,'export-'+rate+'.json');
  fs.writeFileSync(config,JSON.stringify({output_path:path.join(out,'raw-'+rate),export_name:'rnbo_source',minimal_export:true,copy_library:true,
    copy_dependencies:false,write_binary_file:false,classname:'rnbomatic',fixedblocksize:256,fixedsamplerate:rate,
    polyphony:'disabled',exposevoiceparams:false,openexportdirectory:false,postexportcommand:'',license:true,
    presets:false,staterestore:false,probing:false,uimessages:false,language:0,debugbuild:false,midi:true},null,2));
  const x=30,y=40+index*230;
  boxes.push({...row(id,'rnbo~ @dumpoutlet 1 @title VoicePELED'+rate,x,y),box:{...row(id,'rnbo~ @dumpoutlet 1 @title VoicePELED'+rate,x,y).box,patcher:graph}},
    {...row(id+'read','read '+config,x,y+35),box:{...row(id+'read','read '+config,x,y+35).box,maxclass:'message'}},
    row(id+'dict','dict '+id,x+400,y+35),
    {...row(id+'export','export cpp-export cpp-code-export '+id,x,y+70),box:{...row(id+'export','export cpp-export cpp-code-export '+id,x,y+70).box,maxclass:'message'}},
    row(id+'delay','delay '+(1500+index*6000),x,y+105),row(id+'print','print VOICE_PE_EXPORT_'+rate,x+400,y+105));
  lines.push(line('start',id+'read'),line(id+'read',id+'dict'),line('start',id+'delay'),line(id+'delay',id+'export'),line(id+'export',id),line(id,id+'print',2));
}
boxes.push(row('start','loadbang',30,570));
fs.writeFileSync(path.join(out,'fixture.rnbopat'),JSON.stringify({patcher:graph},null,2)+'\n');
fs.writeFileSync(path.join(out,'export-two-rates.maxpat'),JSON.stringify({patcher:{fileversion:1,classnamespace:'box',rect:[50,50,1100,650],boxes,lines}},null,2)+'\n');
process.stdout.write(path.join(out,'export-two-rates.maxpat')+'\n');
