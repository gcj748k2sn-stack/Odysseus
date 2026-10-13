"""A local page for labelling web results: one search per screen, y/n per result.

Started by `bench_web_filter.py serve`. Reads and writes the same label sheet
as `label`/`run` (data/bench/web_filter/labels.csv); it never touches
data/web_ratings.jsonl, so a label here never becomes a live rating and the
replay can still grade ratings against these labels.

Searches with unlabelled rows come first, those whose scores sit nearest the
threshold at the top (a label there can change a decision); scores come from
the sheet's `score` column (`label --scores-from …`). Standard library only.
"""
import json
import math
import re
import sys
import threading
import urllib.request
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_web_filter as W  # noqa: E402

PREVIEW_CHARS = 2000
PREVIEW_MAX_BYTES = 1_500_000
PREVIEW_TIMEOUT = 8


class SheetChanged(Exception):
    """labels.csv was changed by something else since the page last read it."""


def _stamp(path):
    st = Path(path).stat()
    return (st.st_mtime_ns, st.st_size)


def _score(row):
    try:
        return float(row.get("score") or "")
    except ValueError:
        return None


def _rank(row):
    try:
        return int(row.get("rank") or "")
    except ValueError:
        return 10 ** 6


class LabelStore:
    """The label sheet in memory. Every change is written back at once; a
    sheet changed on disk meanwhile (e.g. saved from Numbers) is never
    overwritten — the write is refused and the page asks for a reload."""

    def __init__(self, path, threshold=W.LIVE_THRESHOLD):
        self.path = Path(path)
        self.threshold = threshold
        self.lock = threading.Lock()
        self.backed_up = False
        self.reload()

    def reload(self):
        with self.lock:
            self.rows = W.read_label_rows(self.path)
            self.stamp = _stamp(self.path)

    def counts(self):
        done = sum(1 for r in self.rows if W._LABEL_VALUES.get((r.get("label") or "").strip().lower()))
        return {"labelled": done, "total": len(self.rows)}

    def _distance(self, rows):
        """How close the nearest unlabelled score is to the threshold, in log
        space (sigmoid scores pile up near 0). No score: after every scored one."""
        best = math.inf
        for r in rows:
            sc = _score(r)
            if sc is not None and sc > 0 and not (r.get("label") or "").strip():
                best = min(best, abs(math.log(sc / self.threshold)))
        return best

    def searches(self):
        groups, order = {}, []
        for r in self.rows:
            q = W.label_key(r["query"], "")[0]
            if q not in groups:
                groups[q] = []
                order.append(q)
            groups[q].append(r)
        out = []
        for pos, q in enumerate(order):
            rows = sorted(groups[q], key=_rank)
            items = [{
                "id": W.row_id(r["query"], r["url"]),
                "label": W._LABEL_VALUES.get((r.get("label") or "").strip().lower(), ""),
                "score": _score(r), "rank": r.get("rank", ""), "hint": r.get("hint", ""),
                "title": r.get("title", ""), "url": r["url"],
                "domain": r.get("domain") or W.domain_of(r["url"]), "snippet": r.get("snippet", ""),
            } for r in rows]
            open_rows = sum(1 for i in items if not i["label"])
            out.append({"query": rows[0]["query"], "rows": items, "open": open_rows,
                        "_key": (open_rows == 0, self._distance(rows), pos)})
        out.sort(key=lambda s: s.pop("_key"))
        return out

    def set_label(self, rid, value):
        value = (value or "").strip().lower()
        if value not in ("y", "n", ""):
            raise ValueError(f"label must be y, n or empty, not {value!r}")
        with self.lock:
            if _stamp(self.path) != self.stamp:
                raise SheetChanged(f"{self.path} changed on disk since it was loaded")
            hits = [r for r in self.rows if W.row_id(r["query"], r["url"]) == rid]
            if not hits:
                raise KeyError(rid)
            for r in hits:
                r["label"] = value
            if not self.backed_up:
                self.path.with_name(self.path.name + ".bak").write_bytes(self.path.read_bytes())
                self.backed_up = True
            W.save_label_rows(self.path, self.rows)
            self.stamp = _stamp(self.path)

    def has_url(self, url):
        return any(r["url"].strip() == url for r in self.rows)


# ------------------------------------------------------------------ preview ---

class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "svg", "form", "aside", "template"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)


def html_to_text(markup, limit=PREVIEW_CHARS):
    p = _TextExtractor()
    try:
        p.feed(markup)
    except Exception:  # malformed markup: keep what was read
        pass
    lines = (" ".join(line.split()) for line in "".join(p.parts).split("\n"))
    text = "\n".join(line for line in lines if len(line) > 30)
    return " ".join(p.title.split()), text[:limit]


def fetch_preview(url, timeout=PREVIEW_TIMEOUT):
    if urlparse(url).scheme not in ("http", "https"):
        return {"error": "not an http(s) URL"}
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "en,de;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype:
                return {"error": f"not a web page ({ctype or 'no content type'})"}
            raw = resp.read(PREVIEW_MAX_BYTES)
            charset = resp.headers.get_content_charset() or "utf-8"
    except Exception as exc:  # 403/429/timeouts are worth seeing, not hiding
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}
    title, text = html_to_text(raw.decode(charset, errors="replace"))
    return {"title": title, "text": text or "(no readable text — page may need JavaScript)"}


# ------------------------------------------------------------------- server ---

def make_handler(store, fetch=fetch_preview):
    cache = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quiet; the page shows errors itself
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif u.path == "/api/searches":
                if (parse_qs(u.query).get("reload") or [""])[0]:
                    store.reload()
                self._send(200, {"searches": store.searches(), "counts": store.counts(),
                                 "threshold": store.threshold, "sheet": str(store.path)})
            elif u.path == "/api/preview":
                url = (parse_qs(u.query).get("url") or [""])[0]
                if not store.has_url(url):  # only URLs from the sheet, never arbitrary ones
                    self._send(404, {"error": "URL not in the label sheet"})
                    return
                if url not in cache:
                    cache[url] = fetch(url)
                self._send(200, cache[url])
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if urlparse(self.path).path != "/api/label":
                self._send(404, {"error": "not found"})
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                store.set_label(str(body.get("id", "")), body.get("label", ""))
            except SheetChanged as exc:
                self._send(409, {"error": f"{exc}. Reload the page (r) to pick up the other changes."})
            except KeyError:
                self._send(404, {"error": "unknown row id"})
            except (ValueError, TypeError) as exc:
                self._send(400, {"error": str(exc)})
            else:
                self._send(200, {"ok": True, "counts": store.counts()})

    return Handler


def serve(labels, host="127.0.0.1", port=8765, threshold=W.LIVE_THRESHOLD):
    labels = Path(labels)
    if not labels.is_file():
        raise SystemExit(f"{labels} not found — run `extract` and `label` first")
    store = LabelStore(labels, threshold)
    httpd = ThreadingHTTPServer((host, port), make_handler(store))
    c = store.counts()
    print(f"Labelling {labels}: {c['labelled']} of {c['total']} rows labelled.")
    print(f"Open http://{host}:{port}/  — Ctrl+C to stop. Every click is saved at once.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Label web results</title>
<style>
:root{--bg:#fafaf9;--fg:#1c1917;--mut:#78716c;--line:#e7e5e4;--card:#fff;--y:#15803d;--yb:#dcfce7;--n:#b91c1c;--nb:#fee2e2;--cur:#2563eb}
@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--mut:#a8a29e;--line:#44403c;--card:#292524;--y:#4ade80;--yb:#14532d;--n:#f87171;--nb:#7f1d1d;--cur:#60a5fa}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;z-index:2}
.bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-size:13px;color:var(--mut)}
.q{font-size:20px;font-weight:600;color:var(--fg);margin:6px 0 2px}
main{max-width:980px;margin:0 auto;padding:12px 16px 80px}
.row{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0;display:grid;grid-template-columns:auto 1fr;gap:4px 12px}
.row.cur{outline:2px solid var(--cur)}.row.y{border-left:6px solid var(--y)}.row.n{border-left:6px solid var(--n)}
.btns{display:flex;flex-direction:column;gap:4px}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:3px 10px;cursor:pointer}
.row.y .by{background:var(--yb);color:var(--y);font-weight:700}.row.n .bn{background:var(--nb);color:var(--n);font-weight:700}
.t{font-weight:600}.t a{color:inherit}.meta{font-size:12px;color:var(--mut)}.low{color:var(--n)}
.snip{font-size:14px}.pv{grid-column:2;font-size:13px;white-space:pre-wrap;border-top:1px dashed var(--line);padding-top:6px;max-height:260px;overflow:auto;color:var(--mut)}
.err{color:var(--n)}kbd{border:1px solid var(--line);border-radius:4px;padding:0 4px;font-size:12px}
#msg{min-height:1.2em}
</style></head><body>
<header>
 <div class="bar"><span id="count"></span><span id="pos"></span><span id="msg" class="err"></span>
  <span style="margin-left:auto"><kbd>y</kbd>/<kbd>n</kbd> label · <kbd>u</kbd> clear · <kbd>j</kbd>/<kbd>k</kbd> row · <kbd>p</kbd> preview · <kbd>o</kbd> open · <kbd>←</kbd>/<kbd>→</kbd> search · <kbd>r</kbd> reload</span></div>
 <div class="q" id="query"></div>
 <div class="bar"><button id="prev">← previous</button><button id="next">next →</button><span id="open"></span></div>
</header>
<main id="rows"></main>
<script>
let S=[],TH=0.035,si=0,ri=0;const pv={};
const $=id=>document.getElementById(id);
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c])}
async function load(reload){
  const r=await fetch("/api/searches"+(reload?"?reload=1":""));const d=await r.json();
  S=d.searches;TH=d.threshold;$("msg").textContent="";counts(d.counts);show(0);
}
function counts(c){$("count").textContent=`${c.labelled} / ${c.total} labelled`}
function render(){
  const s=S[si];if(!s){$("query").textContent="Nothing to label.";$("rows").innerHTML="";return}
  $("query").textContent=s.query;
  $("pos").textContent=`search ${si+1} of ${S.length}`;
  $("open").textContent=`${s.rows.filter(r=>!r.label).length} open here`;
  $("rows").innerHTML=s.rows.map((r,i)=>{
    const sc=r.score==null?"":`score <span class="${r.score<TH?"low":""}">${r.score.toFixed(3)}</span> · `;
    const p=pv[r.url];
    const pvh=p===undefined?"":`<div class="pv">${p===null?"loading…":p.error?`<span class="err">${esc(p.error)}</span>`:(p.title?`<b>${esc(p.title)}</b>\n`:"")+esc(p.text)}</div>`;
    return `<div class="row ${r.label} ${i===ri?"cur":""}" data-i="${i}">
     <div class="btns"><button class="by" data-l="y">y</button><button class="bn" data-l="n">n</button></div>
     <div><div class="t"><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title||r.url)}</a></div>
     <div class="meta">${sc}#${esc(r.rank)} · ${esc(r.domain)}${r.hint?" · "+esc(r.hint):""} · <a href="#" data-p="1">preview</a></div>
     <div class="snip">${esc(r.snippet)}</div></div>${pvh}</div>`}).join("");
  const cur=document.querySelector(".row.cur");if(cur)cur.scrollIntoView({block:"nearest"});
}
async function label(v){
  const s=S[si],r=s&&s.rows[ri];if(!r)return;
  const old=r.label;r.label=v;render();
  const res=await fetch("/api/label",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:r.id,label:v})});
  const d=await res.json();
  if(!res.ok){r.label=old;render();$("msg").textContent=d.error;return}
  $("msg").textContent="";counts(d.counts);
  if(!v)return;
  const nextOpen=s.rows.findIndex((x,i)=>i>ri&&!x.label);
  if(nextOpen>=0)ri=nextOpen;else if(s.rows.every(x=>x.label)){go(1);return}else ri=Math.min(ri+1,s.rows.length-1);
  render();
}
function go(d){show(si+d)}
function show(i){si=Math.max(0,Math.min(S.length-1,i));const s=S[si];ri=s?Math.max(0,s.rows.findIndex(x=>!x.label)):0;render();window.scrollTo(0,0)}
async function preview(i){
  const r=S[si]&&S[si].rows[i];if(!r)return;
  if(pv[r.url]!==undefined){delete pv[r.url];render();return}
  pv[r.url]=null;render();
  try{const res=await fetch("/api/preview?url="+encodeURIComponent(r.url));pv[r.url]=await res.json()}
  catch(e){pv[r.url]={error:String(e)}}
  render();
}
$("rows").addEventListener("click",e=>{
  const row=e.target.closest(".row");if(!row)return;ri=+row.dataset.i;
  if(e.target.dataset.l){label(S[si].rows[ri].label===e.target.dataset.l?"":e.target.dataset.l)}
  else if(e.target.dataset.p){e.preventDefault();preview(ri)}
  else if(e.target.tagName!=="A")render();
});
$("prev").onclick=()=>go(-1);$("next").onclick=()=>go(1);
document.addEventListener("keydown",e=>{
  if(e.metaKey||e.ctrlKey||e.altKey)return;const s=S[si];
  const k=e.key;
  if(k==="y"||k==="n")label(k);else if(k==="u")label("");
  else if(k==="j"||k==="ArrowDown"){if(s){ri=Math.min(ri+1,s.rows.length-1);render()}e.preventDefault()}
  else if(k==="k"||k==="ArrowUp"){ri=Math.max(ri-1,0);render();e.preventDefault()}
  else if(k==="ArrowRight"||k==="Enter")go(1);else if(k==="ArrowLeft")go(-1);
  else if(k==="p")preview(ri);
  else if(k==="o"){const r=s&&s.rows[ri];if(r)window.open(r.url,"_blank","noopener")}
  else if(k==="r")load(true);
});
load(false);
</script></body></html>
"""
