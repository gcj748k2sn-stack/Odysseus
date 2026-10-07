# Session log

Brief, dated summaries of what each session *did* — not findings (those live in
[todo.md](todo.md) and [resolvedissues.md](resolvedissues.md)), just scope and
state changes, so the next session isn't starting cold. Newest first. Keep each
entry to a few lines — if it needs more, the detail belongs in `todo.md` or
`resolvedissues.md` and this should just link to it.

Keep roughly the last working day here; older entries move verbatim to
[archive/](archive/) (history, not current state): 2026-10-06 in
[archive/session-log-2026-10-06.md](archive/session-log-2026-10-06.md),
2026-07-30 to 2026-10-06 00:20 in
[archive/session-log-until-2026-10-06.md](archive/session-log-until-2026-10-06.md).

---

## 2026-10-07 (21:20–) — approval-flow fixes built: items 65, 66, 67 and the `409` log line — uncommitted

- 🔧 **65:** `doc_tool_result_landed` (`src/turn_report.py`) — a document tool waiting on a card is no longer reported as done, the non-document report skips it too, and an approved document action replayed at the start of a turn now gets its closing line (it never did). **66:** `_eventInsideElement` (`static/js/document.js`) ignores scripted events and 0×0 elements. **67:** `static/js/chat.js` skips the pre-approval save when no editor buffer exists. **`409`:** `routes/chat_routes.py` logs which check rejected an approval. Details in each item.
- 🧪 Linux clone, Python 3.13, deps from `requirements.txt` (not the M1 venv): new `tests/test_approval_pending_not_reported.py` 13 passed, 4 mutations each caught; `test_dangling_promise_turn.py` updated (it pinned the old gate's text); the approval/gate/report files 339 passed; **full suite `-n 4`: 7,445 passed, 11 skipped, 1 failed** — `test_integrations_url_join.py::test_api_call_root_path_has_no_trailing_slash`, the sandbox has no DNS (`host does not resolve`). **M1 run owed.** **JS: `node --check` only.**
- ➡️ **Live check (owed, in this order, Odysseus restarted first):** (1) agent turn that edits a document after untrusted context → card, and **no** *"Updated"* line; (2) **Allow** with the panel open → `POST /api/chat_stream` in `app.log`, document version up, closing line names the new version; (3) same again, then reload the page, panel closed, **Allow** → succeeds; (4) an expired or retired card (send any message first, then Allow the old card) → `Tool approval …… rejected (409): not pending …` in `app.log`; (5) *Resend* on a message with a document open → it sends. Watch for the empty-buffer / stale `v1` badge after (2).
- **Edited:** `src/turn_report.py`, `src/agent_loop.py` (2 call sites), `routes/chat_routes.py`, `static/js/document.js`, `static/js/chat.js`, `tests/test_approval_pending_not_reported.py` (new), `tests/test_dangling_promise_turn.py`, `notes/todo.md`, this file.

---

## 2026-10-07 (19:15–20:45) — cleanup committed and checked live; items 63–68 filed

- ✅ **Cleanup on the M1:** suite 7,441 passed, 3 skipped, 0 failed (the previous 7,451 minus the 10 removed tests); committed as `37cbbb10` (code) and `c46cf8b2` (notes), not pushed. The two benchmark runs of the day (Bonsai 17:15, Qwen 17:54) ran on code from before it — Odysseus had started at 16:06, the cleanup landed at 16:10 — so **Qwen's 34/36 is the "before" number**.
- ✅ **Live check after a restart (19:58):** an agent `edit_document` took the test document to **v2** with the change (copy of `app.db`), and the kept `switchAway` trace recorded **7 entries**. Getting the edit approved needed a console workaround, which is how the approval-flow bugs below were found.
- 🐞 **Filed:** item **65** (S1) — a pending approval is reported as *"Updated the document."*; **66** — Allow, Resend and queued sends are swallowed by the hidden email Send button's (0,0) hit-test; **67** — Allow with the document panel closed fails as *"Document could not be saved"*; **68** (S1) — Qwen claimed *"Created 'Switch check'"* with zero tool calls. 66 and 67 are upstream code; none comes from the cleanup. **Together, a document edit that needs approval cannot be approved from the UI today.** Approvals also expire after 10 minutes, and a stale one returns an unlogged `409`.
- 📝 **Filed items 63** (validation-gated changes to the agent rules, after SkillOpt) **and 64** (10 decisions waiting for the maintainer). From a copy of `app.db`: 72 sessions still pinned to `qwen3.5:9b-32k`; `[doc-put-404]` once ever, 0 since 08-01. A known-facts test produced no warning because the text never named the subject — test design, not a defect.
- ✅ The *"Pink"* test document's text was typed by hand — no cross-document leak. Both test documents deleted 21:05.
- ➡️ **Next session, in order:** fix items 65–67 (about a line each) and log why an approval is rejected with `409`; retest an approval from a reloaded page; then the owed verifications (items 7, 21, 9b, 2a).
- **Edited:** `notes/todo.md`, `notes/items/63-…`, `notes/items/64-…`, this file.

---

## 2026-10-07 (21:10) — item 60 closed as accepted

- ✅ **Item 60 closed (maintainer's decision):** file tools hold under upstream's `_is_app_state_path` (`grep` re-checked: no leak); `bash` is kept off with the *Shell Access* button and needs an approval card per command; nothing secret is stored (search keys empty, no email accounts, no keyed endpoints). Reopen conditions and three ways the button can be bypassed (chat-mode auto-escalation, absolute-path workspace binding, `ui_control` toggle) are in [items/60](items/60-read-file-write-file-can-read-and.md). Row moved to [resolvedissues.md](resolvedissues.md); `todo.md` counts corrected to 34 open / 40 closed (both were stale).
- Read-only checks on copies of `app.db`, `settings.json`, `cookbook_state.json`; a sandbox `grep` probe. **Edited:** `notes/todo.md`, `notes/resolvedissues.md`, `notes/items/60-…`, this file.

---

## 2026-10-07 (17:15–19:00) — first valid benchmark runs: Bonsai 2 `--quick`, Qwen full ×2; two scoring fixes — committed 18:54 (`3b1cce60`)

- 📌 **Current state of the benchmark — how to run it, why it is built this way, valid results — is now [benchmark.md](benchmark.md).** The 2026-10-05/06 benchmark entries below are history.
- 📊 **Bonsai 2** `--quick` (`20261007-171522`, plus `20261007-012621` from the night): **16/16**, median 142 s/task, 62 s/round, uncached prefill ~64 tok/s, cache hit 51 %. **Qwen 3.5 9B** full suite ×2 (`20261007-175428`): **34/36 as scored, 35/36 after the fix below**, median 42 s/task, 19 s/round, 30 min. On the 8 tasks both ran: 16/16 each. 0 empty answers after tool rounds for either; approval cards 7 (Bonsai, mostly its habit of computing with `python`) and 11 (Qwen). Report: `data/bench/agent/report.md` (gitignored).
- 🔧 **Odysseus's closing report is no longer scored as model text.** `src/turn_report.py` appends *"⚠️ **`python` failed** — …"* for any failed side-effecting tool, **even one the model recovered from** later in the turn; Qwen's `json_output` r2 replied exactly `{"rows":36,"nodes":3}` and failed *"no prose"* on that appended line. Checks now see the reply without the trailing report block (`split_turn_report`); the record keeps it as `turn_report` with flag `odysseus_turn_report`. ⚠️ Worth deciding separately whether a recovered failure should still be reported to the user that way — it is the fork's deliberate *"failures always"* rule.
- 🔧 **`calendar_create` split like `note_create`:** *"event created"* vs *"title copied exactly"*; Qwen r1 created `bench-2d22 Dentist` (brackets dropped) and then told the user it created `"[bench-2d22] Dentist"`. Cleanup and preflight match `BENCH_RE` (`\[?bench-[0-9a-f]{3,4}\]?`) instead of the `[bench-` prefix, which had left that event in the calendar (14 Oct, 14:00) — **`bench_agent.py cleanup` removes it once this is committed.**
- 🧪 Stub/mock only for the two fixes; the runs above used the previous version. **Edited:** `scripts/bench_agent.py`, `scripts/bench_agent_tasks.py`, this file.

---

## 2026-10-07 (00:00–00:20, written to the M1 16:10) — streamlining: dead stream-failure path removed, fork reporting moved out of `agent_loop.py`, comments condensed, notes split — committed 19:12 (`37cbbb10`, `c46cf8b2`)

- 🔧 **Code.** Removed `_stream_failure_notice`, `_stream_error_detail` and `stream_errors` — unreachable since the merge (every `event: error` now ends in upstream's `agent_terminal` + `return`); 10 tests went with them, and `ui_notices.py` still strips the old notice from saved chats. Removed the `[doc-put]` and `[doc-del]` log lines (their removal conditions were met); **kept** the `switchAway` trace (resolvedissues ties it to the 30–35 cluster, and 34 is open), `_stackFrames`, `[doc-put-404]` and the `[ai-tidy]` logging. Moved the fork's end-of-turn reporting to `src/turn_report.py` and the browser gate to `src/browser_gate.py` — `agent_loop.py` now differs from upstream by about 370 added lines instead of 1,340. Fork comments condensed to the why, with notes cited by title.
- 🧪 Linux clone, Python 3.13, `-n 2`: **7,440 passed, 4 skipped, 0 failed** (7,450 before, minus the 10 removed). Real `stream_agent_loop` driven through 28 scripted scenarios: output, prompts, tool calls and `src.*` log lines identical to the tree before the change. Comment-only edits checked mechanically: identical Python AST apart from docstrings, identical JS token stream. **Not run on the M1. JS not checked in a browser** (`node --check` only; the `switchToDoc` trace is unchanged code).
- 📝 **Notes.** `todo.md` is now the open-item dashboard (217 → 49 KB); 17 long items moved to `notes/items/`; the 35 closed rows are indexed at the top of `resolvedissues.md`, with new conclusions for items 18, 26, 36, 37 and 38. `CLAUDE.md` condensed (461 → 218 lines); fixed two stale claims (the "two pre-existing failures" and the `app.py` line numbers) and added §0 on keeping fork code out of upstream functions. Verbatim snapshots in `notes/archive/`. `qwensetup.md` left as is — its history is interleaved with current setup, not a separate block.
- ➡️ **Next:** the M1 full suite on these changes; one live agent turn that edits a document, and a hard reload with a document open (checks `switchToDoc`). The uncommitted benchmark changes from 22:45 were not touched.

---
