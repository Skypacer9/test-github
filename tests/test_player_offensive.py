"""Player Offensive — attacker+target, capacity, soft cap, ally betrayal."""

from __future__ import annotations

import sys
from pathlib import Path

_SIM = Path(__file__).resolve().parents[1]
if str(_SIM) not in sys.path:
    sys.path.insert(0, str(_SIM))

from engine.conflict import offensive_capacity, resolve_attack
from engine.tick import player_offensive, tick
from engine.world import new_world


def test_offensive_attacker_and_target_pickers():
    w = new_world()
    # Ensure Chu can afford a march
    chu = w.agents["chu"]
    chu.grain = 80
    chu.treasury = 80
    chu.viability = 90
    before_trust = float(w.trust.get("chu->qin", 0.5))
    player_offensive(w, "chu", "qin")
    assert w.last_player_offensive_error is None, w.last_player_offensive_error
    assert w.last_player_offensive
    assert w.last_player_offensive.get("attacker") == "chu"
    assert w.last_player_offensive.get("defender") == "qin"
    assert int(w.player_offensive_actions_left) == 2
    assert int(w.player_offensive_fronts.get("chu", 0)) == 1
    # War chill
    assert float(w.trust.get("chu->qin", 1.0)) < before_trust


def test_offensive_ally_betrayal_spike():
    w = new_world()
    w.agents["chu"].grain = 80
    w.agents["chu"].treasury = 80
    w.agents["chu"].viability = 90
    w.agents["qi"].grain = 70
    w.agents["qi"].treasury = 70
    betrayal0 = float(w.agents["qi"].state.betrayal_memory)
    player_offensive(w, "chu", "qi")
    assert w.last_player_offensive_error is None, w.last_player_offensive_error
    assert float(w.agents["qi"].state.betrayal_memory) > betrayal0


def test_offensive_soft_cap_and_capacity_refuse():
    w = new_world()
    # Drain Yan — weak court cannot open a front
    yan = w.agents["yan"]
    yan.grain = 3
    yan.treasury = 3
    yan.viability = 20
    cap = offensive_capacity(w, "yan")
    assert cap["can_launch"] is False
    player_offensive(w, "yan", "zhao")
    assert w.last_player_offensive_error
    assert "capacity" in w.last_player_offensive_error.lower() or "lacks" in w.last_player_offensive_error.lower()

    # Soft global cap 3 — use three different strong attackers (avoids multi-front refuse)
    w2 = new_world()
    launches = (("chu", "qin"), ("qi", "zhao"), ("zhao", "yan"))
    for aid, tgt in launches:
        ag = w2.agents[aid]
        ag.grain = 95
        ag.treasury = 95
        ag.viability = 95
        player_offensive(w2, aid, tgt)
        assert w2.last_player_offensive_error is None, (aid, tgt, w2.last_player_offensive_error)
    assert int(w2.player_offensive_actions_left) == 0
    player_offensive(w2, "chu", "qin")
    assert w2.last_player_offensive_error and "budget" in w2.last_player_offensive_error.lower()
    # Advance refreshes soft cap + clears per-court fronts
    tick(w2)
    assert int(w2.player_offensive_actions_left) == 3
    assert w2.player_offensive_fronts == {}


def test_resolve_attack_force_scale_weakens():
    w = new_world()
    w.agents["chu"].grain = 80
    w.agents["chu"].treasury = 80
    full = resolve_attack(w, "chu", "qin", force_scale=1.0)
    w2 = new_world()
    w2.agents["chu"].grain = 80
    w2.agents["chu"].treasury = 80
    thin = resolve_attack(w2, "chu", "qin", force_scale=0.4)
    assert full.get("cancelled") is False
    assert thin.get("cancelled") is False
    assert float(thin["atk_pow"]) < float(full["atk_pow"])
