"""src/search_output_fit.py: a web_search result that is too long loses page
text, never its closing instructions (fork; notes item 71).

Built against the real writer (comprehensive_web_search with providers and
fetches stubbed), because the fitter finds head, pages and tail by the
writer's own markers: a format change upstream must fail here.
"""
import asyncio

import pytest

from src.search_output_fit import SHORTENED, fit_search_output

PAGE = ("Pink oysters fruit at 20-30 C. They need high humidity and fresh air. " * 60).strip()


def _real_output(monkeypatch, n_pages=5, page=PAGE):
    from services.search import core
    results = [{"title": f"Guide {i}", "url": f"https://site{i}.example/p", "snippet": "pink oyster temperature"}
               for i in range(n_pages)]
    monkeypatch.setattr(core, "_get_search_settings", lambda: {"search_provider": "searxng"})
    monkeypatch.setattr(core, "_get_result_count", lambda: n_pages)
    monkeypatch.setattr(core, "_build_provider_chain", lambda primary: ["searxng"])
    monkeypatch.setattr(core, "_call_provider", lambda *a, **k: [dict(r) for r in results])
    monkeypatch.setattr(core, "fetch_webpage_content", lambda url, *a, **k: {
        "success": True, "url": url, "title": "T " + url, "content": page})
    return core.comprehensive_web_search("pink oyster pinning temperature", max_pages=n_pages)


def test_short_output_is_untouched(monkeypatch):
    text = _real_output(monkeypatch, n_pages=1, page="short page")
    assert fit_search_output(text, 10_000) == text


def test_long_output_keeps_head_and_instructions_and_shortens_pages(monkeypatch):
    text = _real_output(monkeypatch)
    assert len(text) > 10_000
    out = fit_search_output(text, 10_000)
    assert len(out) <= 10_000
    assert out.rstrip().endswith(text.rstrip()[-200:])             # the tail is whole
    assert "IMPORTANT INSTRUCTIONS" in out and "END OF WEB SEARCH RESULTS" in out
    assert out.startswith(text[:text.index("FETCHED PAGE CONTENT:")])   # the head is whole
    for i in range(5):
        assert f"[CONTENT {i + 1}] From: https://site{i}.example/p" in out  # every page keeps its header
    assert out.count(SHORTENED) == 5


def test_pages_are_cut_at_sentence_ends(monkeypatch):
    out = fit_search_output(_real_output(monkeypatch), 10_000)
    for piece in out.split(SHORTENED)[:-1]:
        assert piece.rstrip().endswith((".", "C", ":")) or piece.endswith("\n")


def test_a_short_page_gives_its_share_to_the_long_ones():
    head = "```sources\n[1] a\n```\nSEARCH RESULTS SUMMARY:\n" + "\nFETCHED PAGE CONTENT:\n" + "-" * 50
    blocks = "\n[CONTENT 1] From: https://a\nshort.\n" + "\n[CONTENT 2] From: https://b\n" + ("Long sentence here. " * 400)
    tail = "\n" + "=" * 70 + "\nEND OF WEB SEARCH RESULTS\n" + "=" * 70 + "\n\nIMPORTANT INSTRUCTIONS:\n1. answer"
    out = fit_search_output(head + blocks + tail, 2000)
    assert len(out) <= 2000 and out.endswith("1. answer")
    assert "short." in out and SHORTENED in out
    assert len(out) > 1800                                   # the budget is used, not wasted


def test_text_without_the_markers_falls_back_to_the_plain_cut():
    assert fit_search_output("x" * 50, 20) == "x" * 20
    assert fit_search_output("Web search failed — " + "y" * 50, 10) == "Web search failed — "[:10]


def test_a_huge_summary_still_keeps_the_instructions():
    head = "SEARCH RESULTS SUMMARY:\n" + ("[1] t\n    Snippet: s...\n" * 500) + "\nFETCHED PAGE CONTENT:\n" + "-" * 50
    tail = "\n" + "=" * 70 + "\nEND OF WEB SEARCH RESULTS\n\nIMPORTANT INSTRUCTIONS: answer"
    out = fit_search_output(head + "\n[CONTENT 1] From: https://a\npage" + tail, 1000)
    assert len(out) <= 1000 and out.endswith("IMPORTANT INSTRUCTIONS: answer")


def test_the_web_search_tool_uses_the_fitter(monkeypatch):
    text = _real_output(monkeypatch)
    import src.search as S
    from src.agent_tools.web_tools import WebSearchTool
    monkeypatch.setattr(S, "comprehensive_web_search", lambda *a, **k: (text, []))
    out = asyncio.run(WebSearchTool().execute("pink oyster", {}))["output"]
    assert len(out) <= 10_000 and "IMPORTANT INSTRUCTIONS" in out
