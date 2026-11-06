#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Closed qualification exporter. It cannot produce a player package or modify
// the normal exporter's fixed256 admission. Licensed output stays under build/.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {describeFlatPatcher} from '../archive/importer/patcher.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const require=createRequire(import.meta.url);
const args=process.argv.slice(2);
if(args.length!==2||args[0]!=='--out')throw Error('Usage: node tools/export_gen_partition_probe.mjs --out NEW_BUILD_DIRECTORY');
const out=path.resolve(args[1]);
if(!out.startsWith(root+'/build/')||fs.existsSync(out))throw Error('Use a fresh private build/ output directory');
// Canonical parent resolution prevents an alias from targeting the package.
let ancestor=path.dirname(out);while(!fs.existsSync(ancestor))ancestor=path.dirname(ancestor);
if(!fs.realpathSync(ancestor).startsWith(root+'/build'))throw Error('Output parent must remain in this repository build tree');
const catalogPath=path.join(root,'tests/fixtures/gen/partitions/catalog.json');
const catalog=JSON.parse(fs.readFileSync(catalogPath));
if(catalog.format!=='rnbo-gen-direct-partition-catalog-v1'||catalog.programs.length!==3||catalog.producer_fixedblocksize!==0||catalog.module_abi!==false)throw Error('Unexpected closed direct-probe catalog');
const pkg=fs.realpathSync(process.env.RNBO_DIR??path.join(os.homedir(),'Documents/Max 9/Packages/RNBO'));
if(JSON.parse(fs.readFileSync(path.join(pkg,'package-info.json'))).version!=='1.4.4')throw Error('The direct probe requires licensed RNBO1.4.4');
process.env.RNBO_DIR=pkg;process.env.BABEL_DISABLE_CACHE='1';
const xam=require(path.join(pkg,'server/node_modules/@rnbo/xam'));
const runner=require(path.join(pkg,'server/node_modules/@rnbo/xam-runner'));
fs.mkdirSync(out,{recursive:true});
for(const entry of catalog.programs){
 if(![1,2,3].includes(entry.model)||entry.class_name!=='genpartition'+entry.model||!entry.patch.startsWith('tests/fixtures/gen/')||entry.patch.includes('..'))throw Error('Unexpected direct-probe source');
 const raw=fs.readFileSync(path.join(root,entry.patch));if(hash(raw)!==entry.patch_sha256)throw Error('Source graph hash differs');
 const graph=describeFlatPatcher(JSON.parse(raw).patcher,xam);
 const invocation=runner.createInvocation(xam,graph,{language:0,classname:entry.class_name,fixedblocksize:0,fixedsamplerate:44100,polyphony:0,midi:false,presets:false,staterestore:false,probing:false,license:true});
 const result=await runner.codegenInvocationStorage.run({reportCodegenProgress:()=>{}},()=>invocation.call());
 const d=result.desc;
 if(typeof result.code!=='string'||!result.code||d.numInputChannels!==2||d.numOutputChannels!==2||d.numParameters!==1||d.parameters[0].name!=='reset'||d.parameters[0].paramId!=='s3_reset'||d.externalDataRefs.length!==0)throw Error('Direct-probe port/parameter/resource contract differs');
 const directory=path.join(out,entry.id);fs.mkdirSync(directory);
 fs.writeFileSync(path.join(directory,'rnbo_source.h'),result.code);
 fs.writeFileSync(path.join(directory,'description.json'),JSON.stringify(d,null,2)+'\n');
 fs.writeFileSync(path.join(directory,'source.rnbopat'),raw);
 fs.cpSync(path.join(pkg,'source/rnbo/common'),path.join(directory,'common'),{recursive:true,filter:p=>fs.statSync(p).isDirectory()||/\.(h|hpp)$/.test(p)});
 fs.copyFileSync(path.join(pkg,'source/rnbo/LICENSE'),path.join(directory,'RNBO-runtime-LICENSE'));
 const meta={format:'rnbo-gen-direct-partition-export-v1',execution_route:'direct-variable-producer',module_abi:false,rnbo_version:'1.4.4',class_name:entry.class_name,block_frames:0,sample_rate:44100,source_sha256:hash(raw),generated_sha256:hash(Buffer.from(result.code)),catalog_sha256:hash(fs.readFileSync(catalogPath)),adapter_sha256:hash(fs.readFileSync(fileURLToPath(import.meta.url))),patcher_adapter_sha256:hash(fs.readFileSync(path.join(root,'archive/importer/patcher.mjs'))),gen_visual_adapter_sha256:hash(fs.readFileSync(path.join(root,'archive/importer/gen_visual.mjs')))};
 fs.writeFileSync(path.join(directory,'generator.json'),JSON.stringify(meta,null,2)+'\n');
 process.stdout.write(entry.id+' exported direct variable-frame producer\n');
}
