#!/usr/bin/env python3
"""How much does a system message change thinking on the direct reply path?

The direct low-signal path (src/agent_loop.py, after item 75 src/direct_reply.py)
sends the user's question ALONE. On 2026-10-09 Qwen 3.5 9B thought 7,000–12,100
chars for `explain` there, against 300–565 chars on the normal path with
Odysseus's system prompt (notes/todo.md item 76). This script asks the model
server directly, bypassing Odysseus, with four system-message variants:

  bare       the question alone (what the direct path sends today)
  brief      + "Answer directly and briefly; keep your reasoning short."
  offer      + brief + offer a web lookup when unsure or when the answer can change
  odysseus   + Odysseus's own native-tools system prompt with no tools (the
               normal path's text, minus the tool schemas)
  proposal_a / proposal_b  the maintainer's two leaner prompts (item 77; not run by default)
  odysseus_offer  odysseus + the lookup-offer rule (not run by default; the
               first probe, 2026-10-09 22:06, found the rule ignored on its own)

and three questions: one it should know (RAM vs flash), one it cannot know
(gold price right now), one obscure fact (who described Morchella elata, and
when: Elias Fries, 1822) where guessing is the failure.

Run with only that model's server up and Odysseus idle (nothing else on the
model). Standard library only; prints a table and writes JSON next to the
benchmark results.

  python3 scripts/probe_direct_reply.py --url http://localhost:1234 --model qwen/qwen3.5-9b
  python3 scripts/probe_direct_reply.py --url http://localhost:8090 --model bonsai2-27b --reps 1
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

BRIEF = "Answer directly and briefly; keep your reasoning short."
# Maintainer's proposals for a leaner system prompt (2026-10-09 23:11, notes/todo.md item 77).
PROPOSAL_A = """You are an AI assistant with native tool/function calling. Only the tool schemas provided by the API are available for this turn. Use native tool calls when action is needed; do not write tool syntax or tool instructions in chat.

## Available tools
none

## Base rules
- Prefer native tool/function calling when tools are needed.
- Only call tools when they materially help answer the request. For casual messages answer normally.
- You MUST use tools to take action; do not claim you did something without a tool result.
- If a needed tool/domain is missing from this turn, say what is missing briefly instead of pretending.
- Keep answers concise unless the user asks for depth.
- After a tool succeeds, do not second-guess it; reply with one short confirmation unless more work remains.
- After a tool fails, retry with a concrete fix or state what is blocking you.
- Finish only when the user's concrete request is actually done, or clearly state that you are blocked."""

PROPOSAL_B = """You are an AI assistant. No tools are available for this reply.

## Rules
- Answer directly. Settle on an answer once; do not second-guess it or go over it again.
- Keep answers concise unless asked for depth.
- If the answer needs a tool or current data you don't have, say so briefly instead of guessing."""

OFFER_RULE = ("- If the answer depends on information that changes over time (prices, versions, news) or on a "
              "specific name, date or number you are not certain of, say so in one sentence and offer to look it up "
              "on the web; do not guess.")
OFFER = (BRIEF + " If the answer depends on information that changes over time (prices, versions, news) "
         "or on a specific fact you are not sure of, say so in one sentence and offer to look it up "
         "on the web; do not guess.")

QUESTIONS = {
    "explain": ("In at most three sentences: what is the difference between RAM and flash memory on a "
                "microcontroller like the ESP32?"),
    "price_now": "What is the gold price right now, in US dollars per troy ounce?",
    "obscure": "Who first described the morel Morchella elata, and in which year?",
}

OFFER_RE = re.compile(r"look (it|this|that) up|search (the web|online|for)|web search|check (online|the web)|"
                      r"want me to|shall i|should i (look|search|check)|i can (look|search|check)", re.I)
HEDGE_RE = re.compile(r"not (sure|certain)|don't know|do not know|can't|cannot|unable|no access|real[- ]time|"
                      r"live (data|price)|knowledge cut-?off|may have changed|i believe|i think", re.I)


def odysseus_prompt():
    """The normal path's system prompt without tool schemas (needs the repo venv)."""
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")   # importing src touches the DB
    sys.path.insert(0, str(REPO))
    from src.agent_loop import _assemble_prompt
    return _assemble_prompt(set(), compact=True)


def ask(url, model, system, question, max_tokens, timeout):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": question}]
    body = json.dumps({"model": model, "messages": msgs, "max_tokens": max_tokens, "stream": False}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    wall = time.time() - t0
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    m = re.search(r"<think>(.*?)</think>", content, re.S)          # inline thinking, if not split out
    if m:
        reasoning += m.group(1)
        content = content[m.end():]
    usage = data.get("usage") or {}
    return {"wall_s": round(wall, 1), "completion_tokens": usage.get("completion_tokens"),
            "prompt_tokens": usage.get("prompt_tokens"), "thinking_chars": len(reasoning),
            "answer_chars": len(content.strip()), "answer": content.strip(),
            "finish": (data.get("choices") or [{}])[0].get("finish_reason"),
            "offers_lookup": bool(OFFER_RE.search(content)), "hedges": bool(HEDGE_RE.search(content)),
            "fries_1822": bool(re.search(r"fries", content, re.I) and "1822" in content)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", required=True, help="model server base URL, e.g. http://localhost:1234")
    ap.add_argument("--model", required=True)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--variants", default="bare,brief,offer,odysseus")
    ap.add_argument("--questions", default=",".join(QUESTIONS))
    ap.add_argument("--max-tokens", type=int, default=4096, help="same as the direct path's default (item 75)")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    systems = {"bare": "", "brief": BRIEF, "offer": OFFER, "proposal_a": PROPOSAL_A, "proposal_b": PROPOSAL_B}
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    if {"odysseus", "odysseus_offer"} & set(variants):
        try:
            systems["odysseus"] = odysseus_prompt()
            systems["odysseus_offer"] = systems["odysseus"].rstrip() + "\n" + OFFER_RULE
        except Exception as e:                                  # system python without the venv
            print(f"skipping the odysseus variants ({type(e).__name__}: {e}); run with ./venv/bin/python")
            variants = [v for v in variants if not v.startswith("odysseus")]

    rows = []
    for q in [x.strip() for x in args.questions.split(",") if x.strip()]:
        for v in variants:
            for rep in range(1, args.reps + 1):
                print(f"{q:10} {v:9} r{rep} … ", end="", flush=True)
                try:
                    r = ask(args.url, args.model, systems[v], QUESTIONS[q], args.max_tokens, args.timeout)
                except Exception as e:
                    r = {"error": f"{type(e).__name__}: {e}"}
                r.update({"question": q, "variant": v, "rep": rep})
                rows.append(r)
                print(r.get("error") or f"{r['wall_s']:6.1f} s  think {r['thinking_chars']:6}  "
                      f"answer {r['answer_chars']:4}  offer={r['offers_lookup']} hedge={r['hedges']}"
                      + (f" fries1822={r['fries_1822']}" if q == "obscure" else ""))

    print("\nmedian per question × variant (seconds / thinking chars):")
    for q in dict.fromkeys(r["question"] for r in rows):
        cells = []
        for v in variants:
            ok = [r for r in rows if r["question"] == q and r["variant"] == v and "error" not in r]
            if ok:
                ws = sorted(r["wall_s"] for r in ok)
                th = sorted(r["thinking_chars"] for r in ok)
                cells.append(f"{v}: {ws[len(ws) // 2]:.0f} s / {th[len(th) // 2]}")
        print(f"  {q:10} " + " | ".join(cells))

    out = REPO / "data" / "bench" / "probe" / (dt.datetime.now().strftime("%Y%m%d-%H%M%S")
                                              + "-" + re.sub(r"\W+", "_", args.model) + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"url": args.url, "model": args.model, "systems": systems, "rows": rows}, indent=2))
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
