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

  const rev = $derived(live?.detectors.revolution ?? null);

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
</script>

<header>
  <Wordmark />
  {#if live?.synthetic}<span class="badge">synthetic</span>{/if}
</header>

<main>
  {#if error}<div class="error halo-card">{error}</div>{/if}

  {#if config}
    <LiveView
      roi={config.detectors.revolution.roi}
      procWidth={config.camera.width}
      procHeight={config.camera.height}
      {mask}
      onchange={(roi) => applyRevolution({ roi })}
    />
    <Counter state={rev} />
    <Controls
      config={config.detectors.revolution}
      bind:mask
      roiMean={rev?.roi_mean ?? 0}
      rotation={config.camera.rotation}
      onchange={applyRevolution}
      onrotate={applyRotation}
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
  main {
    max-width: 560px;
    margin: 0 auto;
    padding: 0.5rem 1.2rem 2rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .error {
    color: var(--halo-error);
    font-size: 0.9rem;
  }
  .loading {
    text-align: center;
    color: var(--halo-text-muted);
    padding: 3rem 0;
    font-family: var(--halo-font-heading);
  }
</style>
