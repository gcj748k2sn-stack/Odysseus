"""A chat's retrieved tool set stays stable on local servers (prompt-cache prefix).

notes/todo.md, "A different tool set per message defeats prompt caching on
local servers"; measured with the prefix probe on 2026-10-08.
"""
from pathlib import Path

import pytest

from src import sticky_tools as S

LOCAL = "http://localhost:8090/v1"


@pytest.fixture(autouse=True)
def _clean():
    S._sets.clear()
    yield
    S._sets.clear()


def test_follow_up_keeps_earlier_tools():
    assert S.stabilize("c1", LOCAL, "m", {"python", "ask_user"}) == {"python", "ask_user"}
    assert S.stabilize("c1", LOCAL, "m", {"manage_tasks", "ask_user"}) == {"python", "ask_user", "manage_tasks"}
    # a third message that needs nothing new sends exactly the same set again
    assert S.stabilize("c1", LOCAL, "m", {"ask_user"}) == {"python", "ask_user", "manage_tasks"}


@pytest.mark.parametrize("url", ["https://api.openai.com/v1", "https://openrouter.ai/api/v1", ""])
def test_remote_endpoints_are_untouched(url):
    S.stabilize("c1", url, "m", {"a"})
    assert S.stabilize("c1", url, "m", {"b"}) == {"b"}


@pytest.mark.parametrize("url", ["http://127.0.0.1:1234/v1", "http://192.168.0.5:8090/v1",
                                 "http://localhost:11434/v1", "http://mac.local:1234/v1"])
def test_local_and_lan_endpoints_count_as_local(url):
    assert S.is_local_endpoint(url)


def test_chats_and_models_are_separate():
    S.stabilize("c1", LOCAL, "m", {"a"})
    assert S.stabilize("c2", LOCAL, "m", {"b"}) == {"b"}
    assert S.stabilize("c1", LOCAL, "other-model", {"b"}) == {"b"}


def test_no_session_or_no_tools_passes_through():
    assert S.stabilize(None, LOCAL, "m", {"a"}) == {"a"}
    assert S.stabilize("c1", LOCAL, "m", None) is None
    assert S.stabilize("c1", LOCAL, "m", set()) == set()


def test_union_past_the_cap_resets_to_the_current_set():
    first = {f"t{i}" for i in range(S.MAX_TOOLS)}
    S.stabilize("c1", LOCAL, "m", first)
    assert S.stabilize("c1", LOCAL, "m", {"new"}) == {"new"}


def test_wired_after_retrieval_and_before_every_filter():
    src = Path(S.__file__).with_name("agent_loop.py").read_text(encoding="utf-8")
    call = src.index("stabilize_tool_set(session_id, endpoint_url, model, set(_relevant_tools))")
    assert src.rindex("Keyword fallback selected", 0, call) < call
    guard = src.rindex("if not guide_only and not relevant_tools and _relevant_tools is not None:", 0, call)
    assert call - guard < 200, "skipped when the caller provides its own tool set"
    for later in ("If deterministic domain detection fired", "If this turn targets the open document",
                  "Browser gate.", "Per-request forced tools"):
        assert src.index(later) > call, later
