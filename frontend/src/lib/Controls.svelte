<!-- Detector tuning: threshold, mask preview toggle, marker polarity, debounce,
     enable. Changes apply live (parent POSTs to the backend). -->
<script lang="ts">
  import type { RevolutionConfig } from "../api";

  let {
    config,
    mask = $bindable(),
    roiMean,
    rotation,
    onchange,
    onrotate,
  }: {
    config: RevolutionConfig;
    mask: boolean;
    roiMean: number;
    rotation: number;
    onchange: (changes: Partial<RevolutionConfig>) => void;
    onrotate: (rotation: number) => void;
  } = $props();
</script>

<div class="controls halo-card">
  <div class="rotate">
    <span>orientation <em class="mono-num">{rotation}°</em></span>
    <button type="button" onclick={() => onrotate((rotation + 90) % 360)}
      >rotate 90°</button
    >
  </div>

  <label class="row">
    <span>threshold <em class="mono-num">{config.threshold}</em></span>
    <input
      type="range"
      min="0"
      max="255"
      value={config.threshold}
      oninput={(e) => onchange({ threshold: +e.currentTarget.value })}
    />
  </label>
  <div class="hint mono-num">roi mean: {roiMean}</div>

  <label class="toggle">
    <input type="checkbox" bind:checked={mask} />
    <span>show threshold mask</span>
  </label>

  <label class="toggle">
    <input
      type="checkbox"
      checked={config.marker_is_dark}
      onchange={(e) => onchange({ marker_is_dark: e.currentTarget.checked })}
    />
    <span>marker is dark</span>
  </label>

  <label class="row">
    <span>debounce <em class="mono-num">{config.debounce_frames}f</em></span>
    <input
      type="range"
      min="1"
      max="10"
      value={config.debounce_frames}
      oninput={(e) => onchange({ debounce_frames: +e.currentTarget.value })}
    />
  </label>

  <label class="toggle">
    <input
      type="checkbox"
      checked={config.enabled}
      onchange={(e) => onchange({ enabled: e.currentTarget.checked })}
    />
    <span>detector enabled</span>
  </label>
</div>

<style>
  .controls {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .row {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    font-family: var(--halo-font-heading);
    font-size: 0.85rem;
    color: var(--halo-text-muted);
    text-transform: lowercase;
  }
  .row em {
    color: var(--halo-accent);
    font-style: normal;
  }
  input[type="range"] {
    width: 100%;
    accent-color: var(--halo-accent);
    height: 1.6rem;
  }
  .toggle {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-family: var(--halo-font-heading);
    font-size: 0.85rem;
    color: var(--halo-text-muted);
    text-transform: lowercase;
    min-height: 44px;
  }
  .toggle input {
    width: 1.2rem;
    height: 1.2rem;
    accent-color: var(--halo-accent);
  }
  .hint {
    font-size: 0.75rem;
    color: var(--halo-text-light);
    margin-top: -0.4rem;
  }
  .rotate {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-family: var(--halo-font-heading);
    font-size: 0.85rem;
    color: var(--halo-text-muted);
    text-transform: lowercase;
  }
  .rotate em {
    color: var(--halo-accent);
    font-style: normal;
  }
  .rotate button {
    font-family: var(--halo-font-heading);
    text-transform: lowercase;
    font-size: 0.8rem;
    color: var(--halo-text-main);
    background: var(--halo-bg-light);
    border: 1px solid var(--halo-border);
    border-radius: var(--halo-radius-pill);
    padding: 0.5rem 0.8rem;
    min-height: 44px;
    cursor: pointer;
  }
  .rotate button:active {
    border-color: var(--halo-accent);
    color: var(--halo-accent);
  }
</style>
