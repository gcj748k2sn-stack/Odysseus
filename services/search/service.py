# services/search/service.py
"""Search service — clean interface for web search."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from . import (
    comprehensive_web_search,
    get_search_config,
)


@dataclass
class SearchResult:
    """A single search result."""
    url: str
    title: str
    snippet: str
    content: Optional[str] = None


@dataclass
class SearchResponse:
    """Response from a search query."""
    query: str
    results: List[SearchResult]
    total: int
    cached: bool = False


class SearchService:
    """
    Web search service.

    Usage:
        service = SearchService()
        result = await service.search("python async patterns")
        for r in result.results:
            print(f"{r.title}: {r.url}")
    """

    def __init__(self, default_depth: int = 1, fetch_content: bool = True):
        self.default_depth = default_depth
        self.fetch_content = fetch_content

    async def search(
        self,
        query: str,
        depth: Optional[int] = None,
        fetch_content: Optional[bool] = None,
    ) -> SearchResponse:
        """
        Search the web.

        Args:
            query: Search query
            depth: Search depth (1=quick, 2=thorough, 3=comprehensive)
            fetch_content: Whether to fetch full page content

        Returns:
            SearchResponse with results
        """
        depth = depth or self.default_depth

        # comprehensive_web_search is synchronous and, with return_sources=True,
        # returns (context_str, [{"url", "title"}, ...]). Run it off the event
        # loop so we don't block it, and use the source list as the result rows.
        # `fetch_content` is accepted for API compatibility; the comprehensive
        # search always fetches page content.
        import asyncio
        _context, raw_results = await asyncio.to_thread(
            comprehensive_web_search,
            query,
            max_pages=10 * depth,
            return_sources=True,
        )

        results = []
        for r in raw_results:
            if not isinstance(r, dict):
                continue
            results.append(SearchResult(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("snippet", ""),
                content=r.get("content"),
            ))

        return SearchResponse(
            query=query,
            results=results,
            total=len(results),
        )

    # `async def fetch_content(self, url)` used to live here and was deleted
    # 2026-07-31. It carried three defects at once and could never run:
    #   1. it awaited `fetch_webpage_content`, which is synchronous and returns
    #      a dict — `await` on a dict raises TypeError;
    #   2. it annotated itself `-> Optional[str]` while returning that dict;
    #   3. `__init__` sets `self.fetch_content = fetch_content` (a bool), which
    #      SHADOWS the method on every instance — `SearchService().fetch_content`
    #      is `True`, and calling it raises "'bool' object is not callable".
    # (3) is why (1) and (2) never surfaced: the method was unreachable by
    # construction. Deleted rather than repaired — renaming it to free the
    # attribute would have resurrected two live bugs. The `fetch_content`
    # constructor and `search()` parameters are the real knob and stay.
    # Callers wanting a single page use `services.search.fetch_webpage_content`.

    def get_config(self) -> Dict[str, Any]:
        """Get current search configuration."""
        return get_search_config()
