"""A cache hit must be distinguishable from a live fetch.

`fetch_webpage_content` caches for 2h. Nothing in the result, the tool output or
`tool_events` said which you got — same shape, same `exit_code`. That has already
produced a wrong conclusion: two turns 4.5 minutes apart both reported
`uptime: 91 s` from a device whose counter was running, and read back from
`app.db` the second looked like a fresh reading of a frozen device. See
notes/todo.md, "A cache hit is indistinguishable from a live fetch".

Covers both halves of the path: the cache read labelling the dict it serves, and
the web_fetch tool surfacing that to the model and onto the tool event.

Writes only into a temp cache dir — never the live one. Calling
`fetch_webpage_content()` against the real tree writes into the cache the running
instance reads, and doing exactly that once put a fabricated value in front of
the model, which recorded it in a user document as a measurement.
"""
import asyncio
import json
from datetime import datetime, timedelta

import pytest

import services.search.content as content_mod
from src.agent_tools.web_tools import WebFetchTool


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    d = tmp_path / "content"
    d.mkdir()
    monkeypatch.setattr(content_mod, "CONTENT_CACHE_DIR", d)
    monkeypatch.setattr(content_mod, "content_cache_index", {}, raising=False)
    return d


def _write_entry(cache_dir, url, payload, *, age_seconds):
    """Seed a cache entry as if it had been written `age_seconds` ago."""
    cap = content_mod.WEB_FETCH_SOFT_MAX_BYTES
    key = content_mod.generate_cache_key(f"{url}#cap={cap}")
    ts = datetime.now() - timedelta(seconds=age_seconds)
    (cache_dir / f"{key}.cache").write_text(
        json.dumps({"timestamp": ts.isoformat(), "data": payload}),
        encoding="utf-8",
    )


def test_cache_hit_is_labelled_with_its_age(cache_dir):
    url = "http://192.168.1.42/state"
    _write_entry(cache_dir, url, {"content": "uptime: 91 s", "title": "esp32"},
                 age_seconds=270)

    got = content_mod.fetch_webpage_content(url)

    assert got["cached"] is True
    assert got["cache_age_seconds"] == pytest.approx(270, abs=5)
    assert got["cached_at"]
    assert got["content"] == "uptime: 91 s"


def test_labelling_does_not_mutate_the_cached_dict(cache_dir):
    """The served dict is a copy; the entry on disk keeps its own shape."""
    url = "http://192.168.1.42/state"
    payload = {"content": "body", "title": "t"}
    _write_entry(cache_dir, url, payload, age_seconds=10)

    first = content_mod.fetch_webpage_content(url)
    first["content"] = "caller scribbled here"

    second = content_mod.fetch_webpage_content(url)
    assert second["content"] == "body", "a caller mutating the result corrupted the cache"
    assert second["cached"] is True


def test_expired_entry_is_not_served_as_a_cache_hit(cache_dir, monkeypatch):
    """Past the 2h TTL the entry is dropped, not returned with a stale label."""
    url = "http://example.com/"
    _write_entry(cache_dir, url, {"content": "old", "title": ""}, age_seconds=3 * 3600)

    def _boom(*a, **k):
        raise AssertionError("expired entry served instead of refetching")

    monkeypatch.setattr(content_mod, "_get_public_url", _boom)
    with pytest.raises(AssertionError):
        content_mod.fetch_webpage_content(url)


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_tool_output_warns_the_model_and_flags_the_event(monkeypatch):
    """web_fetch must tell the model the body is cached, and flag the event."""
    monkeypatch.setattr(
        "src.search.content.fetch_webpage_content",
        lambda url, **kw: {
            "content": "uptime: 91 s",
            "title": "esp32",
            "cached": True,
            "cached_at": "2026-07-27T18:02:00",
            "cache_age_seconds": 270,
        },
        raising=False,
    )
    out = _run(WebFetchTool().execute("http://192.168.1.42/state", {}))

    assert out["exit_code"] == 0
    assert out["cached"] is True
    assert out["cache_age_seconds"] == 270
    # The model has to see it: it cannot infer staleness, and the failure this
    # guards was the model reporting a cached counter as a live measurement.
    assert "cache" in out["output"].lower()
    assert "4 min" in out["output"]
    assert "NOT a live reading" in out["output"]


def test_cache_notice_survives_the_output_cap(monkeypatch):
    """A huge body must not push the notice past MAX_OUTPUT_CHARS."""
    monkeypatch.setattr(
        "src.search.content.fetch_webpage_content",
        lambda url, **kw: {
            "content": "z" * 400_000,
            "title": "q" * 5000,
            "cached": True,
            "cached_at": "2026-07-27T18:02:00",
            "cache_age_seconds": 30,
        },
        raising=False,
    )
    out = _run(WebFetchTool().execute("http://example.com/", {}))
    assert "NOT a live reading" in out["output"]


def test_live_fetch_carries_no_cache_keys(monkeypatch):
    """Absence of the flag is what marks a fetch as live — keep it absent."""
    monkeypatch.setattr(
        "src.search.content.fetch_webpage_content",
        lambda url, **kw: {"content": "fresh body", "title": "t"},
        raising=False,
    )
    out = _run(WebFetchTool().execute("http://example.com/", {}))

    assert out["exit_code"] == 0
    assert "cached" not in out
    assert "cache" not in out["output"].lower()
