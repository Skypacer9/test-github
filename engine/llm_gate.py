"""Shared LLM enable + rate-limit force-stub gate (stdlib only)."""

from __future__ import annotations

import os
from contextvars import ContextVar

# Per-request override used by the Flask layer when rate-limited.
force_stub_llm: ContextVar[bool] = ContextVar("force_stub_llm", default=False)


def llm_env_enabled() -> bool:
    """True only when operator explicitly opts in AND an API key is present."""
    if force_stub_llm.get():
        return False
    flag = (os.environ.get("WS_LLM_ENABLED") or "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return False
    key = (
        os.environ.get("WS_COUNSEL_API_KEY")
        or os.environ.get("WS_CHRONICLE_API_KEY")
        or ""
    ).strip()
    return bool(key)
