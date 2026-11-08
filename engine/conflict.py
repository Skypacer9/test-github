"""Viability, resources, desperation, Attack Neighbor, Optimizing, annexation.

Early-game pacing: attack gates stay conservative so unassisted runs can last
≥12–15 ticks. Soft-lock remains mechanism-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .agents import GEOGRAPHIC_YIELD, RESOURCE_SEED
from .trust import get_trust, set_trust

if TYPE_CHECKING:
    from .world import WorldState

# Contiguous-ish late Warring States neighbor graph (scaffold, not GIS).
NEIGHBORS: dict[str, tuple[str, ...]] = {
    "qin": ("wei", "han", "chu", "zhao"),
    "chu": ("qin", "han", "wei", "qi"),
    "qi": ("chu", "zhao", "yan"),
    "zhao": ("qin", "wei", "yan", "qi"),
    "han": ("qin", "wei", "chu"),
    "wei": ("qin", "zhao", "han", "chu"),
    "yan": ("zhao", "qi"),
}

LOW_FEAR = 0.38
LOW_NEIGHBOR_TRUST = 0.40
OPTIMIZING_TRUST = 0.22  # mean neighbor trust < ~22% → Optimizing
DESPERATION_PCT = 30.0  # viability OR resource pool < 30% → Desperate
VIABILITY_START = 100.0
LOSS_VIABILITY_HIT = 22.0  # chunk, not instant wipe (was 30)
WINNER_EXHAUSTION = 4.0
ATTACK_COHESION_TAX = 4.5  # rivalry tax, not coalition death
ANNEX_COHESION_HIT = 10.0  # stronger coalition shock on annex
ALLY_BETRAYAL_SPIKE = 0.28  # sharp betrayal when anti-Qin strikes anti-Qin ally
ALLY_BETRAYAL_BYSTANDER = 0.12
ANNEX_BYSTANDER_RESENT = 0.18
ANNEX_BYSTANDER_BETRAYAL = 0.15
ANNEX_BYSTANDER_TRUST_CHILL = 0.12
WAR_TRUST_HIT = 0.32  # was 0.22 — stronger dyadic chill both ways
WAR_RESENTMENT_HIT = 0.10
VIABILITY_REGEN_CAP = 1.8  # mild per-tick regen when not Desperate
# Spend costs — coherent with quarterly income (~2–4 grain/treasury)
ATTACK_COST_TREASURY = 5.0
ATTACK_COST_GRAIN = 4.0
DEFENSE_COST_TREASURY = 2.5
DEFENSE_COST_GRAIN = 2.0
SPOILS_FRACTION = 0.28  # ~30% loser resources stolen
YIELD_LOSS_ON_DEFEAT = 0.04
ATTACK_MIN_TICK = 4
# Mid-game rivalry texture: 1 early, up to 2 once precarious peace settles
MAX_ATTACKS_EARLY = 1
MAX_ATTACKS_MID = 2
MIDGAME_TICK = 10


def _alive(ag: Any) -> bool:
    return ag is not None and not bool(getattr(ag, "annexed", False))


def resource_pool(ag: Any) -> float:
    """Combined grain+treasury as 0–100-ish pool average."""
    return 0.5 * (float(getattr(ag, "grain", 0.0)) + float(getattr(ag, "treasury", 0.0)))


def ensure_econ_fields(world: "WorldState") -> None:
    for aid, ag in world.agents.items():
        if not hasattr(ag, "viability") or ag.viability is None:
            ag.viability = VIABILITY_START
        if not hasattr(ag, "grain") or ag.grain is None:
            g, t = RESOURCE_SEED.get(aid, (60.0, 60.0))
            ag.grain = float(g)
            ag.treasury = float(t)
        if not hasattr(ag, "treasury") or ag.treasury is None:
            ag.treasury = float(RESOURCE_SEED.get(aid, (60.0, 60.0))[1])
        if not hasattr(ag, "geographic_yield") or ag.geographic_yield is None:
            ag.geographic_yield = float(GEOGRAPHIC_YIELD.get(aid, 0.6))
        if not hasattr(ag, "annexed"):
            ag.annexed = False
        if not hasattr(ag, "annexed_by"):
            ag.annexed_by = None
        if not hasattr(ag, "stance_mode"):
            ag.stance_mode = "coalition"
        if not hasattr(ag, "desperate"):
            ag.desperate = False


# Back-compat alias
ensure_viability_fields = ensure_econ_fields


def military_strength(world: "WorldState", aid: str) -> float:
    """Coarse mil/resources proxy for conflict resolution."""
    ag = world.agents.get(aid)
    if not _alive(ag):
        return 0.0
    w = world.world
    if ag.bloc == "qin":
        mil = float(getattr(w, "military_qin", 0.35) or 0.35)
    else:
        mil = float(getattr(w, "military_coalition", 0.30) or 0.30) * 0.55
        demo = getattr(world, "demographics", None)
        mp = 0.5
        if demo is not None and hasattr(demo, "courts"):
            court = demo.courts.get(aid) if hasattr(demo, "courts") else None
            if court is not None and hasattr(court, "available_manpower"):
                mp = float(court.available_manpower)
        mil = mil + 0.25 * mp
    if ag.bloc == "qin":
        mil += 0.12 * float(getattr(w, "qin_projection", 0.4) or 0.4)
    # Resources + yield feed fight power
    mil += 0.20 * (resource_pool(ag) / 100.0)
    mil += 0.15 * float(ag.geographic_yield)
    # M2 tech Adoption Meter — fielded crafts weight the spear
    tech = getattr(world, "tech", None)
    if tech is not None:
        mil_map = getattr(tech, "military", None) or {}
        if isinstance(mil_map, dict):
            mil += 0.35 * float(mil_map.get(aid, 0.0) or 0.0)
    return max(0.05, mil + 0.30 * (float(ag.viability) / 100.0))


def can_afford_attack(ag: Any) -> bool:
    """Must cover full attack spend — broke courts cannot raid."""
    return float(ag.treasury) >= ATTACK_COST_TREASURY and float(ag.grain) >= ATTACK_COST_GRAIN


def can_afford_defense(ag: Any) -> bool:
    return float(ag.treasury) >= DEFENSE_COST_TREASURY and float(ag.grain) >= DEFENSE_COST_GRAIN


def spend_attack(ag: Any) -> None:
    ag.treasury = max(0.0, float(ag.treasury) - ATTACK_COST_TREASURY)
    ag.grain = max(0.0, float(ag.grain) - ATTACK_COST_GRAIN)


def spend_defense(ag: Any) -> None:
    ag.treasury = max(0.0, float(ag.treasury) - DEFENSE_COST_TREASURY)
    ag.grain = max(0.0, float(ag.grain) - DEFENSE_COST_GRAIN)


def max_attacks_this_tick(world: "WorldState") -> int:
    t = int(getattr(world, "tick", 0) or 0)
    return MAX_ATTACKS_MID if t >= MIDGAME_TICK else MAX_ATTACKS_EARLY


def mean_neighbor_trust(world: "WorldState", aid: str) -> float:
    nbrs = [n for n in NEIGHBORS.get(aid, ()) if n in world.agents and _alive(world.agents[n])]
    if not nbrs:
        return 0.5
    vals = []
    for n in nbrs:
        vals.append(get_trust(world.trust, aid, n))
        vals.append(get_trust(world.trust, n, aid))
    return sum(vals) / len(vals) if vals else 0.5


def update_desperation(world: "WorldState") -> list[str]:
    """Resources or viability < 30% → Desperate (ignore Fear_of_Qin, raid for theft)."""
    ensure_econ_fields(world)
    flipped: list[str] = []
    for ag in world.agents.values():
        if not _alive(ag) or ag.bloc != "anti_qin":
            ag.desperate = False
            continue
        low_v = float(ag.viability) < DESPERATION_PCT
        low_r = resource_pool(ag) < DESPERATION_PCT
        was = bool(ag.desperate)
        ag.desperate = low_v or low_r
        if ag.desperate:
            ag.stance_mode = "desperate"
            if not was:
                flipped.append(ag.id)
        elif ag.stance_mode == "desperate":
            ag.stance_mode = "coalition"
    return flipped


def update_optimizing_modes(world: "WorldState") -> list[str]:
    """Trust < 20% with neighbors → Optimizing (unless already Desperate)."""
    ensure_econ_fields(world)
    flipped: list[str] = []
    for ag in world.agents.values():
        if not _alive(ag) or ag.bloc != "anti_qin":
            continue
        if ag.desperate:
            continue
        mt = mean_neighbor_trust(world, ag.id)
        if mt < OPTIMIZING_TRUST:
            if ag.stance_mode != "optimizing":
                flipped.append(ag.id)
            ag.stance_mode = "optimizing"
        elif ag.stance_mode == "optimizing":
            ag.stance_mode = "coalition"
    return flipped


def _weaker_neighbor(world: "WorldState", aid: str) -> str | None:
    nbrs = [
        n
        for n in NEIGHBORS.get(aid, ())
        if n in world.agents and _alive(world.agents[n]) and world.agents[n].bloc == "anti_qin"
    ]
    if not nbrs:
        return None
    scored = sorted(
        nbrs,
        key=lambda n: (
            resource_pool(world.agents[n]),
            float(world.agents[n].viability),
            military_strength(world, n),
        ),
    )
    return scored[0]


def _precarious_restraint(world: "WorldState", aid: str, target: str) -> bool:
    """Temporary competitive restraint under precarious peace / stalemate.

    Warm dyads (mutual trust ≥0.50) among living anti-Qin hold fire while
    pathway reads stalemate — fragile détente, not annihilation. Desperate
    and Optimizing still break the restraint (zero-sum default mid-game).
    """
    if world.meso.pathway_soft != "stalemate":
        return False
    ag = world.agents.get(aid)
    if ag is None or ag.desperate or ag.stance_mode == "optimizing":
        return False
    mutual = 0.5 * (
        get_trust(world.trust, aid, target) + get_trust(world.trust, target, aid)
    )
    return mutual >= 0.50


def ideology_raid_score(ag: Any) -> float:
    """Legalist↑ raid appetite; Mohism/tianxia/patron↓ unless Desperation.

    Mohism (兼爱/非攻 soft prior) dampens neighbor raids when present in
    packet_weights. Returns roughly 0–1.2; Desperate always high.
    """
    if getattr(ag, "desperate", False):
        return 1.25
    from .ideology import ideology_vector, rare_combo_bonus

    v = ideology_vector(ag)
    # Legalist↑ raid priors; soft + mohist↓ (non-attack lean)
    score = 0.32 + 0.50 * v["legalist"] + 0.22 * v["hard"] - 0.42 * v["soft"] - 0.35 * v["mohist"]
    combo = rare_combo_bonus(ag, tick=int(getattr(ag, "_ideo_tick", 0) or 0), sid=str(getattr(ag, "id", "")))
    score += float(combo.get("raid") or 0.0)
    if getattr(ag, "stance_mode", "") == "optimizing":
        score += 0.18
    return max(0.0, min(1.35, score))


def choose_attack_target(world: "WorldState", aid: str) -> str | None:
    ag = world.agents.get(aid)
    if not _alive(ag) or ag.bloc == "qin":
        return None
    if world.tick < ATTACK_MIN_TICK:
        return None
    if not can_afford_attack(ag):
        return None

    nbrs = [
        n
        for n in NEIGHBORS.get(aid, ())
        if n in world.agents and _alive(world.agents[n]) and world.agents[n].bloc == "anti_qin"
    ]
    if not nbrs:
        return None

    # Desperate: ignore Fear_of_Qin — high Attack Neighbor for theft
    if ag.desperate:
        return _weaker_neighbor(world, aid)

    # Ideology gate: soft tianxia/patron courts often refuse to raid
    try:
        ag._ideo_tick = int(getattr(world, "tick", 0) or 0)
    except Exception:
        pass
    ideo = ideology_raid_score(ag)
    if ideo < 0.28 and ag.stance_mode != "optimizing":
        return None

    if ag.stance_mode == "optimizing":
        tgt = _weaker_neighbor(world, aid)
        return tgt

    # Legalist lowers effective fear barrier; soft courts need lower fear to raid
    fear = float(ag.state.fear_of_qin)
    fear_gate = LOW_FEAR + 0.10 * (0.55 - ideo)  # soft → harder to pass
    if fear > fear_gate:
        return None
    candidates = []
    for n in nbrs:
        if _precarious_restraint(world, aid, n):
            continue  # temporary restraint toward warm partners
        mutual = 0.5 * (
            get_trust(world.trust, aid, n) + get_trust(world.trust, n, aid)
        )
        if mutual < LOW_NEIGHBOR_TRUST:
            candidates.append((mutual, n))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


def saturating_trust_hit(cur: float, eta: float) -> float:
    from .nonlinear import saturating_down

    return saturating_down(cur, eta)


def steal_resources(winner: Any, loser: Any) -> dict[str, float]:
    """Winner steals ~30% of loser grain/treasury."""
    g_take = SPOILS_FRACTION * float(loser.grain)
    t_take = SPOILS_FRACTION * float(loser.treasury)
    loser.grain = max(0.0, float(loser.grain) - g_take)
    loser.treasury = max(0.0, float(loser.treasury) - t_take)
    winner.grain = min(100.0, float(winner.grain) + g_take)
    winner.treasury = min(100.0, float(winner.treasury) + t_take)
    return {"grain": round(g_take, 1), "treasury": round(t_take, 1)}



def _apply_ally_betrayal_spike(world: "WorldState", attacker_id: str, defender_id: str) -> None:
    """Anti-Qin attacking anti-Qin peer → sharp betrayal_memory + figure memories."""
    atk = world.agents.get(attacker_id)
    dfn = world.agents.get(defender_id)
    if not atk or not dfn:
        return
    if getattr(atk, "bloc", "") != "anti_qin" or getattr(dfn, "bloc", "") != "anti_qin":
        return
    if getattr(atk, "annexed", False) or getattr(dfn, "annexed", False):
        return
    from .nonlinear import saturating_up
    dfn.state.betrayal_memory = float(
        min(1.0, saturating_up(float(dfn.state.betrayal_memory), ALLY_BETRAYAL_SPIKE))
    )
    dfn.state.resentment = float(
        min(1.0, saturating_up(float(dfn.state.resentment), ALLY_BETRAYAL_SPIKE * 0.7))
    )
    bystanders = []
    for oid, other in world.agents.items():
        if oid in (attacker_id, defender_id):
            continue
        if getattr(other, "bloc", "") != "anti_qin" or getattr(other, "annexed", False):
            continue
        other.state.betrayal_memory = float(
            min(1.0, saturating_up(float(other.state.betrayal_memory), ALLY_BETRAYAL_BYSTANDER))
        )
        bystanders.append(other.name)
    line = (
        f"Ally betrayal: {atk.name} struck peer {dfn.name} — "
        f"victim betrayal_memory↑; "
        + (f"bystanders {', '.join(bystanders)} chill" if bystanders else "coalition scar")
    )
    world.append_log(
        line,
        event_id="ally_betrayal",
        actor=attacker_id,
        action="ally_strike",
        dials_fired=["betrayal_memory", "resentment", "trust"],
    )
    try:
        from .figure_memory import record_ally_betrayal, record_pattern
        record_ally_betrayal(world, attacker_id, defender_id)
        record_pattern(world, f"Ally-strike pattern: {atk.name}→{dfn.name}")
        pr = list(getattr(world, "pattern_reactions", None) or [])
        pr.append(f"[t={world.tick}] {line[:100]}")
        world.pattern_reactions = pr[-8:]
    except Exception:
        pass

def levy_extract(world: "WorldState", aid: str) -> float:
    """0–1 levy/manpower extract proxy for front capacity."""
    demo = getattr(world, "demographics", None)
    if demo is None or not hasattr(demo, "courts"):
        return 0.45
    court = demo.courts.get(aid) if hasattr(demo, "courts") else None
    if court is None:
        return 0.45
    levy = float(getattr(court, "levy_base", 0.5) or 0.5)
    mp = float(getattr(court, "available_manpower", 0.5) or 0.5)
    return max(0.0, min(1.0, 0.55 * levy + 0.45 * mp))


def coerce_offensive_fronts(raw: Any) -> dict[str, list[str]]:
    """Normalize fronts map: attacker → list of target ids opened this quarter.

    Legacy ``{attacker: int}`` counts become opaque placeholders (capacity only).
    """
    out: dict[str, list[str]] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        aid = str(k).strip().lower()
        if not aid:
            continue
        if isinstance(v, list):
            seen: list[str] = []
            for x in v:
                tid = str(x).strip().lower()
                if tid and tid not in seen:
                    seen.append(tid)
            if seen:
                out[aid] = seen
        elif isinstance(v, (int, float)):
            n = max(0, int(v))
            if n:
                out[aid] = [f"_open{i}" for i in range(n)]
    return out


def front_targets_for(world: "WorldState", aid: str) -> list[str]:
    fronts = coerce_offensive_fronts(getattr(world, "player_offensive_fronts", None))
    return list(fronts.get(str(aid), []) or [])


def active_front_targets(world: "WorldState") -> set[str]:
    """Targets that already have an active front this quarter (any attacker)."""
    fronts = coerce_offensive_fronts(getattr(world, "player_offensive_fronts", None))
    out: set[str] = set()
    for targets in fronts.values():
        for tid in targets:
            if tid and not str(tid).startswith("_open"):
                out.add(str(tid))
    return out


def front_pair_blocked(world: "WorldState", attacker: str, target: str) -> str | None:
    """Refuse stacking the same attacker→target (or a second front on the same target)."""
    aid = str(attacker).strip().lower()
    tid = str(target).strip().lower()
    if not aid or not tid:
        return None
    if tid in front_targets_for(world, aid):
        return f"front already open: {aid}→{tid} this quarter"
    if tid in active_front_targets(world):
        return f"target {tid} already has an active front this quarter"
    return None


def offensive_capacity(world: "WorldState", aid: str) -> dict[str, Any]:
    """How many simultaneous fronts this court can still open this quarter.

    Strong courts (force + levy + grain + viability) may open several fronts;
    weak courts get 0–1. Already-opened fronts this quarter reduce residual.
    Pair/target uniqueness is enforced separately in player_offensive.
    """
    ensure_econ_fields(world)
    ag = world.agents.get(aid)
    if not _alive(ag):
        return {
            "attacker": aid,
            "alive": False,
            "score": 0.0,
            "max_fronts": 0,
            "opened": 0,
            "residual": 0,
            "can_launch": False,
            "force_scale": 0.0,
            "reason": "annexed_or_gone",
            "force": 0.0,
            "levy": 0.0,
            "grain": 0.0,
            "viability": 0.0,
            "targets": [],
        }
    force = float(military_strength(world, aid))
    levy = float(levy_extract(world, aid))
    grain = float(ag.grain)
    treasury = float(ag.treasury)
    via = float(ag.viability)
    intent = str(getattr(getattr(ag, "intention", None), "current", "") or "").strip().lower()
    opened_targets = front_targets_for(world, aid)
    # Withholding courts (Qi or any) sit out military offensives / joint fronts.
    if intent in ("withhold", "withholding"):
        return {
            "attacker": aid,
            "alive": True,
            "score": 0.0,
            "max_fronts": 0,
            "opened": len(opened_targets),
            "residual": 0,
            "can_launch": False,
            "force_scale": 0.0,
            "reason": "withholding",
            "intention": intent,
            "force": round(force, 3),
            "levy": round(levy, 3),
            "grain": round(grain, 1),
            "treasury": round(treasury, 1),
            "viability": round(via, 1),
            "targets": list(opened_targets),
        }
    score = (
        0.28 * (via / 100.0)
        + 0.22 * (grain / 100.0)
        + 0.14 * (treasury / 100.0)
        + 0.22 * min(1.0, force / 1.35)
        + 0.14 * levy
    )
    if score < 0.32 or via < 28 or grain < ATTACK_COST_GRAIN or treasury < ATTACK_COST_TREASURY:
        max_fronts = 0
    elif score < 0.48:
        max_fronts = 1
    elif score < 0.68:
        max_fronts = 2
    else:
        max_fronts = 3
    opened = len(opened_targets)
    residual = max(0, max_fronts - opened)
    # Stretching a second/third front weakens the spear
    if residual <= 0:
        force_scale = 0.0
        reason = "no_front_capacity"
        can_launch = False
    elif opened == 0:
        force_scale = 1.0
        reason = "ready"
        can_launch = True
    elif opened == 1:
        force_scale = 0.78 if score >= 0.55 else 0.62
        reason = "second_front_stretched"
        can_launch = True
    else:
        force_scale = 0.55 if score >= 0.70 else 0.42
        reason = "third_front_thin"
        can_launch = score >= 0.55
        if not can_launch:
            force_scale = 0.0
            reason = "too_thin_for_another_front"
    return {
        "attacker": aid,
        "alive": True,
        "score": round(score, 3),
        "max_fronts": max_fronts,
        "opened": opened,
        "residual": residual if can_launch else 0,
        "can_launch": can_launch and residual > 0,
        "force_scale": round(force_scale, 3),
        "reason": reason,
        "intention": intent,
        "force": round(force, 3),
        "levy": round(levy, 3),
        "grain": round(grain, 1),
        "viability": round(via, 1),
        "afford_attack": can_afford_attack(ag),
        "targets": list(opened_targets),
    }


def resolve_attack(
    world: "WorldState",
    attacker_id: str,
    defender_id: str,
    *,
    force_scale: float = 1.0,
) -> dict[str, Any]:
    """Mil/resources fight; loser −~30 viability; winner exhaustion + fear drop + spoils.

    force_scale < 1 weakens the attacker (stretched multi-front). Ally betrayal spike unchanged.
    """
    ensure_econ_fields(world)
    atk = world.agents[attacker_id]
    dfn = world.agents[defender_id]
    # Ally-on-ally strike → sharp betrayal spike (WS-54)
    try:
        _apply_ally_betrayal_spike(world, attacker_id, defender_id)
    except Exception:
        pass

    # Can't fight if broke
    if not can_afford_attack(atk):
        return {
            "attacker": attacker_id,
            "defender": defender_id,
            "cancelled": True,
            "reason": "broke",
            "force_scale": float(force_scale),
        }

    spend_attack(atk)
    if can_afford_defense(dfn):
        spend_defense(dfn)
        d_pow = military_strength(world, defender_id)
    else:
        # Broke defender fights at half strength
        d_pow = 0.5 * military_strength(world, defender_id)

    scale = max(0.25, min(1.25, float(force_scale or 1.0)))
    a_pow = military_strength(world, attacker_id) * scale
    bias = 0.04 if (world.tick + hash(attacker_id) + hash(defender_id)) % 2 == 0 else -0.04
    # Desperate attackers fight harder (theft urgency)
    if atk.desperate:
        a_pow *= 1.12
    atk_wins = (a_pow + bias) >= d_pow

    if atk_wins:
        winner, loser = atk, dfn
        wid, lid = attacker_id, defender_id
    else:
        winner, loser = dfn, atk
        wid, lid = defender_id, attacker_id

    loser.viability = max(0.0, float(loser.viability) - LOSS_VIABILITY_HIT)
    winner.viability = max(0.0, float(winner.viability) - WINNER_EXHAUSTION)
    spoils = steal_resources(winner, loser)
    # Territory strain: loser geographic_yield can drop
    loser.geographic_yield = max(0.15, float(loser.geographic_yield) - YIELD_LOSS_ON_DEFEAT)
    if winner.bloc == "anti_qin":
        winner.state.fear_of_qin = max(0.0, float(winner.state.fear_of_qin) - 0.06)

    set_trust(
        world.trust,
        attacker_id,
        defender_id,
        saturating_trust_hit(get_trust(world.trust, attacker_id, defender_id), WAR_TRUST_HIT),
    )
    set_trust(
        world.trust,
        defender_id,
        attacker_id,
        saturating_trust_hit(get_trust(world.trust, defender_id, attacker_id), WAR_TRUST_HIT),
    )
    # Both sides resent the clash
    atk.state.resentment = min(1.0, float(atk.state.resentment) + WAR_RESENTMENT_HIT)
    dfn.state.resentment = min(1.0, float(dfn.state.resentment) + WAR_RESENTMENT_HIT * 1.15)
    world.meso.cohesion = max(0.0, float(world.meso.cohesion) - ATTACK_COHESION_TAX)

    annexed = False
    if float(loser.viability) <= 0.0:
        annexed = annex_state(world, lid, wid)

    return {
        "attacker": attacker_id,
        "defender": defender_id,
        "winner": wid,
        "loser": lid,
        "atk_pow": round(a_pow, 3),
        "dfn_pow": round(d_pow, 3),
        "loser_viability": round(float(loser.viability), 1),
        "winner_viability": round(float(winner.viability), 1),
        "spoils": spoils,
        "annexed": annexed,
        "cancelled": False,
        "desperate": bool(atk.desperate),
        "force_scale": round(scale, 3),
        "attackers": [attacker_id],
        "contributions": {attacker_id: 1.0},
    }


def resolve_joint_attack(
    world: "WorldState",
    attacker_ids: list[str],
    defender_id: str,
    *,
    force_scales: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Joint/alliance offensive: shared force; attrition split by contribution.

    - Combined attacker power = Σ mil(i)×scale(i)
    - Campaign grain/treasury cost shared across all attackers ∝ contribution
    - Casualty/viability attrition on the attacker side split ∝ contribution
    - Defender still takes the **full** LOSS_VIABILITY_HIT / defense spend / yield hit
    - Ally betrayal spikes if any anti-Qin participant strikes an anti-Qin peer
    """
    ensure_econ_fields(world)
    force_scales = dict(force_scales or {})
    # Dedup preserve order; drop empty/defender
    seen: set[str] = set()
    aids: list[str] = []
    for raw in attacker_ids:
        aid = str(raw or "").strip().lower()
        if not aid or aid == defender_id or aid in seen:
            continue
        if aid not in world.agents or not _alive(world.agents[aid]):
            continue
        seen.add(aid)
        aids.append(aid)
    if not aids or defender_id not in world.agents or not _alive(world.agents[defender_id]):
        return {
            "attacker": (aids[0] if aids else ""),
            "attackers": aids,
            "defender": defender_id,
            "cancelled": True,
            "reason": "no_valid_side",
        }

    dfn = world.agents[defender_id]
    # Betrayal: each anti-Qin participant vs anti-Qin target
    betrayal_members: list[str] = []
    for aid in aids:
        atk = world.agents[aid]
        if getattr(atk, "bloc", "") == "anti_qin" and getattr(dfn, "bloc", "") == "anti_qin":
            try:
                _apply_ally_betrayal_spike(world, aid, defender_id)
                betrayal_members.append(aid)
            except Exception:
                pass

    # Contribution weights from fielded force × scale
    weights: dict[str, float] = {}
    for aid in aids:
        sc = max(0.25, min(1.25, float(force_scales.get(aid, 1.0) or 1.0)))
        mil = military_strength(world, aid) * sc
        if world.agents[aid].desperate:
            mil *= 1.12
        weights[aid] = max(0.05, mil)
    total_w = sum(weights.values()) or 1.0
    shares = {aid: weights[aid] / total_w for aid in aids}

    # Shared campaign cost (one attack purse) — proportional; never zero a court alone
    for aid in aids:
        ag = world.agents[aid]
        g_cost = ATTACK_COST_GRAIN * shares[aid]
        t_cost = ATTACK_COST_TREASURY * shares[aid]
        if float(ag.grain) < g_cost * 0.5 or float(ag.treasury) < t_cost * 0.5:
            return {
                "attacker": aids[0],
                "attackers": aids,
                "defender": defender_id,
                "cancelled": True,
                "reason": f"broke:{aid}",
                "contributions": {k: round(v, 3) for k, v in shares.items()},
            }
    for aid in aids:
        ag = world.agents[aid]
        ag.grain = max(0.0, float(ag.grain) - ATTACK_COST_GRAIN * shares[aid])
        ag.treasury = max(0.0, float(ag.treasury) - ATTACK_COST_TREASURY * shares[aid])

    if can_afford_defense(dfn):
        spend_defense(dfn)
        d_pow = military_strength(world, defender_id)
    else:
        d_pow = 0.5 * military_strength(world, defender_id)

    a_pow = sum(weights.values())
    bias = 0.04 if (world.tick + sum(hash(a) for a in aids) + hash(defender_id)) % 2 == 0 else -0.04
    atk_wins = (a_pow + bias) >= d_pow
    lead = aids[0]

    if atk_wins:
        # Target takes FULL viability hit; attackers share winner exhaustion ∝ contribution
        dfn.viability = max(0.0, float(dfn.viability) - LOSS_VIABILITY_HIT)
        for aid in aids:
            ag = world.agents[aid]
            ag.viability = max(0.0, float(ag.viability) - WINNER_EXHAUSTION * shares[aid])
        # Spoils: lead takes steal, then redistribute grain/treasury slice to allies ∝ share
        spoils = steal_resources(world.agents[lead], dfn)
        if len(aids) > 1 and spoils:
            for aid in aids[1:]:
                g_share = float(spoils.get("grain") or 0) * shares[aid]
                t_share = float(spoils.get("treasury") or 0) * shares[aid]
                world.agents[lead].grain = max(0.0, float(world.agents[lead].grain) - g_share)
                world.agents[lead].treasury = max(0.0, float(world.agents[lead].treasury) - t_share)
                world.agents[aid].grain = min(100.0, float(world.agents[aid].grain) + g_share)
                world.agents[aid].treasury = min(100.0, float(world.agents[aid].treasury) + t_share)
        dfn.geographic_yield = max(0.15, float(dfn.geographic_yield) - YIELD_LOSS_ON_DEFEAT)
        for aid in aids:
            if world.agents[aid].bloc == "anti_qin":
                world.agents[aid].state.fear_of_qin = max(
                    0.0, float(world.agents[aid].state.fear_of_qin) - 0.06 * shares[aid]
                )
        wid, lid = lead, defender_id
    else:
        # Attackers lose: FULL hit still on... user said target takes full hit always for defense?
        # "Target still takes full hit" → defender casualty is full when they lose;
        # when defenders win, attackers split LOSS_VIABILITY_HIT ∝ contribution; target takes WINNER_EXHAUSTION only once
        for aid in aids:
            ag = world.agents[aid]
            ag.viability = max(0.0, float(ag.viability) - LOSS_VIABILITY_HIT * shares[aid])
            ag.geographic_yield = max(
                0.15, float(ag.geographic_yield) - YIELD_LOSS_ON_DEFEAT * shares[aid]
            )
        dfn.viability = max(0.0, float(dfn.viability) - WINNER_EXHAUSTION)
        # Target (winner) steals from lead; proportional drain already applied via shares on attackers
        spoils = steal_resources(dfn, world.agents[lead])
        # Also skim proportional leftovers from allies so lead is not the only purse
        for aid in aids[1:]:
            g_take = SPOILS_FRACTION * float(world.agents[aid].grain) * shares[aid]
            t_take = SPOILS_FRACTION * float(world.agents[aid].treasury) * shares[aid]
            world.agents[aid].grain = max(0.0, float(world.agents[aid].grain) - g_take)
            world.agents[aid].treasury = max(0.0, float(world.agents[aid].treasury) - t_take)
            dfn.grain = min(100.0, float(dfn.grain) + g_take)
            dfn.treasury = min(100.0, float(dfn.treasury) + t_take)
            spoils["grain"] = round(float(spoils.get("grain") or 0) + g_take, 1)
            spoils["treasury"] = round(float(spoils.get("treasury") or 0) + t_take, 1)
        wid, lid = defender_id, lead

    # Trust/resentment: each attacker ↔ defender
    for aid in aids:
        set_trust(
            world.trust,
            aid,
            defender_id,
            saturating_trust_hit(get_trust(world.trust, aid, defender_id), WAR_TRUST_HIT),
        )
        set_trust(
            world.trust,
            defender_id,
            aid,
            saturating_trust_hit(get_trust(world.trust, defender_id, aid), WAR_TRUST_HIT),
        )
        world.agents[aid].state.resentment = min(
            1.0, float(world.agents[aid].state.resentment) + WAR_RESENTMENT_HIT * shares[aid]
        )
    dfn.state.resentment = min(1.0, float(dfn.state.resentment) + WAR_RESENTMENT_HIT * 1.15)
    world.meso.cohesion = max(
        0.0, float(world.meso.cohesion) - ATTACK_COHESION_TAX * (0.7 + 0.15 * len(aids))
    )

    annexed = False
    if float(world.agents[lid].viability) <= 0.0:
        annexed = annex_state(world, lid, wid)

    return {
        "attacker": lead,
        "attackers": aids,
        "defender": defender_id,
        "winner": wid,
        "loser": lid,
        "atk_pow": round(a_pow, 3),
        "dfn_pow": round(d_pow, 3),
        "loser_viability": round(float(world.agents[lid].viability), 1),
        "winner_viability": round(float(world.agents[wid].viability), 1),
        "spoils": spoils,
        "annexed": annexed,
        "cancelled": False,
        "desperate": any(bool(world.agents[a].desperate) for a in aids),
        "force_scale": round(sum(float(force_scales.get(a, 1.0) or 1.0) for a in aids) / len(aids), 3),
        "contributions": {k: round(v, 3) for k, v in shares.items()},
        "betrayal_members": betrayal_members,
        "joint": len(aids) > 1,
    }


def annex_state(world: "WorldState", victim_id: str, by_id: str) -> bool:
    victim = world.agents.get(victim_id)
    victor = world.agents.get(by_id)
    if not victim or victim.annexed:
        return False
    # Absorb remaining resources + a slice of yield
    if victor and not victor.annexed:
        steal_resources(victor, victim)
        victor.geographic_yield = min(
            1.0, float(victor.geographic_yield) + 0.5 * float(victim.geographic_yield)
        )
        victor.viability = min(100.0, float(victor.viability) + 8.0)
        if victor.bloc == "anti_qin":
            world.world.military_coalition = min(
                1.0, float(getattr(world.world, "military_coalition", 0.0)) + 0.03
            )
        elif victor.bloc == "qin":
            world.world.military_qin = min(
                1.0, float(getattr(world.world, "military_qin", 0.0)) + 0.04
            )
            world.qin_pressure = min(100.0, float(world.qin_pressure) + 3.0)
    victim.annexed = True
    victim.annexed_by = by_id
    victim.viability = 0.0
    victim.grain = 0.0
    victim.treasury = 0.0
    victim.intention.current = "withhold"
    victim.stance_mode = "annexed"
    victim.desperate = False

    # Tech absorb: victor known/adopted = max(own, victim) per DAG node; clear victim
    annexer_name = victor.name if victor else by_id
    if victor and not getattr(victor, "annexed", False):
        from .tech import absorb_tech_on_annex

        tech_sum = absorb_tech_on_annex(world, by_id, victim_id)
        up_k = tech_sum.get("nodes_known_up") or []
        up_a = tech_sum.get("nodes_adopted_up") or []
        n_up = len(set(up_k) | set(up_a))
        if n_up:
            detail = (
                f"{n_up} node(s) improved "
                f"(known↑{len(up_k)} adopted↑{len(up_a)}); "
                f"victor mil→{float(tech_sum.get('victor_mil') or 0):.2f}"
            )
        else:
            detail = (
                f"no node gains (already ahead); "
                f"victor mil→{float(tech_sum.get('victor_mil') or 0):.2f}"
            )
        tech_line = (
            f"Tech absorb: {annexer_name} seized {victim.name}'s workshops — "
            f"{detail}; victim board cleared"
        )
        world.append_log(
            tech_line,
            event_id="annex_tech",
            actor=by_id,
            action="tech_absorb",
            dials_fired=["m2", "adoption"],
        )
        _player_log(world, f"[t={world.tick}] {tech_line}")

    # Cohesion shock — annex rattles the living coalition
    world.meso.cohesion = max(0.0, float(world.meso.cohesion) - ANNEX_COHESION_HIT)

    # Amplified bystander resentment among living anti-Qin
    from .nonlinear import saturating_down

    bystander_names: list[str] = []
    for oid, other in world.agents.items():
        if oid in (victim_id, by_id):
            continue
        if other.bloc != "anti_qin" or getattr(other, "annexed", False):
            continue
        other.state.resentment = min(
            1.0, float(other.state.resentment) + ANNEX_BYSTANDER_RESENT
        )
        other.state.betrayal_memory = min(
            1.0, float(other.state.betrayal_memory) + ANNEX_BYSTANDER_BETRAYAL
        )
        cur = get_trust(world.trust, oid, by_id)
        set_trust(
            world.trust, oid, by_id, saturating_down(cur, ANNEX_BYSTANDER_TRUST_CHILL)
        )
        bystander_names.append(other.name)
    if bystander_names:
        line = (
            f"Bystander shock: {victim.name} annexed by {annexer_name} — "
            f"cohesion−{ANNEX_COHESION_HIT:.0f}; "
            f"{', '.join(bystander_names)} resentment↑ betrayal_memory↑; "
            f"trust chill toward annexer"
        )
        world.append_log(
            line,
            event_id="annex_bystander",
            actor=victim_id,
            action="bystander_resentment",
            dials_fired=["resentment", "betrayal_memory", "trust", "cohesion"],
        )
        _player_log(world, f"[t={world.tick}] {line}")
    try:
        from .chronicle import maybe_write_chronicle
        maybe_write_chronicle(world, reason="annex", force=True)
    except Exception:
        pass
    try:
        from .figure_memory import record_annex
        record_annex(world, victim_id, by_id)
    except Exception:
        pass
    return True


def apply_detect_trust_penalties(world: "WorldState", actions: dict[str, str]) -> None:
    from .nonlinear import saturating_down

    anti = [a.id for a in world.agents.values() if a.bloc == "anti_qin" and _alive(a)]
    for actor in anti:
        act = actions.get(actor, "cooperate")
        if act not in ("withhold", "defect"):
            continue
        extra = 0.10 if act == "defect" else 0.055
        for n in NEIGHBORS.get(actor, ()):
            if n not in world.agents or not _alive(world.agents[n]):
                continue
            if world.agents[n].bloc != "anti_qin":
                continue
            cur = get_trust(world.trust, n, actor)
            set_trust(world.trust, n, actor, saturating_down(cur, extra))


def tick_resource_income(world: "WorldState") -> None:
    """Quarterly geographic_yield → grain/treasury (coherent with spend/theft).

    Form (PLACEHOLDER rates; vault yield priors):
      grain_in  = 2.2·Y + rice_bonus(Chu) − 0.008·P   (anti-Qin pressure tax)
      treas_in  = 2.0·Y + fa_bonus(Qin)   − 0.006·P
    Net early income ≈ +1.5–3.5 / quarter at Y∈[0.55,0.88], P≈20–50 —
    enough to fund ~1 attack every 2–3Q without draining into early collapse.

    Also: mild viability regen from yield/grain when not Desperate / not annexed.
    """
    ensure_econ_fields(world)
    p = float(world.qin_pressure)
    for ag in world.agents.values():
        if not _alive(ag):
            continue
        y = float(ag.geographic_yield)
        # Chu river/rice → grain; Qin Legalist efficiency → treasury
        grain_in = 2.2 * y + (0.9 if ag.id == "chu" else 0.0)
        treas_in = 2.0 * y + (1.0 if ag.id == "qin" else 0.0)
        if ag.bloc == "anti_qin":
            grain_in -= 0.008 * p
            treas_in -= 0.006 * p
        # Mild upkeep (courts always spend a little) — not a drain spiral
        grain_in -= 0.35
        treas_in -= 0.30
        ag.grain = max(0.0, min(100.0, float(ag.grain) + grain_in))
        ag.treasury = max(0.0, min(100.0, float(ag.treasury) + treas_in))
        # Mild viability regen when stable (not Desperate)
        if not getattr(ag, "desperate", False):
            g = float(ag.grain)
            regen = VIABILITY_REGEN_CAP * (0.45 * y + 0.008 * max(0.0, g - 40.0))
            regen = max(0.0, min(VIABILITY_REGEN_CAP, regen))
            if regen > 0:
                ag.viability = min(100.0, float(ag.viability) + regen)


def _player_log(world: "WorldState", line: str) -> None:
    if not hasattr(world, "player_log") or world.player_log is None:
        world.player_log = []
    world.player_log.append(line)
    if len(world.player_log) > 80:
        world.player_log = world.player_log[-80:]


def run_autonomous_conflicts(world: "WorldState") -> list[dict[str, Any]]:
    """After Qin pressure + decisions: Desperate/Optimizing/low-fear AI may Attack Neighbor."""
    ensure_econ_fields(world)
    tick_resource_income(world)
    desperados = update_desperation(world)
    update_optimizing_modes(world)

    for aid in desperados:
        ag = world.agents[aid]
        line = (
            f"Shadow: DESPERATION — {ag.name} (viability {ag.viability:.0f}, "
            f"resources {resource_pool(ag):.0f}) ignores Fear of Qin; "
            f"raiding neighbors for grain/treasury."
        )
        world.append_log(line, event_id="desperation", actor=aid, action="desperate")
        _player_log(world, f"[t={world.tick}] {line}")

    candidates: list[tuple[float, str]] = []
    for ag in world.agents.values():
        if not _alive(ag) or ag.bloc != "anti_qin":
            continue
        tgt = choose_attack_target(world, ag.id)
        if not tgt:
            continue
        # Priority: desperate > optimizing > low fear
        if ag.desperate:
            pri = 0.0
        elif ag.stance_mode == "optimizing":
            pri = 0.5
        else:
            pri = 1.0 + float(ag.state.fear_of_qin)
        candidates.append((pri, ag.id))

    candidates.sort()
    results: list[dict[str, Any]] = []
    used: set[str] = set()
    attack_cap = max_attacks_this_tick(world)
    for _, aid in candidates[:attack_cap]:
        if aid in used:
            continue
        tgt = choose_attack_target(world, aid)
        if not tgt or tgt in used:
            continue
        used.add(aid)
        used.add(tgt)
        res = resolve_attack(world, aid, tgt)
        if res.get("cancelled"):
            line = (
                f"Shadow: {world.agents[aid].name} wanted to attack "
                f"{world.agents[tgt].name} but treasury/grain too low — can't fight."
            )
            world.append_log(line, event_id="shadow_broke", actor=aid, action="broke")
            _player_log(world, f"[t={world.tick}] {line}")
            continue
        results.append(res)
        atk_name = world.agents[aid].name
        dfn_name = world.agents[tgt].name
        loser = world.agents[res["loser"]]
        spoils = res.get("spoils") or {}
        tag = "DESPERATE raid" if res.get("desperate") else "attacked"
        shadow = (
            f"Shadow: {atk_name} {tag} {dfn_name} — "
            f"{loser.name} viability {res['loser_viability']:.0f}"
            f" (spoils grain+{spoils.get('grain', 0)}, treasury+{spoils.get('treasury', 0)})"
            + (f" — ANNEXED by {world.agents[res['winner']].name}" if res["annexed"] else "")
        )
        world.append_log(
            shadow,
            event_id="shadow_attack",
            actor=aid,
            action="attack_neighbor",
            dials_fired=["viability", "resources", "fear_of_qin", "cohesion"],
        )
        _player_log(world, f"[t={world.tick}] {shadow}")
        if res["annexed"]:
            ann = (
                f"Shadow: {loser.name} annexed — territory absorbed by "
                f"{world.agents[res['winner']].name}; no further acts."
            )
            world.append_log(ann, event_id="annexation", actor=res["loser"], action="annexed")
            _player_log(world, f"[t={world.tick}] {ann}")
    return results


def civil_war_check(world: "WorldState", target_id: str, *, risk: float = 0.12) -> str | None:
    """Mediation friction risk → mild cool-off (not a despair spiral).

    Floors grain/treasury/viability above DESPERATION_PCT so repeated Broker
    Mediation cannot raid a court into Desperate stance.
    """
    ensure_econ_fields(world)
    ag = world.agents.get(target_id)
    if not _alive(ag):
        return None
    p = min(0.35, risk + 0.12 * float(ag.state.resentment) + 0.08 * float(ag.state.status_threat))
    roll = ((world.tick * 17 + sum(ord(c) for c in target_id) * 13) % 100) / 100.0
    if roll > p:
        return None
    # Mild hit only — never push through desperation floor
    floor = DESPERATION_PCT + 2.0
    hit = min(8.0, 4.0 + 4.0 * float(ag.state.resentment))
    ag.viability = max(floor, float(ag.viability) - hit)
    ag.grain = max(floor, float(ag.grain) - 4.0)
    ag.treasury = max(floor, float(ag.treasury) - 4.0)
    ag.state.resentment = min(1.0, float(ag.state.resentment) + 0.06)
    # Explicitly clear desperation if resources stayed above the floor
    if resource_pool(ag) >= DESPERATION_PCT and float(ag.viability) >= DESPERATION_PCT:
        ag.desperate = False
        if ag.stance_mode == "desperate":
            ag.stance_mode = "coalition"
    note = (
        f"Shadow: Mediation friction in {ag.name} — cool-off "
        f"(viability → {ag.viability:.0f}; no despair spiral)"
    )
    world.append_log(note, event_id="mediation_friction", actor=target_id, action="cool_off")
    _player_log(world, f"[t={world.tick}] {note}")
    return note
