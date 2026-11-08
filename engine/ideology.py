"""Ideology weight hooks — packets drive raids, sync/loyalty, tech, counsel.

Not UI-only. Living agents carry `packet_weights` (syncretic mix of bases +
overlays). Compact readout + rare capped combo bonuses tip real dials.

Bases (see packets.BASE_SCHOOLS):
  legalist_fa · mohist_shangxian · dao_guodian · ru_li
Overlays / syncretisms: chu_patron_client · tianxia_da_yitong · guanzi ·
  huang_lao · lineage_shi · …

Hooks (call sites):
  - conflict.ideology_raid_score — Legalist↑ raid; Mohism/tianxia/patron↓ raid
  - agents.decide_action — Mohism/tianxia/patron↑ contribute; Legalist↑ defect
  - patron_client.sync_bonus / tick — Mohist/patron/tianxia↑ loyalty & sync
  - tech.tick_tech — slight adoption friction + rare Eureka bias from combos
  - counsel._stub_row / apply_counsel_tips — banks + loyalty_shift tips
  - chronicle.assess_cultural_pattern — bloc ideology mix colors state/tone

Unusual combos (rare, capped): see `rare_combo_bonus`.
"""

from __future__ import annotations

import hashlib
from typing import Any

# Hard caps — bonuses stay small even when combos fire
COMBO_TECH_ADOPT_CAP = 0.012
COMBO_EUREKA_CAP = 0.08
COMBO_LOYALTY_CAP = 0.035
COMBO_RAID_CAP = 0.10
COMBO_SYNC_CAP = 1.5  # cohesion points
# Rarity: ~8% when combo qualifies (deterministic hash)
COMBO_FIRE_PCT = 8


def packet_w(ag: Any, key: str) -> float:
    weights = getattr(ag, "packet_weights", None) or {}
    try:
        return float(weights.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def ideology_vector(ag: Any) -> dict[str, float]:
    """Compact ideology readout from packet_weights + trait affinity dials."""
    traits = getattr(ag, "traits", None)
    legalist = packet_w(ag, "legalist_fa") + 0.35 * float(getattr(traits, "legalist_centralism", 0.0) or 0.0)
    mohist = packet_w(ag, "mohist_shangxian")
    dao = packet_w(ag, "dao_guodian")
    ru = packet_w(ag, "ru_li")
    tianxia = packet_w(ag, "tianxia_da_yitong") + 0.25 * float(getattr(traits, "tianxia_unity", 0.0) or 0.0)
    patron = packet_w(ag, "chu_patron_client")
    guanzi = packet_w(ag, "guanzi")
    lineage = packet_w(ag, "lineage_shi") + 0.2 * float(getattr(traits, "lineage_honor", 0.0) or 0.0)
    huang = packet_w(ag, "huang_lao")
    soft = tianxia + patron + 0.55 * mohist + 0.25 * dao + 0.15 * ru
    hard = legalist + 0.25 * guanzi
    return {
        "legalist": max(0.0, legalist),
        "mohist": max(0.0, mohist),
        "dao": max(0.0, dao),
        "ru": max(0.0, ru),
        "tianxia": max(0.0, tianxia),
        "patron": max(0.0, patron),
        "guanzi": max(0.0, guanzi),
        "lineage": max(0.0, lineage),
        "huang_lao": max(0.0, huang),
        "soft": max(0.0, soft),
        "hard": max(0.0, hard),
    }


def bloc_ideology_means(world: Any) -> dict[str, float]:
    """Mean ideology across living non-annexed agents (chronicle / alliance)."""
    keys = ("legalist", "mohist", "dao", "ru", "tianxia", "patron", "soft", "hard", "guanzi", "huang_lao")
    acc = {k: 0.0 for k in keys}
    n = 0
    for ag in getattr(world, "agents", {}).values():
        if ag is None or getattr(ag, "annexed", False):
            continue
        if float(getattr(ag, "viability", 0.0) or 0.0) <= 0:
            continue
        v = ideology_vector(ag)
        for k in keys:
            acc[k] += v.get(k, 0.0)
        n += 1
    if n <= 0:
        return acc
    return {k: acc[k] / n for k in keys}


def loyalty_sync_bias(ag: Any) -> float:
    """Mohist / patron / tianxia → positive loyalty & clique-sync pull (0–~0.35)."""
    v = ideology_vector(ag)
    return min(0.35, 0.22 * v["mohist"] + 0.18 * v["patron"] + 0.16 * v["tianxia"] + 0.06 * v["dao"])


def tech_adoption_bias(ag: Any) -> float:
    """Slight adoption friction multiplier delta (−0.05..+0.08). Mohist/dao/huang↑; lineage↓ slightly."""
    v = ideology_vector(ag)
    raw = 0.06 * v["mohist"] + 0.05 * v["dao"] + 0.04 * v["huang_lao"] + 0.03 * v["legalist"] - 0.04 * v["lineage"]
    return max(-0.05, min(0.08, raw))


def eureka_bias(ag: Any) -> float:
    """Slight Eureka threshold ease (positive = more likely). Capped small."""
    v = ideology_vector(ag)
    raw = 0.05 * v["mohist"] + 0.04 * v["dao"] + 0.03 * v["huang_lao"] + 0.02 * v["legalist"]
    return max(0.0, min(0.10, raw))


def _combo_roll(tick: int, sid: str, kind: str) -> bool:
    h = hashlib.sha256(f"{tick}|{sid}|{kind}|ideo-combo".encode()).hexdigest()
    return (int(h[:8], 16) % 100) < COMBO_FIRE_PCT


def rare_combo_bonus(ag: Any, *, tick: int = 0, sid: str | None = None) -> dict[str, float]:
    """Unusual ideology mixes → rare small bonuses (tech / loyalty / raid). Capped.

    Combos (need both limbs elevated — unusual for most courts):
      - mohist+legalist (merit-fa tension) → tech eureka crumb
      - dao+legalist / huang_lao peak → adoption crumb
      - mohist+patron+tianxia stack → loyalty/sync crumb
      - guanzi+legalist → tiny raid crumb (admin war-math)

    Fires ~COMBO_FIRE_PCT% when qualified; zeros otherwise.
    """
    out = {
        "tech_adopt": 0.0,
        "eureka": 0.0,
        "loyalty": 0.0,
        "raid": 0.0,
        "sync_cohesion": 0.0,
        "combo": "",
    }
    v = ideology_vector(ag)
    aid = sid or str(getattr(ag, "id", "x"))
    # mohist × legalist — unusual dual
    if v["mohist"] >= 0.22 and v["legalist"] >= 0.28 and _combo_roll(tick, aid, "mohist_fa"):
        out["eureka"] = min(COMBO_EUREKA_CAP, 0.05 + 0.04 * min(v["mohist"], v["legalist"]))
        out["tech_adopt"] = min(COMBO_TECH_ADOPT_CAP, 0.006)
        out["combo"] = "mohist_legalist"
        return out
    # dao × legalist or strong huang_lao — syncretic workshop lean
    if (v["dao"] >= 0.25 and v["legalist"] >= 0.25) or v["huang_lao"] >= 0.35:
        if _combo_roll(tick, aid, "dao_fa"):
            out["tech_adopt"] = min(COMBO_TECH_ADOPT_CAP, 0.008 + 0.01 * v["huang_lao"])
            out["eureka"] = min(COMBO_EUREKA_CAP, 0.04)
            out["combo"] = "dao_legalist"
            return out
    # mohist + patron + tianxia — loyalty/sync bloom (still rare)
    if v["mohist"] >= 0.18 and v["patron"] >= 0.22 and v["tianxia"] >= 0.20:
        if _combo_roll(tick, aid, "mohist_patron_tx"):
            out["loyalty"] = min(COMBO_LOYALTY_CAP, 0.02 + 0.02 * v["mohist"])
            out["sync_cohesion"] = min(COMBO_SYNC_CAP, 0.8 + 0.7 * v["patron"])
            out["combo"] = "mohist_patron_tianxia"
            return out
    # guanzi × legalist — admin war-math raid crumb
    if v["guanzi"] >= 0.28 and v["legalist"] >= 0.30 and _combo_roll(tick, aid, "guanzi_fa"):
        out["raid"] = min(COMBO_RAID_CAP, 0.05 + 0.04 * v["guanzi"])
        out["combo"] = "guanzi_legalist"
        return out
    return out
