"""The prefix probe names the first message that changed between two requests.

notes/todo.md, "A different tool set per message defeats prompt caching on
local servers" / "Round 1 of every turn re-prefills the whole prompt".
Report-only diagnostic; these pin what it reports and that it logs no text.
"""
import logging

from src import prefix_probe as P


def _reset():
    P._last.clear()


def test_first_request_reports_nothing():
    _reset()
    assert P.compare("s1", 1, [{"role": "system", "content": "a"}], ["t"]) is None


def test_append_only_is_a_clean_prefix():
    _reset()
    m = [{"role": "system", "content": "rules"}, {"role": "user", "content": "hi"}]
    P.compare("s1", 1, m, ["a", "b"])
    d = P.compare("s1", 2, m + [{"role": "assistant", "content": "x"}], ["a", "b"])
    assert d["tools_same"] and d["first_diff"] == 2 and d["changed"].startswith("(none")


def test_identical_request_is_a_clean_prefix():
    _reset()
    m = [{"role": "system", "content": "rules"}]
    P.compare("s1", 1, m, ["a"])
    d = P.compare("s1", 1, list(m), ["a"])
    assert d["first_diff"] == 1 and d["tools_same"]


def test_changed_context_block_is_named_and_tools_diffed():
    _reset()
    base = [{"role": "system", "content": "rules"},
            {"role": "user", "content": "memory: A", "metadata": {"source": "memory"}},
            {"role": "user", "content": "q1"}]
    P.compare("s1", 1, base, ["read_file", "ls"])
    nxt = [base[0], {"role": "user", "content": "memory: B", "metadata": {"source": "memory"}},
           base[2], {"role": "assistant", "content": "a1"}, {"role": "user", "content": "q2"}]
    d = P.compare("s1", 1, nxt, ["read_file", "web_search"])
    assert d["first_diff"] == 1 and d["changed"].startswith("user:memory")
    assert d["tools_added"] == ["web_search"] and d["tools_removed"] == ["ls"] and not d["tools_same"]


def test_sessions_are_separate():
    _reset()
    P.compare("s1", 1, [{"role": "system", "content": "a"}], [])
    assert P.compare("s2", 1, [{"role": "system", "content": "b"}], []) is None


def test_log_line_carries_no_message_text(caplog):
    _reset()
    secret = "my private note 12345"
    P.log_request("s1", 1, [{"role": "user", "content": secret}], ["a"])
    with caplog.at_level(logging.INFO, logger="src.prefix_probe"):
        P.log_request("s1", 1, [{"role": "user", "content": secret + "!"}], ["a"])
    text = caplog.text
    assert "[prefix-probe]" in text and "changed=user" in text
    assert "private" not in text and "12345" not in text


def test_probe_is_wired_before_each_request():
    src = (P.__file__.replace("prefix_probe.py", "agent_loop.py"))
    body = open(src, encoding="utf-8").read()
    i = body.index("log_prefix_probe(session_id, round_num, messages, _tool_names_sent)")
    assert i < body.index("async for chunk in stream_llm_with_fallback(", i)
