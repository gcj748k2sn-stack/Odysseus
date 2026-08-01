"""Thinking suppression must reach the UTILITY model — docs/todo.md item 44.

`/api/documents/ai-tidy` returned `500` on every logged call for three days.
Two independent faults; this file covers the second half of the first one.

Measured 2026-08-01: the call runs on `nemotron-3-nano:4b` with
`max_tokens=200` and came back `finish_reason=length chars=0` every time. The
same call at 700 finished cleanly with **295 characters (~80 tokens) of answer
after ~29 s ≈ ~300 generated tokens** — so roughly **220 tokens of thinking
before the answer started**, which is why a 200-token budget never reached it.

**The cause was an omission, not a bug:** `"nemotron"` appeared in neither
`_THINKING_MODEL_PATTERNS` nor `_QWEN_THINKING_PATTERNS`, so on this path
**no suppression was attempted at all** — not attempted and rejected, not
attempted and ignored. Nothing was sent.

**Why a new predicate rather than a rename.** `_is_qwen_thinking_model` also
gates the agent/streaming path, where widening the set changes what the CHAT
model does mid-turn, and nothing has measured that. `_accepts_reasoning_effort`
is a deliberate superset used only by `llm_call_async` — the non-streaming
utility path, where thinking is pure token waste and the existing code already
says so. The two stay separate until something measures the other.

⚠️ **The fix is a hypothesis and this file cannot settle it.** These tests pin
that the flag is now SENT. Whether Ollama honours `reasoning_effort` for this
model is a live question — the existing comment warns Ollama rejects it on
models without the capability, in which case the call fails loudly (HTTP 400,
now naming its exception type) rather than silently. **One tidy run decides
it, and the `[finish-reason]` line reports the verdict either way.**
"""

import pytest

from tests.helpers.import_state import clear_fake_database_modules

clear_fake_database_modules()

import src.llm_core as llm_core


# --------------------------------------------------------------------------
# Negative controls. A predicate that matches everything gates nothing.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("model", [
    "",
    "llama3.2:3b",
    "all-minilm:l6-v2",
    "mistral-small",      # matches _THINKING_MODEL_PATTERNS, NOT this one
    "gemma3:12b",         # the model the narrow gate was written for
])
def test_models_outside_the_set_are_not_offered_reasoning_effort(model):
    """`gemma3` is the reason this gate is narrow at all.

    It matches the broad thinking-pattern list, and the existing comment
    records that Ollama rejects `reasoning_effort` for it. Widening the new
    predicate to the broad list would re-create that bug.
    """
    assert llm_core._accepts_reasoning_effort(model) is False


def test_the_agent_gate_is_left_alone():
    """The Qwen predicate must NOT have grown — the streaming/agent path uses
    it, and widening that changes chat behaviour mid-turn.

    This is the control on the *shape* of the change: adding "nemotron" to
    `_QWEN_THINKING_PATTERNS` instead would have passed every other test here
    and quietly altered the chat model's rounds.
    """
    assert llm_core._is_qwen_thinking_model("nemotron-3-nano:4b") is False
    assert "nemotron" not in llm_core._QWEN_THINKING_PATTERNS


# --------------------------------------------------------------------------
# The omission itself.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("model", [
    "nemotron-3-nano:4b",
    "Nemotron-3-Nano:4B",
    "nemotron:latest",
])
def test_the_utility_model_is_now_offered_reasoning_effort(model):
    assert llm_core._accepts_reasoning_effort(model) is True


def test_the_utility_model_reaches_the_outer_gate_too():
    """`reasoning_effort` is nested inside `if _supports_thinking(model)`.

    So the broad list had to grow as well — without this the new predicate is
    never consulted and the fix is a no-op. Checking one without the other is
    how this could ship looking correct and do nothing.
    """
    assert llm_core._supports_thinking("nemotron-3-nano:4b") is True


def test_qwen_still_qualifies_on_both_predicates():
    """Regression control: the model this suppression was built for."""
    for m in ("qwen3.5:9b-64k", "qwq:32b"):
        assert llm_core._supports_thinking(m) is True
        assert llm_core._accepts_reasoning_effort(m) is True
        assert llm_core._is_qwen_thinking_model(m) is True
