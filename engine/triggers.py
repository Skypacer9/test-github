"""Pause triggers — shock / lift-restrict / quorum (engine-side flags only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .world import WorldState

TriggerKind = Literal["shock", "lift_restrict", "quorum_failure", "none"]


@dataclass
class Trigger:
    kind: TriggerKind
    event_id: str
    title: str
    detail: str


def evaluate_triggers(world: "WorldState") -> Trigger | None:
    """Return a pause candidate after auto-step pressure; UI may Skip."""
    # Scheduled shock every 3rd tick
    if world.tick > 0 and world.tick % 3 == 0:
        return Trigger(
            kind="shock",
            event_id=f"shock_q{world.tick}",
            title="Qin demand / bribe probe",
            detail="A quarterly shock card is pending. Skip = default rule.",
        )
    # First defect among anti-Qin → lift-restrict
    if any(
        a.intention.current == "defect" and a.bloc == "anti_qin"
        for a in world.agents.values()
    ) and world.tick >= 2:
        return Trigger(
            kind="lift_restrict",
            event_id=f"lift_q{world.tick}",
            title="Court vignette — first Defect",
            detail="Pick Contribute / Withhold / Defect lean or nudge status_threat.",
        )
    if not world.meso.quorum_ok and world.meso.cascade_armed >= 3:
        return Trigger(
            kind="quorum_failure",
            event_id=f"quorum_q{world.tick}",
            title="Joint-campaign quorum short",
            detail="Reallocate, lower quorum, or accept fail.",
        )
    return None


def apply_shock_default(world: "WorldState") -> None:
    """Skip path: Qin pressure bump + fear rise (paced for early-game survival)."""
    thermo = world.world.thermo_dial
    # Was +4+3·thermo (~+5.5); trimmed so base +2/tick pacing still holds.
    world.qin_pressure = min(100.0, world.qin_pressure + 1.2 + 0.8 * thermo)
    for ag in world.agents.values():
        if ag.bloc == "anti_qin":
            ag.state.fear_of_qin = min(1.0, ag.state.fear_of_qin + 0.04 * thermo)
    world.append_log(
        "Shock card (default): Qin probe raises pressure; courts read the threat.",
        event_id="shock_default",
        action="shock",
        dials_fired=["thermo"],
        anchor="late Warring States alliance pressure (scaffold)",
    )
