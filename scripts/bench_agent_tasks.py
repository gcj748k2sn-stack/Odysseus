"""Task suite for scripts/bench_agent.py — agent benchmark run THROUGH Odysseus.

Each task is a dict:
  id        short name, used in results and on the command line (--tasks)
  cat       category for the report: restraint | files | shell | web | odysseus | multistep | language
  quick     True → part of the --quick subset
  bash      send allow_bash=true for this turn
  web       send allow_web_search=true for this turn
  tools     tools the task is ABOUT. Used only for diagnostics ("was it offered?"),
            except where a check below requires one explicitly.
  setup     setup(ws, ctx) → dict of expected values. Writes fixtures into the
            workspace folder `ws`. Deterministic: same fixtures every run.
  prompt    prompt(ctx) → the user message. ctx["ws"] is the absolute workspace
            path, ctx["marker"] a unique tag like "[bench-3f9a]".
  checks    checks(rec, ctx) → list of (name, ok, detail). The task passes when
            every check passes. rec is the run record built by bench_agent.py:
              rec["final_text"]  visible text after the last tool result
              rec["text"]        all visible text of the turn
              rec["tools"]       [{"tool", "command", "round"}...] in call order
              rec["tool_results"][{"tool", "exit_code"}...]
  cleanup   optional cleanup(ctx) → removes what the task created through the API.

⚠️ PROMPT WORDING MATTERS. routes/chat_routes.py treats a message matching
WEB_INTENT_RE (below, copied from chat_stream) as an explicit web lookup and
DISABLES read_file/write_file/bash/notes/calendar for that turn. A file task
phrased "search the folder for…" would therefore fail for harness reasons, not
model reasons. bench_agent.py refuses to run a non-web task whose prompt matches.
Keep the copy in sync if chat_stream's regex changes.

Standard library only; Python 3.9+.
"""
import datetime as _dt
import json
import os
import random
import re

WEB_INTENT_RE = re.compile(
    r"\b(search|look\s*up|lookup|google|browse|web|online|latest|current|today|news|weather|forecast|rate|exchange\s+rate)\b",
    re.IGNORECASE,
)

# ── helpers ─────────────────────────────────────────────────────────────────

_NUM_RE = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)?(?![\w])")


def numbers_in(text):
    """All numbers in text; accepts a decimal comma (German style)."""
    out = []
    for m in _NUM_RE.finditer(text or ""):
        try:
            out.append(float(m.group(0).replace(",", ".")))
        except ValueError:
            pass
    return out


def has_number(text, value, tol=0.0):
    return any(abs(n - value) <= tol + 1e-9 for n in numbers_in(text))


def contains(text, needle):
    return needle.lower() in (text or "").lower()


def used_tool(rec, *names):
    return any(t.get("tool") in names for t in rec.get("tools", []))


def write(ws, rel, content):
    path = os.path.join(ws, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def read(ws, rel):
    try:
        with open(os.path.join(ws, rel), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def strip_fences(text):
    t = (text or "").strip()
    m = re.match(r"^```[a-zA-Z]*\s*\n(.*?)\n?```$", t, re.DOTALL)
    return m.group(1).strip() if m else t


def chk(name, ok, detail=""):
    return (name, bool(ok), detail)


# src/turn_report.py appends a closing report to the turn ("⚠️ **`python`
# failed** — …", "Ran `bash` — …", "Wrote N bytes …") whenever a side-effecting
# tool ran or failed — even a failure the model recovered from later in the
# turn (2026-10-07, Qwen json_output r2). That text is Odysseus's, not the
# model's, so checks see the reply without it; the runner keeps both.
_REPORT_LINE = re.compile(r"^(⚠️ \*\*`[\w.:-]+` failed\*\* — |⚠️ \*\*That file is empty\*\*|Ran `[\w.:-]+`|Wrote \d+ bytes )")


def split_turn_report(text):
    """(model_text, report) — report is the trailing block of report lines."""
    paras = (text or "").rstrip().split("\n\n")
    tail = []
    while len(paras) > 1 and all(_REPORT_LINE.match(l.strip()) for l in paras[-1].splitlines() if l.strip()):
        tail.insert(0, paras.pop())
    return "\n\n".join(paras).strip(), "\n\n".join(tail).strip()


def answered(rec):
    return chk("final answer not empty", (rec.get("final_text") or "").strip(),
               "empty final answer")


# ── shared fixtures ─────────────────────────────────────────────────────────

NODES = ["climalog-1", "climalog-2", "martha9"]


def make_sensors(ws):
    """36 rows, 3 nodes. Returns expected aggregates."""
    rng = random.Random(42)
    rows, start = [], _dt.datetime(2026, 9, 1, 6, 0)
    for i in range(12):
        for node in NODES:
            base_t = {"climalog-1": 21.0, "climalog-2": 18.5, "martha9": 24.0}[node]
            base_h = {"climalog-1": 48.0, "climalog-2": 61.0, "martha9": 86.0}[node]
            t = round(base_t + rng.uniform(-2.5, 2.5), 1)
            h = round(base_h + rng.uniform(-6, 6), 1)
            rows.append(((start + _dt.timedelta(hours=2 * i)).isoformat(timespec="minutes"), node, t, h))
    # one clear maximum, so "which node" has a single answer
    rows[29] = (rows[29][0], "martha9", rows[29][2], 97.3)
    assert rows[29][1] == "martha9"
    write(ws, "sensors.csv", "timestamp,node,temp_c,humidity\n" +
          "".join(f"{a},{b},{c},{d}\n" for a, b, c, d in rows))
    avg = {n: round(sum(r[2] for r in rows if r[1] == n) / 12, 2) for n in NODES}
    hmax = max(rows, key=lambda r: r[3])
    return {"rows": len(rows), "nodes": len(NODES), "avg_temp": avg,
            "max_h": hmax[3], "max_h_node": hmax[1]}


# ── tasks ───────────────────────────────────────────────────────────────────

TASKS = []


def task(**kw):
    kw.setdefault("bash", False)
    kw.setdefault("web", False)
    kw.setdefault("quick", False)
    kw.setdefault("tools", [])
    kw.setdefault("cleanup", None)
    TASKS.append(kw)


# 1 ─ restraint: no tools needed
task(
    id="arith", cat="restraint", quick=True,
    setup=lambda ws, ctx: {"answer": 391},
    prompt=lambda ctx: "What is 17 × 23? Reply with just the number.",
    checks=lambda rec, ctx: [
        answered(rec),
        chk("answer is 391", has_number(rec["final_text"], 391), rec["final_text"][:80]),
        chk("no tool calls", not rec["tools"], f"{len(rec['tools'])} tool calls"),
    ],
)

task(
    id="explain", cat="restraint",
    setup=lambda ws, ctx: {},
    prompt=lambda ctx: ("In at most three sentences: what is the difference between RAM and "
                        "flash memory on a microcontroller like the ESP32?"),
    checks=lambda rec, ctx: [
        answered(rec),
        chk("mentions volatility/power loss",
            re.search(r"volatil|power|persist|retain|keeps|lost|erase", rec["final_text"], re.I),
            "no mention of what survives a power cut"),
        chk("short (≤ 900 chars)", len(rec["final_text"]) <= 900, f"{len(rec['final_text'])} chars"),
        chk("no tool calls", not rec["tools"], f"{len(rec['tools'])} tool calls"),
    ],
)


# 2 ─ files (workspace)
task(
    id="read_fact", cat="files", quick=True, tools=["read_file"],
    setup=lambda ws, ctx: make_sensors(ws),
    prompt=lambda ctx: (f"Read {ctx['ws']}/sensors.csv. Which node recorded the highest humidity, "
                        "and what was the value?"),
    checks=lambda rec, ctx: [
        answered(rec),
        chk("value " + str(ctx["expect"]["max_h"]), has_number(rec["final_text"], ctx["expect"]["max_h"]),
            rec["final_text"][:120]),
        chk("node " + ctx["expect"]["max_h_node"], contains(rec["final_text"], ctx["expect"]["max_h_node"]),
            rec["final_text"][:120]),
    ],
)


def _setup_find(ws, ctx):
    rng = random.Random(7)
    words = "pump valve relay sensor shelf humidity spores agar tray mister fan filter".split()
    paths = ["notes/todo.txt", "notes/ideas.md", "docs/setup.md", "docs/archive/2025/old_notes.txt",
             "docs/archive/2025/parts.txt", "docs/archive/2024/log.txt", "firmware/README.md",
             "firmware/src/main.cpp", "firmware/src/sensors.h", "photos/captions.txt", "misc/links.txt",
             "misc/shopping.txt"]
    for p in paths:
        body = "\n".join(" ".join(rng.choice(words) for _ in range(9)) for _ in range(12)) + "\n"
        if p == "docs/archive/2025/old_notes.txt":
            lines = body.splitlines()
            lines.insert(7, "codeword: PERSEPHONE (do not share)")
            body = "\n".join(lines) + "\n"
        write(ws, p, body)
    return {"path": "docs/archive/2025/old_notes.txt"}


task(
    id="find_file", cat="files", tools=["grep", "glob", "bash", "ls", "read_file"],
    setup=_setup_find,
    prompt=lambda ctx: (f"Somewhere in the folder {ctx['ws']} there is a file that contains the codeword "
                        "PERSEPHONE. Which file is it? Give its path relative to that folder."),
    checks=lambda rec, ctx: [
        answered(rec),
        chk("names docs/archive/2025/old_notes.txt",
            "archive/2025/old_notes.txt" in rec["final_text"].replace("\\", "/"), rec["final_text"][:160]),
    ],
)


def _check_summary(rec, ctx):
    content = read(ctx["ws"], "summary.md")
    out = [chk("summary.md exists", content is not None, "file missing")]
    if content is None:
        return out
    for node, avg in ctx["expect"]["avg_temp"].items():
        line = next((l for l in content.splitlines() if node in l), "")
        out.append(chk(f"{node} avg ≈ {avg:.1f}", has_number(line, avg, tol=0.11), line.strip()[:100] or "node missing"))
    out.append(chk("is a markdown table", "|" in content and re.search(r"\|\s*:?-{3,}", content), "no table"))
    return out


task(
    id="write_file", cat="files", quick=True, tools=["write_file"],
    setup=lambda ws, ctx: make_sensors(ws),
    prompt=lambda ctx: (f"Using {ctx['ws']}/sensors.csv, create the file {ctx['ws']}/summary.md containing a "
                        "markdown table with one row per node and its average temp_c, rounded to one decimal."),
    checks=_check_summary,
)

CONFIG_BEFORE = """# martha9 chamber config
device: martha9
interval: 60
sensors:
  - aht20
  - bmp280
wifi:
  ssid: "lab"
  retries: 3
"""
CONFIG_AFTER = CONFIG_BEFORE.replace("interval: 60", "interval: 300")


def _norm(s):
    return "\n".join(l.rstrip() for l in (s or "").strip().splitlines())


task(
    id="edit_file", cat="files", quick=True, tools=["edit_file", "apply_patch", "write_file"],
    setup=lambda ws, ctx: (write(ws, "config.yaml", CONFIG_BEFORE), {})[1],
    prompt=lambda ctx: (f"In {ctx['ws']}/config.yaml change the interval from 60 to 300. "
                        "Leave everything else in the file exactly as it is."),
    checks=lambda rec, ctx: [
        chk("interval is 300", "interval: 300" in (read(ctx["ws"], "config.yaml") or ""), "not changed"),
        chk("rest unchanged", _norm(read(ctx["ws"], "config.yaml")) == _norm(CONFIG_AFTER),
            "other lines differ"),
    ],
)


def _setup_typo(ws, ctx):
    return make_sensors(ws)


task(
    id="recover_typo", cat="files", tools=["ls", "glob", "read_file"],
    setup=_setup_typo,
    prompt=lambda ctx: f"How many data rows are in {ctx['ws']}/sensor_data.csv (not counting the header)?",
    checks=lambda rec, ctx: [
        answered(rec),
        chk("recovers: answers 36 or points to sensors.csv",
            has_number(rec["final_text"], ctx["expect"]["rows"]) or contains(rec["final_text"], "sensors.csv"),
            rec["final_text"][:160]),
    ],
)


# 3 ─ shell
def _setup_log(ws, ctx):
    rng = random.Random(11)
    levels, n_err, lines = ["INFO", "DEBUG", "WARN", "ERROR"], 0, []
    for i in range(200):
        lvl = rng.choices(levels, weights=[60, 20, 12, 8])[0]
        msg = rng.choice(["sensor read ok", "retrying i2c", "wifi reconnect", "error budget fine",
                          "deep sleep 300s", "aht20 crc mismatch", "publish ok"])
        lines.append(f"2026-09-0{1 + i // 40} 0{i % 10}:{i % 60:02d}:00 {lvl} {msg}")
        n_err += lvl == "ERROR"
    write(ws, "log.txt", "\n".join(lines) + "\n")
    return {"errors": n_err}


task(
    id="shell_count", cat="shell", bash=True, tools=["bash"],
    setup=_setup_log,
    prompt=lambda ctx: (f"Use the shell to count how many lines in {ctx['ws']}/log.txt contain the exact "
                        "uppercase word ERROR. Reply with the number."),
    checks=lambda rec, ctx: [
        answered(rec),
        chk(f"answer is {ctx['expect']['errors']}", has_number(rec["final_text"], ctx["expect"]["errors"]),
            rec["final_text"][:80]),
        chk("used bash", used_tool(rec, "bash", "python"), "no shell tool call"),
    ],
)


# 4 ─ web
task(
    # Passable from memory (the year is well known) — it tests that the model
    # searches when told to, not that it reads. web_read tests reading.
    id="web_fact", cat="web", web=True, tools=["web_search"],
    setup=lambda ws, ctx: {},
    prompt=lambda ctx: "Search the web: in which year was the Eiffel Tower completed? Answer with the year.",
    checks=lambda rec, ctx: [
        answered(rec),
        chk("answer is 1889", has_number(rec["final_text"], 1889), rec["final_text"][:80]),
        chk("used web_search", used_tool(rec, "web_search"), "no web_search call"),
    ],
)

task(
    id="web_fetch", cat="web", web=True, tools=["web_fetch"],
    setup=lambda ws, ctx: {},
    prompt=lambda ctx: "Fetch https://example.com and tell me the exact text of its main heading.",
    checks=lambda rec, ctx: [
        answered(rec),
        chk("says 'Example Domain'", contains(rec["final_text"], "example domain"), rec["final_text"][:80]),
    ],
)

# Answerable only by reading the article body: the forest type and country
# behind Morchella elata are not the kind of detail a 9B/27B model carries.
# Added 2026-10-06 after item 49 (Wikipedia extracted as the site menu) was
# fixed — on the old extractor this task cannot pass, which is the point.
# Source text (extracted 2026-10-05 21:24, ~5,800 chars into the article, so
# inside web_fetch's 10,000-char output cap): "The seminal taxon Morchella
# elata ... was described by Elias Fries in 1822, from a fir forest in Sweden."
# If Wikipedia rewrites that sentence, update the checks.
# No "used web_fetch" check here or in web_fetch: Odysseus fetches every URL in
# the user's message itself before round 1 (src/chat_processor.py, first
# 10,000 chars, as untrusted context), so a model can answer correctly without
# calling the tool — Bonsai 2 did, 2026-10-06 21:38. Correctness still needs
# the page, which is what these tasks are for.
task(
    id="web_read", cat="web", quick=True, web=True, tools=["web_fetch"],
    setup=lambda ws, ctx: {"who": "Fries", "year": 1822, "forest": "fir", "country": "Sweden"},
    prompt=lambda ctx: ("Read the Wikipedia article https://en.wikipedia.org/wiki/Morchella and tell me: "
                        "who described Morchella elata, in which year, and in what kind of forest and "
                        "which country was it found?"),
    checks=lambda rec, ctx: [
        answered(rec),
        chk("fir forest", re.search(r"\bfir\b", rec["final_text"], re.I), rec["final_text"][:160]),
        chk("Sweden", contains(rec["final_text"], "swed"), rec["final_text"][:160]),
        chk("Fries, 1822", contains(rec["final_text"], "fries") and has_number(rec["final_text"], 1822),
            rec["final_text"][:160]),
    ],
)


# 5 ─ Odysseus features (verified through the API, removed afterwards)
# Checks match the run's exact marker; cleanup matches any "[bench-" so an
# item whose marker the model mistyped is still removed (2026-10-05: Qwen
# wrote "[bench-44b]" for "[bench-44b6]" and the note was left behind).
# Runs are sequential, so no other run's items can be caught by it.
# 2026-10-07: Qwen dropped the brackets ("bench-2d22 Dentist"), so the loose
# match is a pattern, not the "[bench-" prefix.
BENCH_RE = re.compile(r"\[?bench-[0-9a-f]{3,4}\]?")


def _tagged(text, ctx, loose):
    return bool(BENCH_RE.search(text or "")) if loose else ctx["marker"] in (text or "")


def _find_notes(ctx, loose=False):
    try:
        notes = ctx["api"].get("/api/notes").get("notes", [])
    except Exception:
        return []
    return [n for n in notes if _tagged((n.get("title") or "") + (n.get("content") or ""), ctx, loose)]


def _note_ids(ctx):
    try:
        return {n["id"] for n in ctx["api"].get("/api/notes").get("notes", [])}
    except Exception:
        return set()


def _check_note(rec, ctx):
    """Exact title and content are separate checks, so a mistyped marker
    (2026-10-05: "[bench-44b]" for "[bench-44b6]") still shows whether the
    note itself was right. Only notes created during this run are looked at."""
    exact = _find_notes(ctx)
    before = ctx.get("notes_before", set())
    near = [n for n in _find_notes(ctx, loose=True)
            if n["id"] not in before and "workshop shopping" in (n.get("title") or "").lower()]
    note = (exact or near or [None])[0]
    out = [chk("note created (via /api/notes)", note, "no new note titled '… Workshop shopping'"),
           chk("title copied exactly", exact,
               f"title was {note.get('title')!r}" if note else "")]
    if note:
        blob = json.dumps(note, ensure_ascii=False).lower()
        for item in ("pla filament", "m3 screws", "isopropyl alcohol"):
            out.append(chk(f"has item '{item}'", item in blob, "missing"))
    return out


def _cleanup_note(ctx):
    for n in _find_notes(ctx, loose=True):
        ctx["api"].delete(f"/api/notes/{n['id']}")


task(
    id="note_create", cat="odysseus", quick=True, tools=["manage_notes"],
    setup=lambda ws, ctx: (ctx.__setitem__("notes_before", _note_ids(ctx)), {})[1],
    prompt=lambda ctx: (f'Create a checklist note titled "{ctx["marker"]} Workshop shopping" with three items: '
                        "PLA filament, M3 screws, isopropyl alcohol."),
    checks=_check_note, cleanup=_cleanup_note,
)


def _event_day(ctx):
    d = _dt.date.today() + _dt.timedelta(days=7)
    return d


def _local(s):
    """Parse an /api/calendar dtstart into a naive LOCAL datetime."""
    base = _dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    if s.endswith("Z"):
        base = base.replace(tzinfo=_dt.timezone.utc).astimezone().replace(tzinfo=None)
    return base


def _find_events(ctx, loose=False):
    d = _event_day(ctx)
    try:
        evs = ctx["api"].get("/api/calendar/events", params={
            "start": (d - _dt.timedelta(days=3)).isoformat() + "T00:00:00",
            "end": (d + _dt.timedelta(days=4)).isoformat() + "T00:00:00"}).get("events", [])
    except Exception:
        return []
    return [e for e in evs if _tagged(e.get("summary"), ctx, loose)]


def _check_event(rec, ctx):
    """Exact title and the event itself are separate checks, as in note_create
    (2026-10-07: Qwen created "bench-2d22 Dentist" for "[bench-2d22] Dentist")."""
    exact = _find_events(ctx)
    before = ctx.get("events_before", set())
    near = [e for e in _find_events(ctx, loose=True)
            if e["uid"] not in before and "dentist" in (e.get("summary") or "").lower()]
    ev = (exact or near or [None])[0]
    out = [chk("event created (via /api/calendar/events)", ev, "no new event titled '… Dentist'"),
           chk("title copied exactly", exact, f"title was {ev.get('summary')!r}" if ev else "")]
    if ev:
        e, d = ev, _event_day(ctx)
        try:
            s, en = _local(e["dtstart"]), _local(e["dtend"])
            out.append(chk(f"starts {d} 14:00", s.date() == d and (s.hour, s.minute) == (14, 0), e["dtstart"]))
            out.append(chk("ends 15:00", (en.hour, en.minute) == (15, 0), e["dtend"]))
        except Exception as ex:
            out.append(chk("parsable times", False, repr(ex)))
    return out


def _cleanup_event(ctx):
    for e in _find_events(ctx, loose=True):
        ctx["api"].delete(f"/api/calendar/events/{e['uid']}")


task(
    id="calendar_create", cat="odysseus", tools=["manage_calendar"],
    setup=lambda ws, ctx: (ctx.__setitem__("events_before", {e["uid"] for e in _find_events(ctx, loose=True)}), {})[1],
    prompt=lambda ctx: (f'Add a calendar event "{ctx["marker"]} Dentist" on '
                        f'{_event_day(ctx).strftime("%A, %d %B %Y")} from 14:00 to 15:00.'),
    checks=_check_event, cleanup=_cleanup_event,
)


def _find_docs(ctx, loose=False):
    try:
        docs = ctx["api"].get(f"/api/documents/{ctx['session']}")
    except Exception:
        return []
    return [d for d in docs or [] if _tagged(d.get("title"), ctx, loose)]


def _check_doc(rec, ctx):
    docs = _find_docs(ctx)
    out = [chk("document exists (via /api/documents)", docs, "no document with the marker in its title")]
    if docs:
        body = docs[0].get("current_content") or ""
        bullets = [l for l in body.splitlines() if re.match(r"^\s*([-*•]|\d+[.)])\s+\S", l)]
        out.append(chk("exactly 5 list items", len(bullets) == 5, f"{len(bullets)} items"))
    return out


def _cleanup_doc(ctx):
    for d in _find_docs(ctx, loose=True):
        ctx["api"].delete(f"/api/document/{d['id']}")


task(
    id="document_create", cat="odysseus", tools=["create_document"],
    setup=lambda ws, ctx: {},
    prompt=lambda ctx: (f'Create a document titled "{ctx["marker"]} Packing list" containing a bullet list of '
                        "exactly five items for a weekend hiking trip."),
    checks=_check_doc, cleanup=_cleanup_doc,
)


# 6 ─ multi-step
PRICES = {"pla_spool": 21.90, "m3_screws_100": 6.49, "aht20": 4.20, "esp32_c3": 5.95}
ORDER = [(2, "pla_spool"), (3, "aht20"), (4, "esp32_c3"), (1, "m3_screws_100")]


def _setup_order(ws, ctx):
    write(ws, "prices.json", json.dumps(PRICES, indent=2) + "\n")
    write(ws, "order.txt", "".join(f"{q} x {k}\n" for q, k in ORDER))
    return {"total": round(sum(q * PRICES[k] for q, k in ORDER), 2)}


task(
    id="multi_step", cat="multistep", quick=True, tools=["read_file", "write_file"],
    setup=_setup_order,
    prompt=lambda ctx: (f"{ctx['ws']}/order.txt lists quantities and item keys; {ctx['ws']}/prices.json has the "
                        f"unit prices in EUR. Compute the order total and write it to {ctx['ws']}/total.txt — "
                        "the file must contain only the number with two decimals."),
    checks=lambda rec, ctx: [
        chk("total.txt exists", read(ctx["ws"], "total.txt") is not None, "file missing"),
        chk(f"total.txt is {ctx['expect']['total']:.2f}",
            re.fullmatch(r"\s*%s\s*(EUR|€)?\s*" % re.escape(f"{ctx['expect']['total']:.2f}").replace(r"\.", "[.,]"),
                         read(ctx["ws"], "total.txt") or ""),
            repr((read(ctx["ws"], "total.txt") or "")[:40])),
    ],
)


def _setup_long(ws, ctx):
    rng = random.Random(5)
    rooms = ["attic", "garage", "kitchen", "bathroom", "hallway", "office", "bedroom", "garden shed"]
    things = ["fan", "heater", "smoke detector", "router", "light fixture", "thermostat", "pump", "boiler"]
    filler = ("Checked the seals, cleaned the filter, and noted the reading in the logbook. "
              "Nothing unusual; next inspection as scheduled. ")
    entries = []
    for i in range(110):
        room, thing = rng.choice(rooms), rng.choice(things)
        serial = f"{thing[:2].upper()}-{rng.randint(1000, 9999)}-{rng.choice('ABCDEFGH')}{rng.choice('QRSTUVWX')}"
        entries.append(f"## Entry {i + 1}: {room}\n{room.capitalize()} {thing} serviced, serial number {serial}. "
                       + filler * rng.randint(1, 3) + "\n")
    # The needle sits past read_file's 20,000-char cap, so reading the whole
    # file once is not enough: the model has to page, grep, or follow the
    # truncation notice.
    text, pos = "", 0
    for i, e in enumerate(entries):
        text += e
        if not pos and len(text) > 26000:
            pos = i
            text += ("## Entry %d: cellar\nCellar dehumidifier installed, serial number DH-4471-QX. "
                     % (i + 1)) + filler + "\n"
    write(ws, "house_log.md", "# House maintenance log\n\n" + text)
    return {"serial": "DH-4471-QX", "chars": len(text)}


task(
    id="long_file", cat="multistep", tools=["read_file", "grep", "bash"],
    setup=_setup_long,
    prompt=lambda ctx: f"What is the serial number of the dehumidifier in the cellar? It's in {ctx['ws']}/house_log.md.",
    checks=lambda rec, ctx: [
        answered(rec),
        chk("serial DH-4471-QX", contains(rec["final_text"], "DH-4471-QX"), rec["final_text"][:120]),
    ],
)


# 7 ─ language / format
TERMINE = """Termine Herbst 2026
- 14.11.2026, 09:30 — Steuerberater (Unterlagen mitnehmen)
- 28.10.2026, 16:00 — Elternabend
- 03.11.2026, 08:15 — Zahnarzt
- 21.10.2026, 11:00 — TÜV Auto
- 09.12.2026, 18:00 — Weihnachtsfeier Büro
"""


task(
    id="german", cat="language", quick=True, tools=["read_file"],
    setup=lambda ws, ctx: (write(ws, "termine.txt", TERMINE), {"answer": "TÜV"})[1],
    prompt=lambda ctx: (f"Welcher Termin in {ctx['ws']}/termine.txt liegt am frühesten? "
                        "Antworte auf Deutsch in einem Satz."),
    checks=lambda rec, ctx: [
        answered(rec),
        chk("names TÜV (21.10.)", re.search(r"T[ÜU]E?V", rec["final_text"], re.I), rec["final_text"][:120]),
        chk("answers in German",
            len(re.findall(r"\b(der|die|das|ist|am|um|Termin|früheste[nr]?|liegt|und)\b", rec["final_text"], re.I)) >= 2,
            rec["final_text"][:120]),
    ],
)


def _check_json(rec, ctx):
    raw = rec["final_text"].strip()
    obj, prose = None, False
    try:
        obj = json.loads(strip_fences(raw))
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)       # JSON wrapped in prose?
        try:
            obj, prose = (json.loads(m.group(0)), True) if m else (None, False)
        except Exception:
            obj = None
    if obj is None:
        return [answered(rec), chk("valid JSON", False, raw[:120])]
    return [
        chk("valid JSON", True),
        chk("no prose around it", not prose, raw[:60]),
        chk("rows = 36", isinstance(obj, dict) and obj.get("rows") == ctx["expect"]["rows"], str(obj)[:80]),
        chk("nodes = 3", isinstance(obj, dict) and obj.get("nodes") == ctx["expect"]["nodes"], str(obj)[:80]),
    ]


task(
    id="json_output", cat="language", tools=["read_file"],
    setup=lambda ws, ctx: make_sensors(ws),
    prompt=lambda ctx: (f"Read {ctx['ws']}/sensors.csv. Reply with ONLY a JSON object of the form "
                        '{"rows": <number of data rows>, "nodes": <number of distinct nodes>} and nothing else.'),
    checks=_check_json,
)


TASK_IDS = [t["id"] for t in TASKS]
assert len(TASK_IDS) == len(set(TASK_IDS)), "duplicate task id"
