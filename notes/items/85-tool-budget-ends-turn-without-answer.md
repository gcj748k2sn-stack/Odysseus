# 85. The tool budget ends the turn without an answer

Open item, filed 2026-10-13. Its row in the [todo.md](../todo.md) index carries the current status; this file is the full record.

---

**What happens.** When a turn reaches `agent_max_tool_calls`, `stream_agent_loop` emits `budget_exceeded` and `break`s (`src/agent_loop.py`, the `if budget_hit: break` after the tool loop). The model never gets a round to use what it gathered, so the user sees only the turn report's *"I ran `web_fetch`, `web_search` and then stopped without producing an answer"* (item 8's reporting half). The loop-breaker in the same function already handles its own stop correctly: it sets `_force_answer`, appends a system message (*"write your best final answer NOW from the information already gathered, or … say plainly what's blocking you"*) and runs **one round with no tools**. The budget path does not.

**Evidence, 2026-10-13 benchmarks (Qwen 3.5 9B, LM Studio and Ollama).** At least 8 task runs ended `budget_exceeded` with no answer after 19–26 tool calls: webhard 08:52 (1), filter A/B rounds 1–3 (off 2, on 3), web phase Ollama (1), research (1, `res_gold2000`). Same tasks with and without the relevance filter, so the filter is not the cause. The searches were not empty: `bench_web_seen.py` shows `res_gold2000` was shown 295 mostly relevant results. Run dirs in [benchmark.md](../benchmark.md) *Results*. `agent_max_tool_calls` on the M1 not yet read (default 0 = unlimited, so it was set by hand).

**Not item 8.** Item 8 is the model stopping by itself after gathering; here Odysseus stops it. Item 8's history decides the design: its active half (*"finish the job NOW using the appropriate tool"*) was **reverted** after a retry wiped a 6,186-character document (*The agent gathers information, then stops*). Telling a model to act, with tools available, resolves to the most destructive call at hand.

## Plan

0. **Read the setting** (M1): `grep agent_max_tool_calls /Users/cedrik/odysseus/data/settings.json`. If the budget turns out to be the binding limit only in benchmarks, the fix still matters for real chats with the same setting.
1. **Build (fork module + call site).** `src/budget_answer.py`: the system message and the bookkeeping. Call site in `stream_agent_loop` at `budget_hit`: instead of `break`, feed back the results of the calls that ran, answer every **unexecuted** native tool call with a short *"not run: tool budget reached"* result (each `tool_call_id` needs a reply, see `_append_tool_results`), append the message, set `_force_answer`, continue. The forced round reuses the loop-breaker's path, so grace synthesis and the honest fallback already apply.
2. **Safety bounds, tested on the real loop with a scripted model** (pattern: `tests/test_decision_nudge.py`):
   - the forced round's request carries **no tools** (a text-only answer cannot change a document; this is the bound item 8's reverted nudge lacked);
   - at most **one** extra round, and no tool executes after the budget is hit, even if the model emits a tool call in that round;
   - budget 0 (unlimited) → behaviour unchanged; a turn that answers before the budget → unchanged (negative controls);
   - every `tool_call_id` of the cut batch gets a result.
   Check each test fails with the call site removed before it passes with it, and mutate the module (message dropped, tools left on, two forced rounds) with the scores written down.
3. **Verify (M1):** full suite; then webhard ×2 + research ×2 on Qwen/LM Studio (`bench_chain.sh qwen-web` plus `qwen`, ~1.5 h). Measure: task runs ending with no answer (13 Oct baseline: ≥ 8 of ~150), pass rate, and what the forced answers say — an honest *"I could not find …"* fails the checks but is still better than silence; a confident wrong answer is the risk to watch.
4. **Only if 3 leaves many silent turns:** an earlier, softer note (*"N tool calls left"*) a few calls before the budget. Acting on the model earlier is a bigger change; measure 1–3 first.

**Effort: S.** Steps 1–2 about half a day in a sandbox (one fork module, one call site, ~6 tests); step 3 is an unattended benchmark of ~1.5 h plus reading. The call site sits in upstream's most-changed function, so keep it to a few lines.
