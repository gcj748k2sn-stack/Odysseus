# 40. Round 1 of every turn re-prefills the whole prompt

Open item, moved here from `notes/todo.md` on 2026-10-07 so the dashboard stays short. Its row in the [todo.md](../todo.md) index carries the current status; this file is the full record.

---

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

- ❌ **Cold model load.** Round-1 rate by idle gap since the previous round: **7.08 / 8.22 / 8.56 s per 1k tokens** for `<1 min` / `1–5 min` / `>5 min` (n=34/34/31). Flat. A round starting one minute after the last pays the same as one starting fifteen minutes after. **This also settles that `OLLAMA_KEEP_ALIVE` is not a latency problem** — see [qwensetup.md](../qwensetup.md).
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
  - 🆕 **The fixed component is new, it is the part with no explanation, and it is MODEL-SIDE.** Least squares over **n=121** round-1 observations, prompts 3,260–12,671 tokens:

    ```
    round 1     n=121    18.0 s fixed + 5.53 s/1k tok
    rounds 2+   n=232             …   + 3.17 s/1k tok     (median 19.6 s at 11,573 tok
                                                           vs round 1's 59.8 s at 8,064)
    ```

    ⚠️ **The rounds-2+ intercept is not quoted because it fits to −11 s** — an extrapolation artifact, the data starts at 4,102 tokens. **The slopes and the medians are the result**; the intercept is not.
  - ✅ **`prep` is 0.14 s median, 1.54 s max** (`tool_selection` 0.116, `context_trim` 0.016, `prompt_build` 0.002, `request_setup` 0.001). **So Odysseus contributes essentially nothing to the 18 s** — the median model-side wait is **59.2 s**. Whatever this is, it happens between `round_start` and the first byte.
  - **Two separable components, and only one is explained.** The **1.75× per-token difference** (5.53 vs 3.17) is exactly what "round 1 prefills the whole prompt, later rounds prefill the delta" predicts, and that half of this item stands. **The 18 s fixed term is not prefill** — it does not scale with tokens — and nothing in this item accounts for it.
  - ❌ **RETRACTED 2026-08-01, same day, by the server's own timings: the "18 s fixed" term is very likely a FITTING ARTIFACT, not a cost.** `/opt/homebrew/var/log/ollama.log` reports prompt eval at **4.39–5.55 ms/token (180–228 tok/s)** — a 26 % spread — and **essentially proportional, with no fixed component**: 57,210 ms / 12,139 tok, 58,985 ms / 12,455 tok, 17,196 ms / 3,921 tok. **Forcing one slope through a variable rate is what produces an intercept**, and 5.53 s/1k from the client fit sits at the slow end of the server's own range. **Nothing needs to explain 18 s, because there is probably no 18 s.** ⚠️ The client fit is not wrong, it is over-specified; quote the *rate*, not the intercept.

✅ **SERVER-SIDE CONFIRMATION 2026-08-01 — this item's core claim is no longer an inference.**

```
task 0    prompt eval  57210 ms / 12139 tokens     <- ENTIRE prompt
task 0    prompt eval  58985 ms / 12455 tokens     <- ENTIRE prompt
task 0    prompt eval  17196 ms /  3921 tokens     <- ENTIRE prompt
task 739  prompt eval   9927 ms /  1813 tokens     <- DELTA only
task 951  prompt eval  12336 ms /  2224 tokens     <- DELTA only
```

- 🔴 **`task 0` versus `task N` is the whole item.** A round arriving as **`task 0` prefills the entire prompt**; a continuing task prefills **only the delta**. **llama.cpp is telling us directly that the KV cache is not being reused between turns** — which this item had only ever inferred from client-side timings. **Round 1's cost is not a penalty, it is 12k tokens of prefill at ~210 tok/s.**
- ✅ **And it reconciles the client numbers:** server 57–59 s for a ~12k prompt against a client-side round-1 median of 59.8 s. **There is no meaningful queueing or HTTP gap** — the earlier "is it us or them" question is answered: **it is prefill, all of it.**
- ⚠️ **The pairing is by shape, not by turn.** No `task` id was matched to a specific `round_start`; the argument rests on token counts (12k = full prompt, 2k = delta) and on the rates agreeing. **Matching one turn end-to-end would close that gap** and is the only loose thread left in the measurement.
- **The question this item is now actually about: why does every turn open a NEW task instead of continuing the previous one?** The mid-array volatile blocks remain the leading answer — a prefix that diverges early cannot be reused — and the placement is deliberate, so **do not move it on the strength of the hypothesis.** ⚠️ `task 0` recurring (rather than an incrementing id) hints at slot *reset*, not merely a cache miss; those are different fixes and nothing has separated them.
  - ⚠️ **The "no document" arm is thinner than it looks — see item 45.** The frontend sends `active_doc_id=''` on 344 of 445 turns and the server injects one anyway via a session fallback, so *"no document"* here means *"no document the server could find"*, not *"no document open"*.
- ⚠️ **Do not "fix" the placement on the strength of the hypothesis.** It is deliberate — the doc message sits there so it stays close to the user's request and survives context trimming independently. Moving it trades model behaviour for latency, and this project has a record of shipping that trade backwards.
