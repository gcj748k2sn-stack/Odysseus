"""scripts/bench_web_seen.py: scores what each web_search showed the model and
reports the share below the filter threshold per arm, with negative controls
(nothing below → nothing reported) and old cut-short records counted, not read.
A fake scorer stands in for the reranker; the real one is not loaded here.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("bench_web_seen_under_test", ROOT / "scripts" / "bench_web_seen.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def search_output(query, results, notice=""):
    # Same layout as comprehensive_web_search in services/search/core.py.
    lines = ["=" * 70, "WEB SEARCH RESULTS AND FETCHED CONTENT", f"Query: {query}",
             f"Searched {len(results)} results, fetched 0 pages", "=" * 70, "",
             "SEARCH RESULTS SUMMARY:", "-" * 50]
    if notice:
        lines.append(notice)
    for i, (title, url) in enumerate(results, 1):
        lines += [f"\n[{i}] {title}", f"    URL: {url}", f"    Snippet: about {title}..."]
    lines += ["", "=" * 70, "Instructions: ..."]
    return "\n".join(lines)


class FakeScorer:
    """Scores a passage by a keyword: 'singer' or 'lingerie' → junk."""

    def __init__(self):
        self.calls = 0

    def score(self, query, passages):
        self.calls += 1
        return [0.001 if ("singer" in p.lower() or "lingerie" in p.lower()) else 0.6 for p in passages]


def rec(target, task, outputs, passed=True, exit_code=0):
    return {"target": target, "task": task, "passed": passed, "_run": "run",
            "tools": [{"tool": "web_search", "command": "q"} for _ in outputs],
            "tool_results": [{"tool": "web_search", "exit_code": exit_code, "output": o} for o in outputs]}


PINK = [("Pink oyster mushroom fruiting", "https://fungi.com/pink"),
        ("Pink (singer) – Wikipedia", "https://en.wikipedia.org/wiki/Pink_(singer)"),
        ("Pleurotus djamor grow guide", "https://northspore.com/djamor")]
CLEAN = [("Pink oyster mushroom fruiting", "https://fungi.com/pink"),
         ("Pleurotus djamor grow guide", "https://northspore.com/djamor")]


def test_counts_off_topic_results_per_arm():
    recs = [rec("qwen35lm-filteroff", "wh_pink", [search_output("pink oyster temperature", PINK)]),
            rec("qwen35lm-filteron", "wh_pink", [search_output("pink oyster temperature", CLEAN)])]
    S.score_all(recs, FakeScorer())
    off = S.arm_stats([recs[0]], 0.035)
    on = S.arm_stats([recs[1]], 0.035)
    assert (off["shown"], off["low"], off["searches_any_low"]) == (3, 1, 1)
    assert (on["shown"], on["low"], on["searches_any_low"]) == (2, 0, 0)
    text = S.report(recs, 0.035)
    assert "1/3 (33 %)" in text and "0/2 (0 %)" in text
    assert "Pink (singer)" in text


def test_negative_control_nothing_below_reports_nothing():
    recs = [rec("a", "t", [search_output("pink oyster", CLEAN)])]
    S.score_all(recs, FakeScorer())
    s = S.arm_stats(recs, 0.035)
    assert s["low"] == 0 and s["searches_none_ok"] == 0 and s["runs_saw_low"] == 0
    assert "**a**: none" in S.report(recs, 0.035)


def test_all_junk_search_counts_as_fail_open():
    recs = [rec("a", "t", [search_output("pink", [PINK[1], ("Lingerie shop", "https://vs.com")])])]
    S.score_all(recs, FakeScorer())
    assert S.arm_stats(recs, 0.035)["searches_none_ok"] == 1


def test_old_records_cut_at_300_chars_are_unreadable_not_scored():
    cut = search_output("pink oyster temperature", PINK)[:300]
    recs = [rec("a", "t", [cut])]
    scorer = FakeScorer()
    S.score_all(recs, scorer)
    s = S.arm_stats(recs, 0.035)
    assert s["unreadable"] == 1 and s["shown"] == 0 and scorer.calls == 0


def test_failed_searches_are_skipped():
    recs = [rec("a", "t", ["Error: HTTP 429 Rate limit hit"], exit_code=1)]
    S.score_all(recs, FakeScorer())
    s = S.arm_stats(recs, 0.035)
    assert s["searches"] == 0 and s["unreadable"] == 0


def test_the_filters_notice_line_does_not_hide_results():
    out = search_output("pink oyster", PINK, notice="Relevance check: none of these results scored as relevant")
    recs = [rec("a", "t", [out])]
    S.score_all(recs, FakeScorer())
    assert S.arm_stats(recs, 0.035)["shown"] == 3


def test_repeated_results_are_scored_once():
    out = search_output("pink oyster", PINK)
    recs = [rec("a", "t", [out, out])]
    scorer = FakeScorer()
    S.score_all(recs, scorer)
    assert scorer.calls == 1 and S.arm_stats(recs, 0.035)["shown"] == 6


def test_bench_agent_keeps_the_whole_web_search_output():
    """Wiring, not behaviour: the stream handler is not callable on its own, and
    without the longer cap every record is unreadable to this script."""
    src = (ROOT / "scripts" / "bench_agent.py").read_text()
    assert 'cap = 12000 if d.get("tool") == "web_search" else 300' in src
