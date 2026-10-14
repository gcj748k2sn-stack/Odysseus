# Session log

Brief, dated summaries of what each session *did* — not findings (those live in
[todo.md](todo.md) and [resolvedissues.md](resolvedissues.md)), just scope and
state changes, so the next session isn't starting cold. Newest first. Keep each
entry to a few lines — if it needs more, the detail belongs in `todo.md` or
`resolvedissues.md` and this should just link to it.

Keep roughly the last working day here; older entries move verbatim to
[archive/](archive/) (history, not current state): 2026-10-09 (10:55) to 10-10 in
[archive/session-log-2026-10-09.md](archive/session-log-2026-10-09.md),
2026-10-08 (to 10-09 01:40) in
[archive/session-log-2026-10-08.md](archive/session-log-2026-10-08.md), 2026-10-07 in
[archive/session-log-2026-10-07.md](archive/session-log-2026-10-07.md), 2026-10-06 in
[archive/session-log-2026-10-06.md](archive/session-log-2026-10-06.md),
2026-07-30 to 2026-10-06 00:20 in
[archive/session-log-until-2026-10-06.md](archive/session-log-until-2026-10-06.md).

---

## 2026-10-13 — webhard suite to 10 tasks; filter A/B read (cloud session)

- 📊 **Filter A/B on `research` (chain-20261013-0001, M1):** off 13/15, on 10/15, inside the CIs; with fetch-error runs left out off 8/9, on 8/8. Swap 8–14.5 GB all chain, so times are noise. Only `res_gnats` r3 (filter on, gave up after ~17 searches) could be the filter's; check its `[web-filter]` lines. 12 Oct sysmon: LM Studio and Ollama both ~8 GB RSS; Ollama 691 page-outs vs 2,372.
- 🆕 **`webhard` 6 → 10 tasks** (`wh_amazon_length`, `wh_brocken_hoehe`, `wh_lionsmane_typo`, `wh_ssd1306_addr`), keys web-checked; `--quick` 3 → 5. Brought the unmerged `jolly-goodall` webhard commit onto this branch by file copy (same content). Sandbox (Python 3.13 scratch venv): 13 `test_bench_*` files, 250 passed; 6 of 6 mutations of the new checks caught. M1 suite owed.
- 🆕 Chain phase `qwen-web` (webhard ×2 on Qwen/LM Studio only, so sysmon and `BENCH_POWER=1` cover a single-backend run); `bash -n` only.
- 📊 **Webhard on Qwen/LM Studio ×2 (M1, 08:52, after a reboot): 19/20** after fixing a Brocken checker bug (18/20 as scored); 23 W avg, swap +9.6 GB from a clean start. Details in benchmark.md *Results*. One real failure: pink oyster r2 hit the round budget after 23 searches.
- 🆕 `scripts/bench_web_seen.py`: scores what each web_search showed the model, both A/B arms, after the run; `bench_agent.py` now keeps the whole web_search output (12,000 chars). 8 tests, 4 mutations caught; not run on real records. Only runs started after merging it are readable.
- 📊 **Filter A/B on webhard (M1, 09:38–11:40):** pass tie (off 27/30 after a German-check fix, on 25/30); filter-on needs half the tool calls (1.5 vs 3) and is faster per task (56 vs 68 s); reranker ≈ 0.4–0.6 GB in Odysseus. 5 of 9 failures in both arms: Qwen hits the round budget without answering. Details in benchmark.md *Results*.
- 📊 **Chain 12:13–16:24 (M1):** A/B pooled 43/50 on vs 42/50 off, 52 vs 74 s/task → filter kept on; webhard Bonsai 10/10, Ollama 7/10, LMS 27/30; knowledge full Qwen 43/48 vs Bonsai 38/48; research dropped to 6/10 (unexplained). Overview page updated. Details in benchmark.md *Results*.
- 🆕 **Item 85 filed:** the tool budget ends the turn without an answer (no tool-free round, unlike the loop-breaker); ≥ 8 benchmark runs today. Plan and effort (S) in its file. SearXNG: only bing and google cse work (qwensetup.md).
- 🔧 **Item 85 built:** `src/budget_answer.py` + call site at `budget_hit` (one tool-free answer round; intent nudge off in answer rounds). Sandbox: `tests/test_budget_answer.py` 9 passed, 6/6 mutations caught; full sandbox suite: see the item. M1 suite + webhard/research benchmark owed. `agent_max_tool_calls` = 20 on the M1.
- 🐞🔧 **Item 85 first live run (evening):** answer round never fired — the budget ran out on the last allowed round (approval card → fresh 20/20 limits, ~1 call per round). Fixed 10-14: one round past the cap only for a forced answer. 11 tests, mutations caught; quick M1 check (`res_gold2000`, `res_gnats` ×2) owed.
- ✅/❌ **Item 85 live (10-14, budget lowered to 4):** answer round fires (2 log lines, 2 answers), but both answers guessed a wrong year (2011). Added a facts-only instruction and Odysseus's own "budget ran out, may be incomplete" notice above the answer; rerun of the budget-4 check owed.
- ✅ **Item 85 verified live (budget 1 ×3, 12:41):** notice on top, 0 invented answers (r3 correct). Open: answer round at the round cap too? (`agent_max_rounds` back to 20.) Bigger run `qwen-web qwen` (afternoon): webhard 20/20, research 7/10, no budget stop (item 85 not exercised); report crash with `--split-runs` over two suites fixed (`9c13b4d`). **`res_gnats` "7 bullets" was a checker bug** (counted the source list) — fixed, re-score with `--regrade`. Overview page rebuilt as a progress record.
- ➡️ Decide item 85's round-cap question; bigger run when convenient; find out why research fell to 6/10; read pink oyster r2's `[web-filter]` lines.

---

## 2026-10-12 (late) — ratings bias the web filter: built, log-only (cloud session)

- 🆕 `src/rating_bias.py`, call site in `filter_results`: ▲/▼ shift a site's reranker logit in its topic (±0.7 default, `min_keep` unchanged, notice on raw scores). Default mode **`log`**: computes and logs, changes nothing. Replay `run --ratings` (time-ordered, own and rated labels excluded) and `rating-speed`. Decisions and benchmarks in [items/82-web-relevance-filter.md](items/82-web-relevance-filter.md) (*Ratings feed back into the filter*).
- ✅ Sandbox: 131 tests across six files, 10 mutations caught. **M1 (merged into `dev`, `41ed3187`): 8,013 passed**; live in log mode 19:21. JS still unverified (panel setting).
- 📊 **Web phase 19:38–20:50 (M1):** research ×2 per backend — Qwen LM Studio 10/10 (15 min), Qwen Ollama 9/10 (15 min), Bonsai 9/10 (39 min); details and the fetch-429 finding in [benchmark.md](benchmark.md) *Results*. `bench_chain.sh` had a stale `qwen35` target (fixed); `bench_agent.py report` gained `--split-runs` / `--regrade` and counts 429s as environment errors.
- 🆕 Late: `bench_agent.py run --web-filter on|off` and chain phase `filter-ab` (ABBA, Qwen LM Studio); filed **item 84** (HTTP 429 not remembered, so rate-limited pages are re-fetched).
- 🆕 Night: **`webhard` suite** (6 web tasks provoking off-topic results: ambiguous nouns, a misspelled Latin name, German *Essen*, grow-shop results), keys checked by web search, 33 sample tests, 6 mutations caught; `filter-ab` now defaults to it. Not run on a model yet.
- 🔧 19:30: the live log showed most "dropped" results were cut by the 5-result limit, not the threshold, so ratings can swap results at any score there (the notes' reach claim corrected); the replay now applies the limit too.
- ➡️ After a few days of ratings: `extract --from-decisions`, `run --ratings`, read the flips, then decide `apply`.

---

## 2026-10-12 (evening) — notes repaired; item 64 decisions recorded (cloud session, notes only)

- ✅ **Closed 13, 25, 52, 54, 55** (maintainer's decision, item 64): rows and conclusions moved to resolvedissues.md. ⚠️ Their files `notes/items/13-…`, `52-…`, `54-…` are **still in `items/`**: the move to `archive/items/` was refused by the session's permission classifier. Commands are in the hand-off.
- 🧹 **Stale state fixed in todo.md:** rows and bodies of 58, 68, 70, 72, 74–76, 79, 80 said "uncommitted" but are committed (hashes now in each); item 43's "preset disabled" warning (back on since 10-09); the *Next* list rewritten (it still led with item 70); open/closed counts were 36/40, now 35/53 (counted from the tables). Item 82's file notes that its commits say "item 71".
- **Item 64:** §4 decided (remove the document diagnostics if `[doc-put-404]` count is zero). The removal was **not made**: the count needs the M1's logs, and the classifier refused the edit. §9 parked; §10 `.env.bak.before-lmstudio` deleted by the maintainer (it differed from `.env` only by a missing `LM_STUDIO_URL` line).
- 📦 Session-log entries of 10-09 and 10-10 moved to the archive.
- ✅ **Later: item 34 closed, diagnostics removed.** Maintainer's count: one `[doc-put-404]` (the 07-31 repro) in logs from 07-12, 64 stream opens. Removed `[doc-put-404]`, `_stackFrames`, `switchAway`; `node --check` and `py_compile` only — **JS unverified**: manual step, open a document, type one character, confirm one `[doc-save] target=… stamp=… len=…` console line with no `via` lines. M1 suite owed.
- 🐞🔧 **Item 83 found and fixed (17:53–18:10):** typing into an empty editor saved only the first character (server `"h"` for editor "hi", confirmed by the maintainer). One-line stamp in `_autoCreateFromInput` (`d0de5b6`). ✅ **Verified live 18:10 and closed:** new doc `0422a71f` saved `"hi"`; M1 suite 7,977 passed; `dev` pushed by the maintainer. `app.db` copy: no other one-character document.
- **Item 64 round 2 (18:30):** §1 lints **kept** (recorded under item 2a). §3 built: a recovered failure is still reported, with *"(a later `<tool>` call this turn succeeded)"* (`src/turn_report.py`; recorded under item 11). §8 dropped — the M1 already runs `-n auto`. §10 built: `tests/test_bench_web_intent_wiring.py` pins the benchmark's `WEB_INTENT_RE` copy to the route's inline regex. §5 checked in the tree (bench preset `qwen35ol32k` uses the tag); M1 check handed over.
- 🧪 Sandbox (Python 3.13 scratch venv, outside the repo): the 24 test files touching `turn_report`/`bench_agent`, 362 passed; mutations: 5 of 5 caught. **Found on the way:** a test loading `scripts/bench_agent_tasks.py` passed only after another file had put `scripts/` on `sys.path` (its bare `import bench_knowledge_tasks`); both new loaders now add it. M1 suite owed.
- 🐞 **M1 suite 18:40: 1 failed** — `test_route_with_wait_for_probe_returns_the_probe_failure`, order-dependent, not from this session's change. Reproduced in the sandbox with `test_research_endpoint_owner_scope.py` → `test_security_regressions.py::test_require_user_rejects_unauthenticated` → the probe test: the middle test pops `src.auth_helpers` from `sys.modules`, the string-path patch lands on the module still on the `src` package, the route's in-function import loads a fresh copy. Fixed in the victim (patch `importlib.import_module("src.auth_helpers")`); that order now passes. ✅ M1 suite 7,986 passed, 0 failed; `dev` pushed at `8a2598b`.
- ⏸ Item 64 §5: 72 chats pin `qwen3.5:9b-32k` → model kept, parked with the migration recipe.
- ➡️ **Next:** the *Next* list in todo.md.

---

## 2026-10-12 — item 82: web relevance filter built, live, on (cloud session + M1)

- 🆕 Replay `scripts/bench_web_filter.py`; corpus of 888 results all labelled (258 by the maintainer, 630 by Claude). Built `src/web_filter.py` (jina multilingual reranker, threshold 0.035, keep ≥ 3, 15 candidates, best first, decision log `data/logs/web_filter.jsonl`), research topics (`src/research_topics.py`, panel below Deep Research), per-source ▲/▼ ratings (`data/web_ratings.jsonl`), and `src/search_output_fit.py` (search output no longer loses its closing instructions at 10,000 chars; that had hit 132 of 196 past searches).
- ✅ **Live on the M1** (filter on, notice cut-off 0.035 set by the maintainer): drops junk, output fit 9,641 chars with instructions, ratings stored, panel used. **15 candidates cost median 2.35 s per search** (3 searches; predicted ~1 s — wrong).
- 🔧 Same day, maintainer's own work: `src/edit_gutter.py` (strips a copied line-number gutter from edit REPLACE text); its test patched a module by text path and failed only in the full suite → now patches the imported module object. `test_bench_agent_skip.py` preset name updated. **M1 suite: 7,977 passed, 3 skipped.**
- ➡️ **Open:** see the *Open* list at the end of [items/82-web-relevance-filter.md](items/82-web-relevance-filter.md) — first, check `"notice": true` lines in the decision log after a few days; try 10 candidates for speed.

---
