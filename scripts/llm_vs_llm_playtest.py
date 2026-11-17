#!/usr/bin/env python3
"""WS-65/66 strategy playtest — defaults to rule-based (heuristic) AI.

  # Default (CI-safe): heuristic OCEAN decisions, no LLM HTTP
  python3 scripts/llm_vs_llm_playtest.py
  python3 scripts/llm_vs_llm_playtest.py --mode heuristic --n 8 --horizon 40

  # Fixture path (still no HTTP):
  python3 scripts/llm_vs_llm_playtest.py --mode mock

  # Live LLM (opt-in):
  WS_LLM_DECISIONS=1 WS_LLM_ENABLED=1 WS_COUNSEL_API_KEY=… \\
    python3 scripts/llm_vs_llm_playtest.py --mode llm --n 4 --horizon 24

Writes JSON beside this script when --out is set; otherwise prints summary.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="LLM-vs-LLM / mock strategy playtest")
    p.add_argument("--n", type=int, default=8, help="runs per strategy (small N for cost)")
    p.add_argument("--horizon", type=int, default=40, help="max quarters per run")
    p.add_argument(
        "--mode",
        choices=("auto", "mock", "heuristic", "llm"),
        default="heuristic",
        help="decision source (default: heuristic / rule-AI; llm is opt-in)",
    )
    p.add_argument(
        "--strategies",
        nargs="*",
        default=["hezong", "peer_preempt", "qin_preempt", "fluid", "develop"],
    )
    p.add_argument("--out", type=str, default="", help="optional JSON output path")
    args = p.parse_args(argv)

    from engine.llm_gate import api_key_present, llm_decisions_enabled
    from engine.opponent_ai import monte_carlo_strategies

    mode = args.mode
    live_blocked = False
    # Prefer rule-AI unless explicitly asking for llm/auto with gates on.
    rule_default = (os.environ.get("WS_PLAYTEST_RULE_AI") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
        "",
    )
    if mode == "auto":
        if llm_decisions_enabled() and not rule_default:
            mode = "llm"
        else:
            mode = "heuristic"
            live_blocked = not llm_decisions_enabled()
    elif mode == "llm" and not llm_decisions_enabled():
        print(
            "LIVE LLM blocked: need WS_LLM_DECISIONS=1 + WS_LLM_ENABLED=1 + "
            "WS_COUNSEL_API_KEY. Falling back to heuristic (rule-AI).",
            file=sys.stderr,
        )
        mode = "heuristic"
        live_blocked = True
    if mode == "llm" and not api_key_present():
        live_blocked = True
    if mode in ("heuristic", "mock"):
        live_blocked = live_blocked or not api_key_present()

    result = monte_carlo_strategies(
        list(args.strategies),
        n_per=max(1, int(args.n)),
        horizon=max(4, int(args.horizon)),
        mode=mode,
    )
    result["live_llm_blocked"] = bool(live_blocked or result.get("live_llm_blocked"))
    result["enable_hint"] = (
        "export WS_LLM_ENABLED=1 WS_LLM_DECISIONS=1 WS_COUNSEL_API_KEY=… "
        "(optional WS_DECISION_MODEL / WS_DECISION_MAX_TOKENS)"
    )

    text = json.dumps(result, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {out_path}")
    print("final_pct", result["final_pct"])
    print("ever_pct", result["ever_pct"])
    print("by_strategy", json.dumps(result["by_strategy"], indent=2))
    print("act_kinds", result["act_kinds"])
    print("sources", result["sources"])
    print("mode", result["mode"], "live_blocked", result["live_llm_blocked"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
