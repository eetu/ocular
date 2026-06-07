# ocular

A camera-vision app with a pluggable **detector pipeline** over a Raspberry Pi
camera feed. The first detector counts revolutions of a cat exercise wheel from
a high-contrast marker (black tape on the rim); motion / face / object detectors
are the planned next ones.

Part of the homebrew app family (halo-design look, deployed to the Pi by the
[`raspi`](../raspi) pyinfra repo). Backend is **Python** (FastAPI + picamera2);
UI is a **Svelte** SPA the backend serves.

## Layout

```
backend/   FastAPI app — capture core, detector plugins, web layer
frontend/  Svelte + Vite SPA → dist/ (served by the backend)
Dockerfile container-ready (native systemd is the v1 deploy; see below)
```

## How it works

- **Capture** (`backend/src/ocular/camera.py`) — a thread keeps only the latest
  frame (no backlog). Real source is picamera2; off a Pi it falls back to a
  synthetic moving-marker source so the whole app runs on a dev machine.
- **Detectors** (`backend/src/ocular/detectors/`) — each consumes a grayscale
  frame and emits a small state dict. `revolution` is an ROI line-crossing
  counter (threshold + hysteresis debounce). Add one by subclassing `Detector`
  and registering it.
- **Store** (`backend/src/ocular/store.py`) — a SQLite time-series, one row per
  revolution tagged with its `source` ('camera'; 'hall' when the GPIO sensor
  lands) and instantaneous rpm. Replaces the old `state.json` total (migrated on
  first run). Counts, avg speed, activity sessions and distance all derive from
  it; the displayed counter is rebaseable (reset preserves history). Its `meta`
  table also holds the runtime config overrides (see Config) — state that must
  outlive a redeploy lives here, not in the deploy-rendered config file.
- **Web** (`backend/src/ocular/web.py`) — `GET /stream.mjpg[?mask=1]`,
  `GET /api/state`, `GET /api/config`, `POST /api/detectors/revolution/config`
  (live reconfigure), `GET /api/stats`, `GET /api/history?hours&bucket`,
  `GET /api/sessions?hours&gap`, `GET /status` (unauth liveness). Serves the SPA
  from `dist/` (a `live | history` view toggle). Trusts `X-Auth-Request-*` from
  the oauth2-proxy edge.

## Develop

```sh
# backend (serves API + stream on :8099; synthetic source off-Pi)
cd backend && uv run ocular
# frontend (Vite dev server, proxies /api + /stream to :8099)
cd frontend && yarn && yarn dev
```

Tune the ROI/threshold live from the UI while watching the stream — changes
persist to the store and survive a redeploy.

## Config

Three layers, deep-merged (later wins):

1. **Code defaults** — the dataclasses in `config.py`.
2. **Deploy base** — a JSON file (`OCULAR_CONFIG`, `/etc/ocular/config.json`)
   rendered by the raspi deploy from its `OCULAR` dict. Deploy-owned and
   re-rendered every deploy; the app only reads it. Absent in dev → code defaults.
3. **Runtime overrides** — only the keys the UI changed, stored as a JSON delta
   in the SQLite store (`meta.config_overrides`, under `OCULAR_STATE_DIR`).
   App-owned; the deploy never touches the state dir, so a UI tweak (ROI,
   threshold, ...) survives a redeploy and wins over the base.

Env (deploy invariants, not UI-tunable): `OCULAR_BIND`, `OCULAR_STATIC_DIR`,
`OCULAR_CONFIG`, `OCULAR_STATE_DIR`, `OCULAR_DB` (defaults to
`<state_dir>/ocular.db`). Set camera `rotation` to `180` for an upside-down
camera (in the deploy base, or live from the UI); a correctly mounted case
needs `0`.

## Deploy

v1 runs as a sandboxed **native systemd service** on the Pi (picamera2 → `/dev/*`
directly); the `Dockerfile` exists for a later podman-quadlet cutover once
libcamera-in-container is wired. See `tasks/ocular.py` + `tasks/camera.py` in the
`raspi` repo.
