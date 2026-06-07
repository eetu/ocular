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

export type HistoryBucket = {
  t: number; // bucket start, epoch seconds
  revs: number;
  avg_rpm: number;
  peak_rpm: number;
  distance_m: number | null;
};

export type HistoryResponse = { buckets: HistoryBucket[]; bucket_s: number };

export type Session = {
  start: number;
  end: number;
  revs: number;
  duration_s: number;
  avg_rpm: number;
  peak_rpm: number;
  distance_m: number | null;
};

export type Stats = {
  lifetime_revolutions: number;
  displayed: number;
  today_revolutions: number;
  avg_active_rpm: number;
  today_distance_m: number | null;
  today_active_min: number;
  first_ts: number | null;
  last_ts: number | null;
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
  resetRevolution: () =>
    fetch("/api/detectors/revolution/reset", { method: "POST" }).then((r) =>
      json<RevolutionState>(r),
    ),
  setCamera: (changes: Partial<{ rotation: number; fps: number }>) =>
    fetch("/api/camera/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }).then((r) => json<{ rotation: number; fps: number }>(r)),
  stats: () => fetch("/api/stats").then((r) => json<Stats>(r)),
  history: (hours: number, bucket: "hour" | "day") =>
    fetch(`/api/history?hours=${hours}&bucket=${bucket}`).then((r) =>
      json<HistoryResponse>(r),
    ),
  sessions: (hours: number, gap = 30) =>
    fetch(`/api/sessions?hours=${hours}&gap=${gap}`).then((r) =>
      json<{ sessions: Session[] }>(r),
    ),
};
