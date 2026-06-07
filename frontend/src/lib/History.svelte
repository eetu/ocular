<!-- Revolution history: today's rollups, a per-bucket distance/revs bar chart, an
     rpm trend sparkline, and the list of activity sessions (wheel-in-use runs).
     Dependency-free charts (CSS bars + inline SVG) — no chart library. -->
<script lang="ts">
  import { api, type HistoryBucket, type Session, type Stats } from "../api";

  type Range = { label: string; hours: number; bucket: "hour" | "day" };
  const RANGES: Range[] = [
    { label: "24h", hours: 24, bucket: "hour" },
    { label: "7d", hours: 168, bucket: "day" },
  ];

  let range = $state<Range>(RANGES[0]);
  let stats = $state<Stats | null>(null);
  let buckets = $state<HistoryBucket[]>([]);
  let sessions = $state<Session[]>([]);
  let error = $state<string | null>(null);

  // Chart against distance when a circumference is configured, else raw revs.
  const useDistance = $derived(buckets.some((b) => b.distance_m != null));
  const barValue = (b: HistoryBucket): number =>
    useDistance ? (b.distance_m ?? 0) : b.revs;
  const maxBar = $derived(Math.max(1, ...buckets.map(barValue)));
  const maxRpm = $derived(Math.max(1, ...buckets.map((b) => b.peak_rpm)));

  // rpm trend as an SVG polyline over a 100x32 viewBox.
  const spark = $derived(
    buckets.length < 2
      ? ""
      : buckets
          .map((b, i) => {
            const x = (i / (buckets.length - 1)) * 100;
            const y = 32 - (b.avg_rpm / maxRpm) * 32;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
          })
          .join(" "),
  );

  function load(r: Range): void {
    Promise.all([
      api.stats(),
      api.history(r.hours, r.bucket),
      api.sessions(r.hours),
    ])
      .then(([s, h, ss]) => {
        stats = s;
        buckets = h.buckets;
        sessions = ss.sessions;
        error = null;
      })
      .catch((e) => (error = String(e)));
  }

  $effect(() => {
    const r = range;
    load(r);
    const poll = setInterval(() => load(r), 15_000);
    return () => clearInterval(poll);
  });

  function fmtBucket(t: number): string {
    const d = new Date(t * 1000);
    return range.bucket === "hour"
      ? d.toLocaleTimeString([], { hour: "2-digit" })
      : d.toLocaleDateString([], { weekday: "short" });
  }
  function fmtClock(ts: number): string {
    return new Date(ts * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  function fmtDur(s: number): string {
    const m = Math.floor(s / 60);
    const sec = Math.round(s % 60);
    return m ? `${m}m ${sec}s` : `${sec}s`;
  }
  function fmtDist(m: number | null): string {
    if (m == null) return "—";
    return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${m} m`;
  }
</script>

<div class="history">
  {#if error}<div class="err">{error}</div>{/if}

  <div class="ranges">
    {#each RANGES as r (r.label)}
      <button
        type="button"
        class:active={range.label === r.label}
        onclick={() => (range = r)}>{r.label}</button
      >
    {/each}
  </div>

  {#if stats}
    <div class="stats">
      <div class="stat halo-card">
        <div class="val mono-num">
          {stats.today_distance_m != null
            ? fmtDist(stats.today_distance_m)
            : stats.today_revolutions}
        </div>
        <div class="cap">
          {stats.today_distance_m != null ? "today" : "revs today"}
        </div>
      </div>
      <div class="stat halo-card">
        <div class="val mono-num">
          {stats.today_active_min}<small>min</small>
        </div>
        <div class="cap">active today</div>
      </div>
      <div class="stat halo-card">
        <div class="val mono-num">{stats.avg_active_rpm}<small>rpm</small></div>
        <div class="cap">avg today</div>
      </div>
      <div class="stat halo-card">
        <div class="val mono-num">{stats.lifetime_revolutions}</div>
        <div class="cap">lifetime revs</div>
      </div>
    </div>
  {/if}

  <div class="chart halo-card">
    <div class="chart-title">
      {useDistance ? "distance" : "revolutions"} per {range.bucket}
    </div>
    {#if buckets.length}
      <div class="bars">
        {#each buckets as b (b.t)}
          <div class="bar-col" title={`${b.revs} revs · ${b.avg_rpm} avg rpm`}>
            <div
              class="bar"
              style="height: {(barValue(b) / maxBar) * 100}%"
            ></div>
            <div class="bar-lab">{fmtBucket(b.t)}</div>
          </div>
        {/each}
      </div>
      {#if spark}
        <div class="spark-wrap">
          <svg viewBox="0 0 100 32" preserveAspectRatio="none" class="spark">
            <polyline points={spark} />
          </svg>
          <span class="spark-lab">avg rpm trend</span>
        </div>
      {/if}
    {:else}
      <div class="empty">no activity in this range</div>
    {/if}
  </div>

  <div class="sessions halo-card">
    <div class="chart-title">sessions</div>
    {#if sessions.length}
      {#each [...sessions].reverse() as s (s.start)}
        <div class="session">
          <div class="when mono-num">{fmtClock(s.start)}–{fmtClock(s.end)}</div>
          <div class="metrics mono-num">
            <span>{fmtDur(s.duration_s)}</span>
            <span
              >{s.distance_m != null
                ? fmtDist(s.distance_m)
                : `${s.revs} rev`}</span
            >
            <span>{s.avg_rpm}/{s.peak_rpm} rpm</span>
          </div>
        </div>
      {/each}
    {:else}
      <div class="empty">no sessions yet</div>
    {/if}
  </div>
</div>

<style>
  .history {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .err {
    color: var(--halo-error);
    font-size: 0.85rem;
  }
  .ranges {
    display: flex;
    gap: 0.3rem;
    justify-content: flex-end;
  }
  .ranges button {
    font-family: var(--halo-font-heading);
    font-size: 0.8rem;
    min-width: 44px;
    min-height: 44px;
    color: var(--halo-text-main);
    background: var(--halo-bg-light);
    border: 1px solid var(--halo-border);
    border-radius: var(--halo-radius-pill);
    cursor: pointer;
  }
  .ranges button.active {
    border-color: var(--halo-accent);
    color: var(--halo-accent);
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.6rem;
  }
  .stat {
    text-align: center;
    padding: 1rem;
  }
  .stat .val {
    font-size: 1.6rem;
    font-weight: 600;
    color: var(--halo-text-main);
  }
  .stat .val small {
    font-size: 0.7rem;
    color: var(--halo-text-muted);
    margin-left: 0.15rem;
  }
  .stat .cap {
    font-family: var(--halo-font-heading);
    text-transform: lowercase;
    font-size: 0.72rem;
    letter-spacing: 0.04em;
    color: var(--halo-text-muted);
    margin-top: 0.2rem;
  }
  .chart-title {
    font-family: var(--halo-font-heading);
    text-transform: lowercase;
    font-size: 0.85rem;
    color: var(--halo-text-muted);
    margin-bottom: 0.8rem;
  }
  .bars {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 120px;
  }
  .bar-col {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    height: 100%;
    min-width: 0;
  }
  .bar {
    width: 100%;
    max-width: 1.4rem;
    min-height: 2px;
    background: var(--halo-accent);
    border-radius: var(--halo-radius-pill) var(--halo-radius-pill) 0 0;
    transition: height var(--halo-d-med);
  }
  .bar-lab {
    font-family: var(--halo-font-heading);
    font-size: 0.6rem;
    color: var(--halo-text-muted);
    margin-top: 0.3rem;
    white-space: nowrap;
    overflow: hidden;
  }
  .spark-wrap {
    margin-top: 1rem;
  }
  .spark {
    width: 100%;
    height: 32px;
    display: block;
  }
  .spark polyline {
    fill: none;
    stroke: var(--halo-accent);
    stroke-width: 1;
    vector-effect: non-scaling-stroke;
    opacity: 0.7;
  }
  .spark-lab {
    font-family: var(--halo-font-heading);
    font-size: 0.7rem;
    color: var(--halo-text-muted);
  }
  .session {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.6rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--halo-border);
    font-size: 0.8rem;
  }
  .session:first-of-type {
    border-top: none;
  }
  .when {
    color: var(--halo-text-main);
  }
  .metrics {
    display: flex;
    gap: 0.7rem;
    color: var(--halo-text-muted);
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .empty {
    color: var(--halo-text-muted);
    font-size: 0.85rem;
    text-align: center;
    padding: 1rem 0;
  }
</style>
