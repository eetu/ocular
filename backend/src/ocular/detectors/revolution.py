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


def _otsu(gray: np.ndarray) -> int:
    """Otsu's threshold: the 0-255 cut that best splits the ROI into two classes
    (dark marker vs light rim) by maximising between-class variance. Tracks the
    split as overall light changes, so dusk doesn't need a manual re-tune.
    Vectorised over the 256-bin histogram — cheap on a small ROI."""
    hist = np.bincount(gray.ravel(), minlength=256)[:256].astype(np.float64)
    w = hist.cumsum()  # cumulative pixel count below each level
    if w[-1] == 0:
        return 128
    levels = np.arange(256, dtype=np.float64)
    s = (hist * levels).cumsum()
    total, sum_t = w[-1], s[-1]
    wf = total - w
    with np.errstate(invalid="ignore", divide="ignore"):
        mb = s / w
        mf = (sum_t - s) / wf
        between = w * wf * (mb - mf) ** 2
    between[~np.isfinite(between)] = 0.0
    return int(between.argmax())


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
        self._last_threshold = 0
        self._active = False  # marker currently in the ROI (debounced)

    def configure(self, cfg: RevolutionConfig) -> None:
        self._cfg = cfg

    def process(self, frame: np.ndarray) -> None:
        if not self._cfg.enabled:
            return
        x, y, w, h = self._cfg.roi
        h_img, w_img = frame.shape[:2]
        # Clamp the ROI to the frame so a stale/oversized box can't IndexError.
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(w_img, x + w), min(h_img, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        # Grayscale ONLY the ROI (channel-mean luminance) — never the whole
        # frame. Order-agnostic, so picamera2's BGR-vs-RGB quirk doesn't matter.
        gray_roi = frame[y0:y1, x0:x1].mean(axis=2).astype(np.uint8)
        # Auto-threshold (Otsu) tracks the marker/rim split as light changes;
        # else use the fixed cutoff.
        thr = _otsu(gray_roi) if self._cfg.auto_threshold else self._cfg.threshold
        self._last_threshold = thr
        # Fraction of ROI pixels matching the marker (dark by default, light if
        # marker_is_dark is false). A per-pixel test, not a whole-ROI mean, so a
        # small tape band crossing a tall ROI still registers — the metric scales
        # with marker coverage, not with how much empty rim shares the box.
        # Otsu's convention: class 0 (the marker, when dark) is value <= thr.
        hit = gray_roi <= thr if self._cfg.marker_is_dark else gray_roi > thr
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
            "threshold": self._last_threshold,
        }

    def overlay(self) -> dict | None:
        return {"roi": list(self._cfg.roi), "active": self._active, "label": "revolution"}
