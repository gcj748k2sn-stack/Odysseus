"""When a turn uses up its tool budget, give the model one tool-free round to answer.

Without this, reaching ``agent_max_tool_calls`` ended the turn on the spot and
everything the model had gathered was thrown away; the user saw only the turn
report's "stopped without producing an answer" (notes: item 85, *The tool
budget ends the turn without an answer*).

The answer round reuses the loop-breaker's ``_force_answer`` path in
``stream_agent_loop``: no tool schemas are sent and any tool call the model
emits anyway is discarded, so the round can only write text. That bound is
the point: an earlier "finish the job now" nudge with tools still available
wiped a document (notes: *The agent gathers information, then stops*).
"""

NOT_RUN = "Not run: the tool-call budget for this turn was reached."


def should_answer(force_answer_active: bool) -> bool:
    """One answer round, only if none is running yet."""
    return not force_answer_active


def round_allowed(round_num: int, max_rounds: int, force_answer_active: bool) -> bool:
    """Rounds up to the cap run as before; one more runs only to answer.

    The budget is usually hit on the last round: Qwen makes about one call per
    round, and agent_max_tool_calls and agent_max_rounds are both 20 on the
    M1, so without the extra round the answer round was
    skipped every time (2026-10-13 evening runs)."""
    return round_num <= max_rounds or (round_num == max_rounds + 1 and force_answer_active)


def pad_results(n_calls: int, texts: list) -> list:
    """Every call of the cut batch gets a result: the native protocol needs
    one tool message per tool_call id, and an empty one reads as a failure."""
    return list(texts) + [NOT_RUN] * max(0, n_calls - len(texts))


def answer_message(limit: int) -> dict:
    # Facts only from the results: in the first live test (2026-10-14, budget
    # 4) Qwen filled the gap from memory with a wrong year, twice.
    return {
        "role": "system",
        "content": (
            f"The tool-call budget for this turn ({limit} calls) is used up, so no "
            "tools are available any more. Write your final answer now, using only "
            "facts that appear in the tool results above. Do not fill gaps from "
            "memory. If the results do not contain the answer, say plainly that you "
            "could not find it, and in one or two sentences what you did find."
        ),
    }


def notice(limit: int) -> str:
    """Odysseus's own line above the answer, so a partial answer is not read as a
    finished one. Written by the server, not the model; changes nothing."""
    return (f"⚠️ The tool budget for this turn ({limit} calls) ran out before the search "
            "was finished. The answer below uses only what was found so far and may "
            "be incomplete.\n\n")
