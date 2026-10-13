"""The webhard suite's checks accept right answers and reject wrong ones,
above all the off-topic answers the suite exists to provoke (negative controls).

scripts/bench_webhard_tasks.py; same pattern as tests/test_bench_research_tasks.py.
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bench_agent_webhard_under_test", ROOT / "scripts" / "bench_agent.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
T = B.T
BY_ID = {t["id"]: t for t in T.TASKS}
WEB = ("web_search",)


def _checks(task_id, text, tools=WEB):
    t = BY_ID[task_id]
    rec = {"final_text": text, "text": text, "tools": [{"tool": x} for x in tools], "tool_results": []}
    return t["checks"](rec, {})


def _passes(task_id, text, tools=WEB):
    return all(ok for _, ok, _ in _checks(task_id, text, tools))


GOOD = {
    "wh_mercury_day": [
        "A solar day on Mercury (sunrise to sunrise) lasts about **176 Earth days**, twice its 88-day year; it "
        "rotates once every 58.6 days relative to the stars. Source: https://science.nasa.gov/mercury/facts/",
        "Mercury's solar day is ~175.9 Earth days long (https://en.wikipedia.org/wiki/Mercury_(planet)).",
        "The planet Mercury (not Freddie Mercury, and not the element) has a solar day of 176 Earth days "
        "(https://science.nasa.gov/mercury/).",
    ],
    "wh_crane_wingspan": [
        "The common crane (Grus grus) has a wingspan of 180–240 cm. Source: https://en.wikipedia.org/wiki/Common_crane",
        "A common crane's wings span about 220–245 cm (https://www.wildlifetrusts.org/wildlife-explorer/birds/common-crane).",
    ],
    "wh_pink_oyster_temp": [
        "Pink oyster mushrooms (Pleurotus djamor) fruit best at 18–30 °C, ideally 21–26 °C. Source: "
        "https://fungi.com/products/pleurotus-djamor-culture",
        "- Fruiting: 24-30°C for the pink oyster mushroom (https://northspore.com/blogs/pink-oyster)",
        "The pink oyster mushroom (Pleurotus djamor, not the singer Pink) fruits at 20–30 °C (https://fungi.com).",
    ],
    "wh_golden_typo": [
        "You probably mean *Pleurotus citrinopileatus*, the **golden oyster mushroom**: its cap is bright yellow "
        "(https://mushroomexpert.com/pleurotus_citrinopileatus.html).",
    ],
    "wh_essen_einwohner": [
        "Laut Statista lebten Ende 2024 rund 574.700 Menschen in Essen; die Stadt ist damit die elftgrößte "
        "Deutschlands. Quelle: https://de.statista.com/statistik/daten/studie/322472",
        "Essen hat etwa 584 580 Einwohner (Stand Ende 2022, IT.NRW) und ist eine Stadt im Ruhrgebiet. "
        "Quelle: https://statistik.nrw/",
        "Die Stadt Essen hat rund 0,58 Mio. Einwohner, laut https://www.essen.de/",
    ],
    "wh_straw_moisture": [
        "Pasteurized straw should be at about 65 % moisture (squeeze test: a few drops). "
        "Source: https://ucanr.edu/sites/default/files/2011-06/111961.pdf",
        "Aim for 65-75% moisture content (https://www.freshcap.com/guides/straw).",
    ],
    "wh_amazon_length": [
        "The Amazon River is about 6,400 km long (Britannica); a Brazilian study measured 6,992 km from its "
        "source in Peru. Source: https://www.britannica.com/place/Amazon-River",
        "Measured from the Apacheta headwater the Amazon is roughly 6992 kilometres long "
        "(https://en.wikipedia.org/wiki/Amazon_River).",
        "The river (not the company Amazon, not Jeff Bezos's firm) runs about 6.400 km (https://britannica.com).",
    ],
    "wh_brocken_hoehe": [
        "Der Brocken ist mit 1141 m der höchste Berg im Harz. Quelle: https://de.wikipedia.org/wiki/Brocken",
        "Laut https://www.nationalpark-harz.de/ ist der Gipfel des Brocken 1.141,2 Meter hoch und damit der "
        "höchste Punkt in Norddeutschland.",
        # Qwen, 2026-10-13 r1: right and German, failed the first version of the check
        "Der Brocken hat eine Höhe von 1.141 Metern (manche Quellen nennen auch 1.141,1 m oder 1.142 m).\n\n"
        "Quelle: [Wikipedia – Brocken](https://de.wikipedia.org/wiki/Brocken)",
        # Qwen, 2026-10-13 filter A/B: right and German, failed the second version of the check
        "Der Brocken ist 1141,2 Meter über dem Normalnull (NHN) hoch. \n\nQuelle: https://de.wikipedia.org/wiki/Brocken",
    ],
    "wh_lionsmane_typo": [
        "You likely mean *Hericium erinaceus*, the **lion's mane** mushroom. In the wild it grows on hardwoods, "
        "e.g. oak and beech, often from wounds in living trees (https://mykoweb.com/CAF/species/Hericium_erinaceus.html).",
        "Common name: Lion’s Mane (also bearded tooth). It fruits on dead or dying broadleaf trees and logs "
        "(https://en.wikipedia.org/wiki/Hericium_erinaceus).",
    ],
    "wh_ssd1306_addr": [
        "The default 7-bit I2C address is **0x3C** (0x3D if SA0 is pulled high; 0x78 is the 8-bit form). "
        "Source: https://docs.wokwi.com/parts/board-ssd1306",
        "Most 0.96\" SSD1306 modules answer at 0x3c (https://learn.adafruit.com/monochrome-oled-breakouts).",
    ],
}

BAD = {
    "wh_mercury_day": [
        ("sidereal day only", "A day on Mercury lasts 58.6 Earth days (https://example.com)."),
        ("no link", "A solar day on Mercury lasts 176 Earth days."),
        ("derailed to the singer", "Freddie Mercury's day... a solar day on Mercury is 176 Earth days (https://x.org)."),
    ],
    "wh_crane_wingspan": [
        ("construction crane", "A tower crane's jib spans 60 m and lifts 20 tonnes (https://liebherr.com)."),
        ("wrong number", "The common crane bird has a wingspan of 120 cm (https://example.com)."),
    ],
    "wh_pink_oyster_temp": [
        ("the singer", "Pink (singer) performs at 20 °C arenas; mushroom fans... (https://en.wikipedia.org/wiki/Pink_(singer))"),
        ("Fahrenheit only", "Pink oyster mushrooms fruit at 65–85 °F (https://fungi.com)."),
        ("an in-range number that is not °C", "Pink oyster mushrooms fruit after 21 days at 75 °F (https://fungi.com)."),
        ("not the mushroom", "Pink oysters (shellfish) are kept at 2 °C (https://example.com)."),
    ],
    "wh_golden_typo": [
        ("no common name", "Its cap is yellow (https://example.com)."),
        ("wrong colour", "The golden oyster has a grey-brown cap (https://example.com)."),
    ],
    "wh_essen_einwohner": [
        ("answered in English", "Essen has about 574,700 inhabitants according to https://de.statista.com/."),
        ("food instead of the city", "Essen ist gesund, wenn man Gemüse isst und viel Wasser trinkt (https://x.de)."),
        ("wrong number", "Die Stadt Essen hat rund 1,2 Millionen Einwohner, laut https://x.de."),
    ],
    "wh_straw_moisture": [
        ("wrong number", "Straw should be at about 30 % moisture (https://example.com)."),
        ("no number", "Soak the straw and let it drain well (https://example.com)."),
    ],
    "wh_amazon_length": [
        ("the company", "Amazon's main warehouse in Kent, WA is 1 km long; Jeff Bezos founded the retailer "
                        "(https://aboutamazon.com). The river is 6,400 km long."),
        ("miles only", "The Amazon River is about 4,000 miles long (https://britannica.com)."),
        ("wrong number", "The Amazon River is 3,000 km long (https://example.com)."),
    ],
    "wh_brocken_hoehe": [
        ("answered in English", "The Brocken is 1141 m high, the highest mountain in the Harz (https://wikipedia.org)."),
        ("a chunk, not the mountain", "Ein Brocken ist ein großes Stück, das man nicht mit Messer und Gabel isst "
                                      "(https://duden.de)."),
        ("English with German words in it", "The Brocken (der Brocken, die Höhe ist 1141 m) is 1141 m high, the "
                                             "highest mountain in the Harz, according to https://de.wikipedia.org/wiki/Brocken."),
        ("no sentence in any language", "Brocken, Harz: 1141 m (Quelle: https://de.wikipedia.org/wiki/Brocken)"),
        ("wrong height", "Der Brocken ist 1.493 m hoch und der höchste Berg im Harz (https://x.de)."),
    ],
    "wh_lionsmane_typo": [
        ("no common name", "Hericium erinaceus grows on hardwood trees (https://example.com)."),
        ("wrong substrate", "Lion's mane grows in grassland soil (https://example.com)."),
    ],
    "wh_ssd1306_addr": [
        ("an LCD backpack's address", "The default address is 0x27 (https://example.com)."),
        ("8-bit form only", "The SSD1306 uses address 0x78 (https://example.com)."),
        ("no link", "The SSD1306 default I2C address is 0x3C."),
    ],
}


@pytest.mark.parametrize("task_id,text", [(k, t) for k, ts in GOOD.items() for t in ts])
def test_good_answers_pass(task_id, text):
    failed = [(n, d) for n, ok, d in _checks(task_id, text) if not ok]
    assert not failed, failed


@pytest.mark.parametrize("task_id,why,text", [(k, w, t) for k, ws in BAD.items() for w, t in ws])
def test_bad_answers_fail(task_id, why, text):
    assert not _passes(task_id, text), why


def test_no_web_tool_fails_even_with_the_right_answer():
    assert not _passes("wh_mercury_day", GOOD["wh_mercury_day"][0], tools=())


def test_every_task_has_good_and_bad_samples():
    ids = {t["id"] for t in T.TASKS if t["suite"] == "webhard"}
    assert ids == set(GOOD) == set(BAD)


def test_the_suite_is_selectable_and_kept_apart():
    sel = B.select_tasks(SimpleNamespace(suite="webhard", quick=False, tasks=None))
    assert len(sel) == 10 and all(t["web"] for t in sel)
    assert len(B.select_tasks(SimpleNamespace(suite="webhard", quick=True, tasks=None))) == 5
    assert not any(t["suite"] == "webhard" for t in B.select_tasks(SimpleNamespace(suite="research", quick=False, tasks=None)))
    assert {t["kind"] for t in sel} == {"ambiguous", "german", "typo", "crowded"}
