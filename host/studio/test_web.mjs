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
  ids.get('numerical-profile').value = 'float32-strict';
  const document = {
    getElementById: id => ids.get(id),
    createElement: tag => new Element(tag),
    createElementNS: (_namespace, tag) => new Element(tag),
    addEventListener() {}, body: new Element('body'), activeElement: null,
  };
  return {document, get: id => ids.get(id)};
}

async function openStudio({parameters = [], environment = {}} = {}) {
  const dom = mockDocument(), calls = [], timers = new Map(), intervals = new Map();
  let timerId = 0;
  const backend = {
    device: null, parameters, uploadError: null, importError: null, importVisual: null, controlHandler: null,
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
      backend.device = {runtime:'rnbo-esp32s3-player',board: 'xiao', generation:1, panic: false, volume: 50, render_us: 12, peak_us: 16};
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
    numerical_profile: 'float32-strict',
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
    assert.deepEqual(action, {action: 'param', index: 0, value: .3});
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
    {action:'param',role:'main',generation:2,index:0,value:.4});
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
