"""Quoted-phrase filtering and engine attribution in the SearXNG provider.

Background — measured, not assumed. A replay of the 58 ``web_search`` calls
recorded in ``data/app.db`` (290 results) split cleanly on quoting:

    quoted queries   :  7 queries,  6 with junk (86%), 18/35 junk results (51%)
    unquoted queries : 51 queries,  1 with junk ( 2%),  3/255 junk results (1.2%)

The junk was locale-based filler the pinned engines (bing,mojeek,presearch)
backfill when a quoted phrase has few real matches: a Dutch casino, GitHub
Desktop, a hotel in Finnentrop, Psalm 37, a Stack Overflow thread about ``\\0``,
and five pages of the browser game "My Little Farmies". One quoted query came
back 5/5 junk.

Requiring the quoted phrase to actually appear in a result dropped 18/18 of
that junk with 0 false positives across the recorded corpus. This is not a
relevance heuristic: it is the semantics of quoting. A result that does not
contain the phrase the caller asked for verbatim is non-responsive.

Two things this file deliberately pins beyond the happy path:

  * the NEGATIVE CONTROLS — an unquoted query and a quoted query whose results
    all contain the phrase must both come through untouched. A filter with only
    positive cases can be a function that always fires and still look correct.
  * the filter must run BEFORE the ``[:count]`` slice, so dropped slots are
    refilled from further down the engine's list rather than just shrinking an
    already-truncated window.
"""

import pytest

from services.search import providers


# --- helpers ---------------------------------------------------------------

def _response(results):
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": results}

    return _Resp()


def _searxng(monkeypatch, results, count=5):
    """Point the provider at a fake SearXNG returning ``results``."""
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"])
        payload = results.pop(0) if isinstance(results, list) and results and isinstance(results[0], list) else results
        return _response(payload)

    monkeypatch.setattr(providers, "_get_search_instance", lambda: "http://searx.test")
    monkeypatch.setattr(providers, "_get_search_settings", lambda: {"search_safesearch": "strict"})
    monkeypatch.setattr(providers.httpx, "get", fake_get)
    return calls


def _r(title, url, content="", engine="bing"):
    return {"title": title, "url": url, "content": content, "engine": engine}


# --- phrase extraction -----------------------------------------------------

def test_quoted_phrases_extracts_each_phrase_lowercased():
    assert providers.quoted_phrases('"Pleurotus djamor" "pink oyster" guide') == [
        "pleurotus djamor", "pink oyster",
    ]


def test_quoted_phrases_ignores_empty_quotes():
    # A stray quote pair must not yield a phrase that matches everything.
    assert providers.quoted_phrases('mushroom "" guide') == []
    assert providers.quoted_phrases('mushroom "   " guide') == []


def test_quoted_phrases_returns_nothing_for_unquoted_query():
    assert providers.quoted_phrases("pink oyster mushroom growth phases") == []


def test_strip_quotes_removes_quote_characters():
    assert providers.strip_quotes('"Pleurotus djamor" cultivation') == "Pleurotus djamor cultivation"


# --- result_has_phrases ----------------------------------------------------

def test_result_has_phrases_matches_across_title_snippet_and_url():
    phrases = ["pleurotus djamor"]
    assert providers.result_has_phrases(_r("Pleurotus djamor guide", "https://x.test"), phrases)
    assert providers.result_has_phrases(_r("Guide", "https://x.test", "on pleurotus djamor"), phrases)
    # URL separators are normalised to spaces, so a real slug matches.
    assert providers.result_has_phrases(_r("Guide", "https://x.test/pleurotus-djamor-guide"), phrases)


def test_result_has_phrases_requires_every_phrase():
    r = _r("Pleurotus djamor guide", "https://x.test")
    assert providers.result_has_phrases(r, ["pleurotus djamor"]) is True
    assert providers.result_has_phrases(r, ["pleurotus djamor", "pink oyster"]) is False


def test_result_has_phrases_is_vacuously_true_with_no_phrases():
    # NEGATIVE CONTROL: with no phrases the predicate must never reject.
    assert providers.result_has_phrases(_r("anything", "https://x.test"), []) is True


# --- filtering inside searxng_search_api -----------------------------------

def test_quoted_query_drops_results_missing_the_phrase(monkeypatch):
    # Shape taken from a recorded failure: a real P. djamor page plus the
    # locale filler that surrounded it.
    _searxng(monkeypatch, [
        _r("Cultivation of Pleurotus djamor", "https://academia.test/djamor"),
        _r("Luckygem Casino | Hoge Bonussen", "https://theluckygem.nl/"),
        _r("Psalm 37 - Lutherbibel 2017", "https://www.die-bibel.de/psalm-37"),
    ])
    out = providers.searxng_search_api('"Pleurotus djamor" cultivation', count=5)
    assert [r["url"] for r in out] == ["https://academia.test/djamor"]


def test_unquoted_query_is_left_untouched(monkeypatch):
    """NEGATIVE CONTROL: the filter must not fire without quotes.

    These are the same off-topic results as above. Without quoting there is no
    phrase contract to enforce, so every result must survive -- otherwise the
    filter is doing relevance judgement it has no evidence for.
    """
    _searxng(monkeypatch, [
        _r("Cultivation of Pleurotus djamor", "https://academia.test/djamor"),
        _r("Luckygem Casino | Hoge Bonussen", "https://theluckygem.nl/"),
        _r("Psalm 37 - Lutherbibel 2017", "https://www.die-bibel.de/psalm-37"),
    ])
    out = providers.searxng_search_api("Pleurotus djamor cultivation", count=5)
    assert len(out) == 3


def test_quoted_query_with_all_matching_results_drops_nothing(monkeypatch):
    """NEGATIVE CONTROL: a quoted query whose results all contain the phrase.

    One of the seven recorded quoted queries was clean (5/5 contained the
    phrase). That case must pass through unchanged.
    """
    _searxng(monkeypatch, [
        _r("Pleurotus djamor A", "https://a.test"),
        _r("Guide", "https://b.test", "about Pleurotus djamor yield"),
        _r("C", "https://c.test/pleurotus-djamor-guide"),
    ])
    out = providers.searxng_search_api('"Pleurotus djamor" cultivation', count=5)
    assert len(out) == 3


def test_filter_runs_before_the_count_slice(monkeypatch):
    """Dropped slots are refilled from further down, not left short.

    With count=2 and the two responsive results sitting at positions 3 and 4,
    filtering after the slice would return nothing. Filtering before it returns
    both.
    """
    _searxng(monkeypatch, [
        _r("Casino", "https://junk1.test"),
        _r("Hotel", "https://junk2.test"),
        _r("Pleurotus djamor guide", "https://good1.test"),
        _r("Pleurotus djamor yields", "https://good2.test"),
        _r("Pleurotus djamor substrate", "https://good3.test"),
    ])
    out = providers.searxng_search_api('"Pleurotus djamor"', count=2)
    assert [r["url"] for r in out] == ["https://good1.test", "https://good2.test"]


def test_all_results_filtered_triggers_unquoted_retry(monkeypatch):
    """The 5/5-junk case: fall back rather than return an empty search.

    The phrase check runs over title/snippet/url only, so a page whose *body*
    contains the phrase can be dropped. The unquoted retry is what stops that
    from turning into a failed search.
    """
    calls = _searxng(monkeypatch, [
        # first response: nothing contains the phrase
        [_r("My Little Farmies", "https://spiele.rtl.de/my-little-farmies"),
         _r("GitHub Desktop", "https://desktop.github.com/download/")],
        # retry response
        [_r("Pink oyster growing guide", "https://growmushrooms.test/guide")],
    ])
    out = providers.searxng_search_api('"Pleurotus djamor" mushroom cultivation', count=5)

    assert [c["q"] for c in calls] == [
        '"Pleurotus djamor" mushroom cultivation',
        "Pleurotus djamor mushroom cultivation",
    ]
    assert [r["url"] for r in out] == ["https://growmushrooms.test/guide"]


def test_unquoted_retry_does_not_refilter_on_the_original_phrases(monkeypatch):
    """Regression guard for the retry ladder.

    The retry rewrites the query; filtering the rewritten query's results
    against the original phrases would drop exactly the results the rewrite was
    meant to find, and the search would come back empty for the wrong reason.
    """
    _searxng(monkeypatch, [
        [_r("Casino", "https://junk.test")],
        [_r("Oyster mushroom guide", "https://good.test")],  # no "pleurotus djamor"
    ])
    out = providers.searxng_search_api('"Pleurotus djamor" cultivation', count=5)
    assert [r["url"] for r in out] == ["https://good.test"]


# --- engine attribution ----------------------------------------------------

def test_engine_is_carried_through_parsing(monkeypatch):
    _searxng(monkeypatch, [
        _r("A", "https://a.test", engine="bing"),
        _r("B", "https://b.test", engine="mojeek"),
    ])
    out = providers.searxng_search_api("oyster mushroom", count=5)
    assert [r["engine"] for r in out] == ["bing", "mojeek"]


def test_engine_falls_back_to_the_engines_list(monkeypatch):
    results = [{"title": "A", "url": "https://a.test", "content": "",
                "engines": ["bing", "mojeek"]}]
    _searxng(monkeypatch, results)
    out = providers.searxng_search_api("oyster mushroom", count=5)
    assert out[0]["engine"] == "bing,mojeek"


def test_missing_engine_is_empty_string_not_a_crash(monkeypatch):
    _searxng(monkeypatch, [{"title": "A", "url": "https://a.test", "content": ""}])
    out = providers.searxng_search_api("oyster mushroom", count=5)
    assert out[0]["engine"] == ""
