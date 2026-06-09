# ocular backend

Python FastAPI — the family's `python-service` pattern (uv, ruff, plain uvicorn,
src layout). Primary backend here (the hardware lib forces Python): serves the
SPA from `dist/` + `/api` + the MJPEG stream.

## Module map (`src/ocular/`)

- `__main__.py` — console entry (`uv run ocular`) → `uvicorn.run`.
- `main.py` — load `Config`/`Settings`, build + start the app, startup/shutdown
  hooks driving `pipeline.start()` / `.stop()`.
- `config.py` — `Config`/`Settings` dataclasses + the 3-layer merge.
- `camera.py` — `Capture`: picamera2 on Pi, synthetic moving-marker off-Pi.
- `pipeline.py` — frame loop, detector tick, FPS adaptation, latest-frame buffer.
- `store.py` — SQLite time-series (`revolutions`) + migration from old `state.json`.
- `web.py` — FastAPI routes, MJPEG stream, `_mount_spa()` (dist/ + client-route fallback).
- `detectors/revolution.py` — `RevolutionDetector`: ROI, line-crossing, debounce,
  rebaseable count.

## Notes

- No `pydantic-settings` — config is dataclasses from env. Pydantic only for
  request bodies if needed.
- Lint/format: `uv run ruff check` + `uv run ruff format` (config in `pyproject.toml`).
- Detectors are pluggable under `detectors/`; add a new one without touching the
  pipeline contract.
