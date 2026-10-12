"""Research topics, per-source ratings and their API (fork: notes entry "A relevance filter for web results").

Topics are global and admin-edited; ratings are per user and must never leak
between users. Topic assignment never raises: a broken embedding model means
"other", not a failed search.
"""
import json

import numpy as np
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src import research_topics as T
from src import web_ratings as R


class FakeEncoder:
    """Bag-of-words vectors over a tiny vocabulary, normalized."""
    VOCAB = ["mushroom", "oyster", "gold", "price", "recipe", "eggs", "silver", "temperature"]

    def __init__(self):
        self.calls = 0

    def encode(self, texts, normalize_embeddings=True):
        self.calls += 1
        out = []
        for t in texts:
            hits = [float(w in t.lower()) for w in self.VOCAB]
            v = np.array(hits + [0.0 if any(hits) else 1.0])     # last dim: "none of the vocabulary"
            out.append(v / np.linalg.norm(v))
        return np.array(out)


@pytest.fixture(autouse=True)
def _tmp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "_path", lambda: str(tmp_path / "research_topics.json"))
    monkeypatch.setattr(R, "_path", lambda: str(tmp_path / "web_ratings.jsonl"))
    T._example_cache.clear()


# --------------------------------------------------------------------- topics

def test_defaults_are_biology_finance_cooking_until_something_is_saved():
    data = T.load_topics()
    assert [t["name"] for t in data["topics"]] == ["Biology", "Finance", "Cooking"]
    assert all(t["enabled"] and t["examples"] for t in data["topics"])


def test_save_round_trips_and_normalizes():
    saved = T.save_topics({"min_similarity": 0.5, "topics": [
        {"name": "  Mushroom   growing ", "examples": ["oyster  mushroom temperature", " "]},
        {"name": "Mushroom growing", "examples": ["shiitake logs"], "enabled": False},
    ]})
    assert [t["id"] for t in saved["topics"]] == ["mushroom-growing", "mushroom-growing-2"]
    assert saved["topics"][0]["examples"] == ["oyster mushroom temperature"]
    assert T.load_topics() == saved


@pytest.mark.parametrize("bad", [
    {"topics": "x"},
    {"topics": [{"name": "", "examples": ["a"]}]},
    {"topics": [{"name": "A", "examples": []}]},
    {"topics": [{"name": "A", "examples": ["x" * 201]}]},
    {"topics": [{"name": "A", "examples": ["a"]}], "min_similarity": 2},
    {"topics": [{"name": f"t{i}", "examples": ["a"]} for i in range(T.MAX_TOPICS + 1)]},
    {"topics": [{"name": "Other", "examples": ["a"], "id": "other"}]},
])
def test_invalid_topic_lists_are_refused_or_repaired(bad):
    if bad.get("topics") and isinstance(bad["topics"], list) and bad["topics"][0].get("id") == "other":
        assert T.validate(bad)["topics"][0]["id"] != "other"     # reserved id is renamed, not accepted
        return
    with pytest.raises(ValueError):
        T.save_topics(bad)


def test_a_corrupt_file_falls_back_to_defaults(tmp_path):
    (tmp_path / "research_topics.json").write_text("{not json")
    assert [t["id"] for t in T.load_topics()["topics"]] == ["biology", "finance", "cooking"]


def test_assign_topic_picks_the_closest_enabled_topic_or_other():
    data = T.validate({"min_similarity": 0.5, "topics": [
        {"name": "Biology", "examples": ["oyster mushroom temperature"]},
        {"name": "Finance", "examples": ["gold price", "silver price"]},
        {"name": "Cooking", "examples": ["eggs recipe"], "enabled": False},
    ]})
    enc = FakeEncoder()
    assert T.assign_topic("pink oyster mushroom fruiting", data, enc)[0] == "biology"
    assert T.assign_topic("gold price today", data, enc)[0] == "finance"
    assert T.assign_topic("boiled eggs recipe", data, enc)[0] == "other"     # cooking is disabled
    assert T.assign_topic("vfb stuttgart news", data, enc)[0] == "other"     # nothing close enough


def test_example_vectors_are_cached_between_searches():
    data = T.validate({"topics": [{"name": "Finance", "examples": ["gold price"]}]})
    enc = FakeEncoder()
    T.assign_topic("gold", data, enc)
    T.assign_topic("silver", data, enc)
    assert enc.calls == 3            # examples once, each query once


def test_assignment_never_raises():
    class Broken:
        def encode(self, *a, **k):
            raise RuntimeError("no model")
    assert T.assign_topic("gold price", T.load_topics(), Broken()) == ("other", 0.0)
    sid, topic = T.tag_search("gold price", T.load_topics(), Broken(), assign=True)
    assert len(sid) == 12 and topic == "other"
    assert T.tag_search("q", T.load_topics(), Broken(), assign=True)[0] != sid


def test_no_topic_and_no_model_while_the_filter_is_off(monkeypatch):
    from src import web_filter as F
    monkeypatch.setattr(F, "_settings", lambda: dict(F.DEFAULTS))
    monkeypatch.setattr(T, "_get_encoder", lambda: pytest.fail("embedding model loaded with the filter off"))
    sid, topic = T.tag_search("gold price")
    assert len(sid) == 12 and topic == ""
    monkeypatch.setattr(F, "_settings", lambda: {**F.DEFAULTS, "web_filter_enabled": True})
    monkeypatch.setattr(T, "_get_encoder", lambda: FakeEncoder())
    assert T.tag_search("gold price")[1] == "finance"


# -------------------------------------------------------------------- ratings

RATE = {"search_id": "abc123def456", "url": "https://grocycle.com/pink", "rating": "up",
        "query": "pink oyster", "topic": "biology", "title": "Pink oyster guide", "score": 0.4}


def test_latest_rating_wins_and_clear_removes_it():
    R.add_rating("cedrik", RATE)
    R.add_rating("cedrik", {**RATE, "rating": "down"})
    cur = R.current_ratings("cedrik")
    assert cur[("abc123def456", "https://grocycle.com/pink")]["rating"] == "down"
    R.add_rating("cedrik", {**RATE, "rating": "clear"})
    assert R.current_ratings("cedrik") == {}


def test_ratings_are_per_user():
    R.add_rating("cedrik", RATE)
    R.add_rating("guest", {**RATE, "rating": "down"})
    assert R.current_ratings("cedrik")[("abc123def456", RATE["url"])]["rating"] == "up"
    assert R.current_ratings("guest")[("abc123def456", RATE["url"])]["rating"] == "down"
    assert R.current_ratings("nobody") == {}


def test_counts_by_topic_use_current_ratings_only():
    R.add_rating("cedrik", RATE)
    R.add_rating("cedrik", {**RATE, "url": "https://x.com/a", "rating": "down"})
    R.add_rating("cedrik", {**RATE, "url": "https://x.com/b", "rating": "down", "topic": ""})
    R.add_rating("cedrik", {**RATE, "url": "https://x.com/b", "rating": "clear"})
    assert R.counts_by_topic("cedrik") == {"biology": {"up": 1, "down": 1}}


@pytest.mark.parametrize("bad", [
    {**RATE, "rating": "maybe"},
    {**RATE, "search_id": ""},
    {**RATE, "search_id": "../../etc"},
    {**RATE, "url": "javascript:alert(1)"},
    {**RATE, "url": "https://x/" + "a" * 2001},
    "not a dict",
])
def test_bad_ratings_are_refused(bad):
    with pytest.raises(ValueError):
        R.add_rating("cedrik", bad)


def test_a_garbled_line_does_not_hide_the_other_ratings(tmp_path):
    R.add_rating("cedrik", RATE)
    with open(tmp_path / "web_ratings.jsonl", "a") as f:
        f.write("{broken\n")
    R.add_rating("cedrik", {**RATE, "url": "https://x.com/a"})
    assert len(R.current_ratings("cedrik")) == 2


# ------------------------------------------------------------------------ API

@pytest.fixture
def client(monkeypatch, tmp_path):
    from routes import web_feedback_routes as W
    from src import web_filter as F
    monkeypatch.setattr(F, "_decision_log_path", lambda: str(tmp_path / "web_filter.jsonl"))
    admins = {"cedrik"}

    def fake_require_admin(request):
        if getattr(request.state, "current_user", None) not in admins:
            raise W.HTTPException(403, "Admin only")
    monkeypatch.setattr(W, "require_admin", fake_require_admin)
    app = FastAPI()

    @app.middleware("http")
    async def user_from_header(request: Request, call_next):
        request.state.current_user = request.headers.get("x-user")
        return await call_next(request)
    app.include_router(W.setup_web_feedback_routes())
    return TestClient(app)


def test_api_topics_read_by_anyone_written_by_admin_only(client):
    r = client.get("/api/research-topics", headers={"x-user": "guest"})
    assert r.status_code == 200 and [t["id"] for t in r.json()["topics"]] == ["biology", "finance", "cooking"]
    new = {"topics": [{"name": "Mycology", "examples": ["oyster mushroom"]}]}
    assert client.put("/api/research-topics", json=new, headers={"x-user": "guest"}).status_code == 403
    r = client.put("/api/research-topics", json=new, headers={"x-user": "cedrik"})
    assert r.status_code == 200 and r.json()["topics"][0]["id"] == "mycology"
    assert client.put("/api/research-topics", json={"topics": [{"name": "x"}]},
                      headers={"x-user": "cedrik"}).status_code == 400


def test_api_topics_carry_counts(client, tmp_path):
    (tmp_path / "web_filter.jsonl").write_text(
        json.dumps({"topic": "biology"}) + "\n" + json.dumps({"topic": "biology"}) + "\n" + json.dumps({"topic": ""}) + "\n")
    client.post("/api/web-ratings", json=RATE, headers={"x-user": "cedrik"})
    data = client.get("/api/research-topics", headers={"x-user": "cedrik"}).json()
    bio = [t for t in data["topics"] if t["id"] == "biology"][0]
    assert bio["searches"] == 2 and bio["ratings"] == {"up": 1, "down": 0}
    assert data["other"]["searches"] == 1


def test_api_ratings_round_trip_and_stay_per_user(client):
    assert client.post("/api/web-ratings", json=RATE, headers={"x-user": "cedrik"}).status_code == 200
    assert client.post("/api/web-ratings", json={**RATE, "rating": "x"}, headers={"x-user": "cedrik"}).status_code == 400
    got = client.get("/api/web-ratings?search_ids=abc123def456,other", headers={"x-user": "cedrik"}).json()
    assert got == {"ratings": {"abc123def456": {RATE["url"]: "up"}}}
    assert client.get("/api/web-ratings?search_ids=abc123def456", headers={"x-user": "guest"}).json() == {"ratings": {}}


# ------------------------------------------------------ filter settings API

def test_filter_settings_validation():
    from routes.web_feedback_routes import validate_filter_settings as V
    assert V({"web_filter_enabled": True, "web_filter_threshold": "0.04", "web_filter_candidates": 15}) == {
        "web_filter_enabled": True, "web_filter_threshold": 0.04, "web_filter_candidates": 15}
    for bad in ({"web_filter_enabled": "yes"}, {"web_filter_threshold": 2}, {"web_filter_threshold": "nan"},
                {"web_filter_candidates": 100}, {"web_filter_min_keep": 0}, {"search_provider": "x"}, []):
        with pytest.raises(ValueError):
            V(bad)


def test_api_filter_settings_read_by_anyone_written_by_admin_only(client, monkeypatch):
    import src.settings as S
    store = {"search_provider": "searxng", "web_filter_enabled": False}
    monkeypatch.setattr(S, "load_settings", lambda: dict(store))
    monkeypatch.setattr(S, "save_settings", lambda s: store.update(s))
    r = client.get("/api/web-filter/settings", headers={"x-user": "guest"})
    assert r.status_code == 200 and r.json()["web_filter_enabled"] is False
    assert set(r.json()) == {"web_filter_enabled", "web_filter_threshold", "web_filter_min_keep",
                             "web_filter_candidates", "web_filter_notice_below", "web_filter_decision_log"}
    body = {"web_filter_enabled": True, "web_filter_threshold": 0.04}
    assert client.put("/api/web-filter/settings", json=body, headers={"x-user": "guest"}).status_code == 403
    assert store["web_filter_enabled"] is False
    r = client.put("/api/web-filter/settings", json=body, headers={"x-user": "cedrik"})
    assert r.status_code == 200 and r.json()["web_filter_enabled"] is True and r.json()["web_filter_threshold"] == 0.04
    assert store["search_provider"] == "searxng"           # other settings untouched
    assert client.put("/api/web-filter/settings", json={"web_filter_threshold": 5},
                      headers={"x-user": "cedrik"}).status_code == 400
    assert client.put("/api/web-filter/settings", json={"search_provider": "duckduckgo"},
                      headers={"x-user": "cedrik"}).status_code == 400
    assert store["search_provider"] == "searxng"


def test_the_master_switch_turns_topic_matching_off():
    data = T.validate({"enabled": False, "topics": [{"name": "Finance", "examples": ["gold price"]}]})
    assert data["enabled"] is False
    enc = FakeEncoder()
    assert T.assign_topic("gold price today", data, enc) == ("other", 0.0)
    assert enc.calls == 0                                    # no model call while off
    assert T.validate({"topics": []})["enabled"] is True     # on unless switched off
    saved = T.save_topics({"enabled": False, "topics": [{"name": "A", "examples": ["a"]}]})
    assert T.load_topics()["enabled"] is False and saved["enabled"] is False
