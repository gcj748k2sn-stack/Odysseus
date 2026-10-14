# Session log

Brief, dated summaries of what each session *did* — not findings (those live in
[todo.md](todo.md) and [resolvedissues.md](resolvedissues.md)), just scope and
state changes, so the next session isn't starting cold. Newest first. Keep each
entry to a few lines — if it needs more, the detail belongs in `todo.md` or
`resolvedissues.md` and this should just link to it.

Keep roughly the last working day here; older entries move verbatim to
[archive/](archive/) (history, not current state): 2026-10-12 in
[archive/session-log-2026-10-12.md](archive/session-log-2026-10-12.md), 2026-10-09 (10:55) to 10-10 in
[archive/session-log-2026-10-09.md](archive/session-log-2026-10-09.md),
2026-10-08 (to 10-09 01:40) in
[archive/session-log-2026-10-08.md](archive/session-log-2026-10-08.md), 2026-10-07 in
[archive/session-log-2026-10-07.md](archive/session-log-2026-10-07.md), 2026-10-06 in
[archive/session-log-2026-10-06.md](archive/session-log-2026-10-06.md),
2026-07-30 to 2026-10-06 00:20 in
[archive/session-log-until-2026-10-06.md](archive/session-log-until-2026-10-06.md).

---

## 2026-10-14 — item 85 live-verified; checker fixes; progress page (cloud session + M1)

- ✅ **Item 85** (tool budget → one tool-free answer round, facts-only instruction, ⚠️ notice; one round past the cap if needed) **verified live at budget 1 ×3**: 0 invented answers (2 of 2 before the instruction). Open: answer round at the round cap too — moot while `agent_max_rounds` is 20. Record: [items/85-tool-budget-ends-turn-without-answer.md](items/85-tool-budget-ends-turn-without-answer.md).
- 📊 **Qwen/LM Studio afternoon:** webhard 20/20, research **9/10** (re-scored), knowledge 42/48; no budget stop. Details in [benchmark.md](benchmark.md) *Results*.
- 🐞🔧 **Checker bugs, not model misses:** `res_gnats` counted the cited-source list as bullets (fixed `e6923f2`; re-score moved 4 task runs); report crash with `--split-runs` over two suites (`9c13b4d`).
- 📄 Overview page (claude.ai artifact *Odysseus Model Benchmarks*) rebuilt as the progress record: summary, run log, fixes, open problems.
- ➡️ Nothing owed on the M1 except the full suite after the last merge. Candidates: item 84 (429 re-fetch), a keyed search API (SearXNG has only bing + google cse), LM Studio at 48k context.

---

## 2026-10-13 — webhard to 10 tasks; filter A/B; item 85 filed and built (cloud session + M1)

- 🆕 `webhard` 6 → 10 tasks, `bench_web_seen.py` (scores what each search showed the model), chain phase `qwen-web`, power/memory per step. Brocken German check fixed twice.
- 📊 **Filter A/B on webhard (50 task runs per arm):** pass tie (43/50 on, 42/50 off), filter-on 52 vs 74 s per task and half the tool calls; junk seen by the model 49 % → 0 %; reranker ≈ 0.5 GB. **Kept on.** Bing supplies the junk (50 % off-topic); every other SearXNG engine is blocked from this IP ([qwensetup.md](qwensetup.md)).
- 📊 Webhard by backend: Qwen LMS 27/30, Ollama 7/10, Bonsai 10/10; knowledge full Qwen 43/48 vs Bonsai 38/48. Research 6/10 that afternoon = budget stops (→ item 85) + missing links.
- 🆕🔧 **Item 85** filed and built the same evening; first live run showed the budget hit on the last allowed round (fixed 10-14).

---

