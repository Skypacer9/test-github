"""Shared LLM enable + rate-limit force-stub gate (stdlib only)."""

from __future__ import annotations

import os
from contextvars import ContextVar

# Per-request override used by the Flask layer when rate-limited.
force_stub_llm: ContextVar[bool] = ContextVar("force_stub_llm", default=False)


def llm_env_enabled() -> bool:
    """True when an API key is present unless WS_LLM_ENABLED explicitly disables.

    Demo default keeps LLM on when keyed. Force stub with WS_LLM_ENABLED=0 or
    the per-request force_stub_llm context (rate-limit fallback).
    """
    if force_stub_llm.get():
        return False
    flag = (os.environ.get("WS_LLM_ENABLED") or "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    key = (
        os.environ.get("WS_COUNSEL_API_KEY")
        or os.environ.get("WS_CHRONICLE_API_KEY")
        or ""
    ).strip()
    return bool(key)
