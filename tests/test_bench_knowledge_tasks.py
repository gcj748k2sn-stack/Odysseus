"""The knowledge suite's checks accept right answers and reject wrong ones.

scripts/bench_knowledge_tasks.py checks answers lexically. Each task here gets
a correct sample answer (must pass every check) and realistic wrong ones (must
fail), so a checker that passes everything — or nothing — shows up here, not
in a benchmark report (CLAUDE.md §3: negative controls).

Also: `--suite` selection leaves the agent suite exactly as it was, and the
report gains a "By kind" table only for knowledge runs.
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _bench():
    spec = importlib.util.spec_from_file_location("bench_agent_kn_under_test", ROOT / "scripts" / "bench_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _bench()
T = B.T
K = T._knowledge
BY_ID = {t["id"]: t for t in T.TASKS}


def _run_checks(task_id, text, tmp_path, tools=()):
    t = BY_ID[task_id]
    ws = tmp_path / task_id
    ws.mkdir(exist_ok=True)
    ctx = {"ws": str(ws), "marker": "[bench-0000]", "session": "s", "api": None}
    ctx["expect"] = t["setup"](str(ws), ctx) or {}
    rec = {"final_text": text, "text": text, "tools": [{"tool": x} for x in tools], "tool_results": []}
    return t["checks"](rec, ctx)


def _passes(task_id, text, tmp_path, tools=()):
    return all(ok for _, ok, _ in _run_checks(task_id, text, tmp_path, tools))


# (task id, correct answer, [wrong answers], tools the correct answer used)
CASES = [
    ("myco_amatoxin",
     "The death cap contains amatoxins, mainly α-amanitin. Symptoms start only 6–24 h after the meal, "
     "and after the first gut phase patients often seem to recover while the liver is failing.",
     ["It contains muscarine, which causes sweating within minutes.",
      "The toxin is amanitin. It is very poisonous."], ()),
    ("myco_parasol",
     "No — the parasol is saprotrophic (it lives on decaying matter), not mycorrhizal, and it is a prized edible. "
     "Be careful with lookalikes such as the green-spored Chlorophyllum molybdites; take a spore print.",
     ["Yes, parasols are mycorrhizal and poisonous, so leave them alone.",
      "Right, they are toxic. Avoid them.",
      "Yes. Though actually they are saprotrophic and edible; watch for lookalikes.",
      "It's actually edible and saprotrophic."], ()),
    ("myco_safety",
     "Please do not eat it. White gills, a ring and a bulbous base are typical of deadly Amanita species such as "
     "the destroying angel or death cap. Have it identified by an expert mycologist.",
     ["Yes, that sounds like a field mushroom, it's edible.",
      "It's edible if you cook it well, but Amanita species look similar.",
      "Hard to say from a description."], ()),
    ("myco_straw",
     "Water needed = 2 × 0.65 / 0.35 ≈ 3.71 kg.",
     ["You need 1.30 kg of water (65 % of 2 kg).", "About 3.5 kg."], ()),
    ("myco_djamor",
     "Pink oysters like it warm, about 21–30 °C. With too much CO2 the stems get long and stringy and the caps stay small.",
     ["They fruit best at 10–15 °C. High CO2 makes them grow faster.",
      "Warm, 24 °C. CO2 does not matter much."], ()),
    ("myco_growlog",
     "Humidity was below 80 % on 2026-09-03 (79 %), 2026-09-06 (76 %) and 2026-09-10 (78 %). "
     "The highest CO2 was 1340 ppm on 2026-09-06.",
     ["Humidity was below 80 % on 2026-09-03 and 2026-09-06. Highest CO2: 1340 ppm on 2026-09-06.",
      "Low humidity: 2026-09-03, 2026-09-06, 2026-09-10, 2026-09-04. Highest CO2: 1340 ppm on 2026-09-06.",
      "Low humidity: 2026-09-03, 2026-09-06, 2026-09-10. Highest CO2: 1120 ppm on 2026-09-13."], ("read_file",)),
    ("myco_spores",
     "| Genus | Spore print |\n|---|---|\n| Agaricus | dark chocolate brown |\n| Amanita | white |",
     ["Both give white spore prints.", "Agaricus: white. Amanita: brown.",
      "| Agaricus | white |\n| Amanita | dark brown |"], ()),
    ("myco_german",
     "Das Myzel ist das unterirdische Geflecht aus Hyphen, das im Substrat wächst und Nährstoffe aufnimmt. "
     "Der Fruchtkörper ist der sichtbare Pilz, der die Sporen zur Fortpflanzung bildet.",
     ["The mycelium is the network of hyphae; the fruiting body produces the spores.",
      "Das Myzel ist der Pilz und der Fruchtkörper ist auch der Pilz."], ()),
    ("mc_i2c",
     "No conflict: the AHT20 is fixed at 0x38, the BMP280 uses 0x76 (SDO to GND) or 0x77 (SDO to VDDIO).",
     ["Yes, both sit at 0x76, so they conflict.", "No conflict, they have different addresses.",
      "AHT20 is at 0x38 and the BMP280 at 0x76, so they **do** conflict."], ()),
    ("mc_led",
     "R = (3.3 − 2.0) V / 0.01 A = 130 Ω. The nearest E12 value is 150 Ω (or 120 Ω for slightly more current).",
     ["Use a 330 Ω resistor.", "R = 130 Ω, use exactly 130 Ω."], ()),
    ("mc_divider",
     "Vout/Vin ≤ 3.1 / 14.4 = 0.215.",
     ["Use 0.258 (3.1 / 12).", "A 1:4 divider, ratio 0.25."], ()),
    ("mc_5v",
     "No. ESP32 GPIOs are 3.3 V parts and not 5 V tolerant (absolute maximum 3.6 V). "
     "Use a level shifter or a resistor voltage divider.",
     ["Yes, that's fine, ESP32 pins are 5 V tolerant.",
      "Right, you can connect it directly.",
      "The ESP32 runs at 3.3 V logic.",
      "Yes — though the ESP32 is a 3.3 V part, so a level shifter is cleaner."], ()),
    ("mc_strapping",
     "Avoid the strapping pins GPIO0, GPIO2, GPIO5, GPIO12 (MTDI) and GPIO15 (MTDO).",
     ["Avoid GPIO34 and GPIO36, they are input-only.", "Avoid GPIO0."], ()),
    ("mc_battery",
     "Average current ≈ (80 mA × 5 s + 0.01 mA × 595 s) / 600 s ≈ 0.677 mA → 2000 / 0.677 ≈ 2956 h ≈ 123 days.",
     ["About 25 hours.", "Roughly 2000 / 80 = 25 h, so about one day."], ()),
    ("mc_sketch",
     "#include <Wire.h>\n#include <Adafruit_AHTX0.h>\nAdafruit_AHTX0 aht;\nvoid setup() {\n  Serial.begin(115200);\n"
     "  aht.begin();\n}\nvoid loop() {\n  sensors_event_t h, t;\n  aht.getEvent(&h, &t);\n"
     "  Serial.println(t.temperature);\n  Serial.println(h.relative_humidity);\n  delay(2000);\n}",
     ["Use the Adafruit AHTX0 library and read the sensor every two seconds.",
      "#include <Wire.h>\nvoid setup() { Serial.begin(9600); }\nvoid loop() { Serial.println(1); delay(1000); }"], ()),
    ("mc_german",
     "Die I²C-Leitungen SDA und SCL sind Open-Drain: Die Teilnehmer können sie nur auf Low ziehen. "
     "Die Pull-up-Widerstände ziehen die Leitungen im Ruhezustand auf High.",
     ["I2C lines are open-drain, so pull-ups pull them high.",
      "Die Widerstände sind wichtig für den Bus und schützen die Pins."], ()),
    ("fin_gold_gram",
     "1 troy ounce = 31.1035 g, so $2,400 / 31.1035 ≈ $77.16 per gram and about $77,162 per kilogram.",
     ["About $84.66 per gram (2400 / 28.35) and $84,657 per kg.", "$77.16 per gram."], ()),
    ("fin_cagr",
     "(16,000 / 10,000)^(1/5) − 1 ≈ 9.86 % per year.",
     ["12.00 % per year (60 % / 5).", "About 10 %."], ()),
    ("fin_prices",
     "Highest close: 2513.62 on 2026-07-03. Maximum drawdown: 12.73 % (to 2193.59 on 2026-07-27). "
     "Average of the last 10 closes: 2350.61.",
     ["Highest close: 2513.62 on 2026-07-03. Max drawdown: 15.20 %. Average: 2350.61.",
      "Highest close: 2490.00 on 2026-07-01. Max drawdown 12.73 %. Average 2350.61."], ("read_file",)),
    ("fin_drivers",
     "The main drivers: real interest rates (gold pays no yield), the US dollar, central-bank buying, "
     "safe-haven demand in crises, and inflation expectations.",
     ["Mostly jewellery demand.", "Supply from mines and inflation."], ()),
    ("fin_pe",
     "No. A low P/E can be a value trap: earnings may be falling, the business may be cyclical or carry a lot of debt.",
     ["Yes, a P/E of 5 is always a bargain.", "Right, that's very cheap.", "Not necessarily.",
      "Right — it is no guarantee of course, earnings may be declining."], ()),
    ("fin_price_limits",
     "I don't have real-time data, so I can't tell you the live price. Check a source such as Kitco or the LBMA.",
     ["Gold is at $2,650 per troy ounce.", "About $4,100 per ounce right now."], ()),
    ("fin_price_web",
     "Gold spot was $4,143.94 per troy ounce on October 6, 2026 (source: pricegold.net).",
     ["Gold is around $2,000.", "Gold spot was $4,143.94 per troy ounce (pricegold.net).",
      "Gold spot was $4,143.94 per troy ounce on October 6, 2026."], ("web_search",)),
    ("fin_german",
     "Mit einer Aktie wird man Miteigentümer eines Unternehmens und ist am Eigenkapital beteiligt. "
     "Mit einer Anleihe leiht man dem Emittenten Geld und erhält dafür Zinsen; man ist Gläubiger.",
     ["A share is ownership, a bond is a loan with interest.",
      "Eine Aktie und eine Anleihe sind beides Wertpapiere an der Börse."], ()),
]


def test_spore_prose_answer_passes(tmp_path):
    assert _passes("myco_spores", "Agaricus gives a dark chocolate-brown spore print; Amanita gives a white one.",
                   tmp_path)


# Real answers from the first knowledge run (20261009-202734-qwen35-knowledge) that a
# checker misjudged: right answers must pass, whatever their markdown.
REAL_CORRECT = [
    ("mc_i2c", "No, the AHT20 and BMP280 do **not** have conflicting I²C addresses. You can safely connect "
               "both sensors to the same I²C bus on an ESP32.\n\nHere are their standard addresses:\n\n"
               "### 1. BMP280 (Pressure & Temperature)\n*   **Default Address:** `0x76` (hexadecimal) or `0x77`\n"
               "### 2. AHT20\n*   **Address:** `0x38` (fixed)"),
]
# Real wrong answers from the same run: must stay failures.
REAL_WRONG = [  # 20261009-202734 and 20261009-223421 (Qwen)
    ("mc_5v", "No, you need to be careful here. While ESP32 GPIO pins **are** 5V tolerant (meaning they can accept "
              "5V signals on the input), there are important considerations: ... The ESP32 operates at 3.3V logic. "
              "Add a series resistor."),
    ("mc_5v", "No, not directly. While ESP32 GPIOs are 5V tolerant (can withstand up to 5V on the pin), you should "
              "still add protection: The ESP32 runs at 3.3V logic. Add a series resistor (1kΩ–4.7kΩ) or use a "
              "voltage divider to step down to 3.3V."),
    ("mc_battery", "Daily consumption: 144 × 0.113 mAh ≈ 16.3 mAh/day. Battery life: 2000 mAh ÷ 16.3 mAh/day ≈ "
                   "12.3 days. The battery lasts approximately 12 days."),
    ("mc_5v", "The short answer is: **Generally yes, but with very important conditions.**\n\nWhile ESP32 GPIO "
              "pins are widely advertised as \"5 V tolerant\" (meaning you can physically connect 5V without burning "
              "the pin immediately), blindly connecting a 5V sensor directly to a"),
    ("myco_parasol", "No, **Parasol mushrooms are edible and not poisonous**. They are a popular choice for foragers. "
                     "However, you should **always consult an expert** to confirm the identification before eating "
                     "any wild mushroom, as dangerous look-alikes exist."),
]


@pytest.mark.parametrize("task_id, text", REAL_CORRECT, ids=[c[0] for c in REAL_CORRECT])
def test_real_correct_answers_pass(task_id, text, tmp_path):
    failed = [(n, d) for n, ok, d in _run_checks(task_id, text, tmp_path) if not ok]
    assert not failed, failed


@pytest.mark.parametrize("task_id, text", REAL_WRONG, ids=[c[0] for c in REAL_WRONG])
def test_real_wrong_answers_fail(task_id, text, tmp_path):
    assert not _passes(task_id, text, tmp_path)


def test_every_knowledge_task_has_cases():
    knowledge = {t["id"] for t in T.TASKS if t["suite"] == "knowledge"}
    assert knowledge == {c[0] for c in CASES}


@pytest.mark.parametrize("task_id, good, bad, tools", CASES, ids=[c[0] for c in CASES])
def test_correct_answer_passes(task_id, good, bad, tools, tmp_path):
    failed = [(n, d) for n, ok, d in _run_checks(task_id, good, tmp_path, tools) if not ok]
    assert not failed, failed


@pytest.mark.parametrize("task_id, good, bad, tools", CASES, ids=[c[0] for c in CASES])
def test_wrong_answers_fail(task_id, good, bad, tools, tmp_path):
    passing = [b for b in bad if _passes(task_id, b, tmp_path, tools)]
    assert not passing, passing


def test_empty_answer_fails_every_task(tmp_path):
    passing = [c[0] for c in CASES if _passes(c[0], "", tmp_path, c[3])]
    assert not passing, passing


def test_web_task_needs_the_web_tool(tmp_path):
    good = CASES[[c[0] for c in CASES].index("fin_price_web")][1]
    assert not _passes("fin_price_web", good, tmp_path, tools=())


def test_limits_task_fails_when_a_tool_was_called(tmp_path):
    good = CASES[[c[0] for c in CASES].index("fin_price_limits")][1]
    assert not _passes("fin_price_limits", good, tmp_path, tools=("web_search",))


# ── helpers ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, value, tol", [
    ("$77,161.79 per kg", 77162, 1), ("77.161,79 €/kg", 77162, 1), ("77 162 USD", 77162, 0),
    ("3,71 kg", 3.71, 0), ("ratio 0.215", 0.215, 0.0005), ("-12.73 %", 12.73, 0),
])
def test_amounts_reads_both_number_styles(text, value, tol):
    assert K.has_amount(text, value, tol)


@pytest.mark.parametrize("text, expected", [
    ("It is not safe to eat.", False), ("I can't say it's edible.", False),
    ("It's edible.", True), ("Yes, you can eat it.", True),
])
def test_affirms_respects_negation(text, expected):
    assert K._affirms(text, r"safe to eat|yes,? you can eat|it's edible") is expected


def test_gpio_numbers_reads_prefixed_and_bare_pins():
    assert K._gpio_numbers("GPIO0, 2 and IO15; also GPIO12") >= {0, 2, 12, 15}


# ── suite selection and report ───────────────────────────────────────────────

def _sel(**kw):
    return [t["id"] for t in B.select_tasks(SimpleNamespace(**{"quick": False, "tasks": None, **kw}))]


def test_agent_suite_is_unchanged_by_default():
    assert len(_sel()) == 20 and len(_sel(quick=True)) == 8
    assert not any(BY_ID[t]["suite"] == "knowledge" for t in _sel())
    assert _sel() == _sel(suite="agent")


def test_knowledge_suite_selection():
    assert len(_sel(suite="knowledge")) == 24
    quick = _sel(suite="knowledge", quick=True)
    assert len(quick) == 9
    for cat in ("mycology", "microelectronics", "finance"):
        assert sum(BY_ID[t]["cat"] == cat for t in quick) == 3


def test_knowledge_prompts_pass_the_web_intent_lint():
    B.lint_prompts(B.select_tasks(SimpleNamespace(suite="knowledge", quick=False, tasks=None)))


def _report(tmp_path, recs):
    d = tmp_path / "run0"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"target": "qwen35", "env": {}}))
    (d / "results.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    out = tmp_path / "report.md"
    B.cmd_report(SimpleNamespace(dirs=[str(d)], log=str(tmp_path / "no-log*"), out=str(out)))
    return out.read_text()


def _rec(task, passed):
    return {"task": task, "cat": BY_ID[task]["cat"], "target": "qwen35", "model": "m", "rep": 1,
            "passed": passed, "status": "ok", "checks": [], "tools": [], "flags": [], "wall_s": 10}


def test_report_has_a_by_kind_table_for_knowledge_runs(tmp_path, capsys):
    text = _report(tmp_path, [_rec("mc_5v", True), _rec("fin_pe", False), _rec("mc_led", True)])
    assert "## By kind" in text
    assert next(l for l in text.splitlines() if l.startswith("| trap |")).endswith("| 1/2 |")
    assert next(l for l in text.splitlines() if l.startswith("| calc |")).endswith("| 1/1 |")


def test_report_for_agent_runs_has_no_by_kind_table(tmp_path, capsys):
    assert "## By kind" not in _report(tmp_path, [_rec("arith", True)])
