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

- **Approval cards.** Upstream's untrusted-context gate: once a tool result carrying text has entered the turn (a web fetch, search results — and, per `tool_result_should_arm_gate`, even an error body), tools that write files, edit documents, run code or reach the network need an approval click with the exact action sealed. A research → write-a-document turn will now stop on an approval card. Document edits with no open document return *"Open the exact document to edit, then request this action again…"*.
- **Stream failures end differently.** Upstream returns straight after a terminal provider/stream error and yields an `agent_terminal` record (`failed`, `failure`) with `[Agent stopped: Model request failed (HTTP n)]`. The fork's `_stream_failure_notice` (item 9b) no longer runs on that path, and `stream_errors` no longer reaches the final metrics there; the DB record of the failure is upstream's `failed`/`failure` metadata instead.
- **File tools and `data/`.** Everything under `data/` is refused except `agent_workspace/`, `uploads/`, `mail-attachments/`, `personal_docs/`, `personal_uploads/`. That is wider than item 60's list: `data/presets.json`, `memory.json`, `logs/`, `skills/`, `hwfit/` are refused now too. The agent's scratch folder, bash working directory **and bash `$HOME`** moved to `data/agent_workspace/`.
- **Upstream's docs** now live in `website/` (`setup.md`, `email-outlook.md`, …). This fork's notes stay in `docs/`.
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

## Owed checks (M1)

1. Full suite with `./venv/bin/python -m pytest` on the merge branch.
2. Live, after a restart and a hard reload: a plain chat turn; **New Chat twice** (item 54 — two sessions); a research → document turn (expect an approval card; approve it and check the document was written once); *"read data/settings.json"* (refusal naming `manage_documents`); with LM Studio stopped, a turn that fails (expect `[Agent stopped: …]`), then *"what happened?"* — the model's thinking must not quote the note.
3. A `web_fetch` of a LAN device with `WEB_FETCH_BLOCK_PRIVATE_IPS=false` in `.env`.
