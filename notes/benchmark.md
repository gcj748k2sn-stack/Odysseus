# Agent benchmark (`scripts/bench_agent.py`)

Compares models **inside Odysseus**: the same 20 tasks (fewer while their tools are switched off) go through the real
`/api/chat_stream` in agent mode, exactly as the browser sends them, and each is
checked on its outcome — the answer text, files on disk, notes/events/documents
through the API. Tasks: `scripts/bench_agent_tasks.py` (`bench_agent.py tasks`
lists them; 8 are in `--quick`: arith, read_fact, edit_file, web_fact, web_read, document_create, document_edit, document_followup — chosen 2026-10-09 to match real use, which is mostly web and documents). Raw speed per engine is a different script:
`scripts/bench_qwen_backends.py` ([qwensetup.md](qwensetup.md), *Engine benchmark*).

## Running it

One model per run, with only that model's server up. Bonsai 2 and Qwen loaded
together do not fit in 16 GB, and LM Studio loading Qwen while Bonsai runs gave
the *Compute error* of 2026-10-06 ([qwensetup.md](qwensetup.md)).

The steps, in order: `cleanup` removes leftovers from earlier runs, `preflight` must end with *ok*, `run` runs, `report` writes the comparison. Ready-to-paste commands for each kind of run are under [Commands](#commands).

- `--preset custom` sends that Odysseus preset with every turn, as the browser does, and names the run `qwen35+custom`, so the report keeps it apart. Without it, every turn runs at Odysseus's defaults (temp 1.0, no max_tokens). Added 2026-10-08.
- A 502 from Odysseus's repetition guard (*"started repeating tokens"*) is scored as the model's result, like the empty-response 502. A turn counts as a server fault only if none of its errors says it was the model's own result: the `agent_terminal` summary repeats the same failure without the text. Until 2026-10-08 15:45 a loop stopped the run (three times that day).
- **Reasoning effort is part of the run name (since 2026-10-09):** preflight reads the llama-server's command line (`ps`) and names the run `bonsai2@medium`, `bonsai2@xhigh`, …; with `--preset` the preset's own effort wins (Odysseus sends it on every request), marked *from the preset*. `default` = no flag, i.e. the template's own default (`xhigh` for Bonsai 2). The report labels older runs from `meta.json`; the four valid Bonsai runs before this were backfilled as `medium` (`start_bonsai2.sh` since 2026-10-05 22:41). A resume at a different effort stops instead of mixing. Bonsai 2's template accepts exactly `xhigh` (default) / `medium` / `low` and **raises on anything else**; PrismML calls `low` unsupported (*"behave close to `xhigh`"*), measured here as no different from `medium`.
- **An approval answer carries the message's `allow_bash` / `allow_web_search`** (since 2026-10-09), as the browser does. Earlier runs re-read the whole prompt after most approval cards (~11 min of a Bonsai full run), so compare time on approval tasks only between runs on the same side of that fix.
- Asks for the Odysseus password unless `ODYSSEUS_PASSWORD` is set. Odysseus runs on **:7860** (7000 is macOS AirPlay).
- Targets: `bonsai2` (endpoint `ed1cd41c`, llama.cpp :8090) and `qwen35` (`a5179555`, LM Studio :1234), or `NAME=ENDPOINT_ID:MODEL_ID`.
- An interrupted run continues with `--resume <run dir>`. Results go to `data/bench/agent/<run-id>/` (gitignored); task fixtures go to `~/odysseus-bench/<run-id>/` (`BENCH_WS_ROOT` overrides) and can be deleted any time.
- Time: Qwen ~43 s per task, Bonsai 2 ~110–150 s; full suite ×2 ≈ 30 min (Qwen) vs ≈ 1 h 45 min (Bonsai, measured 2026-10-09 before the approval fix).
- **Switched-off tools (since 2026-10-08):** a task whose every usable tool is switched off in Settings → Agent Tools is skipped, not failed (`calendar_create` while `manage_calendar` is off). Preflight prints `⏭ skipping …`; the report shows *⏭ tool off*. Earlier runs include it, so their full-suite totals are out of 18 per run (36 at `--runs 2`) and new ones out of 17 (34); compare per task, or on the report's *only tasks every model ran* row.

## Commands

Paste each block as it is into the Mac terminal (zsh). They carry no `#` comments on purpose: interactive zsh does not treat `#` as a comment and passes it on as arguments. Every block starts in the repo. **Only one model server up per run.** `run` does its own preflight (what is loaded, SearXNG, n_ctx) and prints it before the first task.

**Once per terminal** — asks for the Odysseus password without echoing it or saving it in the shell history, so the commands below don't each ask again:
```
read -s "ODYSSEUS_PASSWORD?Odysseus password: " && export ODYSSEUS_PASSWORD && echo
```

**Before a Qwen run** — Bonsai's llama-server stopped (Ctrl-C in its terminal), then LM Studio's server up with only Qwen loaded:
```
lms server start && lms unload --all && lms load qwen/qwen3.5-9b
```

**Before a Bonsai run** — LM Studio emptied and its server stopped (as `start_bonsai2.sh` asks; also quit Ollama if it runs), then Bonsai's server started in its own terminal and left running:
```
lms unload --all && lms server stop
```
```
~/BonsaiDemo/start_bonsai2.sh
```

**Quick check, Qwen** — 8 tasks once, ~6 min:
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py cleanup && caffeinate -i python3 scripts/bench_agent.py run --target qwen35 --quick --yes
```

**Short run, Qwen** — 8 tasks ×2, ~12 min:
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py cleanup && caffeinate -i python3 scripts/bench_agent.py run --target qwen35 --quick --runs 2 --yes
```

**Full run, Qwen** — 17 tasks ×2, ~30 min:
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py cleanup && caffeinate -i python3 scripts/bench_agent.py run --target qwen35 --runs 2 --yes
```

**Short run, Bonsai 2** — 8 tasks ×2, ~55 min:
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py cleanup && caffeinate -i python3 scripts/bench_agent.py run --target bonsai2 --quick --runs 2 --yes
```

**Full run, Bonsai 2** — 17–18 tasks ×2, ~1 h 45 min (2026-10-09, before the approval and tool-selection fixes; less now):
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py cleanup && caffeinate -i python3 scripts/bench_agent.py run --target bonsai2 --runs 2 --yes
```

**With the custom preset** (currently temp 1.0 / 8192 / effort medium — check `data/presets.json`) — add `--preset custom` to any `run`; the run is named `qwen35+custom` / `bonsai2+custom`. It stops at once if the preset is disabled (the chip's × disables it):
```
cd /Users/cedrik/odysseus && caffeinate -i python3 scripts/bench_agent.py run --target qwen35 --quick --runs 2 --preset custom --yes
```

**A few tasks only** — task ids from `python3 scripts/bench_agent.py tasks`:
```
cd /Users/cedrik/odysseus && caffeinate -i python3 scripts/bench_agent.py run --target qwen35 --tasks calendar_create,json_output --runs 2 --yes
```

**Continue an interrupted run** — same target (and preset) as the original. Since 2026-10-09 the resume keeps the original run's `--runs`; before that it fell back to 1 and silently skipped every missing r2:
```
cd /Users/cedrik/odysseus && caffeinate -i python3 scripts/bench_agent.py run --target qwen35 --preset custom --resume data/bench/agent/20261008-144530-qwen35+custom --yes
```

**Preflight only** — what would distort a run, without running anything:
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py preflight --target bonsai2
```

**Report** — one run, or every valid run since 2026-10-07:
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py report data/bench/agent/RUN_DIR
```
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py report data/bench/agent/2026100[7-9]* --out data/bench/agent/report.md
```
Replace `RUN_DIR` with the folder the run printed at its start (`run dir: …`).

## Knowledge suite (`--suite knowledge`, since 2026-10-09)

What a model **knows and can work out** in three topics, next to the agent suite's tool handling: 24 tasks in `scripts/bench_knowledge_tasks.py`, 8 per topic (mycology, microelectronics, finance), `--quick` = 9 (3 per topic). Each topic mixes the same kinds — `fact`, `calc`, `trap` (false premise to correct), `safety`, `limits` (says what it cannot know), `data` (fixture file), `web`, `code`, `language` (German) — and the report has a **By kind** table. Run dirs end in `-knowledge`, so a `data/bench/agent/2*` glob of agent runs still pools only agent runs if you exclude them (`report` takes explicit dirs).

- **Checks are lexical**, with a correct and ≥ 2 wrong sample answers per task in `tests/test_bench_knowledge_tasks.py` (69 tests; 10 checker mutations caught, e.g. negation ignored, tolerance ×100, opening "yes" not detected, source check dropped). The tests caught one checker bug while writing them: *"Agaricus: white. Amanita: brown."* passed, because a colour in the next sentence counted — matches now stay inside one clause.
- **Needs item 75 committed.** Most tasks have no workspace and no tools, so they take the direct reply path; before the fix its 128-token cap left thinking models with empty answers.
- **Answer keys, checked 2026-10-09:** amatoxins / α-amanitin, onset 6–24 h, false recovery 24–48 h ([WikEM](https://wikem.org/wiki/Mushroom_poisoning)); parasol saprobic, edible with caution, green-spored *Chlorophyllum molybdites* lookalike ([MDC](https://mdc.mo.gov/discover-nature/field-guide/parasol)); pink oyster 21–26 °C, high CO₂ → long stringy stems, small caps ([North Spore](https://northspore.com/products/pink-oyster-mushroom-ready-to-grow-fruiting-block-kit)); spore prints *Agaricus* cocoa/purple/dark brown, *Amanita* white to pale ([MykoWeb](https://mykoweb.com/CAF/skey/agaric.html)); AHT20 fixed at 0x38 ([Linux hwmon](https://docs.kernel.org/6.5/_sources/hwmon/aht10.rst.txt)); BMP280 0x76/0x77 by SDO ([Bosch forum](https://community.bosch-sensortec.com/mems-sensors-forum-jrmujtaw/post/bmp280-reading-data-using-i2c-from-address-0x76-XkXG3A9jAg3E8U0)); ESP32 strapping pins GPIO0/2/5/12/15 ([ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/v5.3/esp32/api-reference/peripherals/gpio.html)); ESP32 supply/IO absolute max 3.6 V, no 5 V tolerance stated ([datasheet](https://documentation.espressif.com/esp32_datasheet_en.pdf)); gold drivers: real rates, dollar, central banks, safe haven, inflation ([Banque de France](https://banque-france.fr/system/files/2024-09/How_can_we_account_for_the_increase_in_the_price_of_gold.pdf)); troy ounce 31.1034768 g = 480 × 64.79891 mg (definition). Calculations computed in code: straw 3.71 kg, LED 130 Ω, divider 0.215, battery 123.2 days, gold 77.16 $/g / 77,162 $/kg, growth 9.86 %.
- **`fin_price_web` accepts 3,000–6,000 $/oz** ($4,143.94 on 2026-10-06, [pricegold.net](https://pricegold.net/2026/october/6/)). Widen it if gold leaves that band.
- **Changed from the first plan (chat, 19:23):** straw prompt says 0 % moisture / % of wet weight (ambiguous otherwise); divider asks for the ratio, not two resistors; RAM-vs-flash replaced by a German I²C question (it duplicated `explain`); the real-return task dropped for a German share-vs-bond task; prompts avoid *rate* / *current* / *today* (web-intent rule).
- **Time (estimate, from today's per-task times):** Qwen quick ×2 ~8 min, full ×2 ~25 min; Bonsai quick ×2 ~20 min, full ×2 ~60 min.

**Results.** Qwen quick ×2 (`20261009-202734-qwen35-knowledge`, `bf504b11`): **8/18 as scored, 42 min.** 6 empty answers = Qwen's thinking used the direct path's whole 4,096-token cap (item 76) — not knowledge failures. 1 checker miss (`mc_i2c` r1, *"do **not** have conflicting"*; fixed: checks read text without `**`, and "have conflicting" counts) → 9/18 rescored. **3 real misses:** `myco_parasol` ×2 (says edible, never corrects *mycorrhizal*), `mc_5v` r1 (*"Generally yes … widely advertised as 5 V tolerant"* — wrong, and cut off at 4,096 tokens). Passed both times: `fin_pe`, `fin_price_limits`; `myco_amatoxin`, `mc_i2c`, `fin_gold_gram`, `myco_straw` once each (the other run empty). Not comparable with later runs once item 76 changes the direct path.

**Qwen after item 76** (`20261009-223421-qwen35-knowledge`, `137aba4a`): **13/18 (15 as scored before the `mc_5v` checker fix), 6.5 min, no empty answers.** Passed both times: `myco_amatoxin`, `myco_straw`, `mc_i2c`, `fin_gold_gram`, `fin_pe`, `fin_price_limits`. Real misses: `myco_parasol` ×2 (keeps "mycorrhizal"), `mc_5v` ×2 ("GPIO pins are 5V tolerant"), `mc_battery` r1 (arithmetic slip). This is the Qwen baseline for the knowledge suite.

**Quick knowledge run** (one model server up, as for the agent suite):
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py cleanup && caffeinate -i python3 scripts/bench_agent.py run --target qwen35 --suite knowledge --quick --runs 2 --yes
```
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py cleanup && caffeinate -i python3 scripts/bench_agent.py run --target bonsai2 --suite knowledge --quick --runs 2 --yes
```
**Full knowledge run** — replace `--quick` by nothing:
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py cleanup && caffeinate -i python3 scripts/bench_agent.py run --target qwen35 --suite knowledge --runs 2 --yes
```
**Report over all knowledge runs:**
```
cd /Users/cedrik/odysseus && python3 scripts/bench_agent.py report data/bench/agent/*-knowledge --out data/bench/agent/report-knowledge.md
```

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
- **Only file tasks get a workspace** (task field `workspace`, since 2026-10-09). Real web and document chats have none, and the workspace path is in the system prompt (*"Active workspace: …"*), so with a workspace on every task the non-file tasks got the "Workspace coding mode" rules (which forbid notes/documents) and no task could reuse the previous task's cached prompt start. File tasks still each have their own folder.
- **Documents open in the panel are sent as `active_doc_id`** with every request of that chat, approval answers included, as the browser does: `document_edit` creates its document through `POST /api/document` after the chat exists (`session_setup`), `document_followup` sends message 2 with the document message 1 created (`followups`). `rec["turns"]` has time and rounds per message.
- **Titles with the run marker are checked twice:** *created* and *copied exactly* are separate checks, and cleanup matches any `bench-xxxx` tag, because both models have mangled the marker.

## Results

Valid runs only (after the 2026-10-06 merge and the workspace fix). Pass counts are per task run. Full comparison: `data/bench/agent/report.md` (regenerated 2026-10-09 15:21, all runs 10-07 … 10-09).

| | Bonsai 2 @medium | Bonsai 2 @low | Qwen 3.5 9B (temp 1.0) | Qwen 3.5 9B +custom (0.6) |
|---|---|---|---|---|
| Passed | 74/76 | 16/16 | 68/72 | 51/52 (+1 loop not recorded) |
| On tasks every config ran | 56/56 | 16/16 | 32/32 | 32/32 |
| Median per task | 131 s | 133 s | 43 s | 44 s |
| Median per round (log) | 52 s | 59 s | 19 s | 20 s |

⚠️ **Second baseline break 2026-10-09 ~15:45 (task suite):** non-file tasks lost their workspace, `document_edit` and `document_followup` were added, and `--quick` was rebalanced (out: write_file, note_create, multi_step, german; in: web_fact, document_create, document_edit, document_followup). Quick-run totals before and after are not comparable; per-task results of unchanged file tasks are.

⚠️ **Baseline break 2026-10-09 ~14:45** (commits `48652619` approval answer, `eea56cb2` keyword-only tool selection, `21282328` prompt trims): runs before it are slower on approval tasks and differ in the tools offered, so compare speed only within one side.

- **Bonsai 2 quick ×1, first run after the break (`20261009-145108-bonsai2@medium`, Odysseus `7e49a802`, restarted): 8/8, 22.4 min** vs 28.1 min (sum of per-task medians of the 6 earlier medium runs); faster on 7 of 8 (edit_file 157 vs 266 s, write_file 373 vs 463 s). `[tool-rag] Local endpoint, keyword selection` logged for every task without the Terminus path. **Approval continuations:** `tools_same=True` now, re-read ~1,200 tokens / ~20 s (was ~72 s) — the rest is the date/time message (`first_diff=1 … user 729ch`): its clock changes between the card and the answer, so everything after the system prompt is re-read. n = 8, one run: direction, not a measurement.
- **Qwen, 2026-10-08 (`20261008-133121`, full ×2, default temp 1.0, Odysseus `7f355714` plus the uncommitted item 7/43/48 fixes, restarted 13:26): 34/36 as scored, 35/36 after the rescore below.** Median 44 s per task, 11 approval cards, same as 10-07. Failures: `calendar_create` r2 wrote `bench-2a8] Dentist` for `[bench-2a8c] Dentist` (the 10-07 copying slip again, so 2 of 4 calendar runs over two days); `json_output` r2 was a **scoring bug** — the reply was exactly the JSON, but Odysseus listed two failed `python` calls as a `- ` bullet list, which `split_turn_report` did not recognise. Fixed in `scripts/bench_agent_tasks.py` (`_REPORT_LINE` takes an optional `- `); rescored by hand, it passes all four checks. Negative control: a model's own bullet stays model text. ⚠️ **`recover_typo` looped on its first attempt in both repetitions** (`[degenerate-stream]` 13:37:58 *'entries rows entries rows'*, 14:07:39 *'lines cover rows lines'*). The script treated Odysseus's repetition 502 as a server fault, stopped, and the resumed attempt was recorded (both passed). Fixed in two steps: `MODEL_EMPTY_RE` recognises the repetition text, and, since 15:45, a turn is judged as a whole. Odysseus reports the failure twice — the `error` event with the text, then `agent_terminal` with only *"Model request failed (HTTP 502)"* — and the bare summary alone still read as a server fault. That is why the first step did not stop the 14:07 halt or the 15:17 one. **Strict reading, with the two loops as failures: 33/36.** Both loops ran at temp 1.0 with no presence penalty from Odysseus; Qwen pairs 1.0 with presence_penalty 1.5.
- **Qwen at temp 0.6, 2026-10-08 (`--preset custom`; every turn logged `Preset custom: temp=0.6, max_tokens=8192`):** quick ×2 `20261008-142729-qwen35+custom` **16/16**, median 64 s; full ×2 `20261008-144530-qwen35+custom` **34/35 recorded**, median 43 s, 11 cards. The missing row, `json_output` r2, **looped** (`[degenerate-stream]` 15:17:54, *'rows rows rows rows'*) and was not saved: the script stopped with *"the model server failed"* (it was not interrupted). Counted as a failure: **34/36**. The other failure: `calendar_create` r2 wrote `bench-0c8c Dentist` (brackets dropped). **Reading: 0.6 and 1.0 are the same at this n** (34/36 vs 33–35/36, same median time). Loops occur at both temperatures (1.0: 2 in `recover_typo`; 0.6: 1 in `json_output`), so lowering the temperature does not remove them. The title-copying slip is now **3 of 6** `calendar_create` runs over two days, the one consistent Qwen weakness here.
- Qwen's real failure: `calendar_create` r1 created *"bench-2d22 Dentist"* (brackets dropped) and then said it had created *"[bench-2d22] Dentist"*. Same kind of copying slip as the 2026-10-05 note.
- Bonsai 2 recovers from its own tool errors (a Python traceback, macOS `cat -A`) but at ~1 min per round; uncached prefill ~64 tok/s, prompt-cache hit ~51 % (item 58).
- **Bonsai 2, 2026-10-08 (`20261008-151903-bonsai2`, `--quick` ×2, no preset): 16/16**, median 151 s per task, 55 min, 7 approval cards, **no repetition loops** (`[degenerate-stream]` 0 in the window). llama.cpp's own sampling for this server: temp 1.0, top_k 20, top_p 0.95, **min_p 0.05**. Across all three Bonsai `--quick` runs: **32/32**. Report over every valid run: `data/bench/agent/report.md` (written 2026-10-08).
- **Comparison, 2026-10-08.** On the 8 `--quick` tasks all three configurations are 100 % (Bonsai 32/32, Qwen 1.0 and Qwen 0.6 each 32/32). Qwen is ~3.5× faster per task (43 s vs 151 s). On the full suite Qwen's only consistent failure is the calendar title copy (3/6), plus occasional repetition loops (3 in 108 task runs across both temperatures). Bonsai has shown neither yet, but has not run the 10 tasks that include `calendar_create`.
- **Where Bonsai's time goes** (run `20261008-151903`, 50 rounds, 55 min, from `[agent-timing]` + llama.cpp `prompt_ms`/`cache_n`): **prefill 66 %, generation 33 %.** **Round 1 of every turn: 0 % cache hit** (0 of 115k tokens), median prompt ~5k tokens, **76 s prefill** at 66 tok/s, before any output. Rounds 2+: 83 % cached, 16 s prefill. Generation (thinking + answer, ~12 tok/s): median 15 s per round. So **the round-1 cache miss is the largest single cost, ~25 of 55 min**. Items 57 (tool list ahead of the history, different per message) and 40 predict exactly that. Thinking at `xhigh` is item 59.
- **Bonsai 2 full, 2026-10-09 (`20261009-031517-bonsai2`, full ×2 incl. `calendar_create`, medium): 34/36**, 1 h 43 min, median 109 s per task / 55 s per round, 15 approval cards. Both failures are `recover_typo`: right file found, then a **repetition loop** while counting rows in thinking (*'cl imal og line'* ×12, *'cl imal og cl'* ×10) — the same task Qwen looped on at 1.0. `calendar_create` 2/2 with the marker copied exactly.
- **Where its time went** (109 rounds, `[agent-timing]` + `[prefix-probe]`): prefill 61 min (59 %), generation 41.5 min (40 %), tools + Odysseus 0.5 min. **New chat, round 1: 33 min** (36 rounds, cache 0, ~3.2k tokens of system prompt + tools even for "17 × 23"). **Continuation after an approval card: 11.6 min** — in 10 of 15 the continuation sends `bash`, which the first turn did not, so `first_diff=0` and the whole prompt is re-read (median 72 s). **Cause: the harness, not Odysseus** — the benchmark's approval answer omitted `allow_bash` / `allow_web_search`; the server reads a missing `allow_bash` as "not restricted" (`routes/chat_routes.py` ~1514). The browser sends both with every answer (`static/js/chat.js` ~1845–1931). Both turns select the same 18 Terminus tools, so the card's sealed tool set plays no part (an earlier reading blamed it — wrong). Fixed 2026-10-09 (`tests/test_bench_agent_approval.py`); **runs before that overstate time on tasks with an approval card** and gave web tasks' continuations no web tools. **Rounds 3+ dropping the previous round's thinking: 8.3 min** prefill (17 rounds, median 26 s vs 3 s for a clean append). Thinking ≈ 47k chars vs 5.5k answer chars.
- **Bonsai 2 at `low`, 2026-10-09 (`20261009-120709-bonsai2low`, quick ×2, server flag `reasoning_effort: low`, labelled `@low` in `meta.json` afterwards): 16/16, 57 min, median 133 s per task.** The flag did arrive: arith's prompt is 3,223 tokens vs 3,193 at medium, the length of the template's *"Reasoning effort is set to low…"* sentence. **No measurable difference from medium** on these 8 tasks: thinking 1,371 chars per task run vs 1,277 at medium (6 runs per task), per round 222 vs 277, per task both directions (edit_file 3,982 vs 1,698; read_fact 689 vs 1,039) — noise at n = 2. My mid-run reading ("xhigh-like", first 6 tasks) was premature. There is no clean `xhigh` run in this harness (the 10-05 run predates the merge and counts thinking differently), so PrismML's *"low … behaves close to xhigh"* is neither confirmed nor refuted here.
- Pre-merge runs `20261005-*` (quick, 2026-10-05) used a different Odysseus and the old `web_fact` task; keep them out of reports.

## Open questions

- Should Odysseus's turn report still list a tool failure the model recovered from later in the same turn? It is the fork's deliberate *failures always* rule; it made a JSON-only answer non-JSON.
- With n = 16–36 per model, pass-rate gaps under ~15 points are noise. Speed is the only firm difference so far.
