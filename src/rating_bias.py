"""Ratings bias the web relevance filter (fork module).

The ▲/▼ ratings from the sources box (src/web_ratings.py) move a result's
reranker score up or down on later searches in the same research topic, so a
site rated down there is dropped sooner and one rated up is kept sooner.

The bias is added to the reranker's logit, not to the 0-1 score: live scores
sit close to the threshold, so a 0-1 offset would turn every rating into a
hard keep or drop. It is bounded by `strength`, the topic "other" (and no
topic) gets none, and selection keeps its min_keep fail-open, so ratings can
never leave the model with fewer results than without them.

Standard library only: scripts/bench_web_filter.py imports this module to
replay the same arithmetic. The notes entry "A relevance filter for web
results" (section "Plan: ratings feed back into the filter") has the design.
"""
import json
import math
import os
import threading
from urllib.parse import urlparse

MODES = ("off", "log", "apply")
MAX_STRENGTH = 1.5
NO_TOPIC = ("", "other")
_EPS = 1e-6

_cache_lock = threading.Lock()
_cache = {"key": None, "records": []}


def domain_of(url):
    try:
        net = urlparse(url or "").netloc.lower()
    except ValueError:
        return ""
    return net[4:] if net.startswith("www.") else net


def covers(key, dom):
    """'webmd.com' covers 'm.webmd.com' but not 'notwebmd.com'."""
    return bool(key) and (dom == key or dom.endswith("." + key))


def logit(p):
    p = min(1.0 - _EPS, max(_EPS, float(p)))
    return math.log(p / (1.0 - p))


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def read_records(path):
    """Rating records in file order (append order, so oldest first)."""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
    except FileNotFoundError:
        pass
    return out


def build_table(records, before=None, exclude_search=None):
    """{"domains": {topic: {domain: [up, down]}}, "urls": {topic: {url: up - down}}}.

    Latest click per (owner, search id, url) wins and "clear" removes it, as in
    src/web_ratings.py; every owner counts. `before` (an ISO local timestamp)
    keeps only clicks made earlier, `exclude_search` drops one search's own
    ratings: the replay uses both so a search is never scored with ratings
    made after it or on it."""
    latest = {}
    for rec in records:
        if before is not None and str(rec.get("ts_local") or "") >= before:
            continue
        if exclude_search and rec.get("search_id") == exclude_search:
            continue
        key = (rec.get("owner", ""), rec.get("search_id"), rec.get("url"))
        if rec.get("rating") == "clear":
            latest.pop(key, None)
        elif rec.get("rating") in ("up", "down") and rec.get("url"):
            latest[key] = rec
    domains, urls = {}, {}
    for rec in latest.values():
        topic = rec.get("topic") or ""
        if topic in NO_TOPIC:
            continue
        up = rec["rating"] == "up"
        counts = domains.setdefault(topic, {}).setdefault(domain_of(rec["url"]), [0, 0])
        counts[0 if up else 1] += 1
        topic_urls = urls.setdefault(topic, {})
        topic_urls[rec["url"]] = topic_urls.get(rec["url"], 0) + (1 if up else -1)
    return {"domains": domains, "urls": urls}


def bias_for(topic, url, table, strength, min_ratings):
    """Logit bias in [-strength, +strength] for one result.

    Domain term: strength × (up − down) / (up + down + 2), once the site has
    min_ratings ratings in this topic (the +2 keeps one click from counting as
    certainty). Exact-URL term: ±strength / 2. Ratings of a site cover its
    subdomains."""
    if topic in NO_TOPIC or strength <= 0:
        return 0.0
    dom = domain_of(url)
    up = down = 0
    for key, (u, d) in table["domains"].get(topic, {}).items():
        if covers(key, dom):
            up += u
            down += d
    total = 0.0
    if up + down >= min_ratings:
        total += strength * (up - down) / (up + down + 2)
    net = table["urls"].get(topic, {}).get(url, 0)
    if net:
        total += math.copysign(strength / 2, net)
    return max(-strength, min(strength, total))


def adjust(scores, results, topic, table, strength, min_ratings):
    """(adjusted scores, biases), both in input order."""
    biases = [bias_for(topic, r.get("url", ""), table, strength, min_ratings) for r in results]
    adjusted = [s if b == 0 else sigmoid(logit(s) + b) for s, b in zip(scores, biases)]
    return adjusted, biases


def settings_of(cfg):
    """(mode, strength, min_ratings) from filter settings, clamped to safe values."""
    mode = cfg.get("web_filter_rating_mode", "log")
    if mode not in MODES:
        mode = "off"
    try:
        strength = min(MAX_STRENGTH, max(0.0, float(cfg.get("web_filter_rating_strength", 0.7))))
        min_ratings = max(1, int(cfg.get("web_filter_rating_min", 2)))
    except (TypeError, ValueError):
        return "off", 0.0, 2
    return mode, strength, min_ratings


def _ratings_path():
    from src.constants import DATA_DIR
    return os.path.join(DATA_DIR, "web_ratings.jsonl")


def current_table(path=None):
    """The live table, re-read only when the ratings file changes."""
    path = path or _ratings_path()
    try:
        st = os.stat(path)
        key = (path, st.st_mtime_ns, st.st_size)
    except FileNotFoundError:
        key = (path, None, None)
    with _cache_lock:
        if _cache["key"] != key:
            _cache["records"] = read_records(path) if key[1] is not None else []
            _cache["table"] = build_table(_cache["records"])
            _cache["key"] = key
        return _cache["table"]
