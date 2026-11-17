"""Field opponent / strategy harness for Monte Carlo + LLM decision playtests.

Strategies (adopted as decision_strategy + field_ai on the world):
  hezong, peer_preempt, qin_preempt, develop, fluid, balanced, …

Fluid mode re-ranks strategies each quarter from situation × tendency priors,
then blends toward the pick before the decision phase runs.
"""

from __future__ import annotations

from typing import Any

from .decision_agents import STRATEGY_IDS
from .tick import tick
from .world import WorldState, new_world

TENDENCY_TO_STRAT = {
    "balanced": "balanced",
    "hezong": "hezong",
    "trust_builder": "hezong",
    "war_hawk": "qin_preempt",
    "isolationist": "isolationist",
    "preemptor": "peer_preempt",
    "qin_preempt": "qin_preempt",
    "peer_preempt": "peer_preempt",
    "develop": "develop",
    "fluid": "fluid",
}

FLUID_CANDIDATES = (
    "hezong",
    "qin_preempt",
    "peer_preempt",
    "develop",
    "isolationist",
    "balanced",
)


def rank_strategies(world: WorldState, *, tendency: str = "balanced") -> list[tuple[str, float]]:
    """Situation × tendency scores for fluid adoption."""
    p = float(world.qin_pressure) / 100.0
    c = float(world.meso.cohesion) / 100.0
    chu = world.agents.get("chu")
    latency = float(getattr(getattr(chu, "traits", None), "response_latency", 0.5) or 0.5)
    scores: dict[str, float] = {
        "hezong": 0.35 + 0.35 * (1.0 - p) + 0.25 * c,
        "qin_preempt": 0.20 + 0.45 * p + 0.15 * (1.0 - c),
        "peer_preempt": 0.15 + 0.25 * p + 0.20 * (1.0 - c),
        "develop": 0.30 + 0.20 * c + 0.15 * (1.0 - p),
        "isolationist": 0.10 + 0.35 * (1.0 - c) + 0.15 * latency,
        "balanced": 0.28,
    }
    tend = (tendency or "balanced").strip().lower()
    boost = {
        "hezong": {"hezong": 0.35, "develop": 0.08},
        "trust_builder": {"hezong": 0.28, "develop": 0.12},
        "qin_preempt": {"qin_preempt": 0.40, "hezong": 0.05},
        "war_hawk": {"qin_preempt": 0.32, "peer_preempt": 0.12},
        "peer_preempt": {"peer_preempt": 0.38, "qin_preempt": 0.08},
        "preemptor": {"peer_preempt": 0.30, "qin_preempt": 0.15},
        "develop": {"develop": 0.40, "hezong": 0.08},
        "isolationist": {"isolationist": 0.45, "develop": 0.10},
        "balanced": {"balanced": 0.15, "hezong": 0.08, "develop": 0.08},
        "fluid": {"hezong": 0.05, "develop": 0.05, "qin_preempt": 0.05},
    }.get(tend, {})
    for k, v in boost.items():
        scores[k] = scores.get(k, 0.2) + v
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked


def pick_fluid_strategy(world: WorldState, *, tendency: str = "balanced") -> str:
    ranked = rank_strategies(world, tendency=tendency)
    return ranked[0][0] if ranked else "balanced"


def arm_opponent(
    world: WorldState,
    *,
    strategy: str = "balanced",
    field_ai: bool = True,
) -> WorldState:
    """Mark world so tick()'s decision phase uses Field APIs + strategy."""
    strat = TENDENCY_TO_STRAT.get(str(strategy).strip().lower(), str(strategy).strip().lower())
    if strat not in STRATEGY_IDS and strat != "fluid":
        strat = "balanced"
    world.decision_strategy = strat
    world.field_ai = bool(field_ai)
    world.opponent_tendency = str(strategy).strip().lower()
    return world


def opponent_ai_quarter(
    world: WorldState,
    *,
    strategy: str | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    """One Field-AI quarter: refresh strategy, decision phase already inside tick.

    For harnesses that call tick() directly, prefer arm_opponent() then tick().
    This helper re-arms fluid ranking then advances one quarter.
    """
    tendency = str(
        strategy
        or getattr(world, "opponent_tendency", None)
        or getattr(world, "decision_strategy", None)
        or "balanced"
    ).strip().lower()
    if tendency == "fluid" or getattr(world, "decision_strategy", "") == "fluid":
        pick = pick_fluid_strategy(world, tendency=str(getattr(world, "opponent_tendency", "fluid")))
        world.decision_strategy = pick
        world.last_fluid_pick = pick
        world.last_fluid_ranking = rank_strategies(
            world, tendency=str(getattr(world, "opponent_tendency", "fluid"))
        )
    else:
        arm_opponent(world, strategy=tendency, field_ai=True)
    # Ensure field AI on for this harness path
    world.field_ai = True
    # Optional: run decision phase with explicit mode before tick (tick also runs it)
    # We only set mode via env-less attribute consumed by obtain_decisions if needed.
    if mode:
        world.decision_mode_override = mode
    before = {
        "tick": world.tick,
        "pressure": float(world.qin_pressure),
        "cohesion": float(world.meso.cohesion),
        "path": world.meso.pathway_soft,
    }
    # Patch run inside tick: temporarily honor decision_mode_override
    import os

    old_mode = os.environ.get("WS_DECISION_MODE")
    if mode:
        os.environ["WS_DECISION_MODE"] = mode
    try:
        tick(world)
    finally:
        if mode is not None:
            if old_mode is None:
                os.environ.pop("WS_DECISION_MODE", None)
            else:
                os.environ["WS_DECISION_MODE"] = old_mode
    return {
        "before": before,
        "after": {
            "tick": world.tick,
            "pressure": float(world.qin_pressure),
            "cohesion": float(world.meso.cohesion),
            "path": world.meso.pathway_soft,
            "ended": bool(world.run_ended),
        },
        "decision": getattr(world, "last_decision_phase", None),
        "fluid_pick": getattr(world, "last_fluid_pick", None),
    }


def run_strategy_match(
    *,
    strategy: str,
    horizon: int = 40,
    mode: str = "mock",
    seed_world: WorldState | None = None,
) -> dict[str, Any]:
    """Single playtest match: Field AI adopts strategy; returns pathway stats."""
    world = seed_world or new_world()
    arm_opponent(world, strategy=strategy, field_ai=True)
    if strategy == "fluid":
        world.decision_strategy = "fluid"
        world.opponent_tendency = "fluid"

    ever: set[str] = set()
    strat_picks: dict[str, int] = {}
    act_kinds: dict[str, int] = {}
    for _ in range(max(1, int(horizon))):
        if world.run_ended:
            break
        # Fluid re-rank each quarter before tick
        if str(getattr(world, "decision_strategy", "")) == "fluid" or strategy == "fluid":
            pick = pick_fluid_strategy(world, tendency="fluid")
            world.decision_strategy = pick
            strat_picks[pick] = strat_picks.get(pick, 0) + 1
        else:
            # Keep baseline strategy label on world for decision phase
            world.decision_strategy = TENDENCY_TO_STRAT.get(strategy, strategy)
            strat_picks[world.decision_strategy] = strat_picks.get(world.decision_strategy, 0) + 1

        import os

        old_mode = os.environ.get("WS_DECISION_MODE")
        os.environ["WS_DECISION_MODE"] = mode
        old_field = os.environ.get("WS_FIELD_AI")
        os.environ["WS_FIELD_AI"] = "1"
        try:
            tick(world)
        finally:
            if old_mode is None:
                os.environ.pop("WS_DECISION_MODE", None)
            else:
                os.environ["WS_DECISION_MODE"] = old_mode
            if old_field is None:
                os.environ.pop("WS_FIELD_AI", None)
            else:
                os.environ["WS_FIELD_AI"] = old_field

        path = str(world.meso.pathway_soft or "other")
        ever.add(path)
        phase = getattr(world, "last_decision_phase", None) or {}
        for item in phase.get("field_fired") or []:
            kind = str(item).split(":", 1)[0]
            act_kinds[kind] = act_kinds.get(kind, 0) + 1

    final = str(world.meso.pathway_soft or "other")
    if world.run_ended and world.end_screen:
        # Prefer soft pathway still; lock kind is separate
        pass
    return {
        "strategy": strategy,
        "mode": mode,
        "ticks": world.tick,
        "final": final,
        "ever": sorted(ever),
        "ended": bool(world.run_ended),
        "lock_kind": (world.end_screen or {}).get("lock_kind") if world.run_ended else None,
        "strat_picks": strat_picks,
        "act_kinds": act_kinds,
        "pressure": float(world.qin_pressure),
        "cohesion": float(world.meso.cohesion),
        "source": (getattr(world, "last_decision_phase", None) or {}).get("source"),
    }


def monte_carlo_strategies(
    strategies: list[str] | None = None,
    *,
    n_per: int = 12,
    horizon: int = 40,
    mode: str = "mock",
) -> dict[str, Any]:
    """Small-N playtest across strategies (LLM-shaped mock or live)."""
    strategies = list(strategies or ["hezong", "peer_preempt", "qin_preempt", "fluid", "develop"])
    by_strat: dict[str, Any] = {}
    final_counts: dict[str, int] = {}
    ever_counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    act_kinds: dict[str, int] = {}
    strat_picks_all: dict[str, int] = {}

    runs = []
    for strat in strategies:
        finals: dict[str, int] = {}
        evers: dict[str, int] = {}
        for i in range(max(1, int(n_per))):
            # Light seed diversity: nudge pressure via tick offset by rebuilding
            w = new_world()
            # Deterministic diversity without RNG dependency: shift chu latency slightly
            chu = w.agents.get("chu")
            if chu is not None:
                chu.traits.response_latency = float(
                    max(0.0, min(1.2, 0.35 + 0.04 * (i % 7) + (0.05 if strat == "hezong" else 0.0)))
                )
                if strat in ("hezong", "develop"):
                    chu.traits.status_threat_sensitivity = float(
                        max(0.2, min(0.9, 0.55 - 0.03 * (i % 5)))
                    )
            m = run_strategy_match(strategy=strat, horizon=horizon, mode=mode, seed_world=w)
            runs.append(m)
            finals[m["final"]] = finals.get(m["final"], 0) + 1
            final_counts[m["final"]] = final_counts.get(m["final"], 0) + 1
            for e in m["ever"]:
                evers[e] = evers.get(e, 0) + 1
                ever_counts[e] = ever_counts.get(e, 0) + 1
            src = str(m.get("source") or mode)
            sources[src] = sources.get(src, 0) + 1
            for k, v in (m.get("act_kinds") or {}).items():
                act_kinds[k] = act_kinds.get(k, 0) + int(v)
            for k, v in (m.get("strat_picks") or {}).items():
                strat_picks_all[k] = strat_picks_all.get(k, 0) + int(v)
        by_strat[strat] = {"final": finals, "ever": evers, "n": n_per}

    total = max(1, len(runs))
    final_pct = {k: round(100.0 * v / total, 1) for k, v in sorted(final_counts.items())}
    ever_pct = {k: round(100.0 * v / total, 1) for k, v in sorted(ever_counts.items())}
    return {
        "n": total,
        "n_per": n_per,
        "horizon": horizon,
        "mode": mode,
        "strategies": strategies,
        "final_pct": final_pct,
        "ever_pct": ever_pct,
        "by_strategy": by_strat,
        "sources": sources,
        "act_kinds": act_kinds,
        "strat_picks": strat_picks_all,
        "live_llm_blocked": mode != "llm",
    }
