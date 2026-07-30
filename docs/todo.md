# Open items — Qwen 9B setup

**How to work on this — [`CLAUDE.md`](../CLAUDE.md) at the repo root.** Evidence rules, guard rules, what to distrust in *this* file, and the traps that recur. Added 2026-07-28 because the drift described at the bottom is structural and the docs alone were not fixing it.

Setup and config: [qwensetup.md](qwensetup.md). Closed investigations: [resolvedissues.md](resolvedissues.md). Last session's summary: [session-log.md](session-log.md). Settled constraints that are *not* work items are at the bottom.

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
| 5 | Uncommitted work — **third recurrence, 2026-07-29** | S2 | XS | 28 in `1a8e804e`, docs in `4a2dfdd0`; **29 still out** | clean clone carries the new test |
| 6 | ~~Answer text lost to the reasoning channel~~ | S2 | S | ✅ fixed 2026-07-28 — a save-path regex | **tests (15)** |
| 7 | ~~Closing summary under-reports / stays silent~~ | S3 | S | ✅ fixed | **live — both branches** |
| 8 | Agent gathers information, then stops | S3 | M | reporting fixed; **active half reverted** | **live** / tests (zero-tool) |
| 9 | ~~Throughput cliff: 2.84 → 0.39 tok/s~~ | — | — | ⊘ **retired — disproved by its own data** | n/a |
| 9b | Streams fail mid-turn; timeout caps document length | S3 | S | reporting ✅; **timeout raised 300→900, unverified** | **live** (notice, bbde3e51) |
| 10 | ~~Failures aren't replayable~~ | S4 | XS | ✅ fixed 2026-07-28 — `full_command` | **live** — 42889f7b |
| 11 | ~~Non-document tools have no closing report~~ | S3 | M | ✅ built 2026-07-28 — report-only | **tests (20)** — needs a live turn |
| 12 | Wasted verification rounds | S4 | XS | open — **re-measure first, see item 20** | — |
| 13 | Terminal access-log noise | S4 | S | open — got in the way twice | — |
| 14 | Web search derails on ambiguous common nouns | S3 | M | open — the quoted-phrase half is item 29 | — |
| 15 | ~~`web_fetch` failure rate on cultivation sources~~ | — | — | ⊘ **folded into 2 — premise already answered** | n/a |
| 16 | SSRF guard tests covered an orphaned function | S4 | S | one instance fixed; **audit open** | tests |
| 17 | ~~Cache hits indistinguishable from live fetches~~ | S4 | XS | ✅ fixed 2026-07-28 | **live** — 42889f7b |
| 18 | Two CAS tests have never passed | S4 | S | open — found 2026-07-28 | n/a |
| 19 | ~~Five tests failed on macOS only~~ | S4 | XS | ✅ fixed 2026-07-28 | **live** — M1 suite |
| 20 | 116 lines of agent rules never reached a model | S3 | S | open — **found 2026-07-28** | tests |
| 21 | ~~Three S1 warnings suppressed when the model wrote a summary~~ | S1 | XS | ✅ **fixed 2026-07-28** | tests (13) |
| 22 | ~~Documents never stream into the editor on this setup~~ | S4 | — | ⊘ **retired — disproved 2026-07-28** | n/a |
| 23 | Finished answers delivered in the reasoning channel | S2 | ? | open — **found 2026-07-29** | **live** — 374d57b7 |
| 24 | ~~Cloned documents were all named "Untitled"~~ | S4 | XS | ✅ fixed 2026-07-29 | **live** — both paths, 2026-07-29 |
| 25 | A path-confinement test passes without the thing it tests | S4 | XS | **confirmed**; fix open | **confirmed on macOS** |
| 26 | Test litter in the repo root, hidden by `ignore_errors=True` | S4 | XS | open — **found 2026-07-29** | reproduced |
| 27 | A LAN address in the prompt deletes every document tool | S3 | S | open — **root-caused 2026-07-29** | **live** ×3 |
| 28 | ~~The model writes the tool call instead of making it~~ | S2 | S | ✅ built + **committed `1a8e804e`** 2026-07-29 | **tests (14)** — live ×3 pre-fix |
| 29 | ~~Quoted phrases return locale filler~~ | S3 | S | built 2026-07-29, ⚠️ **UNCOMMITTED** | **tests (16) green on the M1** — not live |
| 30 | Switching chats writes the editor buffer into the other chat's document | S2 | M | open — **found 2026-07-30** | **live ×2, proven by hash** |

**Numbers are never reused.** A retired item keeps its number and a `⊘` row, because renumbering has silently rotted cross-references four times (see *Notes & constraints*). Item 2 split into 2a/2b, and 9 into 9/9b, rather than taking new numbers, for the same reason.

> ⚠️ **Item 23 changes how item 8's evidence should be read**, and the pair is reciprocal (#8↔#23) so neither can be renumbered quietly. A turn that reports *"stopped without producing an answer"* may have produced one — in the reasoning channel. **Compare `thinking` against `content` before filing another item 8.**

> **Next, in order.** Ordering follows leverage, not severity.
>
> **−1. Item 29 is the last thing not in a commit.** *(Item 5, third recurrence. Item 28 landed in `1a8e804e` and the docs in `4a2dfdd0`, both 2026-07-29 ~21:30.)* ⚠️ **`git add -u` will leave `tests/test_search_quoted_phrase_filter.py` behind** — it is untracked, the same shape that made item 28 the recurrence. ✅ **Snapshot taken 2026-07-29 21:36 while the app was down** — `~/odysseus-snapshots/odysseus-evidence-2026-07-29.tar.gz`, 1,429,813 bytes, `app.db` + `app.log` + `app.log.1`, all three `OK` against hashes taken before the copy. **Everything below changes `app.db` and `app.log`, so it is now safe to run them.**
>
> 0. **Measure rule adherence properly — five same-prompt runs, each in a NEW chat with the document cloned into it.** First reading is **1 of 4** (item 20). This one number decides several other items: whether item 20's remaining rules are worth reviving, whether item 8's active half is needed at all, and whether item 12 is a model problem or was only ever a missing-rule problem. The protocol, and the two ways it has already been run wrong, are in item 20. ⚠️ **Score item 8's predicate by comparing `thinking` against `content`, not by the guard's notice** — see item 23.
> 1. **Item 27 — merge instead of clobber.** A LAN address in the prompt removes every document tool, so the ESP32 workflow cannot produce a document at all. Root-caused, reproduced both directions, and **it has no tests whatsoever**. Fix (a) alone is a few lines; leave (c) for a separate, measured change.
> 1b. **Item 23 — decide the report-only fallback.** S2, seen live. Surfacing reasoning-channel text when a turn produced **no content at all** is report-only, the class that can ship on test evidence (items 11, 21 and 28 all did). **Do not touch the parser** — the layer was checked and the `/v1` retraction holds. ⚠️ *It is no longer "corrupting item 8's tally": measured, 1 of 22 guard-notice turns.*
> 2. **One live turn for 2a**, the last S1 still at *tests*, and the only checker never observed firing. Ask for the ESP32 document and read the closing summary for *"Doesn't match the source"*.
>    ⚠️ **Close the open document in the editor first.** fd0f9ba0 asked three times and got nothing: the model read the open document from context and reasoned "one already exists, I should not duplicate". The document doing the suppressing was `3e99b6e3` from 2026-07-19, which 2b flags four times over. fb5525eb created one on the first try with the editor clear — consistent, but one run and not a controlled comparison. **Opposite precondition to step 0; do not collect both in one session.**
> 3. **Item 3's prevention gap** — `find_stale_values` has exactly one production caller, `document_tools.py:768` *(was cited as `:765`; re-verified 2026-07-29 — grep `find_stale_values`, do not trust the number)*, inside `EditDocumentTool`; `update_document` bypasses the lint entirely *(re-verified 2026-07-28)*. Note the interaction: item 7's live guard promises *"I'll rewrite the document in full instead of patching"*, which routes every edit failure into the one path with no lint.
> 4. **Item 16's audit — narrowed 2026-07-28 to the zero-non-test-references pass.** The `_PRIVATE_NETWORKS` half was walked and is a false lead; the retraction is in the item and re-walking it costs a session.
> 5. **Item 13** — friction, but it has obstructed debugging twice. ⚠️ *Two of the three cited call sites re-verified 2026-07-28; `start-macos.sh:292` is now a bare `uvicorn` CLI invocation with no log flag, which is a different fix shape from a `logging.Filter` on a `uvicorn.run` kwarg.*
>
> **Owed verifications, not investigations.** Each is one run and closes a row that currently overstates itself:
> **item 11** — one turn using a non-document tool; **item 2a** — one ESP32 document with the editor cleared; **item 9b** — three deliberately long *rounds*. ⚠️ *9b is no longer untested and the evidence points the wrong way: a single round ran **448.7 s** on 2026-07-28 23:38 at `timeout=900` and completed, where the old 300 s cap would have killed it — but it logged `text_chars=0 tool_calls=0`, so that silence was **not** a tool-call payload being generated.* ⚠️ **Do not cite the 457 s turn of 2026-07-29 18:06 as a second data point** — it was 8 rounds, longest 140.5 s, and the timeout is per-read inactivity *within* a round. `response_time` is a turn; `elapsed` is a round; **conflating them is how this item was misread the first time.**
>
> **Closed 2026-07-29 by running them:** ~~item 5~~ **— re-opened the same evening, third recurrence; see the item.** The measurement stands (clean clone, `2 failed, 5738 passed`, 2,930 imports resolved) and **was overtaken by work committed after it**. Also item 24 and *"Open in new chat"* (two clones, both carried the source title), and item 25 (macOS run confirms the vacuity) — both still closed.
>
> **Closed and off this list:** item 11 (2026-07-28, built), item 22 (2026-07-28, disproved and retired), item 24 (2026-07-29, fixed).
>
> **Suite: measured `2 failed, 5768 passed, 4 skipped` in 109 s on the M1, 2026-07-29 21:2x** — 5,774 collected, item 18 only, both pre-existing. ⚠️ **This was run in the working tree, which held item 29's 16 uncommitted tests.** `HEAD` after `4a2dfdd0` collects **5,758** and passes **5,752** — subtract them before comparing this line to a clean clone, and **re-measure rather than adjusting once item 29 lands.** *(Prior readings: `5738/5744` earlier the same day, `5588` on 07-28, `5433` before ~1939 upstream commits. The `5,711` once predicted from a sandboxed `--collect-only` was 33 low — replace this line with a measurement, never a prediction.)* Item 8's active half stays parked — read its ❌ bullet first.

---

## S1 — wrong output the user trusts

### 1. ~~Autosave is reverting AI edits~~ ✅ fixed, verified live 2026-07-19
Not autosave and not the compare-and-swap — a single tool call emitted `doc_update` **twice**, and the second delivery made the diff-mode guard restore and persist the pre-edit buffer. **20 reverts pre-fix → 0 post-fix.** [resolvedissues.md](resolvedissues.md), *"Autosave reverting AI edits"*.

### 2. Wrong numbers in documents the user trusts
*Split 2026-07-28: 2a is "the document disagrees with the data it was handed", 2b is "the document disagrees with reality". Both are built and report-only. They looked like one item and share only a severity.*

#### 2a. ~~Document doesn't match its source~~ ✅ built 2026-07-28
`src/document_fidelity.py`, surfaced in the closing summary, silent unless the turn fetched a JSON source. Design argument and the two bugs the tests caught: [resolvedissues.md](resolvedissues.md), *"The document didn't match its source"*.

- ⚠️ **Tests only — the last S1 not seen live.** Ask for the ESP32 document and the closing summary should carry the warning.
- ⚠️ **A live case walked past it on 2026-07-29 18:11 and it had nothing to check.** `web_fetch` returned `exit=1`; the model said *"The fetch timed out — I can't reach http://192.168.0.185 from here"* and called `update_document` anyway. **It fact-checked against nothing and reported that it had.** 2a is silent unless a turn fetched a source the fixture knows — a *failed* fetch leaves it with no source at all, which is the one case where the document is most likely to be invented.
- ⚠️ **Measured 2026-07-28 and again 2026-07-29: it has never fired, on any recorded turn.** *"Doesn't match the source"* appears **0 times** across all **129** recorded assistant messages, against **10** for 2b's warning, **6** for item 3's lint, **13** for item 7's failure branch and **26** for item 8's guard notice. *(The 2026-07-28 reading was 0 against 77 rows, 4 / 3 / 3 — every other checker has fired more often since; this one has not moved off zero as n grew by 52.)* **That is not yet a fault** — it is silent unless a turn fetched a source the fixture knows, and `config/field_semantics.json` knows one device. But it means every part of this item downstream of "does it fire at all" is still untested, so the live turn is worth more here than anywhere else on the list.
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
- ⚠️ **The interaction with item 7 was filed as a theory and was OBSERVED END TO END on 2026-07-29, session d16f7a83.** Turn 1: four `edit_document` calls, every FIND block rejected, item 7's guard fires — *"I'll rewrite the document in full instead of patching individual passages."* Turn 2: the model does exactly that, `update_document`, **v5 written with no consistency lint at any point.** The guard is honest, the promise is reasonable, and it routes each edit failure into the one write path with no checking. **Any fix here has to cover `update_document`, or item 7's success makes item 3 worse.**
- **How much is the model is an open measurement, not a known quantity** — the editor was manufacturing part of it.

### 4. ~~The retired 4B is still live on the research path~~ ✅ done 2026-07-19
`research_model` is now `qwen3.5:9b-32k`. [resolvedissues.md](resolvedissues.md), *"Research path moved off the retired 4B"* — which also records why blanking a model field is a downgrade, not an inherit.

## S2 — silent loss

### 5. Uncommitted work — ⚠️ **re-opened 2026-07-29, third recurrence**
Closed twice and re-opened twice: committed 2026-07-28, recurred within hours and broke `HEAD`, re-committed and verified by cloning — **and recurred again the same evening.** Full account of the first two, including the recovery commands: [resolvedissues.md](resolvedissues.md), *"Sixteen days of uncommitted work"*, *"Upstream rewrote history"*. What stays here is the part that keeps costing sessions.

⚠️ **Third recurrence, found 2026-07-29 ~20:50 — every part of item 28 is in no commit.**

| | in `HEAD` | on disk |
|---|---|---|
| `_fenced_regions`, `_tool_payload_looks_like_edit`, `_tool_payload_as_text_notice` (`src/agent_loop.py`) | **absent** | present |
| `tests/test_tool_payload_as_text.py` (14 tests) | **not in the tree object** | 5,979 bytes |
| item 28's retry-text fix (`src/agent_tools/document_tools.py`) | old wording | new wording |
| `CLAUDE.md`, `docs/todo.md`, `docs/resolvedissues.md` | older | newer |

- **Five modified tracked files, one untracked test file** — the complete divergence, measured, not sampled.
- ✅ **`HEAD` still runs, unlike the last recurrence.** The import sweep over the `HEAD` tree resolves **2,931 first-party imports, 0 unresolved**, because nothing untracked is imported at module top. **This one is a lost *feature*, not a broken `HEAD`.**
- ⚠️ **The untracked file is a test, so `git add -u` will silently leave it behind** and the commit will look complete. That is item 28's 14 tests — the entire evidence for a row this file marks ✅.
- **The drift started the moment the item was marked done, for the third time.** `6b1a6ee7` closed this item at ~17:00; item 28 was built after it and never committed. **The pattern is not "we forget to commit", it is "✅ is written before `git status` is run".**
- ⚠️ **A SECOND uncommitted batch appeared while this was being written** — `services/search/core.py` (carry `engine` through to `app.db` metadata), `services/search/providers.py` (quoted-phrase handling) and an untracked `tests/test_search_quoted_phrase_filter.py`, all mtimed 20:57–21:00 CEST. **Item 14 work, in flight.** `HEAD` still imports cleanly with it present (2,931 imports, 0 unresolved). **Stage by explicit path, never `git add .`** — a blanket add sweeps another session's half-finished work into item 28's commit, which is how the *"Open in new chat"* feature rode into a 3-line title commit (item 24).
- ✅ **Committed 2026-07-29 ~21:30.** Item 28's code and its 14 tests in `1a8e804e`; the docs and these corrections in `4a2dfdd0`. **Verified the way this item requires** — `git clone ~/odysseus /tmp/x` then `git ls-files tests/test_tool_payload_as_text.py` returns the path, so the untracked test is genuinely in `HEAD` and not merely on disk. ⚠️ **Item 29 is still out**, so this item does not close.
- ✅ **Evidence snapshot taken 21:36, app down.** `~/odysseus-snapshots/odysseus-evidence-2026-07-29.tar.gz`, 1,429,813 bytes. Hashes taken before the copy verified `OK` on all three files afterwards, per the rule that a mid-copy write must be visible. `app.log.1` — the 2026-07-12 → 07-28 base — is inside it.
- **How it was found without running git:** `git archive HEAD | tar -x -C /tmp/x && diff -rq /tmp/x .` — reads a tree, takes no index lock, safe from the sandbox, and **it does not trip the CRLF false positive below**, because `git archive` applies the same `eol` attributes as the working tree. Recorded in [`CLAUDE.md`](../CLAUDE.md).

- ⚠️ **`data/app.db` is in no commit and never will be** — `data/` and `*.db` are gitignored, and it holds every run this file reasons about. **A snapshot tarball is the only thing protecting the evidence base.** Committing protects the code; the tarball protects the findings.
  - ❌ ~~"The `outputs/snapshots/*.tar.gz` is the only thing protecting the evidence base"~~ — **corrected 2026-07-29. That path named a file that did not exist.** No `outputs/snapshots/` directory was in the repo and no `*.tar.gz` was anywhere on disk; it had pointed at an agent scratchpad, which is cleared between sessions. **For an unknown period the evidence base was protected by nothing, while this line said otherwise** — and `app.log` had already rotated on 2026-07-28, putting 17–28 July two rotations from deletion. **A snapshot inside an agent's working folder is not a snapshot.**
  - ✅ **Snapshot taken 2026-07-29 to `~/odysseus-snapshots/`, outside the repo** so no git command can reach it. Hash-verified before and after the copy, with a negative control; procedure and caveats in [qwensetup.md](qwensetup.md), *"Reading `data/app.db` when debugging a run"*.
- **Ignoring a file is not protecting it.** `git clean -fdx` deletes ignored files and nothing points at them — an ignored file is *less* safe than an untracked one, having lost the `??` line that would remind you it exists.

✅ **Verification scope of the second close, 2026-07-29 ~17:00.** ⚠️ **It was true when taken and did not survive the evening** — see the third recurrence above. **A clean-clone result has a shelf life measured in commits, not days.** A clone of `dev` into `/tmp`, a fresh venv, and the full suite: **`2 failed, 5738 passed, 4 skipped` in 122.05 s**, byte-identical to the working-tree run, plus **2,930 first-party imports, 0 unresolved**. The two failures are item 18. **`HEAD` is complete and runnable; nothing untracked was load-bearing.**

- ⚠️ **A green suite in the working tree cannot close this item, and that is the entire point.** Every earlier run had the untracked files present on disk. **The suite tests the tree, not the commit.** The 2026-07-29 recurrence — a committed `src/agent_loop.py` importing an untracked `src/known_facts.py`, so a fresh clone could not import the core module — stayed invisible through a full green suite and would have until someone cloned.
- **`✅ fixed` in this file means "it works on this machine", not "it is in the repository".** Both times the drift began the moment an item was marked done. **Before writing ✅ on anything that ADDED a file, run `git status`** — new modules, fixtures and test files are untracked by default and no amount of local green tells you otherwise.
- **The check, when you need it again:** `git clone ~/odysseus /tmp/x && cd /tmp/x` then an AST sweep of every first-party `from (src|routes|core|services)… import` against files on disk. **Seconds, no venv.** The venv-and-suite version is belt-and-braces once the tree is already green.
- ⚠️ **`git status` is this item's whole early-warning system, so noise in it is a real cost — see item 26**, reciprocal (#5↔#26). A test writing untracked directories into the repo root puts permanent `??` lines in front of the one signal that would have shown `known_facts.py` missing.
- ⚠️ **Do not diff working files against blobs to find modifications.** `.gitattributes` sets `*.ps1`/`*.bat` to `eol=crlf`, so the blob is LF and the working tree is CRLF *by design*; comparing `git show HEAD:<file>` against the file reports three Windows scripts as modified when `git status` calls them clean. **Use `git status`, or `git check-attr text eol -- <file>` before believing a diff.**

### 6. ~~Answer text can be lost to the reasoning channel~~ ✅ fixed 2026-07-28
**It was never the stream. It was a regex in the save path** — `_normalize_thinking` in `routes/chat_helpers.py` split by *position*, keeping the last line and moving the rest out of the message, on any answer opening with `"I need "`, `"The user "` and five similar phrases. Two instances in 65 recorded turns; one lost 675 of 705 characters. Full account: [resolvedissues.md](resolvedissues.md), *"The save path decided which half of the answer was thinking"*.

- ⚠️ **Item 8's evidence base needs re-reading because of this.** Run c7da3649 ended on *"Let me correct these issues:"* — a textbook dangling promise, **manufactured by the save path**. **Do not count a dangling-promise run as item 8 without comparing `round_texts` against the saved `content` first.**
- ~~"Confirming it needs the raw stream"~~ and ~~"item 10 unblocks this"~~ — **both wrong, retracted.** `round_texts` persisted the complete pre-split text all along; `full_command` is *tool arguments* and could not have helped. This item recorded itself blocked on item 10 three times. **Check what a field contains before filing a dependency on it.**
- ~~The 2026-07-27 frequency count~~ — **retracted, not evidence.** All-zero `round_texts` is 15 of 40 turns and appears on turns that ended fine; it is the base rate, not a signal.
- **The earlier `/v1` retraction stands and is unrelated.** That one is about `llm_core.py` *during* the stream; this is `routes/chat_helpers.py` *after* it. **Both are true at once**, and reading the retraction as "therefore nothing eats the answer" is what kept this open for nine days.

### 30. Switching chats writes the editor buffer into the other chat's document
**Found 2026-07-30 while collecting item 20's five runs. An AI-written document was destroyed and a second chat's document was overwritten with content it never contained.** Not item 1 — that was a duplicate `doc_update` inside a single tool call, and it stays closed. This is cross-session carry-over, and the pair is reciprocal (#1↔#30).

**Proven by hash, not inferred.** `document_versions.source` records who wrote each version:

```
d1c934f7  v1  12:09:53  src=ai    10,877  sha=59879c9e   model output, session 67c53dab
986c425e  v2  12:11:21  src=user  10,877  sha=59879c9e   same bytes, session c9c2b615
d1c934f7  v2  12:29:21  src=user   8,578  sha=ea089a2f   clone content — the AI version is gone
```

The model finished writing `d1c934f7` at 12:09:53. **88 seconds later the identical bytes appear as a `user` version of a different session's document**, and twenty minutes after that the model's own document is overwritten with the pristine clone content. Both writes are `source=user`, i.e. the editor's PUT path, not the agent.

- ⚠️ **The turn that followed was handed the wrong document and produced nothing.** `[doc-inject] found by ID … content_len=10877` at 12:11:22, one second after the overwrite — the model was given another chat's document, ran **433.1 s**, and logged `text_chars=0 tool_calls=0`. **No assistant row was ever saved for it.** Whether the empty turn is caused by this or merely downstream of it is unestablished.
- **Scope swept across all nine documents of 2026-07-30:** one AI document destroyed (`d1c934f7`), one clone contaminated (`986c425e`), the other two AI outputs (54,390 and 11,756 chars) intact. **`source` + a content hash is the sweep** — length alone is not, and two unrelated documents in this corpus happen to share a length.
- ⚠️ **It corrupts item 20's experiment silently.** The five-clone protocol assumes "five independent copies sharing no version history". Run `c9c2b615` refused to create a document while holding a buffer that had been replaced one second earlier — **that run is unusable, and the refusal cannot be attributed to the model.** Until this is fixed the protocol needs a step: do not return to a finished run's chat, and re-hash the clones before scoring.
- **Two structural defects are confirmed by reading the source; the exact pairing is not.**
  1. **Nothing cancels a pending autosave on a session switch.** `_autoSaveDebounce` is armed at **10 sites** in `static/js/document.js` (800 ms, and 2000 ms on two paths). Every `clearTimeout` on it is the debounce re-arming itself — grep and read the next line. `loadSessionDocs` and `sessions.js`'s switch path never touch it.
  2. **The switch is deferred by 300 ms** — `setTimeout(() => documentModule.loadSessionDocs(id, …), 300)` at `sessions.js:2104`, same shape at `:3412` — against autosave timers of 800/2000 ms.
  - `switchToDoc` itself is **not** the hole: it calls `saveCurrentToMap()` before assigning `activeDocId`, in that order. `loadSessionDocs` is the one that drops other sessions' docs from the map and sets `activeDocId = null` with **no flush and no timer cancel**.
- ⚠️ **Do not file the mechanism as settled.** The above explains *that* a stale write can survive a switch; it does not yet explain the observed pairing (new document id, old buffer content). **This repo has twice recorded a mechanism from a symptom string.** Reproduce it in the UI before writing one down.
- ✅ **The trigger is `chat.js:1596`, not an autosave timer.** `sendMessage` calls `await documentModule.saveDocument()` on **every send** whenever a document is active (again at `:1638` with `silent: true`, which the `lastSyncedContent` equality check then skips). That is the 12:11:21.478 write — **11 ms before** the `[doc-inject]` line for the same send. The debounce timers are a second, slower path to the same hole; they are not what fired here.
- ⚠️ **`saveDocument` has no user-edit check on the happy path.** It PUTs `textarea.value` to whatever `activeDocId` is. `_userDirtyDocId` exists and is consulted **only inside the 409 branch** (`:9587`), where the comment already states the principle — *"any code path that writes the textarea programmatically diverges too … or the retry becomes a way to resurrect content the user never typed"*. The non-409 path never asks. `base_version` matched, so the CAS passed legitimately — **the same conclusion item 1 reached about this guard.**
- ❌ ~~"Fix (a): reject a PUT whose session doesn't match `documents.session_id`"~~ — **retracted 2026-07-30, hours after being written, before any code was touched.** It would not have prevented this. The write targeted `986c425e`, which *belongs to* `c9c2b615`, the chat the user was in — session and document agreed. **It would have caught only the second event and would have read as a fix for both.** A guard has to be checked against the actual failing write, not against the story about it.
- ✅ **REPRODUCED 2026-07-30 13:32:45, with the `[doc-put]` log naming both halves in one line:** `doc=b1754908 doc_session=5bc3c70f base_version=1 len=16294 sha=db92c4f2ae7c`. `b1754908` is chat P's 8,578-char clone; the content is chat Q's 16,293-char AI document. **Removing the single character that was typed makes it byte-identical to `ea73565d` v1** — the divergence is at offset 1454 and nothing else differs. The editor was displaying Q's document while bound to P's id, and **one keystroke persisted it**. No send was involved.
  - **The panel was MINIMIZED to the composer chip across the switch.** With it minimized, switching chats and waiting produced **no PUT at all** (`r1-before` == `r1-after`, zero `[doc-put]`) — `saveDocument` returns early when `doc-editor-textarea` is not in the DOM. The damage happened on *restore*: `openPanel` removes and rebuilds `#doc-editor-pane`, and `_minimizedDocId` / `Modals.isMinimized('doc-panel')` carry the chip across the session switch while `loadSessionDocs` has already repointed `activeDocId`. **Minimize in chat Q → switch to chat P → restore → type.**
  - ⚠️ **The first attempt at this repro was VOID, not clean.** It ran with the panel closed and was read as "the switch is innocent". A protocol whose precondition silently disables the mechanism produces a negative that looks like evidence. **Arm-check first: type one character and confirm a `[doc-put]` line before believing any zero.**
- ✅ **`[doc-put]` instrumentation added 2026-07-30**, `routes/document_routes.py`, before the identical-content skip and before the CAS so a cross-session write is visible even when later rejected. **This bug cost a document precisely because nothing recorded which document each PUT carried.** Keep it until the fix is verified.
- **Candidate fix, not yet safe to build:** gate automatic saves on `_userDirtyDocId === savingDocId`. ⚠️ **`_markUserDirty` is wired to only three inputs** — the textarea, the email rich body, and the four email header fields (`:2562`, `:5612`, `:5873`). **Not the title input, not the language select**, so gating on it as-is would silently stop saving title-only and language-only edits. And `chat.js:1596` passes no `silent` flag, so gating on `silent` misses the very call that caused this.
- ⚠️ **This is a guard that SUPPRESSES writes, so a false positive loses user typing** — the same severity as the bug. Per [`CLAUDE.md`](../CLAUDE.md) §3 it must be bounded and seen failing first, and **there is no JS harness**. Do the reproduction and a report-only PUT log before touching `document.js`.

**Attempted fix, 2026-07-30 — built, and it did NOT hold. Do not read the diff as a fix.**
`static/js/document.js` now stamps `textarea.dataset.docId` in `switchToDoc` and `populateEditor`, and `saveDocument` re-renders instead of writing when the stamp disagrees with `activeDocId`. **A second keystroke wrote through it anyway** — `13:42:23 [doc-put] doc=b1754908 base_version=2 len=16295`, one character on top of the bad v2. Two branches remain and they need different patches:

- **`stamp=(none)`** — the pane was rebuilt with no render, so a fresh `<textarea>` carries no stamp and the guard fails open *by design* (it must, or a legitimate first save would be blocked). Then the fix belongs in `restoreFn` / `openPanel`, not in `saveDocument`.
- **`stamp=<the other document>`** — the guard should have fired and something saved regardless.

An unconditional `console.log('[doc-save] target=… stamp=…')` was added to separate them. ⚠️ **It was `console.debug` first, which Safari hides behind the console's level filter** — a log line nobody can see is not instrumentation.

- ❌ ~~"`loadSessionDocs` has no `res.ok` check, so a 404 leaves the pane holding stale content"~~ — **retracted the same hour.** The `res.ok` gap is real but is not what happened: the 404s in the browser console resolve to `/api/research/status/<session>` and `/api/chat/stream_status/<session>`, the two polling endpoints **item 13** already files as noise. They 404 whenever no run is in flight. The document fetch was never failing. **Third theory this item has killed** — the session-ownership guard, the switch-time autosave, and now this.
- ⚠️ **State as of 2026-07-30 14:00: `b1754908` is still corrupt at v3** (16,295 chars where the clone was 8,578) and the editor displays it inside chat `5bc3c70f`. **v1 is intact at `ea089a2f7fd8` and Q's original at `65580c429b7c`, so nothing is unrecoverable.** Restoring it over the API returns **401** — auth is on and a bare `urllib`/`curl` PUT carries no session cookie. Restore from the UI, or stop the app first.
**Root cause, found 2026-07-30 by tracing instead of reading. `restoreFn` empties the document before rendering it.**

`Modals.register('doc-panel').restoreFn` (`static/js/document.js`) calls `openPanel()` — which builds a **fresh, empty, unstamped** `#doc-editor-textarea` — and then `switchToDoc()`, whose first act is `saveCurrentToMap()`. `activeDocId` still points at the minimized document, so **0 characters are copied over its map entry**, and `switchToDoc` then renders the entry it just emptied:

```
12:48:03.016  saveCurrentToMap  active=aa87b1ce  stamp=null  len=0   blocked=false
12:48:03.016  switchToDoc       id=aa87b1ce      len=0
```

That is the *"the chip opened an empty untitled document"* report, exactly. **No PUT followed, so the 17,085-character server copy survived by luck — one keystroke would have persisted the empty version.** The 14:24 cross-chat write is the *same call* with different timing: instead of empty text the buffer held another chat's document.

- ⚠️ **The first stamp guard let it through because a missing stamp failed open.** `blocked=false` above. **A missing stamp is not permission** — that was the error, and it is the same shape as the guard-that-cannot-fire this file records twice already (items 16, 25).
- ✅ **FIXED and VERIFIED 2026-07-30.** `saveCurrentToMap` now writes only on an explicitly matching stamp, with one exception: a genuinely new document where buffer and map entry are both empty. Same sequence re-run:

  ```
  12:52:28.890  saveCurrentToMap  active=aa87b1ce  stamp=null  bufLen=0  mapLen=17085  blocked=true
  12:52:28.890  switchToDoc       id=aa87b1ce      len=17085
  ```

  **The 12:48 run is the negative control** — identical steps with that branch unguarded, document emptied — so "check it fails before you check it passes" is satisfied without reverting anything. The minimize immediately after logs `bufLen=17085 mapLen=17085 blocked=false`, so a legitimate copy still passes and the guard does not over-block.
- ⚠️ **Only the empty-buffer branch has been observed being blocked.** The foreign-buffer branch (the 14:24 write into `c4da7609`) falls under the same `_stamp !== activeDocId` condition but **has not been triggered on demand**. Do not record it as verified.
- ✅ **`window.__docTrace` is why this was found.** A rolling in-page trace of `loadSessionDocs` / `chipRestore` / `switchToDoc` / `closePanel` / `saveCurrentToMap` / `saveDocument`, dumped with `console.log(JSON.stringify(window.__docTrace))`. **Four fix attempts were argued from reading a 10,000-line file and three were wrong; the trace settled it in one run.** ⚠️ It relies on nothing being open at the time, which is the property the console lacked — two runs were wasted on "was the console open, was the panel open, was the precondition met".
- **Still open:** `restoreFn`'s ordering is the actual defect and is untouched — the guard makes it harmless, it does not make it correct. `openPanel()` should render the active document into the pane it builds, rather than leaving `switchToDoc` to flush an empty buffer first.

## S3 — visible task failure

### 7. ~~Closing summary under-reports, and sometimes says nothing~~ ✅ fixed — live end to end
Two defects: counts were replaced rather than accumulated (10 edits reported as 1), and the guard only fired on an *empty* response, which this model never produces because it opens with its intent. **Item 7's silence caused an item 8 failure.** Mechanism: [resolvedissues.md](resolvedissues.md), *"Turns that did work and reported none of it"*.

- ✅ **Failure branch live 2026-07-27** (31e0af64): *"I couldn't apply the edit — the document is unchanged."*
- ✅ **Accumulation branch live 2026-07-28** (fb5525eb turn 3): *"7 edits applied across 2 rounds, 4 not applied (the FIND text didn't match — those corrections are still missing)."* This was the item's last tests-only scope.
- ⚠️ **Possible under-report, found 2026-07-29 and NOT yet diagnosed — check before trusting the counter.** Session d16f7a83 turn 1 records **four `edit_document` tool events** (all `<<<FIND>>>`, all `exit_code=None`) and the message says *"rejected **1** attempt this turn … (skipped 1)"*. Four events, one attempt reported. It may be legitimate — one attempt retried across four rounds — but **that is the exact shape of the accumulation bug this item was closed on**, and it is one query to settle: compare `tool_events` length against the reported count on that row.

### 8. The agent gathers information, then stops
Four attempts at one task in 16 minutes, **zero files produced**. 0b12aadb read 10,035 chars, correctly identified the embedded HTML page, ended its thinking with *"Let me write out the extracted content:"* — and emitted nothing.

**Shares a root cause with item 7** — every guard tested `full_response` for emptiness, and a dangling promise is not empty. Item 7's silence also *caused* one instance here: told nothing had happened, the user asked again 16 seconds later and the repeat turn spent 162 s producing nothing.

- ✅ **Reporting half — live** (eb2d0ac1): *"I ran `web_search`, `web_fetch` and then stopped without producing an answer — nothing was created or changed."* Detection is positional, not keyword-based: prose is snapshotted before **every** tool block. Tests: `tests/test_dangling_promise_turn.py`.
- ❌ **"The failing turns lost their write tools" — tested and WRONG, 2026-07-29. Do not re-open it.** It is the most attractive hypothesis available and the `[agent-intent]` log kills it: **every turn, failing and succeeding alike, had `edit_document`, `update_document` and `create_document` in `selected_tools`.** Three consecutive failures at 12–25 tools and a success at 13 tools carried near-identical sets — the successful turn's list differs from a failing one's by a single entry (`manage_research`). *(The genuine version of this bug was fixed 2026-07-18 — [resolvedissues.md](resolvedissues.md), "Active-doc turns losing edit tools on low-signal input"; the fix is holding, which is why the tools are there.)*
- **Session 3e0c537b, 2026-07-29 — three consecutive failures, and the `thinking` was read rather than the guard.** All three end on a dangling promise: *"Let me edit it to correct these issues…"*, *"I'll correct these and also tighten up wording"*, *"Let me create a corrected table and update the document:"*. **Genuine item 8, none of them item 23.** Even *"continue"* failed. **Corpus tally: 21 of 108 assistant turns end in the guard notice; exactly 1 of the 21 is item 23.** ✅ **Re-measured 2026-07-29: 26 of 129 (20%, against 19% before), and still exactly 1 is item 23** — first notice 2026-07-19 10:24, latest 2026-07-29 18:10 CEST. **The rate is flat and the item-23 contamination is not growing.**
- ❌ ~~"The verb decides it — *correct* fails where *rewrite* succeeds"~~ — **raised and killed the same day, 2026-07-29. Do not spend runs on it.** It came from three failures on *"correct"* against one success on *"rewrite"*. Over the whole corpus: **"rewrite" 9 turns / 2 guard notices (22%); "correct" 32 turns / 9 (28%)** — indistinguishable. And that evening *"fact check and rewrite the document"*, the identical string in the same session, ran four times: **failed, succeeded, failed, succeeded.** It is nondeterminism. **A lead built on n=1 each way is a coin flip with a story attached.**
- ⚠️ **Some of what this item counts is item 23, not item 8. Check before adding to the tally.** On 2026-07-29 the notice fired twice on turns where the model had **finished the work in the reasoning channel** — 3,892 and 1,032 chars of `thinking` holding a complete fact-check report and a question back to the user. *"Stopped without producing an answer"* is true about tools and false about the answer. **The item 6 check does not separate them:** `round_texts[-1]` is genuinely `''` in the item 23 case, because nothing arrived as content. **Compare `thinking` against `content`.** 48 recorded turns have this shape and 7 look deliverable-shaped; see item 23.
- ✅ **The zero-tool hole, closed 2026-07-28.** fd0f9ba0 turn 3 promised a document, called nothing, and said nothing. **Neither guard was broken; both were out of range** — `_gathering_only_notice` returns `""` with no tools, and `_text_is_only_preamble` needs a tool boundary to be positional about. **This item's "verified live" was recorded from eb2d0ac1, which ran three tools; the scope written down was wider than the thing verified.** `_unstarted_promise_notice()` covers it, measured on all 67 recorded turns before shipping: 3 ran no tools, 5 end on a colon, exactly 1 does both. Tests: `tests/test_zero_tool_turn_reporting.py`.
- ❌ **The active half was tried and REVERTED the same day. Read this before retrying it.** A nudge told the model *"finish the job NOW using the appropriate tool."* Run 8c80cf8d called `update_document` with **empty content**, wiping a 6186-character document, then created two empty `Untitled` documents and emptied one twice — **five zero-length versions in four minutes, against none in the preceding 79.**
  - **Telling an idle model to act is not telling it what to do.** With nothing to write, "act now" resolved to the most destructive available call.
  - **A future attempt needs a narrower directive plus a guard proving the retry can only write content it actually holds.** Tests must assert the directive is *safe*, not merely that it exists — the ones written for the reverted version would have passed no matter how destructive it was.
- ⚠️ **The behaviour has never been observed with the rule against it in force.** *"YOU DECLARE WHEN THE JOB IS DONE … the only wrong moves are trailing off mid-task"* is a direct instruction against this, shadowed since 2026-06-09 (item 20). **Measure with a live rule before building anything in the loop** — that is the cheap experiment, and the reverted nudge is what the expensive one looks like.

#### Session c1af9e2f, 2026-07-28 23:04–23:47 CEST — five reproductions in forty minutes
Eleven prompts in one chat. Seven asked for a document; **three produced one and four produced nothing**, each of the four ending in the guard line.

| # | 23:xx | prompt | outcome |
|---|---|---|---|
| 1 | 04 | create a new document … | ✅ created (v1) |
| 2 | 09 | fact check and correct the document | ✅ updated (v2) |
| 3 | 13 | *(identical to #1)* | ✅ created |
| 4 | 19 | *(identical to #1)* | ❌ `web_search`, then nothing |
| 6 | 24 | *(identical to #1)* | ❌ `web_search`, then nothing |
| 7 | 27 | webfetch and create a new document … | ❌ `web_search`, `web_fetch`, then nothing |
| 9 | 40 | fact check the temperature values | ❌ `web_search`, then nothing |
| 10 | 44 | web search …, then create a new document | ❌ `web_search`, `web_fetch`, then nothing |

- ✅ **The reporting half fired on all five, live.** Every failed turn was saved as *"I ran `web_search` … and then stopped without producing an answer — **nothing was created or changed.**"* This is the item's largest live sample to date and it did not miss once. Both successful document turns also carried 2b/3 ⚠️ warnings.
- ⚠️ **This session cannot attribute a cause, and the attempts to make it are recorded below as warnings.** It is one conversation with a growing history, three documents accumulating, and a changing injected document. **That is precisely what item 20's step-0 protocol has to avoid** — see the corrected protocol there.
- ❌ ~~"The failures start once a document is injected into the prompt"~~ — **wrong, retracted before filing.** `[doc-inject]` is INFO and shows a document injected on **all eleven** turns, including the three that succeeded. The first read came from grepping `app.log` alone after it had **rotated at 23:21:34**, so the first four turns' lines were in `app.log.1` and their absence looked like a signal. **Grep `data/logs/app.log*`, never `app.log`.**
- ❌ ~~"The model is being handed 91,212 tokens against a 32k window"~~ — **wrong, retracted before filing.** `input_tokens` is the **sum across rounds**; `request_context_tokens` is the per-request figure and peaked at **17,712 / 32,768 (54 %)**. No turn came close to the window.
- **What is left after both retractions is a real and narrower observation:** the four failures are consecutive and follow the three successes, with no configuration change between them. Whether that is conversation length, the specific document, or nondeterminism is exactly what five independent runs would separate.

### 9. ~~Throughput cliff on larger context~~ — retired, disproved by its own data
**Not a work item. Kept as a counter-example, because the obvious optimisation it invites is the wrong one.** Ordered by input size the numbers *rise*: 10,223 tok → 5.22 tok/s · 34,723 → 6.52 · 56,323 → **6.78**. Time-to-first-token does climb, but that is prompt ingestion, not generation, and **the two must not be conflated again**. Confirmed 2026-07-28: with TTFT subtracted, all twelve recorded turns run 8.9–13.6 tok/s. **Do not optimise for "less context" on this evidence.**

### 9b. Streams fail mid-turn, and the timeout is a document-length cap
`{"error": "Read timeout", "status": 504}`, logged as a WARNING and persisted nowhere, so the row read as *a slow turn*. Reporting fixed 2026-07-28 — `metrics["stream_errors"]` plus a user-facing notice. [resolvedissues.md](resolvedissues.md), *"A turn that failed read as a turn that was slow"*.

✅ **Reporting verified live on run bbde3e51, 2026-07-28**, three hours after shipping: *"⚠️ The request to the model failed after 375s — `Read timeout (504)`."* Before that day the same turn saved as `143 tokens, 0.38 tok/s` and nothing else.

**Mechanism, proposed 2026-07-28 — the timeout is not the disease.** `agent_stream_timeout_seconds` is a **per-read inactivity** timeout. If Ollama's `/v1` endpoint does not stream native tool-call arguments incrementally, the whole payload arrives in one chunk *after* the model has finished generating it, and the inactivity timeout functions as a hard cap on how long a single tool call may take to produce. At the measured 8.9–13.6 tok/s, 300 s would cap a document at roughly 2,700 tokens.

> ⚠️ **The evidence originally cited for this is not evidence. Retracted 2026-07-28.** It read *"zero `tool_call_delta` events in 35,744 log lines"*. `tool_call_delta` is emitted at **`logger.debug`** (`src/agent_loop.py`, in the SSE dispatch loop) and the root logger is set to INFO at `app.py:88` — **`app.log` contains zero DEBUG lines of any kind.** The grep measured the logging configuration.
>
> ✅ **The conclusion survived a proper test the same day, from a different direction — item 22.** One of the five document-streaming emit sites logs at INFO, and across its **32** recorded firings the document opens a median **0.069 s** before the end-of-stream tool-call event, on rounds running 34–262 s. On the 245 s round at 21:37:19 the model streamed thinking to 40.6 s, went **silent for 204 s**, then emitted open, tool-calls and stream-done inside 91 ms. **The tool-call payload materialises at the end of the stream**, which is what makes a per-read inactivity timeout act as a cap on total generation time. Detail and the one assumption still unverified: [resolvedissues.md](resolvedissues.md), *"Documents do stream into the editor"*.
>
> **Kept as a retraction anyway, because the reasoning was invalid when it was written and being right by luck is not a method.** The next reader should copy the second measurement, not the first.

| run | ttft | silence before the failure | outcome |
|---|---|---|---|
| fb5525eb | 63.8 s | **184.8 s** | ✅ 7,603-char document |
| bbde3e51 t1 | 70.1 s | **305.1 s** | ❌ 504 |
| fd0f9ba0 t3 | 66.5 s | **314.2 s** | ❌ 504 |

**Same prompt, opposite outcomes** — it is decided by how long the model chooses to make the document.

- ✅ **Raised 300 → 900 s on 2026-07-28**, in `data/settings.json` *and* the default in `src/settings.py`. ⚠️ **The saved file overrides the default**, so changing the code alone does nothing on a machine that already has the key.
- ✅ **Confirmed live in the log**: `round_start … timeout=900` from **21:34 CEST** onward; every earlier round that day logs `timeout=300`. Both of the day's 504s (16:00 at 380.7 s, 20:56 at 375.2 s — the fd0f9ba0 and bbde3e51 rows above) are **pre-change**.
- ⚠️ **And the change has therefore told us nothing yet.** Since 21:34 the longest single silent stretch is **245 s** — under the *old* cap. **Zero information gained: no run since has been long enough to test it.** The three runs owed must be deliberately long ones, or the experiment repeats this result.
- ⚠️ **This is an experiment, not a diagnosis.** If a turn still dies at 900 s the cause is a hang, not payload length, and the two want different fixes. **Do not close this until three same-prompt runs succeed.**
- ⚠️ **Raising it also scales the runaway wall-clock deadline** — `max(agent_stream_timeout * 4, 1200)` in `agent_loop.py` is now **3600 s per round**. Lower both together if that is too loose.
- **A second error class exists:** bbde3e51 turn 4 returned `All model candidates returned no substantive output (502)` at 69.8 s, on round 4 of a turn whose earlier rounds had written a document. Not a timeout. Unexplained.
- **Still open:** whether 0b12aadb (0.39 tok/s, 393 s) was the same 504. Its log window predates the check and nothing was persisted.
- ✅ **The failure notice no longer overstates the failure.** bbde3e51 turn 4 wrote v6 of a real document on rounds 1–3, then failed on round 4, and was told *"the turn did not finish, so treat it as incomplete"*. When `tool_events` is non-empty the notice now says work completed before the failure has been kept. **A failure notice that overstates the failure is still a false report** — the `"Done."` bug pointing the other way.

### 22. ~~Documents have never streamed into the editor on this setup~~ — retired, disproved 2026-07-28
**Not a work item.** `doc_stream_open` has fired **32 times since 2026-07-16**, most recently the same day this was filed. The finding it was opened on — *"zero of either in 35,744 log lines"* — grepped for SSE frames that are never logged.

**What is true instead:** the stream opens at **100 % of its round**, a median 0.069 s before the end-of-stream tool-call event, across rounds of 34–262 s. The feature works and is a no-op — the document lands whole at the end. **S4, nothing to build.** It also corroborates 9b's mechanism without depending on a DEBUG grep. Full account, the one assumption still unverified, and the ten-second check that would close it: [resolvedissues.md](resolvedissues.md), *"Documents do stream into the editor"*.

### 23. The model finishes the job in the reasoning channel, and the guard calls it silence
**Found live 2026-07-29, session 374d57b7** — a clean two-prompt session, one cloned document open, 14.5k of a 32,768 window. Not a long-conversation artefact.

Asked to *"fact check the document and correct it"*, the turn ran `web_search` → `web_fetch` → `web_search`, then a fourth round that logged `text_chars=0 tool_calls=0` after **109 seconds**. That round was not empty. It carries **3,892 characters of `thinking`**, and after a short genuine preamble the thinking becomes a finished deliverable — `## **Fact-Checked Corrections:**`, numbered findings, per-claim ✓/⚠️ verdicts, document-claim-versus-correction pairs — ending:

> *"Would you like me to create a corrected version of the document with these verified values, or would you prefer specific sections edited?"*

**It asked the user a question, and the question was never delivered.** The document was never edited because the model was waiting on an answer to something the user could not see. Re-prompted with *"edit all the temperature corrections"*, the next turn ended the same way: 1,032 chars of thinking closing on *"Let me fetch more detailed info … before making edits."*

- ⚠️ **This is being counted as item 8 and it is a different failure.** Item 8 is *the agent gathers information and then stops*; here the agent finished and the answer went out on the wrong channel. **`_gathering_only_notice` fired on both turns** — *"I ran `web_search` … stopped without producing an answer — nothing was created or changed"* — which is **true about tools and false about the answer**. The guard counts content tokens, and there were none. See item 8; the reciprocal warning is filed there.
- **Measured, not impressionistic:** 48 recorded turns end with a silent final round while carrying >800 chars of `thinking`. By a crude heuristic — thinking containing a markdown heading, `**Document claims`, or `Would you like me to` — **7 of those 48 are deliverable-shaped**. ⚠️ **A heuristic, not a classifier**; it is a floor for "how often does this happen", not a rate. The other 41 may be ordinary reasoning.
  - ✅ **Re-measured 2026-07-29 on 129 assistant rows: 74 silent-thinking turns, 9 deliverable-shaped, and still exactly 1 of them carries the guard notice.** ⚠️ **The predicate is mine, not the original's** — last `round_texts` entry blank, `len(thinking) > 800`, same three heuristic markers — so treat 48→74 as *"the shape keeps occurring"*, **not** as a measured growth rate between two comparable readings. **The load-bearing figure is the overlap, and it did not move: 1.** Item 23 remains rare, and it is still not what item 8's tally is made of.
- ✅ **It is NOT the reasoning parser, and the `/v1` retraction stands.** `src/llm_core.py`'s OpenAI-compat path takes `reasoning = delta.get("reasoning_content") or delta.get("reasoning") or delta.get("thinking")` — **the provider labels the channel and the app routes it faithfully.** `_HarmonyStreamRouter` only reclassifies once it has seen Harmony markers (`<|channel|>`), which this model never emits; zero recorded turns contain a literal `<think` tag. **The layer was checked before concluding**, per the rule in [`CLAUDE.md`](../CLAUDE.md), and the retraction in [resolvedissues.md](resolvedissues.md) survives: this is the model choosing where to write, not the parser moving it.
- ⚠️ **So do not "fix" this in the parser.** The plausible levers are model-side — the `reasoning_effort` control (⚠️ and the note claiming it cannot be sent here needs re-checking; the same *Notes* entry that said local models get no tool schemas was wrong), or a prompt rule, or an end-of-turn fallback that surfaces reasoning-channel text **when the turn produced no content at all**. That last one is report-only and is the cheapest safe option.
- **Severity is S2, not S3.** The user is told nothing was produced when a complete answer exists — work is lost silently, and the `"Done."` family is exactly the class this repo has spent the most time on.
- **Sibling of item 6, different layer.** Item 6 was the save path (`routes/chat_helpers.py`) reclassifying text *after* the stream; `round_texts` still held the original, which is how it was caught. Here `round_texts[-1]` is genuinely `''` — nothing arrived as content — so **the item 6 check (`round_texts` vs `content`) does not detect this one. Compare `thinking` against `content` instead.**

### 24. ~~Every cloned document was named "Untitled"~~ ✅ fixed 2026-07-29
`libraryImportDocument` in `static/js/documentLibrary.js` computes `baseTitle`, including the `(2)`/`(3)` dedup against existing titles in the session, and then **never put it in the POST body**. `DocumentCreate.title` defaults to `"Untitled"` (`routes/document_helpers.py`), so every clone took the default — both documents cloned on 2026-07-29 are named `Untitled`.

- **Pre-existing in Clone; "Open in new chat" inherited it** the moment that was added, because it ends by calling the same function.
- ⚠️ **It matters for item 20's step-0 runs**, which clone the same document five times: identically-named `Untitled` documents make the runs hard to tell apart in `app.db`, and the title is one of the things the model is judged on.
- ✅ **Verified live 2026-07-29, both paths.** Clone at 15:36:31 and *"Open in new chat"* at 16:02:53 each produced a document titled `Lion's Mane Mushroom (Hericium erinaceus) - Complete Guide` ~38 ms after their session, neither `Untitled`. No `(2)` suffix on either, which is correct — the dedup only compares titles **within** a session.
- ⚠️ **Verified by reading `app.db`, because this repo has no JS test harness.** That is the available standard here, not a shortcut; a JS change cannot be confirmed any other way.
- ⚠️ **The fix rode into `HEAD` inside a 120-line commit whose message described only the 3-line title change.** The rest is the *"Open in new chat"* feature, which had been sitting uncommitted in the working tree. Amended on 2026-07-29 to say so. **An uncommitted feature will attach itself to the next commit that touches its file** — item 5's failure mode wearing different clothes.

### 27. A LAN address in the prompt deletes every document tool
*"create a document with temperature and humidity data from http://192.168.0.185"* produces no document, three times over. **The model never had the tool.**

`_LOCAL_COMPUTER_REFERENCE_RE`'s third alternative — `\b(?:on|from)\s+(?!this\b|my\b|the\b|a\b|an\b)(?:[a-z][a-z0-9_.-]{1,31})\b` — is meant for named machines *(quoted from the tree 2026-07-29; an earlier paraphrase here dropped the `\b`s inside the lookahead and made the group capturing — same behaviour, wrong text. **Lift the pattern with `ast`, don't retype it.**)* (the rules text says *"Configured Cookbook server names and SSH aliases are target machines"*). It matches `on|from` followed by **any** lowercase word. Measured against the live pattern:

| prompt | | matched |
|---|---|---|
| `…data from http://192.168.0.185` | **fires** | `from http` |
| `create a document about mushroom growth from wikipedia` | **fires** | `from wikipedia` |
| `write a report on climate change` | **fires** | `on climate` |
| `create a document with data from 192.168.0.185` | ok | — *(a bare IP has no leading letter)* |

Then `src/agent_loop.py`, the `[tool-rag] Workspace file/terminal request` branch: **`_relevant_tools = set(_WORKSPACE_TERMINUS_TOOLS)`** — an assignment, not a union. The log shows RAG had already retrieved `create_document` as its top hit and this line discards it. The guard is `not _active_document_relevant`, which only protects an **already open** document; "create a document" has nothing open, so it is unprotected by construction. `_classify_agent_request` had set `domains=['documents', 'web']` — the system knew and overrode itself.

- ✅ **Confirmed by experiment, both directions, 2026-07-29.** With the IP in the message: no document tools, `write_file` instead. Split into two messages (*fetch*, then *"save this as a document"*): `create_document` fires and the document appears.
- ⚠️ **The silent failure is the dangerous one.** At 18:56 `write_file` aimed at `~/` and was refused, so item 11's guard reported it. At 19:16 the model picked `/tmp`, **succeeded**, and reported *"Wrote 1817 bytes to /private/tmp/…"*. You asked for a document, got a temp file, and were told it worked — in a directory that is periodically cleaned.
- ⚠️ **Third defect, wider blast radius: `_local_computer_rules()` is injected on EVERY turn.** Its gate is `set(relevant_tools) & _WORKSPACE_TERMINUS_TOOLS`, and that set contains `web_search`, `web_fetch`, `ask_user`, `update_plan`, `manage_skills`. **Measured: 379 of 379 logged turns — 100%.** ✅ **Re-measured 2026-07-29 across `data/logs/app.log*`: 397 of 397, still 100%** — the ratio held as n grew, so this is the gate's design and not a sample artefact. So *"Do not use personal-assistant tools like … documents …"* is in every prompt on this setup, on a model already carrying ~8.8k tokens of it (item 20).
- **This retires item 11's *"the model chose the wrong tool"* sub-item** (#11↔#27). It did not choose. Session 57dcd968, the founding session for item 11, ran the same prompt and the same `web_fetch` → `write_file` → `get_workspace` sequence.
- **Fix, in risk order.** (a) merge rather than clobber — `_relevant_tools |= _DOMAIN_TOOL_MAP[d]` for each personal-assistant domain the user's own words selected; (b) narrow the regex to configured hosts, which means it takes a host list instead of being a module constant; (c) key the rules injection on `_DOMAIN_TOOL_MAP["files"]`. **Do (c) separately and measure it** — it changes the system prompt on every turn, which is a behavioural change, not a cleanup.
- ⚠️ **Nothing tests any of it.** `_looks_like_local_computer_request`, `_WORKSPACE_TERMINUS_TOOLS` and `_LOCAL_COMPUTER_REFERENCE_RE` appear only in `src/agent_loop.py` — **zero references anywhere in `tests/`, re-confirmed 2026-07-29.** Four tests are needed, one of them the negative control that `list files on mediaserver` still gets the Terminus set.
  - ✅ **The negative control is writable today** — verified 2026-07-29 by lifting the pattern out with `ast` and compiling it standalone (no app import, no migrations): `list files on mediaserver` **fires**, so asserting it still gets the Terminus set is a live assertion and not a tautology. The same probe reproduces every row of the table above, and confirms two prompts that must *not* fire: `fact check the document and correct it` and `create a new document about pink oyster mushroom`.
  - **Lift, don't import.** `ast.get_source_segment` on the `_LOCAL_COMPUTER_REFERENCE_RE` assignment plus `eval(seg, {"re": re})` gives the live pattern with none of the import side effects `CLAUDE.md` warns about. This is the cheapest way to test any module-level constant in `agent_loop.py`.
- **Workaround until fixed:** keep the raw address out of the message that asks for a document.

### 28. ~~The model writes the tool call instead of making it~~ ✅ built 2026-07-29 — report-only
`_tool_payload_as_text_notice()` in `src/agent_loop.py`, wired ahead of `_unstarted_promise_notice` and suppressing it. A ```json fence is display text, so three turns emitted ~1.5 KB of edit payload each, ran nothing, and one claimed success. Mechanism, the mutation results and the retry-text fix: [resolvedissues.md](resolvedissues.md), *"The model wrote the tool call instead of making it"*.

- ⚠️ **NONE OF THIS IS COMMITTED — found 2026-07-29, see item 5.** The two detector functions, the retry-text fix and all 14 tests are working-tree only. **This row's ✅ describes a machine, not the repository.**
- **Tests (14), seven of them negative controls.** Measured on all 129 recorded turns before shipping: 3 hits, all true positives, 0 false positives. ⚠️ **Not yet seen firing live** — every instance predates it, and re-confirmed 2026-07-29: the notice string appears **0 times** in `chat_messages`.
- ✅ **The corpus measurement reproduces, and two filed numbers did not.** Re-run 2026-07-29 by lifting `_fenced_regions` and `_tool_payload_looks_like_edit` out with `ast` and running them over all 129 assistant rows in a hash-verified copy of `app.db`: **3 hits — 17:48:20, 17:55:34, 18:07:52, all `json`-tagged fences matching on edits/find/replace keys.** The closed-fence-only mutation scores **3 of 3**, reproducing [`CLAUDE.md`](../CLAUDE.md) exactly.
  - ❌ **The source docstrings said "2 recorded instances" and "2 of 2".** Written when only the first two existed, never revisited. Corrected in place.
  - ❌ **The `json.loads` comparison — *"1 of 3"* in `CLAUDE.md`, *"1 of the 2"* in the docstring — is not reproducible.** The mutation was never written down, and a plausible reconstruction scores **2 of 3**. **Unfalsifiable as filed**, which is worse than wrong. The direction the design rests on still holds; the number does not. Both files now say so.
- ⚠️ **Root cause open, n=1**, and it belongs to item 23's family: in the one properly-recorded empty call the FIND/REPLACE payload is in `thinking`. **Salvaging it is filed, not built** — an *acting* fix on a data-mutating path at n=1 is the class that wiped a 6,186-character document.
- ⚠️ **Do not re-derive the empty-`edits` count from `app.db`.** A naive sweep returns 9; eight are pre-2026-07-28 rows with no `full_command` key at all. **Check `'full_command' in event`.**

### 29. ~~Quoted phrases return locale filler~~ ✅ built 2026-07-29
When the model writes an exact-phrase query — `"Pleurotus djamor" "pink oyster" …` — the pinned engines return few real matches and **backfill the rest with locale-based filler**. Recorded examples, all against mushroom-cultivation queries: a Dutch casino, GitHub Desktop, a ChatGPT jailbreak repo, a hotel in Finnentrop, Psalm 37 on die-bibel.de, a Stack Overflow thread about `\0` in C, and five pages of the browser game *My Little Farmies*. **One quoted query came back 5 of 5 junk.** The user is in DE and `language=en` is pinned but the region is not, which is the likely reason the filler is German.

Fixed in `services/search/providers.py`: `quoted_phrases` / `result_has_phrases` drop results that do not contain the quoted phrase, and `strip_quotes` drives an unquoted retry when filtering empties the set. **This is not a relevance heuristic — it is the semantics of quoting.** A result that lacks the phrase the caller asked for verbatim is non-responsive.

- ⚠️ **NOT COMMITTED — see item 5.** `tests/test_search_quoted_phrase_filter.py` is a **new file**, so `git add -u` will not pick it up. Same shape as item 28's untracked test.
- **The split is measured, not impressionistic.** Replaying all 58 recorded `web_search` calls (290 results) parsed out of `tool_events[].output` in a copy of `app.db`:

  | query style | queries | with junk | junk results |
  |---|---|---|---|
  | quoted | 7 | 6 (86 %) | 18/35 (51 %) |
  | unquoted | 51 | 1 (2 %) | 3/255 (1.2 %) |

- **Replay of the shipped predicate over that corpus: 18 junk dropped, 0 false positives, 17 good kept, 255 unquoted results untouched.** Re-derive by importing `quoted_phrases`/`result_has_phrases` and re-parsing the corpus; do not trust these numbers without re-running them.
- ⚠️ **The corpus is truncated by the recorder.** `core.py` writes `result['snippet'][:200]`, so a term past character 200 is invisible to the replay, and `age` was not parsed. **51 of 58 searches are a fixed point under the current ranking**; the other 7 are most likely those two gaps, not a parse error — but that was inferred, not shown.
- **Filtering runs BEFORE the `[:count]` slice**, so dropped slots refill from further down the engine's list instead of shrinking an already-truncated window. A test pins this; it fails if the order is swapped.
- **Tests (16), three of them negative controls** — an unquoted query, a quoted query whose results all contain the phrase, and `result_has_phrases` with no phrases. ⚠️ **Reverting both changes turns 7 of the 16 red**, checked before believing them; the negative controls stay green in both states, which is what makes them controls.
- ✅ **The owed M1 run is done, 2026-07-29 21:2x.** `./venv/bin/python -m pytest` over the whole suite: `2 failed, 5768 passed, 4 skipped`, with **`tests/test_search_quoted_phrase_filter.py` 16 passed** on the pinned venv and `asyncio_mode=auto` honoured. The two failures are item 18. *(Superseded: the earlier sandboxed Linux run of `python3 -m pytest` over the search files reported 72 passed with ad-hoc, unpinned httpx/bs4/sqlalchemy/fastapi/pyotp and an unrecognised `asyncio_mode` — it could not have exercised the async paths and should not be cited.)*
- ⚠️ **Not seen live.** Every recorded instance predates the fix.
- **Also landed here: per-result `engine` attribution.** Parsing discarded SearXNG's `engine` field, so no junk result could be traced to the engine that produced it. It is now carried into the parsed result, logged per search, and copied into `web_sources` (`core.py`) so it survives in `app.db` — **`app.log` rotates, `app.db` does not.** Until the first post-fix search, **engine attribution for everything in this file rests on the `msockid=` parameter on the Victoria's Secret URL, which is Microsoft's** — i.e. on one inference, not on a record.

### 14. Web search derails on ambiguous common nouns
Recurring, and **it feeds item 2b** — the wrong-species drift there is partly downstream of this. Run eb2d0ac1 returned **"Pink (singer) — Wikipedia"** as a top result for a pink-oyster cultivation query; an earlier run ranked a Victoria's Secret "PINK" page into the same searches. Nothing in the pipeline notices. The species name is in the document title and isn't being used.

- A prompt rule now tells the model to disambiguate common-word names in queries (2026-07-28, item 20). **That is not a fix** — it is unmeasured, and the ranking problem is upstream of the model.

#### Quoted-phrase filtering → **filed as item 29** (#14↔#29)
Built 2026-07-29 in `services/search/providers.py` + `core.py`. **Item 29 is the live account** — mechanism, the measured quoted/unquoted split, the tests and the owed M1 run all live there. What is kept here is only what a second, read-only assessment added or got wrong.

- ❌ **Retracted: *"the docstring's counts do not reproduce (65 calls / 325 results / 36 of 40 dropped) and '0 false positives' cannot be settled."*** **Wrong, and instructively so.** That replay parsed the `[n] title` / indented-URL pairs out of `tool_events[].output`, which carries **title and url only**. Item 29's corpus carries the snippet as well (truncated at 200 chars). So the replay ran a **strictly stricter predicate** — one field short of the shipped one — and its extra drops were artefacts of the missing field, not false positives. **Item 29's numbers are the better measurement; the ones filed here were withdrawn within the hour.**
  - **The transferable point, which survives the retraction:** *name the corpus, not just the count.* Two honest replays of the same predicate disagreed by 2× because they read different fields, and neither reading said which. Item 29 now names its extraction; so does this retraction.
  - ⚠️ **The open question is narrower than the wrong version of it.** `result_has_phrases` requires **every** phrase, and 2 of the recorded quoted queries carry two. Whether a 200-char snippet is enough to keep a plainly-responsive result like *"Effective Pleurotus Djamor Mushroom Cultivation Tips"* under a two-phrase query is **not answerable from either corpus** — the live snippet is longer than the recorded one. **One live two-phrase search settles it. More replay does not.**
- ✅ **Checked independently and holds:** the news fallback restores the phrase list correctly, because it rebuilds `q` from the original `query` rather than from the rewritten one. The comment claiming this is accurate.
- **Untested half:** `core.py`'s `engine` → `_source_list` has no test — item 21's shape, a test stopping one call short of the user. Harmless in the UI: `buildSourcesBox` (`static/js/chatRenderer.js:948`) reads only `url` and `title`, so the extra key is inert. Unverified beyond reading; no JS harness.
- **Not observed, do not build on it:** `_QUOTED_PHRASE_RE` matches `"` only, so typographic quotes would silently no-op the feature. **0 of 65 recorded `web_search` commands contain one.**
- **Judged as a guard:** it *acts* — it changes what the model sees — but can only remove results, never write, and the unquoted retry bounds the worst case to the old behaviour. Well short of item 8's nudge. The residual risk is a *quietly narrowed* search, which is why the live two-phrase run is the one worth spending.


### 20. A 116-line block of agent rules has never reached a model
`src/agent_loop.py` assigns **`_AGENT_RULES` twice** — the detailed block first, an 851-character "## Base rules" second — so Python keeps the second and the first is dead. `_API_AGENT_RULES` is shadowed the same way. The module imports, the suite is green, and the block reads as live to anyone grepping the file.

**Re-verified 2026-07-28, still shadowed.** Do not cite line numbers for this; the two filed here (~660 / ~776) were already stale, and adding the item 11 guard moved them again. Find them with the grep, which cannot rot:

```
grep -n '^_AGENT_RULES = \|^_API_AGENT_RULES = ' src/agent_loop.py   # 4 hits, 2 per name
```

- **Item 16's shape, applied to the system prompt.** Not dead code that fails loudly — dead code that *looks* enforced.
- **Four items were arguing against rules that do not exist:** *"BIAS TOWARD ACTION … JUST DO IT"* (fd0f9ba0 refused to create, three times), *"AFTER A TOOL SUCCEEDS … no validation theater"* (item 12), *"YOU DECLARE WHEN THE JOB IS DONE"* (item 8), and — added 2026-07-29, the cleanest instance — *"Code/content >15 lines → ```create_document (NOT in chat)"* together with *"Long-form or structured writing is a document by default when the user asks to write/create/make/generate it"*.
- ⚠️ **That fourth one has a consequence beyond adherence, and it is why this item is not merely tidiness.** Session c1af9e2f, 2026-07-29 00:01 CEST: asked to *"create a new document with informations about pink oyster mushroom"*, the model called **no tools at all** and wrote a fenced markdown block into chat, titled *"Red Oyster Mushroom (Pleurotus djamor) — Sustainable Meat Alternative Feedstock Report v1"* with an executive summary addressed to *"plant-based protein manufacturers"*. **Because no document tool ran, items 2a, 2b and 3 never inspected it** — all three hang off document tools. **The turn whose content was most wrong is the turn where every S1 checker was blind.** Both rules that prohibit it are in the shadowed assignment; the live "## Base rules" contains neither.
- **Dated and confirmed on the M1:** written **2026-05-31** (`e5c99a5e`), shadowed **2026-06-09** (`ba9dc2fe`). The parent has one assignment and `ba9dc2fe` has two — **it introduced the shadowing rather than deleting anything**, which is why it reads as an addition in review. Live for nine days.

  ```
  git log -S'validation theater' --format='%h %ad %s' --date=short -- src/agent_loop.py
  git show ba9dc2fe~1:src/agent_loop.py | grep -c '^_AGENT_RULES = '   # 1, vs 2 at ba9dc2fe
  ```

- ⚠️ **Every item in this file was filed after the rules stopped applying** — the Qwen 9B work starts 2026-07-16. **Nobody has yet observed this model with the emphatic instructions in force**, so "prompt-level guidance doesn't work on the 9B" is currently unevidenced.
- ⚠️ **Do not read this as "no rules reach the model".** Weaker equivalents survive in the live "## Base rules", and `_DOMAIN_RULES` is alive and detailed. The emphatic versions — written immediately after watching a failure — are what was lost.
- ✅ **Measured properly 2026-07-30 — and the result inverts the first reading.** Nine sessions, identical prompt verbatim, each a new chat with a clone injected (`[doc-inject] found by ID`, nine distinct ids): **duplicate rule 6 of 6**, **title rule 6 of 6 clean**, **item 12's rule 6 of 6** (no `manage_documents` after a successful document tool). The single refusal, `c9c2b615`, is the run whose open document had been replaced with another chat's content **one second before the prompt** — item 30, so it is discarded rather than counted. One further session had no document open at all and is not a protocol run.
  - ⚠️ **The `1 of 4` baseline below cannot be re-derived and is partly wrong.** Across **every document ever recorded**, exactly **one** title matches the rule's regex — `Pink Oyster Mushroom (Pleurotus djamor) Growth Phases Guide - Fact Checked 2026-07-28`, in session **`c1af9e2f`**. It is filed below against `eb2d0ac1`, whose only document is from **2026-07-19**, nine days before the rule existed. *"Two violations from two opportunities"* is **one violation, counted twice across the UTC/CEST two-hour gap** — `app.db` is naive UTC, `app.log` is local. **Re-derive the baseline before comparing anything to it.**
  - **So the rules do reach the model and mostly steer it.** `ef460706`'s thinking quotes the duplicate rule while complying — *"since they asked for one anyway … I'll just proceed"*. Whether the *shadowed* block would do better is still unmeasured; this measures the rules that are live.
- **First adherence data, 2026-07-28: 1 of 4.** ✅ bbde3e51 turn 1 quoted the new create rule in its own reasoning — *"they're asking for one anyway - I should follow their request and create it as instructed (per the duplicate handling rule)"* — and proceeded. ❌ Turn 2, same prompt eight minutes later, refused and offered options instead. ❌ eb2d0ac1 titled a document *"…- Fact Checked 2026-07-28"*, which the new title rule prohibits outright. ❌ **And again at 21:34 CEST the same evening** — a second document titled *"… Growth Phases Guide - Fact Checked 2026-07-28"*. **Two violations from two opportunities on the one rule with a mechanical test.** So the rules reach the model and sometimes steer it, and are not reliable. Four samples; treat as a first reading, not a rate. **Measuring this properly is still the cheapest open experiment** — see the top of the Next list.
- **Score it mechanically, not by reading replies.** Every rule added on 2026-07-28 has a predicate in `app.db`: the duplicate rule → did `create_document` appear in `tool_events`; the title rule → does `documents.title` match `Fact Checked|Corrected|\d{4}-\d{2}-\d{2}`; item 12's rule → did `manage_documents` run *after* a successful document tool; item 8's → did the turn end on a colon or on a round with 0 chars and 0 tool calls. **The same five runs settle items 20, 12 and 8's live-rule question at once**, which is the leverage argument for doing it first. Run them back to back with no restart: `data/settings.json` changed mid-evening on 2026-07-28 and split that day's runs into two populations.

**The protocol, corrected 2026-07-28 after session c1af9e2f ran it wrong.** That session put eleven prompts in one chat, and the result is uninterpretable for exactly the reason below. Full account under item 8.

1. **A new chat per run — five chats, not five prompts in one.** Otherwise run 5 sees runs 1–4's conversation *and* their documents, and conversation length becomes a second variable nobody is controlling. ⚠️ **A "new chat" that has never been sent leaves no row in `sessions`** (it is a `_pendingChat` held in the frontend until the first message), so *"did I actually start a new chat"* cannot be answered from the record afterwards. Confirm it in the sidebar before typing.
2. **Use the library's "Clone", never "Open".** ⚠️ **"Open" is what has been merging the runs, and it is deliberate, not a bug.** `libraryOpenDocument` in `static/js/documentLibrary.js` does `if (doc.session_id !== currentSessionId) await selectSession(doc.session_id)` — **opening a document switches you into the chat that created it.** There is no "open in a new chat" affordance, and switching sessions clears the editor selection (`sessions.js`, `documentModule.clearSelection`), so a document cannot simply be carried into a fresh chat. This is the mechanism behind eb2d0ac1 taking a new prompt nine days after it was created, and 57dcd968 one day after.
   ✅ **Added 2026-07-29: "Open in new chat" in the library's ⋮ menu** (`libraryOpenInNewChat`) does exactly this in one click — `createDirectChat` → `materializePendingSession` → `libraryImportDocument`. Deliberately only in the ⋮ menu, not the card footer, which carries a note to stay at Clone + Open. ⚠️ **Unverified — this repo has no JS test harness** (`package.json` has one devDependency and no runner), so it is `node --check`-clean and reviewed against the exported `sessions.js` API, nothing more. **Confirm the first run's `[doc-inject]` line before trusting a set of five.**
   Doing it by hand is the same two steps: **new chat first, then Clone into it.** Order matters — cloning first copies into the old session, which is the behaviour being avoided.
3. **Verify each run got a document** before scoring it: `grep 'doc-inject' data/logs/app.log*` should show five `found by ID` lines, **one per run and each with a DIFFERENT id** — a clone is a new document. (An earlier version of this step said "the same id five times", which is right for "Open" and wrong for the protocol that actually works.) **This is the step that catches a run where the precondition silently did not hold.**
   - Cloning is also the cleaner control: five independent copies sharing no version history. And because each run is a fresh session, the title-dedup in `libraryImportDocument` sees no existing titles, so **every clone keeps the identical original title** — no `(2)`/`(3)` drift to become a variable of its own.
4. **Identical prompt text, five times.** Not paraphrases.

- ⚠️ **The five runs need a document OPEN; item 2a's live turn needs the editor CLEAR.** Opposite preconditions — do not try to collect both in one session.
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

Session 57dcd968 ran `web_fetch` → `write_file` → `get_workspace` and saved only the 175-character preamble. Diagnosis, the corrected reading of that turn (`write_file` **failed**; the entry had it backwards), the coverage argument and the corpus sweep: [resolvedissues.md](resolvedissues.md), *"Non-document tools reported nothing at all"*.

- ✅ **Verified live 2026-07-29, session ae223b4c.** `web_fetch` → `write_file` (`exit=1`, *"path '~/…' is outside the allowed roots"*) → `get_workspace`, and the user was told: *"⚠️ `write_file` failed — …"*. **Near-identical to session 57dcd968**, the founding case, which saved a 175-character preamble and nothing else. Same prompt, same tool sequence, same failure, now reported.
- ❌ ~~"Still open, and separate: the model chose the wrong tool"~~ — **retired 2026-07-29, it was never a choice.** A LAN address in the prompt strips every document tool before the model sees them; see item 27, reciprocal (#11↔#27).
- ⚠️ **Known gap, not an oversight:** the five self-reporting tools (`manage_notes`, `manage_calendar`, `manage_tasks`, `list_emails`, `read_email`) are excluded, so a `manage_notes` **create** stays unreported. Fixing it means reordering the end-of-turn block.
- **Still open, and separate: the model chose the wrong tool.** Asked for "a document" it wrote a workspace `.md` file, so items 3, 2a and 2b never applied either. **Do not fold the two together** — the reporting gap was real regardless.
- Item 8's reverted nudge is why any *acting* fix must bound what the retry can write. A reporting fix has no such constraint, which is why this one could ship on test evidence.

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
- ⚠️ **A second instance of the shape was found 2026-07-29 — item 25**, reciprocal (#16↔#25). There the assertion is pointed at a live function and still proves nothing, because the fixture's location satisfies it independently of the mechanism. **The audit below looks for zero-caller functions; it would not have caught item 25.** A test can be vacuous with a perfectly well-called function underneath it, and the only way that surfaces is running the function outside the test.
- Fixed by making the orphan a thin wrapper over `_resolve_public_ips`, so the existing assertions exercise the live path and the two cannot diverge again.
- **Open:** a cheap first pass is to flag module-private functions with zero non-test references. Upstream added SSRF checks to `services/memory/skill_importer.py` independently: a good sign, and more surface for the same divergence.
- ⚠️ **The `_PRIVATE_NETWORKS` half of this item is a false lead. Audited and closed 2026-07-28 — do not re-walk it.** Four copies exist and their contents genuinely differ (`services/search/content.py` 9 entries, `src/webhook_manager.py` 8, `routes/model_routes.py` and `src/model_context.py` 3 each plus the Tailscale CGNAT block). **None of it is a hole.** Two of the four are endpoint *classifiers* — "is this endpoint on my LAN" — not guards. Of the two guards, the missing `0.0.0.0/8` in `webhook_manager` is covered by the stdlib predicates above the list (`addr.is_private or is_loopback or is_link_local or is_reserved or is_multicast or is_unspecified`), which subsume its whole tuple; the list there is dead weight, not a gap. **Counting the copies gives four; reading the callers gives two guards that agree.** The `100.64.0.0/10` difference is deliberate — `content.py` runs a two-tier design with `_GATED_PRIVATE_NETWORKS` so `web_fetch` can reach the LAN on purpose, which is what the 2026-07-27 fix was for.
  - **The transferable point:** this item's own evidence was a `grep -l` count, and a count of files is not a count of behaviours. Same failure as item 11's tool *sequence* versus tool *result*, and 9b's log grep — three in one day. **The audit worth keeping is the zero-non-test-references pass**, which is about callers by construction.
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

### 25. A path-confinement test passes without the mechanism it tests
`tests/test_tool_path_confinement.py::test_extra_roots_opt_in` builds its fixture under `tmp_path`, patches `tool_path_extra_roots` to include it, and asserts the path resolves. **It resolves either way.** `_tool_path_roots()` already contains `/tmp` and `$TMPDIR` (`src/tool_execution.py`, the `# $TMPDIR — per-user temp root on macOS` block), and `tmp_path` lives in one or the other on both platforms. The patch is decoration; there is no negative control asserting rejection *without* the opt-in.

- ✅ **Confirmed on the M1, 2026-07-29.** With the mechanism removed — `return_value=[]` in place of `[str(extra_dir)]` at line ~205 — the file still reports **`25 passed`**. The test does not depend on the setting it is named after.
- **Measured, not read.** Importing the real `src.tool_execution` with `DATABASE_URL=sqlite:///:memory:` and calling `_resolve_tool_path` on a `tmp_path`-shaped location resolved it **with no patch applied**. The mirror-image control passed too: the same probe against a repo-root location was `REJECTED` without the extra root and `ALLOWED` with it. *(Those two ran in a Linux sandbox with a faked `TMPDIR`; the macOS run above is what settles it.)*
- **This is item 16's shape and the pair is reciprocal (#16↔#25).** There it was a security assertion pointed at an orphaned function; here it is a security assertion that holds regardless of the mechanism. **Both were green throughout.** The difference worth keeping: item 16's was found by reading callers, this one only by *running* the function.
- **Fix is a negative control, not a rewrite:** assert the same path is rejected when `tool_path_extra_roots` is empty. That is the assertion the test's own docstring already claims to make.
- ⚠️ **Do not "fix" it by moving the fixture out of `tmp_path` without checking the roots list first** — see item 26, where the same coupling runs the other way.

### 26. Test litter in the repo root, kept invisible by `ignore_errors=True`
`tests/test_chat_helpers.py:176` (`_manifest_test_dir`) builds fixtures at `<repo root>/tmp_pytest_probe/<name>-<uuid4>`. Both callers clean up in a `finally` — with `shutil.rmtree(root, ignore_errors=True)`. **The cleanup ran, failed, and the flag discarded the failure.** Four directories accumulated from two runs on 2026-07-28; `uuid4()` means every run adds rather than reuses.

⚠️ **State refreshed 2026-07-29 — the four subdirectories are gone, deleted on the M1 where the mount restriction does not apply. `tmp_pytest_probe/` itself survives, empty, and is still not in `.gitignore`.** So the visible symptom is cleared and **the defect is not**: the next suite run on a machine that cannot unlink re-creates it. **Do not read the empty directory as a fix.**

- **Reproduced under the sandbox mount:** `rmtree(ignore_errors=False)` raises `PermissionError [Errno 1] Operation not permitted`, and with the flag on, the tree survives silently. The mount permits `create` and refuses `unlink` — the same restriction `CLAUDE.md` records for `.git/`.
- **Why it is not merely untidy:** `tmp_pytest_probe/` is not gitignored, so it appears as untracked in every `git status` — **the one check item 5 depends on to notice untracked files.** The pair is reciprocal (#5↔#26).
- ⚠️ **The location is load-bearing — check before moving it to `tmp_path`.** `DATA_DIR` is `<repo>/data`, not the repo root, so the fixture currently sits outside every default root, which is exactly what makes the test's `tool_path_extra_roots` patch discriminate. Under `tmp_path` it would stop discriminating and the test would go green for a weaker reason — item 25's defect, newly introduced.
- ⚠️ **And if you replace `_tool_path_roots` to keep it honest, `os.path.realpath` the root.** The real function normalises its own inputs; a replacement bypasses that, and on macOS `tmp_path` sits under the `/var` → `/private/var` symlink. Demonstrated: without `realpath` the same path is `REJECTED`, with it `ALLOWED` — **a macOS-only failure, which is item 19's class.**
- **Not a house pattern:** `test_chat_helpers.py:176` is the only test in the suite that *writes* into the repo root; every other `parents[1]` use reads source for AST assertions, and 134 test files already use `tmp_path`.
- **Related, lower priority:** `tests/test_code_nav_tools.py:39` carries the same `ignore_errors=True`, but writes to `/tmp` — deletable on macOS, and unwritable in a Linux sandbox, so it fails loudly instead of leaking. Its `dir="/tmp"` choice is **deliberate and documented in the fixture** (the opposite requirement: it needs to be *inside* the allowlist). Its line 8 `DATABASE_URL` pointing at a file-backed `/tmp` db is inert while `tests/conftest.py:18` sets `:memory:` first, and only bites under `--noconftest`.

### 19. ~~Five tests failed on macOS only~~ ✅ fixed 2026-07-28, verified live
Four `AF_UNIX path too long` (macOS caps `sun_path` at 104 bytes) plus `test_glob_confined_e2e`, whose assertion contradicted its own comment and passed on Linux by luck. **Neither was an application bug**; no confinement hole. [resolvedissues.md](resolvedissues.md), *"Five tests failed on macOS only"* — which also records why a Linux run cannot substitute for a macOS one.

---

## Notes & constraints
Settled. Recorded so they don't get re-litigated. **Working method lives in [`CLAUDE.md`](../CLAUDE.md); this section is facts about the system.**

- **Per-round thinking suppression isn't currently possible.** `reasoning_effort:"none"` needs `tools and _is_qwen_thinking_model and _agent_thinking_disabled()` (`llm_core.py:2276`). `agent_disable_thinking` is `False`, **and** `tools` is always `None` on this endpoint — so flipping the setting changes nothing. Needs an override plumbed through `stream_llm`.
- ~~**Local models get no tool schemas at all**~~ — **retracted 2026-07-28, and it was never true of this model.** The rule reads `all_tool_schemas` is empty unless `_is_api_model`, which is correct; what is wrong is the assumption that a local model is not `_is_api_model`. `qwen3.5:9b-32k` resolves **`_is_api_model=True`** — `src/agent_loop.py` takes `any(h in endpoint_url for h in _API_HOSTS) or _model_supports_tools`, and the endpoint is marked as supporting tools. Every round in `app.log` since **2026-07-15** logs `native_tools=True tools_sent=24..31`, several hundred of them. **There is a channel:** `tool_choice` is plumbed through `stream_llm` (`tool_choice_none`, `src/llm_core.py`), and `_force_answer` already ships the narrowing move — it sets `all_tool_schemas = []` to force an answer.
  - ⚠️ **This one was load-bearing.** It is the stated reason item 8's active half had to be a *text nudge*, and that nudge wiped a 6,186-character document. **A bounded retry can restrict the schema list instead of instructing the model** — which is the shape item 8 asks for ("bound what it can do"), and it was available the whole time.
  - The same wrong claim is duplicated in a docstring on `_doc_edit_retry_directive`; corrected there too.
- **Don't widen `_ody_doc_finetune_mode`.** It gates tool narrowing and `tool_choice_none` as well as the loop break. The reporting path was split out of it deliberately.
- ~~**The redundant `user` document version is cosmetic.**~~ **Retracted 2026-07-19.** It was the visible edge of the duplicate-`doc_update` data loss in item 1.
- **`app.db` lags live activity — "the newest row" is not "the last turn".** Rows are written on `save_sessions()`. A query at 15:20 returned a newest row of 12:36 while fd0f9ba0 had run until 14:00. **`data/app.db-journal` on disk is how you tell the app is running**, and while it is, anything else opening the tree gets `disk I/O error`. Copy the file and query the copy.
- ⚠️ **`round_texts` was absent from every turn that called no tools** — nested under `if tool_events:` in `_compute_final_metrics`. **That is the field separating item 6 from item 8**, so it was missing from exactly the turns where the question arises. Fixed 2026-07-28. **Rows written before then cannot be classified retroactively** — the same limitation items 10 and 17 carry.
- **Timestamps in `app.db` are naive UTC while `ls`/`stat` and `app.log` report local CEST.** Cost a two-hour error that made three post-fix sessions look like they predated the fix. Full statement in [qwensetup.md](qwensetup.md), *"Reading `data/app.db` when debugging a run"* — kept there because that is where you are standing when it bites.
- **Cross-references rot when items are renumbered**, because every edit to these files comes from a different session. Three were found wrong on 2026-07-27; a fourth, in `tests/test_doc_report_gate_split.py`, on 2026-07-28. **All four were one-directional.** Every surviving reference *within* this file is reciprocal — #6↔#10, #7↔#8, #2↔#14, #8↔#20 — so renumbering one visibly breaks the pair. **A cross-file citation that nothing points back at is the fragile kind.** Before renumbering, grep `--include=*.py --include=*.js` for `todo.md` as well as the docs; source comments are cross-references too, and there are more of them.
- **On guards that write.** A guard that only *reports* can ship on test evidence. A guard that makes the model *act* can destroy data, and its tests must bound what it can do, not merely assert it exists. Item 8's reverted nudge passed every test written for it.
- **A "superseded" banner does not retire a document — deleting the prose does.** `KNOWN_ISSUES_debug.md` carried a banner saying its leading theory was wrong; an agent read the banner and argued from the body underneath it anyway, the third trip down a road two retractions exist to close. **Prose that reads like a live finding will be treated as one, however it is framed.** When an item is retracted, cut the reasoning and keep the conclusion.
