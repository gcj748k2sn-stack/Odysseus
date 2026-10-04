#!/usr/bin/env python3
"""Benchmark Qwen3.5-9B on LM Studio MLX vs LM Studio GGUF (llama.cpp) vs Ollama.

Why: docs/qwensetup.md (LM Studio endpoint, "Speed vs Ollama") measured MLX
prefill at 142-156 tok/s against Ollama's 217-233 on this M1 Pro, and
Odysseus's own tok/s figure cannot compare the two. This script sends the
SAME prompts to each backend and times them the same way.

What it measures, per request (client side, streaming):
  * prefill tok/s = prompt_tokens / time to the first streamed token
  * decode tok/s  = (completion_tokens - 1) / (last token - first token)
Every request starts with a fresh random run id, so no prompt cache can help.
The first request after each load is a warm-up and is not counted.

Usage (from the repo root, LM Studio app or service running):
  python3 scripts/bench_qwen_backends.py                # auto-detect models
  python3 scripts/bench_qwen_backends.py --list         # show what it finds
  python3 scripts/bench_qwen_backends.py --lms-key qwen/qwen3.5-9b --label lms-gguf --ollama-model ''
      (a hub model loads the variant selected in My Models; "@" variant keys
       are not loadable with `lms load`, so switch the variant there and re-run)
  python3 scripts/bench_qwen_backends.py --check-64k    # + LM Studio's 64k estimate

Side effects: unloads every LM Studio model and the Ollama model before it
starts and when it ends (Odysseus re-loads on the next chat). Do not chat in
Odysseus while it runs. Writes results to bench_qwen_<timestamp>.json.
Standard library only.
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LMS_URL = "http://localhost:1234"
OLLAMA_URL = "http://localhost:11434"


# ── helpers ──────────────────────────────────────────────────────────────────
def http_json(url, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "null")


def reachable(url):
    try:
        urllib.request.urlopen(url, timeout=3).read()
        return True
    except Exception:
        return False


def lms_bin():
    p = shutil.which("lms") or str(Path.home() / ".lmstudio" / "bin" / "lms")
    return p if Path(p).exists() else None


def run(cmd, timeout=600):
    print("  $", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    out = (p.stdout + p.stderr).strip()
    return p.returncode, out


def build_prompt(target_tokens):
    """~target_tokens of real repo prose (docs), plus a question. Fresh run id first."""
    text = ""
    for f in sorted((REPO / "docs").glob("*.md")):
        text += f.read_text(encoding="utf-8", errors="ignore") + "\n\n"
    if not text:
        text = "The quick brown fox jumps over the lazy dog. " * 5000
    while len(text) < target_tokens * 4:
        text += text
    body = text[: int(target_tokens * 3.6)]
    return [
        {"role": "system", "content": f"Run id {uuid.uuid4()}. You are a concise assistant."},
        {"role": "user", "content": body + "\n\nSummarise the text above in three short bullet points."},
    ]


def stream_once(base, model, messages, max_tokens):
    payload = {
        "model": model, "messages": messages, "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": 0, "max_tokens": max_tokens,
    }
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    t_first = t_last = None
    chunks, usage = 0, None
    with urllib.request.urlopen(req, timeout=1800) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                ev = json.loads(data)
            except ValueError:
                continue
            if ev.get("usage"):
                usage = ev["usage"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                if any(d.get(k) for k in ("content", "reasoning_content", "reasoning")) or d.get("tool_calls"):
                    now = time.perf_counter()
                    t_first = t_first or now
                    t_last = now
                    chunks += 1
    t_end = time.perf_counter()
    if t_first is None:
        raise RuntimeError("no tokens streamed")
    pt = (usage or {}).get("prompt_tokens")
    ct = (usage or {}).get("completion_tokens") or chunks
    ttft = t_first - t0
    gen = (t_last - t_first) if t_last and t_last > t_first else None
    return {
        "prompt_tokens": pt, "completion_tokens": ct, "chunks": chunks,
        "usage_reported": usage is not None,
        "ttft_s": round(ttft, 2), "total_s": round(t_end - t0, 2),
        "prefill_tps": round(pt / ttft, 1) if pt and ttft > 0 else None,
        "decode_tps": round((ct - 1) / gen, 1) if gen and ct > 1 else None,
    }


# ── LM Studio model discovery ────────────────────────────────────────────────
def find_lms_models(lms):
    """Return [(key, fmt, label)] for downloaded models that look like Qwen3.5-9B."""
    out = None
    for args in (["ls", "--json", "--variants"], ["ls", "--json"]):
        p = subprocess.run([lms, *args], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            try:
                out = json.loads(p.stdout)
                break
            except ValueError:
                pass
    found = []

    def walk(o):
        if isinstance(o, dict):
            key = o.get("modelKey") or o.get("key") or o.get("indexedModelIdentifier")
            blob = json.dumps({k: v for k, v in o.items() if not isinstance(v, (dict, list))}).lower()
            if isinstance(key, str) and "qwen3.5" in blob and "9b" in blob:
                fmt = str(o.get("format") or "").lower()
                if not fmt:
                    fmt = "gguf" if "gguf" in blob else ("mlx" if ("mlx" in blob or "safetensors" in blob) else "?")
                if fmt == "safetensors":
                    fmt = "mlx"
                found.append((key, fmt, o.get("displayName") or o.get("path") or key))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(out)
    seen, uniq = set(), []
    for k, f, l in found:
        if (k, f) not in seen:
            seen.add((k, f))
            uniq.append((k, f, l))
    return uniq, out


def lms_loaded_context(identifier):
    try:
        data = http_json(LMS_URL + "/api/v1/models")
        for m in data.get("models") or []:
            for inst in m.get("loaded_instances") or []:
                if inst.get("id") == identifier:
                    cfg = inst.get("config") or {}
                    return cfg.get("context_length") or inst.get("context_length")
    except Exception:
        pass
    return None


def lms_loaded_entry(identifier):
    """Top-level fields of the /api/v1/models entry holding ``identifier`` (shows format/variant if listed)."""
    try:
        for m in http_json(LMS_URL + "/api/v1/models").get("models") or []:
            if any(i.get("id") == identifier for i in m.get("loaded_instances") or []):
                return {k: v for k, v in m.items() if not isinstance(v, (list, dict))}
    except Exception as e:
        return f"unavailable: {e}"
    return None


def ollama_unload(model):
    if model and reachable(OLLAMA_URL + "/api/version"):
        try:
            http_json(OLLAMA_URL + "/api/generate", {"model": model, "keep_alive": 0}, timeout=60)
        except Exception:
            pass


# ── benchmark ────────────────────────────────────────────────────────────────
def bench(name, base, model, sizes, runs, max_tokens):
    print(f"\n== {name}: warm-up")
    try:
        w = stream_once(base, model, build_prompt(200), 16)
        print(f"   warm-up ok ({w['total_s']} s)")
    except Exception as e:
        print(f"   warm-up FAILED: {e}")
        return []
    rows = []
    for size in sizes:
        for i in range(runs):
            try:
                r = stream_once(base, model, build_prompt(size), max_tokens)
            except Exception as e:
                print(f"   ~{size} tok run {i + 1}: FAILED {e}")
                continue
            r.update(backend=name, target=size, run=i + 1)
            rows.append(r)
            print(f"   ~{size} tok run {i + 1}: prompt {r['prompt_tokens']} | ttft {r['ttft_s']} s | "
                  f"prefill {r['prefill_tps']} tok/s | decode {r['decode_tps']} tok/s | total {r['total_s']} s")
    return rows


def summary(rows):
    print("\n" + "=" * 86)
    print(f"{'backend':<14}{'~size':>7}{'prompt tok':>12}{'ttft s':>9}{'prefill tok/s':>15}{'decode tok/s':>14}{'total s':>9}")
    keys = []
    for r in rows:
        k = (r["backend"], r["target"])
        if k not in keys:
            keys.append(k)
    med = lambda xs: round(statistics.median(xs), 1) if xs else None
    for b, t in keys:
        g = [r for r in rows if r["backend"] == b and r["target"] == t]
        pick = lambda f: med([r[f] for r in g if r.get(f) is not None])
        print(f"{b:<14}{t:>7}{str(pick('prompt_tokens')):>12}{str(pick('ttft_s')):>9}"
              f"{str(pick('prefill_tps')):>15}{str(pick('decode_tps')):>14}{str(pick('total_s')):>9}")
    print("=" * 86 + "\n(medians; prefill = prompt / time-to-first-token, decode = after the first token)")
    if any(not r.get("usage_reported") for r in rows):
        print("NOTE: some backends sent no token usage; their counts are streamed chunks, approximate.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mlx-key"), ap.add_argument("--gguf-key")
    ap.add_argument("--lms-key", help="benchmark just this LM Studio key (e.g. the bare hub key, which "
                    "loads whichever variant is selected in My Models); label it with --label")
    ap.add_argument("--label", default="lms", help="name for --lms-key in the results")
    ap.add_argument("--ollama-model", default="qwen3.5:9b-64k", help="'' to skip Ollama")
    ap.add_argument("--context", type=int, default=32768)
    ap.add_argument("--sizes", default="2000,8000", help="approx prompt sizes in tokens")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--check-64k", action="store_true", help="also ask LM Studio for a 65536 load estimate")
    ap.add_argument("--list", action="store_true", help="only list detected models")
    ap.add_argument("--no-lmstudio", action="store_true")
    ap.add_argument("--endpoint", action="append", default=[], metavar="NAME,URL,MODEL",
                    help="extra OpenAI-compatible endpoint, benchmarked as-is (no loading)")
    a = ap.parse_args()
    sizes = [int(s) for s in a.sizes.split(",") if s.strip()]
    rows, plan, notes = [], [], {}

    lms = None
    if not a.no_lmstudio:
        lms = lms_bin()
        if not lms:
            sys.exit("lms CLI not found (expected ~/.lmstudio/bin/lms). Open LM Studio once.")
        if not reachable(LMS_URL + "/api/v1/models"):
            print("LM Studio server is not running - starting it")
            print("  ", run([lms, "server", "start"])[1])
        cands, raw = find_lms_models(lms)
        print("Detected Qwen3.5-9B models in LM Studio:")
        for k, f, l in cands:
            print(f"  [{f:>4}] {k}   ({l})")
        if not cands:
            print("  none - run `lms ls` to see what is downloaded")
        if a.list:
            return
        # `lms load` only accepts top-level keys. A hub model ("qwen/qwen3.5-9b") with
        # several downloaded variants ("…@4bit", "…@q4_k_m") loads whichever variant is
        # selected for it in LM Studio's My Models; the "@" keys are not loadable.
        if a.lms_key:
            plan.append((a.label, a.lms_key))
        elif a.mlx_key or a.gguf_key:
            plan += [("lms-mlx", a.mlx_key), ("lms-gguf", a.gguf_key)]
        else:
            bare = next((k for k, _, _ in cands if "@" not in k), None)
            if bare:
                print(f"\nBenchmarking {bare} = the variant selected in My Models. To compare the other "
                      f"variant, select it there and re-run with --lms-key {bare} --label lms-<format>.")
                plan.append(("lms-selected", bare))

    ollama_unload(a.ollama_model)
    if lms:
        run([lms, "unload", "-a"])

    for name, key in plan:
        if not key:
            continue
        ident = f"bench-{name}"
        if a.check_64k:
            code, out = run([lms, "load", key, "-c", "65536", "--estimate-only", "-y"])
            notes[f"{name} 65536 estimate"] = out
            print("   " + out.replace("\n", "\n   "))
        code, out = run([lms, "load", key, "-c", str(a.context), "--identifier", ident, "--gpu", "max", "-y"])
        if code != 0:
            print(f"   load FAILED ({code}):\n   {out}")
            notes[f"{name} load"] = out
            continue
        ctx = lms_loaded_context(ident)
        print(f"   loaded {key} as {ident}, context {ctx}")
        engine = lms_loaded_entry(ident)
        print(f"   LM Studio's entry for it: {engine}")
        notes[f"{name} entry"] = engine
        notes[f"{name} key"] = key
        notes[f"{name} context"] = ctx
        rows += bench(name, LMS_URL, ident, sizes, a.runs, a.max_tokens)
        run([lms, "unload", "-a"])

    if a.ollama_model:
        if reachable(OLLAMA_URL + "/api/version"):
            rows += bench("ollama", OLLAMA_URL, a.ollama_model, sizes, a.runs, a.max_tokens)
            ollama_unload(a.ollama_model)
        else:
            print("\nOllama not reachable on :11434 - skipped")

    for spec in a.endpoint:
        name, url, model = spec.split(",", 2)
        rows += bench(name, url.rstrip("/"), model, sizes, a.runs, a.max_tokens)

    if rows:
        summary(rows)
        out = Path.cwd() / f"bench_qwen_{time.strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps({"args": vars(a), "notes": notes, "rows": rows}, indent=2))
        print(f"Saved {out}")
    for k, v in notes.items():
        if "estimate" in k or "load" in k:
            print(f"\n{k}:\n{v}")


if __name__ == "__main__":
    main()
