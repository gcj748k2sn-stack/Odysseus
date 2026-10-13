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


def should_answer(force_answer_active: bool, round_num: int, max_rounds: int) -> bool:
    """One answer round, only if none is running yet and a round is left."""
    return not force_answer_active and round_num < max_rounds


def pad_results(n_calls: int, texts: list) -> list:
    """Every call of the cut batch gets a result: the native protocol needs
    one tool message per tool_call id, and an empty one reads as a failure."""
    return list(texts) + [NOT_RUN] * max(0, n_calls - len(texts))


def answer_message(limit: int) -> dict:
    return {
        "role": "system",
        "content": (
            f"The tool-call budget for this turn ({limit} calls) is used up, so no "
            "tools are available any more. Write your final answer now from the "
            "results already gathered above. If they do not answer the question, "
            "say in one or two sentences what you found and what is missing."
        ),
    }
