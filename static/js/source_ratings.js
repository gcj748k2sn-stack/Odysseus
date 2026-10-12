// Per-source ratings in the web sources box (fork module; notes item 71).
//
// buildSourcesBox (chatRenderer.js) calls splitSources() and decorateSource()
// for sources that carry a search_id (set by services/search/core.py). Each
// shown source gets an up and a down arrow; the filter's dropped candidates
// ("filtered": true) are listed in a collapsed "N filtered out" block with the
// same arrows. Clicks POST to /api/web-ratings; ratings are restored on render
// by GET /api/web-ratings. The arrows are UI only and never part of the answer
// text, so the model never sees them.

const UP = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 15 12 9 18 15"/></svg>';
const DOWN = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>';

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function domainOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch (e) { return url || ''; }
}

/** {shown, filtered}: the filter's dropped candidates are kept out of the
 *  numbered list, so [n] still matches the numbers the model cites. */
export function splitSources(sources) {
  const shown = [], filtered = [];
  (sources || []).forEach(s => { if (s) (s.filtered ? filtered : shown).push(s); });
  return { shown, filtered };
}

function rateButtons(s) {
  const data = ' data-search-id="' + esc(s.search_id) + '" data-url="' + esc(s.url) + '"'
    + ' data-query="' + esc(s.query || '') + '" data-topic="' + esc(s.topic || '') + '"'
    + ' data-title="' + esc((s.title || '').slice(0, 300)) + '"'
    + ' data-filtered="' + (s.filtered ? '1' : '') + '"'
    + ' data-score="' + (typeof s.score === 'number' ? s.score : '') + '"';
  return '<span class="src-rate"' + data + '>'
    + '<button type="button" class="src-rate-btn" data-rate="up" title="Useful source" aria-label="Useful source" aria-pressed="false">' + UP + '</button>'
    + '<button type="button" class="src-rate-btn" data-rate="down" title="Not useful" aria-label="Not useful" aria-pressed="false">' + DOWN + '</button>'
    + '</span>';
}

/** Wrap one source row (the <a> buildSourcesBox made) with its arrows.
 *  Sources without a search_id (older chats, research sources) are unchanged. */
export function decorateSource(linkHtml, s) {
  if (!s || !s.search_id || !s.url) return linkHtml;
  return '<div class="src-row">' + linkHtml + rateButtons(s) + '</div>';
}

/** The collapsed "N filtered out" block, or '' when nothing was dropped. */
export function filteredBlock(filtered, safeHref) {
  const rows = (filtered || []).filter(s => s && s.search_id && s.url);
  if (!rows.length) return '';
  let items = '';
  rows.forEach(s => {
    const domain = domainOf(s.url);
    const score = typeof s.score === 'number' ? ' · ' + s.score.toFixed(3) : '';
    const link = '<a href="' + safeHref(s.url) + '" target="_blank" rel="noopener noreferrer" class="source-link src-filtered">'
      + '<span class="source-title">' + esc(s.title || domain) + '</span>'
      + '<span class="source-domain">' + esc(domain) + score + '</span></a>';
    items += decorateSource(link, s);
  });
  return '<details class="src-filtered-block"><summary>' + rows.length + ' filtered out by relevance</summary>'
    + '<div class="src-filtered-list">' + items + '</div></details>';
}

// ── clicks ──

function setState(searchId, url, rating) {
  document.querySelectorAll('.src-rate').forEach(el => {
    if (el.dataset.searchId !== searchId || el.dataset.url !== url) return;
    el.querySelectorAll('.src-rate-btn').forEach(b => {
      const on = b.dataset.rate === rating;
      b.classList.toggle('active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  });
}

async function onClick(ev) {
  const btn = ev.target.closest && ev.target.closest('.src-rate-btn');
  if (!btn) return;
  ev.preventDefault();
  ev.stopPropagation();
  const box = btn.closest('.src-rate');
  const d = box.dataset;
  const rating = btn.classList.contains('active') ? 'clear' : btn.dataset.rate;
  const score = d.score === '' ? null : Number(d.score);
  try {
    const r = await fetch('/api/web-ratings', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ search_id: d.searchId, url: d.url, rating, query: d.query, topic: d.topic,
                             title: d.title, filtered: d.filtered === '1', score }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    setState(d.searchId, d.url, rating === 'clear' ? '' : rating);
  } catch (e) {
    btn.classList.add('src-rate-error');
    setTimeout(() => btn.classList.remove('src-rate-error'), 1200);
  }
}

// ── restore saved ratings on render (live answers and reloaded chats) ──

const _hydrated = new WeakSet();
let _pending = null;

function hydrateSoon() {
  if (_pending) return;
  _pending = setTimeout(async () => {
    _pending = null;
    const boxes = [...document.querySelectorAll('.src-rate')].filter(el => !_hydrated.has(el));
    if (!boxes.length) return;
    boxes.forEach(el => _hydrated.add(el));
    const ids = [...new Set(boxes.map(el => el.dataset.searchId))].slice(0, 200);
    try {
      const r = await fetch('/api/web-ratings?search_ids=' + encodeURIComponent(ids.join(',')), { credentials: 'same-origin' });
      if (!r.ok) return;
      const data = (await r.json()).ratings || {};
      Object.entries(data).forEach(([sid, byUrl]) => {
        Object.entries(byUrl).forEach(([url, rating]) => setState(sid, url, rating));
      });
    } catch (e) { /* ratings stay unshown; clicking still works */ }
  }, 200);
}

const STYLE = `
.src-row { display: flex; align-items: center; gap: 4px; }
.src-row > .source-link { flex: 1; min-width: 0; }
.src-rate { display: inline-flex; gap: 2px; flex-shrink: 0; }
.src-rate-btn { background: none; border: 1px solid transparent; border-radius: 4px; padding: 2px 3px;
  color: var(--fg); opacity: 0.35; cursor: pointer; line-height: 0; }
.src-rate-btn:hover { opacity: 0.8; border-color: color-mix(in srgb, var(--fg) 25%, transparent); }
.src-rate-btn.active { opacity: 1; border-color: color-mix(in srgb, var(--fg) 45%, transparent);
  background: color-mix(in srgb, var(--fg) 10%, transparent); }
.src-rate-btn.src-rate-error { color: var(--red, #e06c75); opacity: 1; }
.src-filtered-block { margin-top: 6px; font-size: 0.9em; }
.src-filtered-block > summary { cursor: pointer; opacity: 0.55; padding: 2px 8px; }
.src-filtered-list { display: flex; flex-direction: column; gap: 3px; margin-top: 4px; }
.src-filtered { opacity: 0.6; }
`;

function init() {
  if (window.__odySourceRatings) return;
  window.__odySourceRatings = true;
  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.appendChild(style);
  document.addEventListener('click', onClick, true);
  new MutationObserver(muts => {
    for (const m of muts) {
      for (const n of m.addedNodes) {
        if (n.nodeType === 1 && (n.matches?.('.src-rate') || n.querySelector?.('.src-rate'))) { hydrateSoon(); return; }
      }
    }
  }).observe(document.body, { childList: true, subtree: true });
  hydrateSoon();
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}
