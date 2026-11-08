"""Shared LLM enable + per-request admit / force-stub gate (stdlib only)."""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Callable

# Per-request override used by the Flask layer when rate-limited or forcing stub.
force_stub_llm: ContextVar[bool] = ContextVar("force_stub_llm", default=False)

# Optional admit callback set by Flask: returns True if this LLM call may proceed
# (and should consume one unit of global+session budget).
_llm_admit: ContextVar[Callable[[], bool] | None] = ContextVar("llm_admit", default=None)


def llm_env_enabled() -> bool:
    """Opt-in only: requires WS_LLM_ENABLED=1|true|yes|on AND an API key.

    Default is OFF so public deploys with keys do not bill anonymous traffic.
    """
    if force_stub_llm.get():
        return False
    flag = (os.environ.get("WS_LLM_ENABLED") or "0").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return False
    key = (
        os.environ.get("WS_COUNSEL_API_KEY")
        or os.environ.get("WS_CHRONICLE_API_KEY")
        or ""
    ).strip()
    return bool(key)


def set_llm_admit(fn: Callable[[], bool] | None):
    """Install (or clear) the Flask-side budget consumer for this request."""
    return _llm_admit.set(fn)


def reset_llm_admit(token) -> None:
    _llm_admit.reset(token)


def admit_llm_call() -> bool:
    """True if an outbound LLM HTTP call is allowed right now.

    When a Flask admit callback is installed, it enforces global+session caps.
    Outside Flask (CLI/tests), falls back to llm_env_enabled() alone.
    """
    if force_stub_llm.get():
        return False
    if not llm_env_enabled():
        return False
    admit = _llm_admit.get()
    if admit is None:
        return True
    try:
        return bool(admit())
    except Exception:  # noqa: BLE001
        return False
