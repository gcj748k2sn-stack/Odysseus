"""Harder web suite for scripts/bench_agent.py (`--suite webhard`): searches that
invite off-topic results, so the web relevance filter has something to do.

The research suite's five tasks pass at or near 10/10 on every backend with the
filter on (2026-10-12), so they cannot show whether it helps. These are built
around its known failure cases. Kinds:
  ambiguous  a common noun that names something else too (Mercury, crane, pink oyster, Amazon)
  german     a German query whose key word is also an everyday word (Essen = food, Brocken = chunk)
  typo       a misspelled Latin name, like the 2026-10-12 "Pinatus djamor" search
  crowded    a topic whose results are mostly shop pages (grow shops, which often refuse
             fetches; display-module listings, which mix in other modules' addresses)

Answer keys checked 2026-10-12 with a web search: Mercury's solar day ~176 Earth
days (sidereal rotation 58.6 d); common crane wingspan 180-240 cm (Wikipedia;
other sources 180-200, up to 245); Essen ~574,700 inhabitants end of 2024
(Statista), 584,580 end of 2022 (IT.NRW); pink oyster fruits at ~18-30 C
(Fungi Perfecti 65-85 F, suppliers 18-30 C); golden oyster (Pleurotus
citrinopileatus) has a yellow cap; pasteurized straw ~65 % moisture.
Checked 2026-10-13: Amazon river 6,400 km (Britannica) to 6,992 km (Brazilian
study); Brocken 1141 m (1140.7-1142 in older maps); Hericium erinaceus = lion's
mane, on hardwoods (MykoWeb); SSD1306 default I2C address 0x3C, 0x3D with SA0
high (Wokwi docs; 0x78/0x7A are the 8-bit forms). Checks are
lexical and accept the spread between sources; good and bad sample answers are
in tests/test_bench_webhard_tasks.py.
"""
import re

from bench_research_tasks import _plain, _rx, domains

_THOUSANDS = r"\d{1,3}(?:[.,\s\u202f]\d{3})+"


def _near(text, unit, lo, hi, gap=15):
    """Numbers in [lo, hi] followed within `gap` characters (same sentence) by
    `unit`, so "18-30 °C" gives 18 and 30. Thousands separators ('.', ',',
    space) are removed; a decimal comma is read as a point."""
    out = []
    pattern = rf"(?<![\d.,])({_THOUSANDS}|\d+(?:[.,]\d+)?)(?=[^.\n]{{0,{gap}}}?(?:{unit}))"
    for m in re.finditer(pattern, text or "", re.I):
        raw = m.group(1)
        raw = re.sub(r"[.,\s\u202f]", "", raw) if re.fullmatch(_THOUSANDS, raw) else raw.replace(",", ".")
        v = float(raw)
        if lo <= v <= hi:
            out.append(v)
    return out


_GERMAN_WORDS = r"\b(und|die|der|das|hat|ist|nicht|mit|laut|rund|etwa|Einwohner|Stadt|Quelle)\b"


def register(task, chk, answered, used_tool):
    def r(**kw):
        kw.setdefault("workspace", False)
        task(suite="webhard", web=True, tools=["web_search", "web_fetch"], **kw)

    def web(rec):
        return chk("used a web tool", used_tool(rec, "web_search", "web_fetch"), "no web tool call")

    def cites(rec, n=1):
        d = domains(rec.get("final_text"))
        return chk(f"cites ≥ {n} source link(s)", len(d) >= n, ", ".join(sorted(d)) or "no links")

    def not_about(label, pattern, rec):
        # "(the planet, not Freddie Mercury)" is a right answer, so a mention
        # within a few words after a negation does not count.
        t = _plain(rec)
        hits = [m.group(0) for m in re.finditer(pattern, t, re.I)
                if not re.search(r"\b(not|n't|rather than|unlike|nicht|kein)\b[^.\n]{0,30}$", t[:m.start()], re.I)]
        return chk(f"not about {label}", not hits, ", ".join(hits[:3]))

    r(id="wh_mercury_day", cat="webhard", kind="ambiguous", quick=True,
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web: how long is a solar day on Mercury, from one sunrise to the next, "
                          "in Earth days? Cite a source with a link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("~176 Earth days", bool(_near(_plain(rec), r"\bdays?\b", 175, 177)), _plain(rec)[:160]),
          not_about("the singer or the element", r"freddie|queen \(band\)|quicksilver|toxic|thermometer", rec),
          cites(rec),
      ])

    r(id="wh_crane_wingspan", cat="webhard", kind="ambiguous",
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web: what is the wingspan of a common crane? Give it in centimetres and "
                          "cite a source with a link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("wingspan 170–250 cm (or 1.7–2.5 m)",
              bool(_near(_plain(rec), r"\bcm\b|centimet", 170, 250)
                   or _near(_plain(rec), r"\bm\b|metres?\b|meters?\b", 1.7, 2.5, gap=10)), _plain(rec)[:160]),
          # an answer about construction cranes fails here; no separate guard, which
          # would also fail "not to be confused with tower cranes"
          chk("about the bird", _rx(r"grus|bird|eurasian crane|common crane", _plain(rec)), _plain(rec)[:160]),
          cites(rec),
      ])

    r(id="wh_pink_oyster_temp", cat="webhard", kind="ambiguous", quick=True,
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web: what temperature range do pink oysters need to fruit? Give the range "
                          "in °C and cite a source with a link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("a fruiting temperature in °C (15–32)",
              bool(_near(_plain(rec), r"°\s*c\b|℃|degrees? c", 15, 32, gap=12)), _plain(rec)[:160]),
          chk("about the mushroom", _rx(r"mushroom|pleurotus|djamor|fung", _plain(rec)), _plain(rec)[:160]),
          not_about("the singer or the brand", r"singer|alecia|p!nk|victoria'?s secret|lingerie", rec),
          cites(rec),
      ])

    r(id="wh_golden_typo", cat="webhard", kind="typo",
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web: what colour is the cap of Pleurotis citrinopileatis, and what is its "
                          "common name? Cite a source with a link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          # the common name says "golden" too, so it does not count as the colour
          chk("yellow / golden cap", _rx(r"yellow|golden|lemon",
                                         re.sub(r"(golden|yellow) oyster", "", _plain(rec), flags=re.I)),
              _plain(rec)[:160]),
          chk("common name golden oyster", _rx(r"golden oyster|yellow oyster", _plain(rec)), _plain(rec)[:160]),
          cites(rec),
      ])

    r(id="wh_essen_einwohner", cat="webhard", kind="german", quick=True,
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Suche im Web: Wie viele Einwohner hat die Stadt Essen? Antworte auf Deutsch und nenne "
                          "eine Quelle mit Link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("560,000–600,000 inhabitants",
              bool(_near(_plain(rec), r"einwohner|menschen|bewohner|people|inhabitants|\(", 560000, 600000, gap=40)
                   or _near(_plain(rec), r"tsd|tausend", 560, 600, gap=3)
                   or _near(_plain(rec), r"mio|millionen", 0.56, 0.6, gap=3)), _plain(rec)[:160]),
          chk("answered in German", len(re.findall(_GERMAN_WORDS, _plain(rec), re.I)) >= 4, _plain(rec)[:120]),
          cites(rec),
      ])

    r(id="wh_straw_moisture", cat="webhard", kind="crowded",
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web: what moisture content, in percent, should pasteurized straw have for "
                          "growing oyster mushrooms? Cite a source with a link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("moisture 55–80 %", bool(_near(_plain(rec), r"%|percent|per cent|prozent", 55, 80, gap=8)),
              _plain(rec)[:160]),
          cites(rec),
      ])

    r(id="wh_amazon_length", cat="webhard", kind="ambiguous", quick=True,
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: "Search the web: how long is the Amazon, in kilometres? Cite a source with a link.",
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("6,300–7,100 km", bool(_near(_plain(rec), r"\bkm\b|kilomet", 6300, 7100)), _plain(rec)[:160]),
          chk("about the river", _rx(r"river|\brio\b|amazonas|headwater|basin", _plain(rec)), _plain(rec)[:160]),
          not_about("the company", r"bezos|\bprime\b|\baws\b|e-commerce|retailer|warehouse", rec),
          cites(rec),
      ])

    r(id="wh_brocken_hoehe", cat="webhard", kind="german",
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: "Suche im Web: Wie hoch ist der Brocken? Antworte auf Deutsch und nenne eine Quelle mit Link.",
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("1140–1142 m", bool(_near(_plain(rec), r"\bm\b|met(?:er|re)", 1140, 1142.5, gap=8)), _plain(rec)[:160]),
          chk("about the mountain", _rx(r"\bberg|gipfel|harz|mountain", _plain(rec)), _plain(rec)[:160]),
          chk("answered in German", len(re.findall(_GERMAN_WORDS, _plain(rec), re.I)) >= 4, _plain(rec)[:120]),
          cites(rec),
      ])

    r(id="wh_lionsmane_typo", cat="webhard", kind="typo",
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web: what is the common name of Hericium erinacious, and what does it grow on "
                          "in the wild? Cite a source with a link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          chk("common name lion's mane", _rx(r"lion[\u2019']?s[\s-]+mane", _plain(rec)), _plain(rec)[:160]),
          chk("grows on wood / trees",
              _rx(r"hardwood|deciduous|broad-?leaf|\boaks?\b|beech|maple|\belms?\b|walnut|\btrees?\b|\blogs?\b"
                  r"|trunk|stump|dead wood", _plain(rec)), _plain(rec)[:160]),
          cites(rec),
      ])

    r(id="wh_ssd1306_addr", cat="webhard", kind="crowded", quick=True,
      setup=lambda ws, ctx: {},
      prompt=lambda ctx: ("Search the web: what is the default I2C address of an SSD1306 OLED display module? "
                          "Give it in hex and cite a source with a link."),
      checks=lambda rec, ctx: [
          answered(rec), web(rec),
          # 0x3D (SA0 high) and the 8-bit 0x78 may be mentioned too; 0x3C must be there
          chk("0x3C", _rx(r"\b0x3c\b", _plain(rec)), _plain(rec)[:160]),
          cites(rec),
      ])
