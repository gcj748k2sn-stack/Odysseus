"""Reasoning effort from the preset, sent to llama.cpp as a chat-template kwarg.

Bonsai 2's chat template reads `reasoning_effort` and accepts exactly `xhigh`
(default), `medium` and `low`; any other value raises a template error, so
every request would fail. `xhigh` and `low` add an instruction sentence to the
system block, `medium` adds none. PrismML: `medium` thinks less than `xhigh`
at about the same accuracy; `low` "is not supported and … will behave close
to `xhigh`". llama.cpp merges a request's `chat_template_kwargs` over the
server's `--chat-template-kwargs`, so the preset can override
`start_bonsai2.sh` per chat.

The effort is resolved once per chat request (`set_for_preset`, called where
the preset is read) and added to every model request of that turn (`apply`),
so all rounds of a turn render the same system block. Changing the effort
between messages changes the prompt prefix, so the next message re-reads the
whole prompt once. Empty means "server default": nothing is sent.
"""
from __future__ import annotations

import contextvars
import logging
from typing import Any, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

# "" = server default. Bonsai 2's template raises on anything else ("high" too).
VALUES = ("", "low", "medium", "xhigh")

_effort: contextvars.ContextVar[str] = contextvars.ContextVar("reasoning_effort", default="")


def normalize(value: Any) -> str:
    v = str(value or "").strip().lower()
    return v if v in VALUES else ""


def from_preset(preset: Optional[Mapping[str, Any]]) -> str:
    """The effort a preset asks for; "" for none, a disabled preset, or junk."""
    if not isinstance(preset, Mapping) or preset.get("enabled") is False:
        return ""
    return normalize(preset.get("reasoning_effort"))


def set_for_preset(preset_id: Optional[str], preset: Optional[Mapping[str, Any]]) -> str:
    """Remember the preset's effort for the rest of this request; returns it."""
    effort = from_preset(preset)
    _effort.set(effort)
    if effort:
        logger.info("[reasoning-effort] preset=%s effort=%s", preset_id, effort)
    return effort


def current() -> str:
    return _effort.get()


def apply(payload: Dict[str, Any], self_hosted: bool) -> None:
    """Add the request's effort to an outgoing payload, in place.

    Only for self-hosted OpenAI-compatible servers (llama.cpp, LM Studio):
    cloud APIs reject unknown top-level fields. Not gated on Ollama: upstream's
    Ollama /v1 check matches every localhost /v1 URL, llama.cpp's included,
    and Ollama ignores the field. A kwarg already in the payload wins.
    """
    effort = _effort.get()
    if not effort or not self_hosted:
        return
    kwargs = payload.get("chat_template_kwargs")
    kwargs = dict(kwargs) if isinstance(kwargs, Mapping) else {}
    kwargs.setdefault("reasoning_effort", effort)
    payload["chat_template_kwargs"] = kwargs
