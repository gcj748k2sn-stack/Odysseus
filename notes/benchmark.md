# Agent benchmark (`scripts/bench_agent.py`)

Compares models **inside Odysseus**: the same 18 tasks go through the real
`/api/chat_stream` in agent mode, exactly as the browser sends them, and each is
checked on its outcome — the answer text, files on disk, notes/events/documents
through the API. Tasks: `scripts/bench_agent_tasks.py` (`bench_agent.py tasks`
lists them; 8 are in `--quick`). Raw speed per engine is a different script:
`scripts/bench_qwen_backends.py` ([qwensetup.md](qwensetup.md), *Engine benchmark*).

## Running it

One model per run, with only that model's server up. Bonsai 2 and Qwen loaded
together do not fit in 16 GB, and LM Studio loading Qwen while Bonsai runs gave
the *Compute error* of 2026-10-06 ([qwensetup.md](qwensetup.md)).

```
cd /Users/cedrik/odysseus
python3 scripts/bench_agent.py cleanup                       # leftovers from earlier runs
python3 scripts/bench_agent.py preflight --target bonsai2    # must end with "ok"
caffeinate -i python3 scripts/bench_agent.py run --target bonsai2 --runs 2 --yes
python3 scripts/bench_agent.py report data/bench/agent/2026100[7-9]* --out data/bench/agent/report.md
```

- `--preset custom` sends that Odysseus preset with every turn, as the browser does, and names the run `qwen35+custom`, so the report keeps it apart. Without it, every turn runs at Odysseus's defaults (temp 1.0, no max_tokens). Added 2026-10-08.
- A 502 from Odysseus's repetition guard (*"started repeating tokens"*) is scored as the model's result, like the empty-response 502. A turn counts as a server fault only if none of its errors says it was the model's own result: the `agent_terminal` summary repeats the same failure without the text. Until 2026-10-08 15:45 a loop stopped the run (three times that day).
- Asks for the Odysseus password unless `ODYSSEUS_PASSWORD` is set. Odysseus runs on **:7860** (7000 is macOS AirPlay).
- Targets: `bonsai2` (endpoint `ed1cd41c`, llama.cpp :8090) and `qwen35` (`a5179555`, LM Studio :1234), or `NAME=ENDPOINT_ID:MODEL_ID`.
- An interrupted run continues with `--resume <run dir>`. Results go to `data/bench/agent/<run-id>/` (gitignored); task fixtures go to `~/odysseus-bench/<run-id>/` (`BENCH_WS_ROOT` overrides) and can be deleted any time.
- Time: Qwen ~40 s per task, Bonsai 2 ~140 s; full suite ×2 ≈ 30 min vs ≈ 3 h.

## Why it is built this way

Each of these was found in the code or in a failed run; changing one changes what the numbers mean.

- **Incognito turns.** Otherwise memory and skill extraction run after each turn, pollute memory, and compete with the next task for the model. A saved skill would also arm the approval gate on every turn.
- **Password login, not an API token.** A token runs as the `api` user, for whom Odysseus drops the workspace binding.
- **Fixtures outside `data/`.** Since the 2026-10-06 merge `vet_workspace` refuses any workspace under `data/` (except `agent_workspace/` & co.). The first post-merge run had every file tool refused, Bonsai wrote a file through `bash` instead, and that counted as a pass — run deleted. A `workspace_rejected` now stops the run.
- **Prompts avoid web-intent words** (*search, current, today, rate, web, …*) except in web tasks: `chat_stream` reads them as a web lookup and removes the file tools. The script refuses such a prompt (`WEB_INTENT_RE`, copied from `chat_stream`).
- **Approval cards are answered with *Allow for this task*** and counted, not scored. Reading a file or fetching a page arms the gate, so most read-then-write tasks hit one card.
- **URLs in the prompt are fetched by Odysseus before round 1** (`src/chat_processor.py`, first 10,000 chars), so web tasks with a URL do not require a `web_fetch` call.
- **Odysseus's closing turn report is not model text.** `src/turn_report.py` appends *"⚠️ `tool` failed — …"* for any failed tool, even one the model recovered from; checks see the reply without it.
- **Server faults stop the run instead of scoring:** unreachable, LM Studio *Compute error*, other HTTP 5xx. Odysseus's 502 *"Model returned an empty response"* and a 400 context overflow are model results.
- **Titles with the run marker are checked twice:** *created* and *copied exactly* are separate checks, and cleanup matches any `bench-xxxx` tag, because both models have mangled the marker.

## Results

Valid runs only (after the 2026-10-06 merge and the workspace fix). Pass counts are per task run.

| | Bonsai 2 27B (llama.cpp, 32k, q4 KV) | Qwen 3.5 9B (LM Studio GGUF Q4_K_M, 64k) |
|---|---|---|
| Runs | `20261007-012621`, `20261007-171522` (`--quick` ×2) | `20261007-175428` (full ×2) |
| Passed | 16/16 | 35/36 (34/36 as scored before the turn-report fix) |
| On the 8 tasks both ran | 16/16 | 16/16 |
| Median per task / per round | 142 s / 62 s | 42 s / 19 s |
| Empty answer after a tool round | 0 of 31 rounds | 0 of 43 |
| Approval cards | 7 — mostly from computing with `python` | 11 |

- **Qwen, 2026-10-08 (`20261008-133121`, full ×2, default temp 1.0, Odysseus `7f355714` plus the uncommitted item 7/43/48 fixes, restarted 13:26): 34/36 as scored, 35/36 after the rescore below.** Median 44 s per task, 11 approval cards, same as 10-07. Failures: `calendar_create` r2 wrote `bench-2a8] Dentist` for `[bench-2a8c] Dentist` (the 10-07 copying slip again, so 2 of 4 calendar runs over two days); `json_output` r2 was a **scoring bug** — the reply was exactly the JSON, but Odysseus listed two failed `python` calls as a `- ` bullet list, which `split_turn_report` did not recognise. Fixed in `scripts/bench_agent_tasks.py` (`_REPORT_LINE` takes an optional `- `); rescored by hand, it passes all four checks. Negative control: a model's own bullet stays model text. ⚠️ **`recover_typo` looped on its first attempt in both repetitions** (`[degenerate-stream]` 13:37:58 *'entries rows entries rows'*, 14:07:39 *'lines cover rows lines'*). The script treated Odysseus's repetition 502 as a server fault, stopped, and the resumed attempt was recorded (both passed). Fixed in two steps: `MODEL_EMPTY_RE` recognises the repetition text, and, since 15:45, a turn is judged as a whole. Odysseus reports the failure twice — the `error` event with the text, then `agent_terminal` with only *"Model request failed (HTTP 502)"* — and the bare summary alone still read as a server fault. That is why the first step did not stop the 14:07 halt or the 15:17 one. **Strict reading, with the two loops as failures: 33/36.** Both loops ran at temp 1.0 with no presence penalty from Odysseus; Qwen pairs 1.0 with presence_penalty 1.5.
- **Qwen at temp 0.6, 2026-10-08 (`--preset custom`; every turn logged `Preset custom: temp=0.6, max_tokens=8192`):** quick ×2 `20261008-142729-qwen35+custom` **16/16**, median 64 s; full ×2 `20261008-144530-qwen35+custom` **34/35 recorded**, median 43 s, 11 cards. The missing row, `json_output` r2, **looped** (`[degenerate-stream]` 15:17:54, *'rows rows rows rows'*) and was not saved: the script stopped with *"the model server failed"* (it was not interrupted). Counted as a failure: **34/36**. The other failure: `calendar_create` r2 wrote `bench-0c8c Dentist` (brackets dropped). **Reading: 0.6 and 1.0 are the same at this n** (34/36 vs 33–35/36, same median time). Loops occur at both temperatures (1.0: 2 in `recover_typo`; 0.6: 1 in `json_output`), so lowering the temperature does not remove them. The title-copying slip is now **3 of 6** `calendar_create` runs over two days, the one consistent Qwen weakness here.
- Qwen's real failure: `calendar_create` r1 created *"bench-2d22 Dentist"* (brackets dropped) and then said it had created *"[bench-2d22] Dentist"*. Same kind of copying slip as the 2026-10-05 note.
- Bonsai 2 recovers from its own tool errors (a Python traceback, macOS `cat -A`) but at ~1 min per round; uncached prefill ~64 tok/s, prompt-cache hit ~51 % (item 58).
- **Bonsai 2, 2026-10-08 (`20261008-151903-bonsai2`, `--quick` ×2, no preset): 16/16**, median 151 s per task, 55 min, 7 approval cards, **no repetition loops** (`[degenerate-stream]` 0 in the window). llama.cpp's own sampling for this server: temp 1.0, top_k 20, top_p 0.95, **min_p 0.05**. Across all three Bonsai `--quick` runs: **32/32**. Report over every valid run: `data/bench/agent/report.md` (written 2026-10-08).
- **Comparison, 2026-10-08.** On the 8 `--quick` tasks all three configurations are 100 % (Bonsai 32/32, Qwen 1.0 and Qwen 0.6 each 32/32). Qwen is ~3.5× faster per task (43 s vs 151 s). On the full suite Qwen's only consistent failure is the calendar title copy (3/6), plus occasional repetition loops (3 in 108 task runs across both temperatures). Bonsai has shown neither yet, but has not run the 10 tasks that include `calendar_create`.
- **Where Bonsai's time goes** (run `20261008-151903`, 50 rounds, 55 min, from `[agent-timing]` + llama.cpp `prompt_ms`/`cache_n`): **prefill 66 %, generation 33 %.** **Round 1 of every turn: 0 % cache hit** (0 of 115k tokens), median prompt ~5k tokens, **76 s prefill** at 66 tok/s, before any output. Rounds 2+: 83 % cached, 16 s prefill. Generation (thinking + answer, ~12 tok/s): median 15 s per round. So **the round-1 cache miss is the largest single cost, ~25 of 55 min**. Items 57 (tool list ahead of the history, different per message) and 40 predict exactly that. Thinking at `xhigh` is item 59.
- **Not yet known:** Bonsai 2 on the 10 tasks outside `--quick` (find_file, recover_typo, shell, web_fact/web_fetch, calendar, document, long_file, json_output). Next run: `--target bonsai2 --runs 2`.
- Pre-merge runs `20261005-*` (quick, 2026-10-05) used a different Odysseus and the old `web_fact` task; keep them out of reports.

## Open questions

- Should Odysseus's turn report still list a tool failure the model recovered from later in the same turn? It is the fork's deliberate *failures always* rule; it made a JSON-only answer non-JSON.
- With n = 16–36 per model, pass-rate gaps under ~15 points are noise. Speed is the only firm difference so far.

### 2026-10-08: switched-off tools
From now on a task whose every usable tool is switched off in Settings → Agent Tools is skipped, not failed (`calendar_create` while `manage_calendar` is off). Earlier runs include it, so their full-suite totals are out of 18 tasks per run (36 at `--runs 2`) and new ones out of 17 (34); compare per task, or on the report's *only tasks every model ran* row when two models differ.
