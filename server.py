#!/usr/bin/env python3
"""Flask HTML frontend for the Warring States sim — thin wrapper over backend.py.

No engine math. Legacy UI app.py is parked; use this or cli.py for playtest.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from backend import (
    advance_quarter,
    attempt_alliance,
    bootstrap_dialogue,
    character_choices,
    character_profile,
    do_player_action,
    export_snapshot,
    fresh_run,
    import_snapshot,
    initial_state,
    intervene_targets,
    latest_dialogue,
    merge_chat,
    run_counsel,
    spend_alliance_fund,
)

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
SAVES = ROOT / "saves"
# Last-session autosave — never deleted by New Run; named slots live beside it.
SESSION_PATH = SAVES / "session.json"
# Legacy filename; still listed/readable, never unlinked on New Run.
LEGACY_AUTOSAVE = SAVES / "autosave.json"

app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")

# Single-player in-memory session (local playtest)
_state: dict[str, Any] = {}
_chat: list[dict[str, str]] = []


def _safe_slot_id(name: str) -> str:
    """Filesystem-safe slot id from a display name (letters, digits, _-)."""
    raw = (name or "").strip()
    if not raw:
        raise ValueError("slot name required")
    out = []
    for ch in raw:
        if ch.isalnum() or ch in ("-", "_"):
            out.append(ch)
        elif ch.isspace() or ch in (".", ":", "/"):
            out.append("_")
        else:
            out.append("_")
    sid = "".join(out).strip("_")
    while "__" in sid:
        sid = sid.replace("__", "_")
    if not sid or sid in (".", "..") or sid.lower() in ("session", "autosave"):
        raise ValueError("invalid slot name")
    if len(sid) > 64:
        sid = sid[:64].rstrip("_")
    return sid


def _slot_path(slot_id: str) -> Path:
    return SAVES / f"{slot_id}.json"


def _read_snap_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _snap_meta(snap: dict[str, Any], *, slot_id: str, name: str | None = None) -> dict[str, Any]:
    return {
        "id": slot_id,
        "name": name or snap.get("slot_name") or slot_id,
        "tick": snap.get("tick"),
        "year": snap.get("year"),
        "saved_at": snap.get("saved_at"),
        "file": f"{slot_id}.json",
    }


def _list_server_slots() -> list[dict[str, Any]]:
    """Named campaign slots under saves/*.json (excludes session/autosave)."""
    SAVES.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for path in sorted(SAVES.glob("*.json")):
        stem = path.stem
        if stem in ("session", "autosave"):
            continue
        snap = _read_snap_file(path)
        if not snap:
            continue
        if not (isinstance(snap.get("engine"), dict) or isinstance(snap.get("agents"), dict)):
            continue
        rows.append(_snap_meta(snap, slot_id=stem, name=snap.get("slot_name") or stem))
    rows.sort(key=lambda r: str(r.get("saved_at") or ""), reverse=True)
    return rows


def _write_session(snap: dict[str, Any]) -> None:
    try:
        SAVES.mkdir(parents=True, exist_ok=True)
        SESSION_PATH.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _write_named_slot(name: str, snap: dict[str, Any]) -> dict[str, Any]:
    """Write/overwrite one named slot file. Returns meta."""
    sid = _safe_slot_id(name)
    snap = dict(snap)
    snap["slot_id"] = sid
    snap["slot_name"] = name.strip()
    SAVES.mkdir(parents=True, exist_ok=True)
    path = _slot_path(sid)
    path.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    return _snap_meta(snap, slot_id=sid, name=snap["slot_name"])


def _client_state(raw: dict[str, Any]) -> dict[str, Any]:
    """Project for the browser — drop the heavy _engine blob."""
    out = {k: v for k, v in raw.items() if k != "_engine"}
    return out


def _pack(
    projected: dict[str, Any],
    new_msgs: list[dict[str, str]] | None = None,
    *,
    replace_chat: bool = False,
) -> dict[str, Any]:
    global _state, _chat
    _state = projected
    if replace_chat:
        _chat = list(new_msgs or [])
    elif new_msgs:
        _chat = merge_chat(_chat, new_msgs)
    speaker, text = latest_dialogue(projected)
    return {
        "ok": True,
        "state": _client_state(projected),
        "chat": deepcopy(_chat),
        "dialogue": {"speaker": speaker, "text": text},
        "new_lines": list(new_msgs or []),
    }


def _ensure() -> dict[str, Any]:
    global _state, _chat
    if not _state or "_engine" not in _state:
        _state = fresh_run()
        _chat = bootstrap_dialogue()
    return _state


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "warring-states-html"})


@app.get("/api/state")
def get_state():
    st = _ensure()
    speaker, text = latest_dialogue(st)
    return jsonify(
        {
            "ok": True,
            "state": _client_state(st),
            "chat": deepcopy(_chat),
            "dialogue": {"speaker": speaker, "text": text},
            "new_lines": [],
        }
    )


@app.post("/api/new")
def api_new():
    """Start a fresh world. Named slots and session autosave are kept."""
    projected = fresh_run()
    return jsonify(_pack(projected, bootstrap_dialogue(), replace_chat=True))


@app.get("/api/saves")
def api_saves_list():
    """List named server slots under saves/*.json."""
    session = None
    for path in (SESSION_PATH, LEGACY_AUTOSAVE):
        snap = _read_snap_file(path) if path.exists() else None
        if snap:
            session = _snap_meta(snap, slot_id="session", name="Last session")
            break
    return jsonify({"ok": True, "slots": _list_server_slots(), "session": session})


@app.get("/api/save")
@app.post("/api/save")
def api_save():
    """Export snapshot. Optional JSON body {name} writes/overwrites that named slot only.

    Always refreshes saves/session.json (last session). Never deletes other slots.
    """
    st = _ensure()
    snap = export_snapshot(st, _chat)
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or body.get("slot") or "").strip() if isinstance(body, dict) else ""
    meta = None
    if name:
        try:
            meta = _write_named_slot(name, snap)
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        except OSError as e:
            return jsonify({"ok": False, "error": f"write failed: {e}"}), 500
    _write_session(snap)
    return jsonify(
        {
            "ok": True,
            "snapshot": snap,
            "tick": snap.get("tick"),
            "saved_at": snap.get("saved_at"),
            "slot": meta,
            "slots": _list_server_slots(),
        }
    )


@app.post("/api/load")
def api_load():
    """Restore from snapshot body, {snapshot}, or {slot: name} server file."""
    global _state, _chat
    body = request.get_json(silent=True) or {}
    snap = None
    slot_name = ""
    if isinstance(body, dict):
        slot_name = str(body.get("slot") or body.get("name") or "").strip()
        if slot_name:
            try:
                sid = "session" if slot_name.lower() in ("session", "last", "autosave") else _safe_slot_id(slot_name)
            except ValueError as e:
                return jsonify({"ok": False, "error": str(e)}), 400
            if sid == "session":
                path = SESSION_PATH if SESSION_PATH.exists() else LEGACY_AUTOSAVE
            else:
                path = _slot_path(sid)
            snap = _read_snap_file(path)
            if not snap:
                return jsonify({"ok": False, "error": f"slot not found: {slot_name}"}), 404
        elif isinstance(body.get("snapshot"), dict):
            snap = body["snapshot"]
        else:
            snap = body
    if not isinstance(snap, dict):
        return jsonify({"ok": False, "error": "snapshot must be a JSON object"}), 400
    try:
        projected = import_snapshot(snap)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:  # noqa: BLE001 — surface bad saves cleanly
        return jsonify({"ok": False, "error": f"load failed: {e}"}), 400
    chat = []
    if isinstance(snap.get("chat"), list):
        chat = list(snap["chat"])
    if not chat:
        chat = bootstrap_dialogue()
    pack = _pack(projected, chat, replace_chat=True)
    _write_session(export_snapshot(projected, _chat))
    return jsonify(pack)


@app.post("/api/advance")
def api_advance():
    st = _ensure()
    projected, msgs = advance_quarter(st)
    return jsonify(_pack(projected, msgs))


@app.post("/api/intervene")
def api_intervene():
    st = _ensure()
    body = request.get_json(silent=True) or {}
    targets = body.get("targets") or body.get("target") or ["chu"]
    if isinstance(targets, str):
        targets = [targets]
    cleaned = [str(t).strip().lower() for t in targets if str(t).strip()]
    allowed = {"qin", "chu", "qi"}
    cleaned = [t for t in cleaned if t in allowed]
    if not cleaned:
        return jsonify({"ok": False, "error": "Pick at least one of qin, chu, qi"}), 400
    projected, msgs, err = intervene_targets(st, cleaned)
    pack = _pack(projected, msgs)
    if err:
        pack["ok"] = False
        pack["error"] = err
        return jsonify(pack), 400
    return jsonify(pack)


@app.post("/api/alliance")
def api_alliance():
    st = _ensure()
    projected, msgs, err = attempt_alliance(st)
    pack = _pack(projected, msgs)
    if err:
        pack["ok"] = False
        pack["error"] = err
        return jsonify(pack), 400
    return jsonify(pack)


@app.post("/api/alliance_fund")
def api_alliance_fund():
    """Spend joint alliance fund: tech | agriculture | construction | military."""
    st = _ensure()
    body = request.get_json(silent=True) or {}
    purpose = str(body.get("purpose") or body.get("action") or "").strip().lower()
    allowed = {
        "tech", "agriculture", "construction", "military",
        "agri", "farm", "build", "mil", "army", "research", "m2", "infra", "arms",
    }
    if purpose not in allowed:
        return jsonify({"ok": False, "error": "purpose must be tech|agriculture|construction|military"}), 400
    before_g = float(st.get("alliance_fund_grain") or 0.0)
    before_t = float(st.get("alliance_fund_treasury") or 0.0)
    projected, msgs, err = spend_alliance_fund(st, purpose)
    pack = _pack(projected, msgs)
    # Echo fund totals at pack root so UI can refresh even if state nesting is missed
    pack["alliance_fund_grain"] = float(projected.get("alliance_fund_grain") or 0.0)
    pack["alliance_fund_treasury"] = float(projected.get("alliance_fund_treasury") or 0.0)
    pack["alliance_fund_before"] = {"grain": before_g, "treasury": before_t}
    pack["alliance_fund_spent_purposes"] = list(
        projected.get("alliance_fund_spent_purposes") or []
    )
    pack["alliance_fund_actions_left"] = int(projected.get("alliance_fund_actions_left") or 0)
    if err:
        pack["ok"] = False
        pack["error"] = err
        return jsonify(pack), 400
    return jsonify(pack)


def _invest_response(action: str, target: str):
    """Shared invest handler — surfaces engine rejection as ok:false + error."""
    st = _ensure()
    projected, msgs, err = do_player_action(st, action, target)
    pack = _pack(projected, msgs)
    if err:
        pack["ok"] = False
        pack["error"] = err
        return jsonify(pack), 400
    return jsonify(pack)


@app.post("/api/player_action")
def api_player_action():
    """Fund Military / Send Grain / Broker Mediation — target an anti-Qin state."""
    body = request.get_json(silent=True) or {}
    action = str(body.get("action") or "").strip().lower()
    target = str(body.get("target") or "chu").strip().lower()
    allowed = {
        "fund_military", "send_grain", "broker_mediation",
        "fund", "grain", "mediate", "mediation", "broker", "military", "send",
    }
    if action not in allowed:
        return jsonify({"ok": False, "error": "action must be fund_military|send_grain|broker_mediation"}), 400
    return _invest_response(action, target)


@app.post("/api/fund_military")
def api_fund_military():
    body = request.get_json(silent=True) or {}
    target = str(body.get("target") or "chu").strip().lower()
    return _invest_response("fund_military", target)


@app.post("/api/send_grain")
def api_send_grain():
    body = request.get_json(silent=True) or {}
    target = str(body.get("target") or "chu").strip().lower()
    return _invest_response("send_grain", target)


@app.post("/api/broker_mediation")
def api_broker_mediation():
    body = request.get_json(silent=True) or {}
    target = str(body.get("target") or "chu").strip().lower()
    return _invest_response("broker_mediation", target)


@app.post("/api/counsel")
def api_counsel():
    """Counsel among figures or one-on-one via figure_id.

    Body: { "prompt": "...", "commit": false, "figure_id": "zhaoxiang"|null }.
    Tips dials on close only. English UI.
    """
    st = _ensure()
    body = request.get_json(silent=True) or {}
    prompt = body.get("prompt") or body.get("text") or ""
    commit = bool(body.get("commit") or body.get("close") or False)
    figure_id = body.get("figure_id") or body.get("figure") or None
    if figure_id is not None:
        figure_id = str(figure_id).strip().lower() or None
    projected, msgs, err, result = run_counsel(
        st, prompt=str(prompt), commit=commit, figure_id=figure_id
    )
    pack = _pack(projected, msgs)
    pack["counsel_result"] = projected.get("counsel_result") or result
    pack["talkable_cast"] = projected.get("talkable_cast")
    if err:
        pack["ok"] = False
        pack["error"] = err
        return jsonify(pack), 400
    return jsonify(pack)


@app.get("/api/talkable")
def api_talkable():
    """Living + era-gated cast for the portrait strip picker."""
    st = _ensure()
    from backend import _talkable_cast, _world_from_ui

    world = _world_from_ui(st)
    return jsonify({
        "ok": True,
        "bce_year": abs(int(getattr(world, "year", -260))),
        "figures": _talkable_cast(world),
        "counsel_session": (st.get("counsel_session") if isinstance(st, dict) else None)
        or getattr(world, "counsel_session", {}),
    })


@app.get("/api/profile")
def api_profile():
    """Named-figure Character Profile — reuses backend.character_profile."""
    st = _ensure()
    fig_id = request.args.get("id") or request.args.get("figure") or ""
    choices = [{"id": vid, "label": lab} for lab, vid in character_choices(st)]
    # Short radio labels (match prior Gradio RADIO_FIGURES spirit)
    short = {
        "kaolie": "Kaolie — King of Chu",
        "king_you": "King You — Chu successor",
        "chunshen": "Chunshen — Chu patron",
        "chu_nobility": "Chu nobility — clients",
        "zhaoxiang": "Zhaoxiang — King of Qin",
        "ying_zheng": "Ying Zheng — King of Qin",
        "li_si": "Li Si — Qin chancellor",
        "king_jian": "King Jian — Qi isolationist",
    }
    for row in choices:
        row["short"] = short.get(row["id"], row["label"])
    prof = character_profile(st, fig_id)
    if prof.get("error"):
        return jsonify({"ok": False, "error": prof["error"], "figures": choices, "profile": prof}), 400
    return jsonify({"ok": True, "figures": choices, "profile": prof, "id": prof.get("id")})


def main() -> None:
    host = os.environ.get("WS_HOST", "127.0.0.1")
    port = int(os.environ.get("WS_PORT", "8080"))
    # Seed session so first GET /api/state is ready
    global _state, _chat
    _state = initial_state()
    # mark opening like fresh_run for consistent playtest
    _state = fresh_run()
    _chat = bootstrap_dialogue()
    print(f"Warring States HTML frontend")
    print(f"Open http://{host}:{port}/")
    print(
        "API: /api/state /api/new /api/saves /api/save /api/load /api/advance /api/intervene /api/alliance "
        "/api/alliance_fund /api/player_action /api/fund_military /api/send_grain "
        "/api/broker_mediation /api/profile /api/counsel /api/talkable"
    )
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
