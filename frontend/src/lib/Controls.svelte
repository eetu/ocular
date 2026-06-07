<!-- Detector tuning: orientation, capture fps, threshold, coverage trigger, mask
     preview, marker polarity, debounce, enable — each with an inline hint and a
     "how it works" disclosure. Changes apply live (parent POSTs to the backend). -->
<script lang="ts">
  import RotateCw from "@lucide/svelte/icons/rotate-cw";

  import type { RevolutionConfig } from "../api";

  let {
    config,
    mask = $bindable(),
    coverage,
    liveThreshold,
    rotation,
    fps,
    onchange,
    onrotate,
    onfps,
    onreset,
  }: {
    config: RevolutionConfig;
    mask: boolean;
    coverage: number;
    liveThreshold: number;
    rotation: number;
    fps: number;
    onchange: (changes: Partial<RevolutionConfig>) => void;
    onrotate: (rotation: number) => void;
    onfps: (fps: number) => void;
    onreset: () => void;
  } = $props();

  const FPS_OPTIONS = [15, 20, 30];

  // Reset is two-step: first tap arms it, second within 4s confirms.
  let resetArmed = $state(false);
  let resetTimer: ReturnType<typeof setTimeout>;
  function clickReset() {
    if (!resetArmed) {
      resetArmed = true;
      resetTimer = setTimeout(() => (resetArmed = false), 4000);
      return;
    }
    clearTimeout(resetTimer);
    resetArmed = false;
    onreset();
  }
</script>

<div class="controls halo-card">
  <details class="help">
    <summary>how it works</summary>
    <p>
      The counter watches one region (the orange box) and ticks once each time
      the high-contrast marker — black tape on the rim — sweeps through it. Aim:
      turn on <em>mask</em>, place the box on the marker's track, and tune so
      the box reads mostly rim normally and floods with marker pixels as the
      tape passes.
    </p>
  </details>

  <div class="rotate">
    <span>orientation <em class="mono-num">{rotation}°</em></span>
    <button
      type="button"
      class="icon-btn"
      aria-label="rotate 90°"
      title="rotate 90°"
      onclick={() => onrotate((rotation + 90) % 360)}
    >
      <RotateCw size={18} aria-hidden="true" />
    </button>
  </div>
  <div class="hint">Rotate the feed upright. The ROI rotates with it.</div>

  <div class="rotate">
    <span>capture fps</span>
    <div class="segmented">
      {#each FPS_OPTIONS as opt (opt)}
        <button
          type="button"
          class:active={fps === opt}
          onclick={() => onfps(opt)}>{opt}</button
        >
      {/each}
    </div>
  </div>
  <div class="hint">
    Detection sample rate — raise it for a fast wheel so the marker isn't missed
    between frames. The preview is capped at 12 fps to spare the Pi.
  </div>

  <label class="toggle">
    <input
      type="checkbox"
      checked={config.auto_threshold}
      onchange={(e) => onchange({ auto_threshold: e.currentTarget.checked })}
    />
    <span>auto threshold (adapt to light)</span>
  </label>
  <div class="hint">
    Picks the marker/rim cutoff from the image itself each frame, so it keeps
    working as light changes (dusk). Off = use the fixed value below. Either way
    counting pauses when it's too dark to see the marker.
  </div>

  {#if config.auto_threshold}
    <label class="row">
      <span>auto max <em class="mono-num">{config.auto_threshold_max}</em></span
      >
      <input
        type="range"
        min="0"
        max="255"
        value={config.auto_threshold_max}
        oninput={(e) =>
          onchange({ auto_threshold_max: +e.currentTarget.value })}
      />
    </label>
    <div class="hint">
      Ceiling on the auto cutoff. A busy scene (spokes, a grate) can push auto
      so high the rim counts as marker and every spoke fakes a turn — cap it
      (~60 for dark tape) so auto can adapt down for dusk but never run away
      upward.
    </div>
  {/if}

  <label class="row">
    <span
      >threshold {config.auto_threshold ? "(auto)" : ""}
      <em class="mono-num"
        >{config.auto_threshold ? liveThreshold : config.threshold}</em
      ></span
    >
    <input
      type="range"
      min="0"
      max="255"
      disabled={config.auto_threshold}
      value={config.threshold}
      oninput={(e) => onchange({ threshold: +e.currentTarget.value })}
    />
  </label>
  <div class="hint">
    Brightness cutoff (0–255). Pixels darker than this count as marker — in mask
    view they turn black. Black tape on a light rim → keep it low (~60). When
    auto is on this tracks live; the slider is the manual fallback.
  </div>

  <label class="row">
    <span
      >coverage trigger
      <em class="mono-num">{Math.round(config.min_coverage * 100)}%</em></span
    >
    <input
      type="range"
      min="1"
      max="100"
      value={Math.round(config.min_coverage * 100)}
      oninput={(e) => onchange({ min_coverage: +e.currentTarget.value / 100 })}
    />
  </label>
  <div class="hint mono-num">
    coverage now: {Math.round(coverage * 100)}% (fires ≥ {Math.round(
      config.min_coverage * 100,
    )}%)
  </div>
  <div class="hint">
    How much of the box must be marker pixels to count as present. Set it
    between the empty-box and tape-passing readings above. Raise it if noise
    triggers.
  </div>

  <label class="toggle">
    <input type="checkbox" bind:checked={mask} />
    <span>show threshold mask</span>
  </label>
  <div class="hint">
    Shows exactly what the detector sees: black = marker pixels, white = rim.
    Use it to aim and size the box.
  </div>

  <label class="toggle">
    <input
      type="checkbox"
      checked={config.marker_is_dark}
      onchange={(e) => onchange({ marker_is_dark: e.currentTarget.checked })}
    />
    <span>marker is dark</span>
  </label>
  <div class="hint">
    On: dark tape on a light rim (default). Off: a light/reflective marker on a
    dark rim.
  </div>

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
  <div class="hint">
    Frames the marker must stay present (or absent) before the state flips.
    Higher rejects noise but can miss very fast passes; lower is twitchier.
  </div>

  <label class="toggle">
    <input
      type="checkbox"
      checked={config.enabled}
      onchange={(e) => onchange({ enabled: e.currentTarget.checked })}
    />
    <span>detector enabled</span>
  </label>

  <button
    type="button"
    class="reset"
    class:armed={resetArmed}
    onclick={clickReset}
  >
    {resetArmed ? "tap again to confirm reset" : "reset count"}
  </button>
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
    color: var(--halo-text-main);
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
  input[type="range"]:disabled {
    opacity: 0.4;
  }
  .toggle {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-family: var(--halo-font-heading);
    font-size: 0.85rem;
    color: var(--halo-text-main);
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
    line-height: 1.35;
    color: var(--halo-text-muted);
    margin-top: -0.6rem;
  }
  .help {
    font-family: var(--halo-font-heading);
    font-size: 0.8rem;
    color: var(--halo-text-muted);
  }
  .help summary {
    cursor: pointer;
    text-transform: lowercase;
    color: var(--halo-accent);
    min-height: 44px;
    display: flex;
    align-items: center;
  }
  .help p {
    margin: 0.2rem 0 0;
    line-height: 1.5;
    color: var(--halo-text-muted);
    text-transform: none;
  }
  .help em {
    color: var(--halo-accent);
    font-style: normal;
  }
  .segmented {
    display: flex;
    gap: 0.3rem;
  }
  .segmented button {
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
  .segmented button.active {
    border-color: var(--halo-accent);
    color: var(--halo-accent);
  }
  .reset {
    font-family: var(--halo-font-heading);
    text-transform: lowercase;
    font-size: 0.8rem;
    color: var(--halo-text-muted);
    background: transparent;
    border: 1px solid var(--halo-border);
    border-radius: var(--halo-radius-pill);
    padding: 0.6rem 1rem;
    min-height: 44px;
    cursor: pointer;
  }
  .reset.armed {
    color: var(--halo-error);
    border-color: var(--halo-error);
  }
  .rotate {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-family: var(--halo-font-heading);
    font-size: 0.85rem;
    color: var(--halo-text-main);
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
  /* Icon-only variant: square, centered glyph (currentColor inherits the
     button's text colour, so :active still tints it accent). */
  .rotate button.icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 44px;
    padding: 0.5rem;
  }
</style>
