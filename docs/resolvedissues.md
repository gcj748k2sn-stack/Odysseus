# Resolved issues — Qwen 9B setup

Closed investigations. Setup and config in [qwensetup.md](qwensetup.md); open items in [todo.md](todo.md); last session's summary in [session-log.md](session-log.md).

**Trimmed 2026-07-28 from 283 lines to what still earns its keep.** The test applied to every line: *would someone about to make a decision be worse off without it?* What survived is **retractions** (wrong mechanisms recorded as findings — three separate re-investigations have been stopped by these), **traps that recur**, **ground truth**, and **the scope a fix was verified at**. What went is mechanism walkthroughs, per-run evidence tables and timings: all of it describes code that is now fixed, tested and committed, so it is re-derivable and was costing a re-read on every visit.

**Where the detail went.** Everything fixed before 2026-07-28 is in the initial commit series `b700632`…`ae4fa58`, whose messages carry the diagnosis; later work is in its own commit. **List them with `git log --format='%h %s' origin/dev..HEAD`** — deliberately not `<base-hash>..`, because the base moved: these were rebased onto a rewritten upstream on 2026-07-28 and every hash in these docs changed with it. Then `git show <hash>`, or `git log -S<symbol>` to find the change that touched a function. **Headings here are cited by title from source comments — rename with care** (see *Notes & constraints* in [todo.md](todo.md)).

---

## Three S1 warnings were suppressed whenever the model wrote its own summary — fixed 2026-07-28 (item 21)
`_closing_doc_summary` returned early on `if existing and not preamble_only`, discarding the **whole** of `_doc_tool_summary` — item 3's `stale_values`, 2a's `fidelity` and 2b's `known_facts`. The finetune-break path had the same gate. **The user had been told what happened, but not that it was wrong.**

**Run eb2d0ac1, 2026-07-28:** an 8,636-character document titled *"… Growth Phases Guide - **Fact Checked** 2026-07-28"* prescribing a *"Temperature drop of 5 – 10°F"* — a cold shock on a thermophilic species, the exact failure that retired the 4B. **2b caught it**; the model then wrote a confident ✅-ticked summary, so the warning was dropped and the user saw neither finding.

- **The net was withheld because the model sounded sure**, which is the one case it exists for. **Inverse of the `"Done."` bug:** that reported success for work that never happened; this reported success for work that happened wrongly.
- **Fix:** `_doc_tool_summary(info, warnings_only=True)` returns the ⚠️ blocks without the *"Created/Updated …"* action line, and both call sites append rather than return. Tests: `tests/test_doc_warnings_survive_model_prose.py`, with a byte-exact pin that default rendering did not change.
- ⚠️ **This invalidated part of 2a's and 2b's verification scope, and the re-verification is still owed.** Both were recorded live on `fb5525eb`, where the model wrote *nothing* after the tool (`round_texts=[0, 0]`) — the branch that always worked. **Neither has been seen live on the branch that was broken.** Re-verify by asking for a document on a turn where the model summarises its own work.
- **Found by reading runs, not by testing.** Every wiring test asserted the findings reach `_doc_tool_summary`; none asserted `_doc_tool_summary` reaches the user. **A test that stops one call short of the user is the item 16 shape** — it pins the plumbing and not the delivery.

## Every cloned document was named "Untitled" — fixed 2026-07-29 (item 24)
`libraryImportDocument` in `static/js/documentLibrary.js` computed `baseTitle`, including the `(2)`/`(3)` dedup, and then **never put it in the POST body**. `DocumentCreate.title` defaults to `"Untitled"` (`routes/document_helpers.py`), so every clone took the default.

- **Pre-existing in Clone; "Open in new chat" inherited it** the moment that was added, because it ends by calling the same function.
- ✅ **Verified live 2026-07-29, both paths** — clone at 15:36:31 and *"Open in new chat"* at 16:02:53 each produced a correctly titled document ~38 ms after their session. No `(2)` suffix on either, which is correct: the dedup only compares titles **within** a session.
- ⚠️ **Verified by reading `app.db`, because this repo has no JS test harness.** That is the available standard here, not a shortcut — a JS change cannot be confirmed any other way.
- ⚠️ **The fix rode into `HEAD` inside a 120-line commit whose message described only the 3-line title change.** The rest was the *"Open in new chat"* feature, sitting uncommitted in the working tree. Amended the same day. **An uncommitted feature will attach itself to the next commit that touches its file** — item 5's failure mode wearing different clothes.

## Quoted phrases returned locale filler — fixed 2026-07-29 (item 29)
When the model writes an exact-phrase query, the pinned engines return few real matches and **backfill with locale-based filler**: a Dutch casino, GitHub Desktop, a hotel in Finnentrop, Psalm 37, five pages of *My Little Farmies*. **One quoted query came back 5 of 5 junk.** The user is in DE and `language=en` is pinned but the region is not. Fixed in `services/search/providers.py` — `quoted_phrases` / `result_has_phrases` drop results lacking the quoted phrase, `strip_quotes` drives an unquoted retry when filtering empties the set. **This is not a relevance heuristic; it is the semantics of quoting.**

- **The split is measured, not impressionistic.** Replaying all 58 recorded `web_search` calls (290 results) out of `tool_events[].output`: **quoted — 7 queries, 6 with junk, 18/35 junk results; unquoted — 51 queries, 1 with junk, 3/255.** Replay of the shipped predicate: 18 junk dropped, 0 false positives, 17 good kept, 255 unquoted untouched.
- ⚠️ **The corpus is truncated by the recorder.** `core.py` writes `result['snippet'][:200]`, so a term past character 200 is invisible to the replay, and `age` was not parsed. **51 of 58 searches are a fixed point under the current ranking**; the other 7 are most likely those two gaps — inferred, not shown.
- **Filtering runs BEFORE the `[:count]` slice**, so dropped slots refill from further down instead of shrinking an already-truncated window. A test pins this and fails if the order is swapped.
- **Tests (16), three negative controls.** ⚠️ **Reverting both changes turns 7 of the 16 red**, checked before believing them; the controls stay green in both states, which is what makes them controls. M1 run 2026-07-29: 16 passed on the pinned venv with `asyncio_mode=auto` honoured. *(A sandboxed Linux run reporting 72 passed with unpinned deps could not have exercised the async paths and should not be cited.)*
- ⚠️ **Not seen live.** Every recorded instance predates the fix.
- **Also landed here: per-result `engine` attribution**, carried into the parsed result and copied into `web_sources` so it survives in `app.db` — **`app.log` rotates, `app.db` does not.** Until the first post-fix search, engine attribution for everything in this file rests on the `msockid=` parameter on one URL, which is Microsoft's — **one inference, not a record.**

## Throughput cliff on larger context — RETIRED, disproved by its own data (item 9)
**Not a work item. Kept as a counter-example, because the obvious optimisation it invites is the wrong one.** Ordered by input size the numbers *rise*: 10,223 tok → 5.22 tok/s · 34,723 → 6.52 · 56,323 → **6.78**. Time-to-first-token does climb, but that is prompt ingestion, not generation, and **the two must not be conflated again**. Confirmed 2026-07-28: with TTFT subtracted, all twelve recorded turns run 8.9–13.6 tok/s. **Do not optimise for "less context" on this evidence.**

## `web_fetch` failure rate on cultivation sources — folded into item 2, never measured (item 15)
**Its premise was answered before it was measured.** Roughly a third of fetches fail on the sites this task reaches for. But run 31e0af64 fetched **one clean source, verified byte-exact**, and still produced four defects. **Retrieval quality is not the load-bearing cause.** Worth knowing when a fact-check turn ends empty-handed; measuring it precisely would not change what gets built next.

## A turn that failed read as a turn that was slow — fixed 2026-07-28 (item 9b)
Run fd0f9ba0 ended on `{"error": "Read timeout", "status": 504}` after 380.673 s. `app.log` carried it as a WARNING and nothing else; the persisted row said 29 output tokens, 380 s, `usage_source: estimated` — the profile of *a slow turn*, not a failed one. **Three sessions of throughput analysis were built on rows of that shape**, including the retired "throughput cliff" and its unexplained 0.39 tok/s outlier.

- **The mechanism was in `app.log` the whole time.** One grep, after a session of inferring mechanisms from database columns. This is the first entry in these notes where the log would have replaced the entire investigation — see the rule at the top of [CLAUDE.md](../CLAUDE.md).
- **Fix:** `metrics["stream_errors"]` persists round, elapsed and detail; `_stream_failure_notice()` tells the user the request failed and that what they are reading is partial. Absence of the key means the stream raised nothing — the item 17 convention. The zero-tool promise notice is suppressed when the stream failed: the model didn't choose to stop, so "ask me again and I'll do it" would misdescribe it.
- ⚠️ **The instrument built before reading the log was wrong, and one live run caught it.** `max_delta_gap` (longest silence between deltas) spans tool execution and the next round's prefill, so the first real turn recorded a 168 s "gap" on a turn that generated 2,131 tokens — 130 tok/s implied, against a measured band of 8.9–13.6. Removed the same day. **A metric that reads plausibly and measures something else is the orphaned-guard failure in a new place.**
- **Generation speed itself is not the problem and never was.** With time-to-first-token subtracted, all twelve recorded turns run 8.9–13.6 tok/s from 10k to 56k input tokens. Do not re-open "throughput collapses with context".

## The model wrote the tool call instead of making it — guard built 2026-07-29 (item 28)
Session ae223b4c. `edit_document` failed with *"received no content"*, whose error text said *"Retry by writing the edit as a fenced block"*. The model complied and tagged the fence ```json. **The fence tag IS the dispatch key** (`_TOOL_BLOCK_RE` over `TOOL_TAGS`), so ```json is inert display text. Three turns emitted ~1.5 KB of edit payload each, ran no tools and changed nothing; one closed with *"Updated … now contains only current sensor readings as requested"* — a false success claim, the `"Done."` family.

- **Every prior guard was blind to it, each defensibly.** `_gathering_only_notice` needs a tool to have run; `_unstarted_promise_notice` needs a trailing colon and this text ends on a confident sentence; `_text_is_only_preamble` needs a tool boundary. 2,266 characters of prose reads as answered. `tests/test_tool_payload_as_text.py` pins the promise notice as silent on both fixtures *before* asserting the new one fires.
- **Detection is lexical and that is load-bearing — established by mutation, not assertion.** The payload embeds literal newlines inside JSON string values and dies on `Unterminated string`. **A parser is the wrong instrument for detecting malformed output — it filters out the evidence.**
  - ❌ **The `json.loads` comparison — *"1 of 3"* here, *"1 of the 2"* in the docstring — is NOT reproducible.** Re-checked 2026-07-29: the mutation itself was never written down, and a plausible reconstruction scores **2 of 3**. **Unfalsifiable as filed**, which is worse than wrong. The direction the design rests on still holds; the number does not.
  - ✅ **The corpus measurement does reproduce.** Lifting `_fenced_regions` and `_tool_payload_looks_like_edit` out with `ast` and running them over all 129 assistant rows in a hash-verified copy of `app.db`: **3 hits — 17:48:20, 17:55:34, 18:07:52**, all `json`-tagged fences matching on edits/find/replace keys. The closed-fence-only mutation scores **3 of 3**.
  - ❌ **The source docstrings said "2 recorded instances" and "2 of 2"** — written when only the first two existed, never revisited. Corrected in place.
- ⚠️ **Do not re-derive the empty-`edits` count from `app.db`.** A naive sweep returns 9; eight are pre-2026-07-28 rows with no `full_command` key at all. **Check `'full_command' in event`, not `event.get(...)`.**
- ⚠️ **The unterminated-fence branch is defensive and has never fired.** A closed-fence-only mutation still scores 3 of 3. An earlier draft of the docstring called it "half the corpus"; that was wrong and is corrected in the source. **The first detector missed an instance because of `json.loads`, not because of the fence** — two different guesses, one written down before it was checked.
- **Measured on all 129 recorded turns before shipping: 3 hits, all true positives, 0 false positives**, and 0 on turns that did run tools.
- **Proximate cause fixed with it:** both retry texts now state that the fence tag must be the tool name and that a ```json block runs nothing.
- ⚠️ **Root cause open and n=1.** In the one properly-recorded empty call the FIND/REPLACE payload is sitting in `thinking` — item 23's mechanism applied to tool arguments. **Salvaging it is filed, not built:** bounded (it could only write content it already holds) but an *acting* fix on a data-mutating path at n=1, which is the class that wiped a 6,186-character document.

## Non-document tools reported nothing at all — guard built 2026-07-28 (item 11)
`_side_effect_tool_summary` in `src/agent_loop.py`, wired into the turn-end path beside `_gathering_only_notice`. Report-only, so it shipped on test evidence.

**Session 57dcd968.** Asked for *"a document with temperature and humidity data over time from http://192.168.0.185"*, the turn ran `web_fetch` → `write_file` → `get_workspace` and the entire saved reply was the 175-character preamble written before any tool ran.

- ⚠️ **The founding claim was backwards, and its lesson with it.** Filed as *"a file was written and the user was told nothing about it"*. The record says `exit_code=1` — *"path 'TEMPERATURE_HUMIDITY_READINGS.md' is outside the allowed roots"* — then `get_workspace` answering *"No workspace is set"*, then a round of 0 chars and 0 tool calls. **The tool failed with an actionable error, the model was handed the fix, and the user was told none of it.** The entry also argued the watch note's trigger (*"refile if a non-document tool is seen **failing** silently"*) would have missed it because the turn succeeded. It failed. **The trigger would have caught it; what failed was reading the row** — the claim came from the tool *sequence* without reading the tool *result*.
- **Every guard missed it, each defensibly.** `_gathering_only_notice` requires all tools in `READ_ONLY_TOOLS` and `write_file` is not one; `_unstarted_promise_notice` bails when any tool ran; `_doc_tool_summary` only knows document tools. `tests/test_non_document_tool_report.py` pins all three as silent on that turn *before* asserting the new one fires.
- **Coverage is the inverse of `READ_ONLY_TOOLS`, deliberately.** That allowlist's argument does not transfer: there, guessing wrong tells a user nothing happened when something did; here it costs one extra line quoting what a tool returned. **The failure modes are not symmetric, so the defaults should not be either.**
- **Successes report only when the model said nothing; failures report either way** — item 21's argument on the non-document path.
- **Measured on the whole corpus before shipping:** 77 recorded turns, 72 with tool events, **7 produce a line — 5 saved as a bare `"Done."` with `round_texts` all zero, 2 as a preamble. None had a reply describing the work, so zero duplicates.** One of the five is `write_file` returning *"Wrote 0 bytes"* — a file emptied and reported as success, in the window item 8's reverted nudge covers.
- ⚠️ **Known gap:** `manage_notes`, `manage_calendar`, `manage_tasks`, `list_emails`, `read_email` are excluded, because the end-of-turn path *replaces* `full_response` with their output and would discard anything appended earlier. A `manage_notes` **create** stays unreported. Fixing it means reordering that block.
- ✅ **Verified live 2026-07-29, session ae223b4c.** `web_fetch` → `write_file` (`exit=1`, *"path '~/…' is outside the allowed roots"*) → `get_workspace`, and the user was told: *"⚠️ `write_file` failed — …"*. **Near-identical to the founding case above**, which saved a 175-character preamble and nothing else. Same prompt, same sequence, same failure, now reported.
- ❌ ~~"Separately, unresolved: the model chose the wrong tool — asked for 'a document' it wrote a workspace `.md` file"~~ — **RETIRED 2026-07-29, it was never a choice.** A LAN address in the prompt strips every document tool before the model sees them; see [todo.md](todo.md) item 27, reciprocal (#11↔#27). ⚠️ **This claim survived in two places at once for a day** — retracted in one bullet of the item and restated as live three bullets later. **A retraction that leaves the original prose standing has not retracted anything.**

## Documents do stream into the editor — the item was wrong, the complaint behind it was not — 2026-07-28 (item 22)
Filed as *"there are zero `doc_stream_open` / `doc_stream_delta` in 35,744 lines of `app.log`"*. **Both are SSE frames yielded to the browser; neither is ever logged.** The grep measured nothing. **But one of the five emit sites has an INFO log beside it** — `Doc streaming: open title=…` — and that one has fired **32 times since 2026-07-16**, most recently 21:41 CEST on 2026-07-28.

**What is true instead, and it is worth more than the original claim.** Across all 32, the stream opens at **100 % of its round** — median 0.1 s before `round_stream_done`, and a median of **0.069 s** before the end-of-stream `received N native tool call(s)` event. Round lengths ranged 34 s to 262 s and the position never moved. On the 245 s round at 21:37:19: thinking streams normally to `first_visible_token` at 40.6 s, then **204 seconds of silence**, then open, tool-calls and stream-done inside 91 ms.

- **So the feature works and is a no-op.** The user watches an empty editor for the whole generation and the document lands whole at the end. The lived experience the item was opened on is real; *"never streams"* was the wrong description of it. **Severity: S4** — nothing is lost or wrong, and the per-delta scanning cost (`_doc_acc`, `_fence_markers`, the `"title"` regex) is trivial. **There is nothing to build.**
- **It corroborates 9b's mechanism from a direction that does not depend on a DEBUG grep.** The tool-call payload materialises at end-of-stream, which is what a per-read inactivity timeout needs in order to act as a cap on total generation time.
- ⚠️ **One assumption remains and should be named rather than assumed away:** this reasoning needs `"title"` to precede `"content"` on the wire. The schema declares `properties` and `required` in that order (`src/tool_schemas.py`), and the parser at the emit site searches for the title first, so it is the intended order — but it has not been observed directly. `full_command` cannot settle it: document tools persist a *rendered* form (title, then content, joined), not the raw JSON, so all 35 recorded values contain no `"title"` key at all. **Do not try to read wire order out of `full_command`.**
- **The ten-second check that closes it**, if anyone needs it closed: `_root_logger.setLevel(logging.INFO)` at `app.py:88` → `DEBUG`, run one `create_document` turn, and count `tool_call_delta` lines. **One** means the payload is buffered; **many** means it streams and the title simply arrives last. Nothing else in the codebase distinguishes the two.
- **The transferable lesson is about where the evidence came from, not about streaming.** One grep produced this item and 9b's mechanism, and neither string could ever have appeared in the file being grepped. The fix that found the truth was reading the *emit site* — and discovering that one of the five had a logger call the others lacked. See [CLAUDE.md](../CLAUDE.md), *"An absence in the log is only evidence if the thing could have been logged"*.

## The save path decided which half of the answer was thinking — fixed 2026-07-28 (item 6)
`_normalize_thinking` in `routes/chat_helpers.py` wraps *untagged* inline reasoning in `<think>` tags so it survives a reload. Its fallbacks picked the split point by **position** — "everything above the last plausible line is reasoning" — and `save_assistant_response` then overwrote `metadata["thinking"]` with the result, discarding the stream's own correct classification. Any answer opening with `"I need "`, `"The user "`, `"I should "`, `"I will "`, `"They are "`, `"The question "` or `"I can "` was eligible.

- **The arithmetic filed under item 6 for nine days was exactly right and pointed at the wrong layer.** `thinking` was a byte-for-byte 219-char prefix of a 300-char `round_texts[0]`, saved message 79 chars. Replaying the "last resort" branch by hand against the stored text reproduces the split at 219 characters exactly.
- **Two instances in 65 recorded turns.** f14a8f52 lost a clarifying question (300 → 79); c7da3649 lost a fact-check naming three real errors (705 → **28**, leaving *"Let me correct these issues:"*).
- ⚠️ **The second one had been read as item 8.** A turn that ends on a lead-in *is* a dangling promise, and this manufactured one. **Two different bugs are indistinguishable from the saved message alone** — separating them needs `round_texts` next to `content`, which is the same one-query check the REVERT/BLEND split gives for item 1. Item 8's counts should be re-read on that basis.
- **The retraction it kept colliding with was about a different file.** *"The reasoning parser eats the answer / investigate `<think>` handling on the `/v1` stream path"* is retracted and stays retracted — that is `llm_core.py`, during the stream. This is `routes/chat_helpers.py`, after it. **A retraction scoped to one layer is not a finding about the other**, and reading it as one is what kept the item open.
- ⚠️ **Item 8's evidence base needs re-reading because of this.** Run c7da3649 ended on *"Let me correct these issues:"* — a textbook dangling promise, **manufactured by the save path**. **Do not count a dangling-promise run as item 8 without comparing `round_texts` against the saved `content` first.**
- ❌ ~~The 2026-07-27 frequency count~~ — **retracted, not evidence.** All-zero `round_texts` is 15 of 40 turns and appears on turns that ended fine; it is the base rate, not a signal.
- ⚠️ **The item had also filed itself as blocked on item 10**, needing "the raw stream". It never was: `round_texts` persists the complete pre-split text and always has, while `full_command` carries tool *arguments* and could not have helped. **A dependency on a field nobody has re-read is a guess** — the same shape as item 10's own effort estimate being M for a one-line change.
- **Fix:** inferred splits must clear `_reasoning_split_is_safe` (a reply ending in a colon is a lead-in; markdown structure in the discarded half means authored output). Declared splits — real `<think>` tags, an explicit `Thinking Process:` marker with a clean boundary — are untouched. **Refusing is cheap and accepting wrongly is not**, so it refuses whenever unsure.
- **The tests need their negative controls more than their assertions.** A "fix" returning the input unchanged satisfies every loss assertion and deletes the feature; `test_genuine_*` is what stops it. Same shape as item 19's `isabs` guard and 2a's clean run.

## The document contradicted what we had already established — checker built 2026-07-28 (item 2b)
`src/known_facts.py` against `config/known_facts.json`. Sibling of 2a and deliberately the same shape: report-only, silent by default, findings in the closing summary. Different question — 2a asks whether a document matches *the data it was handed*, this asks whether it matches *facts established once and written down*.

**The measurement that justifies it:** six same-task runs scored against cultivation sources. The plain "create a document" run came out **closest to correct**. The run *asked* for fact-checked information, which fetched four sources to get it, came out **worst** — the *P. ostreatus* range on a tropical species, and 26 °C flagged as too warm when it is optimal. Both bad documents titled themselves "Fact Checked & Corrected". **The agent's own verification step is anti-correlated with correctness here**, so the check cannot live inside it.

- **The negative control is the design constraint, not a nicety.** The first version reported the best document in the corpus as wrong six times over. Every rule was narrowed until it went silent on that document while still catching both bad ones.
- **Five false-positive classes, all found by sweeping all 20 recorded documents rather than the 3 fixtures.** Worth knowing because four of them are mistakes about *what a number means*, not about the fact:
  1. **A delta read as a setpoint.** "slight reduction of 3-5 °C" reported as a temperature outside the fruiting range. This is the checker committing the exact error it exists to catch.
  2. **A limit read as a setpoint.** "below 15 °C fruiting stalls" is true and is not a claim that 15 °C is the target.
  3. **A hazard named in troubleshooting read as a prescription.** The best document lists "Temperature shock" as a *cause* of dark caps. **A document that agrees with you must not be reported for agreeing.**
  4. **A phase named in a comparison read as an attribution.** "20-25 °C, cooler than colonization" is a *fruiting* number; scanning the line for phase words judged it against the colonization range. Attribution is now taken only from a heading, a table row's first cell, or an explicit `for`/`during` — never from `than`.
  5. **A passing mention read as a subject.** A DHT22 datasheet naming the project it was written for became eligible for mushroom facts, and its "±2 °C accuracy" was reported as a prescribed drop. The marker must now appear in a heading or more than once.
- **Whole-line filtering was the wrong instrument and broke the acceptance case.** Excluding any line containing a delta word silenced `14–21°C … for fruiting` because "cooler" sat 30 characters away in another clause — the single worst claim in the corpus, hidden by its own fix. Qualifiers are now judged in a window around the number, because whether a number is a setpoint is a property of the number, not of the line.
- **Ranges are judged on their midpoint.** "24-30 °C" against a recorded 24-29 is a wider tolerance, not a false claim; firing on one degree of overhang produced more findings than signal and would train the reader to skim.
- ⚠️ **Tests only — not seen on a live turn**, same as 2a, and for the same reason: `app.db`'s newest row predates both checkers.

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
- ⚠️ **Item 6 filed itself as blocked on item 10 three times and was wrong every time.** `full_command` is *tool arguments*; item 6 needed `round_texts`, which was already persisted. **A dependency on a field nobody has re-read is a guess.** Kept as the back-reference so the pair stays reciprocal.
- ⚠️ **Item 17's trap that the fix does not close: `full: true` changes the cache key.** The same URL fetched with and without `full` uses two independent entries and can return two different bodies in one session. *Which* entry you got is now visible; **that there are two remains a trap.**
- ⚠️ **The label is delivered and half-believed, twice now.** 42889f7b quoted *"cached ~77 seconds ago"* in its body and titled itself *"(Live Fetch)"*; eb2d0ac1 built on a fetch **1,123 seconds** old and called the result *"fact-checked"* with *"✅ verified facts"*. **The model reads the flag and then writes a claim that contradicts it** — getting the label into the prompt was necessary and is not sufficient. Operational detail in [qwensetup.md](qwensetup.md), *"`web_fetch` — what it sees, and what it silently reuses"*.
- **A replay harness over history, symmetric with the editor-side one in `tests/tools/`, is now possible and not built.**

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

## Sixteen days of uncommitted work — committed 2026-07-28, recurred, closed 2026-07-29 (item 5)
Was item 5. Seven commits, `b700632`…`ae4fa58`, 47 files, identity set repo-locally, nothing pushed.

**It recurred within hours of being closed, and that time it broke `HEAD`.** The 2026-07-28 commit swept up everything *up to that morning*; everything built later the same day went untracked while the row read *✅ committed — verified live*. A committed `src/agent_loop.py` imported an untracked `src/known_facts.py`, so a fresh clone could not import the core agent module — the app would not start and a committed test file could not be collected. `CLAUDE.md`, the working rules every session reads, had never been committed at all. Re-committed in five commits on 2026-07-29, the first (`0173fc8d`) existing only to make `HEAD` importable.

- ✅ **Closed 2026-07-29 by the check that was missing both times: a clean clone.** `git clone` into `/tmp`, fresh venv, full suite — **`2 failed, 5738 passed, 4 skipped` in 122.05 s**, identical to the working tree, plus **2,930 first-party imports, 0 unresolved.** The two failures are item 18.
- ⚠️ **A green suite in the working tree cannot detect this and never could.** Every run had the untracked files on disk. **The suite tests the tree, not the commit.** The mechanical check is an AST sweep of every first-party `from (src|routes|core|services)… import` against files present in a clone — seconds, no venv, and it is not part of any gate.
- **Both recurrences began the moment an item was marked done.** `✅ fixed` means "works on this machine", not "is in the repository". **Before writing ✅ on anything that ADDED a file, run `git status`.**
- ⚠️ **An uncommitted feature attaches itself to the next commit that touches its file.** The item 24 clone-title fix — three lines — went in as a 120-line commit that also carried an entire *"Open in new chat"* feature left in the working tree by an earlier session, under a message describing only the three lines. Same disease, later stage.
- ⚠️ **Do not diff working files against blobs to decide what is modified.** `.gitattributes` sets `*.ps1`/`*.bat` to `eol=crlf`, so the blob is LF and the working tree is CRLF by design; a `git show HEAD:<file>` comparison reports three Windows scripts as modified that `git status` calls clean.

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

## Autosave reverting AI edits — fixed 2026-07-19. It was a duplicated SSE event, not autosave and not the CAS. (item 1)
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
- **✅ Failure branch verified live 2026-07-27** (31e0af64): *"I couldn't apply the edit — the document is unchanged."* **✅ Accumulation branch verified live 2026-07-28** (fb5525eb turn 3): *"7 edits applied across 2 rounds, 4 not applied…"* — that was the item's last tests-only scope, and it closed it.
- ⚠️ **One possible under-report is recorded and NOT diagnosed — check before trusting the counter.** Session d16f7a83 turn 1 records **four `edit_document` tool events** (all `<<<FIND>>>`, all `exit_code=None`) while the message says *"rejected **1** attempt this turn … (skipped 1)"*. It may be legitimate — one attempt retried across four rounds — but **that is the exact shape of the accumulation bug this item was closed on.** One query settles it: compare `tool_events` length against the reported count on that row. Carried as an owed verification in [todo.md](todo.md).

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

## Research path moved off the retired 4B — 2026-07-19 (item 4)
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
