# Open items — Qwen 9B setup

Setup and config: [qwensetup.md](qwensetup.md). Closed investigations: [resolvedissues.md](resolvedissues.md). Settled constraints that are *not* work items are at the bottom. *(These three files were four until 2026-07-28; `llmSetup.md` was a redirect and is gone.)*

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
| **2a** | **Transcription doesn't match the source** | **S1** | **S** | **open — next** | — |
| 2b | Fact-check inverts ground truth | S1 | M | open | — |
| 3 | Documents contradict themselves | S1 | M | partly re-diagnosed; editor half fixed | tests |
| 4 | ~~Retired 4B still on the research path~~ | S1 | XS | ✅ done | live |
| 5 | ~~Uncommitted work — since 2026-07-12~~ | S2 | XS | ✅ **committed 2026-07-28** — 7 commits, 47 files | **live** |
| 6 | Answer text lost to the reasoning channel | S2 | M | lead only — **#10 landed, now unblocked** | — |
| 7 | ~~Closing summary under-reports / stays silent~~ | S3 | S | ✅ fixed | **live** — skipped-edit report, 2026-07-27 |
| 8 | Agent gathers information, then stops | S3 | M | reporting fixed; **active half reverted** | **live** (reporting) |
| 9 | ~~Throughput cliff: 2.84 → 0.39 tok/s~~ | — | — | ⊘ **retired — disproved by its own data** | n/a |
| 10 | ~~Failures aren't replayable~~ | S4 | XS | ✅ **fixed 2026-07-28** — `full_command` persisted | tests (7) |
| 11 | ~~Retry-at-failure covers only document tools~~ | — | — | ⊘ **retired to a watch note — no instance** | n/a |
| 12 | Wasted verification rounds | S4 | XS | open — still reproducing | — |
| 13 | Terminal access-log noise | S4 | S | open — got in the way twice | — |
| 14 | Web search derails on ambiguous common nouns | S3 | M | open — recurring | — |
| 15 | ~~`web_fetch` failure rate on cultivation sources~~ | — | — | ⊘ **folded into 2 — premise already answered** | n/a |
| 16 | SSRF guard tests covered an orphaned function | S4 | S | one instance fixed; **audit open** | tests |
| 17 | ~~Cache hits are indistinguishable from live fetches~~ | S4 | XS | ✅ **fixed 2026-07-28** — `cached` + age | tests (6) |
| 18 | Two CAS tests have never passed | S4 | S | open — found 2026-07-28 | n/a |
| 19 | ~~Five tests fail on macOS only~~ | S4 | XS | ✅ fixed 2026-07-28 | **length half reproduced on Linux**; symlink half by path arithmetic — **awaiting one M1 run** |

**Numbers are never reused.** A retired item keeps its number and a `⊘` row, because renumbering has silently rotted cross-references four times (see *Notes & constraints*). Item 2 split into 2a/2b rather than becoming 2 and 19 for the same reason.

> **Next, in order.** Items 5, 10, 17 and 19 closed on 2026-07-28, so the work is committed and the record of a run is now interpretable. Ordering follows leverage.
>
> 1. **Item 2a** — the transcription diff. The only S1 with fresh evidence and no work done, cheaper than 2b, and it generalises to every "turn this data into a table" turn.
> 2. **Item 3's real gap** — `find_stale_values` has exactly one production caller, `document_tools.py:765`, inside `EditDocumentTool`; `update_document` bypasses the lint entirely. Note the interaction: item 7's live guard promises *"I'll rewrite the document in full instead of patching"*, which routes every edit failure into the one path with no lint.
> 3. **Item 6** — unblocked now that #10 persists `full_command`, but **only for runs recorded after 2026-07-28**. Needs a fresh reproduction; the three 2026-07-27 runs cannot be re-examined.
> 4. **Item 13** — friction, but it has obstructed debugging twice and all three cited call sites are verified unchanged. Cheaper to fix than to work around a third time.
>
> **First, though: run the full suite on the M1.** Items 19 and 18 both hinge on it. Expected `2 failed` (item 18 only), down from 7. Item 8's active half stays parked — read its ❌ bullet before touching it.

---

## S1 — wrong output the user trusts

### 1. ~~Autosave is reverting AI edits~~ ✅ fixed and verified live 2026-07-19
**Not autosave, and not the compare-and-swap** — both behaved correctly throughout. A single document tool call emitted `doc_update` **twice**; the second delivery re-entered `handleDocUpdate`, hit the #2484 guard, and `exitDiffMode(true)` restored the pre-edit buffer and PUT it back under the now-fresh `base_version`, so the destructive write passed CAS legitimately. Full diagnosis and the three-layer fix in [resolvedissues.md](resolvedissues.md).

**Verified properly, unlike the two previous times this was closed.** Every client-side write in `app.db` was classified:

| Era | REVERT (byte-identical to an earlier version) | BLEND (matches no stored version) |
|---|---|---|
| pre-fix | **20**, across 10 documents and several days | 1 |
| post-fix | **0** | 2 → then fixed separately, see item 3 |

Five consecutive post-fix sessions, including one edit changing 154 lines — the largest qualifying edit in the dataset and exactly the shape that used to revert every time.

### 2. Wrong numbers in documents the user trusts — 2a transcription, 2b ground truth
*Split 2026-07-28; the two halves are set out in the table further down this entry. Everything below was filed as one item.*

#### 2b. The fact-check step inverts ground truth
**The only S1 with no work done on it.** Two consecutive runs re-introduced cold shock on a tropical species. 009660d2 stated it outright: *"pink oysters prefer slightly cooler than other Pleurotus species during fruiting"* at 65–70°F, with *"Cool down by 3-5°F from spawn temp"*. That is backwards — *P. djamor* is the thermophilic one — and it's the failure that retired the 4B, now produced twice by the 9B. Both documents title themselves "Fact Checked & Corrected", which is the damage: wrong chamber setpoints wearing the authority of verification.

**The more it fact-checks, the worse it gets — measured 2026-07-19:**

| Run | Prompt | Result |
|---|---|---|
| acba4766 | plain "create a document" | **closest to correct** — 24–28°C, CO₂ <1000 ppm |
| 4d97aa60 | "create with **fact checked** infos", 4 web fetches | **worst yet** — fruiting 14–21°C, ">26°C may reduce…", no CO₂ at all |
| baac5d34 | create, then "fact check and correct" | 4 edit rounds, corrections partly destroyed by item 1 |

14–21°C is the *P. ostreatus* range on a tropical species, and 26°C — flagged as too warm — is squarely optimal. Asking for verification up front produced more confidently wrong numbers than not asking at all, after four source fetches. **The retrieval step is not neutral; it actively drags the answer toward the wrong species** — and item 14 is part of why.

**Fix:** the ground truth is already written down in [resolvedissues.md](resolvedissues.md) ("4B retired") — colonization 24–29°C, fruiting 20–30°C **no cold shock**, RH 85–95%, CO₂ 500–800 ppm at 3–6 ACH. Make it a fixture plus a checker that flags a document contradicting it. Generalises to "assert a document doesn't contradict a known-facts file".

#### 2a. Transcription doesn't match the source it was handed

**2026-07-27 — the same severity with no retrieval involved at all.** Run 31e0af64 fetched one clean JSON document (40 history points, complete, verified byte-exact against the source) and asked for a table. No search, no fact-check, no ambiguous nouns — item 14 cannot be blamed. Four defects landed in the document anyway:

- **39 of 40 rows transcribed correctly; row `s=360` lost a column** — `| 360 | 87.4 | 26.9 |`, temperature `24.5` dropped, everything shifted left.
- **It noticed, misdiagnosed its own error, and burned a round on it.** Thinking: *"I notice there's an error at time=360 where I accidentally copied values incorrectly (t:24.5, h:87.4 swapped with dp)"* — nothing was swapped, a value was missing. It then sent `edit_document` with a FIND block matching the **correct** row it had never written. No match, no-op.
- **Time axis wrong by ~57×, and self-contradictory:** *"~19 hours (~7.5 days of sampling)"* for 40 points at 30 s = **20 minutes**. The source field is `"s"`, seconds of uptime, with no unit in the payload. The document's column is headed "Time", unitless.
- **A raw inverted register reported as a metric:** *"duty cycle: 252"*. 252 is the PWM value after a BC547 inversion — 255 is off. Actual power was the `dp` field, 5.1 %. Anyone reading that infers near-full power.
- Two of three sensors absent from the document although present in the JSON.

**Why this sharpens the item:** the failure is not "the model retrieves bad sources". It is that a 40-row verbatim transcription at ~6.8 tok/s is near the edge of what this model does reliably, and there is no check that the output matches the input it was handed. A row-count-plus-cell diff against the source is cheap and would have caught three of the four. Complements the known-facts checker above rather than replacing it.

**Split into two independent pieces, 2026-07-28 — do 2a first.** They share a severity and nothing else: different inputs, different mechanisms, and 2a is both cheaper and more general.

| | Piece | What it checks | Effort |
|---|---|---|---|
| **2a** | Transcription diff | Output matches the input the model was *handed* — row count, then cell-by-cell | S |
| **2b** | Known-facts fixture | Output doesn't contradict a file of settled ground truth | M |

2a needs no domain knowledge, catches three of the four defects in 31e0af64, and generalises to every "turn this data into a table" turn. 2b is the one that catches cold shock on a thermophile, and its ground truth is already written down in [resolvedissues.md](resolvedissues.md) under *"4B retired"*.

**Retrieval quality is not the bottleneck — folded in from the old item 15.** Roughly a third of `web_fetch` calls fail on the sites this task reaches for: `thesporedepot` HTTP 403 repeatedly across days, `shroomstop.ca` 404, `kvkwestkhasihills.nic.in` non-HTML. The model moves on correctly each time. Worth knowing when a fact-check turn ends empty-handed, but 31e0af64 failed on a single clean verified source, so **neither 2a nor 2b should wait on measuring this.**

### 3. Partial edits leave documents contradicting themselves
Run 127d32b0: 8 edits fixed the prose and missed the summary table, leaving four CO₂ thresholds and three colonization durations in one document.

> **Partly re-diagnosed 2026-07-19 — a share of this was the editor, not the model.** The diff-review overlay was writing documents containing **both** the pre-edit and post-edit text for the same section. Doc `92f3b2a0` v3: twelve such regions from a *single* Accept click, including a garbled `5-1°C (68-F)` line restored next to its own correction. Cause: an un-reviewed chunk was treated as rejected, and `_resolveChunk` persisted that reading on every click. Fixed — see [resolvedissues.md](resolvedissues.md).

**How much of the model-caused problem remains is now an open measurement rather than a known quantity.** The last clean run still showed the lint firing correctly (*"`20-30°C`, `3-7 days` were corrected in one place but still appear elsewhere"*), so the model half is real — just not the whole story.

- Detection exists (`find_stale_values()`), surfacing was fixed 2026-07-18. **Prevention doesn't** — the model is never asked to fix what the lint finds.
- **Gap:** the lint runs only inside `EditDocumentTool` (`document_tools.py`). A full `update_document` rewrite bypasses it entirely.

### 4. ~~The retired 4B is still live on the research path~~ ✅ done 2026-07-19
`research_model` is now `qwen3.5:9b-32k`; `_RETRY_CONTINUATION_RE` recognises document/research context. See [resolvedissues.md](resolvedissues.md).

## S2 — silent loss

### 5. ~~Everything since 2026-07-12 — uncommitted~~ ✅ committed 2026-07-28
Seven commits, `825bcc1`…`e216313`, 47 files. Identity set **repo-locally** (`git config --local`), so nothing reached a global config; nothing pushed. Full account — including the two bookkeeping defects that had made this item's own "everything is protected" claim false — in [resolvedissues.md](resolvedissues.md), *"Sixteen days of uncommitted work"*.

**Still live, and not closed by the commit:**

- ⚠️ **Branch `dev` is 4 commits behind `origin/dev`.** The tree is clean now, so `git merge origin/dev` is safe. Do it before writing more code, not after.
- ⚠️ **`data/app.db` is in no commit and never will be** — `data/` and `*.db` are both gitignored. It holds every run this file reasons about: the 20 reverts, the `round_texts` arithmetic, the cache-hit contradiction. **`outputs/snapshots/odysseus-restorepoint-*.tar.gz` is the only thing protecting the evidence base**, and pushing to a remote would not change that. Committing protects the code; the tarball protects the findings.
- **Ignoring a file is not protecting it.** `git clean -fdx` deletes ignored files and nothing points at them, so an ignored file is *less* safe than an untracked one — it has lost the `??` line that would remind you it exists. Only a commit makes content recoverable by path. `COMMIT_PLAN.sh` is therefore left untracked-but-not-ignored: it is obsolete now that it has run, and it stays visible rather than silently deletable.
- **A stale zero-byte `.git/index.lock` blocks every git operation, silently.** The 2026-07-18 instance ran for 13 hours and is the likely reason two weeks went uncommitted; two more appeared on 2026-07-28 from a process that could not unlink its own lock. **Check `ls .git/index.lock` before believing git itself is broken.**
- ✅ `searxng/` gitignored — 138 MB with a nested upstream `.git` plus its own venv, one `git add -A` from being swallowed. Audited before staging: no credentials, no personal paths, `data/` already excluded.

**Recovering the two files deleted as superseded.** Both were staged-but-never-committed, which is the fragile state:

- `llmSetup.md`, 2026-07-28: `git cat-file -p 93bdbbb7 > docs/llmSetup.md` (24 lines, the mapping-table version). Its worktree copy differed from its staged blob — `746a08ef`, an older 7-line stub — so `git hash-object -w` was run on it *first*; otherwise deleting it would have destroyed the only copy anyone had read. It survived only as a redirect for source citations, and **its stated exit condition undercounted them by two**: seven citations existed, not five. Delete a redirect by grepping, not by trusting the count written inside it.
- `KNOWN_ISSUES_debug.md`, 2026-07-27: `git cat-file -p b570b679 > KNOWN_ISSUES_debug.md` (62 lines, the pre-trim body). The obvious command does **not** work — it was renamed with `git mv` before deletion, so `git show :KNOWN_ISSUES_debug.md` returns nothing, and `git rm --cached` then dropped that index entry too. `git fsck --lost-found` misses it as well, because a stale index generation still references it.

  **General trap: for a staged-but-never-committed file, renaming or re-staging invalidates every path-based recovery route, and there is no commit to fall back on.** Run `hash-object -w` before deleting, and write the hash down.

### 6. Answer text can be lost to the reasoning channel
Run f14a8f52, exact from `app.db`: `round_texts[0]` was 300 chars, `thinking` was a byte-for-byte 219-char **prefix** of it, and the saved message is the remaining 79 chars. The reply starts mid-list at "2.", and the model's most important question — *"1. Where is the existing HTML, CSS and JavaScript located?"* — is absent from history entirely.

**This is a lead, not a diagnosis.** "The reasoning parser eats the answer" is the hypothesis [resolvedissues.md](resolvedissues.md) already retracted once; that retraction was correct for those runs. The arithmetic above shows the mechanism is real *somewhere*. Confirming it needs the raw stream. ✅ **Item 10 landed 2026-07-28, so this is now unblocked** — document tool events carry `full_command`. Note the limit: only runs recorded *after* that date are replayable, so the three 2026-07-27 runs counted below cannot be re-examined this way and a fresh reproduction is needed.

**Count only, 2026-07-27.** Three further runs with `round_texts` all-zero and a complete, correct prose summary sitting in `thinking`: 2ebdd27a `[0,0]`, 4eb184ae `[0,0]`, 31e0af64 `[0,0,0,0]`. Recorded as *frequency*, deliberately without a mechanism — the retraction above exists precisely because these look like misrouting and the earlier ones weren't. Worth noting the retraction is load-bearing: it stopped a re-investigation of the `/v1` thinking path on 2026-07-27, which would have been the third time down that road.

## S3 — visible task failure

### 7. ~~Closing summary under-reports, and sometimes says nothing~~ ✅ fixed 2026-07-19 — failure branch live 2026-07-27, success branch tests only
**Two defects. The one that wasn't filed was the expensive one.**

*Under-reporting*, as filed: `_ody_doc_tool_info` was replaced by each successful call, so a turn with several edit rounds reported only the last. baac5d34 applied 5+1+3+1 = 10 edits and reported *"1 edit applied"* — tenfold under-reporting that read as near-total failure.

*Silence*: `_closing_doc_summary` only fired when the response was **empty**, assuming non-empty meant the model had summarised. It doesn't — this model opens with its intent before calling any tool. Run 4e217ae0 turn 2 applied **4 edits and reported none of them**. Told nothing had happened, the user asked again 16 seconds later, and the repeat turn spent 162s producing nothing. **Item 7's silence caused an item 8 failure.**

Fixed: `applied`/`skipped` accumulate (`version`/`title`/`stale_values` take the latest, since they describe the document as it now stands); a preamble is detected **positionally** — text written before the tool ran cannot describe what the tool did — and the report is appended rather than replacing the model's words. Both the finetune loop break and end-of-turn handle all three cases. Tests: `tests/test_doc_closing_summary_accumulates.py`.

**✅ Seen live 2026-07-27** — the failure branch, at least. Run 31e0af64 ended on an `edit_document` whose single FIND block matched nothing, and the user was told: *"I couldn't apply the edit — **the document is unchanged.** The edit tool rejected 1 attempt this turn (No edits applied — none of the FIND blocks matched the document content (skipped 1)). Ask me to try again and I'll rewrite the document in full instead of patching individual passages."* Accurate, actionable, and it correctly did **not** claim success — the exact case that used to surface as `"Done."`. `round_texts` was `[0,0,0,0]`, so every word of that came from the guard.

**Still unverified: the accumulation path.** A turn with several *successful* edit rounds reporting *"N edits applied across M rounds"* has not been observed. Scope this as "failure branch live, success branch tests only" rather than promoting the whole item.

### 8. The agent gathers information, then stops
Four attempts at one task in 16 minutes, **zero files produced**. 0b12aadb found `martha9_1.ino`, read 10,035 chars, correctly identified the embedded HTML page, ended its thinking with *"Let me write out the extracted content:"* — and emitted nothing.

- ✅ **Reporting half — fixed and now verified live.** Run eb2d0ac1 (2026-07-19, 12:24) is the first time this was observed working: the model ran `web_search`, `web_fetch`, `web_search` and stopped, and the user was told *"I ran `web_search`, `web_fetch` and then stopped without producing an answer — **nothing was created or changed.**"* Previously the same turn produced `"Done."` or a dangling promise.
  - Root cause was shared with item 7: every guard tested `full_response` for emptiness, and a dangling promise is not empty. The per-round `_INTENT_RE` supervisor couldn't see it either — the promise was written in an *earlier* round than the one that ended the turn.
  - The loop now snapshots prose before **every** tool block (not just document tools — 4e217ae0 turn 3 used only `web_search`/`web_fetch`). Positional, not keyword matching.
  - Tests: `tests/test_dangling_promise_turn.py`.
- ❌ **The active half was tried and REVERTED the same day. Read this before retrying it.** A nudge told the model *"finish the job NOW using the appropriate tool."* Run 8c80cf8d: it called `update_document` with **empty content**, wiping a 6186-character document to zero bytes, then created two empty `Untitled` documents and emptied one of those twice. **Five zero-length versions in four minutes, against none in the preceding 79.**
  - **Telling an idle model to act is not the same as telling it what to do.** With nothing to write, "act now" resolved to the most destructive available call.
  - It exposed a genuine latent bug, which is the more valuable find — see [resolvedissues.md](resolvedissues.md): `update_document`/`create_document` accepted empty content, so *any* empty call from any cause destroyed a document. All three tools now refuse it.
  - **A future attempt needs a narrower directive plus a guard proving the retry can only write content it actually holds.** Tests must assert the directive is *safe*, not merely that it exists — the ones written for the reverted version would have passed no matter how destructive it was. Still absorbs the old "enforce the edit tool on correction turns" item.
- **The underlying behaviour is untouched.** The model still gathers and stops; it is now honest about it.

### 9. ~~Throughput cliff on larger context~~ — retired 2026-07-28, disproved by its own data
**Not a work item. Kept as a counter-example, because the obvious optimisation it invites is the wrong one.** The framing was "throughput collapses as context grows". The 2026-07-27 measurement, four turns on one task ordered by input size, says otherwise: 10,223 tok → 5.22 tok/s · 11,078 → 5.22 · 34,723 → 6.52 · 56,323 → **6.78**. Throughput *rose* at 48.6 % of a 32k window. Time-to-first-token did climb, 33 → 63 s, and one turn reached 266 s total — but that is prompt ingestion, not generation slowing, and the two must not be conflated again.

What remains unexplained is a single outlier: 0b12aadb at **0.39 tok/s**, 393 s for 154 output tokens, against dd3e7371 at 2.84 on the same prompt with ~2.5k fewer tokens. Three sessions since have not reproduced it, so it is one event with no mechanism, not a curve. The milder within-session drift once filed here (4e217ae0: 5.66 → 5.03 → 3.35) is the same conflation — those were fact-check turns carrying fetch context, i.e. bigger prompts, i.e. slower first tokens.

**Do not optimise for "less context" on this evidence.** If the cliff recurs, it needs a memory-pressure measurement on the 16 GB M1 taken *during* the run, not a throughput number after it.

### 14. Web search derails on ambiguous common nouns
Recurring and now recorded as its own item, because it feeds item 2. Run eb2d0ac1 (2026-07-19) returned **"Pink (singer) — Wikipedia"** as a top result for a pink-oyster cultivation query; an earlier run ranked a Victoria's Secret "PINK" page into the same searches. Nothing in the pipeline notices, and the wrong-species drift in item 2 is partly downstream of this. Query disambiguation for ambiguous common nouns is weak — the species name is right there in the document title and isn't being used.

## S4 — friction and blocked diagnosis

### 10. ~~Failures aren't replayable~~ ✅ fixed 2026-07-28
Document tool events now carry `full_command` — the complete arguments, capped at 16 KB with an in-band truncation marker — alongside the truncated `command`. Persisted on success as well as failure. Diagnosis and the reasoning behind both choices in [resolvedissues.md](resolvedissues.md), *"The record of a run didn't say what happened"*.

- **Unblocks item 6**, which needed the raw stream and had been blocked on this three times.
- **Effort was filed as M and was actually one line plus a cap.** `full_command` was already computed and already streamed to the client; only the persistence dict substituted `cmd_display`. The estimate was stale because nobody had re-read the code since filing — the line numbers had drifted too (4313/4326/4673 → 4389/4405/4755).
- ⚠️ **Rows written before 2026-07-28 have no `full_command` and are not replayable.** The existing history is still only as good as `<<<FIND>>>`.
- A replay harness over history, symmetric with the editor-side one in `tests/tools/`, is now possible and is not yet built.

### 11. ~~Retry-at-failure covers only document tools~~ — retired 2026-07-28 to a watch note
**Conditional by its own wording** — "extend *if* the same silence appears on `bash`/`web_fetch`/`manage_calendar`" — and in the nine days since filing, no instance has appeared. That is a trigger, not a task; it was drawing attention as an open item without any evidence behind it.

The escalating directive still applies only to `edit_document`/`suggest_document`/`update_document`; every other tool gets the generic prompt line, which b5fe4ef5 showed is insufficient *for document tools*. **Refile with a run id if a non-document tool is seen failing silently** — and note that item 8's reverted nudge is the precedent for why the fix must bound what the retry can write, not merely tell the model to try again.

### 12. Wasted verification rounds
9B sometimes runs `manage_documents` "to check" after creating a doc (~47s for nothing). **Still reproducing** — run 27a94a01 (2026-07-19) did exactly this. A "don't re-verify what you just created" prompt line would trim it.

### 13. Terminal access-log noise
Every request prints, so real errors scroll away — worst during polling (`/api/research/status/<id>`, `/api/chat/stream_status/<id>`). **This got in the way twice on 2026-07-19** while trying to confirm PUT traffic during the editor investigation. Hide 200s; hide 304s behind their own toggle, since a 304 storm is how you spot a stale-cache bug. Don't use `--no-access-log` (kills 4xx/5xx) — add a `logging.Filter` on `uvicorn.access` keyed by status, wired at `app.py:1281`, `launcher.py:142`, `start-macos.sh:292`, with an `access_log_hide_statuses` setting.

### 15. ~~`web_fetch` failure rate on cultivation sources~~ — folded into item 2, 2026-07-28
**Its premise was answered before it was measured.** The item existed to test whether item 2 is "purely a reasoning problem" by checking how many sources a fact-check turn loses — roughly a third fail on the sites this task reaches for: `thesporedepot` HTTP 403 repeatedly across days, `shroomstop.ca` 404, `kvkwestkhasihills.nic.in` non-HTML. But run 31e0af64 on 2026-07-27 fetched **one clean source, complete and verified byte-exact**, and still produced four defects. Retrieval quality is therefore not the load-bearing cause, and item 2's transcription checker doesn't depend on this number.

Kept as a note under item 2 rather than a task: the failure rate is real and worth knowing when a fact-check turn ends empty-handed, but measuring it more precisely would not change what gets built next.

### 16. SSRF guard tests covered an orphaned function
One instance found and fixed 2026-07-27 (see [resolvedissues.md](resolvedissues.md), "web_fetch could not reach the LAN"); the **audit is the open part**.

`_public_http_url()` in `services/search/content.py` had no production callers. Commit `5e9b415` moved the live check to `_resolve_public_ips` and left the old function behind. `tests/test_search_content_url_guards.py` — a file that exists solely to test URL guards — asserted **3 of 3** cases against the orphan; `test_web_fetch_size_caps.py:93` monkeypatched it to `lambda u: True`, a no-op. The live guard had no coverage at all, and the suite was green throughout.

- **This is worse than dead code: it is a green test suite asserting a security property that nothing enforces.** The suite would not have caught a regression in the real guard.
- Fixed by making the orphan a thin wrapper over `_resolve_public_ips` rather than deleting it, so the existing assertions now exercise the live path and the two cannot diverge again.
- **Open:** the same shape is plausible elsewhere — `5e9b415` is not special, any refactor that moves a call site can leave one. A cheap first pass: flag module-private functions with zero non-test references. `src/webhook_manager.py`, `routes/model_routes.py` and `src/model_context.py` each carry their own `_PRIVATE_NETWORKS` copy and are the obvious places to look next.
- Related smell from the same commit, not yet fixed: `test_web_fetch_size_caps.py` patches `content_mod.httpx.stream` while `_get_public_url` uses `httpx.Client(...).stream`. Those tests are not exercising what they claim either.

### 17. ~~A cache hit is indistinguishable from a live fetch~~ ✅ fixed 2026-07-28
A served-from-cache result now carries `cached: true`, `cached_at` and `cache_age_seconds`; `tool_events` persists them and the `web_fetch` output tells the model *"served from cache, fetched N min M s ago — NOT a live reading"*. **Absence of the flag means live.** Full account in [resolvedissues.md](resolvedissues.md), *"The record of a run didn't say what happened"*.

- **Labelling the record alone would not have fixed the original failure** — it was the *model* reporting a cached `uptime: 91 s` as a current measurement, so the notice has to reach the model, ahead of the output trim.
- ⚠️ **Still true and not addressed:** `full: true` changes the cache key, because the download budget is part of it. The same URL fetched with and without `full` uses two independent entries and can return two different bodies in one session. Knowing *which* entry you got is now visible; that there are two remains a trap.
- ⚠️ Rows written before 2026-07-28 carry no flag either way.
- Operational detail in [qwensetup.md](qwensetup.md) under "`web_fetch` — what it sees, and what it silently reuses", including why you must never run `fetch_webpage_content()` against the live tree.

### 18. Two tests in `test_document_put_version_conflict.py` have never passed
Found 2026-07-28 while establishing a baseline before committing. `test_concurrent_ai_edit_after_read_loses_the_swap` and `test_losing_swap_does_not_leave_a_partial_version_row` both do `droutes._reserve_document_uploads` — but that function is defined at `routes/document_routes.py:82`, **nested inside `setup_document_routes()`**. It is a closure, never a module attribute, so the lookup raises `AttributeError` and can never have worked.

Measured across all 24 test files in the commit series: **959 passed, 2 failed**, these two. The commit message for the document commit had been drafted claiming *"687 source-level tests pass"* — corrected before committing rather than inherited.

- **Third instance of the item 16 shape, and the least dangerous kind.** Here the test fails loudly. Item 16's orphan failed *green*, which is why that one is the priority. But the underlying cause is identical: a test reaching for an implementation detail that a refactor moved, with nothing checking the reference still resolves.
- **Fixing it is a design decision, not a repair.** Patching a closure means either exposing it at module scope, injecting it, or restructuring the test to drive the behaviour through the endpoint instead of the internals. The last is the option `TESTING_STANDARD.md` would favour — the other two exist only to make the patch possible.
- ⚠️ **Do not "fix" these by deleting them.** They cover the CAS race that item 1 spent three diagnoses on: an AI edit landing between the handler's read and its write. That case genuinely needs coverage; what's broken is how the test reaches it.

### 19. Five tests fail on macOS only — the suite has never been green on the dev machine
Found 2026-07-28 by running the full suite on the M1 for the first time: **`7 failed, 5415 passed, 4 skipped`**. Two are item 18. The other five fail *only* on macOS, for two environment reasons, and **neither is an application bug** — the code under test is correct in all five cases.

**`OSError: AF_UNIX path too long` — 4 tests.** `test_cookbook_docker_access.py:65`, `test_shell_routes.py:302` (×2 params) and `:317` bind a Unix socket at `tmp_path / "docker.sock"`. macOS caps `sockaddr_un.sun_path` at **104 bytes** (Linux allows 108) and hands out a deep `$TMPDIR`, so the path is **126 bytes — 22 over**:

```
/private/var/folders/96/…/T/pytest-of-cedrik/pytest-3/test_container_opt_in_with_uni0/docker.sock
```

The same path under Linux's `/tmp` is 74 bytes and fits, which is why this has never been seen. **Fix: bind the socket in a short directory** (`tempfile.mkdtemp(dir="/tmp")` plus a short filename), not under `tmp_path`. The directory only needs to hold a socket for the length of the `with` block.

**`test_workspace_confine.py::test_glob_confined_e2e` — the assertion contradicts its own comment.** The test creates a secret outside the workspace and globs a traversal pattern at it. It correctly gets `No files`, then asserts `secret not in r["output"]`. But the comment three lines above says: *"The not-found message echoes the pattern the model supplied, so the signal is the absence of a match, not the absence of the path string."* The comment is right and the assertion contradicts it.

It passes on Linux by luck. `outside = tempfile.mkdtemp()` returns `/var/folders/…` unresolved, while the workspace is compared as `os.path.realpath(ws)` = `/private/var/folders/…`. `os.path.relpath` is purely lexical, so it walks up seven levels and back down through the **absolute** path — `../../../../../../../var/folders/…/secret.txt` — which necessarily contains the secret string. On Linux both paths are already canonical, so `relpath` yields `../tmpYYYY/secret.txt` and the assertion holds vacuously.

**Fix: `outside = os.path.realpath(tempfile.mkdtemp())`.** Then `relpath` stays relative on both platforms and the assertion tests what it was written to test. **No confinement hole here** — glob refused correctly; it echoed back a pattern the caller already supplied, which reveals nothing.

**Both fixed 2026-07-28. The macOS conditions were reproduced on Linux rather than reasoned about**, which is the only reason this is recorded as verified:

- *`AF_UNIX`:* re-running with `TMPDIR` set to a 60-byte path (the real macOS one is 57) reproduced `OSError: AF_UNIX path too long` **on Linux**, at 130 bytes, from the old `tmp_path` pattern. The new helper then passed 33 tests under that same deep `TMPDIR`. The failure is a path-length function, so it is fully reproducible anywhere once the length is matched.
- *`glob`:* the symlink half could not be reproduced live — it needs a **root-level** symlink (`/var` → `/private/var`) and this sandbox cannot write to `/`. Verified instead by running `os.path.relpath` over the exact path strings from the failing run: the old shape yields `../../../../../../../var/folders/…/secret.txt`, which embeds the absolute secret; with the temp root resolved it yields `../tmpmzmii5bz/secret.txt`, which does not. **The leak is in the pattern the test constructs, never in glob's output.**
- The fix is `outside = os.path.realpath(tempfile.mkdtemp())` plus a precondition `assert outside == os.path.realpath(outside)`. **A first attempt guarded with `not os.path.isabs(rel)` and was worthless** — the leaking path is a *traversal*, not an absolute path, so `isabs` is `False` in both the broken and fixed cases. Worth keeping as a reminder that a guard which passes in the failing case is not a guard.
- Shared helper: `tests/helpers/unix_socket.py`, `bound_unix_socket()`. It asserts its own path is under 104 bytes, so the next person to lengthen it gets a clear message instead of `OSError`.
- **Not yet observed green on the M1** — 117 tests pass across the three files on Linux, and the length condition is reproduced, but the `/private` symlink is genuinely absent here. One host run closes it.
- **A permanently-red suite is its own hazard.** Seven expected failures on every run trains you to skim the summary, and that is how the eighth gets through. Same family as item 16's green-suite-asserting-nothing, inverted.
- **`-m area_security` reported `654 passed` clean on this tree** while four docker-socket privilege-gate tests were failing, because the taxonomy keys off filenames: `test_shell_routes.py` → `area_routes`, `test_cookbook_docker_access.py` → `area_services`. **An area marker says what the file is called, not what it protects** — don't use the security lane as a pre-commit gate on its own.

---

## Notes & constraints
Settled. Recorded so they don't get re-litigated.

- **Per-round thinking suppression isn't currently possible.** `reasoning_effort:"none"` needs `tools and _is_qwen_thinking_model and _agent_thinking_disabled()` (`llm_core.py:2276`). `agent_disable_thinking` is `False`, **and** `tools` is always `None` on this endpoint — so flipping the setting changes nothing. Needs an override plumbed through `stream_llm`.
- **Local models get no tool schemas at all** (`all_tool_schemas` is empty unless `_is_api_model`). Anything shaped like "force/narrow/restrict the tools" has no channel here and must happen in the loop.
- **Don't widen `_ody_doc_finetune_mode`.** It gates tool narrowing and `tool_choice_none` as well as the loop break. The reporting path was split out of it deliberately.
- ~~**The redundant `user` document version is cosmetic.**~~ **Retracted 2026-07-19.** It was not cosmetic and not byte-identical — it was the visible edge of the duplicate-`doc_update` data loss in item 1.
- **Timestamps in `app.db` are naive UTC while `ls`/`stat` report local CEST.** Cost a two-hour error that made three post-fix sessions look like they predated the fix. Full statement, including the sanity check, in [qwensetup.md](qwensetup.md) under *Reading `data/app.db` when debugging a run* — kept there rather than restated here, because that is where you are standing when it bites.
- **On writing these docs:** "fixed" has twice been recorded from a single happy-path run, and a mechanism twice from a symptom string. Record the scope a fix was verified at, not just the outcome — hence the Verified column above.
- **Every edit to these four files comes from a different session, none of which could see the others.** That is the structural reason things drift here, and it produces one failure mode reliably: **cross-references rot when items are renumbered.** Three were found wrong on 2026-07-27 — `resolvedissues.md` pointed at #1 for the 4B's wrong numbers (that is #2), at #2 for the "Done." path (closed entries in its own file), and at #7 for the agent-stops-early behaviour (that is #8). Each was correct when written. **Before renumbering anything, grep the other three files for `#<old>` and `item <old>`**; a numeric reference across files has no integrity check and reads plausibly while pointing at the wrong thing. Prefer citing an entry by *title* over by number where the choice exists.

  **All 37 item references were audited on 2026-07-27; the three that had rotted share a shape.** Every reference *within* this file that survived is **reciprocal** — #6↔#10, #7↔#8, #2↔#14 each name the other, so renumbering one would have visibly broken the pair. All three broken ones were **one-directional, `resolvedissues.md` → here**, with no named back-reference to notice the drift. So: a cross-file citation that nothing points back at is the fragile kind. Either make it reciprocal or cite the entry by title.
- **The 2026-07-27 reference audit covered the four docs and not the code — and the code had rotted too.** "All 37 item references were audited" meant *within* the docs. Extending the same audit to source and tests on 2026-07-28 found a fourth broken reference of the identical one-directional shape: `tests/test_doc_report_gate_split.py` cited `docs/todo.md #2` **three times** for the closing-summary reporting path, which is #7 — #2 is the unrelated fact-check inversion. Also normalised seven `TODO.md item N` citations in `static/js/document.js` (the file is `docs/todo.md`; the mismatch is invisible on a case-insensitive macOS volume and breaks on Linux/CI). **Source comments are cross-references too, and there are more of them than there are in these files.** Grep `--include=*.py --include=*.js` for `todo.md` before renumbering, not just the four docs.
- **On guards that write.** A guard that only *reports* can be shipped on test evidence. A guard that makes the model *act* can destroy data, and its tests must bound what it can do, not merely assert it exists. Item 8's reverted nudge passed every test written for it.
- **A "superseded" banner does not retire a document — deleting the prose does.** `KNOWN_ISSUES_debug.md` carried a banner from 2026-07-18 stating that its leading theory (the reasoning parser eating the answer) was wrong, with a pointer to the retraction. On 2026-07-27 an agent read that banner and then argued from the body underneath it anyway, proposing to re-investigate the `/v1` thinking path — the third trip down a road two retractions exist to close. **Prose that reads like a live finding will be treated as one, however it is framed.** The file was emptied and then removed; its content survives as a loose object, recoverable with the `git cat-file` command in item 5 — **not** "in the git index", as this line claimed until 2026-07-28, which item 5's own recovery note directly contradicts. Corollary for this file: when an item is retracted, cut the reasoning, keep the conclusion.
