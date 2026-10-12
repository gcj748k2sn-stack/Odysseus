"""Ratings of web search results from the chat (fork module).

The sources box under an answer lets the user mark each result useful (up) or
not (down). Each click appends one JSON line to data/web_ratings.jsonl; the
latest line per (owner, search id, url) wins, and "clear" removes the rating.
Ratings feed the replay (scripts/bench_web_filter.py import-ratings) as labels,
and bias later searches in the same topic through src/rating_bias.py (logged
only unless web_filter_rating_mode is "apply"). The notes entry "A relevance
filter for web results" has the design.
"""
import datetime as dt
import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

RATINGS = ("up", "down", "clear")
_lock = threading.Lock()


def _path():
    from src.constants import DATA_DIR
    return os.path.join(DATA_DIR, "web_ratings.jsonl")


def _text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def add_rating(owner, payload, path=None):
    """Validate and append one rating; returns the stored record. Raises ValueError."""
    if not isinstance(payload, dict):
        raise ValueError("expected an object")
    rating = payload.get("rating")
    if rating not in RATINGS:
        raise ValueError("rating must be up, down or clear")
    search_id = str(payload.get("search_id") or "")
    if not (1 <= len(search_id) <= 64 and search_id.replace("-", "").isalnum()):
        raise ValueError("bad search_id")
    url = str(payload.get("url") or "")
    if not url.startswith(("http://", "https://")) or len(url) > 2000:
        raise ValueError("bad url")
    record = {
        "ts_local": dt.datetime.now().isoformat(timespec="seconds"),
        "owner": owner or "",
        "search_id": search_id,
        "url": url,
        "rating": rating,
        "query": _text(payload.get("query"), 500),
        "topic": _text(payload.get("topic"), 48),
        "title": _text(payload.get("title"), 300),
        "filtered": bool(payload.get("filtered")),
        "score": payload.get("score") if isinstance(payload.get("score"), (int, float)) else None,
    }
    path = path or _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _records(path=None):
    path = path or _path()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    yield rec
    except FileNotFoundError:
        return


def current_ratings(owner, search_ids=None, path=None):
    """{(search_id, url): record} for `owner`, latest click wins, cleared ones removed."""
    wanted = set(search_ids) if search_ids is not None else None
    out = {}
    for rec in _records(path):
        if rec.get("owner", "") != (owner or ""):
            continue
        if wanted is not None and rec.get("search_id") not in wanted:
            continue
        key = (rec.get("search_id"), rec.get("url"))
        if rec.get("rating") == "clear":
            out.pop(key, None)
        else:
            out[key] = rec
    return out


def counts_by_topic(owner, path=None):
    """{topic: {"up": n, "down": n}} over the owner's current ratings."""
    counts = {}
    for rec in current_ratings(owner, path=path).values():
        c = counts.setdefault(rec.get("topic") or "other", {"up": 0, "down": 0})
        c[rec["rating"]] = c.get(rec["rating"], 0) + 1
    return counts
