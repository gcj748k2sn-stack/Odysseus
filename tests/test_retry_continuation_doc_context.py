""""try again" must keep task context on document/research turns too.

`_is_contextual_retry_continuation` decides whether a terse follow-up ("try
again", "why did u stop") may inherit earlier user turns when selecting tools
and building context. It only recognised Cookbook vocabulary, so after a
document correction that silently did nothing — the exact b5fe4ef5 situation —
"why did u stop, try again" classified as a fresh low-signal turn and the
retry lost the task it was retrying.

Both context sets stay deliberately narrow: the words have to have actually
been used in the recent turns. Ordinary chat must not inherit stale context
just because someone said "again".
"""

from src.agent_loop import _is_contextual_retry_continuation


def _msgs(*user_turns):
    return [{"role": "user", "content": t} for t in user_turns]


# --------------------------------------------------------------------------
# Document / research follow-ups — the gap being closed
# --------------------------------------------------------------------------

def test_why_did_u_stop_after_a_correction_turn():
    """The observed phrasing, after the document turn that did nothing."""
    msgs = _msgs("create a document about pink oyster growth phases",
                 "fact check and correct the dokument")
    assert _is_contextual_retry_continuation(msgs, "why did u stop, try again")


def test_plain_try_again_after_an_edit_request():
    msgs = _msgs("edit the document and fix the temperatures")
    assert _is_contextual_retry_continuation(msgs, "try again")


def test_research_follow_up():
    msgs = _msgs("research pink oyster fruiting conditions and cite sources")
    assert _is_contextual_retry_continuation(msgs, "that failed, retry")


def test_report_and_rewrite_vocabulary():
    for turn in ("write a report on the sensor data",
                 "rewrite the summary section",
                 "add citations to the article"):
        assert _is_contextual_retry_continuation(_msgs(turn), "try again"), turn


# --------------------------------------------------------------------------
# Existing behaviour must be untouched
# --------------------------------------------------------------------------

def test_cookbook_context_still_works():
    msgs = _msgs("serve minimax m2.7 on the gpu box")
    assert _is_contextual_retry_continuation(msgs, "try again it failed")


def test_ordinary_chat_does_not_inherit_context():
    """No task vocabulary anywhere — "again" alone must not carry context."""
    msgs = _msgs("what's the capital of France?")
    assert not _is_contextual_retry_continuation(msgs, "say that again")


def test_retry_words_are_still_required():
    """Document context alone isn't a retry; the follow-up has to ask for one."""
    msgs = _msgs("fact check and correct the document")
    assert not _is_contextual_retry_continuation(msgs, "thanks, looks good")


def test_empty_follow_up_is_not_a_retry():
    assert not _is_contextual_retry_continuation(_msgs("edit the document"), "")
