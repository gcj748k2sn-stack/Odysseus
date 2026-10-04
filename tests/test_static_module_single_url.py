"""Every ES module in static/ must be loaded under exactly one URL.

Browsers key ES modules by their full URL, query string included. When
`static/app.js` imported `./js/sessions.js?v=20260722ctxheader4` while
`chat.js` and fourteen other modules imported plain `./sessions.js`, the page
ran TWO copies of `sessions.js`, each with its own `currentSessionId` and
pending-chat state. The New Chat button cleared one copy; sending read the
other — so after the first message on a page, "New Chat" showed an empty
screen while the next message was posted into whichever chat was open before
(reproduced 2026-10-04 in a live page: `window.sessionModule !==
await import('/static/js/sessions.js')`, and a send after New Chat targeted
session 2e3ff29e). Eleven modules were split this way.

The `?v=` suffixes were cache-busters, and they are not needed:
`_RevalidatingStatic` in app.py serves every .js with `Cache-Control:
no-cache`, and the service worker fetches JS network-first.

This test is static — it reads the import graph, it does not run a browser.
"""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

_JS_SPEC = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)(['"])([^'"\n]+?\.js(?:\?[^'"\n]*)?)\1"""
)
_HTML_SPEC = re.compile(
    r"""<(?:script[^>]*\btype=["']module["'][^>]*\bsrc|link[^>]*\brel=["']modulepreload["'][^>]*\bhref)=["']([^"']+\.js(?:\?[^"']*)?)["']"""
)


def _first_party_js():
    for p in STATIC.rglob("*.js"):
        rel = p.relative_to(STATIC).as_posix()
        if rel.startswith(("lib/", "vendor/")) or "/vendor/" in rel:
            continue
        yield p


def _resolve(spec: str, importer_dir: Path):
    """(module path relative to static/, query) — or None for non-local specs."""
    if spec.startswith(("http:", "https:", "//", "data:")):
        return None
    path, _, query = spec.partition("?")
    if path.startswith("/static/"):
        abs_path = STATIC / path[len("/static/"):]
    elif path.startswith("/"):
        return None
    elif path.startswith("."):
        abs_path = importer_dir / path
    else:
        return None  # bare specifier (import map) — not used here
    rel = Path(os.path.normpath(abs_path)).relative_to(STATIC).as_posix()
    return rel, query


def module_urls(js_files, html_files):
    """{module path: {query, ...}} over every import and module tag."""
    seen = {}
    for p in js_files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        for m in _JS_SPEC.finditer(text):
            r = _resolve(m.group(2), p.parent)
            if r:
                seen.setdefault(r[0], set()).add(r[1])
    for p in html_files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        for m in _HTML_SPEC.finditer(text):
            r = _resolve(m.group(1), STATIC)
            if r:
                seen.setdefault(r[0], set()).add(r[1])
    return seen


def test_every_module_has_exactly_one_url():
    seen = module_urls(list(_first_party_js()), [STATIC / "index.html"])
    assert "js/sessions.js" in seen, "scanner found no import of sessions.js — the scan is broken"
    split = {k: sorted(v) for k, v in seen.items() if len(v) > 1}
    assert not split, f"modules loaded under more than one URL (one copy each!): {split}"


def test_no_module_url_carries_a_query_string():
    # Stricter than "one URL each": a lone `?v=` is one edit away from a split.
    seen = module_urls(list(_first_party_js()), [STATIC / "index.html"])
    with_query = {k: sorted(q for q in v if q) for k, v in seen.items() if any(v)}
    assert not with_query, f"module specifiers with a query string: {with_query}"


def test_scanner_catches_a_split(tmp_path):
    # Negative control: the scanner must flag the exact shape that caused the bug.
    js = tmp_path / "js"
    js.mkdir()
    (js / "sessions.js").write_text("export default {};\n")
    (js / "chat.js").write_text("import s from './sessions.js';\n")
    app = tmp_path / "app.js"
    app.write_text("import s from './js/sessions.js?v=20260722ctxheader4';\n")
    global STATIC
    old = STATIC
    STATIC = tmp_path
    try:
        seen = module_urls([js / "chat.js", app], [])
    finally:
        STATIC = old
    assert seen["js/sessions.js"] == {"", "v=20260722ctxheader4"}


def test_static_js_is_served_revalidating():
    # The reason dropping `?v=` is safe. If this ever changes, cache-busting
    # has to come back — as ONE URL per module, not per importer.
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'resp.headers["Cache-Control"] = "no-cache"' in src
    assert '".js"' in src
