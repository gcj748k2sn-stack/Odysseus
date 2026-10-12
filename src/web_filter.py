"""Relevance filter for web search results (fork module).

Scores each result's title + snippet against the search query with a
cross-encoder reranker and drops the ones below a threshold, before
comprehensive_web_search picks pages to fetch and hands the list to the model.

Off by default (`web_filter_enabled` in data/settings.json). Fail-open by
construction: any error returns the results unchanged, and at least
`web_filter_min_keep` results always survive. When every result scores below
`web_filter_notice_below` (off by default) the results are kept and a notice is
returned for the model instead; that cut-off is separate from the drop
threshold and needs its own measurement (scripts/bench_web_filter.py run).

Measured offline in the notes entry "A relevance filter for web results" with
scripts/bench_web_filter.py; the defaults below come from that replay.
"""
import datetime as dt
import json
import logging
import math
import os
import threading
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULTS = {
    "web_filter_enabled": False,
    "web_filter_model": "jinaai/jina-reranker-v2-base-multilingual",
    "web_filter_threshold": 0.035,
    "web_filter_min_keep": 3,
    # Notice to the model when the best result scores below this. 0 = never.
    # Kept separate from the drop threshold: relevant results often score
    # near it, so the same cut-off flagged good searches as off-topic.
    "web_filter_notice_below": 0.0,
    # Ask the search provider for this many results while the filter is on,
    # score them all and pass on the best (up to the normal result count).
    "web_filter_candidates": 15,
    # One JSON line per filtered search (every result, score, kept or not)
    # in data/logs/web_filter.jsonl, so the filter's own decisions can be
    # replayed and labelled; dropped results are recorded nowhere else.
    "web_filter_decision_log": True,
    # ▲/▼ ratings bias later searches in the same topic (src/rating_bias.py):
    # "off", "log" (compute and log, change nothing) or "apply". Strength is
    # a logit offset (0.7 ≈ odds ×2); a site's own term needs this many ratings.
    "web_filter_rating_mode": "log",
    "web_filter_rating_strength": 0.7,
    "web_filter_rating_min": 2,
}

DECISION_LOG_MAX_BYTES = 20 * 1024 * 1024

OFF_TOPIC_NOTICE = (
    "Relevance check: none of these results scored as relevant to the query. "
    "They may be about something else that shares a word with it; consider "
    "rephrasing the search with more specific terms."
)

_model = None
_model_name = None
_model_lock = threading.Lock()
_logged_state = None   # last on/off state written to the log
_decision_lock = threading.Lock()


def _settings():
    try:
        from src.settings import load_settings
        s = load_settings()
    except Exception:
        s = {}
    out = dict(DEFAULTS)
    out.update({k: s[k] for k in DEFAULTS if k in s})
    return out


def _domain(url):
    try:
        net = urlparse(url or "").netloc.lower()
    except ValueError:
        return ""
    return net[4:] if net.startswith("www.") else net


def _passage(result):
    # Same text the replay scored: title, snippet, domain.
    return f"{result.get('title', '')}. {result.get('snippet', '')} ({_domain(result.get('url', ''))})"


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def _load_model(name):
    global _model, _model_name
    with _model_lock:
        if _model is None or _model_name != name:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            from src.constants import FASTEMBED_CACHE_DIR
            os.makedirs(FASTEMBED_CACHE_DIR, exist_ok=True)
            _model = TextCrossEncoder(model_name=name, cache_dir=FASTEMBED_CACHE_DIR)
            _model_name = name
        return _model


def score_results(query, results, model):
    """Relevance in 0..1 per result, in input order."""
    logits = list(model.rerank(query, [_passage(r) for r in results]))
    if len(logits) != len(results):
        raise RuntimeError(f"reranker returned {len(logits)} scores for {len(results)} results")
    return [_sigmoid(float(x)) for x in logits]


def candidate_count(base, settings=None):
    """How many results to request from the provider: `base` normally, more
    while the filter is on so dropped results can be replaced."""
    cfg = settings if settings is not None else _settings()
    if not cfg.get("web_filter_enabled"):
        return base
    try:
        return max(base, int(cfg.get("web_filter_candidates", DEFAULTS["web_filter_candidates"])))
    except (TypeError, ValueError):
        return base


def select(scores, threshold, min_keep, limit=None):
    """Indices to pass on, best score first: those >= threshold, topped up to
    min_keep with the next best (fail-open), cut to `limit`."""
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    passing = [i for i in order if scores[i] >= threshold]
    if len(passing) < min(min_keep, len(scores)):
        passing = order[:min_keep]
    return passing[:limit] if limit else passing


def _decision_log_path():
    from src.constants import DATA_DIR
    return os.path.join(DATA_DIR, "logs", "web_filter.jsonl")


def _write_decision(record, path=None):
    """Append one JSON line; rotate to .1 past DECISION_LOG_MAX_BYTES. Never raises."""
    try:
        path = path or _decision_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with _decision_lock:
            if os.path.exists(path) and os.path.getsize(path) > DECISION_LOG_MAX_BYTES:
                os.replace(path, path + ".1")
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("[web-filter] decision log not written: %s: %s", type(e).__name__, e)


def _rating_bias(scores, results, topic, cfg, table=None):
    """(mode, scores to select on, biases). Never raises: on any error, no bias."""
    from src import rating_bias
    mode, strength, min_ratings = rating_bias.settings_of(cfg)
    if mode == "off":
        return mode, scores, [0.0] * len(scores)
    try:
        table = table if table is not None else rating_bias.current_table()
        adjusted, biases = rating_bias.adjust(scores, results, topic, table, strength, min_ratings)
    except Exception as e:
        logger.warning("[web-filter] rating bias skipped: %s: %s", type(e).__name__, e)
        return mode, scores, [0.0] * len(scores)
    return mode, adjusted, biases


def filter_results(query, results, settings=None, model=None, limit=None, decision_log=None, info=None,
                   rating_table=None):
    """Return (results to use, notice for the model or "").

    `info` (optional dict): its "search_id" and "topic" go into the decision
    log; the filter adds "scores" ({url: score}), "dropped" (the candidates
    not passed on) and "rating_bias" ({url: bias}, non-zero only), which
    annotate_sources() turns into the sources box data.

    With the filter on, results are returned best score first, at most `limit`
    of them. Never raises and never returns fewer than min(min_keep, limit,
    len(results)); when disabled or on any error it returns the results in
    their original order, cut to `limit`.

    Ratings (`web_filter_rating_mode`): "log" computes the rating bias and
    records what it would change; "apply" selects on the biased scores. The
    off-topic notice always uses the unbiased scores (its cut-off was measured
    on them); `notice_either` in the decision log records whether it would
    also fire on the biased ones. `rating_table` is for tests."""
    global _logged_state
    cfg = settings if settings is not None else _settings()
    enabled = bool(cfg.get("web_filter_enabled"))
    # One line per state change, so a log without [web-filter] lines can be
    # told apart: old code (none at all), off ("off"), or on.
    if enabled != _logged_state:
        logger.info("[web-filter] %s (web_filter_enabled in data/settings.json)", "on" if enabled else "off")
        _logged_state = enabled
    unchanged = results[:limit] if limit else results
    if not enabled or not results or not (query or "").strip():
        return unchanged, ""
    started = time.monotonic()
    try:
        threshold = float(cfg.get("web_filter_threshold", DEFAULTS["web_filter_threshold"]))
        min_keep = max(1, int(cfg.get("web_filter_min_keep", DEFAULTS["web_filter_min_keep"])))
        model = model or _load_model(cfg.get("web_filter_model") or DEFAULTS["web_filter_model"])
        notice_below = float(cfg.get("web_filter_notice_below", DEFAULTS["web_filter_notice_below"]))
        scores = score_results(query, results, model)
    except Exception as e:
        logger.warning("[web-filter] skipped, results unchanged: %s: %s", type(e).__name__, e)
        return unchanged, ""
    topic = (info or {}).get("topic", "")
    rating_mode, adjusted, biases = _rating_bias(scores, results, topic, cfg, rating_table)
    raw_kept = select(scores, threshold, min_keep, limit)
    rated_kept = select(adjusted, threshold, min_keep, limit) if rating_mode != "off" else raw_kept
    kept = rated_kept if rating_mode == "apply" else raw_kept
    selected_on = adjusted if rating_mode == "apply" else scores
    kept_set, rated_set, raw_set = set(kept), set(rated_kept), set(raw_kept)
    if info is not None:
        info["scores"] = {r.get("url"): round(scores[i], 5) for i, r in enumerate(results) if r.get("url")}
        info["dropped"] = [results[i] for i in range(len(results)) if i not in kept_set]
        info["rating_bias"] = {r.get("url"): round(biases[i], 4) for i, r in enumerate(results)
                               if r.get("url") and biases[i]}
    all_low = not any(s >= threshold for s in scores)
    best = max(scores)
    notice = OFF_TOPIC_NOTICE if best < notice_below else ""
    notice_either = bool(notice) or max(adjusted) < notice_below
    ms = int((time.monotonic() - started) * 1000)
    # Results the ratings move across the threshold (applied, or would be in "log" mode).
    rating_changes = [f"{_domain(results[i].get('url'))}:{'kept→dropped' if i in raw_set else 'dropped→kept'}"
                      for i in range(len(results)) if (i in raw_set) != (i in rated_set)]
    logger.info(
        "[web-filter] query=%r kept=%d/%d threshold=%.3g best=%.3f all_low=%s notice=%s ms=%d kept=%s dropped=%s"
        " ratings=%s biased=%d rating_changes=%s",
        query[:120], len(kept), len(results), threshold, best, all_low, bool(notice), ms,
        [f"{_domain(results[i].get('url'))}:{selected_on[i]:.3f}" for i in kept],
        [f"{_domain(results[i].get('url'))}:{selected_on[i]:.3f}" for i in range(len(results)) if i not in kept_set],
        rating_mode, sum(1 for b in biases if b), rating_changes,
    )
    if cfg.get("web_filter_decision_log", DEFAULTS["web_filter_decision_log"]):
        position = {i: n for n, i in enumerate(kept, 1)}
        _write_decision({
            "ts_local": dt.datetime.now().isoformat(timespec="seconds"),
            "search_id": (info or {}).get("search_id", ""), "topic": (info or {}).get("topic", ""),
            "query": query, "model": cfg.get("web_filter_model") or DEFAULTS["web_filter_model"],
            "threshold": threshold, "min_keep": min_keep, "limit": limit, "ms": ms, "notice": bool(notice),
            "rating_mode": rating_mode, "notice_either": notice_either,
            "results": [{
                "rank_in": i + 1, "url": r.get("url", ""), "title": r.get("title", ""),
                "snippet": (r.get("snippet") or "")[:500], "engine": r.get("engine", ""),
                "score": round(scores[i], 5), "kept": i in kept_set, "position_out": position.get(i),
                "bias": round(biases[i], 4), "adjusted": round(adjusted[i], 5), "rated_kept": i in rated_set,
            } for i, r in enumerate(results)],
        }, decision_log)
    return [results[i] for i in kept], notice


def annotate_sources(sources, query, info):
    """Add search id, query, topic and score to each source for the sources box,
    then append the filter's dropped candidates flagged `"filtered": true`.

    The list is display data only (the model never sees it; agent_loop strips
    the SOURCES marker), but from here on `web_sources` holds more than what
    the model saw: test `filtered` before reading it as such."""
    info = info or {}
    scores = info.get("scores") or {}
    biases = info.get("rating_bias") or {}
    meta = {"search_id": info.get("search_id", ""), "query": query, "topic": info.get("topic", "")}

    def bias(url):
        return {"rating_bias": biases[url]} if url in biases else {}
    out = []
    for src in sources:
        out.append({**src, **meta, "score": scores.get(src.get("url")), **bias(src.get("url"))})
    for r in info.get("dropped") or []:
        if r.get("url"):
            out.append({"url": r.get("url", ""), "title": r.get("title", ""), "engine": r.get("engine", ""),
                        **meta, "score": scores.get(r.get("url")), **bias(r.get("url")), "filtered": True})
    return out
