"""Node-driven tests for static/js/source_ratings.js (fork: notes item 71).

The rendering helpers decide what the sources box shows: dropped results stay
out of the numbered list (so [n] keeps matching the model's citations), old
sources without a search id render exactly as before, and everything that goes
into HTML attributes is escaped. Click handling and restoring saved ratings
need a browser and are checked by hand (steps in notes item 71).
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_MOD = _REPO / "static" / "js" / "source_ratings.js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node not on PATH")


def _run(body):
    js = f"import * as M from '{_MOD.as_posix()}';\n{body}"
    proc = subprocess.run(["node", "--input-type=module"], input=js, capture_output=True,
                          text=True, cwd=str(_REPO), timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip())


def test_dropped_results_are_split_out_of_the_numbered_list():
    out = _run("""
      const r = M.splitSources([{url:'a'}, {url:'b', filtered:true}, {url:'c'}, null]);
      console.log(JSON.stringify({shown: r.shown.map(s => s.url), filtered: r.filtered.map(s => s.url)}));
    """)
    assert out == {"shown": ["a", "c"], "filtered": ["b"]}


def test_sources_without_a_search_id_render_unchanged():
    out = _run("""
      console.log(JSON.stringify([M.decorateSource('<a>x</a>', {url: 'https://a'}),
                                  M.decorateSource('<a>x</a>', null),
                                  M.filteredBlock([], u => u)]));
    """)
    assert out == ["<a>x</a>", "<a>x</a>", ""]


def test_rating_arrows_carry_escaped_data():
    out = _run("""
      const s = {search_id: 'abc', url: 'https://x.com/?a=1&b="2"', query: 'q<script>', topic: 'biology',
                 title: '"><img src=x onerror=alert(1)>', score: 0.25};
      console.log(JSON.stringify(M.decorateSource('<a>x</a>', s)));
    """)
    assert out.startswith('<div class="src-row"><a>x</a><span class="src-rate"')
    assert 'data-search-id="abc"' in out and 'data-score="0.25"' in out and 'data-topic="biology"' in out
    assert "<img" not in out and "<script>" not in out
    assert 'data-url="https://x.com/?a=1&amp;b=&quot;2&quot;"' in out
    assert out.count('class="src-rate-btn"') == 2
    assert 'data-rate="up"' in out and 'data-rate="down"' in out


def test_filtered_block_lists_dropped_results_with_scores_and_arrows():
    out = _run("""
      const html = M.filteredBlock([
        {search_id:'s', url:'https://www.victoriassecret.com/pink', title:'PINK <b>', score: 0.0123, filtered: true},
        {search_id:'s', url:'https://oyster.tfl.gov.uk/', title:'', filtered: true},
        {url: 'https://no-id.example/'},
      ], u => 'SAFE:' + u);
      console.log(JSON.stringify(html));
    """)
    assert "2 filtered out by relevance" in out
    assert 'href="SAFE:https://www.victoriassecret.com/pink"' in out
    assert "victoriassecret.com · 0.012" in out
    assert '<span class="source-title">PINK &lt;b&gt;</span>' in out and "PINK <b>" not in out
    assert out.count('class="src-rate"') == 2 and 'data-filtered="1"' in out
    assert "no-id.example" not in out


def test_filtered_block_is_not_a_details_element():
    """style.css shrinks every `details .source-link` to tiny inline tags."""
    out = _run("""
      console.log(JSON.stringify(M.filteredBlock([{search_id:'s', url:'https://a.example/', title:'A', filtered:true}], u => u)));
    """)
    assert "<details" not in out and "<summary" not in out
    assert 'class="src-filtered-toggle" aria-expanded="false"' in out
    assert '<div class="src-filtered-list" hidden>' in out
