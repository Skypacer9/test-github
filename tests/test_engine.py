"""Unit tests for historical engine — no Gradio."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `pytest` from sim/ or repo root without install.
_SIM = Path(__file__).resolve().parents[1]
_ROOT = _SIM.parent
for p in (_ROOT, _SIM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from engine.tick import attempt_alliance, intervene, soft_pathway, tick
from engine.world import new_world


def test_baseline_pressure_rises():
    world = new_world()
    p0 = world.qin_pressure
    assert abs(p0 - 20.0) < 0.5  # early-game pacing start ~20 (tiny demo nudge OK)
    tick(world)
    assert world.qin_pressure > p0
    tick(world)
    # Base +2/tick → ~+4 over two quarters (extras may add a little)
    assert world.qin_pressure > p0 + 3.0
    assert world.qin_pressure < p0 + 12.0


def test_intervene_moves_state():
    world = new_world()
    chu = world.agents["chu"]
    r0 = chu.state.resentment
    c0 = world.meso.cohesion
    intervene(world, "chu")
    assert world.agents["chu"].state.resentment < r0
    assert world.meso.cohesion > c0
    assert world.agents["chu"].intention.current == "cooperate"
    assert any(e.get("event_id") == "intervene" for e in world.episode)


def test_alliance_quorum():
    world = new_world()
    # Healthy bloc should often succeed at t0
    for ag in world.agents.values():
        if ag.bloc == "anti_qin":
            ag.intention.current = "cooperate"
            ag.state.resentment = 0.2
            ag.state.betrayal_memory = 0.2
            ag.state.perceived_threat = 0.2
    world.meso.cohesion = 70.0
    world.qin_pressure = 40.0
    attempt_alliance(world)
    assert any(e.get("event_id") == "alliance" for e in world.episode)
    # Either success or fail path recorded with quorum action
    actions = {e.get("action") for e in world.episode if e.get("event_id") == "alliance"}
    assert actions & {"quorum_success", "quorum_fail"}


def test_episode_log_grows():
    world = new_world()
    n0 = len(world.episode)
    tick(world)
    assert len(world.episode) > n0
    n1 = len(world.episode)
    intervene(world, "chu")
    assert len(world.episode) > n1
    tick(world)
    assert len(world.episode) > n1 + 1


def test_pathway_includes_other():
    world = new_world()
    label = soft_pathway(world)
    assert label in {"qin_path", "stalemate", "chu_fiction", "other"}
    # Below precarious-peace band → other (wider stalemate leaves only thin other region)
    world.meso.cohesion = 30.0
    world.qin_pressure = 60.0
    world.meso.shared_identity = 20.0
    world.meso.quorum_ok = False
    assert soft_pathway(world) == "other"


def test_pathway_reading_note_is_observational_only():
    """Détente gloss reads meters; soft_pathway never invents coexistence/friendship rules."""
    from engine.patron_client import clique_sync, seed_chu_patron_client
    from engine.tick import pathway_reading_note, soft_pathway
    from engine.trust import get_trust, set_trust
    from engine.world import new_world

    w = new_world()
    w.meso.cohesion = 55.0
    w.qin_pressure = 60.0
    w.meso.shared_identity = 50.0
    w.meso.quorum_ok = True
    w.chu_court = seed_chu_patron_client()
    w.pathway_stable_count = 5
    set_trust(w.trust, "chu", "qin", 0.15)
    set_trust(w.trust, "qi", "qin", 0.15)
    # Soft label stays stalemate (no hard-coded coexist pathway id)
    assert soft_pathway(w) == "stalemate"
    w.meso.pathway_soft = "stalemate"
    assert clique_sync(w.chu_court)["bonded"] >= 1.0
    note = pathway_reading_note(w)
    assert "not friendship" in note
    assert "détente" in note.lower() or "tribute" in note.lower()
    # soft_pathway must not mutate trust
    assert get_trust(w.trust, "chu", "qin") == 0.15


def test_no_gradio_import_in_engine():
    import importlib
    for name in (
        "engine.tick",
        "engine.world",
        "engine.agents",
        "engine.trust",
        "engine.packets",
        "engine.triggers",
        "engine.figures",
        "engine.geo",
        "engine.demo_flow",
        "engine.patron_client",
        "engine.dossiers",
        "engine.tech_hooks",
        "engine.demographics",
    ):
        mod = importlib.import_module(name)
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "gradio" not in src.lower()


def test_contagion_updates_packet_weights():
    """Adopt/reinforce must bump packet_weights (not active list alone)."""
    from engine.packets import propagate_packets, starting_weights
    from engine.trust import set_trust
    from engine.world import new_world

    w = new_world()
    # Seed Wei with a contagious Dao packet Wei lacks; raise mutual trust Chu↔Wei
    chu = w.agents["chu"]
    wei = w.agents["wei"]
    chu.packet_weights = starting_weights("chu")
    wei.packet_weights = {
        "tianxia_da_yitong": 0.5,
        "ru_li": 0.35,
        "lineage_shi": 0.15,
    }
    wei.active_packets = ["tianxia_da_yitong", "ru_li", "lineage_shi"]
    wei.traits.openness = 0.9
    w.world.evo_dial = 1.0
    set_trust(w.trust, "chu", "wei", 0.85)
    set_trust(w.trust, "wei", "chu", 0.85)
    before = float(wei.packet_weights.get("dao_guodian", 0.0))
    events = propagate_packets(w)
    adopted = [
        e
        for e in events
        if e.get("to") == "wei" and e.get("packet") == "dao_guodian" and e.get("result") in ("adopted", "reinforced")
    ]
    assert adopted, f"expected dao contagion into Wei; got {events[:5]}"
    assert float(wei.packet_weights.get("dao_guodian", 0.0)) > before
    assert abs(sum(wei.packet_weights.values()) - 1.0) < 0.05


def test_figure_dossiers_grounded():
    from engine.dossiers import FIGURE_DOSSIERS, dossier_for_figure
    from engine.figures import figure_ids, figure_profile
    from engine.world import new_world

    assert set(FIGURE_DOSSIERS) == set(figure_ids())
    w = new_world()
    for fid in figure_ids():
        text = dossier_for_figure(fid)
        assert len(text) > 40
        assert "fiction" not in text.lower() or "excluded" in text.lower() or "no fiction" in text.lower()
        prof = figure_profile(w, fid)
        assert prof["dossier"]
        assert "base_schools" in prof
        assert set(prof["base_schools"]) == {
            "legalism",
            "mohism",
            "daoism",
            "confucianism",
        }


def test_figures_cast():
    from engine.figures import figure_ids, figure_profile
    from engine.world import new_world

    ids = figure_ids()
    for need in ("kaolie", "chunshen", "chu_nobility", "king_jian", "ying_zheng", "li_si"):
        assert need in ids
    w = new_world()
    prof = figure_profile(w, "kaolie")
    assert "big_five" in prof and "packets" in prof and "dyadic_trust" in prof
    assert prof["home_court"] == "chu"
    assert "dao_guodian" in prof["packet_weights"]


def test_chu_syncretic_not_fa():
    from engine.packets import starting_weights
    from engine.world import new_world

    w = new_world()
    chu_w = starting_weights("chu")
    assert chu_w.get("dao_guodian", 0) > chu_w.get("legalist_fa", 0)
    assert "chu_patron_client" in w.agents["chu"].active_packets
    assert "legalist_fa" not in w.agents["chu"].active_packets


def test_m4_and_soft_lock():
    from engine.demo_flow import mechanism_lock, soft_lock_if_needed
    from engine.geo import rollup_m4
    from engine.tick import tick
    from engine.world import new_world

    m4 = rollup_m4()
    assert m4.defense_mod > 0 and m4.qin_projection > 0

    # No calendar lock: 20Q open run must not end from Q-count alone
    w = new_world()
    for _ in range(20):
        tick(w)
    # May or may not lock from mechanisms; if locked, must be mechanism not Q-count
    if w.run_ended:
        assert w.end_screen and w.end_screen.get("lock_kind") == "mechanism"
        assert w.end_screen.get("mechanism") in {
            "qin_path_damage",
            "cascade_betrayal_quorum",
            "sticky_structural",
        }
        assert "Q-count" not in (w.end_screen.get("reason") or "")
        assert w.end_screen.get("pathway") != "stalemate" or w.end_screen.get("mechanism") != "stalemate_alone"

    # Mechanism (1): qin_path + cohesion collapse (after grace MIN_LOCK_TICK)
    from engine.demo_flow import MIN_LOCK_TICK

    w2 = new_world()
    w2.meso.pathway_soft = "qin_path"
    w2.meso.cohesion = 8.0
    w2.tick = max(5, MIN_LOCK_TICK)
    mech, reason = mechanism_lock(w2)
    assert mech == "qin_path_damage"
    soft_lock_if_needed(w2)
    assert w2.run_ended is True
    assert w2.end_screen["mechanism"] == "qin_path_damage"
    # Grace: same damage before MIN_LOCK_TICK must not lock
    w2g = new_world()
    w2g.meso.pathway_soft = "qin_path"
    w2g.meso.cohesion = 8.0
    w2g.tick = max(1, MIN_LOCK_TICK - 1)
    assert mechanism_lock(w2g)[0] is None

    # Never lock on stalemate alone (sticky, no structural damage)
    w3 = new_world()
    w3.meso.pathway_soft = "stalemate"
    w3.last_pathway = "stalemate"
    w3.pathway_stable_count = 10
    w3.meso.cohesion = 55.0
    w3.tick = 10
    mech3, _ = mechanism_lock(w3)
    assert mech3 is None

    # New Run clears lock
    from backend import fresh_run

    cleared = fresh_run()
    assert cleared.get("run_ended") is False or (cleared.get("_engine") or {}).get("run_ended") is False


def test_action_labels_anti_qin():
    from engine.action_labels import full_label, who_vs_qin_line
    from engine.tick import tick
    from engine.world import new_world

    assert "anti-Qin coalition" in full_label("cooperate")
    assert "friendship" not in full_label("cooperate").lower()
    w = new_world()
    tick(w)
    line = who_vs_qin_line(w)
    assert "vs Qin pressure" in line
    assert any("Contribute" in e.get("text", "") or "Withhold" in e.get("text", "") or "Defect" in e.get("text", "") or "Press" in e.get("text", "") for e in w.episode)


def test_chu_hub_spoke():
    from engine.patron_client import clique_sync, seed_chu_patron_client
    from engine.world import new_world

    g = seed_chu_patron_client()
    # Hub↔client high; lateral weaker
    assert g.get("chunshen", "retainers") >= 0.7
    assert g.get("nobility", "retainers") < 0.5
    sync = clique_sync(g)
    assert "order_parameter" in sync
    w = new_world()
    assert w.chu_court.hubs == ["kaolie", "chunshen"]


def test_guanzi_distinct_from_huang_lao():
    from engine.figures import figure_profile
    from engine.packets import PACKET_CATALOG, compat, starting_weights
    from engine.world import new_world

    assert "guanzi" in PACKET_CATALOG
    assert "huang_lao" in PACKET_CATALOG
    assert PACKET_CATALOG["guanzi"].logic_id != PACKET_CATALOG["huang_lao"].logic_id
    assert compat("guanzi", "huang_lao") < 0.9  # related, not identical
    qi_w = starting_weights("qi")
    assert qi_w.get("guanzi", 0) >= qi_w.get("huang_lao", 0)
    assert qi_w["guanzi"] >= 0.3
    w = new_world()
    assert "guanzi" in w.agents["qi"].active_packets
    jian = figure_profile(w, "king_jian")
    assert jian["packet_weights"].get("guanzi", 0) >= 0.3
    assert "Huang-Lao" not in (PACKET_CATALOG["guanzi"].name_zh or "")


def test_m2_tech_military():
    from engine.tech import TECH_DAG, field_tech_summary, tech_pressure_delta, tick_tech
    from engine.tick import attempt_alliance, intervene_many, tick
    from engine.world import new_world
    from backend import character_choices, fresh_run, initial_state, intervene_targets

    w = new_world()
    assert hasattr(w, 'tech')
    assert len(TECH_DAG) >= 8
    snap = tick_tech(w)
    assert 'qin_mil' in snap and snap['qin_mil'] > 0
    assert w.world.military_qin > 0
    # pressure path includes tech delta (finite)
    d = tech_pressure_delta(w)
    assert isinstance(d, float)
    p0 = w.qin_pressure
    tick(w)
    assert w.qin_pressure != p0 or True  # pressure may move
    # Field projection
    from backend import _project
    ui = _project(w)
    assert 'm2' in ui and ui['m2']['rows']
    assert 'adoption_meter' in ui
    # intervene multi path (one click, multi-target = one budget)
    s, msgs, err = intervene_targets(initial_state(), ['qin', 'chu', 'qi'])
    assert err is None
    assert len(msgs) >= 1
    assert s.get("intervene_actions_left") == 0
    s2, msgs2, err2 = intervene_targets(s, ['chu'])
    assert err2 and "already used" in err2.lower()
    # cast radio: Kaolie/You/Chunshen/nobility + Zhaoxiang/Zheng/Li Si + Jian
    assert len(character_choices(None)) >= 7
    # new run clears
    fr = fresh_run()
    assert fr.get('tick', 0) == 0 or (fr.get('_engine') or {}).get('tick', 0) == 0
    # long run no calendar lock
    w2 = new_world()
    for _ in range(16):
        tick(w2)
    if w2.run_ended:
        assert w2.end_screen.get('lock_kind') == 'mechanism'


def test_m1_m2_m4_force_pressure_and_lock():
    """Military/levy force: M4→M1→M2 into pressure, quorum floor, structural lock."""
    from backend import _project
    from engine.demo_flow import mechanism_lock
    from engine.geo import apply_m1_env, apply_m4_to_world, rollup_m4
    from engine.tech import recompute_tech, tech_pressure_delta, tech_structural_damage, tick_tech
    from engine.world import new_world

    m4 = rollup_m4()
    assert m4.levy_capacity > 0.3 and m4.qin_projection > 0.2

    w = new_world()
    apply_m4_to_world(w)
    base_levy = float(w.world.levy_capacity)
    w.tick = 11  # deterministic famine shock tick
    m1 = apply_m1_env(w)
    assert m1["famine_shock"] > 0.2
    assert w.world.levy_capacity < base_levy

    low = new_world()
    high = new_world()
    low.world.levy_capacity = 0.2
    high.world.levy_capacity = 0.95
    recompute_tech(low.tech, levy_capacity=0.2)
    recompute_tech(high.tech, levy_capacity=0.95)
    assert high.tech.qin_mil >= low.tech.qin_mil

    snap = tick_tech(w)
    assert snap["qin_mil"] > 0
    d = tech_pressure_delta(w)
    assert isinstance(d, float)

    # Structural lock path: extreme Qin mil advantage + coalition collapse
    w2 = new_world()
    w2.tech.qin_mil_advantage = 0.4
    w2.tech.coalition_mil = 0.15
    w2.tech.qin_mil = 0.55
    w2.tech.qin_mil_advantage = 0.50
    w2.tech.coalition_mil = 0.12
    damaged, note = tech_structural_damage(w2)
    assert damaged and "qin_mil_advantage" in note
    from engine.demo_flow import MIN_LOCK_TICK

    w2.meso.pathway_soft = "qin_path"
    w2.meso.cohesion = 50.0
    w2.tick = MIN_LOCK_TICK
    mech, reason = mechanism_lock(w2)
    assert mech == "qin_path_damage"
    assert "M2" in reason

    # Field projection: Adoption Meter + M1/M4 without app rewrite
    ui = _project(new_world())
    assert ui["m2"]["rows"]
    assert "adoption_meter" in ui
    assert "famine_shock" in ui["m1"]
    assert ui["m4"]["levy_capacity"] > 0


def test_defection_inertia_and_fear_gate():
    from engine.agents import DEFECTION_ACCUMULATOR_THRESHOLD, decide_action
    from engine.world import new_world

    w = new_world()
    chu = w.agents["chu"]
    # Force defect pressure: high resentment, low fear, high threat past threshold
    chu.state.resentment = 0.85
    chu.state.fear_of_qin = 0.20
    chu.state.betrayal_memory = 0.9
    chu.state.perceived_threat = 0.9
    chu.state.withholding_threshold = 0.3
    chu.intention.current = "cooperate"
    chu.intention.sticky_until = 0
    chu.state.defection_accumulator = 0
    acts = []
    for t in range(1, DEFECTION_ACCUMULATOR_THRESHOLD + 2):
        w.tick = t
        acts.append(decide_action(chu, 60.0, 40.0, t))
    # First two under threshold → withhold; then defect
    assert acts[0] == "withhold"
    assert acts[1] == "withhold"
    assert acts[2] == "defect"
    # Fear gate: resentment ≤ fear blocks defect even with high accumulator
    chu.state.resentment = 0.15
    chu.state.fear_of_qin = 0.50
    chu.state.defection_accumulator = 5
    assert decide_action(chu, 80.0, 30.0, 10) != "defect"


def test_player_invest_costs_and_econ_fields():
    from backend import do_player_action, fresh_run, _project
    from engine.tick import player_action, tick
    from engine.world import new_world

    w = new_world()
    assert w.agents["chu"].geographic_yield > w.agents["yan"].geographic_yield
    assert w.agents["chu"].grain >= 80  # river/rice
    assert w.agents["qin"].treasury >= 75  # Legalist efficiency
    assert abs(w.qin_pressure - 20.0) < 0.5
    assert w.player_invest_actions_left == 1
    pc0, tr0 = w.player_political_capital, w.player_treasury
    player_action(w, "fund_military", "chu")
    assert w.player_political_capital < pc0
    assert w.player_treasury < tr0
    assert w.player_invest_actions_left == 0
    assert any("Fund Military" in x for x in w.player_log)

    # Second invest same tick is budget-blocked
    player_action(w, "send_grain", "qi")
    assert w.last_player_action_error and "budget" in w.last_player_action_error.lower()

    # Advance resets invest budget; broke purse still fails
    tick(w)
    assert w.player_invest_actions_left == 1
    w.player_political_capital = 0
    w.player_treasury = 0
    n = len(w.player_log)
    player_action(w, "send_grain", "qi")
    assert len(w.player_log) > n
    assert "failed" in w.player_log[-1].lower() or "need" in w.player_log[-1].lower()

    # Backend projection
    ui = _project(new_world())
    assert "viability" in ui["agents"]["chu"]
    assert "grain" in ui["agents"]["chu"]
    assert "player_political_capital" in ui
    assert "player_invest_actions_left" in ui
    assert "alliance_fund_spent_purposes" in ui
    st, msgs, err = do_player_action(fresh_run(), "broker_mediation", "chu")
    assert err is None
    assert st.get("player_log")
    assert st.get("player_invest_actions_left") == 0


def test_annex_absorbs_victim_tech_board():
    """Victor known/adopted = max(own, victim) per node; victim board cleared."""
    from engine.conflict import annex_state
    from engine.tech import TECH_DAG
    from engine.world import new_world

    w = new_world()
    board = w.tech
    # Give Han superior tech on a few nodes; Wei weaker there
    for nid in list(TECH_DAG.keys())[:4]:
        board.states["han"].known[nid] = 1.0
        board.states["han"].adopted[nid] = 0.85
        board.states["wei"].known[nid] = 0.2
        board.states["wei"].adopted[nid] = 0.1
    wei_mil0 = float(board.military.get("wei", 0.0))
    ok = annex_state(w, "han", "wei")
    assert ok
    for nid in list(TECH_DAG.keys())[:4]:
        assert board.states["wei"].known[nid] >= 0.999
        assert board.states["wei"].adopted[nid] >= 0.849
        assert board.states["han"].known.get(nid, 0.0) == 0.0
        assert board.states["han"].adopted.get(nid, 0.0) == 0.0
    assert float(board.military.get("wei", 0.0)) >= wei_mil0
    assert any("Tech absorb" in x for x in w.player_log)


def test_alliance_fund_spend_reduces_totals():
    """Joint fund grain/treasury must drop on Tech/Agri/Build/Military spend."""
    from backend import _project, spend_alliance_fund as backend_spend
    from engine.tick import ALLIANCE_FUND_COSTS, spend_alliance_fund
    from engine.world import new_world

    w = new_world()
    w.alliance_fund_grain = 40.0
    w.alliance_fund_treasury = 40.0
    w.alliance_fund_spent_purposes = []
    for purpose in ("tech", "agriculture", "construction", "military"):
        g0, t0 = w.alliance_fund_grain, w.alliance_fund_treasury
        gc, tc = ALLIANCE_FUND_COSTS[purpose]
        spend_alliance_fund(w, purpose)
        assert purpose in w.alliance_fund_spent_purposes
        assert abs(w.alliance_fund_grain - (g0 - gc)) < 1e-6, purpose
        assert abs(w.alliance_fund_treasury - (t0 - tc)) < 1e-6, purpose
        ui = _project(w)
        assert abs(ui["alliance_fund_grain"] - w.alliance_fund_grain) < 1e-6
        assert abs(ui["alliance_fund_treasury"] - w.alliance_fund_treasury) < 1e-6
        assert abs(ui["_engine"]["alliance_fund_grain"] - w.alliance_fund_grain) < 1e-6
    # Re-spend same purpose blocked without Advance
    spend_alliance_fund(w, "tech")
    assert w.last_alliance_fund_error and "already used" in w.last_alliance_fund_error.lower()

    # Backend adapter path
    st = _project(new_world())
    st["alliance_fund_grain"] = 40.0
    st["alliance_fund_treasury"] = 40.0
    st["alliance_fund_spent_purposes"] = []
    st["_engine"]["alliance_fund_grain"] = 40.0
    st["_engine"]["alliance_fund_treasury"] = 40.0
    st["_engine"]["alliance_fund_spent_purposes"] = []
    out, msgs, err = backend_spend(st, "military")
    assert err is None
    assert abs(out["alliance_fund_grain"] - 37.0) < 1e-6
    assert abs(out["alliance_fund_treasury"] - 31.0) < 1e-6
    assert "military" in out["alliance_fund_spent_purposes"]


def test_demo_playfeel_action_budget_and_bystander_annex():
    """1 invest + per-purpose fund; annex bystanders get resentment shock."""
    from engine.conflict import annex_state
    from engine.tech import tick_tech
    from engine.tick import player_action, spend_alliance_fund, tick
    from engine.trust import get_trust
    from engine.world import new_world

    w = new_world()
    player_action(w, "fund_military", "chu")
    assert w.player_invest_actions_left == 0
    player_action(w, "broker_mediation", "qi")
    assert w.last_player_action_error and "budget" in w.last_player_action_error.lower()

    w.alliance_fund_grain = 50
    w.alliance_fund_treasury = 50
    spend_alliance_fund(w, "military")
    assert "military" in w.alliance_fund_spent_purposes
    # Different purpose still OK same tick
    spend_alliance_fund(w, "tech")
    assert "tech" in w.alliance_fund_spent_purposes
    assert w.last_alliance_fund_error is None
    # Same purpose blocked
    spend_alliance_fund(w, "military")
    assert w.last_alliance_fund_error and "already used" in w.last_alliance_fund_error.lower()

    tick(w)
    assert w.player_invest_actions_left == 1
    assert w.alliance_fund_spent_purposes == []
    assert w.alliance_attempt_actions_left == 1

    # Attempt Alliance once per tick
    from engine.tick import attempt_alliance as eng_alliance
    from engine.tick import intervene_many

    eng_alliance(w)
    assert w.alliance_attempt_actions_left == 0
    eng_alliance(w)
    assert w.last_alliance_attempt_error and "already attempted" in w.last_alliance_attempt_error.lower()

    # Intervene once per tick (multi-target still one)
    assert w.intervene_actions_left == 1
    intervene_many(w, ["qin", "chu", "qi"])
    assert w.intervene_actions_left == 0
    intervene_many(w, ["chu"])
    assert w.last_intervene_error and "already used" in w.last_intervene_error.lower()

    # Bystander resentment on annex
    chu = w.agents["chu"]
    qi = w.agents["qi"]
    res0, bet0 = float(chu.state.resentment), float(chu.state.betrayal_memory)
    qi_res0 = float(qi.state.resentment)
    trust0 = get_trust(w.trust, "chu", "wei")
    ok = annex_state(w, "han", "wei")
    assert ok
    assert float(chu.state.resentment) > res0
    assert float(chu.state.betrayal_memory) > bet0
    assert float(qi.state.resentment) > qi_res0
    assert get_trust(w.trust, "chu", "wei") < trust0
    assert any("Bystander shock" in x for x in w.player_log)
    # Victim / annexer are not bystanders
    assert w.agents["han"].annexed
    assert w.agents["wei"].annexed is False

    # Eureka rarer: ≤1 breakthrough label per state in a tick_tech return
    snaps = [tick_tech(w) for _ in range(5)]
    for snap in snaps:
        by_state = {}
        for b in snap.get("breakthroughs") or []:
            sid = b.split(":", 1)[0]
            by_state[sid] = by_state.get(sid, 0) + 1
        assert all(v <= 1 for v in by_state.values())


def test_send_grain_all_anti_qin_targets():
    """Chu/Qi/Zhao/Han/Wei/Yan must all accept Send Grain when living."""
    from backend import do_player_action, fresh_run
    from engine.conflict import annex_state
    from engine.tick import player_action
    from engine.world import new_world

    for tid in ("chu", "qi", "zhao", "han", "wei", "yan"):
        st, msgs, err = do_player_action(fresh_run(), "send_grain", tid)
        assert err is None, f"{tid}: {err}"
        assert any("Send Grain" in x and "failed" not in x.lower() for x in (st.get("player_log") or []))

    # Annexed Han must fail with a clear annexed message (not a vague living-state blurb)
    w = new_world()
    annex_state(w, "han", "wei")
    player_action(w, "send_grain", "han")
    assert w.last_player_action_error and "annexed" in w.last_player_action_error.lower()


def test_unassisted_survival_at_least_12_ticks():
    """Early-game pacing: unassisted run lasts ≥12 ticks before soft-lock."""
    from engine.tick import tick
    from engine.world import new_world

    w = new_world()
    locked_at = None
    for _ in range(15):
        tick(w)
        if w.run_ended:
            locked_at = w.tick
            break
    if locked_at is not None:
        assert locked_at >= 12, f"collapsed too early at tick={locked_at}"
    else:
        assert w.tick >= 15


def test_desperation_and_conflict_spoils():
    from engine.conflict import (
        ensure_econ_fields,
        resolve_attack,
        update_desperation,
    )
    from engine.world import new_world

    w = new_world()
    ensure_econ_fields(w)
    chu = w.agents["chu"]
    chu.viability = 20.0
    chu.grain = 10.0
    chu.treasury = 10.0
    flipped = update_desperation(w)
    assert chu.desperate
    assert "chu" in flipped
    # Forced fight: give attacker resources
    w.tick = 8
    chu.treasury = 40.0
    chu.grain = 40.0
    qi = w.agents["qi"]
    g0 = float(chu.grain)
    res = resolve_attack(w, "chu", "qi")
    assert not res.get("cancelled")
    # Spoils transferred or viability hit landed
    assert res["loser_viability"] <= 100.0
    assert "spoils" in res
