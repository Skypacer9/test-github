"""M4 Geographic constraints — table scalars derived from vault GIS/physics priors.

Not a GIS twin / pathfinding / DEM. Coefficients come from:
  - concrete seed WGS84 + haversine capital axis (docs/ws-archaeology-gis-sources.md §3)
  - Zhengguo canal grade ~0.6‰ → silt_irrigation_index (archaeology-casting §3.1)
  - ordinal ranks → soft scalars via engine/gis_priors.py (documented map)
  - fiscal extractability ranks stay in demographics / economic-grounding-sources.md

Sources:
  docs/ws-archaeology-gis-sources.md
  docs/archaeology-casting-infra-morphospaces.md §2–3
  docs/economic-grounding-sources.md (extraction vs geo levy split)
  docs/engine-architecture-summary.md §2 M4
  docs/grafted-persona-world-engine-blueprint.md §2.4
  docs/mechanisms-master.md (M4/M1 math)
  sim/data/gis_physics_priors.json
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .gis_priors import inventory_summary, load_priors, node_scalars, silt_irrigation_index


@dataclass
class GeoNode:
    id: str
    label: str
    kind: str  # pass | corridor | riverine | plain | levy_basin
    defense_mod: float = 0.5
    march_cost: float = 0.5
    extraction_mod: float = 0.5
    levy_mod: float = 0.5
    qin_pressure_mod: float = 0.0  # additive slope bias when relevant
    notes: str = ""
    sources: list[str] = field(default_factory=list)


def _build_m4_table() -> dict[str, GeoNode]:
    """Derive M4 node scalars from gis_physics_priors.json (ordinal→scalar + physics)."""
    priors = load_priors()
    silt = silt_irrigation_index(priors)
    inv = inventory_summary()
    dist_km = inv.get("ying_xianyang_km")

    meta = {
        "hangu_pass": (
            "Hangu Pass (函谷)",
            "pass",
            "Qin eastern chokepoint: defense/march from ordinal rank 5; "
            "no vault DEM elevation — not GPS-precise.",
            [
                "docs/grafted-persona-world-engine-blueprint.md (Qin passes Hangu/Wu)",
                "sim/data/gis_physics_priors.json#ordinal_ranks.nodes.hangu_pass",
            ],
        ),
        "wu_pass": (
            "Wu Pass (武关)",
            "pass",
            "Southern Qin approach; secondary projection corridor (ordinal).",
            [
                "docs/grafted-persona-world-engine-blueprint.md",
                "sim/data/gis_physics_priors.json#ordinal_ranks.nodes.wu_pass",
            ],
        ),
        "central_plain_corridor": (
            "Central plain corridor (Han/Wei buffer)",
            "corridor",
            f"Low terrain friction; march blended with Ying–Xianyang haversine "
            f"{dist_km} km / 800 km theater (seed coords only).",
            [
                "docs/ws-archaeology-gis-sources.md §3 (Ying/Xianyang WGS84)",
                "sim/data/gis_physics_priors.json#derived_distances_km",
            ],
        ),
        "chu_riverine": (
            "Chu rivers / wetlands",
            "riverine",
            "Riverine defense & Qin southward march friction; Ying seed ~16 km² "
            "areal-depth nudge — aristocratic fiscal levy is economic doc, not M4.",
            [
                "docs/ws-archaeology-gis-sources.md §3 (纪南 ~16 km²)",
                "docs/archaeology-casting-infra-morphospaces.md §3",
                "docs/economic-grounding-sources.md (Chu patronage extractability)",
            ],
        ),
        "qi_peninsula": (
            "Qi peninsula / eastern closure",
            "plain",
            "Geographic closure + basin yield ordinal; mint/foundry intensity → M2/econ.",
            [
                "docs/belief-logics-ontologies.md (Qi border closure)",
                "docs/archaeology-casting-infra-morphospaces.md §2.1 (临淄 metal sites)",
            ],
        ),
        "guanzhong_levy": (
            "Guanzhong levy basin (Qin)",
            "levy_basin",
            f"Hydraulic/geographic yield; Zhengguo grade 0.6‰ → silt_index={silt} "
            f"(famine buffer in M1). Fiscal registration intensity → demographics.",
            [
                "docs/archaeology-casting-infra-morphospaces.md §3 (郑国渠/都江堰)",
                "docs/economic-grounding-sources.md (Qin 户籍 extractability)",
                "sim/data/gis_physics_priors.json#canal_physics",
            ],
        ),
    }

    table: dict[str, GeoNode] = {}
    for nid, (label, kind, notes, sources) in meta.items():
        sc = node_scalars(nid, priors)
        table[nid] = GeoNode(
            id=nid,
            label=label,
            kind=kind,
            defense_mod=sc["defense_mod"],
            march_cost=sc["march_cost"],
            extraction_mod=sc["extraction_mod"],
            levy_mod=sc["levy_mod"],
            qin_pressure_mod=sc["qin_pressure_mod"],
            notes=notes,
            sources=sources,
        )
    return table


# Built once at import — scalars are deterministic from the JSON priors file.
M4_TABLE: dict[str, GeoNode] = _build_m4_table()

# Which nodes weight which state for UI / levy rollup
STATE_GEO: dict[str, list[str]] = {
    "qin": ["hangu_pass", "wu_pass", "guanzhong_levy"],
    "chu": ["chu_riverine"],
    "qi": ["qi_peninsula"],
    "han": ["central_plain_corridor"],
    "wei": ["central_plain_corridor"],
    "zhao": ["central_plain_corridor"],
    "yan": ["qi_peninsula"],  # northern flank thin prior
}


@dataclass
class M4State:
    """Live rollup scalars written into WorldMods each tick."""

    defense_mod: float = 0.5
    march_cost: float = 0.5
    extraction_mod: float = 0.5
    levy_capacity: float = 0.6
    qin_projection: float = 0.4  # how hard geography lets Qin push
    active_nodes: list[str] = field(default_factory=list)
    silt_irrigation_index: float = 0.0
    capital_axis_km: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        inv = inventory_summary()
        return {
            "defense_mod": self.defense_mod,
            "march_cost": self.march_cost,
            "extraction_mod": self.extraction_mod,
            "levy_capacity": self.levy_capacity,
            "qin_projection": self.qin_projection,
            "active_nodes": list(self.active_nodes),
            "silt_irrigation_index": self.silt_irrigation_index,
            "capital_axis_km": self.capital_axis_km,
            "table": {
                nid: {
                    "label": n.label,
                    "kind": n.kind,
                    "defense_mod": n.defense_mod,
                    "march_cost": n.march_cost,
                    "levy_mod": n.levy_mod,
                    "qin_pressure_mod": n.qin_pressure_mod,
                    "notes": n.notes,
                }
                for nid, n in M4_TABLE.items()
            },
            "gis_inventory": {
                "ying_xianyang_km": inv.get("ying_xianyang_km"),
                "zhengguo_grade_permille": inv.get("zhengguo_grade_permille"),
                "silt_irrigation_index": inv.get("silt_irrigation_index"),
            },
            "honesty": (
                "M4 scalars from vault GIS/physics priors (ordinal→scalar + "
                "seed haversine / canal grade) — not GIS pathfinding / DEM / OOB."
            ),
        }


def rollup_m4() -> M4State:
    """Aggregate table into world scalars (Qin projection + Chu defense weighted).

    Weights unchanged in spirit from mechanisms-master; node *values* now come
    from gis_priors ordinal/physics maps rather than anonymous flavor floats.
    """
    hangu = M4_TABLE["hangu_pass"]
    corridor = M4_TABLE["central_plain_corridor"]
    chu_r = M4_TABLE["chu_riverine"]
    guan = M4_TABLE["guanzhong_levy"]
    qi = M4_TABLE["qi_peninsula"]
    inv = inventory_summary()

    defense = (
        0.35 * hangu.defense_mod
        + 0.25 * chu_r.defense_mod
        + 0.15 * qi.defense_mod
        + 0.15 * guan.defense_mod
        + 0.10 * corridor.defense_mod
    )
    march = (
        0.4 * hangu.march_cost
        + 0.25 * chu_r.march_cost
        + 0.2 * corridor.march_cost
        + 0.15 * qi.march_cost
    )
    # Geographic extraction ease (terrain) — fiscal machine intensity is demographics.
    extract = (
        0.45 * guan.extraction_mod
        + 0.25 * corridor.extraction_mod
        + 0.20 * qi.extraction_mod
        + 0.10 * chu_r.extraction_mod
    )
    # Geographic/hydraulic basin yield (GIS). Chu patronage fiscal haircut ≠ here.
    levy = 0.45 * guan.levy_mod + 0.25 * chu_r.levy_mod + 0.30 * qi.levy_mod
    # Qin projection: passes + corridor help; Chu riverine dampens (signed qpm).
    projection = max(
        0.0,
        min(
            1.0,
            0.32
            + 0.28 * hangu.qin_pressure_mod
            + 0.22 * corridor.qin_pressure_mod
            + 0.14 * guan.qin_pressure_mod
            + 0.14 * chu_r.qin_pressure_mod,
        ),
    )
    return M4State(
        defense_mod=round(defense, 3),
        march_cost=round(march, 3),
        extraction_mod=round(extract, 3),
        levy_capacity=round(levy, 3),
        qin_projection=round(projection, 3),
        active_nodes=list(M4_TABLE.keys()),
        silt_irrigation_index=float(inv.get("silt_irrigation_index") or 0.0),
        capital_axis_km=float(inv.get("ying_xianyang_km") or 0.0),
    )


def apply_m4_to_world(world: Any) -> M4State:
    """Write M4 rollup into WorldMods; return state for logging/UI."""
    m4 = rollup_m4()
    w = world.world
    w.defense_mod = m4.defense_mod
    w.march_cost = getattr(w, "march_cost", m4.march_cost)
    if hasattr(w, "march_cost"):
        w.march_cost = m4.march_cost
    else:
        setattr(w, "march_cost", m4.march_cost)
    if hasattr(w, "extraction_mod"):
        w.extraction_mod = m4.extraction_mod
    else:
        setattr(w, "extraction_mod", m4.extraction_mod)
    w.levy_capacity = m4.levy_capacity
    if hasattr(w, "qin_projection"):
        w.qin_projection = m4.qin_projection
    else:
        setattr(w, "qin_projection", m4.qin_projection)
    # Physics priors mirrored for UI / M1 silt buffer
    setattr(w, "silt_irrigation_index", m4.silt_irrigation_index)
    setattr(w, "capital_axis_km", m4.capital_axis_km)
    return m4


def apply_m1_env(world: Any) -> dict[str, float]:
    """Coarse M1 demography/env draws — famine cuts levy_capacity after M4 rollup.

    Deterministic from tick + thermo (no RNG). Guanzhong silt-irrigation index
    (Zhengguo ~0.6‰ → 0.6) buffers famine haircut slightly — embodied hydraulic
    practice, not a modern hydrology solve.

    Honesty: not full demography; disaster size is a scalar draw.
    """
    w = world.world
    tick = int(getattr(world, "tick", 0) or 0)
    thermo = float(getattr(w, "thermo_dial", 0.5))
    prev = float(getattr(w, "famine_shock", 0.0) or 0.0)
    shock = 0.0
    if tick > 0 and tick % 11 == 0:
        shock = 0.35 + 0.2 * thermo
    elif tick > 0 and tick % 5 == 0:
        shock = 0.12 + 0.1 * thermo
    famine = max(shock, prev * 0.55)
    base_levy = float(getattr(w, "levy_capacity", 0.6))
    # M4 sets base each tick; M1 applies famine haircut on top.
    # silt_buffer from canal grade prior (docs/archaeology-casting… §3.1).
    silt = float(
        getattr(w, "silt_irrigation_index", None) or silt_irrigation_index()
    )
    silt_buffer = 0.12 * silt  # max 0.12 when index=1; ~0.072 at Zhengguo 0.6
    haircut = max(0.35, 0.55 - silt_buffer)
    levy = max(0.15, base_levy * (1.0 - haircut * famine))
    w.famine_shock = round(famine, 4)
    w.levy_capacity = round(levy, 4)
    return {
        "famine_shock": float(w.famine_shock),
        "levy_capacity": float(w.levy_capacity),
        "levy_base_m4": round(base_levy, 4),
        "silt_irrigation_index": round(silt, 4),
        "famine_haircut": round(haircut, 4),
    }


def m4_pressure_delta(world: Any, thermo: float) -> float:
    """Geography-shaped Qin pressure increment with defense/march bottlenecks.

    Axis term uses vault haversine km/800 (GIS-fitted coeff). Defense dampening
    is Michaelis–Menten style diminishing return — strong passes help less than
    linearly (bottleneck), not a DEM solve.
    """
    from .nonlinear import michaelis_menten

    m4 = rollup_m4()
    # Base climb × projection; capital-axis length slightly raises projection
    # pressure once corridor is the relevant theater (not a road-cost solve).
    axis_u = min(1.0, float(m4.capital_axis_km) / 800.0) if m4.capital_axis_km else 0.68
    delta = (4.0 + 3.5 * m4.qin_projection + 0.4 * axis_u) * (0.7 + 0.6 * thermo)
    # Defense bottleneck: diminishing dampener as defense_mod rises
    defense_dampen = michaelis_menten(float(m4.defense_mod), vmax=0.22, km=0.55)
    delta *= 1.0 - defense_dampen
    # March cost raises projection friction slightly (corridor bottleneck gloss)
    march_drag = michaelis_menten(float(m4.march_cost), vmax=0.10, km=0.60)
    delta *= 1.0 - 0.5 * march_drag
    # Chu riverine defense dampens pressure felt as levy shock on southern front
    chu = world.agents.get("chu")
    if chu and chu.intention.current == "cooperate":
        delta *= 1.0 - 0.08 * M4_TABLE["chu_riverine"].defense_mod
    # M1 famine: levy shortfall slightly raises pressure (extractive stress)
    famine = float(getattr(world.world, "famine_shock", 0.0) or 0.0)
    delta += 1.4 * famine
    return delta


def state_geo_card(state_id: str) -> list[dict[str, Any]]:
    out = []
    for nid in STATE_GEO.get(state_id, []):
        n = M4_TABLE[nid]
        out.append(
            {
                "id": n.id,
                "label": n.label,
                "kind": n.kind,
                "defense_mod": n.defense_mod,
                "march_cost": n.march_cost,
                "levy_mod": n.levy_mod,
            }
        )
    return out
