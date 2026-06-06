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

import asyncio
import io
import threading
import time
from collections.abc import AsyncIterator

import numpy as np
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from PIL import Image, ImageDraw
from starlette.concurrency import run_in_threadpool

from .config import Settings
from .pipeline import Pipeline

_BOUNDARY = "ocularframe"
# The MJPEG preview is JPEG-encoded per frame — the heavy bit on a Pi 3 B+. The
# detector samples at the full camera fps; the *preview* doesn't need to, so cap
# it well below so a 30/60 fps capture rate can't peg the CPU on encoding.
_STREAM_FPS_CAP = 12
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


class StreamHub:
    """One shared MJPEG encoder for all viewers.

    The old code ran a separate encode loop per connection, so cost scaled with
    viewer count — and an infinite generator with no disconnect check leaked an
    encoder on every page reload (the old stream kept running behind the proxy).
    This hub encodes each frame *once* and fans the bytes out to every viewer;
    the encoder thread only runs while at least one viewer is connected and stops
    when the count hits zero, so an idle app (no tab open) does no encoding at
    all. Viewers are reference-counted; the count is exposed at /api/state."""

    def __init__(self, pipeline: Pipeline) -> None:
        self._pipeline = pipeline
        self._lock = threading.Lock()
        self._viewers = 0
        self._jpeg: bytes | None = None
        self._seq = 0
        self._thread: threading.Thread | None = None

    @property
    def viewers(self) -> int:
        with self._lock:
            return self._viewers

    def acquire(self) -> None:
        with self._lock:
            self._viewers += 1
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(
                    target=self._encode_loop, name="ocular-stream", daemon=True
                )
                self._thread.start()

    def release(self) -> None:
        with self._lock:
            self._viewers = max(0, self._viewers - 1)

    def latest(self, since_seq: int) -> tuple[bytes, int] | None:
        """Return (jpeg, seq) if a frame newer than since_seq exists, else None."""
        with self._lock:
            if self._jpeg is not None and self._seq != since_seq:
                return self._jpeg, self._seq
            return None

    def _encode_loop(self) -> None:
        while True:
            with self._lock:
                if self._viewers == 0:
                    self._jpeg = None  # drop the last frame; encoder exits
                    return
            frame = self._pipeline.latest_frame()
            if frame is not None:
                threshold = self._pipeline.config.detectors.revolution.threshold
                jpeg = _render(frame, self._pipeline.overlays(), mask=False, threshold=threshold)
                with self._lock:
                    self._jpeg = jpeg
                    self._seq += 1
            cap = min(self._pipeline.effective_fps, _STREAM_FPS_CAP)
            time.sleep(1.0 / cap)


def create_app(pipeline: Pipeline, settings: Settings) -> FastAPI:
    app = FastAPI(title="ocular", docs_url=None, redoc_url=None, openapi_url=None)
    hub = StreamHub(pipeline)

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
        return {
            "synthetic": pipeline.is_synthetic,
            "viewers": hub.viewers,
            "capture_fps": pipeline.effective_fps,
            "detectors": pipeline.states(),
        }

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

    def _part(jpeg: bytes) -> bytes:
        return (
            f"--{_BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
            f"Content-Length: {len(jpeg)}\r\n\r\n"
        ).encode() + jpeg + b"\r\n"

    @app.get("/stream.mjpg")
    async def stream(request: Request, mask: int = 0) -> StreamingResponse:
        # Reference-count this viewer so the hub knows when to encode / idle, and
        # release it when the client goes away (browser close, reload, nav). The
        # async is_disconnected() check is what actually reaps a closed stream —
        # the old infinite generator never noticed, so reloads leaked encoders.
        hub.acquire()

        async def frames() -> AsyncIterator[bytes]:
            last = -1
            try:
                while not await request.is_disconnected():
                    cap = min(pipeline.effective_fps, _STREAM_FPS_CAP)
                    if mask:
                        # Mask is a per-client tuning view (rare) — encode off the
                        # event loop so it can't block other requests.
                        frame = pipeline.latest_frame()
                        if frame is None:
                            await asyncio.sleep(0.05)
                            continue
                        threshold = pipeline.config.detectors.revolution.threshold
                        jpeg = await run_in_threadpool(
                            _render, frame, pipeline.overlays(), mask=True, threshold=threshold
                        )
                        yield _part(jpeg)
                        await asyncio.sleep(1.0 / cap)
                    else:
                        got = hub.latest(last)  # shared bytes — no per-client encode
                        if got is None:
                            await asyncio.sleep(0.5 / cap)
                            continue
                        jpeg, last = got
                        yield _part(jpeg)
            finally:
                hub.release()

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
