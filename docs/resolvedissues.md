# Resolved issues — Qwen 9B setup

Closed investigations. Setup and config live in [qwensetup.md](qwensetup.md); open items in [todo.md](todo.md).

## The record of a run didn't say what happened — fixed 2026-07-28 (items 10 + 17)
Two separate blind spots, filed separately and fixed together because they are the same failure: **`app.db` looked complete while omitting the one field that made a run interpretable.** Between them they blocked diagnosis three times and produced one wrong conclusion.

**Item 10 — tool arguments were truncated to their first line.** `tool_event["command"]` is `block.content.split("\n")[0][:80]`, which for a document edit is literally `<<<FIND>>>`: enough to know a call happened, nothing about what it asked for. Document tool events now also carry `full_command`, the complete arguments, capped at 16 KB by `_cap_persisted_command()` with an in-band `…[truncated by agent_loop: N more chars]` marker.

- **Persisted always, not only on failure.** The item was originally filed as "persist raw args on any conversion or parse failure", which is too narrow: c7da3649 **succeeded** — `v5, 2 edit(s)` — while silently skipping a third FIND block inside the same call. A failure-only rule would have discarded precisely the interesting case.
- **The data already existed and was thrown away at the last step.** `full_command` was computed and streamed to the client; only the persistence dict substituted `cmd_display`. The fix is one line plus the cap, not the M-effort the item was filed at — the estimate was wrong because nobody had read the code since.
- **Truncation is marked because an unmarked clip is worse than no record.** A replay that cannot tell a clipped payload from a complete one will faithfully reproduce a *different* call and call it a reproduction.

**Item 17 — a cache hit was indistinguishable from a live fetch.** `fetch_webpage_content` caches for 2 h and returned the stored dict unchanged, so nothing in the result, the tool output or `tool_events` said whether the bytes had left the machine. Two turns 4½ minutes apart both reported `uptime: 91 s` from a device whose counter was running; read back from `app.db` the second looked like a fresh reading of a frozen device.

- The served dict now carries `cached: true`, `cached_at` and `cache_age_seconds`, and `tool_events` persists them. **Absence of the flag means live.**
- **The model is told too, not just the database.** `web_fetch` output opens with *"served from cache, fetched N min M s ago — NOT a live reading"*, ahead of the `MAX_OUTPUT_CHARS` trim so a large body cannot push the notice out of range. The original failure was the *model* presenting a cached counter as a current measurement; labelling only the record would have left that intact.
- The served dict is a **copy**. Mutating the parsed cache payload in place would let any caller that keeps the result corrupt what the next hit returns.

Tests: `tests/test_tool_event_full_command.py` (7), `tests/test_web_fetch_cache_visibility.py` (6). The cache tests write only into a temp `CONTENT_CACHE_DIR` — never the live one, since calling `fetch_webpage_content()` against the real tree once put a fabricated value in front of the model, which recorded it in a user document as a measurement.

**Verified as non-regression by differential run, not by assertion.** 176 relevant test files with the change: `10 failed, 1692 passed`. The same 174 files at `HEAD` in a detached worktree: `10 failed, 1679 passed`. Identical failures, +13 being the new tests. The 10 are 8 in `test_web_fetch_size_caps.py` — which need DNS to resolve `example.com` and fail closed under the SSRF guard without it, reproduced identically at `HEAD` — plus the 2 in [todo.md](todo.md) item 18.

## Sixteen days of uncommitted work — committed 2026-07-28. The bookkeeping was wrong twice, in ways that would have lost the evidence.
Was [todo.md](todo.md) item 5. Last commit had been `df2fad2`, 2026-07-12; the work landed as seven commits (`825bcc1`…`e216313`), 47 files. Identity set repo-locally, nothing pushed.

**The item had been sitting on one blocker — "awaiting a git identity" — while two silent defects made the "protected" claim false.**

- **"44 files, staged" described 2026-07-19 and was never revised.** The entire 2026-07-27 session was *unstaged*: the two-tier SSRF guard in `services/search/content.py`, its two test files, the `.env.example` entry, every doc edit. So the sentence asserting everything was protected was itself the reason nobody checked. **A count written in prose is a claim with an expiry date and no test.** Nine days stale.
- **`COMMIT_PLAN.sh` named no `git add` for three staged test files** — `test_dangling_promise_turn.py`, `test_doc_closing_summary_accumulates.py`, `test_document_tools_reject_empty_writes.py` — and the script opens with `git reset -q`, so they would have emerged **untracked**: the staged-but-never-committed trap below, applied to the whole evidence base for items 7 and 8. Fixed, and the script now ends with a **coverage check** that diffs "staged when I started" against "present in the new commits" and names anything left behind. This class of error is invisible to human review and trivial to detect mechanically — which is the general lesson.
- The script also refused nothing on a second run: `git reset -q` would unstage everything, then the first `git commit` would fail on an empty index, leaving the tree *less* protected than before it ran. It now aborts when nothing is staged.
- **Rehearsed before running.** A copy of `.git` plus a throwaway identity, pointed at the real worktree: 7 commits, 47 files, coverage clean, second run correctly refused — then verified `HEAD` was still `df2fad2` with 47 staged and no identity. **Knowing a script parses is not knowing it runs**; `bash -n` had passed on the version that silently dropped three files.
- **A zero-byte `.git/index.lock` recurred twice during this session**, from a git process that lacked permission to unlink its own lock. The original 2026-07-18 instance blocked every git operation for 13 hours and is the likely reason nothing was committed for two weeks. It is worth checking `ls .git/index.lock` before concluding git is broken — the failure is silent and total.
- **Two pre-existing test failures were found and recorded rather than inherited.** The commit message for the document commit had been drafted claiming "687 source-level tests pass"; the measured result across all 24 test files in the series was **959 passed, 2 failed**, both in `test_document_put_version_conflict.py`. See [todo.md](todo.md) item 18 — they have never passed. The message now states this.

Deleted along the way: `llmSetup.md`, a redirect stub kept alive only by source citations, all seven of which now name entries in this file by title. Its worktree copy differed from its staged blob, so it was written to the object database with `git hash-object -w` before removal — recoverable at `93bdbbb7`.

## Turns that did work and reported none of it — fixed 2026-07-19 (items 7 + 8)
Two guards, one wrong assumption: **`full_response` being non-empty was taken to mean the model had said something meaningful.** It doesn't. This model habitually opens with its intent — *"I'll fact-check the guide by searching for verified data…"* — before calling any tool, and that preamble made every end-of-turn check pass.

Run 4e217ae0, one session, both failures back to back:

| Turn | Tools | Outcome | What the user saw |
|---|---|---|---|
| 2 | search, fetch ×2, **edit_document** | **4 edits landed** | the opening sentence, nothing about the edits |
| 3 | search, fetch ×2 | nothing | the opening sentence |

Turn 2 is item 7 (`_closing_doc_summary` bailed on a non-empty response). Turn 3 is item 8 (`_gathering_only_notice`, same test). And they compound: told nothing had happened in turn 2, the user reissued the identical request 16 seconds later, and turn 3 spent 162s producing nothing. **The silent success caused the silent failure.**

The per-round `_INTENT_RE` supervisor couldn't catch turn 3 either — it only inspects the current round's text, and the promise was written in an *earlier* round, before the tools ran.

**Fix.** A preamble is now detected **positionally**: the loop snapshots the prose before every tool block, and text still equal to that snapshot at end of turn cannot be a report of what the tool did. Positional rather than lexical deliberately — matching on "I'll" or "Let me" would be brittle and English-only. The synthesized report is **appended** to the preamble rather than replacing it, so the model keeps its voice. Separately, `applied`/`skipped` now accumulate across the turn (`version`/`title`/`stale_values` take the latest, since they describe the document as it currently stands); baac5d34's 5+1+3+1 now reads *"10 edits applied across 4 rounds"* instead of *"1 edit applied"*.

**Verified:** item 8's reporting half **live** on run eb2d0ac1 — *"I ran `web_search`, `web_fetch` and then stopped without producing an answer — nothing was created or changed."* Item 7's **failure branch went live 2026-07-27** on run 31e0af64, where an `edit_document` matched nothing and the turn reported *"I couldn't apply the edit — the document is unchanged… (skipped 1)"* with `round_texts` all zero, i.e. every word from the guard. The **accumulation branch** (*"N edits applied across M rounds"*, several successful rounds) is still tests only. Tests: `tests/test_doc_closing_summary_accumulates.py`, `tests/test_dangling_promise_turn.py`.

**The active half of item 8 — pushing another round — was tried the same day and reverted after it destroyed a document. See the next entry; it is the more important of the two.**

## Empty document writes destroyed a document — fixed 2026-07-19. Found by causing it.
`update_document` and `create_document` accepted **empty content**. `update_document` takes the full new document text, so "no content" and "delete everything" are indistinguishable at the call site — and it honoured the empty case, overwriting `current_content` with `""`. `edit_document` has refused empty content since 2026-07-18; these two never did. **Any empty call, from any cause, silently destroyed a document.**

**How it surfaced: a fix of ours triggered it.** The item 8 "cross-round stall" nudge told the model *"finish the job NOW using the appropriate tool."* Run 8c80cf8d — the first session to run that change:

| Time (UTC) | Document | Result |
|---|---|---|
| 09:53:25 | Pink Oyster Growth Phases | **6186 chars → 0 bytes** |
| 09:53:40 | Untitled | created empty |
| 09:53:52 | Untitled | created empty |
| 09:55:23 / 09:55:30 | Untitled | emptied twice more |

**Five zero-length versions in four minutes, against none in the preceding 79.** Attribution was unambiguous: a scan of every version in `app.db` found zero-length content *only* in the single session running that change.

**Fix.** All three document tools now refuse empty content with an error naming the alternative (`edit_document` for targeted changes). In `update_document` the check sits **before** the email coercion, which would otherwise rebuild an empty body into a valid-looking header block and launder the empty write into something that looks real. The refusal is an error, not a silent no-op, so the existing retry directive fires. The near-loss is logged with the size of what would have gone. Tests: `tests/test_document_tools_reject_empty_writes.py`.

The user's document was fully recoverable from `document_versions` — worth noting that version history, not the current-content column, is what made this survivable.

**Three lessons, all costly:**
- **Telling an idle model to act is not the same as telling it what to do.** With nothing to write, an imperative "act now" resolved to the most destructive available call. Detection and reporting are safe to ship on test evidence; directives that make the model *act* are not.
- **Tests must bound what a guard can do, not assert that it exists.** Every test written for the nudge passed — they checked it was present and capped, never what it could cause.
- **A destructive latent bug can sit indefinitely behind the fact that nothing ever calls it wrongly.** The empty-write hole predated all of this; it took a bad prompt to expose it, and it is the more valuable of the two findings.

## Diff review corrupted documents — fixed 2026-07-19. The editor manufactured item 3.
One Accept click in the AI-edit review overlay wrote a document containing **both** the pre-edit and post-edit text for twelve sections. Caught in production on the run that was testing the previous fix: doc `92f3b2a0` v3, +12 lines / −0, zero novel text, stamped `Diff review — chunk resolved` by the write labels added the same morning. That label is what identified it in one query.

**Mechanism, confirmed by replay.** Three things compounded:
1. `_applyResolvedChunksToTextarea` treated an **un-reviewed** chunk as rejected — "I haven't looked at this yet" was recorded as "I rejected this".
2. `_resolveChunk` called `saveDocument()` on **every click**, so that reading was written to the server mid-review.
3. Line-level LCS splits a rewritten block into separate delete and insert chunks. Leaving the delete un-reviewed restored the old heading while the neighbouring insert supplied the new one — so the document ended up asserting both.

**This is the mechanical cause of [item 3](todo.md) in at least some runs.** "Documents contradict themselves" was filed as the model fixing prose and missing the summary table. Here the model had already flagged the document as inconsistent; the editor then made it materially worse.

**Fix.** Revert a chunk **only** on an explicit rejection — accepted or not-yet-reviewed both keep the new side, which is what the server already holds. And `_resolveChunk` no longer persists: a review is a transaction that commits when it ends. Both apply paths now share one rule, where the original had two subtly different conditions (`resolved && accepted` vs bare `accepted`).

**Validated against external practice, not just intuition.** Monaco's diff model pairs a replacement as a single `LineRangeMapping` carrying both an original and a modified `LineRange` rather than two independent chunks; VS Code's merge editor requires all conflicts resolved before Complete Merge and deliberately updates the buffer *without* writing to disk. Both principles — never persist a partial review, never infer a decision from silence — are standard, and this code violated both.

**Scope verified at.** 810 source-level tests, including 605 property/fuzz cases over the ported diff engine. Replayed every recorded corrupted row: three of four are now **unreachable by any combination of decisions**, and the fourth requires **five explicit Reject clicks** — deliberate intent, not silent corruption. Zero-interaction and accept-only now always yield clean AI content. **Not yet observed in a live run** — the next review turn should produce either no `user` row or one labelled `Diff review — applied`.

**Trade accepted:** an in-progress review is lost on refresh. That was the stated reason for saving on every click; it is the correct trade and matches VS Code.

## Autosave reverting AI edits — fixed 2026-07-19. It was a duplicated SSE event, not autosave and not the CAS.
Third time this symptom has been written up, and the first time the mechanism was actually found. The compare-and-swap added on 2026-07-18 works correctly and was never bypassed — every destructive write passed it legitimately, because the client genuinely held the newest `base_version` and the *oldest* content.

**Trigger.** A single document tool call emitted `doc_update` **twice**: `src/agent_loop.py` had two emitters in the same `for i, block in enumerate(tool_blocks)` loop with no mutual exclusion (`is_doc_tool and "action" in result`, and `block.tool_type in (...) and result.get("doc_id")`). `static/js/chat.js` adds a third delivery on `tool_output` as a deliberate safety net. Nothing deduplicated them.

**Weapon.** `handleDocUpdate` opens with the #2484 guard `if (_diffModeActive) exitDiffMode(true)`. `enterDiffMode` deliberately leaves the textarea holding **pre-edit** content while the docs map and the server have already advanced to the post-edit version — so `exitDiffMode(discard=true)`, which restored `_diffOldContent` and then called `saveDocument()`, was shipping a strictly older buffer under a fresh `base_version`. The second delivery of the same event re-entered `handleDocUpdate`, hit that guard, and PUT the pre-edit content back ~80ms after the edit landed, recorded as `source="user"` / "Manual edit".

**Replayed against `app.db`, doc `0680daa3` of run baac5d34 — the model reproduces all nine rows, including the two it must *not* produce:**

| Transition | Changed lines | Predicted | Observed |
|---|---|---|---|
| v1→v2 | 7 | ≥3 → diff → revert to v1 | **v3 = v1**, +85ms |
| v2→v4 | 1 | <3 → animate, **no user row** | none written ✅ |
| v4→v5 | 3 | ≥3 → diff → revert to v4 | **v6 = v4**, +78ms |
| v5→v7 | 28 | ≥3 → diff → 409 → retry wins | **v8 = v4**, +79ms |

The v8 row also convicted a third defect: `saveDocument`'s 409 handler inferred "user typed" from content divergence alone, so the diff-restored buffer took the *"newest user intent wins"* retry and overwrote v7 on a fresh base.

**Fix — three layers, because any one alone leaves the others loaded:**
1. `src/agent_loop.py` — per-block `doc_update_emitted` flag; the second emitter is now a fallback for results that carry a `doc_id` but no `action`.
2. `static/js/document.js` — `exitDiffMode(discard, { persist = true })`. AI-driven teardowns (`handleDocUpdate`, `streamDocOpen`, `handleDocSuggestions`, `enterDiffMode`'s self-guard) pass `persist: false` and touch neither the textarea nor the server. A **user** pressing Reject-All / Escape / switching tabs still persists — that is a real intent to undo the edit.
3. `static/js/document.js` — `_userDirtyDocId`, set only from real DOM `input` events (browsers do not fire `input` for `textarea.value = …`). The 409 retry now requires it, so no code path can resurrect content the user never typed.

**Scope this was verified at — and this time it was actually verified.** Static source tests (`tests/test_document_diff_discard_on_update_js.py`, 11 assertions covering all three layers) with a negative control: the pre-fix sources fail 9 of them. Then, unlike the two previous closures, **confirmed against live runs.** Every client-side write in `app.db` was classified as REVERT (byte-identical to an earlier version) or BLEND (matching none):

| Era | REVERT | BLEND |
|---|---|---|
| pre-fix | **20**, across 10 documents and several days | 1 |
| post-fix | **0** | 2 → separate defect, fixed below |

Five consecutive post-fix sessions with zero reverts, including one edit changing **154 lines** — the largest qualifying edit in the dataset and precisely the shape that used to revert every time. The REVERT/BLEND split is worth keeping as a standing check: a revert is byte-identical to some stored version, a blend to none.

**A timezone error nearly buried this.** `app.db` stores naive UTC; `stat` reports local CEST. Comparing them directly made three post-fix sessions look like they predated the fix, and the first verification attempt wrongly concluded the runs proved nothing. Convert before concluding anything about ordering.

**Two lessons the earlier write-ups paid for:**
- The symptom named the wrong subsystem for three rounds. "Autosave is reverting edits" put every investigation inside the save path; the save path was correct throughout, and the bug was an event fired twice plus a guard that persisted its own cleanup.
- The 2026-06-07 fix for #2484 was itself the weapon. A guard that *writes* is not a guard. Tearing down state and persisting state are different operations, and the fix conflated them.

## The "Done." turns — diagnosed and fixed 2026-07-18. It was never a parser bug.
Turns that did real work returned `content="Done."` with all `round_texts` empty (11ea1727 t1, 88af1770 t1/t3, 127d32b0 t2). **Two wrong hypotheses were recorded before the cause was found — both are retracted:** (1) "thinking on → collapse" — fit the first four runs perfectly, then broke on the next pair; (2) "the reasoning parser eats the answer / investigate `<think>` close-tag handling on the `/v1` stream path" — sent debugging in entirely the wrong direction.
- **Actual cause** (`src/agent_loop.py`, the `_ody_doc_tool_completed` break): the doc-finetune path **breaks the agent loop the instant a document tool succeeds**, so the model never gets a round to write its closing summary. `"Done."` was a deliberate placeholder for when `full_response` was still empty at that point — working as designed, just badly.
- **Why it looked like misrouting:** the model's *reasoning* for that round naturally reads like a summary ("The document has been corrected with accurate pink oyster-specific parameters from CNC Substrates…"), so the answer appeared to be sitting in the thinking channel. It wasn't misplaced — the prose summary was never generated at all.
- **What actually predicts it:** did the turn end on a document tool, and had the model written anything yet?

  | Run | Last tool | `full_response` at break | Result |
  |---|---|---|---|
  | 127d32b0 t2 | `edit_document` | empty | "Done." |
  | 11ea1727 t1, 88af1770 t1/t3 | doc tool | empty | "Done." |
  | 127d32b0 t1 / f4da3893 t1 | `create_document` | 733 / 373 chars | kept its text |
  | f4da3893 t2 | `web_fetch` — no doc tool | n/a, no break | 5,978 chars |

  Thinking was ON for every row. It was never the variable.
- **⚠️ Correction 2026-07-18 (third wrong turn on this bug): the fix is gated off for `qwen3.5:9b-32k`.** `_ody_doc_tool_completed` requires `_ody_doc_finetune_mode`, which requires `_ody_qwen_finetune_model = model.lower().startswith("odysseus-qwen3")` (`src/agent_loop.py:2690`). The current model doesn't match, so the break being "fixed" never fires here in the first place. The diagnosis above is correct **for the Odysseus Qwen finetune**; `_doc_tool_summary()` is dead code on the current setup. The gate should have been checked before writing the patch. *Reference corrected 2026-07-27: this pointed at `todo.md` #2 (fact-check inverts ground truth), which is unrelated — the numbering shifted under it.* Both halves it meant are now closed entries in this file: the live "Done." path (`chat_routes.py:1495`) under *"'Done.' on read-only turns"*, and the split-gate recommendation under *"The document reporting path was dead code on the current model"*.
- **Fix:** new `_doc_tool_summary()` in `src/agent_loop.py` synthesizes the closing line from the tool result instead of the bare placeholder — free, no extra round, and more reliable than asking a 9B to recall its own edits. `"Created **X** (v1)."` / `"Updated **X** (v2) — 8 edits applied."` It also surfaces `skipped`, which matters: **`edit_document` returns success whenever ≥1 FIND block matches**, so partially-applied edits were previously silent — now they read `"6 edits applied, **3 not applied** (the FIND text didn't match — those corrections are still missing)"`. Tests: `tests/test_doc_tool_closing_summary.py`.
- **Lesson worth keeping:** two plausible hypotheses were written into this doc as findings before either was tested against the code. The correlation in the first was real and perfect across four runs, and still wrong. Check the code path before recording a mechanism.

## web_fetch could not reach the LAN — fixed 2026-07-27. Two SSRF policies in one repo, and a guard whose tests tested nothing.
`webfetch http://127.0.0.1:5500/…` returned `NetworkError: Blocked non-public IP literal: 127.0.0.1`. The block is not about loopback — `_PRIVATE_NETWORKS` in `services/search/content.py` covers every RFC-1918 range, so **`192.168.x.x` fails identically**. Reaching an ESP32 on the LAN was never possible, and switching from a local dev server to the real device would have hit the same wall with a different IP in the message.

- **The repo contained two contradicting policies.** `src/url_safety.py` (embeddings, webhooks, ntfy, notes) is deliberately local-first: it blocks only link-local/metadata by default and gates private/loopback behind `*_BLOCK_PRIVATE_IPS`, with a docstring arguing that pointing at a local vLLM/llama.cpp/Ollama is the primary use case. `services/search/content.py` — the only path `web_fetch` uses — was a hard lockdown with no knob. Same product, opposite defaults, no note anywhere.
- **Fix:** two-tier classification mirroring `url_safety.py`. *Hard* (never reachable, no override): link-local incl. `169.254.169.254`, multicast, reserved, unspecified, `0.0.0.0/8`, and the `metadata` hostnames. *Gated*: loopback, RFC-1918, ULA, and the `.local`/`.lan`/`.internal`/`.intranet` suffixes. Knob `WEB_FETCH_BLOCK_PRIVATE_IPS`, **default `true`** so no deployment changes behaviour, read per call so a running instance picks up an edit.
- **The relaxation applies to the first hop only.** `_get_public_url()` re-resolves every redirect; letting the opt-in ride along would mean a public page could 302 into RFC-1918 space — a textbook SSRF chain and a genuine regression. `allow_private and hop == 0`. `_PinnedBackend`/`_PinnedTransport` (the #704 DNS-rebinding pin) are untouched and still apply.
- **The trap the tests caught: Python reports IPv6 `::1` as `is_reserved`.** Tiered naively, the v6 loopback lands in the hard tier while `127.0.0.1` sits in the gated one — same host, two different answers depending on which literal the user typed. Gated ranges now win where the tiers overlap.
- **`_public_http_url()` had no production callers, and three test files were asserting against it.** Commit `5e9b415` (#704) moved the live check to `_resolve_public_ips` and left the old function in place; `git show 5e9b415^:services/search/content.py` still has it called at line 154. `tests/test_search_content_url_guards.py` — the file whose entire purpose is URL guards — tests **3 of 3** cases against the orphan and was not touched by that commit, so the live guard had zero coverage for weeks. `test_web_fetch_size_caps.py:93` monkeypatches the same orphan to `lambda u: True`, a no-op. It is now a thin wrapper over `_resolve_public_ips`, so the two cannot diverge again and the existing assertions exercise the real path. **Filed as [todo.md](todo.md) #16** — this class of false assurance is worth an audit beyond this one function.
- **Verification, stated at the scope it was done:** baseline captured against `HEAD` before comparing — 22 failures before, 22 after, *identical set*, passing 96 → 141. The 22 are pre-existing sandbox artefacts (`nh3` missing; the size-cap tests monkeypatch `httpx.stream` while the code uses `httpx.Client().stream`, another `5e9b415` leftover). End-to-end against a real server on `127.0.0.1:5500`: unset → blocked, `=true` → blocked, `=false` → content returned, `169.254.169.254` under `=false` → still blocked. Then live: `web_fetch http://192.168.0.185/api/state` returned 1806 bytes of complete JSON.
- One existing test needed updating, not weakening: `test_dns_rebinding_redirect_re_resolves_per_hop` stubs `_resolve_public_ips` and didn't know the new kwarg. The stub now records it and asserts both hops run strict; a new sibling test asserts hop 0 carries the opt-in and hop 1 does not.
- **Lesson:** the symptom said "localhost is blocked", which sounds like a dev-environment quirk. It was a product-wide policy contradiction, and the naive reading would have sent someone to whitelist `127.0.0.1` and ship something still unable to talk to the hardware.

## Research path moved off the retired 4B — 2026-07-19
`data/settings.json` had `research_model = qwen3.5:4b-16k`. The 4B was retired as chat model on 2026-07-18 for confident, plausible, wrong numbers — but deep research kept running on it, and research output feeds documents, so it was still doing exactly the damage described in [todo.md](todo.md) **#2** *(corrected 2026-07-27 from #1, which is the autosave data-loss item — the numbering shifted under this reference)*. The `-16k` suffix also gave it half the chat model's context. Now `qwen3.5:9b-32k`.
- **⚠️ "Or blank it to inherit the default" — the other option originally recorded here — was wrong,** and worth knowing before anyone reaches for it on `task_model`/`utility_model` too. `resolve_endpoint()` (`src/endpoint_resolver.py:305`) keys its fallback on the **endpoint id**, not the model: if `{prefix}_endpoint_id` is empty it takes `utility_endpoint_id`/**`utility_model`** (here `nemotron-3-nano:4b`, *smaller* than the 4B), and only falls through to `default_model` if utility is unset too. And with the endpoint id set — the current state, all three prefixes point at `f9264875` — a blank model reaches `_first_chat_model(enabled models)` and picks whatever the endpoint lists first. Blanking would have been non-deterministic at best and a downgrade at worst. Set it explicitly.
- **Also fixed: the retry follow-up lost task context.** `_is_contextual_retry_continuation()` only recognised Cookbook vocabulary, so "why did u stop, try again" after a document correction classified as a fresh low-signal turn and the retry no longer knew what it was retrying. Added `_DOC_RESEARCH_CONTEXT_RE` (document/edit/correct/fact-check/rewrite/research/sources), checked alongside the Cookbook set and equally narrow — the words must actually appear in recent turns, so ordinary chat still can't inherit stale context on the word "again". Tests: `tests/test_retry_continuation_doc_context.py` (8).
- `research_max_tokens` stays 16384, which is fine inside a 32k window.

## "Done." on read-only turns — the document fix didn't generalise, 2026-07-19
The "Done." bug was recorded as fixed twice above. Both fixes keyed off document tools, and `_empty_response_fallback` still returned early whenever `tool_events` was non-empty — so **every non-document turn kept falling through** to `routes/chat_routes.py:1495`. Four consecutive runs on 2026-07-19 (05:15–05:32, same request each time, user retrying) produced no file at all; two of them saved a bare "Done.".
- Worst case, 0b12aadb: `glob` found `martha9_1.ino`, `read_file` pulled 10,035 chars, and the model's own thinking ends *"I'll create a standalone index.html … Let me write out the extracted content:"* — then nothing. 393s, 154 output tokens, **0.39 tok/s**, no `write_file`.
- **Fix:** `_gathering_only_notice()` in `src/agent_loop.py`. If a turn produced no visible text and used **only** tools from an explicit `READ_ONLY_TOOLS` allowlist, it reports what ran and states plainly that nothing was created or changed. Any effectful tool, or any tool not on the list, and the guard stays silent — guessing an unknown MCP tool is read-only could tell a user their email wasn't sent when it was, which is worse than the bug.
- **Placement matters, and the first attempt got it wrong.** The guard initially sat inside `_empty_response_fallback`, which runs *before* `strip_tool_blocks` — at that point `full_response` still contains the tool fence the model emitted, so the turn looks like it produced text and the guard never fired. Caught by the end-to-end test, not the unit tests. It now runs after stripping, next to `_closing_doc_summary`, for the same reason that one does.
- Tests: `tests/test_gathering_only_turn.py` (11) plus an end-to-end case replaying 0b12aadb's shape.
- **Scope, stated honestly:** this stops the false success. It does *not* make the agent finish the job, and the two runs that wrote a dangling promise ("Let me first explore your workspace…") have a non-empty response so nothing fires for them. Open as [todo.md](todo.md) **#8** *(corrected 2026-07-27 from #7 — "the agent gathers information, then stops" is #8; #7 is the closing summary)*.
- **Lesson:** "fixed" was written down after one happy-path run on one tool path. The same class of failure was live on another path the whole time. A fix keyed to a specific tool set should be recorded with that scope attached.

## The document reporting path was dead code on the current model — split gate, 2026-07-18
`_doc_tool_summary()` and the stale-value warning sat behind `_ody_doc_tool_completed` → `_ody_doc_finetune_mode` → `_ody_qwen_finetune_model`, i.e. `model.lower().startswith("odysseus-qwen3")`. `qwen3.5:9b-32k` doesn't match, so both were unreachable on the model actually in use — the fix recorded under "The 'Done.' turns" had never once run here. Confirmed live on run c436d4a8 (21:19): `update_document` wrote v2, and the turn reported **"Done."** with no version, no edit count, nothing about what changed, on a turn whose entire point was the corrections.
- **Split, not widened.** Widening `_ody_doc_finetune_mode` would also switch on `:3134` (narrows `_relevant_tools` to five document tools when a doc is open) and `:3564` (`tool_choice_none`), taking 25-tool rounds down to 5 and re-enabling the loop break — which would kill the unprompted `create_document` → `edit_document` self-correction seen on b5fe4ef5 turn 1. That behaviour exists *because* the break is inert. Reporting is safe for every model; breaking the loop is not.
- **What changed** (`src/agent_loop.py`): the `_ody_doc_tool_info` payload is now built whenever any document tool succeeds, for every model; only `_ody_doc_tool_completed = True` (the loop break) stays behind the finetune flag. New `_closing_doc_summary()` synthesizes the closing line at end of turn for non-finetune models — placed *after* `strip_tool_blocks`, so a response that was nothing but a tool fence counts as empty. It fires only when the model wrote nothing; a real summary always beats a synthesized one. A later document-tool failure clears the payload so a stale success can't be reported after it.
- This also closes the surfacing gap on `find_stale_values()`: the lint was already model-agnostic, but its warning rendered through the gated summary, so on this model the finding only ever reached the logs.
- Tests: `tests/test_doc_report_gate_split.py` (10). Seven pin the closing-line behaviour; three pin the *structure* via AST — that the report payload has no `_ody_doc_finetune_mode` guard, that the loop break still does, and that tool narrowing and `tool_choice_none` remain gated. Verified the AST checks actually fail against a synthetic re-merged gate, so they aren't vacuous.
- **✅ Verified live 2026-07-19** (run 009660d2 turn 2). `round_texts` was `[0, 0]` — the model wrote nothing — and the saved response was **"Updated **Pink Oyster Mushroom Growth Phases** (v2) — 7 edits applied."**, byte-identical to what `_doc_tool_summary()` produces for that turn's tool result. Same shape that produced a bare "Done." the run before.

## `edit_document` silently received nothing — fixed 2026-07-18. Three recorded diagnoses, two of them wrong.
Run b5fe4ef5 turn 2 ("fact check and correct the dokument"): `web_search` → `edit_document` → **"No valid `<<<FIND>>>...<<<REPLACE>>>...<<<END>>>` blocks found"** → `update_plan` → stop. 526 seconds, document never touched (versions show only v1/v2, both from turn 1), no error surfaced in chat. **Two mechanisms were recorded here before the code was checked; both are retracted:**

1. ~~"The model emits malformed FIND blocks"~~ — written from the error *string* alone. The tool received nothing at all.
2. ~~"The model emitted a bare ` ```edit_document ` fence header, thinking having burned the output budget"~~ — written from the stored `command: ""` field without checking how that field is populated. Does not survive the parser (below).

- **Why (2) is impossible.** `command` is not the argument: for document tools `cmd_display = block.content.split("\n")[0].strip()[:80]` (`src/agent_loop.py:4105-4108`), a first-line preview. Turn 1 proves it — a *successful* 5-edit call stored `command: "<<<FIND>>>"`, and `create_document` stored only the title. And an empty fence can never reach dispatch: `parse_tool_blocks` drops a fence with an empty body, with the sole exception of `BUILTIN_EMAIL_TOOLS` (`src/tool_parsing.py:1268-1281`), and `_fenced_tool_call` strips the body (`:62`). A bare fence header would have produced **no tool event at all**.
- **Actual cause: a structured call with a misshaped argument, silently converted to an empty string.** The markup patterns (`<tool_call>` / `<invoke>` / `<tool_code>` / raw OpenAI JSON leaked as text — all active on this endpoint) funnel into `function_call_to_tool_block` (`src/tool_schemas.py`). Its `edit_document` branch read `edits = args.get("edits", [])`, coerced anything non-list to `[]`, appended nothing, and returned `content = ""` — which was then dispatched. Any shape but a well-formed `edits` array landed here. `_REQUIRED_NATIVE_TOOL_ARGS` would have rejected it but lists only `web_search`/`web_fetch`/`read_file`/`write_file`/`edit_file`; `_repair_document_function_args` only handles `update_document`.
- **The budget claim was also wrong.** 1440 output tokens across 4 rounds against `max_tokens=4096` *per round* — nothing was truncated. Not the #9 residual.
- **And the model did react to the failure.** Round 3's thinking opens *"I apologize for the confusion in my previous response"* and re-derives the corrections. It then re-emitted the same broken shape and fell through to `update_plan`. The generic parse error never told it what was actually wrong.
- **Fix, part 1 — `_coerce_edit_items()` in `src/tool_schemas.py`,** used by the `edit_document` and `suggest_document` branches. Now accepts the shapes models actually emit: a single dict where a list is expected, double-encoded JSON (`"edits": "[{...}]"`), raw `<<<FIND>>>` markup as the argument or under `content`/`text`/`body`, a `find`/`replace` pair hoisted to top level, a list of markup strings, and `old_string`/`new_string` aliases. Fallbacks only run when the dedicated key yielded nothing, so a well-formed call is never second-guessed. **This alone would have made turn 2 succeed.**
- **Fix, part 2 — `src/agent_tools/document_tools.py`** now separates "received nothing" from "markers are wrong", with the fenced syntax shown in the empty case. Sharing one message is what let a converter bug read as model syntax error for a whole debugging round.
- **Fix, part 3 — retry directive, `_doc_edit_retry_directive()` in `src/agent_loop.py`.** A failed document tool result now carries the exact syntax and "the document is UNCHANGED, retry now, do not end the turn". On the **second** consecutive failure it demands `update_document` with the complete corrected document — a full rewrite has no FIND text to mismatch. Counter resets on any document-tool success.
- **Fix, part 4 — end-of-turn guard, `_empty_response_fallback()`.** A turn whose last document edit failed can no longer report success: with no text it emits "I couldn't apply the edit — the document is unchanged"; with text it appends the same notice, because prose surviving a failed edit is almost always a false success claim. The old guard returned early on `tool_events` alone — exactly how a 526-second no-op reached `routes/chat_routes.py:1495` and was saved as "Done.".
- **Parts 3 and 4 are not equivalent.** Part 3 is still guidance, just delivered at the failure instead of buried in a 30k-token prompt; for local models it's the only channel, since no tool schemas are sent to them at all. Part 4 is the half the loop can actually enforce, and it — not the retry — is the real answer to "the user asked for a correction and got nothing".
- Tests: `tests/test_edit_document_call_shapes.py` (12), `tests/test_doc_edit_retry.py` (8), `tests/test_doc_edit_failure_end_to_end.py` (7). Also fixed in passing: `tests/conftest.py`'s `src.database` stub lacked `Document`/`DocumentVersion`, so any test reaching a document tool died at its lazy import.
- **On testing these paths: organic runs can't.** Parts 3 and 4 only fire when the model emits a broken call shape, which after part 1 is rare — run 009660d2 edited cleanly on the first attempt and touched none of this code. Waiting for a real failure to recur is not a test strategy, so `test_doc_edit_failure_end_to_end.py` injects one: it drives the real `stream_agent_loop` with a scripted model stream (monkeypatching `stream_llm_with_fallback`, the pattern already used by `test_fenced_example_not_executed_for_native_models.py`) and asserts the directive actually reaches the next round's prompt, that escalation counts across rounds, and that a silent failed turn streams the failure notice rather than "Done.".
- **Lesson, third time on this same bug family:** a mechanism was recorded from a symptom string, then a second from a metadata field, neither checked against the code that produces them. Check the *writer* of the evidence, not just the evidence.

## ⚠️ Editor autosave silently reverting AI document edits — REGRESSED 2026-07-19, reopened as [todo.md](todo.md) #1
**Do not read the entry below as current.** The same failure returned on run baac5d34 (document `0680daa3`), worse than before: three separate `user` "Manual edit" rows, each written in the *same second* as the AI edit it reverted, verified by content hash (v3 == v1, v6 == v4, v8 == v4). It also corrupted the agent loop — the model ran four `edit_document` rounds with FIND texts that kept missing, because the document was being reverted underneath it between rounds. The fixes below were real and verified at the time; something in this path is not covered by them. Full evidence table in [todo.md](todo.md) #1.

## Editor autosave silently reverting AI document edits — fixed 2026-07-18 (see regression note above)
Was TOP PRIORITY silent data loss: `saveDocument()` PUT the browser's cached copy back over a newer AI-written version ~60ms after the edit landed, recorded as `source="user"` (evidence: v3 user byte-identical to v1, 60–70ms after v2 ai, docs 5bce6d08/ec865815). Fixed on both sides:
- Server (`routes/document_routes.py`, `routes/document_helpers.py`): `DocumentUpdate` gains optional `base_version`; `PUT /api/document/{id}` returns **409 version_conflict** when it doesn't match `version_count`. Callers not sending it keep legacy behaviour.
- Client (`static/js/document.js`): docs-map entries track `lastSyncedContent`; autosave **skips the PUT when content is unchanged since last server sync**; PUTs send `base_version`; on 409 the client refetches — pure stale autosave adopts the server (AI) state into map+editor, real user typing retries once on top of the fresh version (newest user intent wins). `handleDocUpdate` also clears any queued autosave timer when an AI edit lands.
- Tests: `tests/test_document_put_version_conflict.py` (4 pinned directions). Note the coalesce-window audit-trail destruction (`VERSION_COALESCE_SECONDS`) is moot for this path — the stale save is now rejected before it can coalesce.
- **Verified live 2026-07-18** (run 127d32b0, doc 71de75d9): `v1 ai 1eded656 → v2 ai dd9af516 → v3 user dd9af516`, `CURRENT = dd9af516`. v3 now carries **v2's hash instead of reverting to v1's**, and the gap moved from 60–70ms (stale clobber) to 10s (normal debounced autosave after refresh). The AI's corrections persisted.
- Residual, cosmetic: the client still writes that redundant `source="user"` / "Manual edit" version with byte-identical content. The server's `if doc.current_content == incoming_content: return` guard should have skipped it, and `summary="Manual edit"` rules out a deliberate `force_version` checkpoint — so either a normalization difference or a PUT already in flight when v2 committed. No data loss; just inflates version history.
- **Race reappeared 2026-07-18 07:49, now closed properly.** Same doc, turns 3–4: `v4 ai 82ade60c (07:49:02) → v5 user dd9af516 (07:49:02, stale clobber back to v2's content) → v6 user 82ade60c (07:51:22, self-healed)`. `CURRENT` ended correct so nothing was lost permanently, but for ~2m20s the editor showed the pre-correction document. The `base_version` check hadn't failed — it had been *bypassed*: it compares against a `version_count` SELECTed at the top of the handler, so an AI edit committing between that read and the write validates cleanly and then clobbers. Check-then-write was never atomic; the first fix only narrowed the window from ~60ms to same-second.
  - **Fixed** in `routes/document_routes.py`: the write is now a compare-and-swap — `UPDATE documents SET … WHERE id = :id AND version_count = :base_version`, with 0 rows matched treated as the conflict (409). A concurrent AI edit bumps `version_count`, the WHERE stops matching, and the rollback discards the staged `DocumentVersion` insert so a losing write leaves no trace in history. The early `base_version` check is kept as a cheap pre-filter but is explicitly documented as non-authoritative.
  - Tests: `tests/test_document_put_version_conflict.py` — 3 added, including one that interleaves a real committing AI edit inside the handler's read→write window (the exact 07:49:02 shape).

## Active-doc turns losing edit tools on low-signal input — fixed 2026-07-18
"yes and include sources" classified `low_signal=True, domains=[]` → RAG path sent 11 tools without `edit_document`/`update_document` → model created a duplicate doc. New `_vague_turn_keeps_active_document()` in `src/agent_loop.py`: when `_turn_targets_active_document()` says no but the turn is low-signal or a continuation, mid-conversation, with a document open (and not a casual greeting), the document stays relevant — so the existing guard adds `edit_document`/`update_document`/`suggest_document` and the doc context rides along. Tests: `tests/test_active_doc_vague_turn_tools.py` (pins the exact observed failure input). Was knownIssues #3.
- **Verified live 2026-07-18** via `[agent-debug]` lines: `tools_sent=25` with `edit_document` + `update_document` present on **every round of both runs**. The 9B called `edit_document` at round 4 → `Document edited: (v2, 8 edit(s))`. Stronger confirmation: the 08:49 run had the classifier still misfiring (`relevant_tools=['ask_teacher','list_downloads','search_hf_models'…]`) and the document tools were force-included anyway — the guard holds even when intent classification is wrong.
- **Important reclassification:** the 4B in the same test had all 25 tools on all 6 rounds and *still* never called one — 2 searches + 3 fetches, then a 5,978-char chat essay describing corrections it never applied (doc stayed at v1). That failure was previously blamed on tool stripping; it is model capability, and it is what retired the 4B.

## Tooling added 2026-07-19
Built during the editor investigation, useful beyond it. Moved here from [todo.md](todo.md) on 2026-07-27 — it is a record of work done, not a work item.

- **`tests/tools/diff_model.py`** — faithful Python port of the editor's diff engine (`_computeLineDiff`, `_buildDiffChunks`, the two apply paths) plus a small editor state machine. Lets diff/merge behaviour be replayed and property-tested offline, with no browser.
- **`tests/tools/replay_blend_rows.py`** — replays recorded `document_versions` rows against that model, searching operation sequences that reproduce a corrupted row byte-exact. Reproduced one; proved three others unreachable under the fixed rules. Re-runnable against any future `app.db`.
- **Write labels.** Every client-side document write now carries which path produced it (`Autosave`, `Diff review — chunk resolved`, `Diff review — applied`, …) in the version summary, visible in the version-history panel. This identified the diff-review corruption in **one query** after a replay harness had failed to pin it. Highest value-per-line change of the day.

## Run log — the pink-oyster series, 2026-07-18 → 07-19 (9B, thinking ON)
Same task each time: create a growth-phase document → "fact check and correct". Mechanics converge across the series; content does not.

| Run | Turn 2 | Time | Document | Closing line |
|---|---|---|---|---|
| b5fe4ef5 19:24 | `edit_document` → empty-arg error → `update_plan` → stop | **526s** | **never touched** | "Done." |
| c436d4a8 21:19 | `update_document` full rewrite | 394s | v2 written | "Done." |
| 009660d2 07-19 04:55 | `edit_document`, 7 edits, first attempt | **161s** | v2 written | **"Updated **…** (v2) — 7 edits applied."** |

- **Mechanically: fixed.** 009660d2 is the first run in the series where the turn both changed the document *and* told the user what it changed. The closing line is the synthesized summary — `round_texts` was `[0, 0]`, the model wrote no prose at all. Time also fell 526s → 161s across the series.
- **The failure paths went untested by all three.** 009660d2's edit succeeded on the first attempt, so the retry directive, the escalation, and the failure notice never ran. That is what `tests/test_doc_edit_failure_end_to_end.py` exists for.
- **Content got worse, not better.** c436d4a8 re-introduced cold shock ("slight cooling to 20–24°C helps initiate pinning"); 009660d2 went further and inverted the species outright — *"pink oysters prefer slightly cooler than other Pleurotus species during fruiting"* at 65–70°F, with an explicit "Cool down by 3-5°F from spawn temp". Both documents call themselves "Fact Checked & Corrected". One genuine win: 009660d2 got CO₂ right (`<800 ppm`) for the first time in the series. Open as [todo.md](todo.md) #2.
- **Autosave holding.** Clean `v1 ai → v2 ai` on every run; the only residual is the byte-identical `user` row (009660d2 v3 == v2), which is cosmetic.

### b5fe4ef5, 2026-07-18 19:24 — detail
Fourth round of the same pink-oyster task. Mixed: the autosave fix is clearly holding, the edit path clearly is not.
- ✅ **No stale `user` version at all.** Document 10bfeee3 has only `v1 ai` / `v2 ai` — the first run in this whole series with a clean version history. Previous runs always carried a redundant or reverting `user` row. The client-side `lastSyncedContent` guard is doing its job.
- ✅ **Turn 1 self-corrected unprompted:** `create_document` (v1, 8580 chars) → `edit_document` (v2, 5 edits, 7115 chars) in the same turn — it reviewed and tightened its own output without being asked. New behaviour, and the reason it could happen is that the doc-finetune break is inert on this model (it would otherwise have stopped after `create_document`). An accidental benefit of the gate being off.
- ❌ **Turn 2 accomplished nothing in 526s.** `edit_document` errored → `update_plan` → stop. Document unchanged. ~~Malformed FIND blocks.~~ Diagnosed and fixed 2026-07-18 — the tool received an empty string because the argument converter discarded the call's shape; see "edit_document silently received nothing" above.
- Timings: t1 326s / 9.13 tok/s, t2 526s / **2.74 tok/s** (slowest recorded — 30.7k input but only 1440 output over 3 rounds).

## 4B retired — 2026-07-18
Six same-task runs (create a pink-oyster growth-phase doc → fact-check → correct), with the documents independently fact-checked against cultivation sources rather than scored on whether the tool chain completed. Ground truth used: colonization 24–29°C, fruiting 20–30°C (tropical, **no cold shock**), RH 85–95%, CO₂ 500–800 ppm at 3–6 air exchanges/hour.

| Model | Thinking | Document produced |
|---|---|---|
| 4b | off | worst — invented a 22-day "storage phase" at 15–20°C, harvest pushed to day 46–50 while its own overview said 3–4 weeks |
| 4b | **on** | bad — fruiting at 16–20°C (*P. ostreatus* cold-shock rule applied to a tropical species); CO₂ held at 1000–1500 ppm through fruiting, backwards |
| 9b | off | good — colonization 24–30°C correct; dodged the CO₂ trap mainly by not specifying CO₂ |
| 9b | **on** | **best — correct on every parameter checked, only one with sources** |

Round 2 (2026-07-18) removed the last doubt: with `edit_document` provably in hand on every round, the 4B still refused to edit and wrote an essay instead. **The 4B's failure mode is the dangerous kind** — specific, confident, plausible numbers aimed at chamber setpoints. Retired; 9B is the sole chat model.
- **The fact-check step is not trustworthy — this outlived the 4B.** Every run "corrected" toward a *different* temperature, and **none caught the CO₂ error**, the most consequential mistake in the set. Round 2 showed the 9B's fact-check is wrong in a subtler way (see "Partial find/replace" in [todo.md](todo.md)). It reads as thorough — tables, ✅/⚠️ markers, citations — while not converging on truth. Treat an agent fact-check as a prompt to go look, never as a verdict.
- Search quality contributes: runs pulled junk results (a Victoria's Secret "PINK" page ranked into mushroom searches) and none noticed. Query disambiguation for ambiguous common nouns is weak. One `web_fetch` also took an HTTP 403 (thesporedepot) and the model correctly moved on.

## Thinking suppression for agent rounds — 2026-07-17
Closes the old open item "Disable/cap thinking" and the #9 residual (thinking burning the whole max_tokens budget → 0-char/0-call empty round). Went with disable-thinking (Option A), behind a configurable toggle. Key finding that cost two failed attempts: **Ollama's `/v1` OpenAI-compat endpoint silently ignores the native `think` param** — the working control is `reasoning_effort: "none"` (confirmed at docs.ollama.com/api/openai-compatibility; the old code comment claiming `think:false` worked on `/v1` was wrong, and Odysseus streams via `/v1`, so suppression had never actually fired). Patched `src/llm_core.py`: agent/tool rounds (calls that pass `tools`) on Qwen thinking models (`qwen3`/`qwq` only — Ollama rejects the param on non-thinking models like gemma3) send `reasoning_effort:"none"`; native `/api/chat` path also gets `think:false` + a `/no_think` system-message fallback for pre-0.9 Ollama. Gated by setting **`agent_disable_thinking`** (default `true`). Chat rounds (no tools) always keep thinking. Tests: `tests/test_llm_core_ollama_thinking.py`. Verify via the `[agent-timing] first_visible_token … thinking=` log line.
Current setting: `agent_disable_thinking: false` in `data/settings.json` — thinking stays ON for the 9B. The toggle remains as an escape hatch.
- **Token note** (recurring misconception): no-think does NOT use more tokens. The per-round prompt growth is web_search results (~3k/search) plus the created document echoing back through the replayed tool call — unrelated to reasoning.
- **9B-on cost, measured:** first token 27–60s/round, whole turns ~220–335s. Context peaks ~13k/32k on create turns but **76–89k input tokens on fact-check turns** once fetched pages accumulate — the fetches, not the reasoning, are what fills the window. Inherent to a 9B on a 16GB M1 Pro.

## Context-window mismatch — 2026-07-16
The app logged a known context window of `131072`, but the `-16k` Ollama variants serve `num_ctx 16384` (confirmed via `ollama show` and server log `n_ctx_slot = 16384`). Context trimming budgeted against a window **8× larger than real**, so Ollama silently truncated the prompt top (system prompt + skills die first). Fixed in `src/model_context.py`: for local endpoints a `-16k`/`-32k` name suffix now declares the window and beats the known-models table; live endpoint reports (llama.cpp `/slots`, `/v1/models` context fields) still beat the suffix. Tests: `tests/test_model_context_name_suffix.py`. Expect the log line `Model name suffix declares context window for … : 16384`. **Takes effect only after an app restart.** Hence the 32k build in Models — the suffix logic picks it up automatically (fits 16GB with `OLLAMA_KV_CACHE_TYPE=q8_0`).

## Agent preset max_tokens — 2026-07-16
Set to 6400.

## Skill pipeline rollback — 2026-07-17
The experimental component-lookup / reference-creation skill pipeline was rolled back: the two split skills (`component-library-check`, `sensor-component-spec-reference-creation`) and the old combined `electrical-component-reference-lookup` were deleted, and the local `src/agent_loop.py` patches (skill tool-union, step-1 supervisor, ask-gate, pending-ask continuation flag) were reverted along with their tests. The general Skills facts in [qwensetup.md](qwensetup.md) still hold; that enforcement machinery is no longer in the tree.
