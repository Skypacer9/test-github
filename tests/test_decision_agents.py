"""WS-64/66: OCEAN figure decisions → court acts → world deltas.

Default path is rule-based (heuristic). Tests that exercise the LLM admission /
mock-complete injection path are marked ``llm`` and skipped in CI unless
``WS_RUN_LLM_TESTS=1``.
"""

from __future__ import annotations

import json
import os

import pytest

from engine.decision_agents import (
    apply_stance_decisions,
    clamp_decision,
    heuristic_decisions,
    mock_llm_decisions,
    obtain_decisions,
    parse_decisions_payload,
    run_decision_phase,
)
from engine.decision_llm import set_mock_complete
from engine.llm_gate import llm_decisions_enabled
from engine.tick import tick
from engine.world import new_world


def setup_function() -> None:
    set_mock_complete(None)
    os.environ.pop("WS_LLM_DECISIONS", None)
    os.environ.pop("WS_LLM_ENABLED", None)
    os.environ.pop("WS_COUNSEL_API_KEY", None)
    os.environ.pop("WS_FIELD_AI", None)
    os.environ["WS_DECISION_AGENTS"] = "1"
    os.environ["WS_DECISION_MODE"] = "heuristic"


@pytest.mark.rule
def test_clamp_and_parse_schema():
    row = clamp_decision(
        {
            "figure_id": "chunshen",
            "home": "chu",
            "stance": "cooperate",
            "alliance_lean": 1.7,
            "offensive_pref": "bogus",
            "invest_pref": "tech",
            "invest_target": "chu",
            "intervene_pref": "chu",
        }
    )
    assert row["stance"] == "contribute"
    assert row["alliance_lean"] == 1.0
    assert row["offensive_pref"] == "none"
    rows = parse_decisions_payload(json.dumps({"decisions": [row]}))
    assert len(rows) == 1
    assert rows[0]["figure_id"] == "chunshen"


@pytest.mark.rule
def test_heuristic_ocean_decisions_apply_stance():
    w = new_world()
    rows = heuristic_decisions(w, strategy="hezong")
    assert rows
    assert all("stance" in r and "alliance_lean" in r for r in rows)
    chu_rows = [r for r in rows if r["home"] == "chu"]
    assert chu_rows
    summary = apply_stance_decisions(w, rows)
    assert "chu" in summary["courts"]
    assert w.agents["chu"].intention.sticky_until >= w.tick


@pytest.mark.rule
def test_tick_runs_decision_phase_without_api_key():
    w = new_world()
    p0 = float(w.qin_pressure)
    tick(w)
    assert w.tick == 1
    phase = w.last_decision_phase
    assert isinstance(phase, dict)
    # Rule-AI default: heuristic (mock only if WS_DECISION_MODE=mock)
    assert phase.get("source") == "heuristic"
    assert "courts" in (phase.get("stance") or {})
    assert float(w.qin_pressure) != p0 or w.meso.cohesion is not None


@pytest.mark.rule
def test_llm_decisions_gate_off_by_default():
    assert llm_decisions_enabled() is False


@pytest.mark.rule
def test_mock_mode_and_field_ai():
    """Mock fixture path is still rule-shaped (no HTTP) — kept in default suite."""
    w = new_world()
    w.field_ai = True
    w.decision_strategy = "hezong"
    out = run_decision_phase(w, strategy="hezong", mode="mock", field_ai=True)
    assert out["source"] == "mock"
    assert out["stance"]["n_figures"] >= 1
    assert "field" in out


@pytest.mark.llm
def test_obtain_decisions_mock_complete_injection():
    """Opt-in: exercises decision_llm mock completer + LLM gate env (no live HTTP)."""
    w = new_world()

    def _fake(_snap: str):
        return [
            {
                "figure_id": "chunshen",
                "home": "chu",
                "stance": "contribute",
                "alliance_lean": 0.9,
                "offensive_pref": "none",
                "invest_pref": "mediation",
                "invest_target": "chu",
                "intervene_pref": "chu",
                "rationale_tag": "fixture",
            }
        ]

    set_mock_complete(_fake)
    os.environ["WS_LLM_ENABLED"] = "1"
    os.environ["WS_LLM_DECISIONS"] = "1"
    os.environ["WS_COUNSEL_API_KEY"] = "test-not-real"
    rows, src = obtain_decisions(w, strategy="hezong", mode="llm")
    assert src == "llm"
    assert any(r["figure_id"] == "chunshen" for r in rows)
    set_mock_complete(None)


@pytest.mark.rule
def test_mock_llm_strategy_signatures():
    w = new_world()
    hez = mock_llm_decisions(w, strategy="hezong")
    assert all(str(r["rationale_tag"]).startswith("mock:") for r in hez)
    anti = [r for r in hez if r["home"] != "qin"]
    assert anti
    peer = mock_llm_decisions(w, strategy="peer_preempt")
    hez_ally = sum(float(r["alliance_lean"]) for r in hez if r["home"] != "qin") / len(anti)
    peer_ally = sum(float(r["alliance_lean"]) for r in peer if r["home"] != "qin") / max(
        1, len([r for r in peer if r["home"] != "qin"])
    )
    assert hez_ally > peer_ally


@pytest.mark.rule
def test_circumstance_crisis_raises_alliance():
    from engine.decision_agents import board_situation, heuristic_decisions

    calm = new_world()
    crisis = new_world()
    crisis.qin_pressure = 85.0
    crisis.meso.cohesion = 30.0
    assert board_situation(crisis)["crisis"] is True
    calm_rows = heuristic_decisions(calm, strategy="peer_preempt")
    crisis_rows = heuristic_decisions(crisis, strategy="peer_preempt")
    calm_a = sum(float(r["alliance_lean"]) for r in calm_rows if r["home"] != "qin")
    crisis_a = sum(float(r["alliance_lean"]) for r in crisis_rows if r["home"] != "qin")
    assert crisis_a > calm_a


@pytest.mark.rule
def test_seven_state_figure_decisions():
    from engine.decision_agents import heuristic_decisions

    w = new_world()
    rows = heuristic_decisions(w, strategy="hezong")
    homes = {r["home"] for r in rows}
    assert homes >= {"qin", "chu", "qi", "zhao", "han", "wei", "yan"}
    assert len(rows) >= 7


@pytest.mark.rule
def test_speak_chips_strategy_ocean():
    from engine.counsel import suggest_prompt_chips

    w = new_world()
    w.decision_strategy = "hezong"
    chips = suggest_prompt_chips(w, n=4, figure_id="chunshen")
    assert 1 <= len(chips) <= 4
    blob = " ".join(chips).lower()
    assert "hezong" in blob or "contribute" in blob or "patron" in blob or "coalition" in blob


@pytest.mark.rule
def test_obtain_decisions_defaults_to_heuristic():
    w = new_world()
    rows, src = obtain_decisions(w, strategy="balanced", mode="auto")
    assert src == "heuristic"
    assert rows
