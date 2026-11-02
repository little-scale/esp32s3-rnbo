// SPDX-License-Identifier: MIT
// Metadata reconstruction for the pinned RNBO 1.4.4 runner. Editable source is
// never changed; message payloads and UI number attributes use native XAM forms.
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
    } else if (box.maxclass === 'flonum') {
      if (box.rnbo_classname !== undefined && box.rnbo_classname !== 'number') throw Error('flonum must describe an RNBO number object');
      if (box.text) throw Error('Unexpected operator text on a flonum UI box');
      box.rnbo_classname = 'number';
      box.rnbo_extra_attributes = {initialFormat: 'float', ...box.rnbo_extra_attributes};
      compilerText = 'number';
    } else if (box.maxclass === 'newobj' && typeof box.text === 'string') {
      compilerText = box.text;
    } else {
      throw Error('Only newobj, message, flonum, comments and panels are supported by this importer');
    }
    const spec = xam.parseBoxText(compilerText);
    if (!spec || spec.xamclass === 'gen~') throw Error(`Unsupported object form: ${compilerText}`);
    // XAM gives explicit text priority over stale extra attributes. This is
    // significant for Max-saved message boxes whose extra text can be empty.
    xam.parseExtraAttributes(spec.xamclass, box.rnbo_extra_attributes, spec.attributes);
    box.rnbo_uniqueid ||= `s3_${box.id}`;
    if (typeof box.rnbo_uniqueid !== 'string' || uniqueIds.has(box.rnbo_uniqueid)) throw Error('RNBO object IDs must be unique');
    uniqueIds.add(box.rnbo_uniqueid);
    if (box.rnbo_serial === undefined) box.rnbo_serial = index;
    if (!Number.isInteger(box.rnbo_serial) || box.rnbo_serial < 0 || box.rnbo_serial > 0x7fffffff) throw Error('Invalid saved RNBO object serial');
    // Serials can repeat across different object classes. Preserve saved
    // values, especially loadbang order, rather than assigning array indices.
    box.rnboinfo = xam.getObjectDescription(xam.createObject(spec.xamclass, spec.attributes));
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
