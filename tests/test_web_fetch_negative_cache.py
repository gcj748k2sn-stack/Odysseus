"""A URL that fails permanently must be requested once, not once per appearance.

Successful fetches have been cached for 2 h; failures were not cached at all, so
every re-appearance of a dead URL cost another round trip. Measured 2026-07-31 in
session 93c1c383: one ResearchGate URL returning 403 was fetched **four times**
inside a single agent turn — three because ``web_search`` fetches its own top
results and that URL ranked top-3 for all three of the model's queries, plus one
explicit ``web_fetch``. Requests 2-4 could not return anything request 1 did not.

The risk this introduces is the mirror image — remembering a failure that was
only ever transient — so the tests below spend more effort on what must NOT be
cached than on what must. ``_PERMANENT_HTTP_STATUSES`` is a closed allowlist for
that reason.

MUTATIONS RUN AGAINST THIS FILE (record the mutation, not just the score — a
number nobody can re-derive is worse than no number):

  1. Widen ``_PERMANENT_HTTP_STATUSES`` to include 429 or 500
     -> ``test_rate_limit_is_not_remembered`` and ``test_server_error_is_not_remembered``
        fail; every other test still passes. This is the mutation that matters:
        without those two the allowlist could silently become "anything that
        raised" and the suite would stay green.
  2. Drop the ``_is_local_target`` check in ``_negative_cache_store``
     -> ``test_lan_failure_is_not_remembered`` fails, nothing else does.
  3. Drop the TTL comparison in ``_negative_cache_lookup`` (always serve)
     -> ``test_entry_expires`` fails.
  4. Stop setting ``cached``/``cache_age_seconds`` on the served failure
     -> ``test_remembered_failure_is_labelled`` and the two web_fetch tool tests
        fail. The negative control ``test_fresh_failure_carries_no_cache_keys``
        stays green in ALL FOUR states above, which is what makes it a control.

Writes only into a temp cache dir and clears module state between tests — the
negative cache is process-global, and ``fetch_webpage_content`` against the live
tree writes into the cache the running instance reads.
"""
import asyncio

import httpx
import pytest

import services.search.content as content_mod
from src.agent_tools.web_tools import WebFetchTool


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Temp cache dir, and an empty negative cache — it is module-global."""
    d = tmp_path / "content"
    d.mkdir()
    monkeypatch.setattr(content_mod, "CONTENT_CACHE_DIR", d)
    monkeypatch.setattr(content_mod, "content_cache_index", {}, raising=False)
    content_mod.clear_negative_cache()
    yield
    content_mod.clear_negative_cache()


def _responder(monkeypatch, status):
    """Patch the fetch to return ``status`` and count how often it is called."""
    calls = []

    def _fake(url, headers=None, timeout=None, max_bytes=None, **kw):
        calls.append(url)
        return httpx.Response(status, request=httpx.Request("GET", url))

    monkeypatch.setattr(content_mod, "_get_public_url", _fake)
    return calls


RG = ("https://www.researchgate.net/publication/377402725_Optimal_Culture_"
      "Conditions_for_the_Enhanced_Mycelial_Growth")


# ── what must be remembered ──────────────────────────────────────────────────

@pytest.mark.parametrize("status", [401, 403, 404, 410, 451])
def test_permanent_failure_is_requested_once(monkeypatch, status):
    calls = _responder(monkeypatch, status)

    first = content_mod.fetch_webpage_content(RG)
    second = content_mod.fetch_webpage_content(RG)

    assert len(calls) == 1, f"HTTP {status} was re-requested {len(calls)} times"
    assert first["success"] is False and second["success"] is False
    # The served error is byte-identical to the live one, so nothing downstream
    # has to learn a second shape.
    assert second["error"] == first["error"]


def test_remembered_failure_is_labelled(monkeypatch):
    """An unlabelled cache hit is indistinguishable from a live call in app.db.

    That mistake was already made once on the SUCCESS path and produced a wrong
    conclusion about a frozen device. The failure path must not repeat it.
    """
    _responder(monkeypatch, 403)
    content_mod.fetch_webpage_content(RG)

    served = content_mod.fetch_webpage_content(RG)
    assert served["cached"] is True
    assert served["http_status"] == 403
    assert served["cached_at"]
    assert isinstance(served["cache_age_seconds"], int)


def test_fresh_failure_carries_no_cache_keys(monkeypatch):
    """NEGATIVE CONTROL. Absence of the flag is what marks a real attempt.

    Stays green under every mutation listed in the module docstring; if this one
    ever fails, the labelling has started firing on calls that did leave the
    machine and the flag means nothing.
    """
    _responder(monkeypatch, 403)
    first = content_mod.fetch_webpage_content(RG)
    assert "cached" not in first
    assert "http_status" not in first


def test_entry_expires(monkeypatch):
    """Past the TTL the URL is tried again rather than served as remembered."""
    calls = _responder(monkeypatch, 403)
    content_mod.fetch_webpage_content(RG)
    assert len(calls) == 1

    monkeypatch.setattr(content_mod, "_NEGATIVE_CACHE_TTL",
                        content_mod.timedelta(seconds=0))
    content_mod.fetch_webpage_content(RG)
    assert len(calls) == 2, "expired entry was served instead of re-fetched"


# ── what must NOT be remembered (the risk this change introduces) ────────────

def test_rate_limit_is_not_remembered(monkeypatch):
    """429 is 'try later'. Caching it turns a rate limit into a 30-min outage."""
    calls = _responder(monkeypatch, 429)

    content_mod.fetch_webpage_content(RG)
    content_mod.fetch_webpage_content(RG)

    assert len(calls) == 2


def test_server_error_is_not_remembered(monkeypatch):
    """5xx is the server having a bad minute, not a permanent verdict."""
    calls = _responder(monkeypatch, 503)

    content_mod.fetch_webpage_content(RG)
    content_mod.fetch_webpage_content(RG)

    assert len(calls) == 2


def test_network_error_is_not_remembered(monkeypatch):
    """A transport failure says nothing about the URL."""
    calls = []

    def _fake(url, **kw):
        calls.append(url)
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(content_mod, "_get_public_url", _fake)
    content_mod.fetch_webpage_content("https://example.com/x")
    content_mod.fetch_webpage_content("https://example.com/x")

    assert len(calls) == 2


@pytest.mark.parametrize("url", [
    "http://192.168.1.42/state",
    "http://127.0.0.1:8080/api",
    "http://esp32.local/status",
    "http://localhost/x",
])
def test_lan_failure_is_not_remembered(monkeypatch, url):
    """A LAN device answering 403 is the case the user fixes and retries.

    Remembering it means the retry silently does not happen, which is worse
    than the extra request this change exists to avoid.
    """
    calls = _responder(monkeypatch, 403)

    content_mod.fetch_webpage_content(url)
    content_mod.fetch_webpage_content(url)

    assert len(calls) == 2, f"{url} was remembered as permanently broken"


def test_a_good_body_still_wins(monkeypatch):
    """The positive cache is checked first; a remembered failure never hides content."""
    calls = _responder(monkeypatch, 403)
    content_mod.fetch_webpage_content(RG)
    assert len(calls) == 1

    import json
    from datetime import datetime
    key = content_mod.generate_cache_key(f"{RG}#cap={content_mod.WEB_FETCH_SOFT_MAX_BYTES}")
    (content_mod.CONTENT_CACHE_DIR / f"{key}.cache").write_text(
        json.dumps({"timestamp": datetime.now().isoformat(),
                    "data": {"content": "real body", "title": "t"}}),
        encoding="utf-8",
    )

    got = content_mod.fetch_webpage_content(RG)
    assert got["content"] == "real body"


def test_cache_is_bounded(monkeypatch):
    """Unbounded growth keyed on URLs is a leak in a long-running process."""
    _responder(monkeypatch, 403)
    limit = content_mod._NEGATIVE_CACHE_MAX_ENTRIES
    for i in range(limit + 25):
        content_mod.fetch_webpage_content(f"https://example.com/{i}")

    assert len(content_mod._negative_cache) <= limit


def test_bound_holds_under_concurrent_stores():
    """The parallel path is the NORMAL path, not an edge case.

    ``comprehensive_web_search`` fetches its top results through a
    ThreadPoolExecutor, which is exactly the code that produced the repeated
    403s this cache exists to stop. Individual dict ops are atomic under the
    GIL; the read-then-evict sequence is not. Without the lock this is the
    test that goes flaky rather than red — so treat any intermittent failure
    here as a real result, not noise.
    """
    import threading

    limit = content_mod._NEGATIVE_CACHE_MAX_ENTRIES
    errors = []

    def worker(base):
        try:
            for i in range(200):
                content_mod._negative_cache_store(
                    f"https://example.com/{base}/{i}", 403, "HTTP 403: nope")
        except Exception as e:  # pragma: no cover - only on a real race
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent stores raised: {errors}"
    assert len(content_mod._negative_cache) <= limit


def test_manual_retry_path_is_reachable():
    """The docstring promises a manual retry; an unexported function is not one.

    Pins the export, not the behaviour — `clear_negative_cache` was written
    before anything could reach it from outside the module.
    """
    from services.search import clear_negative_cache as exported

    assert exported is content_mod.clear_negative_cache


# ── the model's view ─────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_tool_tells_the_model_it_was_not_re_requested(monkeypatch):
    """Otherwise the model reads a memory as a fresh attempt and retries again."""
    monkeypatch.setattr(
        "src.search.content.fetch_webpage_content",
        lambda url, **kw: {
            "content": "", "title": "", "error": "HTTP 403: forbidden",
            "cached": True, "cached_at": "2026-07-31T18:16:23",
            "cache_age_seconds": 154,
        },
        raising=False,
    )
    out = _run(WebFetchTool().execute(RG, {}))

    assert out["exit_code"] == 1
    assert out["cached"] is True
    assert out["cache_age_seconds"] == 154
    assert "NOT re-requested" in out["error"]
    assert "2 min 34 s ago" in out["error"]


def test_fresh_tool_failure_is_not_labelled(monkeypatch):
    """NEGATIVE CONTROL for the tool half — a real 403 must look like one."""
    monkeypatch.setattr(
        "src.search.content.fetch_webpage_content",
        lambda url, **kw: {"content": "", "title": "", "error": "HTTP 403: forbidden"},
        raising=False,
    )
    out = _run(WebFetchTool().execute(RG, {}))

    assert out["exit_code"] == 1
    assert "cached" not in out
    assert "NOT re-requested" not in out["error"]
