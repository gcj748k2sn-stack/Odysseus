# 42. Sessions pin the model tag per row; a tag Ollama no longer serves does not fall back

Open item, moved here from `notes/todo.md` on 2026-10-07 so the dashboard stays short. Its row in the [todo.md](../todo.md) index carries the current status; this file is the full record.

---

**Filed 2026-08-01 from re-checking *"the 64k switch is live and measured"* — true, and narrower than it reads: it was verified on one of only two sessions then on the new tag.**

**`sessions.model` is a per-row column and a THIRD channel pinning the tag.** [qwensetup.md](../qwensetup.md) names `default_model` and `research_model` as *"the two settings"*. There is a third, it is per session, and nothing recorded it.

```
sessions by model, 2026-08-01:   72 'qwen3.5:9b-32k'   7 'qwen3.5:9b-64k'
                                  3 'qwen3.5:4b-32k'   2 ''
```

- ⊘ **THE HEADLINE THIS WAS FILED ON IS DEAD, disproved hours later by the one command the fix draft asked for.** Filed as *"two 9B variants ≈ 13 GB of 16"* — **arithmetic, never a measurement.** `ollama ps` showed **one** model: Ollama **evicts** rather than co-residing, confirmed with three minutes of timer margin, and **the forced reload costs ~2.6 s**. **The staging in that draft is the only reason this cost an hour instead of a build.** ⚠️ Two 9B variants say nothing about a 9B plus the 4B utility model; `all-minilm` is confirmed free.
- ✅ **CONFIRMED LIVE 2026-08-01 21:08 — the dead-tag branch, which is now the whole severity.** One `hi` into a session pinned to the retired `qwen3.5:4b-32k`: `local endpoint returned 404 — check the base URL and model name. (model 'qwen3.5:4b-32k' not found)`. **The chain read from source holds**: `normalize_model_id` returns `None` for a tag the endpoint lacks, the caller is `if norm:`, so the dead tag goes out on the wire. `try_fallback_endpoint` cannot rescue it — it skips the current endpoint and only fires when the endpoint itself is unreachable.
  - ⚠️ **It fails VISIBLY — the message names the model and the status.** Not a silent failure, so severity stays S3.
  - 🔴 **The reason to fix it anyway: [qwensetup.md](../qwensetup.md) plans to delete `qwen3.5:9b-32k` once 64k has run a week, and that would do this to 72 sessions at once.** The *"do not delete it"* note there is load-bearing, not cautious.
  - ⚠️ **The first attempt at this test MISSED** — a `qwen3.5:9b-32k` session answered, and that tag exists, so it proved nothing. All three candidates are named *"Pink Oyster Mushroom Growth Stages"*; **the precondition is the composer chip reading the dead tag before you send.**
- ⚠️ **The 32k budget defect is still live on 72 sessions:** at 32,768 with `max_tokens 8192` the real input room is 24,576 against an auto budget of 27,852, so the app can assemble prompts that cannot fit alongside a full answer. It degrades quietly.
- **Fix, not built. Two halves, and only one is a code change.**
  - **Data:** `research_model` is still `qwen3.5:9b-32k`; the 72 rows are a preference now the memory argument is gone. If migrating, snapshot first, app down. ✅ **It destroys no evidence** — `chat_messages.metadata` carries `model` and `requested_model` per assistant row (checked: `requested_model != model` on **0 of 179**).
  - **Code:** the real defect is that **`normalize_model_id` returns `None` for two different conditions** — *"the endpoint answered and lacks this model"* (safe to act on) and *"the endpoint did not answer"* (not). Distinguish them at the call site; fall back to `default_model` on the first, **and log it before letting it act**. Negative control: an unreachable endpoint must leave the tag alone.
