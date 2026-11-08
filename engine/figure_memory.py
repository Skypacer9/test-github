"""Capped figure memories — historical priors + in-run events.

Feeds counsel utterances and field snapshots. No player dossier / OCEAN.
Memories are figure-scoped only (never remember the player as a person).
"""

from __future__ import annotations

import hashlib
from typing import Any

MEMORY_CAP = 8  # max entries per figure (priors + events combined after prune)
PRIOR_CAP = 3
EVENT_KINDS = (
    "annex",
    "betrayal",
    "ally_betrayal",
    "breakthrough",
    "rare_combo",
    "raid",
    "pattern",
)
# Unusual-event counsel comment rarity (~22% when a fresh event is pending)
COMMENT_FIRE_PCT = 22
COMMENT_COOLDOWN = 2  # ticks between event comments per figure

# Historical soft priors — short English; design flavor, not encyclopedia
HISTORICAL_PRIORS: dict[str, tuple[str, ...]] = {
    "kaolie": (
        "Remember: Chu face rides the patron web, not Qin fa.",
        "Chunshen's brokerage kept the southern hub breathing.",
        "Levy delay once cost a season of courage.",
    ),
    "king_you": (
        "Father Kaolie's hub is gone — the web frays in my hands.",
        "Succession shock: patrons glance past the throne.",
        "Qin pressure feels louder than any banquet vow.",
    ),
    "chunshen": (
        "Guest-houses keep receipts longer than treaties.",
        "合纵 talk without grain is empty armor.",
        "I have seen hubs starve their spokes — and bleed.",
    ),
    "chu_nobility": (
        "Lineage debt outlasts one king's seal.",
        "Unpaid ritual still itches under the robe.",
        "We remember who abandoned the patron first.",
    ),
    "zhaoxiang": (
        "Long reigns taught staged pressure, not thunder alone.",
        "Guest talent cuts cleaner when laws stay clear.",
        "Patience took more courts than haste ever toasted.",
    ),
    "ying_zheng": (
        "Sequential conquest is a checklist I intend to finish.",
        "Guest ministers stay if they sharpen the mould.",
        "Banquet loyalty is fog on the western passes.",
    ),
    "li_si": (
        "The memorial against guest-expulsion still guides my brief.",
        "Fa drafts the road; toast-logic loses the levy.",
        "I remember courts that drowned in soft words.",
    ),
    "king_jian": (
        "After Yan's 284 wound, isolation felt like armor.",
        "Guanzi books price coalitions — hymns do not.",
        "Betrayal memory sticks harder than any Qin smile.",
    ),
}


def _board(world: Any) -> dict[str, list[dict[str, Any]]]:
    mem = getattr(world, "figure_memories", None)
    if not isinstance(mem, dict):
        mem = {}
        world.figure_memories = mem
    return mem


def _comment_at(world: Any) -> dict[str, int]:
    cool = getattr(world, "figure_memory_comment_at", None)
    if not isinstance(cool, dict):
        cool = {}
        world.figure_memory_comment_at = cool
    return cool


def ensure_figure_memories(world: Any) -> dict[str, list[dict[str, Any]]]:
    """Seed historical priors once per figure; prune to cap."""
    board = _board(world)
    from .figures import FIGURES

    for fig in FIGURES:
        fid = str(fig["id"])
        rows = list(board.get(fid) or [])
        if not any(r.get("kind") == "prior" for r in rows):
            for i, text in enumerate(HISTORICAL_PRIORS.get(fid, ())[:PRIOR_CAP]):
                rows.append(
                    {
                        "kind": "prior",
                        "text": str(text)[:120],
                        "tick": -1000 + i,
                        "salience": 0.55 - 0.05 * i,
                    }
                )
        board[fid] = _prune(rows)
    world.figure_memories = board
    return board


def _prune(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Keep priors first, then newest/highest salience events
    priors = [r for r in rows if r.get("kind") == "prior"][:PRIOR_CAP]
    events = [r for r in rows if r.get("kind") != "prior"]
    events.sort(key=lambda r: (float(r.get("salience") or 0), int(r.get("tick") or 0)), reverse=True)
    room = max(0, MEMORY_CAP - len(priors))
    return priors + events[:room]


def remember(
    world: Any,
    fid: str,
    *,
    kind: str,
    text: str,
    salience: float = 0.7,
) -> None:
    """Append one in-run memory for a figure; capped; no player dossier."""
    if not fid:
        return
    kind = kind if kind in EVENT_KINDS or kind == "prior" else "pattern"
    board = ensure_figure_memories(world)
    rows = list(board.get(fid) or [])
    rows.append(
        {
            "kind": kind,
            "text": str(text).strip()[:120],
            "tick": int(getattr(world, "tick", 0) or 0),
            "salience": float(max(0.0, min(1.0, salience))),
        }
    )
    board[fid] = _prune(rows)
    world.figure_memories = board
    # Pending unusual comment flag
    pending = getattr(world, "figure_memory_pending", None)
    if not isinstance(pending, dict):
        pending = {}
    if kind in ("annex", "betrayal", "ally_betrayal", "breakthrough", "rare_combo"):
        pending[fid] = {"kind": kind, "text": str(text).strip()[:100], "tick": int(getattr(world, "tick", 0) or 0)}
    world.figure_memory_pending = pending


def remember_living(
    world: Any,
    *,
    kind: str,
    text: str,
    salience: float = 0.7,
    homes: set[str] | None = None,
    exclude_fids: set[str] | None = None,
) -> None:
    """Broadcast a memory to living talkable figures (optionally home-filtered)."""
    from .figures import figure_available_for_talk, FIGURES

    exclude_fids = exclude_fids or set()
    for fig in FIGURES:
        fid = str(fig["id"])
        if fid in exclude_fids:
            continue
        home = str(fig.get("home") or "")
        if homes is not None and home not in homes:
            continue
        if not figure_available_for_talk(world, fid):
            continue
        remember(world, fid, kind=kind, text=text, salience=salience)


def memories_for(world: Any, fid: str, *, limit: int = 3) -> list[dict[str, Any]]:
    board = ensure_figure_memories(world)
    rows = list(board.get(fid) or [])
    # Prefer recent events, then priors
    events = [r for r in rows if r.get("kind") != "prior"]
    events.sort(key=lambda r: int(r.get("tick") or 0), reverse=True)
    priors = [r for r in rows if r.get("kind") == "prior"]
    out = events[: max(1, limit - 1)] + priors[:1]
    return out[:limit]


def memory_bite(world: Any, fid: str) -> str:
    """One short memory line for utterance shaping (may be empty)."""
    rows = memories_for(world, fid, limit=2)
    if not rows:
        return ""
    # Prefer in-run event over prior when present
    pick = rows[0]
    text = str(pick.get("text") or "").strip()
    if not text:
        return ""
    kind = str(pick.get("kind") or "")
    if kind == "prior":
        return text if len(text) <= 72 else text[:69] + "…"
    return text if len(text) <= 80 else text[:77] + "…"


def _role_event_comment(role: str, kind: str, detail: str) -> str:
    role = (role or "minister").lower()
    d = (detail or "").strip()
    short = d.split("—")[0].strip()[:48] if d else "the field"
    table = {
        "ruler": {
            "annex": f"A court falls — {short}. The seal must answer.",
            "betrayal": f"Betrayal scars the map near {short}.",
            "ally_betrayal": f"An ally turns steel. {short}.",
            "breakthrough": f"A workshop flash — {short}.",
            "rare_combo": f"Strange doctrine sparks — {short}.",
            "raid": f"Raid weather: {short}.",
            "pattern": f"I note the pattern: {short}.",
        },
        "minister": {
            "annex": f"Annex on the books — {short}. Adjust the levy.",
            "betrayal": f"Ledger marks betrayal: {short}.",
            "ally_betrayal": f"Ally-strike logged — {short}. Trust chill.",
            "breakthrough": f"Tech flash noted — {short}.",
            "rare_combo": f"Unusual mix pays a crumb — {short}.",
            "raid": f"Raid math: {short}.",
            "pattern": f"Pattern brief: {short}.",
        },
        "general": {
            "annex": f"Annex — fords shift. {short}.",
            "betrayal": f"Betrayal on the line — {short}.",
            "ally_betrayal": f"Ally spears us. {short}. Hold grain.",
            "breakthrough": f"New fittings — {short}.",
            "rare_combo": f"Odd doctrine at camp — {short}.",
            "raid": f"Raid call: {short}.",
            "pattern": f"Camp sees the pattern: {short}.",
        },
        "retainer": {
            "annex": f"A hub falls — spokes starve. {short}.",
            "betrayal": f"Face cracked — {short}.",
            "ally_betrayal": f"Ally forgot the banquet. {short}.",
            "breakthrough": f"Craft spark downstream — {short}.",
            "rare_combo": f"Strange court mix — {short}.",
            "raid": f"Raid rumor: {short}.",
            "pattern": f"We feel the pattern: {short}.",
        },
    }
    return (table.get(role) or table["minister"]).get(kind) or (table.get(role) or table["minister"])["pattern"]


def maybe_unusual_event_comment(
    world: Any,
    fig: dict[str, Any],
    *,
    role: str | None = None,
) -> str | None:
    """Brief role-colored comment on a pending unusual event — not every tick."""
    fid = str(fig.get("id") or "")
    if not fid:
        return None
    pending = getattr(world, "figure_memory_pending", None) or {}
    item = pending.get(fid)
    if not isinstance(item, dict):
        return None
    tick = int(getattr(world, "tick", 0) or 0)
    cool = _comment_at(world)
    last = int(cool.get(fid, -999))
    if last >= 0 and tick - last < COMMENT_COOLDOWN:
        return None
    h = hashlib.sha256(f"{tick}|{fid}|{item.get('kind')}|mem-comment".encode()).hexdigest()
    if (int(h[:8], 16) % 100) >= COMMENT_FIRE_PCT:
        return None
    kind = str(item.get("kind") or "pattern")
    detail = str(item.get("text") or "")
    role = role or str(fig.get("speech_role") or "minister")
    line = _role_event_comment(role, kind, detail)
    cool[fid] = tick
    world.figure_memory_comment_at = cool
    # consume pending so we don't spam
    pending = dict(pending)
    pending.pop(fid, None)
    world.figure_memory_pending = pending
    return line[:110]


def snapshot_lines(world: Any, fid: str) -> str:
    rows = memories_for(world, fid, limit=3)
    if not rows:
        return "memories=[]"
    bits = [f"{r.get('kind')}:{str(r.get('text') or '')[:40]}" for r in rows]
    return "memories=[" + "; ".join(bits) + "]"


def record_annex(world: Any, victim_id: str, by_id: str) -> None:
    v = world.agents.get(victim_id)
    b = world.agents.get(by_id)
    vname = getattr(v, "name", None) or victim_id
    bname = getattr(b, "name", None) or by_id
    text = f"{vname} annexed by {bname}"
    remember_living(world, kind="annex", text=text, salience=0.85)


def record_ally_betrayal(world: Any, attacker_id: str, victim_id: str) -> None:
    a = world.agents.get(attacker_id)
    v = world.agents.get(victim_id)
    an = getattr(a, "name", None) or attacker_id
    vn = getattr(v, "name", None) or victim_id
    text = f"{an} struck ally {vn}"
    remember_living(
        world,
        kind="ally_betrayal",
        text=text,
        salience=0.9,
        homes={attacker_id, victim_id} | {
            oid
            for oid, og in world.agents.items()
            if getattr(og, "bloc", "") == "anti_qin" and not getattr(og, "annexed", False)
        },
    )


def record_breakthrough(world: Any, fid: str, home: str, note: str) -> None:
    remember(world, fid, kind="breakthrough", text=note or f"breakthrough at {home}", salience=0.75)
    # peers at same home may lightly note
    from .figures import FIGURES, figure_available_for_talk

    for fig in FIGURES:
        if fig["id"] == fid:
            continue
        if fig.get("home") == home and figure_available_for_talk(world, fig["id"]):
            remember(
                world,
                fig["id"],
                kind="breakthrough",
                text=f"Court flash near {fid}: {(note or '')[:60]}",
                salience=0.55,
            )


def record_rare_combo(world: Any, sid: str, combo: str) -> None:
    if not combo:
        return
    text = f"Unusual ideology mix ({combo}) tips {sid}"
    from .figures import FIGURES, figure_available_for_talk

    for fig in FIGURES:
        if fig.get("home") == sid and figure_available_for_talk(world, fig["id"]):
            remember(world, fig["id"], kind="rare_combo", text=text, salience=0.7)


def record_pattern(world: Any, note: str, *, homes: set[str] | None = None) -> None:
    remember_living(world, kind="pattern", text=note[:100], salience=0.5, homes=homes)
