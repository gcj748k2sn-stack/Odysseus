"""bench_sysmon.py: parsers for macOS command output, and the per-step summary.

The fixtures are the shapes macOS prints (M1, macOS 14/15); every parser must
return nothing, not raise, on output it does not recognise.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("bench_sysmon_under_test", ROOT / "scripts" / "bench_sysmon.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

TOP = """Processes: 512 total, 3 running, 509 sleeping, 2911 threads
2026/10/10 14:51:00
Load Avg: 3.10, 2.80, 2.50
CPU usage: 3.33% user, 8.88% sys, 87.77% idle
PhysMem: 15G used (2116M wired, 3087M compressor), 160M unused.

Processes: 512 total, 3 running, 509 sleeping, 2911 threads
2026/10/10 14:51:01
Load Avg: 3.10, 2.80, 2.50
CPU usage: 21.50% user, 4.25% sys, 74.25% idle
PhysMem: 15G used (2120M wired, 3100M compressor), 152M unused.
"""

VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                                5123.
Pages active:                            301234.
Pages occupied by compressor:             61440.
Pageins:                                9123456.
Pageouts:                                 45678.
Swapins:                                   1200.
Swapouts:                                  3400.
"""

IOREG = """+-o AGXAcceleratorG13X  <class AGXAcceleratorG13X, id 0x1000003a5, registered, matched, active, busy 0 (1 ms), retain 85>
    {
      "PerformanceStatistics" = {"In use system memory (driver)"=0,"Alloc system memory"=7314571264,"Tiler Utilization %"=12,"Renderer Utilization %"=97,"Device Utilization %"=98,"In use system memory"=8053063680}
    }
"""

PS = """ 8123456  92.5 /Users/x/BonsaiDemo/bin/llama-server -m models/b.gguf --alias bonsai2-27b
  412000   3.0 /Users/x/odysseus/venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 7000
  200000   0.5 /Applications/LM Studio.app/Contents/MacOS/LM Studio
  100000   1,5 /Users/x/.lmstudio/extensions/backends/llama.cpp/llmworker
   20000   0.1 /usr/bin/python3 scripts/bench_sysmon.py sample --out x
   10000   0.0 /bin/zsh
"""

POWERMETRICS = """Machine model: MacBookPro18,3

*** Sampled system activity (Sat Oct 10 14:51:00 2026 +0200) (10004.12ms elapsed) ***

**** Processor usage ****
CPU Power: 1520 mW
GPU Power: 14250 mW
ANE Power: 0 mW
Combined Power (CPU + GPU + ANE): 15770 mW

**** Thermal pressure ****
Current pressure level: Nominal

*** Sampled system activity (Sat Oct 10 14:51:10 2026 +0200) (10001.00ms elapsed) ***
CPU Power: 1000 mW
GPU Power: 9000 mW
Combined Power (CPU + GPU + ANE): 10000 mW
Current pressure level: Moderate
"""


def test_top_takes_the_last_sample():
    t = M.parse_top(TOP)
    assert t["cpu_busy"] == 25.75 and t["cpu_user"] == 21.5
    assert t["mem_used_mb"] == 15360 and t["wired_mb"] == 2120 and t["compressor_mb"] == 3100 and t["unused_mb"] == 152


def test_vm_stat_counters_and_compressed_memory():
    v = M.parse_vm_stat(VM_STAT)
    assert v == {"pageouts": 45678, "swapins": 1200, "swapouts": 3400, "compressed_mb": 960.0}


def test_swap():
    assert M.parse_swap("total = 2048.00M  used = 1037.25M  free = 1010.75M  (encrypted)") == \
        {"swap_total_mb": 2048.0, "swap_used_mb": 1037.2}
    assert M.parse_swap("total = 3.00G  used = 0.00M  free = 3.00G") == {"swap_total_mb": 3072.0, "swap_used_mb": 0.0}


def test_gpu_reads_device_utilisation_not_the_driver_field():
    assert M.parse_gpu(IOREG) == {"gpu_busy": 98.0, "gpu_renderer": 97.0, "gpu_mem_mb": 7680.0}


def test_thermal_and_battery():
    assert M.parse_therm("CPU_Scheduler_Limit \t= 100\nCPU_Available_CPUs \t= 10\nCPU_Speed_Limit \t= 72\n") == \
        {"cpu_speed_limit": 72}
    assert M.parse_therm("Note: No thermal warning level has been recorded\n") == {}
    assert M.parse_batt("Now drawing from 'AC Power'\n -InternalBattery-0 (id=4653155)\t87%; charging; 0:45 remaining present: true") == \
        {"power_source": "AC Power", "battery_pct": 87}


def test_processes_are_grouped_and_others_ignored():
    p = M.parse_ps(PS)
    assert p["bonsai"] == {"rss_mb": 7933.1, "cpu": 92.5}
    assert p["odysseus"]["rss_mb"] == 402.3
    assert p["lmstudio"] == {"rss_mb": 293.0, "cpu": 2.0}
    assert set(p) == {"bonsai", "odysseus", "lmstudio"}


def test_powermetrics_samples():
    s = M.parse_powermetrics(POWERMETRICS)
    assert [x["total_w"] for x in s] == [15.77, 10.0]
    assert s[0]["gpu_w"] == 14.25 and s[0]["thermal_pressure"] == "Nominal" and s[1]["thermal_pressure"] == "Moderate"


@pytest.mark.parametrize("parser", [M.parse_top, M.parse_vm_stat, M.parse_swap, M.parse_gpu,
                                    M.parse_therm, M.parse_batt, M.parse_ps, M.parse_powermetrics])
def test_unrecognised_output_gives_nothing(parser):
    assert not parser("") and not parser("command not found\n")


def test_summary_one_row_per_step_with_deltas_and_power():
    base = 1791636000.0
    samples = []
    for i in range(6):
        step = "qwen-agent-full" if i < 3 else "bonsai-research"
        samples.append({"epoch": base + 10 * i, "step": step, "cpu_busy": 10 * (i + 1), "gpu_busy": 50 + i,
                        "mem_free_pct": 40 - i, "swap_used_mb": 100 + 50 * i, "pageouts": 1000 + i * i,
                        "thermal_state": 1 if i == 4 else 0,
                        "procs": {"bonsai" if i >= 3 else "lmstudio": {"rss_mb": 8000 + i, "cpu": 90}}})
    table = M.summarize(samples, [{"epoch": base + 35, "total_w": 15.0}, {"epoch": base + 45, "total_w": 17.0}])
    lines = table.splitlines()
    assert len(lines) == 4
    qwen, bonsai = lines[2], lines[3]
    assert qwen.startswith("| qwen-agent-full | 0 | 20/30 | 51/52 | 38 | 200 (+100) | 4 | 0 | –/– | lmstudio 8002 |")
    assert bonsai.startswith("| bonsai-research | 0 | 50/60 | 54/55 | 35 | 350 (+100) | 16 | 1 | 16/17 | bonsai 8005 |")


def test_sample_once_never_raises_without_macos_tools(tmp_path):
    rec = M.sample_once("x")
    assert rec["step"] == "x" and "epoch" in rec
    M.main(["sample", "--out", str(tmp_path), "--interval", "1", "--count", "1"])
    M.main(["summary", str(tmp_path)])
    assert json.loads((tmp_path / "sysmon.jsonl").read_text().splitlines()[0])["step"] == "-"
