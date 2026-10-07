"""Which machines a prompt can name: configured Cookbook servers and SSH aliases,
nothing else.

The old check accepted "on|from" + ANY word, so "data from http://..." routed
to the Terminus branch and a document request became rounds of ping and port
scans (notes: "A LAN address in the prompt deletes every document tool"). The
rules text already says configured server names and SSH aliases are target
machines; this makes the check agree.

Sources, both re-read when their mtime changes:

- data/cookbook_state.json: env.servers[].name and .host (and the part after
  user@). "Local" and localhost are skipped; "this computer" is matched
  separately in agent_loop.
- ~/.ssh/config: Host aliases, skipping patterns (*, ?, !). Include is not
  followed. Only alias strings are kept, in memory; nothing from the file
  reaches a prompt.
"""
from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import FrozenSet, Iterable, Optional, Set

logger = logging.getLogger(__name__)

_SKIP_NAMES = {"local", "localhost", "127.0.0.1", "::1", "this machine", "here"}
_cache: dict = {}


def _clean(name) -> Optional[str]:
    if not isinstance(name, str):
        return None
    n = name.strip().strip('"').strip()
    n = re.sub(r":\d+$", "", n)  # host:port
    if len(n) < 2 or n.lower() in _SKIP_NAMES:
        return None
    return n


def cookbook_machine_names(path: str) -> Set[str]:
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    env = (state or {}).get("env") if isinstance(state, dict) else None
    servers = (env or {}).get("servers") if isinstance(env, dict) else None
    out: Set[str] = set()
    for s in servers or ():
        if not isinstance(s, dict):
            continue
        for raw in (s.get("name"), s.get("host")):
            n = _clean(raw)
            if n:
                out.add(n)
                if "@" in n:
                    tail = _clean(n.split("@", 1)[1])
                    if tail:
                        out.add(tail)
    return out


def ssh_config_aliases(path: str) -> Set[str]:
    out: Set[str] = set()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = re.split(r"[\s=]+", s, maxsplit=1)
            if len(parts) != 2 or parts[0].lower() != "host":
                continue
            for tok in parts[1].split():
                if any(c in tok for c in "*?!"):
                    continue
                n = _clean(tok)
                if n:
                    out.add(n)
    return out


def _read_cached(path: str, parser) -> FrozenSet[str]:
    try:
        mtime = os.stat(path).st_mtime_ns
    except OSError:
        _cache.pop(path, None)
        return frozenset()
    hit = _cache.get(path)
    if hit is None or hit[0] != mtime:
        try:
            names = frozenset(parser(path))
        except Exception as e:  # unreadable or malformed: no names, never an error
            logger.debug("named machines: could not read %s: %s", path, e)
            names = frozenset()
        _cache[path] = (mtime, names)
        hit = _cache[path]
    return hit[1]


def configured_machine_names(
    cookbook_path: Optional[str] = None, ssh_config_path: Optional[str] = None
) -> FrozenSet[str]:
    if cookbook_path is None:
        try:
            from src.constants import COOKBOOK_STATE_FILE as cookbook_path
        except Exception:
            cookbook_path = ""
    if ssh_config_path is None:
        ssh_config_path = os.path.expanduser("~/.ssh/config")
    names: Set[str] = set()
    if cookbook_path:
        names |= _read_cached(cookbook_path, cookbook_machine_names)
    if ssh_config_path:
        names |= _read_cached(ssh_config_path, ssh_config_aliases)
    return frozenset(names)


@lru_cache(maxsize=32)
def _names_regex(names: FrozenSet[str]):
    pats = []
    for name in sorted(names, key=len, reverse=True):
        parts = [re.escape(p) for p in re.split(r"[\s_-]+", name) if p]
        if parts:
            pats.append(r"[\s_-]+".join(parts))
    if not pats:
        return None
    # "on gpu-box", "from the gpu box", "on gpu-box." — not "on gpu-boxes",
    # not "on gpu-box.lan" unless that is the configured name.
    return re.compile(
        r"\b(?:on|from)\s+(?:the\s+)?(?:" + "|".join(pats) + r")(?![\w-]|\.\w)",
        re.IGNORECASE,
    )


def mentions_named_machine(text: str, names: Iterable[str]) -> bool:
    text = str(text or "")
    if not text.strip():
        return False
    rx = _names_regex(frozenset(n for n in names if n))
    return bool(rx and rx.search(text))
