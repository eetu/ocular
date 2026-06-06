"""Capture core.

A background thread pulls frames from a source and keeps only the *latest* one
(no queue), so consumers — the detector pipeline and the MJPEG stream — never
fall behind real time. This is the documented fix for the Pi's frame-pile-up
latency trap: a naive read loop accumulates a multi-second backlog.

Two sources:
  * Picamera2Source — the real Pi camera (libcamera). Imported lazily so the
    package runs on a dev machine / in CI where picamera2 isn't installed.
  * SyntheticSource — an off-Pi fallback that renders a moving dark marker on a
    light field, so the whole app (UI, stream, revolution counter) is
    exercisable without hardware.

Frames are plain numpy uint8 HxWx3 arrays. We deliberately avoid OpenCV: numpy
covers the grayscale/threshold the detectors need, and Pillow covers JPEG encode
+ overlay drawing in the web layer — one fewer heavy ARM dependency on the Pi.
"""

from __future__ import annotations

import threading
import time

import numpy as np

from .config import CameraConfig


class CameraSource:
    """Capture source interface."""

    def start(self) -> None: ...

    def capture(self) -> np.ndarray:
        """Return one frame as an HxWx3 uint8 array."""
        raise NotImplementedError

    def set_fps(self, fps: int) -> None:
        """Retune the capture frame rate live (no-op if the source can't)."""

    def stop(self) -> None: ...


class Picamera2Source(CameraSource):
    def __init__(self, cfg: CameraConfig) -> None:
        self._cfg = cfg
        self._cam = None

    def start(self) -> None:
        from picamera2 import Picamera2  # lazy: only present on the Pi

        self._cam = Picamera2()
        # NB: picamera2's "RGB888" delivers channels in BGR order in memory.
        # Irrelevant for the luminance the detectors use; the web layer corrects
        # the order before JPEG-encoding for display.
        video = self._cam.create_video_configuration(
            main={"size": (self._cfg.width, self._cfg.height), "format": "RGB888"},
            controls={"FrameRate": float(self._cfg.fps)},
        )
        self._cam.configure(video)
        self._cam.start()

    def capture(self) -> np.ndarray:
        return self._cam.capture_array()

    def set_fps(self, fps: int) -> None:
        if self._cam is not None:
            try:
                self._cam.set_controls({"FrameRate": float(fps)})
            except Exception as e:  # control may be momentarily unsettable
                print(f"ocular: could not set FrameRate={fps}: {e}")

    def stop(self) -> None:
        if self._cam is not None:
            self._cam.stop()
            self._cam.close()
            self._cam = None


class SyntheticSource(CameraSource):
    """Off-Pi fallback: a light field with a dark bar sweeping across, so the
    revolution detector sees a periodic marker crossing without a camera."""

    def __init__(self, cfg: CameraConfig) -> None:
        self._cfg = cfg
        self._fps = max(1, cfg.fps)
        self._start = 0.0

    def start(self) -> None:
        self._start = time.monotonic()

    def capture(self) -> np.ndarray:
        w, h = self._cfg.width, self._cfg.height
        frame = np.full((h, w, 3), 200, dtype=np.uint8)  # light grey field
        # One full sweep every 4 s → ~0.25 "rev/s" for the counter to pick up.
        phase = ((time.monotonic() - self._start) / 4.0) % 1.0
        bar_x = int(phase * w)
        # Wide enough to fully darken a typical ROI as it sweeps through, so the
        # revolution counter actually triggers in dev without a camera.
        frame[:, max(0, bar_x - 60) : bar_x + 60] = 20
        time.sleep(1.0 / self._fps)
        return frame

    def set_fps(self, fps: int) -> None:
        self._fps = max(1, fps)

    def stop(self) -> None:
        pass


def build_source(cfg: CameraConfig) -> CameraSource:
    """Pick the real camera if picamera2 is importable, else the fallback."""
    try:
        import picamera2  # noqa: F401

        return Picamera2Source(cfg)
    except Exception:
        print("ocular: picamera2 unavailable — using synthetic capture source")
        return SyntheticSource(cfg)


def _rotate(frame: np.ndarray, rotation: int) -> np.ndarray:
    k = (rotation // 90) % 4
    return frame if k == 0 else np.rot90(frame, k)


class Capture:
    """Owns the source + background thread, exposes the latest frame."""

    def __init__(self, cfg: CameraConfig) -> None:
        self._cfg = cfg
        self._source = build_source(cfg)
        self._rotation = cfg.rotation  # mutable: tunable live from the UI
        self._fps = max(1, cfg.fps)  # effective rate; driven by adaptive idling
        self._latest: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def set_rotation(self, rotation: int) -> None:
        self._rotation = rotation % 360

    def set_fps(self, fps: int) -> None:
        # Effective capture rate — driven by the pipeline's adaptive idle logic,
        # so it deliberately does NOT touch the configured CameraConfig.fps (the
        # active-rate ceiling the user picked). Just retunes the live source.
        self._fps = max(1, int(fps))
        self._source.set_fps(self._fps)

    @property
    def is_synthetic(self) -> bool:
        return isinstance(self._source, SyntheticSource)

    def start(self) -> None:
        self._source.start()
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="ocular-capture", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            try:
                frame = _rotate(self._source.capture(), self._rotation)
                with self._lock:
                    self._latest = frame
            except Exception as e:  # keep the thread alive across transient errors
                print(f"ocular: capture error: {e}")
                time.sleep(0.2)

    def latest(self) -> np.ndarray | None:
        with self._lock:
            return None if self._latest is None else self._latest.copy()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._source.stop()
