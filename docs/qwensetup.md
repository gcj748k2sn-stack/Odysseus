# Odysseus + Qwen/Ollama setup — MacBook M1 Pro, 16GB

Odysseus runs natively from `~/odysseus` (venv at `~/odysseus/venv`), models via Ollama (localhost:11434, brew service) and MLX server (127.0.0.1:8000).

Open items / todo live in [todo.md](todo.md); closed investigations in [resolvedissues.md](resolvedissues.md). *(`llmSetup.md`, the pre-2026-07-18 combined document, was deleted 2026-07-28 once its last source citations were repointed — see [todo.md](todo.md) item 5.)*

## Models
- **Agent/main — the only chat model:** Qwen3.5-9B-32k, thinking ON. Create: `printf 'FROM qwen3.5:9b\nPARAMETER num_ctx 32768\n' > /tmp/mf && ollama create qwen3.5:9b-32k -f /tmp/mf`.
- **Utility:** nemotron-3-nano:4b
- **4B removed 2026-07-18.** Two head-to-head rounds settled it: the 4B produces confident, plausible, wrong numbers aimed straight at chamber setpoints, and even with all the right tools in hand it won't call them for a document edit (see [resolvedissues.md](resolvedissues.md): "4B retired"). Not a speed/quality tradeoff — a correctness floor it doesn't clear.
- Set `OLLAMA_KEEP_ALIVE=30m`. With one chat model there's no swap thrash to avoid, but a cold load is still ~6GB.

## Required config (each of these caused real failures)

**1. Context window — Ollama defaults to num_ctx 2048.** It silently truncates Odysseus's 4–15k-token prompts (`truncating input prompt` in the log) → agent runs die after a few thinking tokens.

**2. Native tools — off by default for manual Ollama endpoints** (Odysseus issue #1567; no UI toggle). Without it, models improvise fenced blocks that get executed as bash. Fix in `~/odysseus/data/app.db`:
```
UPDATE model_endpoints SET supports_tools=1 WHERE base_url LIKE '%11434%';
```

**3. Sampling.** The "custom" preset resets to temp=1.0 on every new session; re-check it (high temp → hallucinated bash instead of tool calls).
- **Current (9B, thinking ON):** temp **0.6**, top_p 0.95, max_tokens 8192. Do NOT drop to 0.2 — Qwen warns that near-greedy sampling in thinking mode causes endless repetition.
- Thinking-off escape hatch, if ever needed: temp 0.3, top_p 0.8, max_tokens 6400.

**4. ChromaDB (port 8100, tool RAG) — venv breaks if the repo folder moves** (absolute paths). Fix: `rm -rf venv && ./start-macos.sh`. Note: rebuilds wipe extra pip packages (see Web search below).

**5. Embeddings — `all-minilm:l6-v2` must be pulled in Ollama.** It's the hardcoded default (`src/embeddings.py:38`, nothing set in `.env`). Missing model → 404 on `/v1/embeddings` → silent fallback to local FastEmbed (works, just a WARNING). Fix: `ollama pull all-minilm:l6-v2`.

**6. Memory Tidy timeout — was hardcoded 120s** (`services/memory/memory_extractor.py:554`, patched locally to 600). A thinking model on the full memory list needs ~5min (measured 316s) → all 3 retries timed out → misleading "502 Bad Gateway". Re-apply if the file is ever reset from upstream.

**7. Background tasks inherit the ACTIVE SESSION's model.** Resolution order: Task model → Utility model → current session's model → default.

**8. Loopback tool calls hit AirPlay on port 7000.** `internal_api_base()` fell back to `127.0.0.1:7000` — macOS ControlCenter (AirPlay Receiver) listens there and answers 403 → `trigger_research` etc. failed with "research/start returned HTTP 403". Patched 2026-07-16: the real bind port is now recorded from the first request's ASGI scope (`src/constants.py: set_runtime_bind_port`, hooked in `core/middleware.py`); no env needed. Alternative: set `APP_PORT` or `ODYSSEUS_INTERNAL_BASE`.

**9. One Ollama model can't serve agent + background jobs.** Ollama serializes requests per model, so auto-name and memory extraction queue behind agent rounds → 70s+ first token, ReadTimeout retries (auto-name failed 3×), agent stream 504 after 374s. Separately, thinking can burn the entire max_tokens budget → round ends with 0 chars + 0 tool calls and the task dies silently (this half now addressed — see "Thinking suppression for agent rounds — 2026-07-17" in [resolvedissues.md](resolvedissues.md)). Patched 2026-07-16: auto-name now rides the same sequential stream-idle queue as memory/skill extraction instead of a bare `_spawn_bg` (`routes/chat_helpers.py`; test `tests/test_kv_cache_invalidation_2927.py::test_auto_name_is_queued_through_sequential_gate`). Residual: the queue only gates job *start* — an ask_user pause counts as stream-idle, so a job launched while the user reads the question still contends with their reply. The Utility-model split ([todo.md](todo.md)) is the complete fix.

**10. `web_fetch` cannot reach your own LAN until you allow it.** `WEB_FETCH_BLOCK_PRIVATE_IPS=false` in `.env` (set 2026-07-27). Without it every loopback and RFC-1918 target is refused — `127.0.0.1` *and* `192.168.x.x`, so a local dev server and the ESP32 fail identically with `NetworkError: Blocked non-public IP literal`. Default stays `true` so exposed deployments are unaffected; see [resolvedissues.md](resolvedissues.md) "web_fetch could not reach the LAN". Note `load_dotenv()` does **not** override a variable already exported in the shell — check `echo $WEB_FETCH_BLOCK_PRIVATE_IPS` is empty if the setting appears to do nothing.

## Web search
- Odysseus queries SearXNG at `http://localhost:8080` (`SEARXNG_INSTANCE` in `.env`) with `format=json` — SearXNG must have the JSON format enabled (off by default).
- Native no-Docker setup: `searxng/settings.yml` + `searxng/start-searxng.sh` (clones, installs own venv, starts, verifies). **Wired into `start-macos.sh`** (probes :8080 first; first run clones + installs ~2 min; nohup, survives Ctrl+C).
- Fallback: the code imports `from ddgs import DDGS` — the package is **`ddgs`**, NOT `duckduckgo-search` (old package lacks the `ddgs` module; venv had duckduckgo_search 8.1.1 → import failed → flaky HTML scraping). `start-macos.sh` now auto-installs `ddgs` if missing, so venv rebuilds self-heal.
- Browser MCP (Playwright, `npx -y @playwright/mcp@latest`, 30 tools) registered — only needed for JS-heavy/interactive pages.
- PDF sources are silently skipped during extraction unless `pdfminer.six` is installed in the venv. Installed 2026-07-16; reinstall after any venv rebuild.

## `web_fetch` — what it sees, and what it silently reuses
Learned 2026-07-27 wiring an ESP32 on the LAN into a chat. Both halves cost a working session.

- **JavaScript is never executed, and `<script>`/`<style>` are dropped before the text is built.** A page can look complete in the browser and arrive as a shell. Values injected by JS, or delivered afterwards over a WebSocket, do not exist for a fetch — the ESP32 dashboard fetched as `Temperature 1 --  Humidity 1 --` for every field. **Anything the model must read has to be in the server-rendered markup**, and that includes API endpoints: given a page that didn't advertise its own `/api/state`, the 9B concluded no history endpoint existed and wrote that into a document as a finding.
- **Results are cached for 2 h under `sha(url + "#cap=" + budget)`.** Two consequences, both of which have already produced wrong conclusions:
  - `full: true` raises the download budget and therefore **changes the cache key**. The same URL fetched with and without `full` uses two independent entries and can return two different bodies in the same session.
  - ✅ **A cache hit is now labelled — fixed 2026-07-28.** It used to be indistinguishable from a live fetch in `tool_events` (same shape, same `exit_code`), and two fetches 4½ minutes apart both reported `uptime: 91 s` from the device although only the first had left the machine. A served-from-cache result now carries `cached: true`, `cached_at` and `cache_age_seconds`; `tool_events` persists them, and the tool output opens with *"served from cache, fetched N min M s ago — NOT a live reading"* so the model sees it too. **Absence of the flag means the fetch was live.** Older rows in `app.db` predate this and carry nothing either way.
- Inspect: `data/cache/content/*.cache`, fields `data.url` and `timestamp`. Clear: `rm -f data/cache/content/*.cache` — takes effect immediately, **no restart**, because the read path stats the file (`content.py`, `cache_file.exists()`); `content_cache_index` is only cleanup bookkeeping.
- ⚠️ **Never call `fetch_webpage_content()` against the live tree to test something.** It writes into the same cache the running instance reads. Doing exactly this on 2026-07-27 put a *fabricated* value into that cache, and the next chat turn served it to the model, which recorded it in a user document as a measurement. Test against a copy. The same script's `shutil.rmtree(CONTENT_CACHE_DIR)` was one permission bit away from deleting all 232 entries.

## Running the test suite
- **`./venv/bin/python -m pytest`** — the canonical invocation (`tests/README.md`). `pytest` and `pytest-asyncio` are in `requirements.txt`, so a working venv already has them; `pyproject.toml` sets `asyncio_mode = "auto"`, so async tests need no decorator plumbing.
- Focused slices via the taxonomy markers added at collection time: `-m area_security`, `-m "area_services and sub_cookbook"`. Fast lane is `-m "not slow"`. `tests/run_focus.py` validates area names before running.
- **Last measured on the M1, 2026-07-29: `2 failed, 5738 passed, 4 skipped` in 122 s — 5,744 collected.** Both failures are [todo.md](todo.md) item 18 and neither is an application bug. Taken after that day's 27 local commits and the 11 upstream commits merged into them. *(2026-07-28 gave 5588 passed; an earlier run the same day gave 5433, before ~1939 upstream commits arrived.)*
- ⚠️ **This is a measurement; the line it replaced was a prediction of ~5694/5711 and was 33 low** — upstream kept adding tests in between. **Re-measure and rewrite this line rather than adjusting it.** A count in prose is a claim with an expiry date and no test, and this file has carried a wrong one before: an earlier claim of "687 pass" was neither current nor true, and a 24-file subset measured on Linux gave "959 passed, 2 failed" while hiding all five macOS failures. *(The "~5613" that once stood here counted test functions, not collected cases — a parametrized test is one function and three cases.)*
- ⚠️ **A green suite here says nothing about what is committed.** `rootdir` is your working tree, where untracked files are present on disk; that is exactly how a committed `src/agent_loop.py` importing an untracked `src/known_facts.py` stayed green ([todo.md](todo.md) item 5). The separate check is `git clone ~/odysseus /tmp/x` and a first-party import sweep over the clone — seconds, no venv needed.
- ⚠️ **An agent in the Linux sandbox cannot run this suite at all.** `venv/` is a macOS/homebrew tree whose interpreter is a broken symlink from anywhere else, so a sandboxed agent falls back to system `python3 --noconftest` and gets environmental failures that look real. Any count it reports is per-file, not a suite result. See [`CLAUDE.md`](../CLAUDE.md).
- ⚠️ **A Linux run cannot substitute for a macOS run here.** Five failures exist *only* on macOS, and they are invisible on Linux for two environment reasons — the 104-byte `AF_UNIX` limit combined with macOS's deep `$TMPDIR`, and the `/var` → `/private/var` symlink. Both are spelled out in item 19. Run the suite on the machine you ship from.
- **`-m area_security` is not the security gate you'd assume.** It reported `654 passed` clean on the same tree where four docker-socket opt-in tests were failing. The taxonomy is *filename*-token based, so `test_shell_routes.py` and `test_cookbook_docker_access.py` land in `area_routes`/`area_services` despite testing a privilege gate. **A test's area marker reflects what its file is called, not what it protects.**
- **Some tests need working DNS.** `test_web_fetch_size_caps.py` fetches `https://example.com/…`; with no resolver the two-tier SSRF guard sees an empty address list and refuses, so all 8 fail with `Blocked non-public URL` — which looks like a guard regression and is not one. Check `getaddrinfo` before believing it.
- `conftest.py` imports the app, so *every* test needs the full dependency tree — even a test that only parses source with `ast`. A missing dep surfaces as a collection-time `ImportError` in `conftest.py`, not as a failure in the test you ran. `python-multipart`, `markdown` and `nh3` are easy ones to be missing after a venv rebuild.

## Reading `data/app.db` when debugging a run
Most of the diagnosis in [resolvedissues.md](resolvedissues.md) came from here, and two gotchas cost real time.

> ### ⚠️ The evidence base lives OUTSIDE this repo: `~/odysseus-snapshots/`
> `data/app.db` is gitignored, is in no commit and never will be, and
> `data/logs/app.log` **rotates** (`maxBytes=5MB, backupCount=3`, `app.py:107`) —
> three more rotations delete `app.log.1`, which holds the 17–28 July base. A
> snapshot tarball is the only thing protecting either. `git clean -fdx` takes
> the originals; keeping the copy outside the tree is what puts it beyond reach
> of any git command.
>
> - **Latest: `~/odysseus-snapshots/odysseus-evidence-2026-07-29.tar.gz`.**
> - Verify: `tar xzf …tar.gz && cd evidence-2026-07-29 && sha256sum -c SHA256SUMS.snapshot`
>   checks the archive. `SHA256SUMS.source` holds the same hashes under
>   repo-relative paths — run `sha256sum -c SHA256SUMS.source` **from the repo
>   root** to ask the different question of whether the originals still match.
> - **Verify by hash, never by `PRAGMA integrity_check`** — an intact database
>   that quietly lost a row passes that. Hash the source *before* the copy and
>   again *after*, so a mid-copy write is visible; do not import anything under
>   `src/` to read it (that runs migrations against the live file).
> - **Take a new one after any session worth reasoning about.** 2026-07-29's was
>   taken while the app was live: `app.db` grew 3,698,688 → 3,780,608 bytes in
>   ten minutes. It is internally consistent and it is not the latest state.
> - ⚠️ **A snapshot written to an agent's working folder is not a snapshot.**
>   Before 2026-07-29 these docs cited `outputs/snapshots/*.tar.gz`; no such
>   directory existed in the repo and no tarball existed anywhere on disk. The
>   path pointed at a scratchpad that gets cleared between sessions, so the file
>   the docs called the only protection had been gone for an unknown period
>   while every item went on citing it.

- ⚠️ **Check `data/logs/app.log` first.** It carries `[agent-timing] round_start / first_event / first_visible_token / round_stream_done` per round plus `stream_error` with the provider's own payload — and its timestamps are **local CEST while these rows are naive UTC**, so an empty window is usually the wrong two hours. [todo.md](todo.md) item 9b was diagnosed from one grep of it after a whole session of inferring mechanisms from these columns.
- **Copy the file before querying it.** The running app holds it (`data/app.db-journal` on disk is how you tell), a direct read can fail with `disk I/O error`, and importing app modules runs migrations against the real database. Rows also appear *late* — they are written on `save_sessions()`, so the newest row is not the last turn.

- **Timestamps are naive UTC** (`utcnow_naive` in `core/database.py`), while `ls`/`stat` report local CEST (UTC+2). Comparing a file mtime against a DB timestamp directly produced a two-hour error that made three post-fix sessions look like they predated the fix. **Convert before concluding anything about ordering.** Sanity check: the newest row should be ~2h behind the `app.db` file mtime. *(Canonical statement of this gotcha; [todo.md](todo.md) *Notes & constraints* points here.)*
- **`document_versions` holds full content for every version**, which is why document corruption is diagnosable at all — and why a destroyed document is recoverable. `documents.current_content` is only the latest.
- **Client-side writes are now labelled.** Every `source="user"` row carries which path produced it in `summary`: `Autosave`, `Autosave (email body)`, `Diff review — applied`, `Diff review — rejected all`, and so on. An unlabelled "Manual edit" means real typing. This identified a corruption in one query that a replay harness had failed to pin.
- **Two useful classifications of a `user` row:** byte-identical to some earlier version = a *revert*; identical to none = a *blend* (content merged from several generations). Both are bugs; they have different causes.
- **`command` is truncated to the first line** (`cmd_display`) — for document tools that is literally `<<<FIND>>>`. ✅ **Since 2026-07-28 document tool events also carry `full_command`**, the complete arguments, capped at 16 KB with an in-band truncation marker. Replay from `full_command`; `command` is only the display string. Rows written before that date have no `full_command` and are not replayable.
- **`round_texts` is the per-round text as the model wrote it, before the save path touched it.** Comparing it against the saved `content` is the one query that separates *"the model stopped writing"* from *"the save path deleted the answer"* — [todo.md](todo.md) items 8 and 6, which are indistinguishable from the message alone. ⚠️ Absent from zero-tool turns before 2026-07-28.
- **`stream_errors` means the request failed, not that it was slow.** A turn that 504s still records a plausible `response_time` and `tokens_per_second`; without this key those rows read as *slow generation* and three sessions of throughput analysis were built on them. Absence means the stream raised nothing. ⚠️ Not present before 2026-07-28.
- **`usage_source: estimated`** means no usage block came back — token counts are `len(text)//4`, so any tok/s derived from them is a guess. `real` means the provider reported them.
- Offline replay tooling for the editor's diff engine lives in `tests/tools/` (`diff_model.py`, `replay_blend_rows.py`) and runs against any `app.db` copy.

## Known quirks (safe to ignore)
- 404s on `/api/research/status/<id>` and `/api/chat/stream_status/<id>` = normal "nothing to resume" polling.
- Ollama log: `/opt/homebrew/var/log/ollama.log` (brew service, not `~/.ollama/logs/`). `ollama create` needs `-f <file>`, no stdin.
- Odysseus's "known context window 131072" is the model's max, not what Ollama loads — misleading when debugging truncation (root-caused and fixed; see [resolvedissues.md](resolvedissues.md): "Context-window mismatch").
- 8B-class models degrade when 24–36 tool schemas are sent at once — still true; current runs send 25–28. (The related "low-signal path strips write tools" bug is fixed — see [resolvedissues.md](resolvedissues.md), 2026-07-18.)
- `apfel` brew formula: no ARM bottle (only needed for Cookbook serving). SMTP/IMAP unconfigured (email features). `python-magic` missing = cosmetic.
- Skill-audit status feed cuts reasons mid-word — intentional truncation (`[:80]`/`[:100]` in `routes/skills_routes.py:819/836/865`). Full text is stored on the skill.

## Skills (learned 2026-07-16, BME280 end-to-end test)
- **Matching is Jaccard token overlap, threshold 0.3** — short natural queries ("What's the pinout of the BME280") score ~0.04 against a full skill text and never match. The escape hatch: single-word **tags** (pinout, voltage, specs…) force a match when the word appears in the query. Tag every skill with its trigger words.
- `manage_documents` has NO 'search' action — search is a parameter of action='list' (a wrong action in a skill procedure wastes a full round per attempt).
- Skill test harness ("Test this skill") can't validate web paths — its fallback tool set lacks web_search; test in a real chat instead.
