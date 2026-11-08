"""Optional M2 tech surface — Tech worker owns engine/tech.py.

Engine core (tick / demo_flow / world) calls these hooks only.
If tech.py is mid-edit or missing a symbol, dynamics continue without M2.
Do not put phylogeny / Adoption Meter logic here.
"""

from __future__ import annotations

from typing import Any


def tick_tech(world: Any) -> dict[str, Any]:
    try:
        from .tech import tick_tech as _impl

        return dict(_impl(world) or {})
    except Exception:
        return {}


def tech_pressure_delta(world: Any) -> float:
    try:
        from .tech import tech_pressure_delta as _impl

        return float(_impl(world))
    except Exception:
        return 0.0


def tech_structural_damage(world: Any) -> tuple[bool, str]:
    try:
        from .tech import tech_structural_damage as _impl

        return _impl(world)
    except Exception:
        return False, ""


def tech_quorum_ok(world: Any, *, cohesion_ok: bool = True) -> tuple[bool, str]:
    try:
        from .tech import tech_quorum_ok as _impl

        return _impl(world, cohesion_ok=cohesion_ok)
    except Exception:
        return cohesion_ok, "tech_hooks: M2 unavailable — psych quorum only"


def recompute_tech(board: Any, *, levy_capacity: float = 0.6) -> Any:
    try:
        from .tech import recompute_tech as _impl

        return _impl(board, levy_capacity=levy_capacity)
    except Exception:
        return board