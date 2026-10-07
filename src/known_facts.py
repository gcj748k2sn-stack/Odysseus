"""Check a generated document against facts established once and written down.

document_fidelity asks whether a document matches the data it was handed; this
module asks whether it matches reality, for the facts recorded in
config/known_facts.json (notes: "The document contradicted what we had already
established").

Why a fixed record: in recorded runs the model's own "fact-check" step made
documents worse - retrieval dragged the answer toward the wrong species while
the document called itself verified. So the check cannot live in the model's
loop; it compares against something fixed.

check_ranges
    Numbers against numbers, per growth phase, unit-aware (°F converted).
check_contradictions
    Claims that are wrong whatever the number, e.g. a prescribed temperature
    drop. A range check cannot see these ("cool down by 3-5 °F" contains no
    absolute temperature).

Report-only: findings go to the closing summary beside stale_values and
fidelity and nowhere else.

Silence is the normal outcome: only documents about a subject in the fixture
are checked. A checker that guesses trains people to ignore it.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

_DEFAULT_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "known_facts.json",
)

MAX_FINDINGS = 6

# Phase vocabulary. `_PHASE_TERMS` is deliberately small: a term that is
# ambiguous between phases is worse than a missing one, because it lets the
# checker report a violation against the wrong range and be confidently wrong —
# the exact failure this module exists to catch.
_PHASE_TERMS = {
    "colonization": (
        "colonization", "colonisation", "colonizing", "incubation",
        "spawn run", "spawn initiation", "mycelial", "mycelium initiation",
    ),
    "fruiting": (
        "fruiting", "fruit body", "fruitbody", "pinning", "pin formation",
        "pins", "flush", "flowering", "primordia",
    ),
}

_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")

# "24-28°C", "68–75 °F", "20 °C", "65-70F". The unit may follow the span.
_TEMP_RE = re.compile(
    r"(\d{1,3}(?:\.\d)?)\s*(?:[-–—]\s*(\d{1,3}(?:\.\d)?))?\s*°?\s*([CF])\b"
)
_PERCENT_RE = re.compile(r"(\d{1,3})\s*(?:[-–—]\s*(\d{1,3}))?\s*%")
_PPM_RANGE_RE = re.compile(r"(\d{3,5}(?:,\d{3})?)\s*[-–—]\s*(\d{3,5}(?:,\d{3})?)\s*ppm")

# A ppm figure introduced by any of these is a ceiling or a warning, not a
# target. `avoid >1,500 ppm` is correct advice and must not read as a
# prescription of 1500 ppm.
_PPM_WARNING_RE = re.compile(
    r"(?:<|under|below|avoid|above|over|exceed|greater|max|maximum|poison|not\s+exceed)",
    re.IGNORECASE,
)

_RH_CONTEXT_RE = re.compile(r"humidit|\brh\b|moisture", re.IGNORECASE)

# ── what a number on a line actually is ──────────────────────────────────────
# Changes ("drop by 3-5 °C") and limits are common in these documents and must
# not be compared against a setpoint range; doing so is exactly the
# confidently-wrong output this module exists to prevent.
_DELTA_CONTEXT_RE = re.compile(
    r"(?:drop|reduc\w+|decreas\w+|lower\w*|cool\w*|differential|shock|shift|"
    r"increase\s+of|raise\s+by|swing|delta|fluctuat\w+)",
    re.IGNORECASE,
)
# A stated limit is a correct thing to write down. "below 15 °C stalls growth"
# is true and is not a claim that 15 °C is the setpoint.
_THRESHOLD_CONTEXT_RE = re.compile(
    r"(?:<|>|≤|≥|below|above|under|over|beyond|exceed\w*|avoid|too\s+(?:low|high|warm|cold)|"
    r"at\s+least|no\s+(?:more|less)\s+than|stall\w*|extreme)",
    re.IGNORECASE,
)

_TABLE_ROW_RE = re.compile(r"^\s*\|(?P<first>[^|]*)\|")

# An explicit attribution ("14-21 °C for fruiting") is the one case where a
# phase named mid-line may be trusted. A comparison ("cooler than
# colonization") says the opposite, so "than" is deliberately absent.
_ATTRIBUTED_PHASE_RE = re.compile(
    r"(?:\bfor\b|\bduring\b|\bin\b|\bat\b)\s+(?:the\s+)?(\w+(?:\s+\w+)?)\s*(?:phase|stage)?",
    re.IGNORECASE,
)

# How far from a number a qualifying word may be to change its meaning.
# Whole-line matching was too blunt: a qualifier in a different clause hid a
# real error.
_QUALIFIER_BEFORE = 25
_QUALIFIER_AFTER = 15

# Naming a hazard is not prescribing it: a troubleshooting row listing
# "temperature shock" as a cause is correct advice and must not be reported.
_DIAGNOSTIC_CONTEXT_RE = re.compile(
    r"(?:troubleshoot\w*|symptom|problem|issue|cause|avoid|prevent|do\s+not|don't|"
    r"never|stabili[sz]e|fix|remedy|solution|wrong|too\s+(?:much|great|sudden))",
    re.IGNORECASE,
)


def load_facts(path: Optional[str] = None) -> dict:
    """Load the fixture. A missing or unreadable file means no checking."""
    try:
        with open(path or _DEFAULT_FIXTURE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def subject_for(document: str, facts: dict) -> Optional[dict]:
    """The subject this document is *about*, or None.

    A mention is not a subject: a sensor datasheet with a one-line footer about
    the grow chamber must not get cultivation checks (a false positive on an
    unrelated document is the most expensive kind). So the marker has to appear
    in a heading, or more than once.
    """
    text = document or ""
    low = text.lower()
    headings = " ".join(
        m.group(1).lower() for m in (_HEADING_RE.match(l) for l in text.split("\n")) if m
    )
    for subject in (facts or {}).get("subjects", []):
        for marker in subject.get("identify", []):
            m = marker.lower()
            if m in headings or low.count(m) > 1:
                return subject
    return None


def _to_celsius(value: float, unit: str) -> float:
    return (value - 32.0) * 5.0 / 9.0 if unit.upper() == "F" else value


def _phases_in(text: str) -> set:
    low = (text or "").lower()
    return {name for name, terms in _PHASE_TERMS.items() if any(t in low for t in terms)}


def _line_phases(lines: List[str]) -> List[set]:
    """Phase context per line: the nearest heading, or a table row's own label.

    Naming a phase is not being about it: a Fruiting-section row reading "20-25
    °C
    - cooler than colonization" is a fruiting value. Only two things establish
      phase: the heading a line sits under and, for a table row, its first
      cell. Everything else inherits.
    """
    out: List[set] = []
    heading_phases: set = set()
    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            heading_phases = _phases_in(m.group(1))
            out.append(heading_phases)
            continue
        attributed = _ATTRIBUTED_PHASE_RE.findall(line)
        if attributed:
            own = _phases_in(" ".join(attributed))
            if own:
                out.append(own)
                continue
        row = _TABLE_ROW_RE.match(line)
        if row:
            own = _phases_in(row.group("first"))
            out.append(own or heading_phases)
            continue
        out.append(heading_phases)
    return out


def _qualified(line: str, start: int, end: int) -> bool:
    """Is this number a change or a limit rather than a setpoint?

    Judged on a window around the number, not the whole line — see
    `_QUALIFIER_BEFORE`.
    """
    window = line[max(0, start - _QUALIFIER_BEFORE):end + _QUALIFIER_AFTER]
    return bool(_DELTA_CONTEXT_RE.search(window) or _THRESHOLD_CONTEXT_RE.search(window))


def _temperatures_celsius(line: str) -> List[tuple]:
    """Setpoint temperature spans on a line, in °C, as (low, high, raw).

    A dual-unit span — "14–21°C (57–70°F)" — yields both readings; they agree,
    so judging either is the same verdict. Deltas and thresholds are dropped
    here rather than in the caller, because whether a number is a setpoint is a
    property of the number, not of the line it sits on.
    """
    spans = []
    for m in _TEMP_RE.finditer(line):
        if _qualified(line, m.start(), m.end()):
            continue
        lo = float(m.group(1))
        hi = float(m.group(2)) if m.group(2) else lo
        unit = m.group(3)
        spans.append((_to_celsius(lo, unit), _to_celsius(hi, unit), m.group(0).strip()))
    return spans


def check_ranges(document: str, subject: dict) -> List[str]:
    """Numbers stated for a phase, against the numbers on file for that phase."""
    findings: List[str] = []
    lines = (document or "").split("\n")
    phases = _line_phases(lines)
    ranges = subject.get("ranges", [])

    temp_rules = {r["phase"]: r for r in ranges if r.get("unit") == "celsius"}
    rh_rules = {r["phase"]: r for r in ranges if r.get("unit") == "percent_rh"}
    ppm_rule = next((r for r in ranges if r.get("unit") == "ppm"), None)

    for line, ctx in zip(lines, phases):
        stripped = line.strip()
        if not stripped:
            continue

        # ── temperature ──────────────────────────────────────────────────
        # A number is only a setpoint if the line is not describing a change
        # ("drop by 3-5°C") or a limit ("below 15°C stalls growth"). A change
        # that prescribes cooling is still caught — by `check_contradictions`,
        # which is the right place for it, because the damage is the
        # instruction and not the magnitude.
        applicable = [temp_rules[p] for p in ctx if p in temp_rules]
        if applicable:
            for lo, hi, raw in _temperatures_celsius(line):
                # Judge the MIDPOINT, not the endpoints: a slightly wider
                # stated tolerance is not a false claim, and firing on one
                # degree of overhang is noise. A line naming two phases must
                # fail against BOTH before it is reported.
                mid = (lo + hi) / 2.0
                bad = [r for r in applicable if mid < r["low"] or mid > r["high"]]
                if len(bad) == len(applicable):
                    rule = bad[0]
                    where = " / ".join(sorted(r["phase"] for r in bad))
                    findings.append(
                        f"`{raw}` is outside the recorded {where} range "
                        f"{rule['low']}–{rule['high']} °C for {subject['name']} — {stripped[:90]}"
                    )
                    break  # one finding per line; a dual-unit span is one claim

        # ── humidity ─────────────────────────────────────────────────────
        # The percentage has to be near the word, not merely on the same line:
        # "check CO₂ levels ... 4%" was read as a humidity setpoint otherwise.
        for rule in (rh_rules[p] for p in ctx if p in rh_rules):
            for m in _PERCENT_RE.finditer(line):
                if _qualified(line, m.start(), m.end()):
                    continue
                window = line[max(0, m.start() - 45):m.end() + 20]
                if not _RH_CONTEXT_RE.search(window):
                    continue
                lo = float(m.group(1))
                hi = float(m.group(2)) if m.group(2) else lo
                if (lo + hi) / 2.0 < rule["low"] or (lo + hi) / 2.0 > rule["high"]:
                    findings.append(
                        f"`{m.group(0)}` is outside the recorded {rule['phase']} humidity "
                        f"{rule['low']}–{rule['high']} % for {subject['name']} — {stripped[:90]}"
                    )
                    break

        # ── CO2 ──────────────────────────────────────────────────────────
        if ppm_rule and not _PPM_WARNING_RE.search(line):
            for m in _PPM_RANGE_RE.finditer(line):
                lo = float(m.group(1).replace(",", ""))
                if lo > ppm_rule["high"]:
                    findings.append(
                        f"`{m.group(0)}` prescribes more CO₂ than the recorded maximum "
                        f"{ppm_rule['low']}–{ppm_rule['high']} ppm for {subject['name']} — {stripped[:90]}"
                    )
    return findings


def check_contradictions(document: str, subject: dict) -> List[str]:
    """Claims that are wrong whatever number accompanies them.

    Matched per line rather than against the whole document, so the line can be
    tested for diagnostic framing — and so the quote shown to the reader is the
    sentence the claim was actually made in.
    """
    findings = []
    lines = (document or "").split("\n")
    for rule in subject.get("contradictions", []):
        try:
            pattern = re.compile(rule["pattern"], re.IGNORECASE)
        except re.error:
            continue
        for line in lines:
            m = pattern.search(line)
            if not m:
                continue
            # Opt-in, per rule: optimal_temperature_called_too_warm only ever
            # appears in the framing this filter excludes, so filtering it
            # would silence it entirely.
            if rule.get("diagnostic_framing_excluded", True) and _DIAGNOSTIC_CONTEXT_RE.search(line):
                continue
            quote = " ".join(m.group(0).split())[:80]
            findings.append(f"“{quote}” — {rule['message']}")
            break
    return findings


def check_required(document: str, subject: dict) -> List[str]:
    """Parameters whose *absence* is itself a recorded defect.

    Gated on the document actually being an environment specification — it has
    to give both a temperature and a humidity for the omission to mean anything.
    Without that gate the rule fires on any three-line fragment mentioning
    fruiting, which is not what the entry claims to detect.
    """
    findings = []
    low = (document or "").lower()
    specifies_environment = bool(_TEMP_RE.search(document or "")) and bool(_RH_CONTEXT_RE.search(low))
    if not specifies_environment:
        return findings
    for rule in subject.get("requires", []):
        gate = rule.get("only_if_document_mentions") or []
        if gate and not any(g.lower() in low for g in gate):
            continue
        if not any(term.lower() in low for term in rule.get("any_of", [])):
            findings.append(f"No CO₂ or fresh-air guidance anywhere — {rule['message']}")
    return findings


def check_document(document: str, facts: Optional[dict] = None,
                   fixture_path: Optional[str] = None) -> List[str]:
    """Every finding for ``document``, or an empty list.

    Empty is the common case and the intended one: no recognised subject, no
    output. Findings are capped so a systematically wrong document cannot bury
    the rest of the closing summary.
    """
    if not document:
        return []
    facts = facts if facts is not None else load_facts(fixture_path)
    subject = subject_for(document, facts)
    if not subject:
        return []
    findings = (
        check_contradictions(document, subject)
        + check_ranges(document, subject)
        + check_required(document, subject)
    )
    # Order is deliberate: a directional error reaches the chamber, a number
    # out of range is arguable, so the former should not be truncated away.
    seen, unique = set(), []
    for f in findings:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique[:MAX_FINDINGS]
