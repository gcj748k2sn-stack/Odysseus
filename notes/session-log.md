# Session log

Brief, dated summaries of what each session *did* — not findings (those live in
[todo.md](todo.md) and [resolvedissues.md](resolvedissues.md)), just scope and
state changes, so the next session isn't starting cold. Newest first. Keep each
entry to a few lines — if it needs more, the detail belongs in `todo.md` or
`resolvedissues.md` and this should just link to it.

Keep roughly the last working day here; older entries move verbatim to
[archive/](archive/) (history, not current state). Entries from 2026-07-30 to
2026-10-06 00:20 are in [archive/session-log-until-2026-10-06.md](archive/session-log-until-2026-10-06.md).

---

## 2026-10-07 (17:15–19:00) — first valid benchmark runs: Bonsai 2 `--quick`, Qwen full ×2; two scoring fixes — uncommitted

- 📊 **Bonsai 2** `--quick` (`20261007-171522`, plus `20261007-012621` from the night): **16/16**, median 142 s/task, 62 s/round, uncached prefill ~64 tok/s, cache hit 51 %. **Qwen 3.5 9B** full suite ×2 (`20261007-175428`): **34/36 as scored, 35/36 after the fix below**, median 42 s/task, 19 s/round, 30 min. On the 8 tasks both ran: 16/16 each. 0 empty answers after tool rounds for either; approval cards 7 (Bonsai, mostly its habit of computing with `python`) and 11 (Qwen). Report: `data/bench/agent/report.md` (gitignored).
- 🔧 **Odysseus's closing report is no longer scored as model text.** `src/turn_report.py` appends *"⚠️ **`python` failed** — …"* for any failed side-effecting tool, **even one the model recovered from** later in the turn; Qwen's `json_output` r2 replied exactly `{"rows":36,"nodes":3}` and failed *"no prose"* on that appended line. Checks now see the reply without the trailing report block (`split_turn_report`); the record keeps it as `turn_report` with flag `odysseus_turn_report`. ⚠️ Worth deciding separately whether a recovered failure should still be reported to the user that way — it is the fork's deliberate *"failures always"* rule.
- 🔧 **`calendar_create` split like `note_create`:** *"event created"* vs *"title copied exactly"*; Qwen r1 created `bench-2d22 Dentist` (brackets dropped) and then told the user it created `"[bench-2d22] Dentist"`. Cleanup and preflight match `BENCH_RE` (`\[?bench-[0-9a-f]{3,4}\]?`) instead of the `[bench-` prefix, which had left that event in the calendar (14 Oct, 14:00) — **`bench_agent.py cleanup` removes it once this is committed.**
- 🧪 Stub/mock only for the two fixes; the runs above used the previous version. **Edited:** `scripts/bench_agent.py`, `scripts/bench_agent_tasks.py`, this file.

---

## 2026-10-07 (00:00–00:20, written to the M1 16:10) — streamlining: dead stream-failure path removed, fork reporting moved out of `agent_loop.py`, comments condensed, notes split — uncommitted

- 🔧 **Code.** Removed `_stream_failure_notice`, `_stream_error_detail` and `stream_errors` — unreachable since the merge (every `event: error` now ends in upstream's `agent_terminal` + `return`); 10 tests went with them, and `ui_notices.py` still strips the old notice from saved chats. Removed the `[doc-put]` and `[doc-del]` log lines (their removal conditions were met); **kept** the `switchAway` trace (resolvedissues ties it to the 30–35 cluster, and 34 is open), `_stackFrames`, `[doc-put-404]` and the `[ai-tidy]` logging. Moved the fork's end-of-turn reporting to `src/turn_report.py` and the browser gate to `src/browser_gate.py` — `agent_loop.py` now differs from upstream by about 370 added lines instead of 1,340. Fork comments condensed to the why, with notes cited by title.
- 🧪 Linux clone, Python 3.13, `-n 2`: **7,440 passed, 4 skipped, 0 failed** (7,450 before, minus the 10 removed). Real `stream_agent_loop` driven through 28 scripted scenarios: output, prompts, tool calls and `src.*` log lines identical to the tree before the change. Comment-only edits checked mechanically: identical Python AST apart from docstrings, identical JS token stream. **Not run on the M1. JS not checked in a browser** (`node --check` only; the `switchToDoc` trace is unchanged code).
- 📝 **Notes.** `todo.md` is now the open-item dashboard (217 → 49 KB); 17 long items moved to `notes/items/`; the 35 closed rows are indexed at the top of `resolvedissues.md`, with new conclusions for items 18, 26, 36, 37 and 38. `CLAUDE.md` condensed (461 → 218 lines); fixed two stale claims (the "two pre-existing failures" and the `app.py` line numbers) and added §0 on keeping fork code out of upstream functions. Verbatim snapshots in `notes/archive/`. `qwensetup.md` left as is — its history is interleaved with current setup, not a separate block.
- ➡️ **Next:** the M1 full suite on these changes; one live agent turn that edits a document, and a hard reload with a document open (checks `switchToDoc`). The uncommitted benchmark changes from 22:45 were not touched.

---

## 2026-10-06 (22:45–23:05) — first post-merge `--quick` (Bonsai 2) invalid: workspace refused; fixed — uncommitted

- 🔴 **Run `20261006-212201-bonsai2` is invalid — delete it.** Every task came back `workspace_rejected`: since the merge `vet_workspace` refuses anything under `data/` except `agent_workspace/` & co. (`_is_app_state_path`), and the fixtures were in `data/bench/agent/<run>/ws/`. Consequences seen: `read_fact` went down the **direct low-signal reply path with no tools** (`_direct_low_signal` only applies when no workspace is bound) and Bonsai wrote a `<tool_call><function=Read>` as text; on `write_file` the file tools refused the path and **Bonsai wrote `summary.md` with `bash` instead** (item 60's hole, from the model side), which the check counted as a pass.
- 🔧 **Fixtures now go to `~/odysseus-bench/<run-id>/`** (`BENCH_WS_ROOT` overrides); results stay in `data/bench/agent/`. A `workspace_rejected` now **stops the run** unsaved with the `--resume` line.
- 🔧 **`web_read` / `web_fetch` no longer require a `web_fetch` call**: `src/chat_processor.py` fetches every URL in the user message before round 1 (first 10,000 chars, untrusted context). Bonsai answered `web_read` correctly (Fries, 1822, fir forest, Sweden) from that prefetch, with zero tool calls, after a 109 s prefill of 6,804 tokens — and also confirms item 49's fix (`Morchella` cached at 51,880 chars).
- 🔧 **Odysseus's 502 *"Model returned an empty response"* is a result, not a server fault** — it stopped the run at `german`; now saved and shown in the report's failures with the error text. Unreachable / *Compute error* / other 5xx still stop the run.
- 🔧 Report: the direct low-signal path is detected from `app.log` and counted under *"Task tool not offered by Odysseus (incl. no-tools reply path)"*.
- 🧪 Mock only (workspace-rejected abort, empty-response saved, quick suite with cards). **Live `--quick` still owed.**
- **Edited:** `scripts/bench_agent.py`, `scripts/bench_agent_tasks.py`, this file.

---

## 2026-10-06 (21:15–21:45) — benchmark answers approval cards (the handoff's "build first") — uncommitted

- 🔧 **`scripts/bench_agent.py` answers the untrusted-context gate.** On an `ask_user` event with `kind: "tool_approval"` it re-posts the same session with `tool_approval_id` + `tool_approval_decision=approve_task` (cookie login, so `_reject_delegated_tool_approval` does not apply; incognito keeps the turn's context in `_INCOGNITO_CONTEXTS` for 6 h). Rounds are summed across the continuation; the card's question delta and its *"Waiting for an exact user approval."* placeholder are kept out of the answer and the tool results. `--approval deny` and `--max-approvals` (default 4) exist for checking the gate itself. Report: *"Approval cards answered (task runs with ≥1)"*, and a reading note that cards cost a round trip, not points.
- 🔧 **Upstream's terminal failure path:** `agent_terminal` with `failed` is flagged (`agent_terminal_failed`) next to `event: error`. Server faults — *Cannot reach*, LM Studio's *Compute error* (the 11:25 broken copy), any HTTP 5xx — **stop the run without saving that result** and print the `--resume` line; an HTTP 400 such as the context overflow stays a result.
- 🧪 Mock server only, extended to raise cards and terminal failures: 18/18 with two cards on each of `write_file`, `edit_file`, `multi_step`; limit, deny and the 500 abort/resume behave as intended. **Not run live** — the handoff's *"one `--quick` live"* is still owed. `notes/merge-upstream-2026-10-06.md` *Approval cards* line updated to match.
- **Edited:** `scripts/bench_agent.py`, `notes/merge-upstream-2026-10-06.md`, this file. Only `git --no-optional-locks log/show/diff`.

---

## 2026-10-06 (19:30–20:20) — last live checks for the merge; handoff for the benchmark

- ✅ **LAN `web_fetch`** (Qwen, 20:16): the router at `http://192.168.0.1` (found with `route -n get default`) was reached. The error *"no readable text content (… needs JS/login)"* only comes after a response is received. The earlier timeouts on `192.168.178.1` were a wrong address, which `curl` confirmed.
- ✅ **Failed turn → *"what happened"*** (12:36): upstream saves nothing for a turn that fails before any output. **The maintainer decided to keep that.** Recorded under [todo.md](todo.md) item 9b. A turn that fails after a tool call does save `[Agent stopped: …]` (20:03, chat `b25e89e6`).
- ⏭️ **Handoff, for the next session — the benchmark is blocked:**
  - Since the merge, any workspace read (`read_file`, `grep`, …) arms the approval gate, so a later `write_file` or `edit_file` in the same turn needs an approval. `scripts/bench_agent.py` cannot answer approval cards, so `write_file`, `edit_file` and `multi_step` would stall.
  - **Build first:** on an `ask_user` with an `approval_id`, re-post with `tool_approval_id` + `tool_approval_decision=approve_task`, and count approvals per task in the report. Test it against a stub, then run one `--quick` live.
  - **Also:** remove the leftover note *"[bench-44b] Workshop shopping"* with `python3 scripts/bench_agent.py cleanup` before the first run.
  - Run one model at a time, and keep Bonsai 2 off while Qwen runs ([qwensetup.md](qwensetup.md), the *Compute error* line).
- ℹ️ **State:** `dev` is pushed; every 2026-10-06 change is committed. M1 suite 7,451 passed / 0 failed. `data/skills/` is empty. Bonsai 2 is not running. Ollama is down, so auto-naming fails (the maintainer is ignoring that).
- **Edited:** `notes/merge-upstream-2026-10-06.md`, `notes/todo.md` (items 9b, 52, 54), this file. No `git` command run on the Mac; `data/` was read on copies only.

---

## 2026-10-06 (12:25–12:45) — the 12 machine-dependent test failures fixed in the tests — committed 19:30 (`34c7abb9`)

- 🧪 **The suite no longer touches the live `data/`.** `tests/conftest.py` sets a fresh temp `ODYSSEUS_DATA_DIR`. Plus 4 test-only fixes:
  - realpath in `test_write_file_empty_body.py`;
  - `::1` in `test_integration_api_call_ssrf.py`;
  - `DEEP_RESEARCH_DIR` in `test_research_report_read.py`, which had been writing into the live research folder;
  - the opt-in pinned in one `test_security_regressions.py` test.
- **Linux, M1-like:** 7,450 passed, 0 failed. Each fix was checked by reverting it ([merge-upstream-2026-10-06.md](merge-upstream-2026-10-06.md)). **M1, 19:2x: 7,451 passed, 3 skipped, 0 failed**; the `/etc/shadow` count in the live `app.log` stayed at 2, so the suite no longer writes there. Skills moved to `~/odysseus-snapshots/skills-2026-10-06/` at 19:24. `CLAUDE.md` §4 notes the new data directory.
- 🧹 The two learned Arduino skills (July test leftovers) moved out of `data/skills/` by the maintainer at 19:24, because while any skill exists, its index arms the approval gate on every turn.
- **Edited:** 5 test files, `CLAUDE.md`, `notes/merge-upstream-2026-10-06.md`, this file. No `git` command run on the Mac; `data/` only read.

---

## 2026-10-06 (09:10–12:05) — merge checked on the M1 and live, pushed to `dev`; LM Studio "Compute error" explained

- 🧪 **M1 suite:** first run 21 failed (8 caused by the merge, fixed in `d946c87e`; 1 by the docs rule, fixed by moving the notes to `notes/`). Second run **12 failed, 7,439 passed**: the 12 failures are upstream tests that depend on this machine (real `data/auth.json`, `/var` symlink, `127.0.0.2`, the skills arming the gate), as predicted. Table in [merge-upstream-2026-10-06.md](merge-upstream-2026-10-06.md).
- ✅ **Live checks** in the same note:
  - Passed: New Chat twice, research → document with an approval card (Bonsai 2 and Qwen), and the `read_file` refusal.
  - ✅ Done later the same day: the failing-turn notice (a turn that fails before any output saves nothing, which is upstream's design and kept), and a LAN `web_fetch` (router at `192.168.0.1` answered, 20:16).
- 🔴 **Item 60's `bash` hole was used live.** After the `read_file` refusal, Bonsai 2 ran `cat data/settings.json` through `bash` once the maintainer approved it. The output in chat `8abca026` and the document *"Code (json)"* were deleted at 12:05. Fix candidates are in [todo.md](todo.md) item 60; nothing built.
- 🔍 **Qwen "doesn't work" (11:25–11:41)** was LM Studio's broken copy of the model (`500 Compute error`, first loaded while Bonsai 2 was running), not the merge: the request fields are unchanged, and direct `curl` calls worked after `lms unload --all && lms load …`. Recorded in [qwensetup.md](qwensetup.md).
- 🔀 **`dev` fast-forwarded to `c398a6a5` and pushed at 12:03**; bundles and the `merge-upstream` branch removed. Bench JSONs moved to `~/odysseus-snapshots/bench/`, and `/bench_qwen_*.json` is now gitignored.
- **Edited:** `notes/merge-upstream-2026-10-06.md`, `notes/todo.md` (item 60), `notes/qwensetup.md`, `.gitignore`, this file. No `git` command run on the Mac; `data/` was only read (`app.log`).

---

## 2026-10-06 (08:40–09:00) — agent benchmark refined for the full run (Bonsai 2 first) — committed (`2bb475b1`)

- 🆕 **`web_read`** (in `--quick`, replaces `web_fact` there): read `en.wikipedia.org/wiki/Morchella`, answer who described *M. elata*, when, and *"fir forest in Sweden"* — only answerable from the article body, so it exercises item 49's fix. Sentence sits ~5,800 chars in, inside `web_fetch`'s 10,000-char output cap (checked in the 2026-10-05 21:24 cache entry). `web_fact` stays in the full suite, documented as passable from memory. **18 tasks** now.
- 🔧 **`note_create`** splits *"note created"* from *"title copied exactly"* and only looks at notes created during the run (ids snapshotted in setup), so a mistyped marker no longer hides whether the items were right, and a stale leftover can't pass for the new note.
- 🆕 **Preflight** (`preflight` subcommand, and automatically before every `run`): records llama.cpp `/props` (model file, `n_ctx`, build, sampling/reasoning params), LM Studio's loaded models, Ollama's loaded models, SearXNG health and the HEAD commit (read from `.git/` files, no git command) into `meta.json`; warns about other loaded models, a running `:8090` server when Qwen is the target, a SearXNG that returns nothing, and `[bench-` notes left over. Warnings pause 15 s (`--yes` skips). The report prints this setup per run and adds *"runs hit by environment errors left out"* and *"only tasks every model ran"* rows.
- 🐛 Two runs started in the same second shared a directory and the second silently skipped every task — now suffixed `-2`, `-3`.
- 🔍 **Checked for interference over a ~3 h run:** for `cedrik`, *Chat Sessions Tidy* and *Documents Tidy* are paused; *Memory Tidy* / *Skills Audit* fire on new memories/skills, which incognito turns never create. Nothing scheduled should hit the model mid-run.
- 🧪 Mock server only (full suite 18/18 correct, wrong answers fail on the intended checks, mistyped-marker and stale-leftover cases, preflight warnings); on the Mac: `tasks`, prompt lint, `report` on the 2026-10-05 runs. **Not run live.** The leftover note *"[bench-44b] Workshop shopping"* is still in `app.db` (copy checked 08:45); preflight will flag it.
- **Edited:** `scripts/bench_agent.py`, `scripts/bench_agent_tasks.py`, this file.

---

## 2026-10-06 (08:20–09:00) — upstream `dev` merged into the fork, on a branch (`merge-upstream`) — on `dev` since 12:03 (`c398a6a5`)

- 🔀 **Merged upstream `2992bf6d` (132 commits, 07-29 → 10-01) into fork `2dfae628`** in a separate clone, as a merge commit so every cited hash stays valid. 25 files conflicted; resolutions, behaviour changes and owed checks: [merge-upstream-2026-10-06.md](merge-upstream-2026-10-06.md).
- ⚠️ **Item 60 is now upstream's fix** (containment of `data/`, advisory 2026-09-05); the fork's filename list was retired and its test rewritten. Wider than item 60: `data/presets.json`, `memory.json`, `logs/`, `skills/`, `hwfit/` are refused too, and the agent's bash `$HOME` moved to `data/agent_workspace/`.
- ⚠️ **Expect approval cards** after any web result or workspace file read (upstream's untrusted-context gate), and `[Agent stopped: …]` instead of item 9b's notice on stream failures.
- 🐛 **Found by the fork's JS scanner:** upstream's `chat.js` reads `roundHolder` outside its block in the stream-error catch (ReferenceError) — hoisted.
- 🧪 Linux clone, py3.13: **merge 7,443 passed, 11 skipped, 0 failed**; baselines upstream 5,945 / fork 6,254, both 0 failed. 3 mutations caught. `saveDocument` return values unverified (no JS harness). **M1 suite and live checks owed** — list in the merge note *(all done the same day; see the 09:10 and 19:30 entries)*.
- **Delivered as a git bundle**; the maintainer fetches it into `merge-upstream`, runs the suite, then fast-forwards `dev`. Nothing in `/Users/cedrik/odysseus` was changed by this session except the bundle file.

---

## 2026-10-06 (02:10) — agent benchmark: first live run, follow-up fixes, cleanup — committed 02:17 (`2dfae628`)

- 📊 **First live `--quick` run (2026-10-05 08:58–09:43, 8 tasks × 1 run each, incognito):** Qwen 3.5 9B (LM Studio) **7/8**, median **51 s**/task, 18 s/round, 6 min total; Bonsai 2 (`:8090`) **8/8**, median **253 s**/task, 47 s/round, 34 min total, uncached prefill ~53 tok/s, prompt-cache hit 58 %. **0 empty answers after tool rounds** for either (0/22, 0/12). The quality gap is noise at n=8 (95 % CI 68–100 vs 53–98); **speed is the only firm result.** Report: `data/bench/agent/report.md` (gitignored).
  - Qwen's one fail: the `manage_notes` call was right but the title said `[bench-44b]` for `[bench-44b6]` — a copying slip.
  - Bonsai's 5 failed tool calls were all environment: 4 SearXNG `timed out after 30s` (09:26–09:30; the only SearXNG failures in `app.log` when checked at 09:50) and one Britannica 403. Its 3 Wikipedia fetches were item 49's menu (prompt grew ~300 tokens each), so `1889` came from the REST summary API it tried last, or from memory. That run predates item 49's fix.
- 🔧 **Fixes after the run** (in `3bd9a006` unless marked): default URL is **7860**, not 7000 (macOS AirPlay Receiver answers 403 there; the script now says so on an `AirTunes` server header); warm-up and per-task stream errors containing *Cannot reach* abort the run instead of recording fake failures; the report splits failed tool calls into model and environment (timeouts, HTTP 4xx/5xx). **Committed later in `2bb475b1`:** per-task cleanup now matches any `[bench-` tag (`BENCH_TAG` in `bench_agent_tasks.py`) so a model-mistyped marker is still removed — checked with a stub API, not live.
- 🧹 **Left behind, maintainer to remove:** note *"[bench-44b] Workshop shopping"* (`fcb98691`), the only bench leftover in `app.db` (copy checked: no bench sessions, events, documents or memories). `python3 scripts/bench_agent.py cleanup` removes it. Also an unreadable `/tmp/x` tree in the agent VM from an earlier session — not in the repo.
- ⏭️ **Next:** full suite `--runs 2` per model (Qwen ~30 min, Bonsai ~2–3 h). ⚠️ **Blocked since the merge** until the script answers approval cards (see the 19:30 entry); the `web_fact` task can be passed from memory — once item 49's fix is confirmed, add a task answerable only from the fetched page.
- **Edited:** `scripts/bench_agent_tasks.py`, this file. `notes/qwensetup.md` is modified in the tree by another session (Bonsai start-script defaults) — not mine, not included. Only `git --no-optional-locks log/show/archive`; no lock taken.

---

## 2026-10-06 (00:30) — item 52 live check passed; item 45 seen live

- ✅ **Item 52 verified live** in `cdb89980` (last full reply = a stream-failure notice): *"Briefly: what were we talking about"* → thinking recapped the turns with no mention of a failure, error or empty response. A 23:31 attempt was sent incognito (no history read, nothing saved) and did not count.
- 🔴 **Item 45 caught live** at 23:31 in the same chat: the frontend sent another chat's active document (`68647d12`, *Pink Oyster Mushroom Growth Phases*) and the server logged *"cross-session active_doc_id … accepting and rebinding"*. Evidence added to the item, pointing at **item 62**, which another session filed for the same event and is fixing.
- ℹ️ The 00:29 recap repeated Bonsai's own earlier misreadings (*"Cedeago"*, *"parasolo"*) because they are in its saved reply (the `trigger_research` topic line) — history working as designed, not memory leaking.
- **Edited:** `notes/todo.md`, this file. No `git` command run.

---
