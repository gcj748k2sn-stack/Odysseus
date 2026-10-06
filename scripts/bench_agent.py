#!/usr/bin/env python3
"""Agent benchmark through Odysseus: same tasks, same harness, different models.

Why: llama-bench / LM Studio stats measure the model server; Hermes's eval
environments measure the model inside Hermes. Neither says which model works
best inside *this* Odysseus — with its prompts, tool selection, and the
thinking/tool-round handling in src/agent_loop.py. This script drives the real
/api/chat_stream in agent mode, exactly as the browser does, and checks the
outcome (answer text, files on disk, notes/events/documents via the API).

Tasks live in scripts/bench_agent_tasks.py (18 tasks, 8 in --quick; `tasks` lists them).

USAGE (from the repo root, Odysseus running, nobody else chatting):

  export ODYSSEUS_PASSWORD='…'                      # login user defaults to cedrik
  python3 scripts/bench_agent.py targets            # list endpoint ids + models
  python3 scripts/bench_agent.py preflight --target bonsai2   # what is loaded, SearXNG, n_ctx
  caffeinate -i python3 scripts/bench_agent.py run --target bonsai2 --runs 2
  python3 scripts/bench_agent.py run --target qwen35 --runs 2
  python3 scripts/bench_agent.py report data/bench/agent/2*

  --target NAME is a preset below, or NAME=ENDPOINT_ID:MODEL_ID for anything else.
  --runs N repeats every task N times (default 1). --tasks a,b,c picks tasks.
  --resume DIR continues an interrupted run directory.

Run ONE target per invocation, and only that model's server loaded: Bonsai 2
on llama-server and Qwen in LM Studio together do not fit in memory without
swapping, and swapping is what you'd be measuring.

WHAT IT CHANGES
  * Creates one chat session per task run (named "[bench] …") and deletes it
    afterwards. Turns are sent INCOGNITO: no memory/skill extraction, no
    memory injection, so runs do not pollute your memory or each other, and
    no background extraction competes with the next task for the model.
  * Notes, calendar events and documents the tasks create carry a unique
    marker like "[bench-3f9a]" and are deleted through the API after the
    check (use --keep to leave them). `cleanup` sweeps leftovers.
  * Fixtures and results go to data/bench/agent/<run-id>/ (data/ is gitignored).

REPORT
  `report` reads results.jsonl from each run dir and joins data/logs/app.log*
  by time window for per-round numbers (empty answers after tool rounds,
  prompt-cache hits, prefill speed, tools Odysseus actually offered). The log
  is local time, and so are the windows recorded here — same machine, same
  clock, no offset to add.

Standard library only; Python 3.9+.
"""
import argparse
import datetime as dt
import glob
import http.cookiejar
import json
import math
import os
import re
import statistics
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_agent_tasks as T  # noqa: E402

# start-macos.sh serves on 7860 (macOS AirPlay Receiver holds 7000 and answers 403).
DEFAULT_URL = os.environ.get("ODYSSEUS_URL") or "http://localhost:%s" % (
    os.environ.get("ODYSSEUS_PORT") or os.environ.get("APP_PORT") or "7860")
DEFAULT_USER = os.environ.get("ODYSSEUS_USER", "cedrik")
RESULTS_ROOT = REPO / "data" / "bench" / "agent"
# Task fixtures live OUTSIDE data/: since the 2026-10-06 merge Odysseus refuses
# any workspace under its data directory except data/agent_workspace/ & co.
# (`_is_app_state_path` in vet_workspace), so a data/bench workspace came back
# `workspace_rejected` and the file tools refused every path (first full run,
# 2026-10-06 21:22). A plain folder in $HOME is what a user would bind.
WS_ROOT = Path(os.environ.get("BENCH_WS_ROOT") or Path.home() / "odysseus-bench")

# Endpoint ids from this machine's model_endpoints table (2026-10-05).
# `bench_agent.py targets` prints the current ones.
PRESETS = {
    "bonsai2": ("ed1cd41c", "bonsai2-27b"),        # Bonsai 2 (llama.cpp :8090)
    "qwen35": ("a5179555", "qwen/qwen3.5-9b"),     # LM Studio :1234
}

# A server that cannot answer at all is not a model result: unreachable,
# LM Studio's broken-copy "Compute error" (2026-10-06 11:25), any HTTP 5xx.
# An HTTP 400 such as "exceeds the available context size" stays a result.
SERVER_FAULT_RE = re.compile(r"Cannot reach|Compute error|['\"]status['\"]: ?5\d\d|HTTP 5\d\d")
# ...except Odysseus's own 502 for a model that produced nothing: that one is
# the model's result (2026-10-06 21:5x, Bonsai 2 on `german`).
MODEL_EMPTY_RE = re.compile(r"empty response", re.I)


def is_server_fault(err):
    return bool(SERVER_FAULT_RE.search(err)) and not MODEL_EMPTY_RE.search(err)
APPROVAL_WAIT = "Waiting for an exact user approval"   # src/agent_loop.py placeholder output
TASK_TIMEOUT_S = 20 * 60      # whole turn; Bonsai 2 rounds reach 300 s at p90
READ_IDLE_S = 960             # Odysseus's own per-round timeout is 900 s


# ── HTTP client ────────────────────────────────────────────────────────────

class Api:
    def __init__(self, base, user, password):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.user, self.password = user, password

    def _req(self, method, path, form=None, js=None, params=None, timeout=60):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data, headers = None, {}
        if js is not None:
            data, headers["Content-Type"] = json.dumps(js).encode(), "application/json"
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return urllib.request.Request(url, data=data, headers=headers, method=method), timeout

    def call(self, method, path, form=None, js=None, params=None, timeout=60):
        req, timeout = self._req(method, path, form, js, params, timeout)
        try:
            with self.opener.open(req, timeout=timeout) as r:
                body = r.read().decode() or "null"
        except urllib.error.HTTPError as e:
            hint = ""
            if "AirTunes" in (e.headers.get("Server") or ""):
                hint = " — that is macOS AirPlay Receiver, not Odysseus; use --url http://localhost:7860"
            raise RuntimeError(f"{method} {path} → HTTP {e.code}: {e.read().decode(errors='replace')[:300]}{hint}")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return body

    def get(self, path, params=None):
        return self.call("GET", path, params=params)

    def post(self, path, form=None, js=None):
        return self.call("POST", path, form=form, js=js)

    def delete(self, path):
        return self.call("DELETE", path)

    def login(self):
        if not self.password and sys.stdin.isatty():
            # Login is by password: API tokens run as the 'api' user, for whom
            # Odysseus drops the workspace and file confinement.
            import getpass
            self.password = getpass.getpass(f"Odysseus password for {self.user}: ")
        if not self.password:
            sys.exit("error: no password — set ODYSSEUS_PASSWORD, or run from a terminal to be asked.")
        try:
            r = self.post("/api/auth/login", js={"username": self.user, "password": self.password})
        except (RuntimeError, OSError) as e:
            sys.exit(f"error: login to {self.base} failed — is Odysseus running, password right? {e}")
        if not (isinstance(r, dict) and r.get("ok")):
            sys.exit(f"error: login failed: {r}")

    def stream(self, path, form, on_line, timeout=READ_IDLE_S):
        req, _ = self._req("POST", path, form=form)
        with self.opener.open(req, timeout=timeout) as r:
            for raw in r:
                on_line(raw.decode("utf-8", errors="replace").rstrip("\r\n"))


# ── one task run ───────────────────────────────────────────────────────────

def now_local():
    return dt.datetime.now().isoformat(timespec="milliseconds")


def run_one(api, task, target, rep, run_dir, args):
    name, (endpoint_id, model) = target
    marker = "[bench-%s]" % uuid.uuid4().hex[:4]
    ws = WS_ROOT / run_dir.name / f"{task['id']}-{name}-r{rep}"
    ws.mkdir(parents=True, exist_ok=True)
    ctx = {"ws": str(ws.resolve()), "marker": marker, "api": api}
    ctx["expect"] = task["setup"](ctx["ws"], ctx) or {}
    prompt = task["prompt"](ctx)

    rec = {"task": task["id"], "cat": task["cat"], "target": name, "model": model,
           "endpoint_id": endpoint_id, "rep": rep, "marker": marker, "prompt": prompt,
           "expect": ctx["expect"], "status": "ok", "error": None,
           "text": "", "final_text": "", "thinking_chars": 0, "tools": [], "tool_results": [],
           "rounds": 0, "flags": [], "events": {}, "metrics": {}}

    sess = api.post("/api/session", form={"name": f"[bench] {task['id']} {name} r{rep}",
                                          "endpoint_id": endpoint_id, "model": model})
    sid = ctx["session"] = rec["session"] = sess["id"]

    form = {"message": prompt, "session": sid, "mode": "agent", "incognito": "true",
            "allow_bash": "true" if task["bash"] else "false",
            "allow_web_search": "true" if task["web"] else "false",
            "workspace": ctx["ws"]}

    state = {"event": None, "t0": time.time(), "first_text": None, "stream_rounds": 0, "approval": None}
    final_parts, all_parts = [], []
    rec["approvals"] = []

    def on_line(line):
        if not line:
            state["event"] = None
            return
        if line.startswith("event: "):
            state["event"] = line[7:].strip()
            return
        if not line.startswith("data: "):
            return
        payload = line[6:]
        if payload == "[DONE]":
            rec["events"]["done"] = rec["events"].get("done", 0) + 1
            return
        try:
            d = json.loads(payload)
        except json.JSONDecodeError:
            return
        if state["event"] == "error":
            rec["flags"].append("stream_error")
            rec.setdefault("stream_errors", []).append(str(d)[:300])
            return
        if not isinstance(d, dict):
            return
        if "delta" in d:
            if d.get("thinking"):
                rec["thinking_chars"] += len(d["delta"])
            else:
                if state["first_text"] is None:
                    state["first_text"] = time.time() - state["t0"]
                all_parts.append(d["delta"])
                final_parts.append(d["delta"])
            return
        typ = d.get("type")
        rec["events"][typ] = rec["events"].get(typ, 0) + 1
        if typ == "tool_start":
            rec["tools"].append({"tool": d.get("tool"), "round": d.get("round"),
                                 "command": str(d.get("full_command") or d.get("command") or "")[:400]})
        elif typ == "tool_output" and APPROVAL_WAIT in str(d.get("output") or ""):
            pass                         # the card's placeholder, not a tool result
        elif typ == "tool_output":
            rec["tool_results"].append({"tool": d.get("tool"), "exit_code": d.get("exit_code"),
                                        "output": str(d.get("output") or "")[:300]})
            final_parts.clear()          # text after the last tool result is the answer
        elif typ == "agent_step":
            state["stream_rounds"] = max(state["stream_rounds"], int(d.get("round") or 0))
        elif typ == "ask_user" and (d.get("data") or {}).get("kind") == "tool_approval":
            card = d.get("data") or {}
            state["approval"] = card
            # Odysseus streams the card's question as assistant text so the
            # model sees it next turn; it is not part of the model's answer.
            q = (card.get("question") or "").strip()
            for parts in (all_parts, final_parts):
                if parts and parts[-1].strip() == q:
                    parts.pop()
        elif typ == "agent_terminal":
            t = d.get("data") or {}
            if t.get("failed"):
                rec["flags"].append("agent_terminal_failed")
                rec.setdefault("stream_errors", []).append(str(t.get("failure"))[:300])
        elif typ == "metrics":
            m = d.get("data") or {}
            rec["metrics"] = {k: m.get(k) for k in (
                "model", "requested_model", "response_time", "time_to_first_token", "tokens_per_second",
                "prefill_tps", "input_tokens", "output_tokens", "request_context_tokens",
                "context_length", "finish_reasons", "stream_errors")}
        elif typ in ("rounds_exhausted", "budget_exceeded", "loop_breaker_triggered",
                     "intent_nudge_exhausted", "ask_user", "workspace_rejected"):
            rec["flags"].append(typ)
        elif typ == "fallback":
            rec["flags"].append("fallback")
            rec["answered_by"] = d.get("answered_by")

    stopper = threading.Timer(args.task_timeout, lambda: _stop(api, sid, rec))
    stopper.daemon = True
    rec["start"] = now_local()
    stopper.start()
    try:
        while True:
            state["approval"], state["stream_rounds"] = None, 0
            api.stream("/api/chat_stream", form, on_line)
            rec["rounds"] += state["stream_rounds"]
            card = state["approval"]
            if not card or rec.get("timed_out"):
                break
            # Since the 2026-10-06 upstream merge, reading a workspace file or
            # fetching a page arms the untrusted-context gate, and the next
            # write/edit/bash stops on an approval card. A person would click
            # "Allow for this task"; the benchmark does the same — the
            # narrowest scope that lets the request finish — and counts it.
            if len(rec["approvals"]) >= args.max_approvals:
                rec["flags"].append("approval_limit")
                break
            rec["approvals"].append({"approval_id": card.get("approval_id"), "after_s": round(time.time() - state["t0"], 1),
                                     "description": str(card.get("description") or "")[:200],
                                     "decision": args.approval})
            if args.approval == "deny":
                rec["flags"].append("approval_denied")
            form = {"message": "", "session": sid, "incognito": "true", "mode": "agent",
                    "tool_approval_id": card.get("approval_id"), "tool_approval_decision": args.approval}
            if args.approval == "deny":
                api.stream("/api/chat_stream", form, on_line)
                break
    except Exception as e:
        rec["status"], rec["error"] = "http_error", f"{type(e).__name__}: {e}"[:400]
    finally:
        stopper.cancel()
    rec["end"] = now_local()
    rec["wall_s"] = round(time.time() - state["t0"], 2)
    rec["ttft_visible_s"] = round(state["first_text"], 2) if state["first_text"] is not None else None
    rec["text"] = "".join(all_parts).strip()
    rec["final_text"] = "".join(final_parts).strip()
    if rec.get("timed_out"):
        rec["status"] = "timeout"

    try:
        results = task["checks"](rec, ctx)
    except Exception as e:
        results = [("checker crashed", False, f"{type(e).__name__}: {e}")]
    rec["checks"] = [{"name": n, "ok": ok, "detail": det if not ok else ""} for n, ok, det in results]
    rec["passed"] = rec["status"] == "ok" and all(c["ok"] for c in rec["checks"]) \
        and "fallback" not in rec["flags"]

    if not args.keep:
        if task.get("cleanup"):
            try:
                task["cleanup"](ctx)
            except Exception as e:
                rec["cleanup_error"] = str(e)[:200]
        try:
            api.post(f"/api/session/{sid}/delete")
        except Exception as e:
            rec["cleanup_error"] = str(e)[:200]
    return rec


def _stop(api, sid, rec):
    rec["timed_out"] = True
    try:
        api.post(f"/api/chat/stop/{sid}")
    except Exception:
        pass


# ── commands ───────────────────────────────────────────────────────────────

def parse_target(spec):
    if spec in PRESETS:
        return spec, PRESETS[spec]
    m = re.fullmatch(r"([\w.-]+)=([^:]+):(.+)", spec)
    if not m:
        sys.exit(f"error: --target {spec!r}: use a preset ({', '.join(PRESETS)}) or NAME=ENDPOINT_ID:MODEL_ID")
    return m.group(1), (m.group(2), m.group(3))


def select_tasks(args):
    tasks = T.TASKS
    if args.quick:
        tasks = [t for t in tasks if t["quick"]]
    if args.tasks:
        want = [x.strip() for x in args.tasks.split(",") if x.strip()]
        unknown = set(want) - set(T.TASK_IDS)
        if unknown:
            sys.exit(f"error: unknown task(s) {sorted(unknown)}; known: {', '.join(T.TASK_IDS)}")
        tasks = [t for t in T.TASKS if t["id"] in want]
    return tasks


def lint_prompts(tasks):
    """A non-web task whose prompt reads as web intent gets its file tools
    removed by chat_stream — refuse to run it rather than report a model failure."""
    fake = {"ws": "/x", "marker": "[bench-0000]", "expect": {}, "session": "s", "api": None}
    bad = []
    for t in tasks:
        m = T.WEB_INTENT_RE.search(t["prompt"](fake))
        if m and not t["web"]:
            bad.append(f"{t['id']}: '{m.group(0)}'")
    if bad:
        sys.exit("error: these prompts trigger Odysseus's web-intent rule and would lose their file tools:\n  "
                 + "\n  ".join(bad))


def probe(url, timeout=4):
    """GET a local server's JSON; None when it is not there."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode() or "null")
    except Exception:
        return None


def git_head():
    """HEAD commit without running git (no index lock; see CLAUDE.md §6)."""
    try:
        head = (REPO / ".git" / "HEAD").read_text().strip()
        if not head.startswith("ref: "):
            return head[:12]
        ref = head[5:]
        p = REPO / ".git" / ref
        if p.exists():
            return f"{ref.rsplit('/', 1)[-1]}@{p.read_text().strip()[:12]}"
        for line in (REPO / ".git" / "packed-refs").read_text().splitlines():
            if line.endswith(" " + ref):
                return f"{ref.rsplit('/', 1)[-1]}@{line[:12]}"
    except OSError:
        pass
    return None


LMS_ROOT, OLLAMA_ROOT = "http://localhost:1234", "http://localhost:11434"


def preflight(api, target, tasks):
    """Record the serving setup and warn about what would distort the run.
    Returns (env, warnings). Everything here is read-only."""
    name, (endpoint_id, model) = target
    env, warn = {"checked": now_local(), "git_head": git_head()}, []
    eps = api.get("/api/model-endpoints")
    eps = eps.get("endpoints", eps) if isinstance(eps, dict) else eps
    base = next((ep.get("base_url") for ep in eps or [] if ep.get("id") == endpoint_id), None)
    if not base:
        sys.exit(f"error: endpoint {endpoint_id} not found in Odysseus — run `targets`")
    root = re.sub(r"/v1/?$", "", base.rstrip("/"))
    env["endpoint_base"] = base

    props = probe(root + "/props")                       # llama.cpp server
    if isinstance(props, dict) and "default_generation_settings" in props:
        gen = props.get("default_generation_settings") or {}
        params = gen.get("params") or {}
        env["llamacpp"] = {
            "model_path": props.get("model_path"), "build_info": props.get("build_info"),
            "n_ctx": gen.get("n_ctx"), "total_slots": props.get("total_slots"),
            "params": {k: v for k, v in params.items() if isinstance(v, (int, float, str, bool)) and k in (
                "temperature", "top_k", "top_p", "min_p", "n_predict", "reasoning_format",
                "reasoning_budget", "reasoning_in_content", "chat_format", "cache_prompt", "n_keep")},
        }

    lms = probe(LMS_ROOT + "/api/v0/models")
    lms_loaded = [m for m in (lms or {}).get("data", []) if m.get("state") == "loaded"]
    env["lmstudio_loaded"] = [{k: m.get(k) for k in ("id", "quantization", "compatibility_type",
                                                    "loaded_context_length", "max_context_length") if k in m}
                              for m in lms_loaded]
    oll = probe(OLLAMA_ROOT + "/api/ps")
    env["ollama_loaded"] = [m.get("name") for m in (oll or {}).get("models", [])]

    on_lms, on_ollama = root.startswith(LMS_ROOT), root.startswith(OLLAMA_ROOT)
    others = [m["id"] for m in lms_loaded if not (on_lms and m["id"] == model)]
    if others:
        warn.append(f"LM Studio has {', '.join(others)} loaded — it competes for memory with {name}. "
                    "Unload: `lms unload --all`" + (f", then `lms load {model}`" if on_lms else ""))
    if env["ollama_loaded"] and not on_ollama:
        warn.append(f"Ollama has {', '.join(env['ollama_loaded'])} loaded — `ollama stop <model>`")
    if not props and not on_lms and not on_ollama:
        warn.append(f"{root}/props did not answer — is the llama.cpp server for {name} up?")
    if not root.startswith("http://localhost:8090") and probe("http://localhost:8090/props", 2):
        warn.append("llama-server on :8090 (Bonsai 2) is running — it holds ~9–10 GB; stop it for a fair run")

    try:
        stale = [n.get("title") for n in api.get("/api/notes").get("notes", []) if "[bench-" in (n.get("title") or "")]
    except Exception:
        stale = []
    if stale:
        warn.append(f"{len(stale)} bench note(s) left from earlier runs ({stale[0]!r}…) — `bench_agent.py cleanup`")

    if any(t["web"] for t in tasks):
        sx = os.environ.get("SEARXNG_INSTANCE", "http://localhost:8080").rstrip("/")
        t0 = time.time()
        res = probe(sx + "/search?" + urllib.parse.urlencode({"q": "Eiffel Tower", "format": "json"}), 15)
        env["searxng"] = {"url": sx, "ok": bool(res and res.get("results")),
                          "results": len((res or {}).get("results", [])), "seconds": round(time.time() - t0, 1)}
        if not env["searxng"]["ok"]:
            warn.append(f"SearXNG at {sx} returned no results — web tasks would fail for environment reasons")
    return env, warn


def show_preflight(env, warn):
    lc = env.get("llamacpp")
    if lc:
        print(f"  llama.cpp: {os.path.basename(lc.get('model_path') or '?')}, n_ctx {lc.get('n_ctx')}, "
              f"build {lc.get('build_info')}, params {lc.get('params')}")
    if env.get("lmstudio_loaded"):
        print(f"  LM Studio loaded: {env['lmstudio_loaded']}")
    if env.get("ollama_loaded"):
        print(f"  Ollama loaded: {env['ollama_loaded']}")
    if env.get("searxng"):
        print(f"  SearXNG: {env['searxng']}")
    print(f"  Odysseus HEAD: {env.get('git_head')}")
    for w in warn:
        print(f"  ⚠️  {w}")


def cmd_preflight(args):
    tasks = select_tasks(args)
    lint_prompts(tasks)
    target = parse_target(args.target)
    api = Api(args.url, args.user, os.environ.get("ODYSSEUS_PASSWORD", ""))
    api.login()
    env, warn = preflight(api, target, tasks)
    print(f"preflight for {target[0]} ({len(tasks)} tasks):")
    show_preflight(env, warn)
    print("ok" if not warn else f"{len(warn)} warning(s)")


def cmd_run(args):
    tasks = select_tasks(args)
    lint_prompts(tasks)
    target = parse_target(args.target)
    api = Api(args.url, args.user, os.environ.get("ODYSSEUS_PASSWORD", ""))
    api.login()
    env, warn = preflight(api, target, tasks)
    print(f"preflight for {target[0]}:")
    show_preflight(env, warn)
    if warn and not args.yes:
        print("starting in 15 s despite the warning(s) above — Ctrl-C to abort (--yes skips this wait)", flush=True)
        time.sleep(15)

    if args.resume:
        run_dir = Path(args.resume)
        meta = json.loads((run_dir / "meta.json").read_text())
        if meta["target"] != target[0]:
            sys.exit(f"error: {run_dir} is a run of {meta['target']}, not {target[0]}")
        meta.setdefault("env_resumed", []).append(dict(env, warnings=warn))
    else:
        run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + target[0]
        run_dir, n = RESULTS_ROOT / run_id, 1
        while run_dir.exists():                 # two starts in one second
            n += 1
            run_dir = RESULTS_ROOT / f"{run_id}-{n}"
        run_dir.mkdir(parents=True)
        meta = {"target": target[0], "endpoint_id": target[1][0], "model": target[1][1],
                "runs": args.runs, "tasks": [t["id"] for t in tasks], "started": now_local(),
                "url": args.url, "host": os.uname().nodename, "env": dict(env, warnings=warn)}
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    out = run_dir / "results.jsonl"
    done = set()
    if out.exists():
        for l in out.read_text().splitlines():
            r = json.loads(l)
            done.add((r["task"], r["rep"]))

    print(f"run dir: {run_dir}")
    if not args.no_warmup and not done:
        print("warm-up (untimed, loads the model)…", flush=True)
        try:
            s = api.post("/api/session", form={"name": "[bench] warm-up", "endpoint_id": target[1][0],
                                               "model": target[1][1]})
            seen = {"err": None, "prev": ""}

            def watch(line):
                if seen["prev"] == "event: error" and line.startswith("data: "):
                    seen["err"] = line[6:]
                seen["prev"] = line
            api.stream("/api/chat_stream", {"message": "Reply with the word OK.", "session": s["id"],
                                            "mode": "chat", "incognito": "true"}, watch)
            api.post(f"/api/session/{s['id']}/delete")
        except Exception as e:
            sys.exit(f"error: warm-up failed — is the model server up? {e}")
        if seen["err"]:
            sys.exit(f"error: warm-up got an error from the model, not running the suite: {seen['err'][:300]}")

    todo = [(t, rep) for rep in range(1, args.runs + 1) for t in tasks if (t["id"], rep) not in done]
    for i, (t, rep) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {t['id']} r{rep} … ", end="", flush=True)
        try:
            rec = run_one(api, t, target, rep, run_dir, args)
        except Exception as e:
            rec = {"task": t["id"], "cat": t["cat"], "target": target[0], "model": target[1][1], "rep": rep,
                   "status": "harness_error", "error": f"{type(e).__name__}: {e}", "passed": False,
                   "trace": traceback.format_exc()[-1500:], "checks": [], "tools": [], "flags": []}
        if "workspace_rejected" in rec.get("flags", []):
            sys.exit(f"\nerror: Odysseus rejected the task workspace ({WS_ROOT}); result not saved. Every file "
                     "task would fail for harness reasons. Set BENCH_WS_ROOT to a plain folder outside "
                     f"Odysseus's data/ directory, then continue with --resume {run_dir}")
        infra = [e for e in rec.get("stream_errors", []) if is_server_fault(e)]
        if infra:
            sys.exit(f"\nerror: the model server failed, not the model ({infra[0][:160]}); result not saved.\n"
                     f"Fix the server (LM Studio 'Compute error': `lms unload --all && lms load <model>`), "
                     f"then continue with --resume {run_dir}")
        with out.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fails = [c["name"] for c in rec.get("checks", []) if not c["ok"]]
        print(("PASS" if rec["passed"] else "FAIL") + f"  {rec.get('wall_s', '-')} s"
              + (f"  [{rec['status']}]" if rec["status"] != "ok" else "")
              + (f"  ({', '.join(sorted(set(rec['flags'])))})" if rec.get("flags") else "")
              + (f"  [{len(rec['approvals'])} approval(s)]" if rec.get("approvals") else "")
              + (f"  ✗ {'; '.join(fails)}" if fails else ""), flush=True)
    meta["finished"] = now_local()
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"\nnext: python3 scripts/bench_agent.py report {run_dir}")


def cmd_targets(args):
    api = Api(args.url, args.user, os.environ.get("ODYSSEUS_PASSWORD", ""))
    api.login()
    eps = api.get("/api/model-endpoints")
    eps = eps.get("endpoints", eps) if isinstance(eps, dict) else eps
    for ep in eps or []:
        print(f"{ep.get('id')}  {ep.get('name')}  {ep.get('base_url')}")
        try:
            ms = api.get(f"/api/model-endpoints/{ep.get('id')}/models")
            ms = ms.get("models", ms) if isinstance(ms, dict) else ms
            for m in ms or []:
                print("      " + (m.get("id") if isinstance(m, dict) else str(m)))
        except Exception as e:
            print(f"      (models unavailable: {str(e)[:80]})")
    print("\npresets: " + ", ".join(f"{k}={v[0]}:{v[1]}" for k, v in PRESETS.items()))


def cmd_cleanup(args):
    api = Api(args.url, args.user, os.environ.get("ODYSSEUS_PASSWORD", ""))
    api.login()
    n = 0
    for note in api.get("/api/notes").get("notes", []):
        if "[bench-" in (note.get("title") or ""):
            api.delete(f"/api/notes/{note['id']}"); n += 1
    today = dt.date.today()
    evs = api.get("/api/calendar/events", params={"start": f"{today - dt.timedelta(days=30)}T00:00:00",
                                                  "end": f"{today + dt.timedelta(days=60)}T00:00:00"})
    for ev in evs.get("events", []):
        if "[bench-" in (ev.get("summary") or ""):
            api.delete(f"/api/calendar/events/{ev['uid']}"); n += 1
    sess = api.get("/api/sessions")
    sess = sess.get("sessions", sess) if isinstance(sess, dict) else sess
    for s in sess or []:
        if (s.get("name") or "").startswith("[bench]"):
            for d in api.get(f"/api/documents/{s['id']}") or []:
                api.delete(f"/api/document/{d['id']}"); n += 1
            api.post(f"/api/session/{s['id']}/delete"); n += 1
    print(f"removed {n} bench leftovers (notes, events, documents, sessions)")


# ── report ─────────────────────────────────────────────────────────────────

LOG_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) ")


def load_log(log_glob):
    lines = []
    for path in glob.glob(log_glob):
        with open(path, encoding="utf-8", errors="replace") as f:
            for l in f:
                if ("[agent-timing]" in l or "[agent-debug]" in l or "produced no answer" in l
                        or "direct low-signal reply path" in l):
                    m = LOG_TS.match(l)
                    if m:
                        ts = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(
                            microsecond=int(m.group(2)) * 1000)
                        lines.append((ts, l))
    lines.sort(key=lambda x: x[0])
    return lines


def _kv(line, key, cast=str):
    m = re.search(r"\b%s=(\S+)" % re.escape(key), line)
    if not m or m.group(1) == "?":
        return None
    try:
        return cast(m.group(1))
    except ValueError:
        return None


def log_rounds(log, start, end):
    """Per-round facts from app.log inside [start, end] (local time)."""
    s = dt.datetime.fromisoformat(start)
    e = dt.datetime.fromisoformat(end)
    rounds, offered, no_answer, direct = [], set(), False, False
    for ts, l in log:
        if ts < s or ts > e:
            continue
        if "tool_names=[" in l:
            offered.update(re.findall(r"'([^']+)'", l.split("tool_names=", 1)[1].split("]", 1)[0]))
        elif "round_stream_done" in l:
            rounds.append({k: _kv(l, k, c) for k, c in (
                ("round", int), ("elapsed", lambda x: float(x.rstrip("s"))), ("text_chars", int),
                ("tool_calls", int), ("finish_reason", str), ("prompt_tokens", int), ("cache_n", int),
                ("prompt_n", int), ("prompt_ms", float))})
        elif "produced no answer" in l:
            no_answer = True
        elif "direct low-signal reply path" in l:
            direct = True        # Odysseus answered without offering any tool
    return rounds, offered, no_answer, direct


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def fmt(x, nd=0, suf=""):
    if x is None:
        return "–"
    return f"{x:.{nd}f}{suf}"


def cmd_report(args):
    recs, metas = [], {}
    for d in args.dirs:
        p = Path(d) / "results.jsonl"
        if not p.exists():
            print(f"skip {d}: no results.jsonl", file=sys.stderr)
            continue
        recs += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        try:
            m = json.loads((Path(d) / "meta.json").read_text())
            metas.setdefault(m["target"], []).append(m)
        except (OSError, ValueError, KeyError):
            pass
    if not recs:
        sys.exit("no results")
    log = load_log(args.log)
    task_tools = {t["id"]: t["tools"] for t in T.TASKS}

    # Windows are clipped to the next run's start, so a fast task never picks up
    # the following task's first round.
    timed = sorted((r for r in recs if r.get("start") and r.get("end")), key=lambda r: r["start"])
    for a, b in zip(timed, timed[1:] + [None]):
        a["_win_end"] = min(a["end"], b["start"]) if b else a["end"]
    for r in recs:
        if r.get("start") and r.get("end"):
            rounds, offered, no_ans, direct = log_rounds(log, r["start"], r["_win_end"])
        else:
            rounds, offered, no_ans, direct = [], set(), False, False
        r["_rounds"], r["_offered"], r["_no_answer_log"], r["_direct"] = rounds, offered, no_ans, direct
        need = task_tools.get(r["task"]) or []
        r["_harness_miss"] = bool(need) and ((bool(offered) and not (set(need) & offered)) or direct)

    targets = sorted({r["target"] for r in recs})
    by = {t: [r for r in recs if r["target"] == t] for t in targets}
    L = []
    L.append(f"# Odysseus agent benchmark — {dt.datetime.now():%Y-%m-%d %H:%M}\n")
    L.append("Runs: " + ", ".join(f"**{t}** ({by[t][0]['model']}, {len(by[t])} task runs)" for t in targets) + "\n")
    env_lines = []
    for t in targets:
        for m in metas.get(t, []):
            e = m.get("env") or {}
            bits = [f"started {m.get('started', '?')[:16]}", f"Odysseus {e.get('git_head') or '?'}"]
            lc = e.get("llamacpp")
            if lc:
                bits.append(f"llama.cpp `{os.path.basename(lc.get('model_path') or '?')}` n_ctx {lc.get('n_ctx')}, "
                            f"build {lc.get('build_info')}, params {lc.get('params')}")
            if e.get("lmstudio_loaded"):
                bits.append("LM Studio loaded " + ", ".join(
                    f"{x.get('id')} ({x.get('quantization', '?')}, ctx {x.get('loaded_context_length', '?')})"
                    for x in e["lmstudio_loaded"]))
            if e.get("ollama_loaded"):
                bits.append("Ollama loaded " + ", ".join(e["ollama_loaded"]))
            if e.get("searxng"):
                bits.append("SearXNG " + ("ok" if e["searxng"].get("ok") else "**not answering**"))
            if e.get("warnings"):
                bits.append("⚠️ " + " / ".join(e["warnings"]))
            env_lines.append(f"- **{t}**: " + "; ".join(bits))
    if env_lines:
        L.append("Setup at the start of each run:\n")
        L += env_lines
        L.append("")

    L.append("## Summary\n")
    L.append("| | " + " | ".join(targets) + " |")
    L.append("|---|" + "---|" * len(targets))

    def row(label, f):
        L.append(f"| {label} | " + " | ".join(f(by[t]) for t in targets) + " |")

    def passrate(rs):
        k, n = sum(r["passed"] for r in rs), len(rs)
        lo, hi = wilson(k, n)
        return f"**{k}/{n}** ({100 * k / n:.0f} %, 95 % CI {100 * lo:.0f}–{100 * hi:.0f})"

    env_re = re.compile(r"timed out|HTTP [45]\d\d|Cannot reach|Connection (refused|reset)", re.I)

    def env_hit(r):
        return any(str(x.get("exit_code")) not in ("0", "None") and env_re.search(x.get("output") or "")
                   for x in r.get("tool_results", []))

    common = set.intersection(*[{r["task"] for r in by[t]} for t in targets])
    row("Tasks passed", passrate)
    if any({r["task"] for r in by[t]} != common for t in targets):
        row("Tasks passed — only tasks every model ran", lambda rs: passrate([r for r in rs if r["task"] in common]))
    row("Tasks passed — runs hit by environment errors left out",
        lambda rs: passrate([r for r in rs if not env_hit(r)]) if any(not env_hit(r) for r in rs) else "–")
    row("Median time per task", lambda rs: fmt(med([r.get("wall_s") for r in rs]), 0, " s"))
    row("Total time", lambda rs: fmt(sum(r.get("wall_s") or 0 for r in rs) / 60, 0, " min"))
    row("Median agent rounds", lambda rs: fmt(med([r.get("rounds") for r in rs]), 1))
    row("Median tool calls", lambda rs: fmt(med([len(r.get("tools", [])) for r in rs]), 1))
    def failed_tools(rs):
        bad = [x for r in rs for x in r.get("tool_results", []) if str(x.get("exit_code")) not in ("0", "None")]
        env = sum(1 for x in bad if env_re.search(x.get("output") or ""))
        return "%d of %d (%d environment: timeouts, HTTP errors)" % (
            len(bad), sum(len(r.get("tool_results", [])) for r in rs), env)
    row("Failed tool calls", failed_tools)
    row("Empty final answer", lambda rs: "%d" % sum(
        1 for r in rs if r.get("status") == "ok" and not (r.get("final_text") or "").strip()))
    row("Timeouts / HTTP errors", lambda rs: "%d / %d" % (
        sum(r.get("status") == "timeout" for r in rs),
        sum(r.get("status") in ("http_error", "harness_error") for r in rs)))
    row("Stream errors / model request failed", lambda rs: str(sum(
        any(f in r.get("flags", []) for f in ("stream_error", "agent_terminal_failed")) for r in rs)))
    row("Approval cards answered (task runs with ≥1)", lambda rs: "%d (%d)" % (
        sum(len(r.get("approvals") or []) for r in rs), sum(1 for r in rs if r.get("approvals"))))
    row("Model asked the user (no one answers)", lambda rs: str(sum("ask_user" in r.get("flags", []) for r in rs)))
    row("Rounds/budget exhausted, loop breaker", lambda rs: str(sum(
        any(f in r.get("flags", []) for f in ("rounds_exhausted", "budget_exceeded", "loop_breaker_triggered"))
        for r in rs)))
    row("⚠️ Answered by a fallback model", lambda rs: str(sum("fallback" in r.get("flags", []) for r in rs)))
    row("Task tool not offered by Odysseus (incl. no-tools reply path)", lambda rs: str(sum(r["_harness_miss"] for r in rs)))

    # per-round numbers from app.log
    def rounds(rs):
        return [x for r in rs for x in r["_rounds"]]
    row("Log: rounds seen", lambda rs: str(len(rounds(rs))))
    row("Log: median round time", lambda rs: fmt(med([x["elapsed"] for x in rounds(rs)]), 0, " s"))
    row("Log: empty rounds after a tool round", lambda rs: (lambda after: "%d of %d" % (
        sum(1 for x in after if not x["text_chars"] and not x["tool_calls"]), len(after)))(
        [x for x in rounds(rs) if (x.get("round") or 1) > 1]))
    row("Log: prompt-cache hit", lambda rs: (lambda xs: fmt(
        100 * sum(x["cache_n"] for x in xs) / max(1, sum(x["prompt_tokens"] for x in xs)), 0, " %")
        if xs else "–")([x for x in rounds(rs) if x.get("cache_n") is not None and x.get("prompt_tokens")]))
    row("Log: prefill speed (uncached)", lambda rs: fmt(med([
        1000 * x["prompt_n"] / x["prompt_ms"] for x in rounds(rs) if x.get("prompt_n") and x.get("prompt_ms")]),
        0, " tok/s"))
    L.append("")
    if not log:
        L.append(f"_No agent-timing lines matched `{args.log}` — run `report` on the Odysseus machine._\n")

    L.append("## By category\n")
    cats = sorted({r["cat"] for r in recs})
    L.append("| category | " + " | ".join(targets) + " |")
    L.append("|---|" + "---|" * len(targets))
    for c in cats:
        L.append(f"| {c} | " + " | ".join(
            "%d/%d" % (sum(r["passed"] for r in by[t] if r["cat"] == c), sum(1 for r in by[t] if r["cat"] == c))
            for t in targets) + " |")
    L.append("")

    L.append("## By task\n")
    L.append("| task | " + " | ".join(targets) + " |")
    L.append("|---|" + "---|" * len(targets))
    for tid in [t for t in T.TASK_IDS if any(r["task"] == t for r in recs)]:
        cells = []
        for t in targets:
            rs = [r for r in by[t] if r["task"] == tid]
            if not rs:
                cells.append("–")
                continue
            k = sum(r["passed"] for r in rs)
            cells.append(f"{'✅' if k == len(rs) else ('❌' if k == 0 else '🟡')} {k}/{len(rs)} · "
                         f"{fmt(med([r.get('wall_s') for r in rs]), 0)} s")
        L.append(f"| {tid} | " + " | ".join(cells) + " |")
    L.append("")

    L.append("## Failures\n")
    any_fail = False
    for r in sorted(recs, key=lambda r: (r["target"], T.TASK_IDS.index(r["task"]) if r["task"] in T.TASK_IDS else 99, r["rep"])):
        if r["passed"]:
            continue
        any_fail = True
        why = [c["name"] + (f" — {c['detail']}" if c.get("detail") else "") for c in r.get("checks", []) if not c["ok"]]
        extra = []
        if r.get("status") != "ok":
            extra.append(f"status {r['status']}: {r.get('error') or ''}".strip())
        if r.get("flags"):
            extra.append("flags: " + ", ".join(sorted(set(r["flags"]))))
        if r["_direct"]:
            extra.append("Odysseus took its direct low-signal reply path — no tools were offered at all")
        elif r["_harness_miss"]:
            extra.append(f"Odysseus never offered {task_tools[r['task']]} (offered: {sorted(r['_offered'])})")
        if r["_no_answer_log"]:
            extra.append("log: 'gathered information but produced no answer'")
        tools = " → ".join(x["tool"] or "?" for x in r.get("tools", [])) or "no tools"
        if r.get("approvals"):
            tools += f"; {len(r['approvals'])} approval card(s) answered"
        L.append(f"- **{r['target']} · {r['task']} r{r['rep']}** ({r.get('wall_s', '–')} s, {tools})")
        for w in why + extra:
            L.append(f"  - {w}")
    if not any_fail:
        L.append("None.")
    L.append("")
    n_per = min(len(v) for v in by.values())
    L.append("## Reading this\n")
    L.append(f"- With {n_per} task runs per model, a pass-rate gap smaller than the confidence intervals is noise. "
             "`--runs 3` triples the time and narrows them.")
    L.append("- Every turn ran in incognito: no memory or skills context, which differs from your normal chats "
             "on purpose (reproducible, and no background extraction competing for the model).")
    L.append("- A failure with *tool not offered* is Odysseus's tool selection, not the model.")
    L.append("- Approval cards (Odysseus's untrusted-context gate since the 2026-10-06 merge) were answered "
             "automatically with *Allow for this task*; they cost a round trip, not points. The count shows how "
             "often a model's tool sequence hits the gate.")
    L.append("- Sampling settings are whatever each endpoint gets with no preset (Bonsai 2 relies on the "
             "no-preset `temp=1.0`, see notes/todo.md).")

    text = "\n".join(L) + "\n"
    if args.out:
        Path(args.out).write_text(text)
        print(f"wrote {args.out}", file=sys.stderr)
    print(text)


# ── main ───────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--user", default=DEFAULT_USER)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the task suite against one model")
    r.add_argument("--target", required=True, help="preset (%s) or NAME=ENDPOINT_ID:MODEL_ID" % ", ".join(PRESETS))
    r.add_argument("--quick", action="store_true", help="8-task subset")
    r.add_argument("--tasks", help="comma-separated task ids")
    r.add_argument("--runs", type=int, default=1)
    r.add_argument("--resume", help="continue this run directory")
    r.add_argument("--keep", action="store_true", help="keep sessions/notes/events/documents")
    r.add_argument("--no-warmup", action="store_true")
    r.add_argument("--approval", choices=["approve_task", "deny"], default="approve_task",
                   help="answer to approval cards (default approve_task, as a person finishing the task would)")
    r.add_argument("--max-approvals", type=int, default=4, help="per task run, then stop (default 4)")
    r.add_argument("--yes", action="store_true", help="do not pause on preflight warnings (unattended runs)")
    r.add_argument("--task-timeout", type=int, default=TASK_TIMEOUT_S)
    r.set_defaults(func=cmd_run)

    p = sub.add_parser("report", help="summarise one or more run directories")
    p.add_argument("dirs", nargs="+")
    p.add_argument("--log", default=str(REPO / "data" / "logs" / "app.log*"))
    p.add_argument("--out", help="also write the markdown here")
    p.set_defaults(func=cmd_report)

    pf = sub.add_parser("preflight", help="check the serving setup for a run without running it")
    pf.add_argument("--target", required=True)
    pf.add_argument("--quick", action="store_true")
    pf.add_argument("--tasks")
    pf.set_defaults(func=cmd_preflight)
    sub.add_parser("targets", help="list endpoint ids and models").set_defaults(func=cmd_targets)
    sub.add_parser("cleanup", help="delete [bench] leftovers").set_defaults(func=cmd_cleanup)
    sub.add_parser("tasks", help="list tasks").set_defaults(func=lambda a: [
        print(f"{t['id']:16} {t['cat']:10} {'quick' if t['quick'] else '':6}"
              f"{'bash ' if t['bash'] else ''}{'web' if t['web'] else ''}") for t in T.TASKS])

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
