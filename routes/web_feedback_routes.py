"""Research topics and per-source ratings API (fork routes).

GET  /api/research-topics      topics + per-topic counts (any signed-in user)
PUT  /api/research-topics      replace the topic list (admin)
POST /api/web-ratings          rate one source: {search_id, url, rating: up|down|clear, ...}
GET  /api/web-ratings?search_ids=a,b   the caller's current ratings for those searches
GET  /api/web-filter/settings  the relevance filter's settings (any signed-in user)
PUT  /api/web-filter/settings  change them (admin); written into data/settings.json

Ratings are per user; topics are global (the search layer has no user).
Storage: src/research_topics.py, src/web_ratings.py. Notes entry "A relevance filter for web results".
"""
import json
import os
from collections import Counter

from fastapi import APIRouter, HTTPException, Request

from core.middleware import require_admin
from src.auth_helpers import effective_user
from src import research_topics, web_ratings


def _searches_per_topic(limit_bytes=5 * 1024 * 1024):
    """Topic counts from the tail of the filter's decision log (cheap, approximate)."""
    from src.web_filter import _decision_log_path
    counts = Counter()
    path = _decision_log_path()
    try:
        with open(path, "rb") as f:
            size = os.path.getsize(path)
            f.seek(max(0, size - limit_bytes))
            for line in f.read().decode("utf-8", "replace").splitlines():
                try:
                    counts[json.loads(line).get("topic") or "other"] += 1
                except (json.JSONDecodeError, AttributeError):
                    continue
    except OSError:
        pass
    return counts


# Settings the Research topics panel may change, with their accepted ranges.
_FILTER_KEYS = {
    "web_filter_enabled": bool,
    "web_filter_threshold": (0.0, 1.0),
    "web_filter_min_keep": (1, 10),
    "web_filter_candidates": (5, 30),
    "web_filter_notice_below": (0.0, 1.0),
    "web_filter_decision_log": bool,
    "web_filter_rating_mode": ("off", "log", "apply"),
    "web_filter_rating_strength": (0.0, 1.5),
    "web_filter_rating_min": (1, 20),
}


def validate_filter_settings(body):
    """Normalized subset of `body` for the keys above; ValueError on a bad value."""
    if not isinstance(body, dict):
        raise ValueError("expected an object")
    out = {}
    for key, rule in _FILTER_KEYS.items():
        if key not in body:
            continue
        val = body[key]
        if rule is bool:
            if not isinstance(val, bool):
                raise ValueError(f"{key} must be true or false")
        elif all(isinstance(c, str) for c in rule):
            if val not in rule:
                raise ValueError(f"{key} must be one of {', '.join(rule)}")
        else:
            lo, hi = rule
            kind = int if isinstance(lo, int) else float
            try:
                val = kind(val)
            except (TypeError, ValueError):
                raise ValueError(f"{key} must be a number")
            if isinstance(val, float) and val != val:
                raise ValueError(f"{key} must be a number")
            if not lo <= val <= hi:
                raise ValueError(f"{key} must be between {lo} and {hi}")
        out[key] = val
    unknown = set(body) - set(_FILTER_KEYS)
    if unknown:
        raise ValueError(f"unknown setting(s): {sorted(unknown)}")
    return out


def setup_web_feedback_routes():
    router = APIRouter(prefix="/api", tags=["web-feedback"])

    @router.get("/research-topics")
    async def get_topics(request: Request):
        owner = effective_user(request)
        data = research_topics.load_topics()
        ratings = web_ratings.counts_by_topic(owner)
        searches = _searches_per_topic()
        for t in data["topics"] + [{"id": research_topics.OTHER}]:
            t["searches"] = searches.get(t["id"], 0)
            t["ratings"] = ratings.get(t["id"], {"up": 0, "down": 0})
        data["other"] = {"searches": searches.get(research_topics.OTHER, 0),
                         "ratings": ratings.get(research_topics.OTHER, {"up": 0, "down": 0})}
        return data

    @router.put("/research-topics")
    async def put_topics(request: Request):
        require_admin(request)
        try:
            body = await request.json()
            return research_topics.save_topics(body)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.post("/web-ratings")
    async def post_rating(request: Request):
        owner = effective_user(request)
        try:
            body = await request.json()
            rec = web_ratings.add_rating(owner, body)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"ok": True, "rating": rec["rating"]}

    @router.get("/web-ratings")
    async def get_ratings(request: Request, search_ids: str = ""):
        owner = effective_user(request)
        ids = [s for s in search_ids.split(",") if s][:200]
        cur = web_ratings.current_ratings(owner, ids)
        out = {}
        for (sid, url), rec in cur.items():
            out.setdefault(sid, {})[url] = rec["rating"]
        return {"ratings": out}

    @router.get("/web-filter/settings")
    async def get_filter_settings(request: Request):
        from src.web_filter import _settings
        cfg = _settings()
        return {k: cfg.get(k) for k in _FILTER_KEYS}

    @router.put("/web-filter/settings")
    async def put_filter_settings(request: Request):
        require_admin(request)
        try:
            changes = validate_filter_settings(await request.json())
        except ValueError as e:
            raise HTTPException(400, str(e))
        from src.settings import load_settings, save_settings
        from src.web_filter import _settings
        current = dict(load_settings())
        current.update(changes)
        save_settings(current)
        cfg = _settings()
        return {k: cfg.get(k) for k in _FILTER_KEYS}

    return router
