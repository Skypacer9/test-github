"""CLI demo — batch smoke with quarterly Live-system log, or full text REPL.

Batch:
  cd …/sim && python3 -m engine.demo
  python3 -m engine.demo --steps=8
  python3 -m engine.demo --steps=6 --intervene --alliance

Preferred one-liner (same quarterly log shape):
  python3 abm_run.py --steps=8

Interactive playtest (all mechanisms):
  python3 -m engine.demo --repl
  # or: python3 cli.py
"""

from __future__ import annotations

import json
import os
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--repl" in argv or "--cli" in argv:
        cleaned = [a for a in argv if a not in ("--repl", "--cli")]
        try:
            from cli import main as cli_main  # type: ignore
        except ImportError:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if root not in sys.path:
                sys.path.insert(0, root)
            from cli import main as cli_main  # type: ignore
        return int(cli_main(cleaned))

    # Delegate batch quarterly log to abm_run (single source of truth)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    steps = 4
    do_intervene = "--intervene" in argv
    do_alliance = "--alliance" in argv
    do_json = "--json" in argv
    for a in argv:
        if a.startswith("--steps="):
            steps = int(a.split("=", 1)[1])

    from abm_run import main as abm_main

    abm_argv: list[str] = [f"--steps={steps}"]
    if do_intervene:
        abm_argv.extend(["--intervene", "chu"])
    if do_alliance:
        abm_argv.append("--alliance")
    rc = int(abm_main(abm_argv))

    if do_json:
        from engine.world import new_world
        from engine.tick import tick

        # Tiny world dump for debugging (fresh short run, not the abm state)
        w = new_world()
        for _ in range(min(2, steps)):
            tick(w)
        print(json.dumps(w.to_dict(), indent=2)[:2000])

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
