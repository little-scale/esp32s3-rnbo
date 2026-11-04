// SPDX-License-Identifier: MIT
// Uses the authorized local RNBO installation, never a mock XAM implementation.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import test from 'node:test';
import {describeFlatPatcher} from './patcher.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const packageDir = process.env.RNBO_DIR ?? path.join(os.homedir(), 'Documents/Max 9/Packages/RNBO');
const available = fs.existsSync(path.join(packageDir, 'server/node_modules/@rnbo/xam'));
process.env.RNBO_DIR = packageDir;
process.env.BABEL_DISABLE_CACHE = '1';
const require = createRequire(import.meta.url);
const xam = available ? require(path.join(packageDir, 'server/node_modules/@rnbo/xam')) : undefined;
const graph = (boxes, lines = []) => ({classnamespace: 'rnbo', boxes: boxes.map(box => ({box})), lines: lines.map(([source, destination]) => ({patchline: {source, destination}}))});
const box = (id, maxclass, text, extra = {}) => ({id, maxclass, ...(text === undefined ? {} : {text}), patching_rect: [0, 0, 50, 20], ...extra});

test('inline physical input metadata survives the real RNBO export with display names and stable IDs', {skip: !available, timeout: 120000}, () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'rnbo-inline-inputs-'));
  try {
    const source = path.join(root, 'examples/physical-inputs.rnbopat');
    const original = fs.readFileSync(source);
    const output = path.join(temporary, 'export');
    const result = spawnSync(process.execPath, ['host/export/export.mjs', source, '--out', output],
      {cwd: root, encoding: 'utf8', timeout: 90000, env: process.env});
    assert.equal(result.status, 0, result.stderr + result.stdout);
    const parameters = JSON.parse(fs.readFileSync(path.join(output, 'description.json'), 'utf8')).parameters;
    for (const [name, type, pin] of [['note', 'analog', 'A0'], ['gate', 'digital', 'D6'], ['accent', 'touch', 'D3']]) {
      const p = parameters.find(p => p.name === name);
      assert.deepEqual(p.meta, {esp32: {type, pin}});
      assert.equal(p.paramId, `s3_${name}`);
      assert.equal(p.displayName, name[0].toUpperCase() + name.slice(1));
    }
    assert.deepEqual(fs.readFileSync(source), original);
  } finally { fs.rmSync(temporary, {recursive: true, force: true}); }
});

test('native message payload and float UI metadata preserve authored data and saved serials', {skip: !available}, () => {
  const source = graph([
    box('load', 'newobj', 'loadbang', {rnbo_serial: 9}),
    box('msg', 'message', '0.5', {rnbo_serial: 9, rnbo_extra_attributes: {text: '', storeempty: 0}}),
    box('num', 'flonum', undefined, {rnbo_serial: 2, rnbo_classname: 'number', rnbo_extra_attributes: {minimum: 0, maximum: 0.99, initialFormat: 'float'}}),
    box('pitch', 'message', '48', {rnbo_serial: 1, rnbo_extra_attributes: {text: ''}})
  ], [[['msg', 0], ['num', 0]]]);
  const original = structuredClone(source);
  const described = describeFlatPatcher(source, xam);
  assert.deepEqual(source, original, 'metadata construction must not mutate editable source');
  assert.deepEqual(described.boxes.map(({box}) => box.rnbo_serial), [9, 9, 2, 1]);
  assert.equal(described.boxes[2].box.rnboinfo.classname, 'number');
  assert.equal(described.boxes[2].box.rnboinfo.outputs.length, 1, 'GUI-only outlet must not become a generated connection');
  for (const text of ['0.5', '48']) {
    const spec = xam.parseBoxText(`message @text ${text}`);
    xam.parseExtraAttributes(spec.xamclass, {text: ''}, spec.attributes);
    assert.equal(String(spec.attributes.text), text, 'native text takes priority over stale saved attributes');
  }
});

test('unsupported GUI ports and ambiguous forms fail before native runner can drop them', {skip: !available}, () => {
  const source = graph([box('n', 'flonum'), box('s', 'newobj', 'sig~')], [[['n', 1], ['s', 0]]]);
  assert.throws(() => describeFlatPatcher(source, xam), /unsupported RNBO port/);
  for (const invalid of [box('n', 'flonum', 'cycle~'), box('n', 'flonum', undefined, {rnbo_classname: 'slider'}), box('n', 'button'), box('n', 'newobj', 'gen~')]) {
    assert.throws(() => describeFlatPatcher(graph([invalid]), xam));
  }
  const repeatedId = graph([box('a', 'message', '1', {rnbo_uniqueid: 'same'}), box('b', 'message', '2', {rnbo_uniqueid: 'same'})]);
  assert.throws(() => describeFlatPatcher(repeatedId, xam), /RNBO object IDs/);
});

test('integer number UI retains native format, optional bounds and source identity', {skip: !available}, () => {
  for (const [extra, expected] of [
    [{}, 'integer'],
    [{format: 0, rnbo_classname: 'number', rnbo_extra_attributes: {initialFormat: 'integer', minimum: '<none>', maximum: '<none>'}}, 'integer'],
    [{format: 6}, 'float'],
    [{format: 0, rnbo_extra_attributes: {initialFormat: 'float'}}, 'float'],
    [{rnbo_extra_attributes: {initialFormat: 0}}, 0],
    [{rnbo_extra_attributes: {initialFormat: undefined}}, 'integer']
  ]) {
    const original = graph([box('integer-ui', 'number', undefined, extra)]);
    const saved = structuredClone(original);
    const actual = describeFlatPatcher(original, xam).boxes[0].box;
    assert.deepEqual(original, saved);
    assert.equal(actual.maxclass, 'number');
    assert.equal(actual.rnbo_classname, 'number');
    assert.equal(actual.rnbo_extra_attributes.initialFormat, expected);
    assert.equal(actual.rnboinfo.outputs.length, 1);
  }
  for (const extra of [{text: 'cycle~'}, {rnbo_classname: 'slider'}, {format: 99},
    {rnbo_extra_attributes: null}, {rnbo_extra_attributes: []},
    {rnbo_extra_attributes: {initialFormat: 'invalid'}}, {rnbo_extra_attributes: {initialFormat: 'INTEGER'}},
    {rnbo_extra_attributes: {initialFormat: null}}]) {
    assert.throws(() => describeFlatPatcher(graph([box('bad-number', 'number', undefined, extra)]), xam));
  }
  assert.throws(() => describeFlatPatcher(graph([box('integer-ui', 'number'), box('signal', 'newobj', 'sig~')],
    [[['integer-ui', 1], ['signal', 0]]]), xam), /unsupported RNBO port/);
  assert.throws(() => describeFlatPatcher(graph([box('specific-box', 'button')]), xam),
    /id="specific-box" maxclass="button"/);
});

test('integer number default truncates while explicit float format retains fractions in actual native DSP', {skip: !available, timeout: 120000}, () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'rnbo-import-integer-ui-'));
  function command(executable, arguments_) {
    const result = spawnSync(executable, arguments_, {cwd: root, encoding: 'utf8', timeout: 90000, env: process.env});
    assert.equal(result.status, 0, result.stderr + result.stdout);
    return result.stdout;
  }
  try {
    const source = graph([
      box('load', 'newobj', 'loadbang'), box('msg', 'message', '-1.75'),
      box('integer', 'number', undefined, {format: 0, rnbo_extra_attributes: {minimum: '<none>', maximum: '<none>'}}),
      box('float', 'number', undefined, {format: 6}),
      box('left-signal', 'newobj', 'sig~'), box('right-signal', 'newobj', 'sig~'),
      box('left', 'newobj', 'out~ 1'), box('right', 'newobj', 'out~ 2')
    ], [[['load', 0], ['msg', 0]], [['msg', 0], ['integer', 0]], [['msg', 0], ['float', 0]],
        [['integer', 0], ['left-signal', 0]], [['float', 0], ['right-signal', 0]],
        [['left-signal', 0], ['left', 0]], [['right-signal', 0], ['right', 0]]]);
    const input = path.join(temporary, 'integer.rnbopat');
    const exported = path.join(temporary, 'export'), prepared = path.join(temporary, 'prepared'), build = path.join(temporary, 'build');
    fs.writeFileSync(input, JSON.stringify({patcher: source}));
    const saved = fs.readFileSync(input);
    command(process.execPath, ['host/export/export.mjs', input, '--out', exported, '--voices', '1']);
    command('python3', ['host/compiler/prepare.py', '--export', exported, '--out', prepared, '--class-name', 'rnbos3patch', '--role', 'main']);
    command('python3', ['host/compiler/build.py', '--export', prepared, '--build-dir', build]);
    const floats = path.join(temporary, 'render.f32');
    const report = JSON.parse(command(path.join(build, 'rnbo_render'), ['--output', path.join(temporary, 'render.wav'), '--float-output', floats, '--warmup', '1', '--blocks', '2']));
    assert.equal(report.errors, 0); assert.equal(report.late_platform_allocations, 0);
    const audio = fs.readFileSync(floats);
    assert.equal(audio.length, 2 * 256 * 2 * 4);
    for (let i = 0; i < audio.length; i += 8) {
      assert.equal(audio.readFloatLE(i), -1, 'integer UI truncates toward zero, not floor or float passthrough');
      assert.equal(audio.readFloatLE(i + 4), -1.75, 'explicit float number UI preserves the fraction');
    }
    assert.deepEqual(fs.readFileSync(input), saved);
    assert.deepEqual(fs.readFileSync(path.join(exported, 'source.rnbopat')), saved);
  } finally { fs.rmSync(temporary, {recursive: true, force: true}); }
});

test('export, prepare and native render retain loadbang message and fractional number clipping', {skip: !available, timeout: 120000}, () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'rnbo-import-ui-'));
  function command(executable, arguments_) {
    const result = spawnSync(executable, arguments_, {cwd: root, encoding: 'utf8', timeout: 90000, env: process.env});
    assert.equal(result.status, 0, result.stderr + result.stdout);
    return result.stdout;
  }
  try {
    const source = graph([
      box('load', 'newobj', 'loadbang', {rnbo_serial: 12}),
      box('msg', 'message', '0.5', {rnbo_serial: 12, rnbo_extra_attributes: {text: ''}}),
      box('num', 'flonum', undefined, {rnbo_extra_attributes: {minimum: 0, maximum: 0.3, initialFormat: 'float'}}),
      box('signal', 'newobj', 'sig~'), box('left', 'newobj', 'out~ 1'), box('right', 'newobj', 'out~ 2')
    ], [[['load', 0], ['msg', 0]], [['msg', 0], ['num', 0]], [['num', 0], ['signal', 0]], [['signal', 0], ['left', 0]], [['signal', 0], ['right', 0]]]);
    const input = path.join(temporary, 'ui.rnbopat');
    const exported = path.join(temporary, 'export');
    const prepared = path.join(temporary, 'prepared');
    const build = path.join(temporary, 'build');
    fs.writeFileSync(input, JSON.stringify({patcher: source}));
    const saved = fs.readFileSync(input);
    command(process.execPath, ['host/export/export.mjs', input, '--out', exported, '--voices', '1']);
    command('python3', ['host/compiler/prepare.py', '--export', exported, '--out', prepared, '--class-name', 'rnbos3patch', '--role', 'main']);
    command('python3', ['host/compiler/build.py', '--export', prepared, '--build-dir', build]);
    const floats = path.join(temporary, 'render.f32');
    const report = JSON.parse(command(path.join(build, 'rnbo_render'), ['--output', path.join(temporary, 'render.wav'), '--float-output', floats, '--warmup', '1', '--blocks', '2']));
    assert.equal(report.errors, 0);
    assert.equal(report.late_platform_allocations, 0);
    const audio = fs.readFileSync(floats);
    assert.equal(audio.length, 2 * 256 * 2 * 4);
    for (let i = 0; i < audio.length; i += 4) assert.ok(Math.abs(audio.readFloatLE(i) - 0.3) < 1e-7, 'loadbang must emit saved0.5, number must retain fraction and clamp to0.3');
    assert.deepEqual(fs.readFileSync(input), saved);
    assert.deepEqual(fs.readFileSync(path.join(exported, 'source.rnbopat')), saved);
  } finally {
    fs.rmSync(temporary, {recursive: true, force: true});
  }
});
