"""Figure counsel — stub, dial tips, dialogue close, belief/breakthrough caps."""

from __future__ import annotations

import os

from backend import initial_state, run_counsel
from engine.conflict import annex_state
from engine.counsel import (
    APHORISM_SEEDS,
    FIGURE_UTTERANCE_BANKS,
    IDEOLOGY_UTTERANCE_BANKS,
    LEGALIST_SEED_MARKERS,
    apply_belief_seeds,
    apply_breakthrough,
    counsel_backend_name,
    parse_counsel_payload,
    run_counsel_round,
    suggest_prompt_chips,
    _ideology_for,
    _speech_role_for,
    _utter,
    ROLE_UTTERANCE_BANKS,
)
from engine.figures import get_figure
from engine.tick import tick
from engine.trust import get_trust
from engine.world import new_world


def test_aphorism_seed_cap_english():
    assert 1 <= len(APHORISM_SEEDS) <= 20
    for s in APHORISM_SEEDS:
        assert s.isascii() or all(ord(c) < 0x3400 for c in s)


def test_counsel_backend_stub_without_key():
    os.environ["WS_COUNSEL_API_KEY"] = ""
    assert counsel_backend_name() == "stub"


def test_counsel_stub_round_and_close_auto():
    w = new_world()
    r = run_counsel_round(w, force_stub=True, player_initiated=False)
    assert r["ok"] and r.get("mode") == "stub" and r.get("closed")
    assert 2 <= len(r["rows"]) <= 4
    for row in r["rows"]:
        assert row["stance_lean"] in (
            "contribute",
            "withhold",
            "defect",
            "hedge",
            "refuse",
            "cooperate",
        )
        assert -0.25 <= float(row["loyalty_shift"]) <= 0.25
        assert row["utterance"]
        # No CJK in UI utterances
        assert not any("\u4e00" <= ch <= "\u9fff" for ch in row["utterance"])
    assert w.counsel_log
    assert any(e.get("event_id") == "counsel" for e in w.episode)


def test_counsel_stub_tips_dials():
    w = new_world()
    coh0 = float(w.meso.cohesion)
    t0 = get_trust(w.trust, "chu", "qi")
    r = run_counsel_round(w, force_stub=True)
    assert r["ok"] and r.get("closed")
    tips = r.get("tips") or {}
    # tips applied; cohesion/trust may move or cancel — still logged
    assert tips is not None
    assert "cohesion_delta" in tips
    # annexed homes excluded from living selection
    annex_state(w, "han", "wei")
    r2 = run_counsel_round(w, force_stub=True)
    homes = {row["home"] for row in r2["rows"]}
    assert "han" not in homes


def test_hedge_refuse_no_forced_intention():
    w = new_world()
    before = {aid: ag.intention.current for aid, ag in w.agents.items()}
    rows = [
        {
            "figure_id": "chunshen",
            "home": "chu",
            "stance_lean": "hedge",
            "loyalty_shift": 0.0,
            "event_tag": "hedge",
            "utterance": "Hedge.",
            "belief_seed": None,
            "breakthrough": None,
        },
        {
            "figure_id": "king_jian",
            "home": "qi",
            "stance_lean": "refuse",
            "loyalty_shift": -0.02,
            "event_tag": "refuse",
            "utterance": "Refuse.",
            "belief_seed": None,
            "breakthrough": None,
        },
    ]
    from engine.counsel import apply_counsel_tips

    apply_counsel_tips(w, rows)
    assert w.agents["chu"].intention.current == before["chu"]
    assert w.agents["qi"].intention.current == before["qi"]


def test_multi_turn_forced_close_no_player_dossier():
    w = new_world()
    # Open talk
    r1 = run_counsel_round(w, prompt="Among the courts: hold the line.", force_stub=True, player_initiated=True)
    assert r1["ok"]
    if not r1.get("closed"):
        assert r1["exchange"] >= 1
        # Session has no player ocean / dossier keys
        sess = w.counsel_session
        assert "player_ocean" not in sess
        assert "choice_dossier" not in sess
        # Force close
        r2 = run_counsel_round(
            w,
            prompt="Close counsel: lean contribute.",
            force_stub=True,
            player_initiated=True,
            commit=True,
        )
        assert r2["ok"] and r2.get("closed")
        assert r2.get("tips") is not None
    # After close, ephemeral pressure wiped
    assert not (w.counsel_session or {}).get("open")
    assert (w.counsel_session or {}).get("pressure", "") in ("", None)


def test_belief_cascade_caps():
    w = new_world()
    rows = [
        {
            "figure_id": "chunshen",
            "home": "chu",
            "stance_lean": "contribute",
            "loyalty_shift": 0.05,
            "event_tag": "belief_cascade",
            "utterance": "Seed one.",
            "belief_seed": {
                "belief_id": "patron_obligation_over_qin_fear",
                "weight_delta": 0.08,
                "spread_hint": "along_loyalty",
            },
            "breakthrough": None,
        },
        {
            "figure_id": "kaolie",
            "home": "chu",
            "stance_lean": "contribute",
            "loyalty_shift": 0.02,
            "event_tag": "belief_cascade",
            "utterance": "Seed two ignored.",
            "belief_seed": {
                "belief_id": "second_should_drop",
                "weight_delta": 0.1,
                "spread_hint": "along_loyalty",
            },
            "breakthrough": None,
        },
    ]
    applied = apply_belief_seeds(w, rows)
    assert applied and applied["belief_id"] == "patron_obligation_over_qin_fear"
    # Quiet null ok
    assert apply_belief_seeds(w, [{"figure_id": "chunshen", "home": "chu", "belief_seed": None}]) == {}


def test_breakthrough_caps_and_cooldown():
    w = new_world()
    row = {
        "figure_id": "li_si",
        "home": "qin",
        "stance_lean": "defect",
        "loyalty_shift": 0.05,
        "event_tag": "personal_breakthrough",
        "utterance": "Flash.",
        "belief_seed": None,
        "breakthrough": {
            "kind": "loyalty_flip",
            "stance_tip": None,
            "tech_node": None,
            "trust_edge": "qin->chu",
            "note": "Probe.",
        },
    }
    t0 = get_trust(w.trust, "qin", "chu")
    a1 = apply_breakthrough(w, [row])
    assert a1.get("kind") == "loyalty_flip"
    assert get_trust(w.trust, "qin", "chu") <= t0 + 0.08 + 1e-9
    # cooldown drops second
    a2 = apply_breakthrough(w, [row])
    assert a2 == {}
    # invalid tech log-only path
    w.tick = int(w.tick) + 5
    row2 = dict(row)
    row2["breakthrough"] = {
        "kind": "tech_flash",
        "stance_tip": None,
        "tech_node": "not_a_real_node",
        "trust_edge": None,
        "note": "bad",
    }
    a3 = apply_breakthrough(w, [row2])
    assert a3.get("tech_invalid") == "not_a_real_node"


def test_stub_often_null_breakthrough():
    w = new_world()
    nulls = 0
    for _ in range(8):
        r = run_counsel_round(w, force_stub=True)
        if r.get("applied_breakthrough") in (None, False, {}):
            nulls += 1
    assert nulls >= 1


def test_tick_wires_counsel():
    w = new_world()
    tick(w)
    assert getattr(w, "counsel_log", None) is not None
    assert any(e.get("event_id") == "counsel" for e in w.episode) or w.counsel_log


def test_chips_and_backend_projection():
    w = new_world()
    chips = suggest_prompt_chips(w)
    assert 2 <= len(chips) <= 3
    assert all("God" not in c and "god" not in c for c in chips)
    s = initial_state()
    assert "counsel_log" in s and "counsel_prompt_chips" in s
    # No player ocean in projection
    assert "player_ocean" not in s


def test_flask_counsel_api():
    from server import app

    c = app.test_client()
    assert c.get("/api/health").status_code == 200
    r = c.post("/api/counsel", json={"prompt": "Among the courts: hold the south."})
    j = r.get_json()
    assert r.status_code == 200 and j.get("ok")
    assert j.get("state") is not None
    # Close
    r2 = c.post("/api/counsel", json={"prompt": "Close counsel: lean contribute.", "commit": True})
    assert r2.status_code == 200 and r2.get_json().get("ok")


def test_parse_clamps():
    rows = parse_counsel_payload(
        '[{"figure_id":"chunshen","home":"chu","stance_lean":"cooperate",'
        '"loyalty_shift":9,"event_tag":"nope","utterance":"ok"}]'
    )
    assert rows[0]["stance_lean"] == "contribute"
    assert rows[0]["loyalty_shift"] <= 0.25
    assert rows[0]["event_tag"] == "other"


def test_distinct_figure_stub_replies():
    """Two different figures must not share identical stub utterance bodies."""
    w = new_world()
    w.year = -240  # unlock Li Si
    r1 = run_counsel_round(
        w, prompt="Hold the line.", force_stub=True, player_initiated=True, figure_id="li_si"
    )
    w2 = new_world()
    w2.year = -240
    r2 = run_counsel_round(
        w2, prompt="Hold the line.", force_stub=True, player_initiated=True, figure_id="chu_nobility"
    )
    assert r1.get("ok") and r2.get("ok")
    u1 = r1["rows"][0]["utterance"]
    u2 = r2["rows"][0]["utterance"]
    assert u1 != u2
    body1 = u1.split("]: ", 1)[-1]
    body2 = u2.split("]: ", 1)[-1]
    assert body1 != body2


def test_chu_stub_not_legalist_seed():
    """Chu figures must never emit Qin-Legalist marker lines (ideology gate)."""
    assert _ideology_for(get_figure("chu_nobility")) == "chu_patronage_tianxia"
    assert _ideology_for(get_figure("kaolie")) == "chu_patronage_tianxia"
    # Banks themselves
    for line in IDEOLOGY_UTTERANCE_BANKS["chu_patronage_tianxia"]:
        low = line.lower()
        assert not any(m in low for m in LEGALIST_SEED_MARKERS), line
    for fid in ("kaolie", "chunshen", "chu_nobility"):
        for line in FIGURE_UTTERANCE_BANKS[fid]:
            low = line.lower()
            assert not any(m in low for m in LEGALIST_SEED_MARKERS), (fid, line)
    # Stub utterances across ticks/tags
    w = new_world()
    for fid in ("chu_nobility", "kaolie", "chunshen"):
        fig = get_figure(fid)
        for tick in range(0, 16):
            w.tick = tick
            for tag in (
                "patron_rebuke",
                "sync_appeal",
                "legalist_probe",
                "other",
                "hedge",
                "belief_cascade",
            ):
                for lean in ("contribute", "withhold", "defect", "hedge", "refuse"):
                    u = _utter(w, fig, tag, lean).lower()
                    assert not any(m in u for m in LEGALIST_SEED_MARKERS), (fid, tick, tag, u)
    # One-on-one round
    r = run_counsel_round(
        w, prompt="Speak of law and clear orders.", force_stub=True, player_initiated=True, figure_id="chu_nobility"
    )
    assert r.get("ok")
    utt = r["rows"][0]["utterance"].lower()
    assert not any(m in utt for m in LEGALIST_SEED_MARKERS), utt
    # Classic banned line must not appear
    assert "when laws are clear" not in utt
    assert "orders need few words" not in utt


def test_role_same_event_different_perspective():
    """Same event_tag → different stub body for ruler vs minister vs retainer."""
    w = new_world()
    w.year = -240
    tag = "sync_appeal"
    lean = "contribute"
    bodies = {}
    for fid in ("zhaoxiang", "li_si", "chu_nobility"):
        fig = get_figure(fid)
        assert fig and _speech_role_for(fig) in ("ruler", "minister", "retainer", "general")
        u = _utter(w, fig, tag, lean)
        body = u.split("]: ", 1)[-1]
        bodies[fid] = body
        # role tag visible in prefix
        assert _speech_role_for(fig) in u
    assert bodies["zhaoxiang"] != bodies["li_si"]
    assert bodies["li_si"] != bodies["chu_nobility"]
    assert bodies["zhaoxiang"] != bodies["chu_nobility"]
    # Role banks exist
    assert set(ROLE_UTTERANCE_BANKS) >= {"ruler", "minister", "general", "retainer"}
