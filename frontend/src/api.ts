// Thin typed wrapper over the backend JSON API. Types are hand-written to match
// the backend's dataclasses (no codegen) — the house contract.

export type RevolutionState = {
  revolutions: number;
  rpm: number;
  distance_m: number | null;
  marker_present: boolean;
  coverage: number;
  min_coverage: number;
  threshold: number;
};

export type StateResponse = {
  synthetic: boolean;
  viewers: number;
  capture_fps: number;
  blind: boolean;
  detectors: { revolution?: RevolutionState };
};

export type RevolutionConfig = {
  enabled: boolean;
  roi: [number, number, number, number];
  threshold: number;
  auto_threshold: boolean;
  min_coverage: number;
  debounce_frames: number;
  wheel_circumference_m: number;
  marker_is_dark: boolean;
};

export type ConfigResponse = {
  camera: { width: number; height: number; fps: number; rotation: number };
  detectors: { revolution: RevolutionConfig };
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  state: () => fetch("/api/state").then((r) => json<StateResponse>(r)),
  config: () => fetch("/api/config").then((r) => json<ConfigResponse>(r)),
  setRevolution: (changes: Partial<RevolutionConfig>) =>
    fetch("/api/detectors/revolution/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }).then((r) => json<RevolutionState>(r)),
  setCamera: (changes: Partial<{ rotation: number; fps: number }>) =>
    fetch("/api/camera/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }).then((r) => json<{ rotation: number; fps: number }>(r)),
};
