# 14. Web search derails on ambiguous common nouns

Open item, moved here from `notes/todo.md` on 2026-10-07 so the dashboard stays short. Its row in the [todo.md](../todo.md) index carries the current status; this file is the full record.

---

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
