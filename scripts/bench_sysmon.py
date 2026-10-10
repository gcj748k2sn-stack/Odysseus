#!/usr/bin/env python3
"""Record what the Mac was doing while a benchmark chain ran.

    python3 scripts/bench_sysmon.py env     --out DIR                 # machine snapshot -> DIR/env.json
    python3 scripts/bench_sysmon.py sample  --out DIR [--interval 10] [--until-pid PID]
    python3 scripts/bench_sysmon.py summary DIR                       # per-step table (markdown)

`sample` appends one JSON line per interval to DIR/sysmon.jsonl: CPU and GPU
utilisation, load, memory free, wired/compressed memory, swap, page-outs,
thermal state (0 nominal … 3 critical), power source and battery, and memory/CPU of the model
servers and Odysseus. The step being run is read from DIR/current_step
(bench_chain.sh writes it). It stops when --until-pid exits, so it never
outlives the chain.

No sudo needed. Power draw in watts needs `powermetrics` (root); bench_chain.sh
runs it when BENCH_POWER=1 and `summary` reads DIR/powermetrics.txt if present.
macOS only for the real numbers; every command that fails just leaves its
fields out, so the script never stops the chain.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# ── parsers (pure, tested with captured macOS output) ─────────────────────

_UNIT = {"K": 1 / 1024, "M": 1.0, "G": 1024.0, "T": 1024.0 * 1024}


def _mb(num: str, unit: str) -> float:
    return round(float(num) * _UNIT.get(unit.upper(), 1.0), 1)


def parse_top(text: str) -> Dict[str, float]:
    """`top -l 2 -n 0 -s 1`: the last sample's CPU split and PhysMem line."""
    out: Dict[str, float] = {}
    cpu = re.findall(r"CPU usage:\s*([\d.]+)% user,\s*([\d.]+)% sys,\s*([\d.]+)% idle", text)
    if cpu:
        user, sys_, idle = (float(x) for x in cpu[-1])
        out.update(cpu_user=user, cpu_sys=sys_, cpu_busy=round(100 - idle, 2))
    mem = re.findall(r"PhysMem:\s*([\d.]+)([KMGT]) used \(([\d.]+)([KMGT]) wired(?:,\s*([\d.]+)([KMGT]) compressor)?\),\s*([\d.]+)([KMGT]) unused", text)
    if mem:
        m = mem[-1]
        out.update(mem_used_mb=_mb(m[0], m[1]), wired_mb=_mb(m[2], m[3]), unused_mb=_mb(m[6], m[7]))
        if m[4]:
            out["compressor_mb"] = _mb(m[4], m[5])
    return out


def parse_vm_stat(text: str) -> Dict[str, int]:
    """Cumulative paging counters; `summary` turns them into per-step deltas."""
    page = re.search(r"page size of (\d+) bytes", text)
    size = int(page.group(1)) if page else 16384
    out: Dict[str, int] = {}
    for key, label in (("pageouts", "Pageouts"), ("swapins", "Swapins"), ("swapouts", "Swapouts"),
                       ("compressor_pages", "Pages occupied by compressor")):
        m = re.search(rf"^{label}:\s+(\d+)\.", text, re.M)
        if m:
            out[key] = int(m.group(1))
    if "compressor_pages" in out:
        out["compressed_mb"] = round(out.pop("compressor_pages") * size / 1048576, 1)
    return out


def parse_swap(text: str) -> Dict[str, float]:
    """`sysctl -n vm.swapusage`."""
    m = re.search(r"total = ([\d.]+)([KMGT])\s+used = ([\d.]+)([KMGT])", text)
    return {"swap_total_mb": _mb(m.group(1), m.group(2)), "swap_used_mb": _mb(m.group(3), m.group(4))} if m else {}


def parse_gpu(text: str) -> Dict[str, float]:
    """`ioreg -r -d 1 -w 0 -c IOAccelerator`: Apple GPU utilisation without root."""
    out: Dict[str, float] = {}
    for key, label in (("gpu_busy", "Device Utilization %"), ("gpu_renderer", "Renderer Utilization %")):
        m = re.search(rf'"{re.escape(label)}"\s*=\s*(\d+)', text)
        if m:
            out[key] = float(m.group(1))
    m = re.search(r'"In use system memory"\s*=\s*(\d+)', text)
    if m:
        out["gpu_mem_mb"] = round(int(m.group(1)) / 1048576, 1)
    return out


def parse_therm(text: str) -> Dict[str, object]:
    """`pmset -g therm`: macOS lowers CPU_Speed_Limit below 100 when it throttles."""
    out: Dict[str, object] = {}
    m = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", text)
    if m:
        out["cpu_speed_limit"] = int(m.group(1))
    m = re.search(r"thermal warning level.*?(\d+|has been recorded)", text, re.I)
    if m and m.group(1).isdigit():
        out["thermal_warning"] = int(m.group(1))
    return out


def parse_batt(text: str) -> Dict[str, object]:
    """`pmset -g batt`."""
    out: Dict[str, object] = {}
    m = re.search(r"drawing from '([^']+)'", text)
    if m:
        out["power_source"] = m.group(1)
    m = re.search(r"(\d+)%;", text)
    if m:
        out["battery_pct"] = int(m.group(1))
    return out


_GROUPS = (
    ("bonsai", lambda a: "llama-server" in a),
    ("lmstudio", lambda a: "lm studio" in a or "lmstudio" in a or "/.lmstudio/" in a),
    ("odysseus", lambda a: "uvicorn app:app" in a),
    ("chroma", lambda a: "chroma run" in a),
    ("searxng", lambda a: "searx" in a),
    ("ollama", lambda a: "ollama" in a),
)


def parse_ps(text: str) -> Dict[str, Dict[str, float]]:
    """`ps -A -o rss=,%cpu=,args=`, summed per program we care about (RSS in MB)."""
    out: Dict[str, Dict[str, float]] = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            rss_kb, cpu = int(parts[0]), float(parts[1].replace(",", "."))
        except ValueError:
            continue
        args = parts[2].lower()
        for name, match in _GROUPS:
            if match(args):
                g = out.setdefault(name, {"rss_mb": 0.0, "cpu": 0.0})
                g["rss_mb"] = round(g["rss_mb"] + rss_kb / 1024, 1)
                g["cpu"] = round(g["cpu"] + cpu, 1)
                break
    return out


_PM_HEAD = re.compile(r"\*\*\* Sampled system activity \((.+?)\) \(([\d.]+)ms elapsed\) \*\*\*")


def parse_powermetrics(text: str) -> List[Dict[str, object]]:
    """`powermetrics --samplers cpu_power,gpu_power,thermal` text output, one dict per sample."""
    samples = []
    heads = list(_PM_HEAD.finditer(text))
    for i, h in enumerate(heads):
        body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        try:
            ts = _dt.datetime.strptime(h.group(1), "%a %b %d %H:%M:%S %Y %z").timestamp()
        except ValueError:
            continue
        s: Dict[str, object] = {"epoch": ts}
        for key, label in (("cpu_w", "CPU Power"), ("gpu_w", "GPU Power"), ("ane_w", "ANE Power"),
                           ("total_w", r"Combined Power \(CPU \+ GPU \+ ANE\)")):
            m = re.search(rf"^{label}:\s*(\d+)\s*mW", body, re.M)
            if m:
                s[key] = round(int(m.group(1)) / 1000, 2)
        m = re.search(r"Current pressure level:\s*(\w+)", body)
        if m:
            s["thermal_pressure"] = m.group(1)
        samples.append(s)
    return samples


# ── sampling ──────────────────────────────────────────────────────────────

def _run(cmd: List[str], timeout: float = 8) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


# NSProcessInfo.thermalState: the same signal apps get, no root needed on Apple Silicon
_THERMAL_JXA = "ObjC.import('Foundation'); $.NSProcessInfo.processInfo.thermalState"


def sample_once(step: str) -> Dict[str, object]:
    now = time.time()
    s: Dict[str, object] = {"t": _dt.datetime.fromtimestamp(now).isoformat(timespec="seconds"),
                            "epoch": round(now, 1), "step": step}
    s.update(parse_top(_run(["top", "-l", "2", "-n", "0", "-s", "1"])))
    s.update(parse_vm_stat(_run(["vm_stat"])))
    s.update(parse_swap(_run(["sysctl", "-n", "vm.swapusage"])))
    level = _run(["sysctl", "-n", "kern.memorystatus_level"]).strip()
    if level.isdigit():
        s["mem_free_pct"] = int(level)          # what macOS's memory pressure graph shows, inverted
    s.update(parse_gpu(_run(["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"])))
    s.update(parse_therm(_run(["pmset", "-g", "therm"])))
    state = _run(["osascript", "-l", "JavaScript", "-e", _THERMAL_JXA]).strip()
    if state.isdigit():
        s["thermal_state"] = int(state)         # 0 nominal, 1 fair, 2 serious, 3 critical
    s.update(parse_batt(_run(["pmset", "-g", "batt"])))
    try:
        s["load1"] = round(os.getloadavg()[0], 2)
    except OSError:
        pass
    procs = parse_ps(_run(["ps", "-A", "-o", "rss=,%cpu=,args="]))
    if procs:
        s["procs"] = procs
    return s


def _alive(pid: Optional[int]) -> bool:
    if not pid:
        return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def cmd_sample(args) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    step_file = out / "current_step"
    path = out / "sysmon.jsonl"
    while _alive(args.until_pid):
        t0 = time.time()
        try:
            step = step_file.read_text().strip() if step_file.exists() else "-"
        except OSError:
            step = "-"
        try:
            rec = sample_once(step or "-")
            with path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception as e:                    # never take the chain down
            print(f"sysmon: sample failed: {e}", file=sys.stderr)
        if args.count and sum(1 for _ in path.open()) >= args.count:
            return
        time.sleep(max(1.0, args.interval - (time.time() - t0)))


def cmd_env(args) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    env = {
        "taken": _dt.datetime.now().isoformat(timespec="seconds"),
        "macos": _run(["sw_vers", "-productVersion"]).strip(),
        "model": _run(["sysctl", "-n", "hw.model"]).strip(),
        "chip": _run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip(),
        "cores": _run(["sysctl", "-n", "hw.ncpu"]).strip(),
        "perf_cores": _run(["sysctl", "-n", "hw.perflevel0.physicalcpu"]).strip(),
        "mem_gb": round(int(_run(["sysctl", "-n", "hw.memsize"]).strip() or 0) / 2**30, 1),
        "gpu_wired_limit_mb": _run(["sysctl", "-n", "iogpu.wired_limit_mb"]).strip(),
        "low_power_mode": _run(["pmset", "-g"]).count("lowpowermode         1") > 0,
        **parse_batt(_run(["pmset", "-g", "batt"])),
        **parse_swap(_run(["sysctl", "-n", "vm.swapusage"])),
        "uptime": _run(["uptime"]).strip(),
    }
    (out / "env.json").write_text(json.dumps(env, indent=2))


# ── summary ───────────────────────────────────────────────────────────────

def _avg(xs):
    return round(statistics.fmean(xs), 1) if xs else None


def _fmt(v, suffix=""):
    return "–" if v is None else f"{v:g}{suffix}"


def summarize(samples: List[Dict[str, object]], power: List[Dict[str, object]]) -> str:
    steps: List[str] = []
    by: Dict[str, List[Dict[str, object]]] = {}
    for s in samples:
        name = str(s.get("step") or "-")
        if name not in by:
            steps.append(name)
            by[name] = []
        by[name].append(s)
    rows = ["| step | min | CPU avg/max % | GPU avg/max % | mem free min % | swap max MB (+Δ) | page-outs Δ | thermal max | W avg/max | top RSS MB |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for name in steps:
        ss = by[name]
        if name == "-" and len(ss) < 2:
            continue
        t0, t1 = ss[0]["epoch"], ss[-1]["epoch"]

        def col(key):
            return [s[key] for s in ss if isinstance(s.get(key), (int, float))]

        def delta(key):
            v = col(key)
            return (v[-1] - v[0]) if len(v) >= 2 else None

        cpu, gpu, free, swap = col("cpu_busy"), col("gpu_busy"), col("mem_free_pct"), col("swap_used_mb")
        therm = col("thermal_state")
        watts = [p["total_w"] for p in power if t0 <= p["epoch"] <= t1 and "total_w" in p]
        rss: Dict[str, float] = {}
        for s in ss:
            for proc, v in (s.get("procs") or {}).items():
                rss[proc] = max(rss.get(proc, 0.0), v.get("rss_mb", 0.0))
        top = ", ".join(f"{k} {v:.0f}" for k, v in sorted(rss.items(), key=lambda kv: -kv[1])[:2])
        swap_d = delta("swap_used_mb")
        rows.append("| " + " | ".join([
            name, f"{(t1 - t0) / 60:.0f}",
            f"{_fmt(_avg(cpu))}/{_fmt(max(cpu) if cpu else None)}",
            f"{_fmt(_avg(gpu))}/{_fmt(max(gpu) if gpu else None)}",
            _fmt(min(free) if free else None),
            "–" if not swap else f"{max(swap):g} ({'+' if (swap_d or 0) >= 0 else ''}{_fmt(swap_d)})",
            _fmt(delta("pageouts")),
            _fmt(max(therm) if therm else None),
            f"{_fmt(_avg(watts))}/{_fmt(max(watts) if watts else None)}",
            top or "–",
        ]) + " |")
    return "\n".join(rows)


def cmd_summary(args) -> None:
    d = Path(args.dir)
    samples = []
    if (d / "sysmon.jsonl").exists():
        for line in (d / "sysmon.jsonl").read_text().splitlines():
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    power = parse_powermetrics((d / "powermetrics.txt").read_text(errors="replace")) \
        if (d / "powermetrics.txt").exists() else []
    if not samples:
        print("sysmon: no samples")
        return
    table = summarize(samples, power)
    (d / "sysmon-summary.md").write_text(table + "\n")
    print(table)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("sample")
    a.add_argument("--out", required=True)
    a.add_argument("--interval", type=float, default=10)
    a.add_argument("--until-pid", type=int)
    a.add_argument("--count", type=int, default=0, help="stop after N samples in the file (testing)")
    a.set_defaults(func=cmd_sample)
    e = sub.add_parser("env")
    e.add_argument("--out", required=True)
    e.set_defaults(func=cmd_env)
    s = sub.add_parser("summary")
    s.add_argument("dir")
    s.set_defaults(func=cmd_summary)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
