#!/usr/bin/env python3
"""Text-only ABM batch runner — N quarters with full Live-system quarterly log.

No Gradio / Flask / HTML. Prefer this one-liner for smoke + playtest transcripts:

  cd …/sim && python3 abm_run.py
  python3 abm_run.py --steps=8
  python3 abm_run.py -n 12 --intervene chu qi --alliance

Also: python3 cli.py -c "run 8"  ·  python3 -m engine.demo --steps=8
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


def _parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run N quarters of the Warring States ABM with a quarterly Live-system log"
    )
    p.add_argument(
        "-n",
        "--steps",
        type=int,
        default=8,
        help="Number of quarters to advance (default 8, max 80)",
    )
    p.add_argument(
        "--intervene",
        nargs="*",
        metavar="TARGET",
        help="Optional intervene targets before the run (qin/chu/qi)",
    )
    p.add_argument(
        "--alliance",
        action="store_true",
        help="Attempt alliance quorum once before the run",
    )
    p.add_argument(
        "--short",
        type=int,
        nargs="?",
        const=8,
        default=None,
        metavar="N",
        help="Arm Short Demo flavor (no calendar lock)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    # Local imports so `python3 abm_run.py` works from sim/
    from backend import (
        advance_quarter,
        arm_short_demo,
        attempt_alliance,
        fresh_run,
        intervene_targets,
    )
    from cli import print_quarterly_log

    n = max(1, min(int(args.steps), 80))
    state: dict[str, Any] = fresh_run()
    print("Warring States — text ABM (no UI)")
    print(f"Batch: {n} quarters · Live systems + Partial demo/sat/manpower stubs")
    print_quarterly_log(state)  # tick=0 baseline

    if args.short is not None:
        state = arm_short_demo(state, int(args.short))
        print(f"  Short Demo armed (horizon={int(args.short)}; no calendar lock)")

    if args.intervene is not None:
        targets = [t.lower() for t in (args.intervene or ["chu"])]
        bad = [t for t in targets if t not in ("qin", "chu", "qi")]
        if bad:
            print(f"  refuse intervene targets {bad} (need qin/chu/qi)", file=sys.stderr)
            return 2
        state, msgs, err = intervene_targets(state, targets)
        if err:
            print(f"  ! {err}")
        print(f"  intervened: {targets}")
        for m in msgs[-4:]:
            text = (m.get("content") or "").replace("**", "")
            if text:
                print(f"  · {text[:140]}")

    if args.alliance:
        state, msgs, err = attempt_alliance(state)
        if err:
            print(f"  ! {err}")
        print(
            f"  alliance → quorum_ok={state.get('quorum_ok')} "
            f"cohesion={float(state.get('alliance_cohesion') or 0):.1f}"
        )
        for m in msgs[-3:]:
            text = (m.get("content") or "").replace("**", "")
            if text:
                print(f"  · {text[:140]}")

    for i in range(n):
        state, msgs = advance_quarter(state)
        print_quarterly_log(state)
        for m in msgs:
            text = (m.get("content") or "").replace("**", "")
            if "Qin pressure" in text or "Belief contagion" in text or "soft-lock" in text.lower():
                print(f"  · {text[:160]}")
        if state.get("run_ended"):
            print(f"  soft-lock after {i + 1} advances (tick={state.get('tick')})")
            break
    else:
        print(f"  done tick={state.get('tick')} pathway={state.get('pathway_soft')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
