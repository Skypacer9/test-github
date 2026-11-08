"""Optional HTTP counsel completion. Stdlib only; never required for offline play."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

SYSTEM_PROMPT = """You are a thin Warring States figure-counsel layer.
The player channel is collective consciousness / counsel among figures —
not a person they remember, not talk-to-God. Soft priors only; refuse/hedge/flip OK.

VOICE (required): action-RPG gloss like Immortals Fenyx Rising x Fire Emblem —
vivid, lightly heroic, spoken in the moment — NOT an academic essay or historiography lecture.
Ground EACH utterance in (1) that figure's OCEAN priors from the snapshot, (2) period-English
aphorism / symbolism soft priors (syncretic paraphrase OK), (3) the field meters.
Each figure_id must have a DISTINCT voice and wording — never reuse the same line across
unrelated figures (Li Si ≠ Chu nobility).
Ideology gate: Chu patronage/tianxia figures must NEVER use Qin-Legalist aphorisms
(e.g. "when laws are clear, orders need few words"); Qi stays mercantile/Guanzi;
Qin may use fa/statute soft priors.
Role gate: speak AS that figure's role (ruler vs minister/chancellor vs general vs retainer).
Same event_tag must yield different perspective by role — never interchangeable voices.
English only — no Chinese characters.
Never dump long quotes; never invent campaigns.

Return ONLY a JSON list (1-4 objects; 1 if one-on-one). Each object:
{"figure_id":"...","home":"qin|chu|qi|...","stance_lean":"contribute|withhold|defect|hedge|refuse",
 "loyalty_shift": number in [-0.25,0.25],
 "event_tag":"patron_rebuke|legalist_probe|isolation_caution|sync_appeal|belief_cascade|personal_breakthrough|hedge|refuse|other",
 "utterance":"<=140 chars English only, vivid RPG tone"}
Rules: soft priors tip dials — do not rewrite PAS. No markdown fences if possible."""


def complete_counsel_json(field_snapshot: str, *, prompt: str | None = None) -> str:
    """One batched completion → raw text (JSON list). Raises on hard failure."""
    from .llm_gate import llm_env_enabled

    if not llm_env_enabled():
        raise RuntimeError("llm_disabled")
    api_key = (os.environ.get("WS_COUNSEL_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("no_api_key")
    base = (os.environ.get("WS_COUNSEL_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = (os.environ.get("WS_COUNSEL_MODEL") or "gpt-4o-mini").strip()
    user = "Field snapshot:\n" + field_snapshot
    if prompt:
        user += "\n\nPlayer prompt: " + str(prompt)[:400]
    user += "\n\nRespond with the JSON list only."

    url = f"{base}/chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "temperature": 0.7,
        "max_tokens": 700,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
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
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
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
