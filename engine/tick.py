"""Quarter clock — advance world, decisions, pathway soft-label."""

from __future__ import annotations

from .action_labels import format_decision_records, who_vs_qin_line
from .agents import decide_action
from .packets import logic_conflict, propagate_packets
from .patron_client import tick_patron_graph
from .trust import update_trust_from_actions
from .triggers import apply_shock_default, evaluate_triggers
from .world import WorldState


def soft_pathway(world: WorldState) -> str:
    """Soft readability label only — does NOT drive dynamics or mutate state.

    Dynamics emerge from trust / packets / Chu sync / pressure / M2 tech.
    No hard-coded coexistence or friendship rules. Labels only name coarse
    meter regions (qin_path / stalemate / chu_fiction / other).
    """
    c = world.meso.cohesion
    p = world.qin_pressure
    sid = world.meso.shared_identity
    chu = world.agents.get("chu")
    chu_coop = chu is not None and chu.intention.current == "cooperate"
    chu_fast = chu is not None and chu.traits.response_latency < 0.6

    # Fiction branch: only if dials clearly flipped (low latency + low status threat)
    if (
        chu_coop
        and chu_fast
        and chu is not None
        and chu.traits.status_threat_sensitivity < 0.45
        and c >= 55
        and p < 70
    ):
        return "chu_fiction"

    # Qin-path only when pressure is clearly crushing and cohesion broken
    if c < 32 and p >= 78:
        return "qin_path"
    # Precarious peace / fragile stalemate — wider mid-band so rivalry can grind
    living_anti = [
        a
        for a in world.agents.values()
        if a.bloc == "anti_qin" and not getattr(a, "annexed", False)
    ]
    subgroup_hold = len(living_anti) >= 3 and c >= 38 and p < 85
    classic_stalemate = c >= 45 and p < 80 and sid >= 38
    if (classic_stalemate or subgroup_hold) and p < 88:
        # Quorum soft: allow stalemate even if quorum flickers (precarious, not dead)
        return "stalemate"
    return "other"


def pathway_reading_note(world: WorldState) -> str:
    """Optional Field gloss — observational only, never a rule or state change.

    Stalemate readings name precarious peace / partial détente among subgroups,
    or cold trust-to-Qin + bonded Chu sync. Not friendship; not a hard lock.
    """
    from .patron_client import clique_sync
    from .trust import get_trust

    if world.meso.pathway_soft != "stalemate":
        return ""
    chu_qin = get_trust(world.trust, "chu", "qin")
    qi_qin = get_trust(world.trust, "qi", "qin")
    chu_qi = get_trust(world.trust, "chu", "qi")
    qi_chu = get_trust(world.trust, "qi", "chu")
    sync = clique_sync(world.chu_court) if getattr(world, "chu_court", None) else {}
    bonded = float(sync.get("bonded", 0.0)) >= 1.0
    sustained = int(getattr(world, "pathway_stable_count", 0)) >= 4
    # Subgroup precarious peace: some dyads still warm while pressure climbs
    subgroup = chu_qi >= 0.42 and qi_chu >= 0.35 and float(world.qin_pressure) >= 40
    if bonded and sustained and chu_qin <= 0.32 and qi_qin <= 0.35:
        return (
            "reading: Qin–Chu détente/partition/tribute flavor "
            f"(chu→qin trust={chu_qin:.2f}, Chu sync bonded) — not friendship"
        )
    if subgroup or sustained:
        return (
            "reading: precarious peace — fragile détente among some courts "
            f"(chu↔qi≈{(chu_qi + qi_chu) / 2:.2f}); zero-sum rivalry continues "
            "under the surface — not irreversible annexation"
        )
    return ""


def tick(world: WorldState, *, apply_pending_shock: bool = True) -> WorldState:
    """One quarterly auto-step. Mutates and returns world."""
    from .demo_flow import ensure_demo_fields, soft_lock_if_needed
    from .geo import apply_m4_to_world, m4_pressure_delta

    ensure_demo_fields(world)
    if world.run_ended:
        world.append_log(
            "Run soft-locked — Advance ignored. New Run / restart to replay.",
            event_id="soft_lock",
            action="blocked",
        )
        return world

    world.tick += 1
    world.quarter_in_year = ((world.tick - 1) % 4) + 1
    if world.tick > 1 and world.quarter_in_year == 1:
        world.year += 1
    # Demo play-feel: refresh action budgets on Advance Quarter
    world.player_invest_actions_left = 1
    world.alliance_attempt_actions_left = 1
    world.intervene_actions_left = 1
    world.player_offensive_actions_left = 3  # soft player offensive cap ~2–3/quarter
    world.player_offensive_fronts = {}
    world.alliance_fund_spent_purposes = []
    world.counsel_actions_left = 6  # refresh Speak→Decide episode budget
    # Close any open counsel talk on Advance — no lingering player prompt memory
    from .counsel import clear_counsel_session
    clear_counsel_session(world)
    world.last_player_action_error = None
    world.last_player_offensive_error = None
    world.last_alliance_attempt_error = None
    world.last_intervene_error = None
    world.last_alliance_fund_error = None

    # M4 geo rollup → defense / levy / projection (not GIS)
    m4 = apply_m4_to_world(world)
    # M1 famine/levy haircut on M4 base (feeds M2 amp + pressure)
    from .geo import apply_m1_env

    m1 = apply_m1_env(world)

    # PLACEHOLDER demographics / satisfaction / manpower drift (uncalibrated)
    from .demographics import apply_placeholder_hooks, tick_demographics

    demo_snap = tick_demographics(world)

    # M2 via tech_hooks (this force owns tech.py; hooks isolate mid-edit)
    from .tech_hooks import tech_pressure_delta, tick_tech

    tech_snap = tick_tech(world)
    # Tiny soft hooks after tech mirrors so manpower can nibble military scalars
    demo_hooks = apply_placeholder_hooks(world)

    # Pressure advance — early-game pacing: base +2/tick (start ~20).
    # M4/M2/resentment contribute lightly so early alliance can survive;
    # soft-lock remains mechanism-only (qin_path + damage, etc.).
    from .nonlinear import accel_midband, logistic_room

    thermo = world.world.thermo_dial
    chu = world.agents.get("chu")
    resentment_boost = (chu.state.resentment * 4.0) if chu else 0.0
    m4_raw = m4_pressure_delta(world, thermo)
    tech_raw = tech_pressure_delta(world)
    # Base climb +2; damp M4/M2/resentment so net early rise stays ~+2–3
    extras = (
        0.12 * m4_raw
        + 0.12 * tech_raw
        + resentment_boost * 0.015
        + 0.25 * (1.0 - float(m4.defense_mod) * 0.15)
    )
    raw_delta = 2.0 + extras
    p_now = float(world.qin_pressure)
    # room→0 near ceiling; mild accel (kept soft for early pacing)
    world.qin_pressure = min(
        100.0,
        p_now
        + raw_delta
        * logistic_room(p_now, 100.0)
        * accel_midband(p_now, 100.0, base=0.85, span=0.35),
    )

    # Optional default shock on schedule
    trig = evaluate_triggers(world)
    if trig and trig.kind == "shock" and apply_pending_shock:
        apply_shock_default(world)
        world.pending_trigger = None
    elif trig:
        world.pending_trigger = trig.kind
    else:
        world.pending_trigger = None

    world.recompute_meso()
    cohesion = world.meso.cohesion

    actions = {}
    for ag in world.agents.values():
        if getattr(ag, "annexed", False):
            actions[ag.id] = "withhold"
            continue
        if logic_conflict(ag.active_packets) and ag.bloc == "anti_qin":
            ag.state.perceived_threat = min(1.0, ag.state.perceived_threat + 0.05)
        act = decide_action(ag, world.qin_pressure, cohesion, world.tick)
        actions[ag.id] = act

    # Clear coalition-stance lines (never imply Qin↔Chu friendship)
    for row in format_decision_records(world, actions):
        world.append_log(
            row["text"],
            event_id="decision" if row["action"] != "who_vs_qin" else "who_vs_qin",
            actor=row["actor"],
            action=row["action"],
            dials_fired=["threshold"] if row["action"] != "who_vs_qin" else [],
        )

    update_trust_from_actions(world, actions)
    from .conflict import apply_detect_trust_penalties, run_autonomous_conflicts

    apply_detect_trust_penalties(world, actions)
    world.last_actions = dict(actions)
    # Autonomous Attack Neighbor / Desperation / Optimizing (after pressure + PAS)
    run_autonomous_conflicts(world)
    # Chu hub–spoke patron–client sync (not flat digraph label-only)
    if hasattr(world, "chu_court") and world.chu_court is not None:
        bonus = tick_patron_graph(world, actions)
        if bonus.get("bonded"):
            world.append_log(
                (
                    f"Chu patron–client clique bonded "
                    f"(order={bonus.get('order_parameter', 0):.2f}): "
                    f"sync bonus to coalition holding — not Qin friendship."
                ),
                event_id="chu_sync",
                actor="chu",
                action="patron_sync",
            )
    contagion = propagate_packets(world)
    for ev in contagion[:8]:
        world.append_log(
            (
                f"Belief contagion {ev.get('result')}: "
                f"{ev.get('from')}→{ev.get('to')} packet={ev.get('packet')} "
                f"(receptivity={ev.get('receptivity', ev.get('conflict', '?'))})"
            ),
            event_id="contagion",
            actor=str(ev.get("to") or ""),
            action=str(ev.get("result") or "contagion"),
            dials_fired=["openness", "trust"],
        )

    # Evo dial: frequency-dependent withhold contagion (threshold on local fraction)
    from .nonlinear import saturating_down, saturating_up, soft_threshold

    evo = world.world.evo_dial
    anti_ids = [a for a in actions if world.agents[a].bloc == "anti_qin"]
    withholders = sum(1 for a in anti_ids if actions[a] == "withhold")
    withhold_freq = withholders / max(1, len(anti_ids))
    if withholders and evo > 0:
        for ag in world.agents.values():
            if ag.bloc != "anti_qin":
                continue
            if ag.intention.current == "cooperate":
                # Personal threshold lower when neurotic / high status threat
                theta_w = 0.22 + 0.2 * (1.0 - float(ag.traits.neuroticism))
                gate = soft_threshold(withhold_freq, theta_w, k=8.0)
                bump = 0.04 * evo * gate * (0.5 + 0.5 * withhold_freq)
                ag.state.perceived_threat = saturating_up(ag.state.perceived_threat, bump)

    # Mild betrayal_memory decay (saturating toward 0)
    for ag in world.agents.values():
        ag.state.betrayal_memory = max(0.0, saturating_down(ag.state.betrayal_memory, 0.01))

    world.recompute_meso()
    # Cohesion tax under pressure — gentler early so ≥12–15 tick unassisted window
    p_u = float(world.qin_pressure) / 100.0
    cohesion_tax = 0.9 + 2.4 * (p_u ** 1.6)
    world.meso.cohesion = max(0.0, world.meso.cohesion - cohesion_tax)
    world.meso.pathway_soft = soft_pathway(world)
    world.clamp()

    reading = pathway_reading_note(world)
    if reading:
        world.append_log(
            reading,
            event_id="pathway_reading",
            action="observational",
        )

    era = f"Q{world.quarter_in_year} · {abs(world.year)} BCE"
    world.append_log(
        (
            f"{era}: Qin pressure {world.qin_pressure:.0f}, "
            f"anti-Qin cohesion {world.meso.cohesion:.0f}, "
            f"shared_id {world.meso.shared_identity:.0f}, pathway={world.meso.pathway_soft}, "
            f"cascade_armed={world.meso.cascade_armed}, quorum_ok={world.meso.quorum_ok}, "
            f"M4 defense={world.world.defense_mod:.2f} projection={world.world.qin_projection:.2f}, "
            f"M1 famine={m1.get('famine_shock', 0):.2f} levy={world.world.levy_capacity:.2f}, "
            f"M2 qin_mil={tech_snap.get('qin_mil', 0):.2f} "
            f"coal_mil={tech_snap.get('coalition_mil', 0):.2f} "
            f"adv={tech_snap.get('advantage', 0):+.2f} "
            f"adopt={world.world.adoption_meter:.2f}, "
            f"demo_sat={demo_snap.get('mean_satisfaction', 0):.2f} "
            f"manpower={demo_snap.get('mean_manpower', 0):.2f} "
            f"(placeholder hooks levy={demo_hooks.get('levy_nudge', 0):+.3f}). "
            f"{who_vs_qin_line(world, actions)}"
        ),
        event_id="summary",
        action="tick",
    )
    if tech_snap.get("breakthroughs"):
        world.append_log(
            f"M2 rare breakthrough spill: {', '.join(tech_snap['breakthroughs'][:4])}",
            event_id="m2_breakthrough",
            action="eureka",
            dials_fired=["evo", "m2"],
        )
    # Soft regen of player purse (political capital / treasury) — paced
    world.player_political_capital = min(
        100.0, float(getattr(world, "player_political_capital", 100.0)) + 2.5
    )
    world.player_treasury = min(
        100.0, float(getattr(world, "player_treasury", 100.0)) + 2.0
    )
    # Auto figure counsel (one-shot decision close; tips dials only)
    if getattr(world, "counsel_auto", True) and not world.run_ended:
        from .counsel import run_counsel_round
        run_counsel_round(world, force_stub=False, player_initiated=False)
    # Cultural chronicle LAST so Chronicler lands at the end of the quarterly log
    # (previously buried under auto-counsel rows → looked like narration "skipped")
    from .chronicle import maybe_write_chronicle
    maybe_write_chronicle(world)
    soft_lock_if_needed(world)
    return world


def _faction_snap(world: WorldState, aid: str) -> dict[str, float]:
    ag = world.agents.get(aid)
    if not ag:
        return {}
    return {
        "resentment": float(ag.state.resentment),
        "fear_of_qin": float(ag.state.fear_of_qin),
        "betrayal_memory": float(ag.state.betrayal_memory),
        "status_threat": float(ag.state.status_threat),
        "perceived_threat": float(ag.state.perceived_threat),
    }


# Player soft-lock invest actions (HTML / CLI / API)
PLAYER_ACTIONS = ("fund_military", "send_grain", "broker_mediation")
PLAYER_ACTION_LABELS = {
    "fund_military": "Fund Military",
    "send_grain": "Send Grain",
    "broker_mediation": "Broker Mediation",
}
# Costs: (political_capital, treasury)
PLAYER_ACTION_COSTS = {
    "fund_military": (12.0, 18.0),
    "send_grain": (8.0, 14.0),
    "broker_mediation": (16.0, 10.0),
}
OVERCONFIDENCE_FEAR = 0.20  # Trust-Action Paradox threshold
ANTI_QIN_TARGETS = ("chu", "qi", "zhao", "han", "wei", "yan")
# Name / alias → canonical state id (invest targets)
TARGET_ALIASES = {
    "qin": "qin",
    "秦": "qin",
    "chu": "chu",
    "楚": "chu",
    "qi": "qi",
    "齐": "qi",
    "齊": "qi",
    "zhao": "zhao",
    "趙": "zhao",
    "赵": "zhao",
    "han": "han",
    "韓": "han",
    "韩": "han",
    "wei": "wei",
    "魏": "wei",
    "yan": "yan",
    "燕": "yan",
}
OFFENSIVE_STATE_IDS = ("qin", "chu", "qi", "zhao", "han", "wei", "yan")
OFFENSIVE_PC_COST = 10.0
OFFENSIVE_TR_COST = 12.0
PLAYER_OFFENSIVE_SOFT_CAP = 3


def _as_bool(val: object, default: bool = False) -> bool:
    """Truthy coercion that treats 'false'/'0'/'' as False (JSON/string-safe)."""
    if val is None:
        return default
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(val)


def _normalize_invest_target(target: str | None) -> str:
    raw = str(target or "chu").strip().lower()
    return TARGET_ALIASES.get(raw, raw)


def _living_anti_qin(world: WorldState, tid: str):
    """Return (agent|None, error|None). Living = known anti-Qin, not annexed, viability>0."""
    if tid not in ANTI_QIN_TARGETS:
        return None, (
            f"Player action failed: target must be one of "
            f"{', '.join(ANTI_QIN_TARGETS)} (got {tid!r})"
        )
    ag = world.agents.get(tid)
    if ag is None:
        return None, f"Player action failed: unknown court {tid!r} (not in world.agents)"
    bloc = str(getattr(ag, "bloc", "") or "")
    if bloc != "anti_qin":
        return None, (
            f"Player action failed: {getattr(ag, 'name', tid)} is bloc={bloc!r}, "
            f"need living anti-Qin"
        )
    annexed = _as_bool(getattr(ag, "annexed", False))
    # Keep flag clean for later checks / UI
    ag.annexed = annexed
    if annexed:
        by = getattr(ag, "annexed_by", None) or "?"
        return None, (
            f"Player action failed: {ag.name} is annexed by {by} — "
            f"cannot Fund Military / Send Grain / Mediate"
        )
    if float(getattr(ag, "viability", 0.0) or 0.0) <= 0.0:
        return None, (
            f"Player action failed: {ag.name} viability is 0 — "
            f"court is gone; pick another state"
        )
    return ag, None


def _append_player_log(world: WorldState, line: str) -> None:
    if not hasattr(world, "player_log") or world.player_log is None:
        world.player_log = []
    world.player_log.append(line)
    if len(world.player_log) > 80:
        world.player_log = world.player_log[-80:]


def player_action(world: WorldState, action: str, target: str = "chu") -> WorldState:
    """Invest action targeting one anti-Qin court — spends player Political Capital/Treasury.

    Fund Military / Send Grain / Broker Mediation each lower Fear_of_Qin and
    Resentment (and cool defection_accumulator). Mediation raises trust; failure
    risk → civil war. If Fear drops below ~0.20, Trust-Action Paradox fires.

    Valid targets: chu, qi, zhao, han, wei, yan (living / not annexed).
    Sets world.last_player_action_error (str|None) for API/UI.
    """
    from .conflict import civil_war_check, ensure_econ_fields

    ensure_econ_fields(world)
    world.last_player_action_error = None
    act = str(action or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "fund": "fund_military",
        "military": "fund_military",
        "grain": "send_grain",
        "send": "send_grain",
        "mediate": "broker_mediation",
        "mediation": "broker_mediation",
        "broker": "broker_mediation",
    }
    act = aliases.get(act, act)
    tid = _normalize_invest_target(target)
    if act not in PLAYER_ACTIONS:
        note = f"Player action failed: unknown action {action!r} (need fund_military|send_grain|broker_mediation)"
        world.last_player_action_error = note
        world.append_log(note, event_id="player_action", action="error")
        _append_player_log(world, note)
        return world
    left = int(getattr(world, "player_invest_actions_left", 1))
    if left <= 0:
        note = (
            "Player action failed: invest budget spent this quarter "
            "(Fund Military / Send Grain / Broker Mediation share 1 action) — Advance to reset"
        )
        world.last_player_action_error = note
        world.append_log(note, event_id="player_action", action="budget")
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    ag, err = _living_anti_qin(world, tid)
    if err or ag is None:
        note = err or f"Player action failed: target must be a living anti-Qin state (got {tid!r})"
        world.last_player_action_error = note
        world.append_log(note, event_id="player_action", action="error")
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world

    pc_cost, tr_cost = PLAYER_ACTION_COSTS[act]
    pc = float(getattr(world, "player_political_capital", 100.0))
    tr = float(getattr(world, "player_treasury", 100.0))
    if pc < pc_cost or tr < tr_cost:
        note = (
            f"Player action failed: need Political Capital ≥{pc_cost:.0f} and "
            f"Treasury ≥{tr_cost:.0f} (have PC={pc:.0f} Treasury={tr:.0f})"
        )
        world.last_player_action_error = note
        world.append_log(note, event_id="player_action", action="broke")
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    world.player_political_capital = pc - pc_cost
    world.player_treasury = tr - tr_cost
    world.player_invest_actions_left = max(0, left - 1)

    label = PLAYER_ACTION_LABELS[act]
    before = _faction_snap(world, tid)
    fear0 = float(ag.state.fear_of_qin)
    res0 = float(ag.state.resentment)

    civil_note = ""
    if act == "fund_military":
        fear_delta, res_delta = -0.14, -0.07
        ag.state.status_threat = max(0.0, ag.state.status_threat - 0.06)
        ag.treasury = min(100.0, float(ag.treasury) + 8.0)
        world.meso.cohesion = min(100.0, world.meso.cohesion + 4.0)
        world.world.military_coalition = min(
            1.0, float(getattr(world.world, "military_coalition", 0.0)) + 0.04
        )
        flavor = "arms stipend cools Fear of Qin; court holds the line a little longer"
    elif act == "send_grain":
        fear_delta, res_delta = -0.07, -0.14
        ag.state.betrayal_memory = max(0.0, ag.state.betrayal_memory - 0.04)
        ag.grain = min(100.0, float(ag.grain) + 12.0)
        world.meso.cohesion = min(100.0, world.meso.cohesion + 3.0)
        demo = getattr(world, "demographics", None)
        if demo is not None and hasattr(demo, "courts"):
            court = demo.courts.get(tid) if hasattr(demo, "courts") else None
            if court is not None and hasattr(court, "satisfaction"):
                court.satisfaction = min(1.0, float(court.satisfaction) + 0.05)
        flavor = "grain relief eases Resentment; granaries steady the coalition"
    else:  # broker_mediation
        fear_delta, res_delta = -0.09, -0.15
        ag.state.status_threat = max(0.0, ag.state.status_threat - 0.10)
        from .nonlinear import saturating_up as _sat_up

        for other_id, other in world.agents.items():
            if other.bloc != "anti_qin" or other_id == tid or getattr(other, "annexed", False):
                continue
            world.trust[f"{other_id}->{tid}"] = _sat_up(world.trust.get(f"{other_id}->{tid}", 0.5), 0.10)
            world.trust[f"{tid}->{other_id}"] = _sat_up(world.trust.get(f"{tid}->{other_id}", 0.5), 0.10)
        world.meso.cohesion = min(100.0, world.meso.cohesion + 5.0)
        flavor = "brokered mediation cools Resentment and rebuilds interstate trust"
        cw = civil_war_check(world, tid)
        if cw:
            civil_note = " " + cw

    ag.state.fear_of_qin = max(0.0, min(1.0, fear0 + fear_delta))
    ag.state.resentment = max(0.0, min(1.0, res0 + res_delta))
    ag.state.defection_accumulator = 0
    if not getattr(ag, "annexed", False):
        ag.intention.current = "cooperate"
        ag.intention.sticky_until = world.tick + 2
        if ag.desperate and resource_pool_safe(ag) >= 30.0 and float(ag.viability) >= 30.0:
            ag.desperate = False
            if ag.stance_mode == "desperate":
                ag.stance_mode = "coalition"

    paradox_note = ""
    if not getattr(ag, "annexed", False) and float(ag.state.fear_of_qin) < OVERCONFIDENCE_FEAR:
        bumps = []
        for other_id, other in world.agents.items():
            if other.bloc != "anti_qin" or other_id == tid or getattr(other, "annexed", False):
                continue
            other.state.resentment = min(1.0, float(other.state.resentment) + 0.08)
            other.state.status_threat = min(1.0, float(other.state.status_threat) + 0.04)
            bumps.append(other.name)
        paradox_note = (
            f" Trust-Action Paradox: Fear of Qin fell below {OVERCONFIDENCE_FEAR:.2f} — "
            f"overconfidence; Resentment toward {', '.join(bumps) or 'other courts'} rises."
        )

    world.recompute_meso()
    world.meso.pathway_soft = soft_pathway(world)
    after = _faction_snap(world, tid)
    deltas = {k: round(after[k] - before.get(k, 0.0), 3) for k in after}
    note = (
        f"{label} → {ag.name} (−PC {pc_cost:.0f}/−Treasury {tr_cost:.0f}): "
        f"fear {fear0:.2f}→{ag.state.fear_of_qin:.2f}, "
        f"resentment {res0:.2f}→{ag.state.resentment:.2f}; "
        f"grain={float(ag.grain):.0f} treasury={float(ag.treasury):.0f} "
        f"viability={float(ag.viability):.0f} ({flavor})."
        f"{paradox_note}{civil_note}"
    )
    world.record_faction_deltas(
        event_id="player_action",
        actor=tid,
        action=act,
        per_faction={tid: deltas},
        note=note,
    )
    world.append_log(
        note,
        event_id="player_action",
        actor=tid,
        action=act,
        dials_fired=["fear_of_qin", "resentment", "defection_accumulator", "resources"],
        anchor="player soft-lock invest (Fund Military / Send Grain / Broker Mediation)",
    )
    _append_player_log(world, f"[t={world.tick}] {note}")
    world.clamp()
    return world


def player_offensive(
    world: WorldState,
    attacker: str,
    target: str,
) -> WorldState:
    """Player-initiated Offensive: pick attacker + target (not fixed focus).

    Soft global cap ~2–3 launches/quarter. Each launch checks that court's
    force / levy extract / grain / viability — refuse if no front capacity;
    weaken (force_scale < 1) when stretching a second/third front. Strong
    courts may open several fronts; weak courts cannot. Ally betrayal spike
    still fires via resolve_attack when anti-Qin strikes anti-Qin.
    """
    from .conflict import (
        NEIGHBORS,
        ensure_econ_fields,
        offensive_capacity,
        resolve_attack,
    )

    ensure_econ_fields(world)
    world.last_player_offensive_error = None
    world.last_player_offensive = None
    aid = _normalize_invest_target(attacker)
    tid = _normalize_invest_target(target)
    if aid not in OFFENSIVE_STATE_IDS or tid not in OFFENSIVE_STATE_IDS:
        note = (
            f"Offensive failed: attacker/target must be living Field states "
            f"({', '.join(OFFENSIVE_STATE_IDS)}); got {attacker!r}→{target!r}"
        )
        world.last_player_offensive_error = note
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    if aid == tid:
        note = "Offensive failed: attacker and target must differ"
        world.last_player_offensive_error = note
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    atk = world.agents.get(aid)
    dfn = world.agents.get(tid)
    if atk is None or dfn is None:
        note = f"Offensive failed: unknown court ({aid}→{tid})"
        world.last_player_offensive_error = note
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    if getattr(atk, "annexed", False) or float(getattr(atk, "viability", 0) or 0) <= 0:
        note = f"Offensive failed: {getattr(atk, 'name', aid)} cannot field an army (annexed/gone)"
        world.last_player_offensive_error = note
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    if getattr(dfn, "annexed", False) or float(getattr(dfn, "viability", 0) or 0) <= 0:
        note = f"Offensive failed: {getattr(dfn, 'name', tid)} is already gone"
        world.last_player_offensive_error = note
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    nbrs = NEIGHBORS.get(aid, ())
    if tid not in nbrs:
        note = (
            f"Offensive failed: {atk.name} does not neighbor {dfn.name} "
            f"(adjacent: {', '.join(nbrs) or '—'})"
        )
        world.last_player_offensive_error = note
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world

    left = int(getattr(world, "player_offensive_actions_left", PLAYER_OFFENSIVE_SOFT_CAP))
    if left <= 0:
        note = (
            f"Offensive failed: player launch budget spent this quarter "
            f"(soft cap {PLAYER_OFFENSIVE_SOFT_CAP}) — Advance to reset"
        )
        world.last_player_offensive_error = note
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world

    cap = offensive_capacity(world, aid)
    if not cap.get("can_launch"):
        why = str(cap.get("reason") or "no_capacity")
        note = (
            f"Offensive failed: {atk.name} lacks capacity for another front "
            f"(force={cap.get('force')}, levy={cap.get('levy')}, "
            f"grain={cap.get('grain')}, viability={cap.get('viability')}, "
            f"opened={cap.get('opened')}/{cap.get('max_fronts')}, {why})"
        )
        world.last_player_offensive_error = note
        world.last_player_offensive = dict(cap)
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world

    pc = float(getattr(world, "player_political_capital", 100.0))
    tr = float(getattr(world, "player_treasury", 100.0))
    if pc < OFFENSIVE_PC_COST or tr < OFFENSIVE_TR_COST:
        note = (
            f"Offensive failed: need Political Capital ≥{OFFENSIVE_PC_COST:.0f} and "
            f"Treasury ≥{OFFENSIVE_TR_COST:.0f} (have PC={pc:.0f} Treasury={tr:.0f})"
        )
        world.last_player_offensive_error = note
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world

    world.player_political_capital = pc - OFFENSIVE_PC_COST
    world.player_treasury = tr - OFFENSIVE_TR_COST
    world.player_offensive_actions_left = max(0, left - 1)
    fronts = dict(getattr(world, "player_offensive_fronts", None) or {})
    fronts[aid] = int(fronts.get(aid, 0) or 0) + 1
    world.player_offensive_fronts = fronts

    scale = float(cap.get("force_scale") or 1.0)
    res = resolve_attack(world, aid, tid, force_scale=scale)
    if res.get("cancelled"):
        # Refund player budget/purse if court could not actually march (broke mid-check)
        world.player_political_capital = min(100.0, float(world.player_political_capital) + OFFENSIVE_PC_COST)
        world.player_treasury = min(100.0, float(world.player_treasury) + OFFENSIVE_TR_COST)
        world.player_offensive_actions_left = left
        fronts[aid] = max(0, int(fronts.get(aid, 1)) - 1)
        if fronts[aid] <= 0:
            fronts.pop(aid, None)
        world.player_offensive_fronts = fronts
        note = (
            f"Offensive cancelled: {atk.name} could not afford the march on {dfn.name} "
            f"({res.get('reason') or 'broke'})"
        )
        world.last_player_offensive_error = note
        world.last_player_offensive = {**cap, **res}
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world

    residual_after = offensive_capacity(world, aid)
    stretch = ""
    if scale < 0.99:
        stretch = f" stretched front (force×{scale:.2f});"
    ally = ""
    if getattr(atk, "bloc", "") == "anti_qin" and getattr(dfn, "bloc", "") == "anti_qin":
        ally = " Ally betrayal spike applied."
    note = (
        f"Offensive: {atk.name} → {dfn.name} (−PC {OFFENSIVE_PC_COST:.0f}/−Treasury {OFFENSIVE_TR_COST:.0f});"
        f"{stretch} winner={res.get('winner')} loser={res.get('loser')} "
        f"atk_pow={res.get('atk_pow')} dfn_pow={res.get('dfn_pow')}; "
        f"player launches left={world.player_offensive_actions_left}; "
        f"{atk.name} residual fronts={residual_after.get('residual')}/"
        f"{residual_after.get('max_fronts')}."
        f"{ally}"
    )
    world.last_player_offensive = {
        **res,
        "capacity_before": cap,
        "capacity_after": residual_after,
        "player_launches_left": int(world.player_offensive_actions_left),
    }
    world.append_log(
        note,
        event_id="player_offensive",
        actor=aid,
        action="offensive",
        dials_fired=["trust", "resentment", "betrayal_memory", "viability", "resources"],
        anchor="player Offensive (attacker+target)",
    )
    _append_player_log(world, f"[t={world.tick}] {note}")
    world.recompute_meso()
    world.meso.pathway_soft = soft_pathway(world)
    world.clamp()
    return world


def resource_pool_safe(ag) -> float:
    return 0.5 * (float(getattr(ag, "grain", 0.0)) + float(getattr(ag, "treasury", 0.0)))


def intervene(world: WorldState, target: str = "chu") -> WorldState:
    """Political capital on one court. Qin = delay/cool pressure; anti-Qin = Contribute sticky."""
    ag = world.agents.get(target)
    if not ag:
        world.append_log(f"Intervene failed: unknown target {target}", event_id="intervene")
        return world

    before = _faction_snap(world, target)
    ag.state.resentment = max(0.0, ag.state.resentment - 0.15)
    ag.state.status_threat = max(0.0, ag.state.status_threat - 0.12)
    # Cool-down: clear defection inertia on the intervened court
    ag.state.defection_accumulator = 0

    if ag.bloc == "qin":
        # Diplomatic capital at Qin court: slow the probe, cool predatory lean slightly.
        ag.state.resentment = max(0.0, ag.state.resentment - 0.05)
        world.qin_pressure = max(0.0, world.qin_pressure - 5.0)
        ag.intention.current = "withhold"  # pause opportunistic Defect pulse
        ag.intention.sticky_until = world.tick + 2
        dials = ["qin_pressure", "resentment"]
        anchor = "Qin court diplomatic delay (design dial; Shiji bribery/probe scaffold)"
        note = (
            f"Intervene at Qin court: Qin pressure eased →{world.qin_pressure:.0f}; "
            f"Qin holds probe (sticky). Not a friendship with Chu — delay only."
        )
    else:
        ag.traits.response_latency = max(0.0, ag.traits.response_latency - 0.35)
        ag.intention.current = "cooperate"
        ag.intention.sticky_until = world.tick + 2
        from .nonlinear import saturating_up as _sat_up

        for other_id, other in world.agents.items():
            if other.bloc != "anti_qin" or other_id == target:
                continue
            key = f"{other_id}->{target}"
            world.trust[key] = _sat_up(world.trust.get(key, 0.5), 0.08)
            key2 = f"{target}->{other_id}"
            world.trust[key2] = _sat_up(world.trust.get(key2, 0.5), 0.05)
        world.qin_pressure = min(100.0, world.qin_pressure + 2.0)
        world.meso.cohesion = min(100.0, world.meso.cohesion + 6.0)
        dials = ["status_threat", "response_latency"]
        anchor = f"{ag.name} court intervene (latency / status threat design dial)"
        note = (
            f"Intervene in {ag.name}: cooled resentment/status; "
            f"sticky Contribute to anti-Qin coalition. "
            f"Bloc cohesion→{world.meso.cohesion:.0f} (vs Qin pressure, not Qin friendship)."
        )

    world.recompute_meso()
    world.meso.pathway_soft = soft_pathway(world)
    after = _faction_snap(world, target)
    deltas = {k: round(after[k] - before.get(k, 0.0), 3) for k in after}
    world.record_faction_deltas(
        event_id="intervene",
        actor=target,
        action="intervene",
        per_faction={target: deltas},
        note=note,
    )
    world.append_log(
        note,
        event_id="intervene",
        actor=target,
        action="intervene",
        dials_fired=dials,
        anchor=anchor,
    )
    return world


def intervene_many(world: WorldState, targets: list[str]) -> WorldState:
    """Intervene on Qin / Chu / Qi (multi-select). Empty → no-op log.

    Demo play-feel: one Intervene click per tick (multi-target still costs one).
    """
    world.last_intervene_error = None
    cleaned: list[str] = []
    for t in targets or []:
        tid = str(t).strip().lower()
        if tid in ("qin", "chu", "qi") and tid not in cleaned:
            cleaned.append(tid)
    if not cleaned:
        world.append_log(
            "Intervene skipped: pick Qin, Chu, and/or Qi.",
            event_id="intervene",
            action="intervene_none",
        )
        return world
    left = int(getattr(world, "intervene_actions_left", 1))
    if left <= 0:
        note = (
            "Intervene failed: already used this quarter "
            "(1 Intervene / tick) — Advance to reset"
        )
        world.last_intervene_error = note
        world.append_log(note, event_id="intervene", action="budget")
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    world.intervene_actions_left = max(0, left - 1)
    for tid in cleaned:
        intervene(world, tid)
    return world


# Fraction of each contributor's grain/treasury pooled on quorum success
ALLIANCE_POOL_FRACTION = 0.15
# Skip 15% skim when joint fund already substantial (grain+treasury)
ALLIANCE_FUND_SKIM_SKIP_TOTAL = 55.0

ALLIANCE_FUND_PURPOSES = ("tech", "agriculture", "construction", "military")
ALLIANCE_FUND_LABELS = {
    "tech": "Tech",
    "agriculture": "Agriculture",
    "construction": "Construction",
    "military": "Military",
}
# Spend cost (grain, treasury) per purpose action from the joint fund
ALLIANCE_FUND_COSTS = {
    "tech": (4.0, 8.0),
    "agriculture": (8.0, 3.0),
    "construction": (5.0, 6.0),
    "military": (3.0, 9.0),
}


def _alliance_eligible(ag) -> bool:
    """Alliance gate: living, not annexed, not broke (can still field a levy)."""
    if ag is None or getattr(ag, "annexed", False):
        return False
    if ag.bloc != "anti_qin":
        return False
    pool = 0.5 * (float(getattr(ag, "grain", 0.0)) + float(getattr(ag, "treasury", 0.0)))
    return pool >= 8.0 and float(getattr(ag, "viability", 0.0)) > 0.0


def spend_alliance_fund(world: WorldState, purpose: str) -> WorldState:
    """Spend joint alliance fund on tech / agriculture / construction / military.

    Demo play-feel: at most one alliance-fund spend per tick (separate from invest).
    """
    world.last_alliance_fund_error = None
    pur = str(purpose or "").strip().lower()
    aliases = {
        "agri": "agriculture",
        "farm": "agriculture",
        "grain": "agriculture",
        "build": "construction",
        "infra": "construction",
        "mil": "military",
        "army": "military",
        "arms": "military",
        "research": "tech",
        "m2": "tech",
    }
    pur = aliases.get(pur, pur)
    if pur not in ALLIANCE_FUND_PURPOSES:
        note = (
            f"Alliance fund spend failed: purpose must be "
            f"tech|agriculture|construction|military (got {purpose!r})"
        )
        world.last_alliance_fund_error = note
        world.append_log(note, event_id="alliance_fund", action="error")
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    spent = list(getattr(world, "alliance_fund_spent_purposes", None) or [])
    if pur in spent:
        note = (
            f"Alliance fund spend failed: {ALLIANCE_FUND_LABELS[pur]} already used "
            f"this quarter (each purpose once / tick) — Advance to reset"
        )
        world.last_alliance_fund_error = note
        world.append_log(note, event_id="alliance_fund", action="budget")
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    g_cost, t_cost = ALLIANCE_FUND_COSTS[pur]
    g = float(getattr(world, "alliance_fund_grain", 0.0))
    t = float(getattr(world, "alliance_fund_treasury", 0.0))
    if g < g_cost or t < t_cost:
        note = (
            f"Alliance fund broke: need grain≥{g_cost:.0f} treasury≥{t_cost:.0f} "
            f"for {ALLIANCE_FUND_LABELS[pur]} (have {g:.1f}/{t:.1f})"
        )
        world.last_alliance_fund_error = note
        world.append_log(note, event_id="alliance_fund", action="broke")
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    world.alliance_fund_grain = g - g_cost
    world.alliance_fund_treasury = t - t_cost
    spent.append(pur)
    world.alliance_fund_spent_purposes = spent
    label = ALLIANCE_FUND_LABELS[pur]
    effect = ""
    if pur == "tech":
        world.world.adoption_meter = min(
            1.0, float(getattr(world.world, "adoption_meter", 0.0)) + 0.04
        )
        world.world.military_coalition = min(
            1.0, float(getattr(world.world, "military_coalition", 0.0)) + 0.02
        )
        effect = f"adoption→{world.world.adoption_meter:.2f}, coal_mil↑"
    elif pur == "agriculture":
        for ag in world.agents.values():
            if ag.bloc == "anti_qin" and not getattr(ag, "annexed", False):
                ag.grain = min(100.0, float(ag.grain) + 3.0)
                ag.geographic_yield = min(1.0, float(ag.geographic_yield) + 0.01)
        effect = "anti-Qin grain+3, yield+0.01"
    elif pur == "construction":
        world.world.defense_mod = min(1.0, float(world.world.defense_mod) + 0.03)
        world.meso.cohesion = min(100.0, world.meso.cohesion + 2.0)
        effect = f"defense_mod→{world.world.defense_mod:.2f}, cohesion+2"
    else:  # military
        world.world.military_coalition = min(
            1.0, float(getattr(world.world, "military_coalition", 0.0)) + 0.05
        )
        world.qin_pressure = max(0.0, float(world.qin_pressure) - 2.0)
        effect = (
            f"coal_mil→{world.world.military_coalition:.2f}, "
            f"pressure→{world.qin_pressure:.0f}"
        )
    note = (
        f"Alliance fund → {label} (−grain {g_cost:.0f}/−treasury {t_cost:.0f}): {effect}. "
        f"Fund now grain={world.alliance_fund_grain:.1f} treasury={world.alliance_fund_treasury:.1f}"
    )
    if not hasattr(world, "alliance_fund_log") or world.alliance_fund_log is None:
        world.alliance_fund_log = []
    world.alliance_fund_log.append(f"[t={world.tick}] {note}")
    world.append_log(
        note,
        event_id="alliance_fund",
        action=pur,
        dials_fired=["alliance_fund", pur],
    )
    _append_player_log(world, f"[t={world.tick}] {note}")
    world.clamp()
    return world


def attempt_alliance(world: WorldState) -> WorldState:
    """Joint-campaign quorum — psychology + M2 military/levy floor.

    Excludes annexed and broke courts from the contributor pool.
    Demo play-feel: at most one Attempt Alliance per tick (separate from invest / fund spend).
    """
    from .tech_hooks import tech_quorum_ok, tick_tech

    world.last_alliance_attempt_error = None
    left = int(getattr(world, "alliance_attempt_actions_left", 1))
    if left <= 0:
        note = (
            "Alliance attempt failed: already attempted this quarter "
            "(1 Attempt Alliance / tick) — Advance to reset"
        )
        world.last_alliance_attempt_error = note
        world.append_log(note, event_id="alliance", action="budget")
        _append_player_log(world, f"[t={world.tick}] {note}")
        return world
    world.alliance_attempt_actions_left = max(0, left - 1)

    tick_tech(world)
    world.recompute_meso()
    anti = [a for a in world.agents.values() if _alliance_eligible(a)]
    for ag in anti:
        decide_action(ag, world.qin_pressure, world.meso.cohesion, world.tick)

    contributors = [a for a in anti if a.intention.current == "cooperate"]
    qi = world.agents.get("qi")
    chu = world.agents.get("chu")
    qi_ok = (
        _alliance_eligible(qi)
        and qi.intention.current != "defect"
        and (world.trust.get("qi->chu", 0.4) >= 0.35 or qi.state.betrayal_memory < 0.7)
    )
    chu_ok = _alliance_eligible(chu) and chu.state.resentment <= 0.55
    need = max(2, (len(anti) + 1) // 2) if anti else 3
    psych_ok = (
        len(contributors) >= need and qi_ok and chu_ok and world.meso.cohesion >= 40
    )
    tech_ok, tech_why = tech_quorum_ok(world, cohesion_ok=psych_ok)
    quorum = psych_ok and tech_ok

    if quorum:
        world.meso.cohesion = min(100.0, world.meso.cohesion + 9.0)
        world.qin_pressure = max(0.0, world.qin_pressure - 8.0)
        # Psych cool always; 15% skim only when joint fund is still thin
        for a in contributors:
            a.state.fear_of_qin = max(0.0, a.state.fear_of_qin - 0.05)
            a.state.betrayal_memory = max(0.0, a.state.betrayal_memory - 0.03)
        fund_g = float(getattr(world, "alliance_fund_grain", 0.0))
        fund_t = float(getattr(world, "alliance_fund_treasury", 0.0))
        fund_total = fund_g + fund_t
        pooled_g = 0.0
        pooled_t = 0.0
        if fund_total >= ALLIANCE_FUND_SKIM_SKIP_TOTAL:
            fund_line = (
                f"Joint fund skim skipped (already {fund_g:.1f}/{fund_t:.1f} ≥ "
                f"{ALLIANCE_FUND_SKIM_SKIP_TOTAL:.0f} total) — no re-levy this quorum"
            )
        else:
            for a in contributors:
                g_take = ALLIANCE_POOL_FRACTION * float(getattr(a, "grain", 0.0))
                t_take = ALLIANCE_POOL_FRACTION * float(getattr(a, "treasury", 0.0))
                a.grain = max(0.0, float(a.grain) - g_take)
                a.treasury = max(0.0, float(a.treasury) - t_take)
                pooled_g += g_take
                pooled_t += t_take
            world.alliance_fund_grain = fund_g + pooled_g
            world.alliance_fund_treasury = fund_t + pooled_t
            fund_line = (
                f"Joint fund +grain {pooled_g:.1f} / +treasury {pooled_t:.1f} "
                f"from {len(contributors)} contributors "
                f"(pool {ALLIANCE_POOL_FRACTION:.0%} each) → "
                f"fund grain={world.alliance_fund_grain:.1f} treasury={world.alliance_fund_treasury:.1f}"
            )
        if not hasattr(world, "alliance_fund_log") or world.alliance_fund_log is None:
            world.alliance_fund_log = []
        world.alliance_fund_log.append(f"[t={world.tick}] {fund_line}")
        _append_player_log(world, f"[t={world.tick}] Alliance: {fund_line}")
        world.meso.quorum_ok = True
        world.append_log(
            (
                f"Alliance quorum met ({len(contributors)}/{len(anti)} Contribute; "
                f"M2 {tech_why}): sync pulse — cohesion {world.meso.cohesion:.0f}, "
                f"pressure {world.qin_pressure:.0f}, "
                f"coal_mil={world.world.military_coalition:.2f}. {fund_line}."
            ),
            event_id="alliance",
            action="quorum_success",
            dials_fired=["quorum", "m2", "alliance_fund"],
        )
        from .chronicle import maybe_write_chronicle
        maybe_write_chronicle(world, reason="alliance", force=True)
    else:
        world.meso.cohesion = max(0.0, world.meso.cohesion - 8.0)
        world.qin_pressure = min(100.0, world.qin_pressure + 7.0)
        if qi:
            qi.state.betrayal_memory = min(1.0, qi.state.betrayal_memory + 0.08)
            qi.intention.current = "withhold"
        if chu:
            chu.state.resentment = min(1.0, chu.state.resentment + 0.06)
        world.meso.quorum_ok = False
        fail_bits = []
        if not psych_ok:
            fail_bits.append(
                f"psych need≥{need} Contribute+Qi/Chu+cohesion≥40 (have {len(contributors)}; annexed/broke excluded)"
            )
        if not tech_ok:
            fail_bits.append(f"M2 {tech_why}")
        world.append_log(
            (
                f"Alliance attempt fails: {'; '.join(fail_bits)}. "
                f"cohesion {world.meso.cohesion:.0f}; "
                f"qin_mil_adv={world.world.qin_mil_advantage:+.2f}. Quake risk up."
            ),
            event_id="alliance",
            action="quorum_fail",
            dials_fired=["quorum", "m2"],
        )

    world.recompute_meso()
    world.meso.pathway_soft = soft_pathway(world)
    world.clamp()
    return world
