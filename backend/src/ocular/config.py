"""Runtime configuration.

Config comes from two layers, in order of precedence:
  1. Environment (deploy-time invariants: bind address, paths, log level).
  2. A JSON file (live-tunable detector params: ROI, threshold, fps, rotation).

The JSON file is the source of truth for everything the UI can tweak. The web
layer rewrites it (atomically) when a detector is reconfigured, so changes
survive a restart. On the Pi it is rendered from the OCULAR dict by the raspi
deploy (tasks/ocular.py) and lives at /etc/ocular/config.json; in dev it falls
back to baked-in defaults so the app runs with no config present.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

# --- Camera + capture ---------------------------------------------------------


@dataclass
class CameraConfig:
    width: int = 640
    height: int = 480
    fps: int = 15
    # 0 / 90 / 180 / 270. Default 0: a correctly-mounted case needs no rotation.
    # Set 180 for an upside-down hang. Applied to the captured frame so the feed
    # AND detector ROI coordinates read upright.
    rotation: int = 0


# --- Detectors ----------------------------------------------------------------


@dataclass
class RevolutionConfig:
    """ROI line-crossing counter for a high-contrast marker (black tape) on a
    rotating rim — e.g. a cat exercise wheel."""

    enabled: bool = True
    # Region of interest the marker passes through, in *processing* pixels
    # (i.e. after capture downscale): [x, y, w, h]. Make it a tall, thin strip
    # laid ALONG the marker's travel track: the marker then dwells inside it for
    # many frames (a wide time window, so a fast wheel isn't aliased away between
    # samples), while the coverage metric (below) keeps it from being diluted.
    roi: list[int] = field(default_factory=lambda: [280, 160, 60, 220])
    # 0-255 per-pixel brightness cutoff. A pixel counts as "marker" when it's
    # darker than this (or lighter, if marker_is_dark is false). Black tape on a
    # light rim → a low threshold like 60 works.
    threshold: int = 60
    # Fraction (0-1) of ROI pixels that must match the marker for it to count as
    # present. Decouples detection from ROI size: a short tape band crossing a
    # tall ROI still spikes coverage, where a whole-ROI *mean* would barely move.
    min_coverage: float = 0.12
    # Marker must be continuously present/absent this many frames before a state
    # flip counts — debounces a slow marker dwelling across several frames.
    debounce_frames: int = 3
    # Rim circumference, for deriving distance travelled from the revolution
    # count. Optional; 0 disables distance.
    wheel_circumference_m: float = 0.0
    # If true the marker is darker than the rim (count dark dwell). Set false if
    # you use a light/reflective marker on a dark rim.
    marker_is_dark: bool = True


@dataclass
class DetectorsConfig:
    revolution: RevolutionConfig = field(default_factory=RevolutionConfig)


# --- Top-level ----------------------------------------------------------------


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detectors: DetectorsConfig = field(default_factory=DetectorsConfig)

    # --- (de)serialization ---

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        cam = CameraConfig(**(data.get("camera") or {}))
        det_data = data.get("detectors") or {}
        rev = RevolutionConfig(**(det_data.get("revolution") or {}))
        return cls(camera=cam, detectors=DetectorsConfig(revolution=rev))

    def to_dict(self) -> dict:
        return asdict(self)


# --- Environment-level settings (not UI-tunable) ------------------------------


@dataclass
class Settings:
    bind_host: str
    bind_port: int
    static_dir: Path
    config_path: Path
    state_dir: Path

    @classmethod
    def from_env(cls) -> Settings:
        bind = os.environ.get("OCULAR_BIND", "0.0.0.0:8099")
        host, _, port = bind.partition(":")
        return cls(
            bind_host=host or "0.0.0.0",
            bind_port=int(port or "8099"),
            static_dir=Path(os.environ.get("OCULAR_STATIC_DIR", "./dist")),
            config_path=Path(os.environ.get("OCULAR_CONFIG", "/etc/ocular/config.json")),
            state_dir=Path(os.environ.get("OCULAR_STATE_DIR", "/var/lib/ocular")),
        )


def load_config(path: Path) -> Config:
    """Read the JSON config file, falling back to defaults if it's absent."""
    try:
        return Config.from_dict(json.loads(path.read_text()))
    except (FileNotFoundError, json.JSONDecodeError):
        return Config()


def save_config(path: Path, config: Config) -> None:
    """Atomically persist config so a crash mid-write can't truncate it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(config.to_dict(), indent=2))
    tmp.replace(path)
