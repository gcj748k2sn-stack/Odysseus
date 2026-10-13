"""bench_web_filter_label_ui.py: the labelling page writes labels to the sheet,
and only there, never loses a label made elsewhere, and only previews URLs
that are in the sheet."""
import ast
import csv
import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("bench_web_filter_label_ui_under_test",
                                                  ROOT / "scripts" / "bench_web_filter_label_ui.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


U = _load()
W = U.W

ROWS = [
    # far from the threshold, unlabelled
    {"label": "", "score": "0.900000", "query": "silver price today", "rank": "1",
     "domain": "kitco.com", "title": "Silver", "snippet": "spot", "url": "https://kitco.com/s"},
    # nearest the threshold, unlabelled, ranked second in its search
    {"label": "", "score": "0.040000", "query": "pink oyster fruiting", "rank": "2",
     "domain": "grocycle.com", "title": "Grow pink oyster", "snippet": "20-30 C", "url": "https://grocycle.com/p"},
    {"label": "n", "score": "0.020000", "query": "pink oyster fruiting", "rank": "1",
     "domain": "victoriassecret.com", "title": "Pink", "snippet": "", "url": "https://victoriassecret.com/x"},
    # every row labelled
    {"label": "y", "score": "0.036000", "query": "Essen Wetter", "rank": "1",
     "domain": "wetter.com", "title": "Essen", "snippet": "", "url": "https://wetter.com/essen"},
    # no score at all
    {"label": "", "score": "", "query": "ssd1306 address", "rank": "1",
     "domain": "adafruit.com", "title": "SSD1306", "snippet": "0x3C", "url": "https://adafruit.com/ssd"},
]


@pytest.fixture
def sheet(tmp_path):
    path = tmp_path / "labels.csv"
    W.save_label_rows(path, [dict(r) for r in ROWS])
    return path


def _labels(path):
    with open(path, encoding="utf-8", newline="") as f:
        return {r["url"]: r["label"] for r in csv.DictReader(f)}


def _id(url):
    row = next(r for r in ROWS if r["url"] == url)
    return W.row_id(row["query"], url)


def test_searches_nearest_the_threshold_first_unscored_after_labelled_last(sheet):
    s = U.LabelStore(sheet).searches()
    assert [x["query"] for x in s] == ["pink oyster fruiting", "silver price today",
                                       "ssd1306 address", "Essen Wetter"]
    assert [r["rank"] for r in s[0]["rows"]] == ["1", "2"]
    assert s[0]["open"] == 1 and s[-1]["open"] == 0


def test_a_label_is_saved_at_once_and_nothing_else_changes(sheet):
    store = U.LabelStore(sheet)
    store.set_label(_id("https://grocycle.com/p"), "y")
    after = _labels(sheet)
    assert after["https://grocycle.com/p"] == "y"
    assert after == {**{r["url"]: r["label"] for r in ROWS}, "https://grocycle.com/p": "y"}
    assert W.load_labels(sheet)[W.label_key("pink oyster fruiting", "https://grocycle.com/p")] == "y"
    assert _labels(sheet.with_name("labels.csv.bak"))["https://grocycle.com/p"] == ""
    store.set_label(_id("https://grocycle.com/p"), "")
    assert _labels(sheet)["https://grocycle.com/p"] == ""


def test_a_sheet_changed_on_disk_is_never_overwritten(sheet):
    store = U.LabelStore(sheet)
    rows = W.read_label_rows(sheet)
    rows[0]["label"] = "n"  # labelled in Numbers while the page was open
    rows.append({"label": "y", "query": "extra", "url": "https://extra.org/"})
    W.save_label_rows(sheet, rows)
    before = sheet.read_bytes()
    with pytest.raises(U.SheetChanged):
        store.set_label(_id("https://grocycle.com/p"), "y")
    assert sheet.read_bytes() == before
    store.reload()
    store.set_label(_id("https://grocycle.com/p"), "y")
    after = _labels(sheet)
    assert after["https://kitco.com/s"] == "n" and after["https://extra.org/"] == "y"


def test_bad_values_and_unknown_rows_are_refused(sheet):
    store = U.LabelStore(sheet)
    before = sheet.read_bytes()
    with pytest.raises(ValueError):
        store.set_label(_id("https://kitco.com/s"), "maybe")
    with pytest.raises(KeyError):
        store.set_label("0000000000", "y")
    assert sheet.read_bytes() == before


def test_the_page_never_writes_ratings():
    """Labels here are what the rating replay grades against; a label written
    as a rating would be left out of that grading and bias live searches."""
    tree = ast.parse((ROOT / "scripts" / "bench_web_filter_label_ui.py").read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
            {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    code_strings = [s for s in strings if "never touches" not in s and "Never writes" not in s]
    assert "RATINGS_FILE" not in names and not any(n.startswith("rating") for n in names)
    assert not any("web_ratings" in s or "/api/web-ratings" in s for s in code_strings)


def test_html_to_text_keeps_the_text_and_drops_scripts_and_menus():
    title, text = U.html_to_text(
        "<html><head><title> Pink  Oyster </title><script>var x='hidden script text that is long';</script></head>"
        "<body><nav>Home | Shop | A menu line that is long enough to count</nav>"
        "<p>Pleurotus djamor fruits between 20 and 30 degrees Celsius.</p><p>short</p></body></html>")
    assert title == "Pink Oyster"
    assert text == "Pleurotus djamor fruits between 20 and 30 degrees Celsius."


def test_preview_refuses_non_http_urls():
    assert "error" in U.fetch_preview("file:///etc/passwd")


@pytest.fixture
def server(sheet):
    store = U.LabelStore(sheet)
    fetched = []

    def fake_fetch(url):
        fetched.append(url)
        return {"title": "T", "text": "page text"}

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), U.make_handler(store, fetch=fake_fetch))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", fetched, sheet
    httpd.shutdown()
    httpd.server_close()


def _get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_server_round_trip(server):
    base, fetched, sheet = server
    with urllib.request.urlopen(base + "/") as r:
        assert b"/api/label" in r.read()
    code, data = _get(base + "/api/searches")
    assert code == 200 and data["counts"] == {"labelled": 2, "total": 5}
    rid = data["searches"][0]["rows"][1]["id"]
    assert _post(base + "/api/label", {"id": rid, "label": "n"}) == (200, {"ok": True, "counts": {"labelled": 3, "total": 5}})
    assert _labels(sheet)["https://grocycle.com/p"] == "n"
    assert _post(base + "/api/label", {"id": rid, "label": "x"})[0] == 400
    assert _post(base + "/api/label", {"id": "nope", "label": "y"})[0] == 404


def test_server_previews_only_urls_from_the_sheet_and_caches_them(server):
    base, fetched, _ = server
    q = urllib.parse.quote
    assert _get(base + "/api/preview?url=" + q("http://169.254.169.254/latest"))[0] == 404
    assert fetched == []
    for _ in range(2):
        assert _get(base + "/api/preview?url=" + q("https://kitco.com/s")) == (200, {"title": "T", "text": "page text"})
    assert fetched == ["https://kitco.com/s"]


def test_server_reports_a_sheet_changed_on_disk(server):
    base, _, sheet = server
    rows = W.read_label_rows(sheet)
    rows[0]["label"] = "y"
    rows[0]["snippet"] = "edited elsewhere, so the size changes"
    W.save_label_rows(sheet, rows)
    code, data = _post(base + "/api/label", {"id": _id("https://grocycle.com/p"), "label": "y"})
    assert code == 409 and "Reload" in data["error"]
    assert _labels(sheet)["https://kitco.com/s"] == "y"


def test_fetch_preview_reads_a_page_and_reports_a_refusal():
    from http.server import BaseHTTPRequestHandler

    class Site(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/page":
                body = "<title>Käse</title><p>Pleurotus djamor mag es warm, über zwanzig Grad.</p>".encode("latin-1")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=iso-8859-1")
            elif self.path == "/pdf":
                body = b"%PDF-1.4"
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
            else:
                body = b"no"
                self.send_response(403)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert U.fetch_preview(base + "/page") == {
            "title": "Käse", "text": "Pleurotus djamor mag es warm, über zwanzig Grad."}
        assert "403" in U.fetch_preview(base + "/blocked")["error"]
        assert "application/pdf" in U.fetch_preview(base + "/pdf")["error"]
    finally:
        httpd.shutdown()
        httpd.server_close()
