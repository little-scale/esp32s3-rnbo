// SPDX-License-Identifier: MIT
// Uses the authorised installed producer; no generated RNBO body is vendored.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import test from 'node:test';
import {inspectGraph} from './inspect_onepole_graph.mjs';

const pkg = process.env.RNBO_DIR ?? path.join(os.homedir(), 'Documents/Max 9/Packages/RNBO');
const available = fs.existsSync(path.join(pkg, 'server/node_modules/@rnbo/xam'));
process.env.RNBO_DIR = pkg;
process.env.BABEL_DISABLE_CACHE = '1';
const require = createRequire(import.meta.url);
const xam = available ? require(path.join(pkg, 'server/node_modules/@rnbo/xam')) : undefined;
const graph = texts => ({patcher: {classnamespace: 'rnbo',
  boxes: texts.map((text, i) => ({box: {id: String(i), maxclass: 'newobj', text}})), lines: []}});

test('builtin arithmetic, literal-looking parameter ID and graph source are preserved', {skip: !available}, () => {
  const source = graph(['in~ 1', 'out~ 1', 'onepole~ 0.05', 'param onepole_tilde_01_b1 1000', '+~', '*~ 0.25']);
  const before = structuredClone(source);
  const record = inspectGraph(source, xam);
  assert.equal(record.objects.filter(obj => obj.converted_builtin).length, 2);
  assert.deepEqual(source, before);
});

test('custom code, dependency and class overrides are rejected', {skip: !available}, () => {
  for (const text of ['codebox~', 'expr~ in1', 'gen~', 'rnbo~', 'onepole~ #1']) {
    assert.throws(() => inspectGraph(graph(['onepole~', text]), xam));
  }
  assert.throws(() => inspectGraph(graph(['onepole~ @freqInHz 1234.5']), xam), /not interpreted/);
  for (const text of ['+~ @file custom', '*~ @objects custom', 'onepole~ @code custom',
    'param cutoff 1000 @fromnormalized value*value',
    'param cutoff 1000 @tonormalized sqrt(value)', 'param cutoff 1000 @ctlin 1',
    'param cutoff 1000 @id identifier.with.dot']) {
    assert.throws(() => inspectGraph(graph(['onepole~', text]), xam));
  }
  for (const extra of [{code: 'x'}, {objects: []}, {expr: 'out1 = 0'}, {classname: 'codebox~'},
    {fromnormalized: 'value*value'}, {tonormalized: 'sqrt(value)'}, {ctlin: 1}, {id: 'identifier.with.dot'}]) {
    const source = graph(['onepole~', '+~']);
    source.patcher.boxes[1].box.rnbo_extra_attributes = extra;
    assert.throws(() => inspectGraph(source, xam));
  }
  const source = graph(['onepole~']);
  source.patcher.boxes[0].box.rnbo_classname = 'codebox~';
  assert.throws(() => inspectGraph(source, xam), /Saved object class/);
});

test('flatness, port validity and genuine Hz filter presence are required', {skip: !available}, () => {
  assert.throws(() => inspectGraph(graph(['cycle~']), xam), /No Hz onepole/);
  const embedded = graph(['onepole~']);
  embedded.patcher.boxes[0].box.patcher = {};
  assert.throws(() => inspectGraph(embedded, xam), /Embedded/);
  const port = graph(['in~ 1', 'onepole~']);
  port.patcher.lines.push({patchline: {source: ['0', 5], destination: ['1', 0]}});
  assert.throws(() => inspectGraph(port, xam), /unsupported RNBO port/);
});
