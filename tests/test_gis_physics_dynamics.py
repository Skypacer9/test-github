"""GIS/physics priors → M4/M1/M2 dynamics — intentional, stable, sourced."""

from __future__ import annotations

import sys
from pathlib import Path

_SIM = Path(__file__).resolve().parents[1]
_ROOT = _SIM.parent
for pth in (_ROOT, _SIM):
    if str(pth) not in sys.path:
        sys.path.insert(0, str(pth))


def test_priors_inventory_has_concrete_numbers():
    from engine.gis_priors import capital_axis_distance_unit, inventory_summary, silt_irrigation_index

    inv = inventory_summary()
    assert inv["ying_xianyang_km"] == 544.7
    assert inv["zhengguo_grade_permille"] == 0.6
    assert silt_irrigation_index() == 0.6
    assert 0.65 <= capital_axis_distance_unit() <= 0.72
    assert "hangu_pass" in inv["ordinal_nodes"]


def test_ordinal_to_scalar_map_documented():
    from engine.gis_priors import node_scalars, ordinal_unit, soft_scalar

    assert ordinal_unit(1) == 0.0
    assert ordinal_unit(5) == 1.0
    assert soft_scalar(1.0, floor=0.25, span=0.65) == 0.9
    hangu = node_scalars("hangu_pass")
    assert hangu["defense_mod"] == 0.9
    assert hangu["march_cost"] == 0.9
    # Chu qpm is dampening (rank 1 → negative floor)
    chu = node_scalars("chu_riverine")
    assert chu["qin_pressure_mod"] < 0


def test_m4_table_matches_priors_not_anonymous():
    from engine.geo import M4_TABLE, rollup_m4
    from engine.gis_priors import node_scalars

    for nid, node in M4_TABLE.items():
        sc = node_scalars(nid)
        assert node.defense_mod == sc["defense_mod"]
        assert node.march_cost == sc["march_cost"]
        assert node.levy_mod == sc["levy_mod"]
        assert "gis_physics_priors" in " ".join(node.sources) or any(
            "archaeology" in s or "ws-archaeology" in s or "economic" in s for s in node.sources
        )

    m4 = rollup_m4()
    # Intentional GIS-informed band (Guanzhong silt raises levy vs old ~0.72 flavor)
    assert 0.74 <= m4.levy_capacity <= 0.85
    assert 0.65 <= m4.defense_mod <= 0.80
    assert 0.50 <= m4.qin_projection <= 0.70
    assert m4.silt_irrigation_index == 0.6
    assert m4.capital_axis_km == 544.7


def test_m1_silt_buffer_reduces_famine_haircut():
    from engine.geo import apply_m1_env, apply_m4_to_world
    from engine.world import new_world

    w = new_world()
    apply_m4_to_world(w)
    base = float(w.world.levy_capacity)
    w.tick = 11
    m1 = apply_m1_env(w)
    assert m1["silt_irrigation_index"] == 0.6
    # haircut = 0.55 - 0.12*0.6 = 0.478 (not raw 0.55)
    assert abs(m1["famine_haircut"] - 0.478) < 1e-6
    assert m1["famine_shock"] > 0.2
    assert m1["levy_capacity"] < base
    # With silt buffer, post-famine levy stays above the no-buffer counterfactual
    no_buffer = base * (1.0 - 0.55 * m1["famine_shock"])
    assert m1["levy_capacity"] > no_buffer


def test_m2_levy_amp_uses_silt_prior():
    from engine.tech import recompute_tech, seed_tech_board

    board = seed_tech_board()
    recompute_tech(board, levy_capacity=0.7)
    base_qin = board.military["qin"]
    board.silt_irrigation_index = 0.6
    recompute_tech(board, levy_capacity=0.7)
    assert board.military["qin"] >= base_qin
    # canal_logistics levy_w bumped for Zhengguo prior
    from engine.tech import TECH_DAG

    assert TECH_DAG["canal_logistics"].levy_w == 0.15


def test_dynamics_stable_across_ticks():
    from engine.tick import tick
    from engine.world import new_world

    w = new_world()
    levies = []
    projections = []
    for _ in range(12):
        tick(w)
        levies.append(float(w.world.levy_capacity))
        projections.append(float(getattr(w.world, "qin_projection", 0.0)))
    # Projection (pre-famine geography) stable; levy dips on famine ticks then recovers
    assert all(0.45 <= p <= 0.75 for p in projections)
    assert min(levies) < max(levies)
    assert w.qin_pressure > 0
    assert float(getattr(w.world, "silt_irrigation_index", 0)) == 0.6
