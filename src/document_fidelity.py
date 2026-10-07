"""Check a generated document against the data the model was actually handed.

Recorded runs copied almost every cell correctly and were still wrong because
the model picked the wrong *field* (a raw PWM register printed as a duty
cycle). So of the two halves, the smaller one carries most of the weight:

check_field_semantics
    Compares the document against written-down facts about the fields
    (config/field_semantics.json): correct values, wrong meaning - the class
    a diff cannot see.
check_transcription
    Row and cell comparison against the source records: dropped columns,
    rows and fields. Real but incidental.

Report-only: findings go into the closing summary next to stale_values and
never back to the model (notes: "The document didn't match its source").

Silence is a supported outcome: check_document returns nothing unless the turn
has a JSON payload in its tool output. A checker that guesses on ordinary prose
teaches people to ignore it.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "field_semantics.json",
)

# A table row: "| 360 | 24.5 | 87.4 | 26.9 |". The leading cell must be numeric
# so prose tables (| Field | Value |) are never treated as data rows.
_DATA_ROW_RE = re.compile(r"^\s*\|\s*-?\d+(?:\.\d+)?\s*\|.*\|\s*$")

_MAX_FINDINGS = 12


def _load_fixture(path: Optional[str] = None) -> dict:
    try:
        with open(path or _FIXTURE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"sources": []}
    except Exception as exc:  # a malformed fixture must not break a turn
        logger.warning("field_semantics.json unreadable, skipping checks: %s", exc)
        return {"sources": []}


def _source_entry(url: str, fixture: dict) -> Optional[dict]:
    """The fixture entry whose ``match`` appears in ``url``.

    Keyed on the URL rather than the field name on purpose: a field called
    ``duty`` on some other device must not be judged by this device's entry.
    """
    for entry in fixture.get("sources", []):
        m = entry.get("match")
        if m and m in (url or ""):
            return entry
    return None


def extract_json_payload(text: str) -> Optional[Any]:
    """The first JSON object embedded in a tool output, or None.

    ``web_fetch`` output carries a header and possibly a cache notice before
    the body, so this scans for the first balanced ``{...}`` that parses.
    """
    if not text:
        return None
    for start in (m.start() for m in re.finditer(r"\{", text)):
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:
                        break
        # unbalanced or unparseable from here; try the next '{'
    return None


def _records(payload: Any) -> List[dict]:
    """The longest list-of-dicts in the payload — the history series, if any."""
    best: List[dict] = []
    if isinstance(payload, list):
        if payload and all(isinstance(x, dict) for x in payload):
            best = payload
    elif isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                if len(value) > len(best):
                    best = value
    return best


def _identifier_key(records: List[dict], rows: List[str]) -> Optional[str]:
    """Which field the table's first column is keyed on.

    Matched against the rendered rows, NOT taken from the first key of the
    first record: JSON key order is an accident of serialisation, and assuming
    it made every row lookup miss silently.
    """
    best, best_hits = None, 0
    for key in (records[0] if records else {}):
        hits = 0
        for rec in records:
            marker = re.escape(str(rec.get(key)))
            if any(re.match(r"^\s*\|\s*%s\s*\|" % marker, r) for r in rows):
                hits += 1
        if hits > best_hits:
            best, best_hits = key, hits
    # Require most rows to line up, so an unrelated table can't be adopted.
    return best if best_hits >= max(2, len(records) // 2) else None


def check_field_semantics(document: str, payload: Any, url: str,
                          *, fixture_path: Optional[str] = None) -> List[str]:
    """Flag fields whose value is right and whose meaning is wrong."""
    findings: List[str] = []
    entry = _source_entry(url, _load_fixture(fixture_path))
    if not entry or not isinstance(payload, dict):
        return findings
    fields = entry.get("fields") or {}

    for name, spec in fields.items():
        if not spec.get("raw_register"):
            continue
        if name not in payload:
            continue
        raw = payload[name]
        # Only complain if the raw value is actually printed in the document.
        if not re.search(r"(?<![\d.])%s(?![\d.])" % re.escape(str(raw)), document):
            continue
        prefer = spec.get("prefer")
        hint = ""
        if prefer and prefer in payload:
            hint = " The figure that answers it is `%s` = %s." % (prefer, payload[prefer])
        if spec.get("inverted") and spec.get("max_value"):
            hint += " Note %s is inverted: %s means off." % (name, spec["max_value"])
        findings.append(
            "`%s` is a raw register, not a metric — the document prints %s as a "
            "reportable value.%s" % (name, raw, hint)
        )

    # A span asserted in prose that the sample interval contradicts.
    records = _records(payload)
    for name, spec in fields.items():
        interval = spec.get("interval")
        if not interval or not records or name not in (records[0] or {}):
            continue
        true_seconds = (len(records) - 1) * interval
        for value, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(hours?|days?)\b", document, re.I):
            claimed = float(value) * (3600 if unit.lower().startswith("hour") else 86400)
            if claimed > max(true_seconds * 2, true_seconds + 600):
                findings.append(
                    "the document claims a span of %s %s, but %d records at %ss apart "
                    "cover %.1f minutes" % (value, unit, len(records), interval, true_seconds / 60)
                )
                break
    return findings


def check_liveness(document: str, cached: bool, age_seconds: Optional[int]) -> List[str]:
    """Flag a document asserting freshness over a cache hit."""
    if not cached:
        return []
    claims = re.findall(r"(?i)\blive fetch\b|\blive reading\b|\breal[- ]time\b", document)
    if not claims:
        return []
    age = " (%ss old)" % age_seconds if age_seconds is not None else ""
    return ["the source was served from cache%s, but the document asserts %s"
            % (age, ", ".join(sorted({c.lower() for c in claims})))]


def check_transcription(document: str, payload: Any) -> List[str]:
    """Compare the document's data table against the source records."""
    findings: List[str] = []
    records = _records(payload)
    if not records:
        return findings
    rows = [l for l in document.split("\n") if _DATA_ROW_RE.match(l)]
    if not rows:
        return findings  # no data table rendered; nothing to compare

    widths = {len(r.strip().strip("|").split("|")) for r in rows}
    if len(widths) > 1:
        findings.append(
            "the data table has ragged rows (%s columns) — a dropped cell shifts "
            "every value left of it" % "/".join(str(w) for w in sorted(widths))
        )

    if len(rows) != len(records):
        findings.append("source has %d records, the table has %d rows"
                        % (len(records), len(rows)))

    key = _identifier_key(records, rows)
    if key is not None:
        for rec in records:
            marker = str(rec.get(key))
            row = next((r for r in rows if re.match(r"^\s*\|\s*%s\s*\|" % re.escape(marker), r)), None)
            if row is None:
                continue  # row-count mismatch is already reported above
            for field, value in rec.items():
                if field == key:
                    continue
                if not re.search(r"(?<![\d.])%s(?![\d.])" % re.escape(str(value)), row):
                    findings.append("record %s=%s: `%s` = %s is not in its table row"
                                    % (key, marker, field, value))
                    if len(findings) >= _MAX_FINDINGS:
                        return findings
    return findings


def check_document(document: str, tool_events: Sequence[Dict[str, Any]],
                   *, fixture_path: Optional[str] = None) -> List[str]:
    """All checks against the most recent structured source in this turn.

    Returns an empty list when there is no JSON source — the common case, and a
    supported outcome rather than a failure to detect anything.
    """
    if not document or not tool_events:
        return []
    for event in reversed(list(tool_events)):
        if event.get("tool") not in ("web_fetch", "read_file"):
            continue
        payload = extract_json_payload(event.get("output") or "")
        if payload is None:
            continue
        url = ""
        try:
            args = json.loads(event.get("command") or "{}")
            if isinstance(args, dict):
                url = str(args.get("url") or args.get("path") or "")
        except Exception:
            url = str(event.get("command") or "")
        findings = (
            check_field_semantics(document, payload, url, fixture_path=fixture_path)
            + check_liveness(document, bool(event.get("cached")), event.get("cache_age_seconds"))
            + check_transcription(document, payload)
        )
        return findings[:_MAX_FINDINGS]
    return []
