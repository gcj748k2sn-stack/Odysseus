#!/usr/bin/env python3
"""Offline replay: would a relevance filter have kept the junk out of web results?

Why: web_search hands the model whatever the search engines return, re-ordered
by services/search/ranking.py — a word-match + domain + recency formula that
never drops anything. Recorded runs show singer pages for a mushroom query and
recipe/health pages for cultivation queries (notes: "Web search derails on
ambiguous common nouns"). Before building a filter into Odysseus, this script
measures candidate scorers against what web_search actually returned on this
machine, with no live change.

USAGE (from the repo root; standard library only, except `run --scorer rerank`
and `pages`, which need fastembed — already in Odysseus's requirements.txt):

  ./venv/bin/python scripts/bench_web_filter.py extract
  ./venv/bin/python scripts/bench_web_filter.py label --dir data/bench/web_filter/<run>
  ./venv/bin/python scripts/bench_web_filter.py run   --dir data/bench/web_filter/<run>
  ./venv/bin/python scripts/bench_web_filter.py pages --dir data/bench/web_filter/<run>

extract  Copies data/app.db (hash, copy, hash again; read-only open of the copy)
         and writes corpus.jsonl: one row per recorded web_search (query, the
         user message that led to it, every result with title/url/snippet in
         the order the model saw them) and one per web_fetch.
label    Writes/updates data/bench/web_filter/labels.csv — one row per (query,
         url). Fill the `label` column with y (relevant) or n (junk). Labels
         survive re-extraction; they are keyed on query + url, not on run ids.
run      Scores every result with each scorer, applies a keep/drop threshold at
         several cut points, and writes report.md: junk dropped, relevant
         dropped (the cost), searches where the fail-open kicked in, and junk
         left in the fetched top 5. Without labels it falls back to SEED_RULES
         (a handful of known-bad cases from notes/) and says so.
pages    Splits recorded web_fetch pages into paragraphs, scores each against
         the user's message, and writes pages.md showing what a budgeted
         paragraph filter would keep and drop. For reading, not for a score.

WHAT THE CORPUS CAN AND CANNOT SEE
  * Agent turns only: chat-mode turns store web_sources (title/url/engine) but
    no snippet, so they are counted and skipped.
  * Snippets are cut at 200 chars by the writer (services/search/core.py), and
    the stored tool output is cut at MAX_OUTPUT_CHARS (10,000); a summary cut
    mid-result loses that result.
  * The user message is the last role='user' row in the same session at or
    before the assistant row — app.db timestamps, naive UTC.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import statistics
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO / "data" / "app.db"
OUT_ROOT = REPO / "data" / "bench" / "web_filter"
LABELS_FILE = OUT_ROOT / "labels.csv"
DOMAINS_FILE = OUT_ROOT / "domains.json"
# Same cache Odysseus uses for its own fastembed models (src/constants.py).
FASTEMBED_CACHE = os.getenv("FASTEMBED_CACHE_PATH") or str(REPO / "data" / "fastembed_cache")

DEFAULT_RERANKER = "Xenova/ms-marco-MiniLM-L-6-v2"   # 80 MB, English
MULTILINGUAL_RERANKER = "jinaai/jina-reranker-v2-base-multilingual"  # 1.1 GB, de/en
FETCHED_TOP_N = 5        # comprehensive_web_search fetches the top max_pages (default 5)
MIN_KEEP = 3             # fail-open: never hand the model fewer results than this

# Known-bad results recorded in notes/items/14-…: (query pattern, result pattern).
# A proxy for labels, used only when labels.csv has none — not ground truth.
SEED_RULES = [
    (r"pink\s+oyster|pleurotus", r"pink \(singer\)|victoria.?s secret|/wiki/pink_\(singer\)"),
    # Mushroom queries: the singer, the lingerie brand, London's Oyster card and
    # a hotel-review site share words with them (seen in the 2026-10-12 replay).
    (r"mushroom|pleurotus|oyster.*(grow|cultivat|fruit)|mycel|fung",
     r"victoriassecret\.com|oyster\.tfl\.gov\.uk|//(www\.)?oyster\.com/|/wiki/pink_\(singer\)"),
    (r"cultivat|growing|fruiting|coloni[sz]ation|substrate|spawn",
     r"allrecipes\.com|tasteofhome\.com|webmd\.com|healthline\.com"),
]

STOPWORDS = set("""
a an and are as at be by for from how in is it of on or that the this to was what when where which who why with
best guide vs versus about into your you can do does
der die das und oder ist ein eine einen einem einer für mit von zu im in am an auf aus bei wie was wo wer
""".split())

_WORD_RE = re.compile(r"\w+", re.UNICODE)


# ---------------------------------------------------------------- database ---

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def snapshot_db(src, dest_dir):
    """Copy app.db and prove the copy is consistent: hash, copy, hash again.

    Never opens the source. Raises if it is missing (sqlite3.connect would
    silently create it) or if it changed while being copied.
    """
    src = Path(src)
    if not src.is_file():
        raise SystemExit(f"no database at {src}")
    before = sha256_file(src)
    dest = Path(dest_dir) / "app.db"
    shutil.copy2(src, dest)
    after = sha256_file(src)
    copied = sha256_file(dest)
    if not (before == after == copied):
        raise SystemExit(
            f"{src} changed while it was copied (Odysseus wrote to it). "
            "Retry when no chat is running, or stop Odysseus first."
        )
    return dest, before


def open_readonly(path):
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"no database at {path}")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


# ------------------------------------------------------------------ parsing ---

_SUMMARY_HEADER = "SEARCH RESULTS SUMMARY:"
_RESULT_RE = re.compile(r"^\[(\d+)\] (.*)$")


def parse_search_output(text):
    """Read the result list out of a stored web_search tool output.

    The writer is comprehensive_web_search in services/search/core.py:
        [i] title / '    URL: …' / '    Snippet: <=200 chars…' / '    Age: …'
    A result whose URL line was cut off by output truncation is dropped.
    Returns (query or None, [{rank, title, url, snippet, age}]).
    """
    if not text:
        return None, []
    query = None
    m = re.search(r"^Query: (.*)$", text, re.MULTILINE)
    if m:
        query = m.group(1).strip()
    start = text.find(_SUMMARY_HEADER)
    if start < 0:
        return query, []
    body = text[start + len(_SUMMARY_HEADER):]
    for stop in ("\nFETCHED PAGE CONTENT:", "\n" + "=" * 70):
        idx = body.find(stop)
        if idx >= 0:
            body = body[:idx]
    results, cur = [], None
    for line in body.splitlines():
        hit = _RESULT_RE.match(line)
        if hit:
            if cur and cur.get("url"):
                results.append(cur)
            cur = {"rank": int(hit.group(1)), "title": hit.group(2).strip(),
                   "url": "", "snippet": "", "age": ""}
            continue
        if cur is None:
            continue
        s = line.strip()
        if s.startswith("URL: "):
            cur["url"] = s[5:].strip()
        elif s.startswith("Snippet: "):
            snip = s[9:]
            cur["snippet"] = snip[:-3] if snip.endswith("...") else snip
        elif s.startswith("Age: "):
            cur["age"] = s[5:].strip()
    if cur and cur.get("url"):
        results.append(cur)
    return query, results


def parse_command_query(command):
    command = (command or "").strip()
    if command.startswith("{"):
        try:
            obj = json.loads(command)
            if isinstance(obj, dict):
                return str(obj.get("query") or obj.get("url") or "").strip()
        except json.JSONDecodeError:
            pass
    return command.split("\n")[0].strip()


def page_text_from_fetch_output(text):
    """Strip web_fetch's notices and '# title / Source:' header; return (title, url, body)."""
    title, url = "", ""
    lines = (text or "").split("\n")
    i = 0
    while i < len(lines) and lines[i].startswith("["):      # partial/cache notices
        i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].startswith("# "):
        title = lines[i][2:].strip()
        i += 1
    if i < len(lines) and lines[i].startswith("Source: "):
        url = lines[i][8:].strip()
        i += 1
    body = "\n".join(lines[i:]).strip()
    body = re.sub(r"\n\n\[\.\.\.truncated\]$", "", body)
    return title, url, body


def extract_corpus(con):
    """One row per web_search / web_fetch tool event in agent turns."""
    rows = con.execute(
        "select id, session_id, timestamp, metadata from chat_messages "
        "where role='assistant' and metadata like '%web_%' order by timestamp"
    ).fetchall()
    searches, fetches = [], []
    stats = Counter()
    for msg_id, session_id, ts, meta_raw in rows:
        try:
            meta = json.loads(meta_raw or "{}")
        except json.JSONDecodeError:
            stats["metadata_unreadable"] += 1
            continue
        events = meta.get("tool_events") or []
        if not events and meta.get("web_sources"):
            stats["chat_mode_rows_skipped"] += 1
            continue
        user = con.execute(
            "select content from chat_messages where session_id=? and role='user' "
            "and timestamp<=? order by timestamp desc limit 1",
            (session_id, ts),
        ).fetchone()
        user_msg = (user[0] if user else "") or ""
        last_query = ""
        for n, ev in enumerate(events):
            tool = ev.get("tool")
            if tool == "web_search":
                q_out, results = parse_search_output(ev.get("output") or "")
                query = q_out or parse_command_query(ev.get("command"))
                last_query = query
                if not results:
                    stats["searches_without_results"] += 1
                    continue
                searches.append({
                    "kind": "search", "id": f"{msg_id}:{n}", "session_id": session_id,
                    "timestamp_utc": ts, "query": query, "user_message": user_msg,
                    "exit_code": ev.get("exit_code"), "results": results,
                })
            elif tool == "web_fetch":
                title, url, body = page_text_from_fetch_output(ev.get("output") or "")
                fetches.append({
                    "kind": "fetch", "id": f"{msg_id}:{n}", "session_id": session_id,
                    "timestamp_utc": ts, "url": url or parse_command_query(ev.get("command")),
                    "title": title, "exit_code": ev.get("exit_code"),
                    "cached": bool(ev.get("cached")), "user_message": user_msg,
                    "query": last_query, "text": body if ev.get("exit_code") == 0 else "",
                    "error": "" if ev.get("exit_code") == 0 else (ev.get("output") or "")[:300],
                })
    return searches, fetches, stats


# ------------------------------------------------------------------ scoring ---

def domain_of(url):
    try:
        net = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return net[4:] if net.startswith("www.") else net


def _stem(word):
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def distinctive_terms(query):
    return [_stem(w) for w in (t.lower() for t in _WORD_RE.findall(query or ""))
            if len(w) > 2 and w not in STOPWORDS and not w.isdigit()]


def lexical_score(query, result):
    """Share of the query's distinctive terms present in title, snippet or URL."""
    terms = distinctive_terms(query)
    if not terms:
        return 1.0
    hay = " ".join((result.get("title", ""), result.get("snippet", ""),
                    re.sub(r"[/\-_.]", " ", result.get("url", ""))))
    words = {_stem(w.lower()) for w in _WORD_RE.findall(hay)}
    return sum(1 for t in terms if t in words) / len(terms)


def load_domain_priors(path=DOMAINS_FILE):
    """{"webmd.com": -0.3, "kitco.com": 0.2} — added to the score; optional file."""
    path = Path(path)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k.lower().removeprefix("www."): float(v) for k, v in data.items()}


def domain_prior(url, priors):
    """Longest matching suffix on a label boundary: 'webmd.com' covers
    'm.webmd.com' but not 'notwebmd.com'."""
    dom = domain_of(url)
    best, best_len = 0.0, -1
    for key, val in priors.items():
        if (dom == key or dom.endswith("." + key)) and len(key) > best_len:
            best, best_len = val, len(key)
    return best


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


class Reranker:
    """fastembed cross-encoder: reads (query, passage) together, outputs a logit."""

    def __init__(self, model_name=DEFAULT_RERANKER, cache_dir=FASTEMBED_CACHE, model=None):
        self.model_name = model_name
        if model is None:
            try:
                from fastembed.rerank.cross_encoder import TextCrossEncoder
            except ImportError as e:
                raise SystemExit(f"fastembed with rerank support is needed for this scorer: {e}")
            os.makedirs(cache_dir, exist_ok=True)
            model = TextCrossEncoder(model_name=model_name, cache_dir=cache_dir)
        self._model = model

    def score(self, query, passages):
        if not passages:
            return []
        logits = list(self._model.rerank(query, list(passages)))
        if len(logits) != len(passages):
            raise RuntimeError(f"reranker returned {len(logits)} scores for {len(passages)} passages")
        return [_sigmoid(float(x)) for x in logits]


def result_passage(result):
    return f"{result.get('title', '')}. {result.get('snippet', '')} ({domain_of(result.get('url', ''))})"


def scoring_target(search, against):
    user = (search.get("user_message") or "").strip()[:600]
    if against == "query":
        return search["query"]
    if against == "user":
        return user or search["query"]
    return f"{user}\nSearch: {search['query']}" if user else search["query"]


def score_corpus(searches, scorers, priors, reranker=None):
    """Return {scorer_name: {(search_id, url): score}}; priors are added to every scorer."""
    out = {}
    for name in scorers:
        kind, _, against = name.partition(":")
        scores = {}
        for s in searches:
            target = scoring_target(s, against or "query")
            if kind == "lexical":
                vals = [lexical_score(target, r) for r in s["results"]]
            elif kind == "rerank":
                if reranker is None:
                    raise SystemExit("rerank scorer requested without a reranker")
                vals = reranker.score(target, [result_passage(r) for r in s["results"]])
            else:
                raise SystemExit(f"unknown scorer {name}")
            for r, v in zip(s["results"], vals):
                scores[(s["id"], r["url"])] = v + domain_prior(r["url"], priors)
        out[name] = scores
    return out


def decide(scored, threshold, min_keep=MIN_KEEP):
    """Keep results scoring >= threshold; if that leaves fewer than min_keep,
    keep the min_keep best instead (fail-open: a filter must never be the
    reason the model gets nothing). `scored` is [(key, score)] in display order.
    Returns (kept keys in display order, fell_back)."""
    kept = [k for k, v in scored if v >= threshold]
    if len(kept) >= min(min_keep, len(scored)):
        return kept, False
    best = sorted(scored, key=lambda kv: kv[1], reverse=True)[:min_keep]
    best_keys = {k for k, _ in best}
    return [k for k, _ in scored if k in best_keys], True


# ------------------------------------------------------------------- labels ---

def label_key(query, url):
    return (" ".join((query or "").lower().split()), url.strip())


_LABEL_VALUES = {"y": "y", "yes": "y", "j": "y", "ja": "y", "n": "n", "no": "n", "nein": "n"}


def read_label_rows(path):
    """Rows of the label sheet as dicts with lower-case column names.

    The sheet is edited by hand, so it may come back from Numbers or Excel with
    a BOM, `;` or tab separators (German locale) or Windows-1252 encoding.
    Refuses — rather than guesses — when the needed columns are missing, so a
    sheet it cannot read is never rewritten and its labels never lost."""
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    header = text.split("\n", 1)[0]
    delim = max((",", ";", "\t"), key=header.count)
    reader = csv.DictReader(text.splitlines(), delimiter=delim)
    reader.fieldnames = [(n or "").strip().lower() for n in (reader.fieldnames or [])]
    missing = {"label", "query", "url"} - set(reader.fieldnames)
    if missing:
        raise SystemExit(
            f"{path}: cannot read the label sheet — missing column(s) {sorted(missing)}; "
            f"header read as {reader.fieldnames[:6]} with separator {delim!r}. Nothing was changed."
        )
    return [row for row in reader if (row.get("url") or "").strip()]


def load_labels(path=LABELS_FILE):
    labels = {}
    path = Path(path)
    if not path.is_file():
        return labels
    for row in read_label_rows(path):
        val = _LABEL_VALUES.get((row.get("label") or "").strip().lower())
        if val:
            labels[label_key(row["query"], row["url"])] = val
    return labels


def seed_label(query, result):
    text = f"{result.get('title', '')} {result.get('url', '')}".lower()
    for q_pat, r_pat in SEED_RULES:
        if re.search(q_pat, query or "", re.I) and re.search(r_pat, text, re.I):
            return "n"
    return None


def read_scores(path, scorer):
    """{label_key: score} for one scorer from a run's scores.jsonl."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if scorer in row:
                out[label_key(row["query"], row["url"])] = row[scorer]
    return out


def write_label_sheet(searches, path=LABELS_FILE, scores=None):
    """Add a row for every (query, url) not yet in the sheet; keep existing labels.

    With `scores` ({label_key: score}), every row's `score` column is set, so
    the sheet can be sorted to label the drop candidates first."""
    path = Path(path)
    existing, rows = set(), []
    if path.is_file():
        for row in read_label_rows(path):
            rows.append(row)
            existing.add(label_key(row["query"], row["url"]))
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    added = 0
    for s in searches:
        for r in s["results"]:
            key = label_key(s["query"], r["url"])
            if key in existing:
                continue
            existing.add(key)
            rows.append({
                "label": "", "hint": "seed:n" if seed_label(s["query"], r) else "",
                "query": s["query"], "rank": r["rank"], "domain": domain_of(r["url"]),
                "title": r["title"], "snippet": r["snippet"][:200], "url": r["url"],
                "user_message": (s.get("user_message") or "")[:200].replace("\n", " "),
            })
            added += 1
    for row in rows:
        # Recomputed every time, so a changed SEED_RULES reaches existing rows.
        row["hint"] = "seed:n" if seed_label(row["query"], row) else ""
        if scores is not None:
            sc = scores.get(label_key(row["query"], row["url"]))
            row["score"] = "" if sc is None else f"{sc:.6f}"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["label", "score", "hint", "query", "rank", "domain", "title", "snippet", "url", "user_message"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return added, len(rows)


def labels_for(searches, labels):
    """{(search_id, url): 'y'|'n'} from labels.csv, else from SEED_RULES."""
    out, source = {}, "labels.csv"
    for s in searches:
        for r in s["results"]:
            lab = labels.get(label_key(s["query"], r["url"]))
            if lab:
                out[(s["id"], r["url"])] = lab
    if not out:
        source = "SEED_RULES proxy (no labels in labels.csv) — known junk only, no relevant labels"
        for s in searches:
            for r in s["results"]:
                if seed_label(s["query"], r):
                    out[(s["id"], r["url"])] = "n"
    return out, source


# --------------------------------------------------------------- evaluation ---

def evaluate(searches, scores, truth, threshold, min_keep=MIN_KEEP, top_n=FETCHED_TOP_N):
    row = Counter()
    good_dropped = []
    for s in searches:
        scored = [((s["id"], r["url"]), scores[(s["id"], r["url"])]) for r in s["results"]]
        kept, fell_back = decide(scored, threshold, min_keep)
        kept = set(kept)
        row["fell_back"] += fell_back
        reordered = sorted(scored, key=lambda kv: kv[1], reverse=True)[:top_n]
        row["junk_top_after"] += sum(1 for k, _ in reordered if truth.get(k) == "n" and k in kept)
        for key, _ in scored:
            lab = truth.get(key)
            dropped = key not in kept
            row["results"] += 1
            row["dropped"] += dropped
            if lab == "n":
                row["junk"] += 1
                row["junk_dropped"] += dropped
            elif lab == "y":
                row["good"] += 1
                row["good_dropped"] += dropped
                if dropped:
                    good_dropped.append((s["query"], key[1], scores[key]))
            else:
                row["unlabeled_dropped"] += dropped
    return row, good_dropped


def junk_in_current_top(searches, truth, top_n=FETCHED_TOP_N):
    return sum(1 for s in searches for r in s["results"][:top_n] if truth.get((s["id"], r["url"])) == "n")


def threshold_grid(scores, shares=(0.1, 0.2, 0.3, 0.4, 0.5)):
    """Cut points that would drop roughly 10 %, 20 % … of all results.

    Not rounded: reranker scores pile up near 0 after the sigmoid, and
    rounding merged distinct cut points. A cut point equal to the lowest
    score would drop nothing, so it moves up to the next distinct value."""
    vals = sorted(scores.values())
    if not vals:
        return []
    distinct = sorted(set(vals))
    out = set()
    for share in shares:
        thr = vals[min(len(vals) - 1, int(share * len(vals)))]
        if thr == distinct[0] and len(distinct) > 1:
            thr = distinct[1]
        out.add(thr)
    return sorted(out)


# ------------------------------------------------------------------- pages ---

def chunk_text(text, target=600, hard_max=1200):
    """Paragraphs merged up to ~target chars; a single long paragraph is split."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(p) > hard_max and cur:
            chunks.append(cur)
            cur = ""
        while len(p) > hard_max:
            chunks.append(p[:hard_max])
            p = p[hard_max:]
        if cur and len(cur) + len(p) + 2 > target:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks


def keep_within_budget(chunks, scores, budget):
    """Best-scoring chunks until the char budget is used; returned in page order.
    The best chunk is always kept, even if it alone exceeds the budget."""
    order = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    kept, used = set(), 0
    for i in order:
        if kept and used + len(chunks[i]) > budget:
            continue
        kept.add(i)
        used += len(chunks[i])
    return sorted(kept)


# --------------------------------------------------------------------- CLI ---

def read_corpus(run_dir):
    path = Path(run_dir) / "corpus.jsonl"
    if not path.is_file():
        raise SystemExit(f"{path} not found — run `extract` first")
    searches, fetches = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            (searches if row["kind"] == "search" else fetches).append(row)
    return searches, fetches


def cmd_extract(args):
    run_dir = Path(args.out) if args.out else OUT_ROOT / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    if Path(str(args.db) + "-journal").exists():
        print("note: app.db-journal exists — a write may be in progress; the hash check will tell.")
    with tempfile.TemporaryDirectory() as tmp:
        copy, digest = snapshot_db(args.db, tmp)
        con = open_readonly(copy)
        try:
            searches, fetches, stats = extract_corpus(con)
        finally:
            con.close()
    with open(run_dir / "corpus.jsonl", "w", encoding="utf-8") as f:
        for row in searches + fetches:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    meta = {"db": str(args.db), "db_sha256": digest, "extracted_at_local": dt.datetime.now().isoformat(),
            "searches": len(searches), "results": sum(len(s["results"]) for s in searches),
            "fetches": len(fetches), **stats}
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    print(f"\ncorpus: {run_dir / 'corpus.jsonl'}")


def cmd_label(args):
    searches, _ = read_corpus(args.dir)
    scores = None
    if args.scores_from:
        scores = read_scores(Path(args.dir) / "scores.jsonl", args.scores_from)
        if not scores:
            raise SystemExit(f"no '{args.scores_from}' scores in {args.dir}/scores.jsonl — run `run` first")
    added, total = write_label_sheet(searches, args.labels, scores)
    print(f"{args.labels}: {added} new rows, {total} total. Fill the label column with y or n.")
    if scores:
        print(f"score column = {args.scores_from}; sort ascending to label the drop candidates first.")


def cmd_run(args):
    searches, fetches = read_corpus(args.dir)
    priors = load_domain_priors(args.domains)
    scorers = [s.strip() for s in args.scorers.split(",") if s.strip()]
    reranker = Reranker(args.model) if any(s.startswith("rerank") for s in scorers) else None
    all_scores = score_corpus(searches, scorers, priors, reranker)
    truth, source = labels_for(searches, load_labels(args.labels))

    out = Path(args.dir)
    with open(out / "scores.jsonl", "w", encoding="utf-8") as f:
        for s in searches:
            for r in s["results"]:
                key = (s["id"], r["url"])
                f.write(json.dumps({"search": s["id"], "query": s["query"], "rank": r["rank"],
                                    "url": r["url"], "title": r["title"], "label": truth.get(key),
                                    **{n: round(sc[key], 4) for n, sc in all_scores.items()}},
                                   ensure_ascii=False) + "\n")

    n_res = sum(len(s["results"]) for s in searches)
    lines = [
        "# Web filter replay", "",
        f"- Corpus: `{out / 'corpus.jsonl'}` — {len(searches)} searches, {n_res} results, "
        f"{len(fetches)} fetches; timestamps {min((s['timestamp_utc'] for s in searches), default='-')} "
        f"→ {max((s['timestamp_utc'] for s in searches), default='-')} (UTC).",
        f"- Labels: {source}. y={sum(v == 'y' for v in truth.values())}, "
        f"n={sum(v == 'n' for v in truth.values())}, unlabeled={n_res - len(truth)}.",
        f"- Domain priors: {len(priors)} from `{args.domains}`." if priors else "- Domain priors: none.",
        f"- Reranker: `{args.model}`." if reranker else "- Reranker: not used.",
        f"- Fail-open: at least {args.min_keep} results kept per search. "
        f"\"top {FETCHED_TOP_N}\" = the pages comprehensive_web_search fetches.",
        "",
        f"**Today's order:** {junk_in_current_top(searches, truth)} junk results in the fetched top {FETCHED_TOP_N}.",
        "",
    ]
    for name, scores in all_scores.items():
        lines += [f"## {name}", "",
                  "| threshold | junk dropped | relevant dropped | unlabeled dropped | fail-open searches | junk in top 5 after re-sort |",
                  "|---:|---:|---:|---:|---:|---:|"]
        best = None
        for thr in threshold_grid(scores):
            row, good_dropped = evaluate(searches, scores, truth, thr, args.min_keep)
            lines.append(f"| {thr:.3g} | {row['junk_dropped']}/{row['junk']} | {row['good_dropped']}/{row['good']} "
                         f"| {row['unlabeled_dropped']} | {row['fell_back']}/{len(searches)} | {row['junk_top_after']} |")
            if row["good_dropped"] == 0 and (best is None or row["junk_dropped"] > best[1]["junk_dropped"]):
                best = (thr, row, good_dropped)
        lines.append("")
        thr_hi = max(threshold_grid(scores), default=None)
        if thr_hi is not None:
            _, gd = evaluate(searches, scores, truth, thr_hi, args.min_keep)
            if gd:
                lines += [f"Relevant results dropped at {thr_hi:.3g} (the cost side — read these):", ""]
                lines += [f"- {sc:.3f} · {q[:70]} → {u}" for q, u, sc in gd[:20]]
                lines.append("")
        if best and any(v == "y" for v in truth.values()):
            lines += [f"Highest threshold in the grid that drops no labelled-relevant result: **{best[0]:.3g}** "
                      f"({best[1]['junk_dropped']}/{best[1]['junk']} junk dropped).", ""]

    # Per-domain view: the raw material for a domains.json
    seen, rank_sum, labs, fails, fetch_n = Counter(), Counter(), defaultdict(Counter), Counter(), Counter()
    for s in searches:
        for r in s["results"]:
            d = domain_of(r["url"])
            seen[d] += 1
            rank_sum[d] += r["rank"]
            lab = truth.get((s["id"], r["url"]))
            if lab:
                labs[d][lab] += 1
    for f_ in fetches:
        d = domain_of(f_["url"] if "://" in f_["url"] else "https://" + f_["url"])
        fetch_n[d] += 1
        fails[d] += f_["exit_code"] != 0
    lines += ["## Domains (top 40 by appearances)", "",
              "| domain | seen | mean rank | labelled y | labelled n | fetched | fetch failed | prior |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for d, n in seen.most_common(40):
        lines.append(f"| {d} | {n} | {rank_sum[d] / n:.1f} | {labs[d]['y']} | {labs[d]['n']} "
                     f"| {fetch_n[d]} | {fails[d]} | {domain_prior('https://' + d, priors):+.2f} |")
    with open(out / "domains_seen.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain", "seen", "mean_rank", "label_y", "label_n", "fetched", "fetch_failed"])
        for d in sorted(set(seen) | set(fetch_n), key=lambda x: (-seen[x], x)):
            w.writerow([d, seen[d], round(rank_sum[d] / seen[d], 1) if seen[d] else "",
                        labs[d]["y"], labs[d]["n"], fetch_n[d], fails[d]])
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwritten: {out / 'report.md'}, {out / 'scores.jsonl'}, {out / 'domains_seen.csv'}")


def cmd_pages(args):
    _, fetches = read_corpus(args.dir)
    pages = [f for f in fetches if f["exit_code"] == 0 and f["text"]][: args.limit]
    reranker = None if args.lexical else Reranker(args.model)
    scorer_name = "lexical" if args.lexical else f"reranker `{args.model}`"
    lines = ["# Paragraph filter preview", "",
             f"Budget {args.budget} chars per page; {scorer_name}; target = user message + last search query.", ""]
    total_in = total_kept = 0
    for p in pages:
        chunks = chunk_text(p["text"])
        target = (p["user_message"] or "")[:600] + (f"\nSearch: {p['query']}" if p["query"] else "")
        target = target.strip() or p["title"]
        if reranker is None:
            scores = [lexical_score(target, {"title": "", "snippet": c, "url": ""}) for c in chunks]
        else:
            scores = reranker.score(target, chunks)
        kept = set(keep_within_budget(chunks, scores, args.budget))
        size = sum(len(c) for c in chunks)
        kept_size = sum(len(chunks[i]) for i in kept)
        total_in += size
        total_kept += kept_size
        lines += [f"## {p['title'][:90] or p['url']}", f"{p['url']} — {size} → {kept_size} chars", ""]
        for i, (c, sc) in enumerate(zip(chunks, scores)):
            mark = "KEEP" if i in kept else "drop"
            lines.append(f"- `{mark} {sc:.3f}` {c[:160].replace(chr(10), ' ')}…")
        lines.append("")
    lines.insert(3, f"Overall: {total_in} → {total_kept} chars across {len(pages)} pages "
                    f"({(total_kept / total_in * 100 if total_in else 0):.0f} % kept).\n")
    out = Path(args.dir) / "pages.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written: {out}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="copy app.db and write corpus.jsonl")
    e.add_argument("--db", type=Path, default=DEFAULT_DB)
    e.add_argument("--out", help="run directory (default data/bench/web_filter/<timestamp>)")
    lab = sub.add_parser("label", help="create/update the labels sheet")
    lab.add_argument("--dir", required=True)
    lab.add_argument("--labels", type=Path, default=LABELS_FILE)
    lab.add_argument("--scores-from", metavar="SCORER",
                     help="fill a score column from this scorer in <dir>/scores.jsonl, e.g. rerank:query")
    r = sub.add_parser("run", help="score, evaluate, write report.md")
    r.add_argument("--dir", required=True)
    r.add_argument("--labels", type=Path, default=LABELS_FILE)
    r.add_argument("--domains", type=Path, default=DOMAINS_FILE)
    r.add_argument("--scorers", default="lexical:query,rerank:query,rerank:user,rerank:both",
                   help="comma list of lexical|rerank : query|user|both")
    r.add_argument("--model", default=DEFAULT_RERANKER,
                   help=f"fastembed reranker (multilingual: {MULTILINGUAL_RERANKER})")
    r.add_argument("--min-keep", type=int, default=MIN_KEEP)
    p = sub.add_parser("pages", help="preview a paragraph filter on fetched pages")
    p.add_argument("--dir", required=True)
    p.add_argument("--model", default=DEFAULT_RERANKER)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--lexical", action="store_true", help="word matching instead of the reranker (no download)")
    args = ap.parse_args(argv)
    {"extract": cmd_extract, "label": cmd_label, "run": cmd_run, "pages": cmd_pages}[args.cmd](args)


if __name__ == "__main__":
    main()
