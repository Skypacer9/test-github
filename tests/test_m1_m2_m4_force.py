"""Focused M1/M2/M4 force tests — pressure, locks, Adoption Meter projection."""

from __future__ import annotations

import sys
from pathlib import Path

_SIM = Path(__file__).resolve().parents[1]
_ROOT = _SIM.parent
for pth in (_ROOT, _SIM):
    if str(pth) not in sys.path:
        sys.path.insert(0, str(pth))


def test_tick_wires_m1_before_m2():
    from engine.tick import tick
    from engine.world import new_world

    w = new_world()
    for _ in range(5):
        tick(w)
    assert w.tick == 5
    assert w.world.famine_shock > 0.0
    assert any("M1 famine" in (e.get("text") or "") for e in w.episode)
    assert w.world.military_qin > 0
    assert w.world.adoption_meter > 0


def test_adoption_meter_in_field_projection():
    """Backend projection carries M1/M2 meters (Gradio HTML path is parked)."""
    from backend import _project, advance_quarter, initial_state
    from engine.world import WorldState

    s0 = initial_state()
    assert "adoption_meter" in s0
    assert "m2" in s0 and "m1" in s0
    assert "famine_shock" in s0["m1"]

    s1, _ = advance_quarter(s0)
    w = WorldState.from_dict(s1["_engine"])
    ui = _project(w)
    assert ui["adoption_meter"] >= 0
    assert ui["m2"]["rows"]
    assert "famine_shock" in ui["m1"]
    assert "demographics" in ui
    assert "satisfaction" in ui
    assert "available_manpower" in ui


def test_levy_collapse_structural_lock():
    from engine.demo_flow import MIN_LOCK_TICK, mechanism_lock, soft_lock_if_needed
    from engine.world import new_world

    w = new_world()
    w.meso.pathway_soft = "qin_path"
    w.tick = MIN_LOCK_TICK  # after grace
    # Severe levy collapse (threshold now < 0.05 each)
    w.tech.levy_tech["chu"] = 0.04
    w.tech.levy_tech["qi"] = 0.04
    w.tech.qin_mil_advantage = 0.1
    w.tech.coalition_mil = 0.4
    mech, reason = mechanism_lock(w)
    assert mech == "qin_path_damage"
    assert "levy_tech" in reason
    soft_lock_if_needed(w)
    assert w.run_ended and w.end_screen["lock_kind"] == "mechanism"
