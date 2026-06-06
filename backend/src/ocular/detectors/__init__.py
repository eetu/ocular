"""Detector plugin API.

A detector consumes frames and emits a small JSON-able state dict. The pipeline
feeds every enabled detector the same raw frame each tick; a detector grayscales
only the region it cares about (its ROI), so the hot path never pays for a
full-frame conversion. Detectors are deliberately cheap and stateful (they hold
their own counters / history).

Add a detector by subclassing Detector and registering it in REGISTRY. The
revolution counter is the first; motion / face / object are the planned next
ones (see README). Keeping the contract this small is what lets a heavier
detector later run on better hardware without touching the pipeline.
"""

from __future__ import annotations

import numpy as np


class Detector:
    #: stable key used in config + the /api/state payload
    name: str = "detector"

    def configure(self, cfg: object) -> None:
        """Apply a (possibly live-updated) config dataclass."""

    def process(self, frame: np.ndarray) -> None:
        """Consume one raw frame (HxWx3 uint8). Grayscale only what you need
        (e.g. the ROI) and update internal state."""
        raise NotImplementedError

    def state(self) -> dict:
        """Return the current JSON-able state for the API."""
        return {}

    def overlay(self) -> dict | None:
        """Optional drawing hint for the stream overlay, e.g.
        {"roi": [x, y, w, h], "active": bool}. None = nothing to draw."""
        return None


from .revolution import RevolutionDetector  # noqa: E402  (after Detector is defined)

REGISTRY: dict[str, type[Detector]] = {
    RevolutionDetector.name: RevolutionDetector,
}
