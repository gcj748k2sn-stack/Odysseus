# 71. A relevance filter for web results — measure it offline first

Open item. Its row in the [todo.md](../todo.md) index carries the current status; this file is the full record.

---

**Idea (maintainer, 2026-10-12):** a small "decision" model between web retrieval and the thinking model (Qwen 3.5 / Bonsai 2) that decides what reaches it. **Proposed shape:** a cross-encoder reranker (fastembed, already a dependency), not a generative model. It scores (question, passage) pairs in milliseconds and does not compete with the chat model for LM Studio. Two levels: (1) the search result list (title/URL/snippet), where *"Web search derails on ambiguous common nouns"* and *"today/latest routes web_search to the news category"* happen; (2) paragraphs of fetched pages, where most of the context, and so most of the prefill time, goes.

**Nothing is built into Odysseus.** What exists is the offline replay: `scripts/bench_web_filter.py` with `tests/test_bench_web_filter.py` (33 tests).

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

## Verification

- 2026-10-12, cloud sandbox (Linux, Python 3.13, `requirements.txt` in a fresh venv): `tests/test_bench_web_filter.py` 22 passed; 26 after the 11:19 fixes (grid, seed rules, score column), four more mutations, all caught. Ten mutations, nine caught: fail-open removed; snippet dots kept; substring domain match; user message taken from after the search; parser not stopping at page content; chunk order; stopwords counted; budget keeping nothing; no seed fallback. Not caught: a URL-less result kept when the next `[i]` line starts. The writer always writes the URL line, so this is not reachable from recorded data.
- End-to-end `extract → label → run (lexical) → pages --lexical` ran on a small database built from the real writer's output.
- **The reranker path is unverified:** the sandbox could not download fastembed models. The adapter is tested with a fake model (logit order, sigmoid, length check). Owed: step 4 on the M1.
- **Not yet measured on the real corpus:** everything. Next step: steps 2–4 on the M1, label, read the report.
