<script lang="ts">
  import {
    api,
    type ConfigResponse,
    type RevolutionConfig,
    type StateResponse,
  } from "./api";
  import Controls from "./lib/Controls.svelte";
  import Counter from "./lib/Counter.svelte";
  import LiveView from "./lib/LiveView.svelte";
  import Wordmark from "./lib/Wordmark.svelte";

  let config = $state<ConfigResponse | null>(null);
  let live = $state<StateResponse | null>(null);
  let mask = $state(false);
  let error = $state<string | null>(null);
  // Preview is opt-in: the live MJPEG stream is the expensive part, and most of
  // the time you only want the count (cheap /api/state poll). Off → no stream
  // connection → the backend encoder stays idle.
  let showPreview = $state(false);
  // Auto-stop: once shown, the preview turns itself back off after the scene has
  // been still a while (capture_fps drops below the configured rate when there's
  // no motion), so a forgotten-open tab doesn't keep streaming.
  const AUTO_STOP_MS = 60_000;
  let lastActiveMs = 0;

  function togglePreview() {
    showPreview = !showPreview;
    if (showPreview) lastActiveMs = Date.now();
  }

  const rev = $derived(live?.detectors.revolution ?? null);

  // A 90°/270° rotation swaps the frame's width/height (np.rot90 on the backend),
  // so the stream — and the ROI coordinate space the backend draws + detects in —
  // is portrait. The overlay must scale against those effective dims, not the raw
  // camera dims, or the orange box and the real detection region drift apart.
  const rotated = $derived((config?.camera.rotation ?? 0) % 180 !== 0);
  const procWidth = $derived(
    (rotated ? config?.camera.height : config?.camera.width) ?? 0,
  );
  const procHeight = $derived(
    (rotated ? config?.camera.width : config?.camera.height) ?? 0,
  );

  $effect(() => {
    api
      .config()
      .then((c) => (config = c))
      .catch((e) => (error = String(e)));

    const poll = setInterval(() => {
      api
        .state()
        .then((s) => {
          live = s;
          error = null;
          // Scene is "active" when capture hasn't idled below the configured fps.
          if (showPreview && config) {
            if (s.capture_fps >= config.camera.fps) lastActiveMs = Date.now();
            else if (Date.now() - lastActiveMs > AUTO_STOP_MS)
              showPreview = false;
          }
        })
        .catch((e) => (error = String(e)));
    }, 1000);
    return () => clearInterval(poll);
  });

  // Apply a detector change locally (so the UI stays snappy) and persist it.
  function applyRevolution(changes: Partial<RevolutionConfig>) {
    if (config)
      config.detectors.revolution = {
        ...config.detectors.revolution,
        ...changes,
      };
    api.setRevolution(changes).catch((e) => (error = String(e)));
  }

  function applyRotation(rotation: number) {
    if (config) config.camera.rotation = rotation;
    api.setCamera({ rotation }).catch((e) => (error = String(e)));
  }

  function applyFps(fps: number) {
    if (config) config.camera.fps = fps;
    api.setCamera({ fps }).catch((e) => (error = String(e)));
  }
</script>

<header>
  <Wordmark />
  {#if live?.synthetic}<span class="badge">synthetic</span>{/if}
  {#if live}<span class="badge viewers" title="connected stream viewers"
      >{live.viewers} watching</span
    >{/if}
  {#if live}<span
      class="badge viewers"
      title="live capture rate (drops when the wheel is still)"
      >{live.capture_fps} fps</span
    >{/if}
  {#if live?.blind}<span
      class="badge blind"
      title="too dark to see the marker — counting paused until there's light"
      >camera dark — paused</span
    >{/if}
</header>

<!-- Fixed toast: overlays, never reflows the content beneath it. -->
{#if error}<div class="error halo-card" role="alert">{error}</div>{/if}

<main>
  {#if config}
    <div class="preview-bar">
      <span>live preview</span>
      <button type="button" class="preview-toggle" onclick={togglePreview}>
        {showPreview ? "stop" : "show"}
      </button>
    </div>
    {#if showPreview}
      <LiveView
        roi={config.detectors.revolution.roi}
        {procWidth}
        {procHeight}
        {mask}
        onchange={(roi) => applyRevolution({ roi })}
      />
    {:else}
      <button
        type="button"
        class="preview-off halo-card"
        onclick={togglePreview}
      >
        preview off — counting continues. tap to show.
      </button>
    {/if}
    <Counter state={rev} />
    <Controls
      config={config.detectors.revolution}
      bind:mask
      coverage={rev?.coverage ?? 0}
      liveThreshold={rev?.threshold ?? config.detectors.revolution.threshold}
      rotation={config.camera.rotation}
      fps={config.camera.fps}
      onchange={applyRevolution}
      onrotate={applyRotation}
      onfps={applyFps}
    />
  {:else if !error}
    <div class="loading">connecting…</div>
  {/if}
</main>

<style>
  header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 1rem 1.2rem 0.5rem;
    max-width: 560px;
    margin: 0 auto;
  }
  .badge {
    font-family: var(--halo-font-heading);
    font-size: 0.7rem;
    text-transform: lowercase;
    color: var(--halo-accent);
    border: 1px solid var(--halo-accent);
    border-radius: var(--halo-radius-pill);
    padding: 0.1rem 0.4rem;
  }
  .badge.viewers {
    color: var(--halo-text-muted);
    border-color: var(--halo-border);
  }
  .badge.blind {
    color: var(--halo-error);
    border-color: var(--halo-error);
  }
  main {
    max-width: 560px;
    margin: 0 auto;
    padding: 0.5rem 1.2rem 2rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .error {
    position: fixed;
    top: 0.75rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;
    max-width: min(520px, calc(100vw - 2rem));
    color: var(--halo-error);
    font-size: 0.85rem;
    box-shadow: var(--halo-shadow, 0 4px 16px rgb(0 0 0 / 0.25));
    pointer-events: none;
  }
  .loading {
    text-align: center;
    color: var(--halo-text-muted);
    padding: 3rem 0;
    font-family: var(--halo-font-heading);
  }
  .preview-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-family: var(--halo-font-heading);
    font-size: 0.85rem;
    color: var(--halo-text-main);
    text-transform: lowercase;
    margin-bottom: -0.4rem;
  }
  .preview-toggle {
    font-family: var(--halo-font-heading);
    text-transform: lowercase;
    font-size: 0.8rem;
    color: var(--halo-text-main);
    background: var(--halo-bg-light);
    border: 1px solid var(--halo-border);
    border-radius: var(--halo-radius-pill);
    padding: 0.5rem 1.1rem;
    min-height: 44px;
    cursor: pointer;
  }
  .preview-toggle:active {
    border-color: var(--halo-accent);
    color: var(--halo-accent);
  }
  .preview-off {
    width: 100%;
    text-align: center;
    padding: 1.6rem 1rem;
    font-family: var(--halo-font-heading);
    font-size: 0.85rem;
    text-transform: lowercase;
    color: var(--halo-text-muted);
    border: 1px dashed var(--halo-border);
    cursor: pointer;
  }
  .preview-off:active {
    border-color: var(--halo-accent);
    color: var(--halo-accent);
  }
</style>
