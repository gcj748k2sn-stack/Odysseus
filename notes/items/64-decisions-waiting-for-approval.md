# 64. Decisions waiting for the maintainer's approval

Open item, filed 2026-10-07. A parking list, not a defect: each entry is a choice that needs the maintainer, with the evidence and a recommendation. Its row in the [todo.md](../todo.md) index carries the status. **When an entry is decided, record the decision in the item it belongs to (or in resolvedissues.md) and delete it here.**

---

## 1. Keep or remove the two document lints — `known_facts` and `document_fidelity` (items 2a, 2b)

- **What:** `src/known_facts.py` + `config/known_facts.json` check generated documents against recorded pink-oyster cultivation facts; `src/document_fidelity.py` + `config/field_semantics.json` check a document against the data it was built from. Report-only; ~890 lines with tests for known_facts.
- **Evidence (2026-10-07):** 36 known-facts warnings in `app.log*`, all 2026-07-28…31, none since. Fidelity: never seen firing live. Of 86 documents created in July, 56 were about pink oyster; of 16 created in August and October, none. 0 check errors in any log. Cost ≈ 2.4 ms per document tool call on an oyster document, ≈ 0.2 ms on anything else.
- **Options:** keep both · remove both (one call site in `src/turn_report.py`, two modules, two configs, four test files, fixtures). They stand or fall together.
- **Recommendation: keep.** Dormant, not obsolete; practically free; isolated in fork modules since 2026-10-07; and they are the deterministic trigger for the planned benchmark checks of items 21 and 2a. Add a subject only after a real failure.

## 2. Close items that are built and verified

Open by this file's convention (title not struck), but their status says done:
- **25** — fixed `b9616240`; the owed M1 suite has since passed several times (7,441 passed on 2026-10-07).
- **52** — built `c084b9e3`, live check passed 2026-10-06 00:31.
- **54** — fixed `c29a068a`, verified live in the pane and in Safari.
- **55** — fixed `0c71f29e`, verified live 2026-10-04 23:24.
- **13** — both halves built and seen live; tests (15).

Not yet: **46, 48, 56** each still owe a manual UI check; **60** has the bash hole seen live after the merge.
- **Recommendation:** close the five, moving each conclusion to resolvedissues.md (CLAUDE.md §5).

## 3. The closing report flags tool failures the model already recovered from

- **What:** `_side_effect_tool_summary` in `src/turn_report.py` appends *"⚠️ `python` failed — …"* for any failed side-effecting tool, even when the model retried and succeeded later in the turn. Seen in the 2026-10-07 Qwen benchmark (`json_output`); the benchmark now scores without the report.
- **Options:** keep (every failure reported, by design — a confident summary must not bury one) · report only failures not followed by a successful call of the same tool · keep them but phrase recovered ones as such.
- **Recommendation:** the third — same honesty, less noise. Needs a decision on what counts as "recovered".

## 4. The temporary document diagnostics still in `static/js/document.js`

- **What:** `_stackFrames` ("remove once the paths are named") and the `switchAway` trace (remove when the 30–35 cluster is done; item 34 still open). Plus `[doc-put-404]` in `routes/document/document_routes.py` for item 34.
- **Evidence:** item 34's last measurement, 2026-08-01: 0 spontaneous `[doc-put-404]` in 7 document stream opens — "too small to close". Nobody has worked on naming the paths since.
- **Options:** close item 34 as bounded by the 404 reaper and remove all three · keep measuring.
- **Recommendation:** count `[doc-put-404]` in `app.log*` since 2026-08-01 first; if still zero, close 34 and remove them.

## 5. The Ollama 32k model files

- **What:** `models/qwen3.5-9b-32k.Modelfile` and `models/make-qwen3.5-9b-32k.sh` build `qwen3.5:9b-32k`, kept 2026-07-31 as the fallback "until 64k has run a week". The fallback has been `qwen3.5:9b-64k` since, and chat moved to LM Studio on 2026-10-02.
- **Check first:** whether any session row still pins the 32k tag (item 42 — a pinned tag Ollama no longer serves does not fall back).
- **Recommendation:** if none does, delete the two files and the Ollama tag.

## 6. `qwensetup.md` — trim the history?

- **What:** 45 KB; current setup and July history are interleaved bullet by bullet, so it could not be archived mechanically on 2026-10-07. It is not on the default read path.
- **Recommendation:** low priority. Only worth doing if a session is misled by a stale bullet.

## 7. Skills arm the untrusted-context gate on every turn

- **What:** since the 2026-10-06 merge, the skills index enters the prompt through `untrusted_context_message("skills", …)`, so any saved skill makes every write, edit or bash call need an approval click (notes/merge-upstream-2026-10-06.md). `data/skills/` is empty on this machine today, so it does not bite yet.
- **Options:** keep upstream's policy · pass `arm_tool_gate=False` for the skills message and accept that a poisoned skill could steer tools unprompted.
- **Recommendation:** keep upstream's policy; decide again only when skills are back in use.
- **Related, decided 2026-10-07 22:48 (maintainer: "do two"):** the user's own **memories** and **documents** no longer arm the gate — `src/user_content_trust.py`; record in [session-log.md](../session-log.md), 2026-10-07 21:20 entry. Skills are untouched by that change.

## 8. Test fast lane on the M1

- **What:** `pytest-xdist` is not in the M1 venv, so every run is single-process (~3 min). `-n 4 -m "not slow"` passed cleanly on Linux.
- **Command:** `/Users/cedrik/odysseus/venv/bin/python -m pip install pytest-xdist`, then `./venv/bin/python -m pytest -n 4 -m "not slow" -q` while working; a plain full run before "done" (CLAUDE.md §4).
- **Recommendation:** install.

## 9. Offer the fork's generic fixes upstream

- **What:** several fork fixes would help any Odysseus user and, once taken upstream, leave the fork's diff: document data-loss fixes (closing a tab, the editor-buffer flush, tidy archives instead of deleting), the `chat.js` ReferenceErrors, `<main>` extraction for Wikipedia, the negative cache for permanently failing URLs, LM Studio context discovery, `trigger_research` reporting a dead model.
- **How:** upstream's CONTRIBUTING asks agents to open an issue first, not a PR.
- **Recommendation:** worth it for the document data-loss fixes first; each accepted one shrinks every future merge.

## 10. Small housekeeping

- **`.env.bak.before-lmstudio`** (2026-08-07) in the repo root: a copy of secrets, gitignored but readable by the agent's bash, which runs from the repo root. Move it out of the repo.
- **`scripts/bench_agent_tasks.py`** keeps a hand-copied `WEB_INTENT_RE`; a five-line test comparing it with `routes/chat_routes.py` would catch drift.
- **`tests/test_static_js_block_scope.py`** is a 576-line hand-written JS scanner; ESLint `no-undef` would do the same with a real parser, at the cost of an npm devDependency and a globals list. Optional.

## 11. Live test of the AI document tidy's archive branch (item 44) — parked 2026-10-08

**Maintainer: not relevant for now; keep for later.** It blocks nothing: the AI tidy (`POST /api/documents/ai-tidy`) runs **only** when someone clicks *Tidy* in the Library (`static/js/documentLibrary.js`, phase 2 after the regex tidy). The scheduled *Documents Tidy* task (`action_tidy_documents` → `src/document_actions.run_document_tidy`) makes no model call. What stays unverified: the branch that archives a document on a `junk` verdict has never run live, and verdict quality is unmeasured (one run: all `keep`; an earlier unsuppressed run: mostly `junk`). **Until then, the Library's *Tidy* button runs that unobserved branch on real documents** — archiving is reversible, but worth knowing. When picked up: a batch of throwaway junk documents (empty, `asdf`, three identical copies) next to real ones, then check that only the junk is archived; or test the parser and the archive step against a copy of `app.db` first. Record in resolvedissues.md under item 44.


## 12. Shorter tool descriptions for local models — parked 2026-10-08

**Reviewed and judged not worth the code yet.** Bonsai's template puts every tool schema as JSON at the start of the prompt (read from the GGUF's `tokenizer.chat_template`), so descriptions are read in full on every uncached round. Measured in chat `01492028`: real prompt 3,711–4,745 tokens (Odysseus's own `prompt_tokens` estimate, ~2,000, leaves out the schemas), prefill ~62 tok/s.

- **Gain:** `ask_user` + `update_plan` trimmed ≈ 830 chars ≈ 240 tokens ≈ **4 s per uncached round** (first message of a chat, or a message that widens the sticky tool set). `ui_control` ≈ 2,140 chars ≈ 10 s, only when it is selected.
- **Cost:** a fork module holding a second copy of these descriptions that has to follow upstream changes; behaviour of `ui_control`/`update_plan` is not covered by the benchmark (0 calls in ~170 task runs), so it needs a manual three-prompt check (open notes panel, create a theme, tick a plan step).
- **Cheaper first:** switch off tools that are never used by chat (Settings → Agent Tools). `manage_mcp` rode along on every message of the test chat (retrieval noise kept by sticky tools) and alone is ~850 chars.
- **Rejected variant:** send `update_plan` only while a plan is active — the app sends `approved_plan` only with the first message after approval (`static/js/chat.js`), so later "change the plan" requests would lose the tool.
- **If revived:** draft at the maintainer's request in the 2026-10-08 session; wire at the per-candidate send site (`agent_loop.py` ~5100, `candidate_url`) so remote fallbacks keep the full text; keep `ask_user`'s "only when you cannot proceed well without the answer".
