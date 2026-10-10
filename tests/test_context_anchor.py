"""Trimming a long tool chain keeps the turn's user message.

Covers ``src/context_anchor.py`` and its call sites in
``src/context_compactor.trim_for_context``. Before the fix a web-research turn
on Bonsai 2 reached round 9 with only system, assistant and tool messages, and
the chat template rejected it ("No user query found in messages").
"""

from src.context_anchor import drop_oldest, latest_user
from src.context_compactor import trim_for_context
from src.model_context import estimate_tokens

_SYSTEM = {"role": "system", "content": "You are an AI assistant with native tool calling."}


def _tool_chain(rounds, page_chars=6000):
    """system, the user's request, then `rounds` x (assistant tool call, tool result)."""
    msgs = [dict(_SYSTEM), {"role": "user", "content": "When did gold first close above $2,000?"}]
    for r in range(rounds):
        call_id = f"call_{r}"
        msgs.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": call_id, "type": "function",
             "function": {"name": "web_search", "arguments": f'{{"query": "gold {r}"}}'}}]})
        msgs.append({"role": "tool", "tool_call_id": call_id, "content": f"page {r} " + "x" * page_chars})
    return msgs


def _roles(msgs):
    return [m["role"] for m in msgs]


def test_long_tool_chain_keeps_the_user_request():
    msgs = _tool_chain(12)
    assert estimate_tokens(msgs) > 12000
    out = trim_for_context(msgs, 12000, reserve_tokens=1024)
    users = [m for m in out if m["role"] == "user"]
    assert [u["content"] for u in users] == ["When did gold first close above $2,000?"]
    # still in order: system, the request, then the newest rounds
    assert _roles(out)[:2] == ["system", "user"]
    assert out[-1]["content"].startswith("page 11 ")
    assert estimate_tokens(out) <= 12000


def test_short_chain_takes_the_other_branch_and_keeps_the_user_request_too():
    # fewer than 10 prior messages: the second trimming loop
    msgs = _tool_chain(3, page_chars=20000)
    out = trim_for_context(msgs, 9000, reserve_tokens=512)
    assert "user" in _roles(out)
    assert out[-1]["content"].startswith("page 2 ")


def test_no_orphan_tool_results_after_the_kept_request():
    out = trim_for_context(_tool_chain(12), 12000, reserve_tokens=1024)
    for i, m in enumerate(out):
        if m["role"] == "tool":
            prev = out[i - 1]
            assert prev["role"] == "tool" or prev.get("tool_calls"), _roles(out)


def test_plain_chat_still_drops_older_user_turns():
    """Negative control: only the newest user message is protected."""
    msgs = [dict(_SYSTEM)]
    for i in range(12):
        msgs.append({"role": "user", "content": f"question {i} " + "y" * 4000})
        msgs.append({"role": "assistant", "content": f"answer {i} " + "z" * 4000})
    msgs.append({"role": "user", "content": "last question"})
    out = trim_for_context(msgs, 8000, reserve_tokens=512)
    contents = [m["content"] for m in out if m["role"] == "user"]
    assert contents[-1] == "last question"
    assert not any(c.startswith("question 0 ") for c in contents)


def test_under_budget_is_untouched():
    msgs = _tool_chain(2, page_chars=100)
    assert trim_for_context(msgs, 32000) is msgs


def test_helpers():
    a, b, c = {"role": "user"}, {"role": "assistant"}, {"role": "user"}
    assert latest_user([a, b, c]) is c
    assert latest_user([b]) is None
    items = [b, c, a]
    assert drop_oldest(items, c) and items == [c, a]
    assert drop_oldest(items, c) and items == [c]
    assert not drop_oldest(items, c) and items == [c]
    assert not drop_oldest([], None)
