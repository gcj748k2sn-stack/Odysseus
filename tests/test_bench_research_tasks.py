"""The research suite's checks accept right answers and reject wrong ones (negative controls).

scripts/bench_research_tasks.py; same pattern as tests/test_bench_knowledge_tasks.py.
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bench_agent_res_under_test", ROOT / "scripts" / "bench_agent.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
T = B.T
R = T._research
BY_ID = {t["id"]: t for t in T.TASKS}
WEB = ("web_search",)


def _checks(task_id, text, tools=WEB):
    t = BY_ID[task_id]
    ctx = {"ws": "/x", "marker": "[bench-0000]", "session": "s", "api": None}
    ctx["expect"] = t["setup"]("/x", ctx) or {}
    rec = {"final_text": text, "text": text, "tools": [{"tool": x} for x in tools], "tool_results": []}
    return t["checks"](rec, ctx)


def _passes(task_id, text, tools=WEB):
    return all(ok for _, ok, _ in _checks(task_id, text, tools))


CASES = [
    ("res_esp32c3",
     "The ESP32-C3 has a **single-core** 32-bit **RISC-V** CPU running at up to **160 MHz** "
     "(source: https://www.elektormagazine.com/news/esp32-c3-risc-v-core).",
     ["The ESP32-C3 is a dual-core Xtensa LX6 at 240 MHz (https://espressif.com).",
      "Single-core RISC-V at 160 MHz.",
      "It has a dual-core RISC-V CPU at 160 MHz (https://example.com).",
      "It is dual-core; a single core is RISC-V and runs at 160 MHz (https://example.com)."]),
    ("res_gold2000",
     "Gold first broke above $2,000 per troy ounce in August 2020 (on 4 August), according to "
     "https://www.spglobal.com/...",
     ["Gold first passed $2,000 in March 2024 (https://example.com).",
      "In August 2020."]),
    ("res_towers",
     "The Berlin Fernsehturm is 368 m tall (incl. antenna) and the Eiffel Tower is 330 m since 2022, so the "
     "Fernsehturm is taller by 38 m. Sources: https://en.wikipedia.org/wiki/Fernsehturm_Berlin, "
     "https://en.wikipedia.org/wiki/Eiffel_Tower",
     ["The Eiffel Tower is 330 m and the Fernsehturm 368 m, so the Eiffel Tower is taller by 38 m "
      "(https://en.wikipedia.org).",
      "The Fernsehturm (368 m) is taller than the Eiffel Tower (330 m) by 38 m.",
      "The Fernsehturm is 365 m and the Eiffel Tower 300 m; the Fernsehturm is taller by 65 m (https://x.org)."]),
    ("res_djamor",
     "Pink oyster mushrooms grow wild in tropical and subtropical regions, on dead wood such as logs and palm "
     "trunks (https://en.wikipedia.org/wiki/Pleurotus_djamor).",
     ["They grow in cold boreal forests on soil (https://example.com).",
      "Tropical regions, on dead wood."]),
    ("res_gnats",
     "- Hang yellow sticky traps in the tent.\n- Put fine mesh over the air intakes.\n"
     "- Keep it clean and discard infested or spent blocks.\n- Use beneficial nematodes if larvae appear.\n\n"
     "Sources: https://lamycosphere.com/..., https://learn.hydrobuilder.com/...",
     ["- Hang yellow sticky traps.\n- Put mesh over intakes.\n- Keep it clean.\n\nSource: https://lamycosphere.com/x",
      "Use sticky traps and mesh. https://a.com https://b.com",
      "- Water more.\n- Add sugar.\n- Raise the temperature.\n\nhttps://a.com https://b.com"]),
]


def test_every_research_task_has_cases():
    assert {t["id"] for t in T.TASKS if t["suite"] == "research"} == {c[0] for c in CASES}


@pytest.mark.parametrize("task_id, good, bad", CASES, ids=[c[0] for c in CASES])
def test_correct_answer_passes(task_id, good, bad):
    failed = [(n, d) for n, ok, d in _checks(task_id, good) if not ok]
    assert not failed, failed


@pytest.mark.parametrize("task_id, good, bad", CASES, ids=[c[0] for c in CASES])
def test_wrong_answers_fail(task_id, good, bad):
    assert not [b for b in bad if _passes(task_id, b)]


@pytest.mark.parametrize("task_id, good, bad", CASES, ids=[c[0] for c in CASES])
def test_correct_answer_without_a_web_tool_fails(task_id, good, bad):
    assert not _passes(task_id, good, tools=())


def test_domains_counts_distinct_sites():
    assert R.domains("see https://www.a.com/x and https://a.com/y and http://b.org") == {"a.com", "b.org"}


def test_research_suite_selection():
    sel = B.select_tasks(SimpleNamespace(suite="research", quick=False, tasks=None))
    assert len(sel) == 5 and all(t["web"] for t in sel)
    assert len(B.select_tasks(SimpleNamespace(suite="research", quick=True, tasks=None))) == 3
    assert len(B.select_tasks(SimpleNamespace(suite="agent", quick=False, tasks=None))) == 20
