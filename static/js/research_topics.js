// Research topics panel (fork module; notes item 71).
//
// Opened from the left icon bar and the sidebar tools list (below Deep
// Research). Built from the Brain panel's own classes (memory-modal-content,
// memory-tabs, admin-card, memory-item) so it looks and themes the same.
//   Topics tab:   one card per topic like a memory — name, example queries,
//                 counts, an on/off switch, edit and delete.
//   Settings tab: the relevance filter (on/off, cut-off, candidates, decision
//                 log) and the topic-matching similarity.
// Reads GET /api/research-topics and /api/web-filter/settings; saving is admin only.

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

const ICON = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:6px"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>';
const LIST_ICON = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>';
const GEAR_ICON = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>';

let _modal = null;
let _data = null;       // {min_similarity, topics:[...], other:{...}}
let _filter = null;     // {web_filter_enabled, web_filter_threshold, ...}
let _editing = null;    // index of the topic being edited, 'new' or null

// ── rendering ──

function badge(text, title) {
  return '<span class="memory-cat-badge"' + (title ? ' title="' + esc(title) + '"' : '') + '>' + esc(text) + '</span>';
}

function metaFor(t) {
  const r = t.ratings || { up: 0, down: 0 };
  return badge((t.searches || 0) + ' searches', 'Web searches assigned to this topic (from the decision log)')
    + badge(r.up + ' up · ' + r.down + ' down', 'Your source ratings in this topic')
    + (t.enabled === false ? badge('off') : '');
}

function topicItem(t, idx) {
  if (_editing === idx) return editItem(t, idx);
  return '<div class="memory-item rt-item" data-idx="' + idx + '">'
    + '<div class="memory-item-content">'
    + '<span class="memory-item-text rt-name">' + esc(t.name) + '</span>'
    + '<span class="rt-examples">' + esc((t.examples || []).join(' · ')) + '</span>'
    + '<div class="memory-item-meta">' + metaFor(t) + '</div>'
    + '</div>'
    + '<div class="rt-item-side">'
    + '<label class="admin-switch" title="Use this topic"><input type="checkbox" class="rt-on" aria-label="Use this topic"'
    + (t.enabled !== false ? ' checked' : '') + ' /><span class="admin-slider"></span></label>'
    + '<button type="button" class="memory-item-btn rt-edit">edit</button>'
    + '<button type="button" class="memory-item-btn rt-del">delete</button>'
    + '</div></div>';
}

function editItem(t, idx) {
  return '<div class="memory-item memory-item-editing rt-item" data-idx="' + idx + '">'
    + '<div class="memory-item-content rt-edit-col">'
    + '<input type="text" class="memory-item-edit-input rt-name-in" maxlength="60" placeholder="Topic name" value="' + esc(t.name) + '" />'
    + '<textarea class="memory-item-edit-input rt-ex-in" rows="5" placeholder="Example queries, one per line (1–10)">'
    + esc((t.examples || []).join('\n')) + '</textarea>'
    + '<div class="memory-item-actions" style="opacity:1">'
    + '<button type="button" class="memory-item-btn save rt-save-item">save</button>'
    + '<button type="button" class="memory-item-btn rt-cancel">cancel</button>'
    + '</div></div></div>';
}

function topicsPanel() {
  if (!_data) return '<div class="admin-card"><p class="memory-desc doclib-desc">Loading…</p></div>';
  const items = _data.topics.map(topicItem).join('')
    + (_editing === 'new' ? editItem({ name: '', examples: [] }, 'new') : '');
  const other = _data.other || {};
  return '<div class="admin-card" style="display:flex;flex-direction:column;min-height:0;">'
    + '<div style="display:flex;align-items:center;gap:8px;margin-bottom:2px;">'
    + '<h2 style="display:flex;align-items:center;gap:6px;margin:0;padding:0;line-height:1;">' + ICON + 'Topics</h2>'
    + '<span style="flex:1"></span>'
    + '<button type="button" class="memory-toolbar-btn rt-add" title="Add a topic">+ Add topic</button>'
    + '</div>'
    + '<p class="memory-desc doclib-desc" style="margin-top:6px;">Web searches are matched to the topic whose example queries are closest '
    + '(while the relevance filter is on). Your up/down ratings in the sources box are counted per topic.</p>'
    + '<div class="memory-list rt-list">' + items
    + '<div class="memory-item rt-other"><div class="memory-item-content">'
    + '<span class="memory-item-text">other</span><span class="rt-examples">Searches that matched no topic</span>'
    + '<div class="memory-item-meta">' + metaFor({ ...other, enabled: true }) + '</div></div></div>'
    + '</div><span class="admin-toggle-sub rt-status" style="display:block;margin-top:6px"></span></div>';
}

function settingRow(title, sub, control) {
  return '<div class="admin-card">'
    + '<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:32px">'
    + '<h2 style="margin:0;display:inline-flex;align-items:center;gap:6px">' + esc(title) + '</h2>' + control + '</div>'
    + '<span class="admin-toggle-sub" style="display:block;margin-top:6px;opacity:0.6">' + sub + '</span></div>';
}

function slider(key, value, min, max, step, fmt) {
  return '<span style="display:flex;align-items:center;gap:8px;flex-shrink:0">'
    + '<span class="admin-toggle-sub rt-val" data-for="' + key + '" style="margin:0;min-width:42px;text-align:right;font-variant-numeric:tabular-nums">'
    + esc(fmt(value)) + '</span>'
    + '<input type="range" class="preset-range rt-range" data-key="' + key + '" min="' + min + '" max="' + max + '" step="' + step
    + '" value="' + esc(value) + '" style="width:120px;margin:0" /></span>';
}

function sw(key, on) {
  return '<label class="admin-switch" style="flex-shrink:0"><input type="checkbox" class="rt-flag" data-key="' + key + '"'
    + (on ? ' checked' : '') + ' /><span class="admin-slider"></span></label>';
}

const FMT = {
  web_filter_threshold: v => Number(v).toFixed(3),
  web_filter_candidates: v => String(v),
  web_filter_min_keep: v => String(v),
  min_similarity: v => Number(v).toFixed(2),
};

function settingsPanel() {
  if (!_filter || !_data) return '<div class="admin-card"><p class="memory-desc doclib-desc">Loading…</p></div>';
  const f = _filter;
  return settingRow('Relevance filter',
      'Scores each web result against the search query and drops off-topic ones before the model sees them. '
      + 'Takes effect within 2 seconds; no restart.', sw('web_filter_enabled', f.web_filter_enabled))
    + settingRow('Cut-off',
      'Results scoring below this are dropped. Measured on 888 labelled results: 0.026–0.041 dropped a fifth to a third '
      + 'of the junk and almost nothing relevant.',
      slider('web_filter_threshold', f.web_filter_threshold, 0.005, 0.2, 0.005, FMT.web_filter_threshold))
    + settingRow('Candidates per search',
      'How many results to request and score; the best of them (up to the usual count) reach the model. More costs time.',
      slider('web_filter_candidates', f.web_filter_candidates, 5, 30, 1, FMT.web_filter_candidates))
    + settingRow('Always keep',
      'Never pass on fewer results than this, even if they score below the cut-off.',
      slider('web_filter_min_keep', f.web_filter_min_keep, 1, 10, 1, FMT.web_filter_min_keep))
    + settingRow('Decision log',
      'Write every search\'s candidates, scores and outcome to data/logs/web_filter.jsonl, for the replay and ratings.',
      sw('web_filter_decision_log', f.web_filter_decision_log))
    + settingRow('Topic matching',
      'How similar a search must be to a topic\'s examples to be assigned to it; below this it goes to "other".',
      slider('min_similarity', _data.min_similarity, 0.1, 0.9, 0.05, FMT.min_similarity))
    + '<div class="admin-card" style="display:flex;align-items:center;gap:8px">'
    + '<button type="button" class="memory-toolbar-btn rt-save-settings">Save settings</button>'
    + '<span class="admin-toggle-sub rt-status" style="margin:0"></span></div>';
}

function render() {
  const tab = _modal.dataset.tab || 'topics';
  _modal.querySelectorAll('[data-rt-tab]').forEach(b => b.classList.toggle('active', b.dataset.rtTab === tab));
  _modal.querySelectorAll('[data-rt-panel]').forEach(p => p.classList.toggle('hidden', p.dataset.rtPanel !== tab));
  _modal.querySelector('[data-rt-panel="topics"]').innerHTML = topicsPanel();
  _modal.querySelector('[data-rt-panel="settings"]').innerHTML = settingsPanel();
}

function status(text, bad) {
  _modal.querySelectorAll('.rt-status').forEach(el => {
    el.textContent = text || '';
    el.style.color = bad ? 'var(--red, #e06c75)' : '';
  });
}

// ── data ──

async function load() {
  try {
    const [t, f] = await Promise.all([
      fetch('/api/research-topics', { credentials: 'same-origin' }),
      fetch('/api/web-filter/settings', { credentials: 'same-origin' }),
    ]);
    if (!t.ok || !f.ok) throw new Error('HTTP ' + (t.ok ? f.status : t.status));
    _data = await t.json();
    _filter = await f.json();
    render();
  } catch (e) {
    _data = _data || { topics: [], min_similarity: 0.35 };
    render();
    status('Could not load: ' + e.message, true);
  }
}

async function put(url, body) {
  const r = await fetch(url, {
    method: 'PUT', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (r.status === 403) throw new Error('Only an admin can change this.');
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || ('HTTP ' + r.status));
  return data;
}

async function saveTopics(topics, okText) {
  status('Saving…');
  try {
    await put('/api/research-topics', { min_similarity: _data.min_similarity, topics });
    _editing = null;
    await load();
    status(okText || 'Saved.');
  } catch (e) {
    status(e.message, true);
  }
}

function plainTopics() {
  return _data.topics.map(t => ({ id: t.id, name: t.name, enabled: t.enabled !== false, examples: t.examples || [] }));
}

// ── events ──

function onClick(ev) {
  const t = ev.target;
  if (t.closest('.rt-close') || t === _modal) return close();
  const tabBtn = t.closest('[data-rt-tab]');
  if (tabBtn) { _modal.dataset.tab = tabBtn.dataset.rtTab; render(); return; }
  if (!_data) return;
  const item = t.closest('.rt-item');
  const idx = item && item.dataset.idx !== 'new' ? Number(item.dataset.idx) : null;
  if (t.closest('.rt-add')) { _editing = 'new'; render(); _modal.querySelector('.rt-name-in')?.focus(); return; }
  if (t.closest('.rt-edit')) { _editing = idx; render(); return; }
  if (t.closest('.rt-cancel')) { _editing = null; render(); return; }
  if (t.closest('.rt-del')) {
    const name = _data.topics[idx]?.name || 'this topic';
    if (!window.confirm('Delete "' + name + '"? Searches already assigned keep their topic in the log.')) return;
    return saveTopics(plainTopics().filter((_, i) => i !== idx), 'Deleted.');
  }
  if (t.closest('.rt-save-item')) {
    const name = item.querySelector('.rt-name-in').value;
    const examples = item.querySelector('.rt-ex-in').value.split('\n').map(x => x.trim()).filter(Boolean);
    const topics = plainTopics();
    if (_editing === 'new') topics.push({ id: '', name, enabled: true, examples });
    else topics[idx] = { ...topics[idx], name, examples };
    return saveTopics(topics);
  }
  if (t.closest('.rt-save-settings')) return saveSettings();
}

function onChange(ev) {
  const t = ev.target;
  if (t.classList.contains('rt-on')) {
    const idx = Number(t.closest('.rt-item').dataset.idx);
    const topics = plainTopics();
    topics[idx].enabled = t.checked;
    saveTopics(topics, t.checked ? 'Topic on.' : 'Topic off.');
  }
}

function onInput(ev) {
  const t = ev.target;
  if (!t.classList.contains('rt-range')) return;
  const label = _modal.querySelector('.rt-val[data-for="' + t.dataset.key + '"]');
  if (label) label.textContent = (FMT[t.dataset.key] || String)(t.value);
}

async function saveSettings() {
  const body = {};
  _modal.querySelectorAll('.rt-flag').forEach(el => { body[el.dataset.key] = el.checked; });
  let minSim = _data.min_similarity;
  _modal.querySelectorAll('.rt-range').forEach(el => {
    if (el.dataset.key === 'min_similarity') minSim = Number(el.value);
    else body[el.dataset.key] = Number(el.value);
  });
  status('Saving…');
  try {
    _filter = await put('/api/web-filter/settings', body);
    if (minSim !== _data.min_similarity) {
      await put('/api/research-topics', { min_similarity: minSim, topics: plainTopics() });
    }
    await load();
    status('Saved.');
  } catch (e) {
    status(e.message, true);
  }
}

// ── modal ──

const STYLE = `
#research-topics-modal .rt-list { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
#research-topics-modal .rt-item .memory-item-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
#research-topics-modal .rt-name { font-weight: 600; }
#research-topics-modal .rt-examples { opacity: 0.6; font-size: 0.92em; overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
#research-topics-modal .rt-item-side { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
#research-topics-modal .rt-edit-col textarea { resize: vertical; width: 100%; box-sizing: border-box; }
#research-topics-modal .rt-other { opacity: 0.75; }
`;

function build() {
  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.appendChild(style);
  _modal = document.createElement('div');
  _modal.id = 'research-topics-modal';
  _modal.className = 'modal hidden';
  _modal.dataset.tab = 'topics';
  // data-rt-tab / data-rt-panel, not data-memory-*: memory.js wires every
  // [data-memory-tab] on the page, and its panels by [data-memory-panel].
  _modal.innerHTML = '<div class="modal-content memory-modal-content" role="dialog" aria-label="Research topics" style="background:var(--bg)">'
    + '<div class="modal-header"><h4>' + ICON + 'Research topics</h4>'
    + '<button class="close-btn rt-close" aria-label="Close research topics">&#x2716;</button></div>'
    + '<div class="modal-body memory-modal-body">'
    + '<div class="memory-tabs">'
    + '<button type="button" class="memory-tab active" data-rt-tab="topics">' + LIST_ICON + 'Topics</button>'
    + '<button type="button" class="memory-tab" data-rt-tab="settings">' + GEAR_ICON + 'Settings</button>'
    + '</div>'
    + '<div class="memory-tab-panel" data-rt-panel="topics"></div>'
    + '<div class="memory-tab-panel hidden" data-rt-panel="settings"></div>'
    + '</div></div>';
  _modal.addEventListener('click', onClick);
  _modal.addEventListener('change', onChange);
  _modal.addEventListener('input', onInput);
  document.body.appendChild(_modal);
}

export function open() {
  if (!_modal) build();
  _editing = null;
  _modal.classList.remove('hidden');
  render();
  load();
}

export function close() {
  if (_modal) _modal.classList.add('hidden');
}

function init() {
  ['rail-research-topics', 'tool-research-topics-btn'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', open);
  });
  document.addEventListener('keydown', ev => {
    if (ev.key === 'Escape' && _modal && !_modal.classList.contains('hidden')) close();
  });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}
