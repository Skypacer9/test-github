#!/usr/bin/env python3
"""Text playtest REPL for every live engine mechanism — no Gradio.

Launch (from this directory):
  python3 cli.py
  python3 cli.py --help
  python3 -c "from cli import main; raise SystemExit(main())"

Also: python3 -m engine.demo --repl
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from typing import Any

from backend import (
    advance_quarter,
    arm_short_demo,
    attempt_alliance,
    character_ids,
    character_label_map,
    character_profile,
    do_player_action,
    fresh_run,
    intervene_targets,
    spend_alliance_fund,
)
from engine.demo_flow import (
    OPENING_CARD,
    PATHWAY_BLURBS,
    mechanism_lock,
    structural_damage,
)
from engine.packets import BASE_SCHOOLS, COURT_MIXES, PACKET_CATALOG, packet_public_view
from engine.patron_client import clique_sync
from engine.tech import adoption_meter_rows, field_tech_summary
from engine.world import WorldState


HELP = """
Commands (type help for this list):
  new | reset              Fresh WorldState (clears soft-lock)
  advance | tick | step    Advance one quarter
  run N                    Advance N quarters (e.g. run 8)
  intervene [qin|chu|qi…]  Intervene one or more courts (default: chu)
  fund [state]             Fund Military (default chu) — spends PC/Treasury
  grain [state]            Send Grain (default chu)
  mediate [state]          Broker Mediation (default chu); failure → civil war risk
  playerlog | plog         Print Player Log / Shadow Actions
  alliance                 Attempt anti-Qin alliance quorum (pools 15% → joint fund)
  fundspend <purpose>      Spend joint fund: tech|agriculture|construction|military
  jointfund | afund        Show alliance joint fund balances
  short [N]                Arm Short Demo focus (no calendar lock; default 8)
  field | summary          Print meso / M1 / M2 / M4 / pathway field
  profile [figure]         Figure profile (kaolie chunshen chu_nobility
                           ying_zheng li_si king_jian) — default kaolie
  figures                  List figure ids
  trust                    Dyadic trust matrix (featured + all edges)
  packets [state]          Court packet mixes / catalog peek
  m1 | m2 | m4             Force-module detail
  demo | sat | manpower    PLACEHOLDER demographics / satisfaction / manpower
  contagion                Recent belief-contagion episode rows
  dials                    thermo_dial / evo_dial (read-only peek)
  pathway | lock           Soft pathway + mechanism soft-lock status
  chu | patron             Chu patron–client clique sync
  episode [N]              Last N episode rows (default 20)
  opening                  Print opening card text
  who                      Who-vs-Qin stance line
  json                     Dump projected state keys (truncated)
  help | ?                 This help
  quit | exit | q          Leave REPL
""".strip()


def _world(state: dict[str, Any]) -> WorldState:
    eng = state.get("_engine")
    if isinstance(eng, dict) and eng.get("agents"):
        return WorldState.from_dict(eng)
    from engine.world import new_world

    return new_world()


def _print_chat(msgs: list[dict[str, str]]) -> None:
    for m in msgs:
        text = (m.get("content") or "").replace("**", "")
        if text:
            print(f"  · {text}")


def print_quarterly_log(state: dict[str, Any]) -> None:
    """Compact per-quarter stdout block covering every Live + Partial stub system.

    Used by `run N` and `abm_run.py`. One composition per tick — no UI.
    """
    tick = int(state.get("tick") or 0)
    year = state.get("year")
    qiy = state.get("quarter_in_year") or (((tick - 1) % 4) + 1 if tick else 0)
    era = f"{abs(int(year))} BCE" if year is not None else "?"
    print(f"═══ tick={tick}  year={era}  Q{qiy}/4 ═══")
    print(f"  who_vs_qin: {state.get('who_vs_qin')}")

    agents = state.get("agents") or {}
    intent_bits = []
    pas_bits = []
    for aid in ("qin", "chu", "qi", "zhao", "han", "wei", "yan"):
        ag = agents.get(aid) or {}
        lab = ag.get("intention_label") or ag.get("intention") or "?"
        intent_bits.append(f"{aid}:{lab}")
        if aid in ("qin", "chu", "qi"):
            via = float(ag.get("viability", 100) or 100)
            tag = " ANNEXED" if ag.get("annexed") else (" DESPERATE" if ag.get("desperate") else "")
            pas_bits.append(
                f"{aid} O={float(ag.get('openness', 0)):.2f}"
                f" A={float(ag.get('agreeableness', 0)):.2f}"
                f" threat={float(ag.get('perceived_threat', 0)):.2f}"
                f" fear={float(ag.get('fear_of_qin', 0)):.2f}"
                f" betray={float(ag.get('betrayal_memory', 0)):.2f}"
                f" resent={float(ag.get('resentment', 0)):.2f}"
                f" via={via:.0f}"
                f" g/t={float(ag.get('grain', 0)):.0f}/{float(ag.get('treasury', 0)):.0f}"
                f"{tag}"
            )
    print("  intentions: " + " | ".join(intent_bits))
    print("  PAS: " + " · ".join(pas_bits))
    print(
        f"  player: PC={float(state.get('player_political_capital') or 0):.0f}  "
        f"Treasury={float(state.get('player_treasury') or 0):.0f}  "
        f"alliance_fund g/t="
        f"{float(state.get('alliance_fund_grain') or 0):.1f}/"
        f"{float(state.get('alliance_fund_treasury') or 0):.1f}"
    )
    plog = state.get("player_log") or []
    if plog:
        print("  player_log (last 3):")
        for line in plog[-3:]:
            print(f"    · {line}")

    print(
        f"  meters: qin_pressure={float(state.get('qin_pressure') or 0):.1f}  "
        f"cohesion={float(state.get('alliance_cohesion') or 0):.1f}  "
        f"shared_id={float(state.get('shared_identity') or 0):.1f}  "
        f"cascade={state.get('cascade_armed')}  quorum={state.get('quorum_ok')}"
    )

    path = state.get("pathway_soft")
    reading = state.get("pathway_reading") or ""
    lock_note = "no"
    if state.get("run_ended"):
        end = state.get("end_screen") or {}
        lock_note = (
            f"LOCKED mech={end.get('mechanism')} "
            f"({end.get('reason') or end.get('lock_kind')})"
        )
    print(f"  pathway={path}  soft-lock={lock_note}")
    if reading:
        print(f"  pathway_reading: {reading}")

    ft = state.get("featured_trust") or {}
    if ft:
        print(
            "  trust★: "
            + ", ".join(f"{k}={float(v):.2f}" for k, v in sorted(ft.items()))
        )

    pkt_bits = []
    for aid in ("qin", "chu", "qi"):
        ag = agents.get(aid) or {}
        pkt_bits.append(
            f"{aid}={ag.get('packets')} conflict={ag.get('logic_conflict')}"
        )
    print("  packets: " + " | ".join(pkt_bits))
    contagion = state.get("contagion_recent") or []
    if contagion:
        last = contagion[-1]
        ctext = (last.get("text") or "")[:110]
        print(f"  contagion: {ctext}")
    else:
        print("  contagion: (none this window)")

    sync = state.get("chu_sync") or {}
    meso_b = state.get("chu_sync_meso_bonus") or {}
    print(
        f"  Chu patron: order={sync.get('order_parameter', sync.get('order', '?'))} "
        f"bonded={sync.get('bonded')}  "
        f"interstate={float(state.get('chu_interstate_clique') or 0):.2f}  "
        f"meso_bonus c+{float(meso_b.get('cohesion') or 0):.1f}/"
        f"sid+{float(meso_b.get('shared_identity') or 0):.1f}"
    )

    m1 = state.get("m1") or {}
    m4 = state.get("m4") or {}
    print(
        f"  M1: famine={float(m1.get('famine_shock') or 0):.2f} "
        f"levy={float(m1.get('levy_capacity') or 0):.2f}  |  "
        f"M4: def={float(m4.get('defense_mod') or 0):.2f} "
        f"march={float(m4.get('march_cost') or 0):.2f} "
        f"extract={float(m4.get('extraction_mod') or 0):.2f} "
        f"qin_proj={float(m4.get('qin_projection') or 0):.2f}"
    )
    tc = state.get("tech_coupling") or {}
    print(
        f"  M2: qin_mil={float(state.get('military_qin') or 0):.2f} "
        f"coal={float(state.get('military_coalition') or 0):.2f} "
        f"adv={float(state.get('qin_mil_advantage') or 0):+.2f} "
        f"adopt={float(state.get('adoption_meter') or 0):.2f}  "
        f"tech_ΔP={float(tc.get('tech_pressure_delta') or 0):+.2f} "
        f"tech_quorum={tc.get('tech_quorum_ok')} "
        f"struct_dmg={tc.get('tech_structural_damage')}"
    )

    demo = state.get("demographics") or {}
    print(
        f"  PLACEHOLDER demo/sat/manpower: "
        f"sat={float(state.get('satisfaction') or demo.get('mean_satisfaction') or 0):.2f} "
        f"manpower={float(state.get('available_manpower') or demo.get('mean_manpower') or 0):.2f} "
        f"pop={float(demo.get('mean_population') or 0):.2f}"
    )
    dials = state.get("dials") or {}
    if dials:
        print(
            f"  dials: thermo={dials.get('thermo_dial')} evo={dials.get('evo_dial')}"
        )


def cmd_field(state: dict[str, Any]) -> None:
    w = _world(state)
    print("─ FIELD ─")
    print(
        f"  tick=Q{state.get('tick', 0)}  year={state.get('year')}  "
        f"demo={state.get('demo_mode')}  ended={state.get('run_ended')}"
    )
    print(
        f"  qin_pressure={state.get('qin_pressure'):.1f}  "
        f"cohesion={state.get('alliance_cohesion'):.1f}  "
        f"shared_id={state.get('shared_identity'):.1f}"
    )
    print(
        f"  cascade_armed={state.get('cascade_armed')}  "
        f"quorum_ok={state.get('quorum_ok')}  "
        f"pathway={state.get('pathway_soft')}"
    )
    reading = state.get("pathway_reading") or ""
    if reading:
        print(f"  pathway_reading: {reading}")
    print(f"  who_vs_qin: {state.get('who_vs_qin')}")
    ft = state.get("featured_trust") or {}
    print(
        "  featured trust: "
        + ", ".join(f"{k}={v:.2f}" for k, v in sorted(ft.items()))
    )
    m1 = state.get("m1") or {}
    m4 = state.get("m4") or {}
    m2 = state.get("m2") or {}
    print(
        f"  M1 famine={m1.get('famine_shock', 0):.2f} "
        f"levy={m1.get('levy_capacity', 0):.2f}"
    )
    print(
        f"  M4 def={m4.get('defense_mod', 0):.2f} "
        f"march={m4.get('march_cost', 0):.2f} "
        f"extract={m4.get('extraction_mod', 0):.2f} "
        f"qin_proj={m4.get('qin_projection', 0):.2f}"
    )
    print(
        f"  M2 qin_mil={state.get('military_qin', 0):.2f} "
        f"coal_mil={state.get('military_coalition', 0):.2f} "
        f"adv={state.get('qin_mil_advantage', 0):+.2f} "
        f"adopt={state.get('adoption_meter', 0):.2f}"
    )
    if m2:
        print(f"  M2 summary keys: {', '.join(sorted(m2.keys())[:12])}")
    sync = state.get("chu_sync") or {}
    if sync:
        print(
            f"  Chu sync: order={sync.get('order_parameter', sync.get('order', '?'))} "
            f"bonded={sync.get('bonded')}  "
            f"interstate_clique={state.get('chu_interstate_clique', 0):.2f}"
        )
    meso_b = state.get("chu_sync_meso_bonus") or {}
    if meso_b:
        print(
            f"  Chu→meso bonus: cohesion+{meso_b.get('cohesion', 0):.1f} "
            f"shared_id+{meso_b.get('shared_identity', 0):.1f} "
            f"(bonded={meso_b.get('bonded')})"
        )
    tc = state.get("tech_coupling") or {}
    if tc:
        print(
            f"  tech_coupling: pressure_Δ={tc.get('tech_pressure_delta', 0):+.2f} "
            f"quorum={tc.get('tech_quorum_ok')} ({tc.get('tech_quorum_why')}) "
            f"struct_dmg={tc.get('tech_structural_damage')}"
        )
    demo = state.get("demographics") or {}
    print(
        f"  PLACEHOLDER demo: sat={state.get('satisfaction', demo.get('mean_satisfaction', 0)):.2f} "
        f"manpower={state.get('available_manpower', demo.get('mean_manpower', 0)):.2f} "
        f"pop={demo.get('mean_population', 0):.2f}"
    )
    dials = state.get("dials") or {}
    if dials:
        print(
            f"  dials: thermo={dials.get('thermo_dial', '?')} "
            f"evo={dials.get('evo_dial', '?')}"
        )
    contagion = state.get("contagion_recent") or []
    if contagion:
        last = contagion[-1]
        print(
            f"  last contagion: {last.get('text', '')[:100]}"
        )
    if state.get("run_ended"):
        end = state.get("end_screen") or {}
        print(
            f"  SOFT-LOCK: mech={end.get('mechanism')} "
            f"pathway={end.get('pathway')} — {end.get('reason')}"
        )
    # Intention strip
    agents = state.get("agents") or {}
    bits = []
    for aid in ("qin", "chu", "qi", "zhao", "han", "wei", "yan"):
        ag = agents.get(aid) or {}
        lab = ag.get("intention_label") or ag.get("intention") or "?"
        bits.append(f"{aid}:{lab}")
    print("  intentions: " + " | ".join(bits))
    _ = w  # kept for future world-only peeks


def cmd_profile(state: dict[str, Any], fid: str = "kaolie") -> None:
    prof = character_profile(state, fid)
    if prof.get("error"):
        print(f"  profile error: {prof['error']}")
        return
    title = prof.get("name") or prof.get("label") or prof.get("id") or fid
    print(f"─ PROFILE · {title} ─")
    print(f"  id={prof.get('id')}  role={prof.get('role_label')}  home={prof.get('home_court') or prof.get('home')}")
    intent = prof.get("intention")
    if isinstance(intent, dict):
        print(
            f"  intention: {intent.get('label') or intent.get('current')} "
            f"(sticky_until={intent.get('sticky_until')})"
        )
    elif intent:
        print(f"  intention: {intent}")
    dossier = prof.get("dossier")
    if dossier:
        print(f"  dossier: {dossier[:220]}{'…' if len(str(dossier)) > 220 else ''}")
    note = prof.get("syncretism_note")
    if note:
        print(f"  syncretism: {note[:180]}{'…' if len(str(note)) > 180 else ''}")
    ocean = prof.get("big_five") or prof.get("ocean") or {}
    if not ocean:
        ocean = {
            k: prof.get(k)
            for k in (
                "openness",
                "conscientiousness",
                "extraversion",
                "agreeableness",
                "neuroticism",
            )
            if k in prof
        }
    if ocean:
        print(
            "  OCEAN: "
            + ", ".join(f"{k[0].upper()}={float(v):.2f}" for k, v in ocean.items())
        )
    state_layer = prof.get("state") or {}
    if state_layer:
        print(
            "  state: "
            + ", ".join(
                f"{k}={float(v):.2f}" if isinstance(v, (int, float)) else f"{k}={v}"
                for k, v in state_layer.items()
                if v is not None
            )
        )
    pk = prof.get("packets") or []
    if pk:
        print(f"  packets: {pk}")
    bases = prof.get("base_schools") or {}
    if bases:
        print(
            "  base_schools: "
            + ", ".join(f"{k}={float(v):.2f}" for k, v in bases.items())
        )
    tw = prof.get("dyadic_trust") or prof.get("trust") or {}
    if tw:
        items = list(tw.items())[:12]
        print(
            "  trust: "
            + ", ".join(
                f"{k}={float(v):.2f}" if isinstance(v, (int, float)) else f"{k}={v}"
                for k, v in items
            )
        )


def cmd_trust(state: dict[str, Any]) -> None:
    trust = state.get("trust") or {}
    print("─ TRUST (asymmetric i→j) ─")
    ft = state.get("featured_trust") or {}
    print("  featured:")
    for k, v in sorted(ft.items()):
        print(f"    {k}: {v:.3f}")
    print("  all edges:")
    for k in sorted(trust.keys()):
        print(f"    {k}: {float(trust[k]):.3f}")


def cmd_packets(state: dict[str, Any], focus: str | None = None) -> None:
    print("─ PACKETS ─")
    print("  four bases: " + ", ".join(f"{s}→{pid}" for s, pid in BASE_SCHOOLS.items()))
    print(f"  catalog size: {len(PACKET_CATALOG)}")
    if focus:
        focus = focus.lower()
        mix = COURT_MIXES.get(focus)
        if mix:
            print(f"  COURT_MIXES[{focus}]: {mix}")
        agents = state.get("agents") or {}
        ag = agents.get(focus)
        if ag:
            print(f"  live {focus} packets: {ag.get('packets')}")
            print(f"  logic_conflict: {ag.get('logic_conflict')}")
            for pv in ag.get("packet_views") or []:
                print(
                    f"    · {pv.get('id')} [{pv.get('kind')}] "
                    f"logic={pv.get('logic_id')} str={pv.get('strength')}"
                )
        elif not mix:
            # catalog peek
            pkt = PACKET_CATALOG.get(focus) or packet_public_view(focus)
            if pkt:
                print(f"  packet {focus}: {pkt if isinstance(pkt, dict) else pkt}")
            else:
                print(f"  unknown focus '{focus}' (try qin/chu/qi or a packet id)")
        return
    print("  court mixes:")
    for sid, mix in COURT_MIXES.items():
        top = sorted(mix.items(), key=lambda x: -x[1])[:4]
        print(f"    {sid}: " + ", ".join(f"{k}={v:.2f}" for k, v in top))
    agents = state.get("agents") or {}
    print("  live active packets:")
    for aid in ("qin", "chu", "qi", "zhao", "han", "wei", "yan"):
        ag = agents.get(aid) or {}
        print(f"    {aid}: {ag.get('packets')} conflict={ag.get('logic_conflict')}")


def cmd_m1(state: dict[str, Any]) -> None:
    m1 = state.get("m1") or {}
    print("─ M1 demographics/env (coarse) ─")
    print(f"  famine_shock={m1.get('famine_shock')}")
    print(f"  levy_capacity={m1.get('levy_capacity')}")
    print("  (deterministic haircut in geo.apply_m1_env on ticks %5 / %11)")
    print("  PLACEHOLDER court demography → see `demo` / `sat` / `manpower`")


def cmd_m2(state: dict[str, Any]) -> None:
    w = _world(state)
    print("─ M2 tech DAG + Adoption Meter ─")
    print(
        f"  military_qin={state.get('military_qin'):.3f}  "
        f"military_coalition={state.get('military_coalition'):.3f}  "
        f"qin_mil_advantage={state.get('qin_mil_advantage'):+.3f}"
    )
    print(f"  adoption_meter={state.get('adoption_meter'):.3f}")
    tc = state.get("tech_coupling") or {}
    if tc:
        print(
            f"  coupling → pressure_Δ={tc.get('tech_pressure_delta', 0):+.3f}  "
            f"quorum_ok={tc.get('tech_quorum_ok')} ({tc.get('tech_quorum_why')})"
        )
        print(
            f"  structural_damage={tc.get('tech_structural_damage')} "
            f"{tc.get('tech_structural_why') or ''}".rstrip()
        )
    summary = state.get("m2") or field_tech_summary(w)
    if isinstance(summary, dict):
        for k, v in sorted(summary.items()):
            if k == "rows":
                continue
            print(f"  {k}: {v}")
    rows = adoption_meter_rows(w)[:8]
    if rows:
        print("  adoption rows (Qin/Chu/Qi sample):")
        for r in rows:
            nid = r.get("id") or r.get("node") or "?"
            label = r.get("label") or ""
            print(
                f"    {nid} ({label}): "
                f"Qin known={r.get('qin_known')} adopt={r.get('qin_adopted')} | "
                f"Chu known={r.get('chu_known')} adopt={r.get('chu_adopted')} | "
                f"Qi known={r.get('qi_known')} adopt={r.get('qi_adopted')}"
            )


def cmd_m4(state: dict[str, Any]) -> None:
    m4 = state.get("m4") or {}
    print("─ M4 geography (table, not GIS) ─")
    for k in (
        "defense_mod",
        "march_cost",
        "extraction_mod",
        "levy_capacity",
        "qin_projection",
        "famine_shock",
    ):
        if k in m4:
            print(f"  {k}={m4[k]}")
    nodes = m4.get("nodes") or {}
    if nodes:
        print("  nodes:")
        for nid, n in sorted(nodes.items()):
            print(
                f"    {nid}: {n.get('label')} [{n.get('kind')}] "
                f"def={n.get('defense_mod')} march={n.get('march_cost')} "
                f"levy={n.get('levy_mod')} qin_mod={n.get('qin_pressure_mod')}"
            )
    by_state = m4.get("by_state") or {}
    if by_state:
        print("  by_state cards:")
        for sid, cards in sorted(by_state.items()):
            labels = ", ".join(c.get("label") or c.get("id") or "?" for c in cards)
            print(f"    {sid}: {labels}")


def cmd_demo(state: dict[str, Any], focus: str | None = None) -> None:
    """PLACEHOLDER demographics / satisfaction / available manpower."""
    demo = state.get("demographics") or {}
    print("─ DEMOGRAPHICS / SATISFACTION / MANPOWER (PLACEHOLDER) ─")
    print(f"  honesty: {demo.get('honesty') or 'uncalibrated stubs'}")
    print(
        f"  means: sat={state.get('satisfaction', demo.get('mean_satisfaction', 0)):.3f}  "
        f"manpower={state.get('available_manpower', demo.get('mean_manpower', 0)):.3f}  "
        f"pop={demo.get('mean_population', 0):.3f}"
    )
    courts = demo.get("courts") or {}
    focus = (focus or "").lower() or None
    ids = [focus] if focus and focus in courts else list(courts.keys())
    for cid in ids:
        c = courts.get(cid) or {}
        print(
            f"  {cid}: pop={c.get('population', 0):.2f} "
            f"levy_base={c.get('levy_base', 0):.2f} "
            f"urban={c.get('urban_share', 0):.2f} "
            f"sat={c.get('satisfaction', 0):.2f} "
            f"manpower={c.get('available_manpower', 0):.2f}"
        )
    print("  soft hooks: tiny levy/cohesion/pressure/military nudges only — not calibrated")


def cmd_contagion(state: dict[str, Any], n: int = 12) -> None:
    rows = state.get("contagion_recent") or []
    if not rows:
        # Fall back to episode filter
        rows = [
            rec
            for rec in (state.get("episode") or [])
            if rec.get("event_id") == "contagion"
        ][-n:]
    print(f"─ CONTAGION (last {min(n, len(rows))} of recent) ─")
    if not rows:
        print("  (none yet — advance quarters; M3 logs adopt/reinforce along trust edges)")
        return
    for rec in rows[-n:]:
        t = rec.get("tick", "?")
        text = (rec.get("text") or "").replace("\n", " ")
        if len(text) > 140:
            text = text[:140] + "…"
        print(f"  [t{t}] {text}")


def cmd_dials(state: dict[str, Any]) -> None:
    dials = state.get("dials") or {}
    print("─ DIALS (read-only peek; CLI setters still thin) ─")
    print(f"  thermo_dial={dials.get('thermo_dial')}")
    print(f"  evo_dial={dials.get('evo_dial')}")
    print("  thermo → M1 famine size / M4 pressure slope; evo → contagion + tech adoption")


def cmd_pathway(state: dict[str, Any]) -> None:
    w = _world(state)
    path = state.get("pathway_soft") or w.meso.pathway_soft
    print("─ PATHWAY + SOFT-LOCK ─")
    print(f"  pathway_soft={path}")
    print(f"  blurb: {PATHWAY_BLURBS.get(path, PATHWAY_BLURBS['other'])}")
    reading = state.get("pathway_reading") or ""
    print(f"  reading: {reading or '(none — observational détente gloss only when meters fit)'}")
    print(
        f"  sticky_count={getattr(w, 'pathway_stable_count', 0)}  "
        f"last_pathway={getattr(w, 'last_pathway', None)}"
    )
    damaged, dead, cohesion_down, tech_note = structural_damage(w)
    print(
        f"  structural_damage={damaged}  dead_edges={len(dead)}  "
        f"cohesion_collapsed={cohesion_down}  tech={tech_note or 'ok'}"
    )
    if dead:
        print(f"  dead sample: {', '.join(dead[:8])}")
    mech, reason = mechanism_lock(w)
    print(f"  would_lock_now: {mech or 'no'} — {reason or 'no mechanism fire'}")
    print(f"  run_ended={state.get('run_ended')}")
    if state.get("end_screen"):
        end = state["end_screen"]
        print(
            f"  end_screen: kind={end.get('lock_kind')} mech={end.get('mechanism')} "
            f"reason={end.get('reason')}"
        )
    print("  lock rules: (1) qin_path+damage  (2) cascade+betrayal+quorum death  "
          "(3) sticky pathway+damage — never Q-count, never stalemate alone")


def cmd_chu(state: dict[str, Any]) -> None:
    w = _world(state)
    print("─ CHU PATRON–CLIENT ─")
    court = state.get("chu_court") or {}
    sync = state.get("chu_sync") or (clique_sync(w.chu_court) if w.chu_court else {})
    print(f"  sync: {sync}")
    print(f"  interstate_clique={state.get('chu_interstate_clique')}")
    meso_b = state.get("chu_sync_meso_bonus") or {}
    if meso_b:
        print(
            f"  feeds meso: cohesion+{meso_b.get('cohesion', 0):.1f} "
            f"shared_identity+{meso_b.get('shared_identity', 0):.1f} "
            f"when bonded/order high (applied in tick_patron_graph)"
        )
    edges = court.get("edges") or {}
    if edges:
        print("  court edges:")
        for k, v in sorted(edges.items()):
            print(f"    {k}: {float(v):.3f}")
    nodes = court.get("nodes") or court.get("hubs") or []
    if nodes:
        print(f"  nodes: {nodes}")


def cmd_episode(state: dict[str, Any], n: int = 20) -> None:
    ep = state.get("episode") or []
    print(f"─ EPISODE (last {n} of {len(ep)}) ─")
    for rec in ep[-n:]:
        t = rec.get("tick", "?")
        actor = rec.get("actor") or "world"
        action = rec.get("action") or ""
        text = (rec.get("text") or "").replace("\n", " ")
        if len(text) > 160:
            text = text[:160] + "…"
        print(f"  [t{t}] {actor}/{action}: {text}")


def cmd_opening() -> None:
    print(f"─ {OPENING_CARD['title']} ─")
    print(OPENING_CARD["body"])
    print("irreversibles:")
    for line in OPENING_CARD.get("irreversibles_preview") or []:
        print(f"  · {line}")


def dispatch(state: dict[str, Any], line: str) -> dict[str, Any] | None:
    """Run one command. Returns new state, or None to quit."""
    line = line.strip()
    if not line:
        return state
    try:
        parts = shlex.split(line)
    except ValueError as e:
        print(f"  parse error: {e}")
        return state
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in ("quit", "exit", "q"):
        return None
    if cmd in ("help", "?", "h"):
        print(HELP)
        return state
    if cmd in ("new", "reset", "fresh"):
        state = fresh_run()
        print("  New run. tick=0, soft-lock cleared.")
        cmd_field(state)
        return state
    if cmd in ("advance", "tick", "step"):
        state, msgs = advance_quarter(state)
        print(f"  Advanced → tick={state.get('tick')} pathway={state.get('pathway_soft')}")
        _print_chat(msgs[-6:])
        if state.get("run_ended"):
            print(f"  *** soft-locked: {(state.get('end_screen') or {}).get('reason')}")
        return state
    if cmd == "run":
        n = int(args[0]) if args else 4
        n = max(1, min(n, 80))
        print(f"  Running {n} quarters (Live-system quarterly log)…")
        for i in range(n):
            state, msgs = advance_quarter(state)
            print_quarterly_log(state)
            # One-line chronicler peek (summary + soft-lock / contagion if any)
            for m in msgs:
                text = (m.get("content") or "").replace("**", "")
                if "Qin pressure" in text or "soft-lock" in text.lower() or "Belief contagion" in text:
                    print(f"  · {text[:160]}")
            if state.get("run_ended"):
                print(f"  soft-lock at tick={state.get('tick')} after {i + 1} advances")
                break
        else:
            print(f"  done tick={state.get('tick')} pathway={state.get('pathway_soft')}")
        return state
    if cmd in ("intervene", "int"):
        targets = [a.lower() for a in args] if args else ["chu"]
        bad = [t for t in targets if t not in ("qin", "chu", "qi")]
        if bad:
            print(f"  intervene targets must be qin/chu/qi (got {bad})")
            return state
        state, msgs, err = intervene_targets(state, targets)
        if err:
            print(f"  ! {err}")
        print(f"  Intervened: {targets}")
        _print_chat(msgs)
        return state
    if cmd in ("fund", "fund_military", "military"):
        target = (args[0] if args else "chu").lower()
        state, msgs, err = do_player_action(state, "fund_military", target)
        if err:
            print(f"  ! {err}")
        else:
            print(f"  Fund Military → {target}  PC={state.get('player_political_capital'):.0f} Treasury={state.get('player_treasury'):.0f}")
        _print_chat(msgs)
        return state
    if cmd in ("grain", "send_grain", "send"):
        target = (args[0] if args else "chu").lower()
        state, msgs, err = do_player_action(state, "send_grain", target)
        if err:
            print(f"  ! {err}")
        else:
            print(f"  Send Grain → {target}  PC={state.get('player_political_capital'):.0f} Treasury={state.get('player_treasury'):.0f}")
        _print_chat(msgs)
        return state
    if cmd in ("mediate", "mediation", "broker", "broker_mediation"):
        target = (args[0] if args else "chu").lower()
        state, msgs, err = do_player_action(state, "broker_mediation", target)
        if err:
            print(f"  ! {err}")
        else:
            print(f"  Broker Mediation → {target}  PC={state.get('player_political_capital'):.0f} Treasury={state.get('player_treasury'):.0f}")
        _print_chat(msgs)
        return state
    if cmd in ("playerlog", "plog", "shadow"):
        plog = state.get("player_log") or []
        print("─ PLAYER LOG / SHADOW ─")
        if not plog:
            print("  (empty)")
        for line in plog:
            print(f"  {line}")
        return state
    if cmd in ("alliance", "ally", "quorum"):
        state, msgs, err = attempt_alliance(state)
        if err:
            print(f"  ! {err}")
        print(
            f"  Alliance attempt → quorum_ok={state.get('quorum_ok')} "
            f"cohesion={state.get('alliance_cohesion'):.1f}  "
            f"joint_fund g/t="
            f"{float(state.get('alliance_fund_grain') or 0):.1f}/"
            f"{float(state.get('alliance_fund_treasury') or 0):.1f}"
        )
        _print_chat(msgs)
        return state
    if cmd in ("fundspend", "afspend", "spendfund"):
        purpose = (args[0] if args else "").lower()
        if not purpose:
            print("  usage: fundspend tech|agriculture|construction|military")
            return state
        state, msgs, err = spend_alliance_fund(state, purpose)
        if err:
            print(f"  ! {err}")
        else:
            print(
                f"  Alliance fund → {purpose}  "
                f"g/t={float(state.get('alliance_fund_grain') or 0):.1f}/"
                f"{float(state.get('alliance_fund_treasury') or 0):.1f}"
            )
        _print_chat(msgs)
        return state
    if cmd in ("jointfund", "afund", "alliancefund"):
        print("─ ALLIANCE JOINT FUND ─")
        print(
            f"  grain={float(state.get('alliance_fund_grain') or 0):.1f}  "
            f"treasury={float(state.get('alliance_fund_treasury') or 0):.1f}"
        )
        for line in (state.get("alliance_fund_log") or [])[-8:]:
            print(f"  · {line}")
        return state
    if cmd == "short":
        horizon = int(args[0]) if args else 8
        state = arm_short_demo(state, horizon)
        print(f"  Short Demo armed (horizon recorded={horizon}; no calendar lock).")
        return state
    if cmd in ("field", "summary", "status", "s"):
        cmd_field(state)
        return state
    if cmd in ("profile", "fig", "figure"):
        fid = args[0] if args else "kaolie"
        cmd_profile(state, fid)
        return state
    if cmd in ("figures", "cast"):
        labels = character_label_map()
        print("─ FIGURES ─")
        for fid in character_ids():
            print(f"  {fid}: {labels.get(fid, fid)}")
        return state
    if cmd == "trust":
        cmd_trust(state)
        return state
    if cmd in ("packets", "packet"):
        cmd_packets(state, args[0] if args else None)
        return state
    if cmd == "m1":
        cmd_m1(state)
        return state
    if cmd == "m2":
        cmd_m2(state)
        return state
    if cmd == "m4":
        cmd_m4(state)
        return state
    if cmd in ("demo", "demographics", "sat", "satisfaction", "manpower", "mp"):
        focus = args[0] if args else None
        cmd_demo(state, focus)
        return state
    if cmd in ("contagion", "contag"):
        n = int(args[0]) if args else 12
        cmd_contagion(state, n)
        return state
    if cmd in ("dials", "dial"):
        cmd_dials(state)
        return state
    if cmd in ("pathway", "lock", "softlock"):
        cmd_pathway(state)
        return state
    if cmd in ("chu", "patron", "sync"):
        cmd_chu(state)
        return state
    if cmd in ("episode", "log", "ep"):
        n = int(args[0]) if args else 20
        cmd_episode(state, n)
        return state
    if cmd == "opening":
        cmd_opening()
        return state
    if cmd == "who":
        print(f"  {state.get('who_vs_qin')}")
        return state
    if cmd == "json":
        slim = {k: v for k, v in state.items() if k != "_engine"}
        text = json.dumps(slim, indent=2, default=str)
        print(text[:4000] + ("…" if len(text) > 4000 else ""))
        return state

    print(f"  unknown command '{cmd}' — type help")
    return state


def repl(state: dict[str, Any] | None = None) -> int:
    state = state or fresh_run()
    print("Warring States — text playtest CLI (no Gradio)")
    print("Type help for commands. Starting field:")
    cmd_field(state)
    print()
    while True:
        try:
            line = input("ws> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        nxt = dispatch(state, line)
        if nxt is None:
            break
        state = nxt
    print("bye")
    return 0


def run_script(commands: list[str], state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Non-interactive: run a list of command lines; return final state."""
    state = state or fresh_run()
    for line in commands:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        print(f"ws> {line}")
        nxt = dispatch(state, line)
        if nxt is None:
            break
        state = nxt
    return state


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Text playtest CLI for Warring States engine mechanisms"
    )
    p.add_argument(
        "-c",
        "--command",
        action="append",
        dest="commands",
        help="Run a command then continue (repeatable). Implies non-interactive if no --repl.",
    )
    p.add_argument(
        "--script",
        type=str,
        help="Path to a file of commands (one per line)",
    )
    p.add_argument(
        "--repl",
        action="store_true",
        help="Enter interactive REPL after scripted commands",
    )
    p.add_argument(
        "--batch",
        action="store_true",
        help="Non-interactive only (default when -c/--script given)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    commands: list[str] = []
    if args.script:
        with open(args.script, encoding="utf-8") as f:
            commands.extend(f.readlines())
    if args.commands:
        commands.extend(args.commands)

    if commands:
        state = run_script(commands)
        if args.repl and not args.batch:
            return repl(state)
        return 0

    # No scripted commands → interactive REPL
    return repl()


if __name__ == "__main__":
    raise SystemExit(main())
