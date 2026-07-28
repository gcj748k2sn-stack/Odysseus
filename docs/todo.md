# Open items — Qwen 9B setup

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
| 2 | Fact-check inverts ground truth | S1 | M | open | — |
| 3 | Documents contradict themselves | S1 | M | partly re-diagnosed; editor half fixed | tests |
| 4 | ~~Retired 4B still on the research path~~ | S1 | XS | ✅ done | live |
| 5 | Uncommitted work — since 2026-07-12 | S2 | XS | **47 files staged, plan rehearsed — awaiting a git identity** | **live** — dry run, 7 commits |
| 6 | Answer text lost to the reasoning channel | S2 | M | lead only — blocked on #10 | — |
| 7 | ~~Closing summary under-reports / stays silent~~ | S3 | S | ✅ fixed | **live** — skipped-edit report, 2026-07-27 |
| 8 | Agent gathers information, then stops | S3 | M | reporting fixed; **active half reverted** | **live** (reporting) |
| 9 | Throughput cliff: 2.84 → 0.39 tok/s | S3 | M | open | — |
| 10 | Failures aren't replayable | S4 | S | open — **blocked diagnosis twice** | — |
| 11 | Retry-at-failure covers only document tools | S4 | S | open | — |
| 12 | Wasted verification rounds | S4 | XS | open — still reproducing | — |
| 13 | Terminal access-log noise | S4 | S | open — got in the way twice | — |
| 14 | Web search derails on ambiguous common nouns | S3 | M | open — recurring | — |
| 15 | `web_fetch` failure rate on cultivation sources | S4 | S | open | — |
| 16 | SSRF guard tests covered an orphaned function | S4 | S | one instance fixed; **audit open** | tests |
| 17 | Cache hits are indistinguishable from live fetches | S4 | S | open — **produced a wrong conclusion** | — |

> **Next:** item 5 needs one decision from you (a git identity: two `git config` lines, no GitHub account) and everything else here is now genuinely staged — as of 2026-07-28 it wasn't, see the item. Then item 2 is the only S1 left with no work done on it — and it has fresh evidence from 2026-07-27 that the failure is transcription, not just retrieval. Item 10 still blocks diagnosis of everything else, and item 17 is its close relative: both are cases where the record of a run doesn't say what actually happened.

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

### 2. The fact-check step inverts ground truth
**The only S1 with no work done on it.** Two consecutive runs re-introduced cold shock on a tropical species. 009660d2 stated it outright: *"pink oysters prefer slightly cooler than other Pleurotus species during fruiting"* at 65–70°F, with *"Cool down by 3-5°F from spawn temp"*. That is backwards — *P. djamor* is the thermophilic one — and it's the failure that retired the 4B, now produced twice by the 9B. Both documents title themselves "Fact Checked & Corrected", which is the damage: wrong chamber setpoints wearing the authority of verification.

**The more it fact-checks, the worse it gets — measured 2026-07-19:**

| Run | Prompt | Result |
|---|---|---|
| acba4766 | plain "create a document" | **closest to correct** — 24–28°C, CO₂ <1000 ppm |
| 4d97aa60 | "create with **fact checked** infos", 4 web fetches | **worst yet** — fruiting 14–21°C, ">26°C may reduce…", no CO₂ at all |
| baac5d34 | create, then "fact check and correct" | 4 edit rounds, corrections partly destroyed by item 1 |

14–21°C is the *P. ostreatus* range on a tropical species, and 26°C — flagged as too warm — is squarely optimal. Asking for verification up front produced more confidently wrong numbers than not asking at all, after four source fetches. **The retrieval step is not neutral; it actively drags the answer toward the wrong species** — and item 14 is part of why.

**Fix:** the ground truth is already written down in [resolvedissues.md](resolvedissues.md) ("4B retired") — colonization 24–29°C, fruiting 20–30°C **no cold shock**, RH 85–95%, CO₂ 500–800 ppm at 3–6 ACH. Make it a fixture plus a checker that flags a document contradicting it. Generalises to "assert a document doesn't contradict a known-facts file".

**2026-07-27 — the same severity with no retrieval involved at all.** Run 31e0af64 fetched one clean JSON document (40 history points, complete, verified byte-exact against the source) and asked for a table. No search, no fact-check, no ambiguous nouns — item 14 cannot be blamed. Four defects landed in the document anyway:

- **39 of 40 rows transcribed correctly; row `s=360` lost a column** — `| 360 | 87.4 | 26.9 |`, temperature `24.5` dropped, everything shifted left.
- **It noticed, misdiagnosed its own error, and burned a round on it.** Thinking: *"I notice there's an error at time=360 where I accidentally copied values incorrectly (t:24.5, h:87.4 swapped with dp)"* — nothing was swapped, a value was missing. It then sent `edit_document` with a FIND block matching the **correct** row it had never written. No match, no-op.
- **Time axis wrong by ~57×, and self-contradictory:** *"~19 hours (~7.5 days of sampling)"* for 40 points at 30 s = **20 minutes**. The source field is `"s"`, seconds of uptime, with no unit in the payload. The document's column is headed "Time", unitless.
- **A raw inverted register reported as a metric:** *"duty cycle: 252"*. 252 is the PWM value after a BC547 inversion — 255 is off. Actual power was the `dp` field, 5.1 %. Anyone reading that infers near-full power.
- Two of three sensors absent from the document although present in the JSON.

**Why this sharpens the item:** the failure is not "the model retrieves bad sources". It is that a 40-row verbatim transcription at ~6.8 tok/s is near the edge of what this model does reliably, and there is no check that the output matches the input it was handed. A row-count-plus-cell diff against the source is cheap and would have caught three of the four. Complements the known-facts checker above rather than replacing it.

### 3. Partial edits leave documents contradicting themselves
Run 127d32b0: 8 edits fixed the prose and missed the summary table, leaving four CO₂ thresholds and three colonization durations in one document.

> **Partly re-diagnosed 2026-07-19 — a share of this was the editor, not the model.** The diff-review overlay was writing documents containing **both** the pre-edit and post-edit text for the same section. Doc `92f3b2a0` v3: twelve such regions from a *single* Accept click, including a garbled `5-1°C (68-F)` line restored next to its own correction. Cause: an un-reviewed chunk was treated as rejected, and `_resolveChunk` persisted that reading on every click. Fixed — see [resolvedissues.md](resolvedissues.md).

**How much of the model-caused problem remains is now an open measurement rather than a known quantity.** The last clean run still showed the lint firing correctly (*"`20-30°C`, `3-7 days` were corrected in one place but still appear elsewhere"*), so the model half is real — just not the whole story.

- Detection exists (`find_stale_values()`), surfacing was fixed 2026-07-18. **Prevention doesn't** — the model is never asked to fix what the lint finds.
- **Gap:** the lint runs only inside `EditDocumentTool` (`document_tools.py`). A full `update_document` rewrite bypasses it entirely.

### 4. ~~The retired 4B is still live on the research path~~ ✅ done 2026-07-19
`research_model` is now `qwen3.5:9b-32k`; `_RETRY_CONTINUATION_RE` recognises document/research context. See [resolvedissues.md](resolvedissues.md).

## S2 — silent loss

### 5. Everything since 2026-07-12 — staged, not yet committed
Last commit `df2fad2` is **2026-07-12**; as of 2026-07-28 that is **16 days**, not the seven this item was filed with. *Stated as a date rather than a duration from here on, since the duration goes stale on its own.* The tree is **staged — 47 files** — with a **seven**-commit split in `COMMIT_PLAN.sh`. It will not run until a git identity is set — deliberately, since this repo has none and its history is authored by other people. **No GitHub account is needed:** the identity is unverified free text; only `git push` would involve an account, and that is a separate decision after the merge below.

**2026-07-28 — this item's own bookkeeping was wrong in two ways that would have lost work.** Both are fixed; recorded because each is a shape that recurs.

- **"44 files, staged" described 2026-07-19 and was never updated.** The whole 2026-07-27 session — the two-tier SSRF guard in `services/search/content.py`, its two test files, the `.env.example` entry, and every doc edit — was **unstaged**, i.e. outside the only protection this item claims to have. Now staged: 47 files. **A snapshot count in prose is a claim with an expiry date and no check;** the sentence read as current for nine days.
- **`COMMIT_PLAN.sh` named no `git add` for three staged test files** — `test_dangling_promise_turn.py`, `test_doc_closing_summary_accumulates.py`, `test_document_tools_reject_empty_writes.py`. Since the script opens with `git reset -q`, they would have come out untracked: the exact staged-but-never-committed trap documented below, applied to the entire evidence base for items 7 and 8. Added, plus **a coverage check at the end of the script that lists any path staged at start and absent from the new commits**, because this class of error is invisible to review and trivial to detect mechanically.
- The script also now **refuses to run with an empty index** (a second run used to unstage everything, then fail on the first empty commit — leaving the tree *less* protected than before), and a seventh commit carries the SSRF work.
- ✅ **Rehearsed end to end 2026-07-28**, against a copy of `.git` with a throwaway identity and the real worktree, so nothing in the repo was touched: 7 commits, all 47 files landed, coverage check clean, second run correctly refused. Verified `HEAD` still `df2fad2`, still 47 staged, still no identity afterwards. **The plan is known to run, not merely known to parse** — which is the distinction the *Verified* column exists for.

- ✅ **`searxng/` is now gitignored.** It was genuinely unprotected; 138 MB with a nested upstream `.git` plus its own venv, one `git add -A` from being swallowed.
- ✅ **A restore point exists outside git** — `outputs/snapshots/odysseus-restorepoint-*.tar.gz`, full worktree plus `.git` plus `data/app.db`, excluding regenerable caches. This was the real gap: the risk was never only "you might run `git checkout`", it was having no restore point at all while agents edit the tree.
- ✅ Audited before staging: no credentials, `data/` already ignored so `app.db` and settings stay out, docs contain no personal paths.
- **A stale `.git/index.lock` from 2026-07-18 21:16 had been failing every git operation for 13 hours.** Zero bytes, crashed process. Probably why nothing got committed. Cleared.
- ⚠️ Branch `dev` is **4 commits behind `origin/dev`** — commit first, then merge; don't pull into a dirty tree.
- ✅ **`KNOWN_ISSUES_debug.md` — resolved by deletion, 2026-07-27.** This line used to read "deliberately left unstaged"; it was in fact staged (`A`, 62 insertions), so the intent had never taken effect. Rather than re-deciding whether superseded content should reach a public remote, the file was removed: everything in it was disproved, fixed, or already duplicated in these three docs. The one lesson worth keeping is in *Notes & constraints* below. Nothing referenced the file — the two source comments citing `knownIssues #3` were numbering references, and both now cite [resolvedissues.md](resolvedissues.md) *"Active-doc turns losing edit tools on low-signal input"* by title (rewritten 2026-07-28 when `llmSetup.md`, which had held the mapping table, was itself deleted — see the entry below).

- ✅ **`llmSetup.md` — resolved by deletion, 2026-07-28.** It existed only as a redirect, kept alive because source comments cited it. All of them now cite [resolvedissues.md](resolvedissues.md) **by entry title** rather than by number, so there is nothing left to point at. There were **seven** citations, not the five the file claimed: `tests/test_document_put_version_conflict.py`, `tests/test_active_doc_vague_turn_tools.py`, `static/js/document.js:9340`, `routes/document_helpers.py:36`, `src/agent_loop.py:1431` and `:2927`, plus the `git add` line in `COMMIT_PLAN.sh`. Two of them also carried the dead `knownIssues #3` numbering, which now has no successor anywhere. **Its own stated exit condition undercounted the work by two** — a redirect kept for N callers should be deleted by grepping, not by trusting the count written in it.

  **Recovering it:** `git cat-file -p 93bdbbb7 > docs/llmSetup.md` (24 lines, the mapping-table version). Learning from the `KNOWN_ISSUES_debug.md` trap directly below, the worktree copy was written into the object database with `git hash-object -w` *before* deletion — it was staged-but-never-committed **and** the staged blob `746a08ef` was a different, older 7-line stub, so deleting the file would otherwise have destroyed the only copy of the version anyone had read. **When removing a staged-but-uncommitted file whose worktree copy differs from its staged blob, `hash-object -w` it first; there is no other recovery route.**

  **Recovering `KNOWN_ISSUES_debug.md`, if ever wanted:** `git cat-file -p b570b679 > KNOWN_ISSUES_debug.md` (62 lines, the pre-trim body). Note the obvious command does **not** work: the file was renamed with `git mv` before deletion, so `git show :KNOWN_ISSUES_debug.md` returns nothing — the index knew it under the new name, and `git rm --cached` then dropped that entry too. The blob survives only as a loose object, findable with `git cat-file --batch-all-objects --batch-check` filtered on content. **This is a general trap for anything staged-but-never-committed: renaming it invalidates every path-based recovery route, and it is not in any commit to fall back on.** `git fsck --lost-found` does not list it either, because it is still referenced from a stale index generation.

### 6. Answer text can be lost to the reasoning channel
Run f14a8f52, exact from `app.db`: `round_texts[0]` was 300 chars, `thinking` was a byte-for-byte 219-char **prefix** of it, and the saved message is the remaining 79 chars. The reply starts mid-list at "2.", and the model's most important question — *"1. Where is the existing HTML, CSS and JavaScript located?"* — is absent from history entirely.

**This is a lead, not a diagnosis.** "The reasoning parser eats the answer" is the hypothesis [resolvedissues.md](resolvedissues.md) already retracted once; that retraction was correct for those runs. The arithmetic above shows the mechanism is real *somewhere*. Confirming it needs the raw stream, which **item 10 unlocks** — and item 10 has now blocked diagnosis twice more.

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

### 9. Throughput cliff on larger context
dd3e7371 ran at 2.84 tok/s; 0b12aadb at **0.39 tok/s** — same prompt, the only difference being ~2.5k extra tokens from a file read. 393 seconds for 154 output tokens. An 8× collapse from that little context smells like KV-cache or memory pressure on the 16GB M1, not model speed.

**Milder but consistent degradation within a session**, 2026-07-19: 4e217ae0 ran 5.66 → 5.03 → 3.35 tok/s across three turns; eb2d0ac1 ran 8.95 → 3.68. Create turns are consistently fast (177–183s); fact-check turns, which carry accumulated fetch context, are consistently slow.

**2026-07-27, four turns on the same task, ordered by input size:** 10,223 tok → 5.22 tok/s · 11,078 → 5.22 · 34,723 → 6.52 · 56,323 → 6.78. **Throughput did not fall — it rose slightly**, at 48.6 % of a 32k window. Time-to-first-token did climb (33 → 63 s), and total turn time reached 266 s, but that is the prompt being ingested, not generation slowing. So the 8× cliff at 0.39 tok/s is *not* a smooth function of context size; something else distinguished 0b12aadb. Worth keeping as a counter-example before anyone optimises for "less context".

### 14. Web search derails on ambiguous common nouns
Recurring and now recorded as its own item, because it feeds item 2. Run eb2d0ac1 (2026-07-19) returned **"Pink (singer) — Wikipedia"** as a top result for a pink-oyster cultivation query; an earlier run ranked a Victoria's Secret "PINK" page into the same searches. Nothing in the pipeline notices, and the wrong-species drift in item 2 is partly downstream of this. Query disambiguation for ambiguous common nouns is weak — the species name is right there in the document title and isn't being used.

## S4 — friction and blocked diagnosis

### 10. Failures aren't replayable — now the top S4
`tool_event` persists `cmd_display`, which for document tools is `block.content.split("\n")[0][:80]` — i.e. literally `<<<FIND>>>`. **This blocked diagnosis twice more on 2026-07-19**: once testing whether skipped FIND texts landed in regions the diff had rolled back, once attributing the empty-write incident.

**Two corrections to the item as originally written, both from real data:**
- *"Persist raw args on any conversion or parse failure" is too narrow.* The c7da3649 calls **succeeded** (`v5, 2 edit(s)`) with one edit skipped inside the same call. Under a failure-only rule nothing would be persisted and the interesting case is still lost. Persist always for document tools.
- *The data already exists and is thrown away at the last step.* `full_command` is computed at `agent_loop.py:4313` and streamed to the client at `:4326`; only the persistence dict at `:4673` substitutes `cmd_display`. Roughly one line plus a size cap — much cheaper than the M-effort framing implies. Cap at ~16 KB with an explicit truncation marker; message metadata is currently 566 KB across 92 rows in a 2.4 MB database.

Unlocks item 6 and a replay harness over history, symmetric with the editor-side one already built in `tests/tools/`.

### 11. Retry-at-failure covers only document tools
The escalating directive applies to `edit_document`/`suggest_document`/`update_document`. Every other tool gets only the generic prompt line, which b5fe4ef5 showed is insufficient. Extend if the same silence appears on `bash`/`web_fetch`/`manage_calendar`.

### 12. Wasted verification rounds
9B sometimes runs `manage_documents` "to check" after creating a doc (~47s for nothing). **Still reproducing** — run 27a94a01 (2026-07-19) did exactly this. A "don't re-verify what you just created" prompt line would trim it.

### 13. Terminal access-log noise
Every request prints, so real errors scroll away — worst during polling (`/api/research/status/<id>`, `/api/chat/stream_status/<id>`). **This got in the way twice on 2026-07-19** while trying to confirm PUT traffic during the editor investigation. Hide 200s; hide 304s behind their own toggle, since a 304 storm is how you spot a stale-cache bug. Don't use `--no-access-log` (kills 4xx/5xx) — add a `logging.Filter` on `uvicorn.access` keyed by status, wired at `app.py:1281`, `launcher.py:142`, `start-macos.sh:292`, with an `access_log_hide_statuses` setting.

### 15. `web_fetch` failure rate on cultivation sources
Roughly a third of fetches fail on the sites this task keeps reaching for: `thesporedepot` HTTP 403 (repeatedly, across days), `shroomstop.ca` HTTP 404, `kvkwestkhasihills.nic.in` non-HTML. The model correctly moves on each time, but a fact-check turn that loses a third of its sources is part of why those turns keep ending empty-handed. Worth measuring before treating item 2 as purely a reasoning problem.

### 16. SSRF guard tests covered an orphaned function
One instance found and fixed 2026-07-27 (see [resolvedissues.md](resolvedissues.md), "web_fetch could not reach the LAN"); the **audit is the open part**.

`_public_http_url()` in `services/search/content.py` had no production callers. Commit `5e9b415` moved the live check to `_resolve_public_ips` and left the old function behind. `tests/test_search_content_url_guards.py` — a file that exists solely to test URL guards — asserted **3 of 3** cases against the orphan; `test_web_fetch_size_caps.py:93` monkeypatched it to `lambda u: True`, a no-op. The live guard had no coverage at all, and the suite was green throughout.

- **This is worse than dead code: it is a green test suite asserting a security property that nothing enforces.** The suite would not have caught a regression in the real guard.
- Fixed by making the orphan a thin wrapper over `_resolve_public_ips` rather than deleting it, so the existing assertions now exercise the live path and the two cannot diverge again.
- **Open:** the same shape is plausible elsewhere — `5e9b415` is not special, any refactor that moves a call site can leave one. A cheap first pass: flag module-private functions with zero non-test references. `src/webhook_manager.py`, `routes/model_routes.py` and `src/model_context.py` each carry their own `_PRIVATE_NETWORKS` copy and are the obvious places to look next.
- Related smell from the same commit, not yet fixed: `test_web_fetch_size_caps.py` patches `content_mod.httpx.stream` while `_get_public_url` uses `httpx.Client(...).stream`. Those tests are not exercising what they claim either.

### 17. A cache hit is indistinguishable from a live fetch
`fetch_webpage_content` caches for 2 h under `sha(url + "#cap=" + budget)`. Nothing in `tool_events` distinguishes a served-from-cache result from one that left the machine — same shape, same `exit_code`, no flag.

- **It has already produced a wrong conclusion.** Two turns 4½ minutes apart both reported `uptime: 91 s` from a device whose uptime counter was running; only the first fetch was real. Read from `app.db` alone, the second turn looks like a fresh reading of a frozen device.
- **`full: true` changes the cache key**, because the budget is part of it. The same URL fetched with and without `full` uses two independent entries and can return two different bodies in one session — a second trap on top of the first.
- Sibling of item 10: both are cases where the stored record of a run doesn't say what actually happened, and both cost diagnosis time before anyone suspects the record itself.
- **Cheap fix:** carry `cached: true` plus the entry's `timestamp` into the tool result. Anything more (per-call bypass, shorter TTL) is optional; knowing *which* is the part that blocks diagnosis.
- Operational note for anyone debugging this path lives in [qwensetup.md](qwensetup.md) under "`web_fetch` — what it sees, and what it silently reuses", including why you must never run `fetch_webpage_content()` against the live tree.

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
