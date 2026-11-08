"""Named historical figures for Character Profile — not one generic per state.

Each figure maps to docs/big-five-historical-profiles.json + a home court agent
in WorldState (OCEAN from JSON; packets/trust from court + Chu hub–spoke overlay).
No Ling / fiction cast.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .packets import (
    COURT_MIXES,
    conflict_score,
    expand_to_base_schools,
    normalize_packet_list,
    packet_public_view,
    starting_packets,
    starting_weights,
)
from .profiles import profile_by_id
from .trust import get_trust

if TYPE_CHECKING:
    from .world import WorldState

# Dropdown order — court groups (Chu court first so "chu" is never a choice id)
FIGURES: list[dict[str, Any]] = [
    {
        "id": "kaolie",
        "profile_id": "chu-king-kaolie",
        "home": "chu",
        "court_group": "Chu court",
        "court_node": "kaolie",
        "role_label": "King of Chu (royal hub)",
        "speech_role": "ruler",
        "era_exit_bce": 238,  # historical death ~238 BCE — locks when year ≤ 238
        "packet_bias": {
            "dao_guodian": 0.30,
            "chu_patron_client": 0.30,
            "lineage_shi": 0.20,
            "huang_lao": 0.12,
            "tianxia_da_yitong": 0.08,
        },
    },
    {
        "id": "king_you",
        "profile_id": "chu-king-you",
        "home": "chu",
        "court_group": "Chu court",
        "court_node": "kaolie",  # inherits royal hub node; weak successor
        "role_label": "King You of Chu (weak successor)",
        "speech_role": "ruler",
        "era_unlock_bce": 238,  # talkable when BCE year ≤ 238 (Kaolie exits)
        "packet_bias": {
            "chu_patron_client": 0.28,
            "lineage_shi": 0.28,
            "dao_guodian": 0.22,
            "huang_lao": 0.12,
            "tianxia_da_yitong": 0.10,
        },
    },
    {
        "id": "chunshen",
        "profile_id": "chu-lord-chunshen",
        "home": "chu",
        "court_group": "Chu court",
        "court_node": "chunshen",
        "role_label": "Lord Chunshen (patron hub)",
        "speech_role": "minister",
        "packet_bias": {
            "chu_patron_client": 0.35,
            "tianxia_da_yitong": 0.25,
            "dao_guodian": 0.20,
            "huang_lao": 0.10,
            "lineage_shi": 0.10,
        },
    },
    {
        "id": "chu_nobility",
        "profile_id": "chu-nobility-faction",
        "home": "chu",
        "court_group": "Chu court",
        "court_node": "nobility",
        "role_label": "Chu nobility clients (aggregate)",
        "speech_role": "retainer",
        "packet_bias": {
            "lineage_shi": 0.45,
            "chu_patron_client": 0.25,
            "dao_guodian": 0.15,
            "huang_lao": 0.05,
            "tianxia_da_yitong": 0.10,
        },
    },
    {
        "id": "zhaoxiang",
        "profile_id": "qin-zhaoxiang",
        "home": "qin",
        "court_group": "Qin court",
        "role_label": "King Zhaoxiang of Qin (long reign)",
        "speech_role": "ruler",
        "era_unlock_bce": None,  # available from scenario start
        "packet_bias": {
            "legalist_fa": 0.40,
            "tianxia_da_yitong": 0.25,
            "huang_lao": 0.20,
            "ru_li": 0.15,
        },
    },
    {
        "id": "ying_zheng",
        "profile_id": "qin-ying-zheng",
        "home": "qin",
        "court_group": "Qin court",
        "role_label": "King of Qin",
        "speech_role": "ruler",
        "era_unlock_bce": 247,
        "packet_bias": {
            "legalist_fa": 0.55,
            "tianxia_da_yitong": 0.25,
            "huang_lao": 0.15,
            "ru_li": 0.05,
        },
    },
    {
        "id": "li_si",
        "profile_id": "qin-li-si",
        "home": "qin",
        "court_group": "Qin court",
        "role_label": "Qin chancellor / Legalist advisor",
        "speech_role": "minister",
        "era_unlock_bce": 247,
        "packet_bias": {"legalist_fa": 0.55, "huang_lao": 0.30, "ru_li": 0.15},
    },
    {
        "id": "king_jian",
        "profile_id": "qi-king-jian-isolationist-court",
        "home": "qi",
        "court_group": "Qi court",
        "role_label": "King Jian of Qi (isolationist court)",
        "speech_role": "ruler",
        "packet_bias": {
            "guanzi": 0.40,  # Qi Guanzi fa+dao — not Huang-Lao
            "lineage_shi": 0.30,
            "dao_guodian": 0.12,
            "ru_li": 0.10,
            "tianxia_da_yitong": 0.08,
        },
    },
]

# Legacy state-agent ids -> figure ids (NOT territorial fall)
LEGACY_FIGURE_MAP: dict[str, str] = {
    "chu": "kaolie",
    "qin": "zhaoxiang",  # early-era Qin face; Zheng gated
    "qi": "king_jian",
    "zhao": "kaolie",  # no dedicated figure yet — stay on a valid choice
    "han": "kaolie",
    "wei": "chunshen",
    "yan": "chunshen",
}

DEFAULT_FIGURE_ID = "kaolie"


def figure_ids() -> list[str]:
    return [f["id"] for f in FIGURES]


def figure_label_for(fid: str) -> str:
    f = next((x for x in FIGURES if x["id"] == fid), None)
    if not f:
        return fid
    row = profile_by_id(f["profile_id"])
    name = (row or {}).get("name_en") or f["id"]
    group = f.get("court_group") or "Court"
    return f"[{group}] {name} — {f['role_label']}"


def figure_label_map() -> dict[str, str]:
    return {f["id"]: figure_label_for(f["id"]) for f in FIGURES}


def figure_dropdown_choices() -> list[tuple[str, str]]:
    """(label, value) pairs — values are figure ids only (never bare 'chu')."""
    return [(figure_label_for(f["id"]), f["id"]) for f in FIGURES]


def normalize_figure_id(fid: str | None) -> str:
    """Coerce dropdown / legacy values onto a live figure id. Never leave 'chu' as value."""
    if isinstance(fid, (list, tuple)):
        fid = fid[0] if fid else None
    raw = str(fid or "").strip()
    if not raw:
        return DEFAULT_FIGURE_ID
    low = raw.lower()
    known = set(figure_ids())
    if low in known:
        return low
    if low in LEGACY_FIGURE_MAP:
        return LEGACY_FIGURE_MAP[low]
    # UI may echo the visible label instead of the value
    labels = figure_label_map()
    for fid_k, label in labels.items():
        if raw == label or low == label.lower():
            return fid_k
    return DEFAULT_FIGURE_ID


def get_figure(fid: str) -> dict[str, Any] | None:
    nid = normalize_figure_id(fid)
    for f in FIGURES:
        if f["id"] == nid:
            return f
    return None


def _norm_weights(bias: dict[str, float]) -> dict[str, float]:
    s = sum(bias.values()) or 1.0
    return {k: round(v / s, 4) for k, v in bias.items()}



ERA_GATED_FIGURES = ("ying_zheng", "li_si")
QIN_EARLY_FACE = "zhaoxiang"
CHU_LATE_FACE = "king_you"
CHU_EARLY_FACE = "kaolie"


def bce_year(world: "WorldState | None" = None, year: int | None = None) -> int:
    """Positive BCE year for era gates (sim stores negative years, e.g. -260)."""
    if year is None:
        year = int(getattr(world, "year", -260) if world is not None else -260)
    y = int(year)
    return abs(y) if y < 0 else y


def figure_era_unlocked(fid: str, world: "WorldState | None" = None, *, year: int | None = None) -> bool:
    """Era gates aligned on positive BCE year.

    - era_unlock_bce: available when BCE year ≤ unlock (Ying Zheng/Li Si ≤247; King You ≤238).
    - era_exit_bce: locked when BCE year ≤ exit (Kaolie dies ~238).
    """
    meta = next((f for f in FIGURES if f["id"] == normalize_figure_id(fid)), None)
    if not meta:
        return False
    y = bce_year(world, year)
    exit_at = meta.get("era_exit_bce")
    if exit_at is not None and y <= int(exit_at):
        return False
    unlock = meta.get("era_unlock_bce")
    if unlock is None:
        return True
    return y <= int(unlock)


def figure_available_for_talk(world: "WorldState", fid: str) -> bool:
    """Living home court + era unlock."""
    meta = get_figure(fid)
    if not meta:
        return False
    if not figure_era_unlocked(meta["id"], world):
        return False
    home = meta["home"]
    ag = world.agents.get(home)
    if ag is None or bool(getattr(ag, "annexed", False)):
        return False
    if float(getattr(ag, "viability", 0.0)) <= 0.0:
        return False
    return True


def talkable_figures(world: "WorldState") -> list[dict[str, Any]]:
    """Cast selectable for one-on-one counsel (era + living).

    Ensures a Qin face pre-247 (Zhaoxiang) and a Chu royal face (Kaolie early /
    King You after ≤238).
    """
    out = [f for f in FIGURES if figure_available_for_talk(world, f["id"])]
    qin = world.agents.get("qin")
    if qin is not None and not getattr(qin, "annexed", False) and float(getattr(qin, "viability", 0)) > 0:
        if not any(f["id"] == QIN_EARLY_FACE for f in out) and figure_era_unlocked(QIN_EARLY_FACE, world):
            z = get_figure(QIN_EARLY_FACE)
            if z:
                out.insert(0, z)
    chu = world.agents.get("chu")
    if chu is not None and not getattr(chu, "annexed", False) and float(getattr(chu, "viability", 0)) > 0:
        chu_royals = ("kaolie", "king_you")
        if not any(f["id"] in chu_royals for f in out):
            # Prefer unlocked royal face
            for cand in ("king_you", "kaolie"):
                if figure_era_unlocked(cand, world) and figure_available_for_talk(world, cand):
                    z = get_figure(cand)
                    if z:
                        out.insert(0, z)
                    break
    return out


def figure_cast_status(world: "WorldState", fid: str) -> dict[str, Any]:
    """UI status for picker/profile: talkable | not_yet_risen | annexed_home | missing."""
    fid = normalize_figure_id(fid)
    meta = get_figure(fid)
    if not meta:
        return {"id": fid, "status": "missing", "talkable": False}
    if not figure_era_unlocked(fid, world):
        y = bce_year(world)
        exit_at = meta.get("era_exit_bce")
        unlock = meta.get("era_unlock_bce")
        if exit_at is not None and y <= int(exit_at):
            return {
                "id": fid,
                "status": "exited",
                "talkable": False,
                "note": f"Left the stage (locked at ≤{int(exit_at)} BCE).",
                "bce_year": y,
            }
        return {
            "id": fid,
            "status": "not_yet_risen",
            "talkable": False,
            "note": f"Not yet risen (unlocks at ≤{unlock or 247} BCE).",
            "bce_year": y,
        }
    home = meta["home"]
    ag = world.agents.get(home)
    if ag is None:
        return {"id": fid, "status": "missing_home", "talkable": False}
    if getattr(ag, "annexed", False) or float(getattr(ag, "viability", 0)) <= 0:
        return {"id": fid, "status": "annexed_home", "talkable": False, "note": "Home court annexed."}
    return {"id": fid, "status": "talkable", "talkable": True, "home": home}


def figure_profile(world: "WorldState", figure_id: str) -> dict[str, Any]:
    """Full Character Profile payload for one named figure."""
    figure_id = normalize_figure_id(figure_id)
    meta = get_figure(figure_id)
    if not meta:
        return {"error": f"unknown figure {figure_id}", "id": figure_id}

    row = profile_by_id(meta["profile_id"]) or {}
    home = meta["home"]
    ag = world.agents.get(home)
    if not ag:
        return {"error": f"missing home court {home}", "id": figure_id}

    bf = row.get("big_five") or {}
    ocean = {
        "openness": float(bf.get("O", ag.traits.openness)),
        "conscientiousness": float(bf.get("C", ag.traits.conscientiousness)),
        "extraversion": float(bf.get("E", ag.traits.extraversion)),
        "agreeableness": float(bf.get("A", ag.traits.agreeableness)),
        "neuroticism": float(bf.get("N", ag.traits.neuroticism)),
    }
    weights = _norm_weights(meta.get("packet_bias") or starting_weights(home))
    packets = [p for p, w in sorted(weights.items(), key=lambda x: -x[1]) if w >= 0.08]
    if not packets:
        packets = starting_packets(home)

    # Dyadic trust: interstate edges from home court + Chu court node if any
    dyadic: dict[str, float] = {}
    for key, val in world.trust.items():
        if key.startswith(f"{home}->") or key.endswith(f"->{home}"):
            dyadic[key] = float(val)
    court_edges: dict[str, float] = {}
    court_node = meta.get("court_node")
    if court_node and getattr(world, "chu_court", None) is not None:
        g = world.chu_court
        for key, val in g.edges.items():
            if key.startswith(f"{court_node}->") or key.endswith(f"->{court_node}"):
                court_edges[key] = float(val)
                dyadic[f"chu_court:{key}"] = float(val)

    from .dossiers import dossier_for_figure

    dossier = dossier_for_figure(figure_id)

    return {
        "id": figure_id,
        "kind": "figure",
        "name": row.get("name_en") or figure_id,
        "name_zh": row.get("name_zh") or "",
        "role_label": meta["role_label"],
        "home_court": home,
        "home_court_name": ag.name,
        "bloc": ag.bloc,
        "profile_id": meta["profile_id"],
        "dossier": dossier,
        "confidence": row.get("confidence", "low"),
        "shiji_anchors": list(row.get("shiji_anchors") or [])[:6],
        "justifications": row.get("justifications") or {},
        "fiction": False,
        "big_five": ocean,
        # Live affective layer from home court (shared WorldState)
        "state": {
            "resentment": ag.state.resentment,
            "fear_of_qin": ag.state.fear_of_qin,
            "betrayal_memory": ag.state.betrayal_memory,
            "status_threat": ag.state.status_threat,
            "perceived_threat": ag.state.perceived_threat,
            "withholding_threshold": ag.state.withholding_threshold,
        },
        "intention": {
            "current": ag.intention.current,
            "label": _intent_label(ag),
            "sticky_until": ag.intention.sticky_until,
            "hysteresis_mu": ag.intention.hysteresis_mu,
            "note": f"Sticky intention tracked on home court '{home}' (meso field).",
        },
        "packets": packets,
        "packet_weights": weights,
        "base_schools": expand_to_base_schools(weights),
        "syncretism_note": (
            "Four bases: Legalism / Mohism / Daoism / Confucianism. "
            "Syncretisms (Huang-Lao, Guanzi, …) = weighted combos; many mixes allowed. "
            "Institutional overlays (lineage, tianxia, Chu patronage) may ride along. "
            "Packet weights = multi-philosophy balance, not exclusive school labels."
        ),
        "packet_views": [packet_public_view(p) for p in packets],
        "logic_conflict": conflict_score(packets, weights),
        "dyadic_trust": dyadic,
        "court_edges": court_edges,
        "court_node": court_node,
        "qin_pressure": world.qin_pressure,
        "alliance_cohesion": world.meso.cohesion,
        "shared_identity": world.meso.shared_identity,
        "cascade_armed": world.meso.cascade_armed,
        "quorum_ok": world.meso.quorum_ok,
        "pathway_soft": world.meso.pathway_soft,
        "tick": world.tick,
        "era_status": figure_cast_status(world, figure_id),
        "talkable": figure_available_for_talk(world, figure_id),
        "portrait": f"/static/portraits/{figure_id}.jpg",
        "allegiance": home,
        "bce_year": bce_year(world),
        "ideology": {
            "legalist_centralism": ag.traits.legalist_centralism,
            "lineage_honor": ag.traits.lineage_honor,
            "tianxia_unity": ag.traits.tianxia_unity,
            "status_threat_sensitivity": ag.traits.status_threat_sensitivity,
            "response_latency": ag.traits.response_latency,
            "betrayal_memory_weight": ag.traits.betrayal_memory_weight,
            "memory_bias": ag.traits.memory_bias,
        },
    }


def _intent_label(ag: Any) -> str:
    from .action_labels import short_label

    return short_label(ag.intention.current, bloc=ag.bloc)


def _state_agent_fallback(world: "WorldState", aid: str) -> dict[str, Any]:
    from .dossiers import dossier_for

    ag = world.agents[aid]
    packets = normalize_packet_list(ag.active_packets)
    weights = ag.packet_weights or starting_weights(aid)
    dyadic = {
        k: float(v)
        for k, v in world.trust.items()
        if k.startswith(f"{aid}->") or k.endswith(f"->{aid}")
    }
    return {
        "id": aid,
        "kind": "state_agent",
        "name": ag.name,
        "home_court": aid,
        "bloc": ag.bloc,
        "dossier": dossier_for(aid),
        "big_five": {
            "openness": ag.traits.openness,
            "conscientiousness": ag.traits.conscientiousness,
            "extraversion": ag.traits.extraversion,
            "agreeableness": ag.traits.agreeableness,
            "neuroticism": ag.traits.neuroticism,
        },
        "state": {
            "resentment": ag.state.resentment,
            "fear_of_qin": ag.state.fear_of_qin,
            "betrayal_memory": ag.state.betrayal_memory,
            "status_threat": ag.state.status_threat,
            "perceived_threat": ag.state.perceived_threat,
            "withholding_threshold": ag.state.withholding_threshold,
        },
        "intention": {
            "current": ag.intention.current,
            "label": _intent_label(ag),
            "sticky_until": ag.intention.sticky_until,
            "hysteresis_mu": ag.intention.hysteresis_mu,
        },
        "packets": packets,
        "packet_weights": weights,
        "packet_views": [packet_public_view(p) for p in packets],
        "dyadic_trust": dyadic,
        "qin_pressure": world.qin_pressure,
        "alliance_cohesion": world.meso.cohesion,
        "shared_identity": world.meso.shared_identity,
        "cascade_armed": world.meso.cascade_armed,
        "quorum_ok": world.meso.quorum_ok,
        "pathway_soft": world.meso.pathway_soft,
        "tick": world.tick,
        "fiction": False,
    }
