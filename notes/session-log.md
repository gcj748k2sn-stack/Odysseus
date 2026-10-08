# Session log

Brief, dated summaries of what each session *did* — not findings (those live in
[todo.md](todo.md) and [resolvedissues.md](resolvedissues.md)), just scope and
state changes, so the next session isn't starting cold. Newest first. Keep each
entry to a few lines — if it needs more, the detail belongs in `todo.md` or
`resolvedissues.md` and this should just link to it.

Keep roughly the last working day here; older entries move verbatim to
[archive/](archive/) (history, not current state): 2026-10-07 in
[archive/session-log-2026-10-07.md](archive/session-log-2026-10-07.md), 2026-10-06 in
[archive/session-log-2026-10-06.md](archive/session-log-2026-10-06.md),
2026-07-30 to 2026-10-06 00:20 in
[archive/session-log-until-2026-10-06.md](archive/session-log-until-2026-10-06.md).

---

## 2026-10-08 (17:00) – 2026-10-09 (01:40) — item 57 built and verified live; tool selection reviewed; item 70 filed

- ✅ **Item 57 done:** prefix probe `2778b2be`; sticky tools `6dd7aaeb`; follow-up fix `fa0a3ba1` after the first live check (21:35) still missed. **Live 21:54 (chat `01492028`, Bonsai):** a low-signal follow-up reused the set, `first_diff=3/7`, **6.3 s instead of ~80 s**. A message that adds tools still re-reads the whole prompt once.
- ⚙️ **Maintainer switched off `manage_skills` and `manage_calendar`** (Settings → Agent Tools); email, contacts, chats, cookbook and multi-model tools were already off. 36 tools are on.
- 🔧 **Benchmark skips tasks whose tools are switched off** (`797ae545`, 8 tests): `calendar_create` is now *⏭ tool off*, so full runs are out of 17 tasks per run. [benchmark.md](benchmark.md) has a new **Commands** section with paste-ready blocks for each kind of run.
- 🅿️ **Shorter tool descriptions parked** ([item 64, entry 12](items/64-decisions-waiting-for-approval.md)): ~4 s per uncached round, not worth a second copy of the descriptions. Measured on the way: the real prompt is ~4,700 tokens, while Odysseus's own estimate (~2,000) leaves out the tool schemas.
- 📝 **Item 70 filed, high priority:** an offline replay of 263 agent turns shows the similarity search was needed in 1 turn; keywords + topic detection cover the rest. Keyword-only selection for local models is the next step.
- ⚠️ M1 suite once failed `test_trigger_research_probe.py::test_route_with_wait_for_probe_returns_the_probe_failure`; it passed alone and on the rerun — a flake, watch it. Process slip: `git status` was run twice from the sandbox (CLAUDE.md §6); no `index.lock` left behind.
- **Uncommitted:** `CLAUDE.md` (§7: no `#` comments in pasted commands; stop a chain on a failing suite through a file), `notes/todo.md`, `notes/benchmark.md`, `notes/items/64-…`, `notes/archive/` (README + `session-log-2026-10-07.md`), this file.
- ➡️ **Next:** item 70; then the owed benchmark runs (Qwen 0.6 `json_output` r2 via `--resume`, Bonsai full suite); decide on the custom preset (disabled since 17:06).

---

## 2026-10-08 (13:30–16:30) — benchmark day: Qwen at 1.0 and 0.6, Bonsai quick; three harness fixes

- 📊 **Results** (detail in [benchmark.md](benchmark.md); report `data/bench/agent/report.md`): Qwen full at 1.0 **35/36** after the rescore (33/36 counting two loops); Qwen at 0.6, quick **16/16** and full **34/36** (one loop, one title slip); Bonsai 2 quick **16/16**, no loops. **Temperature 0.6 vs 1.0 makes no difference at this n.** Qwen's weak spots: `calendar_create` title copying (3/6) and repetition loops (3 in 108 task runs).
- 🔧 **Harness fixes, uncommitted:** (1) `--preset` option, run named `TARGET+PRESET` (committed `31d2948d`); (2) a repetition loop is a model result. It needed a second fix at 15:45, because Odysseus repeats the failure in an `agent_terminal` summary without the text, so the run stopped three times (13:37, 14:07, 15:17); (3) `split_turn_report` recognises the bulleted closing report (`- ⚠️ …`), which had failed `json_output` r2 for prose that was Odysseus's own.
- 🔎 **Bonsai time (16:30):** prefill 66 %, generation 33 %; round 1 never hits the cache (0 of 115k tokens). **Item 59 closed:** `start_bonsai2.sh` has sent `reasoning_effort: medium` since 10-05. **Item 57 not built yet, on purpose:** the hybrid-model cache restores only at message boundaries, so first `src/prefix_probe.py` (uncommitted) finds which message breaks the prefix on follow-ups.
- ⏳ **Owed:** the Qwen 0.6 full run is missing `json_output` r2. Resume with LM Studio back up: `--resume data/bench/agent/20261008-144530-qwen35+custom`. The Bonsai full suite (10 tasks never run) is still owed.
- **Edited:** `scripts/bench_agent.py`, `scripts/bench_agent_tasks.py`, `notes/benchmark.md`, this file.

---

## 2026-10-08 (09:25–10:20) — owed checks all done: 69 and 9b closed, item 7 fixed (uncommitted), 2a and 21 verified live

- ✅ **69 closed:** approved edit with the panel closed after a reload (09:34, session `791d372a`) → editor v4, new text, stamped. Row and body moved to resolvedissues.md.
- 🐞🔧 **7 — the d16f7a83 shape was a false report, and current code still produced it:** four edits, v2 and v3 landed, two rejected, and the reply said *"the document is unchanged … rejected 1 attempt"*. Fixed in `src/turn_report.py` (`doc_edit_failed_notice`) and `src/agent_loop.py` (`_doc_edit_landed`); `tests/test_doc_edit_partial_failure_report.py` (4, real loop, 4 mutations caught). Sandbox (Python 3.10 venv, `-n 4`): 7,494 passed, 2 failed — the no-DNS test and `test_mcp_reconnect_args`, which passes alone (test order under xdist). **Needs a restart to go live; not seen live. M1 suite and commit owed.**
- ✅ **2a fired live for the first time** (09:38, session `1a92b5d3`): `read_file` of `data/agent_workspace/grow_log.json` (test fixture, delete when done), a table of 4 of 6 records → *"Doesn't match the source — source has 6 records, the table has 4 rows"*. It was a requested subset, so this is a known false positive; report-only.
- ✅ **21 re-verified live** for 2a (09:38) and 2b (09:42): each warning kept after the model's own summary. A one-line test document gives no 2b finding (no heading, so no subject) — by design.
- ✅ **9b closed:** three same-prompt long runs on LM Studio succeeded — round 1 took 507, 461 and 432 s; the browser saw silent stretches of 447 and 417 s; documents of 43–55 k chars; no 504. Scope note: LM Studio, not Ollama. Item file moved to `archive/items/`.
- 🔧 **48 — the 10-04 fix was half right:** the popup's *used* figure was Odysseus's estimate, while the percentage is the provider's real count (live: 28,629 shown beside 34.1 %). Now prints the last usage bucket; 56/56 rows with buckets match. `static/js/chatRenderer.js`, uncommitted, live via reload.
- ✅ **56 closed** — failed send to a down Ollama rendered the error and no `ReferenceError`. **`_send_email_sync`** checked: dead code; scheduled delivery is owner-scoped; `agent_draft` rows have no writer.
- ✅ **46 closed** — the Admin *Tools* selector verified live (auto → `null`, on → `true`, survives a reload).
- 📉 **20 re-measured:** duplicate rule 3 of 5 (07-30: 6 of 6), titles and item 12's rule 3 of 3. Confounded — see the next bullet.
- 🔎 **43:** since 10-04 **every** request runs `Preset None: temp=1.0, max_tokens=0`. The custom preset in `data/presets.json` was disabled at 10-04 19:43, and `loadPresets` never selects a tuning-only preset on page load (upstream). No fix made; the maintainer decides.
- 🔧 **43 fixed (uncommitted):** preset re-enabled at 0.6/8192, and `static/js/presets.js` `loadPresets` now selects a tuning-only preset on load; every request since 10:56 is `Preset custom`. **20 second batch at 0.6: 4 of 5** — temperature does not explain the drop from 6/6.
- ⚠️ **M1 suite 13:52 (committed as `a100ee61`…`d2d7a3b0`): 7,496 passed, 1 failed** — `test_tool_path_odysseus_state.py::test_grep_never_prints_state_files[python-fallback]`. It passes alone (sandbox, 37/37) and passed in the 09:23 M1 run. It ran during a benchmark run on the same Mac. Suspect the spawn-worker fallback in `src/agent_tools/filesystem_tools.py` (upstream): it waits 50 ms for the final queue record after the worker exits, and under load that can read as *"fallback worker exited 0"* with no output. **Re-run alone on the M1 at 14:25: passed.** So it's a load-dependent flake, not a regression; worth a longer wait in the fallback if it recurs.
- 🧹 Item 20 left ten chats and ten clone documents (sessions `812725ec`, `9a1b66f1`, `f99a8f81`, `3969c1f6`, `54422491`, `7365035a`, `00e6291b`, `6d2027eb`, `b2d6cb29`, `dc502fe0`), plus 7 created documents.
- 🧹 Test documents: *"Grow log A/B"*, *"Pink oyster fruiting"* (1 and 2), *"9b long run"* ×3, *"Yellow Oyster check 4"* (now v4).
- **Edited:** `src/turn_report.py`, `src/agent_loop.py`, `tests/test_doc_edit_partial_failure_report.py` (new), `notes/todo.md`, `notes/resolvedissues.md`, this file.

---

## 2026-10-08 (08:40–09:00) — approval-flow live check finished; item 69 found and fixed (uncommitted)

- ✅ **Live, session `791d372a`, Qwen on LM Studio**, done from the agent's browser pane: (3) reload, panel closed, **Allow** → `edit_document` ran, v1 → v2 (verifies 67); (4) a card retired by a later message, re-posted → `Tool approval Dr069acB… rejected (409): not pending …` at 08:53:09; (5) *Resend* with the document panel open → `POST /api/chat_stream` 08:53:38 and no email error (verifies 66, together with Allow at 08:49). Every card was saved with no *"Updated"* line (65).
- 🐞🔧 **Item 69 (S2):** after an approved document edit, the editor showed an **empty buffer stamped with the document's id**, so a Save or a keystroke would write an empty version. Cause: `chat.js`'s `tool_output` fallback read `document_*` keys, and the approved replay sends raw keys. It also explains both empty editors under item 67. Fixed in `static/js/chat.js`; reproduced, then verified live at 08:49 (editor `v3`, stamped). Test file `tests/test_approved_doc_tool_output_js.py`, run with system `python3`, not pytest. **M1 run owed.**
- 🧹 Test document *"Yellow Oyster check 4"* (`04123181`) is now v3 (CO2 900 ppm, humidity 65–80 %); delete it when done.
- **Edited:** `static/js/chat.js`, `tests/test_approved_doc_tool_output_js.py` (new), `notes/todo.md`, this file.
- ✅ **Committed** `09d75c4e` (fix) and `2c507b60` (notes). **M1 suite, `-n auto`: 7,493 passed, 3 skipped, 82 s.** `pytest-xdist` is now in `requirements.txt`. Items 65–67 closed (conclusions in resolvedissues.md).
- ➡️ **Next:** items 7, 21, 9b, 2a.
