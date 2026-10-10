"""Research suite for scripts/bench_agent.py (`--suite research`): web research by the chat model.

Not Odysseus's deep-research job (`trigger_research`): that runs on the research
model (Qwen in LM Studio), which is down while Bonsai runs. These tasks test the
chat model itself: search, read, combine several facts, cite sources. Kinds:
  lookup     one fact cluster from the web, with a source link
  compare    two lookups combined into a comparison
  synthesis  advice gathered from several sites, at least two cited

Answer keys checked 2026-10-10: ESP32-C3 is single-core RISC-V at 160 MHz
(Elektor); gold spot first above $2,000/oz on 4 Aug 2020 (S&P Global); Berlin
Fernsehturm 368 m incl. antenna, Eiffel Tower 330 m since the March 2022 antenna
(Wikipedia; older sources say 324 m, accepted); Pleurotus djamor grows in
tropical and subtropical areas (Wikipedia); fungus-gnat measures: yellow sticky
traps, mesh on air intakes, hygiene/removing old blocks, UV traps, nematodes
(La Mycosphère). Checks are lexical; good and bad sample answers are in
tests/test_bench_research_tasks.py.
"""
import re

_URL_RE = re.compile(r"https?://(?:www\.)?([a-z0-9.-]+\.[a-z]{2,})", re.I)


def domains(text):
    """Distinct cited domains, written as links."""
    return {m.group(1).lower() for m in _URL_RE.finditer(text or "")}


def _rx(pattern, text):
    return re.search(pattern, text or "", re.I | re.S)


def _plain(rec):
    return re.sub(r"\*\*|__", "", rec.get("final_text") or "")


def register(task, chk, answered, used_tool):
    def r(**kw):
        kw.setdefault("workspace", False)
        task(suite="research", web=True, tools=["web_search", "web_fetch"], **kw)

    def web(rec):
        return chk("used a web tool", used_tool(rec, "web_search", "web_fetch"), "no web tool call")

    def cites(rec, n=1):
        d = domains(rec.get("final_text"))
        return chk(f"cites ≥ {n} source link(s)", len(d) >= n, ", ".join(sorted(d)) or "no links")

    r(id="res_esp32c3", cat="research", kind="lookup", quick=True,
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web: what CPU architecture, how many cores and what maximum clock speed "
                          "does the ESP32-C3 have? Cite your source with a link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("RISC-V", _rx(r"risc-?\s?v", _plain(rec)), _plain(rec)[:160]),
          chk("single core", _rx(r"single[- ]core|one core|1 core|1-core|a single (32-bit )?(risc-?v )?core|"
                                  r"single 32-bit", _plain(rec)) and not _rx(r"dual[- ]core", _plain(rec)),
              _plain(rec)[:160]),
          chk("160 MHz", _rx(r"\b160\s?mhz", _plain(rec)), _plain(rec)[:160]),
          cites(rec),
      ])

    r(id="res_gold2000", cat="research", kind="lookup",
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web: in which year and month did the gold spot price first rise above "
                          "2,000 US dollars per troy ounce? Cite a source with a link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("2020", _rx(r"\b2020\b", _plain(rec)), _plain(rec)[:160]),
          chk("August", _rx(r"\baug(ust)?\b|\b0?8/2020|2020-08", _plain(rec)), _plain(rec)[:160]),
          cites(rec),
      ])

    def _towers(rec, ctx):
        t = _plain(rec)
        return [
            answered(rec), web(rec),
            chk("Fernsehturm 368 m", _rx(r"\b368\s?(m|metres|meters)\b", t), t[:200]),
            chk("Eiffel Tower 330 m (or 324 m)", _rx(r"\b(330|324)\s?(m|metres|meters)\b", t), t[:200]),
            chk("difference 38 m (or 44 m)", _rx(r"\b(38|44)\s?(m|metres|meters)\b", t), t[:200]),
            chk("Fernsehturm is taller",
                _rx(r"(fernsehturm|tv tower|tower in berlin|berlin)[^.\n]{0,80}(taller|higher)|"
                    r"(taller|higher)[^.\n]{0,40}(fernsehturm|tv tower|berlin)", t)
                and not _rx(r"eiffel tower is (the )?(taller|higher)", t), t[:200]),
            cites(rec),
        ]

    r(id="res_towers", cat="research", kind="compare", quick=True,
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web for the heights of the Berlin TV Tower (Fernsehturm) and the Eiffel "
                          "Tower, then tell me which is taller and by how many metres. Cite your sources with links."),
      checks=_towers)

    r(id="res_djamor", cat="research", kind="lookup",
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web: in what kind of climate does the pink oyster mushroom (Pleurotus djamor) "
                          "grow in the wild, and on what material does it grow? Cite a source with a link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("tropical / subtropical", _rx(r"tropic", _plain(rec)), _plain(rec)[:160]),
          chk("on wood (dead wood, logs, palms)",
              _rx(r"wood|log|timber|tree|palm|coconut|branch|stump|trunk", _plain(rec)), _plain(rec)[:160]),
          cites(rec),
      ])

    def _gnats(rec, ctx):
        t = _plain(rec)
        measures = {
            "sticky traps": r"sticky|yellow (card|trap)|fly ?paper",
            "mesh / filter on intakes": r"mesh|screen|filter|net",
            "hygiene / remove old blocks": r"clean|hygien|sanit|remove (old|spent|infested)|discard|dispose",
            "UV traps": r"\buv\b|ultraviolet|bug zapper",
            "biological control": r"nematode|predat|bti\b|bacillus|neem|pyrethr",
            "dry / humidity control": r"dry (out|the)|let .{0,20}dry|overwater",
        }
        hit = [m for m, p in measures.items() if _rx(p, t)]
        bullets = len(re.findall(r"^\s*(?:[-*•]|\d+[.)])\s+\S", t, re.M))
        return [
            answered(rec), web(rec),
            chk("3–5 bullet points", 3 <= bullets <= 6, f"{bullets} bullets"),
            chk("≥ 2 known measures", len(hit) >= 2, ", ".join(hit) or t[:120]),
            cites(rec, 2),
        ]

    r(id="res_gnats", cat="research", kind="synthesis", quick=True,
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web and give me 3–5 bullet points on how to keep fungus gnats out of a "
                          "mushroom grow tent. Cite at least two different websites with links."),
      checks=_gnats)
