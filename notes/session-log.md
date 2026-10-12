# Session log

Brief, dated summaries of what each session *did* — not findings (those live in
[todo.md](todo.md) and [resolvedissues.md](resolvedissues.md)), just scope and
state changes, so the next session isn't starting cold. Newest first. Keep each
entry to a few lines — if it needs more, the detail belongs in `todo.md` or
`resolvedissues.md` and this should just link to it.

Keep roughly the last working day here; older entries move verbatim to
[archive/](archive/) (history, not current state): 2026-10-08 (to 10-09 01:40) in
[archive/session-log-2026-10-08.md](archive/session-log-2026-10-08.md), 2026-10-07 in
[archive/session-log-2026-10-07.md](archive/session-log-2026-10-07.md), 2026-10-06 in
[archive/session-log-2026-10-06.md](archive/session-log-2026-10-06.md),
2026-07-30 to 2026-10-06 00:20 in
[archive/session-log-until-2026-10-06.md](archive/session-log-until-2026-10-06.md).

---

## 2026-10-12 — item 82: web relevance filter built, live, on (cloud session + M1)

- 🆕 Replay `scripts/bench_web_filter.py`; corpus of 888 results all labelled (258 by the maintainer, 630 by Claude). Built `src/web_filter.py` (jina multilingual reranker, threshold 0.035, keep ≥ 3, 15 candidates, best first, decision log `data/logs/web_filter.jsonl`), research topics (`src/research_topics.py`, panel below Deep Research), per-source ▲/▼ ratings (`data/web_ratings.jsonl`), and `src/search_output_fit.py` (search output no longer loses its closing instructions at 10,000 chars; that had hit 132 of 196 past searches).
- ✅ **Live on the M1** (filter on, notice cut-off 0.035 set by the maintainer): drops junk, output fit 9,641 chars with instructions, ratings stored, panel used. **15 candidates cost median 2.35 s per search** (3 searches; predicted ~1 s — wrong).
- 🔧 Same day, maintainer's own work: `src/edit_gutter.py` (strips a copied line-number gutter from edit REPLACE text); its test patched a module by text path and failed only in the full suite → now patches the imported module object. `test_bench_agent_skip.py` preset name updated. **M1 suite: 7,977 passed, 3 skipped.**
- ➡️ **Open:** see the *Open* list at the end of [items/82-web-relevance-filter.md](items/82-web-relevance-filter.md) — first, check `"notice": true` lines in the decision log after a few days; try 10 candidates for speed.

---

## 2026-10-10 (14:20–15:00) — Bonsai long chain analysed; items 78, 79 found and fixed, 58 built (uncommitted)

- 📊 Chain `chain-20261010-0935` read: knowledge 38/48, agent 37/40, research aborted at task 2, prompt probe → keep current prompt, thinking off works on llama.cpp. Details in benchmark.md *Results*.
- 🐞🔧 **78:** `trim_for_context` dropped the turn's user message in a long tool chain → llama.cpp 500 *No user query found*. `src/context_anchor.py`. Harness: template rejections are recorded (`request_rejected`) instead of stopping the run.
- 🐞🔧 **79:** the repetition guard read sub-word deltas as words and dropped one-digit numbers → stopped CSV restating (`'cl imal og cl'`). `src/stream_words.py`.
- 🔧 **58 built:** `src/turn_reasoning.py` (local endpoints keep every round's thinking, capped); `estimate_tokens` counts `reasoning_content`.
- 🔧 Bench: `reasoning_flags` labels `enable_thinking:false` as `@nothink`; `bench_chain.sh` phases `qwen-full`, `bonsai-check`, Odysseus freshness check, `start_bonsai` takes flags, `stop_bonsai` waits for the port.
- 🧪 **Sandbox suite** (Python 3.10 venv, `-n 4`, 12 slices): 7,791 passed, 4 skipped, 1 failed (item 73's DNS test). New tests: `test_context_anchor.py` (6), `test_turn_reasoning.py` (7), `test_stream_words.py` (12), `test_bench_agent_errors.py` (5), +1 in `test_bench_agent_effort.py`; 14 mutations caught. M1 run owed.
- 🔧 **15:00:** `bench_chain.sh full` (= `qwen-full bonsai-full`) and `scripts/bench_sysmon.py` (CPU/GPU/memory/swap/thermal/processes every 10 s per step, optional watts with `BENCH_POWER=1`, log copies per phase); `tests/test_bench_sysmon.py` (17), 3 of 4 mutations caught, the 4th was dead code and is removed.
- ➡️ **Next:** M1 suite + commit, restart Odysseus, `bench_chain.sh full`; then read `cache_n` on rounds 3+ (58), research completion (78), CSV tasks (79), `@nothink` knowledge vs medium.

---

## 2026-10-10 (08:20–09:40) — items 72 and 68 built (uncommitted)

- 🔧 **Item 72:** filed cause was wrong (the path block is not chat-mode-only). Real causes: the task-word gate and the trailing `?`. New `src/message_path_workspace.py` (bind any existing, vetted path; bash only for action requests), call site `routes/chat_routes.py`. 45 tests, 11 mutations caught.
- 🔧 **Item 68:** report-only `_action_claim_notice` in `src/turn_report.py` + `src/ui_notices.py`. Corpus: 2 of 94 zero-tool replies flagged, both real. 33 tests, 9 mutations caught.
- 🧪 **Sandbox suite** (Python 3.10 venv, `-n 4`, run in slices): 7,738 passed, 3 skipped, 2 failed — item 73's DNS test, and `test_tls_overrides_scope.py` timing out while reading the Mac `venv/` over the folder share (environment). M1 run owed.
- 🧹 Process: `git diff` run from the sandbox (no `index.lock` left). Scratch venv and mutation script live outside the repo.
- ➡️ **Next:** M1 suite + commit; restart; live check of item 72 (commands in todo.md); watch `app.log` for item 68's log line. Then items 71, 58.

---

## 2026-10-09 (20:55–21:20) — Odysseus as a launchd service + installable app (uncommitted)

- 🔧 **New `launchd/`:** agents `local.odysseus`, `local.odysseus.chroma`, `local.odysseus.apfel` (only if `apfel` is on PATH), all through `launchd/run.sh <mode>` (foreground `exec`, `.env` as in `start-macos.sh`, logs `logs/<mode>-service.log` rotated at 10 MB on restart, reinstalls deps when the `requirements.txt` hash changes). `install.sh` / `uninstall.sh` mirror `searxng/install-launchagent.sh`. See [launchd/README.md](../launchd/README.md).
- 🔧 **`start-macos.sh`:** one fork call site before the port check: `launchd/handoff.sh` opens the UI and exits when `local.odysseus` is loaded.
- 📱 PWA needed nothing: `static/manifest.json` + `sw.js` already exist. Install via Chrome *Install page as app* or Safari *Add to Dock*.
- ✅ **Installed on the M1 2026-10-10 08:33:** all three agents up (`logs/*-service.log`: Apfel listening on :11435, ChromaDB serving the app, UI loaded). Fix on the way: `install.sh` `envval` under `pipefail` when `.env` has no `APP_PORT`. ✅ **Reboot verified:** boot 08:32:29, all three agents up at 08:33:11 without a manual step. Committed `ba6ea57b`, `b256049a`.

## 2026-10-09 (16:05–17:45) — Bonsai memory: prompt cache off; approval replay fixed (item 74, uncommitted)

- ⚙️ **`~/BonsaiDemo/start_bonsai2.sh`: `--cache-ram 0`** (was 2048). Vision projector was already off. A full log showed 0 RAM-cache hits with entries of 455–846 MiB; measured at startup (`-lv 4` log `~/BonsaiDemo/logs/bonsai-2026-10-09-1630.log`): model 6.9 GB, KV 576 MiB, recurrent state 150 MiB, checkpoints 150 MiB each (peak 4). Server output is now logged with `tee -i` to `~/BonsaiDemo/logs/` (commands in `~/Desktop/TerminalCheatSheet.md`).
- 📊 **`20261009-163128-bonsai2@medium`** (quick ×1, cache off): 8/8, 16.5 min vs 13.1–13.5 for `155236`; without `edit_file` 11.1 vs 10.0–10.9. Prefill 65.8 tok/s, decode 10.3 — unchanged. The gap is item 74.
- 🔧 **Item 74 built, uncommitted:** `src/approval_replay.py`, `src/decision_nudge.py`, call sites in `core/models.py` and `src/agent_loop.py`, `tests/test_approval_replay.py`, `tests/test_decision_nudge.py`. Earlier uncommitted work (`ui_control` narrowing) untouched.
- 🧪 **Sandbox suite** (Python 3.10 venv, `-n 4 --timeout=30`, run in slices): 7,548 passed. Failures: the DNS test (item 73); 20 timeouts in one slice that all pass alone (68/68); `test_session_tools_registry.py` ×7 in its slice, **also with the original `core/models.py` and `src/agent_loop.py`** — order-dependent, passes alone. M1 run owed.
- ⚠️ `src/local_tool_selection.py` has an uncommitted change from before this work (saved 16:54, narrows `ui_control` further) — not part of item 74; left as is.
- 🧹 Process: one `git diff --stat` from the sandbox (no `index.lock` left). A debug test file was created and deleted again (delete permission granted for this session).
- ✅ **Committed** `1364ee37` (fix) and `88d307f0` (notes) by the maintainer; M1 suite green. **Live 17:54–18:15 (`20261009-175432`): 16/16, 9.8 / 10.6 min per run** (was 13.1–13.5); `edit_file` 127 / 149 s with correct answers. Confounded with the `ui_control` narrowing going live at the same restart (−1,100 prompt tokens on simple tasks) — see item 74.
- 📊 **Qwen (`c35f1b2a`, LM Studio):** quick ×1 `182456` 8/8, 3.9 min; full ×2 `182957` **37/40**, 12.5 min/run. Fails: `explain` ×2 (item 75, new), `document_followup` r1 (title brackets dropped — known title-copy slip). On 17 tasks unchanged since 10-07: 14.8 → 11.7 min.
- 🔧 **Item 75 built (uncommitted, 19:58–20:15):** `src/direct_reply.py` + call site; `tests/test_direct_reply_cap.py` (9), 3 mutations caught; related files 267 + 145 passed in the sandbox.
- 🧪 **Knowledge suite built (20:06–21:00, uncommitted):** `scripts/bench_knowledge_tasks.py` (24 tasks: mycology, microelectronics, finance; quick 9), `--suite` in `scripts/bench_agent.py` (default `agent`, unchanged: 20 / 8), run dirs `…-knowledge`, report **By kind**. Answer keys fact-checked against sources ([benchmark.md](benchmark.md#knowledge-suite---suite-knowledge-since-2026-10-09)). `tests/test_bench_knowledge_tasks.py` 69 passed, 10 mutations caught; harness tests 102 passed.
- ✅ Committed by the maintainer: item 75 `b3a52e79` (live: `explain` 2/2, but 75 / 124 s), knowledge suite `bf504b11`.
- 📊 **Knowledge quick ×2, Qwen: 8/18** — 6 empty (thinking used the 4,096-token cap, item 76), 1 checker miss (`mc_i2c`, fixed, uncommitted: `scripts/bench_knowledge_tasks.py`, `tests/test_bench_knowledge_tasks.py` 72 passed, mutation caught), 3 real misses. Item 76 filed (direct path has no system prompt; a lookup offer would get no web tool on "yes"); `scripts/probe_direct_reply.py` written, not run yet.
- ✅ Checker fix committed `666c026a`. **Probe run 22:06:** Odysseus's own system prompt cuts Qwen's thinking 10–25× on the direct path (10–20 s instead of 70–195 s); one-liners don't; the lookup-offer line was ignored (0/6); the obscure-fact question got a confident wrong answer every time (Persoon instead of Fries 1822).
- 🔧 **Item 76 thinking half built (uncommitted):** `src/direct_reply.py`, call site `src/agent_loop.py`, `tests/test_direct_reply_cap.py`; `scripts/probe_direct_reply.py` gained `odysseus_offer`.
- ✅ Item 76 committed `137aba4a`. **Knowledge quick, Qwen: 13/18 in 6.5 min** (was 8/18, 42 min). Checker fix: `mc_5v` now fails answers that call the pins 5 V tolerant (both "passes" did) — uncommitted, 75 tests, mutation caught. Lookup offer re-probed and **dropped** (0 real offers, one fake tool call).
- 🧪 **Item 77 (maintainer's leaner prompts) probed 23:26:** version A = current prompt's speed and answers at 973 chars (vs 1,348); version B (no-tool, 306 chars) brings the long thinking back (81–179 s in 3 of 6). Notes and probe variants uncommitted.
- 🧪 **2026-10-10 07:58 probe (item 77):** C (607 chars), framing-only and C-without-tools-line each let 1 of 6 rounds run long (61–168 s); C-without-tools-line also wrote a fake tool call. A: 0 slow of 12 so far — the candidate.
- 🧪 **09:14:** LM Studio ignores `enable_thinking: false` per request (Qwen thought as usual). Battery calc with thinking: current prompt 4/5, A 2/5 → hold A. `og_refined`/`a_refined` (08:23): the thinking rule adds nothing; "helpful assistant" makes Qwen think 4–8× longer.
- 🧪 **Research suite + long Bonsai chain (09:20–10:00, uncommitted):** `scripts/bench_research_tasks.py` (5 web-research tasks, fact-checked), `--suite research`; `scripts/bench_chain.sh` phases `bonsai`, `bonsai-long`, `qwen` (dry-run tested). Tests: research 18, knowledge + harness 99 — 117 passed.
- ➡️ **Next:** commit; run `bench_chain.sh bonsai-long qwen`. Earlier: Bonsai knowledge quick (Bonsai's server, LM Studio stopped). New Bonsai agent baseline is `20261009-175432`. Commit or drop the uncommitted `src/local_tool_selection.py` change (it is live now). Items 71, 58, 72.

## 2026-10-09 (10:55–16:55) — Bonsai full run read; effort picker; item 70 built; prompt trims; benchmark rebuilt

- 📊 **Bonsai full ×2 (`20261009-031517`, medium): 34/36** (both `recover_typo` repetition loops). Time: prefill 59 %, new-chat round 1 33 min, approval continuations 11.6 min, dropped thinking 8 min ([benchmark.md](benchmark.md)).
- 🔧 **Committed today** (all by the maintainer; M1 suite green each time, last 7,585 passed): effort recorded per benchmark run (`TARGET@EFFORT`); *Reasoning effort* picker in the custom preset → `chat_template_kwargs` (`src/reasoning_effort.py`; `high` removed — Bonsai's template raises on it; `low` is accepted but measured no different from `medium`); benchmark approval answer carries `allow_bash`/`allow_web_search` (the "bash re-read" was the harness's own bug); **item 70** keyword-only tool selection on local endpoints (`src/local_tool_selection.py`); `src/prompt_trims.py` — Terminus rules only with file/shell tools, date context = the date alone, no "Available tools" list; **benchmark rebuilt** — workspace only for file tasks, `document_edit` / `document_followup`, `--quick` = arith, read_fact, edit_file, web_fact, web_read, document_create, document_edit, document_followup.
- 📏 **Live:** reuse across chats works (same message + tools in two new chats: prefill 59.6 s → 4.0 s). New-suite baseline `20261009-155236-bonsai2@medium`: **16/16**, ~27 min.
- 🔧 **Uncommitted:** `ui_control` only for named UI actions on local endpoints (`src/local_tool_selection.py`, call site in `src/agent_loop.py`, 15 tests); `notes/todo.md` (items 70 status, 71–73 filed), this file. Commands handed over at 16:55.
- ⚙️ Maintainer switched off `manage_memory`. Custom preset now temp 1.0 / 8192 / effort medium.
- 🧹 Process: `git status` run once from the sandbox before reading CLAUDE.md §6 (no lock left); related test files ran in a venv built in the sandbox from `requirements.txt` (+ pytest, pytest-xdist, pytest-timeout; Python 3.10, gone with the session) — only the DNS test (item 73) fails there; some unrelated tests hang without network, so run test files selectively with `--timeout=30`.
- ➡️ **Next:** item 71 (follow-up with an open document changes the tool set — cause in the log), then item 58 (dropped thinking), item 72 (file path without workspace).

---
