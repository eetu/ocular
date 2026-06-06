"""Revolution counter — ROI line-crossing on a high-contrast marker.

Watches one small region the marker passes through each turn (a black tape strip
on a cat-wheel rim). Each frame: take the mean brightness inside the ROI; the
marker is "present" when that mean crosses the threshold. A revolution is counted
on each present→absent edge, with hysteresis (the state must hold for
debounce_frames consecutive frames before it flips) so a marker that dwells
across several frames at low RPM counts exactly once.

Pure numpy — a cropped mean + a small state machine. Trivially real-time on a
Pi 3 B+ at 320-640px wide.
"""

from __future__ import annotations

import time

import numpy as np

from ..config import RevolutionConfig
from . import Detector


class RevolutionDetector(Detector):
    name = "revolution"

    def __init__(self) -> None:
        self._cfg = RevolutionConfig()
        # marker-present state machine
        self._present = False
        self._candidate = False
        self._candidate_frames = 0
        # results
        self._count = 0
        self._last_cross = 0.0
        self._rpm = 0.0
        self._last_mean = 0.0
        self._active = False  # marker currently in the ROI (debounced)

    def configure(self, cfg: RevolutionConfig) -> None:
        self._cfg = cfg

    def process(self, gray: np.ndarray) -> None:
        if not self._cfg.enabled:
            return
        x, y, w, h = self._cfg.roi
        h_img, w_img = gray.shape[:2]
        # Clamp the ROI to the frame so a stale/oversized box can't IndexError.
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(w_img, x + w), min(h_img, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        mean = float(gray[y0:y1, x0:x1].mean())
        self._last_mean = mean

        # "marker present" = ROI is dark (default) or light, per marker_is_dark.
        instant = mean < self._cfg.threshold
        if not self._cfg.marker_is_dark:
            instant = mean > self._cfg.threshold

        # Debounce: only flip the committed state after N consistent frames.
        if instant != self._candidate:
            self._candidate = instant
            self._candidate_frames = 1
        else:
            self._candidate_frames += 1

        if self._candidate_frames >= self._cfg.debounce_frames and self._present != self._candidate:
            self._present = self._candidate
            self._active = self._present
            if not self._present:
                # present → absent edge = one full revolution
                now = time.monotonic()
                if self._last_cross:
                    dt = now - self._last_cross
                    if dt > 0:
                        self._rpm = 60.0 / dt
                self._last_cross = now
                self._count += 1

    def load_count(self, count: int) -> None:
        """Seed the running total from persisted state on startup."""
        self._count = count

    def state(self) -> dict:
        circ = self._cfg.wheel_circumference_m
        return {
            "revolutions": self._count,
            "rpm": round(self._rpm, 1),
            "distance_m": round(self._count * circ, 1) if circ else None,
            "marker_present": self._active,
            "roi_mean": round(self._last_mean, 1),
            "threshold": self._cfg.threshold,
        }

    def overlay(self) -> dict | None:
        return {"roi": list(self._cfg.roi), "active": self._active, "label": "revolution"}
