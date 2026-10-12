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

## 2026-10-12 (evening) — notes repaired; item 64 decisions recorded (cloud session, notes only)

- ✅ **Closed 13, 25, 52, 54, 55** (maintainer's decision, item 64): rows and conclusions moved to resolvedissues.md. ⚠️ Their files `notes/items/13-…`, `52-…`, `54-…` are **still in `items/`**: the move to `archive/items/` was refused by the session's permission classifier. Commands are in the hand-off.
- 🧹 **Stale state fixed in todo.md:** rows and bodies of 58, 68, 70, 72, 74–76, 79, 80 said "uncommitted" but are committed (hashes now in each); item 43's "preset disabled" warning (back on since 10-09); the *Next* list rewritten (it still led with item 70); open/closed counts were 36/40, now 35/53 (counted from the tables). Item 82's file notes that its commits say "item 71".
- **Item 64:** §4 decided (remove the document diagnostics if `[doc-put-404]` count is zero). The removal was **not made**: the count needs the M1's logs, and the classifier refused the edit. §9 parked; §10 `.env.bak.before-lmstudio` deleted by the maintainer (it differed from `.env` only by a missing `LM_STUDIO_URL` line).
- 📦 Session-log entries of 10-09 and 10-10 moved to the archive.
- ✅ **Later: item 34 closed, diagnostics removed.** Maintainer's count: one `[doc-put-404]` (the 07-31 repro) in logs from 07-12, 64 stream opens. Removed `[doc-put-404]`, `_stackFrames`, `switchAway`; `node --check` and `py_compile` only — **JS unverified**: manual step, open a document, type one character, confirm one `[doc-save] target=… stamp=… len=…` console line with no `via` lines. M1 suite owed.
- 🐞🔧 **Item 83 found and fixed (17:53–18:10):** typing into an empty editor saved only the first character (server `"h"` for editor "hi", confirmed by the maintainer). One-line stamp in `_autoCreateFromInput`; `node --check` only, live check owed (steps in todo.md).
- ➡️ **Next:** item 83's live check; then the *Next* list in todo.md.

---

## 2026-10-12 — item 82: web relevance filter built, live, on (cloud session + M1)

- 🆕 Replay `scripts/bench_web_filter.py`; corpus of 888 results all labelled (258 by the maintainer, 630 by Claude). Built `src/web_filter.py` (jina multilingual reranker, threshold 0.035, keep ≥ 3, 15 candidates, best first, decision log `data/logs/web_filter.jsonl`), research topics (`src/research_topics.py`, panel below Deep Research), per-source ▲/▼ ratings (`data/web_ratings.jsonl`), and `src/search_output_fit.py` (search output no longer loses its closing instructions at 10,000 chars; that had hit 132 of 196 past searches).
- ✅ **Live on the M1** (filter on, notice cut-off 0.035 set by the maintainer): drops junk, output fit 9,641 chars with instructions, ratings stored, panel used. **15 candidates cost median 2.35 s per search** (3 searches; predicted ~1 s — wrong).
- 🔧 Same day, maintainer's own work: `src/edit_gutter.py` (strips a copied line-number gutter from edit REPLACE text); its test patched a module by text path and failed only in the full suite → now patches the imported module object. `test_bench_agent_skip.py` preset name updated. **M1 suite: 7,977 passed, 3 skipped.**
- ➡️ **Open:** see the *Open* list at the end of [items/82-web-relevance-filter.md](items/82-web-relevance-filter.md) — first, check `"notice": true` lines in the decision log after a few days; try 10 candidates for speed.

---
