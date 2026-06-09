# ocular — repo overview

Camera-vision detector over a Raspberry Pi camera feed (synthetic source
off-Pi). Currently counts cat-wheel revolutions; the detector layer is
pluggable. Sibling in eetu's homebrew family ([halo](../halo), [chat](../chat),
[scribe](../scribe), [raspi-dashboard](../raspi-dashboard)) — shares the design
system; first **Python**-backed app and first **Svelte** frontend.

## Layout

```
backend/         Python FastAPI + picamera2 (Pi) / synthetic source (dev), SQLite
frontend/        Svelte 5 + Vite SPA (raw Svelte, not SvelteKit)
.claude/skills/  ocular-design skill (visual language, brand)
Dockerfile       multi-stage: node build + Python runtime (picamera2 via apt)
```

Per-area instructions in `backend/CLAUDE.md` and `frontend/CLAUDE.md`.
Backend conventions are the family's `python-service` pattern.

## Conventions

- **Auth at the edge.** Behind oauth2-proxy (Traefik). Trusts
  `X-Auth-Request-User` / `-Email`; `/status` is unauthenticated (liveness probe).
- **3-layer config.** Code defaults (`Config` dataclass) → deploy base JSON
  (`OCULAR_CONFIG`, re-rendered per deploy) → runtime UI overrides (SQLite
  `meta.config_overrides`, deep-merged so they survive redeploys).
- **Synthetic fallback.** Off-Pi, `picamera2` import fails gracefully and
  `camera.py` serves a synthetic moving-marker through the same frame loop — dev
  the detector + UI on a Mac with no hardware.
- **Latest-frame only.** Capture thread keeps just the newest frame (no queue
  backlog when encoding/serving lags).
- **Rebaseable count.** Revolution count persists in SQLite (`revolutions`,
  tagged per source); the displayed counter resets via
  `POST /api/detectors/revolution/reset` without dropping history.
- **Lazy MJPEG.** `GET /stream.mjpg?mask=1` encodes JPEG frames (optional ROI/
  line overlays) only while a viewer is connected.

## Working on this repo

- Backend `:8099` (`OCULAR_BIND`), synthetic source, no picamera2 needed:
  `cd backend && uv run ocular`.
- Frontend dev `:5173`: `cd frontend && yarn && yarn dev`; Vite proxies `/api`
  and `/stream.mjpg` to `:8099`.
- Key env: `OCULAR_BIND`, `OCULAR_STATE_DIR`, `OCULAR_DB`, `OCULAR_CONFIG`,
  `OCULAR_STATIC_DIR`. See `backend/src/ocular/config.py`.

## Out of scope (for now)

- Detectors beyond revolution (motion/face/object are planned, not built)
- Hall-GPIO input (config stub exists, disabled)
- Persistent login / per-user prefs (edge auth only)

If a feature crosses into those areas, raise it before implementing.
