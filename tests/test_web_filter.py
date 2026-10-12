"""src/web_filter.py: the relevance filter drops off-topic search results
without ever leaving the model with nothing.

It is a guard that changes what the model sees, so the tests bound what it can
do (CLAUDE.md §3): off by default, results unchanged on any error, never fewer
than min_keep results, and a search with nothing relevant keeps its results and
gets a notice instead of being emptied. The end-to-end tests run the real
comprehensive_web_search with providers and fetches stubbed.
"""
import logging
import random

import pytest

from src import web_filter as F

ON = {**F.DEFAULTS, "web_filter_enabled": True, "web_filter_threshold": 0.5, "web_filter_min_keep": 2}


class Fake:
    """Logit +5 for passages mentioning 'oyster mushroom', -5 otherwise."""

    def __init__(self):
        self.calls = 0

    def rerank(self, query, docs):
        self.calls += 1
        return [5.0 if "oyster mushroom" in d.lower() else -5.0 for d in docs]


class Boom:
    def rerank(self, query, docs):
        raise RuntimeError("model exploded")


def _r(title, url, snippet=""):
    return {"title": title, "url": url, "snippet": snippet}


RESULTS = [
    _r("Pink (singer) - Wikipedia", "https://en.wikipedia.org/wiki/Pink_(singer)"),
    _r("Growing pink oyster mushrooms", "https://grocycle.com/pink"),
    _r("Find Hotel Deals | Oyster.com", "https://www.oyster.com/"),
    _r("Oyster mushroom fruiting guide", "https://www.out-grow.com/guide"),
    _r("PINK | Victoria's Secret", "https://www.victoriassecret.com/pink"),
]


# --------------------------------------------------------------- off / errors

def test_off_by_default_and_the_model_is_never_loaded(monkeypatch):
    monkeypatch.setattr(F, "_load_model", lambda name: pytest.fail("model loaded while disabled"))
    assert F.DEFAULTS["web_filter_enabled"] is False
    assert F.filter_results("pink oyster", RESULTS, settings=dict(F.DEFAULTS)) == (RESULTS, "")


def test_a_failing_model_leaves_results_unchanged_and_says_so(caplog):
    with caplog.at_level(logging.WARNING, logger="src.web_filter"):
        assert F.filter_results("pink oyster", RESULTS, settings=ON, model=Boom()) == (RESULTS, "")
    assert "[web-filter] skipped" in caplog.text


def test_a_short_score_list_leaves_results_unchanged():
    class Short:
        def rerank(self, q, docs):
            return [1.0]
    assert F.filter_results("pink oyster", RESULTS, settings=ON, model=Short()) == (RESULTS, "")


def test_missing_fastembed_or_model_download_failure_is_fail_open(monkeypatch):
    def broken(name):
        raise ImportError("no fastembed")
    monkeypatch.setattr(F, "_load_model", broken)
    assert F.filter_results("pink oyster", RESULTS, settings=ON) == (RESULTS, "")


def test_empty_query_or_results_pass_through():
    model = Fake()
    assert F.filter_results("", RESULTS, settings=ON, model=model) == (RESULTS, "")
    assert F.filter_results("q", [], settings=ON, model=model) == ([], "")
    assert model.calls == 0


# ------------------------------------------------------------------ filtering

def test_drops_off_topic_results_best_score_first(caplog):
    with caplog.at_level(logging.INFO, logger="src.web_filter"):
        kept, notice = F.filter_results("pink oyster mushroom", RESULTS, settings=ON, model=Fake())
    assert [r["url"] for r in kept] == ["https://grocycle.com/pink", "https://www.out-grow.com/guide"]
    assert notice == ""
    line = [r.getMessage() for r in caplog.records if "kept=" in r.getMessage()][0]
    assert "kept=2/5" in line and "victoriassecret.com:" in line and "oyster.com:" in line
    assert "best=0.993" in line and "grocycle.com:0.993" in line


def test_min_keep_tops_up_with_the_best_scores():
    cfg = {**ON, "web_filter_min_keep": 3}
    kept, notice = F.filter_results("pink oyster mushroom", RESULTS, settings=cfg, model=Fake())
    assert len(kept) == 3 and notice == ""
    assert {"https://grocycle.com/pink", "https://www.out-grow.com/guide"} <= {r["url"] for r in kept}


def test_nothing_relevant_keeps_results_and_the_notice_is_off_by_default():
    junk = [RESULTS[0], RESULTS[2], RESULTS[4]]
    assert F.DEFAULTS["web_filter_notice_below"] == 0.0
    kept, notice = F.filter_results("pink oyster mushroom", junk, settings=ON, model=Fake())
    assert len(kept) == 2                       # min_keep, not zero
    assert notice == ""


def test_notice_fires_only_when_the_best_score_is_below_its_own_cut_off():
    junk = [RESULTS[0], RESULTS[2], RESULTS[4]]
    cfg = {**ON, "web_filter_notice_below": 0.1}
    assert F.filter_results("pink oyster mushroom", junk, settings=cfg, model=Fake())[1] == F.OFF_TOPIC_NOTICE
    # all results below the drop threshold, but the best one above the notice cut-off: no notice
    class Low:
        def rerank(self, q, docs):
            return [-2.0, -4.0, -6.0]            # sigmoid ~0.12, 0.018, 0.0025
    cfg = {**ON, "web_filter_threshold": 0.5, "web_filter_notice_below": 0.05}
    kept, notice = F.filter_results("q", junk, settings=cfg, model=Low())
    assert notice == "" and len(kept) == 2


def test_negative_control_all_relevant_nothing_dropped():
    good = [RESULTS[1], RESULTS[3]]
    assert F.filter_results("pink oyster mushroom", good, settings=ON, model=Fake()) == (good, "")


def test_select_never_returns_fewer_than_min_keep_or_more_than_limit():
    rng = random.Random(7)
    for _ in range(500):
        n = rng.randint(1, 15)
        scores = [rng.random() for _ in range(n)]
        min_keep, limit = rng.randint(1, 5), rng.choice([None, 3, 5, 8])
        kept = F.select(scores, rng.random(), min_keep, limit)
        assert len(kept) >= min(min_keep, limit or n, n)
        assert limit is None or len(kept) <= limit
        assert len(set(kept)) == len(kept) and all(0 <= i < n for i in kept)
        assert [scores[i] for i in kept] == sorted((scores[i] for i in kept), reverse=True)


def test_settings_from_the_settings_file_are_merged_over_the_defaults(monkeypatch):
    import src.settings as S
    monkeypatch.setattr(S, "load_settings", lambda: {"web_filter_enabled": True, "unrelated": 1})
    cfg = F._settings()
    assert cfg["web_filter_enabled"] is True
    assert cfg["web_filter_threshold"] == F.DEFAULTS["web_filter_threshold"]
    assert "unrelated" not in cfg


# ----------------------------------------------------- end to end, real writer

@pytest.fixture(autouse=True)
def _no_decision_log(monkeypatch, tmp_path):
    # Keep the decision log out of the suite's data dir unless a test asks for it,
    # and keep topic tagging off the real embedding model.
    monkeypatch.setattr(F, "_decision_log_path", lambda: str(tmp_path / "web_filter.jsonl"))
    from src import research_topics as T
    monkeypatch.setattr(T, "assign_topic", lambda query, *a, **k: ("finance" if "gold" in query else "other", 0.9))


@pytest.fixture
def search_env(monkeypatch):
    from services.search import core
    fetched = []
    monkeypatch.setattr(core, "_get_search_settings", lambda: {"search_provider": "searxng"})
    monkeypatch.setattr(core, "_get_result_count", lambda: 10)
    monkeypatch.setattr(core, "_build_provider_chain", lambda primary: ["searxng"])
    monkeypatch.setattr(core, "_call_provider", lambda *a, **k: [dict(r) for r in RESULTS])

    def fetch(url, *a, **k):
        fetched.append(url)
        return {"success": True, "url": url, "title": "T", "content": "body"}
    monkeypatch.setattr(core, "fetch_webpage_content", fetch)
    return core, fetched


def test_disabled_filter_leaves_comprehensive_search_output_unchanged(search_env, monkeypatch):
    core, fetched = search_env
    monkeypatch.setattr(F, "_settings", lambda: dict(F.DEFAULTS))
    text, sources = core.comprehensive_web_search("pink oyster mushroom", max_pages=5, return_sources=True)
    assert len(sources) == len(RESULTS)
    assert F.OFF_TOPIC_NOTICE not in text


def test_enabled_filter_removes_junk_from_sources_fetches_and_output(search_env, monkeypatch):
    core, fetched = search_env
    monkeypatch.setattr(F, "_settings", lambda: dict(ON))
    monkeypatch.setattr(F, "_load_model", lambda name: Fake())
    text, sources = core.comprehensive_web_search("pink oyster mushroom", max_pages=5, return_sources=True)
    urls = {s["url"] for s in sources if not s.get("filtered")}
    assert urls == {"https://grocycle.com/pink", "https://www.out-grow.com/guide"}
    dropped = {s["url"] for s in sources if s.get("filtered")}
    assert dropped == {r["url"] for r in RESULTS} - urls
    assert len({s["search_id"] for s in sources}) == 1 and all(s["query"] == "pink oyster mushroom" for s in sources)
    assert all(isinstance(s["score"], float) for s in sources)
    assert set(fetched) == urls
    assert "victoriassecret" not in text and "Pink (singer)" not in text
    assert F.OFF_TOPIC_NOTICE not in text


def test_all_junk_search_reaches_the_model_with_the_notice(search_env, monkeypatch):
    core, fetched = search_env
    monkeypatch.setattr(core, "_call_provider", lambda *a, **k: [dict(RESULTS[i]) for i in (0, 2, 4)])
    monkeypatch.setattr(F, "_settings", lambda: {**ON, "web_filter_notice_below": 0.1})
    monkeypatch.setattr(F, "_load_model", lambda name: Fake())
    text, sources = core.comprehensive_web_search("pink oyster mushroom", max_pages=5, return_sources=True)
    assert len([s for s in sources if not s.get("filtered")]) == 2
    summary = text[text.index("SEARCH RESULTS SUMMARY:"):]
    assert F.OFF_TOPIC_NOTICE in summary


def test_the_on_off_state_is_logged_once_per_change(monkeypatch, caplog):
    monkeypatch.setattr(F, "_logged_state", None)
    model = Fake()
    with caplog.at_level(logging.INFO, logger="src.web_filter"):
        F.filter_results("q oyster mushroom", RESULTS, settings=dict(F.DEFAULTS), model=model)
        F.filter_results("q oyster mushroom", RESULTS, settings=dict(F.DEFAULTS), model=model)
        F.filter_results("q oyster mushroom", RESULTS, settings=ON, model=model)
    states = [r.getMessage().split()[1] for r in caplog.records if r.getMessage().startswith("[web-filter] o")]
    assert states == ["off", "on"]


# ------------------------------------------------- more candidates, decision log

MORE = RESULTS + [
    _r("Pink oyster mushroom growing temperatures", "https://mushroomalmanac.com/pink"),
    _r("Oyster mushroom fruiting conditions chart", "https://fungilorious.com/chart"),
    _r("Oyster card top-up", "https://oyster.tfl.gov.uk/"),
]


def test_candidate_count_grows_only_while_the_filter_is_on():
    assert F.candidate_count(5, settings=dict(F.DEFAULTS)) == 5
    assert F.candidate_count(5, settings={**ON, "web_filter_candidates": 15}) == 15
    assert F.candidate_count(20, settings={**ON, "web_filter_candidates": 15}) == 20
    assert F.candidate_count(5, settings={**ON, "web_filter_candidates": "x"}) == 5


def test_disabled_or_failing_filter_cuts_extra_candidates_back_to_the_limit():
    assert F.filter_results("q", MORE, settings=dict(F.DEFAULTS), limit=5) == (MORE[:5], "")
    assert F.filter_results("q oyster mushroom", MORE, settings=ON, model=Boom(), limit=5) == (MORE[:5], "")


def test_dropped_results_are_replaced_from_the_extra_candidates():
    kept, _ = F.filter_results("pink oyster mushroom", MORE, settings=ON, model=Fake(), limit=5)
    urls = [r["url"] for r in kept]
    assert len(urls) == 4                        # 4 relevant of 8; the junk is not used to fill up to 5
    assert "https://mushroomalmanac.com/pink" in urls and "https://fungilorious.com/chart" in urls
    assert not any(j in u for u in urls for j in ("victoriassecret", "oyster.com", "tfl.gov.uk", "Pink_(singer)"))


def test_decision_log_records_every_candidate_with_score_and_outcome(tmp_path):
    import json
    log = tmp_path / "decisions.jsonl"
    F.filter_results("pink oyster mushroom", MORE, settings=ON, model=Fake(), limit=5, decision_log=str(log))
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert rec["query"] == "pink oyster mushroom" and rec["limit"] == 5
    assert len(rec["results"]) == len(MORE)
    by_url = {r["url"]: r for r in rec["results"]}
    assert by_url["https://www.victoriassecret.com/pink"]["kept"] is False
    assert by_url["https://www.victoriassecret.com/pink"]["position_out"] is None
    assert by_url["https://grocycle.com/pink"]["kept"] is True and by_url["https://grocycle.com/pink"]["score"] > 0.9
    assert sorted(r["position_out"] for r in rec["results"] if r["kept"]) == [1, 2, 3, 4]


def test_decision_log_can_be_switched_off_and_a_write_failure_does_not_break_search(tmp_path, caplog):
    log = tmp_path / "d.jsonl"
    F.filter_results("pink oyster mushroom", MORE, settings={**ON, "web_filter_decision_log": False},
                     model=Fake(), decision_log=str(log))
    assert not log.exists()
    blocked = tmp_path / "not_a_dir"
    blocked.write_text("x")
    with caplog.at_level(logging.WARNING, logger="src.web_filter"):
        kept, _ = F.filter_results("pink oyster mushroom", MORE, settings=ON, model=Fake(),
                                   decision_log=str(blocked / "d.jsonl"))
    assert kept and "decision log not written" in caplog.text


def test_decision_log_rotates_past_its_size_cap(tmp_path, monkeypatch):
    log = tmp_path / "d.jsonl"
    log.write_text("x" * 100)
    monkeypatch.setattr(F, "DECISION_LOG_MAX_BYTES", 50)
    F._write_decision({"a": 1}, str(log))
    assert (tmp_path / "d.jsonl.1").read_text() == "x" * 100
    assert log.read_text().strip() == '{"a": 1}'


def test_comprehensive_search_asks_for_more_candidates_only_while_on(search_env, monkeypatch):
    core, fetched = search_env
    asked = []

    def provider(name, query, count, time_filter=None):
        asked.append(count)
        return [dict(r) for r in MORE]
    monkeypatch.setattr(core, "_call_provider", provider)
    monkeypatch.setattr(F, "_load_model", lambda name: Fake())
    monkeypatch.setattr(F, "_settings", lambda: dict(F.DEFAULTS))
    _, sources_off = core.comprehensive_web_search("pink oyster mushroom", max_pages=5, return_sources=True)
    monkeypatch.setattr(F, "_settings", lambda: {**ON, "web_filter_candidates": 15})
    _, sources_on = core.comprehensive_web_search("pink oyster mushroom", max_pages=5, return_sources=True)
    assert asked == [10, 15]                      # result count stub is 10
    assert len(sources_off) == len(MORE)          # provider returned 8 < 10: nothing cut
    assert not any(s.get("filtered") for s in sources_off)
    assert {s["url"] for s in sources_on if not s.get("filtered")} == {r["url"] for r in MORE if "oyster mushroom" in _r_text(r)}


def _r_text(r):
    return f"{r['title']} {r['snippet']}".lower()


def test_comprehensive_search_passes_on_no_more_than_the_normal_result_count(search_env, monkeypatch):
    core, fetched = search_env
    monkeypatch.setattr(core, "_get_result_count", lambda: 3)
    monkeypatch.setattr(core, "_call_provider", lambda *a, **k: [dict(r) for r in MORE])
    monkeypatch.setattr(F, "_load_model", lambda name: Fake())
    monkeypatch.setattr(F, "_settings", lambda: {**ON, "web_filter_candidates": 15})
    _, sources = core.comprehensive_web_search("pink oyster mushroom", max_pages=3, return_sources=True)
    assert len([s for s in sources if not s.get("filtered")]) == 3   # 4 relevant candidates, 3 shown


def test_dropped_results_never_reach_the_model_text(search_env, monkeypatch):
    """The dropped candidates ride in the sources list (display data) only."""
    core, fetched = search_env
    monkeypatch.setattr(F, "_settings", lambda: dict(ON))
    monkeypatch.setattr(F, "_load_model", lambda name: Fake())
    text, sources = core.comprehensive_web_search("pink oyster mushroom", max_pages=5, return_sources=True)
    assert any(s.get("filtered") for s in sources)
    for s in sources:
        if s.get("filtered"):
            assert s["url"] not in text and s["title"] not in text


def test_agent_tool_marker_survives_a_title_containing_the_comment_end(monkeypatch):
    """A '-->' in a title must not end the SOURCES marker early: agent_loop would
    fail to strip it and the model would read the whole list."""
    import asyncio
    import json as _json
    import src.search as S
    from src.agent_tools.web_tools import WebSearchTool
    srcs = [{"url": "https://a.example/x", "title": "Arrows --> everywhere", "filtered": True}]
    monkeypatch.setattr(S, "comprehensive_web_search", lambda *a, **k: ("body text", srcs))
    out = asyncio.run(WebSearchTool().execute("arrows", {}))["output"]
    i = out.find("<!-- SOURCES:")
    end = out.find(" -->", i)                          # agent_loop's own search
    assert _json.loads(out[i + len("<!-- SOURCES:"):end]) == srcs
    assert out[:i].rstrip() == "body text"
