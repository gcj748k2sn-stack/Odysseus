# 85. Local Wikipedia packs: search a local topic subset first, propose new topics with an approval card

Open item, **planned 2026-10-13, nothing built.** Its row in the [todo.md](../todo.md) index carries the current status; this file is the full record.

## Why

Measured 2026-10-13 from `data/logs/web_filter.jsonl` on the M1 (247 searches, 12 Oct 14:00 → 13 Oct 11:59 local; reranker scores, not labels):

| engine | results | median score | below 0.035 | searches | searches with every result below 0.035 |
|---|---|---|---|---|---|
| bing | 1567 | 0.033 | 54 % | 176 | 60 |
| google cse | 1362 | 0.517 | 0 % | 133 | 0 |
| bing news | 130 | 0.039 | 38 % | 15 | 0 |

- Engine combinations: **103 searches Bing only**, 77 Bing + Google CSE, 56 Google CSE only, 15 Bing News. **26 Bing-only searches had every result below 0.035**, so fail-open handed the model the 3 least-bad junk results.
- Example: *"Pleurotus djamor pink oyster mushroom native range Indonesia Philippines natural habitat"* — all 8 Google CSE results about the mushroom, all 7 Bing results about *Thunder* (Wikipedia, Imagine Dragons, Thundr). The filter dropped all 7.
- Google CSE drops out by hour: 0 of 52 searches in the 13 Oct 01:00 hour (a night benchmark run), back at 08:00 (11 of 11), mixed at 09:00–10:00, gone at 11:00 (0 of 23). That does not fit a daily quota (it would reset at 09:00 local). It fits SearXNG suspending the engine after CAPTCHA / *too many requests*, which item 47 recorded from `searxng/searxng.log` on 2026-10-02. **Unverified for these hours** — Phase 0 step 1 checks it.
- Mojeek and Wikipedia are enabled in `searxng/settings.yml` (per [qwensetup.md](../qwensetup.md)) and appear in none of the 247 searches.
- **Consequence for benchmarks:** the filter A/B of `chain-20261013-0001` ran in those hours. Whether a run had Google may matter more than whether the filter was on. Count Google-less searches per run before reading that A/B.

A web-scale index can't be self-hosted. A topic subset of Wikipedia can: many of the recorded questions are encyclopedic (species ranges, wingspans, heights, chip addresses), and a local index cannot be blocked or rate-limited.

## Goal and non-goals

- **Goal:** for searches in a topic that has a local pack, answer from local Wikipedia articles when they are good enough, and otherwise add them to the web candidates. Propose packs for topics that keep producing weak web results, and download only after the maintainer approves.
- **Not:** a full Wikipedia mirror; cultivation guides, prices, news or shops (those stay on the web); a crawler for arbitrary sites (a later "trusted sites" pack type, separate item); the model deciding to download anything.

## Shape

```
web_search / chat search / deep research
  └─ comprehensive_web_search (services/search/core.py)
       ├─ tag_search(query)                  → topic            (moved before the provider call)
       ├─ local_wiki.lookup(query, topic)    → local candidates (src/local_wiki.py, FTS5, ms)
       │     mode off  : nothing
       │     mode log  : look up, log, change nothing
       │     mode merge: local candidates join the web candidates before the reranker
       │     mode first: if local is good enough, skip the web provider entirely
       ├─ provider chain (SearXNG …)          ← skipped only in "first" when local suffices
       ├─ filter_results (reranker)           ← scores local and web candidates alike
       ├─ fetch: local URLs take their text from the pack, no HTTP fetch
       └─ proposal check (report only)        → card data on the sources, if a pack is missing
```

Fork modules: `src/wiki_packs.py` (pack definitions, builder, storage; standard library only), `src/local_wiki.py` (lookup, modes, proposal rule), `routes/wiki_pack_routes.py`, `static/js/wiki_packs.js`, `scripts/wiki_pack.py` (CLI), `scripts/bench_local_wiki.py` (replay). Upstream files get call sites only: `services/search/core.py` (lookup + local fetch), the route registration, and one hook in `buildSourcesBox` (via `source_ratings.js`, already a fork file).

## Phase 0 — facts to check first (M1, maintainer, ~15 min)

1. **Why Google CSE drops out.** Every block or suspension of Google CSE since 12 Oct:
   ```
   grep -i "google cse" /Users/cedrik/odysseus/searxng/searxng.log | grep -i -E "suspend|captcha|too many|429|403|denied" | tail -40
   ```
   Suspension lines in the 01:00 and 11:00 hours of 13 Oct confirm the mechanism; none means look elsewhere (timeouts, engine errors) before building on it.
2. **FTS5 in the venv's SQLite** (`core/database.py` probes it; check the venv itself):
   ```
   /Users/cedrik/odysseus/venv/bin/python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('create virtual table t using fts5(x)'); print('fts5 ok', sqlite3.sqlite_version)"
   ```
3. **Wikipedia API reachable from the M1**, and the direct size of the candidate categories (direct members only; the tree is counted in Phase 1):
   ```
   curl -s -A "Odysseus-local-wiki/0.1 (personal research tool)" "https://en.wikipedia.org/w/api.php?action=query&titles=Category:Fungi|Category:Mycology|Category:Edible_fungi&prop=categoryinfo&format=json"
   curl -s -A "Odysseus-local-wiki/0.1 (personal research tool)" "https://de.wikipedia.org/w/api.php?action=query&titles=Kategorie:Pilze|Kategorie:Mykologie|Kategorie:Speisepilzart&prop=categoryinfo&format=json"
   ```
   This cloud session could not reach wikipedia.org (proxy 403), so no size in this file is measured yet.

## Phase 1 — build one pack: mycology (S–M, guess)

**Pack definition** (`data/wiki_packs/packs.json`, one entry per pack):

```json
{"id": "mycology-en", "name": "Mycology", "topic": "biology", "lang": "en",
 "source": {"type": "wikiproject", "name": "Fungi"},
 "exclude_title": ["^List of .* (albums|songs)"],
 "state": "planned", "articles": null, "bytes": null, "built": null, "updated": null}
```

Two source types: `wikiproject` (pages whose talk page carries the project banner; usually the cleanest set) and `category` with a `depth` (2–3; category trees drift — a few levels below *Fungi* sit beer and bread, so the plan output must show it). German packs use categories (`Kategorie:Pilze`); German Wikipedia has no WikiProject banners in the same form.

**Builder** (`src/wiki_packs.py`, CLI `scripts/wiki_pack.py`; standard library only, so it never imports `core.database` and cannot touch `app.db`):

- `plan PACK` — resolves the article list without downloading text. Prints the count, 25 random titles, for category packs the count per depth and the subcategories reached at the deepest level, and an estimated size (count × mean extract length from a 50-article sample). Writes the list to `data/wiki_packs/<id>.titles`. Nothing is built.
- `build PACK` — downloads plain text per article. **Choose in Phase 0/1 by timing, not now:**
  - (a) `prop=extracts&explaintext=1`: clean text, but full extracts come one page per request;
  - (b) `prop=revisions&rvprop=content&rvslots=main`: wikitext for up to 50 pages per request, needs a wikitext stripper (templates, refs, tables; `mwparserfromhell` is not a dependency).
  Measure 50 articles both ways and pick. Either way: serial requests, a descriptive User-Agent, `maxlag=5`, back off on HTTP 429/503 (Wikimedia's API etiquette).
  Also fetches each article's redirects (`prop=redirects`, batched 50) as aliases, so *"pink oyster mushroom"* reaches *Pleurotus djamor*.
- **Resumable:** articles are stored with `pageid` and `revid`; a rerun skips stored ones, so an interrupted build continues.
- `update PACK` — re-lists, fetches only articles whose `revid` changed, removes articles no longer in the set.
- `query PACK "text"` — top hits with BM25 score and snippet, for checking by hand.
- `delete PACK`.

**Storage:** one SQLite file per pack, `data/wiki_packs/<id>.sqlite`:
- `articles(pageid, title, url, lang, revid, rev_ts, fetched_at, text)`,
- `aliases(pageid, alias)`,
- `chunks` FTS5 table `(title, aliases, heading, body)` with sections split at ~600 characters (same idea as `chunk_text` in `bench_web_filter.py`), `bm25` weights favouring title and aliases.
Reuse `_sanitize_fts_query` from `src/session_search.py` — free text with FTS5 operators otherwise raises.

**Tests** (`tests/test_wiki_packs.py`, no network: API responses from recorded fixtures):
- plan on a fixture category tree respects depth and `exclude_title`;
- build stores, resumes after an interruption at article N without refetching, and update refetches only changed `revid`;
- redirects become aliases and are searchable;
- FTS query with operators and quotes in the user text does not raise;
- **negative controls:** queries about gold price, crepes, Imagine Dragons return nothing above a minimal BM25 score from the mycology fixture.
- Mutations to record: no depth limit; alias table ignored; `revid` check removed; MATCH builder bypassed.

**Exit:** `mycology-en` built on the M1, count and size written into this file, `query` spot-checked on 10 recorded mushroom queries.

## Phase 2 — replay: would the pack have answered? (S, guess)

`scripts/bench_local_wiki.py` over the decision log corpus (`bench_web_filter.py extract --from-decisions`):

1. For every recorded search, the top 5 local chunks (BM25), re-scored with the same reranker and passage format as the web filter.
2. Local hits are written into the **existing label sheet** as rows keyed on query + Wikipedia URL with hint `local`, so they are labelled on the `serve` page like web results. No new labelling tool.
3. Report:
   - **coverage:** searches whose best local hit is labelled `y`, per topic;
   - **"local suffices" precision** at candidate cut-offs `T_local`: a search counts as wrongly answered locally if local passes `T_local` but its local hits are labelled `n`. A cut-off is a candidate only with **zero** wrong searches on the labelled set, as for the web threshold;
   - **what it would replace:** among Bing-only all-junk searches, how many had a `y` local hit;
   - **negative controls:** finance and cooking searches must produce no local hit above `T_local`.
4. Every number with its corpus and labels count; the mutation list as in Phase 1.

**Exit, decided by the maintainer:** is coverage on mycology searches worth Phase 3, and which `T_local`? If coverage is low, stop here; the pack builder still serves Phase 4's catalogue later or not at all.

## Phase 3 — local-first in the search path (M, guess)

`src/local_wiki.py`, settings merged over its `DEFAULTS` like `web_filter`:

- `local_wiki_mode`: `off` (default) → `log` → `merge` → `first`.
  - `log`: look up and log `[local-wiki] query=… topic=… packs=… hits=N best=… would=merge|first|none ms=…`, change nothing.
  - `merge`: local hits become candidates (engine `local wikipedia`, real Wikipedia URL, snippet from the chunk) before `filter_results`; the reranker and ratings treat them like any result.
  - `first`: when at least `local_wiki_min_hits` (2) local hits score ≥ `local_wiki_threshold` (from Phase 2), skip the provider chain; otherwise behave as `merge`.
- `local_wiki_threshold`, `local_wiki_min_hits`, `local_wiki_max_hits` (5).
- **Which packs:** every built pack; FTS is milliseconds and the reranker sorts. The topic is logged, not used to exclude (topic assignment misses would otherwise hide a good pack).
- **Call order change in `core.py`:** `tag_search` moves before the provider loop (it only needs the query). One moved line plus one lookup call.
- **Fetch:** local URLs take their text from the pack (the matched sections first, up to the 3,000 characters the output already allows per page); they are left out of the `ThreadPoolExecutor` fetch. Fork helper, two-line call site.
- **Output to the model:** unchanged format; the summary line says `Searched N results (M from local Wikipedia, revision dates …)` so the model and the user can tell. In `first` mode one line: *"Answered from a local Wikipedia copy (revisions up to YYYY-MM-DD); search the web if you need current information."*
- **Decision log:** `local` block per search (mode, packs, hits with score and pageid, `skipped_web`).
- **Fail-open:** missing or unreadable pack, FTS error, timeout over 300 ms → log one warning, web search as today.
- **Benchmarks:** `bench_agent.py` records `local_wiki_mode` in run metadata, so a run with packs is never compared with one without unknowingly.

**Tests:** mode `off` leaves `comprehensive_web_search` output byte-identical (wiring test, `tests/test_local_wiki_wiring.py`, the deliberate structural exception); `merge` adds candidates and they pass through the filter; `first` skips the provider only above the threshold (the provider stub must record zero calls) and falls back otherwise; local fetch never opens HTTP; a broken pack file falls back with a warning; negative controls from Phase 2 as fixtures. Mutations: threshold ignored in `first`; min_hits ignored; local URLs fetched over HTTP; fail-open removed.

**Live check (M1):** three mushroom searches in `log`, read the `[local-wiki]` lines; then `merge` for a day; `first` only after the decision log shows the `would=first` searches were right.

## Phase 4 — proposals and the approval card (M, guess)

**Not the agent's tool-approval card.** `src/tool_approvals.py` gates tools *after external context armed the run* (`decision_for` in `src/tool_capabilities.py`): a download tool would run unasked before any web search, and a 9B model would decide when to propose. A download is an admin change. So the server proposes, deterministically, and the card is UI with buttons that call an admin-only route.

**When a card appears** (`local_wiki.proposal_for(search)`, report-only, computed after the search):
- the search topic is not `other`, **and** no built or planned pack covers the topic, **and**
- this search was weak (best score below the off-topic notice cut-off, or Bing-only with every result below the threshold) **or** the topic has had ≥ 3 searches in 7 days without a pack;
- **and** the topic is not snoozed or declined.
- The candidate pack comes from a hand-written catalogue `data/wiki_packs/catalogue.json` (topic → sources, e.g. `biology` → WikiProject Fungi (en), Kategorie:Pilze (de), WikiProject Plants…). No catalogue entry, no card. The model never names a pack.

**The card** (under the sources box; `annotate_sources` carries a `wiki_proposal` field, `static/js/wiki_packs.js` renders it):

> **Local Wikipedia: Mycology (WikiProject Fungi, en)** — searches in *Biology* often come back weak from the web.
> [Check size] [Not now] [Never for Biology]

Two steps, so nothing downloads unseen:
1. **Check size** runs `plan` in the background; the card updates to *"9,812 articles, ~140 MB, sample: Amanita muscaria, Pleurotus djamor, …"* (made-up numbers for illustration) with **[Download] [Cancel]**.
2. **Download** starts `build` as a background job; the card and the Research topics panel show progress.
- *Not now* snoozes the topic for 30 days; *Never* stores a decline. Both in `data/wiki_packs/decisions.json`.

**Research topics panel:** each topic gets a *Local Wikipedia* line — none / planned (count, size) / building (progress) / built (articles, last update) — with *Check size*, *Download*, *Update*, *Delete*. Packs can be had without waiting for a card.

**Background job:** one build at a time, a thread in the app process, progress in `data/wiki_packs/<id>.status.json`, resumable after a restart (Phase 1's `revid` skip), cancellable. Routes in `routes/wiki_pack_routes.py`: `GET /api/wiki-packs`, `POST /api/wiki-packs/{id}/plan`, `POST …/build`, `POST …/update`, `POST …/cancel`, `DELETE …/{id}`, `POST /api/wiki-packs/decisions` — admin only (like `PUT /api/research-topics`), reads for any user.

**Tests:** proposal rule with negative controls (pack exists → no card; topic `other` → none; snoozed / declined → none; strong search and fewer than 3 in 7 days → none); routes admin-only with per-user isolation; plan/build/cancel state machine with a fake builder; card data never reaches a model-facing path (wiring test). JS ships on `node --check` only — **unverified**; manual step: trigger a weak Biology search with no pack, confirm the card, click *Check size*, confirm the count appears and nothing is downloaded until *Download*.

## Phase 5 — upkeep (S, guess)

- Weekly `update` for built packs through the task scheduler (off by default), or by hand from the panel.
- Disk use per pack in the panel; delete removes the SQLite file and the status files.
- Later, separate item: a **trusted sites** pack type (crawl the domains labelled `y` and rated ▲ in a topic), same storage and lookup.

## Risks and open questions

- **Wikipedia is not always right or current.** Citations keep the live URL, the output carries the revision date, and `first` mode tells the model it can search the web.
- **Size of WikiProject Fungi and the German categories is unknown** (Phase 0 step 3, Phase 1 `plan`).
- **Extract vs. wikitext** decides the build time (Phase 1).
- **Category drift** (beer below *Fungi*): the plan output shows it before anything is downloaded.
- **License:** CC BY-SA; private use with source URLs. No redistribution planned.
- **Swap pressure on the M1** (8–14.5 GB during the 13 Oct chain): FTS5 needs little RAM, and the reranker is already loaded. Measure RSS before and after a build.
- **A/B and benchmark confound** (see *Why*): local packs change web benchmark results; Phase 3 records the mode per run.

## Verification

Nothing built. All numbers in *Why* come from the maintainer's runs of two scripts on the M1 decision log (13 Oct, pasted in the session); sizes and effort are guesses.
