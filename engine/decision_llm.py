"""Optional HTTP completion for structured OCEAN decision agents.

Stdlib only. Never required for offline play — heuristic path is the default.
Cost caps: short system prompt, compact snapshot, max_tokens, JSON-only,
and admit_llm_call / WS_LLM_DECISIONS gate.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

# Injected by tests / dry-run playtest (returns JSON text or list/dict).
_mock_complete: Callable[[str], Any] | None = None

SYSTEM_PROMPT = """Warring States figure decision layer (actions, not speech).
Act like a game AI: strategy in the snapshot is a SOFT PRIOR / bias only — respond to
board circumstances each tick (qin_pressure, cohesion, grain, fronts, betrayal,
chu latency/sts). Do NOT always-do-X for a strategy label.
Each figure: Big Five (OCEAN) + role + memory + board line.
Return ONLY JSON {\"decisions\":[...]} (one object per figure_id). Schema:
{"figure_id":str,"home":str,
 "stance":"contribute"|"withhold"|"defect",
 "alliance_lean":0..1,
 "offensive_pref":"none"|"peer:<id>"|"qin"|"alliance_qin",
 "invest_pref":"none"|"tech"|"agriculture"|"construction"|"military"|"mediation",
 "invest_target":"chu"|"qi"|"zhao"|"han"|"wei"|"yan"|"none",
 "intervene_pref":"none"|"chu"|"qi"|"qin",
 "rationale_tag":"<=24 chars"}
Rules: high A→contribute; high N→withhold; low A+threat→defect.
Crisis (high P, low C): prefer alliance/contribute/intervene even if war-biased.
Low grain / open fronts: avoid new peer war; invest agriculture or mediation.
Qin figures lean defect/offensive. No markdown. English only. No Chinese."""


def set_mock_complete(fn: Callable[[str], Any] | None) -> None:
    """Install (or clear) a mock completer for fixtures / dry-run playtests."""
    global _mock_complete
    _mock_complete = fn


def complete_decisions_json(snapshot: str) -> str:
    """One batched completion → raw text (JSON list). Raises on hard failure."""
    from .llm_gate import admit_llm_call, llm_decisions_enabled

    if _mock_complete is not None:
        out = _mock_complete(snapshot)
        if isinstance(out, (list, dict)):
            return json.dumps(out)
        return str(out)

    if not llm_decisions_enabled():
        raise RuntimeError("llm_decisions_disabled")
    if not admit_llm_call():
        raise RuntimeError("llm_denied")
    api_key = (os.environ.get("WS_COUNSEL_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("no_api_key")
    base = (os.environ.get("WS_COUNSEL_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = (
        os.environ.get("WS_DECISION_MODEL")
        or os.environ.get("WS_COUNSEL_MODEL")
        or "gpt-4o-mini"
    ).strip()
    max_tokens = int(os.environ.get("WS_DECISION_MAX_TOKENS") or "500")
    max_tokens = max(120, min(800, max_tokens))

    user = "Figures+world (compact):\n" + str(snapshot)[:2800]
    user += "\n\nJSON list only."

    url = f"{base}/chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "temperature": 0.35,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    # Prefer JSON mode when the host supports it (OpenAI-compatible).
    if (os.environ.get("WS_DECISION_JSON_MODE") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        body["response_format"] = {"type": "json_object"}
        user = (
            "Return a JSON object {\"decisions\":[...]} with one object per figure.\n"
            + user
        )
        body["messages"][1]["content"] = user

    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    timeout = float(os.environ.get("WS_DECISION_TIMEOUT_SEC") or "12")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"http_{exc.code}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(type(exc).__name__) from exc

    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("empty_choices")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if not content:
        raise RuntimeError("empty_content")
    return str(content)
