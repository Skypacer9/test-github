"""Smoke: text ABM batch exits 0 and quarterly log covers Live + Partial stubs."""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

_SIM = Path(__file__).resolve().parents[1]
_ROOT = _SIM.parent
for pth in (_ROOT, _SIM):
    if str(pth) not in sys.path:
        sys.path.insert(0, str(pth))


def test_abm_run_exits_zero_and_logs_systems():
    from abm_run import main as abm_main

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = abm_main(["--steps=3"])
    out = buf.getvalue()
    assert rc == 0
    # Three advanced quarters + tick=0 baseline header
    assert out.count("═══ tick=") >= 4
    for needle in (
        "who_vs_qin",
        "intentions:",
        "PAS:",
        "qin_pressure=",
        "cohesion=",
        "quorum=",
        "pathway=",
        "trust★:",
        "packets:",
        "contagion:",
        "Chu patron:",
        "M1:",
        "M4:",
        "M2:",
        "PLACEHOLDER demo/sat/manpower:",
        "dials:",
    ):
        assert needle in out, f"missing quarterly log line for {needle!r}"


def test_cli_run_prints_quarterly_log():
    from cli import main as cli_main

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(["-c", "run 2"])
    out = buf.getvalue()
    assert rc == 0
    assert out.count("═══ tick=") >= 2
    assert "Live-system quarterly log" in out
