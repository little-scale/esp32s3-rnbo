/* RNBO Studio: local source, explicit build target, USB upload and live controls. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = {
    csrf: '', environment: {}, serverBusy: false, reachable: false,
    exportPayload: null, patch: null, name: 'RNBO Export', revision: 0, valid: false,
    artifact: null, firmware: null, firmwareOptions: [], currentFirmware: null, catalogueLoading: false,
    job: null, jobRevision: -1, operation: null, linkedJob: null,
    loadFailure: null, loadingTransport: 'usb',
    connecting: false, connectedPort: '', connectedTransport: 'usb', connectedDeviceId: '',
    device: null, deviceError: '', parameters: [], parameterKey: '',
    portSerials: new Map(), portsInitialized: false,
    wifi: {}, paired: [], pairedInitialized: false, refreshingWifi: false,
    jobTimer: null, parsingTimer: null, refreshing: false, pollingDevice: false,
    controlEpoch: 0, controlQueue: Promise.resolve(), controlTimers: new Map(),
  };
  const boards = {xiao: 'XIAO ESP32-S3', amoled: 'Waveshare AMOLED 1.8 V2'};
  const activeStates = new Set(['queued', 'building', 'uploading']);
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  const number = value => finite(value) ? new Intl.NumberFormat(undefined, {maximumFractionDigits: 3}).format(value) : '—';
  const bytes = value => finite(value) ? (value >= 1048576 ? `${number(value / 1048576)} MiB` : `${number(value / 1024)} KiB`) : '—';
  const busy = () => Boolean(state.operation || state.connecting || state.refreshing || state.serverBusy);
  const transport = () => $('transport').value === 'wifi' ? 'wifi' : 'usb';
  const firstInstall = () => $('firmware-mode').value === 'first-install';
  const installOptions = () => firstInstall() ? {mode:'first-install',erase_confirmed:$('firmware-erase').checked} : {};
  const selectedConnection = () => Boolean(state.device) && transport() === state.connectedTransport
    && (transport() === 'wifi' ? Boolean(state.connectedDeviceId && state.connectedDeviceId === $('wifi-device').value)
      : Boolean(state.connectedPort && state.connectedPort === $('port').value));
  function cancelQueuedControls() {
    state.controlEpoch += 1;
    for (const timer of state.controlTimers.values()) clearTimeout(timer);
    state.controlTimers.clear();
  }
  function wifiTarget() {
    const target = {id: $('wifi-device').value};
    const ip = $('wifi-ip').value.trim();
    if (ip) target.ip = ip;
    return target;
  }

  function message(text = '') {
    $('message').textContent = text;
    $('message').hidden = !text;
  }

  async function api(path, body) {
    const options = {headers: {'Accept': 'application/json'}, cache: 'no-store'};
    if (body !== undefined) {
      if (!state.csrf) throw new Error('The local session is not ready. Refresh the page and try again.');
      options.method = 'POST';
      options.headers['Content-Type'] = 'application/json';
      options.headers['X-Studio-Token'] = state.csrf;
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    const text = await response.text();
    let data;
    try { data = JSON.parse(text); }
    catch (_) { throw new Error(`The local server returned an unreadable response (${response.status}).`); }
    if (!response.ok || (data.error && !data.job)) {
      const error = new Error(data.error || `Request failed (${response.status}).`);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function availability(value) {
    if (value === false || value === null) return false;
    if (value && typeof value === 'object') {
      for (const key of ['available', 'ok', 'installed']) if (typeof value[key] === 'boolean') return value[key];
    }
    if (value === true || (typeof value === 'string' && value.length)) return true;
    return null;
  }

  function missingTools(forUpload = false) {
    const keys = forUpload ? ['python_serial'] : ['idf'];

    return keys.filter(key => availability(state.environment[key]) === false);
  }

  function updateButtons() {
    const working = busy();
    const usb = transport() === 'usb';
    const serialMissing = usb && missingTools(true).length > 0;
    const availableArtifact = state.artifact && state.artifact.revision === state.revision;
    const selectedConnected = selectedConnection();
    const hasTarget = usb ? Boolean($('port').value) : Boolean($('wifi-device').value);
    const isPlayer = state.device && state.device.runtime === 'rnbo-esp32s3-player';
    const eraseAllowed = !firstInstall() || $('firmware-erase').checked;
    $('running-main').textContent = selectedConnected
      ? state.device.main?.name ? `${state.device.main.name}${state.device.paused ? ' · paused' : ''}` : 'No Main patch loaded'
      : 'Not connected to the selected player';
    $('package-to-load').textContent = availableArtifact ? state.artifact.result.title || 'Compiled package'
      : state.operation === 'build' ? 'Compiling…' : 'None compiled or opened';
    $('usb-connection').hidden = !usb; $('wifi-connection').hidden = usb;
    $('transport').disabled = working;
    $('port').disabled = working; $('board').disabled = working;
    $('wifi-device').disabled = working; $('wifi-ip').disabled = working;
    const setup = usb && selectedConnected && isPlayer && state.wifi.supported === true && !working && !serialMissing;
    $('wifi-ssid').disabled = !setup; $('wifi-password').disabled = !setup;
    $('wifi-setup').disabled = !setup;
    $('wifi-scan').disabled = !setup;
    $('wifi-networks').disabled = !setup;
    $('wifi-scan').textContent = state.operation === 'wifi-scan' ? 'Scanning…' : 'Scan nearby networks';
    $('wifi-scan').setAttribute('aria-busy', String(state.operation === 'wifi-scan'));
    $('wifi-forget').disabled = !setup || !state.wifi.configured;
    $('install-player').disabled = !usb || !state.csrf || !$('port').value || working || !eraseAllowed || serialMissing || availability(state.environment.idf) === false;
    $('install-player').textContent = firstInstall() ? 'Build, erase & install player' : 'Build & update player';
    $('firmware-mode').disabled = working;
    $('firmware-erase-label').hidden = !firstInstall();
    $('firmware-erase').disabled = working || !firstInstall();
    $('open-firmware').disabled = !state.reachable || !state.csrf || working;
    $('firmware-file').disabled = working;
    $('firmware-choice').disabled = !state.reachable || !state.csrf || working || state.catalogueLoading;
    $('refresh-firmware').disabled = !state.reachable || !state.csrf || working || state.catalogueLoading;
    $('flash-firmware').disabled = !usb || !state.reachable || !state.csrf || !state.firmware || !$('port').value
      || working || !eraseAllowed || firstInstall() && !state.firmware?.first_install_available
      || serialMissing || availability(state.environment.firmware_tools) === false;
    $('flash-firmware').textContent = state.firmware
      ? firstInstall() ? `Erase & install ${boards[state.firmware.board]} player` : `Update ${boards[state.firmware.board]} player`
      : firstInstall() ? 'Erase & install player' : 'Flash selected firmware';
    $('compile').disabled = !state.reachable || !state.csrf || !state.valid || working || missingTools().length > 0;
    $('open-package').disabled = !state.reachable || !state.csrf || working;
    $('connect').disabled = !state.csrf || !hasTarget || working || serialMissing;
    $('connect').textContent = usb ? 'Connect USB' : 'Connect Wi-Fi';
    $('upload').disabled = !state.csrf || !availableArtifact || !hasTarget || working || serialMissing;
    $('download').disabled = !availableArtifact || state.operation === 'upload';
    $('download-trial').disabled = !availableArtifact || state.operation === 'upload';
    $('example').disabled = state.operation === 'upload';
    $('refresh-ports').disabled = state.refreshing || state.operation === 'upload';
    const live = Boolean(state.device) && typeof state.device.device_id === 'string'
      && selectedConnected && !working && !serialMissing && !state.device.maintenance;
    $('volume').disabled = !live;
    $('pause').disabled = !live;
    $('pause').textContent = state.device && (state.device.paused ?? state.device.panic) === true ? 'Resume audio' : 'Pause audio';
    $('pause').setAttribute('aria-pressed', String(Boolean(state.device && (state.device.paused ?? state.device.panic) === true)));
    for (const input of $('parameters').querySelectorAll('input')) input.disabled = !live;
    const midi = live && state.device?.midi_input_version === 1 && state.device?.midi?.uart_supported === true;
    $('midi-mode').disabled = !midi; $('midi-save').disabled = !midi;
    if (!state.operation) {
      if (!state.reachable) $('compile-status').textContent = 'Local server unavailable';
      else if (missingTools().length) $('compile-status').textContent = 'A required local tool is unavailable. See Local tools.';
      else if (state.serverBusy) $('compile-status').textContent = 'Local tools are busy…';
      else if (availableArtifact) $('compile-status').textContent = 'Package ready to download or load';
      else $('compile-status').textContent = state.valid ? 'Ready to compile' : 'Open a Max Minimal Export to compile';
      if (!availableArtifact) $('upload-status').textContent = 'Compile the current patch and settings before uploading.';
      else if (!hasTarget) $('upload-status').textContent = usb ? 'Choose a USB device for the compiled package.' : 'Choose a saved Wi-Fi player for the compiled package.';
      else if (!$('upload-status').dataset.completed) $('upload-status').textContent = isPlayer ? 'Ready to load the package into the connected player.' : 'Connect a stable player, or install it below first.';
      if (state.loadFailure) $('upload-status').textContent = state.loadFailure.cpuUs !== null
        ? 'The package was rejected before activation. See the CPU admission result below.'
        : 'Load failed. The package is still available for retry or download.';
    }
    renderLoadFailure();
  }

  function recordLoadFailure(error) {
    const raw = String(error);
    const match = raw.match(/Candidate uses\s+(\d+(?:\.\d+)?)\s*(?:us|µs)\s+per callback/i);
    const used = match ? Number(match[1]) : null;
    const result = state.artifact?.result || {};
    const rate = state.device?.rate ?? state.device?.sample_rate ?? result.sample_rate;
    const frames = state.device?.block_frames ?? result.block_frames;
    state.loadFailure = {raw, title:result.title || state.name, cpuUs:finite(used) && used > 0 ? used : null,
      budgetMs:finite(rate) && rate > 0 && finite(frames) && frames > 0 ? frames / rate * 1000 : 256 / 44100 * 1000,
      transport:state.loadingTransport, priorMain:selectedConnection() ? state.device.main?.name : null,
      priorPaused:state.device?.paused ?? state.device?.panic};
  }

  function renderLoadFailure() {
    const failure = state.loadFailure;
    $('load-failure').hidden = !failure;
    $('optimise-hint').hidden = !failure || failure.cpuUs === null;
    $('optimise-hint').textContent = 'Simplify the patch in Max and export again. Native exports use the baseline Float32 wrapper; previous importer optimisation profiles are retired.';
    if (!failure) return;
    $('load-failure-title').textContent = `${failure.cpuUs !== null ? 'Last load rejected' : 'Last load error'}: ${failure.title}`;
    const retained = failure.priorMain ? failure.priorPaused ? 'The previous patch stays loaded and paused.' : 'The previous patch remains running.'
      : 'The player retained its previous state.';
    $('load-failure-summary').textContent = failure.cpuUs !== null
      ? `${failure.transport === 'wifi' ? 'Wi-Fi' : 'USB'} transfer completed, but this patch needs about ${(failure.cpuUs / 1000).toFixed(2)} ms per block. The audio block budget is ${failure.budgetMs.toFixed(2)} ms, and the player reserves part of it for audio output. ${retained}`
      : failure.raw;
    $('load-failure-raw').textContent = failure.raw;
    $('load-failure-details').hidden = failure.cpuUs === null;
  }

  function invalidate() {
    state.revision += 1;
    state.artifact = null;
    $('build-result').hidden = true;
    delete $('upload-status').dataset.completed;
    updateButtons();
  }

  function patchGraph(patch) {
    if (!patch || typeof patch !== 'object' || Array.isArray(patch)) throw new Error('The patch must be a JSON object.');
    const graph = patch.patcher || patch;
    if (!Array.isArray(graph.boxes)) throw new Error('No RNBO patch boxes were found in this JSON.');
    return graph;
  }

  function svgElement(name, attributes = {}, text) {
    const element = document.createElementNS('http://www.w3.org/2000/svg', name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function drawPatch(patch) {
    const graph = patchGraph(patch);
    const svg = $('patch-svg');
    svg.replaceChildren();
    const boxes = graph.boxes.map(entry => entry.box || entry).filter(box => box && typeof box === 'object');
    const nodes = new Map();
    for (const [index, box] of boxes.slice(0, 500).entries()) {
      const rect = Array.isArray(box.patching_rect) ? box.patching_rect : [];
      const label = String(box.text || box.maxclass || 'object');
      nodes.set(String(box.id ?? index), {
        box, label,
        x: finite(rect[0]) ? rect[0] : (index % 5) * 155,
        y: finite(rect[1]) ? rect[1] : Math.floor(index / 5) * 85,
        width: finite(rect[2]) ? clamp(rect[2], 65, 340) : clamp(label.length * 7 + 24, 80, 230),
        height: finite(rect[3]) ? clamp(rect[3], 28, 90) : 30,
        inputPorts: 1, outputPorts: 1,
      });
    }
    const lines = (Array.isArray(graph.lines) ? graph.lines : []).map(entry => entry.patchline || entry);
    for (const line of lines) {
      if (!Array.isArray(line.source) || !Array.isArray(line.destination)) continue;
      const source = nodes.get(String(line.source[0])), destination = nodes.get(String(line.destination[0]));
      if (source && Number.isInteger(line.source[1])) source.outputPorts = Math.max(source.outputPorts, line.source[1] + 1);
      if (destination && Number.isInteger(line.destination[1])) destination.inputPorts = Math.max(destination.inputPorts, line.destination[1] + 1);
    }
    const portX = (node, port, count) => node.x + 10 + clamp(port, 0, count - 1) * (node.width - 20) / Math.max(1, count - 1);
    const wires = svgElement('g');
    for (const line of lines) {
      if (!Array.isArray(line.source) || !Array.isArray(line.destination)) continue;
      const a = nodes.get(String(line.source[0])), b = nodes.get(String(line.destination[0]));
      if (!a || !b) continue;
      const x1 = portX(a, Number(line.source[1]) || 0, a.outputPorts), y1 = a.y + a.height;
      const x2 = portX(b, Number(line.destination[1]) || 0, b.inputPorts), y2 = b.y;
      const bend = Math.max(24, Math.abs(y2 - y1) * .45);
      wires.append(svgElement('path', {d: `M${x1},${y1} C${x1},${y1 + bend} ${x2},${y2 - bend} ${x2},${y2}`, class: 'patch-wire'}));
    }
    svg.append(wires);
    for (const node of nodes.values()) {
      const kind = /^(in~?)(\s|$)/.test(node.label) ? 'input' : /^(out~?)(\s|$)/.test(node.label) ? 'output' : /^(param|number|sig~)(\s|$)/.test(node.label) ? 'control' : '';
      const group = svgElement('g', {class: `patch-node ${kind}`});
      group.append(svgElement('title', {}, node.label));
      group.append(svgElement('rect', {x: node.x, y: node.y, width: node.width, height: node.height, rx: 5}));
      const maxLetters = Math.max(5, Math.floor((node.width - 18) / 6.7));
      const label = node.label.replace(/\s+/g, ' ');
      group.append(svgElement('text', {x: node.x + 9, y: node.y + node.height / 2 + 4}, label.length > maxLetters ? `${label.slice(0, maxLetters - 1)}…` : label));
      for (let i = 0; i < Math.min(node.inputPorts, 32); i++) group.append(svgElement('circle', {cx: portX(node, i, node.inputPorts), cy: node.y, r: 2, class: 'patch-port'}));
      for (let i = 0; i < Math.min(node.outputPorts, 32); i++) group.append(svgElement('circle', {cx: portX(node, i, node.outputPorts), cy: node.y + node.height, r: 2, class: 'patch-port'}));
      svg.append(group);
    }
    if (nodes.size) {
      const values = [...nodes.values()];
      const x = Math.min(...values.map(n => n.x)) - 28, y = Math.min(...values.map(n => n.y)) - 34;
      const width = Math.max(...values.map(n => n.x + n.width)) - x + 28;
      const height = Math.max(...values.map(n => n.y + n.height)) - y + 34;
      svg.setAttribute('viewBox', `${x} ${y} ${Math.max(width, 200)} ${Math.max(height, 150)}`);
    } else svg.setAttribute('viewBox', '0 0 300 200');
    $('empty-preview').hidden = nodes.size > 0;
    svg.toggleAttribute('hidden', nodes.size === 0);
    $('patch-facts').textContent = `${boxes.length} boxes · ${lines.length} connections${boxes.length > 500 ? ' · first 500 shown' : ''}`;
  }

  function drawPackagePreview(visual) {
    const svg = $('patch-svg'); svg.replaceChildren();
    $('source-title').textContent = 'Saved compiled package';
    $('empty-title').textContent = 'Saved compiled package';
    $('empty-description').textContent = 'No visual layout is included. The package is ready to load; editable patch JSON is not included.';
    $('patch-facts').textContent = 'Saved package · editable source not included';
    $('empty-preview').hidden = false; svg.setAttribute('hidden', '');
    svg.setAttribute('aria-label', 'Saved package compiled layout');
    const integer = value => Number.isInteger(value) && Number.isFinite(value);
    if (!visual || visual.available !== true || visual.width !== 336 || visual.height !== 232
        || !Array.isArray(visual.nodes) || visual.nodes.length < 1 || visual.nodes.length > 96
        || !Array.isArray(visual.segments) || visual.segments.length > 384
        || !Array.isArray(visual.parameters) || visual.parameters.length > 32) return;
    const parameters = visual.parameters;
    if (parameters.some(p => !p || typeof p.name !== 'string')) return;
    if (visual.nodes.some(n => !n || typeof n.label !== 'string'
        || ![n.x, n.y, n.width, n.height, n.parameter].every(integer)
        || n.x < 0 || n.y < 0 || n.width < 1 || n.height < 1
        || n.x + n.width > 336 || n.y + n.height > 232
        || (n.parameter !== 255 && (n.parameter < 0 || n.parameter >= parameters.length)))) return;
    if (visual.segments.some(s => !Array.isArray(s) || s.length !== 4 || !s.every(integer)
        || s.some((point, i) => point < 0 || point >= (i % 2 === 0 ? 336 : 232)))) return;
    const wires = svgElement('g');
    for (const [x1, y1, x2, y2] of visual.segments) {
      wires.append(svgElement('path', {d: `M${x1},${y1} L${x2},${y2}`, class: 'patch-wire'}));
    }
    svg.append(wires);
    for (const node of visual.nodes) {
      const isParameter = node.parameter !== 255;
      const label = node.label.slice(0, 31);
      const group = svgElement('g', {class: `patch-node ${isParameter ? 'control' : ''}`});
      if (isParameter) group.setAttribute('data-parameter', node.parameter);
      group.append(svgElement('title', {}, isParameter ? `${label} · ${parameters[node.parameter].name.slice(0, 95)}` : label));
      group.append(svgElement('rect', {x: node.x, y: node.y, width: node.width, height: node.height, rx: 3}));
      group.append(svgElement('text', {x: node.x + 3, y: node.y + node.height / 2 + 4}, label));
      svg.append(group);
    }
    svg.setAttribute('viewBox', '-8 -8 352 248');
    svg.toggleAttribute('hidden', false);
    $('empty-preview').hidden = true;
    $('patch-facts').textContent = `Compiled layout · ${visual.nodes.length} objects · ${visual.segments.length} wire segments · ${parameters.length} parameters`;
  }

  async function openFile(file) {
    if (!file || busy()) return;
    try {
      if (!file.name.toLowerCase().endsWith('.zip') || file.size > 32 * 1048576) throw new Error('Choose a Minimal Export ZIP up to 32 MiB.');
      const data = new Uint8Array(await file.arrayBuffer());
      state.exportPayload = {zip_base64: toBase64(data)};
      acceptExport(file.name);
    } catch (error) { message(`Could not open ${file.name}: ${error.message}`); }
    $('file').value = '';
  }

  function toBase64(data) {
    let binary = '';
    for (let offset = 0; offset < data.length; offset += 8192)
      binary += String.fromCharCode(...data.subarray(offset, offset + 8192));
    return btoa(binary);
  }

  function acceptExport(name) {
    $('source-title').textContent = 'Max C++ export';
    state.linkedJob = null; state.name = name; state.patch = null; state.valid = true;
    invalidate();
    $('file-name').textContent = name;
    $('patch-svg').setAttribute('hidden', ''); $('empty-preview').hidden = false;
    $('empty-title').textContent = 'Max C++ export selected';
    $('empty-description').textContent = 'Add the original .rnbopat for a drawing, or compile the exported code directly.';
    $('patch-facts').textContent = 'Minimal C++ · source checked during build';
    $('source-state').textContent = 'Export selected. Compilation uses C++ only; optional patch drawings do not change DSP.';
    $('source-state').classList.remove('source-error'); message(); updateButtons();
  }

  async function openFolder(files) {
    if (!files?.length || busy()) return;
    try {
      if (files.length > 1024 || [...files].reduce((sum, file) => sum + file.size, 0) > 32 * 1048576)
        throw new Error('Export exceeds the 1024-file / 32 MiB limit.');
      const rows = [];
      for (const file of files) rows.push({path:file.webkitRelativePath || file.name,
        data_base64:toBase64(new Uint8Array(await file.arrayBuffer()))});
      state.exportPayload = {export_files:rows};
      acceptExport((files[0].webkitRelativePath || 'RNBO Export').split('/')[0]);
    } catch (error) { message(error.message); }
    $('folder').value = '';
  }

  async function openLayout(file) {
    if (!file || busy()) return;
    try {
      if (!state.exportPayload) throw new Error('Open the matching C++ export first.');
      if (!file.name.toLowerCase().endsWith('.rnbopat') || file.size > 1048576) throw new Error('Choose a .rnbopat drawing up to 1 MiB.');
      const patch = JSON.parse(await file.text()); patchGraph(patch);
      state.patch = patch; invalidate(); drawPatch(patch);
      $('source-state').textContent = 'Drawing attached only. Re-export in Max whenever you change the audio patch.';
      message();
    } catch (error) { message(error.message); }
    $('layout-file').value = '';
  }

  async function openPackage(file) {
    if (!file || busy()) return;
    try {
      if (!file.name.toLowerCase().endsWith('.rnbopkg') || file.size < 128 || file.size > 589952) {
        throw new Error('Choose a .rnbopkg file up to 589,952 bytes.');
      }
      state.operation = 'import'; updateButtons(); message();
      const raw = new Uint8Array(await file.arrayBuffer());
      if (raw.length < 128 || raw.length > 589952) throw new Error('The package size is invalid.');
      let binary = '';
      for (let offset = 0; offset < raw.length; offset += 8192) {
        binary += String.fromCharCode(...raw.subarray(offset, offset + 8192));
      }
      const response = await api('/api/import-package', {name: file.name, package_base64: btoa(binary)});
      if (!response.job || response.job.state !== 'ready' || response.job.result?.kind !== 'package') {
        throw new Error('The saved package was not accepted.');
      }
      clearTimeout(state.parsingTimer);
      invalidate();
      state.job = response.job;
      state.artifact = {id: response.job.id, revision: state.revision, result: response.job.result};
      state.linkedJob = null; state.exportPayload = null; state.patch = null; state.valid = false; state.name = file.name;
      $('file-name').textContent = file.name;
      drawPackagePreview(response.job.result.visual);
      $('source-state').textContent = 'Saved package validated. Ready to load without recompiling.';
      $('source-state').classList.remove('source-error');
      $('build-log').textContent = response.job.log || 'Saved package ready to load.';
      showResult(response.job.result);
    } catch (error) { message(`Could not open package: ${error.message}`); }
    finally { state.operation = null; $('package-file').value = ''; updateButtons(); }
  }

  function showFirmware(item, details = '') {
    if (!item || !/^[0-9a-f]{32}$/.test(item.id) || !Object.hasOwn(boards,item.board)
        || !/^[0-9a-f]{64}$/.test(item.firmware_elf_sha256)) throw new Error('The firmware file was not accepted.');
    state.firmware = item;
    $('firmware-status').textContent = `${item.name} · ${boards[item.board]} · ${bytes(item.application_bytes)}${item.usb_midi_host ? ' · experimental USB MIDI host' : ''}\n${details}${item.first_install_available ? 'Supports update and first install.' : 'Update only; no bootloader in this ZIP.'} Selection does not change the board.`;
  }

  async function refreshFirmwareOptions() {
    if (busy() || state.catalogueLoading) return;
    state.catalogueLoading = true; updateButtons();
    try {
      const response = await api('/api/firmware/options');
      const rows = response.firmwares;
      if (!Array.isArray(rows) || rows.length > 2 || new Set(rows.map(row=>row.id)).size !== rows.length
          || rows.some(row=>!Object.hasOwn(boards,row.id) || row.board!==row.id || typeof row.available!=='boolean'
            || row.available && (!/^[0-9a-f]{64}$/.test(row.sha256) || !/^[0-9a-f]{64}$/.test(row.firmware_elf_sha256))))
        throw new Error('The current firmware list was not accepted.');
      state.firmwareOptions = rows;
      if (state.currentFirmware && !rows.some(row=>row.available && row.id===state.currentFirmware.id && row.sha256===state.currentFirmware.sha256)) {
        state.firmware = null; state.currentFirmware = null; $('firmware-erase').checked = false;
        $('firmware-status').textContent = 'Current firmware changed or needs rebuilding. Choose it again from the refreshed list.';
      }
      const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = 'Choose current firmware…';
      $('firmware-choice').replaceChildren(placeholder, ...rows.map(row=>{
        const option = document.createElement('option'); option.value = row.id; option.disabled = !row.available;
        option.textContent = `${boards[row.board]} · ${row.available ? 'USB + Wi-Fi · current' : 'build required'}`;
        return option;
      }));
      $('firmware-choice').value = state.currentFirmware?.id || '';
      $('firmware-catalogue-status').textContent = [
        rows.some(row=>row.available) ? 'Current builds on this computer. Choose one to prepare it; install with the button below.' : 'No current player build is ready. Build locally below, or open a firmware ZIP.',
        ...rows.filter(row=>!row.available).map(row=>`${boards[row.board]}: ${String(row.reason || 'Build required').slice(0,400)}`)
      ].join('\n');
    } catch (error) {
      state.firmwareOptions = [];
      $('firmware-choice').replaceChildren();
      $('firmware-catalogue-status').textContent = `Could not refresh current firmware: ${error.message}`;
    } finally { state.catalogueLoading = false; updateButtons(); }
  }

  async function chooseCurrentFirmware() {
    if (busy() || state.catalogueLoading) return;
    const row = state.firmwareOptions.find(item=>item.id===$('firmware-choice').value && item.available);
    state.firmware = null; state.currentFirmware = null; $('firmware-erase').checked = false;
    if (!row) { $('firmware-status').textContent = 'Choose a current player firmware or open a firmware ZIP.'; updateButtons(); return; }
    try {
      state.operation = 'firmware-open'; updateButtons(); message();
      $('firmware-status').textContent = 'Preparing the selected current firmware…';
      const response = await api('/api/firmware/select', {id:row.id,sha256:row.sha256});
      if (response.firmware?.board!==row.board || response.firmware?.firmware_elf_sha256!==row.firmware_elf_sha256)
        throw new Error('Selected firmware identity changed. Refresh the firmware list and choose it again.');
      const built = new Date(row.built_at);
      showFirmware(response.firmware, `USB + Wi-Fi · build ${row.firmware_elf_sha256.slice(0,12)}${Number.isFinite(built.getTime()) ? ' · '+built.toLocaleString() : ''}\n`);
      state.currentFirmware = {id:row.id,sha256:row.sha256};
    } catch (error) {
      state.firmware = null; $('firmware-choice').value = '';
      $('firmware-status').textContent = error.message; message(error.message);
    } finally { state.operation = null; updateButtons(); }
  }

  async function openFirmware(file) {
    if (!file || busy()) return;
    state.firmware = null;
    state.currentFirmware = null; $('firmware-choice').value = '';
    $('firmware-erase').checked = false;
    try {
      if (!file.name.toLowerCase().endsWith('.zip') || file.size <= 0 || file.size > 4 * 1048576)
        throw new Error('Choose an RNBO player firmware ZIP up to 4 MiB. Raw BIN and patch packages use different formats.');
      state.operation = 'firmware-open'; updateButtons(); message();
      $('firmware-status').textContent = 'Checking firmware file…';
      const raw = new Uint8Array(await file.arrayBuffer());
      if (!raw.length || raw.length > 4 * 1048576) throw new Error('Firmware ZIP exceeds its size limit.');
      const response = await api('/api/firmware/import', {name:file.name, firmware_base64:toBase64(raw)});
      showFirmware(response.firmware);
    } catch (error) { $('firmware-status').textContent = error.message; message(error.message); }
    finally { state.operation = null; $('firmware-file').value = ''; updateButtons(); }
  }

  async function flashFirmware() {
    if ($('flash-firmware').disabled) return;
    try {
      message(); state.operation = 'firmware'; cancelQueuedControls(); updateButtons();
      $('firmware-status').textContent = 'Preparing USB firmware upload…'; $('build-output').open = true;
      const options = installOptions(); $('firmware-erase').checked = false;
      const response = await api('/api/firmware/upload', {id:state.firmware.id, port:$('port').value,...options});
      await handleJob(response.job);
    } catch (error) {
      state.operation = null; $('firmware-status').textContent = error.message; message(error.message);
      await refreshDevice(); updateButtons();
    }
  }

  function buildOptions() {
    return {...state.exportPayload, name:state.name, visual_patch:state.patch, role:'main',
      initial_volume:Number($('initial-volume').value), arena_bytes:Number($('arena').value) * 1048576};
  }

  function showResult(result) {
    $('result-title').textContent = result.title || 'Package ready';
    const bindings = result.physical_inputs?.bindings || [];
    const facts = [bindings.length ? 'Main package · XIAO physical inputs' : 'Main package · both boards', finite(result.package_bytes) ? bytes(result.package_bytes) : null,
      finite(result.sample_rate) ? `${number(result.sample_rate)} Hz` : null,
      finite(result.block_frames) ? `${result.block_frames} frames` : null,
      Array.isArray(result.parameters) ? `${result.parameters.length} parameters` : null].filter(Boolean);
    $('result-facts').replaceChildren(...facts.map(text => {
      const span = document.createElement('span'); span.textContent = text; return span;
    }));
    $('input-bindings').hidden = !bindings.length;
    $('input-bindings').replaceChildren(...bindings.map(binding => {
      const row = document.createElement('div');
      row.textContent = `${binding.pin} · ${binding.type} → ${binding.parameter_id}`;
      return row;
    }));
    const trial = result.float32_trial;
    $('trial-status').hidden = !trial;
    $('download-trial').hidden = !trial || result.trial_report_available !== true;
    if (trial) {
      const comparison = result.trial_comparison;
      $('trial-status').textContent = `Experimental Float32 trial · unverified. ${trial.trial_method_count} additional DSP methods changed; ${trial.skipped_method_count} skipped.`
        + (comparison ? ` Default-output comparison: maximum float difference ${comparison.max_absolute_error}; PCM ${comparison.max_pcm_difference_lsb} LSB. This is a smoke test, not full validation.` : ' The package carries its audit identity; a full report is available in the original build session.')
        + (result.trial_device_check ? ' Device runtime smoke recorded; outputs remain unverified.' : '');
    }
    $('build-result').hidden = false;
  }

  async function handleJob(job) {
    if (!job || !job.id || !job.state) throw new Error('The server did not return a valid job.');
    state.job = job;
    const label = String(job.stage || job.state).replace(/[_-]/g, ' ');
    $('compile-status').textContent = state.operation === 'upload' ? 'Compiled package · load in progress' : label.charAt(0).toUpperCase() + label.slice(1);
    if (state.operation === 'upload') $('upload-status').textContent = `Uploading · ${label}`;
    if (state.operation === 'firmware' || state.operation === 'install') $('firmware-status').textContent = label;
    const log = Array.isArray(job.log) ? job.log.join('\n') : String(job.log || '');
    const output = $('build-log'), follow = output.scrollHeight - output.clientHeight - output.scrollTop < 55;
    output.textContent = log || `${label}…`;
    if (follow) output.scrollTop = output.scrollHeight;
    clearTimeout(state.jobTimer);
    if (activeStates.has(job.state)) {
      updateButtons();
      state.jobTimer = setTimeout(() => pollJob(job.id), 850);
      return;
    }
    const operation = state.operation;
    state.operation = null;
    if (operation) state.serverBusy = false;
    if (job.state === 'failed' || job.error) {
      message(job.error || 'The operation failed. See the build output for details.');
      $('build-output').open = true;
      $('compile-status').textContent = 'Build failed';
      if (operation === 'upload') $('upload-status').textContent = 'Upload failed. Review the output before retrying.';
      if (operation === 'upload') state.deviceError = job.error || 'Upload failed. Review the build output before retrying.';
      if (operation === 'upload') recordLoadFailure(job.error || 'The package could not be loaded.');
      if (operation === 'firmware' || operation === 'install') $('firmware-status').textContent = `Firmware installation failed: ${job.error || 'See output for details.'}`;
    } else if (job.state === 'ready' || job.state === 'done') {
      if (operation === 'build') {
        if (state.jobRevision === state.revision) {
          const result = job.result || {};
          state.artifact = {id: job.id, revision: state.revision, result};
          showResult(result);
          if (!state.exportPayload) {
            drawPackagePreview(result.visual);
            if (state.linkedJob === job.id) {
              $('source-title').textContent = 'Build from Max';
              $('file-name').textContent = result.title || 'Live Max export';
            }
          }
        } else $('source-state').textContent = 'The patch or settings changed during compilation. Compile again to use the current version.';
      } else if (operation === 'upload' || operation === 'install' || operation === 'firmware') {
        if (operation === 'upload') state.loadFailure = null;
        if (operation === 'upload' && state.artifact?.id === job.id && job.result) {
          state.artifact.result = job.result; showResult(job.result);
        }
        if (operation === 'firmware' || operation === 'install') $('firmware-status').textContent = 'Player firmware verified and running.';
        if (operation !== 'firmware') {
          $('upload-status').textContent = operation === 'install' ? 'Stable player installed. Compile and load a package.' : 'Package loaded and saved. Player firmware unchanged.';
          $('upload-status').dataset.completed = 'true';
        }
        state.deviceError = '';
      }
    } else {
      message(`The server returned an unknown job state: ${job.state}`);
    }
    if (operation === 'upload' || operation === 'install' || operation === 'firmware') {
      await refreshDevices();
      await refreshDevice();
    }
    updateButtons();
    if ((job.state === 'failed' || job.error) && operation === 'build') $('compile-status').textContent = 'Build failed · see output';
    if ((job.state === 'failed' || job.error) && operation === 'upload' && state.loadFailure?.cpuUs === null) $('upload-status').textContent = 'Upload failed. The compiled package is still available for retry or download.';
  }

  async function pollJob(id) {
    if (state.job && state.job.id !== id) return;
    try { const response = await api(`/api/job?id=${encodeURIComponent(id)}`); await handleJob(response.job); }
    catch (error) {
      if (error.status === 400 || error.status === 404) {
        state.operation = null;
        state.job = null;
        message(`${error.message} Compile again to create a new package job.`);
        updateButtons();
        return;
      }
      $('compile-status').textContent = 'Progress connection interrupted';
      message(`${error.message} Retrying the job status…`);
      state.jobTimer = setTimeout(() => pollJob(id), 2200);
    }
  }

  async function compile() {
    if ($('compile').disabled) return;
    try {
      if (!state.valid) return;
      const options = buildOptions();
      message();
      state.artifact = null; $('build-result').hidden = true;
      state.operation = 'build'; state.jobRevision = state.revision;
      $('compile-status').textContent = 'Starting local build…';
      $('build-output').open = true; $('build-log').textContent = 'Starting local build…';
      updateButtons();
      const response = await api('/api/build', options);
      await handleJob(response.job);
    } catch (error) { state.operation = null; message(error.message); updateButtons(); }
  }

  async function upload() {
    if ($('upload').disabled || !state.artifact) return;
    try {
      message(); state.loadFailure = null; state.loadingTransport = transport(); state.operation = 'upload';
      state.controlEpoch += 1;
      for (const timer of state.controlTimers.values()) clearTimeout(timer);
      state.controlTimers.clear();
      delete $('upload-status').dataset.completed;
      $('upload-status').textContent = 'Loading package. Audio will pause briefly…';
      $('build-output').open = true; updateButtons();
      const wifi = wifiTarget();
      const target = transport() === 'wifi'
        ? {transport:'wifi', device_id:wifi.id, ...(wifi.ip ? {ip:wifi.ip} : {})}
        : {port:$('port').value};
      const response = await api('/api/upload', {id: state.artifact.id, ...target});
      await handleJob(response.job);
    } catch (error) {
      state.operation = null; state.deviceError = error.message; recordLoadFailure(error.message); message(error.message);
      await refreshDevices(); await refreshDevice(); updateButtons();
    }
  }

  function renderWifi(response, preferCurrent = false) {
    state.wifi = response && typeof response.wifi === 'object' && response.wifi ? response.wifi : {};
    state.paired = Array.isArray(response?.paired) ? response.paired.filter(p => p && typeof p.id === 'string'
      && p.id.length > 0 && p.id.length <= 128).slice(0, 32) : [];
    const current = $('wifi-device').value;
    let selected = state.paired.some(p => p.id === current) ? current : '';
    if (preferCurrent || (!state.pairedInitialized && !current)) {
      selected = state.paired.some(p => p.id === state.wifi.device_id) ? state.wifi.device_id : state.paired[0]?.id || '';
    }
    const prompt = document.createElement('option'); prompt.value = '';
    prompt.textContent = state.paired.length ? 'Choose a paired player…' : 'No paired players saved';
    $('wifi-device').replaceChildren(prompt, ...state.paired.map(p => {
      const option = document.createElement('option'); option.value = p.id;
      option.textContent = `${String(p.label || 'Player').slice(0, 160)} · ${p.id}${p.ip ? ` · ${String(p.ip).slice(0, 64)}` : ''}`;
      return option;
    }));
    $('wifi-device').value = selected; state.pairedInitialized = true;
    const wifi = state.wifi;
    $('wifi-status').textContent = wifi.connected
      ? `Wi-Fi connected${wifi.ip ? ` · ${String(wifi.ip).slice(0, 64)}` : ''}${wifi.paired ? ' · paired with Studio' : ''}`
      : wifi.configured ? 'Wi-Fi settings saved. Waiting for the network connection.'
      : wifi.supported ? 'No Wi-Fi network configured. Enter its settings below while connected by USB.'
      : state.device && state.connectedTransport === 'usb' ? 'This firmware does not offer Wi-Fi setup. Install an updated player to use it.'
      : 'Connect by USB to set up Wi-Fi.';
    updateButtons();
  }

  async function refreshWifi() {
    if (state.refreshingWifi || state.operation || state.connecting || state.serverBusy) return;
    state.refreshingWifi = true;
    try { renderWifi(await api('/api/wifi')); }
    catch (_) {
      state.wifi = {};
      $('wifi-status').textContent = 'Wi-Fi status unavailable. USB remains available.';
      updateButtons();
    } finally { state.refreshingWifi = false; }
  }

  function clearNetworks() {
    const prompt = document.createElement('option'); prompt.value = ''; prompt.textContent = 'Choose a network…';
    $('wifi-networks').replaceChildren(prompt); $('wifi-scan-results').hidden = true;
  }

  async function scanWifi() {
    if ($('wifi-scan').disabled) return;
    clearNetworks(); state.operation = 'wifi-scan'; cancelQueuedControls(); updateButtons();
    $('wifi-scan-status').textContent = 'Scanning nearby networks. Audio pauses briefly…';
    try {
      const response = await api('/api/wifi/scan', {});
      if (!Array.isArray(response.networks)) throw new Error('Invalid scan response');
      const networks = response.networks.slice(0, 24).filter(n => n && typeof n.ssid === 'string'
        && n.ssid.length > 0 && n.ssid.length <= 32 && !n.ssid.includes('\0') && finite(n.rssi)
        && Number.isInteger(n.channel) && typeof n.secure === 'boolean');
      const options = networks.map(n => {
        const option = document.createElement('option'); option.value = n.ssid;
        option.textContent = `${n.ssid} · ${n.rssi} dBm · ${n.secure ? 'secured' : 'open'}`;
        return option;
      });
      $('wifi-networks').append(...options); $('wifi-scan-results').hidden = networks.length === 0;
      $('wifi-scan-status').textContent = networks.length ? `${networks.length} networks found. Choose one or enter a hidden network manually.`
        : 'No named networks found. You can enter a hidden network manually.';
    } catch (_) {
      clearNetworks(); $('wifi-scan-status').textContent = 'Scan failed. Check the USB connection or enter the network name manually.';
    } finally { state.operation = null; updateButtons(); }
  }

  async function configureWifi(forget = false) {
    if ($(forget ? 'wifi-forget' : 'wifi-setup').disabled) return;
    const password = $('wifi-password').value;
    $('wifi-password').value = ''; // Never retain a sent password in the page.
    const fields = forget ? {} : {ssid:$('wifi-ssid').value, password};
    state.operation = 'wifi-setup'; cancelQueuedControls(); updateButtons(); message();
    $('wifi-feedback').textContent = forget ? 'Forgetting Wi-Fi settings…' : 'Sending settings over USB…';
    try {
      renderWifi(await api(forget ? '/api/wifi/forget' : '/api/wifi/setup', fields), !forget);
      $('wifi-feedback').textContent = forget ? 'Wi-Fi settings and saved pairing removed.' : 'Settings sent. Wait for Wi-Fi to connect, then select Wi-Fi above.';
      if (forget) $('wifi-ssid').value = '';
    } catch (error) {
      $('wifi-feedback').textContent = forget ? 'Could not forget Wi-Fi. Check the USB connection.' : 'Could not save Wi-Fi. Check the USB connection and try again.';
      message('Wi-Fi setup could not finish. Check the USB connection and network settings.');
    } finally { state.operation = null; updateButtons(); }
  }

  async function refreshDevices() {
    if (state.refreshing) return;
    state.refreshing = true; updateButtons();
    try {
      const response = await api('/api/devices');
      const current = $('port').value;
      const previousSerial = state.portSerials.get(current);
      const devices = Array.isArray(response.devices) ? response.devices : [];
      let selected = '';
      if (current && previousSerial) {
        const matches = devices.filter(device => device.serial_number === previousSerial);
        if (matches.length === 1) selected = matches[0].port;
      } else if (current && devices.some(device => device.port === current)) selected = current;
      else if (!state.portsInitialized && !current && devices.length) selected = devices[0].port;
      const prompt = document.createElement('option'); prompt.value = '';
      prompt.textContent = devices.length ? 'Choose a USB device…' : 'No USB devices found';
      const options = devices.map(device => {
        const option = document.createElement('option'); option.value = device.port;
        option.textContent = device.label ? `${device.label} · ${device.port}` : device.port;
        return option;
      });
      $('port').replaceChildren(prompt, ...options);
      $('port').value = selected;
      state.portSerials = new Map(devices.filter(device => typeof device.serial_number === 'string' && device.serial_number.length)
        .map(device => [device.port, device.serial_number]));
      state.portsInitialized = true;
    } catch (error) { $('device-status').textContent = error.message; }
    finally { state.refreshing = false; updateButtons(); }
  }

  function parameterNormalized(parameter) {
    if (finite(parameter.normalized)) return clamp(parameter.normalized, 0, 1);
    if (finite(parameter.initial_normalized)) return clamp(parameter.initial_normalized, 0, 1);
    return .5;
  }

  function parameterReadback(parameter, normalized) {
    const actual = finite(parameter.actual) ? parameter.actual : parameter.value;
    return finite(actual) ? number(actual) : `${number(normalized * 100)}% normalized`;
  }

  function renderParameters(parameters) {
    const metadata = parameters.filter(parameter => Number.isInteger(parameter.index));
    const key = JSON.stringify(metadata.map(p => [p.role, p.generation, p.index, p.name, p.min, p.max, p.initial]));
    if (key !== state.parameterKey) {
      state.parameterKey = key;
      $('parameters').replaceChildren();
      for (const parameter of metadata) {
        const row = document.createElement('div'); row.className = 'parameter';
        const heading = document.createElement('div'); heading.className = 'parameter-heading';
        const label = document.createElement('label'); label.htmlFor = `parameter-${parameter.index}`; label.textContent = parameter.name || `Parameter ${parameter.index + 1}`;
        const output = document.createElement('output'); output.htmlFor = label.htmlFor;
        const input = document.createElement('input');
        input.id = label.htmlFor; input.type = 'range'; input.min = '0'; input.max = '1'; input.step = '.001'; input.dataset.index = String(parameter.index);
        input.value = String(parameterNormalized(parameter)); output.textContent = parameterReadback(parameter, Number(input.value));
        const onValue = () => {
          output.textContent = `${number(Number(input.value) * 100)}% normalized`;
          scheduleControl({action: 'param', index: parameter.index, value: Number(input.value), ...(parameter.role ? {role: parameter.role, generation: parameter.generation} : {})}, `param-${parameter.index}`);
        };
        input.addEventListener('input', onValue);
        input.addEventListener('change', () => flushControl({action: 'param', index: parameter.index, value: Number(input.value), ...(parameter.role ? {role: parameter.role, generation: parameter.generation} : {})}, `param-${parameter.index}`));
        heading.append(label, output); row.append(heading, input);
        const range = document.createElement('div'); range.className = 'parameter-range';
        range.textContent = `${number(parameter.min)} – ${number(parameter.max)}`; row.append(range);
        $('parameters').append(row);
      }
      if (!metadata.length) { const text = document.createElement('p'); text.className = 'hint'; text.textContent = 'This patch has no exposed parameters.'; $('parameters').append(text); }
    } else {
      for (const parameter of metadata) {
        const input = $(`parameter-${parameter.index}`);
        if (!input || document.activeElement === input || state.controlTimers.has(`param-${parameter.index}`)) continue;
        input.value = String(parameterNormalized(parameter));
        input.previousElementSibling.querySelector('output').textContent = parameterReadback(parameter, Number(input.value));
      }
    }
  }

  function renderDevice(response) {
    if (state.device && response.device && state.device.generation !== response.device.generation) {
      state.controlEpoch += 1;
      for (const timer of state.controlTimers.values()) clearTimeout(timer);
      state.controlTimers.clear();
    }
    state.device = response.device || null;
    if (Array.isArray(response.parameters)) state.parameters = response.parameters;
    const device = state.device;
    const midi = device?.midi;
    if (midi) {
      if (!$('midi-mode').dataset.dirty) $('midi-mode').value = midi.uart_enabled ? 'uart' : 'off';
      $('midi-status').textContent = `${midi.uart_enabled ? 'UART enabled · D7 / GPIO44' : 'UART off'}${midi.usb_host_compiled ? ` · USB host ${midi.usb_connected ? 'device attached' : 'waiting for device'}` : ''}. `
        + (midi.patch_input_supported ? `${midi.delivered || 0} MIDI messages delivered · ${midi.overflows || 0} overflows.` : 'Compile a patch containing MIDI objects to receive MIDI.')
        + (midi.error ? ` ${midi.error}` : '');
    } else $('midi-status').textContent = 'Install the updated player to configure MIDI.';
    const physical = device?.main?.physical_inputs;
    const inputStatus = $('physical-input-status');
    inputStatus.hidden = !physical || (!physical.error && !physical.bindings?.length);
    inputStatus.replaceChildren();
    if (physical?.error) inputStatus.textContent = physical.error;
    else for (const binding of physical?.bindings || []) {
      const row = document.createElement('div');
      const parameter = state.parameters.find(p => p.index === binding.index);
      const status = !binding.valid ? 'waiting for input' : !binding.ready ? 'calibrating' : `${number(binding.normalized * 100)}%`;
      row.textContent = `${binding.pin} / GPIO${binding.gpio} → ${parameter?.name || `Parameter ${binding.index + 1}`} · ${status} · raw ${binding.raw}${binding.read_errors ? ` · ${binding.read_errors} read errors` : ''}`;
      inputStatus.append(row);
    }
    $('connection').textContent = device ? (device.paused ?? device.panic) === true ? 'PAUSED' : 'CONNECTED' : 'OFFLINE';
    $('connection').classList.toggle('online', Boolean(device));
    $('runtime-controls').hidden = !device; $('resources').hidden = !device;
    if (!device) {
      $('device-status').textContent = state.deviceError || (transport() === 'wifi' ? 'Choose a saved Wi-Fi player to connect.' : 'Choose a USB device to connect.');
      state.parameterKey = ''; state.parameters = []; state.connectedPort = ''; state.connectedDeviceId = '';
      updateButtons(); return;
    }
    state.deviceError = '';
    state.connectedTransport = (device.transport || response.transport || state.connectedTransport) === 'wifi' ? 'wifi' : 'usb';
    if (state.connectedTransport === 'wifi') {
      state.connectedDeviceId = device.device_id || response.device_id || state.connectedDeviceId;
      state.connectedPort = '';
    } else if (device.port || response.port) state.connectedPort = device.port || response.port;
    const selectedConnected = selectedConnection();
    $('device-status').textContent = selectedConnected
      ? `${boards[device.board] || device.board || 'Device'} · ${state.connectedTransport === 'wifi' ? 'Wi-Fi' : 'USB'} · ${(device.paused ?? device.panic) === true ? 'audio paused' : 'connected'}`
      : 'Another connection is selected. Connect it to use its live controls.';
    $('runtime-name').textContent = String(device.main?.name || device.runtime || '');
    if (finite(device.volume) && document.activeElement !== $('volume') && !state.controlTimers.has('volume')) {
      $('volume').value = String(clamp(device.volume, 0, 100)); $('volume-value').textContent = `${Math.round(device.volume)}%`;
    }
    $('render-time').textContent = finite(device.render_us) ? `${number(device.render_us)} µs` : '—';
    $('peak-time').textContent = finite(device.peak_us) ? `${number(device.peak_us)} µs` : '—';
    $('internal-free').textContent = bytes(device.internal_free_bytes); $('psram-free').textContent = bytes(device.psram_free_bytes);
    const sampleRate = device.rate ?? device.sample_rate;
    const audioPercent = time => finite(time) && time >= 0 && finite(sampleRate) && sampleRate > 0
      && finite(device.block_frames) && device.block_frames > 0
      ? `${number(time * sampleRate / (device.block_frames * 1000000) * 100)}% audio` : '—';
    $('audio-cpu').textContent = audioPercent(device.render_us);
    $('peak-audio-cpu').textContent = audioPercent(device.peak_us);
    $('runtime-facts').textContent = [finite(sampleRate) ? `${number(sampleRate)} Hz` : null, finite(device.block_frames) ? `${device.block_frames} frames / block` : null].filter(Boolean).join(' · ');
    renderParameters(state.parameters); updateButtons();
  }

  async function refreshDevice() {
    if (state.pollingDevice || state.operation || state.connecting) return;
    state.pollingDevice = true;
    try { renderDevice(await api('/api/device')); }
    catch (error) { state.deviceError = `Device status unavailable: ${error.message}`; renderDevice({device: null}); }
    finally { state.pollingDevice = false; }
  }

  async function connect() {
    if ($('connect').disabled) return;
    state.connecting = true; state.deviceError = ''; cancelQueuedControls(); updateButtons(); message();
    const method = transport();
    $('device-status').textContent = method === 'wifi' ? 'Connecting over Wi-Fi…' : 'Connecting over USB…';
    try {
      const port = $('port').value;
      const response = method === 'wifi' ? await api('/api/wifi/connect', wifiTarget()) : await api('/api/connect', {port});
      if (!response.device) throw new Error('No instrument status was returned by the selected device.');
      state.connectedTransport = method;
      state.connectedPort = method === 'usb' ? port : '';
      state.connectedDeviceId = method === 'wifi' ? $('wifi-device').value : '';
      renderDevice(response);
    } catch (error) { state.deviceError = error.message; renderDevice({device: null}); message(error.message); }
    finally { state.connecting = false; updateButtons(); await refreshWifi(); }
  }

  function enqueueControl(action) {
    const epoch = state.controlEpoch;
    const request = stampControl(action);
    state.controlQueue = state.controlQueue.catch(() => {}).then(async () => {
      if (epoch !== state.controlEpoch || !state.device || state.operation || !selectedConnection()) return;
      try {
        const response = await api('/api/control', request);
        if (epoch === state.controlEpoch && Object.hasOwn(response, 'device')) renderDevice(response);
      } catch (error) { message(`Could not update the instrument: ${error.message}`); }
    });
  }

  function stampControl(action) {
    return action.target ? action : {...action,
      target:{device_id:state.device?.device_id, transport:state.connectedTransport}};
  }

  function scheduleControl(action, key) {
    const request = stampControl(action);
    clearTimeout(state.controlTimers.get(key));
    state.controlTimers.set(key, setTimeout(() => { state.controlTimers.delete(key); enqueueControl(request); }, 140));
  }

  function flushControl(action, key) {
    clearTimeout(state.controlTimers.get(key)); state.controlTimers.delete(key); enqueueControl(action);
  }

  async function refreshStatus() {
    try {
      const response = await api('/api/status');
      if (state.csrf && response.csrf && state.csrf !== response.csrf) {
        clearTimeout(state.jobTimer); state.job = null; state.operation = null;
        invalidate();
        state.firmware = null; state.currentFirmware = null; $('firmware-choice').value = '';
        $('firmware-status').textContent = 'Studio restarted. Select current firmware or open its ZIP again.';
        $('firmware-erase').checked = false;
        message('The local server restarted. Compile the patch again before uploading.');
      }
      state.csrf = response.csrf || ''; state.environment = response.environment || {};
      state.serverBusy = Boolean(response.busy); state.reachable = true;
      const names = {idf: 'ESP32 tools', python_serial: 'USB tools', firmware_tools:'Firmware USB tools', amoled_components: 'AMOLED components'};
      $('environment').replaceChildren(...Object.entries(names).map(([key, label]) => {
        const span = document.createElement('span'), available = availability(state.environment[key]);
        span.textContent = `${label} ${available === true ? '✓' : available === false ? 'unavailable' : '—'}`;
        span.className = available === false ? 'missing' : available === true ? 'available' : '';
        const value = state.environment[key];
        if (typeof value === 'string') span.title = value;
        else if (value && typeof value === 'object') span.title = value.error || value.path || '';
        return span;
      }));
    } catch (error) {
      state.reachable = false;
      $('environment').textContent = 'The local server could not be reached.';
      if (!state.operation) $('compile-status').textContent = error.message;
    }
    updateButtons();
    if (state.reachable) await refreshWifi();
  }

  $('open-file').addEventListener('click', () => $('file').click());
  $('file').addEventListener('change', () => openFile($('file').files[0]));
  $('open-package').addEventListener('click', () => $('package-file').click());
  $('package-file').addEventListener('change', () => openPackage($('package-file').files[0]));
  $('open-firmware').addEventListener('click', () => $('firmware-file').click());
  $('firmware-file').addEventListener('change', () => openFirmware($('firmware-file').files[0]));
  $('flash-firmware').addEventListener('click', flashFirmware);
  $('firmware-choice').addEventListener('change', chooseCurrentFirmware);
  $('refresh-firmware').addEventListener('click', refreshFirmwareOptions);
  $('open-folder').addEventListener('click', () => $('folder').click());
  $('folder').addEventListener('change', () => openFolder($('folder').files));
  $('open-layout').addEventListener('click', () => $('layout-file').click());
  $('layout-file').addEventListener('change', () => openLayout($('layout-file').files[0]));
  $('example').addEventListener('click', async () => {
    try { const response = await api('/api/example'); message(response.guidance); }
    catch (error) { message(error.message); }
  });
  const drop = $('drop-zone');
  drop.addEventListener('keydown', event => { if ((event.key === 'Enter' || event.key === ' ') && event.target === drop) { event.preventDefault(); $('file').click(); } });
  for (const type of ['dragenter', 'dragover']) drop.addEventListener(type, event => { event.preventDefault(); drop.classList.add('dragging'); });
  for (const type of ['dragleave', 'drop']) drop.addEventListener(type, event => { event.preventDefault(); drop.classList.remove('dragging'); });
  drop.addEventListener('drop', event => openFile(event.dataTransfer.files[0]));
  document.addEventListener('dragover', event => event.preventDefault());
  document.addEventListener('drop', event => event.preventDefault());
  for (const id of ['arena', 'initial-volume']) {
    $(id).addEventListener(id === 'comb-max' || id === 'initial-volume' ? 'input' : 'change', () => {
      $('initial-volume-value').textContent = `${$('initial-volume').value}%`; invalidate();
    });
  }
  $('compile').addEventListener('click', compile);
  $('upload').addEventListener('click', upload);
  $('install-player').addEventListener('click', async () => {
    if ($('install-player').disabled) return;
    try {
      message(); state.operation = 'install'; state.controlEpoch += 1;
      for (const timer of state.controlTimers.values()) clearTimeout(timer);
      state.controlTimers.clear(); updateButtons();
      $('build-output').open = true;
      $('firmware-status').textContent = 'Building player firmware…';
      const options = installOptions(); $('firmware-erase').checked = false;
      const response = await api('/api/install-player', {board: $('board').value, port: $('port').value,...options});
      await handleJob(response.job);
    } catch (error) { state.operation = null; message(error.message); updateButtons(); }
  });
  $('download').addEventListener('click', () => {
    if (!state.artifact || state.artifact.revision !== state.revision) return;
    const link = document.createElement('a'); link.href = `/api/artifact?id=${encodeURIComponent(state.artifact.id)}`;
    link.download = 'patch.rnbopkg'; document.body.append(link); link.click(); link.remove();
  });
  $('download-trial').addEventListener('click', () => {
    if (!state.artifact || state.artifact.revision !== state.revision || state.artifact.result?.trial_report_available !== true) return;
    const link = document.createElement('a'); link.href = `/api/trial-report?id=${encodeURIComponent(state.artifact.id)}`;
    link.download = 'float32-trial-report.json'; document.body.append(link); link.click(); link.remove();
  });
  $('refresh-ports').addEventListener('click', refreshDevices);
  $('midi-mode').addEventListener('change', () => { $('midi-mode').dataset.dirty='true'; });
  $('midi-save').addEventListener('click', async () => {
    if ($('midi-save').disabled) return;
    try {
      const device=state.device; state.operation='midi'; updateButtons();
      const response=await api('/api/midi/configure', {mode:$('midi-mode').value,target:{device_id:device.device_id,transport:state.connectedTransport}});
      delete $('midi-mode').dataset.dirty; renderDevice(response);
    } catch (error) { message(error.message); }
    finally { state.operation=null; updateButtons(); }
  });
  for (const id of ['transport', 'port', 'wifi-device']) $(id).addEventListener('change', () => {
    $('firmware-erase').checked = false;
    cancelQueuedControls(); clearNetworks(); $('wifi-scan-status').textContent = '';
    if (id === 'transport') $('wifi-password').value = '';
    if (id === 'wifi-device') $('wifi-ip').value = '';
    delete $('upload-status').dataset.completed;
    renderDevice({device: state.device, parameters: state.parameters});
  });
  for (const id of ['firmware-mode','board']) $(id).addEventListener('change', () => {
    $('firmware-erase').checked = false; updateButtons();
  });
  $('firmware-erase').addEventListener('change', updateButtons);
  $('wifi-scan').addEventListener('click', scanWifi);
  $('wifi-networks').addEventListener('change', () => {
    if (!$('wifi-networks').disabled && $('wifi-networks').value) $('wifi-ssid').value = $('wifi-networks').value;
  });
  $('wifi-setup').addEventListener('click', () => configureWifi(false));
  $('wifi-forget').addEventListener('click', () => configureWifi(true));
  $('connect').addEventListener('click', connect);
  $('volume').addEventListener('input', () => {
    $('volume-value').textContent = `${$('volume').value}%`;
    scheduleControl({action: 'volume', value: Number($('volume').value)}, 'volume');
  });
  $('volume').addEventListener('change', () => flushControl({action: 'volume', value: Number($('volume').value)}, 'volume'));
  $('pause').addEventListener('click', () => enqueueControl({action: state.device && (state.device.paused ?? state.device.panic) === true ? 'resume' : 'pause'}));
  document.addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter' && !$('compile').disabled) { event.preventDefault(); compile(); }
  });

  async function openLinkedJob() {
    const identity = new URLSearchParams(location.search).get('job');
    if (!identity) return;
    if (!/^[0-9a-f]{32}$/.test(identity)) { message('Invalid Studio build link.'); return; }
    try {
      state.linkedJob = identity; state.operation = 'build'; state.jobRevision = state.revision;
      $('source-state').textContent = 'Build submitted from Max. The live drawing and C++ export were supplied together.';
      $('build-output').open = true;
      const job = (await api(`/api/job?id=${identity}`)).job;
      if (job?.id !== identity) throw new Error('The linked build identity does not match Studio’s reply.');
      $('build-output').open = activeStates.has(job.state) || job.state === 'failed';
      await handleJob(job);
    } catch (error) { state.operation = null; message(error.message); updateButtons(); }
  }

  (async () => {
    await refreshStatus();
    await refreshFirmwareOptions();
    await Promise.all([refreshDevices(), refreshDevice()]);
    await openLinkedJob();
    setInterval(() => { if (!state.operation && !state.connecting) refreshDevice(); }, 1800);
    setInterval(refreshStatus, 6000);
  })();
})();
