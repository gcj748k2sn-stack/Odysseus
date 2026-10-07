"""Webpage content fetching with caching, PDF extraction, and summarization helpers."""

import copy
import io
import ipaddress
import json
import os
import re
import logging
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import List
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from src.constants import WEB_FETCH_SOFT_MAX_BYTES, WEB_FETCH_HARD_MAX_BYTES, WEB_FETCH_USER_AGENT
from src import outbound_fetch as _outbound_fetch

from .analytics import RateLimitError, error_logger
from .cache import (
    CONTENT_CACHE_DIR,
    content_cache_index,
    generate_cache_key,
    cleanup_cache,
)

logger = logging.getLogger(__name__)

def _is_private_address(addr):
    return _outbound_fetch._is_private_address(addr)


# The SSRF policy, including the two-tier LAN opt-in
# (WEB_FETCH_BLOCK_PRIVATE_IPS), lives in src/outbound_fetch.py since upstream
# moved the transport there. These wrappers keep this module's names and
# resolve through this module's _resolve_hostname_ips / _resolve_public_ips, so
# tests that monkeypatch them here still steer the real fetch path.
_is_hard_blocked_address = _outbound_fetch._is_hard_blocked_address
_is_gated_private_address = _outbound_fetch._is_gated_private_address


def _private_targets_allowed():
    return _outbound_fetch._private_targets_allowed()


def _resolve_hostname_ips(hostname):
    return _outbound_fetch._resolve_hostname_ips(hostname)


def _public_http_url(url, *, allow_private=False):
    return _outbound_fetch._public_http_url(
        url, resolver=_resolve_hostname_ips, allow_private=allow_private
    )


def _resolve_public_ips(url, *, allow_private=False):
    return _outbound_fetch._resolve_public_ips(
        url, resolver=_resolve_hostname_ips, allow_private=allow_private
    )


_PinnedBackend = _outbound_fetch._PinnedBackend
_PinnedTransport = _outbound_fetch._PinnedTransport
BodyTooLargeError = _outbound_fetch.BodyTooLargeError
_CappedFetch = _outbound_fetch._CappedFetch


def _get_public_url(url, headers, timeout, max_redirects=5, max_bytes=None,
                    allow_private=None):
    """See ``src.outbound_fetch._get_public_url``. ``allow_private`` applies to
    the first hop only and defaults to WEB_FETCH_BLOCK_PRIVATE_IPS."""
    if allow_private is None:
        allow_private = _private_targets_allowed()
    return _outbound_fetch._get_public_url(
        url,
        headers=headers,
        timeout=timeout,
        max_redirects=max_redirects,
        max_bytes=max_bytes,
        allow_private=allow_private,
        resolve_public_ips=_resolve_public_ips,
        transport_factory=_PinnedTransport,
    )


# PDF extraction (optional dependency)
try:
    from pdfminer.high_level import extract_text as pdf_extract_text
except ImportError:
    pdf_extract_text = None  # type: ignore


# ----------------------------------------------------------------------
# HTML extraction helpers
# ----------------------------------------------------------------------
def _extract_meta(soup: BeautifulSoup) -> dict:
    """Pull meta description and keywords if present."""
    description = ""
    keywords = ""
    desc_tag = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    if desc_tag and desc_tag.get("content"):
        description = desc_tag["content"].strip()
    kw_tag = soup.find("meta", attrs={"name": re.compile("keywords", re.I)})
    if kw_tag and kw_tag.get("content"):
        keywords = kw_tag["content"].strip()
    return {"description": description, "keywords": keywords}


def _extract_og_image(soup: BeautifulSoup) -> str:
    """Extract the best representative image URL from meta tags.

    Only returns absolute http(s) URLs -- skips relative paths and data URIs.
    """
    candidates = []
    for prop in ("og:image", "og:image:url", "og:image:secure_url"):
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content", "").strip():
            candidates.append(tag["content"].strip())
    tag = soup.find("meta", attrs={"name": "twitter:image"})
    if tag and tag.get("content", "").strip():
        candidates.append(tag["content"].strip())
    tag = soup.find("meta", attrs={"name": "thumbnail"})
    if tag and tag.get("content", "").strip():
        candidates.append(tag["content"].strip())
    for url in candidates:
        if url.startswith(("https://", "http://")) and not url.endswith((".svg", ".ico")):
            return url
    return ""


def _extract_lists(soup: BeautifulSoup) -> List[List[str]]:
    """Return a list of lists, each inner list representing a <ul>/<ol>."""
    all_lists = []
    for lst in soup.find_all(["ul", "ol"]):
        items = [li.get_text(separator=" ", strip=True) for li in lst.find_all("li")]
        if items:
            all_lists.append(items)
    return all_lists


def _extract_tables(soup: BeautifulSoup) -> List[List[List[str]]]:
    """Return a list of tables, each table is a list of rows, each row a list of cell texts."""
    tables_data = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(separator=" ", strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            tables_data.append(rows)
    return tables_data


def _extract_code_blocks(soup: BeautifulSoup) -> List[str]:
    """Collect text from <pre> and <code> blocks."""
    blocks = []
    for tag in soup.find_all(["pre", "code"]):
        txt = tag.get_text(separator=" ", strip=True)
        if txt:
            blocks.append(txt)
    return blocks


def _detect_js_frameworks(soup: BeautifulSoup) -> bool:
    """Very naive detection of common JS frameworks."""
    js_indicators = [
        "react", "angular", "vue", "svelte", "next", "nuxt",
        "ember", "backbone", "jquery", "polymer", "mithril",
    ]
    for script in soup.find_all("script"):
        src = script.get("src", "").lower()
        if any(fr in src for fr in js_indicators):
            return True
        if script.string:
            content = script.string.lower()
            if any(fr in content for fr in js_indicators):
                return True
    if soup.find(attrs={"data-reactroot": True}) or soup.find(attrs={"ng-app": True}):
        return True
    return False


# Page chrome that is dropped from extracted text, even inside the main content
# element: Wikipedia puts its language menu in a <header> and its
# Article/Talk/Read/Edit tabs in a <nav> inside <main>.
_BOILERPLATE_TAGS = ["script", "style", "noscript", "template", "nav", "header", "footer", "aside"]


def _primary_content_element(soup: BeautifulSoup):
    """The element the page itself marks as its main content, or None.

    ``<main>`` or ``role="main"`` first; otherwise an ``<article>`` if it is the
    only one (a listing page with several has no single main article).
    """
    primary = soup.find("main")
    if primary is None:
        primary = soup.find(attrs={"role": "main"})
    if primary is not None:
        return primary
    articles = soup.find_all("article")
    return articles[0] if len(articles) == 1 else None


def _empty_result(url: str, error: str = "") -> dict:
    """Build a standard failure result dict."""
    return {
        "url": url,
        "title": "",
        "content": "",
        "lists": [],
        "tables": [],
        "code_blocks": [],
        "meta_description": "",
        "meta_keywords": "",
        "js_rendered": False,
        "js_message": "",
        "success": False,
        "error": error,
    }


# ----------------------------------------------------------------------
# Negative cache — URLs whose failure is not worth re-discovering
# ----------------------------------------------------------------------
# A successful fetch is cached for 2 h; a failed one was not cached at all, so
# a permanently failing URL was re-requested every time it appeared - several
# times in one turn, since web_search fetches its own top results.
#
# ONLY non-transient statuses are stored. A 429, a 5xx or a network error is a
# blip; caching it would turn the blip into a self-inflicted outage for that
# URL. So the status set is a closed allowlist, not "anything that raised".
_PERMANENT_HTTP_STATUSES = frozenset({401, 403, 404, 410, 451})
_NEGATIVE_CACHE_TTL = timedelta(minutes=30)
_NEGATIVE_CACHE_MAX_ENTRIES = 512

# url -> (status, error_text, stored_at), ordered so eviction is oldest-first.
# In memory, not on disk: it clears on restart, cannot be poisoned by a stray
# script, and needs no cleanup.
_negative_cache: "OrderedDict[str, tuple]" = OrderedDict()

# This IS touched concurrently: comprehensive_web_search fetches its top
# results through a ThreadPoolExecutor. Single dict operations are atomic under
# the GIL, but read-then-evict and expire-then-pop are not, so the whole
# sequence is locked.
_negative_cache_lock = threading.Lock()

# Hosts being actively worked on (an ESP32, a NAS, a dev server behind auth)
# must not be remembered as broken - the user fixes something and retries at
# once. DNS-free on purpose: only IP literals and local-sounding suffixes
# count. A miss in the "not local" direction just caches the URL; the other
# direction just means no caching.
_LOCAL_HOST_SUFFIXES = (".local", ".lan", ".internal", ".home", ".localdomain")


def _is_local_target(url: str) -> bool:
    """True for loopback/RFC-1918 literals and local-sounding hostnames."""
    try:
        host = (urlparse(url).hostname or "").strip().lower()
    except Exception:
        return False
    if not host:
        return False
    if host == "localhost" or host.endswith(_LOCAL_HOST_SUFFIXES):
        return True
    try:
        return _is_private_address(ipaddress.ip_address(host))
    except ValueError:
        # Not an IP literal, and not a local suffix. Treat as remote without
        # resolving it — see the note above on which direction is safe.
        return False


def _negative_cache_lookup(url: str) -> "dict | None":
    """A remembered permanent failure for url, or None to go to the network.

    The returned dict carries the SAME error string a live failure would, plus
    the cached / cached_at / cache_age_seconds labels the positive cache uses.
    The labels are the point: an unlabelled cache hit is indistinguishable from
    a live call in app.db.
    """
    with _negative_cache_lock:
        entry = _negative_cache.get(url)
        if entry is None:
            return None
        status, error_text, stored_at = entry
        age = datetime.now() - stored_at
        if age >= _NEGATIVE_CACHE_TTL:
            _negative_cache.pop(url, None)
            return None
    served = _empty_result(url, error_text)
    served["cached"] = True
    served["cached_at"] = stored_at.isoformat()
    served["cache_age_seconds"] = int(age.total_seconds())
    served["http_status"] = status
    return served


def _negative_cache_store(url: str, status: int, error_text: str) -> bool:
    """Remember a permanent failure. Returns whether it was stored."""
    if status not in _PERMANENT_HTTP_STATUSES or _is_local_target(url):
        return False
    with _negative_cache_lock:
        _negative_cache.pop(url, None)
        _negative_cache[url] = (status, error_text, datetime.now())
        while len(_negative_cache) > _NEGATIVE_CACHE_MAX_ENTRIES:
            _negative_cache.popitem(last=False)
    return True


def clear_negative_cache() -> None:
    """Drop every remembered failure - the manual retry path.

    Exported from services.search so a caller who just fixed whatever returned
    401/403 can force the next fetch to leave the machine instead of waiting
    out the TTL.
    """
    with _negative_cache_lock:
        _negative_cache.clear()


# ----------------------------------------------------------------------
# Main content fetcher
# ----------------------------------------------------------------------
def fetch_webpage_content(url: str, timeout: int = 5, retry_attempt: int = 0,
                          max_bytes: int = None) -> dict:
    """Fetch and extract meaningful content from a webpage with caching.

    ``max_bytes`` raises the download budget per call (clamped to the hard
    cap); the default is the soft cap. When the body is cut short the result
    carries ``truncated``/``fetched_bytes``/``total_bytes`` so callers can
    tell the model the content is partial (#3812).
    """
    effective_cap = min(max_bytes or WEB_FETCH_SOFT_MAX_BYTES, WEB_FETCH_HARD_MAX_BYTES)
    # The cap is part of the cache identity: a truncated soft-cap fetch must
    # not be served to a later full-budget request for the same URL.
    cache_key = generate_cache_key(f"{url}#cap={effective_cap}")
    cache_file = CONTENT_CACHE_DIR / f"{cache_key}.cache"

    # Check cache
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            timestamp = datetime.fromisoformat(cached_data["timestamp"])
            if datetime.now() - timestamp < timedelta(hours=2):
                logger.debug(f"Content cache hit for URL: {url}")
                # Label the hit and say how old it is: an unlabelled cache hit
                # read back from app.db looks like a fresh reading
                # (resolvedissues: "The record of a run didn't say what
                # happened"). Copied, not mutated in place: callers may keep
                # cached_data["data"].
                served = dict(cached_data["data"])
                served["cached"] = True
                served["cached_at"] = cached_data["timestamp"]
                served["cache_age_seconds"] = int(
                    (datetime.now() - timestamp).total_seconds()
                )
                return served
            else:
                cache_file.unlink(missing_ok=True)
                content_cache_index.pop(cache_key, None)
        except Exception as e:
            logger.warning(f"Failed to read content cache for {url}: {e}")
            cache_file.unlink(missing_ok=True)
            content_cache_index.pop(cache_key, None)

    # A URL that already failed permanently is not worth another round trip.
    # Checked AFTER the positive cache (a good body always wins) and before the
    # network. Keyed on the URL alone: a 403 does not become a 200 because the
    # caller raised `full`, and a size failure is not stored here at all.
    remembered_failure = _negative_cache_lookup(url)
    if remembered_failure is not None:
        return remembered_failure

    # Fetch
    try:
        headers = {
            "User-Agent": WEB_FETCH_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            # identity so the streamed size cap in _get_public_url stays honest
            # (a compressed body can decode to far more than Content-Length).
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
        }
        response = _get_public_url(url, headers=headers, timeout=timeout,
                                   max_bytes=effective_cap)

        if response.status_code == 429:
            raise RateLimitError(f"Rate limit hit for {url} (attempt {retry_attempt})")

        response.raise_for_status()
    except BodyTooLargeError as e:
        error_logger.warning(f"Refused oversized body for {url}: {e}")
        return _empty_result(url, f"TooLarge: {e}")
    except httpx.HTTPStatusError as e:
        error_logger.warning(f"HTTP {e.response.status_code} fetching {url}: {e}")
        _error_text = f"HTTP {e.response.status_code}: {e}"
        _negative_cache_store(url, e.response.status_code, _error_text)
        return _empty_result(url, _error_text)
    except httpx.RequestError as e:
        error_logger.error(f"NetworkError fetching {url} (attempt {retry_attempt}): {e}")
        return _empty_result(url, f"NetworkError: {e}")
    except RateLimitError as e:
        error_logger.error(str(e))
        return _empty_result(url, str(e))

    # Size bookkeeping shared by every content branch below. getattr keeps
    # plain httpx.Response stand-ins (tests) working without the cap fields.
    _size_fields = {
        "truncated": getattr(response, "truncated", False),
        "fetched_bytes": len(response.content),
        "total_bytes": getattr(response, "declared_bytes", None),
    }

    # PDF handling
    content_type = response.headers.get("Content-Type", "").lower()
    if "application/pdf" in content_type or url.lower().endswith(".pdf"):
        if _size_fields["truncated"]:
            # A PDF cut mid-stream is not parseable; unlike text there is no
            # useful partial result, so report the budget problem instead.
            _declared = _size_fields["total_bytes"]
            return _empty_result(
                url,
                f"TooLarge: PDF exceeds the {effective_cap:,}-byte fetch budget"
                + (f" (size {_declared:,} bytes)" if _declared else "")
                + "; retry with a larger budget if it fits under the hard cap",
            )
        if pdf_extract_text is None:
            logger.error("pdfminer.six is not installed; cannot extract PDF text.")
            pdf_text = ""
        else:
            try:
                pdf_bytes = io.BytesIO(response.content)
                pdf_text = pdf_extract_text(pdf_bytes)
            except Exception as e:
                logger.warning(f"PDF extraction failed for {url}: {e}")
                pdf_text = ""
        result = {
            "url": url,
            "title": os.path.basename(url),
            "content": pdf_text,
            "lists": [],
            "tables": [],
            "code_blocks": [],
            "meta_description": "",
            "meta_keywords": "",
            "js_rendered": False,
            "js_message": "",
            "success": bool(pdf_text),
            "error": "" if pdf_text else "Failed to extract PDF text",
            **_size_fields,
        }
        _cache_result(cache_file, cache_key, result, url)
        return result

    # Plain-text / Markdown / JSON handling. Sources like
    # raw.githubusercontent.com serve Markdown as `text/plain`, JSON APIs and
    # raw config files serve `application/json`, and a lot of code and tool
    # docs live in `.md` / `.txt`. These have no HTML structure, so the HTML
    # branch below would extract nothing and report "no readable text content".
    # Return the body verbatim instead. The `is_html` guard keeps real HTML
    # (including `application/xhtml+xml`) on the parsing path; the `json` check
    # covers `application/json` and `+json` suffixes; the URL-suffix fallback
    # catches servers that mislabel text files as `application/octet-stream`.
    is_html = "html" in content_type
    is_json = "json" in content_type
    url_path = url.lower().split("?", 1)[0].split("#", 1)[0]
    looks_like_text_file = url_path.endswith(
        (".md", ".markdown", ".txt", ".text", ".json", ".jsonl")
    )
    if not is_html and (content_type.startswith("text/") or is_json or looks_like_text_file):
        text_body = (response.text or "").strip()
        result = {
            "url": url,
            "title": os.path.basename(url_path) or url,
            "content": text_body,
            "lists": [],
            "tables": [],
            "code_blocks": [],
            "meta_description": "",
            "meta_keywords": "",
            "js_rendered": False,
            "js_message": "",
            "success": bool(text_body),
            "error": "" if text_body else "Empty response body",
            **_size_fields,
        }
        _cache_result(cache_file, cache_key, result, url)
        return result

    # HTML handling
    try:
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        error_logger.error(f"ParseError parsing HTML from {url} (attempt {retry_attempt}): {e}")
        result = _empty_result(url, f"ParseError: {e}")
        _cache_result(cache_file, cache_key, result, url)
        return result

    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    meta_info = _extract_meta(soup)
    og_image = _extract_og_image(soup)
    js_rendered = _detect_js_frameworks(soup)
    js_message = "Page appears to be rendered by a JavaScript framework; content may be incomplete." if js_rendered else ""

    # Main textual content. Prefer the element the page marks as its main
    # content (<main>, role="main", a lone <article>); only without one guess
    # from class names. The class guess alone returned Wikipedia articles as
    # three copies of the site menu
    # (tests/test_search_content_main_landmark.py).
    main_content = ""
    primary = _primary_content_element(soup)
    if primary is not None:
        primary_copy = copy.copy(primary)
        for noise in primary_copy.find_all(_BOILERPLATE_TAGS):
            noise.extract()
        main_content = primary_copy.get_text(separator=" ", strip=True)
    else:
        content_areas = soup.find_all(
            ["main", "article", "section", "div"],
            class_=re.compile("content|main|body|article|post|entry|text", re.I),
        )
        for area in content_areas[:3]:
            main_content += area.get_text(separator=" ", strip=True) + " "
    main_content = re.sub(r"\s+", " ", main_content).strip()

    # If the heuristic finds only a tiny wrapper, fall back to body text with
    # obvious boilerplate stripped so UI/deep-research search results do not
    # look empty for app/landing pages.
    THIN_CONTENT_CHARS = 600
    if len(main_content) < THIN_CONTENT_CHARS:
        body = soup.find("body")
        if body:
            body_copy = copy.copy(body)
            for noise in body_copy.find_all(_BOILERPLATE_TAGS):
                noise.extract()
            body_text = re.sub(r"\s+", " ", body_copy.get_text(separator=" ", strip=True)).strip()
            if len(body_text) > len(main_content):
                main_content = body_text

    result = {
        "url": url,
        "title": title_text,
        "content": main_content,
        "lists": _extract_lists(soup),
        "tables": _extract_tables(soup),
        "code_blocks": _extract_code_blocks(soup),
        "meta_description": meta_info.get("description", ""),
        "meta_keywords": meta_info.get("keywords", ""),
        "og_image": og_image,
        "js_rendered": js_rendered,
        "js_message": js_message,
        "success": True,
        "error": "",
        **_size_fields,
    }
    _cache_result(cache_file, cache_key, result, url)
    return result


def _cache_result(cache_file, cache_key: str, result: dict, url: str):
    """Write a result to the content cache."""
    try:
        cache_data = {"timestamp": datetime.now().isoformat(), "data": result}
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)
        content_cache_index[cache_key] = datetime.now()
        cleanup_cache(CONTENT_CACHE_DIR, content_cache_index, timedelta(hours=2))
    except Exception as e:
        logger.warning(f"Failed to write content cache for {url}: {e}")


# ----------------------------------------------------------------------
# Content summarization helpers
# ----------------------------------------------------------------------
def extract_key_points(text: str) -> List[str]:
    """Pull out bullet-style key points from a block of text."""
    points: List[str] = []
    bullet_pat = re.compile(r"^\s*[-*•]\s+(.*)")
    numbered_pat = re.compile(r"^\s*\d+[\.\)]\s+(.*)")
    for line in text.splitlines():
        m = bullet_pat.match(line) or numbered_pat.match(line)
        if m:
            points.append(m.group(1).strip())
    return points


def get_tldr(text: str, max_sentences: int = 3) -> str:
    """Produce a very short TL;DR by taking the first few sentences."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    selected = [s.strip() for s in sentences if s][:max_sentences]
    return " ".join(selected)


def extract_quotes(text: str) -> List[str]:
    """Return quoted excerpts that are at least 15 characters long."""
    # Backreference the opening quote so the closing quote must match it —
    # otherwise `"text'` (open double, close single) is treated as a quote.
    return [m.group(2).strip() for m in re.finditer(r'(["\'])([^"\']{15,}?)\1', text)]


def extract_statistics(text: str) -> List[str]:
    """Find numbers, percentages, dates and simple measurements."""
    # Match a comma-grouped number (1,000,000) OR a plain digit run (50000) —
    # the old `\d{1,3}(?:,\d{3})*` matched only the first 3 digits of a
    # comma-less number, and the trailing `\b` dropped a closing `%`.
    pattern = re.compile(
        r"\b(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(%|percent|‰|per cent|[a-zA-Z]+)?",
        re.IGNORECASE,
    )
    return [m.group(0).strip() for m in pattern.finditer(text)]
