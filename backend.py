"""Thin Gradio adapter — projects engine WorldState to UI. No sim math here."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from engine.action_labels import short_label, who_vs_qin_line
from engine.demographics import field_court_economy, field_demographics_summary
from engine.dossiers import dossier_for, dossier_bundle
from engine.geo import M4_TABLE, STATE_GEO, state_geo_card
from engine.packets import conflict_score, packet_public_view, resolve_packet_id
from engine.patron_client import clique_sync, sync_bonus
from engine.tech import field_tech_summary, tech_pressure_delta, tech_quorum_ok, tech_structural_damage
from engine.conflict import ensure_econ_fields, resource_pool
from engine.tick import attempt_alliance as eng_alliance
from engine.tick import intervene_many as eng_intervene_many
from engine.tick import pathway_reading_note
from engine.tick import player_action as eng_player_action
from engine.tick import spend_alliance_fund as eng_spend_fund
from engine.tick import tick as eng_tick
from engine.counsel import counsel_log_texts, run_counsel_round as eng_counsel, suggest_prompt_chips
from engine.trust import chu_clique_strength, get_trust
from engine.world import WorldState, new_world

_ENGINE_KEY = "_engine"

# Legacy alias — prefer dossiers.dossier_for
DOSSIERS = {
    "qin": dossier_for("qin"),
    "chu": dossier_for("chu"),
    "qi": dossier_for("qi"),
    "zhao": dossier_for("zhao"),
    "han": dossier_for("han"),
    "wei": dossier_for("wei"),
    "yan": dossier_for("yan"),
}


def _msg(role: str, content: str) -> dict[str, str]:
    return {"role": role, "content": content}


def _speaker_line(rec: dict[str, Any]) -> tuple[str, str]:
    actor = str(rec.get("actor") or "world")
    text = str(rec.get("text") or "")
    # Cultural chronicle rows always speak as Chronicler (actor may be chronicler/world)
    if str(rec.get("event_id") or "") == "chronicle":
        return "Chronicler", text
    names = {
        "qin": "Qin Court",
        "chu": "Chu Court",
        "qi": "Qi Court",
        "zhao": "Zhao Court",
        "han": "Han Court",
        "wei": "Wei Court",
        "yan": "Yan Court",
        "world": "Chronicler",
        "chronicler": "Chronicler",
    }
    return names.get(actor, actor.title()), text


def _project(world: WorldState) -> dict[str, Any]:
    """UI projection — every meter maps 1:1 to an engine field (no orphan dials)."""
    ensure_econ_fields(world)
    world.recompute_meso()
    agents_snap = {}
    for aid, ag in world.agents.items():
        packets = [resolve_packet_id(p) for p in ag.active_packets]
        agents_snap[aid] = {
            "name": ag.name,
            "bloc": ag.bloc,
            "intention": ag.intention.current,
            "intention_label": short_label(ag.intention.current, bloc=ag.bloc),
            "sticky_until": ag.intention.sticky_until,
            "resentment": ag.state.resentment,
            "fear_of_qin": ag.state.fear_of_qin,
            "betrayal_memory": ag.state.betrayal_memory,
            "status_threat": ag.state.status_threat,
            "withholding_threshold": ag.state.withholding_threshold,
            "perceived_threat": ag.state.perceived_threat,
            "defection_accumulator": int(getattr(ag.state, "defection_accumulator", 0) or 0),
            "viability": float(getattr(ag, "viability", 100.0)),
            "grain": float(getattr(ag, "grain", 60.0)),
            "treasury": float(getattr(ag, "treasury", 60.0)),
            "resources": float(resource_pool(ag)),
            "geographic_yield": float(getattr(ag, "geographic_yield", 0.6)),
            "military": float((getattr(world, "tech", None) and getattr(world.tech, "military", {}) or {}).get(aid, 0.0) or 0.0),
            "tech_adopt": float((getattr(world, "tech", None) and getattr(world.tech, "adoption_mean", {}) or {}).get(aid, 0.0) or 0.0),
            "annexed": bool(getattr(ag, "annexed", False)),
            "annexed_by": getattr(ag, "annexed_by", None),
            "stance_mode": str(getattr(ag, "stance_mode", "coalition") or "coalition"),
            "desperate": bool(getattr(ag, "desperate", False)),
            "packets": packets,
            "packet_views": [packet_public_view(p) for p in packets],
            "logic_conflict": conflict_score(packets),
            "openness": ag.traits.openness,
            "conscientiousness": ag.traits.conscientiousness,
            "extraversion": ag.traits.extraversion,
            "agreeableness": ag.traits.agreeableness,
            "neuroticism": ag.traits.neuroticism,
            "profile_ids": list(getattr(ag, "profile_ids", []) or []),
        }
    # Featured dyadic edges for the field strip (still engine trust[])
    featured_trust = {
        "chu->qi": get_trust(world.trust, "chu", "qi"),
        "qi->chu": get_trust(world.trust, "qi", "chu"),
        "chu->zhao": get_trust(world.trust, "chu", "zhao"),
        "qi->zhao": get_trust(world.trust, "qi", "zhao"),
    }
    world.ensure_baselines()
    run_d = world.run_deltas()
    chu_sync = clique_sync(world.chu_court) if getattr(world, "chu_court", None) else {}
    chu_bonus = sync_bonus(world.chu_court) if getattr(world, "chu_court", None) else {}
    tech_ok, tech_why = tech_quorum_ok(world, cohesion_ok=bool(world.meso.quorum_ok))
    tech_dmg, tech_dmg_why = tech_structural_damage(world)
    # Recent contagion rows for Field / CLI visibility (episode already has full log)
    contagion_recent = [
        rec
        for rec in world.episode[-40:]
        if rec.get("event_id") == "contagion"
    ][-12:]
    geo_by_state = {sid: state_geo_card(sid) for sid in STATE_GEO}
    demography = field_demographics_summary(world)
    court_economy = field_court_economy(world)
    return {
        "tick": world.tick,
        "quarter": max(1, world.tick) if world.tick else 1,
        "year": world.year,
        "quarter_in_year": world.quarter_in_year,
        # Meso / macro — exact engine names
        "qin_pressure": world.qin_pressure,
        "alliance_cohesion": world.meso.cohesion,
        "shared_identity": world.meso.shared_identity,
        "cascade_armed": world.meso.cascade_armed,
        "quorum_ok": world.meso.quorum_ok,
        "pathway_soft": world.meso.pathway_soft,
        "pathway_reading": pathway_reading_note(world),
        "trust": dict(world.trust),
        "featured_trust": featured_trust,
        "agents": agents_snap,
        "last_actions": dict(world.last_actions),
        "last_action_labels": {
            aid: short_label(act, bloc=world.agents[aid].bloc if aid in world.agents else "anti_qin")
            for aid, act in world.last_actions.items()
        },
        "who_vs_qin": who_vs_qin_line(world),
        "episode": list(world.episode),
        "run_deltas": run_d,
        "faction_delta_log": list(world.faction_delta_log[-12:]),
        "chu_court": world.chu_court.to_dict(),
        "chu_sync": chu_sync,
        "chu_sync_meso_bonus": {
            "cohesion": float(chu_bonus.get("cohesion", 0.0)),
            "shared_identity": float(chu_bonus.get("shared_identity", 0.0)),
            "bonded": float(chu_bonus.get("bonded", 0.0)),
            "order_parameter": float(chu_bonus.get("order_parameter", 0.0)),
        },
        "chu_interstate_clique": chu_clique_strength(world),
        "m1": {
            "famine_shock": float(getattr(world.world, "famine_shock", 0.0)),
            "levy_capacity": float(world.world.levy_capacity),
        },
        "m4": {
            "defense_mod": world.world.defense_mod,
            "march_cost": getattr(world.world, "march_cost", 0.5),
            "extraction_mod": getattr(world.world, "extraction_mod", 0.5),
            "levy_capacity": world.world.levy_capacity,
            "qin_projection": getattr(world.world, "qin_projection", 0.4),
            "famine_shock": float(getattr(world.world, "famine_shock", 0.0)),
            "nodes": {
                nid: {
                    "label": n.label,
                    "kind": n.kind,
                    "defense_mod": n.defense_mod,
                    "march_cost": n.march_cost,
                    "levy_mod": n.levy_mod,
                    "qin_pressure_mod": n.qin_pressure_mod,
                }
                for nid, n in M4_TABLE.items()
            },
            "by_state": geo_by_state,
            "honesty": "Coarse M4 table — not GIS",
        },
        "m2": field_tech_summary(world),
        "tech_coupling": {
            "tech_pressure_delta": float(tech_pressure_delta(world)),
            "tech_quorum_ok": bool(tech_ok),
            "tech_quorum_why": tech_why,
            "tech_structural_damage": bool(tech_dmg),
            "tech_structural_why": tech_dmg_why or "",
        },
        "military_qin": float(getattr(world.world, "military_qin", 0.0)),
        "military_coalition": float(getattr(world.world, "military_coalition", 0.0)),
        "qin_mil_advantage": float(getattr(world.world, "qin_mil_advantage", 0.0)),
        "adoption_meter": float(getattr(world.world, "adoption_meter", 0.0)),
        "contagion_recent": contagion_recent,
        "dials": {
            "thermo_dial": float(getattr(world.world, "thermo_dial", 0.5)),
            "evo_dial": float(getattr(world.world, "evo_dial", 0.4)),
        },
        # PLACEHOLDER demographics / satisfaction / available manpower
        "demographics": demography,
        "court_economy": court_economy,
        "satisfaction": float(demography.get("mean_satisfaction", 0.0)),
        "available_manpower": float(demography.get("mean_manpower", 0.0)),
        "run_ended": bool(getattr(world, "run_ended", False)),
        "end_screen": getattr(world, "end_screen", None),
        "demo_mode": getattr(world, "demo_mode", "full"),
        "demo_horizon": getattr(world, "demo_horizon", 8),
        "opening_seen": bool(getattr(world, "opening_seen", False)),
        "player_log": list(getattr(world, "player_log", None) or []),
        "player_political_capital": float(getattr(world, "player_political_capital", 100.0)),
        "player_treasury": float(getattr(world, "player_treasury", 100.0)),
        "alliance_fund_grain": float(getattr(world, "alliance_fund_grain", 0.0)),
        "alliance_fund_treasury": float(getattr(world, "alliance_fund_treasury", 0.0)),
        "alliance_fund_log": list(getattr(world, "alliance_fund_log", None) or []),
        "player_invest_actions_left": int(getattr(world, "player_invest_actions_left", 1)),
        "alliance_attempt_actions_left": int(getattr(world, "alliance_attempt_actions_left", 1)),
        "intervene_actions_left": int(getattr(world, "intervene_actions_left", 1)),
        "alliance_fund_spent_purposes": list(
            getattr(world, "alliance_fund_spent_purposes", None) or []
        ),
        # remaining purpose slots this tick (compat / purse count)
        "alliance_fund_actions_left": max(
            0,
            4 - len(getattr(world, "alliance_fund_spent_purposes", None) or []),
        ),
        "counsel_log": counsel_log_texts(
            world,
            channel=(
                (
                    str((getattr(world, "counsel_session", None) or {}).get("channel") or "")
                    or None
                )
                if (getattr(world, "counsel_session", None) or {}).get("open")
                else None
            ),
        ),
        "chronicle_log": list(getattr(world, "chronicle_log", None) or []),
        "chronicle_mode": str(getattr(world, "chronicle_mode", "stub") or "stub"),
        "pattern_reactions": list(getattr(world, "pattern_reactions", None) or [])[-6:],
        "figure_memory_counts": {
            str(k): len(v or []) for k, v in (getattr(world, "figure_memories", None) or {}).items()
        },
        "last_cultural_state": getattr(world, "last_cultural_state", None),
        "last_cultural_tone": getattr(world, "last_cultural_tone", None),
        "counsel_mode": str(getattr(world, "counsel_mode", "stub") or "stub"),
        "counsel_actions_left": int(getattr(world, "counsel_actions_left", 1)),
        "counsel_session": {
            "open": bool((getattr(world, "counsel_session", None) or {}).get("open")),
            "exchanges": int((getattr(world, "counsel_session", None) or {}).get("exchanges") or 0),
            "cap": int((getattr(world, "counsel_session", None) or {}).get("cap") or 5),
            "figure_id": str((getattr(world, "counsel_session", None) or {}).get("figure_id") or ""),
            "figure_ids": list((getattr(world, "counsel_session", None) or {}).get("figure_ids") or []),
            "mode": str((getattr(world, "counsel_session", None) or {}).get("mode") or ""),
            "channel": str((getattr(world, "counsel_session", None) or {}).get("channel") or ""),
        },
        "counsel_prompt_chips": suggest_prompt_chips(world),
        "talkable_cast": _talkable_cast(world),
        "bce_year": abs(int(getattr(world, "year", -260))),
        "figure_beliefs": {
            k: dict(v) for k, v in (getattr(world, "figure_beliefs", None) or {}).items()
        },
        "last_counsel_tips": getattr(world, "last_counsel_tips", None),
        "last_breakthrough": getattr(world, "last_breakthrough", None),
        # aliases kept only as mirrors of the same engine fields (not separate state)
        "coalition_trust": world.meso.cohesion,
        "pathway": world.meso.pathway_soft,
        "qin_resentment": 100.0 * world.agents["qin"].state.resentment if "qin" in world.agents else 0.0,
        "chu_resentment": 100.0 * world.agents["chu"].state.resentment if "chu" in world.agents else 0.0,
        "qi_trust": 100.0 * get_trust(world.trust, "qi", "chu"),
        _ENGINE_KEY: world.to_dict(),
    }


def _world_from_ui(raw: dict[str, Any] | None) -> WorldState:
    if not raw:
        return new_world()
    eng = raw.get(_ENGINE_KEY)
    if isinstance(eng, dict) and eng.get("agents"):
        world = WorldState.from_dict(eng)
        # Purse / joint fund live on WorldState — trust _engine, then ensure
        # projection-only keys that may exist only at the top level are not required.
        # If _engine omitted fund (legacy), adopt top-level totals when engine is empty.
        eng_g = float(getattr(world, "alliance_fund_grain", 0.0) or 0.0)
        eng_t = float(getattr(world, "alliance_fund_treasury", 0.0) or 0.0)
        if eng_g <= 0.0 and eng_t <= 0.0:
            if "alliance_fund_grain" in raw:
                world.alliance_fund_grain = max(0.0, float(raw["alliance_fund_grain"] or 0.0))
            if "alliance_fund_treasury" in raw:
                world.alliance_fund_treasury = max(0.0, float(raw["alliance_fund_treasury"] or 0.0))
        return world
    world = new_world()
    if "qin_pressure" in raw:
        world.qin_pressure = float(raw["qin_pressure"])
    if "alliance_cohesion" in raw:
        world.meso.cohesion = float(raw["alliance_cohesion"])
    elif "coalition_trust" in raw:
        world.meso.cohesion = float(raw["coalition_trust"])
    if "tick" in raw:
        world.tick = int(raw["tick"])
    elif "quarter" in raw:
        world.tick = int(raw["quarter"])
    if "year" in raw:
        world.year = int(raw["year"])
    if isinstance(raw.get("episode"), list):
        world.episode = list(raw["episode"])
    if "alliance_fund_grain" in raw:
        world.alliance_fund_grain = max(0.0, float(raw["alliance_fund_grain"] or 0.0))
    if "alliance_fund_treasury" in raw:
        world.alliance_fund_treasury = max(0.0, float(raw["alliance_fund_treasury"] or 0.0))
    world.recompute_meso()
    return world


def _chat_from_new_logs(world: WorldState, before_len: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for rec in world.episode[before_len:]:
        speaker, text = _speaker_line(rec)
        if text:
            # FE-style: prefix speaker for chatbot rows
            out.append(_msg("assistant", f"**{speaker}** — {text}"))
    return out


def initial_state() -> dict[str, Any]:
    return _project(new_world())


def advance_quarter(raw: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, str]]]:
    from engine.demo_flow import mark_opening_seen

    world = _world_from_ui(raw)
    mark_opening_seen(world)
    before = len(world.episode)
    eng_tick(world)
    projected = _project(world)
    msgs = _chat_from_new_logs(world, before)
    # Prefer the newest Chronicler line for the portrait dialogue plane
    chron = next(
        (
            rec
            for rec in reversed(world.episode[before:])
            if rec.get("event_id") == "chronicle" and rec.get("text")
        ),
        None,
    )
    if chron:
        projected["advance_dialogue"] = {
            "speaker": "Chronicler",
            "text": str(chron.get("text") or "")[:400],
        }
    return projected, msgs


def intervene_chu(raw: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Backward-compatible single-target Chu intervene."""
    return intervene_targets(raw, ["chu"])


def intervene_targets(
    raw: dict[str, Any] | None,
    targets: list[str] | None,
) -> tuple[dict[str, Any], list[dict[str, str]], str | None]:
    """Returns (projected, chat_msgs, error). error set when intervene budget spent."""
    world = _world_from_ui(raw)
    before = len(world.episode)
    eng_intervene_many(world, list(targets or []))
    err = getattr(world, "last_intervene_error", None)
    return _project(world), _chat_from_new_logs(world, before), err


def do_player_action(
    raw: dict[str, Any] | None,
    action: str,
    target: str = "chu",
) -> tuple[dict[str, Any], list[dict[str, str]], str | None]:
    """Returns (projected, chat_msgs, error). error set when invest is rejected."""
    world = _world_from_ui(raw)
    before = len(world.episode)
    eng_player_action(world, action, target)
    err = getattr(world, "last_player_action_error", None)
    return _project(world), _chat_from_new_logs(world, before), err


def attempt_alliance(
    raw: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, str]], str | None]:
    """Returns (projected, chat_msgs, error). error set when alliance budget spent."""
    world = _world_from_ui(raw)
    before = len(world.episode)
    eng_alliance(world)
    err = getattr(world, "last_alliance_attempt_error", None)
    return _project(world), _chat_from_new_logs(world, before), err


def spend_alliance_fund(
    raw: dict[str, Any] | None,
    purpose: str,
) -> tuple[dict[str, Any], list[dict[str, str]], str | None]:
    """Returns (projected, chat_msgs, error). error set when fund spend is rejected."""
    world = _world_from_ui(raw)
    before = len(world.episode)
    eng_spend_fund(world, purpose)
    err = getattr(world, "last_alliance_fund_error", None)
    return _project(world), _chat_from_new_logs(world, before), err



def _talkable_cast(world: "WorldState") -> list[dict]:
    """Compact picker rows: portrait + English name + talkable/era status.

    First row is always Atmosphere — broadcast counsel every living figure hears.
    """
    from engine.counsel import ATMOSPHERE_ID, living_figures
    from engine.figures import FIGURES, figure_cast_status, figure_label_for, get_figure

    short = {
        "kaolie": "Kaolie",
        "king_you": "King You",
        "chunshen": "Chunshen",
        "chu_nobility": "Chu nobility",
        "zhaoxiang": "Zhaoxiang",
        "ying_zheng": "Ying Zheng",
        "li_si": "Li Si",
        "king_jian": "King Jian",
    }
    living_n = len(living_figures(world))
    out = [{
        "id": ATMOSPHERE_ID,
        "name": "Atmosphere",
        "short": "Atmosphere",
        "label": "General atmosphere",
        "role_label": "Field pressure · all living courts hear",
        "home": "",
        "portrait": f"/static/portraits/{ATMOSPHERE_ID}.jpg",
        "talkable": True,
        "status": "atmosphere",
        "note": f"Broadcast — {living_n} living figure(s) answer",
        "era_unlock_bce": None,
        "allegiance": "",
        "atmosphere": True,
    }]
    for fig in FIGURES:
        fid = fig["id"]
        st = figure_cast_status(world, fid)
        out.append({
            "id": fid,
            "name": short.get(fid, (fig.get("role_label") or fid).split("(")[0].strip()),
            "short": short.get(fid, fid),
            "label": figure_label_for(fid),
            "role_label": fig.get("role_label"),
            "home": fig.get("home"),
            "portrait": f"/static/portraits/{fid}.jpg",
            "talkable": bool(st.get("talkable")),
            "status": st.get("status"),
            "note": st.get("note") or "",
            "era_unlock_bce": fig.get("era_unlock_bce"),
            "allegiance": fig.get("home"),
        })
    return out


def character_ids(raw: dict[str, Any] | None = None) -> list[str]:
    """Named figures for Profile dropdown (incl. Zhaoxiang; Zheng/Li Si era-gated in UI)."""
    from engine.figures import figure_ids

    return figure_ids()


def character_label_map(raw: dict[str, Any] | None = None) -> dict[str, str]:
    from engine.figures import figure_label_map

    return figure_label_map()


def character_choices(raw: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    """Gradio dropdown: (label, value) pairs — values never include bare 'chu'."""
    from engine.figures import figure_dropdown_choices

    return figure_dropdown_choices()


def character_profile(raw: dict[str, Any] | None, agent_id: str) -> dict[str, Any]:
    """Profile for a named figure — OCEAN from JSON, packets/trust from WorldState."""
    from engine.figures import figure_profile, normalize_figure_id

    world = _world_from_ui(raw)
    fid = normalize_figure_id(agent_id)
    prof = figure_profile(world, fid)
    if not prof.get("error"):
        prof["prompt_chips"] = suggest_prompt_chips(world, figure_id=fid)
    return prof


def latest_dialogue(raw: dict[str, Any] | None) -> tuple[str, str]:
    """Speaker + line for FE dialogue box from newest episode row."""
    world = _world_from_ui(raw)
    if not world.episode:
        return "Chronicler", (
            "Late Warring States — quarterly watch. "
            "Advance the clock, intervene in Chu, or attempt alliance quorum."
        )
    return _speaker_line(world.episode[-1])


def bootstrap_dialogue() -> list[dict[str, str]]:
    return [
        _msg(
            "assistant",
            "**Chronicler** — Late Warring States meso field online. "
            "Stances = Contribute / Withhold / Defect **toward the anti-Qin coalition** "
            "(never Qin↔Chu friendship). Qin is the pressure source. "
            "Advance · Intervene (Qin/Chu/Qi) · Short Demo · New Run. "
            "Profile cast: Kaolie, Chunshen, Chu nobility, King Jian, Ying Zheng, Li Si.",
        )
    ]


def arm_short_demo(raw: dict[str, Any] | None, horizon: int = 8) -> dict[str, Any]:
    from engine.demo_flow import mark_opening_seen, set_short_demo

    world = _world_from_ui(raw)
    set_short_demo(world, horizon)
    mark_opening_seen(world)
    return _project(world)


def fresh_run() -> dict[str, Any]:
    from engine.demo_flow import mark_opening_seen

    world = new_world()
    mark_opening_seen(world)
    return _project(world)


SAVE_FORMAT_VERSION = 1


def export_snapshot(
    raw: dict[str, Any] | None,
    chat: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Full WorldState JSON snapshot for Save / localStorage / file download."""
    import time

    world = _world_from_ui(raw)
    eng = world.to_dict()
    return {
        "format": "warring-states-abm",
        "version": SAVE_FORMAT_VERSION,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tick": int(eng.get("tick") or 0),
        "year": eng.get("year"),
        "engine": eng,
        "chat": list(chat or []),
    }


def import_snapshot(snap: dict[str, Any] | None) -> dict[str, Any]:
    """Restore projected UI state from a save snapshot (engine + optional chat)."""
    if not isinstance(snap, dict):
        raise ValueError("snapshot must be a JSON object")
    eng = snap.get("engine") or snap.get(_ENGINE_KEY) or snap.get("world")
    # Allow raw WorldState.to_dict() pasted as the whole body
    if not isinstance(eng, dict) or not eng.get("agents"):
        if isinstance(snap.get("agents"), dict):
            eng = snap
        else:
            raise ValueError("snapshot missing engine.agents")
    world = WorldState.from_dict(eng)
    return _project(world)


def merge_chat(
    history: list[dict[str, str]] | None,
    new_msgs: list[dict[str, str]],
) -> list[dict[str, str]]:
    hist = list(history or [])
    hist.extend(deepcopy(new_msgs))
    return hist


def run_counsel(
    raw: dict[str, Any] | None,
    prompt: str | None = None,
    *,
    commit: bool = False,
    figure_id: str | None = None,
    figure_ids: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]], str | None, dict[str, Any]]:
    """Player channel = collective consciousness; private / circle / atmosphere.

    Free-text / chips fill the same prompt. Multi-turn closes by ~3–5 exchanges
    or commit; dial tips apply on close only. No player OCEAN / decision dossier.
    """
    world = _world_from_ui(raw)
    before = len(world.episode)
    result = eng_counsel(
        world,
        prompt=prompt,
        force_stub=False,
        player_initiated=True,
        commit=bool(commit),
        figure_id=figure_id,
        figure_ids=figure_ids,
    )
    err = None if result.get("ok") else (result.get("error") or "counsel failed")
    projected = _project(world)
    rows = list(result.get("rows") or [])
    focus = str(result.get("figure_id") or figure_id or "") or None
    projected["counsel_result"] = {
        "closed": bool(result.get("closed")),
        "episode_closed": bool(result.get("episode_closed") or result.get("closed")),
        "ready_for_new_episode": bool(
            result.get("ready_for_new_episode")
            or (result.get("closed") and result.get("ok"))
        ),
        "exchange": result.get("exchange"),
        "exchanges_left": result.get("exchanges_left"),
        "mode": result.get("mode"),
        "figure_id": focus,
        "figure_ids": result.get("figure_ids") or figure_ids or [],
        "channel": result.get("channel"),
        "talk_mode": result.get("talk_mode"),
        "prompt_chips": result.get("prompt_chips") or suggest_prompt_chips(world),
        "rows": rows,
        "tips": result.get("tips"),
        "error": result.get("error"),
    }
    # Portrait dialogue box: private counsel never hits world.episode — surface focus reply here
    talk_mode = str(result.get("talk_mode") or "")
    focus_row = next(
        (r for r in rows if str(r.get("figure_id") or "").lower() == str(focus or "").lower()),
        rows[0] if rows else None,
    )
    if focus_row and focus_row.get("utterance"):
        speaker = str(focus_row.get("figure_id") or focus or "Counsel")
        if talk_mode == "atmosphere" or str(focus or "") == "atmosphere":
            speaker = str(focus_row.get("figure_id") or "Atmosphere")
        projected["counsel_dialogue"] = {
            "speaker": speaker,
            "text": str(focus_row.get("utterance") or "")[:280],
        }
    # FE chat stream also needs the spoken lines (episode stays private for sealed talk)
    msgs = _chat_from_new_logs(world, before)
    for row in rows:
        u = str(row.get("utterance") or "").strip()
        if not u:
            continue
        who = str(row.get("figure_id") or "Counsel")
        msgs.append(_msg("assistant", f"**{who}** — {u}"))
    return projected, msgs, err, result
