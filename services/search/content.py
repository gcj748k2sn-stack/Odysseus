"""Webpage content fetching with caching, PDF extraction, and summarization helpers."""

import copy
import io
import ipaddress
import json
import os
import re
import logging
import socket
import ssl
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Iterable, List, cast
from urllib.parse import urljoin, urlparse

import httpx
import httpcore
from bs4 import BeautifulSoup

from src.constants import WEB_FETCH_SOFT_MAX_BYTES, WEB_FETCH_HARD_MAX_BYTES, WEB_FETCH_USER_AGENT

from .analytics import RateLimitError, error_logger
from .cache import (
    CONTENT_CACHE_DIR,
    content_cache_index,
    generate_cache_key,
    cleanup_cache,
)

logger = logging.getLogger(__name__)

_PRIVATE_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)

# ── Two-tier SSRF classification ─────────────────────────────────────────────
# Odysseus is local-first: a user pointing web_fetch at their own ESP32, NAS or
# dev server on the LAN is a legitimate, intended thing to do. But the guard has
# to keep rejecting the cloud instance-metadata range unconditionally, since
# that is the credential-exfil vector and nobody serves real content there.
#
# So the address space splits in two, mirroring the tiering already used by
# ``src/url_safety.py`` for the embedding/webhook/ntfy paths:
#
#   HARD  – never reachable, no override. Link-local (incl. 169.254.169.254),
#           multicast, reserved, unspecified, and the 0.0.0.0/8 wildcard.
#   GATED – reachable only when the caller opts in. Loopback, RFC-1918, ULA,
#           and the internal-sounding hostname suffixes.
_HARD_BLOCKED_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
)

_GATED_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
)

# Hostnames that must never resolve anywhere, override or not.
_HARD_BLOCKED_HOSTS = ("metadata", "metadata.google.internal")
# Hostnames/suffixes that only name LAN hosts — gated, not hard-blocked, so
# `http://martha.local/` works once private targets are allowed.
_GATED_HOSTS = ("localhost",)
_GATED_HOST_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".intranet")

_BLOCK_PRIVATE_ENV = "WEB_FETCH_BLOCK_PRIVATE_IPS"


def _normalize(addr: ipaddress._BaseAddress) -> ipaddress._BaseAddress:
    """Judge IPv4-mapped IPv6 (e.g. ::ffff:169.254.169.254) by the embedded v4."""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    return addr


def _is_hard_blocked_address(addr: ipaddress._BaseAddress) -> bool:
    """Addresses no opt-in may ever reach."""
    addr = _normalize(addr)
    # The gated ranges win when the two overlap. Python reports IPv6 ``::1``
    # as ``is_reserved``, which would otherwise put the v6 loopback in the
    # hard tier while ``127.0.0.1`` sits in the gated one — same host, two
    # different answers depending on which literal the user typed.
    if any(addr in net for net in _GATED_PRIVATE_NETWORKS):
        return False
    return (
        addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or any(addr in net for net in _HARD_BLOCKED_NETWORKS)
    )


def _is_gated_private_address(addr: ipaddress._BaseAddress) -> bool:
    """Private/loopback addresses, reachable only with an explicit opt-in."""
    addr = _normalize(addr)
    return (
        addr.is_private
        or addr.is_loopback
        or any(addr in net for net in _GATED_PRIVATE_NETWORKS)
    )


def _is_private_address(addr: ipaddress._BaseAddress) -> bool:
    """Union of both tiers — the historical, always-strict predicate."""
    return _is_hard_blocked_address(addr) or _is_gated_private_address(addr)


def _private_targets_allowed() -> bool:
    """True when ``WEB_FETCH_BLOCK_PRIVATE_IPS`` is explicitly switched off.

    Read per call rather than at import so a running instance picks up a
    changed environment, and so tests can flip it with ``monkeypatch.setenv``.
    Default is ``true``: an existing deployment keeps the strict behaviour.
    """
    raw = os.getenv(_BLOCK_PRIVATE_ENV, "true").strip().lower()
    return raw in ("0", "false", "no", "off")


def _resolve_hostname_ips(hostname: str) -> list[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except Exception:
        return []
    out = []
    for info in infos:
        try:
            out.append(ipaddress.ip_address(info[4][0]))
        except Exception:
            continue
    return out


def _public_http_url(url: str, *, allow_private: bool = False) -> bool:
    """Boolean form of :func:`_resolve_public_ips`.

    Deliberately a thin wrapper rather than a parallel implementation. It used
    to be the guard itself, until #704 moved the fetch path onto
    ``_resolve_public_ips`` and left this function behind with no callers — at
    which point the tests asserting on it stopped covering anything real.
    Delegating keeps the two from drifting again.
    """
    try:
        _resolve_public_ips(url, allow_private=allow_private)
        return True
    except Exception:
        return False


def _resolve_public_ips(
    url: str, *, allow_private: bool = False
) -> list[ipaddress._BaseAddress]:
    """Resolve ``url`` to the IPs it may be connected to, or raise.

    ``allow_private`` opts into loopback/RFC-1918/ULA targets — the local-first
    case (an ESP32 or dev server on the LAN). It never unlocks the hard tier:
    link-local and the instance-metadata range stay rejected either way.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise httpx.RequestError(f"Blocked non-public URL: {url}")
    host = (parsed.hostname or "").strip().lower()

    if host in _HARD_BLOCKED_HOSTS:
        raise httpx.RequestError(f"Blocked non-public hostname: {host}")
    if not allow_private and (
        host in _GATED_HOSTS or host.endswith(_GATED_HOST_SUFFIXES)
    ):
        raise httpx.RequestError(f"Blocked non-public hostname: {host}")

    def _rejected(addr: ipaddress._BaseAddress) -> bool:
        if _is_hard_blocked_address(addr):
            return True
        return not allow_private and _is_gated_private_address(addr)

    try:
        ip = ipaddress.ip_address(host)
        if _rejected(ip):
            raise httpx.RequestError(f"Blocked non-public IP literal: {host}")
        return [ip]
    except httpx.RequestError:
        raise
    except ValueError:
        pass

    addrs = _resolve_hostname_ips(host)
    if not addrs or any(_rejected(a) for a in addrs):
        raise httpx.RequestError(f"Blocked non-public URL: {url}")
    return addrs


class _PinnedBackend(httpcore.NetworkBackend):
    """Network backend that connects to a pre-resolved IP.

    httpcore derives the TLS SNI and the ``Host`` header from the URL's
    origin, not from the host argument passed to ``connect_tcp``. So
    routing the TCP connect to a resolved IP while leaving the URL
    untouched keeps SNI / vhost behaviour correct and closes the
    DNS-rebinding TOCTOU between the SSRF check and the connect.
    """

    def __init__(self, ip: ipaddress._BaseAddress):
        self._ip = str(ip)
        self._real = httpcore.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        return self._real.connect_tcp(
            self._ip, port, timeout, local_address, socket_options
        )

    def connect_unix_socket(self, path, timeout=None, socket_options=None):
        return self._real.connect_unix_socket(path, timeout, socket_options)

    def sleep(self, seconds: float) -> None:
        return self._real.sleep(seconds)


# Map httpcore exception classes to their httpx equivalents. Built
# once at import time from the public exception classes; avoids any
# import of httpx's private transport machinery. httpcore's
# ``ConnectionNotAvailable`` is a pool-internal signal (the pool will
# close and retry on its own) — we never expect to see it surface to
# a transport caller, so it has no httpx counterpart here.
_HTTPCORE_TO_HTTPX_EXC = {
    httpcore.ConnectError: httpx.ConnectError,
    httpcore.ConnectTimeout: httpx.ConnectTimeout,
    httpcore.LocalProtocolError: httpx.LocalProtocolError,
    httpcore.NetworkError: httpx.NetworkError,
    httpcore.PoolTimeout: httpx.PoolTimeout,
    httpcore.ProtocolError: httpx.ProtocolError,
    httpcore.ProxyError: httpx.ProxyError,
    httpcore.ReadError: httpx.ReadError,
    httpcore.ReadTimeout: httpx.ReadTimeout,
    httpcore.RemoteProtocolError: httpx.RemoteProtocolError,
    httpcore.TimeoutException: httpx.TimeoutException,
    httpcore.UnsupportedProtocol: httpx.UnsupportedProtocol,
    httpcore.WriteError: httpx.WriteError,
    httpcore.WriteTimeout: httpx.WriteTimeout,
}


class _PinnedTransport(httpx.BaseTransport):
    """Transport that pins every TCP connect to a pre-resolved IP.

    Uses only the public ``httpcore`` and ``httpx`` APIs — no
    subclassing of ``httpx.HTTPTransport``, no reads of private
    ``httpcore.ConnectionPool`` attributes, no imports from
    ``httpx private transport internals``. The URL is passed through unchanged so SNI
    / vhost work as if httpx had been given the hostname directly;
    only the TCP destination is pinned, closing the DNS-rebinding
    TOCTOU between the SSRF check and the connect.
    """

    def __init__(self, ip: ipaddress._BaseAddress, *, http2: bool = False):
        self._pool = httpcore.ConnectionPool(
            ssl_context=ssl.create_default_context(),
            http1=True,
            http2=http2,
            network_backend=_PinnedBackend(ip),
        )

    def __enter__(self):
        self._pool.__enter__()
        return self

    def __exit__(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._pool.__exit__(exc_type, exc_value, traceback)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        httpcore_req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        try:
            httpcore_resp = self._pool.handle_request(httpcore_req)
            # Eager materialisation matches the original
            # ``response.text`` usage in fetch_webpage_content. The
            # sync pool's stream is a plain Iterable[bytes] despite
            # the httpcore type hint unioning the async variant.
            content = b"".join(cast(Iterable[bytes], httpcore_resp.stream))
        except Exception as exc:
            mapped = _HTTPCORE_TO_HTTPX_EXC.get(type(exc))
            if mapped is not None:
                raise mapped(str(exc)) from exc
            raise

        return httpx.Response(
            status_code=httpcore_resp.status,
            headers=httpcore_resp.headers,
            content=content,
            extensions=httpcore_resp.extensions,
        )

    def close(self) -> None:
        self._pool.close()

class BodyTooLargeError(Exception):
    """The server declared a body larger than the hard fetch ceiling."""

    def __init__(self, url: str, declared_bytes: int):
        self.url = url
        self.declared_bytes = declared_bytes
        super().__init__(
            f"response body is {declared_bytes:,} bytes, over the "
            f"{WEB_FETCH_HARD_MAX_BYTES:,}-byte hard cap"
        )


class _CappedFetch:
    """Result of a size-capped streaming GET.

    Carries just what fetch_webpage_content needs from an httpx.Response,
    plus the cap bookkeeping: the (possibly truncated) body, whether the
    cap cut it short, and the size the server declared via Content-Length
    (wire bytes; None when absent).
    """

    __slots__ = ("status_code", "headers", "content", "truncated",
                 "declared_bytes", "encoding", "url")

    def __init__(self, status_code, headers, content, truncated,
                 declared_bytes, encoding, url):
        self.status_code = status_code
        self.headers = headers
        self.content = content
        self.truncated = truncated
        self.declared_bytes = declared_bytes
        self.encoding = encoding
        self.url = url

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding or "utf-8", errors="replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", self.url)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code} for {self.url}",
                request=request,
                response=httpx.Response(self.status_code, request=request),
            )


def _get_public_url(url: str, headers: dict, timeout: int, max_redirects: int = 5,
                    max_bytes: int = None, allow_private: bool = None) -> "_CappedFetch":
    """Capped streaming GET with SSRF-guarded, DNS-pinned manual redirects.

    Each hop is resolved once, validated as public, and then the actual TCP
    connection is pinned to that resolved IP. The request URL is left unchanged
    so Host and TLS SNI keep the original hostname.

    ``allow_private`` (default: read from ``WEB_FETCH_BLOCK_PRIVATE_IPS``)
    applies to the **first hop only**. A user asking for their own LAN device
    is opting in deliberately; a public page issuing a 302 into RFC-1918 space
    is an SSRF chain and stays blocked regardless of the setting.
    """
    if allow_private is None:
        allow_private = _private_targets_allowed()
    cap = min(max_bytes or WEB_FETCH_SOFT_MAX_BYTES, WEB_FETCH_HARD_MAX_BYTES)
    current = url
    for hop in range(max_redirects + 1):
        ips = _resolve_public_ips(current, allow_private=allow_private and hop == 0)

        # Force identity transfer-encoding. With gzip/deflate the wire bytes
        # and Content-Length can be a small fraction of the decoded body, so a
        # tiny compressed response could pass the hard-cap preflight and then
        # expand past the ceiling in one decoded chunk before the streamed cap
        # below can slice it.
        req_headers = dict(headers or {})
        req_headers["Accept-Encoding"] = "identity"

        with httpx.Client(
            headers=req_headers,
            timeout=timeout,
            follow_redirects=False,
            transport=_PinnedTransport(ips[0]),
        ) as client:
            with client.stream("GET", current) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        return _CappedFetch(response.status_code, response.headers, b"",
                                            False, None, response.encoding, str(response.url))
                    current = urljoin(str(response.url), location)
                    continue

                # A server can ignore the identity request and still return a
                # compressed body; httpx.iter_bytes would then decode it, and a
                # tiny gzip can balloon into one decoded chunk far past the cap.
                # Refuse compressed Content-Encoding so the streamed cap stays
                # a real memory bound.
                enc = (response.headers.get("content-encoding") or "").strip().lower()
                if enc and enc != "identity":
                    raise httpx.RequestError(
                        f"Refusing compressed response (Content-Encoding: {enc}) after "
                        "requesting identity: cannot bound decoded body size",
                        request=httpx.Request("GET", current),
                    )

                declared = None
                raw_len = response.headers.get("content-length")
                if raw_len and raw_len.isdigit():
                    declared = int(raw_len)

                if declared is not None and declared > WEB_FETCH_HARD_MAX_BYTES:
                    raise BodyTooLargeError(current, declared)

                chunks = []
                read = 0
                truncated = False
                for chunk in response.iter_bytes():
                    read += len(chunk)
                    if read > cap:
                        keep = cap - (read - len(chunk))
                        if keep > 0:
                            chunks.append(chunk[:keep])
                        truncated = True
                        break
                    chunks.append(chunk)

                return _CappedFetch(response.status_code, response.headers,
                                    b"".join(chunks), truncated, declared,
                                    response.encoding, str(response.url))

    raise httpx.RequestError("Too many redirects", request=httpx.Request("GET", current))

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
# A SUCCESSFUL fetch is cached for 2 h. A FAILED one was not cached at all, so
# a URL that fails the same way every time was re-requested every time it
# appeared. Measured 2026-07-31 in session 93c1c383: one ResearchGate URL
# returning 403 was fetched FOUR times inside a single agent turn — three
# because ``web_search`` fetches its own top results (services/search/core.py)
# and that URL ranked top-3 for all three queries, plus one explicit
# ``web_fetch``. Requests 2, 3 and 4 could not have returned anything the
# first did not, and the turn ended having gathered nothing.
#
# ⚠️ ONLY non-transient statuses are stored. A 429 is a rate limit, a 5xx is
# the server having a bad minute, and a network error is a network error —
# caching any of those converts a blip into a self-inflicted outage for that
# URL. That is the failure mode this cache could introduce, so the status set
# is a closed allowlist rather than "anything that raised".
_PERMANENT_HTTP_STATUSES = frozenset({401, 403, 404, 410, 451})
_NEGATIVE_CACHE_TTL = timedelta(minutes=30)
_NEGATIVE_CACHE_MAX_ENTRIES = 512

# url -> (status, error_text, stored_at). Ordered so the eviction below is
# oldest-first. In memory rather than on disk: it clears on restart, it cannot
# be poisoned by a stray script the way data/cache/content/ once was (see
# docs/qwensetup.md, "never call fetch_webpage_content() against the live
# tree"), and there is nothing to clean up.
_negative_cache: "OrderedDict[str, tuple]" = OrderedDict()

# ⚠️ This IS touched concurrently. `comprehensive_web_search` fetches its top
# results through a ThreadPoolExecutor (services/search/core.py), which is the
# very path that produced the repeated 403s — so the parallel case is the
# normal case here, not an edge one. Individual dict operations are atomic
# under the GIL, but the read-then-evict sequence below is not, and neither is
# lookup's expire-then-pop. Guard the whole sequence rather than relying on
# the GIL for a compound operation.
_negative_cache_lock = threading.Lock()

# Hosts that are being actively worked on must not be remembered as broken.
# A LAN device answering 403 today is the exact case where the user changes
# something and immediately retries — an ESP32, a NAS, a dev server behind
# auth. Deliberately DNS-free: only IP literals and local-sounding suffixes
# count, so this can never cost a resolution on the hot path. Getting it wrong
# in the "not local" direction is harmless (the URL is simply cached, which is
# the point); getting it wrong the other way only means no caching, i.e. the
# behaviour that shipped before this block existed.
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
    """A remembered permanent failure for ``url``, or None to go to the network.

    The returned dict carries the SAME ``error`` string a live failure would,
    so nothing downstream has to learn a second shape, plus the ``cached`` /
    ``cached_at`` / ``cache_age_seconds`` labels the positive cache already
    uses. **The labels are the point.** An unlabelled cache hit is
    indistinguishable from a live call in ``app.db`` — that mistake has already
    been made once here and produced a wrong conclusion about a frozen device.
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
    """Drop every remembered failure — the manual retry path.

    Exported from ``services.search`` so a user or caller who has just fixed
    whatever was returning 401/403 can force the next fetch to leave the
    machine, instead of waiting out the TTL. Without an export this docstring
    would be describing a path that does not exist.
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
                # A cache hit used to be indistinguishable from a live fetch:
                # same shape, same exit_code, no flag. That has already
                # produced a wrong conclusion — two turns 4.5 minutes apart
                # both reported `uptime: 91 s` from a device whose counter was
                # running, and only the first had left the machine. Read back
                # from app.db, the second looked like a fresh reading of a
                # frozen device. Label the hit and say how old it is.
                #
                # Copied, not mutated in place: `cached_data["data"]` is the
                # dict just parsed from the cache file, and callers are free to
                # keep it. See docs/todo.md, "A cache hit is indistinguishable
                # from a live fetch".
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
    # network. Keyed on the URL alone, not on the byte budget the positive
    # cache keys on: a 403 does not become a 200 because the caller raised
    # `full`, and a size failure is not stored here at all.
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

    # Main textual content (heuristic): prefer semantic / "content"-classed
    # containers to skip nav/footer/boilerplate; tuned for article pages.
    main_content = ""
    content_areas = soup.find_all(
        ["main", "article", "section", "div"],
        class_=re.compile("content|main|body|article|post|entry|text", re.I),
    )
    if content_areas:
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
            for noise in body_copy.find_all(
                ["script", "style", "noscript", "template", "nav", "header", "footer", "aside"]
            ):
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
