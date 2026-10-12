"""Relevance filter for web search results (fork module).

Scores each result's title + snippet against the search query with a
cross-encoder reranker and drops the ones below a threshold, before
comprehensive_web_search picks pages to fetch and hands the list to the model.

Off by default (`web_filter_enabled` in data/settings.json). Fail-open by
construction: any error returns the results unchanged, and at least
`web_filter_min_keep` results always survive. When every result scores below
the threshold the results are kept and a notice is returned for the model
instead, since dropping can't help a search that found nothing relevant.

Measured offline in notes item 71 ("A relevance filter for web results") with
scripts/bench_web_filter.py; the defaults below come from that replay.
"""
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
}

OFF_TOPIC_NOTICE = (
    "Relevance check: none of these results scored as relevant to the query. "
    "They may be about something else that shares a word with it; consider "
    "rephrasing the search with more specific terms."
)

_model = None
_model_name = None
_model_lock = threading.Lock()
_logged_state = None   # last on/off state written to the log


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


def decide(scores, threshold, min_keep):
    """Indices to keep, in input order, and whether every result scored low.

    Keeps results scoring >= threshold; if that leaves fewer than min_keep,
    keeps the min_keep best instead (fail-open)."""
    n = len(scores)
    kept = [i for i, s in enumerate(scores) if s >= threshold]
    all_low = n > 0 and not kept
    if len(kept) < min(min_keep, n):
        best = sorted(range(n), key=lambda i: scores[i], reverse=True)[:min_keep]
        kept = sorted(best)
    return kept, all_low


def filter_results(query, results, settings=None, model=None):
    """Return (results to use, notice for the model or "").

    Never raises and never returns fewer than min(min_keep, len(results))
    results; when disabled or on any error it returns `results` unchanged."""
    global _logged_state
    cfg = settings if settings is not None else _settings()
    enabled = bool(cfg.get("web_filter_enabled"))
    # One line per state change, so a log without [web-filter] lines can be
    # told apart: old code (none at all), off ("off"), or on.
    if enabled != _logged_state:
        logger.info("[web-filter] %s (web_filter_enabled in data/settings.json)", "on" if enabled else "off")
        _logged_state = enabled
    if not enabled or not results or not (query or "").strip():
        return results, ""
    started = time.monotonic()
    try:
        threshold = float(cfg.get("web_filter_threshold", DEFAULTS["web_filter_threshold"]))
        min_keep = max(1, int(cfg.get("web_filter_min_keep", DEFAULTS["web_filter_min_keep"])))
        model = model or _load_model(cfg.get("web_filter_model") or DEFAULTS["web_filter_model"])
        scores = score_results(query, results, model)
    except Exception as e:
        logger.warning("[web-filter] skipped, results unchanged: %s: %s", type(e).__name__, e)
        return results, ""
    kept, all_low = decide(scores, threshold, min_keep)
    dropped = [i for i in range(len(results)) if i not in set(kept)]
    ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "[web-filter] query=%r kept=%d/%d threshold=%.3g all_low=%s ms=%d dropped=%s",
        query[:120], len(kept), len(results), threshold, all_low, ms,
        [f"{_domain(results[i].get('url'))}:{scores[i]:.3f}" for i in dropped],
    )
    return [results[i] for i in kept], (OFF_TOPIC_NOTICE if all_low else "")
