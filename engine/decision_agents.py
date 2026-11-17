"""OCEAN → per-tick figure actions → world/state deltas.

Invariant (Odetta / WS-64): persona Big Five drives how characters *act* each
round; those acts change their countries that round via existing tick/API paths
(stance → trust/cohesion/pressure; invest/alliance/offensive/intervene APIs).

LLM structured decisions occupy this action slot when WS_LLM_DECISIONS=1 (+ key).
Heuristic agents implement the same schema/interface when LLM is off.
Counsel speech banks remain flavor-only and do not own tick decisions.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from .figures import FIGURES, figure_available_for_talk, get_figure
from .nonlinear import clamp
from .profiles import profile_by_id

STANCE_OK = ("contribute", "withhold", "defect")
STANCE_TO_ENGINE = {
    "contribute": "cooperate",
    "cooperate": "cooperate",
    "withhold": "withhold",
    "defect": "defect",
}
INVEST_OK = ("none", "tech", "agriculture", "construction", "military", "mediation")
INTERVENE_OK = ("none", "chu", "qi", "qin")
INVEST_TARGETS = ("chu", "qi", "zhao", "han", "wei", "yan", "none")
ROLE_WEIGHT = {"ruler": 1.0, "minister": 0.78, "general": 0.72, "retainer": 0.42}
STRATEGY_IDS = (
    "balanced",
    "hezong",
    "peer_preempt",
    "qin_preempt",
    "fluid",
    "develop",
    "trust_builder",
    "war_hawk",
    "isolationist",
    "preemptor",
)

_JSON_LIST_RE = re.compile(r"\[[\s\S]*\]")


def decisions_feature_enabled() -> bool:
    """Figure decision phase always on unless explicitly disabled.

    Default ON: OCEAN acts each tick. Set WS_DECISION_AGENTS=0 to revert to
    pure PAS decide_action without figure aggregation.
    """
    flag = (os.environ.get("WS_DECISION_AGENTS") or "1").strip().lower()
    return flag not in ("0", "false", "no", "off")


def _speech_role(fig: dict[str, Any]) -> str:
    return str(fig.get("speech_role") or "minister").strip().lower()


def _figure_ocean(fig: dict[str, Any], world: Any) -> dict[str, float]:
    if isinstance(fig.get("_proxy_ocean"), dict):
        po = fig["_proxy_ocean"]
        return {
            "O": float(po.get("O", 0.5)),
            "C": float(po.get("C", 0.5)),
            "E": float(po.get("E", 0.5)),
            "A": float(po.get("A", 0.5)),
            "N": float(po.get("N", 0.5)),
        }
    row = profile_by_id(str(fig.get("profile_id") or "")) or {}
    bf = row.get("big_five") or {}
    home = str(fig.get("home") or "")
    ag = world.agents.get(home) if home else None
    return {
        "O": float(bf.get("O", getattr(getattr(ag, "traits", None), "openness", 0.5) or 0.5)),
        "C": float(bf.get("C", getattr(getattr(ag, "traits", None), "conscientiousness", 0.5) or 0.5)),
        "E": float(bf.get("E", getattr(getattr(ag, "traits", None), "extraversion", 0.5) or 0.5)),
        "A": float(bf.get("A", getattr(getattr(ag, "traits", None), "agreeableness", 0.5) or 0.5)),
        "N": float(bf.get("N", getattr(getattr(ag, "traits", None), "neuroticism", 0.5) or 0.5)),
    }


def _court_proxy_figure(home: str, world: Any) -> dict[str, Any]:
    """Synthetic figure row so every living court has an OCEAN action seat."""
    ag = world.agents[home]
    ocean = {
        "O": float(ag.traits.openness),
        "C": float(ag.traits.conscientiousness),
        "E": float(ag.traits.extraversion),
        "A": float(ag.traits.agreeableness),
        "N": float(ag.traits.neuroticism),
    }
    return {
        "id": f"court_{home}",
        "profile_id": "",
        "home": home,
        "court_group": f"{home.title()} court",
        "role_label": f"{ag.name} court (proxy)",
        "speech_role": "ruler",
        "packet_bias": {},
        "_proxy_ocean": ocean,
    }


def _living_cast(world: Any) -> list[dict[str, Any]]:
    """One+ figure per living court across all seven states when possible."""
    out: list[dict[str, Any]] = []
    covered: set[str] = set()
    for fig in FIGURES:
        fid = str(fig.get("id") or "")
        if not fid:
            continue
        if not figure_available_for_talk(world, fid):
            continue
        home = str(fig.get("home") or "")
        ag = world.agents.get(home)
        if ag is None or getattr(ag, "annexed", False) or float(getattr(ag, "viability", 0)) <= 0:
            continue
        out.append(fig)
        covered.add(home)
    # Ensure Qin Chu Qi Zhao Han Wei Yan each have ≥1 decision seat
    for home, ag in world.agents.items():
        if getattr(ag, "annexed", False) or float(getattr(ag, "viability", 0)) <= 0:
            continue
        if home in covered:
            continue
        out.append(_court_proxy_figure(home, world))
        covered.add(home)
    return out


def _memory_bite(world: Any, fid: str) -> str:
    try:
        from .figure_memory import memory_bite, memories_for

        bite = memory_bite(world, fid)
        if bite:
            return str(bite)[:96]
        rows = memories_for(world, fid, limit=2)
        return "; ".join(str(r.get("text") or r.get("kind") or "")[:48] for r in rows)
    except Exception:  # noqa: BLE001
        board = getattr(world, "figure_memories", None) or {}
        rows = list(board.get(fid) or [])[-2:]
        return "; ".join(str(r.get("text") or r.get("kind") or "")[:48] for r in rows)


def board_situation(world: Any) -> dict[str, Any]:
    """Classic game-AI board read — meters the policy must condition on each tick."""
    chu = world.agents.get("chu")
    anti = [
        a
        for a in world.agents.values()
        if a.bloc == "anti_qin" and not getattr(a, "annexed", False) and float(getattr(a, "viability", 0)) > 0
    ]
    grain = sum(float(a.grain) for a in anti) / max(1, len(anti))
    treasury = sum(float(a.treasury) for a in anti) / max(1, len(anti))
    betrayal = sum(float(a.state.betrayal_memory) for a in anti) / max(1, len(anti))
    resentment = sum(float(a.state.resentment) for a in anti) / max(1, len(anti))
    fronts_open = 0
    can_launch = 0
    try:
        from .conflict import offensive_capacity

        for a in anti:
            cap = offensive_capacity(world, a.id)
            fronts_open += int(cap.get("opened") or 0)
            if cap.get("can_launch"):
                can_launch += 1
    except Exception:  # noqa: BLE001
        fronts = getattr(world, "player_offensive_fronts", None) or {}
        fronts_open = sum(len(v) for v in fronts.values() if isinstance(v, list))
    dead = list(getattr(world, "dead_edges", None) or [])
    ep = list(getattr(world, "episode", None) or [])[-12:]
    recent_betray = sum(
        1
        for e in ep
        if "betray" in str(e.get("action") or "").lower()
        or "betray" in str(e.get("event_id") or "").lower()
    )
    press = float(world.qin_pressure)
    coh = float(world.meso.cohesion)
    return {
        "tick": int(world.tick),
        "pressure": press,
        "pressure_u": press / 100.0,
        "cohesion": coh,
        "cohesion_u": coh / 100.0,
        "path": str(world.meso.pathway_soft or "other"),
        "grain_avg": grain,
        "treasury_avg": treasury,
        "betrayal_avg": betrayal,
        "resentment_avg": resentment,
        "fronts_open": fronts_open,
        "can_launch": can_launch,
        "dead_edges": len(dead),
        "recent_betray": recent_betray,
        "chu_latency": float(getattr(getattr(chu, "traits", None), "response_latency", 0.8) or 0.8),
        "chu_sts": float(
            getattr(getattr(chu, "traits", None), "status_threat_sensitivity", 0.8) or 0.8
        ),
        "chu_fear": float(getattr(getattr(chu, "state", None), "fear_of_qin", 0.4) or 0.4),
        "n_anti": len(anti),
        "crisis": press >= 72 and coh <= 42,
        "fragile": press >= 55 and coh <= 55,
        "breathing": press < 45 and coh >= 55,
    }


def build_decision_snapshot(world: Any, *, strategy: str = "balanced") -> str:
    """Compact multi-figure snapshot for one batched LLM/heuristic call."""
    sit = board_situation(world)
    lines = [
        f"t={sit['tick']} P={sit['pressure']:.0f} C={sit['cohesion']:.0f} "
        f"path={sit['path']} strat={strategy} (bias only — react to board)",
        f"board grain={sit['grain_avg']:.0f} treas={sit['treasury_avg']:.0f} "
        f"betray={sit['betrayal_avg']:.2f} fronts={sit['fronts_open']}/"
        f"launch={sit['can_launch']} chu_lat={sit['chu_latency']:.2f} "
        f"chu_sts={sit['chu_sts']:.2f} crisis={int(sit['crisis'])}",
    ]
    for fig in _living_cast(world):
        fid = str(fig["id"])
        home = str(fig["home"])
        ag = world.agents[home]
        ocean = _figure_ocean(fig, world)
        role = _speech_role(fig)
        mem = _memory_bite(world, fid)
        lines.append(
            f"{fid}|{home}|{role}|"
            f"O={ocean['O']:.2f} C={ocean['C']:.2f} E={ocean['E']:.2f} "
            f"A={ocean['A']:.2f} N={ocean['N']:.2f}|"
            f"fear={float(ag.state.fear_of_qin):.2f} res={float(ag.state.resentment):.2f} "
            f"g={float(ag.grain):.0f} intent={ag.intention.current}|mem={mem or '-'}"
        )
    return "\n".join(lines)


def clamp_decision(raw: dict[str, Any] | None, *, fallback_home: str = "chu") -> dict[str, Any]:
    """Validate + clamp one structured decision row."""
    raw = raw if isinstance(raw, dict) else {}
    fid = str(raw.get("figure_id") or raw.get("id") or "").strip()
    meta = get_figure(fid) if fid else None
    home = str(raw.get("home") or (meta or {}).get("home") or fallback_home).strip().lower()
    stance = str(raw.get("stance") or raw.get("stance_lean") or "withhold").strip().lower()
    if stance == "cooperate":
        stance = "contribute"
    if stance not in STANCE_OK:
        stance = "withhold"
    try:
        alliance = float(raw.get("alliance_lean", 0.5))
    except (TypeError, ValueError):
        alliance = 0.5
    alliance = float(clamp(alliance, 0.0, 1.0))
    off = str(raw.get("offensive_pref") or "none").strip().lower()
    if off not in ("none", "qin", "alliance_qin") and not off.startswith("peer:"):
        off = "none"
    if off.startswith("peer:"):
        peer = off.split(":", 1)[-1].strip()
        if peer not in ("chu", "qi", "zhao", "han", "wei", "yan", "qin"):
            off = "none"
    inv = str(raw.get("invest_pref") or "none").strip().lower()
    if inv not in INVEST_OK:
        inv = "none"
    itarget = str(raw.get("invest_target") or "none").strip().lower()
    if itarget not in INVEST_TARGETS:
        itarget = home if home in INVEST_TARGETS else "none"
    interv = str(raw.get("intervene_pref") or "none").strip().lower()
    if interv not in INTERVENE_OK:
        interv = "none"
    tag = str(raw.get("rationale_tag") or "ocean")[:24]
    return {
        "figure_id": fid or f"{home}_anon",
        "home": home,
        "stance": stance,
        "alliance_lean": round(alliance, 3),
        "offensive_pref": off,
        "invest_pref": inv,
        "invest_target": itarget,
        "intervene_pref": interv,
        "rationale_tag": tag,
    }


def parse_decisions_payload(text: str) -> list[dict[str, Any]]:
    """Parse LLM/mock JSON into clamped decision rows."""
    text = (text or "").strip()
    if not text:
        return []
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data: Any
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_LIST_RE.search(text)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        data = data.get("decisions") or data.get("figures") or data.get("actions") or []
    if not isinstance(data, list):
        return []
    return [clamp_decision(x if isinstance(x, dict) else None) for x in data]


def _strategy_priors(strat: str) -> dict[str, float]:
    """Soft strategy flavor — never a hard always-do-X script."""
    s = (strat or "balanced").strip().lower()
    table = {
        "hezong": {
            "ally": 0.22,
            "contribute": 0.14,
            "mediate": 0.16,
            "intervene": 0.14,
            "qin_war": -0.12,
            "peer_war": -0.18,
            "develop": 0.04,
        },
        "trust_builder": {
            "ally": 0.18,
            "contribute": 0.12,
            "mediate": 0.20,
            "intervene": 0.12,
            "qin_war": -0.14,
            "peer_war": -0.16,
            "develop": 0.06,
        },
        "qin_preempt": {
            "ally": 0.08,
            "contribute": 0.06,
            "mediate": 0.02,
            "intervene": 0.04,
            "qin_war": 0.22,
            "peer_war": -0.10,
            "develop": 0.02,
        },
        "war_hawk": {
            "ally": 0.04,
            "contribute": 0.04,
            "mediate": -0.04,
            "intervene": 0.0,
            "qin_war": 0.18,
            "peer_war": 0.08,
            "develop": 0.0,
        },
        "peer_preempt": {
            "ally": -0.06,
            "contribute": 0.0,
            "mediate": -0.04,
            "intervene": -0.02,
            "qin_war": 0.04,
            "peer_war": 0.24,
            "develop": 0.0,
        },
        "preemptor": {
            "ally": -0.04,
            "contribute": 0.02,
            "mediate": -0.02,
            "intervene": 0.0,
            "qin_war": 0.10,
            "peer_war": 0.18,
            "develop": 0.0,
        },
        "develop": {
            "ally": 0.06,
            "contribute": 0.08,
            "mediate": 0.06,
            "intervene": 0.06,
            "qin_war": -0.08,
            "peer_war": -0.12,
            "develop": 0.24,
        },
        "isolationist": {
            "ally": -0.28,
            "contribute": -0.10,
            "mediate": 0.0,
            "intervene": -0.06,
            "qin_war": -0.16,
            "peer_war": -0.10,
            "develop": 0.10,
        },
        "fluid": {
            "ally": 0.06,
            "contribute": 0.04,
            "mediate": 0.04,
            "intervene": 0.06,
            "qin_war": 0.04,
            "peer_war": 0.0,
            "develop": 0.08,
        },
        "balanced": {
            "ally": 0.06,
            "contribute": 0.06,
            "mediate": 0.06,
            "intervene": 0.06,
            "qin_war": 0.0,
            "peer_war": -0.04,
            "develop": 0.08,
        },
    }
    return dict(table.get(s, table["balanced"]))


def _circ_noise(world: Any, fid: str, salt: str = "") -> float:
    """Tiny board-reactive jitter (not strategy exaggeration)."""
    h = hashlib.sha256(f"{world.tick}|{fid}|{salt}|{float(world.qin_pressure):.0f}".encode()).hexdigest()
    return (int(h[:6], 16) / float(0xFFFFFF)) * 0.08 - 0.04


def heuristic_figure_decision(
    world: Any,
    fig: dict[str, Any],
    *,
    strategy: str = "balanced",
) -> dict[str, Any]:
    """OCEAN + board circumstance utility; strategy is a soft prior only."""
    fid = str(fig["id"])
    home = str(fig["home"])
    ag = world.agents[home]
    ocean = _figure_ocean(fig, world)
    O, C, E, A, N = ocean["O"], ocean["C"], ocean["E"], ocean["A"], ocean["N"]
    role = _speech_role(fig)
    sit = board_situation(world)
    prior = _strategy_priors(strategy)
    press = float(sit["pressure_u"])
    fear = float(ag.state.fear_of_qin)
    res = float(ag.state.resentment)
    betray = float(ag.state.betrayal_memory)
    grain = float(ag.grain)
    broke = grain < 28 or float(ag.treasury) < 22
    noise = _circ_noise(world, fid, strategy)

    # --- Stance utilities (persona + circumstance) ---
    contribute = (
        0.32 * A
        + 0.18 * C
        + 0.12 * E
        + 0.14 * (1.0 - fear)
        + 0.10 * (1.0 - res)
        + 0.12 * sit["cohesion_u"]
        + prior["contribute"]
        + noise
    )
    withhold = (
        0.34 * N
        + 0.16 * (1.0 - A)
        + 0.18 * fear
        + 0.12 * press
        + 0.10 * betray
        + (0.12 if broke else 0.0)
        + 0.04 * (1.0 - E)
        - 0.5 * noise
    )
    defect = (
        0.30 * (1.0 - A)
        + 0.22 * res
        + 0.16 * press
        + 0.12 * betray
        + 0.08 * (1.0 - C)
        + 0.08 * N
        + noise * 0.5
    )

    if ag.bloc == "qin":
        defect += 0.35 + 0.12 * C
        contribute *= 0.22
        withhold += 0.08
    if role == "ruler":
        contribute += 0.04 * A
    elif role == "retainer":
        withhold += 0.06

    # Circumstance overrides strategy flavor
    if sit["crisis"] and ag.bloc != "qin":
        contribute += 0.16  # band together under Qin crush
        defect -= 0.10
    if sit["recent_betray"] or sit["dead_edges"] >= 2:
        withhold += 0.10
        contribute -= 0.06
    if betray > 0.65:
        defect += 0.08
        contribute -= 0.08

    scores = {"contribute": contribute, "withhold": withhold, "defect": defect}
    stance = max(scores, key=scores.get)

    # --- Alliance lean ---
    alliance = (
        0.22
        + 0.40 * A
        + 0.20 * E
        - 0.28 * N
        - 0.16 * fear
        - 0.18 * betray
        + 0.18 * (1.0 - press)
        + 0.12 * sit["cohesion_u"]
        + prior["ally"]
    )
    if sit["crisis"]:
        alliance += 0.14  # even war hawks may hezong when meters scream
    if sit["breathing"] and prior["ally"] < 0:
        alliance -= 0.06  # isolationist/preempt keep distance when safe
    if broke:
        alliance -= 0.10
    if ag.bloc == "qin":
        alliance = 0.05
    alliance = float(clamp(alliance, 0.0, 1.0))

    # --- Offensive utilities (gated by capacity / grain / fronts) ---
    off = "none"
    can_war = sit["can_launch"] > 0 and not broke and sit["fronts_open"] < max(2, sit["n_anti"])
    qin_u = (
        0.20 * press
        + 0.15 * (1.0 - A)
        + 0.12 * res
        + 0.10 * sit["cohesion_u"]  # need some hold to march
        + prior["qin_war"]
        + (0.08 if alliance >= 0.5 else -0.05)
    )
    peer_u = (
        0.18 * (1.0 - A)
        + 0.14 * res
        + 0.10 * betray
        + prior["peer_war"]
        - 0.12 * press  # don't fratricide under Qin heat
        - 0.10 * sit["cohesion_u"]
    )
    if ag.bloc == "qin":
        off = "peer:chu" if (0.25 + 0.4 * press + 0.2 * C) > 0.45 else "none"
    elif can_war:
        if qin_u >= 0.42 and qin_u >= peer_u:
            off = "alliance_qin" if alliance >= 0.52 and sit["cohesion_u"] >= 0.40 else "qin"
        elif peer_u >= 0.48 and peer_u > qin_u + 0.04:
            for cand in ("zhao", "han", "wei", "yan", "qi", "chu"):
                if cand == home:
                    continue
                other = world.agents.get(cand)
                if other and not getattr(other, "annexed", False) and other.bloc == "anti_qin":
                    # Prefer weaker / higher-resentment peer
                    if float(other.state.resentment) >= 0.35 or float(other.viability) < 70:
                        off = f"peer:{cand}"
                        break
                    if off == "none":
                        off = f"peer:{cand}"
        # Hezong bias: suppress peer war unless circumstance is calm+spiteful
        if prior["peer_war"] < -0.1 and off.startswith("peer:") and not (
            sit["breathing"] and betray > 0.55
        ):
            off = "none"
        # Under crisis, cancel peer war; prefer alliance or qin strike only if prior wants it
        if sit["crisis"] and off.startswith("peer:"):
            off = "alliance_qin" if alliance >= 0.45 and prior["qin_war"] >= 0 else "none"

    # --- Invest utilities ---
    inv_scores = {
        "mediation": 0.15 * A + 0.12 * (1.0 - sit["cohesion_u"]) + 0.10 * betray + prior["mediate"],
        "tech": 0.20 * O + 0.10 * C + prior["develop"] + (0.08 if sit["breathing"] else 0.0),
        "construction": 0.14 * C + 0.10 * O + 0.5 * prior["develop"],
        "agriculture": 0.18 * C + (0.22 if broke or grain < 40 else 0.04),
        "military": 0.14 * (1.0 - A) + 0.16 * press + max(0.0, prior["qin_war"], prior["peer_war"]),
        "none": 0.05,
    }
    if sit["fragile"] or sit["crisis"]:
        inv_scores["mediation"] += 0.12
        inv_scores["military"] += 0.06 if prior["qin_war"] > 0 else -0.04
    if sit["chu_latency"] > 0.7 or sit["chu_sts"] > 0.55:
        inv_scores["mediation"] += 0.10  # cool Chu toward fiction band helpers
    if ag.bloc == "qin":
        inv_scores = {"military": 0.6 + 0.2 * C, "none": 0.2, "tech": 0.15 * O}
    inv = max(inv_scores, key=inv_scores.get)
    itarget = home if home != "qin" else "chu"
    if inv == "mediation":
        itarget = "chu" if sit["chu_fear"] > 0.35 or sit["chu_latency"] > 0.55 else "qi"
    if inv == "none":
        itarget = "none"

    # --- Intervene ---
    interv = "none"
    interv_chu = (
        0.15
        + 0.20 * sit["chu_latency"]
        + 0.15 * sit["chu_sts"]
        + 0.12 * sit["chu_fear"]
        + prior["intervene"]
        + (0.12 if sit["fragile"] or sit["crisis"] else 0.0)
    )
    interv_qin = 0.10 + 0.25 * press + (0.08 if prior["qin_war"] > 0 else -0.05)
    interv_qi = 0.08 + 0.10 * betray + 0.08 * (1.0 - A)
    if ag.bloc != "qin" and max(interv_chu, interv_qin, interv_qi) >= 0.42:
        if interv_chu >= interv_qin and interv_chu >= interv_qi:
            interv = "chu"
        elif interv_qin >= interv_qi:
            interv = "qin"
        else:
            interv = "qi"
    # Develop / hezong under breathing room: still cool Chu latency for fiction path
    if (
        ag.bloc != "qin"
        and interv == "none"
        and prior["intervene"] > 0.08
        and (sit["chu_latency"] > 0.65 or sit["chu_sts"] > 0.5)
    ):
        interv = "chu"

    tag = f"circ:{strategy}"[:24]
    if sit["crisis"]:
        tag = f"crisis:{strategy}"[:24]
    elif sit["fragile"]:
        tag = f"fragile:{strategy}"[:24]

    return clamp_decision(
        {
            "figure_id": fid,
            "home": home,
            "stance": stance,
            "alliance_lean": alliance,
            "offensive_pref": off,
            "invest_pref": inv,
            "invest_target": itarget,
            "intervene_pref": interv,
            "rationale_tag": tag,
        }
    )


def heuristic_decisions(world: Any, *, strategy: str = "balanced") -> list[dict[str, Any]]:
    return [heuristic_figure_decision(world, fig, strategy=strategy) for fig in _living_cast(world)]


def mock_llm_decisions(world: Any, *, strategy: str = "balanced") -> list[dict[str, Any]]:
    """Fixture path: same circumstance-reactive policy as heuristic (no rigid script).

    Marks rationale_tag with mock: so playtests can tell fixture vs live LLM.
    Strategy remains a soft prior inside heuristic_figure_decision.
    """
    rows = heuristic_decisions(world, strategy=strategy)
    for r in rows:
        base = str(r.get("rationale_tag") or strategy)
        r["rationale_tag"] = f"mock:{base}"[:24]
    return rows


def aggregate_court_stances(decisions: list[dict[str, Any]], world: Any) -> dict[str, str]:
    """Weight figure stances by role → per-court engine action."""
    tallies: dict[str, dict[str, float]] = {}
    for row in decisions:
        home = str(row.get("home") or "")
        if home not in world.agents:
            continue
        fig = get_figure(str(row.get("figure_id") or "")) or {"speech_role": "minister", "home": home}
        w = float(ROLE_WEIGHT.get(_speech_role(fig), 0.55))
        stance = str(row.get("stance") or "withhold")
        eng = STANCE_TO_ENGINE.get(stance, "withhold")
        bucket = tallies.setdefault(home, {"cooperate": 0.0, "withhold": 0.0, "defect": 0.0})
        bucket[eng] = bucket.get(eng, 0.0) + w
    out: dict[str, str] = {}
    for home, bucket in tallies.items():
        out[home] = max(bucket, key=bucket.get)
    return out


def apply_stance_decisions(world: Any, decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Write aggregated OCEAN stances onto court intentions (sticky 1–2 ticks)."""
    courts = aggregate_court_stances(decisions, world)
    applied = 0
    for home, eng in courts.items():
        ag = world.agents.get(home)
        if ag is None or getattr(ag, "annexed", False):
            continue
        if ag.bloc == "qin" and eng != "defect":
            # Qin persona may withhold briefly; never "cooperate" into anti-Qin quorum
            eng = "withhold" if eng == "cooperate" else eng
        if ag.intention.current != eng:
            applied += 1
        ag.intention.current = eng  # type: ignore[assignment]
        ag.intention.sticky_until = max(int(ag.intention.sticky_until or 0), world.tick + 1)
    summary = {"courts": courts, "stance_writes": applied, "n_figures": len(decisions)}
    world.last_figure_decisions = list(decisions)
    world.last_decision_summary = summary
    return summary


def _pick_field_plan(
    decisions: list[dict[str, Any]],
    world: Any,
    *,
    strategy: str,
) -> dict[str, Any]:
    """Collapse figure leans into Field APIs — circumstance gates, strategy soft."""
    anti = [r for r in decisions if str(r.get("home")) != "qin"]
    if not anti:
        return {"alliance": False}

    sit = board_situation(world)
    alliance_score = sum(float(r.get("alliance_lean") or 0) for r in anti) / max(1, len(anti))
    inv_votes: dict[str, float] = {}
    inv_target: dict[str, float] = {}
    off_votes: dict[str, float] = {}
    interv_votes: dict[str, float] = {}
    for r in anti:
        fig = get_figure(str(r.get("figure_id") or "")) or {}
        w = float(ROLE_WEIGHT.get(_speech_role(fig), 0.55))
        inv = str(r.get("invest_pref") or "none")
        if inv != "none":
            inv_votes[inv] = inv_votes.get(inv, 0.0) + w
            tgt = str(r.get("invest_target") or "chu")
            if tgt != "none":
                inv_target[tgt] = inv_target.get(tgt, 0.0) + w
        off = str(r.get("offensive_pref") or "none")
        if off != "none":
            off_votes[off] = off_votes.get(off, 0.0) + w
        interv = str(r.get("intervene_pref") or "none")
        if interv != "none":
            interv_votes[interv] = interv_votes.get(interv, 0.0) + w

    strat = (strategy or "balanced").strip().lower()
    prior = _strategy_priors(strat)
    plan: dict[str, Any] = {
        "alliance": False,
        "fund": None,
        "invest": None,
        "invest_target": None,
        "offensive": None,
        "intervene": None,
    }

    # Base threshold from strategy prior; crisis lowers the bar for everyone
    thr = 0.55 - 0.35 * prior["ally"]
    if sit["crisis"]:
        thr -= 0.12
    elif sit["fragile"]:
        thr -= 0.06
    elif sit["breathing"] and prior["ally"] < 0:
        thr += 0.10
    if sit["betrayal_avg"] > 0.6:
        thr += 0.06
    thr = float(clamp(thr, 0.32, 0.88))
    plan["alliance"] = alliance_score >= thr

    if inv_votes:
        purpose = max(inv_votes, key=inv_votes.get)
        tgt = max(inv_target, key=inv_target.get) if inv_target else "chu"
        # Broke board → force agriculture if anyone voted it or grain is low
        if sit["grain_avg"] < 36 and "agriculture" in inv_votes:
            purpose = "agriculture"
        plan["invest"] = purpose
        plan["invest_target"] = tgt
        # Alliance-shaped spend when quorum looks real (hezong-weighted, not exclusive)
        if plan["alliance"] and (
            prior["ally"] > 0.05
            or purpose in ("mediation", "military", "tech")
            or sit["crisis"]
        ):
            plan["fund"] = purpose if purpose != "none" else "mediation"

    if off_votes and sit["can_launch"] > 0 and sit["grain_avg"] >= 30:
        plan["offensive"] = max(off_votes, key=off_votes.get)
        # Circumstance: no peer war under crisis; hezong bias already in votes
        if sit["crisis"] and str(plan["offensive"]).startswith("peer:"):
            plan["offensive"] = "alliance_qin" if alliance_score >= 0.45 else None
        if sit["fronts_open"] >= 3:
            plan["offensive"] = None
        if prior["peer_war"] < -0.1 and str(plan["offensive"] or "").startswith("peer:"):
            if not (sit["breathing"] and sit["betrayal_avg"] > 0.55):
                plan["offensive"] = None
    elif off_votes and sit["can_launch"] <= 0:
        plan["offensive"] = None

    if interv_votes:
        plan["intervene"] = max(interv_votes, key=interv_votes.get)
    elif sit["chu_latency"] > 0.7 and prior["intervene"] > 0.05:
        plan["intervene"] = "chu"
    elif sit["crisis"] and press_cool_qin(sit, prior):
        plan["intervene"] = "qin"

    plan["alliance_score"] = round(alliance_score, 3)
    plan["situation"] = {
        "crisis": sit["crisis"],
        "fragile": sit["fragile"],
        "thr": round(thr, 3),
        "can_launch": sit["can_launch"],
    }
    return plan


def press_cool_qin(sit: dict[str, Any], prior: dict[str, float]) -> bool:
    return bool(sit.get("pressure", 0) >= 65 or prior.get("qin_war", 0) > 0.1)


def apply_field_actions(
    world: Any,
    decisions: list[dict[str, Any]],
    *,
    strategy: str = "balanced",
) -> dict[str, Any]:
    """Map structured leans onto existing Field APIs (at most one each / quarter)."""
    from .tick import (
        alliance_offensive,
        attempt_alliance,
        intervene_many,
        player_action,
        player_offensive,
        spend_alliance_fund,
    )

    plan = _pick_field_plan(decisions, world, strategy=strategy)
    fired: list[str] = []

    if plan.get("intervene") and plan["intervene"] != "none":
        intervene_many(world, [str(plan["intervene"])])
        if not getattr(world, "last_intervene_error", None):
            fired.append(f"intervene:{plan['intervene']}")

    if plan.get("alliance"):
        attempt_alliance(world)
        if not getattr(world, "last_alliance_attempt_error", None):
            fired.append("alliance")

    if plan.get("fund"):
        spend_alliance_fund(world, str(plan["fund"]))
        if not getattr(world, "last_alliance_fund_error", None):
            fired.append(f"fund:{plan['fund']}")

    if plan.get("invest") and int(getattr(world, "player_invest_actions_left", 0) or 0) > 0:
        tgt = str(plan.get("invest_target") or "chu")
        player_action(world, str(plan["invest"]), tgt)
        if not getattr(world, "last_player_action_error", None):
            fired.append(f"invest:{plan['invest']}:{tgt}")

    off = plan.get("offensive")
    if off and off != "none":
        if off == "alliance_qin" or off == "qin":
            if off == "alliance_qin":
                alliance_offensive(world, "qin")
            else:
                # Lead with strongest living anti-Qin neighbor of Qin
                lead = "chu"
                for cand in ("chu", "zhao", "han", "wei", "yan", "qi"):
                    ag = world.agents.get(cand)
                    if ag and not getattr(ag, "annexed", False):
                        lead = cand
                        break
                player_offensive(world, lead, "qin")
            if not getattr(world, "last_player_offensive_error", None):
                fired.append(f"offensive:{off}")
        elif str(off).startswith("peer:"):
            peer = str(off).split(":", 1)[-1]
            lead = "chu"
            for cand in ("chu", "qi", "zhao", "wei", "han", "yan"):
                if cand == peer:
                    continue
                ag = world.agents.get(cand)
                if ag and not getattr(ag, "annexed", False):
                    lead = cand
                    break
            if lead != peer:
                player_offensive(world, lead, peer)
                if not getattr(world, "last_player_offensive_error", None):
                    fired.append(f"offensive:{off}")

    result = {"plan": plan, "fired": fired}
    world.last_field_ai = result
    if fired:
        world.append_log(
            f"Decision-agents Field AI ({strategy}): " + ", ".join(fired),
            event_id="decision_agents",
            action="field_ai",
            dials_fired=["trust", "cohesion", "qin_pressure", "resources"],
            anchor="OCEAN figure decisions → Field APIs",
        )
    return result


def obtain_decisions(
    world: Any,
    *,
    strategy: str = "balanced",
    mode: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Return (decisions, source) where source is llm|mock|heuristic.

    mode: auto|llm|mock|heuristic — default auto uses LLM when enabled, else heuristic.
    """
    from .llm_gate import llm_decisions_enabled

    mode = (mode or os.environ.get("WS_DECISION_MODE") or "auto").strip().lower()
    if mode == "heuristic":
        return heuristic_decisions(world, strategy=strategy), "heuristic"
    if mode == "mock":
        return mock_llm_decisions(world, strategy=strategy), "mock"
    if mode == "llm" or (mode == "auto" and llm_decisions_enabled()):
        try:
            from .decision_llm import complete_decisions_json

            snap = build_decision_snapshot(world, strategy=strategy)
            raw = complete_decisions_json(snap)
            rows = parse_decisions_payload(raw)
            # Ensure every living figure has a row; fill gaps from heuristic
            have = {str(r.get("figure_id")) for r in rows}
            for fig in _living_cast(world):
                if str(fig["id"]) not in have:
                    rows.append(heuristic_figure_decision(world, fig, strategy=strategy))
            # Re-clamp + keep only known figures
            known = {str(f["id"]) for f in _living_cast(world)}
            rows = [clamp_decision(r) for r in rows if str(r.get("figure_id")) in known]
            if rows:
                return rows, "llm"
        except Exception:  # noqa: BLE001
            pass
        # Fall through to heuristic (or mock if WS_DECISION_FALLBACK=mock)
        fb = (os.environ.get("WS_DECISION_FALLBACK") or "heuristic").strip().lower()
        if fb == "mock":
            return mock_llm_decisions(world, strategy=strategy), "mock"
        return heuristic_decisions(world, strategy=strategy), "heuristic"
    return heuristic_decisions(world, strategy=strategy), "heuristic"


def run_decision_phase(
    world: Any,
    *,
    strategy: str | None = None,
    mode: str | None = None,
    field_ai: bool | None = None,
) -> dict[str, Any]:
    """Per-tick action slot: OCEAN decisions → court stance (+ optional Field APIs).

    Call after budgets refresh and before PAS action resolution so sticky
    intentions from figures shape trust/cohesion/pressure that quarter.
    """
    if not decisions_feature_enabled():
        return {"skipped": True, "reason": "WS_DECISION_AGENTS=0"}

    strat = (
        strategy
        or getattr(world, "decision_strategy", None)
        or os.environ.get("WS_DECISION_STRATEGY")
        or "balanced"
    )
    strat = str(strat).strip().lower() or "balanced"

    rows, source = obtain_decisions(world, strategy=strat, mode=mode)
    stance = apply_stance_decisions(world, rows)

    do_field = field_ai
    if do_field is None:
        do_field = (os.environ.get("WS_FIELD_AI") or "0").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ) or bool(getattr(world, "field_ai", False))

    field: dict[str, Any] = {}
    if do_field:
        field = apply_field_actions(world, rows, strategy=strat)

    world.append_log(
        (
            f"Figure decision phase ({source}/{strat}): "
            f"{stance.get('n_figures', 0)} figures → courts {stance.get('courts', {})}"
        ),
        event_id="decision_agents",
        action="stance",
        dials_fired=["intention", "ocean"],
        anchor="persona OCEAN → court act → state deltas via tick",
    )
    out = {"source": source, "strategy": strat, "stance": stance, "field": field, "decisions": rows}
    world.last_decision_phase = {
        "source": source,
        "strategy": strat,
        "stance": stance,
        "field_fired": list((field or {}).get("fired") or []),
    }
    return out
