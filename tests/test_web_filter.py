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

def test_drops_off_topic_results_and_keeps_display_order(caplog):
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


def test_decide_never_returns_fewer_than_min_keep_for_random_scores():
    rng = random.Random(7)
    for _ in range(500):
        n = rng.randint(1, 10)
        scores = [rng.random() for _ in range(n)]
        min_keep = rng.randint(1, 5)
        kept, all_low = F.decide(scores, rng.random(), min_keep)
        assert len(kept) >= min(min_keep, n)
        assert kept == sorted(set(kept))
        assert all(0 <= i < n for i in kept)


def test_settings_from_the_settings_file_are_merged_over_the_defaults(monkeypatch):
    import src.settings as S
    monkeypatch.setattr(S, "load_settings", lambda: {"web_filter_enabled": True, "unrelated": 1})
    cfg = F._settings()
    assert cfg["web_filter_enabled"] is True
    assert cfg["web_filter_threshold"] == F.DEFAULTS["web_filter_threshold"]
    assert "unrelated" not in cfg


# ----------------------------------------------------- end to end, real writer

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
    urls = {s["url"] for s in sources}
    assert urls == {"https://grocycle.com/pink", "https://www.out-grow.com/guide"}
    assert set(fetched) == urls
    assert "victoriassecret" not in text and "Pink (singer)" not in text
    assert F.OFF_TOPIC_NOTICE not in text


def test_all_junk_search_reaches_the_model_with_the_notice(search_env, monkeypatch):
    core, fetched = search_env
    monkeypatch.setattr(core, "_call_provider", lambda *a, **k: [dict(RESULTS[i]) for i in (0, 2, 4)])
    monkeypatch.setattr(F, "_settings", lambda: {**ON, "web_filter_notice_below": 0.1})
    monkeypatch.setattr(F, "_load_model", lambda name: Fake())
    text, sources = core.comprehensive_web_search("pink oyster mushroom", max_pages=5, return_sources=True)
    assert len(sources) == 2
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
