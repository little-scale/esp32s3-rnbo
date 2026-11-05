// SPDX-License-Identifier: MIT
// Real installed RNBO/XAM admission tests. No vendor code is copied here.
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
const expression = 'History z(0); out1=in1+0.5*z; out2=z+0*in2; z=out1;';
const source = (text = 'gen~', extra = {expr: expression, geninlets: 2, genoutlets: 2}) => ({classnamespace: 'rnbo', boxes: [{box: {id: 'g', maxclass: 'newobj', text, rnbo_extra_attributes: extra}}], lines: []});

test('authored saved GenExpr and text expression use real dynamic port metadata without source mutation', {skip: !available}, () => {
  for (const original of [source(), source('gen~ @expr out1 = in1; @geninlets 1 @genoutlets 1', {})]) {
    const before = structuredClone(original);
    const actual = describeFlatPatcher(original, xam);
    assert.deepEqual(original, before);
    assert.equal(actual.boxes[0].box.rnboinfo.classname, 'gen~');
    const count = original.boxes[0].box.text === 'gen~' ? 2 : 1;
    assert.equal(actual.boxes[0].box.rnboinfo.inputs.length, count);
    assert.equal(actual.boxes[0].box.rnboinfo.outputs.length, count);
  }
  const actual = describeFlatPatcher(source('gen~ @expr out1=in1; @geninlets 1 @genoutlets 1'), xam);
  assert.equal(actual.boxes[0].box.rnboinfo.outputs.length, 1, 'native text priority must override stale saved expression/counts');
});

test('GenExpr file, visual, converted-code and unknown behavioral options fail closed', {skip: !available}, () => {
  for (const option of ['file', 'gencode', 'exposeparams', 'title', 't', 'reset', 'code', 'objects', 'id', 'foo']) {
    assert.throws(() => describeFlatPatcher(source('gen~', {expr: expression, [option]: 'anything'}), xam), /Unsupported GenExpr/);
    assert.throws(() => describeFlatPatcher(source(`gen~ @${option} anything`, {expr: expression}), xam), /Unsupported GenExpr/);
  }
  assert.throws(() => describeFlatPatcher(source('gen~ filename'), xam), /Unsupported GenExpr|positional/);
  const embedded = source(); embedded.boxes[0].box.patcher = {boxes: [], lines: []};
  assert.throws(() => describeFlatPatcher(embedded, xam), /Embedded subpatches/);
  for (const extra of [[], null, {expr: ''}, {expr: '  '}, {expr: '\0'}, {expr: 'x'.repeat(65537)}, {expr: [expression]}, {}]) {
    assert.throws(() => describeFlatPatcher(source('gen~', extra), xam));
  }
});

test('declared GenExpr ports cannot hide code ports, malformed counts or invalid patch connections', {skip: !available}, () => {
  for (const count of [-1, 1.5, '2', 65, Number.NaN, Number.POSITIVE_INFINITY]) {
    assert.throws(() => describeFlatPatcher(source('gen~', {expr: expression, geninlets: count, genoutlets: 2}), xam), /integer/);
    assert.throws(() => describeFlatPatcher(source('gen~', {expr: expression, geninlets: 2, genoutlets: count}), xam), /integer/);
  }
  assert.throws(() => describeFlatPatcher(source('gen~', {expr: expression, geninlets: 2, genoutlets: 0}), xam), /integer/);
  assert.throws(() => describeFlatPatcher(source('gen~', {expr: expression, geninlets: 1, genoutlets: 1}), xam), /declared/);
  const bad = source(); bad.lines.push({patchline: {source: ['g', 2], destination: ['g', 0]}});
  assert.throws(() => describeFlatPatcher(bad, xam), /unsupported RNBO port/);
});

test('autonomous GenExpr accepts zero or omitted signal inputs and publicly exports Main zero-to-two', {skip: !available, timeout: 30000}, () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'rnbo-gen-autonomous-'));
  try {
    for (const [index, expr] of ['out1=0.5;out2=1;', 'out1=noise();out2=0;'].entries()) {
      const graph = source('gen~', {expr, genoutlets: 2, ...(index === 0 ? {geninlets: 0} : {})});
      const described = describeFlatPatcher(graph, xam);
      assert.equal(described.boxes[0].box.rnboinfo.inputs.length, 1, 'Gen retains a base control inlet even without a signal input');
      graph.boxes.push({box: {id: 'left', maxclass: 'newobj', text: 'out~ 1'}}, {box: {id: 'right', maxclass: 'newobj', text: 'out~ 2'}});
      graph.lines.push({patchline: {source: ['g', 0], destination: ['left', 0]}}, {patchline: {source: ['g', 1], destination: ['right', 0]}});
      const input = path.join(temporary, `${index}.rnbopat`), exported = path.join(temporary, `${index}-export`), prepared = path.join(temporary, `${index}-prepared`);
      fs.writeFileSync(input, JSON.stringify({patcher: graph}));
      for (const [exe, args] of [[process.execPath, ['host/export/export.mjs', input, '--out', exported]], ['python3', ['host/compiler/prepare.py', '--export', exported, '--out', prepared, '--class-name', 'rnbos3patch', '--role', 'main']]]) {
        const result = spawnSync(exe, args, {cwd: root, env: process.env, encoding: 'utf8', timeout: 15000});
        assert.equal(result.status, 0, result.stderr + result.stdout);
      }
      const description = JSON.parse(fs.readFileSync(path.join(exported, 'description.json')));
      assert.equal(description.numInputChannels, 0);
      assert.equal(description.numOutputChannels, 2);
    }
  } finally { fs.rmSync(temporary, {recursive: true, force: true}); }
});

test('public exporter rejects native Gen parse failure instead of exporting an empty error fallback', {skip: !available, timeout: 30000}, () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'rnbo-gen-error-'));
  try {
    const input = path.join(temporary, 'invalid.rnbopat');
    const out = path.join(temporary, 'export');
    fs.writeFileSync(input, JSON.stringify({patcher: source('gen~', {expr: '???'})}));
    const result = spawnSync(process.execPath, ['host/export/export.mjs', input, '--out', out], {cwd: root, env: process.env, encoding: 'utf8', timeout: 20000});
    assert.equal(result.status, 1);
    assert.match(result.stderr, /GenExpr did not produce a valid signal object/);
    assert.equal(fs.existsSync(out), false);
  } finally { fs.rmSync(temporary, {recursive: true, force: true}); }
});

test('original history fixtures export through the public fixed-256 route and prepare unchanged source', {skip: !available, timeout: 120000}, () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'rnbo-gen-fixed-'));
  function command(executable, args) {
    const result = spawnSync(executable, args, {cwd: root, env: process.env, encoding: 'utf8', timeout: 50000});
    assert.equal(result.status, 0, result.stderr + result.stdout);
  }
  try {
    for (const name of ['history-feedback', 'two-history-swap']) {
      const input = path.join(root, 'tests/fixtures/gen', `${name}.rnbopat`);
      const exported = path.join(temporary, name, 'export');
      const prepared = path.join(temporary, name, 'prepared');
      command(process.execPath, ['host/export/export.mjs', input, '--out', exported]);
      command('python3', ['host/compiler/prepare.py', '--export', exported, '--out', prepared, '--class-name', 'rnbos3patch', '--role', 'fx']);
      assert.deepEqual(fs.readFileSync(path.join(exported, 'source.rnbopat')), fs.readFileSync(input));
      const description = JSON.parse(fs.readFileSync(path.join(exported, 'description.json')));
      assert.equal(description.numInputChannels, 2);
      assert.equal(description.numOutputChannels, 2);
      assert.equal(description.parameters[0].paramId, 's3_reset');
    }
  } finally { fs.rmSync(temporary, {recursive: true, force: true}); }
});

test('Gen buffer declarations stay visible and unsupported external resources fail normal prepare admission', {skip: !available, timeout: 30000}, () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'rnbo-gen-buffer-'));
  try {
    const input = path.join(temporary, 'buffer.rnbopat');
    const exported = path.join(temporary, 'export');
    const prepared = path.join(temporary, 'prepared');
    const original = JSON.parse(fs.readFileSync(path.join(root, 'tests/fixtures/gen/history-feedback.rnbopat')));
    original.patcher.boxes.find(({box}) => box.id === 'gen').box.rnbo_extra_attributes.expr = 'Buffer external("external"); out1=peek(external,0); out2=in2;';
    fs.writeFileSync(input, JSON.stringify(original));
    const result = spawnSync(process.execPath, ['host/export/export.mjs', input, '--out', exported], {cwd: root, env: process.env, encoding: 'utf8', timeout: 15000});
    assert.equal(result.status, 0, result.stderr + result.stdout);
    const description = JSON.parse(fs.readFileSync(path.join(exported, 'description.json')));
    assert.deepEqual(description.externalDataRefs, [{id: 'external', type: 'Float32Buffer', tag: 'buffer~'}]);
    const admission = spawnSync('python3', ['host/compiler/prepare.py', '--export', exported, '--out', prepared, '--class-name', 'rnbos3patch', '--role', 'fx'], {cwd: root, env: process.env, encoding: 'utf8', timeout: 15000});
    assert.notEqual(admission.status, 0);
    assert.match(admission.stderr, /external|resource/i);
    assert.equal(fs.existsSync(prepared), false, 'rejection must not leave a prepared partial patch');
  } finally { fs.rmSync(temporary, {recursive: true, force: true}); }
});

test('producer variable-block history kernels preserve per-sample state across partitions, reset and reconstruction', {skip: !available, timeout: 120000}, () => {
  // The public module ABI remains fixed-256. Only this producer invocation
  // requests variable block sizes, to observe the generated Gen sample kernel
  // directly at 1/2/odd/256 samples without altering its algorithm or runtime.
  const retain = process.env.GEN_NATIVE_OUT;
  const temporary = retain ? path.resolve(retain) : fs.mkdtempSync(path.join(os.tmpdir(), 'rnbo-gen-native-'));
  if (retain) { assert.equal(fs.existsSync(temporary), false, 'choose a fresh GEN_NATIVE_OUT'); fs.mkdirSync(temporary, {recursive: true}); }
  const summaries = [];
  function command(executable, args, label) {
    const result = spawnSync(executable, args, {cwd: root, env: process.env, encoding: 'utf8', timeout: 45000});
    fs.writeFileSync(path.join(temporary, `${label}.stdout`), result.stdout ?? '');
    fs.writeFileSync(path.join(temporary, `${label}.stderr`), result.stderr ?? '');
    assert.equal(result.status, 0, `${label}: ${result.stderr}${result.stdout}`);
    return result.stdout;
  }
  try {
    const original = fs.readFileSync(path.join(root, 'host/export/export.mjs'), 'utf8');
    assert.equal(original.split('fixedblocksize: 256').length, 2);
    const variable = original.replace('fixedblocksize: 256', 'fixedblocksize: 0')
      .replace('block_frames: 256', 'block_frames: 0')
      .replace("'rnbo-s3-flat-rnbopat-v2'", "'private-genexpr-variable-block-test-v1'");
    const script = path.join(temporary, 'export-variable.mjs');
    fs.writeFileSync(script, variable);
    for (const file of ['patcher.mjs','gen_visual.mjs']) fs.copyFileSync(path.join(root, 'host/export', file), path.join(temporary, file));
    for (const [index, name] of ['history-feedback', 'two-history-swap'].entries()) {
      const exported = path.join(temporary, name, 'export');
      command(process.execPath, [script, path.join(root, 'tests/fixtures/gen', `${name}.rnbopat`), '--out', exported], `${name}-export`);
      const captures = [];
      for (const mode of ['O3', 'UBSan']) {
        const executable = path.join(temporary, name, `probe-${mode}`);
        const flags = mode === 'O3' ? ['-O3'] : ['-O2', '-fsanitize=undefined,float-cast-overflow', '-fno-sanitize-recover=all'];
        command(process.env.CXX ?? 'c++', ['-std=c++17', '-ffp-contract=off', ...flags, `-DGEN_PROGRAM=${index + 1}`, '-I', exported, '-I', path.join(exported, 'common'), path.join(root, 'tests/fixtures/gen/native/probe.cpp'), '-o', executable], `${name}-compile-${mode}`);
        const capture = path.join(temporary, name, `output-${mode}.f32`);
        const summary = JSON.parse(command(executable, [capture], `${name}-run-${mode}`));
        assert.equal(summary.partition_compared_words, 98304);
        assert.equal(summary.reset_actions, 52);
        assert.equal(summary.repeated_prepares, 26);
        assert.ok(summary.maximum_ideal_error <= 2e-6);
        assert.equal(summary.module_abi, false);
        captures.push(fs.readFileSync(capture));
        summaries.push({fixture: name, mode, ...summary});
      }
      assert.deepEqual(captures[0], captures[1], 'O3 and UBSan output captures must match bit for bit');
    }
    fs.writeFileSync(path.join(temporary, 'summaries.json'), JSON.stringify(summaries, null, 2) + '\n');
  } finally { if (!retain) fs.rmSync(temporary, {recursive: true, force: true}); }
});
