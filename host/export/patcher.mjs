// SPDX-License-Identifier: MIT
// Metadata reconstruction for the pinned RNBO 1.4.4 runner. Editable source is
// never changed; message payloads and UI number attributes use native XAM forms.
import { lowerVisualGen } from './gen_visual.mjs';
const genOptions = new Set(['expr', 'geninlets', 'genoutlets']);
const numberFormats = ['integer', 'hex', 'octal', 'binary', 'midi', 'midi_c4', 'float'];

function numberAttributes(box) {
  if (box.rnbo_classname !== undefined && box.rnbo_classname !== 'number') throw Error(`${box.maxclass} must describe an RNBO number object`);
  if (box.text !== undefined && box.text !== '') throw Error(`Unexpected operator text on a ${box.maxclass} UI box`);
  const extra = box.rnbo_extra_attributes;
  if (extra !== undefined && (!extra || typeof extra !== 'object' || Array.isArray(extra))) throw Error('Number UI saved attributes must be an object');
  if (box.format !== undefined && (!Number.isInteger(box.format) || box.format < 0 || box.format >= numberFormats.length)) throw Error('Unsupported number UI format');
  // XAM's number class itself defaults to Float. Max's integer number UI must
  // explicitly supply its distinct initial format. Saved native initialFormat
  // has priority; the GUI format/default is only a missing-metadata fallback.
  const initialFormat = extra?.initialFormat ?? (box.format === undefined ? (box.maxclass === 'number' ? 'integer' : 'float') : numberFormats[box.format]);
  if (!(Number.isInteger(initialFormat) && initialFormat >= 0 && initialFormat < numberFormats.length) &&
      !(typeof initialFormat === 'string' && numberFormats.includes(initialFormat))) throw Error('Unsupported RNBO number initialFormat');
  if (extra?.initialFormat === null) throw Error('Unsupported RNBO number initialFormat');
  box.rnbo_classname = 'number';
  box.rnbo_extra_attributes = {initialFormat, ...extra};
  box.rnbo_extra_attributes.initialFormat = initialFormat;
}

function genExpression(spec, extra, xam) {
  // This route describes authored GenExpr, not a .gendsp loader. XAM ignores
  // unknown options and its file-only form can produce an empty perform method.
  // Check both sources before text-priority merging can conceal an option.
  if (extra !== undefined && (!extra || typeof extra !== 'object' || Array.isArray(extra))) {
    throw Error('GenExpr saved attributes must be an object');
  }
  for (const [key, value] of Object.entries(extra ?? {})) {
    if (!genOptions.has(key)) throw Error(`Unsupported GenExpr saved option: ${key}`);
    if (key === 'expr' && typeof value !== 'string') throw Error('Saved GenExpr code must be a string');
  }
  for (const key of Object.keys(spec.attributes)) {
    if (!genOptions.has(key) && key !== 'classname' && key !== 'defaultArgs') {
      throw Error(`Unsupported GenExpr text option: ${key}`);
    }
  }
  if (spec.attributes.defaultArgs?.length) throw Error('GenExpr positional file/title forms are not implemented');
  xam.parseExtraAttributes(spec.xamclass, extra, spec.attributes);
  const expression = spec.attributes.expr;
  if (typeof expression !== 'string' && !(Array.isArray(expression) && expression.length && expression.every(v => typeof v === 'string' || (typeof v === 'number' && Number.isFinite(v))))) {
    throw Error('gen~ requires explicit authored GenExpr code in expr');
  }
  const code = xam.Expression.consolidateExpression(expression);
  if (typeof code !== 'string' || !code.trim() || code.includes('\0') || code.length > 65536) {
    throw Error('GenExpr code must be nonempty, without NUL, and at most 65536 characters');
  }
  for (const key of ['geninlets', 'genoutlets']) {
    const count = spec.attributes[key];
    const minimum = key === 'geninlets' ? 0 : 1;
    if (count !== undefined && (!Number.isInteger(count) || count < minimum || count > 64)) {
      throw Error(`GenExpr ${key} must be an integer from ${minimum} to 64`);
    }
  }
}

export function describeFlatPatcher(source, xam) {
  const patcher = structuredClone(source);
  if (!patcher || patcher.classnamespace !== 'rnbo' || !Array.isArray(patcher.boxes) || !Array.isArray(patcher.lines)) {
    throw Error('A standalone RNBO patcher graph is required');
  }
  if (patcher.boxes.length > 2048 || patcher.lines.length > 8192) throw Error('Patch exceeds the initial graph limit');
  const ids = new Set();
  const uniqueIds = new Set();
  const metadata = new Map();
  patcher.boxes.forEach(({box}, index) => {
    if (!box || typeof box.id !== 'string' || !box.id || ids.has(box.id)) throw Error('Box IDs must be unique');
    ids.add(box.id);
    if (box.patcher || box.rnbo_abstraction || box.filename) throw Error('Embedded subpatches and external dependencies are not implemented by this importer');
    if (box.maxclass === 'comment' || box.maxclass === 'panel') return;
    let compilerText;
    if (box.maxclass === 'message') {
      if (box.text !== undefined && typeof box.text !== 'string') throw Error('Message text must be a string');
      // Exactly the runner's message rule; leave maxclass/text intact so it
      // applies that rule once during the real invocation, not twice.
      box.rnbo_classname = 'message';
      compilerText = box.text ? `message @text ${box.text}` : 'message';
    } else if (box.maxclass === 'flonum' || box.maxclass === 'number') {
      numberAttributes(box);
      compilerText = 'number';
    } else if (box.maxclass === 'newobj' && typeof box.text === 'string') {
      compilerText = box.text;
    } else {
      throw Error(`Unsupported box id=${JSON.stringify(box.id)} maxclass=${JSON.stringify(box.maxclass)}: only newobj, message, number, flonum, comments and panels are supported by this importer`);
    }
    const spec = xam.parseBoxText(compilerText);
    if (!spec) throw Error(`Unsupported object form: ${compilerText}`);
    if (box.genpatcher!==undefined) {
      if (spec.xamclass!=='gen~') throw Error('genpatcher is only valid on an embedded gen~');
      const extra=box.rnbo_extra_attributes;
      if (extra!==undefined && (!extra || typeof extra!=='object' || Array.isArray(extra))) throw Error('Visual Gen saved attributes must be an object');
      for (const attrs of [spec.attributes,extra??{}])for (const [key,value] of Object.entries(attrs)) {
        if (key==='classname')continue;
        if (key==='defaultArgs' && Array.isArray(value) && !value.length)continue;
        if (key==='exposeparams' && (value===0 || value===false))continue;
        throw Error(`Unsupported or ambiguous visual Gen option: ${key}`);
      }
      const lowered=lowerVisualGen(box.genpatcher);
      spec.attributes={expr:lowered.expression,geninlets:lowered.geninlets,genoutlets:lowered.genoutlets};
      box.rnbo_extra_attributes={...spec.attributes};
      box.rnbo_visual_gen=lowered;
    }

    // XAM gives explicit text priority over stale extra attributes. This is
    // significant for Max-saved message boxes whose extra text can be empty.
    if (spec.xamclass === 'gen~') genExpression(spec, box.rnbo_extra_attributes, xam);
    else xam.parseExtraAttributes(spec.xamclass, box.rnbo_extra_attributes, spec.attributes);
    box.rnbo_uniqueid ||= `s3_${box.id}`;
    if (typeof box.rnbo_uniqueid !== 'string' || uniqueIds.has(box.rnbo_uniqueid)) throw Error('RNBO object IDs must be unique');
    uniqueIds.add(box.rnbo_uniqueid);
    if (box.rnbo_serial === undefined) box.rnbo_serial = index;
    if (!Number.isInteger(box.rnbo_serial) || box.rnbo_serial < 0 || box.rnbo_serial > 0x7fffffff) throw Error('Invalid saved RNBO object serial');
    // Serials can repeat across different object classes. Preserve saved
    // values, especially loadbang order, rather than assigning array indices.
    const object = xam.createObject(spec.xamclass, spec.attributes);
    box.rnboinfo = xam.getObjectDescription(object);
    if (spec.xamclass === 'gen~') {
      // RNBO 1.4.4 can report a Gen parse error without throwing. Finalize sets
      // expr=true only on success; never export its empty error fallback.
      if (object.expr !== true || !box.rnboinfo.inputs?.length || !box.rnboinfo.outputs?.length || box.rnboinfo.inputs.length > 64 || box.rnboinfo.outputs.length > 64) {
        throw Error('GenExpr did not produce a valid signal object');
      }
      for (const [key, ports] of [['geninlets', 'inputs'], ['genoutlets', 'outputs']]) {
        // Gen always retains its base control inlet, including autonomous
        // expressions whose saved Gen signal-input count is zero.
        const declared = key === 'geninlets' ? Math.max(1, spec.attributes[key]) : spec.attributes[key];
        if (spec.attributes[key] !== undefined && box.rnboinfo[ports].length !== declared) {
          throw Error(`GenExpr code exceeds its declared ${key}`);
        }
      }
    }
    metadata.set(box.id, box.rnboinfo);
  });
  patcher.lines.forEach(({patchline}) => {
    for (const endpoint of [patchline?.source, patchline?.destination]) {
      if (!Array.isArray(endpoint) || endpoint.length !== 2 || !ids.has(endpoint[0]) || !Number.isInteger(endpoint[1]) || endpoint[1] < 0) throw Error('Malformed patch connection');
    }
    if (patchline.disabled) return;
    const [sourceId, outlet] = patchline.source;
    const [destinationId, inlet] = patchline.destination;
    if (outlet >= (metadata.get(sourceId)?.outputs?.length ?? 0) || inlet >= (metadata.get(destinationId)?.inputs?.length ?? 0)) {
      throw Error(`Connection references an unsupported RNBO port: ${sourceId}:${outlet} -> ${destinationId}:${inlet}`);
    }
  });
  return patcher;
}
