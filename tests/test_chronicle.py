"""Cultural chronicle — emergent pattern + resentment tone, not inevitability."""

from __future__ import annotations

from engine.chronicle import (
    CHRONICLE_EVERY_N,
    assess_cultural_pattern,
    chronicle_backend_name,
    maybe_write_chronicle,
    stub_chronicle,
)
from engine.conflict import annex_state
from engine.tick import attempt_alliance, tick
from engine.trust import set_trust
from engine.world import new_world


def test_stub_english_no_cjk_and_not_destiny():
    w = new_world()
    w.meso.cohesion = 75
    w.meso.shared_identity = 60
    w.meso.pathway_soft = "chu_fiction"
    text = stub_chronicle(w, reason="test")
    assert text
    assert not any("\u4e00" <= ch <= "\u9fff" for ch in text)
    assert "not a locked destiny" in text.lower() or "among several" in text.lower()
    # Must state an assessed cultural reading — not assume renaissance
    assert "cultural state reading:" in text.lower()


def test_chu_path_does_not_hardcode_renaissance():
    """Chu pathway label alone must not force renaissance/syncretism."""
    w = new_world()
    w.meso.pathway_soft = "chu_fiction"
    w.meso.cohesion = 50
    w.meso.shared_identity = 40
    for ag in w.agents.values():
        ag.state.resentment = 0.55  # bitter
    p = assess_cultural_pattern(w, reason="cadence")
    assert not p["renaissance_earned"]
    assert not p["syncretic_earned"]
    assert p["state"] not in ("craft_renaissance", "syncretic_bloom")
    text = stub_chronicle(w, reason="cadence").lower()
    assert "renaissance" not in text
    # bitterness / realism should color narration
    assert p["tone"] in ("bitter", "hard")
    assert any(k in text for k in ("bitter", "realist", "resent", "hard realism", "unsentimental", "cold"))


def test_high_resentment_bitter_tone():
    w = new_world()
    for ag in w.agents.values():
        ag.state.resentment = 0.7
    w.meso.cohesion = 40
    p = assess_cultural_pattern(w)
    assert p["tone"] == "bitter"
    assert p["resentment"] >= 0.55
    text = stub_chronicle(w, reason="cadence").lower()
    assert "bitter" in text or "realism" in text or "resent" in text


def test_earned_syncretic_bloom_and_renaissance():
    w = new_world()
    w.meso.cohesion = 78
    w.meso.shared_identity = 55
    w.meso.pathway_soft = "chu_fiction"
    w.qin_pressure = 40
    for ag in w.agents.values():
        ag.state.resentment = 0.2
        ag.annexed = False
    set_trust(w.trust, "chu", "qi", 0.7)
    set_trust(w.trust, "qi", "chu", 0.65)
    # Recent sync counsel + breakthrough episode
    w.episode.append({"event_id": "counsel", "action": "sync_appeal", "text": "sync"})
    w.episode.append({"event_id": "counsel", "action": "belief_cascade", "text": "belief"})
    p1 = assess_cultural_pattern(w)
    assert p1["syncretic_earned"]
    assert p1["state"] in ("syncretic_bloom", "craft_renaissance", "plural_contest")
    # Add tech burst → renaissance earned
    w.episode.append({"event_id": "m2_breakthrough", "action": "eureka", "text": "qin:iron"})
    p2 = assess_cultural_pattern(w)
    assert p2["renaissance_earned"]
    assert p2["state"] == "craft_renaissance"
    text = stub_chronicle(w, reason="cadence").lower()
    assert "renaissance" in text or "craft" in text
    assert p2["tone"] in ("generative", "warm")


def test_pathway_is_hint_not_sole_key():
    w = new_world()
    w.meso.cohesion = 70
    # Same warm/bitter setups under different pathway labels
    for ag in w.agents.values():
        ag.state.resentment = 0.65
    states = set()
    for path in ("qin_path", "stalemate", "other", "chu_fiction"):
        w.meso.pathway_soft = path
        states.add(assess_cultural_pattern(w)["tone"])
    assert "bitter" in states or "hard" in states


def test_maybe_write_force_and_cadence():
    w = new_world()
    assert chronicle_backend_name() in ("stub", "llm")
    r = maybe_write_chronicle(w, reason="test", force=True)
    assert r and r["ok"] and w.chronicle_log
    assert r.get("cultural_state")
    assert any(e.get("event_id") == "chronicle" for e in w.episode)

    w2 = new_world()
    for _ in range(CHRONICLE_EVERY_N):
        tick(w2)
    assert w2.chronicle_log, "expected cadence chronicle within N advances"


def test_annex_and_alliance_triggers():
    w = new_world()
    n0 = len(w.chronicle_log or [])
    annex_state(w, "han", "wei")
    assert len(w.chronicle_log) > n0

    w3 = new_world()
    for ag in w3.agents.values():
        if ag.bloc == "anti_qin":
            ag.intention.current = "cooperate"
            ag.state.resentment = 0.15
            ag.state.betrayal_memory = 0.15
    w3.meso.cohesion = 75
    w3.qin_pressure = 35
    w3.alliance_attempt_actions_left = 1
    n1 = len(w3.chronicle_log or [])
    attempt_alliance(w3)
    if any(e.get("action") == "quorum_success" for e in w3.episode if e.get("event_id") == "alliance"):
        assert len(w3.chronicle_log) > n1


def test_backend_projects_chronicle():
    from backend import advance_quarter, initial_state

    s = initial_state()
    assert "chronicle_log" in s
    s2, msgs = advance_quarter(s)
    assert "chronicle_log" in s2
    assert "chronicle_mode" in s2
    # Every Advance is due — wry Chronicler line in projection + chat msgs
    assert s2.get("chronicle_log"), "Advance must append chronicle when due"
    assert any("Chronicler" in (m.get("content") or "") for m in msgs)
    assert (s2.get("advance_dialogue") or {}).get("speaker") == "Chronicler"
    assert (s2.get("advance_dialogue") or {}).get("text")
    # Second Advance also writes (not buried / not skipped)
    s3, msgs3 = advance_quarter(s2)
    assert len(s3.get("chronicle_log") or []) >= 2
    assert any("Chronicler" in (m.get("content") or "") for m in msgs3)


def test_html_has_chronicle_panel():
    html = open("static/index.html", encoding="utf-8").read()
    assert "chronicle-log" in html
    assert "Cultural chronicle" in html
