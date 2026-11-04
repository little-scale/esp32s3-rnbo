// SPDX-License-Identifier: MIT
// Run the real frontend against a tiny DOM and mocked JSON API. No server,
// serial library, hardware, external package or network connection is used.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const html = readFileSync(new URL('./web/index.html', import.meta.url), 'utf8');
const source = readFileSync(new URL('./web/app.js', import.meta.url), 'utf8');
const settle = async () => { await new Promise(resolve => setImmediate(resolve)); };
const example = {
  name: 'test.rnbopat',
  patch: {patcher: {
    boxes: [
      {box: {id: 'tone', text: 'cycle~ 440', patching_rect: [0, 0, 100, 25]}},
      {box: {id: 'output', text: 'out~ 1', patching_rect: [0, 100, 70, 25]}},
    ],
    lines: [{patchline: {source: ['tone', 0], destination: ['output', 0]}}],
  }},
};

function mockDocument() {
  const ids = new Map();
  class Element {
    constructor(tag = 'div', id = '') {
      this.tagName = tag.toUpperCase();
      this.attributes = new Map();
      this.id = id;
      this.value = ''; this.textContent = ''; this.disabled = false;
      this.checked = false; this.dataset = {}; this.children = []; this.events = new Map();
      this.scrollHeight = 0; this.clientHeight = 0; this.scrollTop = 0;
      const classes = new Set();
      this.classList = {
        add: (...names) => names.forEach(name => classes.add(name)),
        remove: (...names) => names.forEach(name => classes.delete(name)),
        toggle: (name, on) => on ? classes.add(name) : classes.delete(name),
      };
    }
    set id(value) { this._id = value; if (value) ids.set(value, this); }
    get id() { return this._id; }
    set hidden(value) { this.toggleAttribute('hidden', value); }
    get hidden() { return this.attributes.has('hidden'); }
    get previousElementSibling() {
      return this.parent?.children[this.parent.children.indexOf(this) - 1] || null;
    }
    setAttribute(key, value) { this.attributes.set(key, String(value)); }
    getAttribute(key) { return this.attributes.get(key) ?? null; }
    toggleAttribute(key, value) { if (value) this.attributes.set(key, ''); else this.attributes.delete(key); }
    addEventListener(name, callback) {
      if (!this.events.has(name)) this.events.set(name, []);
      this.events.get(name).push(callback);
    }
    async fire(name, details = {}) {
      if (name === 'click' && this.disabled) return;
      for (const callback of this.events.get(name) || []) {
        await callback({target: this, preventDefault() {}, ...details});
      }
    }
    append(...children) {
      for (const child of children) { child.parent = this; this.children.push(child); }
    }
    replaceChildren(...children) {
      this.children = []; this.append(...children);
      if (this.tagName === 'SELECT') this.value = children[0]?.value || '';
    }
    querySelectorAll(tag) {
      return this.children.flatMap(child => [
        ...(child.tagName === tag.toUpperCase() ? [child] : []),
        ...child.querySelectorAll(tag),
      ]);
    }
    querySelector(tag) { return this.querySelectorAll(tag)[0] || null; }
    click() {} remove() {}
  }
  for (const match of html.matchAll(/<([a-z][\w-]*)\b[^>]*\bid="([^"]+)"[^>]*>/gi)) {
    const element = new Element(match[1], match[2]);
    element.hidden = /\bhidden\b/.test(match[0]);
    element.disabled = /\bdisabled\b/.test(match[0]);
    const value = match[0].match(/\bvalue="([^"]*)"/);
    if (value) element.value = value[1];
  }
  ids.get('board').value = 'xiao'; ids.get('voices').value = '1'; ids.get('arena').value = '1';
  ids.get('numerical-profile').value = 'float32-auto-v1';
  const document = {
    getElementById: id => ids.get(id),
    createElement: tag => new Element(tag),
    createElementNS: (_namespace, tag) => new Element(tag),
    addEventListener() {}, body: new Element('body'), activeElement: null,
  };
  return {document, get: id => ids.get(id)};
}

async function openStudio({parameters = [], environment = {}, paired = []} = {}) {
  const dom = mockDocument(), calls = [], timers = new Map(), intervals = new Map();
  let timerId = 0;
  const backend = {
    device: null, parameters, uploadError: null, importError: null, importVisual: null, controlHandler: null,
    wifi:{supported:false,configured:false,connected:false,paired:false,device_id:'001122334455'},
    paired, wifiSetupHandler:null, wifiConnectError:null, networks:[], wifiScanHandler:null,
    devices: [{port: 'test-port', label: 'Mock USB', serial_number: 'mock-board-01'}],
    result: {kind: 'package', title: 'Test patch', package_bytes: 12345, parameters: [], sample_rate: 44100, block_frames: 256},
  };
  const snapshot = () => ({device: backend.device, parameters: backend.parameters});
  const fetch = async (path, options) => {
    assert.match(path, /^\/api\//, 'The mock must intercept every request');
    if (options.method === 'POST') assert.equal(options.headers['X-Studio-Token'], 'test-token');
    const body = options.body ? JSON.parse(options.body) : undefined;
    calls.push({path, options, body});
    let data;
    if (path === '/api/status') data = {
      csrf: 'test-token', busy: false,
      environment: {node: true, rnbo: true, idf: true, python_serial: true, amoled_components: false, ...environment},
    };
    else if (path === '/api/devices') data = {devices: backend.devices};
    else if (path === '/api/device') data = snapshot();
    else if (path === '/api/wifi') data = {wifi:backend.wifi,paired:backend.paired};
    else if (path === '/api/wifi/scan') data=backend.wifiScanHandler ? await backend.wifiScanHandler(body) : {networks:backend.networks};
    else if (path === '/api/wifi/setup') {
      if (backend.wifiSetupHandler) data = await backend.wifiSetupHandler(body);
      else { backend.wifi={...backend.wifi,supported:true,configured:true,connected:true,paired:true,ip:'192.168.1.20'};
        backend.paired=[{id:backend.wifi.device_id,label:'Player',ip:backend.wifi.ip}];data={wifi:backend.wifi,paired:backend.paired}; }
    } else if (path === '/api/wifi/forget') {
      backend.wifi={...backend.wifi,configured:false,connected:false,paired:false};backend.paired=[];
      data={wifi:backend.wifi,paired:[]};
    } else if (path === '/api/wifi/connect') {
      if (backend.wifiConnectError) data={error:backend.wifiConnectError};
      else { backend.device={runtime:'rnbo-esp32s3-player',board:'xiao',transport:'wifi',device_id:body.id,generation:1,panic:false,volume:50,rate:44100,block_frames:256,render_us:1000,peak_us:6000};data=snapshot(); }
    }
    else if (path === '/api/example') data = example;
    else if (path === '/api/import-package') {
      const result = {...backend.result, origin:'imported', visual:backend.importVisual}; delete result.parameters;
      data = backend.importError ? {error:backend.importError} : {job:{id:'import1',state:'ready',result,log:'Package validated; no rebuild'}};
    }
    else if (path === '/api/build') data = {job: {id: 'build1', state: 'building', stage: 'Compiling', log: 'working'}};
    else if (path.startsWith('/api/job?')) data = {job: {id: 'build1', state: 'ready', stage: 'Ready', log: 'done', result: backend.result}};
    else if (path === '/api/install-player') data = {job: {id:'install1',state:'done',stage:'Installed',result:{kind:'player',board:'xiao'}}};
    else if (path === '/api/upload') data = {job: {
      id: 'build1', state: backend.uploadError ? 'ready' : 'done', stage: 'Upload finished', error: backend.uploadError,
    }};
    else if (path === '/api/connect') {
      backend.device = {runtime:'rnbo-esp32s3-player',board: 'xiao', transport:'usb', device_id:'001122334455', generation:1, panic: false, volume: 50, render_us: 12, peak_us: 16};
      data = snapshot();
    } else if (path === '/api/control') {
      if (backend.controlHandler) data = await backend.controlHandler(body);
      else {
        if (body.action === 'pause') backend.device.panic = true;
        if (body.action === 'resume') backend.device.panic = false;
        data = snapshot();
      }
    } else assert.fail(`Unexpected API request: ${path}`);
    return {ok: true, status: 200, text: async () => JSON.stringify(data)};
  };
  vm.runInNewContext(source, {
    document: dom.document, fetch, console, Intl, btoa: value => Buffer.from(value,'binary').toString('base64'),
    setTimeout(callback, delay) { const id = ++timerId; timers.set(id, {callback, delay}); return id; },
    clearTimeout: id => timers.delete(id), setInterval(callback, delay) { intervals.set(delay, callback); },
  }, {filename: 'host/studio/web/app.js'});
  await settle();
  const runTimer = async delay => {
    const entry = [...timers].find(([, value]) => value.delay === delay);
    assert.ok(entry, `Expected a ${delay} ms frontend timer`);
    timers.delete(entry[0]); await entry[1].callback(); await settle();
  };
  return {
    ...dom, backend, calls, runTimer, snapshot,
    async runInterval(delay) {
      assert.ok(intervals.has(delay), `Expected a ${delay} ms frontend interval`);
      await intervals.get(delay)(); await settle();
    },
    async readyArtifact() {
      await dom.get('example').fire('click');
      await dom.get('compile').fire('click');
      await runTimer(850);
      assert.equal(dom.get('upload').disabled, false);
    },
  };
}

test('example, SVG and build workflow use the local session token and typed settings', async () => {
  const app = await openStudio();
  assert.equal(app.get('compile').disabled, true);
  await app.get('example').fire('click');
  assert.equal(app.get('compile').disabled, false);
  assert.equal(app.get('patch-svg').hidden, false);
  assert.match(app.get('patch-facts').textContent, /2 boxes/);
  assert.match(app.get('patch-facts').textContent, /1 connection/);
  await app.get('compile').fire('click');
  const request = app.calls.find(call => call.path === '/api/build');
  assert.equal(request.options.headers['X-Studio-Token'], 'test-token');
  assert.deepEqual(request.body, {
    name: 'test.rnbopat', patch: example.patch, role: 'main', initial_volume: 50,
    voices: 1, arena_bytes: 1048576, filter_delay_max_ms: null, float32_delays: false,
    numerical_profile: 'float32-auto-v1',
  });
  assert.equal(app.get('upload').disabled, true);
  await app.runTimer(850);
  assert.equal(app.get('build-result').hidden, false);
  assert.equal(app.get('download').disabled, false);
  assert.equal(app.get('upload').disabled, false);
  app.get('numerical-profile').value = 'float32-audio-v1';
  await app.get('numerical-profile').fire('change');
  assert.equal(app.get('upload').disabled, true);
  assert.equal(app.get('build-result').hidden, true);
  await app.get('compile').fire('click');
  assert.equal(app.calls.filter(call => call.path === '/api/build').at(-1).body.numerical_profile, 'float32-audio-v1');
  await app.runTimer(850);
});

test('an edit during compilation prevents the old ready job from becoming uploadable', async () => {
  const app = await openStudio();
  await app.get('example').fire('click');
  await app.get('compile').fire('click');
  app.get('source').value = '{';
  await app.get('source').fire('input');
  await app.runTimer(850);
  assert.equal(app.get('build-result').hidden, true);
  assert.equal(app.get('upload').disabled, true);
  assert.equal(app.get('download').disabled, true);
  await app.runTimer(300);
  assert.equal(app.get('compile').disabled, true);
  assert.match(app.get('source-state').textContent, /Check the patch JSON/);
  await app.get('example').fire('click');
  assert.equal(app.get('compile').disabled, false);
  assert.equal(app.get('upload').disabled, true);
});

test('ready plus upload error preserves the artifact for retry rather than claiming success', async () => {
  const app = await openStudio();
  await app.readyArtifact();
  app.backend.uploadError = 'Mock USB upload failed';
  await app.get('upload').fire('click');
  assert.match(app.get('message').textContent, /Mock USB upload failed/);
  assert.match(app.get('upload-status').textContent, /still available for retry or download/);
  assert.equal(app.get('upload').disabled, false);
  assert.equal(app.get('download').disabled, false);
  assert.notEqual(app.get('upload-status').dataset.completed, 'true');
  app.backend.uploadError = null;
  await app.get('upload').fire('click');
  assert.equal(app.get('upload-status').dataset.completed, 'true');
  const uploads = app.calls.filter(call => call.path === '/api/upload');
  assert.equal(uploads.length, 2);
  for (const request of uploads) {
    assert.deepEqual(request.body, {id: 'build1', port: 'test-port'});
    assert.equal(request.options.headers['X-Studio-Token'], 'test-token');
  }
});

test('upload refreshes ports by unique serial identity and never substitutes another board', async () => {
  const app = await openStudio();
  await app.readyArtifact();
  // The original path is now a different board; the selected board moved.
  app.backend.devices = [
    {port: 'test-port', label: 'Another board', serial_number: 'mock-board-02'},
    {port: 'renumbered-port', label: 'Original board', serial_number: 'mock-board-01'},
  ];
  app.backend.uploadError = 'Mock post-upload health check failed';
  await app.get('upload').fire('click');
  assert.equal(app.get('port').value, 'renumbered-port');
  assert.equal(app.get('upload').disabled, false);
  assert.equal(app.get('download').disabled, false);
  assert.match(app.get('device-status').textContent, /Mock post-upload health check failed/);
  await app.runInterval(1800);
  assert.match(app.get('device-status').textContent, /Mock post-upload health check failed/);
  const firstUpload = app.calls.findIndex(call => call.path === '/api/upload');
  assert.deepEqual(app.calls.slice(firstUpload + 1, firstUpload + 3).map(call => call.path), ['/api/devices', '/api/device']);
  app.backend.uploadError = null;
  await app.get('upload').fire('click');
  assert.equal(app.calls.filter(call => call.path === '/api/upload').at(-1).body.port, 'renumbered-port');
  const lastUpload = app.calls.findLastIndex(call => call.path === '/api/upload');
  assert.deepEqual(app.calls.slice(lastUpload + 1, lastUpload + 3).map(call => call.path), ['/api/devices', '/api/device']);
  // Duplicate IDs require a new explicit user choice.
  app.backend.devices = [
    {port: 'ambiguous-a', serial_number: 'mock-board-01'},
    {port: 'ambiguous-b', serial_number: 'mock-board-01'},
  ];
  await app.get('refresh-ports').fire('click');
  assert.equal(app.get('port').value, '');
  assert.equal(app.get('upload').disabled, true);
  assert.equal(app.get('connect').disabled, true);
  app.get('port').value = 'ambiguous-a';
  await app.get('port').fire('change');
  app.backend.devices = [{port: 'unrelated-port', serial_number: 'mock-board-02'}];
  await app.get('refresh-ports').fire('click');
  assert.equal(app.get('port').value, '');
  assert.equal(app.get('upload').disabled, true);
  // A disappearing selection with no serial also must not pick another board.
  app.backend.devices = [{port: 'no-serial-port'}];
  await app.get('refresh-ports').fire('click');
  app.get('port').value = 'no-serial-port';
  await app.get('port').fire('change');
  app.backend.devices = [{port: 'unrelated-port', serial_number: 'mock-board-02'}];
  await app.get('refresh-ports').fire('click');
  assert.equal(app.get('port').value, '');
  assert.equal(app.get('upload').disabled, true);
  assert.equal(app.get('connect').disabled, true);
});

test('one Pause/Resume button follows the acknowledged device state', async () => {
  const app = await openStudio();
  assert.equal(app.get('resume'), undefined);
  await app.get('connect').fire('click');
  assert.equal(app.get('pause').textContent, 'Pause audio');
  await app.get('pause').fire('click'); await settle();
  assert.equal(app.get('pause').textContent, 'Resume audio');
  assert.equal(app.get('pause').getAttribute('aria-pressed'), 'true');
  // A request is not a state acknowledgement: this mock still reports paused.
  app.backend.controlHandler = () => app.snapshot();
  await app.get('pause').fire('click'); await settle();
  assert.equal(app.get('pause').textContent, 'Resume audio');
  app.backend.controlHandler = null;
  await app.get('pause').fire('click'); await settle();
  assert.equal(app.get('pause').textContent, 'Pause audio');
  const controls = app.calls.filter(call => call.path === '/api/control');
  assert.deepEqual(controls.map(call => call.body.action), ['pause', 'resume', 'resume']);
  for (const call of controls) assert.equal(call.options.headers['X-Studio-Token'], 'test-token');
});

test('nonlinear parameter controls show actual readback and explicitly normalized drag values', async () => {
  const app = await openStudio({parameters: [{index: 0, name: 'Frequency', min: 100, max: 10000, initial: 440, actual: 2500, normalized: .7}]});
  await app.get('connect').fire('click');
  const slider = app.get('parameter-0');
  const output = slider.previousElementSibling.querySelector('output');
  assert.equal(Number(slider.value), .7);
  assert.equal(output.textContent, new Intl.NumberFormat(undefined, {maximumFractionDigits: 3}).format(2500));
  slider.value = '.3';
  await slider.fire('input');
  assert.equal(output.textContent, '30% normalized');
  assert.equal(app.calls.filter(call => call.path === '/api/control').length, 0);
  app.backend.controlHandler = action => {
    assert.deepEqual(action, {action: 'param', index: 0, value: .3, target:{device_id:'001122334455',transport:'usb'}});
    app.backend.parameters[0] = {...app.backend.parameters[0], actual: 960, normalized: .3};
    return app.snapshot();
  };
  await app.runTimer(140);
  assert.equal(output.textContent, '960');
  assert.equal(Number(slider.value), .3);
  const request = app.calls.find(call => call.path === '/api/control');
  assert.equal(request.options.headers['X-Studio-Token'], 'test-token');
});


test('board selection only affects explicit player installation, not a compiled package', async () => {
  const app = await openStudio(); await app.readyArtifact();
  app.get('board').value = 'amoled'; await app.get('board').fire('change');
  assert.equal(app.get('upload').disabled, false);
  await app.get('install-player').fire('click');
  assert.deepEqual(app.calls.find(c => c.path === '/api/install-player').body, {board:'amoled',port:'test-port'});
  assert.equal(app.get('upload').disabled, false);
});


test('generation change discards a pending old-patch control and stamps new controls', async () => {
  const app = await openStudio({parameters:[{role:'main',generation:1,index:0,name:'Gain',min:0,max:1,initial:.5,actual:.5,normalized:.5}]});
  await app.get('connect').fire('click');
  let slider=app.get('parameter-0');slider.value='.3';await slider.fire('input');
  app.backend.device.generation=2;
  app.backend.parameters=[{...app.backend.parameters[0],generation:2}];
  await app.runInterval(1800);
  assert.equal(app.calls.filter(c => c.path==='/api/control').length,0);
  slider=app.get('parameter-0');slider.value='.4';await slider.fire('input');await app.runTimer(140);
  assert.deepEqual(app.calls.filter(c => c.path==='/api/control').at(-1).body,
    {action:'param',role:'main',generation:2,index:0,value:.4,target:{device_id:'001122334455',transport:'usb'}});
});


test('saved package opens after restart and loads without source or build tools', async () => {
  const app = await openStudio({environment:{node:false,rnbo:false,idf:false}});
  const raw=new Uint8Array(128);raw[0]=82;
  app.get('package-file').files=[{name:'saved.rnbopkg',size:128,arrayBuffer:async()=>raw.buffer}];
  assert.equal(app.get('open-package').disabled,false);
  await app.get('package-file').fire('change');
  const request=app.calls.find(c=>c.path==='/api/import-package');
  assert.equal(request.body.name,'saved.rnbopkg');
  assert.equal(request.body.package_base64,Buffer.from(raw).toString('base64'));
  assert.equal(app.calls.some(c=>c.path==='/api/build'),false);
  assert.equal(app.get('compile').disabled,true);
  assert.equal(app.get('upload').disabled,false);
  assert.equal(app.get('download').disabled,false);
  assert.match(app.get('source-state').textContent,/without recompiling/);
  await app.get('upload').fire('click');
  assert.equal(app.calls.find(c=>c.path==='/api/upload').body.id,'import1');
});

test('invalid saved package preserves an existing ready artifact', async () => {
  const app=await openStudio();await app.readyArtifact();
  app.backend.importError='Package checksum mismatch';
  app.get('package-file').files=[{name:'broken.rnbopkg',size:128,arrayBuffer:async()=>new Uint8Array(128).buffer}];
  await app.get('package-file').fire('change');
  assert.match(app.get('message').textContent,/checksum mismatch/);
  assert.equal(app.get('upload').disabled,false);
  await app.get('upload').fire('click');
  assert.equal(app.calls.find(c=>c.path==='/api/upload').body.id,'build1');
});


test('saved package renders bounded compiled layout and highlights parameter boxes without editable source', async () => {
  const app=await openStudio();
  app.backend.importVisual={available:true,width:336,height:232,
    parameters:[{name:'Cutoff <script>'}],
    nodes:[{x:4,y:2,width:80,height:18,parameter:0,label:'Cutoff <script>'},
           {x:4,y:80,width:60,height:18,parameter:255,label:'out~ 1'}],
    segments:[[44,19,34,80]]};
  app.get('package-file').files=[{name:'saved.rnbopkg',size:128,arrayBuffer:async()=>new Uint8Array(128).buffer}];
  await app.get('package-file').fire('change');
  assert.equal(app.get('source-title').textContent,'Saved compiled package');
  assert.equal(app.get('source').value,'');assert.equal(app.get('compile').disabled,true);
  assert.equal(app.get('patch-svg').hidden,false);assert.equal(app.get('empty-preview').hidden,true);
  assert.equal(app.get('patch-svg').getAttribute('viewBox'),'-8 -8 352 248');
  const groups=app.get('patch-svg').querySelectorAll('g');
  assert.equal(groups.filter(g=>g.getAttribute('data-parameter')==='0').length,1);
  assert.equal(app.get('patch-svg').querySelectorAll('text')[0].textContent,'Cutoff <script>');
  assert.equal(app.get('patch-svg').querySelectorAll('script').length,0);
  assert.match(app.get('patch-facts').textContent,/2 objects.*1 wire segments.*1 parameters/);
});

test('missing or invalid package visual gets compiled-package placeholder and source opening resets it', async () => {
  const app=await openStudio();
  for (const visual of [null,{available:true,width:336,height:232,parameters:[],
      nodes:[{x:1e100,y:0,width:60,height:18,parameter:255,label:'bad'}],segments:[]}]) {
    app.backend.importVisual=visual;
    app.get('package-file').files=[{name:'saved.rnbopkg',size:128,arrayBuffer:async()=>new Uint8Array(128).buffer}];
    await app.get('package-file').fire('change');
    assert.equal(app.get('empty-title').textContent,'Saved compiled package');
    assert.equal(app.get('patch-svg').hidden,true);assert.equal(app.get('source').value,'');
  }
  await app.get('example').fire('click');
  assert.equal(app.get('source-title').textContent,'Your RNBO patch');
  assert.equal(app.get('empty-title').textContent,'Open an RNBO patch');
  assert.equal(app.get('patch-svg').hidden,false);
});


test('audio CPU percentages use actual block budget, retain microseconds and show over-budget peak', async () => {
  const app=await openStudio();await app.get('connect').fire('click');
  Object.assign(app.backend.device,{render_us:1000,peak_us:6000,rate:44100,block_frames:256});
  await app.runInterval(1800);
  const format=value=>new Intl.NumberFormat(undefined,{maximumFractionDigits:3}).format(value);
  assert.equal(app.get('render-time').textContent,`${format(1000)} µs`);
  assert.equal(app.get('audio-cpu').textContent,`${format(1000*44100/(256*1e6)*100)}% audio`);
  assert.equal(app.get('peak-audio-cpu').textContent,`${format(6000*44100/(256*1e6)*100)}% audio`);
  delete app.backend.device.rate;await app.runInterval(1800);
  assert.equal(app.get('audio-cpu').textContent,'—');
  assert.match(app.get('render-time').textContent,/µs/);
});

test('Wi-Fi setup is USB-only and clears password before sending without displaying it on error', async () => {
  const app=await openStudio();
  app.backend.wifi.supported=true;
  assert.equal(app.get('wifi-setup').disabled,true);
  await app.get('connect').fire('click');
  assert.equal(app.get('wifi-setup').disabled,false);
  app.get('wifi-ssid').value='Test network';app.get('wifi-password').value='private-password';
  app.backend.wifiSetupHandler=async body=>{
    assert.equal(app.get('wifi-password').value,'');
    assert.deepEqual(body,{ssid:'Test network',password:'private-password'});
    throw new Error('private-password');
  };
  await app.get('wifi-setup').fire('click');
  assert.equal(app.get('wifi-password').value,'');
  assert.doesNotMatch(app.get('message').textContent,/private-password/);
  assert.doesNotMatch(app.get('build-log').textContent,/private-password/);
  app.backend.wifiSetupHandler=null;app.get('wifi-password').value='another-password';
  await app.get('wifi-setup').fire('click');
  assert.equal(app.get('wifi-password').value,'');
  assert.equal(app.get('wifi-device').value,'001122334455');
  assert.match(app.get('wifi-status').textContent,/192.168.1.20/);
  app.get('transport').value='wifi';await app.get('transport').fire('change');
  assert.equal(app.get('wifi-setup').disabled,true);assert.equal(app.get('wifi-forget').disabled,true);
  app.get('transport').value='usb';await app.get('transport').fire('change');
  await app.get('wifi-forget').fire('click');
  assert.equal(app.get('wifi-device').value,'');assert.equal(app.get('wifi-forget').disabled,true);
  assert.deepEqual(app.calls.find(c=>c.path==='/api/wifi/forget').body,{});
});

test('saved Wi-Fi player connects and loads package with no USB device or serial tools', async () => {
  const app=await openStudio({environment:{python_serial:false},paired:[{id:'001122334455',label:'My Player',ip:'192.168.1.20'}]});
  app.backend.devices=[];await app.get('refresh-ports').fire('click');
  app.get('transport').value='wifi';await app.get('transport').fire('change');
  assert.equal(app.get('connect').disabled,false);assert.equal(app.get('install-player').disabled,true);
  app.get('wifi-ip').value='192.168.1.21';await app.get('connect').fire('click');
  assert.deepEqual(app.calls.find(c=>c.path==='/api/wifi/connect').body,{id:'001122334455',ip:'192.168.1.21'});
  assert.match(app.get('device-status').textContent,/Wi-Fi/);
  assert.equal(app.get('pause').disabled,false);
  await app.readyArtifact();await app.get('upload').fire('click');
  assert.deepEqual(app.calls.find(c=>c.path==='/api/upload').body,
    {id:'build1',transport:'wifi',device_id:'001122334455',ip:'192.168.1.21'});
  assert.equal(app.calls.some(c=>c.path==='/api/connect'||c.path==='/api/install-player'),false);
});

test('paired status polling is modest and never substitutes another saved identity', async () => {
  const app=await openStudio({paired:[{id:'001122334455',label:'A',ip:'192.168.1.20'}]});
  app.get('transport').value='wifi';await app.get('transport').fire('change');await app.get('connect').fire('click');
  const count=()=>app.calls.filter(c=>c.path==='/api/wifi').length;
  const before=count();await app.runInterval(1800);assert.equal(count(),before);
  app.backend.paired=[{id:'aabbccddeeff',label:'Other',ip:'192.168.1.22'}];
  await app.runInterval(6000);assert.equal(count(),before+1);
  assert.equal(app.get('wifi-device').value,'');assert.equal(app.get('connect').disabled,true);
  assert.equal(app.get('pause').disabled,true);
});


test('in-flight controls keep their original device target and cannot repaint a newly connected player', async () => {
  const app=await openStudio({paired:[{id:'aabbccddeeff',label:'Other',ip:'192.168.1.22'}]});
  await app.get('connect').fire('click');
  let finish;
  app.backend.controlHandler=async()=>new Promise(resolve=>{finish=resolve;});
  await app.get('pause').fire('click');await settle();
  const request=app.calls.find(c=>c.path==='/api/control');
  assert.deepEqual(request.body.target,{device_id:'001122334455',transport:'usb'});
  app.get('transport').value='wifi';await app.get('transport').fire('change');
  await app.get('connect').fire('click');
  assert.match(app.get('device-status').textContent,/Wi-Fi/);
  finish({device:{transport:'usb',device_id:'001122334455',board:'xiao',panic:true},parameters:[]});
  await settle();
  assert.match(app.get('device-status').textContent,/Wi-Fi/);
  assert.equal(app.get('pause').textContent,'Pause audio');
  assert.deepEqual(request.body.target,{device_id:'001122334455',transport:'usb'});
});


test('nearby network scan is USB-only, disables setup during scan and selects safe SSID text without configuring', async () => {
  const app=await openStudio();app.backend.wifi.supported=true;
  assert.equal(app.get('wifi-scan').disabled,true);
  await app.get('wifi-scan').fire('click');assert.equal(app.calls.some(c=>c.path==='/api/wifi/scan'),false);
  await app.get('connect').fire('click');
  const ssid='<script>alert(1)</script>';let finish;
  app.backend.wifiScanHandler=body=>{
    assert.deepEqual(body,{});return new Promise(resolve=>{finish=resolve;});
  };
  const pending=app.get('wifi-scan').fire('click');await settle();
  assert.equal(app.get('wifi-setup').disabled,true);assert.equal(app.get('wifi-scan').disabled,true);
  assert.equal(app.get('wifi-scan').getAttribute('aria-busy'),'true');
  assert.match(app.get('wifi-scan-status').textContent,/Audio pauses briefly/);
  finish({networks:[{ssid,rssi:-40,channel:6,secure:true}]});await pending;
  assert.equal(app.get('wifi-scan-results').hidden,false);
  const option=app.get('wifi-networks').children[1];assert.equal(option.value,ssid);
  assert.equal(option.textContent,`${ssid} · -40 dBm · secured`);
  assert.equal(app.get('wifi-networks').querySelectorAll('script').length,0);
  app.get('wifi-networks').value=ssid;await app.get('wifi-networks').fire('change');
  assert.equal(app.get('wifi-ssid').value,ssid);
  assert.equal(app.calls.some(c=>c.path==='/api/wifi/setup'),false);
  app.get('transport').value='wifi';await app.get('transport').fire('change');
  assert.equal(app.get('wifi-scan').disabled,true);assert.equal(app.get('wifi-scan-results').hidden,true);
});

test('failed scan clears previous results and busy state while keeping manual network entry', async () => {
  const app=await openStudio();app.backend.wifi.supported=true;await app.get('connect').fire('click');
  app.backend.networks=[{ssid:'First',rssi:-60,channel:1,secure:true}];
  await app.get('wifi-scan').fire('click');assert.equal(app.get('wifi-scan-results').hidden,false);
  app.get('wifi-ssid').value='Hidden network';
  app.backend.wifiScanHandler=async()=>{throw new Error('scan transport failed');};
  await app.get('wifi-scan').fire('click');
  assert.equal(app.get('wifi-scan-results').hidden,true);assert.equal(app.get('wifi-networks').children.length,1);
  assert.equal(app.get('wifi-scan').getAttribute('aria-busy'),'false');
  assert.equal(app.get('wifi-scan').disabled,false);assert.equal(app.get('wifi-setup').disabled,false);
  assert.equal(app.get('wifi-ssid').value,'Hidden network');assert.match(app.get('wifi-scan-status').textContent,/Scan failed/);
  assert.equal(app.calls.some(c=>c.path==='/api/wifi/setup'||c.path==='/api/wifi/forget'),false);
});


test('CPU admission rejection explains completed transfer and keeps active Main distinct through polling', async () => {
  const app=await openStudio();await app.get('connect').fire('click');
  Object.assign(app.backend.device,{main:{name:'DDD'},rate:44100,block_frames:256});
  await app.runInterval(1800);
  app.get('numerical-profile').value='float32-strict';await app.get('numerical-profile').fire('change');
  await app.readyArtifact();
  assert.equal(app.calls.find(c=>c.path==='/api/build').body.numerical_profile,'float32-strict');
  app.backend.uploadError="Device rejected capture command: 'Candidate uses 10047us per callback; player screen reserves time for the audio sink'";
  await app.get('upload').fire('click');
  assert.equal(app.get('load-failure').hidden,false);
  assert.match(app.get('load-failure-summary').textContent,/USB transfer completed/);
  assert.match(app.get('load-failure-summary').textContent,/10\.05 ms.*5\.80 ms/);
  assert.match(app.get('load-failure-summary').textContent,/previous patch remains running/);
  assert.equal(app.get('load-failure-raw').textContent,app.backend.uploadError);
  assert.equal(app.get('running-main').textContent,'DDD');
  assert.equal(app.get('package-to-load').textContent,'Test patch');
  assert.equal(app.get('optimise-recompile').hidden,false);
  const before=app.get('load-failure-summary').textContent;
  await app.runInterval(1800);await app.runInterval(6000);
  assert.equal(app.get('load-failure-summary').textContent,before);
  assert.equal(app.get('load-failure').hidden,false);
  const loads=app.calls.filter(c=>c.path==='/api/upload').length;
  app.get('float32-delays').checked=false;
  await app.get('optimise-recompile').fire('click');
  const request=app.calls.filter(c=>c.path==='/api/build').at(-1);
  assert.equal(request.body.numerical_profile,'float32-auto-v1');
  assert.equal(request.body.float32_delays,false);
  assert.equal(app.get('upload').disabled,true);
  await app.runTimer(850);
  assert.equal(app.calls.filter(c=>c.path==='/api/upload').length,loads);
  assert.equal(app.get('running-main').textContent,'DDD');
  assert.equal(app.get('upload').disabled,false);
});

test('ordinary load errors stay verbatim and saved packages cannot offer source recompilation', async () => {
  const app=await openStudio();
  app.get('package-file').files=[{name:'saved.rnbopkg',size:128,arrayBuffer:async()=>new Uint8Array(128).buffer}];
  await app.get('package-file').fire('change');
  app.backend.uploadError='Application state could not be read';
  await app.get('upload').fire('click');
  assert.equal(app.get('load-failure-summary').textContent,app.backend.uploadError);
  assert.equal(app.get('optimise-recompile').hidden,true);
  await app.runInterval(1800);assert.equal(app.get('load-failure-summary').textContent,app.backend.uploadError);
  app.backend.uploadError="Device rejected capture command: 'Candidate uses 9965 us per callback'";
  await app.get('upload').fire('click');
  assert.match(app.get('load-failure-summary').textContent,/9\.96 ms.*5\.80 ms/);
  assert.equal(app.get('optimise-recompile').hidden,true);
  app.backend.uploadError=null;await app.get('upload').fire('click');
  assert.equal(app.get('load-failure').hidden,true);
});


test('Auto CPU failure offers no identical recompile or automatic activation', async () => {
  const app=await openStudio();await app.readyArtifact();
  assert.equal(app.get('numerical-profile').value,'float32-auto-v1');
  app.backend.uploadError="Device rejected capture command: 'Candidate uses 10047us per callback'";
  await app.get('upload').fire('click');
  assert.equal(app.get('optimise-recompile').hidden,true);
  assert.equal(app.get('optimise-hint').hidden,false);
  assert.equal(app.get('optimise-hint').textContent,'Automatic optimisation is already selected; this patch still needs further optimisation.');
  const builds=app.calls.filter(c=>c.path==='/api/build').length;
  const loads=app.calls.filter(c=>c.path==='/api/upload').length;
  await app.get('optimise-recompile').fire('click');await app.runInterval(1800);await app.runInterval(6000);
  assert.equal(app.calls.filter(c=>c.path==='/api/build').length,builds);
  assert.equal(app.calls.filter(c=>c.path==='/api/upload').length,loads);
  assert.equal(app.get('load-failure').hidden,false);
  assert.match(app.get('load-failure-summary').textContent,/USB transfer completed/);
  assert.equal(app.get('load-failure-raw').textContent,app.backend.uploadError);
});
