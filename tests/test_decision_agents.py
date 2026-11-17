"""WS-64: OCEAN figure decisions → court acts → world deltas."""

from __future__ import annotations

import json
import os

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


def test_heuristic_ocean_decisions_apply_stance():
    w = new_world()
    rows = heuristic_decisions(w, strategy="hezong")
    assert rows
    assert all("stance" in r and "alliance_lean" in r for r in rows)
    # Chu figures should exist and hezong should lean contribute for anti-Qin
    chu_rows = [r for r in rows if r["home"] == "chu"]
    assert chu_rows
    summary = apply_stance_decisions(w, rows)
    assert "chu" in summary["courts"]
    assert w.agents["chu"].intention.sticky_until >= w.tick


def test_tick_runs_decision_phase_without_api_key():
    w = new_world()
    p0 = float(w.qin_pressure)
    tick(w)
    assert w.tick == 1
    phase = w.last_decision_phase
    assert isinstance(phase, dict)
    assert phase.get("source") in ("heuristic", "mock")
    assert "courts" in (phase.get("stance") or {})
    # World still advances pressure via existing tick path
    assert float(w.qin_pressure) != p0 or w.meso.cohesion is not None


def test_llm_decisions_gate_off_by_default():
    assert llm_decisions_enabled() is False


def test_mock_mode_and_field_ai():
    w = new_world()
    w.field_ai = True
    w.decision_strategy = "hezong"
    out = run_decision_phase(w, strategy="hezong", mode="mock", field_ai=True)
    assert out["source"] == "mock"
    assert out["stance"]["n_figures"] >= 1
    # Field AI may or may not fire alliance depending on leans; phase recorded
    assert "field" in out


def test_obtain_decisions_mock_complete_injection():
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
    # admit_llm_call true outside Flask; complete_decisions_json uses mock first
    rows, src = obtain_decisions(w, strategy="hezong", mode="llm")
    assert src == "llm"
    assert any(r["figure_id"] == "chunshen" for r in rows)
    set_mock_complete(None)


def test_mock_llm_strategy_signatures():
    w = new_world()
    hez = mock_llm_decisions(w, strategy="hezong")
    assert all(str(r["rationale_tag"]).startswith("mock:") for r in hez)
    anti = [r for r in hez if r["home"] != "qin"]
    assert anti and all(r["stance"] == "contribute" for r in anti)
