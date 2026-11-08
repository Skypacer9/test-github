#!/usr/bin/env python3
"""Flask HTML frontend for the Warring States sim — thin wrapper over backend.py.

Per-browser cookie sessions isolate campaigns. Optional WS_ACCESS_TOKEN gates
mutating APIs. LLM counsel/chronicle stay offline unless WS_LLM_ENABLED=1 and an
API key is set, with per-session rate limits.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory, session

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
PLAYERS_ROOT = SAVES / "players"

app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
app.secret_key = (
    os.environ.get("WS_SECRET_KEY")
    or os.environ.get("FLASK_SECRET_KEY")
    or secrets.token_hex(32)
)
app.config.update(
    SESSION_COOKIE_NAME="ws_field_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
)

_lock = threading.RLock()
# player_id -> {state, chat, llm_ts, write_ts}
_players: dict[str, dict[str, Any]] = {}

LLM_MAX_PER_HOUR = int(os.environ.get("WS_LLM_MAX_PER_HOUR") or "8")
WRITE_MAX_PER_MIN = int(os.environ.get("WS_WRITE_MAX_PER_MIN") or "90")


def _llm_enabled() -> bool:
    flag = (os.environ.get("WS_LLM_ENABLED") or "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return False
    key = (
        os.environ.get("WS_COUNSEL_API_KEY")
        or os.environ.get("WS_CHRONICLE_API_KEY")
        or ""
    ).strip()
    return bool(key)


def _access_token() -> str:
    return (os.environ.get("WS_ACCESS_TOKEN") or "").strip()


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


def _player_id() -> str:
    pid = session.get("player_id")
    if not isinstance(pid, str) or len(pid) < 12:
        pid = secrets.token_urlsafe(18)
        session["player_id"] = pid
        session.permanent = True
    if not session.get("csrf"):
        session["csrf"] = secrets.token_urlsafe(24)
    return pid


def _player_dir(pid: str) -> Path:
    # Keep path segment filesystem-safe (token_urlsafe is already safe).
    safe = "".join(ch for ch in pid if ch.isalnum() or ch in ("-", "_"))[:64]
    if not safe:
        safe = "anon"
    path = PLAYERS_ROOT / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_path(pid: str) -> Path:
    return _player_dir(pid) / "session.json"


def _legacy_autosave(pid: str) -> Path:
    return _player_dir(pid) / "autosave.json"


def _slot_path(pid: str, slot_id: str) -> Path:
    return _player_dir(pid) / f"{slot_id}.json"


def _bucket() -> dict[str, Any]:
    pid = _player_id()
    with _lock:
        b = _players.get(pid)
        if b is None:
            b = {"state": {}, "chat": [], "llm_ts": [], "write_ts": []}
            _players[pid] = b
        return b


def _prune_ts(rows: list[float], window_s: float) -> list[float]:
    now = time.time()
    return [t for t in rows if now - t < window_s]


def _rate_limit_writes(b: dict[str, Any]) -> str | None:
    with _lock:
        b["write_ts"] = _prune_ts(list(b.get("write_ts") or []), 60.0)
        if len(b["write_ts"]) >= max(1, WRITE_MAX_PER_MIN):
            return "rate limit: too many actions — wait a moment"
        b["write_ts"].append(time.time())
    return None


def _rate_limit_llm(b: dict[str, Any]) -> str | None:
    with _lock:
        b["llm_ts"] = _prune_ts(list(b.get("llm_ts") or []), 3600.0)
        if len(b["llm_ts"]) >= max(1, LLM_MAX_PER_HOUR):
            return "LLM rate limit — offline stub only for now"
        b["llm_ts"].append(time.time())
    return None


def _auth_gate() -> tuple[bool, str | None]:
    """Private-app-safe gate: signed session always; optional shared access token."""
    _player_id()  # ensure cookie session exists
    token = _access_token()
    if not token:
        return True, None
    auth = request.headers.get("Authorization") or ""
    hdr = (request.headers.get("X-WS-Token") or "").strip()
    q = (request.args.get("access_token") or "").strip()
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if secrets.compare_digest(bearer, token) or secrets.compare_digest(hdr, token) or secrets.compare_digest(q, token):
        return True, None
    return False, "unauthorized"


def _csrf_ok() -> bool:
    """Mutations must echo the session CSRF (header or JSON body)."""
    expected = session.get("csrf")
    if not isinstance(expected, str) or not expected:
        return False
    got = (request.headers.get("X-WS-CSRF") or "").strip()
    if got and secrets.compare_digest(got, expected):
        return True
    body = request.get_json(silent=True) or {}
    if isinstance(body, dict):
        b = str(body.get("csrf") or "").strip()
        if b and secrets.compare_digest(b, expected):
            return True
    return False


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


def _list_server_slots(pid: str) -> list[dict[str, Any]]:
    """Named campaign slots under this player's save dir."""
    root = _player_dir(pid)
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
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


def _write_session(pid: str, snap: dict[str, Any]) -> None:
    try:
        path = _session_path(pid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _write_named_slot(pid: str, name: str, snap: dict[str, Any]) -> dict[str, Any]:
    """Write/overwrite one named slot file. Returns meta."""
    sid = _safe_slot_id(name)
    snap = dict(snap)
    snap["slot_id"] = sid
    snap["slot_name"] = name.strip()
    path = _slot_path(pid, sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    return _snap_meta(snap, slot_id=sid, name=snap["slot_name"])


def _client_state(raw: dict[str, Any]) -> dict[str, Any]:
    """Project for the browser — drop the heavy _engine blob."""
    return {k: v for k, v in raw.items() if k != "_engine"}


def _pack(
    projected: dict[str, Any],
    new_msgs: list[dict[str, str]] | None = None,
    *,
    replace_chat: bool = False,
) -> dict[str, Any]:
    b = _bucket()
    with _lock:
        b["state"] = projected
        if replace_chat:
            b["chat"] = list(new_msgs or [])
        elif new_msgs:
            b["chat"] = merge_chat(list(b.get("chat") or []), new_msgs)
        chat = list(b["chat"])
    speaker, text = latest_dialogue(projected)
    return {
        "ok": True,
        "state": _client_state(projected),
        "chat": deepcopy(chat),
        "dialogue": {"speaker": speaker, "text": text},
        "new_lines": list(new_msgs or []),
        "csrf": session.get("csrf"),
        "player_id": session.get("player_id"),
        "llm_enabled": _llm_enabled(),
    }


def _ensure() -> dict[str, Any]:
    b = _bucket()
    with _lock:
        st = b.get("state") or {}
        if not st or "_engine" not in st:
            st = fresh_run()
            b["state"] = st
            b["chat"] = bootstrap_dialogue()
        return b["state"]


def _mutate_guard() -> tuple[Any, int] | None:
    """Shared gate for POST/write APIs. Returns Flask (response, status) on failure."""
    ok, err = _auth_gate()
    if not ok:
        return jsonify({"ok": False, "error": err or "unauthorized"}), 401
    _player_id()
    if not _csrf_ok():
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "missing csrf — GET /api/state first",
                    "csrf": session.get("csrf"),
                }
            ),
            403,
        )
    b = _bucket()
    limited = _rate_limit_writes(b)
    if limited:
        return jsonify({"ok": False, "error": limited}), 429
    return None


@app.before_request
def _touch_session():
    # Ensure every page/API visit has a signed player cookie (except static).
    if request.path.startswith("/static/"):
        return None
    if request.path == "/api/health":
        return None
    _player_id()
    return None


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "warring-states-html", "llm_enabled": _llm_enabled()})


@app.get("/api/state")
def get_state():
    ok, err = _auth_gate()
    if not ok:
        return jsonify({"ok": False, "error": err or "unauthorized"}), 401
    st = _ensure()
    b = _bucket()
    with _lock:
        chat = deepcopy(list(b.get("chat") or []))
    speaker, text = latest_dialogue(st)
    return jsonify(
        {
            "ok": True,
            "state": _client_state(st),
            "chat": chat,
            "dialogue": {"speaker": speaker, "text": text},
            "new_lines": [],
            "csrf": session.get("csrf"),
            "player_id": session.get("player_id"),
            "llm_enabled": _llm_enabled(),
        }
    )


@app.post("/api/new")
def api_new():
    """Start a fresh world for this player only. Named slots are kept."""
    blocked = _mutate_guard()
    if blocked:
        return blocked
    projected = fresh_run()
    return jsonify(_pack(projected, bootstrap_dialogue(), replace_chat=True))


@app.get("/api/saves")
def api_saves_list():
    """List named server slots under this player's save dir."""
    ok, err = _auth_gate()
    if not ok:
        return jsonify({"ok": False, "error": err or "unauthorized"}), 401
    pid = _player_id()
    session_meta = None
    for path in (_session_path(pid), _legacy_autosave(pid)):
        snap = _read_snap_file(path) if path.exists() else None
        if snap:
            session_meta = _snap_meta(snap, slot_id="session", name="Last session")
            break
    return jsonify({"ok": True, "slots": _list_server_slots(pid), "session": session_meta, "csrf": session.get("csrf")})


@app.get("/api/save")
@app.post("/api/save")
def api_save():
    """Export snapshot. Optional JSON body {name} writes that named slot for this player."""
    if request.method == "POST":
        blocked = _mutate_guard()
        if blocked:
            return blocked
    else:
        ok, err = _auth_gate()
        if not ok:
            return jsonify({"ok": False, "error": err or "unauthorized"}), 401
    pid = _player_id()
    st = _ensure()
    b = _bucket()
    with _lock:
        chat = list(b.get("chat") or [])
    snap = export_snapshot(st, chat)
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or body.get("slot") or "").strip() if isinstance(body, dict) else ""
    meta = None
    if name:
        try:
            meta = _write_named_slot(pid, name, snap)
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        except OSError as e:
            return jsonify({"ok": False, "error": f"write failed: {e}"}), 500
    _write_session(pid, snap)
    return jsonify(
        {
            "ok": True,
            "snapshot": snap,
            "tick": snap.get("tick"),
            "saved_at": snap.get("saved_at"),
            "slot": meta,
            "slots": _list_server_slots(pid),
            "csrf": session.get("csrf"),
        }
    )


@app.post("/api/load")
def api_load():
    """Restore from snapshot body, {snapshot}, or {slot: name} in this player's dir."""
    blocked = _mutate_guard()
    if blocked:
        return blocked
    pid = _player_id()
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
                path = _session_path(pid) if _session_path(pid).exists() else _legacy_autosave(pid)
            else:
                path = _slot_path(pid, sid)
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
    chat: list[dict[str, str]] = []
    if isinstance(snap.get("chat"), list):
        chat = list(snap["chat"])
    if not chat:
        chat = bootstrap_dialogue()
    pack = _pack(projected, chat, replace_chat=True)
    b = _bucket()
    with _lock:
        cur_chat = list(b.get("chat") or [])
    _write_session(pid, export_snapshot(projected, cur_chat))
    return jsonify(pack)


@app.post("/api/advance")
def api_advance():
    blocked = _mutate_guard()
    if blocked:
        return blocked
    st = _ensure()
    projected, msgs = advance_quarter(st)
    return jsonify(_pack(projected, msgs))


@app.post("/api/intervene")
def api_intervene():
    blocked = _mutate_guard()
    if blocked:
        return blocked
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
    blocked = _mutate_guard()
    if blocked:
        return blocked
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
    blocked = _mutate_guard()
    if blocked:
        return blocked
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
    blocked = _mutate_guard()
    if blocked:
        return blocked
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
    blocked = _mutate_guard()
    if blocked:
        return blocked
    body = request.get_json(silent=True) or {}
    target = str(body.get("target") or "chu").strip().lower()
    return _invest_response("fund_military", target)


@app.post("/api/send_grain")
def api_send_grain():
    blocked = _mutate_guard()
    if blocked:
        return blocked
    body = request.get_json(silent=True) or {}
    target = str(body.get("target") or "chu").strip().lower()
    return _invest_response("send_grain", target)


@app.post("/api/broker_mediation")
def api_broker_mediation():
    blocked = _mutate_guard()
    if blocked:
        return blocked
    body = request.get_json(silent=True) or {}
    target = str(body.get("target") or "chu").strip().lower()
    return _invest_response("broker_mediation", target)


@app.post("/api/counsel")
def api_counsel():
    """Counsel among figures or one-on-one via figure_id.

    Body: { "prompt": "...", "commit": false, "figure_id": "zhaoxiang"|null }.
    Tips dials on close only. English UI. Defaults to offline stub.
    """
    blocked = _mutate_guard()
    if blocked:
        return blocked
    st = _ensure()
    b = _bucket()
    from engine.llm_gate import force_stub_llm

    stub_token = None
    if _llm_enabled():
        llm_err = _rate_limit_llm(b)
        if llm_err:
            stub_token = force_stub_llm.set(True)
    body = request.get_json(silent=True) or {}
    prompt = body.get("prompt") or body.get("text") or ""
    commit = bool(body.get("commit") or body.get("close") or False)
    figure_id = body.get("figure_id") or body.get("figure") or None
    if figure_id is not None:
        figure_id = str(figure_id).strip().lower() or None
    try:
        projected, msgs, err, result = run_counsel(
            st, prompt=str(prompt), commit=commit, figure_id=figure_id
        )
    finally:
        if stub_token is not None:
            force_stub_llm.reset(stub_token)
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
    ok, err = _auth_gate()
    if not ok:
        return jsonify({"ok": False, "error": err or "unauthorized"}), 401
    st = _ensure()
    from backend import _talkable_cast, _world_from_ui

    world = _world_from_ui(st)
    return jsonify({
        "ok": True,
        "bce_year": abs(int(getattr(world, "year", -260))),
        "figures": _talkable_cast(world),
        "counsel_session": (st.get("counsel_session") if isinstance(st, dict) else None)
        or getattr(world, "counsel_session", {}),
        "csrf": session.get("csrf"),
    })


@app.get("/api/profile")
def api_profile():
    """Named-figure Character Profile — reuses backend.character_profile."""
    ok, err = _auth_gate()
    if not ok:
        return jsonify({"ok": False, "error": err or "unauthorized"}), 401
    st = _ensure()
    fig_id = request.args.get("id") or request.args.get("figure") or ""
    choices = [{"id": vid, "label": lab} for lab, vid in character_choices(st)]
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
    return jsonify({"ok": True, "figures": choices, "profile": prof, "id": prof.get("id"), "csrf": session.get("csrf")})


def main() -> None:
    host = os.environ.get("WS_HOST", "127.0.0.1")
    port = int(os.environ.get("WS_PORT", "8080"))
    # Warm default templates only — each browser still gets its own session world.
    _ = initial_state
    print("Warring States HTML frontend (per-session isolation)")
    print(f"Open http://{host}:{port}/")
    print(f"LLM enabled: {_llm_enabled()} (needs WS_LLM_ENABLED=1 + API key)")
    print(
        "API: /api/state /api/new /api/saves /api/save /api/load /api/advance /api/intervene /api/alliance "
        "/api/alliance_fund /api/player_action /api/fund_military /api/send_grain "
        "/api/broker_mediation /api/profile /api/counsel /api/talkable"
    )
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
