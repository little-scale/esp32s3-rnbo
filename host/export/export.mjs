#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Original adapter for the local RNBO 1.4.4 internal generator. Only a flat,
// self-contained RNBO graph is admitted. The authorized installed package is
// read, never modified; generated code retains its own upstream notices.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { describeFlatPatcher } from './patcher.mjs';
const require = createRequire(import.meta.url);
const args = process.argv.slice(2);
function option(flag, fallback) {
  const i = args.indexOf(flag);
  if (i < 0) return fallback;
  if (i + 1 >= args.length || args[i + 1].startsWith('--')) throw Error(`${flag} needs a value`);
  return args.splice(i, 2)[1];
}
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
function destination(candidate) {
  // Resolve existing parent aliases before checking that the installed package
  // remains read-only. The destination itself must not exist.
  let ancestor = path.resolve(candidate);
  const suffix = [];
  while (!fs.existsSync(ancestor)) {
    suffix.unshift(path.basename(ancestor));
    const parent = path.dirname(ancestor);
    if (parent === ancestor) throw Error('Cannot resolve output destination');
    ancestor = parent;
  }
  return path.join(fs.realpathSync(ancestor), ...suffix);
}
let temporary;
try {
  const outArg = option('--out');
  const voices = Number(option('--voices', '1'));
  if (![1, 2, 4].includes(voices)) throw Error('--voices must be 1, 2, or 4');
  const packageArg = option('--rnbo-dir', process.env.RNBO_DIR);
  if (!outArg || args.length !== 1 || !args[0].endsWith('.rnbopat')) {
    throw Error('Usage: node host/export/export.mjs INPUT.rnbopat --out NEW_EXPORT_DIR [--voices 1|2|4] [--rnbo-dir RNBO_PACKAGE]');
  }
  const input = path.resolve(args[0]);
  const out = destination(outArg);
  if (fs.existsSync(out)) throw Error('Output already exists; choose a fresh export directory');
  const candidates = packageArg ? [packageArg] : [path.join(os.homedir(), 'Documents/Max 9/Packages/RNBO'), '/Applications/Max.app/Contents/Resources/C74/packages/RNBO'];
  const found = candidates.map(p => path.resolve(p)).find(p => fs.existsSync(path.join(p, 'server/node_modules/@rnbo/xam')));
  if (!found) throw Error('Set --rnbo-dir or RNBO_DIR to your authorized RNBO 1.4.4 package');
  const pkg = fs.realpathSync(found);
  const packageRelativeOutput = path.relative(pkg, out);
  if (!packageRelativeOutput || (!packageRelativeOutput.startsWith(`..${path.sep}`) && packageRelativeOutput !== '..' && !path.isAbsolute(packageRelativeOutput))) {
    throw Error('Output must be outside the installed RNBO package');
  }
  const version = JSON.parse(fs.readFileSync(path.join(pkg, 'package-info.json'), 'utf8')).version;
  if (version !== '1.4.4') throw Error(`Internal generator is pinned to RNBO 1.4.4; found ${version}`);
  process.env.RNBO_DIR = pkg;
  process.env.BABEL_DISABLE_CACHE = '1';
  const raw = fs.readFileSync(input);
  if (raw.length > 1024 * 1024) throw Error('Input patch exceeds the initial 1 MiB limit');
  const parsed = JSON.parse(raw.toString('utf8'));
  const xam = require(path.join(pkg, 'server/node_modules/@rnbo/xam'));
  const runner = require(path.join(pkg, 'server/node_modules/@rnbo/xam-runner'));
  const patcher = describeFlatPatcher(parsed.patcher, xam);
  const invocation = runner.createInvocation(xam, patcher, {
    language: 0, classname: 'rnbos3patch', fixedblocksize: 256, fixedsamplerate: 44100,
    polyphony: voices > 1 ? voices : 0, midi: true, presets: false, staterestore: false, probing: false, license: true
  });
  const result = await runner.codegenInvocationStorage.run({reportCodegenProgress: () => {}}, () => invocation.call());
  if (typeof result.code !== 'string' || !result.code || !result.desc) throw Error('Generator returned no source or description');
  fs.mkdirSync(path.dirname(out), {recursive: true});
  temporary = fs.mkdtempSync(path.join(path.dirname(out), '.export-'));
  fs.writeFileSync(path.join(temporary, 'rnbo_source.h'), result.code);
  fs.writeFileSync(path.join(temporary, 'description.json'), JSON.stringify(result.desc, null, 2) + '\n');
  const runtime = path.join(pkg, 'source/rnbo/common');
  fs.cpSync(runtime, path.join(temporary, 'common'), {recursive: true, filter: filename => fs.statSync(filename).isDirectory() || /\.(h|hpp)$/.test(filename)});
  fs.copyFileSync(path.join(pkg, 'source/rnbo/LICENSE'), path.join(temporary, 'RNBO-runtime-LICENSE'));
  fs.writeFileSync(path.join(temporary, 'source.rnbopat'), raw);
  fs.writeFileSync(path.join(temporary, 'generator.json'), JSON.stringify({
    generator: 'rnbo-s3-flat-rnbopat-v2', rnbo_version: version,
    class_name: 'rnbos3patch', sample_rate: 44100, block_frames: 256,
    voices, topology: voices > 1 ? 'polyphonic-export' : 'single-export',
    source_sha256: hash(raw), generated_sha256: hash(result.code),
    adapter_sha256: hash(fs.readFileSync(fileURLToPath(import.meta.url))),
    patcher_adapter_sha256: hash(fs.readFileSync(new URL('./patcher.mjs', import.meta.url))),
    gen_visual_adapter_sha256: hash(fs.readFileSync(new URL('./gen_visual.mjs', import.meta.url))),
    package_info_sha256: hash(fs.readFileSync(path.join(pkg, 'package-info.json'))),
    visual_gen: patcher.boxes.filter(({box})=>box.rnbo_visual_gen).map(({box})=>({
      box_id:box.id,policy:box.rnbo_visual_gen.policy,nodes:box.rnbo_visual_gen.nodes,
      edges:box.rnbo_visual_gen.edges,histories:box.rnbo_visual_gen.history_count,
      operators:box.rnbo_visual_gen.operators,
      source_graph_sha256:hash(JSON.stringify(box.genpatcher)),
      lowered_genexpr_sha256:hash(box.rnbo_visual_gen.expression),
      adapter_sha256:hash(fs.readFileSync(new URL('./gen_visual.mjs',import.meta.url)))
    })),
    generator_package_sha256: Object.fromEntries(['@rnbo/xam', '@rnbo/xam-runner'].map(name => [name,
      hash(fs.readFileSync(path.join(pkg, 'server/node_modules', name, 'package.json')))])),
    note: 'Raw generated code; prepare.py performs independently recorded runtime fixes. No FM1 DSP optimizations.'
  }, null, 2) + '\n');
  if (fs.existsSync(out)) throw Error('Output was created concurrently');
  fs.renameSync(temporary, out);
  temporary = undefined;
  process.stdout.write(JSON.stringify({export: out, class_name: 'rnbos3patch', generated_bytes: Buffer.byteLength(result.code), rnbo_version: version, voices}) + '\n');
} catch (error) {
  if (temporary) fs.rmSync(temporary, {recursive: true, force: true});
  process.stderr.write(`Export failed: ${error.message}\n`);
  process.exitCode = 1;
}
