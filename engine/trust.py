"""Dyadic trust — build slow, fall fast (η⁻ ≫ η⁺) with saturating bounds.

Chu starts as aristocratic patron–client cliques (Chunshen-style hub), not Qin fa graph.

Form: room-to-ceiling / room-to-floor updates (not unbounded linear drift).
Evidence: asymmetric η from betrayal-memory / fall-fast rise-slow social psych;
saturating toward [0,1] approximates bounded relational capital (PLACEHOLDER η coeffs).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .nonlinear import saturating_down, saturating_up
from .packets import ontology_tags_act_as_betrayal

if TYPE_CHECKING:
    from .agents import Action
    from .world import WorldState

ETA_PLUS = 0.03
ETA_MINUS = 0.18  # ≫ eta_plus

# Chu romantic/aristocratic client web — high mutual trust among southern hub clique.
# Wei (Xinling tradition) pairs with Chunshen in Shiji relief; Yan as northern guest-tie.
CHU_PATRON_CLIQUE = ("chu", "wei", "yan")


def default_trust_matrix(agent_ids: list[str]) -> dict[str, float]:
    """Directed edges as 'i->j' keys; Chu patron–client clique boosted."""
    trust: dict[str, float] = {}
    for i in agent_ids:
        for j in agent_ids:
            if i == j:
                continue
            if i == "qin" or j == "qin":
                trust[f"{i}->{j}"] = 0.15
            else:
                trust[f"{i}->{j}"] = 0.58
    # Qi isolation lean
    for other in agent_ids:
        if other in ("qi", "qin"):
            continue
        trust[f"qi->{other}"] = 0.42
        trust[f"{other}->qi"] = 0.48
    # Chu aristocratic patron–client clique (not Legalist command graph)
    for i in CHU_PATRON_CLIQUE:
        if i not in agent_ids:
            continue
        for j in CHU_PATRON_CLIQUE:
            if i == j or j not in agent_ids:
                continue
            # Patron hub warmth: Chu↔Wei especially (Chunshen + Xinling joint command)
            base = 0.72 if {i, j} == {"chu", "wei"} else 0.66
            trust[f"{i}->{j}"] = base
    # Chu looks to Qi with aristocratic hospitality hope; Qi colder (trauma)
    if "chu" in agent_ids and "qi" in agent_ids:
        trust["chu->qi"] = 0.55
        trust["qi->chu"] = 0.40
    # Zhao as northern military peer — mid trust to Chu hub
    if "zhao" in agent_ids and "chu" in agent_ids:
        trust["chu->zhao"] = 0.60
        trust["zhao->chu"] = 0.55
    return trust


def get_trust(trust: dict[str, float], i: str, j: str) -> float:
    return float(trust.get(f"{i}->{j}", 0.5))


def set_trust(trust: dict[str, float], i: str, j: str, value: float) -> None:
    trust[f"{i}->{j}"] = max(0.0, min(1.0, value))


def update_trust_from_actions(world: "WorldState", actions: dict[str, "Action"]) -> None:
    """After decisions: Confirm → slow saturating rise; Withhold/Defect → fast fall.

    Updates use room-to-bound forms:
      cooperate: T ← T + η⁺·(1−T)   (×1.35 inside Chu clique)
      withhold:  T ← T − (η⁻·0.6)·T
      defect:    T ← T − η⁻·T

    Betrayal_memory spikes only when observer's active ontology tags the act as betrayal;
    spikes themselves saturate: m ← m + δ·(1−m).
    """
    anti = [a.id for a in world.agents.values() if a.bloc == "anti_qin"]
    for observer in anti:
        obs = world.agents[observer]
        for actor in anti:
            if observer == actor:
                continue
            act = actions.get(actor, "cooperate")
            cur = get_trust(world.trust, observer, actor)
            if act == "cooperate":
                eta = ETA_PLUS
                # Patron clique: Cooperate inside Chu web builds slightly faster (en-yi)
                if observer in CHU_PATRON_CLIQUE and actor in CHU_PATRON_CLIQUE:
                    eta *= 1.35
                set_trust(world.trust, observer, actor, saturating_up(cur, eta))
            elif act == "withhold":
                set_trust(world.trust, observer, actor, saturating_down(cur, ETA_MINUS * 0.6))
                if ontology_tags_act_as_betrayal(obs.active_packets, "withhold"):
                    delta = 0.04 * obs.traits.betrayal_memory_weight
                    obs.state.betrayal_memory = saturating_up(obs.state.betrayal_memory, delta)
                    # Chu patron ontology: withhold by client = face wound
                    if "chu_patron_client" in obs.active_packets and actor in CHU_PATRON_CLIQUE:
                        obs.state.status_threat = saturating_up(obs.state.status_threat, 0.03)
            else:  # defect
                set_trust(world.trust, observer, actor, saturating_down(cur, ETA_MINUS))
                if ontology_tags_act_as_betrayal(obs.active_packets, "defect"):
                    delta = 0.12 * obs.traits.betrayal_memory_weight
                    obs.state.betrayal_memory = saturating_up(obs.state.betrayal_memory, delta)
                    obs.state.resentment = saturating_up(obs.state.resentment, 0.08)
                    if "chu_patron_client" in obs.active_packets:
                        obs.state.status_threat = saturating_up(obs.state.status_threat, 0.06)


def mean_bloc_trust(world: "WorldState") -> float:
    anti = [
        a.id
        for a in world.agents.values()
        if a.bloc == "anti_qin" and not getattr(a, "annexed", False)
    ]
    if len(anti) < 2:
        return 50.0
    vals = [get_trust(world.trust, i, j) for i in anti for j in anti if i != j]
    return 100.0 * (sum(vals) / len(vals)) if vals else 50.0


def chu_clique_strength(world: "WorldState") -> float:
    """Order-parameter-ish: mean mutual trust inside Chu patron clique."""
    members = [m for m in CHU_PATRON_CLIQUE if m in world.agents]
    if len(members) < 2:
        return 0.0
    vals = [
        get_trust(world.trust, i, j)
        for i in members
        for j in members
        if i != j
    ]
    return sum(vals) / len(vals) if vals else 0.0
