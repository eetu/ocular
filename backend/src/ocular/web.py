"""HTTP layer.

Endpoints:
  GET  /status                          unauth liveness (gatus probe)
  GET  /api/me                          trusted user from the oauth2-proxy edge
  GET  /api/state                       detector states
  GET  /api/config                      current config
  POST /api/detectors/revolution/config live-reconfigure the counter
  GET  /stream.mjpg[?mask=1]            live MJPEG (overlay, or threshold mask)
  GET  /*                               the Svelte SPA (dist/) with fallback

Trust model: ocular sits behind oauth2-proxy on the Pi edge (a Traefik gated
host), so X-Auth-Request-User / -Email are trustworthy *when present*. We never
log them (PII) and never gate on them here — LAN-direct access (no proxy) is a
supported tuning path, so a missing header just yields an anonymous identity.
"""

from __future__ import annotations

import io
import time
from collections.abc import Iterator

import numpy as np
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from PIL import Image, ImageDraw

from .config import Settings
from .pipeline import Pipeline

_BOUNDARY = "ocularframe"
# accent #f78f08 (active) / muted grey (idle) — matches halo-design tokens.
_ACTIVE_RGB = (247, 143, 8)
_IDLE_RGB = (160, 160, 160)


def _encode_jpeg(img: Image.Image, quality: int = 70) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _render(frame: np.ndarray, overlays: list[dict], *, mask: bool, threshold: int) -> bytes:
    if mask:
        # Show exactly what the detector sees: ROI-threshold as black/white.
        gray = frame.mean(axis=2).astype(np.uint8)
        binary = np.where(gray < threshold, 0, 255).astype(np.uint8)
        img = Image.fromarray(binary, mode="L").convert("RGB")
    else:
        # picamera2 "RGB888" is BGR-in-memory; swap to RGB for correct display.
        img = Image.fromarray(frame[..., ::-1])
    draw = ImageDraw.Draw(img)
    for ov in overlays:
        x, y, w, h = ov.get("roi", (0, 0, 0, 0))
        color = _ACTIVE_RGB if ov.get("active") else _IDLE_RGB
        draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
        label = ov.get("label")
        if label:
            draw.text((x + 4, y + 4), label, fill=color)
    return _encode_jpeg(img)


def create_app(pipeline: Pipeline, settings: Settings) -> FastAPI:
    app = FastAPI(title="ocular", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/status")
    def status() -> dict:
        return {"status": "ok", "synthetic": pipeline.is_synthetic}

    @app.get("/api/me")
    def me(request: Request) -> dict:
        return {
            "user": request.headers.get("X-Auth-Request-User"),
            "email": request.headers.get("X-Auth-Request-Email"),
        }

    @app.get("/api/state")
    def state() -> dict:
        return {"synthetic": pipeline.is_synthetic, "detectors": pipeline.states()}

    @app.get("/api/config")
    def get_config() -> dict:
        return pipeline.config.to_dict()

    @app.post("/api/detectors/revolution/config")
    async def set_revolution(request: Request) -> JSONResponse:
        changes = await request.json()
        return JSONResponse(pipeline.reconfigure_revolution(changes))

    @app.post("/api/camera/config")
    async def set_camera(request: Request) -> JSONResponse:
        changes = await request.json()
        return JSONResponse(pipeline.reconfigure_camera(changes))

    @app.get("/stream.mjpg")
    def stream(mask: int = 0) -> StreamingResponse:
        def frames() -> Iterator[bytes]:
            interval = 1.0 / max(1, pipeline.config.camera.fps)
            while True:
                frame = pipeline.latest_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue
                threshold = pipeline.config.detectors.revolution.threshold
                jpeg = _render(frame, pipeline.overlays(), mask=bool(mask), threshold=threshold)
                yield (
                    f"--{_BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg)}\r\n\r\n"
                ).encode() + jpeg + b"\r\n"
                time.sleep(interval)

        return StreamingResponse(
            frames(),
            media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
            headers={"Cache-Control": "no-store"},
        )

    _mount_spa(app, settings)
    return app


def _mount_spa(app: FastAPI, settings: Settings) -> None:
    """Serve the built Svelte SPA from dist/ with a client-route fallback.

    Real files (assets, index.html) are served directly; any other non-API path
    falls back to index.html so client-side routing works. No-op if dist/ is
    absent (running the backend alone in dev — use the Vite dev server then)."""
    dist = settings.static_dir
    index = dist / "index.html"
    if not index.is_file():
        return

    @app.get("/{path:path}")
    def spa(path: str) -> Response:
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)
