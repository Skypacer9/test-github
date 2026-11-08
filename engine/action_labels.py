"""Human-facing labels for Cooperate/Withhold/Defect.

Engine ids stay cooperate|withhold|defect. UI/log prose always frames the
anti-Qin coalition stance — never Qin↔Chu friendship.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .world import WorldState

# Short nameplate / chip labels
SHORT: dict[str, str] = {
    "cooperate": "Contribute",
    "withhold": "Withhold",
    "defect": "Defect",
}

# Full stance toward the anti-Qin coalition
FULL: dict[str, str] = {
    "cooperate": "Contribute to anti-Qin coalition",
    "withhold": "Withhold from anti-Qin coalition",
    "defect": "Defect from anti-Qin coalition",
}

# Qin is the pressure source — not a coalition voter
QIN_FULL: dict[str, str] = {
    "cooperate": "Pause offensive probe (rare)",
    "withhold": "Hold probe / consolidate",
    "defect": "Press offensive against the bloc",
}


def short_label(action: str, *, bloc: str = "anti_qin") -> str:
    act = (action or "").lower()
    if bloc == "qin":
        return {
            "cooperate": "Pause",
            "withhold": "Hold probe",
            "defect": "Press Qin",
        }.get(act, act or "?")
    return SHORT.get(act, act or "?")


def full_label(action: str, *, bloc: str = "anti_qin") -> str:
    act = (action or "").lower()
    if bloc == "qin":
        return QIN_FULL.get(act, act or "?")
    return FULL.get(act, act or "?")


def decision_line(agent_name: str, agent_id: str, action: str, *, bloc: str) -> str:
    """Episode / dialogue line for one decision — no friendship implication."""
    stance = full_label(action, bloc=bloc)
    if bloc == "qin":
        return f"{agent_name}: {stance} (Qin pressure source — not a coalition partner)."
    return f"{agent_name}: {stance}."


def who_vs_qin_line(world: "WorldState", actions: dict[str, str] | None = None) -> str:
    """One-liner: living anti-Qin (not annexed) vs Qin pressure."""
    acts = actions if actions is not None else dict(world.last_actions)
    anti = []
    for aid, ag in world.agents.items():
        if ag.bloc != "anti_qin":
            continue
        if getattr(ag, "annexed", False):
            continue
        act = acts.get(aid, ag.intention.current)
        anti.append(f"{ag.name}={short_label(act)}")
    who = ", ".join(anti) if anti else "(none living)"
    return f"who: {who} vs Qin pressure {world.qin_pressure:.0f}"


def format_decision_records(
    world: "WorldState",
    actions: dict[str, str],
) -> list[dict[str, Any]]:
    """Build clear log payloads for each actor + optional who-line."""
    rows: list[dict[str, Any]] = []
    for aid, act in actions.items():
        ag = world.agents.get(aid)
        if not ag or getattr(ag, "annexed", False):
            continue  # annexed courts out of stance rollups
        rows.append(
            {
                "actor": aid,
                "action": act,
                "text": decision_line(ag.name, aid, act, bloc=ag.bloc),
            }
        )
    rows.append(
        {
            "actor": "world",
            "action": "who_vs_qin",
            "text": who_vs_qin_line(world, actions),
        }
    )
    return rows
