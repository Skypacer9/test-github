"""OCEAN → per-tick figure actions → world/state deltas.

Invariant (Odetta / WS-64): persona Big Five drives how characters *act* each
round; those acts change their countries that round via existing tick/API paths
(stance → trust/cohesion/pressure; invest/alliance/offensive/intervene APIs).

LLM structured decisions occupy this action slot when WS_LLM_DECISIONS=1 (+ key).
Heuristic agents implement the same schema/interface when LLM is off.
Counsel speech banks remain flavor-only and do not own tick decisions.
"""

from __future__ import annotations

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


def _living_cast(world: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fig in FIGURES:
        fid = str(fig.get("id") or "")
        if not fid:
            continue
        if not figure_available_for_talk(world, fid):
            # Still allow annexed-skip; era-locked figures stay out of decisions
            continue
        home = str(fig.get("home") or "")
        ag = world.agents.get(home)
        if ag is None or getattr(ag, "annexed", False) or float(getattr(ag, "viability", 0)) <= 0:
            continue
        out.append(fig)
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


def build_decision_snapshot(world: Any, *, strategy: str = "balanced") -> str:
    """Compact multi-figure snapshot for one batched LLM/heuristic call."""
    lines = [
        f"t={world.tick} P={float(world.qin_pressure):.0f} "
        f"C={float(world.meso.cohesion):.0f} path={world.meso.pathway_soft} "
        f"strat={strategy}",
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
            f"intent={ag.intention.current}|mem={mem or '-'}"
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


def heuristic_figure_decision(
    world: Any,
    fig: dict[str, Any],
    *,
    strategy: str = "balanced",
) -> dict[str, Any]:
    """OCEAN-driven structured action for one figure (same schema as LLM)."""
    fid = str(fig["id"])
    home = str(fig["home"])
    ag = world.agents[home]
    ocean = _figure_ocean(fig, world)
    O, C, E, A, N = ocean["O"], ocean["C"], ocean["E"], ocean["A"], ocean["N"]
    role = _speech_role(fig)
    press = float(world.qin_pressure) / 100.0
    fear = float(ag.state.fear_of_qin)
    res = float(ag.state.resentment)
    strat = (strategy or "balanced").strip().lower()

    # Stance scores from persona OCEAN + live affect (not speech banks).
    contribute = 0.35 * A + 0.20 * C + 0.15 * E + 0.15 * (1.0 - fear) + 0.10 * (1.0 - res)
    withhold = 0.40 * N + 0.20 * (1.0 - A) + 0.20 * fear + 0.15 * press + 0.05 * (1.0 - E)
    defect = 0.35 * (1.0 - A) + 0.25 * res + 0.20 * press + 0.10 * (1.0 - C) + 0.10 * N

    if ag.bloc == "qin":
        defect += 0.35 + 0.15 * C
        contribute *= 0.25
        withhold += 0.10
    if role == "ruler":
        contribute += 0.05 * A
        defect += 0.04 * (1.0 - A)
    elif role == "retainer":
        withhold += 0.08
        contribute -= 0.04

    # Strategy tendency nudges (Field playtest adoption)
    if strat in ("hezong", "trust_builder"):
        contribute += 0.18
        defect -= 0.10
    elif strat in ("qin_preempt", "war_hawk", "preemptor"):
        if ag.bloc != "qin":
            # Anti-Qin war lean: still cooperate enough to fund marches, then strike
            contribute += 0.06
            defect += 0.04
        else:
            defect += 0.12
    elif strat == "peer_preempt":
        withhold += 0.06
        defect += 0.08
    elif strat == "develop":
        contribute += 0.08
        withhold += 0.04
        defect -= 0.08
    elif strat == "isolationist":
        withhold += 0.22
        contribute -= 0.12
        defect -= 0.06

    scores = {"contribute": contribute, "withhold": withhold, "defect": defect}
    stance = max(scores, key=scores.get)

    alliance = float(clamp(0.25 + 0.45 * A + 0.25 * E - 0.30 * N - 0.15 * fear, 0, 1))
    if strat in ("hezong", "trust_builder", "fluid"):
        alliance = float(clamp(alliance + 0.18, 0, 1))
    if strat == "isolationist":
        alliance = float(clamp(alliance - 0.35, 0, 1))
    if ag.bloc == "qin":
        alliance = 0.05

    # Offensive preference
    off = "none"
    war_heat = (1.0 - A) * 0.4 + res * 0.3 + press * 0.3 + (0.15 if E > 0.55 else 0.0)
    if ag.bloc == "qin":
        off = "peer:chu" if war_heat > 0.35 else "none"
    elif strat in ("qin_preempt", "war_hawk") or (strat == "fluid" and press > 0.55 and alliance > 0.45):
        off = "alliance_qin" if alliance >= 0.5 else "qin"
    elif strat in ("peer_preempt", "preemptor") or war_heat > 0.62:
        # Prefer a living peer neighbor-ish target
        for cand in ("zhao", "han", "wei", "yan", "qi", "chu"):
            if cand == home:
                continue
            other = world.agents.get(cand)
            if other and not getattr(other, "annexed", False) and other.bloc == "anti_qin":
                off = f"peer:{cand}"
                break
    if strat == "hezong":
        off = "none" if alliance > 0.4 else off

    # Invest preference from Openness / Conscientiousness
    inv = "none"
    itarget = home if home != "qin" else "chu"
    if strat == "develop" or O >= 0.55:
        inv = "tech" if O >= 0.5 else "construction"
    elif strat in ("hezong", "trust_builder") or (A >= 0.55 and N < 0.6):
        inv = "mediation"
    elif strat in ("qin_preempt", "war_hawk", "peer_preempt") or (1.0 - A) > 0.55:
        inv = "military"
    elif C >= 0.55:
        inv = "agriculture"
    if ag.bloc == "qin":
        inv = "military" if C > 0.4 else "none"
        itarget = "none"

    interv = "none"
    if strat in ("hezong", "trust_builder", "fluid") and home in ("chu", "qi") and A > 0.45:
        interv = "chu" if fear > 0.4 or float(ag.traits.response_latency) > 0.5 else "qi"
    if strat == "qin_preempt" and press > 0.5:
        interv = "qin"

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
            "rationale_tag": f"ocean:{strat}"[:24],
        }
    )


def heuristic_decisions(world: Any, *, strategy: str = "balanced") -> list[dict[str, Any]]:
    return [heuristic_figure_decision(world, fig, strategy=strategy) for fig in _living_cast(world)]


def mock_llm_decisions(world: Any, *, strategy: str = "balanced") -> list[dict[str, Any]]:
    """Deterministic fixture policy: heuristic OCEAN + light strategy noise.

    Used when playtests need an LLM-shaped path without WS_COUNSEL_API_KEY.
    """
    rows = heuristic_decisions(world, strategy=strategy)
    # Mark provenance so docs/playtest can distinguish fixture vs live
    for r in rows:
        r["rationale_tag"] = f"mock:{strategy}"[:24]
        # Slightly exaggerate strategy signature so adoption is visible
        if strategy == "hezong":
            r["alliance_lean"] = round(min(1.0, float(r["alliance_lean"]) + 0.08), 3)
            if r["home"] != "qin":
                r["stance"] = "contribute"
        elif strategy == "develop":
            r["invest_pref"] = r["invest_pref"] if r["invest_pref"] != "none" else "construction"
        elif strategy == "qin_preempt" and r["home"] != "qin":
            r["offensive_pref"] = "qin" if float(r["alliance_lean"]) < 0.55 else "alliance_qin"
        elif strategy == "peer_preempt" and r["home"] != "qin" and r["offensive_pref"] == "none":
            for cand in ("han", "zhao", "wei"):
                if cand != r["home"] and cand in world.agents:
                    r["offensive_pref"] = f"peer:{cand}"
                    break
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
    """Collapse figure leans into at most one of each Field API this quarter."""
    anti = [r for r in decisions if str(r.get("home")) != "qin"]
    if not anti:
        return {"alliance": False}

    alliance_score = sum(float(r.get("alliance_lean") or 0) for r in anti) / max(1, len(anti))
    # Vote invest / offensive / intervene
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
    plan: dict[str, Any] = {
        "alliance": False,
        "fund": None,
        "invest": None,
        "invest_target": None,
        "offensive": None,
        "intervene": None,
    }

    # Alliance attempt thresholds by strategy
    thr = {
        "hezong": 0.42,
        "trust_builder": 0.45,
        "fluid": 0.48,
        "develop": 0.55,
        "balanced": 0.52,
        "qin_preempt": 0.50,
        "war_hawk": 0.58,
        "peer_preempt": 0.62,
        "preemptor": 0.65,
        "isolationist": 0.85,
    }.get(strat, 0.52)
    plan["alliance"] = alliance_score >= thr

    if inv_votes:
        purpose = max(inv_votes, key=inv_votes.get)
        tgt = max(inv_target, key=inv_target.get) if inv_target else "chu"
        plan["invest"] = purpose
        plan["invest_target"] = tgt
        # Prefer alliance fund when hezong / fluid and alliance looks viable
        if plan["alliance"] and strat in ("hezong", "fluid", "trust_builder", "develop"):
            plan["fund"] = purpose

    if off_votes and strat not in ("isolationist",):
        plan["offensive"] = max(off_votes, key=off_votes.get)
        if strat == "hezong" and alliance_score > 0.55:
            # Hezong holds fire unless alliance_qin
            if not str(plan["offensive"]).endswith("qin"):
                plan["offensive"] = None

    if interv_votes and strat in ("hezong", "trust_builder", "fluid", "qin_preempt", "balanced"):
        plan["intervene"] = max(interv_votes, key=interv_votes.get)

    plan["alliance_score"] = round(alliance_score, 3)
    return plan


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
