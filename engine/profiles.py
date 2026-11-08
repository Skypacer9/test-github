"""Load docs/big-five-historical-profiles.json into state-agent priors.

Speculative design priors from Shiji historiography — not clinical FFM scores.
Excluded: Ling and other design-fiction cast (see JSON meta.excluded).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

# Agent-store docs/ sits two levels above sim/engine/
_DOCS = Path(__file__).resolve().parents[2] / "docs"
_PROFILES_PATH = _DOCS / "big-five-historical-profiles.json"

# Map meso state agents → JSON profile id(s). Blends listed when multiple.
STATE_PROFILE_MAP: dict[str, list[str]] = {
    "qin": ["qin-zhaoxiang", "qin-ying-zheng"],  # Zhaoxiang early-era face; Zheng later
    "chu": ["chu-king-kaolie", "chu-king-you", "chu-nobility-faction"],  # You = post-238 weak successor  # court + aristocratic drag
    "qi": ["qi-king-jian-isolationist-court"],
    # Zhao/Han/Wei/Yan: no named JSON rows yet — scaffold mid priors (not fiction cast)
}

# Optional advisor overlays (not separate state agents in MVP meso field)
ADVISOR_PROFILE_IDS = ("qin-li-si", "chu-lord-chunshen")


@lru_cache(maxsize=1)
def load_profile_pack() -> dict[str, Any]:
    if not _PROFILES_PATH.is_file():
        return {"meta": {"disclaimer": "missing profiles JSON"}, "profiles": []}
    text = _PROFILES_PATH.read_text(encoding="utf-8")
    return json.loads(text)


def profile_by_id(pid: str) -> dict[str, Any] | None:
    for row in load_profile_pack().get("profiles") or []:
        if row.get("id") == pid:
            return row
    return None


def _blend_ocean(rows: list[dict[str, Any]]) -> dict[str, float]:
    keys = ("O", "C", "E", "A", "N")
    out = {k: 0.5 for k in keys}
    if not rows:
        return out
    for k in keys:
        vals = [float((r.get("big_five") or {}).get(k, 0.5)) for r in rows]
        out[k] = sum(vals) / len(vals)
    # Chu blend: nobility O/N dominate status-threat; Kaolie A softens slightly
    if len(rows) == 2 and rows[0].get("id") == "chu-king-kaolie":
        nob = rows[1].get("big_five") or {}
        king = rows[0].get("big_five") or {}
        out["O"] = 0.4 * float(king.get("O", 0.42)) + 0.6 * float(nob.get("O", 0.28))
        out["N"] = 0.35 * float(king.get("N", 0.68)) + 0.65 * float(nob.get("N", 0.72))
        out["A"] = 0.55 * float(king.get("A", 0.62)) + 0.45 * float(nob.get("A", 0.32))
    return out


def ocean_for_state(state_id: str) -> dict[str, float]:
    """Return OCEAN 0–1 for a state agent, grounded in JSON when mapped."""
    ids = STATE_PROFILE_MAP.get(state_id, [])
    rows = [profile_by_id(i) for i in ids]
    rows = [r for r in rows if r]
    if rows:
        return _blend_ocean(rows)
    # Scaffold mid priors for Zhao/Han/Wei/Yan (historical states, thin dossier)
    defaults = {
        "zhao": {"O": 0.45, "C": 0.62, "E": 0.48, "A": 0.42, "N": 0.65},
        "han": {"O": 0.40, "C": 0.55, "E": 0.40, "A": 0.45, "N": 0.60},
        "wei": {"O": 0.48, "C": 0.55, "E": 0.50, "A": 0.45, "N": 0.55},
        "yan": {"O": 0.50, "C": 0.50, "E": 0.52, "A": 0.48, "N": 0.50},
    }
    return defaults.get(state_id, {"O": 0.5, "C": 0.5, "E": 0.5, "A": 0.5, "N": 0.5})


def profile_meta_for_state(state_id: str) -> dict[str, Any]:
    ids = STATE_PROFILE_MAP.get(state_id, [])
    rows = [profile_by_id(i) for i in ids if profile_by_id(i)]
    anchors: list[str] = []
    confidence = []
    for r in rows:
        anchors.extend(list(r.get("shiji_anchors") or []))
        confidence.append(str(r.get("confidence", "low")))
    return {
        "profile_ids": ids,
        "confidence": ",".join(confidence) if confidence else "scaffold",
        "shiji_anchors": anchors[:6],
        "disclaimer": (load_profile_pack().get("meta") or {}).get(
            "disclaimer",
            "Speculative design priors — not clinical scores.",
        ),
        "fiction": False,
    }


def advisor_brief(pid: str) -> dict[str, Any] | None:
    row = profile_by_id(pid)
    if not row:
        return None
    return {
        "id": row["id"],
        "name_en": row.get("name_en"),
        "name_zh": row.get("name_zh"),
        "role": row.get("role"),
        "big_five": row.get("big_five"),
        "confidence": row.get("confidence"),
        "shiji_anchors": list(row.get("shiji_anchors") or [])[:4],
        "fiction": False,
    }
