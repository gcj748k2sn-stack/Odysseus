"""Acceptance gate for notes/todo.md item 2a.

Driven by two **real recorded runs**, extracted from `app.db` into
`tests/fixtures/document_fidelity/` so the gate does not depend on a
machine-local, gitignored database:

  run_31e0af64_defective  2026-07-27. Three defects reached the user: a dropped
                          temperature column at `s=360`, two entirely absent
                          sensors, and `duty: 252` printed as a metric.
  run_42889f7b_clean      2026-07-28. Transcription is byte-clean — 40/40 rows,
                          0 cell errors — and `duty: 252` is *still* wrong.

**The clean run is the negative control and it is the point of this file.** A
checker with only a positive case can be a function that always fires and still
look like it works — the same shape as item 16's green suite asserting a
property nothing enforced, and as the `isabs` guard in item 19 that returned
False in both the broken and the fixed case. `test_clean_run_reports_no_*`
below is what stops that here.
"""
import json
import pathlib

import pytest

from src.document_fidelity import (
    check_document,
    check_field_semantics,
    check_liveness,
    check_transcription,
    extract_json_payload,
)

FIX = pathlib.Path(__file__).parent / "fixtures" / "document_fidelity"
SEMANTICS = pathlib.Path(__file__).parents[1] / "config" / "field_semantics.json"


def _case(name):
    return (
        json.loads((FIX / f"{name}.source.json").read_text()),
        (FIX / f"{name}.document.md").read_text(),
        json.loads((FIX / f"{name}.meta.json").read_text()),
    )


def _events(name, payload_text=None):
    src, _, meta = _case(name)
    return [{
        "tool": "web_fetch",
        "command": json.dumps({"url": "http://192.168.0.185/api/state"}),
        "output": payload_text or ("Source: http://192.168.0.185/api/state\n\n" + json.dumps(src)),
        "cached": meta["fetch_cached"],
        "cache_age_seconds": meta["fetch_cache_age_seconds"],
    }]


# ── the defective run: every defect that reached the user must be named ──────

def test_defective_run_flags_the_dropped_column():
    src, doc, _ = _case("run_31e0af64_defective")
    found = check_transcription(doc, src)
    assert any("360" in f for f in found), found
    assert any("24.5" in f or "ragged" in f for f in found), found


def test_defective_run_flags_the_raw_register():
    src, doc, _ = _case("run_31e0af64_defective")
    found = check_field_semantics(doc, src, "http://192.168.0.185/api/state")
    assert any("duty" in f and "252" in f for f in found), found
    # and points at the field that actually answers the question
    assert any("dp" in f and "5.1" in f for f in found), found


def test_defective_run_end_to_end():
    src, doc, _ = _case("run_31e0af64_defective")
    found = check_document(doc, _events("run_31e0af64_defective"))
    assert found, "the run that produced three user-visible defects reported none"


# ── the clean run: the negative control ─────────────────────────────────────

def test_clean_run_reports_no_transcription_findings():
    """40/40 rows, 0 cell errors — this must be silent, or the checker is noise."""
    src, doc, _ = _case("run_42889f7b_clean")
    assert check_transcription(doc, src) == []


def test_clean_run_still_flags_the_raw_register():
    """Transcription clean and the document still wrong: this is item 2a's point."""
    src, doc, _ = _case("run_42889f7b_clean")
    found = check_field_semantics(doc, src, "http://192.168.0.185/api/state")
    assert any("duty" in f and "252" in f for f in found), found


def test_clean_run_flags_liveness_over_a_cache_hit():
    _, doc, meta = _case("run_42889f7b_clean")
    assert meta["fetch_cached"] is True
    found = check_liveness(doc, True, meta["fetch_cache_age_seconds"])
    assert found and "cache" in found[0].lower(), found


# ── silence where there is nothing to check ─────────────────────────────────

def test_prose_document_with_no_structured_source_is_silent():
    events = [{"tool": "web_search", "command": "pink oyster", "output": "1. A blog post…"}]
    assert check_document("# Growing Guide\n\nKeep humidity at 85-95%.", events) == []


def test_document_with_no_data_table_is_silent():
    src, _, _ = _case("run_42889f7b_clean")
    doc = "# Summary\n\nThe sensor reports a temperature of 26.0 C.\n"
    assert check_transcription(doc, src) == []


def test_prose_table_is_not_mistaken_for_data():
    """`| Field | Value |` is not a data table; the first cell must be numeric."""
    src, _, _ = _case("run_42889f7b_clean")
    doc = "| Field | Value |\n|---|---|\n| Temperature | 26.0 |\n"
    assert check_transcription(doc, src) == []


def test_no_tool_events_is_silent():
    assert check_document("anything", []) == []


def test_unknown_source_gets_no_semantic_findings():
    """A field called `duty` on another device must not be judged by this fixture."""
    payload = {"duty": 252, "dp": 5.1}
    assert check_field_semantics("Duty Cycle: 252", payload, "http://example.com/x") == []


def test_live_fetch_gets_no_liveness_finding():
    assert check_liveness("A live reading of the sensor.", False, None) == []


# ── robustness: a checker that crashes a turn is worse than one that is quiet ─

def test_missing_fixture_file_degrades_quietly(tmp_path):
    src, doc, _ = _case("run_31e0af64_defective")
    assert check_field_semantics(doc, src, "http://192.168.0.185/api/state",
                                 fixture_path=str(tmp_path / "nope.json")) == []


def test_malformed_fixture_degrades_quietly(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    src, doc, _ = _case("run_31e0af64_defective")
    assert check_field_semantics(doc, src, "http://192.168.0.185/api/state",
                                 fixture_path=str(bad)) == []


def test_payload_extraction_survives_the_cache_notice():
    """web_fetch prepends a cache notice and a header; the body must still parse."""
    text = ("[served from cache, fetched 1 min 17 s ago — NOT a live reading.]\n\n"
            "# state\nSource: http://192.168.0.185/api/state\n\n"
            '{"t":26.0,"d":[{"s":0,"t":22.0}]}')
    assert extract_json_payload(text)["t"] == 26.0


def test_findings_are_capped():
    payload = {"d": [{"s": i, "t": 99.0 + i} for i in range(200)]}
    doc = "\n".join("| %d | 0.0 |" % i for i in range(200))
    assert len(check_transcription(doc, payload)) <= 12


# ── the fixture itself ──────────────────────────────────────────────────────

def test_semantics_fixture_is_valid_and_documented():
    data = json.loads(SEMANTICS.read_text())
    assert data["sources"], "fixture has no sources"
    for entry in data["sources"]:
        assert entry.get("match") and entry.get("fields")
        for name, spec in entry["fields"].items():
            if spec.get("raw_register"):
                assert spec.get("note"), f"{name} claims raw_register with no note"
                assert spec.get("prefer"), f"{name} is raw with no field to prefer"
