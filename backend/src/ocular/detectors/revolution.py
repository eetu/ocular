"""Revolution counter — ROI line-crossing on a high-contrast marker.

Watches one region the marker passes through each turn (a black tape strip on a
cat-wheel rim). Each frame: count the fraction of ROI pixels matching the marker
(darker than threshold by default); the marker is "present" when that coverage
crosses min_coverage. A revolution is counted on each present→absent edge, with
hysteresis (the state must hold for debounce_frames consecutive frames before it
flips) so a marker that dwells across several frames counts exactly once.

Coverage rather than mean brightness is what lets the ROI be a tall, thin strip
along the marker's track: the marker dwells in it for many frames (so a fast
wheel isn't aliased away between samples) without the surrounding rim diluting a
whole-ROI average below the trigger.

Pure numpy — a cropped boolean count + a small state machine. Trivially
real-time on a Pi 3 B+ at 320-640px wide.
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
        self._last_coverage = 0.0
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
        roi = gray[y0:y1, x0:x1]
        # Fraction of ROI pixels matching the marker (dark by default, light if
        # marker_is_dark is false). A per-pixel test, not a whole-ROI mean, so a
        # small tape band crossing a tall ROI still registers — the metric scales
        # with marker coverage, not with how much empty rim shares the box.
        hit = roi < self._cfg.threshold if self._cfg.marker_is_dark else roi > self._cfg.threshold
        coverage = float(hit.mean())
        self._last_coverage = coverage

        instant = coverage >= self._cfg.min_coverage

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
            "coverage": round(self._last_coverage, 3),
            "min_coverage": self._cfg.min_coverage,
        }

    def overlay(self) -> dict | None:
        return {"roi": list(self._cfg.roi), "active": self._active, "label": "revolution"}
