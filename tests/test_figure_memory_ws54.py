"""Figure memories, unusual comments, ally betrayal, King You era."""

from __future__ import annotations

from engine.conflict import _apply_ally_betrayal_spike, annex_state, resolve_attack
from engine.counsel import (
    FIGURE_UTTERANCE_BANKS,
    LEGALIST_SEED_MARKERS,
    run_counsel_round,
    suggest_prompt_chips,
    _ideology_for,
    _utter,
)
from engine.figure_memory import (
    MEMORY_CAP,
    ensure_figure_memories,
    memories_for,
    remember,
    snapshot_lines,
)
from engine.figures import figure_available_for_talk, get_figure
from engine.world import new_world


def test_figure_memories_seeded_and_capped():
    w = new_world()
    board = ensure_figure_memories(w)
    assert "kaolie" in board and len(board["kaolie"]) >= 1
    assert "king_you" in board
    for _ in range(12):
        remember(w, "kaolie", kind="raid", text=f"raid note {_}", salience=0.6)
    assert len(w.figure_memories["kaolie"]) <= MEMORY_CAP


def test_unusual_event_memory_on_annex():
    w = new_world()
    ensure_figure_memories(w)
    annex_state(w, "han", "qin")
    # living figures should have annex memory
    found = False
    for fid, rows in (w.figure_memories or {}).items():
        if any(r.get("kind") == "annex" for r in rows):
            found = True
            break
    assert found


def test_ally_betrayal_spike():
    w = new_world()
    b0 = float(w.agents["chu"].state.betrayal_memory)
    _apply_ally_betrayal_spike(w, "qi", "chu")
    assert float(w.agents["chu"].state.betrayal_memory) > b0
    assert any(e.get("event_id") == "ally_betrayal" for e in w.episode)
    assert w.pattern_reactions


def test_king_you_era_gate():
    w = new_world()
    # start year -260 → BCE 260; Kaolie talkable, You locked
    assert figure_available_for_talk(w, "kaolie")
    assert not figure_available_for_talk(w, "king_you")
    w.year = -238  # BCE 238
    assert not figure_available_for_talk(w, "kaolie")
    assert figure_available_for_talk(w, "king_you")
    assert "king_you" in FIGURE_UTTERANCE_BANKS
    fig = get_figure("king_you")
    assert fig and fig.get("speech_role") == "ruler"


def test_chu_not_legalist_and_chips_decluttered():
    w = new_world()
    chips = suggest_prompt_chips(w)
    assert 1 <= len(chips) <= 2
    assert all(len(c) < 80 for c in chips)
    fig = get_figure("chunshen")
    line = _utter(w, fig, "sync_appeal", "contribute").lower()
    for m in LEGALIST_SEED_MARKERS:
        assert m not in line


def test_projection_has_mil_tech_yield():
    from backend import initial_state
    st = initial_state()
    chu = st["agents"]["chu"]
    assert "geographic_yield" in chu and "military" in chu and "tech_adopt" in chu


def test_counsel_still_ok_with_memories():
    w = new_world()
    ensure_figure_memories(w)
    remember(w, "chunshen", kind="breakthrough", text="workshop flash", salience=0.8)
    r = run_counsel_round(w, force_stub=True)
    assert r["ok"] and r.get("rows")
