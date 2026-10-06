"""No first-party JS file may read a block-scoped name outside its block.

A ``const``/``let`` declared inside a ``try`` is invisible to its ``catch``
and ``finally``. ``handleChatSubmit`` in ``static/js/chat.js`` read three such
names in its stream error handler (``streamingTTS``, ``abortCtrl``,
``_isAgent``), so every failed ``/api/chat_stream`` send threw
``ReferenceError: streamingTTS is not defined`` before the error was shown or
the streaming state was cleared (notes/todo.md, *"A failed send throws inside
its own error handler"*, seen 2026-10-04 on every intercepted send). The same
read of ``abortCtrl`` sat in the first-token wait timers, so *"Still waiting
for first token"* could never be shown. The same scan found two more of the
shape: ``_isBg`` read after its block closed (any turn with a generated image
threw at the end of the stream), and an undeclared ``modal`` in the dock-chip
drag handler of ``modalManager.js`` (threw on every desktop pointermove).

None of these is a syntax error, so ``node --check`` passes all of them, and
there is no JS test harness that would execute those paths. This test is
therefore a structural scan, a deliberate exception to the behavioral-first
rule in TESTING_STANDARD.md: the property being pinned *is* lexical scope.

What it checks, per file: an identifier that is *declared somewhere in the
same file* but has *no declaration visible where it is read*. Names declared
nowhere in the file (browser globals, ``window.*`` lookups) are out of scope,
so this cannot flag ``document`` or ``fetch``. Visibility is deliberately
generous — every declaration is visible across its whole block (no temporal
dead zone), ``var``/``function`` across their whole function, and anything in
a parameter list across the function body — so the scan can miss a real leak
but should not invent one. The negative controls below pin both directions.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

_KEYWORDS = frozenset(
    """break case catch class const continue debugger default delete do else
    export extends finally for function if import in instanceof let new return
    super switch this throw try typeof var void while with yield await async
    of static get set null true false undefined as from""".split()
)
# Control keywords whose `( … ) {` opens a plain block, not a function body.
_CONTROL = frozenset({"if", "for", "while", "switch", "catch", "with"})
# A `/` after one of these starts a regex literal, not a division.
_REGEX_AFTER_WORDS = frozenset(
    {"return", "typeof", "case", "in", "of", "new", "delete", "void", "throw",
     "instanceof", "else", "do", "yield", "await"}
)
# Names that are both a browser global and a local name in some file; a read
# with no local declaration in view is the global, and is fine.
_BROWSER_GLOBALS = frozenset(
    {"history", "location", "name", "event", "status", "top", "parent", "self",
     "origin", "screen", "length", "open", "close", "print", "performance",
     "navigator", "document", "window", "console", "fetch", "frames", "external",
     "crypto", "caches", "indexedDB", "localStorage", "sessionStorage", "Storage"}
)

_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_NUMBER = re.compile(r"(?:0[xXoObB][\da-fA-F_]+|\d[\d_]*(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)n?")


class Tok:
    __slots__ = ("kind", "val", "line")

    def __init__(self, kind, val, line):
        self.kind, self.val, self.line = kind, val, line

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"Tok({self.kind},{self.val!r},{self.line})"


def tokenize(src: str) -> list[Tok]:
    """Identifiers, punctuators and opaque literals, with strings, comments,
    regex literals and template text removed. `${` inside a template opens a
    real brace so its expression is tokenized as code."""
    toks: list[Tok] = []
    i, n, line = 0, len(src), 1
    tmpl_depth: list[int] = []  # brace depth at which each open `${` closes
    depth = 0

    def prev_allows_regex() -> bool:
        if not toks:
            return True
        t = toks[-1]
        if t.kind == "id":
            return t.val in _REGEX_AFTER_WORDS
        if t.kind in ("num", "str"):
            return False
        return t.val not in (")", "]")

    def read_template(j: int) -> int:
        # j is just past the opening backtick or a closing `}` of `${`.
        nonlocal line
        while j < n:
            c = src[j]
            if c == "\\":
                j += 2
                continue
            if c == "\n":
                line += 1
            if c == "`":
                return j + 1
            if c == "$" and j + 1 < n and src[j + 1] == "{":
                return -(j + 2)  # negative: entered an expression
            j += 1
        return j

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r\f\v﻿ ":
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += src.count("\n", i, j)
            i = j
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                elif src[j] == "\n":
                    break
                j += 1
            toks.append(Tok("str", "", line))
            i = j + 1
            continue
        if c == "`":
            j = read_template(i + 1)
            if j < 0:
                depth += 1
                tmpl_depth.append(depth)
                toks.append(Tok("str", "", line))
                toks.append(Tok("p", "{", line))
                i = -j
            else:
                toks.append(Tok("str", "", line))
                i = j
            continue
        if c == "}" and tmpl_depth and tmpl_depth[-1] == depth:
            tmpl_depth.pop()
            toks.append(Tok("p", "}", line))
            depth -= 1
            j = read_template(i + 1)
            if j < 0:
                depth += 1
                tmpl_depth.append(depth)
                toks.append(Tok("p", "{", line))
                i = -j
            else:
                toks.append(Tok("str", "", line))
                i = j
            continue
        if c == "/" and prev_allows_regex():
            j, in_class = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                elif src[j] == "/" and not in_class:
                    break
                j += 1
            j += 1
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            toks.append(Tok("str", "", line))
            i = j
            continue
        m = _IDENT.match(src, i)
        if m:
            toks.append(Tok("id", m.group(), line))
            i = m.end()
            continue
        m = _NUMBER.match(src, i)
        if m and m.end() > i:
            toks.append(Tok("num", "", line))
            i = m.end()
            continue
        for p in ("...", "=>", "?."):
            if src.startswith(p, i):
                toks.append(Tok("p", p, line))
                i += len(p)
                break
        else:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            toks.append(Tok("p", c, line))
            i += 1
    return toks


def _match_forward(toks, i, open_, close):
    d = 0
    for j in range(i, len(toks)):
        if toks[j].kind == "p":
            if toks[j].val == open_:
                d += 1
            elif toks[j].val == close:
                d -= 1
                if d == 0:
                    return j
    return len(toks) - 1


def _match_back(toks, i, open_, close):
    d = 0
    for j in range(i, -1, -1):
        if toks[j].kind == "p":
            if toks[j].val == close:
                d += 1
            elif toks[j].val == open_:
                d -= 1
                if d == 0:
                    return j
    return 0


def _is(t, kind, val=None):
    return t is not None and t.kind == kind and (val is None or t.val == val)


def _skip_expr(toks, i, stops):
    """Index of the first token at nesting depth 0 whose value is in `stops`
    (or an unmatched closer), starting at i."""
    d = 0
    while i < len(toks):
        t = toks[i]
        if t.kind == "p":
            if t.val in "([{":
                d += 1
            elif t.val in ")]}":
                if d == 0:
                    return i
                d -= 1
            elif d == 0 and t.val in stops:
                return i
        i += 1
    return i


def _pattern(toks, i, out):
    """Parse a binding target at token i (identifier, `{…}` or `[…]`); append
    (name, token index) pairs to `out`; return the index after it. Default
    values are skipped — they are reads, not bindings."""
    t = toks[i] if i < len(toks) else None
    if _is(t, "id"):
        if t.val not in _KEYWORDS:
            out.append((t.val, i))
        return i + 1
    if _is(t, "p", "{") or _is(t, "p", "["):
        close = "}" if t.val == "{" else "]"
        j = i + 1
        while j < len(toks) and not _is(toks[j], "p", close):
            if _is(toks[j], "p", ","):
                j += 1
                continue
            if _is(toks[j], "p", "..."):
                j = _pattern(toks, j + 1, out)
            elif t.val == "{":
                if _is(toks[j], "p", "["):  # computed key
                    j = _skip_expr(toks, j + 1, ()) + 1
                if j + 1 < len(toks) and _is(toks[j + 1], "p", ":"):
                    j = _pattern(toks, j + 2, out)
                elif _is(toks[j], "p", ":"):
                    j = _pattern(toks, j + 1, out)
                else:
                    j = _pattern(toks, j, out)
            else:
                j = _pattern(toks, j, out)
            if j < len(toks) and _is(toks[j], "p", "="):
                j = _skip_expr(toks, j + 1, (",",))
            if j < len(toks) and not (_is(toks[j], "p", ",") or _is(toks[j], "p", close)):
                j = _skip_expr(toks, j, (",",))  # unrecognised shape: resync
        return j + 1
    return i + 1


def _param_list(toks, open_idx, close_idx, out):
    """Bindings of a parameter list `( … )`."""
    j = open_idx + 1
    while j < close_idx:
        if _is(toks[j], "p", ","):
            j += 1
            continue
        if _is(toks[j], "p", "..."):
            j += 1
        j = _pattern(toks, j, out)
        if j < close_idx and _is(toks[j], "p", "="):
            j = _skip_expr(toks, j + 1, (",",))
        if j < close_idx and not _is(toks[j], "p", ","):
            j = _skip_expr(toks, j, (",",))


def analyse(src: str):
    """Return [(name, line)] for reads of a name that is declared in this file
    but has no declaration in view at that read."""
    toks = tokenize(src)
    n = len(toks)
    ROOT_BLOCK = -1

    # Innermost enclosing block of every token, and each block's parent.
    owner = [ROOT_BLOCK] * n
    parent: dict[int, int | None] = {ROOT_BLOCK: None}
    stack = [ROOT_BLOCK]
    for k, t in enumerate(toks):
        if _is(t, "p", "}") and len(stack) > 1:
            owner[k] = stack.pop()
            continue
        owner[k] = stack[-1]
        if _is(t, "p", "{"):
            parent[k] = stack[-1]
            stack.append(k)

    decls: dict[str, set[int]] = {}
    decl_tok: set[int] = set()

    def bind(pairs, block):
        for name, idx in pairs:
            decls.setdefault(name, set()).add(block)
            decl_tok.add(idx)

    def adopt(open_idx, close_idx, body):
        """Parameter defaults see earlier parameters: resolve every token of
        the list `( … )` as if it sat in the function body."""
        outer = parent[body]
        for q in range(open_idx + 1, close_idx):
            if owner[q] == outer:
                owner[q] = body
            if _is(toks[q], "p", "{") and parent.get(q) == outer:
                parent[q] = body

    # Function bodies: `) {` whose `(` does not follow a control keyword, and
    # `=> {`. Parameters bind into the body; `catch (e) {` binds into its block.
    func_body: set[int] = {ROOT_BLOCK}
    for k, t in enumerate(toks):
        if not _is(t, "p", "{") or k == 0:
            continue
        prev = toks[k - 1]
        if _is(prev, "p", "=>"):
            func_body.add(k)
            p = toks[k - 2] if k >= 2 else None
            pairs = []
            if _is(p, "id"):
                pairs.append((p.val, k - 2))
            elif _is(p, "p", ")"):
                o = _match_back(toks, k - 2, "(", ")")
                _param_list(toks, o, k - 2, pairs)
                adopt(o, k - 2, k)
            bind(pairs, k)
        elif _is(prev, "p", ")"):
            o = _match_back(toks, k - 1, "(", ")")
            before = toks[o - 1] if o >= 1 else None
            if _is(before, "id") and before.val in _CONTROL:
                if before.val == "catch":
                    pairs = []
                    _param_list(toks, o, k - 1, pairs)
                    bind(pairs, k)
                continue
            func_body.add(k)
            pairs = []
            _param_list(toks, o, k - 1, pairs)
            adopt(o, k - 1, k)
            bind(pairs, k)

    def enclosing_function(b):
        while b not in func_body:
            b = parent[b]
        return b

    def declarator_starts(k):
        """Token index of each binding in `const a = 1, b = 2`: the first one,
        then the token after each depth-0 comma, up to the end of the
        statement (`;`, an unmatched closer, `of`/`in` in a for-head, or a new
        line that starts a new statement)."""
        starts = [k + 1]
        j = _pattern(toks, k + 1, [])
        d = 0
        while j < n:
            x = toks[j]
            if x.kind == "p" and x.val in "([{":
                d += 1
            elif x.kind == "p" and x.val in ")]}":
                if d == 0:
                    break
                d -= 1
            elif d == 0:
                if _is(x, "p", ";") or (x.kind == "id" and x.val in ("of", "in")):
                    break
                if _is(x, "p", ","):
                    starts.append(j + 1)
                    j = _pattern(toks, j + 1, [])
                    continue
                pv = toks[j - 1]
                if x.kind == "id" and x.line != pv.line and (
                    (pv.kind in ("id", "num", "str") and pv.val not in _KEYWORDS)
                    or (pv.kind == "p" and pv.val in ")]}")
                ):
                    break  # ASI: a new statement on a new line
            j += 1
        return starts

    for k, t in enumerate(toks):
        if t.kind != "id" or (k and _is(toks[k - 1], "p", ".")):
            continue
        if t.val in ("const", "let", "var"):
            b = owner[k] if t.val != "var" else enclosing_function(owner[k])
            for st in declarator_starts(k):
                pairs = []
                _pattern(toks, st, pairs)
                bind(pairs, b)
        elif t.val in ("function", "class"):
            j = k + 2 if _is(toks[k + 1] if k + 1 < n else None, "p", "*") else k + 1
            nxt = toks[j] if j < n else None
            if _is(nxt, "id") and nxt.val not in _KEYWORDS:
                b = enclosing_function(owner[k]) if t.val == "function" else owner[k]
                bind([(nxt.val, j)], b)
        elif t.val == "import":
            nxt = toks[k + 1] if k + 1 < n else None
            if nxt is None or nxt.kind == "str" or (nxt.kind == "p" and nxt.val in (".", "(")):
                continue  # import(), import.meta, side-effect import
            j = k + 1
            while j < n and not _is(toks[j], "id", "from") and toks[j].kind != "str" and not _is(toks[j], "p", ";"):
                x = toks[j]
                if x.kind == "id" and x.val not in _KEYWORDS:
                    decl_tok.add(j)  # `a` in `{ a as b }` is the exporter's name
                    if not _is(toks[j + 1] if j + 1 < n else None, "id", "as"):
                        bind([(x.val, j)], ROOT_BLOCK)
                j += 1
        elif k + 1 < n and _is(toks[k + 1], "p", "=>") and not _is(toks[k + 2] if k + 2 < n else None, "p", "{"):
            # `x => expr`: bind into the current block (generous)
            bind([(t.val, k)], owner[k])
    for k, t in enumerate(toks):
        # `(a, b) => expr` without braces: bind into the current block
        if _is(t, "p", "=>") and k >= 1 and _is(toks[k - 1], "p", ")") \
                and not _is(toks[k + 1] if k + 1 < n else None, "p", "{"):
            pairs = []
            _param_list(toks, _match_back(toks, k - 1, "(", ")"), k - 1, pairs)
            bind(pairs, owner[k])

    def visible(name, k):
        blocks = decls.get(name, ())
        b = owner[k]
        while b is not None:
            if b in blocks:
                return True
            b = parent[b]
        return False

    leaks = []
    for k, t in enumerate(toks):
        if t.kind != "id" or t.val in _KEYWORDS or k in decl_tok:
            continue
        if t.val not in decls or t.val in _BROWSER_GLOBALS:
            continue
        prev = toks[k - 1] if k else None
        if prev is not None and prev.kind == "p" and prev.val in (".", "?.", "#"):
            continue  # property access / private field
        nxt = toks[k + 1] if k + 1 < n else None
        if _is(nxt, "p", ":") and not _is(prev, "p", "?"):
            continue  # object key or label
        if _is(nxt, "p", "("):
            close = _match_forward(toks, k + 1, "(", ")")
            if _is(toks[close + 1] if close + 1 < n else None, "p", "{"):
                continue  # method definition `name(…) {`
        if not visible(t.val, k):
            leaks.append((t.val, t.line))
    return leaks


def _first_party_js():
    for p in sorted(STATIC.rglob("*.js")):
        rel = p.relative_to(STATIC).as_posix()
        if rel.startswith(("lib/", "vendor/")) or "/vendor/" in rel or rel.endswith(".min.js"):
            continue
        yield p


# ── negative controls: the scanner must see the bug, and only the bug ──

_LEAK = """
async function send() {
  let accumulated = '';
  try {
    const streamingTTS = !!window.tts;
    const abortCtrl = new AbortController();
    for (const x of [1]) { const inner = x; }
    if (streamingTTS) start();
  } catch (err) {
    if (streamingTTS) stop();
    if (abortCtrl && abortCtrl.signal.aborted) return;
    console.log(err, accumulated, `${inner}`);
  }
}
"""

_FIXED = """
import { start, stop, computeSnap as snapImpl } from './x.js';
async function send(opts, { quiet = false } = {}) {
  let accumulated = '';
  let streamingTTS = false;
  let abortCtrl = null;
  try {
    streamingTTS = !!window.tts;
    abortCtrl = new AbortController();
    const { a, b: renamed } = opts, [c, ...rest] = [];
    const re = /["'{]/g;
    const s = `a ${accumulated} {`;
    for (const x of [1]) { const inner = x; use(inner, x); }
    items.forEach(item => use(item));
    items.map((y, z) => y + z);
    if (streamingTTS) start(a, renamed, c, rest, re, s, quiet);
    hoisted();
  } catch (err) {
    if (streamingTTS) stop();
    if (abortCtrl && abortCtrl.signal.aborted) return;
    console.log(err, accumulated, { abortCtrl, key: 1 }, obj.streamingTTS);
  }
  function hoisted() { return accumulated; }
  function computeSnap(v) { return snapImpl(v); }
  const runFix = async (fix, label = fix.label, { tag = label } = {}) => tag;
}
"""


def test_scanner_flags_try_scoped_reads_in_catch():
    leaks = {name for name, _ in analyse(_LEAK)}
    assert leaks == {"streamingTTS", "abortCtrl", "inner"}, leaks


def test_scanner_is_silent_on_the_fixed_shape():
    assert analyse(_FIXED) == []


def test_scanner_sees_the_original_chat_js_defect():
    """Put back the shape that shipped — `streamingTTS` declared inside the
    try, read by the catch — and the scan must flag it. Guards against a
    tokenizer change that silently stops seeing the real file."""
    src = (STATIC / "js" / "chat.js").read_text(encoding="utf-8")
    hoisted = "    let streamingTTS = false;\n"
    assigned = "      streamingTTS = !!(window.aiTTSManager"
    assert src.count(hoisted) == 1 and src.count(assigned) == 1, (
        "chat.js no longer declares streamingTTS where this test expects"
    )
    broken = src.replace(hoisted, "").replace(assigned, "      const streamingTTS = !!(window.aiTTSManager")
    assert analyse(src) == []
    assert "streamingTTS" in {name for name, _ in analyse(broken)}


@pytest.mark.parametrize("path", list(_first_party_js()), ids=lambda p: p.relative_to(STATIC).as_posix())
def test_no_block_scoped_name_is_read_outside_its_block(path):
    leaks = analyse(path.read_text(encoding="utf-8"))
    assert not leaks, (
        f"{path.relative_to(ROOT)} reads names whose declaration is not in view "
        f"(a ReferenceError at runtime): "
        + ", ".join(f"{n} (line {ln})" for n, ln in leaks)
    )
