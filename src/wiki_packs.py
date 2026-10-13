"""Local Wikipedia packs (fork module): a topic subset of Wikipedia in one
SQLite full-text index per pack, for searching locally before the web.

A pack is defined by a category tree (with a depth limit) or a WikiProject
banner, in one language. `plan` lists its articles without downloading text;
`build` downloads plain text and redirect titles, skipping articles whose
revision is already stored, so an interrupted build resumes and a rerun only
refetches what changed. Standard library only, and nothing here imports
core.database, so the CLI cannot touch app.db.

Design and measurements: notes entry "Local Wikipedia packs".
"""
import json
import os
import random
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

USER_AGENT = "Odysseus-local-wiki/0.1 (personal research tool; https://github.com/odysseus-dev/odysseus)"
BATCH = 50                 # titles/pageids per query the API accepts for info/redirects
MAX_RETRIES = 5
MIN_INTERVAL = 0.1         # seconds between requests; requests are serial
CHUNK_TARGET = 600
CHUNK_MAX = 1200
PACK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")

# Sections that are lists of links or citations, not text worth searching.
SKIP_SECTIONS = {
    "references", "external links", "see also", "further reading", "notes", "bibliography",
    "sources", "citations", "gallery", "footnotes",
    "einzelnachweise", "weblinks", "literatur", "siehe auch", "anmerkungen", "quellen",
}
STOPWORDS = set("""
a an and are as at be by for from how in is it of on or that the this to was what when where which who why with
der die das und oder ist ein eine einen einem einer für mit von zu im in am an auf aus bei wie was wo wer
""".split())

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles(pageid INTEGER PRIMARY KEY, title TEXT, url TEXT, lang TEXT,
                                    revid INTEGER, fetched_at TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS aliases(pageid INTEGER, alias TEXT);
CREATE INDEX IF NOT EXISTS aliases_pageid ON aliases(pageid);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
    title, aliases, heading, body, pageid UNINDEXED, chunk_no UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2');
"""


class WikiApiError(RuntimeError):
    pass


def default_dir():
    from src.constants import DATA_DIR
    return os.path.join(DATA_DIR, "wiki_packs")


# --------------------------------------------------------------------- API ---

def _urllib_fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read() or b""


class WikiApi:
    """The MediaWiki action API of one language edition. Serial requests, a
    descriptive User-Agent, maxlag=5, and backoff on 429/503/maxlag, as
    Wikimedia's API etiquette asks. `fetch(url) -> (status, headers, body)`
    and `sleep` are injectable for tests."""

    def __init__(self, lang, fetch=None, sleep=time.sleep, min_interval=MIN_INTERVAL):
        if not re.fullmatch(r"[a-z]{2,3}(-[a-z]+)?", lang or ""):
            raise ValueError(f"not a Wikipedia language code: {lang!r}")
        self.lang = lang
        self.base = f"https://{lang}.wikipedia.org/w/api.php"
        self.fetch = fetch or _urllib_fetch
        self.sleep = sleep
        self.min_interval = min_interval
        self.requests = 0
        self.seconds = 0.0
        self._last = 0.0

    def get(self, **params):
        params = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
        url = self.base + "?" + urllib.parse.urlencode(params)
        for attempt in range(MAX_RETRIES):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                self.sleep(wait)
            started = time.monotonic()
            try:
                status, headers, body = self.fetch(url)
            except OSError as exc:  # DNS, refused, reset, timeout: no point retrying blind
                raise WikiApiError(f"network error reaching {self.lang}.wikipedia.org: {exc}") from exc
            self._last = time.monotonic()
            self.requests += 1
            self.seconds += self._last - started
            retry_after = _retry_after(headers, default=2 ** attempt * 5)
            if status in (429, 503):
                self.sleep(retry_after)
                continue
            if status != 200:
                raise WikiApiError(f"HTTP {status} from {self.lang}.wikipedia.org")
            data = json.loads(body or b"{}")
            err = data.get("error") or {}
            if err.get("code") == "maxlag":
                self.sleep(retry_after)
                continue
            if err:
                raise WikiApiError(f"{err.get('code')}: {err.get('info')}")
            return data
        raise WikiApiError(f"gave up after {MAX_RETRIES} attempts (rate limited or lagged)")

    def query_all(self, **params):
        """Yield each response of a continued query."""
        cont = {}
        while True:
            data = self.get(action="query", **params, **cont)
            yield data
            if "continue" not in data:
                return
            cont = data["continue"]


def _retry_after(headers, default):
    for k, v in (headers or {}).items():
        if k.lower() == "retry-after":
            try:
                return max(1.0, float(v))
            except ValueError:
                break
    return float(default)


def article_url(lang, title):
    return f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"), safe="()_,'-")


# ------------------------------------------------------------- definitions ---

def _registry_path(base):
    return os.path.join(base, "packs.json")


def load_packs(base=None):
    path = _registry_path(base or default_dir())
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {p["id"]: p for p in json.load(f).get("packs", [])}


def save_packs(packs, base=None):
    base = base or default_dir()
    os.makedirs(base, exist_ok=True)
    path = _registry_path(base)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "packs": sorted(packs.values(), key=lambda p: p["id"])}, f,
                  indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def define_pack(pack_id, lang, source, name=None, topic="", exclude_title=(), base=None):
    """Add or replace a pack definition. `source` is {"type": "category",
    "name": ..., "depth": N} or {"type": "wikiproject", "name": ...}."""
    if not PACK_ID_RE.match(pack_id or ""):
        raise ValueError("pack id: lower-case letters, digits and '-', at most 41 characters")
    WikiApi(lang)  # validates the language code
    kind = source.get("type")
    if kind == "category":
        depth = int(source.get("depth", 1))
        if not 0 <= depth <= 6:
            raise ValueError("category depth must be 0-6")
        source = {"type": "category", "name": _strip_ns(source["name"], "Category"), "depth": depth}
    elif kind == "wikiproject":
        source = {"type": "wikiproject", "name": _strip_ns(source["name"], "Template").removeprefix("WikiProject ")}
    else:
        raise ValueError(f"unknown source type {kind!r}")
    for pat in exclude_title:
        re.compile(pat)
    packs = load_packs(base)
    old = packs.get(pack_id, {})
    packs[pack_id] = {"id": pack_id, "name": name or pack_id, "topic": topic, "lang": lang, "source": source,
                      "exclude_title": list(exclude_title), "state": old.get("state", "defined"),
                      "articles": old.get("articles"), "built": old.get("built")}
    save_packs(packs, base)
    return packs[pack_id]


def _strip_ns(title, ns):
    title = (title or "").strip().replace("_", " ")
    for prefix in (("Category:", "Kategorie:") if ns == "Category" else (f"{ns}:",)):
        if title.startswith(prefix):
            return title[len(prefix):].strip()
    return title


# ----------------------------------------------------------------- listing ---

def list_category(api, name, depth):
    """{title: depth found at} for articles in a category tree, and
    {depth: subcategories} — those at depth + 1 were seen but not followed,
    which shows where the tree drifts before anything is built."""
    titles, subcats_at = {}, {}
    seen = {name}
    frontier = [name]
    for d in range(depth + 1):
        nxt = []
        for cat in frontier:
            for data in api.query_all(list="categorymembers", cmtitle=f"Category:{cat}",
                                      cmtype="page|subcat", cmnamespace="0|14", cmlimit="500"):
                for m in data.get("query", {}).get("categorymembers", []):
                    if m.get("ns") == 0:
                        titles.setdefault(m["title"], d)
                    elif m.get("ns") == 14:
                        sub = _strip_ns(m["title"], "Category")
                        subcats_at.setdefault(d + 1, []).append(sub)
                        if sub not in seen:
                            seen.add(sub)
                            nxt.append(sub)
        frontier = nxt
    return titles, subcats_at


def list_wikiproject(api, name):
    titles = {}
    for data in api.query_all(list="embeddedin", eititle=f"Template:WikiProject {name}",
                              einamespace="1", eilimit="500"):
        for m in data.get("query", {}).get("embeddedin", []):
            t = m["title"].split(":", 1)[1] if ":" in m["title"] else m["title"]
            titles.setdefault(t, 0)
    return titles


def resolve_pages(api, titles):
    """Current pageid, revid and wikitext length per article (redirects
    followed, missing pages left out), BATCH titles per request."""
    pages = {}
    titles = list(titles)
    for i in range(0, len(titles), BATCH):
        data = api.get(action="query", prop="info", redirects="1", titles="|".join(titles[i:i + BATCH]))
        for p in data.get("query", {}).get("pages", []):
            if p.get("missing") or p.get("invalid") or p.get("ns", 0) != 0 or "pageid" not in p:
                continue
            pages[p["pageid"]] = {"pageid": p["pageid"], "title": p["title"],
                                  "revid": p.get("lastrevid"), "length": p.get("length", 0)}
    return pages


def plan(pack, api=None, base=None, sample=25, seed=0):
    """List the pack's articles and write <id>.plan.json; download no text."""
    base = base or default_dir()
    api = api or WikiApi(pack["lang"])
    src = pack["source"]
    subcats_at = {}
    if src["type"] == "category":
        titles, subcats_at = list_category(api, src["name"], src["depth"])
    else:
        titles = list_wikiproject(api, src["name"])
    excluded = [t for t in titles if any(re.search(p, t) for p in pack.get("exclude_title", []))]
    for t in excluded:
        titles.pop(t)
    pages = resolve_pages(api, titles)
    by_depth = {}
    depth_of = {t: d for t, d in titles.items()}
    for p in pages.values():
        d = depth_of.get(p["title"], 0)
        by_depth[d] = by_depth.get(d, 0) + 1
    rnd = random.Random(seed)
    result = {
        "pack": pack["id"], "planned": _now(), "articles": len(pages),
        "listed_titles": len(titles) + len(excluded), "excluded": sorted(excluded),
        "by_depth": {str(k): v for k, v in sorted(by_depth.items())},
        "subcategories_not_followed": sorted(set(subcats_at.get(src.get("depth", 0) + 1, []))),
        "wikitext_bytes": sum(p["length"] or 0 for p in pages.values()),
        "sample": sorted(rnd.sample([p["title"] for p in pages.values()], min(sample, len(pages)))),
        "requests": api.requests, "seconds": round(api.seconds, 1),
        "pages": sorted(pages.values(), key=lambda p: p["title"]),
    }
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, f"{pack['id']}.plan.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    _set_state(pack["id"], base, state="planned", articles=len(pages))
    return result


# ------------------------------------------------------------------- build ---

def db_path(pack_id, base=None):
    return os.path.join(base or default_dir(), f"{pack_id}.sqlite")


def open_db(pack_id, base=None):
    con = sqlite3.connect(db_path(pack_id, base))
    con.executescript(SCHEMA)
    return con


def split_sections(text, title):
    """[(heading, body)] from a plain-text extract with `== Heading ==` lines;
    reference and link sections (and their subsections) are left out."""
    sections, heading, lines, skipping = [], "", [], False
    for line in (text or "").splitlines():
        m = re.fullmatch(r"\s*(=+)\s*(.*?)\s*\1\s*", line)
        if m:
            if lines and not skipping:
                sections.append((heading, "\n".join(lines).strip()))
            lines = []
            level, heading = len(m.group(1)), m.group(2)
            if level <= 2:
                skipping = heading.strip().lower() in SKIP_SECTIONS
            elif heading.strip().lower() in SKIP_SECTIONS:
                skipping = True
            continue
        lines.append(line)
    if lines and not skipping:
        sections.append((heading, "\n".join(lines).strip()))
    return [(h, b) for h, b in sections if b]


def chunk_body(body, target=CHUNK_TARGET, hard_max=CHUNK_MAX):
    out, cur = [], ""
    for para in (p.strip() for p in body.split("\n")):
        if not para:
            continue
        while len(para) > hard_max:
            cut = para.rfind(" ", 0, hard_max)
            cut = cut if cut > hard_max // 2 else hard_max
            if cur:
                out.append(cur)
                cur = ""
            out.append(para[:cut].strip())
            para = para[cut:].strip()
        if cur and len(cur) + len(para) + 1 > target:
            out.append(cur)
            cur = para
        else:
            cur = f"{cur}\n{para}" if cur else para
    if cur:
        out.append(cur)
    return out


def fetch_redirects(api, pageids):
    aliases = {}
    ids = list(pageids)
    for i in range(0, len(ids), BATCH):
        for data in api.query_all(prop="redirects", rdnamespace="0", rdlimit="max",
                                  pageids="|".join(str(x) for x in ids[i:i + BATCH])):
            for p in data.get("query", {}).get("pages", []):
                for r in p.get("redirects", []) or []:
                    aliases.setdefault(p["pageid"], []).append(r["title"])
    return aliases


def fetch_extract(api, pageid):
    data = api.get(action="query", prop="extracts|info", explaintext="1", exsectionformat="wiki",
                   pageids=str(pageid))
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    p = pages[0]
    return {"pageid": p["pageid"], "title": p["title"], "revid": p.get("lastrevid"), "text": p.get("extract") or ""}


def store_article(con, lang, art, aliases):
    pid = art["pageid"]
    con.execute("DELETE FROM chunks WHERE pageid = ?", (pid,))
    con.execute("DELETE FROM aliases WHERE pageid = ?", (pid,))
    con.execute("INSERT OR REPLACE INTO articles VALUES (?,?,?,?,?,?,?)",
                (pid, art["title"], article_url(lang, art["title"]), lang, art["revid"], _now(), art["text"]))
    con.executemany("INSERT INTO aliases VALUES (?,?)", [(pid, a) for a in aliases])
    alias_text = " | ".join(aliases)
    n = 0
    for heading, body in split_sections(art["text"], art["title"]):
        for chunk in chunk_body(body):
            con.execute("INSERT INTO chunks(title, aliases, heading, body, pageid, chunk_no) VALUES (?,?,?,?,?,?)",
                        (art["title"], alias_text, heading, chunk, pid, n))
            n += 1
    return n


def build(pack, api=None, base=None, limit=None, progress=None):
    """Bring the pack's index up to date: list, then fetch only articles that
    are new or whose revision changed, and drop articles that left the set.
    Commits per article, so an interrupted build resumes where it stopped."""
    base = base or default_dir()
    api = api or WikiApi(pack["lang"])
    planned = plan(pack, api=api, base=base)
    wanted = {p["pageid"]: p for p in planned["pages"]}
    con = open_db(pack["id"], base)
    try:
        stored = dict(con.execute("SELECT pageid, revid FROM articles"))
        gone = [pid for pid in stored if pid not in wanted]
        for pid in gone:
            con.execute("DELETE FROM chunks WHERE pageid = ?", (pid,))
            con.execute("DELETE FROM aliases WHERE pageid = ?", (pid,))
            con.execute("DELETE FROM articles WHERE pageid = ?", (pid,))
        con.commit()
        todo = [pid for pid, p in wanted.items() if stored.get(pid) != p["revid"]]
        todo.sort(key=lambda pid: wanted[pid]["title"])
        unchanged, pending = len(wanted) - len(todo), len(todo)
        if limit is not None:
            todo = todo[:limit]
        aliases = fetch_redirects(api, todo) if todo else {}
        fetched = chunks = missing = 0
        t0, r0 = api.seconds, api.requests
        for pid in todo:
            art = fetch_extract(api, pid)
            if art is None:
                missing += 1
                continue
            chunks += store_article(con, pack["lang"], art, aliases.get(pid, []))
            con.commit()
            fetched += 1
            if progress and fetched % 25 == 0:
                progress(fetched, len(todo), (api.seconds - t0) / max(1, api.requests - r0))
        total = con.execute("SELECT count(*) FROM articles").fetchone()[0]
        con.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)", (_now(),))
        con.commit()
    finally:
        con.close()
    left = pending - fetched - missing
    _set_state(pack["id"], base, state="partial" if left else "built", articles=total,
               built=_now())
    return {"pack": pack["id"], "listed": len(wanted), "fetched": fetched, "unchanged": unchanged,
            "left_for_later": left, "missing": missing, "removed": len(gone), "chunks_added": chunks, "articles_stored": total,
            "requests": api.requests, "seconds": round(api.seconds, 1),
            "seconds_per_request": round(api.seconds / max(1, api.requests), 3)}


# ------------------------------------------------------------------- query ---

def fts_query(text, max_terms=16):
    """Free text → an FTS5 MATCH string of quoted terms joined by OR. Every
    term is quoted, so operators and punctuation in the text can't raise."""
    terms, seen = [], set()
    for tok in re.findall(r"\w+", text or "", flags=re.UNICODE):
        t = tok.lower()
        if len(t) < 2 or t in STOPWORDS or t in seen:
            continue
        seen.add(t)
        terms.append('"' + t.replace('"', '""') + '"')
        if len(terms) >= max_terms:
            break
    return " OR ".join(terms) or None


def query(pack_id, text, k=5, base=None):
    """Best chunk per article, best articles first: [{title, url, heading,
    snippet, score}] with score = -bm25 (higher is better)."""
    match = fts_query(text)
    path = db_path(pack_id, base)
    if not match or not os.path.isfile(path):
        return []
    con = sqlite3.connect(path)
    try:
        rows = con.execute(
            "SELECT c.pageid, c.title, a.url, c.heading, c.body, bm25(chunks, 10.0, 5.0, 2.0, 1.0) AS s "
            "FROM chunks c JOIN articles a ON a.pageid = c.pageid "
            "WHERE chunks MATCH ? ORDER BY s LIMIT ?", (match, max(50, k * 10))).fetchall()
    finally:
        con.close()
    out, seen = [], set()
    for pid, title, url, heading, body, s in rows:
        if pid in seen:
            continue
        seen.add(pid)
        out.append({"pageid": pid, "title": title, "url": url, "heading": heading,
                    "snippet": " ".join(body.split())[:300], "score": round(-s, 4)})
        if len(out) >= k:
            break
    return out


def delete_pack(pack_id, base=None, forget=False):
    base = base or default_dir()
    removed = []
    for suffix in (".sqlite", ".sqlite-journal", ".plan.json"):
        path = os.path.join(base, pack_id + suffix)
        if os.path.exists(path):
            os.remove(path)
            removed.append(os.path.basename(path))
    packs = load_packs(base)
    if pack_id in packs:
        if forget:
            packs.pop(pack_id)
        else:
            packs[pack_id].update(state="defined", articles=None, built=None)
        save_packs(packs, base)
    return removed


def _set_state(pack_id, base, **fields):
    packs = load_packs(base)
    if pack_id in packs:
        packs[pack_id].update(fields)
        save_packs(packs, base)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
