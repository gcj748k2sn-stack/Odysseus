"""Post-edit lint: values corrected in one place but left standing in another.

Observed 2026-07-18 (run 127d32b0, doc 71de75d9). The model corrected the CO2
figure in one summary-table cell to "500-800 ppm" and left the cell immediately
beside it reading "Keep below 0.4%". The finished document carried four
different CO2 thresholds while reading as freshly fact-checked — worse than not
correcting it at all, because the surviving errors now look verified.

Exact-FIND rescanning cannot catch this (the two cells are different strings),
so the lint compares at the level of measured values instead.
"""

from src.agent_tools.document_tools import find_stale_values


def test_catches_the_real_co2_case():
    """The exact edit pair from run 127d32b0 v2 -> v4."""
    final = (
        "| CO₂ levels | Colonization tolerates **>5000 ppm** (high CO₂); fruiting "
        "requires reduction to **<1000 ppm (<0.1%, ideally 500-800 ppm)** "
        "| Keep below 0.4%; increase fresh air exchange significantly |"
    )
    pairs = [(
        "| CO₂ levels | Moderate (~3%) acceptable initially but reduce to <0.4% for good pinning",
        "| CO₂ levels | Colonization tolerates **>5000 ppm** (high CO₂); fruiting "
        "requires reduction to **<1000 ppm (<0.1%, ideally 500-800 ppm)**",
    )]
    assert find_stale_values(pairs, final) == ["0.4%"]


def test_catches_stale_temperature_left_in_a_table():
    final = "Colonization at 24-30°C is optimal.\n\n| Temp | 15–20°C | 16-24°C |"
    pairs = [("Colonization at 15-20°C is optimal.", "Colonization at 24-30°C is optimal.")]
    assert find_stale_values(pairs, final) == ["15-20°C"]


def test_dash_and_spacing_variants_are_the_same_value():
    """En dash in the document, hyphen in the FIND — still the same figure."""
    assert find_stale_values(
        [("set 15-20 °C", "set 24-30 °C")], "set 24-30 °C ... later: 15 – 20°c",
    ) == ["15-20 °C"]


def test_clean_edit_reports_nothing():
    final = "Fruiting at 20-30°C.\nHumidity 85-95%."
    pairs = [("Fruiting at 16-24°C.", "Fruiting at 20-30°C.")]
    assert find_stale_values(pairs, final) == []


def test_value_deliberately_kept_by_replace_is_not_flagged():
    pairs = [("hold at 85-95% RH", "hold at 85-95% RH during flush")]
    assert find_stale_values(pairs, "hold at 85-95% RH during flush") == []


def test_bare_numbers_do_not_trigger():
    """Headings, list markers and phase numbers must not be treated as values."""
    assert find_stale_values(
        [("Phase 1 intro", "Phase 2 intro")], "Phase 1 and Phase 2 and 3",
    ) == []


def test_each_value_reported_once_across_multiple_edits():
    pairs = [
        ("a 0.4% here", "a 500-800 ppm here"),
        ("b 0.4% there", "b 500-800 ppm there"),
    ]
    assert find_stale_values(pairs, "still 0.4% survives") == ["0.4%"]


def test_no_edits_is_empty():
    assert find_stale_values([], "anything 15-20°C") == []
