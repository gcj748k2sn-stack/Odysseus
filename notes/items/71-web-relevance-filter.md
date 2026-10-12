# 71. A relevance filter for web results — measure it offline first

Open item. Its row in the [todo.md](../todo.md) index carries the current status; this file is the full record.

---

**Idea (maintainer, 2026-10-12):** a small "decision" model between web retrieval and the thinking model (Qwen 3.5 / Bonsai 2) that decides what reaches it. **Proposed shape:** a cross-encoder reranker (fastembed, already a dependency), not a generative model. It scores (question, passage) pairs in milliseconds and does not compete with the chat model for LM Studio. Two levels: (1) the search result list (title/URL/snippet), where *"Web search derails on ambiguous common nouns"* and *"today/latest routes web_search to the news category"* happen; (2) paragraphs of fetched pages, where most of the context, and so most of the prefill time, goes.

**Nothing is built into Odysseus.** What exists is the offline replay: `scripts/bench_web_filter.py` with `tests/test_bench_web_filter.py` (26 tests).

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
   After a first `run` (step 4), refill the sheet with a sortable `score` column and label the lowest scores first, since those are what a filter would drop:
   ```
   ./venv/bin/python scripts/bench_web_filter.py label --dir $RUN --scores-from rerank:query
   ```
   Open it in Numbers/Excel and put `y` (relevant) or `n` (junk) in the `label` column. Unlabelled rows are ignored. Labels are keyed on query + URL, so a later `extract` keeps them. 50–100 labelled rows across a dozen searches already give a usable first reading; label some relevant ones too, otherwise the report cannot show the cost.
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

## Verification

- 2026-10-12, cloud sandbox (Linux, Python 3.13, `requirements.txt` in a fresh venv): `tests/test_bench_web_filter.py` 22 passed; 26 after the 11:19 fixes (grid, seed rules, score column), four more mutations, all caught. Ten mutations, nine caught: fail-open removed; snippet dots kept; substring domain match; user message taken from after the search; parser not stopping at page content; chunk order; stopwords counted; budget keeping nothing; no seed fallback. Not caught: a URL-less result kept when the next `[i]` line starts. The writer always writes the URL line, so this is not reachable from recorded data.
- End-to-end `extract → label → run (lexical) → pages --lexical` ran on a small database built from the real writer's output.
- **The reranker path is unverified:** the sandbox could not download fastembed models. The adapter is tested with a fake model (logit order, sigmoid, length check). Owed: step 4 on the M1.
- **Not yet measured on the real corpus:** everything. Next step: steps 2–4 on the M1, label, read the report.
