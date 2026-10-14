# 82. A relevance filter for web results — measure it offline first

Open item. Its row in the [todo.md](../todo.md) index carries the current status; this file is the full record.

> **Number clash in git history:** commits of 2026-10-12 call this work **"item 71"** (`7a74934` feat, `ceeed10`, `c6620bd`, `4aa265c`, `a0b7d92`). Item 71 is *"A follow-up with an open document changes the tool set"*. This item is 82 everywhere in `notes/`; history keeps the old label. Search `git log` for both.

---

**Idea (maintainer, 2026-10-12):** a small "decision" model between web retrieval and the thinking model (Qwen 3.5 / Bonsai 2) that decides what reaches it. **Proposed shape:** a cross-encoder reranker (fastembed, already a dependency), not a generative model. It scores (question, passage) pairs in milliseconds and does not compete with the chat model for LM Studio. Two levels: (1) the search result list (title/URL/snippet), where *"Web search derails on ambiguous common nouns"* and *"today/latest routes web_search to the news category"* happen; (2) paragraphs of fetched pages, where most of the context, and so most of the prefill time, goes.

**Built 2026-10-12 (off by default) and switched on by the maintainer the same day:** `src/web_filter.py`, called once in `services/search/core.py`; research topics, per-source ratings and the search output fit came after. The offline replay that chose its settings: `scripts/bench_web_filter.py`. Tests: 104 across five files (see *Verification*).

## How results are ranked today

`rank_search_results` in `services/search/ranking.py`, called from `comprehensive_web_search` (`services/search/core.py`) on whatever the first working provider returned:

```
score = 2.0 × title   (share of query words found whole-word in the title)
      + 1.0 × snippet ((min(len, 200)/200 + share of query words in the snippet) / 2)
      + 1.5 × domain  (trusted news list or .edu/.gov 1.0, any .org 0.7, everything else 0.4)
      + 1.0 × recency (≤7 days 1.0, falling to 0 at 30 days; 0 when no date)
      + news adjustment (only when the query contains news/latest/today/…)
```

Then the top `max_pages` (5) are fetched, and every result is listed for the model. What follows from the code (read, not measured on the corpus):

- **Nothing is ever dropped.** Ranking only reorders.
- **The search engine's own order is thrown away.** SearXNG's position isn't an input; it only breaks exact ties (stable sort).
- **Query words are counted raw:** stopwords (*how*, *to*, *for*) count as much as the subject, and there is no stemming (*mushroom* ≠ *mushrooms*).
- **Any `.org` gets +0.45 over a `.com`,** Wikipedia included, whatever the topic, and a long snippet scores higher just for being long.
- **Shown in the sandbox (2026-10-12, `rank_search_results` called directly):** for *"pink oyster mushroom cultivation"*, *"Pink (singer) – Wikipedia"* (long snippet, `.org`, one title word) scores ≈ 2.18 and outranks *"How to Grow Pink Oyster Mushrooms at Home"* on grocycle.com (≈ 1.86). Constructed inputs, not a recorded search.

## Setup and run (M1)

All commands from `/Users/cedrik/odysseus`. `extract` copies `app.db` itself (hash, copy, hash again) and opens only the copy, read-only. It refuses if the database changed during the copy, so run it when no chat is in progress.

1. Tests:
   ```
   cd /Users/cedrik/odysseus
   ./venv/bin/python -m pytest -n auto tests/test_bench_web_filter.py
   ```
2. Extract the corpus (writes `data/bench/web_filter/<YYYYmmdd-HHMMSS>/corpus.jsonl` and `meta.json`), then point `RUN` at the newest run folder (set it again in a new terminal window):
   ```
   ./venv/bin/python scripts/bench_web_filter.py extract
   RUN=$(ls -d data/bench/web_filter/2*/ | tail -1)
   echo $RUN
   ```
3. Labels sheet (`data/bench/web_filter/labels.csv`, one row per query + URL; known junk from notes is hinted `seed:n`):
   ```
   ./venv/bin/python scripts/bench_web_filter.py label --dir $RUN
   ```
   After a first `run` (step 4), refill the sheet with a `score` column, ordered so the unlabelled rows with the lowest scores (what a filter would drop) come first:
   ```
   ./venv/bin/python scripts/bench_web_filter.py label --dir $RUN --scores-from rerank:query
   ```
   Open it in Numbers/Excel and put `y` (relevant) or `n` (junk) in the `label` column. Unlabelled rows are ignored. Labels are keyed on query + URL, so a later `extract` keeps them. 50–100 labelled rows across a dozen searches already give a usable first reading; label some relevant ones too, otherwise the report cannot show the cost.
   To label elsewhere: `export` writes the unlabelled rows (id, query, title, domain, snippet; no user messages) to `data/bench/web_filter/to_label.tsv`; `import FILE` applies `id<TAB>y|n` lines back, keeping labels already in the sheet:
   ```
   ./venv/bin/python scripts/bench_web_filter.py export
   ./venv/bin/python scripts/bench_web_filter.py import data/bench/web_filter/labels_in.tsv
   ```
4. Score and report. The first run downloads the reranker into `data/fastembed_cache` (80 MB):
   ```
   ./venv/bin/python scripts/bench_web_filter.py run --dir $RUN
   ```
   For German queries, also try the multilingual model (1.1 GB):
   ```
   ./venv/bin/python scripts/bench_web_filter.py run --dir $RUN --model jinaai/jina-reranker-v2-base-multilingual
   ```
   Without a download: `--scorers lexical:query`.
5. Paragraph preview of recorded `web_fetch` pages (what a 2,000-char budget per page would keep):
   ```
   ./venv/bin/python scripts/bench_web_filter.py pages --dir $RUN
   ```
6. Read `report.md`, `pages.md` and `domains_seen.csv` in the run directory.

## Reading the report

- One table per scorer: `lexical:query`, `rerank:query` (the search string), `rerank:user` (the user's message), `rerank:both`. Thresholds are the 10–50 % quantiles of that scorer's scores, so the numbers are comparable across models.
- **relevant dropped is the cost; read the listed URLs, not just the count.** A threshold is a candidate only when it drops no labelled-relevant result.
- **fail-open searches:** how often the threshold would have left fewer than 3 results, so the filter kept the best 3 instead. If that is most searches, the threshold is too high.
- **junk in top 5 after re-sort:** junk that would still be fetched if results were ordered by the new score. Compare it with *Today's order* at the top.
- Without labels the report runs on `SEED_RULES` (known junk only) and says so. Then "relevant dropped" is always 0 and means nothing.

## Corpus limits

- Agent turns only. Chat-mode turns store `web_sources` without snippets; they are counted (`chat_mode_rows_skipped` in `meta.json`) and skipped.
- Snippets are cut at 200 chars by the writer, and a stored tool output at 10,000 chars; a result whose URL line was cut off is dropped.
- `web_fetch` pages are stored cut at 10,000 chars, so the paragraph preview sees the start of each page only.
- The user message is the last user row in the same session at or before the assistant row (naive UTC).

## `domains_seen.csv` — what each column counts

One row per domain (`www.` stripped); `report.md` shows the top 40, the CSV has all of them.

- **seen** — how many times the domain appeared in a `web_search` result list, across all recorded searches. A page returned by three searches counts three times.
- **mean_rank** — its average position in those lists, as the model saw them (after `rank_search_results`); 1 = top. Positions 1–5 are the ones `comprehensive_web_search` fetches.
- **label_y / label_n** — your labels from `labels.csv`; while there are none, the SEED_RULES proxy fills `label_n`.
- **fetched / fetch_failed** — `web_fetch` calls the model made itself to that domain, and how many returned `exit_code≠0` (a remembered failure counts too). **The automatic top-5 fetches inside `web_search` are not recorded as tool events and are not in these columns.** A domain with fetches but no appearances got there from a link or the model's own guess.
- **prior** — its value from `domains.json`, 0 without one.

`label --scores-from SCORER` writes the label sheet already ordered: unlabelled rows first, lowest score (the first a filter would drop) at the top, labelled rows at the bottom. Editing in Numbers: open `labels.csv`, label, then **Ablage → Exportieren → CSV** over the same file (Numbers otherwise saves a `.numbers` file and the CSV stays unchanged).

## A list of known domains

Worth having, but as a prior on top of the content score, not as the filter. Authority depends on the topic: WebMD is fine for a nutrition question and junk for a cultivation one (that is why the seed rule needs a growing word in the query).

- Optional file `data/bench/web_filter/domains.json`, `{"allrecipes.com": -0.3, "kitco.com": 0.2}`. The value is added to every scorer's 0–1 score, and matching is by domain suffix (`webmd.com` covers `m.webmd.com`, not `notwebmd.com`).
- Build it from evidence: `domains_seen.csv` lists each domain's appearances, mean rank, y/n labels and how often `web_fetch` failed on it (a site that always 403s is not worth a fetch slot, whatever its quality).
- Keep priors small (±0.1 to ±0.3) and re-run the report after each change.

## First run on the M1 (2026-10-12 11:19 local, run `20261012-111918`)

**Corpus:** 190 searches, 888 results (4.7 per search), 157 fetches, 2026-07-17 → 2026-10-05 (UTC). No labels yet, so this is the SEED_RULES proxy: 32 known-junk results, all 32 in the fetched top 5 today. Reranker `Xenova/ms-marco-MiniLM-L-6-v2`.

| scorer | best row | junk dropped | unlabelled dropped | fail-open | junk in top 5 after re-sort |
|---|---|---:|---:|---:|---:|
| lexical:query | 0.250 | 18/32 | 187 | 79/190 | 14 |
| rerank:query | 0.007 | 28/32 | 191 | 77/190 | 4 |
| rerank:both | 0.045 | 26/32 | 223 | 100/190 | 6 |
| rerank:user | — | grid collapsed to one row | | | |

- **Read with care:** the proxy junk is mostly *"Pink (singer)"*, the easiest case, and **the 191 unlabelled drops are the unknown cost**. Nothing here says the filter is safe yet.
- **Two script faults this run exposed, fixed after it:** (1) the grid rounded thresholds to 4 decimals, and sigmoid reranker scores pile up near 0, so cut points merged (the duplicate `0.000` rows; `rerank:user` collapsed to one row). Now not rounded, printed with 3 significant digits. (2) The Victoria's Secret rule required *"pink oyster"* in the query and a straight apostrophe, so 29 appearances of `victoriassecret.com` got no hint.
- **New collisions in the domain table** (the *ambiguous common nouns* mechanism, not filed before): `oyster.tfl.gov.uk` (London's Oyster card, 10 appearances) and `oyster.com` (hotel reviews, 7), plus `victoriassecret.com` (29). Now a seed rule for mushroom queries.
- `rerank:user` collapsing is probably the English-only model on user messages (many are German) — unmeasured. Run the multilingual model before reading anything into it.
- Fetch failures worth a look: `researchgate.net` 3/3, `forbes.com` 2/2, `msn.com` 2/2, `mushroomexpert.com` 2/2, `thesporedepot.com` 4/8.

## Second run: multilingual reranker, new seed rules (2026-10-12, same corpus)

`jinaai/jina-reranker-v2-base-multilingual`. The new seed rules raise the proxy junk from 32 to **78**, all 78 in the fetched top 5 today. Still no hand labels: "relevant dropped" is 0/0 by construction.

| scorer | threshold | junk dropped | unlabelled dropped | fail-open | junk in top 5 after re-sort |
|---|---:|---:|---:|---:|---:|
| lexical:query | 0.125 | 55/78 | 111 | 58/190 | 23 |
| rerank:query | 0.0409 | 51/78 | 72 | 35/190 | 27 |
| rerank:query | 0.0773 | 57/78 | 118 | 56/190 | 21 |
| rerank:both | 0.101 | 59/78 | 111 | 55/190 | 19 |
| rerank:user | 0.0393 | 38/78 | 179 | 95/190 | 40 |

- **Against this proxy, word matching does about as well as the reranker**, because the new junk (Victoria's Secret, TfL, oyster.com) shares almost no words with the query. That says the proxy is easy, not that word matching is enough: hand labels decide.
- **The user's message is a worse target than the search query** with this model too (38/78 at the most aggressive cut point). The model's own query is already the distilled question.
- The MiniLM and multilingual runs are not comparable here: the seed rules changed between them (32 vs 78 junk).
- `label --scores-from` crashed with `KeyError: 'query'` on the M1's `labels.csv`: the reader assumed the comma-separated UTF-8 file the script writes. **Fixed:** the sheet is read with BOM, `;`/tab separators and Windows-1252 accepted; an unreadable sheet is refused with its header shown and never rewritten; every rewrite leaves `labels.csv.bak`.

## Third run: first hand labels (2026-10-12, same corpus, y=18, n=234)

| model, scorer | threshold | junk dropped | relevant dropped | unlabelled dropped | junk in top 5 after |
|---|---:|---:|---:|---:|---:|
| jina, rerank:query | 0.0258 | 71/234 | **0/18** | 0 | 163 |
| jina, rerank:query | 0.0409 | 118/234 | 4/18 | 1 | 116 |
| jina, rerank:both | 0.046 | 109/234 | 1/18 | 2 | 125 |
| MiniLM, rerank:query | 1.13e-05 | 65/234 | 2/18 | 3 | 169 |
| lexical:query | 0.125 | 125/234 | 4/18 | 37 | 109 |

- **The multilingual reranker is the only scorer with a zero-cost row** (0.0258: 71 junk dropped, nothing relevant, nothing unlabelled). MiniLM's scores sit at 1e-5 and it drops relevant results from its first row; it is out.
- **0/18 is weak evidence:** with 18 relevant labels, a true drop rate up to ~17 % is consistent with seeing none (rule of three). More `y` labels are needed before choosing a threshold.
- **Suspected wrong labels** in the "relevant dropped" lists: `en.wikipedia.org/wiki/Pink_(singer)` and `en.wikipedia.org/wiki/Oyster` (the shellfish) labelled `y` for mushroom queries. If they are mislabels, part of the 4/18 at 0.0409 is not a cost. Maintainer to check.
- **The ceiling is fail-open, not the scorer:** junk dropped stops near 136/234 for every scorer, and "junk in top 5 after" near 98. Searches return ~4.7 results, and when most of them are junk, fail-open still keeps 3. The report now counts these all-junk searches. Proposed: when every result scores below the threshold, keep them but **tell the model the results look off-topic** (a reporting guard, which can't remove anything) instead of handing them over silently.
- **Queries the scorer cannot judge:** a search whose query is literally `<search query>` (the model sent a template placeholder — an Odysseus/model bug, not counted yet), and the *Lactarius procera / Macrolepiota procera / giant milk cap* searches, where the model mixed up species names and the relevant results don't match the query. Scoring against query + user message (`rerank:both`) ranks those higher.
- Report change after this run: relevant drops are listed per threshold (where each is first dropped), not only at the strictest one.

## Fourth run: every result labelled (2026-10-12, same corpus, y=522, n=366)

**Who labelled:** 258 results by the maintainer, 630 by Claude (2026-10-12, at the maintainer's request; recorded in item 82 with the maintainer's agreement). The numbers below therefore partly measure agreement with Claude's judgement; a spot-check of 20–30 of Claude's labels is owed.

Multilingual reranker (`jinaai/jina-reranker-v2-base-multilingual`), fail-open at 3.

| scorer | threshold | junk dropped | relevant dropped | fail-open | junk in top 5 after |
|---|---:|---:|---:|---:|---:|
| rerank:query | 0.0258 | 71/366 (19 %) | **0/522** | 11/190 | 295 |
| rerank:query | 0.0409 | 120/366 (33 %) | 3/522 | 35/190 | 246 |
| rerank:query | 0.0773 | 166/366 (45 %) | 9/522 | 56/190 | 200 |
| rerank:both | 0.046 | 111/366 | 1/522 | 36/190 | 255 |
| lexical:query | 0.0435 | 71/366 | 5/522 | 30/190 | 295 |
| rerank:user | 0.0233 | 27/366 | 26/522 | 18/190 | 339 |

- **rerank:query is the candidate.** Up to 0.0409 the only relevant results lost come from the *Lactarius / Macrolepiota procera / giant milk cap* searches, where the model's query names the wrong species; at 0.0773, 6 of the 9 losses are those or `<search query>` searches. The cost sits in broken queries, not in normal ones.
- **rerank:user is unusable:** its scores are nearly flat (0.0232–0.0233 for good pink-oyster guides), so it drops relevant pages from its first row. Scoring against the user's message is out.
- **Word matching** drops relevant results from its first row (5/522) and is out.
- **Ceiling:** 24 searches have only junk; fail-open keeps 3 of each, so junk in the top 5 never falls below ~175 for any scorer. Those need the "results look off-topic" notice, not a stricter threshold.
- **Domains (labelled):** `en.wikipedia.org` 4 y / 32 n, `youtube.com` 0/19, `economictimes.indiatimes.com` 0/12, `victoriassecret.com` 0/29, `oyster.tfl.gov.uk` 0/10, `oyster.com` 0/7, `instagram.com` 0/6, `zhihu.com` 0/5, `seekingalpha.com` 0/5. Candidates for negative priors.
- **Proposed shape for Odysseus (not built):** rerank the result list against the search query with the multilingual reranker; drop below ~0.03–0.04; keep at least 3; when every result scores below the threshold, keep them and tell the model they look off-topic. Off by default, every decision logged.

## Built into Odysseus (2026-10-12, off by default)

- **What it does:** after `rank_search_results`, scores each result (title, snippet, domain) against the search query with `jinaai/jina-reranker-v2-base-multilingual`. It drops results below 0.035 (between the 0.0258 and 0.0409 rows above) but keeps at least 3, so the fetch slots and the model's list go to what is left. When nothing scores above the threshold, the results are kept and one line goes into the model's *SEARCH RESULTS SUMMARY*: "Relevance check: none of these results scored as relevant…". It covers every `comprehensive_web_search` caller: agent `web_search`, chat-mode web search, deep research and the search route.
- **Settings:** keys in `data/settings.json`, merged over the module's `DEFAULTS`: `web_filter_enabled` (false), `web_filter_threshold` (0.035), `web_filter_min_keep` (3), `web_filter_model`. They aren't in `DEFAULT_SETTINGS`; the Research topics panel's Settings tab sets six of them through `/api/web-filter/settings` (not `web_filter_notice_below`), and a UI settings save keeps them (`set_settings` starts from the loaded file). Picked up within 2 s (settings cache), no restart.
- **Fail-open:** disabled, empty query, missing fastembed, failed model download, model error or a wrong score count all return the results unchanged and log `[web-filter] skipped …`.
- **Log line per search:** `[web-filter] query=… kept=N/M threshold=… all_low=… ms=… dropped=[domain:score, …]`.
- **Tests:** `tests/test_web_filter.py` (14, of which 3 run the real `comprehensive_web_search` with providers and fetches stubbed). Eight mutations, all caught: on by default, errors propagate, no min_keep, notice never set, notice always set, result ignored at the call site, notice not written, keeps everything. The 41 existing search test files pass unchanged (426 tests, Linux venv, Python 3.13).
- **Verified live on the M1** (sections below): first search with model load 2.1 s. Memory next to Qwen/Bonsai not measured.
- **Not done, deliberately:** domain priors (no live data on their effect yet), and the replay's `<search query>` placeholder bug — that's a separate item.

## First live check (M1, 2026-10-12 13:38–13:43, local time)

- `[web-filter] on` logged at the first search after a restart (13:37). Searches before that (13:25–13:30) ran the old code: Odysseus had last started at 08:10 and the file changed at 13:24.
- *"pink oyster mushroom optimal fruiting temperature Celsius"*: **kept 3/5**, dropped `victoriassecret.com` 0.026 and `youtube.com` 0.024 (both labelled junk in the replay), **2109 ms** including the first model load. **`all_low=True`: the 3 kept results also scored below 0.035**, so the off-topic notice reached the model on a search that very likely had relevant guides. **Wrong notice.**
- Two gold-price searches: kept 5/5, ~345 ms each.
- **Cause:** one cut-off (0.035) served both as the drop threshold and the notice trigger. The drop threshold was measured on the labels; the notice's false-positive rate was never measured before shipping (CLAUDE.md §3: a guard that makes the model act).
- **Fixed:** the notice has its own cut-off, `web_filter_notice_below`, **default 0 = never**; it fires only when a search's best score is below it. The log line now has `best=`, `notice=` and the kept results with their scores. The replay report gets an *Off-topic notice* table per scorer (all-junk searches flagged vs searches with a relevant result flagged) to choose the cut-off from.

## More candidates and a decision log (2026-10-12, after the first live check)

- **More candidates:** while the filter is on, `comprehensive_web_search` asks the provider for `web_filter_candidates` (15) results instead of the normal count (5), scores all of them, and passes on the best — threshold and min_keep as before, **best score first, at most the normal count**. Junk is no longer replaced by nothing; it is replaced by the next relevant candidate. SearXNG returns 20–30 results per request and the code used to cut to 5, so the extra candidates cost no extra request there; key-based providers (Brave, Tavily, Serper) are asked for a larger page. Expected cost: scoring 15 instead of 5, estimated ~0.8–1 s per search on the M1 — predicted. **Measured: median 2,353 ms, max 2,610 ms** (3 searches, M1), more than twice the prediction; 10 candidates not tried yet. With the filter off nothing changes: the provider is asked for the normal count.
- **Order change while on:** results reach the model ordered by reranker score, not by `rank_search_results`.
- **Decision log:** one JSON line per filtered search in `data/logs/web_filter.jsonl` (all candidates: URL, title, snippet ≤500 chars, engine, score, kept, position), rotated to `.1` past 20 MB, switchable with `web_filter_decision_log`. Dropped results are recorded nowhere else (`app.db` only holds what the model saw). `bench_web_filter.py extract --from-decisions data/logs/web_filter.jsonl` turns it into a corpus for `label` / `run`.
- Tests: `tests/test_web_filter.py` 24, `tests/test_bench_web_filter.py` 35 (one runs writer → reader). Nine mutations, all caught (one only after adding a test where relevant candidates exceed the limit). 436 tests across the existing search test files pass.

## Research topics and per-source ratings (2026-10-12, built, used live 16:08)

Maintainer's choices: a **Research topics** button in the left icon bar and the sidebar tools list, right below Deep Research; **per-source** ratings with up/down **arrows** (SVG chevrons, no emoji); dropped results listed for rating too; starting topics **Biology, Finance, Cooking**.

- **Topics** (`src/research_topics.py`, `data/research_topics.json`): name, 1–10 example queries, on/off, plus one global `min_similarity` (0.35). A search goes to the enabled topic whose examples are closest (local FastEmbed model, cosine), else `other`. **Global, admin-edited**, not per user as first planned: the search layer has no user. **Only assigned while the relevance filter is on**; with it off, no model loads per search and `topic` is empty.
- **Search id:** every `comprehensive_web_search` call gets one (12 hex chars). It goes into the decision log (with `topic`) and onto every source.
- **Sources list now carries the dropped candidates**, flagged `"filtered": true`, plus `search_id`, `query`, `topic` and `score` on every entry. ⚠️ **`web_sources` in `app.db` metadata no longer equals "what the model saw" for searches made with the filter on**: test `filtered` before reading it that way. Tests check that dropped results never reach the model's text. `src/agent_tools/web_tools.py` now escapes `-->` in the SOURCES marker; before, a title containing it would have left the whole list in the model's text.
- **Ratings** (`src/web_ratings.py`, `data/web_ratings.jsonl`): per user, latest click wins, `clear` removes. API in `routes/web_feedback_routes.py`: `GET/PUT /api/research-topics` (PUT admin only), `POST/GET /api/web-ratings` (the caller's own only).
- **UI:** `static/js/research_topics.js` (panel), `static/js/source_ratings.js` (arrows, a collapsed "N filtered out by relevance" block with scores, ratings restored on render), hooked into `buildSourcesBox` in `chatRenderer.js`. Dropped results are kept out of the numbered list, so `[n]` still matches the model's citations. Sources without a search id (older chats, research sources) render as before.
- **Replay:** `bench_web_filter.py import-ratings [--owner cedrik]` turns the ratings into labels for rows already in the sheet; `extract --from-decisions` first for new searches.
- **Tests:** `tests/test_research_topics_and_ratings.py` (35, incl. the API with per-user isolation), `tests/test_source_ratings_js.py` (4, Node: split, escaping, unchanged old sources, filtered block; 5 mutations caught after one test was tightened), plus additions to the filter and replay tests: 97 across the five files. 593 existing tests that touch `index.html`, `chatRenderer`, the left bar or `app.py`, and 462 search tests, pass.
- **Seen live** 16:08–16:11 (section below): arrows, the filtered-out block, clicks stored; the panel in use. **Not reported:** ratings restored after a reload, the light theme.

## Search output cut at 10,000 characters (2026-10-12 15:00, M1, agent mode, Qwen 3.5 9B)

- **Seen:** *"whats the preferred temperature range of "pink oyster mushrooms" for pinning?"* → the answer began *"It's a race to protect the crop."* and explained a snippet. Its thinking: *"The user … cut off mid-sentence with 'It's a race to protect the ......'"*.
- **Checked in a copy of `app.db`:** the user message was stored intact. The `web_search` tool output is **exactly 10,000 chars**, **without** `IMPORTANT INSTRUCTIONS`, and ends mid-quote inside a fetched page's "Important Quotes". The race sentence sits at position 1,373: a search snippet in the summary, cut at 200 chars plus "...". The filter did its job (kept 5 of 15, dropped Victoria's Secret, YouTube, Instagram, Wikipedia).
- **Mechanism:** `WebSearchTool` cut the result with `text[:MAX_OUTPUT_CHARS]`. Five fetched pages (≤3,000 chars each, plus key points, TL;DR and quotes) push it past 10,000, so the cut removed the end marker and the instructions to answer the user's question, and the result ended mid-sentence. **Pre-existing, not caused by the filter**; it is unmeasured whether the filter makes it more frequent (it puts more substantial pages into the 5 fetch slots).
- **Fixed:** `src/search_output_fit.py`, one line in `src/agent_tools/web_tools.py`. When the result is too long, the fetched page blocks are shortened evenly at line or sentence ends (`[…page text shortened to fit]`); the sources, the summary and the closing instructions are kept whole. Text without the writer's markers falls back to the old cut. `tests/test_search_output_fit.py` (7, against the real writer); five mutations caught; 470 web/search tests pass. **Not seen live yet.**
- **Not changed:** snippets still end in "..." in the summary, which is what the model latched onto. If it recurs with the instructions intact, mark snippets as cut, e.g. `[snippet cut]`.
- **Measured 2026-10-12 (M1, copy of `app.db`, all assistant rows with a `web_search` tool event): 132 of 196 web searches (67 %) lost their closing instructions** (stored output ≥ 10,000 chars and no `IMPORTANT INSTRUCTIONS`). The stored tool output is what the model read (same 10,000 cap, SOURCES marker already stripped). So two thirds of past agent searches ended mid-page with no instruction to answer the question. That predates the filter; it may have contributed to earlier findings such as *"Web search derails on ambiguous common nouns"* and wrong-species drift, but that's unmeasured.
- **Still owed:** whether the 132 turns answered off-topic more often than the other 64.

## Research topics panel, second version (2026-10-12)

Maintainer's feedback on the first version: panel and field colours were inverted; wanted a **Topics** and a **Settings** tab, with topics styled like memories in the Brain panel.

- Rebuilt on the Brain panel's own classes (`memory-modal-content`, `memory-tabs`/`memory-tab`, `memory-tab-panel`, `admin-card`, `memory-item`, `memory-item-meta`, `memory-cat-badge`, `memory-item-btn`, `memory-item-edit-input`, `admin-switch`, `preset-range`), so colours come from the same CSS as Brain. Tabs use `data-rt-tab`/`data-rt-panel`, because `memory.js` wires every `[data-memory-tab]` on the page.
- **Topics tab:** one memory-style card per topic (name, examples, badges for searches and up/down counts, `off` badge), the admin switch for on/off (saves at once), edit (inline, like a memory) and delete (asks first); "+ Add topic"; an `other` card with its counts.
- **Settings tab:** relevance filter on/off, cut-off (slider 0.005–0.2), candidates (5–30), always keep (1–10), decision log on/off, topic-matching similarity (0.1–0.9), one Save button. Backed by new `GET/PUT /api/web-filter/settings` (PUT admin only; only the six `web_filter_*` keys, range-checked; written into `data/settings.json`, other settings untouched). The off-topic notice cut-off is deliberately not in the panel until it has been measured.
- Tests: settings validation and API (admin only, unknown keys refused, other settings untouched); two mutations caught. **The panel itself is unverified in a browser.**
- **Third pass (maintainer's feedback):** title icon in the accent colour and a topic count after "Topics", like "Memories"; a master switch at the top right with the Enabled/Disabled label, stored as `enabled` in `data/research_topics.json` (off = no topic matching at all, list greyed out at 30 %); "+ Add topic" on the left between the description and the list; per-topic switches at the top right of each card; switched-off topics greyed out instead of an `off` badge; no "Topic on/off" messages; in Settings, every filter option and the topic matching are greyed out and not clickable while the relevance filter is off (like Brain's settings). Test for the master switch (no model call while off).
- **Fourth pass:** the panel drags like Brain (`makeWindowDraggable`, `snapModalToZone`); settings save on change, no Save button; with Topics off the whole Topics tab greys like Skills; each switched-off setting greys only its own description.

## Live check of output fit and ratings (2026-10-12 16:08–16:11, M1, Qwen 3.5 9B, agent mode)

- **Output fit works live:** the `web_search` output was 9,641 chars, `IMPORTANT INSTRUCTIONS` present, 2 pages shortened.
- **Ratings work live:** three down-clicks in `data/web_ratings.jsonl` with search id, query, topic `biology`, score and `filtered` (one on a dropped result).
- **But the answer was about Pink the singer.** The model searched *"pink oyster mushrooms Pinatus djamor pinning temperature range fruiting"* (it misspelled *Pleurotus*). All 10 candidates were junk (Victoria's Secret, Pink (singer), TMZ, discography, Instagram, YouTube…). None reached 0.035, so always-keep passed on the 3 best junk results (0.025–0.033). The off-topic notice is off, so nothing told the model, and it answered about the singer. **This is the all-junk case the notice exists for**, and the first live search (13:38) showed the other side: good guides that also all scored under 0.035. A notice at the drop threshold would have misfired then, so the notice cut-off must come from the replay table (`run … | grep -A 13 "Off-topic notice"`), not a guess.
- **Display bug, fixed:** the filtered-out list was a `<details>` element, and `style.css` shrinks every `details .source-link` to small inline tags (tiny text, title and domain run together). Now a plain block with its own toggle; Node test added.

## Off-topic notice cut-off measured (2026-10-12, replay, 888 labelled results)

`rerank:query` (the live scorer): notice fires when a search's best score is below the cut-off.

| cut-off | all-junk searches flagged | searches with a relevant result flagged |
|---:|---:|---:|
| 0.025 | 1/29 | 0/161 |
| 0.03 | 2/29 | 0/161 |
| **0.035** | **6/29** | **0/161** |
| 0.05 | 12/29 | 3/161 (all `<search query>` placeholder searches) |

Recommended **0.035**: the highest cut-off with no wrong flags in the replay; it would have caught the 16:08 Pink (singer) search (best 0.033). Caveats: catches only a fifth of all-junk searches; the 13:38 live search had relevant guides that all scored under 0.035 (exact best score not logged then), and live snippets are longer than the replay's 200 chars. A wrong notice costs one extra search, not a wrong answer. **Set to 0.035 by the maintainer 2026-10-12** in `data/settings.json` (`web_filter_notice_below`); **check the decision log's `"notice": true` lines after a few days.**

## Ratings feed back into the filter (2026-10-12, built, log-only by default)

**What it does:** a ▼ on a source moves that site's reranker score down on later searches *in the same topic*; a ▲ moves it up. `src/rating_bias.py` (standard library only, also imported by the replay), one call site in `filter_results` (`src/web_filter.py`); no upstream file touched.

- **Bias per result**, from the current ratings of all users (latest click per user, search and URL wins; `clear` removes): site term `strength × (up − down) / (up + down + 2)` once the site has `web_filter_rating_min` (2) ratings in the topic, plus `±strength/2` for the exact URL, clamped to ±strength. A site's rating covers its subdomains (`webmd.com` → `m.webmd.com`, not `notwebmd.com`). Topic `other` or none: no bias.
- **Added to the logit, not the 0–1 score.** Live scores sit near 0.035, so a 0–1 offset would make every rating an absolute keep/drop. **Reach at the default strength 0.7 (odds ×2): at the threshold, only raw scores between ~0.018 and ~0.068 can cross 0.035. ⚠️ Corrected 19:21 from the live log: that bound is the threshold only. Searches return more candidates than the result count (`limit`, 5 at 19:21), and the cut to the best 5 happens at any score, so a bias can swap two close results anywhere** (two ▼ on `economictimes.indiatimes.com` in a topic take its 0.470 under `msn.com`'s 0.447; `test_replay_sees_a_rating_flip_at_the_limit_cut_far_above_the_threshold`). ⚠️ The settings ceiling 1.5 reaches ~0.008 to ~0.14, so a 0.01 result can be kept there (test pins it); keep strength ≤ 1.0 unless the replay says otherwise.
- **Unchanged:** `min_keep` fail-open (decision 2), best-first order, `limit`.
- **Modes** (`web_filter_rating_mode`): `off`; **`log` (default)**: computes everything, selection uses raw scores, nothing the model sees changes; `apply`: selection uses the biased scores. Settings in the Research topics panel's Settings tab (*Ratings*, *Rating strength*) and `PUT /api/web-filter/settings`.
- **Off-topic notice:** always on raw scores (decision 3, option (a)); the decision log's `notice_either` records whether option (c) would also have fired.
- **Logged:** `[web-filter] … ratings=log biased=N rating_changes=['near.com:kept→dropped']`; per result in `data/logs/web_filter.jsonl`: `bias`, `adjusted`, `rated_kept`; per search `rating_mode`, `notice_either`. Sources box data carries `rating_bias` (not shown by the JS yet).
- **Cache:** the ratings file is re-read only when its mtime or size changes.

### Decisions (maintainer, 2026-10-12)

1. All users' ratings count, like the global topics.
2. `min_keep` stays absolute: a down-rated site can still be kept by the fail-open; all-junk searches are the notice's job.
3. Notice on raw scores; (c) "raw **or** adjusted below the cut-off" is logged, to be adopted only if the replay shows it adds no wrong flag on the searches with a relevant result. Never (b) adjusted only: a ▲ on a mixed site (`en.wikipedia.org`: 4 y / 32 n in the labels) could lift an all-junk search over the cut-off and silence the notice. *(The maintainer asked for the explanation and did not pick; (a)-then-(c) was Claude's proposal, built as proposed.)*
4. Strength 0.7, `min_ratings` 2 (Claude's choice, at the maintainer's request).

### Benchmarks

- **Filter quality, replay:** `bench_web_filter.py run --dir … --ratings data/web_ratings.jsonl` adds a *Ratings* section at the live threshold (`--threshold`, default 0.035; `--notice-below` 0.035): per strength (0.3 / 0.7 / 1.0), searches with a bias, junk / relevant / unlabelled dropped, junk in the fetched top 5, the notice under (a) and (c), the change per chronological quarter (learning curve), and every flipped result with its URL and label. **Honesty rules, built in:** with `--rating-order time` (default) a search sees only ratings made before it (app.db's UTC converted to local time first), never ratings on its own `search_id`; `loo` uses later ratings too and the report says OPTIMISTIC. Labels whose query + URL match a rating are left out of the score (it says how many), so ratings are not graded against themselves. With no usable rating the report says so instead of reading 0 changes as safe. Topics: the logged one; searches recorded before topics existed get `assign_topic` (embedding model, loaded only if a rating could apply).
- ⚠️ **What the replay can see:** every app.db search (07-17 → 10-05) predates every rating, so under `time` order only decision-log searches (since 10-12 13:38) can show an effect. Build that corpus with `extract --from-decisions data/logs/web_filter.jsonl`; it now keeps `search_id` and `topic`.
- **Replay gap fixed 19:30:** `decide` ignored the live result limit, so on decision-log corpora it counted limit-cut results (e.g. `cnbc.com` 0.297 at 19:21) as kept and could not show rating flips at that cut. `extract --from-decisions` now keeps `limit` and `decide` applies it like `select`; app.db corpora have no limit and are unchanged. Mutation (limit ignored): 2 failures.
- **Speed:** `bench_web_filter.py rating-speed [--lines 10000 --results 15]`, synthetic ratings in a temp dir, no model. Sandbox (Linux, 2026-10-12): 10,000 ratings (1.5 MB) re-read in 59 ms after each new rating, 0.002 ms per search with an unchanged file, 0.27 ms bias for 15 results — against ~2,350 ms for the reranker. M1 not measured.
- **Answer quality end to end:** not built. Needs a provider that replays recorded results (live search is not repeatable) and ~20 runs per variant; worth it only if the replay shows the drops improve.

### Verification

- **Sandbox only (Linux venv from `requirements.txt`, `DATABASE_URL=sqlite:///:memory:`):** `tests/test_rating_bias.py` (27) plus the five filter/ratings files, 131 passed; `test_research_topics_and_ratings.py`'s settings-key test updated for the three new keys. Full suite in the sandbox (`-n auto`): 8,002 passed, 4 skipped, 1 failed — `test_integrations_url_join.py::test_api_call_root_path_has_no_trailing_slash`, which fails the same way without this change (the sandbox cannot resolve DNS). **M1, 2026-10-12, after merging into `dev` (`41ed3187`): 8,013 passed, 3 skipped.**
- **Live, M1, 19:21:** `[web-filter] query='current silver price today' kept=5/10 … ms=2289 … ratings=log biased=0 rating_changes=[]` — new code running; 0 biased as expected (the 3 ratings are in Biology; this search's topic was not checked). Of the 5 dropped, only `freep.com` (0.047) was anywhere near the threshold; the other 4 (0.19–0.45) were cut by the limit.
- **Mutations (`test_rating_bias.py` failures):** clamp removed 1; `+2` removed 4; topic ignored 2; bias in 0–1 space 1; `log` mode acts 1; notice on adjusted scores 2; call site removed 7; replay sees later ratings 3; replay sees the search's own ratings 1; rated labels kept in the score 1.
- **Replay smoke run** on a synthetic 8-search corpus (lexical scorer): section renders, 4 rated labels left out, time order respected. No real data run.
- **JS unverified** (`node --check` only): manual step — open Research topics → Settings, set *Ratings* to *Apply*, confirm `"web_filter_rating_mode": "apply"` in `data/settings.json`, set it back to *Log only*.

## Verification

- **M1, 2026-10-12:** the five test files, 104 passed (`test_web_filter.py`, `test_bench_web_filter.py`, `test_research_topics_and_ratings.py`, `test_source_ratings_js.py` (Node), `test_search_output_fit.py`); full suite later the same day 7,977 passed, 3 skipped. Mutation counts are in each section above.
- **Live, M1, 2026-10-12 13:38–16:11:** filter drops, `[web-filter]` lines, decision log, output fit, ratings, panel (sections above).
- **Cloud sandbox:** the replay and every test above except the real reranker (no model download there).

## Open

0. **A/B verdict, 2026-10-13 (webhard, 50 task runs per arm, Qwen 3.5 9B LM Studio): keep it on.** Pass rates tie (43/50 on, 42/50 off); with the filter Qwen needs half the tool calls and 52 vs 74 s per task; `bench_web_seen.py`: 49 % of shown results off-topic without it, 0 % with it. Nearly all of that junk comes from Bing (50 % of its results off-topic in the decision log; google cse 1 %), and the other SearXNG engines are blocked here, so the filter is what makes Bing usable. Cost ≈ 0.5 GB RAM in Odysseus. Details: [benchmark.md](../benchmark.md) *Results*, [qwensetup.md](../qwensetup.md).
1. **Notice firings:** after a few days, read the decision log's `"notice": true` lines — right searches flagged? (`grep '"notice": true' data/logs/web_filter.jsonl | wc -l`, then read the queries).
2. **Speed:** measured 2026-10-12 evening from the decision log (`ms` by candidate count, setting 15; a provider returning fewer gives a 10-candidate search): **10 candidates: 2 searches, median 2,353 ms; 15: 2 searches, median 2,610 ms.** Read as ~50 ms per extra candidate on top of a ~1.8 s fixed cost (a two-point fit, n = 2 each), so going to 10 would save ~0.25 s per search and leave fewer replacements for dropped results: **keep 15.** ⚠️ `ms` starts before `_load_model`, so the first search after each restart includes loading the 1.1 GB model; there were restarts today, so the fixed cost may be partly load time. Next, cheap: time the load separately in the `[web-filter]` line (reporting only), then re-read the fixed cost.
3. **Spot-check 20–30 of Claude's 630 labels** (*Fourth run*).
4. Whether the 132 truncated searches answered off-topic more often than the other 64 (*Search output cut*).
5. Misspelled queries (*Pinatus*): the filter can only flag them; a separate item if it recurs.
6. **Ratings bias: built, log-only** (*Ratings feed back into the filter*). Next: after a few days with ratings, `extract --from-decisions` + `run --ratings`, read the flips and `notice_either`, then decide `apply`. M1 suite owed. Not built, waiting for data: `[snippet cut]` marking; the notice slider in the Settings tab; the replay's `<search query>` placeholder bug (own item).
