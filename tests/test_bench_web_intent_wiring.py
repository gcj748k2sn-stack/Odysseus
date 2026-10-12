"""The benchmark's copy of the web-intent regex matches the chat route's.

A wiring test, the deliberate exception to behaviour-first: it pins structure.
`routes/chat_routes.py` decides inline (no named constant) that a message is an
explicit web lookup, and then drops read_file/write_file/bash/notes/calendar for
that turn. `scripts/bench_agent_tasks.py` keeps a hand copy, `WEB_INTENT_RE`, so
`bench_agent.py` can refuse a non-web task whose prompt would trip it. If the
route's pattern changes and the copy does not, file tasks fail for harness
reasons and read as model failures. This test fails first instead.
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The route's inline call, as it reads today. If this stops matching, the route
# was restructured: re-check where the web-intent decision now lives and point
# both this test and the benchmark copy at it.
_ROUTE_CALL_RE = re.compile(r'_explicit_web_intent = bool\(re\.search\(\s*r"([^"]+)"')


def _bench_tasks():
    # bench_agent_tasks imports its sibling bench_knowledge_tasks by bare name,
    # as bench_agent.py runs it; without this the test passes only after some
    # other file has put scripts/ on sys.path.
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "bench_agent_tasks_under_test", ROOT / "scripts" / "bench_agent_tasks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _route_patterns(source: str) -> list:
    return _ROUTE_CALL_RE.findall(source)


def test_the_route_decides_web_intent_in_exactly_one_place():
    source = (ROOT / "routes" / "chat_routes.py").read_text(encoding="utf-8")
    assert len(_route_patterns(source)) == 1


def test_the_benchmark_copy_matches_the_route():
    source = (ROOT / "routes" / "chat_routes.py").read_text(encoding="utf-8")
    (route_pattern,) = _route_patterns(source)
    assert _bench_tasks().WEB_INTENT_RE.pattern == route_pattern


def test_negative_control_a_drifted_route_is_caught():
    """Check the check fails: one added word in the route breaks equality."""
    source = (ROOT / "routes" / "chat_routes.py").read_text(encoding="utf-8")
    drifted = source.replace("|weather|", "|weather|price|", 1)
    assert drifted != source
    (route_pattern,) = _route_patterns(drifted)
    assert _bench_tasks().WEB_INTENT_RE.pattern != route_pattern


def test_same_verdict_on_mixed_case_messages():
    """The route lowercases the message; the copy uses IGNORECASE instead."""
    source = (ROOT / "routes" / "chat_routes.py").read_text(encoding="utf-8")
    (route_pattern,) = _route_patterns(source)
    copy = _bench_tasks().WEB_INTENT_RE
    for msg in ("Search the WEB for X", "What is 17 × 23?",
                "Read notes.txt", "EXCHANGE RATE today", "researcher"):
        assert bool(re.search(route_pattern, msg.lower())) == bool(copy.search(msg)), msg
