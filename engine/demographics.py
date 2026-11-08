"""PLACEHOLDER demographics + population satisfaction + available manpower.

Honesty: these are uncalibrated stubs so Field / CLI / Flask have live meters
to wire against. Formulas are NOT historical demography, NOT census priors,
and MUST NOT be treated as calibrated M1. Math-doc worker owns real models later.

Seed ordinals in seed_demographics() follow docs/economic-grounding-sources.md
§3 (Liye/Shuihudi, Baoshan, Linzi mint, Guanzi 轻重) — relative [0,1] ranks
only; still PLACEHOLDER / uncalibrated.

TODO(math-doc): replace tick drift with sourced recovery / migration /
levy-exhaustion schedules (or drop if unused). Seeds are already source-aligned
ordinals, not anonymous flavor.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# Featured courts first; Zhao/Han/Wei/Yan get thin scaffolds.
COURT_IDS: tuple[str, ...] = ("qin", "chu", "qi", "zhao", "han", "wei", "yan")

SourceTier = Literal["archaeological", "textual_ideal", "placeholder"]

# Live meter fields used by tick / hooks / CLI (floats in [0, 1]).
_LIVE_FLOAT_KEYS: tuple[str, ...] = (
    "population",
    "levy_base",
    "urban_share",
    "satisfaction",
    "available_manpower",
    "monetization_index",
    "grain_share_of_levy",
    "registration_intensity",
)


@dataclass
class CourtDemographics:
    """Per-court coarse knobs — all placeholder scalars in [0, 1] unless noted.

    Live meters (ordinal stubs; see economic-grounding-sources.md §3):
      population: relative headcount prior (not absolute census).
      levy_base: fiscal/recruit extractable share prior (feeds soft levy hook).
      urban_share: urban vs rural mix prior (flavor + tiny satisfaction drift).
      satisfaction: population mood 0–1 (placeholder; not calibrated unrest model).
      available_manpower: fieldable men relative prior 0–1 (soft military hook).

    Optional provenance / fiscal-texture meta (parallel keys; do not rename
    levy_capacity). Safe extras for CLI/Flask — ignored by soft hooks.
      monetization_index: coin/mint intensity prior (not GDP).
      grain_share_of_levy: grain-forward vs cash/cloth mix prior.
      registration_intensity: household/上计 extractability prior.
      source_tier: archaeological | textual_ideal | placeholder.
    """

    population: float = 0.5
    levy_base: float = 0.5
    urban_share: float = 0.35
    satisfaction: float = 0.55
    available_manpower: float = 0.45
    monetization_index: float = 0.4
    grain_share_of_levy: float = 0.5
    registration_intensity: float = 0.45
    source_tier: str = "placeholder"

    def clamp(self) -> None:
        self.population = max(0.05, min(1.0, float(self.population)))
        self.levy_base = max(0.05, min(1.0, float(self.levy_base)))
        self.urban_share = max(0.0, min(1.0, float(self.urban_share)))
        self.satisfaction = max(0.0, min(1.0, float(self.satisfaction)))
        self.available_manpower = max(0.0, min(1.0, float(self.available_manpower)))
        self.monetization_index = max(0.0, min(1.0, float(self.monetization_index)))
        self.grain_share_of_levy = max(0.0, min(1.0, float(self.grain_share_of_levy)))
        self.registration_intensity = max(
            0.0, min(1.0, float(self.registration_intensity))
        )
        tier = str(self.source_tier or "placeholder").strip().lower()
        if tier not in ("archaeological", "textual_ideal", "placeholder"):
            tier = "placeholder"
        self.source_tier = tier

    def to_dict(self) -> dict[str, Any]:
        self.clamp()
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "CourtDemographics":
        if not isinstance(raw, dict):
            return cls()
        kwargs: dict[str, Any] = {}
        for k in cls.__dataclass_fields__:
            if k not in raw or raw[k] is None:
                continue
            if k == "source_tier":
                kwargs[k] = str(raw[k])
            elif k in _LIVE_FLOAT_KEYS:
                kwargs[k] = float(raw[k])
        obj = cls(**kwargs)
        obj.clamp()
        return obj


@dataclass
class DemographicsBoard:
    """World-owned placeholder board — Partial / uncalibrated.

    Court seeds are source-aligned ordinals (economic-grounding-sources.md §3),
    still PLACEHOLDER magnitudes — not a census.
    """

    courts: dict[str, CourtDemographics] = field(default_factory=dict)
    # World rollups (means) — mirrors for UI without recomputing clientside
    mean_satisfaction: float = 0.55
    mean_manpower: float = 0.45
    mean_population: float = 0.5
    honesty: str = (
        "PLACEHOLDER demographics/satisfaction/manpower — uncalibrated stubs; "
        "seeds are source-aligned ordinals (economic-grounding-sources.md), "
        "not census; tiny soft hooks only; not historical M1."
    )

    def clamp(self) -> None:
        for c in self.courts.values():
            c.clamp()
        self._rollup()

    def _rollup(self) -> None:
        if not self.courts:
            return
        n = max(1, len(self.courts))
        self.mean_satisfaction = round(
            sum(c.satisfaction for c in self.courts.values()) / n, 4
        )
        self.mean_manpower = round(
            sum(c.available_manpower for c in self.courts.values()) / n, 4
        )
        self.mean_population = round(
            sum(c.population for c in self.courts.values()) / n, 4
        )

    def to_dict(self) -> dict[str, Any]:
        self.clamp()
        return {
            "courts": {k: v.to_dict() for k, v in self.courts.items()},
            "mean_satisfaction": self.mean_satisfaction,
            "mean_manpower": self.mean_manpower,
            "mean_population": self.mean_population,
            "honesty": self.honesty,
            "placeholder": True,
            "seed_grounding": "economic-grounding-sources.md§3",
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "DemographicsBoard":
        if not isinstance(raw, dict):
            return seed_demographics()
        courts_raw = raw.get("courts") or {}
        courts = {
            cid: CourtDemographics.from_dict(payload)
            for cid, payload in courts_raw.items()
        }
        if not courts:
            return seed_demographics()
        board = cls(courts=courts)
        board.clamp()
        return board


def seed_demographics() -> DemographicsBoard:
    """Relative [0,1] ordinal priors — NOT census.

    Ranks follow docs/economic-grounding-sources.md §3. Magnitudes stay soft
    PLACEHOLDER; only ordering is source-aligned.
    """
    # --- Featured courts (comments cite grounding doc corpora) ---------------
    priors: dict[str, dict[str, Any]] = {
        # Qin: 里耶秦简 + 睡虎地秦简 — 户籍/墾田/稅田 + 上计 machine;
        # grain-forward extract; high registration → top levy + manpower.
        # Monetization lower for *core* extract (cash/cloth secondary: 金布律).
        "qin": {
            "population": 0.74,  # high: dense Guanzhong + conquered depth
            "levy_base": 0.84,  # highest among seven
            "urban_share": 0.38,  # mid (not mint-capital apex)
            "satisfaction": 0.50,  # mid: extract stress vs granary competence
            "available_manpower": 0.78,  # highest: registration × levy
            "monetization_index": 0.28,
            "grain_share_of_levy": 0.82,
            "registration_intensity": 0.90,
            "source_tier": "archaeological",
        },
        # Chu: 包山楚简 — patronage / lineage adjudication, not national census;
        # wide areal pop, mid-low *uniform* levy, dispersed riverine urban.
        "chu": {
            "population": 0.86,  # highest areal (wide south)
            "levy_base": 0.42,  # mid-low uniform extract (aristocratic networks)
            "urban_share": 0.24,  # lower: dispersed riverine
            "satisfaction": 0.60,  # mid-high when patronage holds (brittle)
            "available_manpower": 0.48,  # mid: large pop × weaker extract
            "monetization_index": 0.45,
            "grain_share_of_levy": 0.55,
            "registration_intensity": 0.35,
            "source_tier": "archaeological",
        },
        # Qi: 临淄铸钱/冶铸 + 《管子》轻重 (国蓄/海王/山至数…) — high urban +
        # wealth/Guanzi technics levy; monetization high; not Shang Yang fa mass.
        "qi": {
            "population": 0.64,  # mid-high
            "levy_base": 0.72,  # high (wealth + Guanzi-style; below Qin machine)
            "urban_share": 0.52,  # highest among big three (Linzi mint capital)
            "satisfaction": 0.62,  # mid-high: commerce + light-heavy provisioning ideal
            "available_manpower": 0.46,  # mid: wealth ≠ mass fa conscription
            "monetization_index": 0.85,
            "grain_share_of_levy": 0.40,
            "registration_intensity": 0.55,
            "source_tier": "textual_ideal",
        },
        # Thin courts: settlement/workshop lore + Sanjin/Yan coin intensity;
        # no polity-complete household dump — source_tier stays placeholder.
        # 侯马铸铜 / 新郑郑韩 iron: Sanjin mid fiscal craft + high coin gloss.
        "zhao": {
            "population": 0.50,  # mid
            "levy_base": 0.54,  # mid (Sanjin fiscal craft)
            "urban_share": 0.30,
            "satisfaction": 0.42,  # lower under Qin pressure / war
            "available_manpower": 0.42,
            "monetization_index": 0.70,
            "grain_share_of_levy": 0.50,
            "registration_intensity": 0.48,
            "source_tier": "placeholder",
        },
        "han": {
            "population": 0.32,  # smallest among seven
            "levy_base": 0.48,  # mid (thin state; workshop cities)
            "urban_share": 0.34,  # mid workshop-city gloss (新郑)
            "satisfaction": 0.40,
            "available_manpower": 0.30,
            "monetization_index": 0.65,
            "grain_share_of_levy": 0.48,
            "registration_intensity": 0.45,
            "source_tier": "placeholder",
        },
        "wei": {
            "population": 0.46,  # mid
            "levy_base": 0.56,  # mid-high of thin courts (Sanjin craft)
            "urban_share": 0.36,  # mid workshop cities
            "satisfaction": 0.44,
            "available_manpower": 0.40,
            "monetization_index": 0.72,
            "grain_share_of_levy": 0.50,
            "registration_intensity": 0.50,
            "source_tier": "placeholder",
        },
        # Yan: 燕下都明刀 hoards — high coin intensity; mid-low levy/urban.
        "yan": {
            "population": 0.40,  # mid-low
            "levy_base": 0.40,  # mid-low
            "urban_share": 0.22,  # lower
            "satisfaction": 0.43,
            "available_manpower": 0.34,
            "monetization_index": 0.78,
            "grain_share_of_levy": 0.45,
            "registration_intensity": 0.38,
            "source_tier": "placeholder",
        },
    }
    courts = {cid: CourtDemographics(**priors[cid]) for cid in COURT_IDS}
    board = DemographicsBoard(courts=courts)
    board.clamp()
    return board


def tick_demographics(world: Any) -> dict[str, Any]:
    """PLACEHOLDER quarterly drift — saturating approach to sat/manpower targets.

    Form: EMA / room-to-target (not tiny additive linear-only nudges).
    Magnitudes still PLACEHOLDER; seed ordinals from economic-grounding-sources.md.
    TODO(math-doc): real recovery, migration, levy exhaustion, epidemic layers.
    """
    from .nonlinear import clamp

    board: DemographicsBoard = getattr(world, "demographics", None) or seed_demographics()
    famine = float(getattr(world.world, "famine_shock", 0.0) or 0.0)
    pressure = float(getattr(world, "qin_pressure", 0.0) or 0.0) / 100.0
    for cid, court in board.courts.items():
        # Target satisfaction (bounded); famine/pressure pull target down nonlinearly
        base_sat = 0.55
        ag = (getattr(world, "agents", {}) or {}).get(cid)
        famine_hit = 0.35 * (famine ** 1.2)  # accelerating famine pain
        if ag is not None and getattr(ag, "bloc", "") == "anti_qin":
            target_sat = base_sat - famine_hit - 0.25 * (pressure ** 1.1)
        elif cid == "qin":
            target_sat = base_sat - 0.8 * famine_hit + 0.12 * pressure
        else:
            target_sat = base_sat - famine_hit
        # Urban granary buffer (PLACEHOLDER gloss)
        target_sat += 0.08 * court.urban_share * famine
        target_sat = clamp(target_sat)
        # Saturating approach: sat ← sat + λ·(target − sat)
        court.satisfaction = clamp(
            court.satisfaction + 0.18 * (target_sat - court.satisfaction)
        )

        # Manpower: logistic-ish approach to extractable target (pop × levy × sat)
        # Liye/Shuihudi ordinal levy_base ranks feed target — form PLACEHOLDER.
        target_mp = clamp(
            0.55 * court.population
            + 0.35 * court.levy_base
            + 0.15 * court.satisfaction
            - 0.18 * (famine ** 1.15)
        )
        # Faster catch-up when far below target; slow near it (saturating)
        gap = target_mp - court.available_manpower
        rate = 0.12 * (0.4 + 0.6 * abs(gap))
        court.available_manpower = clamp(court.available_manpower + rate * gap)
        # Population barely moves (placeholder stagnation + saturating famine cut)
        pop_target = clamp(
            court.population - 0.05 * (famine ** 1.2) + 0.02 * court.satisfaction,
            lo=0.05,
            hi=1.0,
        )
        court.population = clamp(
            court.population + 0.08 * (pop_target - court.population),
            lo=0.05,
            hi=1.0,
        )
    board.clamp()
    world.demographics = board
    return {
        "mean_satisfaction": board.mean_satisfaction,
        "mean_manpower": board.mean_manpower,
        "mean_population": board.mean_population,
        "placeholder": True,
    }


def apply_placeholder_hooks(world: Any) -> dict[str, float]:
    """Saturating soft hooks so demography isn't inert — still PLACEHOLDER.

    Does NOT pretend calibration. Magnitudes kept << existing M1/M2/M4 terms.
    Nudges use tanh / room-to-bound forms (not pure linear ±k·signal).
    Levy ordinals: Liye/Shuihudi ranks in economic-grounding-sources.md.
    """
    import math

    from .nonlinear import soft_threshold

    board: DemographicsBoard = getattr(world, "demographics", None) or seed_demographics()
    board.clamp()
    world.demographics = board

    featured = ("qin", "chu", "qi")
    anti = ("chu", "qi", "zhao", "han", "wei", "yan")

    def _c(cid: str) -> CourtDemographics:
        return board.courts.get(cid) or CourtDemographics()

    # --- levy soft hook (PLACEHOLDER, saturating) ---
    levy_signal = sum(_c(cid).levy_base * _c(cid).available_manpower for cid in featured) / 3.0
    before_levy = float(world.world.levy_capacity)
    # tanh compresses extremes; room shrinks near ceiling/floor
    room = 1.0 - abs(before_levy - 0.5) * 1.4
    room = max(0.15, room)
    levy_nudge = 0.028 * math.tanh(2.5 * (levy_signal - 0.35)) * room
    world.world.levy_capacity = max(0.12, min(1.0, before_levy + levy_nudge))

    # --- cohesion soft hook (PLACEHOLDER, saturating) ---
    anti_sat = sum(_c(cid).satisfaction for cid in anti) / max(1, len(anti))
    coh_now = float(world.meso.cohesion)
    coh_room = max(0.2, 1.0 - abs(coh_now / 100.0 - 0.5))
    coh_nudge = 1.4 * math.tanh(3.0 * (anti_sat - 0.5)) * coh_room
    world.meso.cohesion = max(0.0, min(100.0, coh_now + coh_nudge))

    # --- pressure soft hook (PLACEHOLDER) — unrest soft-threshold ---
    unrest = max(0.0, 0.55 - anti_sat)
    unrest_gate = soft_threshold(unrest, 0.08, k=12.0)
    pressure_nudge = 0.55 * unrest * unrest_gate  # << M4/M2; silent until unrest clears θ
    world.qin_pressure = max(0.0, min(100.0, float(world.qin_pressure) + pressure_nudge))

    # --- military / manpower soft hook (PLACEHOLDER, saturating) ---
    qin_mp = _c("qin").available_manpower
    coal_mp = sum(_c(cid).available_manpower for cid in ("chu", "qi")) / 2.0
    mq = float(world.world.military_qin)
    mc = float(world.world.military_coalition)
    mil_qin_nudge = 0.03 * math.tanh(2.0 * (qin_mp - 0.5)) * max(0.2, 1.0 - mq)
    mil_coal_nudge = 0.03 * math.tanh(2.0 * (coal_mp - 0.5)) * max(0.2, 1.0 - mc)
    world.world.military_qin = max(0.0, min(1.0, mq + mil_qin_nudge))
    world.world.military_coalition = max(0.0, min(1.0, mc + mil_coal_nudge))
    world.world.qin_mil_advantage = round(
        float(world.world.military_qin) - float(world.world.military_coalition), 4
    )

    return {
        "levy_nudge": round(levy_nudge, 5),
        "cohesion_nudge": round(coh_nudge, 5),
        "pressure_nudge": round(pressure_nudge, 5),
        "mil_qin_nudge": round(mil_qin_nudge, 5),
        "mil_coal_nudge": round(mil_coal_nudge, 5),
        "mean_satisfaction": board.mean_satisfaction,
        "mean_manpower": board.mean_manpower,
    }


def field_demographics_summary(world: Any) -> dict[str, Any]:
    """UI / CLI projection helper."""
    board: DemographicsBoard = getattr(world, "demographics", None) or seed_demographics()
    board.clamp()
    featured_rows = []
    for cid in COURT_IDS:
        c = board.courts.get(cid) or CourtDemographics()
        featured_rows.append({"id": cid, **c.to_dict()})
    return {
        "placeholder": True,
        "honesty": board.honesty,
        "seed_grounding": "economic-grounding-sources.md§3",
        "mean_satisfaction": board.mean_satisfaction,
        "mean_manpower": board.mean_manpower,
        "mean_population": board.mean_population,
        "courts": {cid: (board.courts.get(cid) or CourtDemographics()).to_dict() for cid in COURT_IDS},
        "rows": featured_rows,
    }
