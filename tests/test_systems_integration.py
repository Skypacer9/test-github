"""Systems integration: projection + CLI-visible stubs (no Gradio)."""

from __future__ import annotations

import sys
from pathlib import Path

_SIM = Path(__file__).resolve().parents[1]
_ROOT = _SIM.parent
for pth in (_ROOT, _SIM):
    if str(pth) not in sys.path:
        sys.path.insert(0, str(pth))


def test_demographics_seed_and_serialize():
    from engine.demographics import seed_demographics
    from engine.world import WorldState, new_world

    w = new_world()
    assert w.demographics.courts["qin"].available_manpower > 0
    assert 0.0 <= w.demographics.mean_satisfaction <= 1.0
    blob = w.to_dict()
    assert "demographics" in blob
    assert blob["demographics"]["placeholder"] is True
    w2 = WorldState.from_dict(blob)
    assert "chu" in w2.demographics.courts
    assert abs(
        w2.demographics.courts["qi"].satisfaction
        - w.demographics.courts["qi"].satisfaction
    ) < 1e-6
    # seed helper standalone — ordinal ranks from economic-grounding-sources.md §3
    board = seed_demographics()
    assert set(board.courts) >= {"qin", "chu", "qi"}
    qin, chu, qi = board.courts["qin"], board.courts["chu"], board.courts["qi"]
    assert chu.population > qin.population > qi.population
    assert qin.levy_base > qi.levy_base > chu.levy_base
    assert qi.urban_share > qin.urban_share > chu.urban_share
    assert qin.available_manpower > chu.available_manpower
    assert qin.available_manpower > qi.available_manpower
    assert qin.registration_intensity > chu.registration_intensity
    assert qi.monetization_index > qin.monetization_index
    assert qin.source_tier == "archaeological"
    assert chu.source_tier == "archaeological"
    assert qi.source_tier == "textual_ideal"
    # round-trip keeps meta
    assert blob["demographics"]["courts"]["qin"]["source_tier"] == "archaeological"
    assert "seed_grounding" in blob["demographics"]


def test_demographics_hooks_are_tiny():
    from engine.demographics import apply_placeholder_hooks, tick_demographics
    from engine.world import new_world

    w = new_world()
    before_levy = float(w.world.levy_capacity)
    before_coh = float(w.meso.cohesion)
    before_p = float(w.qin_pressure)
    tick_demographics(w)
    hooks = apply_placeholder_hooks(w)
    # Placeholder nudges must stay small
    assert abs(hooks["levy_nudge"]) < 0.05
    assert abs(hooks["cohesion_nudge"]) < 2.0
    assert abs(hooks["pressure_nudge"]) < 1.0
    assert abs(hooks["mil_qin_nudge"]) < 0.05
    assert abs(float(w.world.levy_capacity) - before_levy) < 0.05
    assert abs(float(w.meso.cohesion) - before_coh) < 2.0
    assert abs(float(w.qin_pressure) - before_p) < 1.0


def test_backend_projects_integration_fields():
    from backend import _project, advance_quarter, initial_state

    s0 = initial_state()
    for key in (
        "demographics",
        "court_economy",
        "satisfaction",
        "available_manpower",
        "tech_coupling",
        "chu_sync_meso_bonus",
        "contagion_recent",
        "dials",
        "pathway_reading",
        "m4",
    ):
        assert key in s0, f"missing projection key {key}"
    assert s0["demographics"]["placeholder"] is True
    assert s0["court_economy"]["placeholder"] is True
    qin_eco = s0["court_economy"]["courts"]["qin"]
    han_eco = s0["court_economy"]["courts"]["han"]
    assert "production_power" in qin_eco
    assert "manpower_regen_rate" in qin_eco
    assert "manpower_delta_q" in qin_eco
    # Larger extractive court should out-produce a thin corridor state
    assert qin_eco["production_power"] > han_eco["production_power"]
    assert "nodes" in s0["m4"]
    assert "by_state" in s0["m4"]
    assert "tech_pressure_delta" in s0["tech_coupling"]
    assert "thermo_dial" in s0["dials"]

    s1, msgs = advance_quarter(s0)
    assert s1["tick"] == 1
    assert "satisfaction" in s1
    assert "available_manpower" in s1
    # Projection stays without needing Gradio
    ui = _project.__wrapped__ if hasattr(_project, "__wrapped__") else None
    _ = ui
    assert isinstance(msgs, list)


def test_tick_logs_demo_placeholder_and_contagion_path():
    from engine.tick import tick
    from engine.world import new_world

    w = new_world()
    tick(w)
    summary = [e for e in w.episode if e.get("event_id") == "summary"]
    assert summary
    text = summary[-1].get("text") or ""
    assert "demo_sat=" in text
    assert "manpower=" in text
    assert "placeholder" in text


def test_cli_demo_and_contagion_commands():
    from cli import dispatch
    from backend import fresh_run

    state = fresh_run()
    state = dispatch(state, "demo")
    assert state is not None
    state = dispatch(state, "sat qin")
    assert state is not None
    state = dispatch(state, "manpower")
    assert state is not None
    state = dispatch(state, "advance")
    state = dispatch(state, "m4")
    state = dispatch(state, "m2")
    state = dispatch(state, "chu")
    state = dispatch(state, "contagion")
    state = dispatch(state, "dials")
    state = dispatch(state, "field")
    assert state["demographics"]["courts"]["qin"]["available_manpower"] >= 0


def test_geo_depth_and_tech_coupling_in_projection():
    from backend import initial_state
    from engine.geo import M4_TABLE, STATE_GEO

    s = initial_state()
    assert set(s["m4"]["nodes"]) == set(M4_TABLE)
    assert "qin" in s["m4"]["by_state"]
    assert STATE_GEO["chu"]
    tc = s["tech_coupling"]
    assert isinstance(tc["tech_quorum_ok"], bool)
    assert "tech_quorum_why" in tc


def test_chu_sync_meso_bonus_projected():
    from backend import _project
    from engine.patron_client import seed_chu_patron_client, sync_bonus
    from engine.world import new_world

    w = new_world()
    w.chu_court = seed_chu_patron_client()
    bonus = sync_bonus(w.chu_court)
    ui = _project(w)
    assert "chu_sync_meso_bonus" in ui
    assert ui["chu_sync_meso_bonus"]["bonded"] == bonus["bonded"]
    assert "cohesion" in ui["chu_sync_meso_bonus"]


def test_figure_profiles_still_complete():
    from engine.dossiers import FIGURE_DOSSIERS, dossier_for_figure
    from engine.figures import figure_ids, figure_profile
    from engine.world import new_world

    w = new_world()
    assert set(figure_ids()) == set(FIGURE_DOSSIERS)
    for fid in figure_ids():
        prof = figure_profile(w, fid)
        assert prof.get("dossier")
        assert dossier_for_figure(fid)
        assert "base_schools" in prof
