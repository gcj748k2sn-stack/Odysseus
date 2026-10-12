"""Research topics (fork module): user-defined topics that web searches are
assigned to, so ratings and filter decisions can be grouped per topic.

A topic is a name plus a few example queries. A search query goes to the topic
whose examples are most similar (local embedding model, cosine), or to "other"
when nothing reaches `min_similarity`. Stored in data/research_topics.json;
global, edited by an admin, readable by every user — the search layer has no
user, so per-user topics could not be applied there.

The notes entry "A relevance filter for web results" has the design.
"""
import json
import logging
import os
import re
import threading
import uuid

logger = logging.getLogger(__name__)

OTHER = "other"
MAX_TOPICS = 30
MAX_EXAMPLES = 10

DEFAULT_TOPICS = {
    "version": 1,
    "enabled": True,
    "min_similarity": 0.35,
    "topics": [
        {"id": "biology", "name": "Biology", "enabled": True, "examples": [
            "pink oyster mushroom fruiting temperature humidity",
            "lion's mane mycelium colonization conditions",
            "parasol mushroom habitat and identification",
            "plant growth requirements soil pH light",
            "insect life cycle stages",
        ]},
        {"id": "finance", "name": "Finance", "enabled": True, "examples": [
            "gold price per ounce today",
            "silver spot price trend last year",
            "stock market news today",
            "EUR USD exchange rate",
            "inflation rate eurozone",
        ]},
        {"id": "cooking", "name": "Cooking", "enabled": True, "examples": [
            "crepe recipe in grams",
            "sourdough starter hydration and crumb",
            "how long to boil eggs",
            "fresh pasta dough recipe",
            "roast chicken oven temperature",
        ]},
    ],
}

_lock = threading.Lock()
_encoder = None
_example_cache = {}   # tuple(examples) -> normalized vectors


def _path():
    from src.constants import DATA_DIR
    return os.path.join(DATA_DIR, "research_topics.json")


def _slug(name, taken):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "topic"
    slug, n = base, 2
    while slug in taken or slug == OTHER:
        slug, n = f"{base}-{n}", n + 1
    return slug


def validate(data):
    """Return a normalized copy of `data` or raise ValueError with the reason."""
    if not isinstance(data, dict) or not isinstance(data.get("topics"), list):
        raise ValueError("expected an object with a 'topics' list")
    topics = data["topics"]
    if len(topics) > MAX_TOPICS:
        raise ValueError(f"at most {MAX_TOPICS} topics")
    try:
        min_sim = float(data.get("min_similarity", DEFAULT_TOPICS["min_similarity"]))
    except (TypeError, ValueError):
        raise ValueError("min_similarity must be a number")
    if not 0.0 <= min_sim <= 1.0:
        raise ValueError("min_similarity must be between 0 and 1")
    out, taken = [], set()
    for t in topics:
        if not isinstance(t, dict):
            raise ValueError("each topic must be an object")
        name = " ".join(str(t.get("name") or "").split())
        if not 1 <= len(name) <= 60:
            raise ValueError("topic names must be 1-60 characters")
        examples = [" ".join(str(e).split()) for e in (t.get("examples") or []) if str(e).strip()]
        if not 1 <= len(examples) <= MAX_EXAMPLES:
            raise ValueError(f"'{name}': give 1-{MAX_EXAMPLES} example queries")
        if any(len(e) > 200 for e in examples):
            raise ValueError(f"'{name}': example queries must be at most 200 characters")
        tid = str(t.get("id") or "")
        if not re.fullmatch(r"[a-z0-9-]{1,48}", tid) or tid in taken or tid == OTHER:
            tid = _slug(name, taken)
        taken.add(tid)
        out.append({"id": tid, "name": name, "enabled": bool(t.get("enabled", True)), "examples": examples})
    return {"version": 1, "enabled": bool(data.get("enabled", True)), "min_similarity": min_sim, "topics": out}


def load_topics(path=None):
    """The saved topics, or the defaults (Biology, Finance, Cooking) when none are saved."""
    path = path or _path()
    try:
        with open(path, encoding="utf-8") as f:
            return validate(json.load(f))
    except FileNotFoundError:
        return validate(DEFAULT_TOPICS)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        logger.warning("[research-topics] %s unreadable (%s); using defaults", path, e)
        return validate(DEFAULT_TOPICS)


def save_topics(data, path=None):
    from core.atomic_io import atomic_write_json
    clean = validate(data)
    with _lock:
        atomic_write_json(path or _path(), clean, indent=2)
    return clean


def _get_encoder():
    global _encoder
    with _lock:
        if _encoder is None:
            from src.embeddings import FastEmbedClient
            _encoder = FastEmbedClient()
        return _encoder


def _vectors(encoder, texts):
    key = (id(encoder), tuple(texts))
    vecs = _example_cache.get(key)
    if vecs is None:
        vecs = encoder.encode(list(texts), normalize_embeddings=True)
        if len(_example_cache) > 200:
            _example_cache.clear()
        _example_cache[key] = vecs
    return vecs


def assign_topic(query, data=None, encoder=None):
    """(topic id or "other", best similarity). Never raises."""
    try:
        data = data or load_topics()
        if not data.get("enabled", True):
            return OTHER, 0.0
        topics = [t for t in data["topics"] if t["enabled"]]
        if not topics or not (query or "").strip():
            return OTHER, 0.0
        encoder = encoder or _get_encoder()
        q = encoder.encode([query], normalize_embeddings=True)[0]
        best_id, best = OTHER, 0.0
        for t in topics:
            sims = _vectors(encoder, t["examples"]) @ q
            s = float(max(sims))
            if s > best:
                best_id, best = t["id"], s
        return (best_id if best >= data["min_similarity"] else OTHER), round(best, 4)
    except Exception as e:
        logger.warning("[research-topics] topic not assigned: %s: %s", type(e).__name__, e)
        return OTHER, 0.0


def tag_search(query, data=None, encoder=None, assign=None):
    """A new search id and the query's topic, for the decision log and the sources.

    The topic is only assigned while the relevance filter is on (`assign`
    None = read the setting): it is filed in the filter's decision log, and
    with the filter off there is no reason to load an embedding model per search."""
    search_id = uuid.uuid4().hex[:12]
    if assign is None:
        try:
            from src.web_filter import _settings
            assign = bool(_settings().get("web_filter_enabled"))
        except Exception:
            assign = False
    if not assign:
        return search_id, ""
    topic, _ = assign_topic(query, data, encoder)
    return search_id, topic
