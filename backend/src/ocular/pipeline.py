"""The pipeline ties capture → detectors → state together.

A background thread reads the latest frame and feeds it to every enabled
detector each tick (detectors grayscale only their own ROI). Detector results
are read by the web layer (/api/state) and drawn onto the MJPEG overlay. The
revolution count is persisted periodically so a restart doesn't lose the total.

Adaptive idle: the loop watches a cheap whole-scene motion signal and drops the
capture rate to camera.idle_fps after a few still seconds, ramping back to
camera.fps the instant something moves — so a parked wheel barely loads the Pi.
"""

from __future__ import annotations

import json
import threading
import time

import numpy as np

from .camera import Capture
from .config import Config, Settings, save_config
from .detectors import Detector
from .detectors.revolution import RevolutionDetector

# Whole-scene motion gate for adaptive idling. Subsample the frame coarsely and
# compare frame-to-frame; mean abs luminance delta over _MOTION_EPS = "moving".
_MOTION_STEP = 16  # px stride → ~30x40 samples on a 480x640 frame, near-free
_MOTION_EPS = 2.0  # 0-255; below this the scene is treated as still
_IDLE_AFTER_S = 4.0  # stay at full fps this long after the last motion


class Pipeline:
    def __init__(self, config: Config, settings: Settings) -> None:
        self.config = config
        self.settings = settings
        self.capture = Capture(config.camera)
        self.detectors: dict[str, Detector] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._state_file = settings.state_dir / "state.json"
        # adaptive idle state
        self._effective_fps = max(1, config.camera.fps)
        self._last_motion = 0.0
        self._prev_small: np.ndarray | None = None

        rev = RevolutionDetector()
        rev.configure(config.detectors.revolution)
        self.detectors[rev.name] = rev

    # --- lifecycle ---

    def start(self) -> None:
        self._load_state()
        self.capture.start()
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="ocular-pipeline", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._save_state()
        self.capture.stop()

    def _loop(self) -> None:
        last_save = 0.0
        while self._running:
            frame = self.capture.latest()
            if frame is None:
                time.sleep(0.05)
                continue
            now = time.monotonic()
            with self._lock:
                for det in self.detectors.values():
                    det.process(frame)
            self._adapt_fps(frame, now)
            if now - last_save > 10.0:
                self._save_state()
                last_save = now
            time.sleep(1.0 / self._effective_fps)

    def _adapt_fps(self, frame: np.ndarray, now: float) -> None:
        """Ramp capture fps to camera.fps on scene motion, drop to idle_fps when
        still. Cheap: a coarse subsample + frame-to-frame luminance delta."""
        active_fps = max(1, self.config.camera.fps)
        idle_fps = self.config.camera.idle_fps
        # idle_fps <= 0 (or >= active) disables idling — just hold the active rate.
        if idle_fps <= 0 or idle_fps >= active_fps:
            target = active_fps
        else:
            small = frame[::_MOTION_STEP, ::_MOTION_STEP].mean(axis=2)
            if self._prev_small is not None and small.shape == self._prev_small.shape:
                if float(np.abs(small - self._prev_small).mean()) > _MOTION_EPS:
                    self._last_motion = now
            self._prev_small = small
            target = active_fps if (now - self._last_motion) < _IDLE_AFTER_S else idle_fps
        if target != self._effective_fps:
            self._effective_fps = target
            self.capture.set_fps(target)

    @property
    def effective_fps(self) -> int:
        return self._effective_fps

    # --- reads ---

    def states(self) -> dict:
        with self._lock:
            return {name: det.state() for name, det in self.detectors.items()}

    def overlays(self) -> list[dict]:
        with self._lock:
            return [o for o in (det.overlay() for det in self.detectors.values()) if o]

    def latest_frame(self) -> np.ndarray | None:
        return self.capture.latest()

    @property
    def is_synthetic(self) -> bool:
        return self.capture.is_synthetic

    # --- live reconfigure ---

    def reconfigure_camera(self, changes: dict) -> dict:
        """Apply UI-driven camera changes (rotation, fps) and persist them.
        Both take effect immediately — rotation on the next captured frame, fps
        on the next loop tick (and via a live control change on the real camera)."""
        with self._lock:
            cam = self.config.camera
            if changes.get("rotation") is not None:
                cam.rotation = int(changes["rotation"]) % 360
                self.capture.set_rotation(cam.rotation)
            if changes.get("fps") is not None:
                cam.fps = max(1, int(changes["fps"]))
                # Treat a manual change as activity so the new rate is felt now,
                # not after the next motion event.
                self._last_motion = time.monotonic()
                self._effective_fps = cam.fps
                self.capture.set_fps(cam.fps)
            if changes.get("idle_fps") is not None:
                cam.idle_fps = max(0, int(changes["idle_fps"]))
            save_config(self.settings.config_path, self.config)
            return {"rotation": cam.rotation, "fps": cam.fps, "idle_fps": cam.idle_fps}

    def reconfigure_revolution(self, changes: dict) -> dict:
        """Apply UI-driven changes to the revolution detector and persist them."""
        with self._lock:
            cfg = self.config.detectors.revolution
            for key in ("enabled", "roi", "threshold", "min_coverage", "debounce_frames",
                        "wheel_circumference_m", "marker_is_dark"):
                if key in changes and changes[key] is not None:
                    setattr(cfg, key, changes[key])
            self.detectors["revolution"].configure(cfg)
            save_config(self.settings.config_path, self.config)
            return self.detectors["revolution"].state()

    # --- state persistence ---

    def _load_state(self) -> None:
        try:
            data = json.loads(self._state_file.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return
        rev = self.detectors.get("revolution")
        if isinstance(rev, RevolutionDetector) and "revolutions" in data:
            rev.load_count(int(data["revolutions"]))

    def _save_state(self) -> None:
        try:
            self.settings.state_dir.mkdir(parents=True, exist_ok=True)
            rev = self.detectors["revolution"].state()
            tmp = self._state_file.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"revolutions": rev["revolutions"]}))
            tmp.replace(self._state_file)
        except OSError as e:
            print(f"ocular: could not persist state: {e}")
