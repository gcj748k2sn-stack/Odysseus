# Resolved issues — Qwen 9B setup

Closed investigations. Setup and config in [qwensetup.md](qwensetup.md); open items in [todo.md](todo.md).

**Trimmed 2026-07-28 from 283 lines to what still earns its keep.** The test applied to every line: *would someone about to make a decision be worse off without it?* What survived is **retractions** (wrong mechanisms recorded as findings — three separate re-investigations have been stopped by these), **traps that recur**, **ground truth**, and **the scope a fix was verified at**. What went is mechanism walkthroughs, per-run evidence tables and timings: all of it describes code that is now fixed, tested and committed, so it is re-derivable and was costing a re-read on every visit.

**Where the detail went.** Everything fixed before 2026-07-28 is in the initial commit series `b700632`…`ae4fa58`, whose messages carry the diagnosis; later work is in its own commit. **List them with `git log --format='%h %s' origin/dev..HEAD`** — deliberately not `<base-hash>..`, because the base moved: these were rebased onto a rewritten upstream on 2026-07-28 and every hash in these docs changed with it. Then `git show <hash>`, or `git log -S<symbol>` to find the change that touched a function. **Headings here are cited by title from source comments — rename with care** (see *Notes & constraints* in [todo.md](todo.md)).

---

## The document didn't match its source — checker built 2026-07-28 (item 2a)
Two runs turned one small JSON payload into a table. **239 of 240 cells were transcribed correctly and both documents were still wrong**, because the model picked the wrong *field*: `duty: 252` is a PWM register after a BC547 inversion — 255 is off, so that is about 1 % power — printed as a reportable duty cycle. Every digit is copied faithfully from the source.

**That is why the obvious design was wrong.** A source-to-document diff is structurally incapable of catching it: the value is in both. The item was filed as "transcription", and transcription turned out to be the *incidental* half — one wrong cell in 240, in one run of two — while field selection was systematic, 2 of 2.

- **`config/field_semantics.json` carries the weight.** Written-down facts about fields the agent keeps misreading: which are raw registers, which field actually answers the question, what the sample interval is, which values are meaningless from cache. Keyed on a substring of the **URL**, so a field called `duty` on another device is never judged by this device's entry.
- **The diff still ships**, because the dropped column and the two absent sensors were real. It just isn't the load-bearing part.
- **The clean run is a required test, not a nicety.** A checker with only a positive case can be a function that always fires and still look like it works — item 16's green suite asserting nothing, and item 19's `isabs` guard that was `False` in both the broken and the fixed case. `test_clean_run_reports_no_transcription_findings` is what stops that recurring here.
- **Report-only, and pinned so by tests.** Item 8's nudge destroyed a 6186-character document by telling an idle model to act. `test_findings_never_reach_a_model_facing_path` asserts the findings appear in no prompt or tool-directive path; the call is wrapped so a failing lint cannot kill a turn.
- **Silence is a supported outcome.** No JSON source in the turn, no findings. Most document turns are prose, and a checker that guesses trains people to ignore it.
- **Two bugs the tests caught that reading did not.** (1) The identifier column was taken from JSON key order, so a fixture written with `sort_keys=True` made every row lookup miss — it reported the ragged table and none of the cells inside it, failing *quietly*, which is the exact failure mode the module exists to prevent. Now chosen by matching the rendered rows. (2) `_doc_tool_summary` returned early for `create_document`, so the warning was dead for the one tool both motivating runs used.
- **Placement:** the loop, not the document tool — the source arrives from a `web_fetch` rounds earlier and only the loop sees both. That also means it covers `update_document`, which bypasses the tool-local stale-value lint (item 3).
- ⚠️ **Verified on both recorded runs and on 25 tests; not yet on a live turn.**

## The record of a run didn't say what happened — fixed 2026-07-28 (items 10 + 17)
Two blind spots, one shape: `app.db` looked complete while omitting the field that made a run interpretable. Between them they blocked diagnosis three times and produced one wrong conclusion. Commit `5e27f6a`.

- **Item 10.** `tool_event["command"]` is the first line of the arguments, which for a document edit is literally `<<<FIND>>>`. Document events now also carry `full_command`, capped at 16 KB with an in-band truncation marker.
  - **Persisted always, not only on failure.** c7da3649 *succeeded* — `v5, 2 edit(s)` — while silently skipping a third FIND block. A failure-only rule discards exactly the interesting case.
  - **An unmarked clip is worse than no record:** a replay that can't tell a clipped payload from a complete one reproduces a *different* call and calls it a reproduction.
- **Item 17.** A cache hit was indistinguishable from a live fetch. Results now carry `cached` / `cached_at` / `cache_age_seconds`; absence means live. The notice also reaches **the model** — the original failure was the model reporting a cached `uptime: 91 s` as a current measurement, so labelling only the database would have left it intact.
- ⚠️ **Rows written before 2026-07-28 carry neither field.** Existing history is still unreplayable, so item 6 needs a fresh reproduction rather than a re-read.
- ✅ **Both verified live on run 42889f7b, 2026-07-28** — the first post-fix run. `tool_events` carries `cached: true` / `cached_at` / `cache_age_seconds: 77`, and the document tool carries `full_command` with the full 3,024-character document. **Item 10's payoff was immediate: that document could be audited against its source, which was impossible for the run this item was filed from.** Item 17 reached the model too — the document body says *"cached ~77 seconds ago"*, quoting the notice. ⚠️ **But it titled itself "(Live Fetch)" anyway**, contradicting its own body three lines down: the label is delivered and half-believed, which is progress and not a fix.
- **Effort was filed as M and was one line plus a cap** — the data was already computed and already streamed; only the persistence dict dropped it. The estimate was stale because nobody had re-read the code since filing.

## Five tests failed on macOS only — fixed 2026-07-28 (item 19)
The suite had never been green on the dev machine: `7 failed, 5415 passed`. **None was an application bug.** Commit `c6b9af3`. ✅ **Verified on the M1 the same day: `2 failed, 5433 passed, 4 skipped` in 104 s** — item 18 only. The count reconciles exactly (5415 + 5 fixed + 13 new tests from items 10/17), so nothing else shifted under the fix.

- **`AF_UNIX path too long` (4 tests).** macOS caps `sun_path` at **104 bytes** (Linux 108) and hands out a deep `$TMPDIR`, so a socket under pytest's `tmp_path` was 126 bytes; the same path under Linux `/tmp` is 74 and fits. Shared helper `tests/helpers/unix_socket.py` binds under a short root and asserts its own length.
- **`test_glob_confined_e2e`: the assertion contradicted a comment three lines above it**, which correctly said the not-found message echoes the caller's own pattern. `tempfile.mkdtemp()` returns an unresolved `/var/…` path while the workspace is compared as `realpath` (`/private/var/…`), and `os.path.relpath` is lexical — so it ascended to `/` and descended through the **absolute** path, embedding the secret in the very pattern the test then asserts is absent. Fixed by resolving the temp root. **No confinement hole:** glob refused correctly every time.
- **A guard that passes in the failing case is not a guard.** The first attempt used `not os.path.isabs(rel)` — worthless, because the leaking path is a *traversal*, not an absolute path, so `isabs` was `False` in both the broken and fixed cases.
- **Reproduced before fixing, not reasoned about:** setting `TMPDIR` to a 60-byte path reproduced the identical `OSError` on Linux. The symlink half could not be — it needs a root-level symlink — so it was verified by running `relpath` over the exact strings from the failing run.
- ⚠️ **`-m area_security` reported `654 passed` clean while four docker-socket privilege-gate tests were failing.** The taxonomy keys off *filenames*, so `test_shell_routes.py` lands in `area_routes`. **An area marker says what a file is called, not what it protects** — don't use the security lane as a pre-commit gate on its own.
- **A permanently-red suite is its own hazard:** seven expected failures on every run trains you to skim the summary, and that is how the eighth gets through.

## Upstream rewrote history; our work was rebased, not merged — 2026-07-28
`git status` said "behind by 4 commits, can be fast-forwarded" and that was **false** — it describes the *cached* `origin/dev` ref, which nobody had refreshed. A `git fetch` changed the answer completely:

- `df2fad2`, the base everything here was built on, is **no longer reachable from `origin/dev`**. Upstream force-pushed a rewritten history.
- The real common ancestor is `71d74290`, **1 June** — not 4 commits back, but 1939 upstream / 1916 local.
- Of those 1916, only **13 were ours.** The other 1903 were upstream's own commits, re-authored.

**`git merge origin/dev` would have been wrong** — it would try to reconcile two near-identical-but-rewritten histories. The right operation was `git rebase --onto origin/dev df2fad2 dev`: replay only the 13 commits we actually wrote, discard the rest.

- **Rehearsed in a throwaway worktree first**, so the conflict count was known (4 hunks, 2 files) before the real branch was touched. A tag `pre-rebase-2026-07-28` marks the old tip; `git reset --hard pre-rebase-2026-07-28` restores it.
- **Two of the four conflicts were upstream having independently fixed the same class of bug.** They ungated the `manage_notes` reporting block from `_ody_notes_finetune_mode` — exactly the split-gate change made here for documents — and added `_response_before_tool_summary`, which their later code reads. Resolution kept *their* ungated form and dropped ours; ours was the superseded shape.
- **Our two headline fixes were NOT upstream** (`doc_update_emitted`, `_userDirtyDocId`, and the whole two-tier SSRF guard: 0 occurrences on `origin/dev`), so all 13 commits were still worth moving.
- ⚠️ **The rebase surfaced a real gap the conflict resolution could not have caught.** `test_no_silent_save_is_left_unlabelled` failed afterwards: upstream had added a **new** silent-save call site in `ensureEmailDraftEnvelope` that our labelling pass predates. Labelled `Autosave (email envelope)`. **A source-text guard is what turns "their new code" into a visible failure instead of a silent hole** — the same value the write labels themselves have.
- **Every commit hash in these docs changed.** 19 references were remapped by matching commit subjects old→new. **Cite by `origin/dev..HEAD` rather than by a base hash from now on** — a base hash is exactly what a rewrite invalidates.

## Sixteen days of uncommitted work — committed 2026-07-28
Was item 5. Seven commits, `b700632`…`ae4fa58`, 47 files, identity set repo-locally, nothing pushed.

- **The item's own bookkeeping was the risk.** "44 files, staged" described 2026-07-19 and was never revised, so the whole 2026-07-27 session sat *unstaged* — outside the only protection the item claimed. **A count written in prose is a claim with an expiry date and no test.**
- **`COMMIT_PLAN.sh` named no `git add` for three staged test files**, and opens with `git reset -q`, so they would have emerged untracked — the staged-but-never-committed trap described at the end of this entry, applied to the entire evidence base for items 7 and 8. The script now ends with a coverage check naming anything staged at start and missing from the new commits. **This class of error is invisible to review and trivial to detect mechanically.**
- **Rehearsed against a copy of `.git` before running.** `bash -n` had passed on the version that silently dropped three files: **knowing a script parses is not knowing it runs.**
- **A zero-byte `.git/index.lock` blocks every git operation, silently.** The 2026-07-18 instance ran 13 hours and is the likely reason two weeks went uncommitted. Check `ls .git/index.lock` before believing git is broken.

**Recovering the two files deleted as superseded** — both staged-but-never-committed, which is the fragile state:

- `llmSetup.md`: `git cat-file -p 93bdbbb7 > docs/llmSetup.md`. Its worktree copy differed from its staged blob (`746a08ef`), so `hash-object -w` was run first. It survived only as a redirect for source citations and **its stated exit condition undercounted them by two** — delete a redirect by grepping, not by trusting the count inside it.
- `KNOWN_ISSUES_debug.md`: `git cat-file -p b570b679 > KNOWN_ISSUES_debug.md`. The obvious commands fail — it was renamed with `git mv` before deletion, so `git show :path` returns nothing and `git fsck --lost-found` misses it too.
- **General trap: for a staged-but-never-committed file, renaming or re-staging invalidates every path-based recovery route.** `hash-object -w` first, and write the hash down.

## web_fetch could not reach the LAN — fixed 2026-07-27. Two SSRF policies in one repo, and a guard whose tests tested nothing.
`web_fetch` refused every RFC-1918 and loopback target, so reaching an ESP32 on the LAN was never possible. Commit `9f52bc3`.

- **The repo held two contradicting policies.** `src/url_safety.py` (embeddings, webhooks, ntfy) is deliberately local-first; `services/search/content.py` — the only path `web_fetch` uses — was a hard lockdown with no knob. Same product, opposite defaults, no note anywhere.
- **Fix:** two-tier classification. *Hard* (no override): link-local incl. `169.254.169.254`, multicast, reserved, unspecified, `0.0.0.0/8`, metadata hostnames. *Gated* behind `WEB_FETCH_BLOCK_PRIVATE_IPS` (**default `true`**): loopback, RFC-1918, ULA, `.local`/`.lan`/`.internal`/`.intranet`.
- **The opt-in applies to the first hop only.** Letting it ride along would let a public page 302 into RFC-1918 space — a textbook SSRF chain.
- ⚠️ **Trap worth keeping: Python reports IPv6 `::1` as `is_reserved`.** Tiered naively, the v6 loopback lands in the hard tier while `127.0.0.1` sits in the gated one — same host, two answers depending on which literal was typed. Gated ranges win where the tiers overlap.
- **`_public_http_url()` had no production callers and three test files asserted against it.** The file whose entire purpose is URL guards tested 3 of 3 cases against the orphan, and the live guard had zero coverage for weeks — **a green suite asserting a security property nothing enforced.** Now a thin wrapper so the two cannot diverge. Audit open as [todo.md](todo.md) #16.
- **Lesson:** the symptom said "localhost is blocked", which sounds like a dev-environment quirk. It was a product-wide policy contradiction, and the naive reading would have shipped a whitelist for `127.0.0.1` that still couldn't talk to the hardware.

## Autosave reverting AI edits — fixed 2026-07-19. It was a duplicated SSE event, not autosave and not the CAS.
**Third write-up of this symptom and the first to find the mechanism.** A single document tool call emitted `doc_update` **twice**; the second delivery re-entered `handleDocUpdate`, hit the #2484 guard, and `exitDiffMode(true)` restored the pre-edit buffer and PUT it back under a now-fresh `base_version` — so every destructive write passed the compare-and-swap *legitimately*. Fixed in three layers (event dedupe, non-persisting AI-driven teardown, `_userDirtyDocId` required for the 409 retry). Commit `5d00e49`.

- **Verified live, unlike the two previous closures:** every client write in `app.db` classified as REVERT (byte-identical to an earlier version) or BLEND (matching none). **Pre-fix 20 reverts across 10 documents; post-fix 0**, over five sessions including a 154-line edit — the largest in the dataset and exactly the shape that used to revert every time.
- **Keep the REVERT/BLEND split as a standing check.** Two different bugs with two different causes, distinguishable in one query.
- ⚠️ **The CAS is correct and was never the bug.** It is still the only lost-update guard and must stay; the source comments that used to call it the fix have been corrected.
- **Two lessons the earlier write-ups paid for:**
  - **The symptom named the wrong subsystem for three rounds.** "Autosave is reverting edits" put every investigation inside the save path, which was correct throughout.
  - **A guard that *writes* is not a guard.** The 2026-06-07 fix for #2484 was itself the weapon: tearing down state and persisting state are different operations, and it conflated them.

## Diff review corrupted documents — fixed 2026-07-19. The editor manufactured item 3.
The diff-review overlay wrote documents containing **both** the pre-edit and post-edit text for the same section — twelve such regions from a *single* Accept click. Cause: an un-reviewed chunk was treated as rejected, and `_resolveChunk` persisted that reading on every click. Commit `5d00e49`.

- **This is the mechanical cause of [todo.md](todo.md) item 3 in at least some runs.** "Documents contradict themselves" was filed against the model; here the model had already flagged the document as inconsistent and the editor then made it materially worse. **How much of item 3 is the model is now an open measurement, not a known quantity.**
- **Rule:** revert a chunk only on an *explicit* rejection, and never persist a partial review. Both are standard — Monaco pairs a replacement as one mapping rather than two independent chunks, and VS Code's merge editor requires all conflicts resolved before completing. This code violated both.
- **Trade accepted:** an in-progress review is lost on refresh. That was the stated reason for saving on every click; it is the correct trade and matches VS Code.
- **Not observed live.** The next review turn should produce either no `user` row or one labelled `Diff review — applied`.

## Empty document writes destroyed a document — fixed 2026-07-19. Found by causing it.
A retry nudge telling the model to "finish the job NOW" produced `update_document` with **empty content**, wiping a 6186-character document to zero bytes: five zero-length versions in four minutes against none in the preceding 79. The nudge was reverted; the latent bug it exposed is the more valuable find — `update_document`/`create_document` accepted empty content, so *any* empty call from any cause destroyed a document. All three tools now refuse it. Commit `5d00e49`.

- **Telling an idle model to act is not telling it what to do.** With nothing to write, "act now" resolved to the most destructive available call.
- **A guard that makes the model *act* must have tests that bound what it can do, not merely assert it exists.** The tests written for the reverted nudge would have passed no matter how destructive it was. See [todo.md](todo.md) item 8 before retrying.

## Turns that did work and reported none of it — fixed 2026-07-19 (items 7 + 8)
One wrong assumption behind two guards: **a non-empty `full_response` was taken to mean the model had said something meaningful.** It doesn't — this model opens with its intent before calling any tool, and that preamble made every end-of-turn check pass. A turn applying 4 edits reported none of them; told nothing had happened, the user asked again 16 seconds later and the repeat turn spent 162s producing nothing. Commit `5d00e49`.

- **Detection is positional, not keyword-based:** text written *before* the tool ran cannot describe what the tool did. Prose is snapshotted before every tool block, not just document ones.
- Counts accumulate across rounds — a turn with several edit rounds once reported only the last, understating 10 edits as 1.
- **✅ Failure branch verified live 2026-07-27**; the accumulation path is still tests-only. Recorded at that scope deliberately.

## The "Done." turns — diagnosed and fixed 2026-07-18. It was never a parser bug.
Turns that did real work returned `content="Done."`. **Two mechanisms were recorded here as findings before either was checked against the code; both are retracted:**

1. ~~"thinking on → collapse"~~ — fit the first four runs perfectly, then broke on the next pair. Thinking was ON for every row; it was never the variable.
2. ~~"the reasoning parser eats the answer / investigate `<think>` handling on the `/v1` stream path"~~ — sent debugging in entirely the wrong direction. **This retraction is load-bearing: it stopped a third trip down that road on 2026-07-27.**

**Actual cause:** the doc-finetune path breaks the agent loop the instant a document tool succeeds, so the model never gets a round to write its closing summary. `"Done."` was a deliberate placeholder. It *looked* like misrouting because the round's reasoning naturally reads like a summary — the prose was never generated at all.

- **⚠️ Then the fix turned out to be gated off for `qwen3.5:9b-32k`** — a third wrong turn on the same bug. The diagnosis is correct *for the Odysseus finetune*; on the current model the code never ran. See the split-gate entry below.
- **Lesson:** the correlation in the first hypothesis was real and perfect across four runs, and still wrong. **Check the code path before recording a mechanism.**

## The document reporting path was dead code on the current model — split gate, 2026-07-18
`_doc_tool_summary()` and the stale-value warning sat behind a gate requiring `model.startswith("odysseus-qwen3")`. `qwen3.5:9b-32k` doesn't match, so both were unreachable on the model actually in use — the "Done." fix had never once run here. Commit `5d00e49`.

- **Split, not widened.** The same flag also narrows tools to five and re-enables the loop break, which would kill the unprompted `create_document` → `edit_document` self-correction. **That behaviour exists *because* the break is inert.** Reporting is safe for every model; breaking the loop is not.
- Also closed the surfacing gap on `find_stale_values()` — the lint was already model-agnostic but rendered through the gated summary, so its findings only ever reached the logs.
- Tests pin the *structure* by AST, and were checked against a synthetic re-merged gate so they aren't vacuous.
- **✅ Verified live 2026-07-19**, byte-identical to the synthesized summary on a turn where the model wrote nothing.

## `edit_document` silently received nothing — fixed 2026-07-18. Three recorded diagnoses, two of them wrong.
526 seconds, document never touched, no error surfaced. **Two mechanisms recorded before the code was checked; both retracted:**

1. ~~"The model emits malformed FIND blocks"~~ — written from the error *string* alone. The tool received nothing at all.
2. ~~"The model emitted a bare fence header, thinking having burned the output budget"~~ — written from the stored `command: ""` field without checking how that field is populated. `command` is a first-line preview, not the argument; a successful 5-edit call stored `"<<<FIND>>>"` too. The budget claim was also wrong: 1440 output tokens against `max_tokens=4096` per round.

**Actual cause:** a structured call with a misshaped argument, silently converted to an empty string — the `edit_document` branch coerced anything non-list to `[]` and dispatched `content=""`. Now `_coerce_edit_items()` accepts the shapes models actually emit, fallbacks only run when the dedicated key yielded nothing, and "received nothing" is reported separately from "markers are wrong". Commit `5d00e49`.

- **Sharing one error message is what let a converter bug read as a model syntax error for a whole debugging round.**
- **Organic runs cannot test failure paths** — after the fix, broken shapes are rare, so the end-to-end test injects one by driving the real loop with a scripted model stream. Waiting for a real failure to recur is not a test strategy.
- **Lesson, third time in this bug family:** a mechanism from a symptom string, then another from a metadata field, neither checked against the code that produces them. **Check the *writer* of the evidence, not just the evidence.**

## "Done." on read-only turns — the document fix didn't generalise, 2026-07-19
The bug was recorded fixed twice above; both fixes keyed off *document* tools, so every non-document turn kept falling through. Four consecutive runs produced no file at all. Now `_gathering_only_notice()` reports what ran and states plainly that nothing was created or changed. Commit `5d00e49`.

- **Only for an explicit `READ_ONLY_TOOLS` allowlist.** Guessing an unknown MCP tool is read-only could tell a user their email wasn't sent when it was — worse than the bug.
- **Placement mattered and the first attempt got it wrong:** the guard ran before `strip_tool_blocks`, so the leftover tool fence made the turn look like it produced text. Caught by the end-to-end test, not the unit tests.
- **Lesson:** "fixed" was written down after one happy-path run on one tool path, while the same failure was live on another path the whole time. **Record the scope a fix was verified at.**

## Editor autosave silently reverting AI document edits — fixed 2026-07-18, REGRESSED, superseded 2026-07-19
Kept only for the lesson. The first fix added `base_version` + a 409; the race reappeared the same day because the check compared against a `version_count` read at the top of the handler, so an AI edit committing between read and write validated cleanly and then clobbered. Replaced with a true compare-and-swap. **Then it regressed again** — and the real cause turned out to be the duplicated `doc_update` event, not this path at all. See *"Autosave reverting AI edits"* above.

- **"Fixed" was recorded here twice from a single happy-path run, both times wrongly.** This entry is why [todo.md](todo.md) tracks *Verified* separately from *Fixed*.
- **Check-then-write was never atomic.** The first fix narrowed the window from ~60 ms to same-second and read as a success.

## Active-doc turns losing edit tools on low-signal input — fixed 2026-07-18
"yes and include sources" classified `low_signal=True, domains=[]`, went down the RAG path without `edit_document`/`update_document`, and the model created a duplicate document. `_vague_turn_keeps_active_document()` now keeps document tools on a vague or continuation turn mid-conversation with a document open. Was `knownIssues #3`. Commit `5d00e49`.

- **✅ Verified live** — and more strongly than intended: one run had the classifier still misfiring entirely, and the document tools were force-included anyway. **The guard holds even when intent classification is wrong.**
- **Important reclassification:** the 4B in the same test had all 25 tools on all 6 rounds and *still* never called one, writing a 5,978-char essay describing corrections it never applied. That failure had been blamed on tool stripping; it is model capability, and it is what retired the 4B.

## 4B retired — 2026-07-18
Six same-task runs, documents fact-checked against cultivation sources rather than scored on whether the tool chain completed.

**Ground truth — this is a fixture, not a narrative. Item 2b's checker is built from it:** colonization **24–29 °C**, fruiting **20–30 °C** (tropical, **no cold shock**), RH **85–95 %**, CO₂ **500–800 ppm** at 3–6 air changes/hour.

| Model | Thinking | Document |
|---|---|---|
| 4b | off | worst — invented a 22-day "storage phase", harvest pushed to day 46–50 against its own 3–4 week overview |
| 4b | **on** | bad — fruiting 16–20 °C (the *P. ostreatus* cold-shock rule applied to a tropical species); CO₂ 1000–1500 ppm through fruiting, backwards |
| 9b | off | good — dodged the CO₂ trap mainly by not specifying CO₂ |
| 9b | **on** | **best — correct on every parameter checked, and the only one with sources** |

- **The 4B's failure mode is the dangerous kind:** specific, confident, plausible numbers aimed straight at chamber setpoints. Not a speed/quality trade — a correctness floor it doesn't clear.
- **The fact-check step is not trustworthy, and this outlived the 4B.** Every run "corrected" toward a *different* temperature and **none caught the CO₂ error**, the most consequential mistake in the set. It reads as thorough — tables, ✅/⚠️ markers, citations — while not converging on truth. **Treat an agent fact-check as a prompt to go look, never as a verdict.** Open as [todo.md](todo.md) item 2b.
- Search quality contributes: a Victoria's Secret "PINK" page ranked into mushroom searches and nothing noticed. Open as item 14.

## Research path moved off the retired 4B — 2026-07-19
`research_model` was still `qwen3.5:4b-16k` after the 4B was retired as chat model — and research output feeds documents, so it kept doing exactly the damage that retired it. Now `qwen3.5:9b-32k`.

- ⚠️ **"Or blank it to inherit the default" was wrong, and matters for `task_model`/`utility_model` too.** `resolve_endpoint()` keys its fallback on the **endpoint id**, not the model: a blank model with the endpoint id set reaches `_first_chat_model(enabled models)` and picks whatever the endpoint lists first; with the id unset it takes `utility_model` — here *smaller* than the 4B. **Blanking is non-deterministic at best and a downgrade at worst. Set it explicitly.**

## Thinking suppression for agent rounds — 2026-07-17
**Key finding, which cost two failed attempts: Ollama's `/v1` OpenAI-compat endpoint silently ignores the native `think` param.** The working control is `reasoning_effort: "none"`. Odysseus streams via `/v1`, so suppression had never actually fired, and the old code comment claiming otherwise was wrong. Gated behind `agent_disable_thinking`; chat rounds always keep thinking. Commit `12a76ea`.

- Currently **off** — thinking stays ON for the 9B. The toggle is an escape hatch.
- **Token note, a recurring misconception: no-think does NOT use fewer prompt tokens.** Per-round growth is web_search results (~3k/search) plus the document echoing back through the replayed tool call. On fact-check turns input reaches 76–89k tokens — **the fetches, not the reasoning, are what fills the window.**

## Context-window mismatch — 2026-07-16
The app assumed `131072` while the `-16k`/`-32k` Ollama variants serve what their name says, so trimming budgeted against a window up to 8× too large and Ollama silently truncated the prompt top — **system prompt and skills die first**. A `-16k`/`-32k` name suffix now declares the window; live endpoint reports still win. **Takes effect only after a restart.** Commit `12a76ea`.

## Tooling that still exists — 2026-07-19
- **`tests/tools/diff_model.py`** — Python port of the editor's diff engine, so diff/merge behaviour can be replayed and property-tested offline with no browser.
- **`tests/tools/replay_blend_rows.py`** — replays recorded `document_versions` rows against that model, searching for operation sequences that reproduce a corrupted row byte-exact. Re-runnable against any `app.db` copy.
- **Write labels.** Every client-side document write records which path produced it (`Autosave`, `Diff review — applied`, …). **Highest value-per-line change of that day** — it identified the diff-review corruption in one query after a replay harness had failed to pin it.

## Skill pipeline rollback — 2026-07-17
The experimental component-lookup / reference-creation skill pipeline was rolled back — both split skills, the combined lookup skill, and the `src/agent_loop.py` patches (skill tool-union, step-1 supervisor, ask-gate, pending-ask continuation flag) with their tests. The general Skills facts in [qwensetup.md](qwensetup.md) still hold; that enforcement machinery is no longer in the tree.

## Agent preset max_tokens — 2026-07-16
Set to 6400.
