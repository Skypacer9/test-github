"""Opening card + mechanism-only soft-lock (never calendar / Q-count).

Soft-lock mechanisms (any one) — delayed for mid-game precarious peace:
  (1) qin_path + (dead trust edges OR cohesion collapse) — after grace ticks
  (2) cascade armed + high betrayal + quorum death
  (3) pathway sticky WITH structural damage (qin_path / chu_fiction only;
      never stalemate alone; "other" is not sticky-lockable)

Never lock on fragile stalemate alone. Never lock on quarter count.
New Run always clears the lock and rebuilds the world.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .world import WorldState

OPENING_CARD = {
    "title": "Opening — Why an anti-Qin coalition?",
    "body": (
        "Qin is an existential military-administrative threat to the eastern courts — "
        "not a friend to bequeath trust to. After Changping and the fall of Chu's old capital "
        "Ying (白起王翦列傳 scaffold), surviving states face rising Qin pressure. "
        "Your play: each quarter, Chu / Qi / Zhao / Han / Wei / Yan choose whether to "
        "Contribute to, Withhold from, or Defect from a fragile anti-Qin holding coalition. "
        "Qin is the pressure source (Legalism/fa), not a coalition partner. "
        "Mid-game is precarious peace + zero-sum rivalry (shadow attacks, theft, Optimizing) — "
        "soft-lock only after irreversible mechanisms, never from Q-count or stalemate alone. "
        "New Run resets."
    ),
    "anchors": [
        "docs/primary-texts/shiji.md (白起王翦列傳 / 秦始皇本紀)",
        "docs/generative-historical-possibility-engine-plan.md (coalition cascade)",
        "docs/pathway-label-honesty.md (other bin retained)",
    ],
    "irreversibles_preview": [
        "No calendar soft-lock — long grinding coexistence window",
        "(1) qin_path + severe dead edges / cohesion collapse (after grace)",
        "(2) cascade + high betrayal + quorum death",
        "(3) sticky qin_path/chu_fiction + structural damage (never stalemate/other alone)",
        "New Run always resets",
    ],
}

PATHWAY_BLURBS = {
    "qin_path": "Qin-favored path — anti-Qin cohesion collapsed under pressure (historical-adjacent).",
    "stalemate": (
        "Precarious peace / fragile stalemate — subgroups hold just enough; "
        "costly equilibrium with zero-sum rivalry under the surface. "
        "Any détente/partition/tribute flavor is emergent from trust/packets/sync "
        "(Field may note a reading) — not a hard-coded coexistence or friendship rule."
    ),
    "chu_fiction": "Chu-federation fiction — labeled design fiction, not historiography.",
    "other": "Other / unknown — run did not fit the readability tags (honesty bin).",
}
# Never soft-lock on stalemate alone (even if sticky); "other" also non-locking alone
NO_LOCK_ALONE = frozenset({"stalemate", "other"})

# Softened / delayed thresholds — mid-game grind before irreversible lock
COHESION_COLLAPSE = 10.0
MIN_DEAD_EDGES = 8
DEAD_EDGE_TRUST = 0.05  # only truly dead edges count
CASCADE_ARMED_MIN = 5
HIGH_BETRAYAL = 0.85
PATHWAY_STICKY_QUARTERS = 12
# Grace: no mechanism soft-lock before this tick (calendar is still not a lock trigger;
# this only delays evaluating irreversible patterns so rivalry can play out)
MIN_LOCK_TICK = 36
# Sticky+damage lock: qin_path / chu_fiction only — NOT "other" (was early dead-end)
STICKY_LOCK_PATHWAYS = frozenset({"qin_path", "chu_fiction"})


def ensure_demo_fields(world: "WorldState") -> None:
    if not hasattr(world, "demo_mode") or world.demo_mode is None:
        world.demo_mode = "full"
    if not hasattr(world, "demo_horizon"):
        world.demo_horizon = 0  # unused — never calendar-locks
    if not hasattr(world, "run_ended"):
        world.run_ended = False
    if not hasattr(world, "end_screen"):
        world.end_screen = None
    if not hasattr(world, "opening_seen"):
        world.opening_seen = False
    if not hasattr(world, "dead_edges"):
        world.dead_edges = []
    if not hasattr(world, "pathway_stable_count"):
        world.pathway_stable_count = 0
    if not hasattr(world, "last_pathway"):
        world.last_pathway = world.meso.pathway_soft


def mark_opening_seen(world: "WorldState") -> None:
    ensure_demo_fields(world)
    world.opening_seen = True


def set_short_demo(world: "WorldState", horizon: int = 8) -> None:
    """UI flavor only — does NOT arm a calendar soft-lock."""
    ensure_demo_fields(world)
    world.demo_mode = "short"
    world.demo_horizon = int(horizon or 0)  # recorded only; never used as Q-count end
    world.run_ended = False
    world.end_screen = None
    world.append_log(
        (
            "Short Demo focus: Advance + Intervene. "
            "No Q-count soft-lock — lock only from mechanisms "
            "(qin_path+damage / cascade+betrayal quorum death / sticky+structural). "
            "New Run resets."
        ),
        event_id="demo_mode",
        action="short_demo",
    )


def collect_dead_edges(world: "WorldState") -> list[str]:
    dead: list[str] = []
    for key, val in world.trust.items():
        if float(val) <= DEAD_EDGE_TRUST:
            dead.append(key)
    g = getattr(world, "chu_court", None)
    if g is not None:
        for key, val in g.edges.items():
            if float(val) <= DEAD_EDGE_TRUST + 0.02:
                dead.append(f"chu_court:{key}")
    return sorted(dead)[:24]


def _mean_anti_qin_betrayal(world: "WorldState") -> float:
    anti = [
        a
        for a in world.agents.values()
        if a.bloc == "anti_qin" and not getattr(a, "annexed", False)
    ]
    if not anti:
        return 0.0
    return sum(float(a.state.betrayal_memory) for a in anti) / len(anti)


def structural_damage(world: "WorldState") -> tuple[bool, list[str], bool, str]:
    """Returns (damaged, dead_edges, cohesion_collapsed, tech_note).

    Structural = severe dead trust edges OR cohesion collapse OR M2 military/levy collapse.
    Thresholds raised so mid-game rivalry does not equal instant lock.
    """
    from .tech_hooks import tech_structural_damage

    dead = collect_dead_edges(world)
    cohesion_down = float(world.meso.cohesion) <= COHESION_COLLAPSE
    tech_dmg, tech_note = tech_structural_damage(world)
    damaged = len(dead) >= MIN_DEAD_EDGES or cohesion_down or tech_dmg
    return damaged, dead, cohesion_down, tech_note


def mechanism_lock(world: "WorldState") -> tuple[str | None, str]:
    """Return (mechanism_id, reason) or (None, '') if no lock.

    (1) qin_path + dead edges / cohesion collapse / M2 military collapse
    (2) cascade + high betrayal + quorum death
    (3) pathway sticky WITH structural damage (qin_path/chu_fiction only;
        never stalemate or other alone)
    Grace: no lock before MIN_LOCK_TICK so precarious peace / rivalry can grind.
    """
    ensure_demo_fields(world)
    path = world.meso.pathway_soft
    # Explicit non-locks first
    if path in NO_LOCK_ALONE:
        return None, ""
    # Open-horizon grace — rivalry window before irreversible patterns can end the run
    if int(getattr(world, "tick", 0) or 0) < MIN_LOCK_TICK:
        return None, ""

    damaged, dead, cohesion_down, tech_note = structural_damage(world)
    sticky = int(world.pathway_stable_count)

    # (1) qin_path + structural damage (trust / cohesion / M2 military)
    if path == "qin_path" and damaged:
        bits = []
        if len(dead) >= MIN_DEAD_EDGES:
            bits.append(f"dead_edges={len(dead)}")
        if cohesion_down:
            bits.append(f"cohesion={world.meso.cohesion:.1f}≤{COHESION_COLLAPSE}")
        if tech_note:
            bits.append(f"M2 {tech_note}")
        return "qin_path_damage", (
            f"(1) qin_path + structural damage: {'; '.join(bits)}"
        )

    # (2) cascade armed + high betrayal + quorum death
    cascade = int(world.meso.cascade_armed)
    quorum_dead = not bool(world.meso.quorum_ok)
    betrayal = _mean_anti_qin_betrayal(world)
    if cascade >= CASCADE_ARMED_MIN and quorum_dead and betrayal >= HIGH_BETRAYAL:
        return "cascade_betrayal_quorum", (
            f"(2) cascade_armed={cascade}≥{CASCADE_ARMED_MIN} + "
            f"mean betrayal={betrayal:.2f}≥{HIGH_BETRAYAL} + quorum death"
        )

    # (3) pathway sticky WITH structural damage — never stalemate alone
    if (
        path in STICKY_LOCK_PATHWAYS
        and sticky >= PATHWAY_STICKY_QUARTERS
        and damaged
    ):
        bits = [f"pathway={path} sticky×{sticky}"]
        if len(dead) >= MIN_DEAD_EDGES:
            bits.append(f"dead_edges={len(dead)}")
        if cohesion_down:
            bits.append(f"cohesion={world.meso.cohesion:.1f}")
        if tech_note:
            bits.append(f"M2 {tech_note}")
        return "sticky_structural", (
            f"(3) pathway sticky + structural damage: {'; '.join(bits)}"
        )

    return None, ""


def soft_lock_if_needed(world: "WorldState") -> dict[str, Any] | None:
    """Mechanism-only soft-lock. Never calendar. New Run clears via new_world()."""
    ensure_demo_fields(world)
    if world.run_ended:
        return world.end_screen

    # Track pathway stickiness as a signal for mechanism (3) — not a calendar
    if world.meso.pathway_soft == world.last_pathway and world.tick > 0:
        world.pathway_stable_count += 1
    else:
        world.pathway_stable_count = 1
        world.last_pathway = world.meso.pathway_soft

    mech, reason = mechanism_lock(world)
    if mech is None:
        return None

    dead = collect_dead_edges(world)
    world.dead_edges = dead
    world.run_ended = True
    path = world.meso.pathway_soft
    end = {
        "title": "Run soft-locked (mechanism)",
        "tick": world.tick,
        "pathway": path,
        "pathway_blurb": PATHWAY_BLURBS.get(path, PATHWAY_BLURBS["other"]),
        "reason": reason,
        "mechanism": mech,
        "qin_pressure": world.qin_pressure,
        "cohesion": world.meso.cohesion,
        "shared_identity": world.meso.shared_identity,
        "dead_edges": dead,
        "who_note": (
            "Mechanism soft-lock (not Q-count, not stalemate alone). "
            "New Run clears the lock and resets the world."
        ),
        "demo_mode": world.demo_mode,
        "lock_kind": "mechanism",
    }
    world.end_screen = end
    world.append_log(
        (
            f"SOFT-LOCK [{mech}]: {reason} pathway={path}. "
            f"Dead edges ({len(dead)}): {', '.join(dead[:6]) or 'none'}. New Run resets."
        ),
        event_id="soft_lock",
        action="end",
        dials_fired=["pathway", "cohesion", "cascade", "quorum"],
    )
    return end


def opening_card_html_plain() -> dict[str, Any]:
    return dict(OPENING_CARD)
