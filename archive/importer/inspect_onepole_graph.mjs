#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Preflight for the regenerated stable-onepole route. This does not generate
// code, modify the patch, or alter the installed, authorised RNBO package.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {describeFlatPatcher} from './patcher.mjs';

const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
// An operator-class policy, never a whitelist of individual patch hashes.
// Other builtin classes can be added after reviewing their ownership model.
const BUILTINS = new Set([
  'in~', 'out~', 'param', 'sig~', 'cycle~', 'phasor~', 'noise~',
  'onepole~', 'onepole_lin~', 'feedback~', 'loadbang', 'message', 'number'
]);
const OPERATORS = new Set(['+', '-', '*', '/', '+~', '-~', '*~', '/~']);
const CODE_ATTRIBUTES = new Set([
  'code', 'codebody', 'expr', 'file', 'filename', 'objects', 'parentInfo',
  'abstraction', 'dependencies', 'includes', 'external', 'isConvertedOperator',
  'classname', 'serialclassname', 'id', 'tonormalized', 'fromnormalized', 'ctlin'
]);

export function inspectGraph(source, xam) {
  const patcher = source?.patcher;
  if (!patcher || !Array.isArray(patcher.boxes)) throw Error('A flat RNBO graph is required');
  const objects = [];
  for (const {box} of patcher.boxes) {
    if (!box || typeof box !== 'object') throw Error('Malformed graph box');
    if (box.maxclass === 'comment' || box.maxclass === 'panel') continue;
    let text;
    if (box.maxclass === 'message') {
      text = box.text ? `message @text ${box.text}` : 'message';
    } else if (box.maxclass === 'flonum') {
      text = 'number';
    } else if (box.maxclass === 'newobj' && typeof box.text === 'string') {
      text = box.text;
    } else {
      throw Error('Unsupported box form for regenerated onepole');
    }
    // The runner substitutes these before parsing. Their class/ownership
    // interpretation is outside this first flat-graph admission envelope.
    if (/#\d+/.test(text)) throw Error('Patcher argument substitution is not supported');
    const surface = text.trim().split(/\s+/)[0];
    if (!BUILTINS.has(surface) && !OPERATORS.has(surface)) {
      throw Error(`Unsupported regenerated-onepole object: ${surface}`);
    }
    const spec = xam.parseBoxText(text);
    if (!spec) throw Error(`Cannot parse ${surface}`);
    const identity = ['classname', 'serialclassname', 'expr', 'isConvertedOperator'];
    const before = JSON.stringify(identity.map(key => spec.attributes[key]));
    if (OPERATORS.has(surface)) {
      const builtin = xam.parseBoxText(surface);
      if (!builtin || spec.xamclass !== builtin.xamclass ||
          spec.attributes.isConvertedOperator !== true ||
          spec.attributes.serialclassname !== surface ||
          spec.attributes.expr !== builtin.attributes.expr) {
        throw Error('Only builtin arithmetic expressions are admitted');
      }
    } else if (spec.xamclass !== surface) {
      throw Error('Unexpected builtin class translation');
    }
    if (box.rnbo_classname !== undefined &&
        ![surface, spec.xamclass].includes(box.rnbo_classname)) {
      throw Error('Saved object class differs from parsed object');
    }
    const extra = box.rnbo_extra_attributes;
    if (extra !== undefined && (!extra || typeof extra !== 'object' || Array.isArray(extra))) {
      throw Error('Saved attributes must be an object');
    }
    // The pinned text parser lowercases @freqInHz to an unknown property,
    // silently retaining the default cutoff. A positional argument or the
    // exact saved attribute name is required; do not qualify ignored intent.
    if (surface === 'onepole~' && (Object.hasOwn(spec.attributes, 'freqinhz') ||
        (extra && Object.hasOwn(extra, 'freqinhz')))) {
      throw Error('onepole~ @freqInHz text is not interpreted by RNBO 1.4.4; use a positional cutoff');
    }
    if (extra && Object.keys(extra).some(key => CODE_ATTRIBUTES.has(key))) {
      throw Error('Code/class/dependency attributes are not admitted');
    }
    xam.parseExtraAttributes(spec.xamclass, extra, spec.attributes);
    if (JSON.stringify(identity.map(key => spec.attributes[key])) !== before) {
      throw Error('Saved attributes change object implementation');
    }
    // Reject dependency/code properties in text too. Only converted arithmetic
    // may carry the expression and conversion marker established above.
    const generatedKeys = new Set(['classname', 'serialclassname',
      ...(OPERATORS.has(surface) ? ['expr', 'isConvertedOperator'] : [])]);
    if (Object.keys(spec.attributes).some(key =>
      CODE_ATTRIBUTES.has(key) && !generatedKeys.has(key))) {
      throw Error('Custom code or dependencies are not admitted');
    }
    objects.push({id: box.id, surface, canonical_class: spec.xamclass,
      converted_builtin: OPERATORS.has(surface)});
  }
  // Validate the same port descriptions, flatness and IDs as the real exporter.
  describeFlatPatcher(patcher, xam);
  if (!objects.some(obj => obj.surface === 'onepole~')) throw Error('No Hz onepole~ object found');
  return {policy: 'flat-builtin-onepole-v1', objects};
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 1 || !args[0].endsWith('.rnbopat')) {
    throw Error('Usage: node inspect_onepole_graph.mjs INPUT.rnbopat');
  }
  const candidates = process.env.RNBO_DIR ? [process.env.RNBO_DIR] : [
    path.join(os.homedir(), 'Documents/Max 9/Packages/RNBO'),
    '/Applications/Max.app/Contents/Resources/C74/packages/RNBO'
  ];
  const found = candidates.find(dir => fs.existsSync(path.join(dir, 'server/node_modules/@rnbo/xam')));
  if (!found) throw Error('Set RNBO_DIR to your authorised RNBO 1.4.4 package');
  const pkg = fs.realpathSync(found);
  const packageInfo = fs.readFileSync(path.join(pkg, 'package-info.json'));
  if (JSON.parse(packageInfo).version !== '1.4.4') throw Error('RNBO 1.4.4 is required');
  process.env.RNBO_DIR = pkg;
  process.env.BABEL_DISABLE_CACHE = '1';
  const raw = fs.readFileSync(args[0]);
  if (raw.length > 1024 * 1024) throw Error('Input patch exceeds 1 MiB');
  const require = createRequire(import.meta.url);
  const xam = require(path.join(pkg, 'server/node_modules/@rnbo/xam'));
  const result = inspectGraph(JSON.parse(raw), xam);
  process.stdout.write(JSON.stringify({...result, rnbo_version: '1.4.4',
    package_directory: pkg, source_sha256: hash(raw),
    package_info_sha256: hash(packageInfo),
    generator_package_sha256: Object.fromEntries(['@rnbo/xam', '@rnbo/xam-runner'].map(name =>
      [name, hash(fs.readFileSync(path.join(pkg, 'server/node_modules', name, 'package.json')))])),
    inspector_sha256: hash(fs.readFileSync(fileURLToPath(import.meta.url))),
    patcher_adapter_sha256: hash(fs.readFileSync(new URL('./patcher.mjs', import.meta.url)))
  }) + '\n');
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => {
    process.stderr.write(`Onepole graph inspection failed: ${error.message}\n`);
    process.exitCode = 1;
  });
}
