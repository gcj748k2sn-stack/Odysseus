"""bench_agent.py: which stream errors stop a run and which are results.

A server that cannot answer stops the run (result not saved, resume later).
A chat template refusing what Odysseus sent is Odysseus's result: recorded
as a failure with the flag ``request_rejected``, and the run goes on.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("bench_agent_errors_under_test", ROOT / "scripts" / "bench_agent.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

# The two records Odysseus sent for one rejected request (llama.cpp, Bonsai 2).
TEMPLATE_500 = str({"status": 500, "text": (
    "local endpoint is having an outage (HTTP 500). ------------\nWhile executing CallExpression at line "
    "100, column 24 in source:\n...lti_step_tool %}↵    {{- raise_exception('No user query found in "
    "messages.') }}↵...")})[:300]
TERMINAL_500 = str({"message": "Model request failed (HTTP 500)", "status": 500})[:300]


def test_template_rejection_is_a_result_not_a_server_fault():
    assert B.classify_stream_errors([TEMPLATE_500, TERMINAL_500]) == ([], ["request_rejected"])


def test_a_bare_500_still_stops_the_run():
    infra, flags = B.classify_stream_errors([TERMINAL_500])
    assert infra == [TERMINAL_500] and flags == []


def test_lm_studio_compute_error_still_stops_the_run():
    err = "LM Studio: Compute error."
    assert B.classify_stream_errors([err]) == ([err], [])


def test_model_loops_are_results():
    loop = str({"status": 502, "text": "Stopped generation: bonsai2-27b started repeating tokens"})
    assert B.classify_stream_errors([loop, TERMINAL_500.replace("500", "502")]) == ([], [])


def test_no_errors():
    assert B.classify_stream_errors([]) == ([], [])
