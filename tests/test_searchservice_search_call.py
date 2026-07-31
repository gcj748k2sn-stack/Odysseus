"""Regression: SearchService.search() must call the (synchronous)
comprehensive_web_search correctly and return structured results.

The wrapper previously did:

    raw_results = await comprehensive_web_search(
        query, max_results=10 * depth, fetch_content=fetch_content)

which is broken three ways:
  * comprehensive_web_search is a plain `def` (sync), so `await` on its return
    raised TypeError;
  * it accepts neither `max_results` nor `fetch_content` (the real knob is
    `max_pages`), so the call raised TypeError on binding before running;
  * it returns a context string (or a (context, sources) tuple), not the list
    of dicts the wrapper then iterates.

SearchService.search is exported via services/search/__init__.py and
services/__init__.py (with a usage example in its own docstring), so this is a
broken public API method. This test drives it with a stubbed search backend.
"""
import asyncio

from services.search import service as search_service
from services.search.service import SearchService, SearchResponse


def test_search_returns_structured_results(monkeypatch):
    calls = {}

    def fake_search(query, max_pages=3, return_sources=False, **kwargs):
        calls["query"] = query
        calls["max_pages"] = max_pages
        calls["return_sources"] = return_sources
        calls["kwargs"] = kwargs
        sources = [{"url": "https://example.com", "title": "Example"}]
        return ("context text", sources) if return_sources else "context text"

    monkeypatch.setattr(search_service, "comprehensive_web_search", fake_search)

    svc = SearchService(default_depth=2)
    resp = asyncio.run(svc.search("python async patterns"))

    assert isinstance(resp, SearchResponse)
    assert resp.total == 1
    assert resp.results[0].url == "https://example.com"
    assert resp.results[0].title == "Example"

    # Called with the real param (max_pages, not max_results) and asked for the
    # structured source list rather than the context string.
    assert calls["return_sources"] is True
    assert calls["max_pages"] == 20  # 10 * depth(2)
    assert "max_results" not in calls["kwargs"]
    assert "fetch_content" not in calls["kwargs"]


def test_no_method_is_shadowed_by_an_instance_attribute():
    """A method and a `self.x` of the same name cannot coexist — the attribute wins.

    `SearchService.fetch_content` was an `async def` on the class AND a bool
    assigned in `__init__`. The attribute shadows the method on every instance,
    so `SearchService().fetch_content` is `True` and calling it raises
    "'bool' object is not callable" — the method was unreachable by
    construction. That is why it kept the SAME `await`-a-sync-function defect
    this file's other test was written for: the fix swept `search()` and left
    its sibling, and nothing could notice because the method could not run.

    Asserted structurally rather than behaviourally, like the `test_*_wiring.py`
    exception in tests/TESTING_STANDARD.md — the property being pinned *is* the
    shape of the class, and a behavioural test cannot reach a method that no
    instance exposes.

    MUTATION: re-add `async def fetch_content(self, url): ...` to SearchService
    -> this test fails and nothing else in the suite does, which is the whole
    point (that is the state the code shipped in).
    """
    import ast
    import inspect

    cls = next(
        n for n in ast.parse(inspect.getsource(search_service)).body
        if isinstance(n, ast.ClassDef) and n.name == "SearchService"
    )
    methods = {
        n.name for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    init = next(
        n for n in cls.body
        if isinstance(n, ast.FunctionDef) and n.name == "__init__"
    )
    attrs = {
        t.attr for n in ast.walk(init) if isinstance(n, ast.Assign)
        for t in n.targets if isinstance(t, ast.Attribute)
    }

    assert not (methods & attrs), (
        f"shadowed by an instance attribute, so unreachable: {sorted(methods & attrs)}"
    )
    # The constructor knob is the real API and must survive the deletion.
    assert SearchService(fetch_content=False).fetch_content is False
