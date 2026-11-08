"""State / faction agents — PAS-lite traits + sticky intentions.

OCEAN priors loaded from docs/big-five-historical-profiles.json when mapped.
Belief starting sets = ontology packets (packets.py), not scalar labels.
No Ling / private-chat grafts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .packets import conflict_score, starting_packets, starting_weights
from .profiles import ocean_for_state, profile_meta_for_state

Action = Literal["cooperate", "withhold", "defect"]

# Historical-scaffold agents only (no Ling / fiction cast).
STATE_IDS = ("qin", "chu", "qi", "zhao", "han", "wei", "yan")


@dataclass
class Traits:
    """Slow layer — Big Five–lite + ideology weights (0–1)."""

    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5
    legalist_centralism: float = 0.3  # affinity dial → legalist_fa ontology
    lineage_honor: float = 0.5  # affinity dial → lineage_shi
    tianxia_unity: float = 0.6  # affinity dial → tianxia_da_yitong
    status_threat_sensitivity: float = 0.5
    response_latency: float = 0.0  # quarters of delay bias (esp. Chu)
    betrayal_memory_weight: float = 0.5
    memory_bias: float = 0.0  # isolation / trauma lean (Qi post-284)


@dataclass
class AffectiveState:
    """Fast layer — per-tick / per-event."""

    resentment: float = 0.0
    fear_of_qin: float = 0.3
    betrayal_memory: float = 0.2
    status_threat: float = 0.3
    perceived_threat: float = 0.3
    withholding_threshold: float = 0.55
    # Cascade latch: once armed, needs margin below threshold to disarm (hysteresis).
    cascade_latched: bool = False
    # Defection inertia: sustained defect pressure must accumulate before Defect fires.
    # Counts ticks of (resentment > fear_of_qin ∧ PAS defect pull); Defect only at ≥3.
    defection_accumulator: int = 0


@dataclass
class Intention:
    current: Action = "cooperate"
    sticky_until: int = 0
    hysteresis_mu: float = 0.08


# Geographic yield priors (scaffold): Chu river/rice high; Qin Legalist efficiency high.
GEOGRAPHIC_YIELD: dict[str, float] = {
    "qin": 0.78,  # Guanzhong + Legalist extractive efficiency
    "chu": 0.88,  # Yangtze riverine / rice basin
    "qi": 0.70,  # peninsula commerce + grain
    "zhao": 0.62,  # northern steppe-edge
    "han": 0.58,  # small corridor state
    "wei": 0.66,  # central plain
    "yan": 0.55,  # far northeast
}

RESOURCE_SEED: dict[str, tuple[float, float]] = {
    # (grain, treasury) 0–100 scale
    "qin": (72.0, 80.0),
    "chu": (85.0, 62.0),
    "qi": (70.0, 74.0),
    "zhao": (58.0, 55.0),
    "han": (48.0, 50.0),
    "wei": (60.0, 58.0),
    "yan": (52.0, 48.0),
}


@dataclass
class Agent:
    id: str
    name: str
    bloc: Literal["qin", "anti_qin"] = "anti_qin"
    traits: Traits = field(default_factory=Traits)
    state: AffectiveState = field(default_factory=AffectiveState)
    intention: Intention = field(default_factory=Intention)
    active_packets: list[str] = field(default_factory=list)
    packet_weights: dict[str, float] = field(default_factory=dict)  # syncretic mix
    profile_ids: list[str] = field(default_factory=list)
    profile_confidence: str = "scaffold"
    # Econ / war layer
    viability: float = 100.0
    grain: float = 60.0
    treasury: float = 60.0
    geographic_yield: float = 0.6
    annexed: bool = False
    annexed_by: str | None = None
    stance_mode: str = "coalition"  # coalition | optimizing | desperate | annexed
    desperate: bool = False

    def clamp(self) -> None:
        s = self.state
        for attr in (
            "resentment",
            "fear_of_qin",
            "betrayal_memory",
            "status_threat",
            "perceived_threat",
            "withholding_threshold",
        ):
            setattr(s, attr, max(0.0, min(1.0, float(getattr(s, attr)))))
        s.cascade_latched = bool(getattr(s, "cascade_latched", False))
        s.defection_accumulator = max(0, int(getattr(s, "defection_accumulator", 0) or 0))
        self.viability = max(0.0, min(100.0, float(self.viability)))
        self.grain = max(0.0, min(100.0, float(self.grain)))
        self.treasury = max(0.0, min(100.0, float(self.treasury)))
        self.geographic_yield = max(0.0, min(1.0, float(self.geographic_yield)))
        # String 'false' must not become True
        if isinstance(self.annexed, str):
            self.annexed = self.annexed.strip().lower() in ("1", "true", "yes", "y", "on")
        else:
            self.annexed = bool(self.annexed)
        if isinstance(self.desperate, str):
            self.desperate = self.desperate.strip().lower() in ("1", "true", "yes", "y", "on")
        else:
            self.desperate = bool(self.desperate)
        if self.annexed:
            self.stance_mode = "annexed"


def _apply_ocean(traits: Traits, state_id: str) -> None:
    ocean = ocean_for_state(state_id)
    traits.openness = float(ocean["O"])
    traits.conscientiousness = float(ocean["C"])
    traits.extraversion = float(ocean["E"])
    traits.agreeableness = float(ocean["A"])
    traits.neuroticism = float(ocean["N"])


def _profiles() -> dict[str, Agent]:
    """Historiography-anchored dials — OCEAN from JSON; packets = ontologies."""
    agents: dict[str, Agent] = {
        "qin": Agent(
            id="qin",
            name="Qin",
            bloc="qin",
            traits=Traits(
                legalist_centralism=0.9,
                lineage_honor=0.35,
                tianxia_unity=0.25,
                status_threat_sensitivity=0.25,
                betrayal_memory_weight=0.2,
            ),
            state=AffectiveState(
                resentment=0.22,
                fear_of_qin=0.0,
                betrayal_memory=0.1,
                status_threat=0.2,
                perceived_threat=0.15,
                withholding_threshold=0.75,
            ),
            active_packets=starting_packets("qin"),
            packet_weights=starting_weights("qin"),
        ),
        "chu": Agent(
            id="chu",
            name="Chu",
            traits=Traits(
                legalist_centralism=0.12,  # explicitly NOT Qin fa court
                lineage_honor=0.7,
                tianxia_unity=0.5,
                status_threat_sensitivity=0.8,
                response_latency=1.2,
                betrayal_memory_weight=0.55,
                openness=0.55,  # overwritten by JSON blend; Dao receptivity lean
            ),
            state=AffectiveState(
                resentment=0.35,
                fear_of_qin=0.4,
                betrayal_memory=0.35,
                status_threat=0.55,
                perceived_threat=0.4,
                withholding_threshold=0.48,
            ),
            active_packets=starting_packets("chu"),
            packet_weights=starting_weights("chu"),
        ),
        "qi": Agent(
            id="qi",
            name="Qi",
            traits=Traits(
                legalist_centralism=0.25,
                lineage_honor=0.55,
                tianxia_unity=0.4,
                status_threat_sensitivity=0.45,
                betrayal_memory_weight=0.85,
                memory_bias=0.7,
            ),
            state=AffectiveState(
                resentment=0.25,
                fear_of_qin=0.35,
                betrayal_memory=0.55,
                status_threat=0.35,
                perceived_threat=0.35,
                withholding_threshold=0.42,
            ),
            active_packets=starting_packets("qi"),
            packet_weights=starting_weights("qi"),
        ),
        "zhao": Agent(
            id="zhao",
            name="Zhao",
            traits=Traits(
                lineage_honor=0.6,
                tianxia_unity=0.5,
                status_threat_sensitivity=0.55,
                betrayal_memory_weight=0.65,
                memory_bias=0.55,
            ),
            state=AffectiveState(
                fear_of_qin=0.55,
                betrayal_memory=0.45,
                perceived_threat=0.5,
                withholding_threshold=0.5,
            ),
            active_packets=starting_packets("zhao"),
            packet_weights=starting_weights("zhao"),
        ),
        "han": Agent(
            id="han",
            name="Han",
            traits=Traits(
                legalist_centralism=0.45,
                tianxia_unity=0.45,
                status_threat_sensitivity=0.5,
                betrayal_memory_weight=0.6,
            ),
            state=AffectiveState(
                fear_of_qin=0.6,
                perceived_threat=0.55,
                withholding_threshold=0.5,
            ),
            active_packets=starting_packets("han"),
            packet_weights=starting_weights("han"),
        ),
        "wei": Agent(
            id="wei",
            name="Wei",
            traits=Traits(
                tianxia_unity=0.45,
                lineage_honor=0.4,
                status_threat_sensitivity=0.55,
                betrayal_memory_weight=0.6,
            ),
            state=AffectiveState(
                fear_of_qin=0.55,
                perceived_threat=0.5,
                withholding_threshold=0.52,
            ),
            active_packets=starting_packets("wei"),
            packet_weights=starting_weights("wei"),
        ),
        "yan": Agent(
            id="yan",
            name="Yan",
            traits=Traits(
                tianxia_unity=0.5,
                status_threat_sensitivity=0.4,
                betrayal_memory_weight=0.45,
            ),
            state=AffectiveState(
                fear_of_qin=0.45,
                perceived_threat=0.4,
                withholding_threshold=0.5,
            ),
            active_packets=starting_packets("yan"),
            packet_weights=starting_weights("yan"),
        ),
    }
    for aid, ag in agents.items():
        _apply_ocean(ag.traits, aid)
        meta = profile_meta_for_state(aid)
        ag.profile_ids = list(meta.get("profile_ids") or [])
        ag.profile_confidence = str(meta.get("confidence") or "scaffold")
        if not ag.packet_weights:
            ag.packet_weights = starting_weights(aid)
        if not ag.active_packets:
            ag.active_packets = starting_packets(aid)
        ag.geographic_yield = float(GEOGRAPHIC_YIELD.get(aid, 0.6))
        g, t = RESOURCE_SEED.get(aid, (60.0, 60.0))
        ag.grain = float(g)
        ag.treasury = float(t)
        ag.viability = 100.0
        ag.annexed = False
        ag.annexed_by = None
        ag.stance_mode = "coalition"
        ag.desperate = False
    return agents


def default_agents() -> dict[str, Agent]:
    return _profiles()


# Sustained defect-pressure ticks required before anti-Qin Defect fires.
DEFECTION_ACCUMULATOR_THRESHOLD = 3


def decide_action(agent: Agent, qin_pressure: float, cohesion: float, tick: int) -> Action:
    """Soft-threshold PAS with sticky hysteresis + defection inertia + fear gate.

    Score→choice is not a pure linear weighted sum: pressure enters mildly
    superlinear, defect uses a logistic soft gate past withholding_threshold,
    and near-ties prefer the sticky intention via softmax-margin hysteresis.

    Early-game pacing (anti-Qin):
      • Fear deterrent — Defect only if resentment > fear_of_qin.
      • Defection inertia — when defect pressure holds, accumulator += 1/tick;
        Withhold while accumulator < 3; Defect only at ≥3. Decay when cleared.
    """
    from .nonlinear import clamp, soft_margins, soft_threshold

    # Annexed courts take no coalition acts
    if getattr(agent, "annexed", False):
        agent.intention.current = "withhold"
        return "withhold"

    if agent.bloc == "qin":
        if agent.intention.current == "withhold" and tick < agent.intention.sticky_until:
            return "withhold"
        agent.intention.current = "defect"
        return "defect"

    s, t = agent.state, agent.traits
    conflict = conflict_score(agent.active_packets, agent.packet_weights)
    latency_penalty = 0.06 * t.response_latency
    pressure_u = qin_pressure / 100.0
    # Mild superlinear pressure perception (accelerating threat near high P)
    pressure_term = 0.45 * (pressure_u ** 1.15)
    cohesion_shelter = 0.2 * ((cohesion / 100.0) ** 0.85) * t.tianxia_unity
    threat = (
        pressure_term
        + 0.25 * s.fear_of_qin
        + 0.15 * s.status_threat * t.status_threat_sensitivity
        + 0.15 * s.betrayal_memory * t.betrayal_memory_weight
        + latency_penalty
        + 0.1 * t.memory_bias
        + 0.08 * conflict
        - cohesion_shelter
    )
    s.perceived_threat = clamp(threat)

    # Soft gate past withholding threshold (replaces hinge max(0, threat−θ))
    excess = soft_threshold(s.perceived_threat, s.withholding_threshold, k=9.0)

    from .ideology import ideology_vector

    ideo = ideology_vector(agent)
    coop = (
        t.tianxia_unity * 0.5
        + (1.0 - s.perceived_threat) * 0.4
        + (1.0 - s.resentment) * 0.1
        + 0.05 * t.agreeableness
        + 0.18 * ideo["mohist"]  # Mohism → contribute / shared-care lean
        + 0.10 * ideo["tianxia"]
        + 0.06 * ideo["patron"]
    )
    withhold = (
        s.perceived_threat * 0.35
        + s.status_threat * t.status_threat_sensitivity * 0.35
        + s.resentment * 0.2
        + latency_penalty
        + 0.12 * conflict  # ontology clash → hesitation
        + 0.08 * excess  # near-threshold hesitation bulge
        + 0.08 * ideo["guanzi"]  # mercantile caution
    )
    defect = (
        s.betrayal_memory * t.betrayal_memory_weight * 0.4
        + s.perceived_threat * 0.25
        + (1.0 - t.agreeableness) * 0.15
        + 0.55 * excess  # logistic soft threshold → defect pull
        + 0.14 * ideo["legalist"]  # fa pressure → harder lean
        - 0.12 * ideo["mohist"]  # non-attack dampens defect pull
    )

    scores = {"cooperate": coop, "withhold": withhold, "defect": defect}
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_act, best_score = ranked[0]
    cur = agent.intention.current
    cur_score = scores.get(cur, scores["cooperate"])
    margins = soft_margins(scores, temperature=0.14)
    # Softmax margin: require clearer win to switch when sticky (beyond raw μ)
    soft_gap = float(margins.get(best_act, 0.0)) - float(margins.get(cur, 0.0))

    if tick < agent.intention.sticky_until:
        if (best_score - cur_score) < agent.intention.hysteresis_mu or soft_gap < 0.12:
            best_act = cur
            best_score = scores.get(cur, best_score)

    # --- Fear deterrent + defection inertia (anti-Qin only) ---
    # Defect pressure: PAS prefers defect AND resentment exceeds fear_of_qin.
    fear_ok = float(s.resentment) > float(s.fear_of_qin)
    pas_wants_defect = (
        scores["defect"] >= scores["withhold"] and scores["defect"] >= scores["cooperate"]
    )
    defect_pressure = pas_wants_defect and fear_ok

    if defect_pressure:
        s.defection_accumulator = int(getattr(s, "defection_accumulator", 0) or 0) + 1
        if s.defection_accumulator >= DEFECTION_ACCUMULATOR_THRESHOLD:
            if best_act != "defect":
                agent.intention.sticky_until = tick + 1
            agent.intention.current = "defect"
            return "defect"
        # Building toward Defect — Withhold meanwhile
        if agent.intention.current != "withhold":
            agent.intention.sticky_until = tick + 1
        agent.intention.current = "withhold"
        return "withhold"

    # Conditions cleared: decay accumulator (or hard-reset after cool interventions)
    acc = int(getattr(s, "defection_accumulator", 0) or 0)
    if acc > 0:
        s.defection_accumulator = max(0, acc - 1)

    # PAS may still score Defect highest, but fear gate blocks it → Withhold
    if best_act == "defect" and not fear_ok:
        if agent.intention.current != "withhold":
            agent.intention.sticky_until = tick + 1
        agent.intention.current = "withhold"
        return "withhold"

    if best_act != cur:
        agent.intention.sticky_until = tick + 1
    agent.intention.current = best_act  # type: ignore[assignment]
    return agent.intention.current
