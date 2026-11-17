"""Default test config: rule-based (heuristic) OCEAN AI; LLM opt-in only.

CI and local pytest run without outbound LLM calls unless explicitly enabled:
  WS_RUN_LLM_TESTS=1  and  WS_COUNSEL_API_KEY (+ WS_LLM_ENABLED / WS_LLM_DECISIONS)

LLM code remains in the tree — fenced by markers + env, not deleted.
"""

from __future__ import annotations

import os

import pytest


def _truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "llm: live or injected LLM paths (opt-in; skipped without key/flag)",
    )
    config.addinivalue_line(
        "markers",
        "rule: rule-based / heuristic OCEAN AI (default)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip @pytest.mark.llm unless WS_RUN_LLM_TESTS=1 and an API key is present.

    Injected mock completers still need the marker so CI never bills by accident;
    set WS_RUN_LLM_TESTS=1 to exercise those paths locally.
    """
    run_llm = _truthy("WS_RUN_LLM_TESTS")
    has_key = bool(
        (os.environ.get("WS_COUNSEL_API_KEY") or os.environ.get("WS_CHRONICLE_API_KEY") or "").strip()
    )
    # Allow pure injection tests when explicitly opted in even without a real key
    allow = run_llm
    skip = pytest.mark.skip(
        reason=(
            "LLM tests opt-in only: set WS_RUN_LLM_TESTS=1 "
            "(and WS_COUNSEL_API_KEY for live HTTP; mock injection still needs the flag)"
        )
    )
    for item in items:
        if "llm" in item.keywords and not allow:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _rule_ai_defaults(monkeypatch: pytest.MonkeyPatch):
    """Force heuristic decision mode for every test unless it is marked llm."""
    # Applied to all tests; llm-marked tests may override inside the test body.
    monkeypatch.setenv("WS_DECISION_MODE", "heuristic")
    monkeypatch.setenv("WS_DECISION_AGENTS", "1")
    monkeypatch.delenv("WS_LLM_ENABLED", raising=False)
    monkeypatch.delenv("WS_LLM_DECISIONS", raising=False)
    monkeypatch.delenv("WS_FIELD_AI", raising=False)
    # Clear any leftover mock completer from a prior llm test
    try:
        from engine.decision_llm import set_mock_complete

        set_mock_complete(None)
    except Exception:  # noqa: BLE001
        pass
    yield
