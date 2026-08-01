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
| 3 | Documents contradict themselves | S2 ⚠️ | M | detection live; **prevention open** — re-verified verbatim 2026-07-31 | **live** (lint); **share attributable to the model never measured** |
| 4 | ~~Retired 4B still on the research path~~ | S1 | XS | ✅ done | live |
| 5 | ~~Uncommitted work — four recurrences~~ | S2 | XS | ✅ **closed 2026-07-31 — moved to [`CLAUDE.md`](../CLAUDE.md) §6, not fixed in code** | n/a — it was never a defect |
| 6 | ~~Answer text lost to the reasoning channel~~ | S2 | S | ✅ fixed 2026-07-28 — a save-path regex | **tests (15)** |
| 7 | ~~Closing summary under-reports / stays silent~~ | S3 | S | ✅ fixed | **live — both branches** |
| 8 | Agent gathers information, then stops | S3 | M | reporting fixed; **active half reverted** | **live** / tests (zero-tool) |
| 9 | ~~Throughput cliff: 2.84 → 0.39 tok/s~~ | — | — | ⊘ **retired — disproved by its own data** | n/a |
| 9b | Streams fail mid-turn; timeout caps document length | S3 | S | reporting ✅; **timeout raised 300→900, unverified**; window 32k→64k (overflow half only) | **live** (notice, bbde3e51) |
| 10 | ~~Failures aren't replayable~~ | S4 | XS | ✅ fixed 2026-07-28 — `full_command` | **live** — 42889f7b |
| 11 | ~~Non-document tools have no closing report~~ | S3 | M | ✅ built 2026-07-28 — report-only | **tests (20)** — needs a live turn |
| 12 | Wasted verification rounds | S4 | XS | open — **re-measure first, see item 20** | — |
| 13 | Terminal access-log noise | S4 | S | open — got in the way twice | — |
| 14 | Web search derails on ambiguous common nouns | S3 | M | open — the quoted-phrase half is item 29 | — |
| 15 | ~~`web_fetch` failure rate on cultivation sources~~ | — | — | ⊘ **folded into 2 — premise already answered** | n/a |
| 16 | ~~SSRF guard tests covered an orphaned function~~ | S4 | S | ✅ **closed 2026-07-31 — instance fixed 07-27, audit run 07-31** | tests; **audit: 271 files, 1,672 names, 3 hits** |
| 17 | ~~Cache hits indistinguishable from live fetches~~ | S4 | XS | ✅ fixed 2026-07-28 | **live** — 42889f7b |
| 18 | ~~Two CAS tests have never passed~~ | S4 | XS | ✅ **fixed 2026-07-31** — patched the module attribute, not the closure | **M1 suite green + mutation**: both fail with the CAS clause removed |
| 19 | ~~Five tests failed on macOS only~~ | S4 | XS | ✅ fixed 2026-07-28 | **live** — M1 suite |
| 20 | 116 lines of agent rules never reached a model | S3 | S | open — **found 2026-07-28** | tests |
| 21 | ~~Three S1 warnings suppressed when the model wrote a summary~~ | S1 | XS | ✅ **fixed 2026-07-28** | tests (13) |
| 22 | ~~Documents never stream into the editor on this setup~~ | S4 | — | ⊘ **retired — disproved 2026-07-28** | n/a |
| 23 | Finished answers delivered in the reasoning channel | S2 | ? | open — **found 2026-07-29** | **live** — 374d57b7 |
| 24 | ~~Cloned documents were all named "Untitled"~~ | S4 | XS | ✅ fixed 2026-07-29 | **live** — both paths, 2026-07-29 |
| 25 | A path-confinement test passes without the thing it tests | S4 | XS | **confirmed**; fix open | **confirmed on macOS** |
| 26 | ~~Test litter in the repo root, hidden by `ignore_errors=True`~~ | S4 | XS | ✅ **closed 2026-07-31** — gitignore half was already done; silence fixed | **verified + negative control**: warns under the mount, silent on a removable tree |
| 27 | A LAN address in the prompt deletes every document tool | S3 | S | open — **root-caused 2026-07-29** | **live** ×3 |
| 28 | ~~The model writes the tool call instead of making it~~ | S2 | S | ✅ built + **committed `1a8e804e`** 2026-07-29 | **tests (14)** — live ×3 pre-fix |
| 29 | ~~Quoted phrases return locale filler~~ | S3 | S | built 2026-07-29, ⚠️ **UNCOMMITTED** | **tests (16) green on the M1** — not live |
| 30 | ~~Switching chats writes the editor buffer into the other chat's document~~ | S2 | M | ✅ **fixed 2026-07-30** — root cause and guard, both branches observed | **live** — 21:27, no flush attempted |
| 33 | ~~`switchToDoc` deletes the document you are leaving, from the map~~ | S2 | XS | ✅ **closed 2026-07-31 — fixed AND unreachable by construction** | **live** — 35 `switchAway` traces; two independent barriers |
| 34 | An aborted document stream orphans its placeholder as `activeDocId` | S2 | XS | open — reaper found, fix narrowed; **reproduced on demand 2026-07-31**, measuring frequency before building | **live — scripted repro + `[doc-put-404]` in `app.log`** |
| 31 | ~~Closing a document tab overwrites a *different* document~~ | S2 | M | ✅ **closed 2026-07-31** — (a) and (b) both verified live; (c) retracted | **live** — (a) 16:02 · (b) 16:55, `syncedLen` 5 and 9270, no `[doc-del]` |
| 32 | ~~A scheduled tidy hard-deletes duplicate documents, versions and all~~ | S2 | S | ✅ **fixed 2026-07-30** — archives, session-scoped, logged | **live** — 17:31, counts held · tests (7 + 3 mutations) |
| 35 | `loadSessionDocs` flushes the editor buffer into the document it is switching TO | S4 | XS | **fixed 2026-07-31 (`flush:false`), verification owed** — S2 latent | **live ×4** — caller frames; **3 of 6 switches in 40 s** |
| 36 | ~~The document-tab actions menu is unreachable — its button is never rendered~~ | S4 | XS | ✅ **closed 2026-07-31 — ACCEPTED AS IS, deliberately not fixed** | **live** — `${menuBtn}` occurs 0 times; every action has another route |
| 37 | ~~Model probes ignore session-backed credentials~~ | — | — | ⊘ **retired 2026-07-31 — out of scope for this deployment, NOT disproved** | source-level; **0 session-backed endpoints, 0 auth sessions** |
| 38 | ~~Four functions look like calls that were never wired up~~ | — | — | ⊘ **retired 2026-07-31 — investigated, 4 of 4 deliberate or superseded** | **wiring three of them up would have caused regressions** |
| 39 | ~~A permanently-failing URL is re-fetched once per appearance~~ | S4 | XS | ✅ **closed 2026-08-01 — fixed, tests (21), verified live** | **3 attempts → 1 request**; ages 44 s / 196 s off one stored failure |
| 40 | Round 1 of every turn re-prefills the whole prompt | S3 | M | **measured 2026-08-01, cause not identified** | **275 rounds**; 4–8× slower than later rounds at matched size |
| 41 | ~~A truncated answer is indistinguishable from a short one~~ | S2 | XS | ✅ **CLOSED 2026-08-01 — built and verified live on BOTH paths the day it was filed** | **live ×2** — `length` closed item 44; `stop`/`tool_calls` on real chat turns, **no `?`** |
| 42 | Sessions pin the model tag per row; a tag Ollama no longer serves does not fall back | S3 | S | **filed 2026-08-01; co-residency half DISPROVED the same day; dead-tag half open** | **72 of 79 on `-32k`**; ⊘ **the 13 GB claim is dead — Ollama evicts, it does not co-reside** |
| 43 | `max_tokens=0, temp=1.0` arrives whenever a request carries no preset | S3 | XS | **value corrected + verified live 2026-08-01; recurrence OPEN, mechanism now known** | **live** — `8192` at 09:54:12; the zero-preset turn caught in the act at 09:51:31 |
| 44 | ~~`/api/documents/ai-tidy` failed every logged call, and the 500s logged nothing~~ | S3 | S | ✅ **CLOSED 2026-08-01 — two faults, both fixed, filed and closed the same day** | **live** — `status=200`, `parsed 28 of 30`, 17.8 s, no retry · ⚠️ **archive branch still unexercised** |
| 45 | The server injects a document the user never named, and closing the editor does not stop it | S3 | S | **filed 2026-08-01 — from the maintainer noticing a chat "knew about" an unopened doc** | **live** — 17 `session fallback` + 1 `in-memory`; frontend sends `active_doc_id=''` on **344 of 445** turns |

> **46 rows — 16 open, 30 closed or retired, as of 2026-08-01 (re-measured with the script below).** ✅ **Item 44 was filed, diagnosed, fixed and verified live inside one day** — the second item to go the whole way in a session, after 39, and for the same reason: **the observable was named before the fix was written.** ⚠️ **It also needed two fixes and each was invisible until the other landed**, which no amount of source reading had shown in four sessions of `500`s. ⚠️ **Items 16 and 37 closed the same day; their bodies are in [`resolvedissues.md`](resolvedissues.md) and in the retirement banner below, and `item 16` still resolves to a row here.** ⚠️ **The suite is `0 failed` as of 2026-07-31 (item 18). Every earlier note here says "expect 2 failed"; those are historical. A failure now is a real one.** Items 32 and 33 were filed and fixed on 07-30, 30 closed the same day; 34 filed on 07-31, then 35 and 36 the same day — **both found while investigating 34 rather than by looking for them**, which is the argument for reproductions over inference. **Item 5 closed by leaving this file**: it was a working rule, not a defect, and four closures failed because a state description ("committed today") is undone by the next hour's work. Measured, not counted by hand ([`CLAUDE.md`](../CLAUDE.md) §5 — *numbers in prose are claims with no test*). **Open: 3, 8, 9b, 12, 13, 14, 20, 23, 25, 27, 34, 35, 40, 41, 42, 43, 44.** ✅ **Item 39 filed, fixed, verified live and closed inside one session (2026-07-31 → 08-01)** — the only item so far to go the whole way without a recurrence, and the reason is that the observable was named *before* the fix was written. ✅ **The 30/31/32/33 document-corruption cluster is fully closed as of 2026-07-31; only 34 and 35 remain, both S4-today.** ⚠️ **31 and 33 are *fixed but not verified* and deliberately still count as open** — a fix nobody has watched fail is not a closed item, and both share the same predicament: item 30's fix removed the condition that would trigger them. A row is closed when its Item cell is struck through; that is the only definition, because a Status cell like *"detection live; prevention open"* is not machine-readable and should not be. Re-derive with:
>
> ```
> cd /Users/cedrik/odysseus && python3 -c "
> import re
> L=open('docs/todo.md').read().split('\n')
> e=next(i for i,l in enumerate(L) if l.startswith('**Numbers are never reused'))
> r=[l for l in L[:e] if re.match(r'^\| (\d+[ab]?) \|', l)]
> o=[x for x in r if '~~' not in x.split('|')[2]]
> print(len(r),'rows —',len(o),'open,',len(r)-len(o),'closed');print('open:',', '.join(x.split('|')[1].strip() for x in o))"
> ```

**Bodies for closed items live in [resolvedissues.md](resolvedissues.md), cited by title.** Migrated 2026-07-30 — 15 bodies, 116 lines. **The table above stays complete, retired rows included: it is the number registry, and it is what enforces *"numbers are never reused"* now that a closed item's prose is in another file.** So `item N` always resolves here, whether or not its body still lives here. ⚠️ **There are ~40 numeric `item N` citations in `.py`/`.js` source comments** — 8 point at item 1 alone — and they now resolve to a table row rather than a body. Cite by title when you touch one.

**Numbers are never reused.** A retired item keeps its number and a `⊘` row, because renumbering has silently rotted cross-references four times (see *Notes & constraints*). Item 2 split into 2a/2b, and 9 into 9/9b, rather than taking new numbers, for the same reason.

> ⚠️ **Item 23 changes how item 8's evidence should be read**, and the pair is reciprocal (#8↔#23) so neither can be renumbered quietly. A turn that reports *"stopped without producing an answer"* may have produced one — in the reasoning channel. **Compare `thinking` against `content` before filing another item 8.**

> **Next, in order.** Ordering follows leverage, not severity. **Re-ranked 2026-08-01 (second pass), after items 41 and 44 landed and item 42's headline was disproved.** Everything the 07-31 list ranked first has now been either done or shown to be the wrong question.
>
> **0. ✅ DONE 2026-08-01 — snapshot taken and verified.** `~/odysseus-snapshots/odysseus-evidence-2026-08-01.tar.gz`, **five** files (the three from 07-29 plus `search_engine_error.log` and `data/settings.json`, both of which became evidence this week), app confirmed down with `lsof`, before/after source hashes identical. Fingerprints and the corrected verify commands are in [qwensetup.md](qwensetup.md). **This was the only irreversible item on the list.**
>
> **1. ✅ DONE — item 41 closed.** Both paths verified live; the streaming samples ruled the token cap out of items 8 and 23 and made item 40 look worse than documented. See below.
>
> **2. Item 40's discriminating test — NOW THE TOP ITEM, and it just got bigger.** Two `round=1` measured at **110.161 s** and **110.092 s** on 2026-08-01, against the 40–50 s this item documents. *"Compare round-1 time for turns with a document open against turns without."* **All three named causes are now eliminated, and the cold-load one with the load independently attested** (a confirmed 6.7 GB reload cost **~2.6 s** against a ~55 s penalty). Only mid-array volatile blocks remain. ⚠️ **Do not move the block on the strength of the hypothesis** — the placement is deliberate and this project has shipped that trade backwards before.
>
> **3. Item 35 — two minutes, and READ THE OBSERVABLE FIRST.** Restart, clear caches, switch chats with the doc panel open. **Expect NO `[doc-map] … not copying`**; baseline is 3 in 6 switches over 40 s. 🔴 **It is a `console.warn` (`static/js/document.js:4917`), so it is only visible in the BROWSER** — Safari → Entwickler → Konsole; ⌘⇧R is Reader, not reload. **A grep of `app.log*` returns 0 and always would have**, which against an absence-shaped observable reads exactly like a pass ([`CLAUDE.md`](../CLAUDE.md) §1). ⚠️ Do not read *"nothing was corrupted"* as verification — the guard already prevented that.
>
> **4. Item 42's stage 2 — one message in session `11ea1727`.** Confirms or kills the dead-tag branch, which is now the item's entire severity after the memory argument was disproved. If it answers instead of failing, the source reading is wrong and no code change is needed.
>
> **5. Item 44's two uncovered halves, if the tidy is going to be trusted.** Its **archiving branch has never run live** (all 28 verdicts came back `keep`, so `retire_document` was not exercised) and **verdict quality under a suppressed reasoning channel is unmeasured** — before suppression the same endpoint said mostly `junk`, after it says all `keep`. *"The junk detector now finds no junk"* is worth one deliberate look.
>
> **6. Measure rule adherence — five same-prompt runs, each in a NEW chat with the document cloned in.** First reading is **1 of 4** (item 20). One number decides whether item 20's remaining rules are worth reviving, whether item 8's active half is needed at all, and whether item 12 was ever a model problem. ⚠️ **Score item 8's predicate by comparing `thinking` against `content`, not by the guard's notice** — see item 23. ⚠️ *Item 32's tidy no longer destroys the clones, so the protocol is safe to run.*
>
> **7. Item 27 — merge instead of clobber.** A LAN address in the prompt removes every document tool, so the ESP32 workflow cannot produce a document at all. Root-caused, reproduced both directions, **and it has no tests whatsoever**. Fix (a) alone is a few lines; leave (c) for a separate, measured change.
>
> **8. Item 23 — decide the report-only fallback.** S2, seen live. Surfacing reasoning-channel text when a turn produced **no content at all** is report-only, the class that ships on test evidence (11, 21, 28 all did). **Do not touch the parser** — the layer was checked and the `/v1` retraction holds. ⚠️ *Measured: 1 of 22 guard-notice turns.* ⚠️ **Item 41 now makes this readable** — a zero-text round with `finish_reason=length` is truncation, not a channel problem, and the two used to be indistinguishable.
>
> **9. One live turn for 2a**, the last S1 still at *tests* and the only checker never observed firing. Ask for the ESP32 document, read the closing summary for *"Doesn't match the source"*. 🔴 **"Close the open document in the editor first" DOES NOT WORK — corrected 2026-08-01, see item 45.** The server falls back to the newest active document in the session when the client names none, so closing the editor changes nothing the model is handed. fd0f9ba0 asked three times and got nothing because a document was injected regardless. **Use a brand-new chat, or delete the document.** **Opposite precondition to the rule-adherence step; do not collect both in one session.**
>
> **10. Item 3's prevention gap** — `find_stale_values` has one production caller inside `EditDocumentTool`, and `update_document` bypasses the lint entirely. *(Re-verified 2026-07-31; grep, do not trust line numbers.)* Interaction: item 7's live guard promises *"I'll rewrite the document in full instead of patching"*, routing every edit failure into the one path with no lint.
>
> **11. Item 13** — friction, but it has obstructed debugging three times, most recently making two routine `404`s look like a defect for two turns. ⚠️ *`start-macos.sh:292` is a bare `uvicorn` CLI invocation with no log flag — a different fix shape from a `logging.Filter` on a `uvicorn.run` kwarg.*
>
> **12. `_send_email_sync`** (`routes/email_routes.py`) — zero callers, and a docstring claiming it is *"shared by /send and scheduled delivery"* with a SECURITY note that reads as live guidance. Item 38 retired at 4-of-4 superseded, so the prior is that this is too — but a false docstring on a send path is worth ten minutes. *(Not a numbered row; if it turns out real, it earns one.)*
>
> **Done since the 07-31 list, and two of them changed what the list should say:** item 43's value (`max_tokens` → 8192, and the *mechanism* corrected — no preset is sent, nothing "resets"); item 34's `[doc-put-404]` count (**run: 0 spontaneous in 7 opens — too small to close, instrumentation stays**); item 42's stage 1 (**ran, and disproved the item's own headline**); item 41 built; item 44 filed, fixed and closed.
>

> **Owed verifications, not investigations.** Each is one run and closes a row that currently overstates itself:
> **item 7** — one query, not a run: session d16f7a83 turn 1 has **four `edit_document` tool events** against a message reporting **1** attempt. Compare `len(tool_events)` with the reported count on that row; it is the shape of the accumulation bug item 7 was closed on. **item 21** — 2a's and 2b's live scope was recorded on a turn where the model wrote nothing after the tool, i.e. the branch that always worked; re-verify on a turn where it summarises its own work. **item 2a** — one ESP32 document with the editor cleared; **item 9b** — three deliberately long *rounds*. ⚠️ *9b is no longer untested and the evidence points the wrong way: a single round ran **448.7 s** on 2026-07-28 23:38 at `timeout=900` and completed, where the old 300 s cap would have killed it — but it logged `text_chars=0 tool_calls=0`, so that silence was **not** a tool-call payload being generated.* ⚠️ **Do not cite the 457 s turn of 2026-07-29 18:06 as a second data point** — it was 8 rounds, longest 140.5 s, and the timeout is per-read inactivity *within* a round. `response_time` is a turn; `elapsed` is a round; **conflating them is how this item was misread the first time.**
>
> **Closed 2026-07-29 by running them:** ~~item 5~~ **— re-opened the same evening, then a fourth time; finally closed 2026-07-31 by moving it out of this file entirely ([`resolvedissues.md`](resolvedissues.md), *"Uncommitted work, four recurrences"*; the rule is [`CLAUDE.md`](../CLAUDE.md) §6).** The measurement stands (clean clone, `2 failed, 5738 passed`, 2,930 imports resolved) and **was overtaken by work committed after it**. Also item 24 and *"Open in new chat"* (two clones, both carried the source title), and item 25 (macOS run confirms the vacuity) — both still closed.
>
> **Closed and off this list:** item 11 (2026-07-28, built), item 22 (2026-07-28, disproved and retired), item 24 (2026-07-29, fixed).
>
> **Suite: `0 failed` as of 2026-07-31 — the first clean run in this project's record.** Item 18's two CAS tests had never executed (`AttributeError` on a closure) and now do; **mutation-verified** by deleting `Document.version_count == base_version` from the CAS filter and watching exactly those two fail. ⚠️ **Every note in these files written before 2026-07-31 says "expect 2 failed". Those are historical. A failure now is a real one**, and "the usual two" is no longer available to wave one through.
>
> **Collection counts, for the arithmetic they enable:** 5,781 collected / 5,775 passed on 2026-07-30 (M1, 109.30 s, clean tree); prior readings 5,774 → 5,758 → 5,588 → 5,433. ⚠️ **Two traps in that series, both paid for.** A run in the working tree counts uncommitted tests — the 07-29 reading included item 29's 16 — so **compare only against a clean tree** (`git archive HEAD | tar -x` + `diff -rq`). And **a `--collect-only` prediction was 33 low**: replace this line with a measurement, never a prediction.

---

## S1 — wrong output the user trusts

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

### 3. Partial edits leave documents contradicting themselves
Run 127d32b0: 8 edits fixed the prose and missed the summary table, leaving four CO₂ thresholds and three colonization durations in one document.

> ⚠️ **Re-scoped S1 → S2 on 2026-07-31, and re-verified verbatim in the same pass.** Challenged as *"probably a relic"* and it is not: `find_stale_values` still has **exactly one** production caller — `src/agent_tools/document_tools.py:768`, inside `EditDocumentTool` (class opens `:609`) — and `UpdateDocumentTool` (`:514`) still has none. *(Grep `find_stale_values`; the numbers move.)* **What changed is the confidence behind the S1, not the mechanism.** The one component of this that was ever measured — the diff-review overlay writing pre- and post-edit text together — turned out to be an editor bug and was fixed; **the share attributable to the model has never been measured at all.** An S1 resting on an unmeasured remainder overstates what is known, so it drops to S2 until step 0's protocol produces a number. **It stays under the S1 heading below for now — the table is the registry, and moving bodies between sections is how cross-references rot.** *Age is not obsolescence: this item looks stale because its evidence is dated 07-18…07-29 while the 30–36 cluster ate every session since.*

> **Partly re-diagnosed 2026-07-19 — a share of this was the editor, not the model.** The diff-review overlay wrote documents containing **both** pre-edit and post-edit text for the same section; twelve such regions from a *single* Accept click. Fixed — [resolvedissues.md](resolvedissues.md), *"Diff review corrupted documents"*.

✅ **The lint fired live on fb5525eb turn 3, 2026-07-28:** *"⚠️ Still inconsistent — `90%` was corrected in one place but still appears elsewhere."* The same turn reported 4 of 11 edits not applied, so the document was left half-corrected **and said so**.

- **Detection exists** (`find_stale_values()`), surfacing fixed 2026-07-18. **Prevention doesn't** — the model is never asked to fix what the lint finds.
- **Gap:** the lint runs only inside `EditDocumentTool`. A full `update_document` rewrite bypasses it entirely.
- ⚠️ **The interaction with item 7 was filed as a theory and was OBSERVED END TO END on 2026-07-29, session d16f7a83.** Turn 1: four `edit_document` calls, every FIND block rejected, item 7's guard fires — *"I'll rewrite the document in full instead of patching individual passages."* Turn 2: the model does exactly that, `update_document`, **v5 written with no consistency lint at any point.** The guard is honest, the promise is reasonable, and it routes each edit failure into the one write path with no checking. **Any fix here has to cover `update_document`, or item 7's success makes item 3 worse.**
- **How much is the model is an open measurement, not a known quantity** — the editor was manufacturing part of it.

## S2 — silent loss

### 30. ~~Switching chats writes the editor buffer into the other chat's document~~ ✅ CLOSED 2026-07-30
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
- ✅ **All four damaged documents recovered 2026-07-30 and verified by hash** — `986c425e` v3 `ea089a2f7fd8`, `d1c934f7` v3 `59879c9e9631` (`ai`), `c4da7609` v5 `d036765bedd7` (`ai`), `b1754908` v4 `2a6319146b84`. **Appended as a new version rather than overwriting `current_content` in place** — restoring the column alone leaves `version_count` naming a version whose content is no longer there, so the badge and the diff view both lie. The corrupt versions are kept deliberately: they are this item's evidence and the only proof the write crossed chats.
- ⚠️ **Superseded, kept for the shape of it — State as of 2026-07-30 14:00: `b1754908` is still corrupt at v3** (16,295 chars where the clone was 8,578) and the editor displays it inside chat `5bc3c70f`. **v1 is intact at `ea089a2f7fd8` and Q's original at `65580c429b7c`, so nothing is unrecoverable.** Restoring it over the API returns **401** — auth is on and a bare `urllib`/`curl` PUT carries no session cookie. Restore from the UI, or stop the app first.
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
- ⚠️ ~~**Only the empty-buffer branch has been observed being blocked.** The foreign-buffer branch (the 14:24 write into `c4da7609`) falls under the same `_stamp !== activeDocId` condition but **has not been triggered on demand**.~~ ✅ **OBSERVED 2026-07-30 ~16:02 CEST, blocking:**

  ```
  [doc-map] buffer (stamp b1754908…, 8579 chars) does not belong to 79879a2f… (5 chars) — not copying
  ```

  A buffer rendered from `b1754908` while `activeDocId` had already moved to `79879a2f` — **8,579 characters of one chat's document, one map-copy away from a 5-character entry in another.** That is the shape of the 14:24 write into `c4da7609`, caught this time. It fell out of item 31's verification run, not from a protocol aimed at it. **Both branches of the guard have now been seen blocking, and row 1 of item 31's trace shows the delete branch still firing when it should** — so neither is a guard that cannot act.
  - ⚠️ **The same run shows the underlying defect is still firing in normal use**, twice in one session: `[doc-map] buffer (stamp (none), 0 chars) does not belong to aa87b1ce… (17085 chars)`. **The guard is doing real work on ordinary chat switches, not just in a staged repro.** `restoreFn` is still the fix that is owed.
  - ⚠️ **And the guard was already live when those writes happened** — re-checked 2026-07-30. `[doc-put]` records `14:17:24 doc=b1754908 … sha=2a6319146b84` (the recovery) and then `14:24:08 doc=c4da7609 … sha=2a6319146b84` — **byte-identical, into another chat's document seven minutes later** — followed by `14:26:51 … len=1757`. The guard was verified at 12:52 and the file last edited at 14:51, so both writes fall inside the guarded window. They are **item 31(a)**, which this guard was never meant to cover: `saveDocument` writes `activeDocId` with a correctly stamped buffer, so nothing fires. **The distinction matters — *"guard ✅ verified"* is true of the map, and reads as though it covered the writes.**
- ✅ **`window.__docTrace` is why this was found.** A rolling in-page trace of `loadSessionDocs` / `chipRestore` / `switchToDoc` / `closePanel` / `saveCurrentToMap` / `saveDocument`, dumped with `console.log(JSON.stringify(window.__docTrace))`. **Four fix attempts were argued from reading a 10,000-line file and three were wrong; the trace settled it in one run.** ⚠️ It relies on nothing being open at the time, which is the property the console lacked — two runs were wasted on "was the console open, was the panel open, was the precondition met".
✅ **ROOT CAUSE FIXED AND VERIFIED LIVE 2026-07-30 21:27. The item is closed.**

**Not** by making `openPanel` render — that was the filed proposal and it is the wrong shape: `openPanel` is **1,353 lines** (4891–6243) with 23 `activeDocId` references, all inside event-handler closures except a three-line tail (`renderTabs()`, then `showEmptyState()` when `!activeDocId`). Threading a document through it is a large change to a large function.

**The defect is one line earlier: `switchToDoc` flushes the buffer into the map UNCONDITIONALLY**, and after a pane rebuild that buffer is a fresh empty node. So `switchToDoc(docId, { flush = true } = {})`, and the callers that have just rebuilt the pane pass `false`.

- **The flush at restore is not merely wrong, it is redundant** — `closePanel('down')` already flushed while the pane was intact and stamped. Confirmed by observation, not argument: `21:26:47 saveCurrentToMap … bufLen=8579 mapLen=8579 blocked=false` at minimize, and the restore 25 s later renders exactly those 8,579 characters.
- **It could not have lost data either way.** By the time it runs the buffer is already gone, and the stamp guard was blocking the call regardless — so removing it is *outcome-identical*, an attempt removed rather than a write.
- ⚠️ **`restoreFn` was not the only site. Three more were found while checking the call list**, all `_ensureDocPaneMounted()` → `switchToDoc(…)`: `_restoreDetachedEmailDoc`, the email-draft path, and both branches of `loadDocument`. **`_ensureDocPaneMounted` rebuilds only *sometimes***, so they cannot hard-code `flush: false` — it now returns whether it rebuilt and each caller passes `flush: !_rebuilt`. **The guard is why these were harmless; nobody had noticed they were the same shape.**

**The three stages of one sequence, all recorded 2026-07-30:**

```
12:48  saveCurrentToMap len=0        →  switchToDoc len=0       17,085 chars emptied
12:52  saveCurrentToMap blocked=true →  switchToDoc len=17085   guard catches it
21:27  (no saveCurrentToMap at all)  →  switchToDoc len=8579    nothing wrong is attempted
```

The 21:27 trace goes straight from `chipRestore` to `switchToDoc`, with no `[doc-map]` warning, no `[doc-put]` and no `[doc-del]`. **The guard stays as defence in depth** — it is what caught the foreign-buffer branch at 16:02 and the three call sites above, and it costs nothing.

### 38. ~~Four functions look like calls that were never wired up~~ ⊘ RETIRED — 4 of 4 disproved

> ⊘ **Retired 2026-07-31, hours after being filed, by investigating it.** All four are **deliberate or superseded**, and **wiring three of them up would have caused a regression.** The hypothesis was mine and it was wrong in every instance.
>
> **The transferable finding, which is worth more than the item was:** *the reason a function is uncalled is never recorded at the function.* In all four cases the explanation sat at the site that deliberately does **not** call it — a branch, a start-up comment, a superseding sibling. **So a zero-caller sweep cannot be triaged from the definitions; it can only be triaged from the callers that aren't there**, which is the same lesson as item 16's *"a count of files is not a count of behaviours"*, one level up. ⚠️ **And it is why nothing was deleted:** the deletion request that produced this item would have been the safe half; the *wiring-up* I was proposing was the dangerous one.

- ❌ **`_compact_tool_line`** (`src/agent_loop.py:1440`) — **not item 20's shape; the opposite.** `_assemble_prompt`'s compact branch emits `- \`{name}\`` and drops the section **on purpose**: its own preamble says *"Only the tool schemas provided by the API are available… do not write tool syntax or tool instructions in chat."* This function injects fenced usage examples, i.e. exactly the syntax the prompt forbids — **and item 28 is *"the model writes the tool call instead of making it."*** Calling it invites that back. ⚠️ **This setup uses the compact prompt** (`_is_api_model` is True for `qwen3.5:9b-32k`), so it would have landed here.
- ❌ **`_event_pings_loop`** (`src/task_scheduler.py:612`) — **deliberately unwired, and the reason is at the start-up site:** *"Calendar event reminders are represented as Notes by the calendar UI, so the Notes scanner is the single reminder dispatch path. **Running the old event scanner too caused duplicate emails/notifications for the same calendar event.**"* The teardown at `:584` still cancels `_event_pings_task` defensively, which is what made it look half-wired — `getattr(self, attr, None)` returns `None` and nothing breaks.
- ❌ **`_looks_like_notes_list_request`** (`src/agent_loop.py:74`) — **superseded by a sibling with a broader remit**, `_looks_like_notes_calendar_followup` (`:2437`), which *is* called and drives the notes/calendar tool clamp.
- ❌ **`_is_private_address`** (`services/search/content.py:117`) — **superseded by the two-tier design and calling it would revert a fix.** It unions `_is_hard_blocked_address` with `_is_gated_private_address`; the gated tier exists so `web_fetch` can reach the LAN on purpose, which is the whole of the 2026-07-27 change.

⚠️ **The one thread that survives and was NOT part of the four:** `_send_email_sync` (`routes/email_routes.py:4126`) has zero callers while its docstring claims it is *"shared by both /send and scheduled delivery"* and carries a SECURITY note on owner scoping that reads as live guidance. The real `/send` (`:4400`) inlines the SMTP work under `Depends(require_owner)`, so **that** endpoint is scoped. **Still unchecked: whether scheduled delivery exists, and whether it is owner-scoped.** Given the four above, the prior should be that it too is superseded — **but a false docstring on a security-scoped send path is worth the ten minutes.**

⚠️ **Separately, and not one of the four:** `_send_email_sync` (`routes/email_routes.py:4126`) has zero callers while its docstring claims it is *"shared by both /send and scheduled delivery"* and carries a SECURITY note on owner scoping that reads as live guidance. The real `/send` (`:4400`) inlines the SMTP work under `Depends(require_owner)`, so **that** endpoint is scoped. **Unchecked: whether scheduled delivery exists at all, and whether it is owner-scoped.** The false docstring is the problem, not the 47 lines.

**~250 further lines are unreferenced and plausibly deletable** — seven `_cookbook_*` helpers, `_ssh`/`_ssh_ps`, `_format_error_response` (defined twice, across a *forked* `research_handler.py`, which is the larger smell), `_embed` (defined three times, in `rag_vector.py`, `memory_vector.py` and `tool_index.py`), `_is_local_openai_compat_url`. **Nothing was deleted:** removing production code on a grep is the failure item 16 exists to describe, and no suite run is available from the sandbox.

### 37. ~~Model probes ignore session-backed credentials, so subscription endpoints report as failing~~ ⊘ RETIRED

> ⊘ **Retired 2026-07-31 — out of scope for this deployment. NOT disproved: the divergence below is real and unfixed.** The maintainer will not add a subscription endpoint, so the branch never executes here. **The condition is falsifiable and is written down precisely so this is not "forgotten":**
>
> ```
> cp /Users/cedrik/odysseus/data/app.db /tmp/probe.db && sqlite3 /tmp/probe.db \
>   "select count(*) from provider_auth_sessions; select id,name,provider_auth_id from model_endpoints;"
> ```
>
> **If that count is ever non-zero, this item is live again.** Recorded this way because *"settled constraints"* in this project have been false before — *"local models get no tool schemas at all"* was the stated reason item 8's active half had to be a text nudge, and that nudge destroyed a document. **A retirement that rests on a premise must carry the test of the premise.**

**Found 2026-07-31 by answering item 16's open question** — *"what does `resolve_endpoint_runtime` do that a raw `api_key` does not?"* — which was filed as the check that would decide whether `_resolve_probe_key` was a defect or deletable dead code. **It is a defect.**

`resolve_endpoint_runtime` (`src/endpoint_resolver.py`) branches on `provider_auth_id`: when set, it resolves **refreshable credentials at call time** via `resolve_runtime_credentials(auth_id, owner=…)` **and overrides the base URL**. Static-key providers use `ModelEndpoint.api_key`; session-backed ones cannot.

**Every live probe caller takes the raw column instead.** `endpoints_cache[ep_id] = {"base_url": ep.base_url, "api_key": ep.api_key}` (`routes/model_routes.py:1812`, same shape at `:2259`), then `_probe_single_model(base, ep_data.get("api_key"), …)` at `:1825`, `:1887`, `:2273`.

- **Consequence:** for any endpoint with `provider_auth_id` set, the probe sends a static key that is null or stale, against a base URL that may be wrong, and reports the model **unreachable when it is fine**. S3 — the task visibly fails and the user is told the wrong reason.
- 🔴 **`_resolve_probe_key` (`routes/model_routes.py:684`) does it correctly and nothing calls it**, while 5 tests assert on it. **This is item 16's shape with a user-visible consequence, and it is the first instance the audit found rather than inherited.** Reciprocal (#16↔#37).
- **Fix is to call the function that already exists** — route the probe callers through `_resolve_probe_key`, which is what its 5 tests already describe.
- ⚠️ **TESTED 2026-07-31 AND IT CANNOT FIRE HERE — severity S3 → S4 today, S3 latent.** Against a copy of `app.db`: **one endpoint total** (`localhost:11434`), `provider_auth_id` **NULL**, and `provider_auth_sessions` holds **0 rows**. There is no session-backed endpoint on this installation, so the branch that diverges is never taken. **The defect is real in source and dormant in practice**, and it becomes live the day a subscription endpoint is added — which is the least likely day for anyone to suspect the probe. Re-derive with:
  ```
  cp /Users/cedrik/odysseus/data/app.db /tmp/probe.db && sqlite3 /tmp/probe.db \
    "select id,name,provider_auth_id from model_endpoints; select count(*) from provider_auth_sessions;"
  ```
- ❌ **The unit-level demonstration could not be run in the sandbox** — `import src.endpoint_resolver` fails on `ModuleNotFoundError: httpx`, the unpinned-dependency problem [`CLAUDE.md`](../CLAUDE.md) §4 describes. So the divergence is established **by reading, not by executing**, and that is the whole of the evidence.
- **The verification that does not need a subscription account is a wiring test:** assert the probe path resolves credentials rather than reading `ModelEndpoint.api_key` off the row. It fails today, passes after the fix, and needs no session-backed endpoint to exist — the deliberate structural-test exception in §4, and the only way this gets checked before someone hits it in production.

### 36. ~~The document-tab actions menu is unreachable — its button is never rendered~~ ✅ ACCEPTED AS IS

> ✅ **Closed 2026-07-31 by decision, not by a fix — and the decision is the content.** Every action has another route (walked below), so **no user is missing anything**, and the cost of leaving it is one ~300-character template string built per tab per `renderTabs` call and immediately discarded. That is not a performance problem. **Wiring the button in would add a UI surface nobody asked for; deleting ~150 lines plus a stylesheet risks more than it returns and needs a suite run.** Neither is worth it.
>
> ⚠️ **What is kept is the trap, because the code still reads as if the feature exists.** `showDocTabMenu` is 133 lines, wired to a handler, styled, and dismissable — and unreachable. **Anyone reading `renderTabs` will assume the menu ships.** If it is ever touched, the one-line fix is to interpolate `${menuBtn}` into the tab template; the one-line check that it is still unreachable is `grep -c '\${menuBtn}' static/js/document.js` → `0`.

**Found 2026-07-31 while a probe of mine returned `[]` twice and I blamed the panel.** `renderTabs` builds the button — `const menuBtn = '<button class="doc-tab-menu-btn" …>'` — and **never interpolates it**: `${menuBtn}` occurs **0 times** in the file. The emitted tab is `${verChip}${langChip}<span class="doc-tab-title">…` plus `.doc-tab-close`.

- **This is not dead code, it is an amputated feature.** Everything downstream of the button exists and is wired: a **133-line** `showDocTabMenu()`, a click handler (`e.target.closest('.doc-tab-menu-btn')`), a click-outside dismiss, an exclusion in the tab-activation handler so the menu click doesn't also switch tabs, and **its own injected stylesheet** (`doc-tab-menu-styles`) with hover, dropdown-item and delete-action rules. The menu offers **Close, Copy, Delete, Download, Run, Save, Send signed reply**.
- ✅ **Severity settled S4 — the list was walked 2026-07-31 and every action has another route.** The menu's eight cases are `save, copy, run, preview, download, signed-reply, close, delete`. **Save and download** are the footer split button (`#doc-copy-export-split` → `#doc-footer-copy-btn` / `#doc-footer-export-btn`); **run** is `.doc-tab-play`; **close** is `.doc-tab-close`, the ✕ already on every tab; **signed-reply** is the compose footer's reply button (`_sendSignedReply(activeDocId)`); **delete** is the Library. **So nothing is unreachable to the user — only to the code.** It is a duplicate access path that was never plugged in, not a missing feature, and no one has lost anything by it.
- **Same shape as item 16** — an orphaned implementation that greps as live. A `grep -c '\${menuBtn}'` is the whole test, and it is the check that distinguishes "written" from "reachable" for every other UI string in this file.

### 35. `loadSessionDocs` flushes the editor buffer into the document it is switching TO
**Found 2026-07-31 by reading the caller frames on a blocked copy, not by looking for it.** In the restore branch, `activeDocId = target.id` (`:7589`) runs **before** `switchToDoc(target.id)` (`:7594`), whose first act is `saveCurrentToMap()` — which reads `activeDocId`. So the flush is aimed at the document being arrived at while the buffer still holds the one being left. `switchToDoc(docId, { flush = true } = {})` defaults to flushing and this caller passes no options.

```
[doc-map] buffer (stamp (none), 300 chars) does not belong to 2ca3ecfd… (14920 chars) — not copying
    via switchToDoc@document.js:4569
    via @document.js:7594
```

- ✅ **Second observation, 2026-07-31 10:02:45, with the magnitudes attached — this is the one to cite.** `loadSessionDocs(4983ee40, wasActive=4bdc724c)` → `saveCurrentToMap active=0b255037 stamp=4bdc724c bufLen=0` → `switchToDoc 0b255037 len=8701`, and the guard: *"buffer (stamp 4bdc724c, 0 chars) does not belong to 0b255037 (8701 chars) — not copying · via switchToDoc@:4569 · via @:7594"*. **An empty buffer against an 8,701-character map entry.** Unguarded, that copy zeroes the entry — and item 33's delete-on-empty is three lines further down the same function. **35 → 30 → 33 in a single trace.** The earlier instance the same morning was 300 chars against 14,920; this one is cleaner because the buffer is empty, which is precisely the state the two map-derived deletes test for.
- ✅ **Now directly countable, as a side effect of item 33's instrumentation.** A `switchAway` entry with **`prev === to`** is this item's signature — `activeDocId` was already the target when `switchToDoc` was called. **3 of 6 switches in 40 seconds of ordinary chat use, 2026-07-31 15:10–15:11.** That is the frequency claim this item previously asserted from source. `console.table(window.__docTrace.filter(e => e.ev === 'switchAway'))`.
- ⚠️ **And it has a second consequence nobody had connected: it makes item 33's branch unreachable on this path** (`prevId !== docId` fails). **Fixing 35 would expose 33's branch to chat switches for the first time** — so 33 should be verified *before* 35 is fixed, or the fix changes the thing being tested. Reciprocal (#33↔#35).
- **Structural, not a race.** It happens on **every** restore-mode chat switch with the panel open. This is the mechanism behind the 2026-07-30 observation that *"the `stamp=(none)` branch also fired twice on ordinary chat switches — the guard is the only thing catching it"*, which was recorded as a symptom with no cause.
- **The other branch is safe by accident, not by design:** `activeDocId = null` at `:7557` makes `saveCurrentToMap` return at its first line, so the non-restore `switchToDoc(target.id)` at `:7603` never attempts the copy.
- **S4 today, S2 latent.** Item 30's guard absorbs all of it — a console warning, no write, nothing lost. What earns it a row is that **the guard is load-bearing in ORDINARY use**, and item 34's session showed the same guard being satisfied by laundered state one save later (`saveDocument`'s mismatch branch re-stamps the buffer, so the next write is legal by construction). A systematic mispairing sitting behind a guard that can be laundered is not a stable place to leave things.
- ✅ **FIXED 2026-07-31 — `switchToDoc(target.id, { flush: false })` at `document.js:7615`** *(grep `Minimize restored doc failed`)*, using the parameter item 30's fix already added. Nothing legitimate can be flushed after `activeDocId` was reassigned two lines earlier, and `:7557` may already have deleted the previous document's map entry. Per the comment at `:4567`, this **removes an attempt, not a write**. `node --check` only — **no JS harness**.
- ⚠️ **UNVERIFIED, and the observable is an ABSENCE.** Restart, clear caches, then switch chats with the doc panel open and minimised-restore active. **Expect no `[doc-map] … not copying` warning, and `switchAway` entries with `prev === to` to stop being followed by one.** The baseline to beat is **3 such warnings in 6 switches over 40 seconds** (2026-07-31 15:10–15:11), so a clean two-minute session is a real signal rather than a quiet one. ⚠️ **Do not read "no corruption" as verification** — the guard already prevented that; the change is about the attempt.
- ⚠️ **Do not verify this by watching it not happen.** The guard blocks it today either way; the discriminating observation is the **absence of the `[doc-map]` warning** on a restore-mode switch, not the absence of a write.
- 🔴 **And that warning is a `console.warn`, so it can only be read in the BROWSER — added 2026-08-01 after nearly recording a pass from the wrong file.** `[doc-map] … not copying` has exactly **one** emitter in the tree, `console.warn` at `static/js/document.js:4917` *(grep the string, not the number)*. **It has never been able to reach `data/logs/app.log`.** A `grep -c 'not copying' data/logs/app.log*` run on 2026-08-01 returned **0 on both files** — which is what it would return whether the fix worked, failed, or was never applied. **That zero measured the logging configuration** ([`CLAUDE.md`](../CLAUDE.md) §1), and against an item whose whole observable is an absence it would have read as the pass. **Safari → Entwickler → Konsole.** ⚠️ Nothing server-side can substitute: `[doc-put]` records the write, and this item is about an *attempt* the guard already blocks, so the write is absent either way.

### 34. An aborted document stream orphans its placeholder as `activeDocId`
**Found 2026-07-31, from the maintainer noticing a *"failed background stream"* message and asking whether it was related.** It is — this is the clearest *source* of the unstamped-buffer state items 30 and 31 have been chasing, and it arrives through a path neither item mentions. Reciprocal with #9b (same event, server side) and #30 (the state it produces).

**The chain, read from source:**

1. `doc_stream_open` creates a synthetic document — `docId = '_streaming_' + Date.now()` (`static/js/document.js:10761`) — puts it in `docs`, sets `activeDocId` to it, calls `openPanel()` (**which rebuilds the pane, so the textarea is a fresh unstamped node**), then writes title and content into that textarea **directly**. It never calls `switchToDoc` or `populateEditor` — **the only two functions in the file that stamp `textarea.dataset.docId`.**
2. The placeholder is migrated to the real id **only** in `handleDocUpdate` when `doc_update` arrives (`:11020`), and `_streamDocId` is cleared **only** in `streamDocFinalize()` (`:10941`), which the same event triggers.
3. **Nothing cleans up on abort or error.** Switching chats mid-stream calls `abortCurrentRequest` (`static/js/chat.js:4037`), which is what produces the console's `AbortError: Fetch is aborted` — so `doc_update` never arrives.

**Result: the `_streaming_…` entry stays in the map, `activeDocId` keeps pointing at a document that does not exist server-side, and the editor holds streamed content with no stamp.**

- ✅ **Observed live, not only read.** `_streaming_1785481974674` sat in the map as `activeDocId` through `switchToDoc` and `saveCurrentToMap` entries in the 2026-07-31 trace, with the `AbortError` in the same console. **17 `Doc streaming: open` events that day**, so the path runs constantly.
- ⚠️ **A confirmed source of unstamped buffers is not the explanation of every one.** The 07:06 New Chat instance under item 31 has buffer lengths pointing at a different document; **do not fold the two together** on the strength of the shape matching.
- **Item 9b files the server side of the same event and neither item mentions the other.** A stream that fails mid-turn leaves this wreckage in the client; a stream the user aborts by switching chats leaves the identical wreckage with no server-side trace at all.

**Re-read against source 2026-07-31 (later session). Four amendments, one of them a correction to this item as filed.**

- 🆕 **A reaper already exists, and the item was filed without it.** `saveDocument`'s 404 branch — `static/js/document.js:9835–9849`, *grep `res.status === 404`, do not trust the number* — deletes the orphan from `docs`, nulls `activeDocId` and re-renders the tabs. Its own comment names this exact case: *"Streaming/empty email drafts can leave a local tab pointing at a temp or already-deleted document."* **So the placeholder is not permanent: it is reaped by a network round-trip on the next autosave, and the "clean up on abort" fix below is smaller than proposed.** The reaper discards the streamed content silently, which is correct here — the server never had it.
- ⚠️ **But `_streamDocId` outlives its referent on every cleanup path.** `_streamDocId = null` occurs **exactly once in 11,600 lines** — `streamDocFinalize()` (`:10941`), whose only caller is `handleDocUpdate` (`:10998`); it is exported but called nowhere outside `document.js`. The 404 reaper clears the map entry and `activeDocId` and **not** the global. `loadSessionDocs` (`:7554–7557`) deletes the placeholder on **every** chat switch and nulls `activeDocId`, and does not clear it either. **Both cleanups leave a global pointing at an id no longer in the map.**
- 🆕 **Consequence of the line above: the temp→real migration is skipped.** It is gated on `docs.has(streamingId)` (`:11020`), so once the reaper or a chat switch has removed the placeholder, a `doc_update` arriving afterwards falls through to the dedup-by-title path below it.
  - ❌ **RETRACTED the same day, by reading one more screen of the function I had already cited: *"a route to a duplicate document — that is item 32's input"* is wrong.** The fall-through is `docs.set(…)` at `:11128–11136` — **pure client-map manipulation, no fetch on the path.** It cannot create a server row, so it cannot reach item 32's tidy, which groups server documents. The reciprocal-with-32 marking was wrong too. **Filed and retracted within the hour, without the experiment being needed** — the claim was reachable from source and I stopped reading at the line that confirmed the first half.
  - **What actually survives the retraction is smaller and client-side.** `docs.delete(streamingId)` runs **only inside** the migration block (`:11022`). So when the placeholder is still in the map, the skipped migration leaves it there *and* adds the real document — **two tabs for one document**, one of them an id the server has never had. Harmless to stored data; it is tab clutter with a live orphan behind it.
  - ✅ **CONFIRMED LIVE 2026-07-31 — a session-less placeholder leaks into other chats.** `streamDocOpen` on a **pending New Chat** (nothing sent, so `currentSessionId` is still `null` — `sessions.js:2204`) creates the placeholder with `sessionId: ''`. Switching to an unrelated chat then renders **two tabs**: `["_streaming_1785485819404", "2ca3ecfd-…"]`. Both `loadSessionDocs` (`:7555`) and `renderTabs` skip only when `doc.sessionId &&` is truthy — an exemption written for session-less email drafts — so **the orphan is shown in every chat** until it is clicked or the page reloads. Confirmed twice over: by the tab list, and by elimination, since anything with a real foreign `sessionId` would have been deleted at `:7555`.
  - ⚠️ **The sharp edge: clicking the ghost tab self-heals, but TYPING into it first loses the typing with no message.** Click → `switchToDoc` renders and stamps → the input handler sets `_userDirtyDocId` and schedules `saveDocument({ silent: true })` (`:6051`) → stamp matches, so nothing blocks → PUT → 404 → the reaper deletes the map entry, nulls `activeDocId` and re-renders the tabs. `showError('Document no longer exists')` is gated on `!silent` (`:9848`), and autosave is silent. **The tab disappears, the text is gone, and nothing is said.** Traced end-to-end in source; not yet reproduced.
  - ⚠️ **The normal path does not reach this** — `chat.js:1240` awaits `materializePendingSession()` before streaming, so a stream started by sending a message has a real `sessionId`. The reachable route is a document stream opening while a New Chat is still pending.
- ❌ **Correction — the guard that bounds this is not the one this item named.** The original bullet credited *"the stamp check in `saveCurrentToMap`"*. That function does block an absent stamp (`:4889` — `_stamp !== activeDocId` is true for `null` unless buffer and map entry are both empty), but it is not what stands between the orphan and the network. **`saveDocument`'s guard deliberately does not block a missing stamp** (`:9740` requires a *mismatched* one; missing is recorded only — item 31's decision of this morning, taken because failing closed would have refused ~14 % of legitimate saves). The placeholder is created without `lastSyncedContent` (`:10762`), so the no-op skip at `:9760` cannot fire either. **The PUT does reach the network, carrying the streamed content, addressed to an id the server has never had.** What the guards bound is the *cross-document* write; they do not bound the orphan.
- ✅ **The "absence proves nothing" reasoning re-verified in source.** In `update_document`, `routes/document_routes.py` raises the 404 (`:647` after this session's edit, `:630` before it) **before** the `[doc-put]` line (`:659` / `:641`), so no orphaned PUT could ever have appeared in `app.log`. *Both numbers moved because the instrumentation below was inserted between them — grep `doc-put`, do not trust either.* The absence measured the instrumentation, not the behaviour — the same shape as the missing `DELETE` lines and the DEBUG-level greps in [`CLAUDE.md`](../CLAUDE.md) §1.
- ✅ **Instrumented 2026-07-31, report-only:** `[doc-put-404]` logs `doc_id`, content length and `base_version` immediately before that raise. **Content is not logged**, only its length. This is the measurement item 31 earned the right to insist on: it turns *"an absence that proves nothing"* into a count of how often the orphan actually reaches the network now that the reaper exists. **Remove it when this item closes.**

**✅ Reproduced on demand 2026-07-31 10:05 CEST — the first scripted reproduction in the 30/31/33/34 complex.** Driven from the Safari console through the public surface (`window.documentModule` exports the whole chain — `:11597–11631`, assigned to `window` at `:11633`; *grep `window.documentModule =`, do not trust the number*); no waiting for an abort, no reverting a fix.

```js
(async () => {
  documentModule.streamDocOpen('Repro 34', 'markdown');
  documentModule.streamDocDelta('x'.repeat(500));
  await documentModule.saveDocument({ silent: true });   // 1st — blocked
  await documentModule.saveDocument({ silent: true });   // 2nd — writes
})();
```

- ❌ **Correction, from running it: the pane rebuild is CONDITIONAL, and the item implied it always happens.** `streamDocOpen` calls `openPanel()` only `if (!isOpen)` (`:10775`). **Panel already open → no rebuild → the textarea keeps the PREVIOUS document's stamp**, which is a *mismatch* and `saveDocument` does block it. **Panel closed → fresh unstamped textarea**, which is the *missing*-stamp case and is **not** blocked. Two states, two different guard outcomes; the filed chain describes only the second.
- ⚠️ **The guard does not block the write — it defers it by one save cycle and launders the stamp.** The mismatch branch (`:9743–9748`) re-renders `docs.get('_streaming_…').content` into the textarea and sets `textarea.dataset.docId` to the placeholder id. **The second save therefore passes the stamp check by construction**, `saveCurrentToMap` records `blocked:false`, and the PUT goes out. This is the same laundering the `saveCurrentToMap` comment at `:4868` was written about, occurring in the function that comment says could not close the hole.
- ✅ **Server-side evidence, the thing no JS test can produce:** `[doc-put-404] doc=_streaming_1785484957239 len=500 base_version=1` — `app.log`, 10:05:26,124 CEST. The client trace records the same event at **08:05:26.107 UTC**, 17 ms earlier. **Both clocks tied to one event for the first time**, which is a check on the two-hour rule in [`CLAUDE.md`](../CLAUDE.md) §1 rather than another instance of it.
- ✅ **The reaper is confirmed, and only on the second cycle.** `getCurrentDocId()` returned the placeholder after save 1 and `null` after save 2. **So the orphan survives exactly as long as the stamp is wrong** — the guard prolongs it rather than ending it.
- ⚠️ **A transient nobody had seen: between `streamDocDelta` and the repair, the textarea held the stream's 500 characters under the REAL document's stamp** (`[doc-save] target=_streaming_… stamp=2ca3ecfd…`). Anything repointing `activeDocId` back at `2ca3ecfd` in that window writes the stream over a 2,337-character document **with the stamp guard approving it** — item 30's corruption shape, reached from this item's path. Nothing did; the document was untouched (`len=2337` throughout the trace).
- **`base_version=1` rode along with the orphaned PUT** — the placeholder's own `version: 1` (`:10767`). Harmless while `_streaming_<ts>` cannot collide with a UUID, and worth knowing it is not `null`.

**✅ THE MEASUREMENT WAS TAKEN 2026-08-01, AND IT DOES NOT DECIDE THE ITEM — n is too small to conclude anything.**

- `grep -c '\[doc-put-404\]' data/logs/app.log*` → **`app.log:1`, `app.log.1:0`.** And **that one hit is this item's own scripted reproduction**: `[doc-put-404] doc=_streaming_1785484957239 len=500 base_version=1` at 10:05:26,124 — the same line already quoted above as the repro's server-side evidence, and `len=500` is `'x'.repeat(500)`. **Spontaneous occurrences in ordinary use: zero.**
- ⚠️ **But the denominator is 5.** Since the instrumentation went live (restart `2026-07-31 09:53:21`) there have been **5 `Doc streaming: open` events**, against 17 on 07-30 alone. **A count of 0 in 5 opportunities is not evidence of absence** — it is a week of ordinary use short of one. *(The wrong denominator to quote is `[doc-put]`, which is 8 over the same window and counts writes that never involved a stream.)*
- ⚠️ **So do NOT close this as bounded by the reaper, and do NOT build the fix yet.** Both readings are still open and the instrumentation is what separates them. **Leave `[doc-put-404]` in** — the *"remove it when this item closes"* note above stands, and this item is not closing.
- **Re-read the count after a week of ordinary use**, quoting `Doc streaming: open` in the same breath: `grep -c '\[doc-put-404\]' data/logs/app.log*; grep -c 'Doc streaming: open' data/logs/app.log*`
- ✅ **First unscripted instance of this item's own trigger, 2026-08-01 09:52 — and it did NOT produce a 404.** The maintainer **opened the document while the stream was running** and the UI showed *"[Background stream encountered an error]"* — this item's founding symptom, arrived at independently. **`[doc-put-404]` did not increment: still 1, still only the repro.** Denominator is now **7 `Doc streaming: open` since instrumentation, 0 spontaneous hits.**
  - ⚠️ **Server side there was no error of any kind.** Round 1 completed normally (82.4 s, 54 chars, 1 tool call) and the tool executed; the next turn found the document by session fallback (`[doc-inject] found by session fallback: title='Tomato Cultivation Basics'`). **The red banner is client-side only** — the document stream being aborted — which is exactly what this item says and is worth knowing before someone greps `app.log` for it and finds nothing.
  - ⚠️ **This is one abort, not the class.** The placeholder is reaped by a network round-trip; whether this one was reaped before it could PUT, or never reached the PUT path, is **not** established by the counter staying at 1. **n=7 is still too small and the item does not close.**

- **Fix, not yet built, and deliberately not built yet.** *Measure first.* If `[doc-put-404]` shows the path still firing, the fix is two lines — clear `_streamDocId` where the map entry is dropped, in the 404 reaper and in `loadSessionDocs` — plus a cleanup hook on the stream's `finally` (`static/js/chat.js:3923`, the one exit every stream passes through, including abort, error and background). If it does not fire, this item may close as bounded by the reaper. ⚠️ **The teardown must not persist anything** — [`resolvedissues.md`](resolvedissues.md), *"Empty document writes destroyed a document"*: a teardown that saves is how a 6,186-character document was wiped, and this one runs when the user has just navigated away. ⚠️ **A cleanup on abort must not kill a legitimately backgrounded stream** — `chat.js:4480` replays a background document stream by calling `streamDocOpen` again, so the abort path and the detached-run path are not the same event.

### 32. ~~A scheduled tidy hard-deletes "duplicate" documents, versions and all~~ ✅ CLOSED 2026-07-30
**Found 2026-07-30 while re-checking item 31's evidence. This is what actually destroyed the 8 documents, and it is the only unrecoverable path in the whole 30/31/32 complex** — everything else soft-deletes or leaves a `document_versions` row to restore from. The maintainer **paused the task** on 2026-07-30 once this was found.

**It is not inferred. The run says so:**

```
task_runs  ad505282-1f59-4a5f-a345-61b5a6f5c5d5   task 0a71978a "Documents Tidy"
2026-07-30 12:01:09 UTC (14:01 CEST)   status=success
"Removed 8 of 70: Pink Oyster Mushroom Growth Phases - Ple (+8 duplicate copies) (+7 more) · 62 kept"
```

**`70 → 62` is this string**, not an independent count — item 31 cited the same numbers as evidence for a different path, and `app.log` carries only `Task 'Documents Tidy' completed (run ad505282)`, with the result kept in the database. It had done it before: `4389c8b9`, 2026-07-29 18:23, *"Removed 2 of 53 … (+2 duplicate copies)"*.

- **The mechanism is by design, in `src/document_actions.py`.** Survivors are grouped by `(_norm_title(title), _content_fingerprint(content))`, sorted by real length, and every member but the first is `db.delete(doc)` — a **hard** delete. `DocumentVersion` is `cascade="all, delete-orphan"` with `ondelete="CASCADE"` (`core/database.py:312`), **so the version history goes with it.** There is no archive, no soft flag, no undo.
- ⚠️ **It fires automatically, on an event, not on a clock.** `src/task_scheduler.py:241` — `trigger_type="event"`, `trigger_event="document_created"`, `trigger_count=5`. **Every fifth document created runs it.** `app.log`: *"Event 'document_created' triggered task 'Documents Tidy' (every 5)"*. As of the pause, `trigger_counter` was **2 of 5**.
- 🔥 **It destroys item 20's experiment by construction.** The five-clone protocol creates five documents with the same title and identical content — that is **one duplicate group and the trigger count in the same act**. Four of the five clones are hard-deleted, with their version rows, and the run leaves nothing in `app.log` to explain where they went. **Item 20 cannot be run while this task is active**; the precondition is now written into item 20.
- **It is also the second half of item 31(b), and of item 30.** `routes/document_routes.py` `tidy_documents` hard-deletes `is_active == False` rows whose `current_content` is `NULL` or `''`, and the same file hard-deletes *active* documents whose content is empty or whose title is in `_JUNK_TITLES`. **An emptied document plus a closed tab is a permanent loss at the next five-document boundary** — that is the chain, and no single step in it looks dangerous on its own.
- **Current exposure, measured on a copy of `app.db` 2026-07-30 ~15:20:** 62 documents, 38 `is_active = 0`, and **0 rows with empty content**, so nothing is currently queued for destruction. The four documents recovered from items 30/31 all still hash to their recorded values, and in each case `current_content` equals the newest version row.
✅ **FIXED 2026-07-30 — (a), (b) and (c). (d) deliberately not done.**

`retire_document()` in `src/document_actions.py` is now the only way a tidy path removes a document: `archived = True` (Archive tab, restorable, and every tidy query filters it out) plus `is_active = False` (gone from the chat's tab bar, which is the visible behaviour the feature is *for*). **`db.delete` no longer appears on any Document in any tidy path** — the scheduled action, `POST /api/documents/tidy` and `POST /api/documents/ai-tidy` all call the same helper, so the two implementations the source comments ask to *"keep in sync"* cannot drift on what removal means.

- **(b)** the duplicate key is now `(normalized title, content fingerprint, session_id)`. Two copies in the **same** chat are still collapsed; the same document cloned into five chats is five working copies.
- **(c)** every retirement is logged with its id and reason — `[doc-tidy] archived N document(s) …` — at the moment it happens. Result strings say **"Archived"**, not "Removed", and name the Archive tab.
- **Archived rows are excluded from the query**, which is what makes retiring terminal instead of a step: without it a second run re-counts what the first one retired, and the duplicate pass re-picks a keeper among documents the user was already told were gone.
- ⚠️ **The `/api/documents/tidy` inactive-and-empty sweep was item 31(b)'s second half and is now closed by the same change.** A document emptied by item 30 and closed by item 31 arrives there as `is_active=0` with empty content, and used to be hard-deleted on arrival. It is archived instead, and archived rows are skipped.
- ❌ **(d) — the event trigger is unchanged, on purpose.** With nothing destructive left to fire, *when* it fires is a scheduling preference, not a safety property. Re-open it only if the archive itself starts to hurt.

**Tests: `tests/test_document_tidy_soft_delete.py`, 7 of them, 2 negative controls. Each branch was checked by MUTATION, and the mutations are written down** ([`CLAUDE.md`](../CLAUDE.md) §3 — a score without its mutation is a number nobody can re-derive):

| mutation | tests it kills |
|---|---|
| group key back to `(title, fingerprint)` — the 07-30 behaviour | `…cloned_into_five_chats_is_not_a_duplicate_group` |
| `retire_document` calls `session.delete(doc)` again | `…junk_is_archived_not_deleted`, `…duplicates_in_one_chat…`, `…session_less_documents…` |
| drop the archived filter from the query | `…second_run_does_not_re_report_what_the_first_archived` |

Each mutation kills a **different** test and the negative controls stay green in all three states, so no test is passing for the wrong reason. The junk test also asserts the `DocumentVersion` rows survive — the `all, delete-orphan` cascade is what made the original deletion unrecoverable, so "the row is still there" is not enough.

- ⚠️ **`tests/test_document_tidy_null_timestamp.py` asserted `count() == 1`, which pinned the hard delete** — a test written for the NULL-timestamp sort crash had quietly become the contract for destroying a row. Updated to assert both rows survive with exactly one archived; the property it exists for is untouched.
- ✅ **M1 suite, 2026-07-30 17:5x: `2 failed, 5775 passed, 4 skipped` in 109.30 s**, item 18 only *(both since fixed — the suite is `0 failed` as of 2026-07-31)*. **The count reconciles exactly:** 5,781 collected against 5,774 before this work — **+7, the seven tests above** — so nothing else shifted under the change. *(The earlier sandbox run on unpinned Linux deps is superseded and should not be quoted.)*
- ✅ **VERIFIED LIVE 2026-07-30 17:31:08, and it caught the right document.**

  ```
  [doc-tidy] archived 1 document(s) via /api/documents/tidy:
             3840c215-… (inactive and empty)
  documents 73 → 73   ·   document_versions 166 → 166   ·   archived 0 → 1
  ```

  **`3840c215` is the empty document from item 31's arm check** — created and closed at 15:54 to prove `[doc-del]` fired, and sitting at `is_active=0` with empty content ever since. **That is exactly the state item 31(b) leaves a document in, and the branch that used to `db.delete` it on sight.** It was archived instead: row intact, version row intact, restorable. `tidy_verdict` is NULL, so this was the regex pass, not the model's verdict.
  - **Both counts held**, which is the assertion that matters — a hard delete would have moved `document_versions` too, via the cascade.
  - **Nothing was collapsed**, which is also correct: the corpus had **zero** duplicate groups under the session-scoped key and **two groups totalling 7 rows** under the old one (a `Pink Oyster Mushroom Growth Phases` group of **7, across 7 distinct sessions**). **Same corpus, same run: 7 destroyed before, 0 touched after.**
  - ⚠️ **The scheduled task never got to run it** — 7 of its runs today ended `aborted — "Queued — waiting for Odysseus to be idle…"`, including the one that fired at 17:24. **The event trigger queues and then loses its window while the browser polls**, so the library's Tidy button is the only reliable way to exercise this path. That button runs `/api/documents/tidy` **and** `/api/documents/ai-tidy` in sequence, so both fixed paths were exercised.
- **Still owed:** a run with real duplicates in one chat, to see the collapse archive rather than no-op. The live run above proves the junk/inactive branch and the *absence* of cross-chat collapsing; it does not show a keeper being chosen.
- ✅ **The pause is real, and it is enforced at two independent layers** — checked 2026-07-30 rather than assumed. `src/event_bus.py:82` filters `status == "active"` when *arming*, so a paused task's `trigger_counter` does not even increment; `src/task_scheduler.py:817` re-checks at execution time and marks an already-queued run `skipped` with `Task no longer active`. **A run queued before the pause cannot fire.** State as of the pause: `0a71978a` = `paused`, counter frozen at **2 of 5**.
  - ⚠️ **Pausing DEFERS the deletion, it does not cancel it.** Duplicates accumulate while it is off and the first run after re-enabling collapses every group in one pass — nine clones became one row on 07-30. **Snapshot or clean up deliberately before re-enabling**, and note it fires on the fifth document *after* that, not immediately.
  - ⚠️ **The manual routes stay live while the task is paused:** `POST /api/documents/tidy` and `POST /api/documents/ai-tidy`. Both need an explicit click, so neither is a background risk, but **ai-tidy asks a model to label documents `junk` and hard-deletes on its verdict** (`routes/document_routes.py:1114`).
- ⚠️ **`tidy_sessions` is the same shape, is STILL ACTIVE, and was not examined.** It ran ten seconds earlier the same day (*"Cleaned 3 sessions"*, `task_runs.ddbf6bb3`) and `src/session_actions.py:91,137` uses `db.delete(row)` on `Session`. It is what leaves documents with `session_id = NULL` (item 31(c)). **`tidy_research` is a third, also unexamined.**

## S3 — visible task failure

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

- ✅ **Ruled out 2026-08-01: these rounds are NOT hitting the token cap.** Two zero-text zero-tool rounds logged `finish_reason=stop` (18.321 s and 13.420 s) — the model chose to end, it was not cut off. **That ambiguity had stood since this item was filed and item 41 removed it in one field.** ⚠️ **n=2, and `stop` says only that the cap is innocent** — it does not say where the text went, which is item 23's question. **Compare `thinking` against `content` on those two rows.**

### 9b. Streams fail mid-turn, and the timeout is a document-length cap
`{"error": "Read timeout", "status": 504}`, logged as a WARNING and persisted nowhere, so the row read as *a slow turn*. Reporting fixed 2026-07-28 — `metrics["stream_errors"]` plus a user-facing notice. [resolvedissues.md](resolvedissues.md), *"A turn that failed read as a turn that was slow"*.

✅ **Reporting verified live on run bbde3e51, 2026-07-28**, three hours after shipping: *"⚠️ The request to the model failed after 375s — `Read timeout (504)`."* Before that day the same turn saved as `143 tokens, 0.38 tok/s` and nothing else.

- ⚠️ **This item covers the SERVER side of a broken stream only. The client side is item 34, and neither knew about the other until 2026-07-31.** A stream that dies mid-turn — or that the user aborts by switching chats — leaves an orphaned `_streaming_…` placeholder as `activeDocId` with an unstamped editor buffer, which is the state items 30 and 31 exist for. **Reciprocal (#9b↔#34): a fix here that only improves reporting leaves the client wreckage untouched.**

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
- ✅ **Two rounds past the old cap, 2026-07-30, both completed** — `813.3 s` (session `ef460706`, round 1, one `create_document` producing a **54,390-character** document) and `433.1 s`. Neither was contrived; both came out of item 20's runs. **Not a close.** The item asks for three same-prompt successes, and the 433 s round is *not* a success in any other sense: `text_chars=0 tool_calls=0`, no assistant row ever saved. ⚠️ **`elapsed=813.3 s` bounds the silent stretch at ≤740.9 s but does not measure it** — `first_visible_token` at 72.5 s is the last event before `round_stream_done`, so the per-read inactivity the timeout actually governs is still unmeasured.
- **A context reading worth keeping from the same turn:** round 2 of `ef460706` opened at `request_context_tokens=40,857` against `context_length=32,768` — `context_percent: 100`. The model's own 54 KB document went straight back into its next round. Right field (not the `input_tokens` trap), real overflow.
  - ✅ **Addressed 2026-07-31 by moving to `qwen3.5:9b-64k`** (`num_ctx 65536`; setup, measurements and the unmeasured half in [qwensetup.md](qwensetup.md), *"Context window"*). **The whole recorded corpus was measured first, not sampled:** 104 rows carrying `request_context_tokens`, median 11,724, p95 22,713, max 40,857 — **2 of 104 over 32,768, none over 49,152.** So the overflow this bullet records is **1.9 % of turns, not a general condition**, and 48k would have covered every one of them.
  - ⚠️ **This does not close 9b and must not be read as a fix for it.** The 504s in the table above are an *inactivity* timeout during generation; context overflow is a separate defect that happens to share a turn. **Widening the window cannot make a stream that stops streaming resume**, and the three same-prompt long runs this item asks for are still owed. If anything the change makes them cheaper to obtain — a larger window admits longer histories, so a deliberately long round is easier to provoke.
  - ⚠️ **A new way for this item's symptom to arrive.** If the 64k KV cache stops fitting in 16 GB, Ollama splits layers to CPU, throughput collapses, and the per-read inactivity timeout fires — **producing this item's exact 504 from a memory cause**. Check `grep offloaded /opt/homebrew/var/log/ollama.log | tail -3` before diagnosing any future 504 as generation length; `34/34 layers to GPU` is the healthy reading. **Recorded here rather than only in [qwensetup.md](qwensetup.md) because this is the item the symptom will be filed against.**
- ⚠️ **This is an experiment, not a diagnosis.** If a turn still dies at 900 s the cause is a hang, not payload length, and the two want different fixes. **Do not close this until three same-prompt runs succeed.**
- ⚠️ **Raising it also scales the runaway wall-clock deadline** — `max(agent_stream_timeout * 4, 1200)` in `agent_loop.py` is now **3600 s per round**. Lower both together if that is too loose.
- **A second error class exists:** bbde3e51 turn 4 returned `All model candidates returned no substantive output (502)` at 69.8 s, on round 4 of a turn whose earlier rounds had written a document. Not a timeout. Unexplained.
- **Still open:** whether 0b12aadb (0.39 tok/s, 393 s) was the same 504. Its log window predates the check and nothing was persisted.
- ✅ **The failure notice no longer overstates the failure.** bbde3e51 turn 4 wrote v6 of a real document on rounds 1–3, then failed on round 4, and was told *"the turn did not finish, so treat it as incomplete"*. When `tool_events` is non-empty the notice now says work completed before the failure has been kept. **A failure notice that overstates the failure is still a false report** — the `"Done."` bug pointing the other way.

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

#### Recurrence 2026-07-31, session 93c1c383 — and this one carried a wrong number
Same shape, different session, **five months of guard work later**: turn 5 of the shiitake session logged `text_chars=0` on **all five rounds**, `round_texts` `['','','','','']`, and **2,320 characters of `thinking`** ending *"Let me summarize the fact-check findings and offer to update specific sections based on verified data."* The user got the gathering-only notice. **The guard reported correctly; the underlying stop is what is unfixed.**

- 🔥 **The thinking contains a Fahrenheit→Celsius conversion that is wrong.** It reads First Flush's *"70-80 °F"* colonization range and renders it **"~20-35°C"**. 70–80 °F is **21–27 °C**. This is the turn immediately after one whose entire job was converting °F to °C in that same document, and the numbers are chamber setpoints. ⚠️ **The only reason it reached nobody is that the turn produced no content** — the failure mode this item calls "work lost silently" was, this once, the thing that prevented a wrong answer. **That is not a mitigation and must not be recorded as one.**
- ❌ **Two candidate causes eliminated, so this is not a model or budget artefact.** (a) **Not the 32k model** — every turn in the session ran `qwen3.5:9b-64k` at `context_length 65536`, and the session row agrees; the 32k slip was a different session ~6 hours later. (b) **Not `max_tokens` exhaustion** — the turn produced **821 output tokens against `max_tokens=6656`**, measured from `app.db` with `usage_source: real`. ⚠️ **A wider claim that no round has *ever* been truncated was RETRACTED the same day — see item 41.** The per-turn measurement above stands on its own; the generalisation rested on a log absence that could not have been present.
- **Peak context on that turn was 17,869 of 65,536 — 27 %.** Not a context-pressure artefact either.

- ✅ **Ruled out 2026-08-01: the cap is innocent.** Two zero-text rounds logged `finish_reason=stop`, not `length` — so a turn that produced no `content` was not truncated mid-answer. **That leaves this item's own mechanism (text delivered on the reasoning channel) as the live explanation rather than one of two.** ⚠️ **n=2**, and the discriminating query is unchanged: `round_texts` cannot separate these, `thinking` vs `content` can.

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

### 14. Web search derails on ambiguous common nouns
Recurring, and **it feeds item 2b** — the wrong-species drift there is partly downstream of this. Run eb2d0ac1 returned **"Pink (singer) — Wikipedia"** as a top result for a pink-oyster cultivation query; an earlier run ranked a Victoria's Secret "PINK" page into the same searches. Nothing in the pipeline notices. The species name is in the document title and isn't being used.

- A prompt rule now tells the model to disambiguate common-word names in queries (2026-07-28, item 20). **That is not a fix** — it is unmeasured, and the ranking problem is upstream of the model.

**A second sub-pattern, and it is NOT the ambiguous-noun mechanism — consumer food/health content outranks cultivation content.** Recorded 2026-07-31/08-01, two sessions, neither query ambiguous:

- *shiitake … optimal growing temperatures … colonization fruiting* → **WebMD and Healthline in 2 of 5 slots on all three queries.** The model reformulated twice and got essentially the same five links back; the only authoritative hit (ResearchGate) 403s, and the one usable source (a `kjmycology.or.kr` PDF) was never fetched.
- *Amanita muscaria cultivation requirements …* → `web_sources` carried **`allrecipes.com` rhubarb dessert recipes and `tasteofhome.com`** alongside the cultivation pages.

**"Amanita muscaria" and "Lentinula edodes" are Latin binomials — there is no common-word collision to disambiguate**, so item 20's prompt rule cannot touch this and neither can item 29's quoted-phrase filter (nothing was quoted). The species term is present and correct in the query and the ranker returns recipes anyway. ⚠️ **Do not fold this into the ambiguous-noun account** — that is the mistake that would make it look already-addressed. Unmeasured; the cheap first step is counting how often a result domain is consumer-food/health across the recorded `web_sources` rows.

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
5. 🔥 **PAUSE *both* tidy tasks first — the protocol destroys its own evidence otherwise.** Added 2026-07-30. **"Documents Tidy"** (`document_created`, every 5) *and* **"Chat Sessions Tidy"** (`session_created`, every 5) — this protocol creates five documents *and* five chats, so it arms both. The session one deletes empty sessions, and a deleted session **nulls its documents' `session_id`**, which makes them invisible to `list_documents` in *every* chat; a run where the model produced nothing leaves a session that can read as empty. **Quieter than the document tidy — nothing is deleted, the evidence just stops being findable.** Verify the status mechanically before the run, not after:

   ```
   cd /Users/cedrik/odysseus && cp data/app.db /tmp/t.db && python3 -c "
   import sqlite3
   for r in sqlite3.connect('/tmp/t.db').execute(\"select name,status,trigger_counter,trigger_count from scheduled_tasks where owner='cedrik' and action like 'tidy%'\"): print(r)"
   ```

   ⚠️ **A pause is UI state and is invisible to anyone reading the repo** — it is not in git, and the next session has no way to know. The query above is the only check. That task hard-deletes documents grouped by `(normalized title, content fingerprint)`, keeping one, **and it triggers on every fifth `document_created`**. Five identical clones are one duplicate group *and* the trigger count in the same act. It removed 8 documents this way on 2026-07-30 (`task_runs.ad505282`) and 2 on 07-29, `document_versions` cascading with them, leaving nothing in `app.log`. **A run of this protocol that comes back short is more likely to have been tidied than to have failed.** See item 32; confirm the pause in the Tasks UI, and re-count `documents` before and after.

- ⚠️ **The five runs need a document OPEN; item 2a's live turn needs the editor CLEAR.** Opposite preconditions — do not try to collect both in one session.
- **Open: decide per rule; do not revive the block wholesale.** The assembled prompt is already ~35k chars (~8.8k tokens) against a 32k window. Six rules were added to the live sections on 2026-07-28 (four document, three web) and `tests/test_agent_rules_reach_the_model.py` pins the four best-known dead markers as *absent*, so reviving one is a deliberate act.

## S4 — friction and blocked diagnosis

### 12. Wasted verification rounds
9B sometimes runs `manage_documents` "to check" after creating a doc (~47 s for nothing). Run 27a94a01 did exactly this.

- ⚠️ **The prompt line against it exists and has never reached the model** (item 20). **This item has only ever been observed with the rule absent**, so "the model ignores it" is not established. Re-measure before building anything in the loop.

### 13. Terminal access-log noise
Every request prints, so real errors scroll away — worst during polling (`/api/research/status/<id>`, `/api/chat/stream_status/<id>`). **Got in the way twice on 2026-07-19** while confirming PUT traffic during the editor investigation. Hide 200s; hide 304s behind their own toggle, since a 304 storm is how you spot a stale-cache bug. Don't use `--no-access-log` (kills 4xx/5xx) — add a `logging.Filter` on `uvicorn.access` keyed by status, wired at `app.py:1281`, `launcher.py:142`, `start-macos.sh:292`, with an `access_log_hide_statuses` setting.

### 18. ~~Two tests in `test_document_put_version_conflict.py` have never passed~~ ✅ CLOSED 2026-07-31
`test_concurrent_ai_edit_after_read_loses_the_swap` and `test_losing_swap_does_not_leave_a_partial_version_row` both patch `droutes._reserve_document_uploads`, which is defined at `routes/document_routes.py:82` **nested inside `setup_document_routes()`**. It is a closure, never a module attribute, so the lookup raises `AttributeError` and can never have worked.

- **Third instance of the item 16 shape, and the least dangerous kind** — here the test fails loudly. Item 16's orphan failed *green*, which is why that one is the priority.
- ❌ **"Fixing it is a design decision, not a repair" was wrong — retracted 2026-07-31.** The three options filed (expose the closure, inject it, drive through the endpoint) missed a fourth that needs **no production change**: the closure's entire body is a call to `reserve_upload_references`, imported at `routes/document_routes.py:15` — a real module attribute — and invoked **unconditionally** at `:83` (the `upload_handler is None` early return lives *inside* that function, so the call happens even with the test's `MagicMock(), None` wiring). Patching it lands in the identical window: after `base_version = doc.version_count` (`:697`), before `db.add(ver)` (`:741`) and the compare-and-swap (`:754`). **The hook the test wanted was one level down the whole time.**
- ✅ **Fixed and MUTATION-VERIFIED on the M1, 2026-07-31.** Both tests, plus a `fired` guard on the second — its old body reassigned `droutes._reserve_document_uploads` to undo itself, which was a *second* route to the same missing attribute; `monkeypatch` already restores. **The suite ran clean, then the `, Document.version_count == base_version` clause was deleted from the CAS filter (`routes/document_routes.py:756`) and the same two tests FAILED**, then passed again once it was restored. So they exercise the compare-and-swap rather than passing for a weaker reason — [`CLAUDE.md`](../CLAUDE.md) §3, checked failing before checked passing. **The mutation is written down here because a score without its mutation is a number nobody can re-derive.**
- ✅ **It landed: the suite's `2 failed` baseline is now `0`** — the first clean run in this project's record. **Any failure from here is a real one**, and "the usual two" is no longer available to wave one through. Every note written before 2026-07-31 that says *"expect 2 failed"* is historical.
- ⚠️ **Do not "fix" these by deleting them.** They cover the CAS race item 1 spent three diagnoses on: an AI edit landing between the handler's read and its write. That case needs coverage; what's broken is how the test reaches it.

### 25. A path-confinement test passes without the mechanism it tests
`tests/test_tool_path_confinement.py::test_extra_roots_opt_in` builds its fixture under `tmp_path`, patches `tool_path_extra_roots` to include it, and asserts the path resolves. **It resolves either way.** `_tool_path_roots()` already contains `/tmp` and `$TMPDIR` (`src/tool_execution.py`, the `# $TMPDIR — per-user temp root on macOS` block), and `tmp_path` lives in one or the other on both platforms. The patch is decoration; there is no negative control asserting rejection *without* the opt-in.

- ✅ **Confirmed on the M1, 2026-07-29.** With the mechanism removed — `return_value=[]` in place of `[str(extra_dir)]` at line ~205 — the file still reports **`25 passed`**. The test does not depend on the setting it is named after.
- **Measured, not read.** Importing the real `src.tool_execution` with `DATABASE_URL=sqlite:///:memory:` and calling `_resolve_tool_path` on a `tmp_path`-shaped location resolved it **with no patch applied**. The mirror-image control passed too: the same probe against a repo-root location was `REJECTED` without the extra root and `ALLOWED` with it. *(Those two ran in a Linux sandbox with a faked `TMPDIR`; the macOS run above is what settles it.)*
- **This is item 16's shape and the pair is reciprocal (#16↔#25).** There it was a security assertion pointed at an orphaned function; here it is a security assertion that holds regardless of the mechanism. **Both were green throughout.** The difference worth keeping: item 16's was found by reading callers, this one only by *running* the function.
- **Fix is a negative control, not a rewrite:** assert the same path is rejected when `tool_path_extra_roots` is empty. That is the assertion the test's own docstring already claims to make.
- ⚠️ **Do not "fix" it by moving the fixture out of `tmp_path` without checking the roots list first** — see item 26, where the same coupling runs the other way.

### 26. ~~Test litter in the repo root, kept invisible by `ignore_errors=True`~~ ✅ CLOSED 2026-07-31
`tests/test_chat_helpers.py:176` (`_manifest_test_dir`) builds fixtures at `<repo root>/tmp_pytest_probe/<name>-<uuid4>`. Both callers clean up in a `finally` — with `shutil.rmtree(root, ignore_errors=True)`. **The cleanup ran, failed, and the flag discarded the failure.** Four directories accumulated from two runs on 2026-07-28; `uuid4()` means every run adds rather than reuses.

⚠️ **State refreshed 2026-07-29 — the four subdirectories are gone, deleted on the M1 where the mount restriction does not apply.** So the visible symptom was cleared and the defect was not: the next suite run on a machine that cannot unlink re-creates it. **Do not read the empty directory as a fix.**

> ✅ **Both halves addressed 2026-07-31 — and one of them had already been done without the item knowing.**
>
> - ❌ **The claim *"`tmp_pytest_probe/` is still not in `.gitignore`"* was STALE when re-checked.** It is at **`.gitignore:125`** and committed. So the reciprocal-with-item-5 concern — repo-root litter polluting `git status` — was already resolved, and the item had been carrying a fixed complaint as a live one. *(Which is §2 exactly: a filed claim is unverified until re-checked, and this one had gone the harmless direction for once.)*
> - ✅ **The silence is fixed.** `_cleanup_manifest_dir()` in `tests/test_chat_helpers.py` replaces `shutil.rmtree(root, ignore_errors=True)` at both call sites: it attempts the removal and **warns with the path** when the tree survives, instead of discarding the `PermissionError`. It deliberately does **not** raise — a sandboxed run genuinely cannot unlink under the mount, and that is the environment's limitation, not the suite's. ⚠️ **Note the interaction with the gitignore fix: now that the directory is ignored, `git status` will never show it again, so this warning is the ONLY thing that can report the leak.** Ignoring the symptom made fixing the silence necessary rather than optional.
> - **The load-bearing location is left alone and now says so in the code** — a comment at `_manifest_test_dir` records why the repo-root path is not litter, so the next reader does not "tidy" it into `tmp_path` and make the test vacuous.
> - ✅ **VERIFIED 2026-07-31 with a negative control, which is what closes this.** Running `_cleanup_manifest_dir`'s exact body under the mount: **1 warning**, `[Errno 1] Operation not permitted`, tree still present, path named. On a removable `/tmp` tree: **0 warnings**, tree gone. **A checker with only positive cases can be a function that always fires** ([`CLAUDE.md`](../CLAUDE.md) §3) — this one is silent when cleanup actually works. The M1 suite also ran clean with the change in.
> - ⚠️ **That verification left `tmp_pytest_probe/verify-943442903ae1…` in the repo root and the sandbox cannot unlink it — the maintainer's to remove.** It is gitignored, so `git status` will not mention it: **the exact interaction this item ends on, demonstrated by accident.** `rm -r /Users/cedrik/odysseus/tmp_pytest_probe`
> - **Left alone deliberately:** `tests/test_code_nav_tools.py:39` keeps `ignore_errors=True`. It writes to `/tmp`, which is deletable on macOS and unwritable in the sandbox, so it fails loudly rather than leaking, and its `dir="/tmp"` choice is documented in the fixture as a requirement.

- **Reproduced under the sandbox mount:** `rmtree(ignore_errors=False)` raises `PermissionError [Errno 1] Operation not permitted`, and with the flag on, the tree survives silently. The mount permits `create` and refuses `unlink` — the same restriction `CLAUDE.md` records for `.git/`.
- **Why it was not merely untidy:** `tmp_pytest_probe/` appeared as untracked in every `git status` — the check the uncommitted-work item depended on to notice untracked files. The pair was reciprocal (#5↔#26). ⚠️ **Both ends have moved since: it is gitignored (`.gitignore:125`) and that item closed into [`CLAUDE.md`](../CLAUDE.md) §6 on 2026-07-31.** The residue is that **nothing in `git status` can report this leak any more** — see the banner above.
- ⚠️ **The location is load-bearing — check before moving it to `tmp_path`.** `DATA_DIR` is `<repo>/data`, not the repo root, so the fixture currently sits outside every default root, which is exactly what makes the test's `tool_path_extra_roots` patch discriminate. Under `tmp_path` it would stop discriminating and the test would go green for a weaker reason — item 25's defect, newly introduced.
- ⚠️ **And if you replace `_tool_path_roots` to keep it honest, `os.path.realpath` the root.** The real function normalises its own inputs; a replacement bypasses that, and on macOS `tmp_path` sits under the `/var` → `/private/var` symlink. Demonstrated: without `realpath` the same path is `REJECTED`, with it `ALLOWED` — **a macOS-only failure, which is item 19's class.**
- **Not a house pattern:** `test_chat_helpers.py:176` is the only test in the suite that *writes* into the repo root; every other `parents[1]` use reads source for AST assertions, and 134 test files already use `tmp_path`.
- **Related, lower priority:** `tests/test_code_nav_tools.py:39` carries the same `ignore_errors=True`, but writes to `/tmp` — deletable on macOS, and unwritable in a Linux sandbox, so it fails loudly instead of leaking. Its `dir="/tmp"` choice is **deliberate and documented in the fixture** (the opposite requirement: it needs to be *inside* the allowlist). Its line 8 `DATABASE_URL` pointing at a file-backed `/tmp` db is inert while `tests/conftest.py:18` sets `:memory:` first, and only bites under `--noconftest`.

### 40. Round 1 of every turn re-prefills the whole prompt
**Measured 2026-08-01 over 275 rounds in `app.log`.** Round 1 is **4–8× slower than a later round at the same prompt size** — not a normalisation artefact, this is absolute time at matched buckets:

| prompt tokens | round 1 | round 2+ |
|---|---|---|
| 0–6,000 | **50.7 s** (n=28) | 6.1 s (n=7) |
| 6,000–9,000 | **62.6 s** (n=44) | 10.5 s (n=31) |
| 9,000–12,000 | **73.3 s** (n=28) | 16.9 s (n=50) |
| 12,000–16,000 | — | 27.0 s (n=47) |
| 16,000+ | — | 47.0 s (n=40) |

A later round carrying **16k+** tokens (47.0 s) still beats round 1 carrying **6–9k** (62.6 s). Round 1 pays roughly **40–50 s** that no later round does, and at 5 turns per session that is the single largest recoverable cost in the loop.

**Three candidates eliminated, each with its own measurement:**

- ❌ **Cold model load.** Round-1 rate by idle gap since the previous round: **7.08 / 8.22 / 8.56 s per 1k tokens** for `<1 min` / `1–5 min` / `>5 min` (n=34/34/31). Flat. A round starting one minute after the last pays the same as one starting fifteen minutes after. **This also settles that `OLLAMA_KEEP_ALIVE` is not a latency problem** — see [qwensetup.md](qwensetup.md).
  - ✅ **Independent control, 2026-08-01, and it is stronger than the idle-gap version because the load is CERTAIN rather than assumed.** Two turns 64 s apart across a **model change**: `-32k` round 1 first token **54.340 s** (4,700 tokens), `-64k` round 1 **58.212 s** (5,933 tokens). Item 42's stage 1 established that Ollama **evicts one 9B to load the other**, so the second turn definitely paid a full 6.7 GB load — **and it cost ~4 s.** ⚠️ **The idle-gap measurement above could not distinguish "no load happened" from "a load happened and was cheap"; this one can**, because the eviction is independently attested. Both readings survive and now mean the same thing.
  - 🔴 **AMENDED 2026-08-01 evening — the penalty is worse than this item documents.** Two `round=1` at **110.161 s** and **110.092 s**, four minutes apart, each producing **one tool call and zero text**. This item's table says 40–50 s and the buckets top out at 73.3 s. **Over double, and reproducible to within 70 ms.** ⚠️ **Prompt sizes for those two rounds are not recorded here** — pull them from `prep_done` before treating this as the same phenomenon at a larger size rather than a different one. Both came from `finish_reason=tool_calls`, i.e. rounds that ended by calling a tool, which the earlier buckets may not have separated.
  - ✅ **Repeated at 10:09–10:11 with the eviction DIRECTLY OBSERVED, not inferred, and the figure holds: ~2.6 s.** Single-round turns, no tools, ~100 characters out either way: `-32k` **46.494 s**, then `-64k` **49.135 s** 23 seconds later, with `ollama ps` confirming `-32k` had been unloaded three minutes early to make room. **A forced 6.7 GB load is ~5 % of the round-1 penalty.** ⚠️ **This is now the strongest of the three eliminations** — the other two rest on a load that may not have happened; this one rests on a load that provably did.
  - ✅ **Round 2 of both turns, same session, larger prompt: 6.830 s and 7.004 s.** Ratios **8.0×** and **8.3×** against their own round 1, with round 2 carrying **+854** and **+839** more tokens. Two more instances at the documented magnitude, on two different models, an hour after the item was filed.
- ❌ **Tool-list churn changing the prompt prefix.** Round 1 with the same tool count as the previous round: **7.52 s/1k** (n=21). With a different count: **8.22 s/1k** (n=78). No effect, despite the count differing on 78 of 99 turns.
- ❌ **A timestamp in the system prompt.** Already fixed — deliberately moved to a late user-role message for exactly this reason (issue #2927, `tests/test_kv_cache_invalidation_2927.py`). ⚠️ **Nearly re-derived as a new finding; read `agent_loop.py:2787` before going near this again.**

**What fits the numbers:** a constant prefill rate of ~110–120 tok/s, with round 1 prefilling the *entire* prompt and later rounds only the delta. 7,500 ÷ 120 ≈ 62 s, matching the 6–9k bucket.

**Leading hypothesis, UNTESTED.** Volatile blocks — document, email, integrations, MCP descriptions, skills, datetime — are inserted immediately *before the last user message* (`agent_loop.py:3271-3290`), i.e. mid-array. Within a turn new tool results are appended at the very end, so the prefix survives; between turns the new history lands where those blocks were, so the common prefix ends there. The document block alone can be thousands of tokens.

- ✅ **THE DISCRIMINATING TEST HAS NOW BEEN RUN — 2026-08-01, from `app.log`, no new instrumentation needed — and it does NOT support the hypothesis.**

  | | n | median round-1 | median prompt | s / 1k tok |
  |---|---|---|---|---|
  | **document injected** | 100 | **63.6 s** | 8,238 | **7.72** |
  | **no document** | 21 | **54.4 s** | 4,838 | **11.24** |

  **Document turns are slower in absolute terms and FASTER per token.** The block costs its ~3,400 extra tokens and **no measurable penalty beyond them** — the opposite of what a cache-breaking insertion predicts. The numbers fit **~17 s fixed + ~7.7 s per 1k tokens** (4,838 × 7.72 = 37 s + 17 = 54; 8,238 × 7.72 = 64), which explains both rows with one constant and replaces this item's *"constant prefill rate"* model.
  - ⚠️ **It does NOT clear mid-array placement, and reading it that way would be the mistake.** Both arms are round 1, and round 1 re-prefills everything either way — so this cannot distinguish *"the document breaks the prefix"* from *"there was no prefix to break."* **And the "no document" arm still carries the other volatile blocks** (datetime, integrations, MCP descriptions, skills), so it is not a clean control for the hypothesis, only for the document half of it.
  - 🆕 **The ~17 s fixed component is new and is the part with no explanation.** It is not prompt size, not cold load (~2.6 s, measured), not tool-list churn. **That, not the per-token rate, is what is left to chase.**
  - ⚠️ **The "no document" arm is thinner than it looks — see item 45.** The frontend sends `active_doc_id=''` on 344 of 445 turns and the server injects one anyway via a session fallback, so *"no document"* here means *"no document the server could find"*, not *"no document open"*.
- ⚠️ **Do not "fix" the placement on the strength of the hypothesis.** It is deliberate — the doc message sits there so it stays close to the user's request and survives context trimming independently. Moving it trades model behaviour for latency, and this project has a record of shipping that trade backwards.

### 41. ~~A truncated answer is indistinguishable from a short one~~ ✅ CLOSED 2026-08-01
**Filed out of a retraction and closed the same day, both paths verified live. Body in [resolvedissues.md](resolvedissues.md), *"A truncated answer was indistinguishable from a short one"*.**

⚠️ **The convention outlives the item and is cited by 8, 9b, 23 and 40: absence means the provider reported nothing, NEVER that the generation finished cleanly.** `finish_reason=?` on `round_stream_done` is *unknown*, not clean.

**🆕 First five streaming samples, and they discriminate something these items could not.** No `finish_reason=length` in any of them:

```
15:20:53  round=6  18.321s  text_chars=0  tool_calls=0  finish_reason=stop
20:26:11  round=1 110.161s  text_chars=0  tool_calls=1  finish_reason=tool_calls
20:26:25  round=2  13.420s  text_chars=0  tool_calls=0  finish_reason=stop
20:30:44  round=1 110.092s  text_chars=0  tool_calls=1  finish_reason=tool_calls
20:31:10  round=2  26.555s  text_chars=775 tool_calls=0  finish_reason=stop
```

- **Two zero-text, zero-tool rounds finished `stop`** — item 8's *"gathers information, then stops"* and item 23's *"answer in the reasoning channel"* shape. **They are not truncation.** ⚠️ **n=2, and `stop` does not say where the text went** — it rules out the cap and nothing else. Compare `thinking` against `content` on those rows before concluding anything (item 23).
- **`round=1` at 110.161 s and 110.092 s — twice, 4 minutes apart, for a single tool call and no text.** Item 40 documents a round-1 penalty of **40–50 s**; this is over double. Folded into that item.


### 42. Sessions pin the model tag per row; a tag Ollama no longer serves does not fall back
> ⊘ **THE HEADLINE THIS ITEM WAS FILED ON IS DEAD — disproved 2026-08-01, hours after filing, by the maintainer running the one command the draft asked for.** It was filed as *"two 9B variants ≈ 13 GB of a 16 GB machine"*. **Ollama does not co-reside them; it evicts.** What survives is the dead-tag branch below, which was found while drafting the fix for the claim that turned out to be wrong. **The arithmetic was the whole severity and it was never a measurement** — see *"Stage 1 — ANSWERED"*.
**Filed 2026-08-01, from re-checking the previous session's own claim that *"the 64k switch is live and measured"*.** That claim is true and it is narrower than it reads: it was verified on session `93c1c383`, which is **one of only two sessions on the new tag**.

**`sessions.model` is a per-row column and it is a THIRD channel pinning the model tag.** [qwensetup.md](qwensetup.md) names two settings — `default_model` and `research_model` — as *"the two settings that pin the model tag"*. There is a third, it is per session, and nothing in these docs mentioned it.

```
sessions by model, data/app.db copied 2026-08-01
  72   'qwen3.5:9b-32k'    newest 2026-07-31 15:32
   3   'qwen3.5:4b-32k'    newest 2026-07-18 19:23   ← the model retired 2026-07-18, item 4
   2   'qwen3.5:9b-64k'    newest 2026-07-31 22:50
   2   ''                  newest 2026-07-12 11:31
sessions touched since 2026-07-31 12:00:  36 on -32k, 2 on -64k
```

- ✅ **Observed live, in one app uptime.** Startup at `2026-08-01 00:15:52`; a full six-round agent turn on **`qwen3.5:9b-32k`** at 00:19:01–00:28:20, then every round from **00:30:51** on `qwen3.5:9b-64k`. **2 minutes 31 seconds apart, no restart between them.** `grep round_start data/logs/app.log` — the model is on the line.
- 🔴 **This inverts a documented recommendation, and that is the reason to file it rather than just change a dropdown.** Two 9B variants are ~6.7 GB each: **~13 GB of a 16 GB M1 Pro before `nemotron-3-nano:4b` and `all-minilm`.** [qwensetup.md](qwensetup.md)'s co-residency warning counts the 4B utility model and the embedder — **it does not count a second copy of the 9B, because nobody knew there was one.** Right now the **5-minute `OLLAMA_KEEP_ALIVE` default is the only thing preventing both being resident**, and qwensetup's standing plan is to fix that to 30m. **Do the tag cleanup first; fixing keep-alive first is the memory-exhaustion case.** The arrival path is already written down there: KV spills to CPU, throughput collapses, the inactivity timeout fires, and it presents as item 9b's 504.
- ⚠️ **`research_model` is still `qwen3.5:9b-32k` in `data/settings.json`** — the *"Owed"* line in [session-log.md](session-log.md)'s 07-31 entry, half done. `default_model` was changed; its sibling was not.
- ⚠️ **The 32k arithmetic defect the 64k raise was made to remove is therefore still live on 72 sessions.** At 32,768 with `max_tokens 8192` the real input room is 24,576 against an auto budget of 27,852 — the app can assemble prompts that cannot fit alongside a full answer. It degrades quietly, which is why nobody noticed it the first time.
- ⚠️ **Three sessions are pinned to `qwen3.5:4b-32k`**, the model retired on 2026-07-18 for a correctness floor it did not clear (item 4). None has been touched since 07-18. **Not established: what happens when one is reopened** — whether Ollama still has that tag, and whether the resolver falls back or pulls. Check before assuming item 4's closure covers it.
- **Not established, and it decides the shape of the fix:** whether the 00:19 turn ran on `-32k` because of the session row or because of `research_model`. Both are `-32k`, so this log cannot separate them. The discriminating test is one turn in a `-32k`-pinned session **after** `research_model` is moved to `-64k`.
**Fix — DRAFTED 2026-08-01, nothing built. Staged, and the first two stages are measurements. Do not skip to stage 3.**

The reason for the staging is that **this item's headline number is arithmetic, not a measurement.** *"Two 9B variants ≈ 13 GB"* multiplies one observed `ollama ps` reading by two. Nothing has watched both be resident. [`CLAUDE.md`](../CLAUDE.md) §3 — measure a claim by mutating it, not by restating it.

**Stage 0 — free, no risk, do it regardless.** `research_model` → `qwen3.5:9b-64k` in the **UI**. It changes no session row and needs no migration.

**Stage 1 — ANSWERED 2026-08-01, and it kills the co-residency claim. ⊘ One row, and it is the wrong model.**

```
qwen3.5:9b-64k   b7b9afeaf023   6.7 GB   100% GPU   65536   4 minutes from now
```

- **The two turns, from `app.log`:** `-32k` at **09:51:33–09:53:08** (`context_length=32768`), `-64k` at **09:54:12–09:56:00** (`context_length=65536`). Same uptime, 64 seconds apart.
- **`-64k` reading `4 minutes from now` puts the `ollama ps` at ≈09:57.** `-32k` was last used at **09:53:08**, so its 5-minute timer does not expire until **09:58:08** — **it should still have been listed, and it was not.** Ollama **unloaded `-32k` to make room for `-64k`.** They do not coexist, so the 16 GB was never going to be exhausted.
- ✅ **And the reload is cheap, which nobody predicted either.** First token: `-32k` round 1 **54.340 s**, `-64k` round 1 **58.212 s**. **A full model change bought ~4 s.** Whatever dominates round 1 is not a cold load — it is item 40, and this is the cleanest control that item has (see *"Round 1 of every turn re-prefills the whole prompt"*).
- ⚠️ **One inference, not a measurement: the `ps` time is derived from the `UNTIL` column, not observed.** It is tight — `4 minutes` pins it to ≈09:56–09:57 against a 10:01 expiry — but it is a reconstruction. `/opt/homebrew/var/log/ollama.log` states an eviction outright and is the better source; it is outside the repo so no sandboxed agent can read it.
- ✅ **EVICTION CONFIRMED on the third `ollama ps`, 2026-08-01 ≈10:11:41 — directly observed, with three minutes of margin.** The protocol below was run as written.

  ```
  10:09:01–10:09:47   turn on qwen3.5:9b-32k      → keep-alive expiry 10:14:47
  10:10:10–10:10:59   turn on qwen3.5:9b-64k      (23 s later — inside the window)
  ≈10:11:41           ollama ps
                      qwen3.5:9b-64k   6.7 GB   100% GPU   65536   4 minutes from now
                      (-32k absent, with 3 min 06 s still on its timer)
  ```

  **`-32k` had been used 1 min 54 s earlier and had over three minutes left. The only thing that happened in between was the `-64k` turn.** ⚠️ **The margin is the whole point** — the previous attempt failed on a 23-second overlap, so the number to quote is *"3 minutes remaining"*, not *"it was absent"*. **The `ps` time is corroborated independently:** `4 minutes from now` against `-64k`'s last stream at 10:10:59 puts it in 10:11:00–10:11:59, and the last `app.log` line is 10:11:09.
  - **Settled: two 9B variants do NOT co-reside on this machine. Ollama unloads one to load the other.** With `all-minilm` co-resident in the previous reading, this is a memory-headroom decision, not a model-count cap.
  - ✅ **And a CONFIRMED cold load costs ~2.6 s.** The `-64k` round 1 that forced the eviction ran **49.135 s**; the `-32k` round 1 before it ran **46.494 s** — both single-round, no tools, ~100 characters out. **This is the same ~4 s figure as the first pair, now with the load attested rather than inferred.** See *"Round 1 of every turn re-prefills the whole prompt"*.

- ⊘ **The SECOND `ollama ps` (≈10:04) is superseded — it missed by 23 seconds and could not have failed. Kept because the reasoning is the reusable part.**

  ```
  qwen3.5:9b-32k      f5b984e67b8d    6.1 GB    100% GPU    32768    4 minutes from now
  all-minilm:l6-v2    1b226e2802db     25 MB    100% GPU      256    2 minutes from now
  ```

  Taken right after a `-32k` turn ran **10:01:23–10:03:08**, so ≈10:04. **But `-64k` was last used at 09:56:00, and its 5-minute timer expired at 10:01:00 — 23 seconds BEFORE the `-32k` turn began.** It was already gone on its own, so its absence here is consistent with eviction *and* with plain expiry, and discriminates neither. ⚠️ **A reading taken to test a claim, that cannot fail the claim, is not a test** — the same shape as the `app.log` grep for item 35's `console.warn`.
  - **The protocol that settled it, with the window written down:** run one turn on each variant, the second **within five minutes of the first finishing**, then `ollama ps` the moment it answers — and **quote the loser's remaining time, not its absence.** This attempt left **5 min 23 s** between the turns; the successful one left **23 s**.
- ✅ **What this second reading DOES settle, and one of them is a measurement [qwensetup.md](qwensetup.md) explicitly asked for.**
  - **The KV-cache cost is now a number, not "under a gigabyte": `6.7 GB` at 64k vs `6.1 GB` at 32k — `+0.6 GB` for `+32,768` tokens.** qwensetup's *Footprint* bullet said *"load `qwen3.5:9b-32k` and diff the `SIZE` column: one command, and it converts 'under a gigabyte' into a number."* This is that command. ⚠️ **Extrapolating to weights ≈5.5 GB and 64k KV ≈1.2 GB assumes linearity and is NOT measured** — only the delta is.
  - **`all-minilm:l6-v2` co-resides with the 9B** (25 MB, `CONTEXT 256`), total ≈6.1 GB of 16 GB. **So Ollama is not enforcing a one-model cap** — whatever keeps two 9Bs apart is about memory, not a count. That removes the simplest competing explanation for the first reading.
  - ❌ **The `nemotron` lead is DEAD, killed 2026-08-01 by watching it load.** It was filed as *"nemotron is in neither reading and appears 0 times in `app.log`"*, hedged as possibly the logging trap. **It was the logging trap.** `ollama ps` during a Library tidy showed `nemotron-3-nano:4b  2.8 GB  100% GPU  4096`. **The utility model is in effect; `app.log` simply never names it.** *(Kept because the hedge is the reusable part — a zero from a grep is a claim about logging until something outside the log agrees with it.)*

- 🔴 **AND THE SAME SEQUENCE SETTLES SOMETHING BIGGER: Ollama holds ONE real model at a time on this machine, even when both would fit.** Eight consecutive `ollama ps` calls during a Library tidy, all before **10:17:10**:

  ```
  ×3   all-minilm:l6-v2 25 MB  +  qwen3.5:9b-64k 6.7 GB
  ×2   (empty)
  ×3   nemotron-3-nano:4b 2.8 GB  100% GPU  4096
  ```

  - **This is a forced unload with ~2 minutes of margin.** The last `-64k` round ended **10:14:10**, so its keep-alive ran to **at least 10:19:10** *(later still if the 10:14:36 / 10:14:55 utility calls touched it)*. **Every reading above was taken before 10:17:10.** So `-64k` was dropped while its timer was live, and `nemotron` took its place.
  - **6.7 + 2.8 = 9.5 GB on a 16 GB machine. It would have fit.** So this is **not** capacity — Ollama is keeping one real model resident and swapping. `all-minilm` at 25 MB rides along; nothing of consequence does.
  - 🔴 **Consequence for [qwensetup.md](qwensetup.md) item 9, whose stated *"complete fix"* is the Utility-model split: the split does not buy parallelism on this machine, it buys a model SWAP.** Item 9's premise is *"one Ollama model can't serve agent + background jobs"* — true, and moving background work to a second model does not fix it here, because the second model evicts the first. **At the measured ~2.6 s per swap this is tolerable, not fatal** — but the item claims something that is not happening, and that is worth more than the seconds.
  - ⚠️ **Not established: whether this is a configurable ceiling.** `OLLAMA_MAX_LOADED_MODELS` defaults low and, like `OLLAMA_KEEP_ALIVE`, a shell export cannot reach a brew-managed launchd daemon — see the keep-alive entry in [qwensetup.md](qwensetup.md), which is the same defect twice. **`launchctl getenv OLLAMA_MAX_LOADED_MODELS` is the ten-second check** and nobody has run it.
- **What this costs instead of memory:** a 6.7 GB reload every time you alternate between a 32k chat and a 64k chat — measured at ~4 s of first-token time, i.e. **noise against the 55 s round-1 penalty.** ⚠️ **Not established: what happens with `nemotron-3-nano:4b` in flight**, which is the case qwensetup's co-residency note was actually about. Eviction between two 9B variants says nothing about a 9B plus a 4B, which may well fit.
- **Consequence for this item: the memory argument is gone and the severity now rests entirely on the dead-tag branch below**, plus the fact that 72 sessions never see the 64k window. The overflow that motivated 64k was **1.9 % of turns**, so that half is S4 on its own.

**Stage 2 — is the dead-tag branch real?** Predicted from source, not observed, and it is what decides whether stage 3 exists.

- ✅ **The endpoint's cached model list, from `model_endpoints` on 2026-08-01:** `qwen3.5:9b-64k`, `qwen3.5:9b-32k`, `nemotron-3-nano:4b`, `all-minilm:l6-v2`, `qwen3.5:9b-16k`, `qwen3:8b-16k`, `qwen3:8b`, `qwen3.5:9b`. **`qwen3.5:4b-32k` is not among them** — Ollama no longer serves the tag those three sessions are pinned to. All three are **`archived=0`**, i.e. live in the sidebar, with 4–6 messages each.
- **Predicted chain, read from source:** `_match_cached_model_id` (`routes/chat_helpers.py`) is exact-match plus a `basename` compare that is a no-op for a tag containing no slash → `None`; `normalize_model_id` (`src/llm_core.py:1804`) applies the identical two rules to the live list → `None`; the caller is `if norm: sess.model = norm`, so **`None` leaves the dead tag in place** and the request goes to Ollama naming a model it does not have. `try_fallback_endpoint` cannot rescue it — it **skips the current endpoint** and only fires when the endpoint itself is unreachable, not when one model is missing.
- **The test is one message** in session `11ea1727` *(or `fae8323e` / `f4da3893`)*. **If it answers instead of failing, the reading above is wrong and stage 3 is not needed.** ⚠️ It appends a user row to a real old chat — that is the whole cost, and it is reversible by deleting the message.

**Stage 3 — the code fix, ONLY if stage 2 confirms.** The defect is not the pinning; it is that **`normalize_model_id` returns `None` for two different conditions and the caller cannot tell them apart**: *"the endpoint answered and does not have this model"* (`avail` non-empty, no match) and *"the endpoint did not answer"* (`avail` empty, `return None` at `:1814`). Only the first is safe to act on. Shape: distinguish them at the call site, and on the first, fall back to `default_model` **and log it**. ⚠️ **Report before acting** — log the remap for a few days before letting it change the model, per [`CLAUDE.md`](../CLAUDE.md) §3; a guard that silently answers as a different model than the chat says is a wrong-output path, and this item is not S1 today. ⚠️ **Negative control is mandatory**: an unreachable endpoint must still leave the tag alone.

**Stage 4 — the 72 rows. ⊘ NO LONGER URGENT — stage 1 refuted the reason for doing it.** It is now a preference: migrate so old chats get the bigger window, or leave them and pay ~4 s on each alternation. **Do not do it before stage 2**, and if you do it, keep the three `4b-32k` rows.

- ✅ **The migration destroys no evidence — checked before proposing it, not after.** `chat_messages.metadata` carries **`model` and `requested_model` per assistant message**: 161 rows on `-32k`, 9 on `-64k`, 8 on `4b-32k`. The per-turn record is independent of `sessions.model`, so rewriting the session rows loses nothing these docs reason from. *(Falsifier, also run: `requested_model != model` on **0 of 179** rows — normalization has never remapped anything, which is the same conclusion the source reading gives.)*

```
# app DOWN and snapshot taken first — see the snapshot block in qwensetup.md.
# Confirm nothing holds the file; app.db-journal does NOT answer this (CLAUDE.md §1):
lsof /Users/cedrik/odysseus/data/app.db
sqlite3 /Users/cedrik/odysseus/data/app.db \
  "UPDATE sessions SET model='qwen3.5:9b-64k' WHERE model='qwen3.5:9b-32k';"
sqlite3 /Users/cedrik/odysseus/data/app.db \
  "SELECT model, count(*) FROM sessions GROUP BY model;"
```

⚠️ **Leave the three `qwen3.5:4b-32k` rows out of it.** They are stage 2's only test fixture, and migrating them onto a working model destroys the one reproduction this item has.
⚠️ **This does not prevent recurrence.** The next tag change re-creates the split; stage 3 is what makes it self-correcting. **Doing stage 4 alone and calling the item fixed is how it comes back.**

### 43. `max_tokens=0, temp=1.0` arrives whenever a request carries no preset
> ✅ **Value corrected and verified live the same day: `Preset custom: temp=0.6, max_tokens=8192` at 2026-08-01 09:54:12.** The row stays open because **setting a slider does not stop it drifting**, and because the mechanism turned out not to be the one [qwensetup.md](qwensetup.md) has described since July.
>
> ❌ **CORRECTION — it is not "the custom preset resets".** `Preset None: temp=1.0, max_tokens=0` was caught in the act at **09:51:31**, one turn before the fix. `temp=1.0` and `max_tokens=0` are **`DEFAULT_TEMPERATURE` and `DEFAULT_MAX_TOKENS`, `src/constants.py:109-110`** *(grep the names, not the numbers)*. `validate_and_extract_preset` seeds both from those constants and only overwrites them inside `if preset_id and preset_id in self.preset_manager.presets` — so **the log line says the request arrived with NO `preset_id`, not that a stored preset was reset.** Nothing was overwritten; nothing needs re-checking in the preset itself. **The fix is on the client that omits it, or in the defaults — a different change from "re-check the slider", which is what qwensetup has been telling every session to do.**
> - **It is common, not an edge case:** `Preset None:` **164** times against `Preset custom:` **296** across both logs — roughly **36 % of turns carry no preset at all** and run at temp 1.0 with an unset cap. ⚠️ *That 36 % is a count of log lines, not of distinct turns; treat it as an order of magnitude.*
> - ⚠️ **What `max_tokens=0` does on the wire is NOT established.** It plainly does not mean "generate nothing" — the 09:51 turn produced 54 characters and a tool call on that setting. Whether it is omitted from the request or sent as a literal `0` is one read of the payload builder away and nobody has done it.
> - ⚠️ **Suggestive and NOT a finding, n=1 with three variables moved at once.** The `temp=1.0 / max_tokens=0` turn ended with `text_chars=0 tool_calls=0` on round 2 and needed the synthesized closing line; the `0.6 / 8192` turn wrote **263 characters** of real closing summary. Its visible message also ran reasoning and answer together with no separator (*"…with this tool.I'll create a brief document…"*), which is item 6/23's shape. **Model, context window and preset all changed between the two turns** — this is precisely the confound the bullet at the foot of this item warned about, hit on the first run after it was written. **Do not fold it into item 23 without a controlled pair.**

**Originally filed 2026-08-01 as *"the sampling preset drifted to `max_tokens=4352`"*, split out of item 41's third bullet, which recorded the spread and not the trend.**

### 45. The server injects a document the user never named, and closing the editor does not stop it
**Found 2026-08-01 by the maintainer noticing a chat "had access to" a document that was neither added manually nor shown in the workspace.** It is real, it is by design, and the design is not visible from the UI.

**`routes/chat_routes.py`** — when the frontend sends no active document, three fallbacks run in order *(grep `[doc-inject]`, do not trust line numbers)*:

1. the newest active **email draft** in this session;
2. **`found by session fallback`** — the newest active document with `session_id == session`, `order_by(updated_at.desc()).first()`;
3. **`found by in-memory active id`** — whatever the tool layer last created or edited, accepted if `not cand.session_id or cand.session_id == session`.

**Measured across `app.log`:** the frontend sends `active_doc_id=''` on **344 of 445** turns, so a fallback is the *normal* path, not an edge case. Outcomes on the 121 turns that reached the decision: **83 by ID, 17 session fallback, 1 in-memory, 21 none.**

- 🔴 **This corrects a precondition recorded under item 2a.** That item says *"close the open document in the editor first"* to stop the model reasoning about a document it was handed. **Closing the editor does not stop it** — fallback (2) keys on `session_id`, not on what the editor is showing, so the newest document in the chat is injected anyway. **The instruction as written cannot be followed**, and fd0f9ba0's failure (asked three times, got nothing, because the model reasoned a document already existed) is explained by the fallback rather than by the editor.
- ⚠️ **Fallback (3) accepts `session_id IS NULL`, so it can inject a document belonging to no session into ANY chat.** That is the same population as the 11 orphaned rows recorded on 07-30 — reciprocal with #34, which produces session-less documents on the client side.
- ⚠️ **Not established: whether this ever crosses into a genuinely NEW chat.** Fallbacks (1) and (2) filter on `session_id == session`, so a fresh session should match nothing; (3) is the only route in. **The discriminating run is a brand-new chat with no message sent, then one question that would reveal a document** — and it has not been done.
- **Not obviously a defect.** The fallback exists so the agent can see the document it just wrote when the client fails to name it. **What is wrong is that it is unobservable from the UI**: the user sees no open document and the model sees one. A one-line notice in the closing summary would close the gap without changing behaviour — report-only, the class that ships on test evidence.

### 44. ~~`/api/documents/ai-tidy` failed every logged call, and the 500s logged nothing~~ ✅ CLOSED 2026-08-01
**Filed, diagnosed, fixed and verified live inside one day. Body in [resolvedissues.md](resolvedissues.md), *"`/api/documents/ai-tidy` failed every logged call for three days"*.**

Two independent faults, each hiding the other: **thinking ate a 200-token budget** on a utility model that was in **neither** suppression pattern list, and **the model does not emit the JSON array the prompt asks for** — so the endpoint would have kept failing on an unlimited budget. `status=200` at 12:03:19, `parsed 28 verdict(s) of 30`, 17.8 s, first attempt.

- ⚠️ **Two things this closure does NOT cover, kept here rather than in the closed body because they are still owed.**
  - **The archiving branch has never been observed live.** All 28 verdicts came back `keep`, so `retire_document` did not run on this path. **The destructive half of this endpoint is still unexercised** — and it is the half that acts on a model's one-word verdict.
  - **Verdict quality under a suppressed reasoning channel is unmeasured.** Before suppression the same endpoint returned mostly `junk`; after, all `keep`. **Not a controlled comparison** — different document set, different config — but *"the junk detector now finds no junk"* is the shape of a result worth one deliberate look before trusting it.
- ⚠️ **`REQUEST_HARD_TIMEOUT = 45` (`app.py`) applies to this route and is not in `_TIMEOUT_EXEMPT_PREFIXES`.** It never fired on the working path (17.8 s), and it is why the earlier `max_tokens=700` experiment 504'd while a retry was still running. **Left alone deliberately** — nothing needs it now, and it exists so one hung handler cannot lock the server.

---

## Notes & constraints
Settled. Recorded so they don't get re-litigated. **Working method lives in [`CLAUDE.md`](../CLAUDE.md); this section is facts about the system.**

- **Per-round thinking suppression isn't currently possible.** `reasoning_effort:"none"` needs `tools and _is_qwen_thinking_model and _agent_thinking_disabled()` (`llm_core.py:2276`). `agent_disable_thinking` is `False`, **and** `tools` is always `None` on this endpoint — so flipping the setting changes nothing. Needs an override plumbed through `stream_llm`.
- ~~**Local models get no tool schemas at all**~~ — **retracted 2026-07-28, and it was never true of this model.** The rule reads `all_tool_schemas` is empty unless `_is_api_model`, which is correct; what is wrong is the assumption that a local model is not `_is_api_model`. `qwen3.5:9b-32k` resolves **`_is_api_model=True`** — `src/agent_loop.py` takes `any(h in endpoint_url for h in _API_HOSTS) or _model_supports_tools`, and the endpoint is marked as supporting tools. Every round in `app.log` since **2026-07-15** logs `native_tools=True tools_sent=24..31`, several hundred of them. ⚠️ **The `24..31` range is stale: a turn on 2026-07-31 sent `tools=42`** — outside the band, and outside the 24–36 degradation range [qwensetup.md](qwensetup.md) records for 8B-class models. **The first `edit_document` of that same turn failed as payload-as-text.** One observation, cause unknown, correlation unmeasured; recorded here rather than as an item because the constraint it contradicts lives here. **There is a channel:** `tool_choice` is plumbed through `stream_llm` (`tool_choice_none`, `src/llm_core.py`), and `_force_answer` already ships the narrowing move — it sets `all_tool_schemas = []` to force an answer.
  - ⚠️ **This one was load-bearing.** It is the stated reason item 8's active half had to be a *text nudge*, and that nudge wiped a 6,186-character document. **A bounded retry can restrict the schema list instead of instructing the model** — which is the shape item 8 asks for ("bound what it can do"), and it was available the whole time.
  - The same wrong claim is duplicated in a docstring on `_doc_edit_retry_directive`; corrected there too.
- **The model NAME is the only channel by which the served context window is known.** Ollama reports neither `/slots` nor a context field on `/v1/models`, so `_ctx_from_name_suffix` (`src/model_context.py:330`, `[-_](\d+)k$`) parsing `…-64k` is what sets `context_length`; without a suffix the known-models table wins and the app budgets against the architecture max while the server truncates at the modelfile's `num_ctx`. **A local variant created without the suffix is silently mis-budgeted, and nothing reports it.**
- **`agent_input_token_budget`'s default value IS the auto sentinel.** `budget_is_explicit` (`src/context_budget.py`) keys off the *value*, not settings presence, because the settings-save path materialises every default into `settings.json`. So `6000` means *scale to `0.85 ×` the window*; **any other number turns auto-scaling off permanently.** Setting it to 6000 deliberately is indistinguishable from leaving it alone, by design — and setting it to 6001 pins the budget for every model forever.
- **Don't widen `_ody_doc_finetune_mode`.** It gates tool narrowing and `tool_choice_none` as well as the loop break. The reporting path was split out of it deliberately.
- ~~**The redundant `user` document version is cosmetic.**~~ **Retracted 2026-07-19.** It was the visible edge of the duplicate-`doc_update` data loss in item 1.
- **`app.db` lags live activity — "the newest row" is not "the last turn".** Rows are written on `save_sessions()`. A query at 15:20 returned a newest row of 12:36 while fd0f9ba0 had run until 14:00. **`data/app.db-journal` on disk is how you tell the app is running**, and while it is, anything else opening the tree gets `disk I/O error`. Copy the file and query the copy.
- ⚠️ **`round_texts` was absent from every turn that called no tools** — nested under `if tool_events:` in `_compute_final_metrics`. **That is the field separating item 6 from item 8**, so it was missing from exactly the turns where the question arises. Fixed 2026-07-28. **Rows written before then cannot be classified retroactively** — the same limitation items 10 and 17 carry.
- **Timestamps in `app.db` are naive UTC while `ls`/`stat` and `app.log` report local CEST.** Cost a two-hour error that made three post-fix sessions look like they predated the fix. Full statement in [qwensetup.md](qwensetup.md), *"Reading `data/app.db` when debugging a run"* — kept there because that is where you are standing when it bites.
- **Cross-references rot when items are renumbered**, because every edit to these files comes from a different session. Three were found wrong on 2026-07-27; a fourth, in `tests/test_doc_report_gate_split.py`, on 2026-07-28. **All four were one-directional.** Every surviving reference *within* this file is reciprocal — #6↔#10, #7↔#8, #2↔#14, #8↔#20 — so renumbering one visibly breaks the pair. **A cross-file citation that nothing points back at is the fragile kind.** Before renumbering, grep `--include=*.py --include=*.js` for `todo.md` as well as the docs; source comments are cross-references too, and there are more of them.
- **On guards that write.** A guard that only *reports* can ship on test evidence. A guard that makes the model *act* can destroy data, and its tests must bound what it can do, not merely assert it exists. Item 8's reverted nudge passed every test written for it.
- **A "superseded" banner does not retire a document — deleting the prose does.** `KNOWN_ISSUES_debug.md` carried a banner saying its leading theory was wrong; an agent read the banner and argued from the body underneath it anyway, the third trip down a road two retractions exist to close. **Prose that reads like a live finding will be treated as one, however it is framed.** When an item is retracted, cut the reasoning and keep the conclusion.
