# Open items — Qwen 9B setup

**How to work on this — [`CLAUDE.md`](../CLAUDE.md) at the repo root.** Evidence rules, guard rules, what to distrust in *this* file, and the traps that recur. Added 2026-07-28 because the drift described at the bottom is structural and the docs alone were not fixing it.

Setup and config: [qwensetup.md](qwensetup.md). Closed investigations: [resolvedissues.md](resolvedissues.md). Settled constraints that are *not* work items are at the bottom.

**Severity is ranked by what the failure does to the user**, not by how broken the code looks:

| | Severity | Meaning |
|---|---|---|
| **S1** | Critical | Produces wrong output the user trusts and acts on |
| **S2** | High | Loses work or content, silently |
| **S3** | Medium | Task visibly fails — wasted time, but the user knows |
| **S4** | Low | Friction, noise, or blocked diagnosis |

**"Verified" is tracked separately from "fixed"**, because this file has twice recorded a fix from a single happy-path run and been wrong. *Live* means observed working in a real run and confirmed in `app.db`; *tests* means source-level or unit coverage only.

| # | Item | Sev | Effort | Status | Verified |
|---|---|---|---|---|---|
| 1 | ~~Autosave reverting AI edits — data loss~~ | S1 | M | ✅ fixed | **live** — 20 reverts → 0 |
| 2a | ~~Document doesn't match its source~~ | S1 | S | ✅ built 2026-07-28 — report-only | **tests (27)** — needs a live turn |
| 2b | ~~Fact-check inverts ground truth~~ | S1 | M | ✅ built 2026-07-28 — report-only | **live** — fb5525eb |
| 3 | Documents contradict themselves | S1 | M | detection live; **prevention open** | **live** (lint) |
| 4 | ~~Retired 4B still on the research path~~ | S1 | XS | ✅ done | live |
| 5 | ~~Uncommitted work — since 2026-07-12~~ | S2 | XS | ✅ committed 2026-07-28 | **live** |
| 6 | ~~Answer text lost to the reasoning channel~~ | S2 | S | ✅ fixed 2026-07-28 — a save-path regex | **tests (15)** |
| 7 | ~~Closing summary under-reports / stays silent~~ | S3 | S | ✅ fixed | **live — both branches** |
| 8 | Agent gathers information, then stops | S3 | M | reporting fixed; **active half reverted** | **live** / tests (zero-tool) |
| 9 | ~~Throughput cliff: 2.84 → 0.39 tok/s~~ | — | — | ⊘ **retired — disproved by its own data** | n/a |
| 9b | Streams fail mid-turn; timeout caps document length | S3 | S | reporting ✅; **timeout raised 300→900, unverified** | **live** (notice, bbde3e51) |
| 10 | ~~Failures aren't replayable~~ | S4 | XS | ✅ fixed 2026-07-28 — `full_command` | **live** — 42889f7b |
| 11 | ~~Non-document tools have no closing report~~ | S3 | M | ✅ built 2026-07-28 — report-only | **tests (20)** — needs a live turn |
| 12 | Wasted verification rounds | S4 | XS | open — **re-measure first, see item 20** | — |
| 13 | Terminal access-log noise | S4 | S | open — got in the way twice | — |
| 14 | Web search derails on ambiguous common nouns | S3 | M | open — recurring | — |
| 15 | ~~`web_fetch` failure rate on cultivation sources~~ | — | — | ⊘ **folded into 2 — premise already answered** | n/a |
| 16 | SSRF guard tests covered an orphaned function | S4 | S | one instance fixed; **audit open** | tests |
| 17 | ~~Cache hits indistinguishable from live fetches~~ | S4 | XS | ✅ fixed 2026-07-28 | **live** — 42889f7b |
| 18 | Two CAS tests have never passed | S4 | S | open — found 2026-07-28 | n/a |
| 19 | ~~Five tests failed on macOS only~~ | S4 | XS | ✅ fixed 2026-07-28 | **live** — M1 suite |
| 20 | 116 lines of agent rules never reached a model | S3 | S | open — **found 2026-07-28** | tests |
| 21 | ~~Three S1 warnings suppressed when the model wrote a summary~~ | S1 | XS | ✅ **fixed 2026-07-28** | tests (13) |
| 22 | Documents never stream into the editor on this setup | ? | ? | open — **found 2026-07-28**, severity unestablished | n/a |

**Numbers are never reused.** A retired item keeps its number and a `⊘` row, because renumbering has silently rotted cross-references four times (see *Notes & constraints*). Item 2 split into 2a/2b, and 9 into 9/9b, rather than taking new numbers, for the same reason.

> **Next, in order.** Ordering follows leverage, not severity.
>
> 0. **Measure rule adherence properly — five same-prompt runs with a document open.** First reading is **1 of 3** (item 20). This one number decides several other items: whether item 20's remaining rules are worth reviving, whether item 8's active half is needed at all, and whether item 12 is a model problem or was only ever a missing-rule problem. **Cheapest experiment on the list and it re-scopes three items either way.**
> 1. **One live turn for 2a**, the last S1 still at *tests*. Ask for the ESP32 document and read the closing summary for *"Doesn't match the source"*.
>    ⚠️ **Close the open document in the editor first.** fd0f9ba0 asked three times and got nothing: the model read the open document from context and reasoned "one already exists, I should not duplicate". The document doing the suppressing was `3e99b6e3` from 2026-07-19, which 2b flags four times over. fb5525eb created one on the first try with the editor clear — consistent, but one run and not a controlled comparison.
> 2. **Item 3's prevention gap** — `find_stale_values` has exactly one production caller, `document_tools.py:765`, inside `EditDocumentTool`; `update_document` bypasses the lint entirely *(re-verified 2026-07-28)*. Note the interaction: item 7's live guard promises *"I'll rewrite the document in full instead of patching"*, which routes every edit failure into the one path with no lint.
> 3. **Item 16's audit** — four independent `_PRIVATE_NETWORKS` copies, all still present *(re-verified 2026-07-28)*. The one open item where a green suite asserts a security property nothing enforces.
> 4. **Item 13** — friction, but it has obstructed debugging twice. ⚠️ *Two of the three cited call sites re-verified 2026-07-28; `start-macos.sh:292` is now a bare `uvicorn` CLI invocation with no log flag, which is a different fix shape from a `logging.Filter` on a `uvicorn.run` kwarg.*
>
> **Item 11 came off this list on 2026-07-28** — built, report-only, tests (20), still owed a live turn.
>
> **Suite: last measured `2 failed, 5588 passed` on the M1** — item 18 only, both pre-existing. ⚠️ **Unmeasured since.** Additions: 2a +27, item 6 +15, 2b +34, items 8/9b +20, item 20 +12, item 21 +13, item 11 +20. Next run should read **5729 passed, 2 failed**. **That is a prediction, not a measurement**, and this file has been wrong about exactly this before — a sandboxed `--collect-only` on 2026-07-28 counted **5,688 + 20 new = 5,708 items**, about twenty short of it, which is a discrepancy to explain rather than a number to trust (collection is not passes, and that run was not the M1 venv). Item 8's active half stays parked — read its ❌ bullet first.

---

## S1 — wrong output the user trusts

### 1. ~~Autosave is reverting AI edits~~ ✅ fixed, verified live 2026-07-19
Not autosave and not the compare-and-swap — a single tool call emitted `doc_update` **twice**, and the second delivery made the diff-mode guard restore and persist the pre-edit buffer. **20 reverts pre-fix → 0 post-fix.** [resolvedissues.md](resolvedissues.md), *"Autosave reverting AI edits"*.

### 2. Wrong numbers in documents the user trusts
*Split 2026-07-28: 2a is "the document disagrees with the data it was handed", 2b is "the document disagrees with reality". Both are built and report-only. They looked like one item and share only a severity.*

#### 2a. ~~Document doesn't match its source~~ ✅ built 2026-07-28
`src/document_fidelity.py`, surfaced in the closing summary, silent unless the turn fetched a JSON source. Design argument and the two bugs the tests caught: [resolvedissues.md](resolvedissues.md), *"The document didn't match its source"*.

- ⚠️ **Tests only — the last S1 not seen live.** Ask for the ESP32 document and the closing summary should carry the warning.
- **The finding that shaped it:** across two runs **239 of 240 cells were transcribed correctly and both documents were still wrong.** Filed as transcription; transcription was the incidental half. **A source-to-document diff cannot catch a correct value under the wrong field.**
- ⚠️ `config/field_semantics.json` describes **one device**. It is a fixture, not config: every entry should come from an observed failure, and an empty one silently checks nothing.

#### 2b. ~~The fact-check step inverts ground truth~~ ✅ built 2026-07-28
`src/known_facts.py` against `config/known_facts.json`, beside 2a's `fidelity` and item 3's `stale_values`. Diagnosis, the design argument and the five false-positive classes the corpus caught: [resolvedissues.md](resolvedissues.md), *"The document contradicted what we had already established"*.

- ✅ **Live on run fb5525eb, 2026-07-28**, first turn after the restart — the model reproduced the cold-shock error on a freshly created document and **it was caught as it happened** rather than nine days later from `app.db`. Fired again on the *corrected* document in turn 3, which is why it is report-only and not a gate.
- ⚠️ **That verification covers one branch of two.** On `fb5525eb` the model wrote nothing after the tool, which is the path that always worked. On a turn where it *does* summarise its own work the warning was discarded entirely until item 21 was fixed later the same day — run eb2d0ac1 lost a prescribed cold shock that way. **Re-verify on a summarising turn.**
- ⚠️ `config/known_facts.json` describes **one species**, from one investigation. Same fixture warning as `field_semantics.json`.
- **It catches a class nobody designed it for: unit confusion.** Run bbde3e51 turn 5 wrote *"21-29°C for fruiting; can tolerate up to ~30**°F**"* — °F where °C was meant. The range check flagged `30°F` because it converts before comparing. Worth knowing when judging the fixture's value: two of its live catches so far are the cold-shock instruction it was built for, and a typo it was not.
- **Ground truth** — colonization 24–29 °C, fruiting 20–30 °C **no cold shock**, RH 85–95 %, CO₂ 500–800 ppm at 3–6 ACH — is recorded in [resolvedissues.md](resolvedissues.md) (*"4B retired"*) and pinned by `test_the_ground_truth_matches_what_resolvedissues_records`, so editing the fixture is a deliberate act.
- ⚠️ **Keep this, it is the reason the checker exists and it is counter-intuitive:** asking for verification made documents *worse*. Plain "create a document" scored closest to correct; "create with fact checked infos" plus four source fetches scored worst, at fruiting 14–21 °C — the *P. ostreatus* range on a tropical species. **The retrieval step is not neutral; it drags the answer toward the wrong species**, and item 14 is part of why. Do not "fix" 2b by searching harder.

### 21. ~~Three S1 warnings were suppressed whenever the model wrote its own summary~~ ✅ fixed 2026-07-28
`_closing_doc_summary` returned early on `if existing and not preamble_only`, discarding the **whole** of `_doc_tool_summary` — which carries item 3's `stale_values`, 2a's `fidelity` and 2b's `known_facts`. The finetune-break path had the same gate. The reasoning was sound and the conclusion was wrong: **the user had been told what happened, but not that it was wrong.**

**Run eb2d0ac1, 2026-07-28.** The model researched, fetched two sources and created an 8,636-character document titled *"…Growth Phases Guide - **Fact Checked** 2026-07-28"*, containing *"Temperature drop of 5 – 10°F"* — a prescribed cold shock on a thermophilic species, the exact failure that retired the 4B. **2b caught it.** The model then wrote a confident summary with ✅ ticks, so the warning was dropped and the user saw neither finding.

- **The net was withheld because the model sounded sure**, which is the one case it exists for. **Inverse of the `"Done."` bug**: that reported success for work that never happened; this reported success for work that happened wrongly.
- **Fix:** `_doc_tool_summary(info, warnings_only=True)` returns the ⚠️ blocks without the *"Created/Updated …"* action line, and both call sites append it instead of returning. The model keeps its own words; the action line is not duplicated. Tests: `tests/test_doc_warnings_survive_model_prose.py`, including a byte-exact pin that the default rendering did not change.
- ⚠️ **This invalidates part of 2a's and 2b's verification scope.** Both were recorded live on `fb5525eb`, where the model wrote *nothing* after the tool (`round_texts=[0, 0]`) — the branch that always worked. **Neither has been seen live on the branch that was broken.** Re-verify by asking for a document on a turn where the model summarises its own work.
- **Found by reading runs, not by testing.** Every wiring test asserted the findings reach `_doc_tool_summary`; none asserted `_doc_tool_summary` reaches the user. **A test that stops one call short of the user is the item 16 shape** — it pins the plumbing and not the delivery.

### 3. Partial edits leave documents contradicting themselves
Run 127d32b0: 8 edits fixed the prose and missed the summary table, leaving four CO₂ thresholds and three colonization durations in one document.

> **Partly re-diagnosed 2026-07-19 — a share of this was the editor, not the model.** The diff-review overlay wrote documents containing **both** pre-edit and post-edit text for the same section; twelve such regions from a *single* Accept click. Fixed — [resolvedissues.md](resolvedissues.md), *"Diff review corrupted documents"*.

✅ **The lint fired live on fb5525eb turn 3, 2026-07-28:** *"⚠️ Still inconsistent — `90%` was corrected in one place but still appears elsewhere."* The same turn reported 4 of 11 edits not applied, so the document was left half-corrected **and said so**.

- **Detection exists** (`find_stale_values()`), surfacing fixed 2026-07-18. **Prevention doesn't** — the model is never asked to fix what the lint finds.
- **Gap:** the lint runs only inside `EditDocumentTool`. A full `update_document` rewrite bypasses it entirely.
- **How much is the model is an open measurement, not a known quantity** — the editor was manufacturing part of it.

### 4. ~~The retired 4B is still live on the research path~~ ✅ done 2026-07-19
`research_model` is now `qwen3.5:9b-32k`. [resolvedissues.md](resolvedissues.md), *"Research path moved off the retired 4B"* — which also records why blanking a model field is a downgrade, not an inherit.

## S2 — silent loss

### 5. ~~Everything since 2026-07-12 — uncommitted~~ ✅ committed 2026-07-28
Seven commits, 47 files, rebased onto the real `origin/dev`. Detail and the recovery commands for two deleted files: [resolvedissues.md](resolvedissues.md), *"Sixteen days of uncommitted work"* and *"Upstream rewrote history"*.

- ⚠️ **`data/app.db` is in no commit and never will be** — `data/` and `*.db` are gitignored, and it holds every run this file reasons about. **The `outputs/snapshots/*.tar.gz` is the only thing protecting the evidence base.** Committing protects the code; the tarball protects the findings.
- **Ignoring a file is not protecting it.** `git clean -fdx` deletes ignored files and nothing points at them — an ignored file is *less* safe than an untracked one, having lost the `??` line that would remind you it exists.

### 6. ~~Answer text can be lost to the reasoning channel~~ ✅ fixed 2026-07-28
**It was never the stream. It was a regex in the save path** — `_normalize_thinking` in `routes/chat_helpers.py` split by *position*, keeping the last line and moving the rest out of the message, on any answer opening with `"I need "`, `"The user "` and five similar phrases. Two instances in 65 recorded turns; one lost 675 of 705 characters. Full account: [resolvedissues.md](resolvedissues.md), *"The save path decided which half of the answer was thinking"*.

- ⚠️ **Item 8's evidence base needs re-reading because of this.** Run c7da3649 ended on *"Let me correct these issues:"* — a textbook dangling promise, **manufactured by the save path**. **Do not count a dangling-promise run as item 8 without comparing `round_texts` against the saved `content` first.**
- ~~"Confirming it needs the raw stream"~~ and ~~"item 10 unblocks this"~~ — **both wrong, retracted.** `round_texts` persisted the complete pre-split text all along; `full_command` is *tool arguments* and could not have helped. This item recorded itself blocked on item 10 three times. **Check what a field contains before filing a dependency on it.**
- ~~The 2026-07-27 frequency count~~ — **retracted, not evidence.** All-zero `round_texts` is 15 of 40 turns and appears on turns that ended fine; it is the base rate, not a signal.
- **The earlier `/v1` retraction stands and is unrelated.** That one is about `llm_core.py` *during* the stream; this is `routes/chat_helpers.py` *after* it. **Both are true at once**, and reading the retraction as "therefore nothing eats the answer" is what kept this open for nine days.

## S3 — visible task failure

### 7. ~~Closing summary under-reports, and sometimes says nothing~~ ✅ fixed — live end to end
Two defects: counts were replaced rather than accumulated (10 edits reported as 1), and the guard only fired on an *empty* response, which this model never produces because it opens with its intent. **Item 7's silence caused an item 8 failure.** Mechanism: [resolvedissues.md](resolvedissues.md), *"Turns that did work and reported none of it"*.

- ✅ **Failure branch live 2026-07-27** (31e0af64): *"I couldn't apply the edit — the document is unchanged."*
- ✅ **Accumulation branch live 2026-07-28** (fb5525eb turn 3): *"7 edits applied across 2 rounds, 4 not applied (the FIND text didn't match — those corrections are still missing)."* This was the item's last tests-only scope.

### 8. The agent gathers information, then stops
Four attempts at one task in 16 minutes, **zero files produced**. 0b12aadb read 10,035 chars, correctly identified the embedded HTML page, ended its thinking with *"Let me write out the extracted content:"* — and emitted nothing.

**Shares a root cause with item 7** — every guard tested `full_response` for emptiness, and a dangling promise is not empty. Item 7's silence also *caused* one instance here: told nothing had happened, the user asked again 16 seconds later and the repeat turn spent 162 s producing nothing.

- ✅ **Reporting half — live** (eb2d0ac1): *"I ran `web_search`, `web_fetch` and then stopped without producing an answer — nothing was created or changed."* Detection is positional, not keyword-based: prose is snapshotted before **every** tool block. Tests: `tests/test_dangling_promise_turn.py`.
- ✅ **The zero-tool hole, closed 2026-07-28.** fd0f9ba0 turn 3 promised a document, called nothing, and said nothing. **Neither guard was broken; both were out of range** — `_gathering_only_notice` returns `""` with no tools, and `_text_is_only_preamble` needs a tool boundary to be positional about. **This item's "verified live" was recorded from eb2d0ac1, which ran three tools; the scope written down was wider than the thing verified.** `_unstarted_promise_notice()` covers it, measured on all 67 recorded turns before shipping: 3 ran no tools, 5 end on a colon, exactly 1 does both. Tests: `tests/test_zero_tool_turn_reporting.py`.
- ❌ **The active half was tried and REVERTED the same day. Read this before retrying it.** A nudge told the model *"finish the job NOW using the appropriate tool."* Run 8c80cf8d called `update_document` with **empty content**, wiping a 6186-character document, then created two empty `Untitled` documents and emptied one twice — **five zero-length versions in four minutes, against none in the preceding 79.**
  - **Telling an idle model to act is not telling it what to do.** With nothing to write, "act now" resolved to the most destructive available call.
  - **A future attempt needs a narrower directive plus a guard proving the retry can only write content it actually holds.** Tests must assert the directive is *safe*, not merely that it exists — the ones written for the reverted version would have passed no matter how destructive it was.
- ⚠️ **The behaviour has never been observed with the rule against it in force.** *"YOU DECLARE WHEN THE JOB IS DONE … the only wrong moves are trailing off mid-task"* is a direct instruction against this, shadowed since 2026-06-09 (item 20). **Measure with a live rule before building anything in the loop** — that is the cheap experiment, and the reverted nudge is what the expensive one looks like.

### 9. ~~Throughput cliff on larger context~~ — retired, disproved by its own data
**Not a work item. Kept as a counter-example, because the obvious optimisation it invites is the wrong one.** Ordered by input size the numbers *rise*: 10,223 tok → 5.22 tok/s · 34,723 → 6.52 · 56,323 → **6.78**. Time-to-first-token does climb, but that is prompt ingestion, not generation, and **the two must not be conflated again**. Confirmed 2026-07-28: with TTFT subtracted, all twelve recorded turns run 8.9–13.6 tok/s. **Do not optimise for "less context" on this evidence.**

### 9b. Streams fail mid-turn, and the timeout is a document-length cap
`{"error": "Read timeout", "status": 504}`, logged as a WARNING and persisted nowhere, so the row read as *a slow turn*. Reporting fixed 2026-07-28 — `metrics["stream_errors"]` plus a user-facing notice. [resolvedissues.md](resolvedissues.md), *"A turn that failed read as a turn that was slow"*.

✅ **Reporting verified live on run bbde3e51, 2026-07-28**, three hours after shipping: *"⚠️ The request to the model failed after 375s — `Read timeout (504)`."* Before that day the same turn saved as `143 tokens, 0.38 tok/s` and nothing else.

**Mechanism, found 2026-07-28 — the timeout is not the disease.** `agent_stream_timeout_seconds` is a **per-read inactivity** timeout. **Ollama's `/v1` endpoint does not stream native tool-call arguments incrementally** — zero `tool_call_delta` events in 35,744 log lines — so the whole payload arrives in one chunk *after* the model has finished generating it. The inactivity timeout therefore functions as a hard cap on how long a single tool call may take to produce. At the measured 8.9–13.6 tok/s, 300 s capped a document at roughly 2,700 tokens.

| run | ttft | silence before the failure | outcome |
|---|---|---|---|
| fb5525eb | 63.8 s | **184.8 s** | ✅ 7,603-char document |
| bbde3e51 t1 | 70.1 s | **305.1 s** | ❌ 504 |
| fd0f9ba0 t3 | 66.5 s | **314.2 s** | ❌ 504 |

**Same prompt, opposite outcomes** — it is decided by how long the model chooses to make the document.

- ✅ **Raised 300 → 900 s on 2026-07-28**, in `data/settings.json` *and* the default in `src/settings.py`. ⚠️ **The saved file overrides the default**, so changing the code alone does nothing on a machine that already has the key.
- ⚠️ **This is an experiment, not a diagnosis.** If a turn still dies at 900 s the cause is a hang, not payload length, and the two want different fixes. **Do not close this until three same-prompt runs succeed.**
- ⚠️ **Raising it also scales the runaway wall-clock deadline** — `max(agent_stream_timeout * 4, 1200)` in `agent_loop.py` is now **3600 s per round**. Lower both together if that is too loose.
- **A second error class exists:** bbde3e51 turn 4 returned `All model candidates returned no substantive output (502)` at 69.8 s, on round 4 of a turn whose earlier rounds had written a document. Not a timeout. Unexplained.
- **Still open:** whether 0b12aadb (0.39 tok/s, 393 s) was the same 504. Its log window predates the check and nothing was persisted.
- ✅ **The failure notice no longer overstates the failure.** bbde3e51 turn 4 wrote v6 of a real document on rounds 1–3, then failed on round 4, and was told *"the turn did not finish, so treat it as incomplete"*. When `tool_events` is non-empty the notice now says work completed before the failure has been kept. **A failure notice that overstates the failure is still a false report** — the `"Done."` bug pointing the other way.

### 22. Documents have never streamed into the editor on this setup
`doc_stream_open` / `doc_stream_delta` exist to stream a document into the editor panel as the model generates it. **There are zero of either in 35,744 lines of `app.log`**, alongside zero `tool_call_delta` — Ollama's `/v1` endpoint delivers a native tool call as one chunk, so there is nothing to stream from. Found 2026-07-28 while diagnosing 9b, which has the same root cause.

- **Severity is unclear and that is the first question.** If the feature is meant to work here it is broken; if it only ever applied to the text-fence path (`_ody_doc_stream_create_mode`) or to API models, it is fine and the dead branch should say so. **Do not "fix" it before establishing which.**
- **It is not free.** The scanning code runs per delta on every round — `_doc_acc`, `_fence_markers`, the `"title"` regex — for an event that never arrives.
- Interacts with 9b: a user watching a document appear would at least *see* that a long generation was progressing. Right now a 300-second buffered tool call is indistinguishable from a hang, which is part of why 9b read as a throughput problem for three sessions.

### 14. Web search derails on ambiguous common nouns
Recurring, and **it feeds item 2b** — the wrong-species drift there is partly downstream of this. Run eb2d0ac1 returned **"Pink (singer) — Wikipedia"** as a top result for a pink-oyster cultivation query; an earlier run ranked a Victoria's Secret "PINK" page into the same searches. Nothing in the pipeline notices. The species name is in the document title and isn't being used.

- A prompt rule now tells the model to disambiguate common-word names in queries (2026-07-28, item 20). **That is not a fix** — it is unmeasured, and the ranking problem is upstream of the model.

### 20. A 116-line block of agent rules has never reached a model
`src/agent_loop.py` assigns **`_AGENT_RULES` twice** — the detailed block at ~660 and an 851-character "## Base rules" at ~776 — so Python keeps the second and the first is dead. `_API_AGENT_RULES` is shadowed the same way. The module imports, the suite is green, and the block reads as live to anyone grepping the file.

- **Item 16's shape, applied to the system prompt.** Not dead code that fails loudly — dead code that *looks* enforced.
- **Three items were arguing against rules that do not exist:** *"BIAS TOWARD ACTION … JUST DO IT"* (fd0f9ba0 refused to create, three times), *"AFTER A TOOL SUCCEEDS … no validation theater"* (item 12), *"YOU DECLARE WHEN THE JOB IS DONE"* (item 8).
- **Dated and confirmed on the M1:** written **2026-05-31** (`e5c99a5e`), shadowed **2026-06-09** (`ba9dc2fe`). The parent has one assignment and `ba9dc2fe` has two — **it introduced the shadowing rather than deleting anything**, which is why it reads as an addition in review. Live for nine days.

  ```
  git log -S'validation theater' --format='%h %ad %s' --date=short -- src/agent_loop.py
  git show ba9dc2fe~1:src/agent_loop.py | grep -c '^_AGENT_RULES = '   # 1, vs 2 at ba9dc2fe
  ```

- ⚠️ **Every item in this file was filed after the rules stopped applying** — the Qwen 9B work starts 2026-07-16. **Nobody has yet observed this model with the emphatic instructions in force**, so "prompt-level guidance doesn't work on the 9B" is currently unevidenced.
- ⚠️ **Do not read this as "no rules reach the model".** Weaker equivalents survive in the live "## Base rules", and `_DOMAIN_RULES` is alive and detailed. The emphatic versions — written immediately after watching a failure — are what was lost.
- **First adherence data, 2026-07-28: 1 of 3.** ✅ bbde3e51 turn 1 quoted the new create rule in its own reasoning — *"they're asking for one anyway - I should follow their request and create it as instructed (per the duplicate handling rule)"* — and proceeded. ❌ Turn 2, same prompt eight minutes later, refused and offered options instead. ❌ eb2d0ac1 titled a document *"…- Fact Checked 2026-07-28"*, which the new title rule prohibits outright. **So the rules reach the model and sometimes steer it, and are not reliable.** Three samples; treat as a first reading, not a rate. **Measuring this properly is the cheapest open experiment** — see the top of the Next list.
- **Open: decide per rule; do not revive the block wholesale.** The assembled prompt is already ~35k chars (~8.8k tokens) against a 32k window. Six rules were added to the live sections on 2026-07-28 (four document, three web) and `tests/test_agent_rules_reach_the_model.py` pins the four best-known dead markers as *absent*, so reviving one is a deliberate act.

## S4 — friction and blocked diagnosis

### 10. ~~Failures aren't replayable~~ ✅ fixed 2026-07-28
Document tool events now carry `full_command` — complete arguments, capped at 16 KB with an in-band truncation marker. Persisted on success as well as failure. [resolvedissues.md](resolvedissues.md), *"The record of a run didn't say what happened"*.

- ⚠️ **Rows written before 2026-07-28 have no `full_command`.** Existing history is still only as good as `<<<FIND>>>`.
- ⚠️ **Item 6 filed itself as blocked on this and was wrong**, three times. `full_command` is *tool arguments*; item 6 needed `round_texts`, which was already persisted. Nothing here ever unblocked it. Kept as the back-reference so the pair stays reciprocal.
- **Effort was filed as M and was one line plus a cap** — the data was already computed and streamed; only the persistence dict dropped it. The estimate was stale because nobody re-read the code after filing.
- A replay harness over history, symmetric with the editor-side one in `tests/tools/`, is now possible and not yet built.

### 11. ~~Non-document tools have no closing report~~ ✅ built 2026-07-28
`_side_effect_tool_summary` in `src/agent_loop.py`, wired into the turn-end path beside `_gathering_only_notice`. Report-only.

The user asked for *"a document with temperature and humidity data over time from http://192.168.0.185"*. Session 57dcd968 ran `web_fetch` → **`write_file`** (`TEMPERATURE_HUMIDITY_READINGS.md`) → `get_workspace`, and the entire reply was the 175-character preamble written *before* any tool ran.

⚠️ **What that turn did, corrected 2026-07-28 from `tool_events` — this entry previously had it backwards.** It was filed here as *"a file was written and the user was told nothing about it"*. The record says `exit_code=1`: *"write_file: path 'TEMPERATURE_HUMIDITY_READINGS.md' is outside the allowed roots"*. `get_workspace` then answered *"No workspace is set"*, and the next round produced 0 characters and 0 tool calls. **The tool failed with an actionable error, the model was handed the fix, and the user was told none of it.** The claim was read from the tool *sequence* without reading the tool *result* — the item 6 shape, one layer out.

- ⚠️ **Which also retracts the lesson filed under it.** This entry said the watch note's trigger (*"refile if a non-document tool is seen **failing** silently"*) would have missed this because the turn *succeeded* silently. It failed silently. **The trigger would have caught it; what failed was reading the row.** The general point survives and the example does not.
- **Every guard missed it, each for a defensible reason.** `_gathering_only_notice` requires all tools to be in `READ_ONLY_TOOLS`, and `write_file` is not one. `_unstarted_promise_notice` bails when any tool ran. `_doc_tool_summary` only knows document tools. `tests/test_non_document_tool_report.py` pins all three as silent on this turn before asserting the new one fires.
- **Coverage is the inverse of `READ_ONLY_TOOLS`, deliberately** — anything not known-read-only, not a document tool and not self-reporting gets a line, MCP and future tools included. That allowlist's argument does not transfer: there, guessing wrong tells a user nothing happened when something did; here it costs one extra line quoting what a tool returned. **The failure modes are not symmetric.**
- **Successes report only when the model said nothing; failures report either way** — item 21's argument on the non-document path.
- **Measured on the whole corpus before shipping**, not just fixtures: 77 recorded turns, 72 with tool events, **7 produce a line — 5 of them saved as a bare `"Done."` with `round_texts` all zero, 2 as a preamble. None had a reply describing the work, so zero duplicates.** One of the five is `write_file` returning *"Wrote 0 bytes"*, a file emptied and reported as success.
- ⚠️ **Known gap, not an oversight:** `manage_notes`, `manage_calendar`, `manage_tasks`, `list_emails`, `read_email` are excluded. The end-of-turn path *replaces* `full_response` with those tools' output, so a line appended before it is discarded — a `manage_notes` **create** therefore stays unreported. Fixing it means reordering that block, which is a separate change.
- **Separately: the model chose the wrong tool.** Asked for "a document", it wrote a workspace `.md` file instead of calling `create_document`, so none of item 3's, 2a's or 2b's checks applied either. Whether that is prompt-level or tool-selection is unmeasured. Do not fold the two problems together — the reporting gap was real regardless of which tool was correct.
- Item 8's reverted nudge is still why any *acting* fix must bound what the retry can write. A reporting fix has no such constraint, which is why this one could ship on test evidence.

### 12. Wasted verification rounds
9B sometimes runs `manage_documents` "to check" after creating a doc (~47 s for nothing). Run 27a94a01 did exactly this.

- ⚠️ **The prompt line against it exists and has never reached the model** (item 20). **This item has only ever been observed with the rule absent**, so "the model ignores it" is not established. Re-measure before building anything in the loop.

### 13. Terminal access-log noise
Every request prints, so real errors scroll away — worst during polling (`/api/research/status/<id>`, `/api/chat/stream_status/<id>`). **Got in the way twice on 2026-07-19** while confirming PUT traffic during the editor investigation. Hide 200s; hide 304s behind their own toggle, since a 304 storm is how you spot a stale-cache bug. Don't use `--no-access-log` (kills 4xx/5xx) — add a `logging.Filter` on `uvicorn.access` keyed by status, wired at `app.py:1281`, `launcher.py:142`, `start-macos.sh:292`, with an `access_log_hide_statuses` setting.

### 15. ~~`web_fetch` failure rate on cultivation sources~~ — folded into item 2
**Its premise was answered before it was measured.** Roughly a third of fetches fail on the sites this task reaches for. But run 31e0af64 fetched **one clean source, verified byte-exact**, and still produced four defects. Retrieval quality is not the load-bearing cause. Worth knowing when a fact-check turn ends empty-handed; measuring it more precisely would not change what gets built next.

### 16. SSRF guard tests covered an orphaned function
One instance fixed 2026-07-27 ([resolvedissues.md](resolvedissues.md), *"web_fetch could not reach the LAN"*); the **audit is the open part**.

`_public_http_url()` in `services/search/content.py` had no production callers, while `tests/test_search_content_url_guards.py` — a file that exists solely to test URL guards — asserted **3 of 3** cases against it, and `test_web_fetch_size_caps.py:93` monkeypatched it to a no-op. **The live guard had no coverage at all and the suite was green throughout.** Find the commit with `git log -S_public_http_url -- services/search/content.py` *(cited by search, not hash: the hash changed in the 2026-07-28 rebase)*.

- **This is worse than dead code: a green suite asserting a security property nothing enforces.**
- Fixed by making the orphan a thin wrapper over `_resolve_public_ips`, so the existing assertions exercise the live path and the two cannot diverge again.
- **Open:** a cheap first pass is to flag module-private functions with zero non-test references. `src/webhook_manager.py`, `routes/model_routes.py` and `src/model_context.py` each carry their own `_PRIVATE_NETWORKS` copy — **four independent implementations**, all still present as of 2026-07-28. Upstream added SSRF checks to `services/memory/skill_importer.py` independently: a good sign, and more surface for the same divergence.
- Related smell, not fixed: `test_web_fetch_size_caps.py` patches `content_mod.httpx.stream` while `_get_public_url` uses `httpx.Client(...).stream`. Those tests are not exercising what they claim either.

### 17. ~~A cache hit is indistinguishable from a live fetch~~ ✅ fixed 2026-07-28
Cached results carry `cached`, `cached_at` and `cache_age_seconds`; the `web_fetch` output tells the model *"served from cache … NOT a live reading"*. **Absence of the flag means live.** [resolvedissues.md](resolvedissues.md), *"The record of a run didn't say what happened"*.

- **Labelling the record alone would not have fixed the original failure** — it was the *model* reporting a cached `uptime: 91 s` as current, so the notice has to reach the model, ahead of the output trim.
- ⚠️ **The notice is delivered and half-believed, twice now.** Run 42889f7b quoted *"cached ~77 seconds ago"* in its document body and titled the same document *"(Live Fetch)"*. Run eb2d0ac1 built on a fetch **1,123 seconds** (18.7 min) old and described the result as *"fact-checked"* with *"✅ verified facts"*. **The model reads the flag and then writes a claim that contradicts it** — which is why item 21's warning path matters and why the new title rule exists. Getting the label into the prompt was necessary and is not sufficient.
- ⚠️ **Still true and not addressed:** `full: true` changes the cache key, so the same URL fetched with and without `full` uses two independent entries and can return two different bodies in one session. *Which* entry you got is now visible; that there are two remains a trap.
- ⚠️ Rows written before 2026-07-28 carry no flag either way.
- Operational detail in [qwensetup.md](qwensetup.md), *"`web_fetch` — what it sees, and what it silently reuses"*.

### 18. Two tests in `test_document_put_version_conflict.py` have never passed
`test_concurrent_ai_edit_after_read_loses_the_swap` and `test_losing_swap_does_not_leave_a_partial_version_row` both patch `droutes._reserve_document_uploads`, which is defined at `routes/document_routes.py:82` **nested inside `setup_document_routes()`**. It is a closure, never a module attribute, so the lookup raises `AttributeError` and can never have worked.

- **Third instance of the item 16 shape, and the least dangerous kind** — here the test fails loudly. Item 16's orphan failed *green*, which is why that one is the priority.
- **Fixing it is a design decision, not a repair.** Expose the closure, inject it, or drive the behaviour through the endpoint. `TESTING_STANDARD.md` favours the last; the other two exist only to make the patch possible.
- ⚠️ **Do not "fix" these by deleting them.** They cover the CAS race item 1 spent three diagnoses on: an AI edit landing between the handler's read and its write. That case needs coverage; what's broken is how the test reaches it.

### 19. ~~Five tests failed on macOS only~~ ✅ fixed 2026-07-28, verified live
Four `AF_UNIX path too long` (macOS caps `sun_path` at 104 bytes) plus `test_glob_confined_e2e`, whose assertion contradicted its own comment and passed on Linux by luck. **Neither was an application bug**; no confinement hole. [resolvedissues.md](resolvedissues.md), *"Five tests failed on macOS only"* — which also records why a Linux run cannot substitute for a macOS one.

---

## Notes & constraints
Settled. Recorded so they don't get re-litigated. **Working method lives in [`CLAUDE.md`](../CLAUDE.md); this section is facts about the system.**

- **Per-round thinking suppression isn't currently possible.** `reasoning_effort:"none"` needs `tools and _is_qwen_thinking_model and _agent_thinking_disabled()` (`llm_core.py:2276`). `agent_disable_thinking` is `False`, **and** `tools` is always `None` on this endpoint — so flipping the setting changes nothing. Needs an override plumbed through `stream_llm`.
- **Local models get no tool schemas at all** (`all_tool_schemas` is empty unless `_is_api_model`). Anything shaped like "force/narrow/restrict the tools" has no channel here and must happen in the loop.
- **Don't widen `_ody_doc_finetune_mode`.** It gates tool narrowing and `tool_choice_none` as well as the loop break. The reporting path was split out of it deliberately.
- ~~**The redundant `user` document version is cosmetic.**~~ **Retracted 2026-07-19.** It was the visible edge of the duplicate-`doc_update` data loss in item 1.
- **`app.db` lags live activity — "the newest row" is not "the last turn".** Rows are written on `save_sessions()`. A query at 15:20 returned a newest row of 12:36 while fd0f9ba0 had run until 14:00. **`data/app.db-journal` on disk is how you tell the app is running**, and while it is, anything else opening the tree gets `disk I/O error`. Copy the file and query the copy.
- ⚠️ **`round_texts` was absent from every turn that called no tools** — nested under `if tool_events:` in `_compute_final_metrics`. **That is the field separating item 6 from item 8**, so it was missing from exactly the turns where the question arises. Fixed 2026-07-28. **Rows written before then cannot be classified retroactively** — the same limitation items 10 and 17 carry.
- **Timestamps in `app.db` are naive UTC while `ls`/`stat` and `app.log` report local CEST.** Cost a two-hour error that made three post-fix sessions look like they predated the fix. Full statement in [qwensetup.md](qwensetup.md), *"Reading `data/app.db` when debugging a run"* — kept there because that is where you are standing when it bites.
- **Cross-references rot when items are renumbered**, because every edit to these files comes from a different session. Three were found wrong on 2026-07-27; a fourth, in `tests/test_doc_report_gate_split.py`, on 2026-07-28. **All four were one-directional.** Every surviving reference *within* this file is reciprocal — #6↔#10, #7↔#8, #2↔#14, #8↔#20 — so renumbering one visibly breaks the pair. **A cross-file citation that nothing points back at is the fragile kind.** Before renumbering, grep `--include=*.py --include=*.js` for `todo.md` as well as the docs; source comments are cross-references too, and there are more of them.
- **On guards that write.** A guard that only *reports* can ship on test evidence. A guard that makes the model *act* can destroy data, and its tests must bound what it can do, not merely assert it exists. Item 8's reverted nudge passed every test written for it.
- **A "superseded" banner does not retire a document — deleting the prose does.** `KNOWN_ISSUES_debug.md` carried a banner saying its leading theory was wrong; an agent read the banner and argued from the body underneath it anyway, the third trip down a road two retractions exist to close. **Prose that reads like a live finding will be treated as one, however it is framed.** When an item is retracted, cut the reasoning and keep the conclusion.
