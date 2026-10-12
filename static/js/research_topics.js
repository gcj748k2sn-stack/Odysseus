// Research topics panel (fork module; notes item 71).
//
// Opened from the left icon bar and the sidebar tools list (below Deep
// Research). Lists the topics web searches are assigned to — name, example
// queries, on/off — with per-topic counts of searches and source ratings.
// Reads GET /api/research-topics, saves with PUT (admin only).

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

const ICON = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>';

let _modal = null;
let _data = null;

function counts(t) {
  const r = t.ratings || { up: 0, down: 0 };
  return (t.searches || 0) + ' searches · ' + r.up + ' up · ' + r.down + ' down';
}

function topicCard(t, idx) {
  return '<div class="rt-card" data-idx="' + idx + '">'
    + '<div class="rt-row">'
    + '<input class="rt-name" type="text" maxlength="60" value="' + esc(t.name) + '" aria-label="Topic name">'
    + '<label class="admin-switch" title="Use this topic"><input type="checkbox" class="rt-on" aria-label="Use this topic"'
    + (t.enabled ? ' checked' : '') + ' /><span class="admin-slider"></span></label>'
    + '<button type="button" class="rt-del admin-btn-sm" title="Delete topic">Delete</button>'
    + '</div>'
    + '<textarea class="rt-examples" rows="4" aria-label="Example queries, one per line">' + esc((t.examples || []).join('\n')) + '</textarea>'
    + '<div class="rt-counts">' + esc(counts(t)) + '</div>'
    + '</div>';
}

function render() {
  const body = _modal.querySelector('.rt-body');
  if (!_data) { body.innerHTML = '<div class="rt-muted">Loading…</div>'; return; }
  body.innerHTML =
    '<p class="rt-muted">While the relevance filter is on, each web search goes to the topic whose example queries are '
    + 'closest to it, or to "other". Ratings from the arrows in the sources box are counted per topic. '
    + 'Example queries: one per line, 1–10 per topic.</p>'
    + '<label class="rt-sim">Minimum similarity <input type="number" class="rt-min" min="0" max="1" step="0.05" value="'
    + esc(_data.min_similarity) + '"></label>'
    + _data.topics.map(topicCard).join('')
    + '<div class="rt-card rt-other"><div class="rt-row"><b>other</b></div><div class="rt-counts">'
    + esc(counts(_data.other || {})) + '</div></div>'
    + '<div class="rt-actions"><button type="button" class="rt-add admin-btn-sm">Add topic</button>'
    + '<button type="button" class="rt-save admin-btn-sm">Save</button><span class="rt-status"></span></div>';
}

function collect() {
  const topics = [];
  _modal.querySelectorAll('.rt-card[data-idx]').forEach(card => {
    const old = _data.topics[Number(card.dataset.idx)] || {};
    topics.push({
      id: old.id || '',
      name: card.querySelector('.rt-name').value,
      enabled: card.querySelector('.rt-on').checked,
      examples: card.querySelector('.rt-examples').value.split('\n').map(x => x.trim()).filter(Boolean),
    });
  });
  return { min_similarity: Number(_modal.querySelector('.rt-min').value), topics };
}

function status(text, bad) {
  const el = _modal.querySelector('.rt-status');
  if (el) { el.textContent = text; el.style.color = bad ? 'var(--red, #e06c75)' : ''; }
}

async function load() {
  _data = null;
  render();
  try {
    const r = await fetch('/api/research-topics', { credentials: 'same-origin' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    _data = await r.json();
    render();
  } catch (e) {
    _modal.querySelector('.rt-body').innerHTML = '<div class="rt-muted">Could not load topics: ' + esc(e.message) + '</div>';
  }
}

async function save() {
  const body = collect();
  status('Saving…');
  try {
    const r = await fetch('/api/research-topics', {
      method: 'PUT', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (r.status === 403) return status('Only an admin can change topics.', true);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return status(data.detail || ('HTTP ' + r.status), true);
    await load();
    status('Saved.');
  } catch (e) {
    status(e.message, true);
  }
}

function onClick(ev) {
  const t = ev.target;
  if (t.closest('.rt-close') || t === _modal) return close();
  if (t.closest('.rt-save')) return save();
  if (t.closest('.rt-add')) {
    _data.topics = collect().topics.map((x, i) => ({ ..._data.topics[i], ...x }));
    _data.min_similarity = Number(_modal.querySelector('.rt-min').value);
    _data.topics.push({ id: '', name: 'New topic', enabled: true, examples: [] });
    render();
    status('Fill in the new topic, then Save.');
    return;
  }
  const del = t.closest('.rt-del');
  if (del) {
    const idx = Number(del.closest('.rt-card').dataset.idx);
    _data.topics = collect().topics.map((x, i) => ({ ..._data.topics[i], ...x })).filter((_, i) => i !== idx);
    render();
    status('Deleted — Save to keep the change.');
  }
}

const STYLE = `
#research-topics-modal .modal-content { max-width: 640px; width: 92vw; max-height: 86vh; display: flex; flex-direction: column; }
#research-topics-modal .rt-body { overflow-y: auto; padding: 10px 14px 14px; }
.rt-muted { opacity: 0.6; font-size: 0.85em; margin: 0 0 10px; }
.rt-sim { display: block; font-size: 0.85em; margin-bottom: 10px; }
.rt-sim input { width: 70px; margin-left: 6px; }
.rt-card { border: 1px solid var(--border); border-radius: 8px; padding: 8px; margin-bottom: 8px; }
.rt-row { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.rt-name { flex: 1; min-width: 0; }
.rt-examples { width: 100%; box-sizing: border-box; font-size: 0.85em; resize: vertical; }
.rt-counts { font-size: 0.75em; opacity: 0.55; margin-top: 4px; }
.rt-actions { display: flex; gap: 8px; align-items: center; margin-top: 6px; }
.rt-status { font-size: 0.85em; opacity: 0.8; }
#research-topics-modal input[type=text], #research-topics-modal input[type=number], #research-topics-modal textarea { background: var(--panel); color: var(--fg);
  border: 1px solid var(--border); border-radius: 4px; padding: 4px 6px; }
`;

function build() {
  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.appendChild(style);
  _modal = document.createElement('div');
  _modal.id = 'research-topics-modal';
  _modal.className = 'modal hidden';
  _modal.innerHTML = '<div class="modal-content admin-modal-content" role="dialog" aria-label="Research topics" style="background:var(--bg)">'
    + '<div class="modal-header"><h4>' + ICON + ' Research topics</h4>'
    + '<button class="close-btn rt-close" aria-label="Close research topics">&#x2716;</button></div>'
    + '<div class="rt-body"></div></div>';
  _modal.addEventListener('click', onClick);
  document.body.appendChild(_modal);
}

export function open() {
  if (!_modal) build();
  _modal.classList.remove('hidden');
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
