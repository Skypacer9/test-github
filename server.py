#!/usr/bin/env python3
"""Flask HTML frontend for the Warring States sim — thin wrapper over backend.py.

Per-browser cookie sessions isolate campaigns. Bounded player/save quotas + TTL,
request size caps, CSRF, optional WS_ACCESS_TOKEN (header/cookie only).
LLM is opt-in (WS_LLM_ENABLED=1 + API key); all LLM paths share global+session caps.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import threading
import time
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any

from flask import Flask, g, jsonify, request, send_from_directory, session

from backend import (
    advance_quarter,
    attempt_alliance,
    bootstrap_dialogue,
    character_choices,
    character_profile,
    do_player_action,
    do_player_offensive,
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

# --- Resource / privacy bounds (override via env) ---
MAX_CONTENT_LENGTH = int(os.environ.get("WS_MAX_CONTENT_LENGTH") or str(256 * 1024))
MAX_PLAYERS = int(os.environ.get("WS_MAX_PLAYERS") or "48")
PLAYER_TTL_S = int(os.environ.get("WS_PLAYER_TTL_S") or str(2 * 60 * 60))
MAX_SLOTS_PER_PLAYER = int(os.environ.get("WS_MAX_SLOTS") or "6")
MAX_PLAYER_DISK_BYTES = int(os.environ.get("WS_MAX_PLAYER_DISK") or str(384 * 1024))
SESSION_CREATE_MAX_PER_MIN = int(os.environ.get("WS_SESSION_CREATE_MAX_PER_MIN") or "20")
LLM_MAX_PER_HOUR = int(os.environ.get("WS_LLM_MAX_PER_HOUR") or "8")
LLM_GLOBAL_MAX_PER_HOUR = int(os.environ.get("WS_LLM_GLOBAL_MAX_PER_HOUR") or "24")
WRITE_MAX_PER_MIN = int(os.environ.get("WS_WRITE_MAX_PER_MIN") or "60")
JSON_MAX_DEPTH = int(os.environ.get("WS_JSON_MAX_DEPTH") or "24")


def _cookie_secure_default() -> bool:
    """Prefer Secure cookies; allow explicit override for plain-HTTP lab binds."""
    raw = (os.environ.get("WS_COOKIE_SECURE") or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    # Published Cursor apps are HTTPS; local loopback still accepts Secure in modern browsers.
    return True


def _resolve_secret_key() -> str:
    """Stable signing secret: env first, else persisted local file (not random each boot)."""
    for key in ("WS_SECRET_KEY", "WS_SECRET", "FLASK_SECRET_KEY"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    # Soft local default — documented for lab/demo only; set WS_SECRET_KEY in production.
    path = SAVES / ".flask_secret"
    try:
        SAVES.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            existing = path.read_text(encoding="utf-8").strip()
            if len(existing) >= 32:
                return existing
        val = secrets.token_hex(32)
        path.write_text(val, encoding="utf-8")
        return val
    except OSError:
        return secrets.token_hex(32)


app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
app.secret_key = _resolve_secret_key()
app.config.update(
    SESSION_COOKIE_NAME="ws_field_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_cookie_secure_default(),
    PERMANENT_SESSION_LIFETIME=timedelta(seconds=max(300, PLAYER_TTL_S)),
    MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
)

_lock = threading.RLock()
# player_id -> {state, chat, llm_ts, write_ts, touched, created}
_players: dict[str, dict[str, Any]] = {}
_global_llm_ts: list[float] = []
_session_create_ts: list[float] = []


def _access_token() -> str:
    return (os.environ.get("WS_ACCESS_TOKEN") or "").strip()


def _llm_enabled() -> bool:
    """Opt-in: WS_LLM_ENABLED=1|true|yes|on AND an API key. Default OFF."""
    from engine.llm_gate import llm_env_enabled

    return llm_env_enabled()


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


def _prune_ts(rows: list[float], window_s: float) -> list[float]:
    now = time.time()
    return [t for t in rows if now - t < window_s]


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def _evict_players_locked(now: float | None = None) -> None:
    """Drop TTL-expired buckets; if still over cap, drop least-recently touched."""
    now = time.time() if now is None else now
    expired = [
        pid
        for pid, b in _players.items()
        if now - float(b.get("touched") or 0) > PLAYER_TTL_S
    ]
    for pid in expired:
        _players.pop(pid, None)
        # Best-effort disk cleanup for expired sessions
        try:
            d = PLAYERS_ROOT / "".join(ch for ch in pid if ch.isalnum() or ch in ("-", "_"))[:64]
            if d.is_dir() and d.resolve().is_relative_to(PLAYERS_ROOT.resolve()):
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass
    while len(_players) > MAX_PLAYERS:
        oldest_pid = min(_players.items(), key=lambda kv: float(kv[1].get("touched") or 0))[0]
        _players.pop(oldest_pid, None)


def _can_create_session_locked() -> str | None:
    global _session_create_ts
    _session_create_ts = _prune_ts(_session_create_ts, 60.0)
    if len(_session_create_ts) >= max(1, SESSION_CREATE_MAX_PER_MIN):
        return "server busy — too many new sessions; retry shortly"
    if len(_players) >= MAX_PLAYERS:
        _evict_players_locked()
    if len(_players) >= MAX_PLAYERS:
        return "server at capacity — try again later"
    return None


def _player_id() -> str:
    pid = session.get("player_id")
    creating = not (isinstance(pid, str) and len(pid) >= 12)
    if creating:
        with _lock:
            err = _can_create_session_locked()
            if err:
                # Surface via session flag; callers check _session_admit_error
                session["admit_error"] = err
                return ""
            pid = secrets.token_urlsafe(18)
            _session_create_ts.append(time.time())
        session["player_id"] = pid
        session.permanent = True
        session.pop("admit_error", None)
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
    if not pid:
        raise RuntimeError(session.get("admit_error") or "session capacity exceeded")
    now = time.time()
    with _lock:
        _evict_players_locked(now)
        b = _players.get(pid)
        if b is None:
            # Returning cookie after eviction — re-admit if capacity allows
            err = _can_create_session_locked()
            if err and len(_players) >= MAX_PLAYERS:
                raise RuntimeError(err)
            b = {
                "state": {},
                "chat": [],
                "llm_ts": [],
                "write_ts": [],
                "touched": now,
                "created": now,
            }
            _players[pid] = b
            _session_create_ts.append(now)
        else:
            b["touched"] = now
        return b


def _json_depth(obj: Any, *, depth: int = 0) -> int:
    if depth > JSON_MAX_DEPTH:
        return depth
    if isinstance(obj, dict):
        if not obj:
            return depth
        return max(_json_depth(v, depth=depth + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return depth
        return max(_json_depth(v, depth=depth + 1) for v in obj)
    return depth


def _rate_limit_writes(b: dict[str, Any]) -> str | None:
    with _lock:
        b["write_ts"] = _prune_ts(list(b.get("write_ts") or []), 60.0)
        if len(b["write_ts"]) >= max(1, WRITE_MAX_PER_MIN):
            return "rate limit: too many actions — wait a moment"
        b["write_ts"].append(time.time())
    return None


def _rate_limit_llm(b: dict[str, Any]) -> str | None:
    """Per-session and global LLM caps (cost / abuse control)."""
    global _global_llm_ts
    with _lock:
        b["llm_ts"] = _prune_ts(list(b.get("llm_ts") or []), 3600.0)
        _global_llm_ts = _prune_ts(_global_llm_ts, 3600.0)
        if len(b["llm_ts"]) >= max(1, LLM_MAX_PER_HOUR):
            return "LLM rate limit — offline stub only for now"
        if len(_global_llm_ts) >= max(1, LLM_GLOBAL_MAX_PER_HOUR):
            return "global LLM budget exhausted — offline stub only"
        now = time.time()
        b["llm_ts"].append(now)
        _global_llm_ts.append(now)
    return None


def _disk_quota_ok(pid: str, *, extra_bytes: int = 0, new_named_slot: bool = False) -> str | None:
    root = _player_dir(pid)
    slots = [p for p in root.glob("*.json") if p.stem not in ("session", "autosave")]
    if new_named_slot and len(slots) >= MAX_SLOTS_PER_PLAYER:
        return f"save slot limit ({MAX_SLOTS_PER_PLAYER}) reached"
    if len(slots) > MAX_SLOTS_PER_PLAYER:
        return f"save slot limit ({MAX_SLOTS_PER_PLAYER}) reached"
    used = _dir_size(root)
    if used + max(0, extra_bytes) > MAX_PLAYER_DISK_BYTES:
        return "save disk quota exceeded for this session"
    return None


def _auth_gate() -> tuple[bool, str | None]:
    """Private-app-safe gate: signed session always; optional shared access token."""
    pid = _player_id()
    if not pid:
        return False, session.get("admit_error") or "server at capacity"
    token = _access_token()
    if not token:
        return True, None
    # Header / cookie only — never accept tokens from query strings (Referer/log leak).
    auth = request.headers.get("Authorization") or ""
    hdr = (request.headers.get("X-WS-Token") or "").strip()
    cookie_tok = (request.cookies.get("ws_access_token") or "").strip()
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if (
        (bearer and secrets.compare_digest(bearer, token))
        or (hdr and secrets.compare_digest(hdr, token))
        or (cookie_tok and secrets.compare_digest(cookie_tok, token))
    ):
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


def _write_session(pid: str, snap: dict[str, Any]) -> str | None:
    """Write autosave; returns error string if quota blocks the write."""
    try:
        raw = json.dumps(snap, ensure_ascii=False)
        path = _session_path(pid)
        existing = path.stat().st_size if path.exists() else 0
        err = _disk_quota_ok(pid, extra_bytes=max(0, len(raw.encode("utf-8")) - existing))
        if err:
            return err
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw, encoding="utf-8")
    except OSError:
        return "save write failed"
    return None


def _write_named_slot(pid: str, name: str, snap: dict[str, Any]) -> dict[str, Any]:
    """Write/overwrite one named slot file. Returns meta. Raises ValueError on quota."""
    sid = _safe_slot_id(name)
    snap = dict(snap)
    snap["slot_id"] = sid
    snap["slot_name"] = name.strip()
    path = _slot_path(pid, sid)
    raw = json.dumps(snap, ensure_ascii=False)
    existing = path.stat().st_size if path.exists() else 0
    is_new = not path.exists()
    err = _disk_quota_ok(
        pid,
        extra_bytes=max(0, len(raw.encode("utf-8")) - existing),
        new_named_slot=is_new,
    )
    if err:
        raise ValueError(err)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
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
        code = 503 if err and ("capacity" in err or "busy" in err) else 401
        return jsonify({"ok": False, "error": err or "unauthorized"}), code
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
    try:
        b = _bucket()
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
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


@app.before_request
def _bind_llm_admit():
    """Attach global+session LLM budget to every API request (advance/tick/counsel/chronicle)."""
    g._llm_admit_token = None
    if not request.path.startswith("/api/"):
        return None
    if request.path == "/api/health":
        return None
    try:
        from engine.llm_gate import set_llm_admit

        b = _bucket()

        def admit() -> bool:
            return _rate_limit_llm(b) is None

        g._llm_admit_token = set_llm_admit(admit)
    except Exception:  # noqa: BLE001 — no session yet / capacity
        g._llm_admit_token = None
    return None


@app.teardown_request
def _clear_llm_admit(_exc: BaseException | None) -> None:
    tok = getattr(g, "_llm_admit_token", None)
    if tok is not None:
        try:
            from engine.llm_gate import reset_llm_admit

            reset_llm_admit(tok)
        except Exception:  # noqa: BLE001
            pass


@app.errorhandler(413)
def _too_large(_err: Any):
    return jsonify({"ok": False, "error": f"payload too large (max {MAX_CONTENT_LENGTH} bytes)"}), 413


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
    sess_err = _write_session(pid, snap)
    if sess_err and not meta:
        return jsonify({"ok": False, "error": sess_err}), 400
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
    # Bound body size even when Content-Length is missing/wrong
    raw = request.get_data(cache=True, as_text=False) or b""
    if len(raw) > MAX_CONTENT_LENGTH:
        return jsonify({"ok": False, "error": f"payload too large (max {MAX_CONTENT_LENGTH} bytes)"}), 413
    body = request.get_json(silent=True) or {}
    if _json_depth(body) > JSON_MAX_DEPTH:
        return jsonify({"ok": False, "error": f"JSON too deeply nested (max depth {JSON_MAX_DEPTH})"}), 400
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
    if _json_depth(snap) > JSON_MAX_DEPTH:
        return jsonify({"ok": False, "error": f"snapshot too deeply nested (max depth {JSON_MAX_DEPTH})"}), 400
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
    pack = _pack(projected, msgs)
    # Portrait dialogue: show this quarter's Chronicler line (not buried auto-counsel)
    adv_dlg = projected.get("advance_dialogue")
    if isinstance(adv_dlg, dict) and adv_dlg.get("text"):
        pack["dialogue"] = {
            "speaker": str(adv_dlg.get("speaker") or "Chronicler"),
            "text": str(adv_dlg.get("text") or ""),
        }
    return jsonify(pack)


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


@app.post("/api/offensive")
def api_offensive():
    """Player Offensive — body: {attacker, target}. Soft cap 3/quarter; court capacity gated."""
    blocked = _mutate_guard()
    if blocked:
        return blocked
    st = _ensure()
    body = request.get_json(silent=True) or {}
    attacker = str(body.get("attacker") or body.get("from") or "").strip().lower()
    target = str(body.get("target") or body.get("to") or body.get("defender") or "").strip().lower()
    if not attacker or not target:
        return jsonify({"ok": False, "error": "attacker and target required"}), 400
    projected, msgs, err = do_player_offensive(st, attacker, target)
    pack = _pack(projected, msgs)
    pack["offensive"] = projected.get("last_player_offensive")
    pack["player_offensive_actions_left"] = int(
        projected.get("player_offensive_actions_left") or 0
    )
    pack["offensive_capacity"] = projected.get("offensive_capacity") or {}
    if err:
        pack["ok"] = False
        pack["error"] = err
        return jsonify(pack), 400
    return jsonify(pack)


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
    """Counsel: private one-on-one, circle (figure_ids), or atmosphere broadcast.

    Body: { "prompt": "...", "commit": false, "figure_id": "zhaoxiang"|null,
            "figure_ids": ["kaolie","chunshen"] }.
    Tips dials on close only. English UI. Defaults to offline stub.
    """
    blocked = _mutate_guard()
    if blocked:
        return blocked
    st = _ensure()
    body = request.get_json(silent=True) or {}
    prompt = body.get("prompt") or body.get("text") or ""
    commit = bool(body.get("commit") or body.get("close") or False)
    figure_id = body.get("figure_id") or body.get("figure") or None
    if figure_id is not None:
        figure_id = str(figure_id).strip().lower() or None
    raw_ids = body.get("figure_ids") or body.get("figures") or None
    figure_ids = None
    if isinstance(raw_ids, (list, tuple)):
        figure_ids = [str(x).strip().lower() for x in raw_ids if str(x).strip()]
    # LLM budget enforced inside counsel_llm/chronicle via admit_llm_call (same caps as tick).
    projected, msgs, err, result = run_counsel(
        st, prompt=str(prompt), commit=commit, figure_id=figure_id, figure_ids=figure_ids
    )
    pack = _pack(projected, msgs)
    pack["counsel_result"] = projected.get("counsel_result") or result
    pack["talkable_cast"] = projected.get("talkable_cast")
    # After Speak/Decide, portrait dialogue must show the focus figure — not stale Chronicler
    dlg = projected.get("counsel_dialogue")
    if isinstance(dlg, dict) and dlg.get("text"):
        pack["dialogue"] = {
            "speaker": str(dlg.get("speaker") or "Counsel"),
            "text": str(dlg.get("text") or ""),
        }
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
    print(f"LLM enabled: {_llm_enabled()} (opt-in: WS_LLM_ENABLED=1 + API key; default off)")
    print(
        "API: /api/state /api/new /api/saves /api/save /api/load /api/advance /api/intervene /api/alliance "
        "/api/alliance_fund /api/player_action /api/fund_military /api/send_grain "
        "/api/broker_mediation /api/offensive /api/profile /api/counsel /api/talkable"
    )
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
