"""Shared nonlinear primitives for mid-fidelity ABM dynamics.

Honesty: these are mechanism *forms* (saturating, logistic soft-thresholds,
frequency gates), not calibrated historical parameters. Callers document
evidence class per equation in docs/mechanisms-master.md.
"""

from __future__ import annotations

import math
from typing import Iterable


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def sigmoid(x: float, k: float = 1.0) -> float:
    """Numerically stable logistic σ(k·x)."""
    z = max(-60.0, min(60.0, float(k) * float(x)))
    return 1.0 / (1.0 + math.exp(-z))


def soft_threshold(x: float, threshold: float, k: float = 8.0) -> float:
    """Smooth step ≈0 below threshold, ≈1 above (Granovetter-style soft gate)."""
    return sigmoid(float(x) - float(threshold), k=k)


def saturating_up(cur: float, eta: float, hi: float = 1.0) -> float:
    """Approach hi with diminishing returns: cur + η·(hi − cur)."""
    c = float(cur)
    return c + float(eta) * (float(hi) - c)


def saturating_down(cur: float, eta: float, lo: float = 0.0) -> float:
    """Approach lo with room-to-floor: cur − η·(cur − lo)."""
    c = float(cur)
    return c - float(eta) * (c - float(lo))


def logistic_room(level: float, capacity: float = 100.0) -> float:
    """Remaining capacity factor (1 − level/K), floored at 0."""
    if capacity <= 0:
        return 0.0
    return max(0.0, 1.0 - float(level) / float(capacity))


def accel_midband(level: float, capacity: float = 100.0, base: float = 0.65, span: float = 0.7) -> float:
    """Mild acceleration as level fills capacity — cascade-feel without blow-up."""
    u = 0.0 if capacity <= 0 else clamp(float(level) / float(capacity))
    return float(base) + float(span) * u


def michaelis_menten(x: float, vmax: float, km: float) -> float:
    """Diminishing-returns / bottleneck: vmax · x / (km + x)."""
    xx = max(0.0, float(x))
    return float(vmax) * xx / (float(km) + xx)


def softmax_pick(scores: dict[str, float], temperature: float = 0.15) -> str:
    """Argmax of temperature-scaled softmax (deterministic; same as argmax of scores
    when temperature > 0, but exposes soft margins for hysteresis callers)."""
    if not scores:
        raise ValueError("softmax_pick: empty scores")
    tau = max(1e-6, float(temperature))
    # Stable: subtract max
    m = max(scores.values())
    exps = {k: math.exp((float(v) - m) / tau) for k, v in scores.items()}
    # Argmax of exp((s-m)/τ) == argmax of s
    return max(exps.items(), key=lambda kv: kv[1])[0]


def soft_margins(scores: dict[str, float], temperature: float = 0.15) -> dict[str, float]:
    """Softmax probabilities — used to strengthen score→choice near ties."""
    if not scores:
        return {}
    tau = max(1e-6, float(temperature))
    m = max(scores.values())
    exps = {k: math.exp((float(v) - m) / tau) for k, v in scores.items()}
    z = sum(exps.values()) or 1.0
    return {k: v / z for k, v in exps.items()}


def mean(xs: Iterable[float]) -> float:
    vals = list(xs)
    if not vals:
        return 0.0
    return sum(vals) / len(vals)
