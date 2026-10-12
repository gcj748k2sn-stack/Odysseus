"""bench_web_filter.py: the offline replay reads what Odysseus wrote, and the
filter it measures can never hand the model nothing.

The parser is checked against the real writer (comprehensive_web_search with
its providers and fetches stubbed), not against a hand-written sample, so a
format change in services/search/core.py fails here instead of silently
emptying the corpus.
"""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("bench_web_filter_under_test",
                                                  ROOT / "scripts" / "bench_web_filter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W = _load()

RESULTS = [
    {"title": "Pink (singer) - Wikipedia", "url": "https://en.wikipedia.org/wiki/Pink_(singer)",
     "snippet": "Alecia Beth Moore, known professionally as Pink, is an American singer. " * 4},
    {"title": "Growing Pink Oyster Mushrooms", "url": "https://grocycle.com/pink-oyster",
     "snippet": "Pleurotus djamor fruits at 20-30 C in high humidity.", "age": "2026-01-02"},
    {"title": "Line one [2] not a result", "url": "https://example.org/x", "snippet": ""},
]


def _real_output(monkeypatch, results=RESULTS, query="pink oyster cultivation"):
    from services.search import core

    monkeypatch.setattr(core, "_get_search_settings", lambda: {"search_provider": "searxng"})
    monkeypatch.setattr(core, "_get_result_count", lambda: 10)
    monkeypatch.setattr(core, "_build_provider_chain", lambda primary: ["searxng"])
    monkeypatch.setattr(core, "_call_provider", lambda *a, **k: [dict(r) for r in results])
    monkeypatch.setattr(core, "fetch_webpage_content", lambda url, *a, **k: {
        "success": True, "url": url, "title": "T", "content": "Body text.\n\n[1] fake line\nURL: nope"})
    text, sources = core.comprehensive_web_search(query, max_pages=2, return_sources=True)
    return text, sources


# ------------------------------------------------------------ reads the writer

def test_parser_reads_every_result_the_real_writer_emits(monkeypatch):
    text, sources = _real_output(monkeypatch)
    query, parsed = W.parse_search_output(text)
    assert query == "pink oyster cultivation"
    assert [p["url"] for p in parsed] == [s["url"] for s in sources]
    by_url = {p["url"]: p for p in parsed}
    singer = by_url["https://en.wikipedia.org/wiki/Pink_(singer)"]
    assert singer["title"] == "Pink (singer) - Wikipedia"
    # The writer cuts snippets at 200 chars and appends "..."; the parser removes the dots.
    assert singer["snippet"] == RESULTS[0]["snippet"][:200]
    assert by_url["https://grocycle.com/pink-oyster"]["age"] == "2026-01-02"


def test_fetched_page_text_is_not_read_as_results(monkeypatch):
    text, _ = _real_output(monkeypatch)
    _, parsed = W.parse_search_output(text)
    assert all(p["url"].startswith("https://") for p in parsed)
    assert len(parsed) == len(RESULTS)


def test_a_result_cut_off_by_output_truncation_is_dropped_not_half_read(monkeypatch):
    text, _ = _real_output(monkeypatch)
    _, full = W.parse_search_output(text)
    cut_at = [p["url"] for p in full].index("https://example.org/x")
    url_line = text.find("    URL: https://example.org/x", text.find(W._SUMMARY_HEADER))
    _, parsed = W.parse_search_output(text[:url_line])
    assert parsed == full[:cut_at]


def test_output_without_a_summary_gives_no_results():
    assert W.parse_search_output("Web search failed — all providers errored") == (None, [])
    assert W.parse_search_output("") == (None, [])


def test_web_fetch_header_and_notices_are_stripped():
    out = ("[served from cache, fetched 3 min 2 s ago — NOT a live reading.]\n\n"
           "# Pink oyster guide\nSource: https://grocycle.com/pink\n\nPara one.\n\nPara two.\n\n[...truncated]")
    title, url, body = W.page_text_from_fetch_output(out)
    assert (title, url) == ("Pink oyster guide", "https://grocycle.com/pink")
    assert body == "Para one.\n\nPara two."


# -------------------------------------------------------------- database side

def test_extract_refuses_a_missing_database_and_does_not_create_it(tmp_path):
    missing = tmp_path / "app.db"
    with pytest.raises(SystemExit):
        W.snapshot_db(missing, tmp_path)
    with pytest.raises(SystemExit):
        W.open_readonly(missing)
    assert not missing.exists()


def test_the_copy_is_opened_read_only(tmp_path):
    db = tmp_path / "x.db"
    sqlite3.connect(db).execute("create table t (a)").connection.commit()
    con = W.open_readonly(db)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("insert into t values (1)")


def _mini_db(path, output):
    con = sqlite3.connect(path)
    con.execute("create table chat_messages (id text, session_id text, role text, content text, "
                "metadata text, timestamp text)")
    rows = [
        ("u1", "s1", "user", "how do I grow pink oysters?", None, "2026-10-01 10:00:00"),
        ("a1", "s1", "assistant", "…", json.dumps({"tool_events": [
            {"tool": "web_search", "command": '{"query": "x"}', "output": output, "exit_code": 0},
            {"tool": "web_fetch", "command": "grocycle.com/pink", "exit_code": 1,
             "output": "web_fetch: 403"}]}), "2026-10-01 10:00:30"),
        ("u2", "s1", "user", "later question", None, "2026-10-01 11:00:00"),
        ("a2", "s2", "assistant", "…", json.dumps({"web_sources": [{"url": "https://a"}]}),
         "2026-10-01 10:05:00"),
    ]
    con.executemany("insert into chat_messages values (?,?,?,?,?,?)", rows)
    con.commit()
    con.close()


def test_extract_links_each_search_to_the_user_message_before_it(monkeypatch, tmp_path):
    text, _ = _real_output(monkeypatch)
    db = tmp_path / "app.db"
    _mini_db(db, text)
    snap = tmp_path / "snap"
    snap.mkdir()
    copy, digest = W.snapshot_db(db, snap)
    con = W.open_readonly(copy)
    searches, fetches, stats = W.extract_corpus(con)
    assert len(searches) == 1
    assert searches[0]["user_message"] == "how do I grow pink oysters?"
    assert searches[0]["query"] == "pink oyster cultivation"   # from the output, not the command
    assert len(fetches) == 1 and fetches[0]["exit_code"] == 1 and fetches[0]["text"] == ""
    assert stats["chat_mode_rows_skipped"] == 1
    assert len(digest) == 64


# ------------------------------------------------------------------- scoring

def test_lexical_score_counts_distinctive_terms_only():
    q = "how to grow pink oyster mushrooms at home"
    good = {"title": "Pink Oyster Mushroom Growing Guide", "snippet": "grow at home", "url": "https://x.com/a"}
    singer = {"title": "Pink (singer) - Wikipedia", "snippet": "American singer", "url": "https://en.wikipedia.org/wiki/Pink"}
    assert W.lexical_score(q, good) > W.lexical_score(q, singer)
    # "how", "to", "at" are stopwords: a page matching only them scores 0
    assert W.lexical_score(q, {"title": "How to get there at night", "snippet": "", "url": ""}) == 0.0
    # plural/singular both ways
    assert W.lexical_score("mushroom", {"title": "Mushrooms", "snippet": "", "url": ""}) == 1.0


def test_domain_prior_matches_on_label_boundaries():
    priors = {"webmd.com": -0.5, "health.webmd.com": -0.9}
    assert W.domain_prior("https://www.webmd.com/a", priors) == -0.5
    assert W.domain_prior("https://m.webmd.com/a", priors) == -0.5
    assert W.domain_prior("https://health.webmd.com/a", priors) == -0.9   # longest suffix wins
    assert W.domain_prior("https://notwebmd.com/a", priors) == 0.0


def test_reranker_adapter_maps_logits_to_0_1_in_input_order():
    class Fake:
        def rerank(self, query, docs):
            return [10.0 if "oyster" in d else -10.0 for d in docs]

    r = W.Reranker(model=Fake())
    s = r.score("q", ["singer", "oyster"])
    assert s[0] < 0.01 and s[1] > 0.99
    assert r.score("q", []) == []


def test_reranker_adapter_refuses_a_short_score_list():
    class Broken:
        def rerank(self, query, docs):
            return [0.0]

    with pytest.raises(RuntimeError):
        W.Reranker(model=Broken()).score("q", ["a", "b"])


# ---------------------------------------------------------------- fail-open

def test_decide_keeps_results_at_or_above_the_threshold_in_display_order():
    scored = [("a", 0.9), ("b", 0.1), ("c", 0.5), ("d", 0.7)]
    kept, fell_back = W.decide(scored, 0.5, min_keep=2)
    assert kept == ["a", "c", "d"] and not fell_back


def test_decide_never_returns_fewer_than_min_keep():
    scored = [("a", 0.1), ("b", 0.3), ("c", 0.2), ("d", 0.05)]
    kept, fell_back = W.decide(scored, 0.99, min_keep=3)
    assert fell_back and kept == ["a", "b", "c"]


def test_decide_with_fewer_results_than_min_keep_keeps_them_all():
    kept, fell_back = W.decide([("a", 0.0)], 0.5, min_keep=3)
    assert kept == ["a"]


def test_decide_negative_control_all_relevant_nothing_dropped():
    scored = [(k, 0.8) for k in "abcde"]
    assert W.decide(scored, 0.5)[0] == list("abcde")


# --------------------------------------------------------------- evaluation

def _searches():
    return [{"id": "s1", "query": "pink oyster", "results": [
        {"rank": 1, "url": "https://junk", "title": "Pink (singer)", "snippet": ""},
        {"rank": 2, "url": "https://good1", "title": "", "snippet": ""},
        {"rank": 3, "url": "https://good2", "title": "", "snippet": ""},
        {"rank": 4, "url": "https://unl", "title": "", "snippet": ""},
    ]}]


def test_evaluate_counts_junk_and_relevant_drops_separately():
    s = _searches()
    scores = {("s1", "https://junk"): 0.1, ("s1", "https://good1"): 0.9,
              ("s1", "https://good2"): 0.4, ("s1", "https://unl"): 0.2}
    truth = {("s1", "https://junk"): "n", ("s1", "https://good1"): "y", ("s1", "https://good2"): "y"}
    row, good_dropped = W.evaluate(s, scores, truth, threshold=0.5, min_keep=1)
    assert (row["junk_dropped"], row["junk"]) == (1, 1)
    assert (row["good_dropped"], row["good"]) == (1, 2)
    assert row["unlabeled_dropped"] == 1
    assert good_dropped == [("pink oyster", "https://good2", 0.4)]
    assert W.junk_in_current_top(s, truth) == 1


def test_labels_survive_re_extraction_and_seed_rules_mark_known_junk(tmp_path):
    sheet = tmp_path / "labels.csv"
    s = _searches()
    added, total = W.write_label_sheet(s, sheet)
    assert added == total == 4
    rows = sheet.read_text(encoding="utf-8").splitlines()
    assert any("seed:n" in r and "Pink (singer)" in r for r in rows)
    sheet.write_text(sheet.read_text(encoding="utf-8").replace("\n,,seed:n,", "\nn,,seed:n,"), encoding="utf-8")
    added, total = W.write_label_sheet(s, sheet)
    assert added == 0 and total == 4
    assert W.load_labels(sheet) == {W.label_key("pink oyster", "https://junk"): "n"}


def test_seed_rules_do_not_fire_outside_their_topic():
    assert W.seed_label("pink oyster cultivation", {"title": "Pink (singer) - Wikipedia", "url": ""}) == "n"
    assert W.seed_label("pink concert tickets", {"title": "Pink (singer) - Wikipedia", "url": ""}) is None
    assert W.seed_label("shiitake nutrition", {"title": "x", "url": "https://www.webmd.com/a"}) is None
    assert W.seed_label("shiitake growing temperature", {"title": "x", "url": "https://www.webmd.com/a"}) == "n"


# --------------------------------------------------------------------- pages

def test_chunking_keeps_all_text_and_respects_the_hard_max():
    text = "\n\n".join(["p" * 300] * 5 + ["q" * 3000])
    chunks = W.chunk_text(text)
    assert all(len(c) <= 1200 for c in chunks)
    assert "".join(c.replace("\n", "") for c in chunks) == text.replace("\n", "")


def test_budget_keeps_best_chunks_in_page_order_and_always_one():
    chunks = ["a" * 500, "b" * 500, "c" * 500]
    assert W.keep_within_budget(chunks, [0.1, 0.9, 0.5], budget=1000) == [1, 2]
    assert W.keep_within_budget(chunks, [0.1, 0.9, 0.5], budget=10) == [1]


def test_without_labels_the_seed_rules_stand_in_and_say_so():
    truth, source = W.labels_for(_searches(), {})
    assert truth == {("s1", "https://junk"): "n"}
    assert source.startswith("SEED_RULES proxy")
    truth, source = W.labels_for(_searches(), {W.label_key("pink oyster", "https://good1"): "y"})
    assert truth == {("s1", "https://good1"): "y"} and source == "labels.csv"


def test_threshold_grid_keeps_cut_points_that_rounding_would_merge():
    # reranker scores after the sigmoid: most results sit very close to 0
    scores = {i: 1e-7 * (1.3 ** i) for i in range(50)}    # 1e-7 … 3e-2, mostly below 1e-4
    grid = W.threshold_grid(scores)
    assert len(grid) == 5
    assert min(grid) > min(scores.values())   # a cut at the lowest score would drop nothing
    assert W.threshold_grid({1: 0.0, 2: 0.0, 3: 0.0, 4: 0.5}) == [0.5]


def test_threshold_grid_of_one_value_does_not_crash():
    assert W.threshold_grid({1: 0.5, 2: 0.5}) == [0.5]
    assert W.threshold_grid({}) == []


def test_seed_rules_catch_the_oyster_collisions_only_for_mushroom_queries():
    vs = {"title": "PINK | Victoria’s Secret", "url": "https://www.victoriassecret.com/us/pink"}
    tfl = {"title": "Oyster card", "url": "https://oyster.tfl.gov.uk/oyster/entry.do"}
    assert W.seed_label("pink mushroom fruiting temperature", vs) == "n"
    assert W.seed_label("oyster mushroom grow kit", tfl) == "n"
    assert W.seed_label("london oyster card top up", tfl) is None
    assert W.seed_label("pink pajamas", vs) is None


def test_label_sheet_gets_a_sortable_score_column_and_refreshed_hints(tmp_path):
    sheet = tmp_path / "labels.csv"
    s = _searches()
    W.write_label_sheet(s, sheet)
    scores = {W.label_key("pink oyster", "https://junk"): 0.001, W.label_key("pink oyster", "https://good1"): 0.9}
    W.write_label_sheet(s, sheet, scores)
    import csv as _csv
    rows = {r["url"]: r for r in _csv.DictReader(open(sheet, encoding="utf-8"))}
    assert rows["https://junk"]["score"] == "0.001000"
    assert rows["https://good1"]["score"] == "0.900000"
    assert rows["https://unl"]["score"] == ""
    assert rows["https://junk"]["hint"] == "seed:n"
    # a sheet written under older SEED_RULES gets its hints recomputed
    sheet.write_text(sheet.read_text(encoding="utf-8").replace("seed:n", ""), encoding="utf-8")
    W.write_label_sheet(s, sheet)
    rows = {r["url"]: r for r in _csv.DictReader(open(sheet, encoding="utf-8"))}
    assert rows["https://junk"]["hint"] == "seed:n"


def test_a_sheet_saved_by_a_german_spreadsheet_app_is_read(tmp_path):
    sheet = tmp_path / "labels.csv"
    text = ("Label;score;hint;Query;rank;domain;title;snippet;URL;user_message\n"
            "n;0.01;seed:n;pink oyster;1;x;Pink (singer);;https://junk;Züchtung\n"
            "ja;0.9;;pink oyster;2;x;Grow guide;;https://good1;\n")
    sheet.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    assert W.load_labels(sheet) == {W.label_key("pink oyster", "https://junk"): "n",
                                    W.label_key("pink oyster", "https://good1"): "y"}
    sheet.write_bytes(text.replace("\n", "\r\n").encode("cp1252"))
    assert len(W.load_labels(sheet)) == 2
    added, total = W.write_label_sheet(_searches(), sheet)
    assert (added, total) == (2, 4)                      # the two labelled rows were recognised
    assert len(W.load_labels(sheet)) == 2                # and their labels kept
    assert (tmp_path / "labels.csv.bak").is_file()


def test_an_unreadable_sheet_is_refused_and_left_untouched(tmp_path):
    sheet = tmp_path / "labels.csv"
    original = "Spalte1;Spalte2\nn;https://junk\n"
    sheet.write_text(original, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        W.write_label_sheet(_searches(), sheet)
    assert "Nothing was changed" in str(exc.value)
    assert sheet.read_text(encoding="utf-8") == original
    with pytest.raises(SystemExit):
        W.load_labels(sheet)


def test_scored_sheet_puts_unlabelled_drop_candidates_on_top(tmp_path):
    sheet = tmp_path / "labels.csv"
    s = _searches()
    W.write_label_sheet(s, sheet)
    text = sheet.read_text(encoding="utf-8").replace("\n,,seed:n,", "\nn,,seed:n,")
    sheet.write_text(text, encoding="utf-8")                       # junk is labelled
    scores = {W.label_key("pink oyster", u): v for u, v in
              [("https://junk", 0.0001), ("https://good1", 0.9), ("https://good2", 0.2)]}
    W.write_label_sheet(s, sheet, scores)
    import csv as _csv
    order = [r["url"] for r in _csv.DictReader(open(sheet, encoding="utf-8"))]
    assert order == ["https://good2", "https://good1", "https://unl", "https://junk"]


def test_all_junk_searches_counts_only_fully_labelled_junk():
    s = _searches()
    keys = [("s1", r["url"]) for r in s[0]["results"]]
    assert W.all_junk_searches(s, {k: "n" for k in keys}) == 1
    assert W.all_junk_searches(s, {k: "n" for k in keys[:3]}) == 0      # one result unlabelled
    assert W.all_junk_searches(s, {**{k: "n" for k in keys}, keys[1]: "y"}) == 0


def _sheet_rows(tmp_path):
    sheet = tmp_path / "labels.csv"
    W.write_label_sheet(_searches(), sheet)
    rows = W.read_label_rows(sheet)
    rows[0]["label"] = "n"                        # one row already labelled
    rows[1]["user_message"] = "private\tchat"
    rows[1]["title"] = "tab\there\nnewline"
    return sheet, rows


def test_export_lists_only_unlabelled_rows_without_user_messages(tmp_path):
    _, rows = _sheet_rows(tmp_path)
    lines = W.export_unlabelled(rows)
    assert lines[0] == "id\tquery\ttitle\tdomain\tsnippet"
    assert len(lines) == 1 + 3
    assert all(len(l.split("\t")) == 5 for l in lines)       # tabs/newlines inside fields flattened
    assert not any("private" in l for l in lines)
    ids = [l.split("\t")[0] for l in lines[1:]]
    assert len(set(ids)) == 3
    assert W.export_unlabelled(rows, limit=2, offset=1)[1:] == lines[2:4]


def test_import_applies_labels_and_keeps_existing_ones(tmp_path):
    sheet, rows = _sheet_rows(tmp_path)
    rid = {r["url"]: W.row_id(r["query"], r["url"]) for r in rows}
    lines = ["id\tlabel",
             f"{rid['https://junk']}\ty",          # already labelled n: kept
             f"{rid['https://good1']}\ty",
             f"{rid['https://good2']} n",
             f"{rid['https://unl']}\tmaybe",
             "0123456789\tn"]
    counts = W.apply_label_lines(rows, lines)
    assert counts == {"applied": 2, "already_labelled": 1, "bad_value": 1, "unknown_id": 1}
    by_url = {r["url"]: r["label"] for r in rows}
    assert by_url == {"https://junk": "n", "https://good1": "y", "https://good2": "n", "https://unl": ""}
    assert W.apply_label_lines(rows, [f"{rid['https://junk']}\ty"], overwrite=True)["applied"] == 1


def test_export_import_round_trip_through_the_sheet(tmp_path):
    sheet, rows = _sheet_rows(tmp_path)
    W.save_label_rows(sheet, rows)
    out = tmp_path / "to_label.tsv"
    W.main(["export", "--labels", str(sheet), "--out", str(out)])
    answers = tmp_path / "answers.tsv"
    answers.write_text("\n".join(l.split("\t")[0] + "\ty" for l in out.read_text().splitlines()[1:]), encoding="utf-8")
    W.main(["import", str(answers), "--labels", str(sheet)])
    labels = W.load_labels(sheet)
    assert sorted(labels.values()) == ["n", "y", "y", "y"]
    assert (tmp_path / "labels.csv.bak").is_file()
