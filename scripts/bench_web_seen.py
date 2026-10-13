#!/usr/bin/env python3
"""What did the model see? Scores the web_search results saved in benchmark runs
with the live relevance filter's model, after the run.

Why: in a filter A/B (`bench_chain.sh filter-ab`) the filter scores nothing in
its off arm, so pass rates alone cannot say how much off-topic material
reached the model in either arm. This scores every result each web_search
showed the model, in both arms, with the same reranker and threshold as
src/web_filter.py, and reports the share below the threshold per arm and task.
Separate from the run, so it adds nothing to the timed turns.

  ./venv/bin/python scripts/bench_web_seen.py data/bench/agent/2026101*-qwen35lm-filter*-webhard \
      --out data/bench/agent/report-web-seen.md

"Below threshold" is the filter's own junk proxy, not a label: on the 888
hand-checked results of 2026-10-12 it is what the filter drops (notes:
items/82-web-relevance-filter.md, *Fourth run*). Runs recorded before
bench_agent.py kept the whole web_search output (2026-10-13) have only its
first 300 characters and are counted as unreadable.

Needs fastembed (Odysseus's requirements) and the model in data/fastembed_cache
(downloaded on first use, 1.1 GB, already there when the filter has run live).
"""
import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_web_filter import (  # noqa: E402
    MULTILINGUAL_RERANKER, Reranker, domain_of, parse_command_query, parse_search_output, result_passage,
)

THRESHOLD = 0.035      # src/web_filter.py DEFAULTS["web_filter_threshold"], the live setting


def load_runs(dirs):
    """All task-run records of the given run folders."""
    recs = []
    for d in dirs:
        p = Path(d) / "results.jsonl"
        if not p.exists():
            print(f"skip {d}: no results.jsonl", file=sys.stderr)
            continue
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                r["_run"] = Path(d).name
                recs.append(r)
    return recs


def searches_of(rec):
    """(query, results) per successful web_search the model was shown, and how
    many successful searches could not be read (output saved cut short)."""
    out, unreadable = [], 0
    commands = [t.get("command") for t in rec.get("tools", []) if t.get("tool") == "web_search"]
    n = 0
    for x in rec.get("tool_results", []):
        if x.get("tool") != "web_search":
            continue
        cmd = commands[n] if n < len(commands) else ""
        n += 1
        if str(x.get("exit_code")) not in ("0", "None"):
            continue
        query, results = parse_search_output(x.get("output") or "")
        query = query or parse_command_query(cmd)
        if not results or not query:
            unreadable += 1
            continue
        out.append((query, results))
    return out, unreadable


def score_all(recs, scorer):
    """Attach `_seen` = [{query, results: [{..., score}]}] to every record."""
    cache = {}
    for r in recs:
        seen, r["_unreadable"] = searches_of(r)
        r["_seen"] = []
        for query, results in seen:
            todo = [res for res in results if (query, res["url"]) not in cache]
            if todo:
                for res, v in zip(todo, scorer.score(query, [result_passage(x) for x in todo])):
                    cache[(query, res["url"])] = v
            r["_seen"].append({"query": query,
                               "results": [dict(res, score=cache[(query, res["url"])]) for res in results]})
    return recs


def arm_stats(recs, threshold):
    shown = [res for r in recs for s in r["_seen"] for res in s["results"]]
    low = [res for res in shown if res["score"] < threshold]
    searches = [s for r in recs for s in r["_seen"]]
    any_low = [s for s in searches if any(res["score"] < threshold for res in s["results"])]
    none_ok = [s for s in searches if all(res["score"] < threshold for res in s["results"])]
    saw_low = [r for r in recs if any(res["score"] < threshold for s in r["_seen"] for res in s["results"])]
    return {
        "task_runs": len(recs), "passed": sum(bool(r.get("passed")) for r in recs),
        "searches": len(searches), "unreadable": sum(r["_unreadable"] for r in recs),
        "shown": len(shown), "low": len(low),
        "searches_any_low": len(any_low), "searches_none_ok": len(none_ok),
        "median_score": statistics.median([res["score"] for res in shown]) if shown else None,
        "runs_saw_low": len(saw_low), "runs_saw_low_passed": sum(bool(r.get("passed")) for r in saw_low),
    }


def pct(k, n):
    return f"{k}/{n} ({100 * k / n:.0f} %)" if n else "–"


def report(recs, threshold, examples=12):
    arms = defaultdict(list)
    for r in recs:
        arms[r.get("target") or "?"].append(r)
    names = sorted(arms)
    st = {a: arm_stats(arms[a], threshold) for a in names}
    lines = [f"# What the model saw in web searches (threshold {threshold})", "",
             "Runs: " + ", ".join(sorted({r['_run'] for r in recs})), "",
             "Every result a web_search showed the model, scored afterwards with the live filter's "
             f"reranker against the search query. *Below threshold* = what the filter would drop "
             "(its junk proxy, not a label).", "",
             "| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]

    def row(label, f):
        lines.append(f"| {label} | " + " | ".join(f(st[a]) for a in names) + " |")

    row("Task runs passed", lambda s: pct(s["passed"], s["task_runs"]))
    row("Web searches read", lambda s: f"{s['searches']}" + (f" (+{s['unreadable']} unreadable)" if s["unreadable"] else ""))
    row("Results shown to the model", lambda s: str(s["shown"]))
    row("**Results below threshold**", lambda s: "**" + pct(s["low"], s["shown"]) + "**")
    row("Searches with ≥ 1 result below", lambda s: pct(s["searches_any_low"], s["searches"]))
    row("Searches with nothing above (fail-open)", lambda s: pct(s["searches_none_ok"], s["searches"]))
    row("Median score of shown results", lambda s: f"{s['median_score']:.3f}" if s["median_score"] is not None else "–")
    row("Task runs that saw ≥ 1 below — passed", lambda s: pct(s["runs_saw_low_passed"], s["runs_saw_low"]))

    tasks = sorted({r.get("task") for r in recs})
    lines += ["", "## By task: results below threshold / shown", "",
              "| task | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for t in tasks:
        cells = []
        for a in names:
            s = arm_stats([r for r in arms[a] if r.get("task") == t], threshold)
            cells.append(f"{s['low']}/{s['shown']} · {s['passed']}/{s['task_runs']} passed" if s["task_runs"] else "–")
        lines.append(f"| {t} | " + " | ".join(cells) + " |")

    lines += ["", f"## Lowest-scoring results shown (up to {examples} per arm)", ""]
    for a in names:
        low = sorted(((res["score"], r.get("task"), s["query"], res) for r in arms[a] for s in r["_seen"]
                      for res in s["results"] if res["score"] < threshold), key=lambda x: x[0])[:examples]
        lines.append(f"**{a}**" + ("" if low else ": none"))
        for score, task, query, res in low:
            lines.append(f"- {score:.3f} · {task} · *{query[:80]}* → {res.get('title', '')[:80]} ({domain_of(res.get('url', ''))})")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("dirs", nargs="+", help="benchmark run folders (data/bench/agent/…)")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--model", default=MULTILINGUAL_RERANKER)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    recs = load_runs(args.dirs)
    if not recs:
        sys.exit("no task runs found")
    text = report(score_all(recs, Reranker(args.model)), args.threshold)
    if args.out:
        args.out.write_text(text + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(text)


if __name__ == "__main__":
    main()
