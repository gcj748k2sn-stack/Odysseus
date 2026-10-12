"""src/rating_bias.py and its call site in src/web_filter.py: ▲/▼ ratings move
a site's score on later searches in the same topic.

In "apply" mode this guard changes what the model sees, so the tests bound
what it can do (CLAUDE.md §3): never more than ±strength, never fewer results
than min_keep, nothing for the topic "other", identical output without
ratings, and "log" mode never changes the kept list. The replay half
(scripts/bench_web_filter.py run --ratings) must not see a search's own or
later ratings, or it grades the ratings against themselves.
"""
import importlib.util
import json
import logging
import math
import random
from pathlib import Path

import pytest

from src import rating_bias as RB
from src import web_filter as F

THRESHOLD = 0.035
BASE = {**F.DEFAULTS, "web_filter_enabled": True, "web_filter_threshold": THRESHOLD, "web_filter_min_keep": 2}


def _logit(p):
    return math.log(p / (1 - p))


class ByDomain:
    """Reranker stub: a fixed score per domain, read from the passage's '(domain)' tail."""

    def __init__(self, scores):
        self.scores = scores

    def rerank(self, query, docs):
        return [_logit(next(v for d, v in self.scores.items() if d in doc)) for doc in docs]


def _r(domain, path="/"):
    return {"title": domain, "url": f"https://{domain}{path}", "snippet": ""}


# a.com and b.com relevant, the rest near the threshold either side
SCORES = {"good.com": 0.6, "fine.com": 0.4, "near.com": 0.04, "low.com": 0.03, "junk.com": 0.01}
RESULTS = [_r(d) for d in SCORES]


def _rec(url, rating, topic="biology", search_id="s1", owner="u", ts="2026-10-12T10:00:00"):
    return {"ts_local": ts, "owner": owner, "search_id": search_id, "url": url, "rating": rating, "topic": topic}


def _table(*recs):
    return RB.build_table(list(recs))


def _run(mode, table, topic="biology", results=RESULTS, extra=None, log=None):
    cfg = {**BASE, "web_filter_rating_mode": mode, **(extra or {})}
    info = {"search_id": "now", "topic": topic}
    kept, notice = F.filter_results("pink oyster", results, settings=cfg, model=ByDomain(SCORES),
                                    info=info, rating_table=table, decision_log=log)
    return [r["url"] for r in kept], notice, info


# ------------------------------------------------------------- the arithmetic

def test_bias_never_exceeds_strength_whatever_the_counts():
    rng = random.Random(7)
    for _ in range(300):
        recs = [_rec(f"https://site.com/p{rng.randint(0, 3)}", rng.choice(["up", "down"]), search_id=f"s{i}")
                for i in range(rng.randint(1, 40))]
        strength = rng.uniform(0, 1.5)
        for path in ("/p0", "/p1", "/other"):
            b = RB.bias_for("biology", "https://site.com" + path, _table(*recs), strength, 1)
            assert abs(b) <= strength + 1e-12


def test_one_click_on_a_site_is_not_yet_a_site_verdict():
    t = _table(_rec("https://near.com/a", "down"))
    assert RB.bias_for("biology", "https://near.com/other", t, 0.7, 2) == 0.0
    # ...but it counts for that exact page
    assert RB.bias_for("biology", "https://near.com/a", t, 0.7, 2) == pytest.approx(-0.35)


def test_two_downs_give_the_smoothed_site_term():
    t = _table(_rec("https://near.com/a", "down", search_id="s1"), _rec("https://near.com/b", "down", search_id="s2"))
    # 0.7 × (0 − 2) / (2 + 2)
    assert RB.bias_for("biology", "https://near.com/c", t, 0.7, 2) == pytest.approx(-0.35)


def test_topic_other_none_and_a_different_topic_get_no_bias():
    t = _table(_rec("https://near.com/a", "down"), _rec("https://near.com/a", "down", search_id="s2"),
               _rec("https://near.com/b", "down", topic="other", search_id="s3"))
    for topic in ("other", "", "finance"):
        assert RB.bias_for(topic, "https://near.com/a", t, 0.7, 1) == 0.0
    assert "other" not in t["domains"]


def test_a_site_rating_covers_subdomains_on_a_label_boundary_only():
    t = _table(_rec("https://webmd.com/a", "down", search_id="s1"), _rec("https://webmd.com/b", "down", search_id="s2"))
    assert RB.bias_for("biology", "https://m.webmd.com/x", t, 0.7, 2) < 0
    assert RB.bias_for("biology", "https://notwebmd.com/x", t, 0.7, 2) == 0.0


def test_latest_click_wins_clear_removes_and_every_owner_counts():
    url = "https://near.com/a"
    t = _table(_rec(url, "down"), _rec(url, "up"))
    assert t["urls"]["biology"][url] == 1
    t = _table(_rec(url, "down"), _rec(url, "clear"))
    assert t["domains"] == {} and t["urls"] == {}
    t = _table(_rec(url, "down", owner="a"), _rec(url, "down", owner="b"))
    assert t["domains"]["biology"]["near.com"] == [0, 2]


def test_before_and_exclude_search_hide_later_and_own_ratings():
    recs = [_rec("https://near.com/a", "down", search_id="s1", ts="2026-10-12T10:00:00"),
            _rec("https://near.com/b", "down", search_id="s2", ts="2026-10-12T12:00:00")]
    assert RB.build_table(recs, before="2026-10-12T11:00:00")["urls"]["biology"] == {"https://near.com/a": -1}
    assert RB.build_table(recs, exclude_search="s1")["urls"]["biology"] == {"https://near.com/b": -1}


def test_settings_are_clamped_and_an_unknown_mode_means_off():
    assert RB.settings_of({"web_filter_rating_mode": "apply", "web_filter_rating_strength": 9}) == ("apply", 1.5, 2)
    assert RB.settings_of({"web_filter_rating_mode": "yes"})[0] == "off"
    assert RB.settings_of({"web_filter_rating_strength": "x"}) == ("off", 0.0, 2)


def test_the_live_table_is_reread_when_the_ratings_file_changes(tmp_path):
    path = tmp_path / "web_ratings.jsonl"
    assert RB.current_table(str(path)) == {"domains": {}, "urls": {}}
    path.write_text(json.dumps(_rec("https://near.com/a", "down")) + "\n", encoding="utf-8")
    assert RB.current_table(str(path))["urls"]["biology"] == {"https://near.com/a": -1}
    with open(path, "a", encoding="utf-8") as f:
        f.write("not json\n" + json.dumps(_rec("https://near.com/a", "clear")) + "\n")
    assert RB.current_table(str(path)) == {"domains": {}, "urls": {}}


# ------------------------------------------------------- in the filter: bounds

DOWN_NEAR = _table(_rec("https://near.com/a", "down", search_id="s1"), _rec("https://near.com/b", "down", search_id="s2"))
UP_LOW = _table(_rec("https://low.com/", "up"))


def test_negative_control_no_ratings_gives_todays_output_in_every_mode():
    empty = RB.build_table([])
    off = _run("off", empty)
    for mode in ("log", "apply"):
        assert _run(mode, empty)[:2] == off[:2]


def test_negative_control_ratings_in_another_topic_or_other_change_nothing():
    off = _run("off", DOWN_NEAR)
    assert _run("apply", DOWN_NEAR, topic="finance")[:2] == off[:2]
    assert _run("apply", DOWN_NEAR, topic="other")[:2] == off[:2]
    assert _run("apply", DOWN_NEAR, topic="")[:2] == off[:2]


def test_apply_drops_a_down_rated_site_near_the_threshold():
    raw, _, _ = _run("off", DOWN_NEAR)
    rated, _, info = _run("apply", DOWN_NEAR)
    assert "https://near.com/" in raw and "https://near.com/" not in rated
    assert info["rating_bias"] == {"https://near.com/": pytest.approx(-0.35)}


def test_apply_keeps_an_up_rated_page_the_filter_had_dropped():
    raw, _, _ = _run("off", UP_LOW)
    rated, _, _ = _run("apply", UP_LOW)
    assert "https://low.com/" not in raw and "https://low.com/" in rated


def test_ratings_at_the_default_strength_cannot_move_a_clear_case():
    # At 0.7 only scores between ~0.018 and ~0.068 can cross 0.035: 0.6 stays
    # kept and 0.01 stays dropped however many ratings there are.
    t = _table(*[_rec(f"https://good.com/{i}", "down", search_id=f"g{i}") for i in range(20)],
               *[_rec(f"https://junk.com/{i}", "up", search_id=f"j{i}") for i in range(20)])
    rated, _, _ = _run("apply", t)
    assert "https://good.com/" in rated and "https://junk.com/" not in rated
    # The 1.5 ceiling reaches further (~0.008 to ~0.14): pinned so raising it is a visible change.
    rated, _, _ = _run("apply", t, extra={"web_filter_rating_strength": 1.5})
    assert "https://junk.com/" in rated and "https://good.com/" in rated


def test_apply_never_returns_fewer_than_min_keep():
    every = _table(*[_rec(f"https://{d}/{i}", "down", search_id=f"{d}{i}") for d in SCORES for i in range(10)])
    rated, _, _ = _run("apply", every, extra={"web_filter_rating_strength": 1.5, "web_filter_min_keep": 3,
                                              "web_filter_threshold": 0.9})
    assert len(rated) == 3


def test_log_mode_never_changes_the_kept_list_and_records_what_apply_would(tmp_path, caplog):
    log = tmp_path / "d.jsonl"
    off = _run("off", DOWN_NEAR)
    with caplog.at_level(logging.INFO, logger="src.web_filter"):
        logged = _run("log", DOWN_NEAR, log=str(log))
    assert logged[:2] == off[:2]
    assert "rating_changes=['near.com:kept→dropped']" in caplog.text and "ratings=log" in caplog.text
    rec = json.loads(log.read_text(encoding="utf-8"))
    near = next(r for r in rec["results"] if r["url"] == "https://near.com/")
    assert rec["rating_mode"] == "log"
    assert near["kept"] is True and near["rated_kept"] is False and near["bias"] == pytest.approx(-0.35)
    assert near["score"] == pytest.approx(0.04, abs=1e-4) and near["adjusted"] < THRESHOLD


def test_off_mode_does_not_read_the_ratings(monkeypatch):
    monkeypatch.setattr(RB, "current_table", lambda path=None: pytest.fail("ratings read while off"))
    F.filter_results("q", RESULTS, settings={**BASE, "web_filter_rating_mode": "off"}, model=ByDomain(SCORES))


def test_a_broken_ratings_table_means_no_bias(monkeypatch, caplog):
    def boom(path=None):
        raise OSError("disk gone")
    monkeypatch.setattr(RB, "current_table", boom)
    off = _run("off", None)
    with caplog.at_level(logging.WARNING, logger="src.web_filter"):
        assert _run("apply", None)[:2] == off[:2]
    assert "rating bias skipped" in caplog.text


# ------------------------------------------------------------ the notice

def test_notice_uses_raw_scores_and_logs_the_either_rule(tmp_path):
    # best raw 0.04 is above the cut-off; down-rated it would fall below
    only = [_r("near.com"), _r("low.com"), _r("junk.com")]
    extra = {"web_filter_notice_below": 0.035}
    log = tmp_path / "d.jsonl"
    _, notice, _ = _run("apply", DOWN_NEAR, results=only, extra=extra, log=str(log))
    assert notice == ""
    assert json.loads(log.read_text(encoding="utf-8"))["notice_either"] is True


def test_an_up_rating_cannot_silence_the_notice():
    only = [_r("low.com"), _r("junk.com")]
    t = _table(*[_rec(f"https://low.com/{i}", "up", search_id=f"s{i}") for i in range(6)])
    _, notice, _ = _run("apply", t, results=only, extra={"web_filter_notice_below": 0.035})
    assert notice == F.OFF_TOPIC_NOTICE


def test_sources_carry_the_bias_for_the_sources_box():
    _, _, info = _run("apply", DOWN_NEAR)
    kept = [r for r in RESULTS if r["url"] != "https://near.com/" and r["url"] not in
            {d["url"] for d in info["dropped"]}]
    out = F.annotate_sources([{"url": r["url"], "title": r["title"]} for r in kept], "q", info)
    near = next(s for s in out if s["url"] == "https://near.com/")
    assert near["filtered"] is True and near["rating_bias"] == pytest.approx(-0.35)
    assert all("rating_bias" not in s for s in out if s["url"] != "https://near.com/")


# --------------------------------------------------------------- settings API

def test_rating_settings_validation():
    from routes.web_feedback_routes import validate_filter_settings as V
    assert V({"web_filter_rating_mode": "apply", "web_filter_rating_strength": 0.7, "web_filter_rating_min": 2}) == {
        "web_filter_rating_mode": "apply", "web_filter_rating_strength": 0.7, "web_filter_rating_min": 2}
    for bad in ({"web_filter_rating_mode": "on"}, {"web_filter_rating_mode": True},
                {"web_filter_rating_strength": 2.0}, {"web_filter_rating_min": 0}):
        with pytest.raises(ValueError):
            V(bad)


# ------------------------------------------------------------------- replay

def _bench():
    spec = importlib.util.spec_from_file_location(
        "bench_web_filter_rating_test", Path(__file__).resolve().parents[1] / "scripts" / "bench_web_filter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W = _bench()


def _search(sid, ts, urls, topic="biology", search_id=""):
    return {"id": sid, "query": "pink oyster " + sid, "timestamp_local": ts, "timestamp_utc": "",
            "topic": topic, "search_id": search_id,
            "results": [{"rank": i + 1, "url": u, "title": "", "snippet": ""} for i, u in enumerate(urls)]}


def test_replay_never_uses_later_ratings_or_the_searchs_own():
    recs = [_rec("https://near.com/a", "down", search_id="live1", ts="2026-10-12T12:00:00")]
    early = _search("e", "2026-10-12T11:00:00", ["https://near.com/a"])
    own = _search("o", "2026-10-12T13:00:00", ["https://near.com/a"], search_id="live1")
    later = _search("l", "2026-10-12T13:00:00", ["https://near.com/a"])
    biases, used = W.rating_biases([early, own, later], recs, 0.7, 2)
    assert biases == {("l", "https://near.com/a"): pytest.approx(-0.35)} and used == 1
    biases, _ = W.rating_biases([early], recs, 0.7, 2, order="loo")
    assert ("e", "https://near.com/a") in biases


def test_replay_converts_app_db_utc_to_local_time():
    s = {"timestamp_utc": "2026-10-12 10:00:00.123456"}
    local = W.search_time_local(s)
    assert len(local) == 19 and local[:10] in ("2026-10-11", "2026-10-12", "2026-10-13")


def test_replay_loads_a_topic_only_when_there_is_a_rating_to_apply():
    calls = []

    def topic_of(s):
        calls.append(s["id"])
        return "biology"
    no_topic = _search("x", "2026-10-12T13:00:00", ["https://near.com/a"], topic="")
    W.rating_biases([no_topic], [], 0.7, 2, topic_of=topic_of)
    assert calls == []
    W.rating_biases([no_topic], [_rec("https://near.com/a", "down")], 0.7, 2, topic_of=topic_of)
    assert calls == ["x"]


def test_replay_report_leaves_out_labels_taken_from_ratings_and_says_when_it_has_no_evidence():
    class A:
        ratings, rating_order, rating_strengths, rating_min = "r.jsonl", "time", [0.7], 2
        threshold, notice_below, min_keep = THRESHOLD, THRESHOLD, 2
    s = _search("x", "2026-10-12T13:00:00", ["https://near.com/a", "https://good.com/", "https://low.com/"])
    raw = {("x", "https://near.com/a"): 0.04, ("x", "https://good.com/"): 0.6, ("x", "https://low.com/"): 0.03}
    truth = {("x", "https://near.com/a"): "n", ("x", "https://good.com/"): "y"}
    rated = {W.label_key(s["query"], "https://near.com/a")}
    text = "\n".join(W.rating_section([s], raw, truth, [], rated, A))
    assert "1 of 2" in text and "no evidence either way" in text
    recs = [_rec("https://near.com/a", "down", search_id="a", ts="2026-10-12T10:00:00"),
            _rec("https://near.com/b", "down", search_id="b", ts="2026-10-12T10:00:00")]
    text = "\n".join(W.rating_section([s], raw, truth, recs, set(), A))
    assert "kept→dropped: label n" in text and "no evidence" not in text


def test_notice_counts_either_rule_only_adds_firings():
    s = _search("x", "t", ["https://a.com/", "https://b.com/"])
    truth = {("x", "https://a.com/"): "n", ("x", "https://b.com/"): "n"}
    raw = {("x", "https://a.com/"): 0.04, ("x", "https://b.com/"): 0.01}
    lower = {("x", "https://a.com/"): 0.02, ("x", "https://b.com/"): 0.01}
    higher = {("x", "https://a.com/"): 0.09, ("x", "https://b.com/"): 0.01}
    assert W.notice_counts([s], raw, lower, truth, 0.035) == {"raw": [0, 1, 0, 0], "either": [1, 1, 0, 0]}
    raw_low = {("x", "https://a.com/"): 0.03, ("x", "https://b.com/"): 0.01}
    assert W.notice_counts([s], raw_low, higher, truth, 0.035)["either"] == [1, 1, 0, 0]
