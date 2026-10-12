# Session log

Brief, dated summaries of what each session *did* — not findings (those live in
[todo.md](todo.md) and [resolvedissues.md](resolvedissues.md)), just scope and
state changes, so the next session isn't starting cold. Newest first. Keep each
entry to a few lines — if it needs more, the detail belongs in `todo.md` or
`resolvedissues.md` and this should just link to it.

Keep roughly the last working day here; older entries move verbatim to
[archive/](archive/) (history, not current state): 2026-10-08 to 10-09 in
[archive/session-log-2026-10-08.md](archive/session-log-2026-10-08.md), 2026-10-07 in
[archive/session-log-2026-10-07.md](archive/session-log-2026-10-07.md), 2026-10-06 in
[archive/session-log-2026-10-06.md](archive/session-log-2026-10-06.md),
2026-07-30 to 2026-10-06 00:20 in
[archive/session-log-until-2026-10-06.md](archive/session-log-until-2026-10-06.md).

---

## 2026-10-12 — item 71: web relevance filter built, live, on (cloud session + M1)

- 🆕 Replay `scripts/bench_web_filter.py`; corpus of 888 results all labelled (258 by the maintainer, 630 by Claude). Built `src/web_filter.py` (jina multilingual reranker, threshold 0.035, keep ≥ 3, 15 candidates, best first, decision log `data/logs/web_filter.jsonl`), research topics (`src/research_topics.py`, panel below Deep Research), per-source ▲/▼ ratings (`data/web_ratings.jsonl`), and `src/search_output_fit.py` (search output no longer loses its closing instructions at 10,000 chars; that had hit 132 of 196 past searches).
- ✅ **Live on the M1** (filter on, notice cut-off 0.035 set by the maintainer): drops junk, output fit 9,641 chars with instructions, ratings stored, panel used. **15 candidates cost median 2.35 s per search** (3 searches; predicted ~1 s — wrong).
- 🔧 Same day, maintainer's own work: `src/edit_gutter.py` (strips a copied line-number gutter from edit REPLACE text); its test patched a module by text path and failed only in the full suite → now patches the imported module object. `test_bench_agent_skip.py` preset name updated. **M1 suite: 7,977 passed, 3 skipped.**
- ➡️ **Open:** see the *Open* list at the end of [items/71-web-relevance-filter.md](items/71-web-relevance-filter.md) — first, check `"notice": true` lines in the decision log after a few days; try 10 candidates for speed.
- ➡️ **Still open from 10-09:** item 70 (next, high priority); owed benchmark runs (Qwen 0.6 `json_output` r2 via `--resume`, Bonsai full suite); the custom-preset decision.

---
