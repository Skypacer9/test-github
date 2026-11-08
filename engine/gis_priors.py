"""Load vault GIS/physics priors and map ordinals → M4 scalars.

Honesty: seed WGS84 + Zhengguo grade are the only concrete survey-ish numbers
in-store. Everything else is an ordinal rank with an explicit linear map.
Do not treat outputs as DEM / pathfinding / GPS precision.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parents[1] / "data" / "gis_physics_priors.json"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (km), R=6371 — derived metric, not a road length."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def load_priors() -> dict[str, Any]:
    with _DATA.open(encoding="utf-8") as f:
        raw = json.load(f)
    # Refresh derived distance from seed coords (single source of truth).
    pts = raw.get("seed_points_wgs84") or {}
    ying = pts.get("ying_jinancheng") or {}
    xian = pts.get("xianyang") or {}
    if ying and xian:
        km = round(
            _haversine_km(
                float(ying["lat"]),
                float(ying["lon"]),
                float(xian["lat"]),
                float(xian["lon"]),
            ),
            1,
        )
        raw.setdefault("derived_distances_km", {})
        raw["derived_distances_km"]["ying_xianyang_haversine"] = {
            "from": "ying_jinancheng",
            "to": "xianyang",
            "km": km,
            "method": "haversine_R6371",
            "theater_scale_km": 800.0,
            "note": "Derived from vault seed coords only — not a digitized road length.",
        }
    return raw


def ordinal_unit(rank: float, *, lo: float = 1.0, hi: float = 5.0) -> float:
    """Map integer-ish rank on [lo, hi] → unit interval. Documented ordinal→scalar."""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (float(rank) - lo) / (hi - lo)))


def soft_scalar(unit: float, *, floor: float, span: float) -> float:
    """unit∈[0,1] → [floor, floor+span]. Keeps gameplay away from hard 0/1."""
    return round(float(floor) + float(span) * max(0.0, min(1.0, float(unit))), 4)


def silt_irrigation_index(priors: dict[str, Any] | None = None) -> float:
    """Zhengguo ~0.6‰ grade → index in [0,1] via min(1, permille/1.0)."""
    p = priors or load_priors()
    grade = float(
        ((p.get("canal_physics") or {}).get("zhengguo_grade_permille") or {}).get(
            "value", 0.6
        )
    )
    return round(min(1.0, max(0.0, grade / 1.0)), 4)


def capital_axis_distance_unit(priors: dict[str, Any] | None = None) -> float:
    """Ying–Xianyang haversine / 800 km theater scale → [0,1]."""
    p = priors or load_priors()
    d = (p.get("derived_distances_km") or {}).get("ying_xianyang_haversine") or {}
    km = float(d.get("km") or 544.7)
    scale = float(d.get("theater_scale_km") or 800.0)
    return round(min(1.0, max(0.0, km / scale)), 4)


def node_scalars(node_id: str, priors: dict[str, Any] | None = None) -> dict[str, float]:
    """Build defense/march/extraction/levy/qin_pressure for one M4 node from ordinals."""
    p = priors or load_priors()
    ranks_meta = p.get("ordinal_ranks") or {}
    scale = ranks_meta.get("scale") or {"lo": 1, "hi": 5}
    lo, hi = float(scale.get("lo", 1)), float(scale.get("hi", 5))
    node = (ranks_meta.get("nodes") or {}).get(node_id)
    if not node:
        raise KeyError(f"unknown GIS prior node: {node_id}")
    sm = p.get("scalar_map") or {}

    def _map(key: str, floor_key: str, span_key: str) -> float:
        u = ordinal_unit(float(node[key]), lo=lo, hi=hi)
        return soft_scalar(
            u, floor=float(sm.get(floor_key, 0.25)), span=float(sm.get(span_key, 0.65))
        )

    defense = _map("defense", "defense_floor", "defense_span")
    march = _map("march", "march_floor", "march_span")
    extraction = _map("extraction", "extraction_floor", "extraction_span")
    levy = _map("levy_geo", "levy_floor", "levy_span")
    # Signed Qin pressure: rank 1 → floor (−0.2), rank 5 → floor+span
    qpm = soft_scalar(
        ordinal_unit(float(node["qin_pressure"]), lo=lo, hi=hi),
        floor=float(sm.get("qin_pressure_floor", -0.2)),
        span=float(sm.get("qin_pressure_span", 0.85)),
    )

    # Corridor: blend low ordinal march with capital-axis distance unit.
    if node_id == "central_plain_corridor":
        blend = float(sm.get("corridor_distance_march_blend", 0.35))
        dist_u = capital_axis_distance_unit(p)
        # Longer documented capital axis ⇒ slightly higher corridor march friction
        # once projection is past the passes (still low vs Hangu).
        march = round((1.0 - blend) * march + blend * soft_scalar(
            dist_u, floor=float(sm.get("march_floor", 0.25)), span=0.45
        ), 4)

    # Guanzhong levy: silt-irrigation index from canal grade nudges geographic yield.
    if node_id == "guanzhong_levy":
        silt = silt_irrigation_index(p)
        levy = round(min(0.95, levy + 0.06 * silt), 4)
        extraction = round(min(0.95, extraction + 0.04 * silt), 4)

    # Chu riverine: Ying ~16 km² capital footprint as areal-depth prior (not wall GPS).
    if node_id == "chu_riverine":
        area = float(
            ((p.get("seed_points_wgs84") or {}).get("ying_jinancheng") or {}).get(
                "approx_area_km2", 16.0
            )
        )
        # Soft depth: 16 km² → ~0.53 on a 30 km² reference; tiny defense nudge only.
        area_u = min(1.0, area / 30.0)
        defense = round(min(0.95, defense + 0.04 * area_u), 4)

    return {
        "defense_mod": defense,
        "march_cost": march,
        "extraction_mod": extraction,
        "levy_mod": levy,
        "qin_pressure_mod": qpm,
    }


def inventory_summary() -> dict[str, Any]:
    """Compact inventory for docs / CLI honesty cards."""
    p = load_priors()
    d = (p.get("derived_distances_km") or {}).get("ying_xianyang_haversine") or {}
    return {
        "seed_points": list((p.get("seed_points_wgs84") or {}).keys()),
        "ying_xianyang_km": d.get("km"),
        "zhengguo_grade_permille": (
            (p.get("canal_physics") or {}).get("zhengguo_grade_permille") or {}
        ).get("value"),
        "silt_irrigation_index": silt_irrigation_index(p),
        "capital_axis_distance_unit": capital_axis_distance_unit(p),
        "ordinal_nodes": list(((p.get("ordinal_ranks") or {}).get("nodes") or {}).keys()),
        "honesty": p.get("honesty"),
        "data_path": str(_DATA),
    }
