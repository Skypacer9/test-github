# Warring States Field

Generative historical possibility engine + Flask HTML frontend for a late Warring States meso-coalition demo.

**Do not confuse with** `Skypacer9/worldLineSim` — this is a separate hand-in.

## Run (Flask)

```bash
pip install -r requirements-web.txt
python server.py
```

Open http://127.0.0.1:8080/

Optional env: `WS_HOST`, `WS_PORT` (default `127.0.0.1:8080`).

## Layout

| Path | Role |
|------|------|
| `engine/` | Historical engine (no Flask/Gradio) |
| `backend.py` | Adapter: engine → UI meters / chat |
| `server.py` | Flask HTML API + static UI |
| `static/` | Frontend (`index.html`, portraits) |
| `cli.py` | Terminal playtest |
| `app.py` | Legacy Gradio UI (parked) |
| `tests/` | pytest |

## Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
```
