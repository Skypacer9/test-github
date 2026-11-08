"""WS-49 seven-state dashboard + parked systems (S1–S5, D1c)."""

from __future__ import annotations

from backend import do_player_action, initial_state, _project
from engine.action_labels import who_vs_qin_line
from engine.conflict import (
    ANNEX_COHESION_HIT,
    ideology_raid_score,
    annex_state,
    resolve_attack,
    tick_resource_income,
)
from engine.tick import ALLIANCE_FUND_SKIM_SKIP_TOTAL, attempt_alliance, player_action
from engine.trust import get_trust
from engine.world import new_world


def test_backend_projects_seven_states_econ():
    a = initial_state()["agents"]
    need = {"qin", "chu", "qi", "zhao", "han", "wei", "yan"}
    assert set(a) >= need
    keys = (
        "viability",
        "grain",
        "treasury",
        "geographic_yield",
        "resentment",
        "fear_of_qin",
        "annexed",
        "desperate",
        "stance_mode",
    )
    for sid in need:
        for k in keys:
            assert k in a[sid], f"{sid} missing {k}"


def test_alliance_skim_skipped_when_fund_substantial():
    w = new_world()
    for ag in w.agents.values():
        if ag.bloc == "anti_qin":
            ag.intention.current = "cooperate"
            ag.state.resentment = 0.15
            ag.state.betrayal_memory = 0.15
            ag.state.fear_of_qin = 0.25
            ag.state.perceived_threat = 0.2
            ag.grain = 60.0
            ag.treasury = 60.0
    w.meso.cohesion = 75.0
    w.qin_pressure = 35.0
    w.alliance_fund_grain = 30.0
    w.alliance_fund_treasury = 30.0  # total 60 ≥ SKIP 55
    w.alliance_attempt_actions_left = 1
    before_g = {aid: float(ag.grain) for aid, ag in w.agents.items() if ag.bloc == "anti_qin"}
    before_t = {aid: float(ag.treasury) for aid, ag in w.agents.items() if ag.bloc == "anti_qin"}
    fund_g0 = float(w.alliance_fund_grain)
    fund_t0 = float(w.alliance_fund_treasury)
    chu_fear0 = float(w.agents["chu"].state.fear_of_qin)

    attempt_alliance(w)

    actions = {e.get("action") for e in w.episode if e.get("event_id") == "alliance"}
    assert "quorum_success" in actions
    # Contributors not levied; fund unchanged
    for aid, g0 in before_g.items():
        assert float(w.agents[aid].grain) == g0
        assert float(w.agents[aid].treasury) == before_t[aid]
    assert float(w.alliance_fund_grain) == fund_g0
    assert float(w.alliance_fund_treasury) == fund_t0
    assert float(w.alliance_fund_grain) + float(w.alliance_fund_treasury) >= ALLIANCE_FUND_SKIM_SKIP_TOTAL
    # Psych cool still applied
    assert float(w.agents["chu"].state.fear_of_qin) < chu_fear0
    blob = " ".join(str(x) for x in (w.player_log or []))
    blob += " ".join(str(e.get("text") or e.get("line") or "") for e in w.episode)
    assert "skim skipped" in blob.lower() or "no re-levy" in blob.lower()


def test_annex_cohesion_and_bystander_shock():
    w = new_world()
    coh0 = float(w.meso.cohesion)
    chu = w.agents["chu"]
    qi = w.agents["qi"]
    res0 = float(chu.state.resentment)
    bet0 = float(chu.state.betrayal_memory)
    trust0 = get_trust(w.trust, "chu", "wei")
    qi_res0 = float(qi.state.resentment)

    assert annex_state(w, "han", "wei")
    assert float(w.meso.cohesion) <= coh0 - ANNEX_COHESION_HIT + 1e-9
    assert ANNEX_COHESION_HIT >= 10.0
    assert float(chu.state.resentment) > res0
    assert float(chu.state.betrayal_memory) > bet0
    assert get_trust(w.trust, "chu", "wei") < trust0
    assert float(qi.state.resentment) > qi_res0
    # Victim + annexer excluded from bystander set
    assert w.agents["han"].annexed
    assert w.agents["wei"].annexed is False
    # Victim resentment not treated as bystander bump requirement
    line = who_vs_qin_line(w)
    assert "Han=" not in line


def test_who_vs_qin_omits_annexed():
    w = new_world()
    annex_state(w, "han", "wei")
    w.last_actions = {
        aid: ("withhold" if getattr(ag, "annexed", False) else "cooperate")
        for aid, ag in w.agents.items()
    }
    line = who_vs_qin_line(w, w.last_actions)
    assert "Han=" not in line
    assert "Chu=" in line
    # Decision rollups omit annexed
    from engine.action_labels import format_decision_records

    rows = format_decision_records(w, w.last_actions)
    actors = {r["actor"] for r in rows if r["action"] != "who_vs_qin"}
    assert "han" not in actors


def test_invest_rejects_annexed():
    w = new_world()
    annex_state(w, "han", "wei")
    player_action(w, "send_grain", "han")
    assert w.last_player_action_error and "annexed" in w.last_player_action_error.lower()

    st = _project(w)
    projected, _msgs, err = do_player_action(st, "fund_military", "han")
    assert err and "annexed" in err.lower()
    # HTML invest list marks annexed disabled
    html = open("static/index.html", encoding="utf-8").read()
    assert "refreshInvestTargets" in html
    assert "disabled" in html


def test_viability_regen_when_stable_not_desperate():
    w = new_world()
    chu = w.agents["chu"]
    chu.desperate = False
    chu.annexed = False
    chu.viability = 70.0
    chu.grain = 55.0
    chu.geographic_yield = 0.75
    v0 = float(chu.viability)
    tick_resource_income(w)
    assert float(chu.viability) > v0

    # Desperate: no regen
    chu.viability = 70.0
    chu.desperate = True
    v1 = float(chu.viability)
    tick_resource_income(w)
    assert float(chu.viability) == v1

    # Annexed: skipped entirely (_alive gate)
    han = w.agents["han"]
    han.annexed = True
    han.desperate = False
    han.viability = 0.0
    tick_resource_income(w)
    assert float(han.viability) == 0.0


def test_war_trust_and_resentment_both_sides():
    w = new_world()
    # Force affordable fight without early-tick gate by calling resolve_attack directly
    atk, dfn = w.agents["chu"], w.agents["wei"]
    atk.grain = atk.treasury = 80.0
    dfn.grain = dfn.treasury = 80.0
    atk.viability = dfn.viability = 90.0
    t_aw = get_trust(w.trust, "chu", "wei")
    t_wa = get_trust(w.trust, "wei", "chu")
    r_a = float(atk.state.resentment)
    r_d = float(dfn.state.resentment)
    res = resolve_attack(w, "chu", "wei")
    assert res and not res.get("cancelled")
    assert get_trust(w.trust, "chu", "wei") < t_aw
    assert get_trust(w.trust, "wei", "chu") < t_wa
    assert float(w.agents["chu"].state.resentment) > r_a
    assert float(w.agents["wei"].state.resentment) > r_d


def test_ideology_raid_priors():
    w = new_world()
    legalist = w.agents["han"]
    soft = w.agents["chu"]
    legalist.desperate = False
    soft.desperate = False
    legalist.stance_mode = "coalition"
    soft.stance_mode = "coalition"
    legalist.packet_weights = {
        "legalist_fa": 0.85,
        "tianxia_da_yitong": 0.05,
        "chu_patron_client": 0.0,
    }
    soft.packet_weights = {
        "legalist_fa": 0.05,
        "tianxia_da_yitong": 0.55,
        "chu_patron_client": 0.45,
    }
    s_leg = ideology_raid_score(legalist)
    s_soft = ideology_raid_score(soft)
    assert s_leg > s_soft
    # Soft gate often refuses raid (< 0.28) unless Optimizing / Desperate
    assert s_soft < 0.28 or s_leg - s_soft >= 0.25
    soft.desperate = True
    assert ideology_raid_score(soft) >= 1.0
    soft.desperate = False
    soft.stance_mode = "optimizing"
    assert ideology_raid_score(soft) > s_soft
