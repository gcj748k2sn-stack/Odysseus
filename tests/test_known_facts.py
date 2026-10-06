"""Acceptance gate for notes/todo.md item 2b.

Three **real recorded documents**, extracted from `app.db` into
`tests/fixtures/known_facts/` so the gate does not depend on a machine-local,
gitignored database:

  run_009660d2_cold_shock         2026-07-19. Prescribes "Cool down by 3-5°F
                                  from spawn temp" and states that pink oysters
                                  "prefer slightly cooler than other Pleurotus
                                  species during fruiting". Both backwards.
  run_4d97aa60_factchecked_worst  2026-07-19. The run that was *asked* for
                                  fact-checked information and fetched four
                                  sources to get it. Fruiting at 14-21 C, and
                                  26 C — squarely optimal — flagged as
                                  yield-reducing.
  run_acba4766_closest_correct    2026-07-19. Plain "create a document", no
                                  fact-check, no fetches. **Scored closest to
                                  correct of the six.**

**The third one is the point of this file.** A checker with only positive cases
can be a function that always fires and still look like it works — item 16's
green suite asserting a property nothing enforced, item 19's `isabs` guard that
was False in the broken and the fixed case alike, and
`test_clean_run_reports_no_transcription_findings` next door. Every rule in
`config/known_facts.json` was narrowed against this document, and the first
version of the checker reported it as wrong six times over.

Two of those false positives are worth keeping in mind, because both are
mistakes about *what a number means* rather than about the fact itself:

  * `3-5°C` in "temperature drop: slight reduction of 3-5°C" is a **difference**
    and was reported as though it were a setpoint outside the fruiting range.
  * "Temperature shock" appears in this document's **troubleshooting** table, as
    a cause of dark caps. Naming a hazard is not prescribing it.
"""
import json
import pathlib

import pytest

from src.known_facts import (
    _phases_in,
    check_contradictions,
    check_document,
    check_ranges,
    load_facts,
    subject_for,
)

FIX = pathlib.Path(__file__).parent / "fixtures" / "known_facts"
RUNS = json.loads((FIX / "runs.json").read_text())

COLD_SHOCK = "run_009660d2_cold_shock"
FACTCHECKED = "run_4d97aa60_factchecked_worst"
CLOSEST = "run_acba4766_closest_correct"


def _doc(name):
    return (FIX / f"{name}.document.md").read_text()


@pytest.fixture(scope="module")
def facts():
    return load_facts()


@pytest.fixture(scope="module")
def djamor(facts):
    return facts["subjects"][0]


# ── the negative control ─────────────────────────────────────────────────────

def test_the_closest_to_correct_document_reports_nothing():
    """If this ever fails, the checker is the thing that is wrong.

    Not "reports few findings" — reports none. This document was scored against
    cultivation sources and came out best of six; a report-only warning that
    fires on it teaches the reader to skim past the ones that matter.
    """
    assert check_document(_doc(CLOSEST)) == []


def test_a_temperature_delta_is_not_read_as_a_setpoint():
    doc = "# Pink oyster\n\n## Fruiting\n\n- Temperature drop: slight reduction of 3-5°C from colonization temps.\n"
    assert [f for f in check_document(doc) if "3-5°C" in f and "outside" in f] == []


def test_a_stated_limit_is_not_read_as_a_setpoint():
    doc = "# Pink oyster\n\n## Fruiting\n\n- Temperature: 24-28°C. Below 15°C fruiting stalls entirely.\n"
    assert [f for f in check_document(doc) if "15°C" in f] == []


def test_naming_a_hazard_is_not_prescribing_it():
    doc = (
        "# Pink oyster\n\n## Troubleshooting\n\n"
        "| Dark/abnormal caps | Temperature shock or inconsistent conditions | Stabilize environment |\n"
    )
    assert check_document(doc) == []


def test_a_comparison_does_not_attribute_the_phase_it_names():
    """"20-25°C, cooler than colonization" is a *fruiting* number.

    Reading "colonization" out of the comparison and judging the value against
    the colonization range is what reported the best document as wrong.
    """
    doc = (
        "# Pink oyster\n\n### Optimal Conditions During Fruiting\n\n"
        "| Temperature | 20-25°C (68-77°F) — cooler than colonization |\n"
        "| Humidity | 90-95% RH |\n"
        "| CO₂ | <1,000 ppm |\n"
    )
    assert check_document(doc) == []


# ── the recorded failures ────────────────────────────────────────────────────

def test_cold_shock_instruction_is_caught():
    findings = check_document(_doc(COLD_SHOCK))
    assert any("cold shock" in f.lower() or "thermophilic" in f.lower() for f in findings), findings


def test_the_species_inversion_is_caught():
    findings = check_document(_doc(COLD_SHOCK))
    assert any("warm-loving" in f for f in findings), findings


def test_the_wrong_species_fruiting_range_is_caught():
    """14-21 C is the P. ostreatus range, on a tropical species."""
    findings = check_document(_doc(FACTCHECKED))
    assert any("14–21°C" in f or "14-21" in f for f in findings), findings


def test_an_optimal_temperature_flagged_as_too_warm_is_caught():
    findings = check_document(_doc(FACTCHECKED))
    assert any("inside the recorded fruiting range" in f for f in findings), findings


def test_the_fact_checked_document_reports_more_than_the_unchecked_one():
    """The measurement that motivated the item, asserted as a property.

    Asking for verification produced a worse document than not asking. If this
    ever inverts, either the model changed or the fixtures were swapped.
    """
    assert len(check_document(_doc(FACTCHECKED))) > len(check_document(_doc(CLOSEST)))


def test_backwards_co2_is_caught():
    doc = "# Pink oyster\n\n## Fruiting\n\n- CO2: maintain elevated levels at 1000-1500 ppm through fruiting.\n"
    assert any("ppm" in f for f in check_document(doc))


def test_a_co2_ceiling_is_not_read_as_a_prescription():
    doc = "# Pink oyster\n\n## Fruiting\n\n- CO₂: <1,000 ppm; avoid >1,500 ppm which causes malformation.\n"
    assert [f for f in check_document(doc) if "ppm" in f] == []


# ── silence ──────────────────────────────────────────────────────────────────

def test_an_unrecognised_subject_produces_nothing():
    doc = "# Shiitake\n\n## Fruiting\n\n- Temperature: 12-16°C. Cold shock by 5°C to initiate.\n"
    assert check_document(doc) == []


def test_an_empty_document_produces_nothing():
    assert check_document("") == []
    assert check_document(None) == []


def test_a_missing_fixture_file_disables_checking_rather_than_raising():
    assert load_facts("/nonexistent/known_facts.json") == {}
    assert check_document(_doc(COLD_SHOCK), fixture_path="/nonexistent/known_facts.json") == []


# ── the fixture is a fixture ─────────────────────────────────────────────────

def test_every_contradiction_cites_where_it_was_seen(djamor):
    """An entry with no observed failure behind it is a guess, and guesses here
    become warnings the user is asked to trust."""
    for rule in djamor["contradictions"]:
        assert rule.get("seen_in"), f"{rule['id']} has no recorded instance"
        assert rule.get("message"), f"{rule['id']} has no reader-facing message"


def test_the_ground_truth_matches_what_resolvedissues_records(djamor):
    """Pin the numbers, so a later edit to the fixture is a deliberate act.

    Source: notes/resolvedissues.md, "4B retired" — colonization 24-29 °C,
    fruiting 20-30 °C with no cold shock, RH 85-95 %, CO2 500-800 ppm.
    """
    by_fact = {r["fact"]: r for r in djamor["ranges"]}
    assert (by_fact["colonization temperature"]["low"], by_fact["colonization temperature"]["high"]) == (24, 29)
    assert (by_fact["fruiting temperature"]["low"], by_fact["fruiting temperature"]["high"]) == (20, 30)
    assert (by_fact["fruiting humidity"]["low"], by_fact["fruiting humidity"]["high"]) == (85, 95)
    assert (by_fact["CO2 concentration"]["low"], by_fact["CO2 concentration"]["high"]) == (500, 800)


def test_the_fixtures_are_the_runs_the_docs_name():
    assert RUNS[COLD_SHOCK]["session_id"].startswith("009660d2")
    assert RUNS[FACTCHECKED]["session_id"].startswith("4d97aa60")
    assert RUNS[CLOSEST]["session_id"].startswith("acba4766")


# ── the halves are independently useful ──────────────────────────────────────

def test_contradictions_fire_without_any_number_present(djamor):
    """The half a range check structurally cannot do.

    "Cool down by 3-5°F from spawn temp" contains no absolute temperature. It is
    also the instruction that reaches the chamber.
    """
    doc = "Pink oyster: cool down by 3-5°F from spawn temp within 4-7 days.\n"
    assert check_contradictions(doc, djamor)
    assert not check_ranges(doc, djamor)


def test_phase_vocabulary_does_not_overlap():
    assert _phases_in("colonization") == {"colonization"}
    assert _phases_in("fruiting") == {"fruiting"}
    assert _phases_in("Colonization/Pinning Initiation") == {"colonization", "fruiting"}


def test_an_ambiguous_phase_must_fail_against_both_ranges(djamor):
    """A heading naming two phases must not produce a confident wrong claim."""
    ok = "# Pink oyster\n\n## Phase 2: Colonization/Pinning Initiation\n\n- Temperature: 22-25°C\n"
    bad = "# Pink oyster\n\n## Phase 2: Colonization/Pinning Initiation\n\n- Temperature: 14-17°C\n"
    assert not [f for f in check_document(ok) if "°C" in f]
    assert [f for f in check_document(bad) if "°C" in f]


def test_subject_is_matched_on_any_identifier(facts):
    for marker in ("pink oyster", "Pleurotus djamor", "P. djamor"):
        assert subject_for(f"# {marker} cultivation\n\nsome text", facts)
    assert subject_for("# Lion's mane\n\nsome text", facts) is None


def test_a_passing_mention_does_not_make_a_document_eligible(facts):
    """The DHT22 datasheet, reduced to its identifying line.

    It names the project it was written for and nothing else about the species.
    The looser substring test made it eligible, and its "±2°C accuracy" was then
    reported as a prescribed temperature drop — a cultivation warning on a
    sensor datasheet, which is the kind of finding that makes a reader stop
    reading all of them.
    """
    datasheet = (
        "# DHT22 Sensor Technical Specifications Reference\n\n"
        "| Accuracy | ±0.5°C typical, lower accuracy (±2°C) at extremes |\n\n"
        "*Document created for environmental monitoring project reference - "
        "Pink Oyster mushroom climate chamber 'martha'*\n"
    )
    assert subject_for(datasheet, facts) is None
    assert check_document(datasheet) == []


def test_a_heading_mention_is_enough(facts):
    assert subject_for("## Pink oyster growth phases\n\nbody text\n", facts)


def test_findings_are_capped():
    from src.known_facts import MAX_FINDINGS
    assert len(check_document(_doc(COLD_SHOCK))) <= MAX_FINDINGS
