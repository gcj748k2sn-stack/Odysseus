"""Reaching the tool budget gives the model one tool-free round to answer.

Covers ``src/budget_answer.py`` and its call site at ``budget_hit`` in
``stream_agent_loop``. The scripted model below keeps asking for tools, as
Qwen did in the 2026-10-13 benchmarks (19–26 calls, then nothing). The tests
bound what the answer round can do, not only that it happens: no tool schemas
are sent, nothing executes after the budget, and at most one extra round runs
(an earlier "finish now" nudge with tools available wiped a document; notes:
*The agent gathers information, then stops*).
"""
import asyncio
import inspect
import json

from src import budget_answer


def test_pad_results_answers_every_call_of_the_cut_batch():
    assert budget_answer.pad_results(3, ["a"]) == ["a", budget_answer.NOT_RUN, budget_answer.NOT_RUN]
    assert budget_answer.pad_results(1, ["a"]) == ["a"]
    assert budget_answer.pad_results(0, []) == []


def test_should_answer_only_once():
    assert budget_answer.should_answer(False)
    assert not budget_answer.should_answer(True)


def test_one_round_past_the_cap_only_to_answer():
    assert budget_answer.round_allowed(10, 10, False)
    assert budget_answer.round_allowed(11, 10, True)
    assert not budget_answer.round_allowed(11, 10, False)
    assert not budget_answer.round_allowed(12, 10, True)


def _run(monkeypatch, *, budget, calls_per_round=2, answer_in_round=None, max_rounds=10,
         tool_call_in_answer_round=False, answer_text="Gold first passed $2,000 in August 2020."):
    """Drive the real loop. The model asks for `calls_per_round` web searches
    every round, except in round `answer_in_round` (if set), where it answers.
    Returns (requests the model saw, tools executed, events, final text)."""
    import src.agent_loop as al

    monkeypatch.setattr(al, "get_setting", lambda k, d=None: d, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setattr(al, "blocked_tools_for_owner", lambda owner: set(), raising=False)
    executed = []

    async def fake_exec(block, *a, **k):
        executed.append(block.tool_type)
        return ("web_search", {"output": f"result {len(executed)}", "exit_code": 0})

    monkeypatch.setattr(al, "execute_tool_block", fake_exec, raising=False)
    import src.llm_core as llm_core

    async def no_synthesis(*a, **k):      # the loop's salvage call for an empty answer round
        return ""

    monkeypatch.setattr(llm_core, "llm_call_async", no_synthesis)
    seen = []

    async def fake_stream(candidates, _messages, **kwargs):
        request = kwargs["candidate_request_factory"](0, *candidates[0])
        if inspect.isawaitable(request):
            request = await request
        seen.append(request)
        n = len(seen)
        no_tools = not _tools_offered(request)
        if (answer_in_round and n == answer_in_round) or (no_tools and not tool_call_in_answer_round):
            yield "data: " + json.dumps({"delta": answer_text}) + "\n\n"
        else:
            calls = [{"id": f"call_{n}_{j}", "name": "web_search",
                      "arguments": json.dumps({"query": f"gold 2000 q{n}{j}"})}
                     for j in range(calls_per_round)]
            yield "data: " + json.dumps({"type": "tool_calls", "calls": calls}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", fake_stream)

    async def run():
        return [c async for c in al.stream_agent_loop(
            "http://localhost:1234/v1", "qwen/qwen3.5-9b",
            [{"role": "user", "content": "Search the web: when did gold first pass $2,000?"}],
            max_rounds=max_rounds, max_tool_calls=budget, relevant_tools={"web_search", "web_fetch"},
        )]

    events = asyncio.run(run())
    text = "".join(json.loads(e[6:]).get("delta", "") for e in events
                   if e.startswith("data: {") and '"delta"' in e)
    return seen, executed, events, text


def _tools_offered(request):
    return bool((request.get("kwargs") or {}).get("tools"))


def test_budget_hit_gets_one_tool_free_answer_round(monkeypatch):
    seen, executed, events, text = _run(monkeypatch, budget=5)
    assert len(executed) == 5, "the budget itself must still hold"
    assert any('"budget_exceeded"' in e for e in events)
    assert all(_tools_offered(r) for r in seen[:-1]), "the scripted rounds before the budget had tools"
    last = seen[-1]
    assert not _tools_offered(last), "the answer round must offer no tools"
    assert any(m.get("role") == "system" and "budget" in str(m.get("content")) for m in last["messages"])
    assert "August 2020" in text
    assert text.index(budget_answer.notice(5).strip()) < text.index("August 2020"), \
        "Odysseus's notice stands above the answer"


def test_the_answer_round_asks_for_facts_from_the_results_only():
    content = budget_answer.answer_message(20)["content"]
    assert "only" in content and "Do not fill gaps from memory" in content
    assert "could not find it" in content


def test_every_tool_call_of_the_cut_batch_has_a_result(monkeypatch):
    # 3 calls per round, budget 4: round 2 runs one call and cuts two.
    seen, executed, _, _ = _run(monkeypatch, budget=4, calls_per_round=3)
    assert len(executed) == 4
    msgs = seen[-1]["messages"]
    asked = [tc["id"] for m in msgs if m.get("role") == "assistant" for tc in m.get("tool_calls") or []]
    answered = {m.get("tool_call_id"): m.get("content") for m in msgs if m.get("role") == "tool"}
    assert asked and set(asked) == set(answered), (asked, list(answered))
    assert sum(1 for v in answered.values() if v == budget_answer.NOT_RUN) == 2


def test_tool_calls_in_the_answer_round_are_discarded_and_it_ends(monkeypatch):
    # A model that ignores the instruction and asks for tools again.
    seen, executed, _, text = _run(monkeypatch, budget=4, tool_call_in_answer_round=True)
    assert len(executed) == 4, "nothing may execute after the budget"
    # rounds 1–2 use the budget, round 3's calls are cut, round 4 is the only extra one
    assert len(seen) == 4
    assert not _tools_offered(seen[-1])
    assert text.strip(), "an empty answer round still ends with the loop's own fallback text"


def test_unlimited_budget_is_unchanged(monkeypatch):
    seen, executed, events, _ = _run(monkeypatch, budget=0, answer_in_round=4)
    assert len(executed) == 6 and len(seen) == 4
    assert not any('"budget_exceeded"' in e for e in events)
    assert all(_tools_offered(r) for r in seen)


def test_a_turn_that_answers_within_the_budget_is_unchanged(monkeypatch):
    seen, executed, events, _ = _run(monkeypatch, budget=20, answer_in_round=2)
    assert len(executed) == 2 and len(seen) == 2
    assert not any('"budget_exceeded"' in e for e in events)
    assert not any(m.get("role") == "system" and "tool-call budget" in str(m.get("content"))
                   for r in seen for m in r["messages"])
    assert "tool budget" not in _run(monkeypatch, budget=20, answer_in_round=2)[3], "no notice without a budget stop"


def test_budget_hit_on_the_last_round_still_gets_its_answer_round(monkeypatch):
    # 2 calls per round, budget 3, cap 2 rounds: round 2 (the last) runs one
    # call and cuts one — the 2026-10-13 evening case (budget and cap both 20).
    seen, executed, events, text = _run(monkeypatch, budget=3, max_rounds=2)
    assert len(executed) == 3
    assert len(seen) == 3, "one round past the cap, only to answer"
    assert not _tools_offered(seen[-1])
    assert "August 2020" in text
    assert not any('"rounds_exhausted"' in e for e in events), "the turn ended with an answer"


def test_running_out_of_rounds_without_a_forced_answer_is_unchanged(monkeypatch):
    # Unlimited budget, a model that never stops: the cap still holds and the
    # client still gets rounds_exhausted (its "Continue" button).
    seen, executed, events, _ = _run(monkeypatch, budget=0, max_rounds=3)
    assert len(seen) == 3 and len(executed) == 6
    assert any('"rounds_exhausted"' in e for e in events)


def test_a_promise_in_the_answer_round_does_not_start_another_round(monkeypatch):
    # "Let me search…" in a tool-free round would otherwise trigger the
    # intent-without-action nudge, which asks for a tool call there is no tool for.
    seen, executed, _, _ = _run(monkeypatch, budget=4, answer_text="Let me search for that.")
    assert len(executed) == 4
    assert len(seen) == 4, "rounds 1–3 plus exactly one answer round"
