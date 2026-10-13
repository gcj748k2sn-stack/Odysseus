"""src/wiki_packs.py: packs list the right articles, builds resume and only
refetch what changed, and queries never raise on user text. The Wikipedia API
is a fake that answers like the real one (formatversion=2), so no network."""
import json
import sqlite3
import urllib.parse

import pytest

from src import wiki_packs as wp

LEAD = "Pleurotus djamor, the pink oyster mushroom, is a species of fungal plant mushroom."


class FakeWiki:
    """A tiny wiki behind the action API. `page_size` forces continuation."""

    def __init__(self, page_size=2):
        self.page_size = page_size
        self.categories = {
            "Edible fungi": [(0, "Pleurotus djamor"), (0, "Boletus edulis"), (14, "Category:Boletus"),
                             (0, "List of fungi albums")],
            "Boletus": [(0, "Boletus badius"), (14, "Category:Beer")],
            "Beer": [(0, "Beer")],
        }
        self.pages = {
            "Pleurotus djamor": {"pageid": 1, "revid": 100, "redirects": ["Pink oyster mushroom", "Flamingo oyster"],
                                 "text": f"{LEAD}\nIt grows in the tropics of Indonesia and the Philippines.\n\n"
                                         "== Distribution ==\nNative range: tropical Asia, Africa and the Americas.\n\n"
                                         "== Cultivation ==\nFruits at 20 to 30 degrees Celsius.\n\n"
                                         "== References ==\nSmith, J. (2001). Mushrooms of the price index.\n"
                                         "=== Further sources ===\nA recipe list for crepes.\n"},
            "Boletus edulis": {"pageid": 2, "revid": 200, "redirects": ["Porcini", "Steinpilz"],
                               "text": "Boletus edulis is a basidiomycete fungus.\n\n== Habitat ==\n"
                                       "It forms mycorrhiza with spruce and pine in Europe."},
            "Boletus badius": {"pageid": 3, "revid": 300, "redirects": [],
                               "text": "Imleria badia, the bay bolete, is an edible fungus."},
            "Beer": {"pageid": 4, "revid": 400, "redirects": [], "text": "Beer is brewed with yeast."},
            "List of fungi albums": {"pageid": 5, "revid": 500, "redirects": [], "text": "Albums."},
            "Lion's mane": {"pageid": 6, "revid": 600, "redirects": [], "text": "Hericium erinaceus."},
        }
        self.banner = ["Talk:Pleurotus djamor", "Talk:Lion's mane", "Talk:Deleted page"]
        self.title_redirects = {"Porcini": "Boletus edulis"}
        self.queue = []          # (status, headers, body) answered before the real response
        self.calls = []          # parsed params of every request
        self.fail_after = None   # raise after this many extract requests

    def by_id(self, pid):
        return next(p | {"title": t} for t, p in self.pages.items() if p["pageid"] == pid)

    def __call__(self, url):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        self.calls.append(q)
        if self.queue:
            return self.queue.pop(0)
        return 200, {}, json.dumps(self.answer(q)).encode()

    def _paged(self, items, key, cont_key, q):
        start = int(q.get(cont_key, 0))
        out = {"batchcomplete": True, "query": {key: items[start:start + self.page_size]}}
        if start + self.page_size < len(items):
            out["continue"] = {cont_key: str(start + self.page_size), "continue": "-||"}
        return out

    def answer(self, q):
        if q.get("list") == "categorymembers":
            name = q["cmtitle"].split(":", 1)[1]
            items = [{"ns": ns, "title": t, "pageid": 0} for ns, t in self.categories.get(name, [])]
            return self._paged(items, "categorymembers", "cmcontinue", q)
        if q.get("list") == "embeddedin":
            assert q["eititle"] == "Template:WikiProject Fungi"
            return self._paged([{"ns": 1, "title": t} for t in self.banner], "embeddedin", "eicontinue", q)
        if q.get("prop") == "info":
            pages = []
            for t in q["titles"].split("|"):
                t = self.title_redirects.get(t, t)
                if t in self.pages:
                    p = self.pages[t]
                    pages.append({"pageid": p["pageid"], "ns": 0, "title": t, "lastrevid": p["revid"],
                                  "length": len(p["text"]) * 2})
                else:
                    pages.append({"ns": 0, "title": t, "missing": True})
            return {"query": {"pages": pages}}
        if q.get("prop") == "redirects":
            items = []
            for pid in q["pageids"].split("|"):
                p = self.by_id(int(pid))
                for r in p["redirects"]:
                    items.append((p["pageid"], r))
            start = int(q.get("rdcontinue", 0))
            chunk = items[start:start + self.page_size]
            pages = {}
            for pid, r in chunk:
                pages.setdefault(pid, {"pageid": pid, "ns": 0, "title": self.by_id(pid)["title"], "redirects": []})
                pages[pid]["redirects"].append({"ns": 0, "title": r})
            out = {"query": {"pages": list(pages.values())}}
            if start + self.page_size < len(items):
                out["continue"] = {"rdcontinue": str(start + self.page_size), "continue": "||"}
            return out
        if q.get("prop") == "extracts|info":
            n = sum(1 for c in self.calls if c.get("prop") == "extracts|info")
            if self.fail_after is not None and n > self.fail_after:
                raise ConnectionError("network gone")
            p = self.by_id(int(q["pageids"]))
            return {"query": {"pages": [{"pageid": p["pageid"], "ns": 0, "title": p["title"],
                                         "lastrevid": p["revid"], "extract": p["text"]}]}}
        raise AssertionError(f"unexpected request {q}")

    def extract_calls(self):
        return [int(c["pageids"]) for c in self.calls if c.get("prop") == "extracts|info"]


@pytest.fixture
def wiki():
    return FakeWiki()


@pytest.fixture
def base(tmp_path):
    return str(tmp_path)


def api(wiki):
    return wp.WikiApi("en", fetch=wiki, sleep=lambda s: None, min_interval=0)


def define(base, depth=1, exclude=(r"^List of .* albums$",)):
    return wp.define_pack("edible-fungi-en", "en", {"type": "category", "name": "Category:Edible fungi", "depth": depth},
                          topic="biology", exclude_title=exclude, base=base)


def test_category_plan_respects_depth_and_exclusions_and_shows_the_drift(wiki, base):
    r = wp.plan(define(base, depth=1), api=api(wiki), base=base)
    titles = {p["title"] for p in r["pages"]}
    assert titles == {"Pleurotus djamor", "Boletus edulis", "Boletus badius"}
    assert r["excluded"] == ["List of fungi albums"]
    assert r["by_depth"] == {"0": 2, "1": 1}
    assert r["subcategories_not_followed"] == ["Beer"]
    assert json.loads(open(f"{base}/edible-fungi-en.plan.json").read())["articles"] == 3
    assert wp.load_packs(base)["edible-fungi-en"]["state"] == "planned"
    assert wiki.extract_calls() == []          # planning downloads no text


def test_depth_zero_lists_only_the_category_itself(wiki, base):
    r = wp.plan(define(base, depth=0), api=api(wiki), base=base)
    assert {p["title"] for p in r["pages"]} == {"Pleurotus djamor", "Boletus edulis"}
    assert r["subcategories_not_followed"] == ["Boletus"]


def test_wikiproject_lists_banner_pages_and_skips_missing_ones(wiki, base):
    pack = wp.define_pack("fungi-project-en", "en", {"type": "wikiproject", "name": "WikiProject Fungi"}, base=base)
    r = wp.plan(pack, api=api(wiki), base=base)
    assert {p["title"] for p in r["pages"]} == {"Pleurotus djamor", "Lion's mane"}


def test_build_stores_text_aliases_and_drops_reference_sections(wiki, base):
    r = wp.build(define(base), api=api(wiki), base=base)
    assert (r["fetched"], r["articles_stored"], r["left_for_later"]) == (3, 3, 0)
    con = sqlite3.connect(wp.db_path("edible-fungi-en", base))
    aliases = {a for (a,) in con.execute("SELECT alias FROM aliases WHERE pageid = 1")}
    assert aliases == {"Pink oyster mushroom", "Flamingo oyster"}
    bodies = " ".join(b for (b,) in con.execute("SELECT body FROM chunks"))
    assert "Native range" in bodies and "price index" not in bodies and "crepes" not in bodies
    url = con.execute("SELECT url FROM articles WHERE pageid = 1").fetchone()[0]
    assert url == "https://en.wikipedia.org/wiki/Pleurotus_djamor"
    assert wp.load_packs(base)["edible-fungi-en"]["state"] == "built"


def test_an_interrupted_build_resumes_without_refetching(wiki, base):
    pack = define(base)
    wiki.fail_after = 1
    with pytest.raises(wp.WikiApiError, match="network error"):
        wp.build(pack, api=api(wiki), base=base)
    assert wiki.extract_calls() == [3, 2]       # alphabetical: Boletus badius, Boletus edulis (failed)
    wiki.fail_after, wiki.calls = None, []
    r = wp.build(pack, api=api(wiki), base=base)
    assert wiki.extract_calls() == [2, 1]       # badius was stored and is not fetched again
    assert (r["fetched"], r["unchanged"], r["articles_stored"]) == (2, 1, 3)


def test_rebuild_fetches_only_changed_articles_and_removes_departed_ones(wiki, base):
    pack = define(base)
    wp.build(pack, api=api(wiki), base=base)
    wiki.pages["Boletus edulis"]["revid"] = 201
    wiki.pages["Boletus edulis"]["text"] = "Boletus edulis, the penny bun, a new revision."
    wiki.categories["Boletus"] = [(14, "Category:Beer")]          # Boletus badius leaves the set
    wiki.calls = []
    r = wp.build(pack, api=api(wiki), base=base)
    assert wiki.extract_calls() == [2]
    assert (r["fetched"], r["removed"], r["articles_stored"]) == (1, 1, 2)
    assert [h["title"] for h in wp.query("edible-fungi-en", "penny bun", base=base)] == ["Boletus edulis"]
    assert wp.query("edible-fungi-en", "bay bolete", base=base) == []


def test_limit_builds_part_and_says_so(wiki, base):
    r = wp.build(define(base), api=api(wiki), base=base, limit=1)
    assert (r["fetched"], r["left_for_later"]) == (1, 2)
    assert wp.load_packs(base)["edible-fungi-en"]["state"] == "partial"


def test_query_ranks_the_right_article_and_finds_it_by_alias(wiki, base):
    wp.build(define(base), api=api(wiki), base=base)
    hits = wp.query("edible-fungi-en", "Pleurotus djamor pink oyster mushroom native range Indonesia", base=base)
    assert hits[0]["title"] == "Pleurotus djamor"
    assert len({h["pageid"] for h in hits}) == len(hits)        # one hit per article
    assert wp.query("edible-fungi-en", "flamingo oyster", base=base)[0]["title"] == "Pleurotus djamor"
    assert wp.query("edible-fungi-en", "Steinpilz", base=base)[0]["title"] == "Boletus edulis"


@pytest.mark.parametrize("text", ['NEAR( "unbalanced', "a AND OR NOT *", "pink^oyster:{x}", "\"\"\"", "-", ""])
def test_query_never_raises_on_user_text(wiki, base, text):
    wp.build(define(base), api=api(wiki), base=base)
    assert isinstance(wp.query("edible-fungi-en", text, base=base), list)


@pytest.mark.parametrize("text", ["gold price per ounce today", "Imagine Dragons Thunder lyrics", "EUR USD exchange rate"])
def test_negative_controls_find_nothing(wiki, base, text):
    """Words that are in no stored article return nothing. (Shared common
    words would match: relevance is the reranker's job, in Phase 2.)"""
    wp.build(define(base), api=api(wiki), base=base)
    assert wp.query("edible-fungi-en", text, base=base) == []


def test_query_on_a_missing_pack_is_empty(base):
    assert wp.query("nope", "pleurotus", base=base) == []


def test_rate_limits_and_maxlag_are_waited_out(wiki):
    waits = []
    a = wp.WikiApi("en", fetch=wiki, sleep=waits.append, min_interval=0)
    wiki.queue = [(429, {"Retry-After": "7"}, b""),
                  (200, {}, json.dumps({"error": {"code": "maxlag", "info": "lagged"}}).encode())]
    data = a.get(action="query", prop="info", titles="Beer")
    assert data["query"]["pages"][0]["title"] == "Beer"
    assert waits == [7.0, 10.0]
    assert all(c["maxlag"] == "5" and c["formatversion"] == "2" for c in wiki.calls)


def test_persistent_rate_limit_gives_up(wiki):
    a = wp.WikiApi("en", fetch=wiki, sleep=lambda s: None, min_interval=0)
    wiki.queue = [(503, {}, b"")] * wp.MAX_RETRIES
    with pytest.raises(wp.WikiApiError):
        a.get(action="query", prop="info", titles="Beer")


def test_api_errors_are_raised_not_swallowed(wiki):
    a = wp.WikiApi("en", fetch=wiki, sleep=lambda s: None, min_interval=0)
    wiki.queue = [(200, {}, json.dumps({"error": {"code": "badvalue", "info": "nope"}}).encode())]
    with pytest.raises(wp.WikiApiError, match="badvalue"):
        a.get(action="query", list="nothing")


def test_definitions_are_validated(base):
    with pytest.raises(ValueError):
        wp.define_pack("Bad Id", "en", {"type": "category", "name": "Fungi"}, base=base)
    with pytest.raises(ValueError):
        wp.define_pack("x", "en.evil.com/", {"type": "category", "name": "Fungi"}, base=base)
    with pytest.raises(ValueError):
        wp.define_pack("x", "en", {"type": "category", "name": "Fungi", "depth": 9}, base=base)
    p = wp.define_pack("pilze-de", "de", {"type": "category", "name": "Kategorie:Speisepilzart", "depth": 0}, base=base)
    assert p["source"]["name"] == "Speisepilzart"


def test_delete_removes_files_and_resets_the_definition(wiki, base):
    wp.build(define(base), api=api(wiki), base=base)
    assert sorted(wp.delete_pack("edible-fungi-en", base=base)) == ["edible-fungi-en.plan.json", "edible-fungi-en.sqlite"]
    assert wp.load_packs(base)["edible-fungi-en"]["state"] == "defined"
    wp.delete_pack("edible-fungi-en", base=base, forget=True)
    assert wp.load_packs(base) == {}


def test_chunks_respect_the_hard_maximum():
    body = ("word " * 700).strip() + "\n" + "short paragraph"
    chunks = wp.chunk_body(body)
    assert all(len(c) <= wp.CHUNK_MAX for c in chunks)
    assert " ".join(chunks).split() == body.replace("\n", " ").split()


def test_module_never_imports_the_database():
    """Importing core.database runs init_db() against data/app.db."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(wp))
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
           {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and (m.startswith("core") or m.startswith("sqlalchemy")) for m in mods)
