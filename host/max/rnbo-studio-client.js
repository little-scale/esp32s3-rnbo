/* SPDX-License-Identifier: MIT
 * Node for Max: completed native exports -> existing localhost Studio API.
 * Explicit package uploads use Studio's existing USB/paired Wi-Fi transport.
 * No RNBO compiler/importer APIs, shell commands or firmware installation.
 */
'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const crypto = require('node:crypto');
const MAX_BYTES = 32 * 1048576, MAX_FILE = 16 * 1048576, MAX_FILES = 1024;

function settings(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('Expected build settings');
  const {requestId, name, visual_patch} = value;
  if (typeof requestId !== 'string' || !/^[a-zA-Z0-9_-]{1,80}$/.test(requestId)) throw Error('Invalid build request identity');
  if (typeof name !== 'string' || !name.trim() || name.length > 64) throw Error('Choose a patch title up to 64 characters');
  if (visual_patch !== null && (!visual_patch?.patcher || !Array.isArray(visual_patch.patcher.boxes) || !Array.isArray(visual_patch.patcher.lines)
      || Buffer.byteLength(JSON.stringify(visual_patch)) > 1048576)) throw Error('Live drawing exceeds its limit or is invalid');
  const volume = value.initial_volume ?? 50, arena = value.arena_bytes ?? 1048576;
  if (!Number.isInteger(volume) || volume < 0 || volume > 100) throw Error('Startup volume must be 0–100');
  if (![1048576,2097152,4194304].includes(arena)) throw Error('Arena must be 1, 2 or 4 MiB');
  const exposevoiceparams=value.exposevoiceparams ?? false;
  if(typeof exposevoiceparams!=='boolean')throw Error('Voice-parameter setting must be boolean');
  return {requestId, name, visual_patch, initial_volume:volume, arena_bytes:arena, exposevoiceparams};
}

function exportConfig(directory) {
  return {output_path:path.join(directory,'export'), export_name:'rnbo_source', minimal_export:true,
    copy_library:true, copy_dependencies:false, write_binary_file:false, classname:'rnbomatic',
    fixedblocksize:256, fixedsamplerate:44100, polyphony:'linked', exposevoiceparams:false,
    openexportdirectory:false, postexportcommand:'', license:true, presets:false, staterestore:false,
    probing:false, uimessages:false, language:0, debugbuild:false, midi:true};
}

async function prepare(value, cache = os.tmpdir()) {
  const checked = settings(value);
  const directory = await fs.mkdtemp(path.join(cache,'rnbo-studio-max-'));
  await fs.chmod(directory,0o700);
  const config = exportConfig(directory);
  config.exposevoiceparams=checked.exposevoiceparams;
  await fs.writeFile(path.join(directory,'drawing.json'),JSON.stringify(checked.visual_patch,null,2),{mode:0o600});
  await fs.writeFile(path.join(directory,'export-config.json'),JSON.stringify(config,null,2),{mode:0o600});
  return {...checked, directory, config};
}

async function readExport(directory) {
  const rows=[];let total=0;
  async function visit(folder) {
    const entries=await fs.readdir(folder,{withFileTypes:true});entries.sort((a,b)=>a.name.localeCompare(b.name));
    for(const entry of entries) {
      const file=path.join(folder,entry.name), info=await fs.lstat(file);
      if(info.isSymbolicLink()) throw Error('Linked export files are not accepted');
      if(info.isDirectory()) await visit(file);
      else if(info.isFile()) {
        total+=info.size;
        if(rows.length>=MAX_FILES || info.size>MAX_FILE || total>MAX_BYTES) throw Error('Export exceeds its file/size limit');
        const raw=await fs.readFile(file);
        if(raw.length!==info.size) throw Error('Export changed while being read');
        rows.push({path:path.relative(directory,file).split(path.sep).join('/'),data_base64:raw.toString('base64')});
      } else throw Error('Special export files are not accepted');
    }
  }
  const root=await fs.lstat(directory);
  if(!root.isDirectory() || root.isSymbolicLink()) throw Error('Expected the new export directory');
  await visit(directory);
  for(const name of ['rnbo_source.h','description.json','common/RNBO_Version.h'])
    if(!rows.some(row=>row.path===name)) throw Error('Incomplete native export: missing '+name);
  return rows;
}

function request(port, endpoint, body, token, binary=false) {
  if(!Number.isInteger(port)||port<1024||port>65535) return Promise.reject(Error('Invalid local Studio port'));
  return new Promise((resolve,reject)=>{
    const raw=body===undefined?null:Buffer.from(JSON.stringify(body));
    const headers={Accept:binary?'application/octet-stream':'application/json'};
    if(raw){headers['Content-Type']='application/json';headers['Content-Length']=raw.length;headers['X-Studio-Token']=token;}
    const req=http.request({hostname:'127.0.0.1',port,path:endpoint,method:raw?'POST':'GET',headers},res=>{
      const chunks=[];let size=0;const limit=binary?589952:2*1048576;
      res.on('data',chunk=>{size+=chunk.length;if(size>limit){res.destroy(Error('Studio response exceeds its limit'));return;}chunks.push(chunk);});
      res.on('error',reject);
      res.on('end',()=>{try{
        const bytes=Buffer.concat(chunks);
        if(res.statusCode!==200&&res.statusCode!==202){let message='Studio request failed ('+res.statusCode+')';try{message=JSON.parse(bytes).error||message;}catch(_){}throw Error(message);}
        resolve(binary?bytes:JSON.parse(bytes));
      }catch(error){reject(error);}});
    });
    req.setTimeout(15000,()=>req.destroy(Error('Local Studio did not reply; start ./host/studio.sh')));
    req.on('error',reject);req.end(raw);
  });
}

async function submit(context,port=8788,call=request) {
  const export_files=await readExport(context.config.output_path);
  const status=await call(port,'/api/status');
  if(typeof status.csrf!=='string'||!status.csrf) throw Error('Studio did not provide a session token');
  const response=await call(port,'/api/build',{name:context.name,visual_patch:context.visual_patch,export_files,
    initial_volume:context.initial_volume,arena_bytes:context.arena_bytes},status.csrf);
  const job=response.job;
  if(!job||!/^[0-9a-f]{32}$/.test(job.id)) throw Error('Studio did not return a build identity');
  return {job,url:`http://127.0.0.1:${port}/?job=${job.id}`};
}

function uploadSettings(transport, target='') {
  if(!['usb','wifi'].includes(transport))throw Error('Use upload usb or upload wifi (optionally followed by a port or paired device ID)');
  if(typeof target!=='string'||target.length>256||/[\x00-\x1f\x7f]/.test(target))throw Error('Invalid upload target');
  if(transport==='wifi'&&target&&!/^[0-9a-f]{12}$/.test(target))throw Error('Wi-Fi target must be a paired 12-character device ID');
  return {transport,target};
}

async function uploadPackage(artifact,selection,port=8788,call=request,progress=()=>{},pause=ms=>new Promise(r=>setTimeout(r,ms))) {
  const {transport,target}=uploadSettings(selection.transport,selection.target);
  if(!artifact||artifact.port!==port)throw Error('Build a package with this helper and Studio port before uploading');
  const checkedJob=response=>{
    const job=response?.job;
    if(!job||job.id!==artifact.id||job.result?.kind!=='package'||job.result.package_sha256!==artifact.sha256)
      throw Error('The completed build is no longer available or its package identity changed. Build again.');
    return job;
  };
  const before=checkedJob(await call(port,'/api/job?id='+artifact.id));
  if(!['ready','done'].includes(before.state))throw Error('Wait for the completed package before uploading');
  let chosen=target;
  if(transport==='usb') {
    const rows=(await call(port,'/api/devices')).devices;
    if(!Array.isArray(rows))throw Error('Studio did not return USB devices');
    if(!chosen&&rows.length===1)chosen=rows[0].port;
    if(!chosen||rows.filter(row=>row.port===chosen).length!==1)throw Error('Choose one USB port: upload usb <port>');
  } else {
    const rows=(await call(port,'/api/wifi')).paired;
    if(!Array.isArray(rows))throw Error('Studio did not return paired Wi-Fi players');
    if(!chosen&&rows.length===1)chosen=rows[0].id;
    if(!chosen||rows.filter(row=>row.id===chosen).length!==1)throw Error('Pair a board in Studio, then use upload wifi <device_id> when several are saved');
  }
  progress('target',transport,chosen);
  const status=await call(port,'/api/status');
  if(typeof status.csrf!=='string'||!status.csrf)throw Error('Studio did not provide a session token');
  const body={id:artifact.id,transport,...(transport==='usb'?{port:chosen}:{device_id:chosen})};
  // One explicit request, never automatically retried after a timeout or lost reply.
  let job=checkedJob(await call(port,'/api/upload',body,status.csrf));
  const end=Date.now()+5*60*1000;let previous='';
  while(true) {
    if(job.stage!==previous){progress('progress',String(job.stage||job.state));previous=job.stage;}
    if(job.error||job.state==='failed')throw Error(job.error||'Package upload failed');
    if(job.state==='done')return {job,transport,target:chosen};
    if(job.state!=='uploading')throw Error('Upload did not finish; inspect the job in Studio before retrying');
    if(Date.now()>end)throw Error('Upload is still running; inspect Studio before retrying');
    await pause(500);
    job=checkedJob(await call(port,'/api/job?id='+artifact.id));
  }
}

function attach(max, dependencies={}) {
  const call=dependencies.request||request;
  let context=null,port=8788,building=false,uploading=false,lastBuild=null;
  const send=(...args)=>max.outlet(...args);
  const fail=(id,error)=>send('build_error',id||'',String(error.message||error));
  max.addHandler('studio_port', value=>{if(context||building||uploading) return fail('',Error('Wait for the current export/build/upload'));if(!Number.isInteger(value)||value<1024||value>65535)return fail('',Error('Invalid Studio port'));if(port!==value)lastBuild=null;port=value;});
  max.addHandler('prepare',async text=>{
    let value;
    try {value=JSON.parse(text);}catch(error){fail('',error);return;}
    if(context||building||uploading){fail(value?.requestId,Error('An export/build/upload is already in progress'));return;}
    building=true;lastBuild=null;
    try {
      context=await prepare(value);
      send('prepared',context.requestId,JSON.stringify(context.config));
    } catch(error){building=false;fail(value?.requestId,error);}
  });
  max.addHandler('abort',id=>{if(context?.requestId===id){context=null;building=false;}});
  max.addHandler('export_success',async id=>{
    if(!context||context.requestId!==id)return;
    const current=context;context=null;
    try {
      const started=await submit(current,port,call);
      send('submitted',id,started.job.id,started.url);
      let job=started.job,previous='';
      const end=Date.now()+25*60*1000;
      while(true){
        if(job.stage!==previous){send('build_progress',id,String(job.stage||job.state));previous=job.stage;}
        if(job.state==='ready')break;
        if(job.state==='failed'||job.error)throw Error(job.error||'Studio compilation failed');
        if(Date.now()>end)throw Error('Build is still running. Continue in Studio: '+started.url);
        await new Promise(resolve=>setTimeout(resolve,1000));
        job=(await call(port,'/api/job?id='+job.id)).job;
        if(!job||job.id!==started.job.id)throw Error('Studio build identity changed');
      }
      const raw=await call(port,'/api/artifact?id='+job.id,undefined,undefined,true);
      if(crypto.createHash('sha256').update(raw).digest('hex')!==job.result.package_sha256)throw Error('Package identity differs from the completed build');
      const file=path.join(current.directory,'patch.rnbopkg');await fs.writeFile(file,raw,{mode:0o600});
      lastBuild={id:job.id,sha256:job.result.package_sha256,port};
      building=false;send('build_ready',id,job.id,started.url,file);
    }catch(error){fail(id,error);}
    finally{building=false;}
  });
  max.addHandler('upload',async(id,transport,target='')=>{
    if(context||building||uploading){send('upload_error',id,'Wait for the current export/build/upload');return;}
    uploading=true;
    try {
      const result=await uploadPackage(lastBuild,uploadSettings(transport,target),port,call,
        (kind,...args)=>send(kind==='target'?'upload_target':'upload_progress',id,...args),dependencies.pause);
      send('upload_done',id,result.job.id,result.transport,result.target);
    }catch(error){send('upload_error',id,String(error.message||error));}
    finally{uploading=false;}
  });
  send('node_ready');
}
module.exports={settings,exportConfig,prepare,readExport,request,submit,uploadSettings,uploadPackage,attach};
try {attach(require('max-api'));} catch(error) {if(error.code!=='MODULE_NOT_FOUND')throw error;}
