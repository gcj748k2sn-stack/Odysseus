# Open items — Qwen 9B setup

**Open items only.** How to work: [`CLAUDE.md`](../CLAUDE.md). Setup: [qwensetup.md](qwensetup.md). Closed and retired items — conclusions, plus the index of their rows: [resolvedissues.md](resolvedissues.md). What the last sessions did: [session-log.md](session-log.md).

Items whose record is longer than a screen live in [`items/`](items/), one file each; the row below always carries the current status. The whole file as it stood before this split (2026-10-06, 217 KB — closed bodies, the old *Next* lists and owed-verification notes included) is [archive/todo-2026-10-06.md](archive/todo-2026-10-06.md): history, not current state.

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
| 3 | Documents contradict themselves | S2 ⚠️ | M | detection live; **prevention open** — re-verified verbatim 2026-07-31 | **live** (lint); **share attributable to the model never measured** |
| 8 | Agent gathers information, then stops | S3 | M | reporting fixed; **active half reverted** | **live** / tests (zero-tool) |
| 12 | Wasted verification rounds | S4 | XS | open — **re-measure first, see item 20** | — |
| 13 | Terminal access-log noise | S4 | S | **built 2026-10-04 (night), commit `2c69b66f` — 200s gone live**; **`GET 304` page-load burst and the per-minute SMTP/IMAP warnings quietened 23:40, commit `e45467d9`** | **live** — two runs (22:57, 23:09): zero `200` access lines, 404s shown · **tests (15)** · 4 mutations |
| 14 | Web search derails on ambiguous common nouns | S3 | M | open — the quoted-phrase half is item 29; the region/news-routing half is item 47 | — |
| 20 | 116 lines of agent rules never reached a model | S3 | S | open — decision per rule pending · **re-measured 2026-10-08: duplicate rule 3 of 5 at temp 1.0, 4 of 5 at temp 0.6** (07-30: 6 of 6 on Ollama) — temperature is not the explanation at n=5 | **live ×5** (LM Studio Qwen) · tests |
| 25 | A path-confinement test passes without the thing it tests | S4 | XS | ✅ **fixed 2026-10-04 (night), commit `b9616240`** — negative control added, fixture moved off `tmp_path` without writing anywhere | **sandbox** — the item's own mutation (`return_value=[]`) now **fails**; 2 more mutations caught · M1 suite owed |
| 27 | A LAN address in the prompt deletes every document tool | S3 | S | **(a) `1e4c0a48` and (b) `9d5f5aac` both verified live** (23:09 / 2026-10-05 07:49) — the LAN prompt now gets document + web tools, no `bash`, and asks when the device is down; (c) still open | **live** `2e9f541d`, 07:49 run · **tests (23 + 19)** · 8 mutations |
| 34 | An aborted document stream orphans its placeholder as `activeDocId` | S2 | XS | open — reaper found, fix narrowed; **reproduced on demand 2026-07-31**, measuring frequency before building | **live — scripted repro + `[doc-put-404]` in `app.log`** |
| 40 | Round 1 of every turn re-prefills the whole prompt | S3 | M | **measured 2026-08-01, cause not identified** · cache-hit log line live since 2026-10-05 (`f5ee9874`) — re-measure with `cache_n` | **275 rounds**; 4–8× slower than later rounds at matched size |
| 42 | Sessions pin the model tag per row; a tag Ollama no longer serves does not fall back | S3 | S | **co-residency half ⊘ disproved; dead-tag half ✅ CONFIRMED LIVE — fix not built** | **live** — `404 (model 'qwen3.5:4b-32k' not found)`, and it fails **visibly** |
| 43 | `max_tokens=0, temp=1.0` arrives whenever a request carries no preset | S3 | XS | **value corrected + verified live 2026-08-01; recurrence OPEN, mechanism now known** | **live** — `8192` at 09:54:12; the zero-preset turn caught in the act at 09:51:31 |
| 45 | The server injects a document the user never named, and closing the editor does not stop it | S3 | S | **filed 2026-08-01 — from the maintainer noticing a chat "knew about" an unopened doc** | **live** — 17 `session fallback` + 1 `in-memory`; frontend sends `active_doc_id=''` on **344 of 445** turns |
| 47 | A query containing "today"/"latest"/"news" goes to SearXNG's news category — here Bing News — and skews price lookups to Indian outlets | S3 | S | filed 2026-10-02 — measured, not fixed; engine mix widened in untracked `searxng/settings.yml` | **log** — 5 of 5 India-domain sources since 08-01 came from `bing news`; 0 of 70 `google cse` results |
| 48 | The context popup's "used" figure is the turn's summed input tokens, not the request size the bar shows | S4 | XS | **second fix 2026-10-08, uncommitted** — the 10-04 fix printed Odysseus's estimate while the percentage uses the provider's real count | **live 2026-10-08** — 9b run 3: before *28,629 used* beside 34.1 % (43.7 % implied); after *22,331 used* = 34.1 % · **corpus:** 56/56 rows with `usage_buckets` now match (0/56 before); 65 older rows without buckets mismatch either way · `node --check` |
| 50 | LM Studio's loaded context is invisible to Odysseus — a long turn outgrows it and LM Studio cuts the middle out of the prompt | S1 | M | **discovery half fixed and verified live 2026-10-04**; **in-turn half mitigated by config 18:41** — GGUF build at a **65,536** window (0 of 511 recorded turns exceed it, peak ≈42.3k); the between-round guard is still not built | **tests (27)** + 4 mutations; M1 suite 5,885 passed, 0 failed (after two test fixes) · **live** — `context_length=32768` at 12:41 · **log** — `TruncateMiddle … removing 22510 / 25702 / 27445 tokens` on rounds 12–14 of `933f8674` · **live** — `context_length=65536` at 18:41 after the switch |
| 52 | Odysseus's own end-of-turn notices were replayed to the model as its words — "Ask me to continue" never worked | S3 | S | ✅ **built 2026-10-04, commit `c084b9e3` — M1 suite green; live check passed 2026-10-06 00:31** | **tests (29)** · 6 mutations · **corpus** — 56 of 56 notice replies stripped, 0 of 212 others touched · **M1 suite 5,953 passed, 2 skipped, 0 failed** |
| 53 | Context blocks (memory, skills index, documents) go to the model as extra user turns at the start of the chat — models read them as things the user said | S3 | M | **drafted 2026-10-04 — design only, nothing built** | **corpus** — 15 of 268 thinking blocks mention the wrappers, several as user turns; code read, prompt not captured |
| 54 | After the first message on a page, "New Chat" showed an empty chat but the next message went into the previously open chat — `sessions.js` (and 10 other modules) ran as two copies | S2 | S | ✅ **fixed 2026-10-04, commit `c29a068a` — verified live in the agent's pane and in Safari** | **live** (pane, sends intercepted) · **tests (4)** · corpus — every multi-test chat of 10-04 |
| 55 | `trigger_research` reports "Deep research started" when the research model is unreachable — the background run fails 1 ms later and nobody is told | S3 | S | ✅ **fixed and verified live 2026-10-04 23:24, commit `0c71f29e`** | **live** (`cf7e2281`) — LM Studio down: `exit_code=1` 73 ms after `/research/start`, reply says it did not start and offers web search · **tests (8)** · 3 mutations |
| 57 | Tool RAG picks a different tool set per message, and the chat template renders tools ahead of the history — every new message re-reads the whole conversation on llama.cpp / LM Studio | S4 | M | filed 2026-10-04 — not measured directly | **log** — 6 → 8 → 7 tools in `cdb89980`; first-token 42–61 s on 3–4k prompts |
| 58 | Each tool round deletes the thinking of earlier rounds, so the prompt prefix changes every round and local servers re-read everything after it | S3 | S | filed 2026-10-04 — **strongly supported by a clean run (23:09), **cache line live (`f5ee9874`) — measured 2026-10-05:** rounds that drop reasoning re-read 8.7–9.5k tokens (149–161 s), rounds that keep the prefix 4.6–26 s; the break point sits ~1k tokens earlier than this item predicts** | **log** — round 2 +57 tokens: 1.7 s to first token; rounds 3–5 +63…+224 tokens: 16–21 s |
| 59 | Odysseus never sends `reasoning_effort` to llama.cpp endpoints, so Bonsai 2 always thinks at its template default `xhigh` | S4 | XS | filed 2026-10-04 — workaround is a server flag | **code** — chat template in the GGUF; no `reasoning_effort` on the llama.cpp path |
| 61 | Web cache — review how it is cleaned, used and scoped | S4 | M | open — **scope only**, filed 2026-10-05 | none yet |
| 62 | A document open in one chat moves into whichever chat you send from next — "New Chat" closes the panel but leaves the document current, and the server rebinds it | S2 | XS | **browser half (b) `82892264`, verified live 01:30 · server half (a) `6a313dd8`** — a document named from another chat is used for the turn and not moved; Pink Oyster restored 01:43 | **live** — doc `68647d12` moved twice in 8 min (23:31, 23:38); 11 moves in the logs since 07-14 · **code** — `closePanel()` keeps `activeDocId` · **tests (7)** source checks, 6 mutations · **live** — console: `getCurrentDocId()` `7a9e32ce…` → New Chat → `[doc-save] … stamp=7a9e32ce… len=252` → `null` |
| 63 | Changes to what the model is told are not measured — adopt SkillOpt's validation-gated edit loop | S4 | M | filed 2026-10-07 — **design only**; item 20 first | none yet |
| 64 | Decisions waiting for the maintainer's approval (lints, closable items, diagnostics, 32k model, …) | — | XS | filed 2026-10-07 — **11 decisions listed**, each with evidence and a recommendation | n/a |
| 68 | A turn that claims an action and called no tool is saved as if it happened — *"Created 'Switch check' document"*, no document | S1 | S | filed 2026-10-07 20:40 — **seen live once**, guard not built | **live** — session `0ca639d6` 20:38:55: `0 native calls, 0 tool blocks`; no such document in `app.db` |

**28 open as of 2026-10-08**; the 40 closed or retired rows are indexed at the top of [resolvedissues.md](resolvedissues.md). **Numbers are never reused** — a closed item keeps its number in that index, and new items continue after the highest number in either table. Renumbering has silently rotted cross-references four times (see *Notes & constraints*); item 2 split into 2a/2b, and 9 into 9/9b, rather than taking new numbers, for the same reason.

> ⚠️ **Item 23 changes how item 8's evidence should be read**, and the pair is reciprocal (#8↔#23) so neither can be renumbered quietly. A turn that reports *"stopped without producing an answer"* may have produced one — in the reasoning channel. **Compare `thinking` against `content` before filing another item 8.**

## Next

The current plan is the ➡️ **Next** line of the newest [session-log.md](session-log.md) entry.

**Next session:** commit item 7's fix after the M1 suite (handed over 2026-10-08), restart Odysseus; then the remaining bullets below.

- **Rule adherence at temp 0.6** — re-run item 20's five-run protocol once item 43's preset is fixed (2026-10-08 reading: 3 of 5 at temp 1.0).
- **Item 27 (c)** — (a) and (b) are verified live.
- **Item 3's prevention gap** — `update_document` bypasses the stale-value lint.
- **`_send_email_sync`** (`routes/email_routes.py`) — **checked 2026-10-08: dead upstream code.** Zero callers (`grep -rn _send_email_sync`); `/send` and scheduled delivery have their own send paths. Scheduled delivery exists (`_scheduled_email_poller`, `routes/email_pollers.py`) and is owner-scoped: rows carry `owner` (the schedule route writes it from `require_owner`), and the poller passes it to `_get_email_config`. The only unscoped case is a legacy row with neither owner nor account (there are 0 rows, and no email accounts). Also dead: `status='agent_draft'` rows. The list/approve/cancel routes exist, but nothing inserts one (the setting in `src/settings.py:41` describes a writer that is not there). **Upstream issue candidate** (item 64): delete `_send_email_sync`, or wire it in and drop the misleading docstring.

---

## S1 — wrong output the user trusts

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

### 34. An aborted document stream orphans its placeholder as `activeDocId`
**Found 2026-07-31, from the maintainer noticing a *"failed background stream"* message and asking whether it was related.** It is — this is the clearest *source* of the unstamped-buffer state items 30 and 31 have been chasing, and it arrives through a path neither item mentions. Reciprocal with #9b (same event, server side) and #30 (the state it produces).

→ Full record: [items/34-an-aborted-document-stream-orphans-its-placeholder.md](items/34-an-aborted-document-stream-orphans-its-placeholder.md)

### 8. The agent gathers information, then stops
Four attempts at one task in 16 minutes, **zero files produced**. 0b12aadb read 10,035 chars, correctly identified the embedded HTML page, ended its thinking with *"Let me write out the extracted content:"* — and emitted nothing.

→ Full record: [items/08-the-agent-gathers-information-then-stops.md](items/08-the-agent-gathers-information-then-stops.md)

### 27. A LAN address in the prompt deletes every document tool
*"create a document with temperature and humidity data from http://192.168.0.185"* produces no document, three times over. **The model never had the tool.**

→ Full record: [items/27-a-lan-address-in-the-prompt-deletes.md](items/27-a-lan-address-in-the-prompt-deletes.md)

### 14. Web search derails on ambiguous common nouns
Recurring, and **it feeds item 2b** — the wrong-species drift there is partly downstream of this. Run eb2d0ac1 returned **"Pink (singer) — Wikipedia"** as a top result for a pink-oyster cultivation query; an earlier run ranked a Victoria's Secret "PINK" page into the same searches. Nothing in the pipeline notices. The species name is in the document title and isn't being used.

→ Full record: [items/14-web-search-derails-on-ambiguous-common-nouns.md](items/14-web-search-derails-on-ambiguous-common-nouns.md)

### 20. A 116-line block of agent rules has never reached a model
`src/agent_loop.py` assigns **`_AGENT_RULES` twice** — the detailed block first, an 851-character "## Base rules" second — so Python keeps the second and the first is dead. `_API_AGENT_RULES` is shadowed the same way. The module imports, the suite is green, and the block reads as live to anyone grepping the file.

→ Full record: [items/20-a-116-line-block-of-agent-rules.md](items/20-a-116-line-block-of-agent-rules.md)

## S4 — friction and blocked diagnosis

### 12. Wasted verification rounds
9B sometimes runs `manage_documents` "to check" after creating a doc (~47 s for nothing). Run 27a94a01 did exactly this.

- ⚠️ **The prompt line against it exists and has never reached the model** (item 20). **This item has only ever been observed with the rule absent**, so "the model ignores it" is not established. Re-measure before building anything in the loop.

### 13. Terminal access-log noise
→ Full record: [items/13-terminal-access-log-noise.md](items/13-terminal-access-log-noise.md)

### 25. A path-confinement test passes without the mechanism it tests
`tests/test_tool_path_confinement.py::test_extra_roots_opt_in` builds its fixture under `tmp_path`, patches `tool_path_extra_roots` to include it, and asserts the path resolves. **It resolves either way.** `_tool_path_roots()` already contains `/tmp` and `$TMPDIR` (`src/tool_execution.py`, the `# $TMPDIR — per-user temp root on macOS` block), and `tmp_path` lives in one or the other on both platforms. The patch is decoration; there is no negative control asserting rejection *without* the opt-in.

- ✅ **Confirmed on the M1, 2026-07-29.** With the mechanism removed — `return_value=[]` in place of `[str(extra_dir)]` at line ~205 — the file still reports **`25 passed`**. The test does not depend on the setting it is named after.
- **Measured, not read.** Importing the real `src.tool_execution` with `DATABASE_URL=sqlite:///:memory:` and calling `_resolve_tool_path` on a `tmp_path`-shaped location resolved it **with no patch applied**. The mirror-image control passed too: the same probe against a repo-root location was `REJECTED` without the extra root and `ALLOWED` with it. *(Those two ran in a Linux sandbox with a faked `TMPDIR`; the macOS run above is what settles it.)*
- **This is item 16's shape and the pair is reciprocal (#16↔#25).** There it was a security assertion pointed at an orphaned function; here it is a security assertion that holds regardless of the mechanism. **Both were green throughout.** The difference worth keeping: item 16's was found by reading callers, this one only by *running* the function.
- **Fix is a negative control, not a rewrite:** assert the same path is rejected when `tool_path_extra_roots` is empty. That is the assertion the test's own docstring already claims to make.
- ⚠️ **Do not "fix" it by moving the fixture out of `tmp_path` without checking the roots list first** — see item 26, where the same coupling runs the other way.
- ✅ **Fixed 2026-10-04 (night), commit `b9616240`.** The fixture is now a path under the filesystem root (`/odysseus-extra-root-<uuid>/file.txt`), outside every default root and **never created** — `_resolve_tool_path` works on the realpath and does not need the file, so nothing is written outside `tmp_path` (the item 26 coupling above). The test asserts *rejected* with `tool_path_extra_roots=[]`, then *allowed* with it. Mutations: the item's own (`return_value=[]` in the opt-in patch) → **fails** (was `25 passed`); `_tool_path_roots` ignoring the setting → fails; containment accepting everything → fails along with 6 others. **M1 suite owed** — macOS's `$TMPDIR` is under `/var/folders`, which this path is also outside.

### 40. Round 1 of every turn re-prefills the whole prompt
**Measured 2026-08-01 over 275 rounds in `app.log`.** Round 1 is **4–8× slower than a later round at the same prompt size** — not a normalisation artefact, this is absolute time at matched buckets:

→ Full record: [items/40-round-1-of-every-turn-re-prefills.md](items/40-round-1-of-every-turn-re-prefills.md)

### 42. Sessions pin the model tag per row; a tag Ollama no longer serves does not fall back
**Filed 2026-08-01 from re-checking *"the 64k switch is live and measured"* — true, and narrower than it reads: it was verified on one of only two sessions then on the new tag.**

→ Full record: [items/42-sessions-pin-the-model-tag-per-row.md](items/42-sessions-pin-the-model-tag-per-row.md)

### 43. `max_tokens=0, temp=1.0` arrives whenever a request carries no preset
> ✅ **Value corrected and verified live the same day: `Preset custom: temp=0.6, max_tokens=8192` at 2026-08-01 09:54:12.** The row stays open because **setting a slider does not stop it drifting**, and because the mechanism turned out not to be the one [qwensetup.md](qwensetup.md) has described since July.
>
> ❌ **CORRECTION — it is not "the custom preset resets".** `Preset None: temp=1.0, max_tokens=0` was caught in the act at **09:51:31**, one turn before the fix. `temp=1.0` and `max_tokens=0` are **`DEFAULT_TEMPERATURE` and `DEFAULT_MAX_TOKENS`, `src/constants.py:109-110`** *(grep the names, not the numbers)*. `validate_and_extract_preset` seeds both from those constants and only overwrites them inside `if preset_id and preset_id in self.preset_manager.presets` — so **the log line says the request arrived with NO `preset_id`, not that a stored preset was reset.** Nothing was overwritten; nothing needs re-checking in the preset itself. **The fix is on the client that omits it, or in the defaults — a different change from "re-check the slider", which is what qwensetup has been telling every session to do.**
> - **It is common, not an edge case:** `Preset None:` **164** times against `Preset custom:` **296** across both logs — roughly **36 % of turns carry no preset at all** and run at temp 1.0 with an unset cap. ⚠️ *That 36 % is a count of log lines, not of distinct turns; treat it as an order of magnitude.*
> - ⚠️ **What `max_tokens=0` does on the wire is NOT established.** It plainly does not mean "generate nothing" — the 09:51 turn produced 54 characters and a tool call on that setting. Whether it is omitted from the request or sent as a literal `0` is one read of the payload builder away and nobody has done it.
> - ⚠️ **Suggestive and NOT a finding, n=1 with three variables moved at once.** The `temp=1.0 / max_tokens=0` turn ended with `text_chars=0 tool_calls=0` on round 2 and needed the synthesized closing line; the `0.6 / 8192` turn wrote **263 characters** of real closing summary. Its visible message also ran reasoning and answer together with no separator (*"…with this tool.I'll create a brief document…"*), which is item 6/23's shape. **Model, context window and preset all changed between the two turns** — this is precisely the confound the bullet at the foot of this item warned about, hit on the first run after it was written. **Do not fold it into item 23 without a controlled pair.**

> 🔎 **2026-10-08 — now on 100 % of turns, and two causes found (code read plus live state; no fix made).** Per day in `app.log*`: `Preset custom` in most turns until 10-02; since **10-04, 0 `custom` against 182 `None`**. (1) **State:** `data/presets.json` was last written 2026-10-04 19:43 and its `custom` entry is now `enabled: false, temperature: 1.0, max_tokens: 4352`. With `enabled: false` the browser never selects it, so every request goes without `preset_id` and gets `DEFAULT_TEMPERATURE` / `DEFAULT_MAX_TOKENS`. Who disabled it is not in the log (preset saves are not logged). (2) **Code (upstream, `static/js/presets.js`, `loadPresets`):** on page load the custom preset is selected only if it has a `character_name` or `system_prompt`. The save path also selects it for tuning alone (`_hasTuning`: temperature ≠ 1.0 or max_tokens ≠ 0) or for inject text. So **a preset that only sets temperature and max tokens is dropped on every reload** until it is saved again — the likely source of the earlier ~36 %. **Maintainer's call:** re-enable the custom preset at 0.6 / 8192 (qwensetup) and decide whether to fix the load path (one condition). Everything tested on 10-04 to 10-08 ran at temp 1.0.
> 🔧 **Fixed 2026-10-08 10:55 (uncommitted, live via reload):** custom preset re-enabled at **0.6 / 8192** (`POST /api/presets/custom`, maintainer's go-ahead), and `loadPresets` now also auto-selects a tuning-only or inject-only preset. Verified live: after a reload `getSelectedPreset()` is `custom`, and all eleven requests since 10:56:26 logged `Preset custom: temp=0.6, max_tokens=8192`. Note: for Qwen 3.5 in thinking mode, Qwen recommends **1.0** for general tasks (presence_penalty 1.5) and **0.6** for precise or coding work (unsloth.ai, *Qwen3.5*); 0.6 is the deliberate choice for tool use. Odysseus sends only temperature and max_tokens on the agent path, so top_p/top_k/presence_penalty come from LM Studio's per-model *Inference* settings (Bonsai: the `start_bonsai2.sh` flags). **Close after the commit, and once a reload made by you shows `custom`.**

**Originally filed 2026-08-01 as *"the sampling preset drifted to `max_tokens=4352`"*, split out of item 41's third bullet, which recorded the spread and not the trend.**

### 45. The server injects a document the user never named, and closing the editor does not stop it
→ Full record: [items/45-the-server-injects-a-document-the-user.md](items/45-the-server-injects-a-document-the-user.md)

### 47. "today"/"latest" routes `web_search` to the news category, which here is mostly Bing News
**Measured 2026-10-02 from `app.log` and `web_sources`.** `services/search/providers.py` switches to `categories=news` whenever the query contains a `_NEWS_HINTS` word (`news`, `latest`, `today`, …) or a `time_filter` is set, and pins only `language=en` (no region). On this instance the news category was effectively one engine: every gold/silver query containing "today" came back **5 of 5 `bing news`**, while the same question without "today" came from `google cse` (goldprice.org, kitco, tradingeconomics). Since 2026-08-01, **all 5 India-domain sources in `web_sources` came from `bing news`, 0 of 70 `google cse` results did.**

- **Mechanism, two parts:** a price lookup is not a news question, and `en` without a region lets Bing mix every English edition — India's financial press dominates bullion coverage.
- **Mitigated, not fixed:** 2026-10-02 the SearXNG news set was widened (reuters, wikinews, mojeek news, qwant news alongside bing news); a test query then returned four news engines instead of one. That file is gitignored — see [qwensetup.md](qwensetup.md), *Web search*.
- **Fix candidates, cheapest first:** (a) route to news only on explicit news words, not `today`/`latest`; (b) a configurable region (`en-GB`, `de-DE`) instead of a bare `en`; (c) a relevance filter dropping results with none of the query's distinctive terms, with the unfiltered list as fallback — **measure (c) against the recorded `web_sources` corpus before shipping**, per [`CLAUDE.md`](../CLAUDE.md) §3.
- **Upstream of this and of item 14:** the free engines rate-limit this IP. Within hours on 2026-10-02 SearXNG logged CAPTCHA / *too many requests* for DuckDuckGo, Google CSE, Brave, Qwant and Google News (`searxng/searxng.log`), so whatever still answers dominates. **The durable fix is an API-keyed provider** — Tavily's free tier (1,000 searches/month, no card) is already supported in Settings → Search. If switched, put `searxng` in `search_fallback_chain` (today `["duckduckgo"]`, which is CAPTCHA-blocked) and set `research_search_provider` explicitly so deep research does not spend the monthly quota.

### 48. The context popup's "used" figure is the turn's summed input tokens
**Seen 2026-10-04 (screenshot, session "Parasol Mushroom Websearch"):** the popup read *"39,672 used / 65,536 total"* beside a bar and a label of **12.7 %**. 39,672 / 65,536 would be 60.5 %. `static/js/chatRenderer.js` drew the bar from `context_percent` (derived from `request_context_tokens`, the last request) but printed `metrics.input_tokens` — **the sum across every round of an agent turn**, the same trap [`CLAUDE.md`](../CLAUDE.md) §1 records for the database. **Fix:** print `request_context_tokens`, falling back to `input_tokens` for rows that lack it. ⚠️ **Unverified** — there is no JS harness; `node --check` passes. **Manual check:** hard-reload Odysseus (Cmd+Shift+R), run a multi-round agent turn, click the ring — the "used" figure ÷ the window should match the percentage.

- **The 10-04 fix was half right — checked live 2026-10-08.** Three writers set `context_percent`: `_build_metrics` from `request_context_tokens` (Odysseus's estimate), then `stream_agent_loop` overwrites it with the **last usage bucket's real `input_tokens`** whenever the provider reported usage, then `routes/chat_routes.py` can overwrite it from `input_tokens`. The popup printed `request_context_tokens`, so *used ÷ window* disagreed with the percentage on every row that has `usage_buckets` (the estimate runs 0.5–1.3× the real count). **Fixed (uncommitted):** the popup prints the last bucket's `input_tokens`, falling back to `request_context_tokens`, then `input_tokens`. Checked mechanically on a copy of `app.db`: 56/56 rows with buckets now match within 0.15 points (0/56 before); 215 rows without buckets match either way; 65 older rows without buckets mismatch either way — their percentage came from a writer this change does not touch. **Close after the commit.**

### 50. LM Studio's loaded context is invisible to Odysseus, so a long turn outgrows it
→ Full record: [items/50-lm-studio-s-loaded-context-is-invisible.md](items/50-lm-studio-s-loaded-context-is-invisible.md)

### 52. Odysseus's own notices are replayed to the model as its words
**Found 2026-10-04 while looking at why models "remember" earlier greetings (sessions `0829a3d2` *"oh"*, `717636da` *"hi mark"*).** The end-of-turn guards in `src/agent_loop.py` append notices to the saved reply — `_empty_response_fallback`'s *"The model returned an empty response…"*, `_stream_failure_notice`, `_gathering_only_notice`, `_unstarted_promise_notice`, `_tool_payload_as_text_notice`. `Session.get_context_messages` replayed them to the model verbatim on every later turn.

→ Full record: [items/52-odysseus-s-own-notices-are-replayed-to.md](items/52-odysseus-s-own-notices-are-replayed-to.md)

### 53. Context blocks go to the model as extra user turns at the start of the chat
**Found 2026-10-04 alongside item 52. Design only — nothing built.**

→ Full record: [items/53-context-blocks-go-to-the-model-as.md](items/53-context-blocks-go-to-the-model-as.md)

### 54. "New Chat" sent the next message into the previously open chat
**Reported 2026-10-04 by the maintainer** (*"i'm clicking new chat each time and it opens the front page. at first it doesn't even show it's the same chat"*), **reproduced and fixed the same evening.**

→ Full record: [items/54-new-chat-sent-the-next-message-into.md](items/54-new-chat-sent-the-next-message-into.md)

### 55. `trigger_research` reports success when the research model is down
**Seen 2026-10-04 20:00:12, session `cdb89980` (Bonsai 2).** The tool returned *"Deep research started: […](#research-rp-1249e3b0d61e)"* (`exit_code=0`); 8 ms later `src/research_handler` logged `Probe failed for qwen/qwen3.5-9b: 503: Cannot reach http://localhost:1234` and `Background research failed`. The model was told the research was running and planned around it; the user saw an *"Open in Deep Research"* link to a run that never started.
- **Why it happens:** research runs on the configured `research_model` (`a5179555`, LM Studio), independent of the chat model, and the probe happens after the tool has already answered.
- **Fix candidates:** probe the research endpoint before returning from `trigger_research` (it is a local call, cheap) and return an error the model can act on; or fall back to the chat model when the research model is unreachable. **Observable:** with LM Studio stopped, `trigger_research` returns `exit_code≠0` with the reason.
- 🔧 **Fixed 2026-10-04 (night), commit `0c71f29e`** — the first candidate. `do_trigger_research` sends `wait_for_probe: true`; `/api/research/start` then awaits `ResearchHandler.wait_until_started()` (≤ 20 s; `probe_ok` is set on the task entry once `_probe_endpoint` passes, `status=error` when it fails). A failed probe comes back as `exit_code=1`: *"Deep research did NOT start: <reason> … offer to look it up with web_search instead"*. A probe still running at 20 s returns *started* with a note. The research panel does not send the flag, so its response is unchanged. `tests/test_trigger_research_probe.py` (8); mutations caught: flag not sent, error status ignored by the tool, `probe_ok` never set. **Live check:** quit LM Studio, ask for deep research → tool result `exit_code=1` naming `localhost:1234`, no *Open in Deep Research* link.
- ✅ **Verified live 2026-10-04 23:24, session `cf7e2281` (Bonsai 2, LM Studio down):** *"can u launch a deep research about dragonflies?"* → `trigger_research` → probe failed at 23:24:40,030 → `/api/research/start` answered at 40,093 → tool `exit_code=1`. The reply: *"The deep research job couldn't start — the research backend model (qwen/qwen3.5-9b on localhost:1234) isn't running… Want me to do a web search on dragonflies instead?"* No research link. ⚠️ **One wart:** item 11's failure footer quotes the tool error verbatim, so the user also sees *"…configured separately f…"*, text written for the model (its *"Tell the user; offer web_search"* tail is cut by the footer's truncation). Cosmetic; the fix would be to keep the model-facing advice out of `error`. Also seen: *"launch"* classified the turn as `cookbook`, so 4 Cookbook tools went out (`tail_serve_output` was sent) — item 57's territory.

### 57. A different tool set per message defeats prompt caching on local servers
**From session `cdb89980` (Bonsai 2 on PrismML llama.cpp), 2026-10-04.** Tool RAG sent 6, then 8, then 7 tools on three consecutive messages. Qwen-family templates render the tool schemas in the system block, ahead of the history, so any change in the set changes the prompt prefix and the server re-reads the entire conversation. At Bonsai's ~70 tok/s prefill a 3–4k-token chat costs 42–61 s before the first token on every message. Within one turn the set is fixed, so rounds 2+ do reuse the cache.
- **Related, not the same:** item 53 (context blocks at the start of the chat change per message too).
- ✅ **Template confirmed 2026-10-04:** the Bonsai 2 chat template (read from the GGUF's `tokenizer.chat_template`, 8,952 chars) emits `<|im_start|>system` → reasoning instruction → `# Tools … <tools>` (one JSON line per tool, in request order) → then the system message → then the history. So the tool list, *and its order*, sit ahead of everything else. Qwen 3.5's template has the same shape.
- **Fix candidates:** for local endpoints, keep the tool set stable across a session (union of sets so far, or a fixed core set plus on-demand additions); or render rarely-changing tools first. **Observable:** llama-server `cache_n` on a follow-up message ≈ the previous prompt length.

### 58. Each tool round deletes earlier rounds' thinking, breaking the prompt prefix
**Found 2026-10-04 reading the Bonsai 2 chat template against `src/agent_loop.py`. Hypothesis — fits the timings, not measured.**

→ Full record: [items/58-each-tool-round-deletes-earlier-rounds-thinking.md](items/58-each-tool-round-deletes-earlier-rounds-thinking.md)

### 59. `reasoning_effort` never reaches llama.cpp endpoints
**From the Bonsai 2 chat template, 2026-10-04.** The template accepts `reasoning_effort` ∈ {`xhigh` (default), `medium`, `low`}: `xhigh` prepends *"Reasoning effort is set to xhigh. Please think carefully through the task, validate key assumptions…"* to the system block, `medium` adds nothing, `low` asks for brief thinking (PrismML: *"`low` … will behave close to `xhigh`"*, i.e. not effective). PrismML recommends `medium` for API clients: *"thinks noticeably less than the default `xhigh` at about the same accuracy"*. Odysseus sends `reasoning_effort` only on Ollama / Mistral / OpenAI paths (`src/llm_core.py`), never `chat_template_kwargs`, so every Bonsai 2 turn thinks at `xhigh` — the largest share of its wait on an M1 Pro (~12 tok/s decode).
- **Workaround, no code:** server-wide default `--chat-template-kwargs '{"reasoning_effort":"medium"}'` on the llama-server command line.
- **Fix candidate:** a per-endpoint `reasoning_effort` (or `chat_template_kwargs`) setting sent on llama.cpp endpoints — same missing-UI shape as item 46.
- **Observable:** thinking length (`output_tokens` minus visible text) on the same prompt, `xhigh` vs `medium`.

### 61. Web cache — review how it is cleaned, used and scoped
**Filed 2026-10-05 at the maintainer's request, after a walkthrough of the cache. Scope only — nothing below is a verified finding.**

- **Parts:** page cache `data/cache/content/` (`fetch_webpage_content` in `services/search/content.py`, 2 h); search-results cache `data/cache/search/` (`searxng_search_results` in `services/search/core.py`); cleanup / LRU (`cleanup_cache` in `services/search/cache.py`); failed-URL memory (in-process `_negative_cache` in `content.py`, 30 min).
- **Open questions:**
  - Are cache files from earlier runs ever removed, and what bounds the folder?
  - Is the search-results cache reached by any live path?
  - How should "Nobody" (incognito) chats interact with the cache and with `app.log`?
  - Should failed extractions be cached?
  - How often does a turn read the same page more than once, and what does that cost in prompt tokens?
- **How to check:** against copies of `data/cache/` and `app.db`, never the live tree (see *"`web_fetch` — what it sees"* in [qwensetup.md](qwensetup.md)). Decide per question before building anything.

### 62. A document open in one chat moves into whichever chat you send from next
→ Full record: [items/62-a-document-open-in-one-chat-moves.md](items/62-a-document-open-in-one-chat-moves.md)

### 68. A turn that claims an action and called no tool is saved as if it happened
**Seen live 2026-10-07 20:38** (Qwen 3.5 9B on LM Studio, session `0ca639d6`): *"Create a second document titled 'Switch check' with the text 'hello'."* Its thinking planned *"I'll use create_document with title='Switch check' …"*; the round ended `text_chars=58 tool_calls=0 finish_reason=stop`, and the reply was *"Created **"Switch check"** document with the text "hello"."* — **no tool ran and no such document exists** (copy of `app.db`).

- **Why no guard fired:** the zero-tool guards in `src/turn_report.py` cover a lead-in that trails off (`_unstarted_promise_notice`) and a tool payload written as text (`_tool_payload_as_text_notice`). A finished-sounding claim in the past tense ("Created …", "Updated …", "Sent …") with zero tool calls matches neither. `_API_AGENT_RULES` already says *"do not claim you did something without a tool result"*; the model ignored it.
- **Candidate guard (report-only, CLAUDE.md §3):** on a turn with zero tool events, flag a reply that asserts a completed side effect — lexical match on the claim verb plus an object the tools create (document, note, event, file, email). Needs negative controls (an explanation, a quote, an answer *about* a past action) and a sweep of the recorded corpus before it ships.
- **Benchmark:** a candidate check for item 63's task set — a task where the correct turn calls `create_document`, scored on the document existing, not on the reply.
- **Relation:** the mirror image of item 65, where a tool *did* run (to an approval card) and the report claimed more than happened.

### 63. Changes to what the model is told are not measured — adopt SkillOpt's validation-gated edit loop
One bounded edit to the agent rules at a time, kept only if held-out benchmark tasks improve; built on `scripts/bench_agent.py`. Item 20 first.

→ Full record: [items/63-prompt-changes-are-not-measured.md](items/63-prompt-changes-are-not-measured.md)

### 64. Decisions waiting for the maintainer's approval
A parking list: keep or remove the document lints, close five built-and-verified items, the temporary document diagnostics, the Ollama 32k model, `qwensetup.md`, skills and the approval gate, the test fast lane, upstreaming fixes, housekeeping. Decide an entry → record it where it belongs and delete it there.

→ Full record: [items/64-decisions-waiting-for-approval.md](items/64-decisions-waiting-for-approval.md)

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
