"""M2 Technological phylogeny — live DAG + Adoption Meter.

Unlock ≠ fieldable. Qin iron ≠ auto high-tech (cap metallurgy; boost logistics).
Feeds pressure, quorum, military strength/levy, and mechanism soft-lock —
not psychology-only.

Anchors: docs/tech-phylogeny-from-vault.md · docs/archaeology-casting-infra-morphospaces.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .world import WorldState


@dataclass(frozen=True)
class TechNode:
    id: str
    label: str
    kind: str  # metallurgy | weapons | logistics | siege | fiscal
    requires: tuple[str, ...] = ()
    military_w: float = 0.0
    logistics_w: float = 0.0
    levy_w: float = 0.0
    siege_w: float = 0.0
    notes: str = ""


# Coarse WS DAG — predecessor gates; honesty: Qin logistics ≠ metallurgy apex
TECH_DAG: dict[str, TechNode] = {
    "bronze_cast_base": TechNode(
        "bronze_cast_base",
        "Bronze casting workshops",
        "metallurgy",
        military_w=0.08,
        notes="Jin/Chu bronze craft baseline",
    ),
    "iron_bloom": TechNode(
        "iron_bloom",
        "Iron bloom / early iron",
        "metallurgy",
        requires=("bronze_cast_base",),
        military_w=0.06,
        levy_w=0.04,
        notes="Not Qin apex — Sanjin/Yan niches stronger",
    ),
    "cast_iron_ag_tools": TechNode(
        "cast_iron_ag_tools",
        "Cast-iron ag tools",
        "fiscal",
        requires=("iron_bloom",),
        levy_w=0.18,
        notes="Fiscal extractability proxy (hackathon iron caution)",
    ),
    "yan_iron_mould": TechNode(
        "yan_iron_mould",
        "Yan iron moulds (兴隆)",
        "metallurgy",
        requires=("iron_bloom",),
        military_w=0.1,
        notes="Mould metallurgy niche",
    ),
    "han_weapon_foundry": TechNode(
        "han_weapon_foundry",
        "Han weapon foundry",
        "weapons",
        requires=("iron_bloom",),
        military_w=0.22,
        notes="Han armorers niche (vault + archaeology partial)",
    ),
    "mass_crossbow_fittings": TechNode(
        "mass_crossbow_fittings",
        "Mass crossbow fittings",
        "weapons",
        requires=("han_weapon_foundry",),
        military_w=0.28,
        notes="Unlock ≠ fieldable — Adoption Meter friction",
    ),
    "canal_logistics": TechNode(
        "canal_logistics",
        "Canal / road logistics",
        "logistics",
        logistics_w=0.35,
        # levy_w raised from 0.12→0.15: Zhengguo ~0.6‰ grade / 都江堰 practice
        # (docs/archaeology-casting-infra-morphospaces.md §3.1; gis_physics_priors).
        levy_w=0.15,
        notes="Qin strength prior (郑国渠 0.6‰ silt-irrig / roads) — not metallurgy apex",
    ),
    "siege_engines": TechNode(
        "siege_engines",
        "Siege / pass assault kit",
        "siege",
        requires=("bronze_cast_base", "canal_logistics"),
        siege_w=0.3,
        military_w=0.12,
        notes="Pass projection — couples to M4 Hangu/Wu",
    ),
    "wrought_weapon_std": TechNode(
        "wrought_weapon_std",
        "Wrought weapon standard",
        "weapons",
        requires=("iron_bloom",),
        military_w=0.14,
        notes="Alternate recipe toward mass fittings",
    ),
}


# Per-state starting known (1.0 = known) and adoption (0–1 fieldable)
# Honesty: Qin logistics high, metallurgy capped; Han weapons niche; Chu bronze.
_START: dict[str, dict[str, tuple[float, float]]] = {
    # node_id -> (known, adopted)
    "qin": {
        "bronze_cast_base": (1.0, 0.85),
        "iron_bloom": (1.0, 0.45),  # known but not metallurgy lead
        "cast_iron_ag_tools": (1.0, 0.55),
        "canal_logistics": (1.0, 0.88),
        "siege_engines": (1.0, 0.62),
        "wrought_weapon_std": (0.7, 0.35),
        "han_weapon_foundry": (0.4, 0.05),
        "mass_crossbow_fittings": (0.3, 0.0),
        "yan_iron_mould": (0.35, 0.05),
    },
    "chu": {
        "bronze_cast_base": (1.0, 0.9),
        "iron_bloom": (0.7, 0.35),
        "cast_iron_ag_tools": (0.5, 0.25),
        "canal_logistics": (0.55, 0.3),
        "siege_engines": (0.4, 0.15),
        "wrought_weapon_std": (0.55, 0.3),
        "han_weapon_foundry": (0.35, 0.08),
        "mass_crossbow_fittings": (0.25, 0.0),
        "yan_iron_mould": (0.3, 0.05),
    },
    "qi": {
        "bronze_cast_base": (1.0, 0.8),
        "iron_bloom": (0.75, 0.4),
        "cast_iron_ag_tools": (0.7, 0.5),
        "canal_logistics": (0.6, 0.4),
        "siege_engines": (0.35, 0.12),
        "wrought_weapon_std": (0.6, 0.35),
        "han_weapon_foundry": (0.4, 0.1),
        "mass_crossbow_fittings": (0.3, 0.05),
        "yan_iron_mould": (0.35, 0.08),
    },
    "zhao": {
        "bronze_cast_base": (1.0, 0.85),
        "iron_bloom": (0.85, 0.55),
        "cast_iron_ag_tools": (0.65, 0.4),
        "canal_logistics": (0.5, 0.28),
        "siege_engines": (0.45, 0.2),
        "wrought_weapon_std": (0.7, 0.45),
        "han_weapon_foundry": (0.5, 0.15),
        "mass_crossbow_fittings": (0.35, 0.08),
        "yan_iron_mould": (0.45, 0.15),
    },
    "han": {
        "bronze_cast_base": (1.0, 0.85),
        "iron_bloom": (1.0, 0.7),
        "cast_iron_ag_tools": (0.75, 0.5),
        "canal_logistics": (0.45, 0.25),
        "siege_engines": (0.4, 0.18),
        "wrought_weapon_std": (0.8, 0.55),
        "han_weapon_foundry": (1.0, 0.75),
        "mass_crossbow_fittings": (0.85, 0.45),
        "yan_iron_mould": (0.5, 0.2),
    },
    "wei": {
        "bronze_cast_base": (1.0, 0.88),
        "iron_bloom": (0.9, 0.6),
        "cast_iron_ag_tools": (0.7, 0.45),
        "canal_logistics": (0.55, 0.32),
        "siege_engines": (0.5, 0.22),
        "wrought_weapon_std": (0.75, 0.5),
        "han_weapon_foundry": (0.55, 0.2),
        "mass_crossbow_fittings": (0.4, 0.1),
        "yan_iron_mould": (0.45, 0.15),
    },
    "yan": {
        "bronze_cast_base": (1.0, 0.8),
        "iron_bloom": (0.95, 0.65),
        "cast_iron_ag_tools": (0.6, 0.35),
        "canal_logistics": (0.4, 0.2),
        "siege_engines": (0.35, 0.12),
        "wrought_weapon_std": (0.7, 0.45),
        "han_weapon_foundry": (0.45, 0.12),
        "mass_crossbow_fittings": (0.3, 0.05),
        "yan_iron_mould": (1.0, 0.8),
    },
}


@dataclass
class StateTech:
    """Per-state Adoption Meter board: known + adopted in [0,1]."""

    known: dict[str, float] = field(default_factory=dict)
    adopted: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"known": dict(self.known), "adopted": dict(self.adopted)}

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "StateTech":
        raw = raw or {}
        return cls(
            known={k: float(v) for k, v in (raw.get("known") or {}).items()},
            adopted={k: float(v) for k, v in (raw.get("adopted") or {}).items()},
        )


@dataclass
class TechBoard:
    """World-level M2 board."""

    states: dict[str, StateTech] = field(default_factory=dict)
    # Rolled scalars (live)
    military: dict[str, float] = field(default_factory=dict)
    logistics: dict[str, float] = field(default_factory=dict)
    levy_tech: dict[str, float] = field(default_factory=dict)
    siege: dict[str, float] = field(default_factory=dict)
    adoption_mean: dict[str, float] = field(default_factory=dict)
    qin_mil_advantage: float = 0.0
    coalition_mil: float = 0.0
    qin_mil: float = 0.0
    # From M4 Guanzhong canal grade prior (Zhengguo ~0.6‰ → index); feeds levy_amp.
    silt_irrigation_index: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "states": {k: v.to_dict() for k, v in self.states.items()},
            "military": dict(self.military),
            "logistics": dict(self.logistics),
            "levy_tech": dict(self.levy_tech),
            "siege": dict(self.siege),
            "adoption_mean": dict(self.adoption_mean),
            "qin_mil_advantage": self.qin_mil_advantage,
            "coalition_mil": self.coalition_mil,
            "qin_mil": self.qin_mil,
            "silt_irrigation_index": self.silt_irrigation_index,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "TechBoard":
        if not raw:
            return seed_tech_board()
        states = {
            sid: StateTech.from_dict(payload)
            for sid, payload in (raw.get("states") or {}).items()
        }
        board = cls(
            states=states or seed_tech_board().states,
            military={k: float(v) for k, v in (raw.get("military") or {}).items()},
            logistics={k: float(v) for k, v in (raw.get("logistics") or {}).items()},
            levy_tech={k: float(v) for k, v in (raw.get("levy_tech") or {}).items()},
            siege={k: float(v) for k, v in (raw.get("siege") or {}).items()},
            adoption_mean={k: float(v) for k, v in (raw.get("adoption_mean") or {}).items()},
            qin_mil_advantage=float(raw.get("qin_mil_advantage") or 0.0),
            coalition_mil=float(raw.get("coalition_mil") or 0.0),
            qin_mil=float(raw.get("qin_mil") or 0.0),
            silt_irrigation_index=float(raw.get("silt_irrigation_index") or 0.0),
        )
        return board


def seed_tech_board() -> TechBoard:
    states: dict[str, StateTech] = {}
    for sid, nodes in _START.items():
        known = {nid: kv[0] for nid, kv in nodes.items()}
        adopted = {nid: kv[1] for nid, kv in nodes.items()}
        states[sid] = StateTech(known=known, adopted=adopted)
    board = TechBoard(states=states)
    recompute_tech(board, levy_capacity=0.6)
    return board


def _prereqs_met(st: StateTech, node: TechNode, *, adopt_floor: float = 0.35) -> bool:
    for req in node.requires:
        if float(st.adopted.get(req, 0.0)) < adopt_floor and float(st.known.get(req, 0.0)) < 0.8:
            return False
    return True


def absorb_tech_on_annex(
    world: "WorldState",
    victor_id: str,
    victim_id: str,
) -> dict[str, Any]:
    """Victor takes max(known/adopted) per TECH_DAG node from victim; freeze victim board.

    Returns a small summary for Player Log / callers.
    """
    board: TechBoard = getattr(world, "tech", None) or seed_tech_board()
    world.tech = board
    if victor_id not in board.states:
        board.states[victor_id] = StateTech()
    if victim_id not in board.states:
        board.states[victim_id] = StateTech()
    victor = board.states[victor_id]
    victim = board.states[victim_id]
    gained_known: list[str] = []
    gained_adopt: list[str] = []
    for nid in TECH_DAG:
        vk = float(victor.known.get(nid, 0.0))
        va = float(victor.adopted.get(nid, 0.0))
        xk = float(victim.known.get(nid, 0.0))
        xa = float(victim.adopted.get(nid, 0.0))
        nk = max(vk, xk)
        na = max(va, xa)
        if nk > vk + 1e-9:
            gained_known.append(nid)
        if na > va + 1e-9:
            gained_adopt.append(nid)
        victor.known[nid] = min(1.0, nk)
        victor.adopted[nid] = min(1.0, na)
    # Freeze / clear victim board — no further fieldable tech or spill seed
    victim.known = {nid: 0.0 for nid in TECH_DAG}
    victim.adopted = {nid: 0.0 for nid in TECH_DAG}

    levy_cap = float(getattr(world.world, "levy_capacity", 0.6) or 0.6)
    board.silt_irrigation_index = float(
        getattr(world.world, "silt_irrigation_index", 0.0) or 0.0
    )
    recompute_tech(board, levy_capacity=levy_cap)
    # Mirror rolled scalars into WorldMods (same as tick_tech)
    world.world.siege_mod = round(board.siege.get("qin", 0.1), 4)
    world.world.military_qin = board.qin_mil
    world.world.military_coalition = board.coalition_mil
    world.world.qin_mil_advantage = board.qin_mil_advantage
    world.world.adoption_meter = round(
        sum(board.adoption_mean.values()) / max(1, len(board.adoption_mean)), 4
    )
    return {
        "victor": victor_id,
        "victim": victim_id,
        "nodes_known_up": gained_known,
        "nodes_adopted_up": gained_adopt,
        "victor_mil": float(board.military.get(victor_id, 0.0)),
        "victim_cleared": True,
    }


def recompute_tech(board: TechBoard, *, levy_capacity: float = 0.6) -> TechBoard:
    """Roll military / logistics / levy / siege from Adoption Meter × DAG weights."""
    mil: dict[str, float] = {}
    logi: dict[str, float] = {}
    levy: dict[str, float] = {}
    siege: dict[str, float] = {}
    adopt_mean: dict[str, float] = {}

    for sid, st in board.states.items():
        m = l = lv = sg = 0.0
        adopted_vals = []
        for nid, node in TECH_DAG.items():
            a = max(0.0, min(1.0, float(st.adopted.get(nid, 0.0))))
            k = max(0.0, min(1.0, float(st.known.get(nid, 0.0))))
            # Fieldable only if known + adopted; prereq soft-gate
            if k < 0.4 or not _prereqs_met(st, node):
                a_eff = a * 0.35
            else:
                a_eff = a
            adopted_vals.append(a_eff)
            m += a_eff * node.military_w
            l += a_eff * node.logistics_w
            lv += a_eff * node.levy_w
            sg += a_eff * node.siege_w
        # Levy capacity (M1/M4 GIS-informed) amplifies fiscal/military fielding.
        # Optional silt term: Guanzhong hydraulic prior (Zhengguo grade→index)
        # slightly raises amp when caller passes silt_irrigation_index via board attr
        # or world mirror — default 0 keeps prior equation shape.
        silt = float(getattr(board, "silt_irrigation_index", 0.0) or 0.0)
        # Saturating levy amp (Michaelis–Menten on capacity) + silt prior.
        # Coeffs: silt 0.06 from Zhengguo grade→index (GIS); km/vmax PLACEHOLDER shape.
        from .nonlinear import michaelis_menten

        levy_sat = michaelis_menten(float(levy_capacity), vmax=0.58, km=0.35)
        levy_amp = 0.68 + levy_sat + 0.06 * silt
        mil[sid] = round(min(1.0, m * levy_amp), 4)
        logi[sid] = round(min(1.0, l), 4)
        levy[sid] = round(min(1.0, lv * levy_amp), 4)
        siege[sid] = round(min(1.0, sg), 4)
        adopt_mean[sid] = round(
            sum(adopted_vals) / max(1, len(adopted_vals)), 4
        )

    board.military = mil
    board.logistics = logi
    board.levy_tech = levy
    board.siege = siege
    board.adoption_mean = adopt_mean
    board.qin_mil = mil.get("qin", 0.0)
    anti = [s for s in mil if s != "qin"]
    board.coalition_mil = (
        round(sum(mil[s] for s in anti) / max(1, len(anti)), 4) if anti else 0.0
    )
    board.qin_mil_advantage = round(board.qin_mil - board.coalition_mil, 4)
    return board


def _det_roll(tick: int, sid: str, nid: str, salt: int = 0) -> int:
    """Deterministic 0–99 roll (reproducible; no RNG import)."""
    h = 0
    for ch in f"{tick}:{sid}:{nid}:{salt}":
        h = (h * 131 + ord(ch)) % 10_007
    return h % 100


def _child_nodes(parent_id: str) -> list[str]:
    return [nid for nid, n in TECH_DAG.items() if parent_id in n.requires]


def tick_tech(world: "WorldState") -> dict[str, Any]:
    """Slow Adoption Meter drift + rare breakthrough; recompute strength."""
    board: TechBoard = getattr(world, "tech", None) or seed_tech_board()
    evo = float(getattr(world.world, "evo_dial", 0.4))
    tick_n = int(getattr(world, "tick", 0) or 0)
    breakthroughs: list[str] = []
    for sid, st in board.states.items():
        ag = world.agents.get(sid) if getattr(world, "agents", None) else None
        if ag is not None and getattr(ag, "annexed", False):
            continue  # frozen / cleared board — no creep or Eureka
        for nid, node in TECH_DAG.items():
            k = float(st.known.get(nid, 0.0))
            a = float(st.adopted.get(nid, 0.0))
            if k < 0.5:
                # Slow knowledge spill from neighbors with higher known
                spill = 0.0
                for other, ost in board.states.items():
                    if other == sid:
                        continue
                    spill = max(spill, float(ost.known.get(nid, 0.0)))
                if spill > k:
                    st.known[nid] = min(1.0, k + 0.015 * evo * (spill - k))
                continue
            if not _prereqs_met(st, node):
                continue
            # Adoption friction: logistic S-curve toward known (diminishing near 1).
            # Form: a ← a + friction·(k−a)·(1−a) — bottleneck / saturation.
            friction = 0.018 * evo
            if sid != "qin":
                friction *= 0.7 + 0.3 * (float(world.meso.cohesion) / 100.0)
            else:
                friction *= 0.9 + 0.2 * float(board.logistics.get("qin", 0.5))
            # Ideology: slight adoption bias + rare combo crumb (capped)
            if ag is not None:
                from .ideology import tech_adoption_bias, rare_combo_bonus
                friction *= 1.0 + tech_adoption_bias(ag)
                combo = rare_combo_bonus(ag, tick=tick_n, sid=sid)
                friction += float(combo.get("tech_adopt") or 0.0)
            gap = max(0.0, k - a)
            st.adopted[nid] = min(1.0, a + friction * gap * (1.0 - a))

            # Rare Eureka: mature node may spill known into a child (unlock ≠ fieldable).
            # Demo play-feel: ~10× rarer than prior ~4–7%/edge, and ≤1 breakthrough / state / tick.
            # Adoption creep above is unchanged. Ideology eases threshold slightly.
            if k >= 0.85 and a >= 0.4:
                state_hit = any(b.startswith(f"{sid}:") for b in breakthroughs)
                if state_hit:
                    continue
                eureka_ease = 0.0
                combo_eu = 0.0
                if ag is not None:
                    from .ideology import eureka_bias, rare_combo_bonus
                    eureka_ease = eureka_bias(ag)
                    combo_eu = float(rare_combo_bonus(ag, tick=tick_n, sid=sid).get("eureka") or 0.0)
                for child in _child_nodes(nid):
                    ck = float(st.known.get(child, 0.0))
                    if ck >= 0.95:
                        continue
                    # Was max(2, int(4+6*evo)) ≈ 6–10; now ≈ 1 (ceil/10)
                    threshold = max(1, int(round((4 + 6 * evo) / 10.0)))
                    # ideology/combo: tiny bump to roll space (still rare)
                    roll_boost = int(round(3 * eureka_ease + 4 * combo_eu))
                    if _det_roll(tick_n, sid, child, salt=7) < threshold + roll_boost:
                        st.known[child] = min(1.0, ck + 0.18 + 0.1 * evo + 0.5 * combo_eu)
                        breakthroughs.append(f"{sid}:{child}")
                        try:
                            from .figure_memory import remember_living, record_rare_combo
                            remember_living(
                                world,
                                kind="breakthrough",
                                text=f"Tech eureka: {sid} unlocks {child}",
                                salience=0.72,
                                homes={sid},
                            )
                            if ag is not None:
                                from .ideology import rare_combo_bonus
                                cb = rare_combo_bonus(ag, tick=tick_n, sid=sid)
                                if cb.get("combo"):
                                    record_rare_combo(world, sid, str(cb["combo"]))
                        except Exception:
                            pass
                        break  # one Eureka attempt success per state per tick

    levy_cap = float(getattr(world.world, "levy_capacity", 0.6))
    # Mirror M4/M1 silt prior into amp (gis_priors / geo.apply_m4_to_world).
    board.silt_irrigation_index = float(
        getattr(world.world, "silt_irrigation_index", 0.0) or 0.0
    )
    recompute_tech(board, levy_capacity=levy_cap)
    world.tech = board

    # Mirror into WorldMods for pressure / UI
    world.world.siege_mod = round(board.siege.get("qin", 0.1), 4)
    world.world.military_qin = board.qin_mil
    world.world.military_coalition = board.coalition_mil
    world.world.qin_mil_advantage = board.qin_mil_advantage
    world.world.adoption_meter = round(
        sum(board.adoption_mean.values()) / max(1, len(board.adoption_mean)), 4
    )
    return {
        "qin_mil": board.qin_mil,
        "coalition_mil": board.coalition_mil,
        "advantage": board.qin_mil_advantage,
        "adoption_mean": dict(board.adoption_mean),
        "levy_tech": dict(board.levy_tech),
        "breakthroughs": breakthroughs[:8],
    }


def tech_pressure_delta(world: "WorldState") -> float:
    """Qin logistics/siege/levy raise pressure; coalition military dampens.

    Qin force terms use mild saturating (MM) projection; coalition dampener
    soft-thresholds so weak coalitions barely help (bottleneck), strong ones
    bite harder — mid-fidelity, PLACEHOLDER coeffs on vault M2 mirrors.
    """
    from .nonlinear import michaelis_menten, soft_threshold

    board = getattr(world, "tech", None)
    if board is None:
        return 0.0
    qin_logi = float(board.logistics.get("qin", 0.4))
    qin_siege = float(board.siege.get("qin", 0.1))
    qin_levy = float(board.levy_tech.get("qin", 0.2))
    coal_mil = float(board.coalition_mil)
    qin_push = (
        1.2 * michaelis_menten(qin_logi, vmax=1.0, km=0.35)
        + 1.5 * michaelis_menten(qin_siege, vmax=1.0, km=0.30)
        + 0.7 * michaelis_menten(qin_levy, vmax=1.0, km=0.35)
        + 0.8 * float(board.qin_mil_advantage)
    )
    # Soft coalition dampener — weak coal barely registers
    coal_gate = soft_threshold(coal_mil, 0.18, k=10.0)
    coal_dampen = 1.8 * coal_mil * (0.35 + 0.65 * coal_gate)
    return round(qin_push - coal_dampen, 4)


def tech_quorum_ok(world: "WorldState", *, cohesion_ok: bool) -> tuple[bool, str]:
    """Military/levy floor for joint campaign — not psychology-only."""
    board = getattr(world, "tech", None)
    if board is None:
        return cohesion_ok, "no_tech_board"
    coal = float(board.coalition_mil)
    levy = float(board.levy_tech.get("chu", 0.2)) + float(board.levy_tech.get("qi", 0.2))
    levy *= 0.5
    mil_ok = coal >= 0.22
    levy_ok = levy >= 0.18 or float(getattr(world.world, "levy_capacity", 0.6)) >= 0.5
    adv = float(board.qin_mil_advantage)
    # If Qin military advantage extreme, quorum harder even with psychology OK
    if adv >= 0.28 and coal < 0.35:
        return False, f"qin_mil_advantage={adv:.2f} coalition_mil={coal:.2f}"
    if not mil_ok:
        return False, f"coalition_mil={coal:.2f}<0.22"
    if not levy_ok:
        return False, f"levy_tech_floor fail ({levy:.2f})"
    if not cohesion_ok:
        return False, "cohesion_psych_fail"
    return True, "tech+psych quorum"


def tech_structural_damage(world: "WorldState") -> tuple[bool, str]:
    """Material collapse signal for soft-lock (alongside dead edges / cohesion).

    Thresholds raised so mid-game rivalry does not equal instant lock.
    """
    board = getattr(world, "tech", None)
    if board is None:
        return False, ""
    if float(board.qin_mil_advantage) >= 0.48 and float(board.coalition_mil) <= 0.14:
        return True, (
            f"qin_mil_advantage={board.qin_mil_advantage:.2f} "
            f"coalition_mil={board.coalition_mil:.2f}"
        )
    if float(board.levy_tech.get("chu", 1.0)) < 0.05 and float(board.levy_tech.get("qi", 1.0)) < 0.05:
        return True, "anti-Qin levy_tech collapse"
    return False, ""


def adoption_meter_rows(world: "WorldState") -> list[dict[str, Any]]:
    """UI rows: featured nodes × Qin/Chu/Qi adoption."""
    board = getattr(world, "tech", None) or seed_tech_board()
    featured = [
        "canal_logistics",
        "siege_engines",
        "han_weapon_foundry",
        "mass_crossbow_fittings",
        "cast_iron_ag_tools",
        "yan_iron_mould",
    ]
    rows = []
    for nid in featured:
        node = TECH_DAG[nid]
        row: dict[str, Any] = {"id": nid, "label": node.label, "kind": node.kind}
        for sid in ("qin", "chu", "qi"):
            st = board.states.get(sid) or StateTech()
            row[f"{sid}_known"] = round(float(st.known.get(nid, 0.0)), 3)
            row[f"{sid}_adopted"] = round(float(st.adopted.get(nid, 0.0)), 3)
        rows.append(row)
    return rows


def field_tech_summary(world: "WorldState") -> dict[str, Any]:
    board = getattr(world, "tech", None) or seed_tech_board()
    return {
        "military": dict(board.military),
        "logistics": dict(board.logistics),
        "levy_tech": dict(board.levy_tech),
        "siege": dict(board.siege),
        "adoption_mean": dict(board.adoption_mean),
        "qin_mil": board.qin_mil,
        "coalition_mil": board.coalition_mil,
        "qin_mil_advantage": board.qin_mil_advantage,
        "adoption_meter": float(getattr(world.world, "adoption_meter", board.adoption_mean.get("qin", 0))),
        "rows": adoption_meter_rows(world),
    }
