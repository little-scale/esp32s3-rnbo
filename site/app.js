const $ = id => document.getElementById(id);
const statuses = new Set(['board', 'in_patch', 'native', 'partial', 'unverified', 'unsupported', 'not_applicable']);
const optimisations = new Set(['available', 'experimental', 'none', 'unassessed']);
const rank = {board: 0, in_patch: 1, partial: 2, native: 3, unsupported: 4, unverified: 5, not_applicable: 6};
const optimisationRank = {available: 0, experimental: 1, none: 2, unassessed: 3};
const collator = new Intl.Collator('en', {numeric: true, sensitivity: 'base'});
const state = {objects: [], filter: 'all', sort: 'name', direction: 1, expanded: new Set()};

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}
function link(label, url) {
  const parsed = new URL(url, location.href);
  if (!['https:', 'http:'].includes(parsed.protocol)) throw Error('Unsupported source URL');
  const node = element('a', label); node.href = parsed.href;
  return node;
}
function boardEvidence(row) { return ['board', 'in_patch', 'partial'].includes(row.working.status) && row.board_evidence === true; }
function performanceValue(row) { return row.performance?.percent ?? -Infinity; }

function details(row) {
  const tr = element('tr', null, 'detail-row'); tr.id = `detail-${row.id}`;
  const cell = element('td'); cell.colSpan = 4;
  const panel = element('div', null, 'detail-panel');
  const scope = element('div'); scope.append(element('h3', 'Tested scope'));
  scope.append(element('p', row.working.detail || 'No qualifying verification is recorded for this spelling and surface.'));
  if (row.optimisation.detail) scope.append(element('p', row.optimisation.detail));
  if (row.aliases?.length) scope.append(element('p', `Aliases: ${row.aliases.join(', ')}`, 'detail-aliases'));
  if (row.canonical_name && row.canonical_name !== row.name) scope.append(element('p', `Canonical name: ${row.canonical_name}`, 'detail-aliases'));
  if (row.performance?.detail) scope.append(element('p', row.performance.detail));
  const sources = element('div'); sources.append(element('h3', 'Sources & results'));
  const list = element('ul');
  for (const source of row.sources || []) { const item = element('li'); item.append(link(source.label, source.url)); list.append(item); }
  if (row.reference_url) { const item = element('li'); item.append(link('RNBO reference', row.reference_url)); list.append(item); }
  if (!list.children.length) sources.append(element('p', 'No measured result is recorded yet.'));
  else sources.append(list);
  panel.append(scope, sources); cell.append(panel); tr.append(cell); return tr;
}

function rowNode(row) {
  const tr = element('tr', null, 'object-row');
  const name = element('td'); name.append(element('div', row.name, 'object-name'));
  const meta = element('div', null, 'object-meta');
  meta.append(element('span', row.surface === 'codebox' ? 'codebox' : row.surface === 'host' ? 'host/editor' : 'patcher', 'surface-tag'));
  if (row.is_alias) meta.append(element('span', 'alias', 'alias-tag'));
  if (row.category) meta.append(element('span', row.category));
  name.append(meta);
  const toggle = element('button', state.expanded.has(row.id) ? 'Close details' : 'Scope & evidence', 'detail-toggle');
  toggle.type = 'button'; toggle.setAttribute('aria-expanded', String(state.expanded.has(row.id)));
  toggle.setAttribute('aria-controls', `detail-${row.id}`); toggle.setAttribute('aria-label', `${toggle.textContent}: ${row.name}, ${row.surface}`);
  toggle.addEventListener('click', () => {
    if (state.expanded.has(row.id)) {state.expanded.delete(row.id); document.getElementById(`detail-${row.id}`)?.remove();}
    else {state.expanded.add(row.id); tr.after(details(row));}
    toggle.textContent = state.expanded.has(row.id) ? 'Close details' : 'Scope & evidence';
    toggle.setAttribute('aria-expanded', String(state.expanded.has(row.id)));
    toggle.setAttribute('aria-label', `${toggle.textContent}: ${row.name}, ${row.surface}`);
  });
  name.append(toggle);
  const working = element('td'); working.append(element('div', row.working.label, `badge ${row.working.status}`));
  if (row.working.short) working.append(element('div', row.working.short, 'subtext'));
  const optimisation = element('td'); optimisation.append(element('div', row.optimisation.label, `optimisation-label ${row.optimisation.status}`));
  if (row.optimisation.short) optimisation.append(element('div', row.optimisation.short, 'subtext'));
  const performance = element('td');
  if (row.performance) {
    performance.append(element('div', row.performance.label, `percentage ${row.performance.phase === 'experimental' ? 'experimental' : ''}`));
    performance.append(element('div', row.performance.scope || 'Whole test patch', 'subtext'));
  } else performance.append(element('div', '—', 'percentage unmeasured'));
  tr.append(name, working, optimisation, performance); return tr;
}

function render() {
  const query = $('search').value.trim().toLocaleLowerCase();
  const surface = $('surface').value; const optimisation = $('optimisation').value;
  const rows = state.objects.filter(row => {
    const working = row.working.status;
    if (surface !== 'all' && row.surface !== surface) return false;
    if (optimisation !== 'all' && row.optimisation.status !== optimisation) return false;
    if (state.filter === 'board' && !boardEvidence(row)) return false;
    if (state.filter === 'native' && working !== 'native') return false;
    if (state.filter === 'partial' && !['partial', 'unsupported'].includes(working)) return false;
    if (state.filter === 'unverified' && working !== 'unverified') return false;
    return !query || [row.name, row.canonical_name, row.category, ...(row.aliases || [])].filter(Boolean).join(' ').toLocaleLowerCase().includes(query);
  });
  rows.sort((a, b) => {
    let result;
    if (state.sort === 'working') result = rank[a.working.status] - rank[b.working.status];
    else if (state.sort === 'optimisation') result = optimisationRank[a.optimisation.status] - optimisationRank[b.optimisation.status];
    else if (state.sort === 'performance') {
      const av = performanceValue(a), bv = performanceValue(b);
      result = av === bv ? 0 : av < bv ? -1 : 1;
    } else result = collator.compare(a.name, b.name);
    return state.direction * result || collator.compare(a.name, b.name) || collator.compare(a.surface, b.surface);
  });
  const fragment = document.createDocumentFragment();
  for (const row of rows) { fragment.append(rowNode(row)); if (state.expanded.has(row.id)) fragment.append(details(row)); }
  if (!rows.length) { const tr = element('tr'); const td = element('td', 'No matching names. Try a different search or filter.', 'empty'); td.colSpan = 4; tr.append(td); fragment.append(tr); }
  $('rows').replaceChildren(fragment);
  $('result-count').textContent = `${rows.length.toLocaleString()} of ${state.objects.length.toLocaleString()} names`;
  const params = new URLSearchParams();
  if (query) params.set('q', $('search').value.trim());
  if (surface !== 'all') params.set('surface', surface);
  if (optimisation !== 'all') params.set('optimisation', optimisation);
  if (state.filter !== 'all') params.set('status', state.filter);
  if (state.sort !== 'name') params.set('sort', state.sort);
  if (state.direction !== (state.sort === 'performance' ? -1 : 1)) params.set('direction', String(state.direction));
  history.replaceState(null, '', `${location.pathname}${params.size ? `?${params}` : ''}${location.hash}`);
  for (const button of document.querySelectorAll('[data-sort]')) {
    const selected = button.dataset.sort === state.sort;
    if (selected) button.closest('th').setAttribute('aria-sort', state.direction === 1 ? 'ascending' : 'descending');
    else button.closest('th').removeAttribute('aria-sort');
    button.querySelector('span').textContent = selected ? (state.direction === 1 ? '↑' : '↓') : '↕';
  }
}

async function start() {
  const response = await fetch('./data/status.json'); if (!response.ok) throw Error(`Inventory HTTP ${response.status}`);
  const data = await response.json();
  if (data.schema_version !== 1 || !Array.isArray(data.objects) || !data.objects.length) throw Error('Invalid inventory');
  const ids = new Set();
  for (const row of data.objects) {
    if (typeof row.id !== 'string' || ids.has(row.id) || typeof row.name !== 'string' || !['patcher', 'codebox', 'host'].includes(row.surface) || !statuses.has(row.working?.status) || !optimisations.has(row.optimisation?.status)) throw Error('Invalid inventory row');
    if (row.performance && (!Number.isFinite(row.performance.percent) || !row.performance.label || !['available', 'experimental'].includes(row.performance.phase))) throw Error('Invalid measurement');
    ids.add(row.id);
  }
  state.objects = data.objects;
  $('version').textContent = `RNBO ${data.rnbo_version}`;
  $('total').textContent = data.objects.length.toLocaleString();
  $('board-count').textContent = data.objects.filter(boardEvidence).length.toLocaleString();
  $('pending-count').textContent = data.objects.filter(row => row.working.status === 'unverified').length.toLocaleString();
  $('inventory-scope').textContent = data.inventory_summary;
  $('scope-note').textContent = data.scope_note;
  $('updated').textContent = `Evidence snapshot · ${data.evidence_updated}`;
  for (const source of data.inventory_sources || []) $('inventory-sources').append(link(source.label, source.url));
  const params = new URLSearchParams(location.search);
  $('search').value = params.get('q') || '';
  if (['patcher', 'codebox', 'host'].includes(params.get('surface'))) $('surface').value = params.get('surface');
  if (optimisations.has(params.get('optimisation'))) $('optimisation').value = params.get('optimisation');
  if (['board', 'native', 'partial', 'unverified'].includes(params.get('status'))) state.filter = params.get('status');
  if (['name', 'working', 'optimisation', 'performance'].includes(params.get('sort'))) state.sort = params.get('sort');
  state.direction = params.get('direction') === '-1' ? -1 : params.get('direction') === '1' ? 1 : state.sort === 'performance' ? -1 : 1;
  for (const button of document.querySelectorAll('[data-filter]')) {
    const selected = button.dataset.filter === state.filter;
    button.classList.toggle('active', selected); button.setAttribute('aria-pressed', String(selected));
    button.addEventListener('click', () => {
      state.filter = button.dataset.filter;
      for (const other of document.querySelectorAll('[data-filter]')) { const on = other === button; other.classList.toggle('active', on); other.setAttribute('aria-pressed', String(on)); }
      render();
    });
  }
  let timer;
  $('search').addEventListener('input', () => {clearTimeout(timer); timer = setTimeout(render, 100);});
  for (const id of ['surface', 'optimisation']) $(id).addEventListener('change', render);
  for (const button of document.querySelectorAll('[data-sort]')) button.addEventListener('click', () => {
    const key = button.dataset.sort;
    state.direction = state.sort === key ? -state.direction : key === 'performance' ? -1 : 1; state.sort = key; render();
  });
  render();
}
start().catch(error => {
  console.error(error);
  const tr = element('tr'); const cell = element('td', 'The inventory could not be loaded. Please reload, or use the data download.', 'empty'); cell.colSpan = 4; cell.setAttribute('role', 'alert'); tr.append(cell); $('rows').replaceChildren(tr); $('result-count').textContent = 'Inventory unavailable';
});
