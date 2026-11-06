/* SPDX-License-Identifier: MIT
 * Run in Max's v8 object inside rnbo.studio.maxpat, never inside RNBO DSP.
 * Drawing capture only. All executable DSP is exported by rnbo~ itself.
 */
autowatch = 0;
inlets = 2;
outlets = 3;
var nodeReady = false, current = null, configDict = null, timeoutTask = null, exportPoll = null;
var lastStudioURL = '', initialVolume = 50, arenaBytes = 1048576;
var wanted = typeof jsarguments !== 'undefined' && jsarguments[1] && String(jsarguments[1]) !== '#1' ? String(jsarguments[1]) : '';

function locateTarget(parent, name) {
    for (var p = parent; p; p = p.parentpatcher) {
        var candidates = [];
        for (var o = p.firstobject; o; o = o.nextobject) {
            if (o.maxclass === 'rnbo~' && (!name || o.varname === name)) candidates.push(o);
        }
        if (candidates.length > 1) throw Error('Multiple rnbo~ objects: supply the intended scripting name as the helper argument');
        if (candidates.length === 1) return candidates[0];
    }
    throw Error(name ? 'No rnbo~ with scripting name '+name : 'No rnbo~ found in a containing Max patch');
}

function captureDrawing(p) {
    if (!p) throw Error('The RNBO patch is not available in memory');
    var objects = [], boxes = [], lines = [];
    for (var o = p.firstobject; o; o = o.nextobject) {
        if (objects.length >= 2048) throw Error('Live drawing exceeds 2048 boxes');
        objects.push(o);
        var rect = o.rect;
        if (!rect || rect.length !== 4 || !rect.every(function(v){return typeof v==='number'&&isFinite(v);})
                || rect[2] <= rect[0] || rect[3] <= rect[1]) throw Error('Invalid live object rectangle: '+String(o.boxtext||o.maxclass)+' '+JSON.stringify(rect));
        var text = o.boxtext || o.maxclass;
        boxes.push({box:{id:'live-'+objects.length,maxclass:o.maxclass==='comment'||o.maxclass==='panel'?o.maxclass:'newobj',
            text:String(text),patching_rect:[rect[0],rect[1],rect[2]-rect[0],rect[3]-rect[1]],numinlets:0,numoutlets:0}});
    }
    for (var index=0; index<objects.length; ++index) {
        var cords=objects[index].patchcords;
        if (!cords || !Array.isArray(cords.outputs)) throw Error('Max did not expose the live patch connections');
        for (var ci=0; ci<cords.outputs.length; ++ci) {
            var c=cords.outputs[ci], from=objects.indexOf(c.srcobject), to=objects.indexOf(c.dstobject);
            if (from!==index || to<0 || !Number.isInteger(c.srcoutlet) || !Number.isInteger(c.dstinlet)
                    || c.srcoutlet<0 || c.srcoutlet>=32 || c.dstinlet<0 || c.dstinlet>=32) throw Error('Unsupported live patch connection');
            if (lines.length>=8192) throw Error('Live drawing exceeds 8192 cords');
            boxes[from].box.numoutlets=Math.max(boxes[from].box.numoutlets,c.srcoutlet+1);
            boxes[to].box.numinlets=Math.max(boxes[to].box.numinlets,c.dstinlet+1);
            lines.push({patchline:{source:[boxes[from].box.id,c.srcoutlet],destination:[boxes[to].box.id,c.dstinlet]}});
        }
    }
    return {patcher:{classnamespace:'rnbo',boxes:boxes,lines:lines}};
}

function status() {
    var args=Array.prototype.slice.call(arguments),label=String(args[0]||'');
    if(label==='ready')label='Package ready. Open Studio to load it.';
    else if(label==='job')label='Build submitted. Open Studio for progress.';
    else if(label==='available')label='Ready to build the live RNBO patch.';
    else label=args.join(' ').slice(0,180);
    try {this.patcher.getnamed('status_label').message('set',label);} catch(_) {}
    outlet.apply(null,[1].concat(args));
}
function stopTimer() { if(timeoutTask){timeoutTask.cancel();timeoutTask=null;} if(exportPoll){exportPoll.cancel();exportPoll=null;} }
function fail(message) {
    stopTimer();
    if(current)outlet(0,'abort',current.id);
    current=null;configDict=null;status('error',String(message));
}
function bang() {
    if(current){status('error','A build is already in progress');return;}
    if(!nodeReady){status('error','Node for Max is starting; try Build again shortly');return;}
    try {
        var target=locateTarget(this.patcher.parentpatcher || this.patcher,wanted);
        if(Number(target.getattr('dumpoutlet'))!==1) throw Error('Enable @dumpoutlet 1 on the rnbo~ object');
        if(String(target.getattr('exportstatus'))==='active')throw Error('An RNBO export is already active');
        var drawing=null;
        try {drawing=captureDrawing(target.subpatcher());}
        catch(error){status('drawing_unavailable',String(error.message||error));}
        var id='build_'+Date.now()+'_'+Math.floor(Math.random()*1000000000);
        var title=String(target.getattr('title')||target.varname||'RNBO Patch').slice(0,64);
        current={id:id,target:target,phase:'preparing',drawing:JSON.stringify(drawing),sawActive:false};
        timeoutTask=new Task(function(){fail('Export timed out. Check the dump-outlet connection and Max Console.');},this);
        timeoutTask.schedule(120000);
        outlet(0,'prepare',JSON.stringify({requestId:id,name:title,visual_patch:drawing,initial_volume:initialVolume,arena_bytes:arenaBytes,exposevoiceparams:!!Number(target.getattr('exposevoiceparams'))}));
        status('preparing',title);
    }catch(error){fail(error.message||error);}
}
function build() {bang.call(this);}
function node_ready() { nodeReady=true;status('available','Max → native export → Studio'); }
function prepared(id,json) {
    if(!current||current.id!==id||current.phase!=='preparing')return;
    try {
        if(!current.target.valid)throw Error('RNBO object was removed');
        if(String(current.target.getattr('exportstatus'))==='active')throw Error('Another RNBO export started');
        configDict=new Dict('rnbo_studio_'+id);
        configDict.parse(json);
        current.phase='exporting';
        current.target.message('export','cpp-export','cpp-code-export',configDict.name);
        status('exporting');
        pollExport();
    }catch(error){fail(error.message||error);}
}
function pollExport() {
    if(!current||current.phase!=='exporting')return;
    try {exportstatus(String(current.target.getattr('exportstatus')));}
    catch(error){fail(error.message||error);return;}
    if(current&&current.phase==='exporting') {
        if(!exportPoll)exportPoll=new Task(pollExport,this);
        exportPoll.schedule(25);
    }
}
function exportstatus(value) {
    if(!current||current.phase!=='exporting')return;
    if(value==='active'){current.sawActive=true;return;}
    if(value==='error'){fail('RNBO export failed. Check the Max Console; no Studio build was submitted.');return;}
    if(value!=='success'||!current.sawActive)return;
    try {
        if(current.drawing!=='null' && JSON.stringify(captureDrawing(current.target.subpatcher()))!==current.drawing)
            throw Error('The patch drawing changed during export. Click Build again.');
        stopTimer();current.phase='building';
        outlet(0,'export_success',current.id);status('building');
    }catch(error){fail(error.message||error);}
}
function submitted(id,job,url) {
    if(!current||current.id!==id)return;
    lastStudioURL=String(url);status('job',String(job),lastStudioURL);
}
function build_progress(id,message) { if(current&&current.id===id)status('progress',String(message)); }
function build_ready(id,job,url,file) {
    if(!current||current.id!==id)return;
    lastStudioURL=String(url);stopTimer();current=null;configDict=null;
    status('ready',String(job),lastStudioURL,String(file));
}
function build_error(id,message) { if(current&&current.id===id)fail(message);else status('error',String(message)); }
function open() { if(lastStudioURL)outlet(2,lastStudioURL);else status('error','Click Build first; the Studio link appears after submission'); }
function startup_volume(value) {
    if(current)return status('error','Wait for the current build');
    if(!Number.isInteger(value)||value<0||value>100)return status('error','Startup volume must be 0–100');
    initialVolume=value;
}
function arena(value) {
    if(current)return status('error','Wait for the current build');
    if([1,2,4].indexOf(value)<0)return status('error','Arena must be 1, 2 or 4 MiB');
    arenaBytes=value*1048576;
}
function studio_port(value) { if(current)return status('error','Wait for the current build');outlet(0,'studio_port',value); }
function notifydeleted() {stopTimer();if(current)outlet(0,'abort',current.id);}
