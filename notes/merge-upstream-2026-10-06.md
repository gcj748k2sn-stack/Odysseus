# Upstream merge, 2026-10-06

Record of the merge of upstream `dev` into this fork: what conflicted, how each
conflict was resolved, and what behaves differently afterwards. Scope and
state, not findings; open questions it raises are listed at the end as owed
checks.

**Parents.** Fork `dev` at `2dfae628` (130 commits on `cb0f6af0`, 2026-07-29)
and upstream `dev` at `2992bf6d` (132 commits on the same base,
2026-07-29 → 2026-10-01, 40 authors). A merge, not a rebase, so every fork
commit hash cited in these docs stays valid.

**Done in a separate clone, not on the M1.** Merged with
`merge.directoryRenames=false` (upstream renamed its `docs/` to `website/`;
without the flag git moves this fork's notes there too). 25 files conflicted.

## Resolutions

| File | Resolution |
|---|---|
| 12 JS/HTML files (`app.js`, `index.html`, `chat.js` imports, `chatStream.js`, `chatRenderer.js`, `document.js` import, `emailInbox.js`, `emailLibrary.js`, `gallery.js`, `sessions.js`, `settings.js`, `slashCommands.js`) | Upstream's side with every first-party module `?v=` removed (item 54: one URL per module). CSS `?v=` kept. |
| `routes/document_routes.py`, `routes/document_helpers.py` | Upstream turned both into shims and moved the code unchanged to `routes/document/`. Shims kept; the fork's cumulative diff applied cleanly to the new files. |
| `.env.example` | Both blocks kept (`WEB_FETCH_BLOCK_PRIVATE_IPS` + upstream's `SECURE_COOKIES` text). |
| `website/setup.md` | Upstream's line. |
| `core/models.py` `get_context_messages` | Fork's notice-stripping view (item 52), then upstream's chat-session approval marker on the result. |
| `routes/chat_routes.py` | Both new helpers kept side by side (`_explicit_active_document`, item 62a; upstream's approval/candidate helpers). |
| `src/agent_tools/document_tools.py` | Fork's empty-update refusal, then upstream's approved-version check. |
| `src/agent_tools/web_tools.py` | Fork's labelled negative-cache failure + upstream's `untrusted_content: True`. |
| `src/llm_core.py` (3) | Upstream's harmony tool aliasing + fork's `think`; fork's defensive choice read and `[finish-reason]` logging around upstream's Mistral content handling and `(text, model)` return; upstream's split timeout handlers, each log line now naming the exception type (item 44). |
| `static/js/chat.js` | Upstream's superseded-send guard; upstream had also hoisted `abortCtrl`/`streamingTTS` (item 56), so its duplicate declaration was removed and the fork's hoist block kept. |
| `static/js/document.js` `saveDocument` | Fork's body (CAS retry, stamp guard, `reason` label), now returning booleans — see *Behaviour changes*. |
| `src/agent_loop.py` (8) | Imports from both; upstream's empty-assistant-turn skip + fork's `_turn_reasoning` tag (item 23); fork's `round_texts` comment; upstream moved the prompt build into per-route code, so the fork's one edit there (`_prompt_mcp_disabled_map`, item 51) was re-applied to the per-route `_build_system_prompt` call; stream error: fork records `_stream_errors`, then upstream's terminal handling; fork's truncation warning + upstream's usage finalisation; fork's split gate (items 2a/2b/7) + upstream's approval turn boundary. |
| `services/search/content.py` | Upstream moved the whole fetch transport to `src/outbound_fetch.py` (#5953). The fork's two-tier LAN guard (resolvedissues *"web_fetch could not reach the LAN"*) was ported there; `content.py` keeps thin wrappers so tests that monkeypatch `content._resolve_hostname_ips` / `_resolve_public_ips` still steer the real path. Negative cache and the item 49 extraction auto-merged. |
| `src/tool_execution.py`, `src/agent_tools/filesystem_tools.py` | **Upstream's version.** Upstream fixed item 60's hole on 2026-09-05 (security advisory) with a containment rule; the fork's filename list was retired. The fork's refusal hint (*"Read documents with manage_documents…"*) was added to upstream's message. Upstream's JSON ripgrep path replaces the fork's rg filter. |

## Changes beyond conflict resolution

Found by the tests or by reading the merged code; each is in the merge commit.

- **`static/js/chat.js`: `roundHolder` hoisted.** Upstream's new terminal-stream-error branch in the `catch` reads `roundHolder?.querySelector(...)`, but `roundHolder` was declared inside the `try` — a ReferenceError whenever `_catchViewHolder` had no `.body` (`?.` does not cover an undeclared name). Found by the fork's `test_static_js_block_scope.py`, which also flags it on upstream's own `chat.js`. Same fix shape as item 56.
- **`static/js/markdown.js`:** `katex.renderToString` → `window.katex.renderToString` inside the `if (window.katex)` guard. Same runtime behaviour; the bare name is also a block-scoped local elsewhere in the file, which the scanner flags.
- **`static/sw.js`:** four `PANEL_PRECACHE` entries lost their `?v=` (they must match the URL the browser requests) and `CACHE_NAME` was bumped. JS is network-first in the service worker and `Cache-Control: no-cache` from `/static`, so version-less URLs do not go stale.
- **`src/ui_notices.py`:** upstream's `[Agent stopped: …]` note is stripped from the model's view like the fork's own notices (item 52 class) — see the stream-error bullet below.

## Behaviour changes to expect

- **Approval cards.** Upstream's untrusted-context gate: once a tool result carrying text has entered the turn (a web fetch, search results — and, per `tool_result_should_arm_gate`, even an error body), tools that write files, edit documents, run code or reach the network need an approval click with the exact action sealed. A research → write-a-document turn will now stop on an approval card. **Reading a workspace file arms it too** (`read_file`, `grep`, `ls`, `glob` and `bash` results are `WORKSPACE_UNTRUSTED`), so *read a file, then write or edit one* in the same turn needs an approval. Checked 2026-10-06 against `ToolRunSecurityContext`: `write_file` is refused after one `read_file`. ⚠️ **`scripts/bench_agent.py` cannot answer approval cards**, so the tasks that read and then write (`write_file`, `edit_file`, `multi_step` in `--quick`) would stall and score as failures. The script needs to approve its own cards (`tool_approval_decision=approve_task`, the narrowest scope) and count them before the next benchmark run. Document edits with no open document return *"Open the exact document to edit, then request this action again…"*.
- **Stream failures end differently.** Upstream returns straight after a terminal provider/stream error and yields an `agent_terminal` record (`failed`, `failure`) with `[Agent stopped: Model request failed (HTTP n)]`. The fork's `_stream_failure_notice` (item 9b) no longer runs on that path, and `stream_errors` no longer reaches the final metrics there; the DB record of the failure is upstream's `failed`/`failure` metadata instead.
- **File tools and `data/`.** Everything under `data/` is refused except `agent_workspace/`, `uploads/`, `mail-attachments/`, `personal_docs/`, `personal_uploads/`. That is wider than item 60's list: `data/presets.json`, `memory.json`, `logs/`, `skills/`, `hwfit/` are refused now too. The agent's scratch folder, bash working directory **and bash `$HOME`** moved to `data/agent_workspace/`. ⚠️ **Not what was seen live:** on 2026-10-06 at 11:16 a relative `cat data/settings.json` succeeded, so that `bash` call ran from the repo root. The turn had called `get_workspace` first, so a bound workspace may set the directory. Which directory applies when is unverified; see [todo.md](todo.md) item 60.
- **Any saved skill arms that gate on every agent turn.** The skills index goes into the prompt through `untrusted_context_message("skills", …)`, which arms the gate by default (`arm_tool_gate=True`; nothing in the tree passes `False`). With this machine's two Arduino skills in `data/skills/` (moved out to `~/odysseus-snapshots/skills-2026-10-06/` at 19:24, so this no longer applies here), every side-effecting tool — `bash`, `write_file`, document edits — needs an approval click even on a turn that fetched nothing. **Upstream's own code behaves the same** with those skills (three upstream agent tests fail identically on `2992bf6d`). Not changed in the merge; it is a policy choice (skills are user-editable and can be imported, which is why upstream wraps them). The two ways out: *Allow for this chat session* on the first card, or pass `arm_tool_gate=False` for the skills message in `src/agent_loop.py` and accept that a poisoned skill could then steer tools unprompted.
- **Upstream's docs** now live in `website/` (`setup.md`, `email-outlook.md`, …). This fork's notes stayed in `docs/` for the merge and moved to `notes/` right after it (upstream's Pages-site rule forbids `.md` in `docs/`).
- **First start migrates `data/app.db`**: upstream adds `email_account_owner_locks` and email-account default/seed migrations (`core/database.py`). Snapshot first.

## Tests

Linux clone, Python 3.13, full `requirements.txt` (optional extras absent),
`DATABASE_URL=sqlite:///:memory:`, `pytest -n 2`:

| Tree | Result |
|---|---|
| Upstream `dev` (`2992bf6d`) | 5,945 passed, 11 skipped, 0 failed |
| Fork `dev` (`2dfae628`) | 6,254 passed, 4 skipped, 0 failed |
| Merge | **7,443 passed, 11 skipped, 0 failed** |

First merged run: 9 failed, 3 errors — fixed as follows:

- Upstream tests that pinned `?v=` tokens (`test_tool_approval_frontend_routing.py`, `test_tool_approval_task_scope.py`, `test_external_context_tool_gate.py`, `test_startup_session_bootstrap_js.py` import rewrites) now assert the version-less invariant instead.
- `test_panel_loader_js.py` precache check → `sw.js` entries fixed.
- `test_static_js_block_scope.py` (chat.js, markdown.js) → the two code fixes above.
- `test_tool_path_odysseus_state.py` rewritten for the merged policy (state refused, user-content dirs readable, the hint, the tools, the dispatcher with an explicit security context); `NOW_REFUSED` pins the tightening.
- `test_doc_edit_failure_end_to_end.py` holds upstream's gate open: it pins the end-of-turn report, and upstream's gate is covered by its own tests.
- `test_ui_notices_context.py`: two cases for the `[Agent stopped: …]` note, one a negative control.

**Mutations, each caught:** LAN opt-in allowed on every redirect hop (1 failure
in the URL-guard tests); route prompt given the unfiltered MCP map (2 failures in
`test_browser_tool_gate.py`); `roundHolder` back inside the `try` (scanner fails).

**Not verified by any test:** `saveDocument`'s return values (no JS harness).
Upstream's approval flow reads `documentSaved === false` as *"Document could not
be saved, so the action was not approved"*; the fork's paths now return `false`
for a refused stamp, a skipped 409 and a second conflict, `true` for
unchanged-since-sync and an adopted server version, and the conflict retry
returns the retry's result.

## First M1 run (2026-10-06 09:10)

`21 failed, 7430 passed, 3 skipped`. Every failure was reproduced or explained in the Linux clone:

| Tests | Cause | Merge-caused? |
|---|---|---|
| `test_web_fetch_size_caps.py` (8) | `WEB_FETCH_BLOCK_PRIVATE_IPS=false` in `.env` → `_get_public_url` passed `allow_private=` to upstream's one-argument test resolver | **Yes — fixed**: a resolver that cannot take the keyword gets the strict call (fails closed) |
| `test_docs_no_orphan_images.py::test_pages_site_owns_its_entrypoint_and_media` (1) | Upstream forbids `.md` in `docs/`; only runs in a git checkout, so the copy-based run had skipped it | **Yes — fixed**: first by exempting this fork's notes, then by moving them to `notes/` and restoring upstream's test unchanged |
| `test_token_cache_atomic_swap.py` (5) | Upstream's fixture calls `auth_manager.setup("admin", …)` against the real `data/auth.json`; with `cedrik` already there setup refuses, so `admin` never exists. (On a machine with no users it *writes* an admin user into the real file.) | No — upstream test reads the live data dir |
| `test_write_file_empty_body.py` (3) | `$TMPDIR` under `/var` → `/private/var`: the tool realpaths, the test's `path == target` hook never matches | No — upstream test, macOS only (reproduced with a symlinked `TMPDIR`) |
| `test_integration_api_call_ssrf.py::test_real_socket_falls_back_from_dead_first_to_live_second` (1) | Uses `127.0.0.2` as the "dead" address; macOS has only `127.0.0.1` on `lo0`, so the connect times out instead of being refused | No — upstream test, macOS only |
| `test_fenced_example_not_executed_for_native_models.py` (2), `test_external_context_tool_gate.py::test_authorized_document_stream_precedes_completed_update` (1) | The three skills in `data/skills/` arm the gate (above) | No — identical on upstream's code with those skills |

Linux clone after the fix, run the M1's way (single process, inside a git checkout, the M1's `.env` toggles): **7,450 passed, 4 skipped, 0 failed.** Expected on the M1 after the fix: the 12 non-merge failures remain until those upstream tests are made hermetic; running them with `ODYSSEUS_DATA_DIR` pointed at an empty directory clears the 8 data-dependent ones.

## The 12 machine-dependent failures, fixed in the tests (2026-10-06 12:40)

Test files only; no app code changed.

- **`tests/conftest.py`** gives the suite a fresh, realpath'd temp `ODYSSEUS_DATA_DIR`. Fixes the token-cache (5) and gate (3) failures, and stops the suite writing into the live `data/` (`app.log`, `skills/_usage.json`, `memory.json`, …).
- **`test_write_file_empty_body.py`** realpaths its fixture path (3, the macOS `/var` alias).
- **`test_integration_api_call_ssrf.py`** uses `::1` instead of `127.0.0.2` as the dead address (1).
- **Two tests the new data directory exposed:**
  - `test_research_report_read.py` wrote its fixture to the relative path `data/deep_research/`, which is the live install on the M1. It now uses `DEEP_RESEARCH_DIR`.
  - `test_security_regressions.py::test_dns_rebinding_redirect_re_resolves_per_hop` assumed the LAN opt-in was off. It now pins the setting itself.

**Linux clone, under M1-like conditions** (a `data/` holding a user in `auth.json` and both skills, a symlinked `TMPDIR`, `WEB_FETCH_BLOCK_PRIVATE_IPS=false`): **7,450 passed, 4 skipped, 0 failed**, and that `data/` was byte-identical afterwards.

**Each change checked by reverting it:**
- Without the conftest change, the 8 failures come back.
- Without the realpath, the 3 come back under a symlinked `TMPDIR`.
- Without the pin, the rebinding test fails with the opt-in on.
- The `::1` test fails when the fallback is mutated to try only the first address.
- ⚠️ **Not reproducible on Linux:** the macOS `127.0.0.2` timeout itself. The M1 run is the check for that one.

**M1, 2026-10-06 19:2x: 7,451 passed, 3 skipped, 0 failed** (committed as `34c7abb9`). The `/etc/shadow` count in the live `app.log` was 2 before and after the run.

## Second M1 run (2026-10-06 ~10:00)

`12 failed, 7,439 passed` — exactly the 12 non-merge failures in the table above, nothing new.

⚠️ **The suite writes to the real `data/logs/app.log`.** The `Tool executed:` lines at 10:00:07–10:00:15 (`read_file: /etc/shadow`, `write_file: ~/.ssh/authorized_keys`, `note.txt`, `run sleep 60`, …) are tests, not the agent. Check the time against the suite run before reading anything into them.

## Live checks (2026-10-06 10:48–11:54, after a restart)

| Check | Result |
|---|---|
| **New Chat twice** (item 54) | ✅ Two sessions. |
| **Research → document**, Bonsai 2 (10:56, 11:02) | ✅ Approval card, approved, document written once. |
| *"read the file data/settings.json"*, Bonsai 2 (11:10) | ⚠️ `read_file` refused (11:13:28, `exit_code=1`). **Bonsai then called `bash`: `cat data/settings.json 2>&1 \| head -100`.** The approval card came up (11:14:11) and was approved; it ran at 11:16:31 (`exit_code=0`). The contents ended up in chat `8abca026` and in a document *"Code (json)"*. **The maintainer deleted both at 12:05.** This is the hole [todo.md](todo.md) item 60 had already predicted, and it was not caused by the merge: the fork had the same gap. The approval card was the only barrier. |
| Document chip after New Chat | By design: the new chat sends `active_doc_id=''`, and the chip lets you decline. |
| **Qwen on LM Studio** (11:25–11:41) | ❌ Every round failed with `500 "Compute error."`. **LM Studio's fault, not the merge.** The request fields are the same as the fork's; the only addition, `_alias_harmony_tools`, applies to gpt-oss only. At 11:25:57 LM Studio loaded the model on demand while Bonsai 2 was still running on `:8090`. That loaded instance then failed every request within 0.03–0.09 s, including after Bonsai stopped (by 11:40). Fixed by `lms unload --all && lms load qwen/qwen3.5-9b --context-length 65536`; direct `curl` calls (plain and with a tool) worked after that. |
| Qwen after the reload (11:49–11:54) | ✅ A plain turn took 15 s. Research → document: the approval card for `manage_documents`, then `create_document`, then the confirmation. ⚠️ **No `web_fetch` or `web_search` in that turn**, so the index of the German Wikipedia page came from the model's memory. That's how the model behaves, not something the merge caused. |
| Failing turn → `[Agent stopped: …]` → *"what happened?"* | ⚠️ Done 12:36 and 20:03; behaves as upstream designed. **A turn that fails before any output saves nothing**: 12:36, a `502` after 14 s, left only the user's *"hey"*, and *"what happened"* got *"Not much just now"*. The model quoted no notice because none existed. That differs from the fork before the merge, whose item 9b saved a reply for such turns; the maintainer decided to keep upstream's behaviour. **A turn that fails after a tool call saves `[Agent stopped: Model request failed (HTTP 502)]`** (20:03, Bonsai 2, chat `b25e89e6`). |
| **LAN `web_fetch`** with `WEB_FETCH_BLOCK_PRIVATE_IPS=false` (20:16, Qwen) | ✅ `http://192.168.0.1` (the router; `route -n get default`) was approved and fetched. **The router answered**: the error was *"no readable text content (not HTML, or the page needs JS/login)"*, which comes after a response is received. With the opt-in off, the request would have been refused before connecting. The earlier timeouts on `192.168.178.1` (19:47–20:15) were a wrong address; `curl` from Terminal timed out the same way. |

`dev` was fast-forwarded to `c398a6a5` and pushed at 12:03.

## Owed checks (M1)

1. ✅ ~~Full suite with `./venv/bin/python -m pytest` on the merge branch.~~ Second M1 run above.
2. ✅ Done, see *Live checks* above. Original list: live, after a restart and a hard reload: a plain chat turn; **New Chat twice** (item 54 — two sessions); a research → document turn (expect an approval card; approve it and check the document was written once); *"read data/settings.json"* (refusal naming `manage_documents`); with LM Studio stopped, a turn that fails (expect `[Agent stopped: …]`), then *"what happened?"* — the model's thinking must not quote the note.
3. ✅ ~~A `web_fetch` of a LAN device with `WEB_FETCH_BLOCK_PRIVATE_IPS=false` in `.env`.~~ The router answered, 20:16 (see *Live checks*).
