<!-- Big revolution counter that eases to new values (halo motion), with rpm,
     distance, and a live marker-present dot. -->
<script lang="ts">
  import { cubicOut } from "svelte/easing";
  import { Tween } from "svelte/motion";

  import type { RevolutionState } from "../api";

  let { state }: { state: RevolutionState | null } = $props();

  const eased = new Tween(0, { duration: 500, easing: cubicOut });
  $effect(() => {
    eased.target = state?.revolutions ?? 0;
  });
</script>

<div class="counter halo-card">
  <div class="big mono-num" class:active={state?.marker_present}>
    {Math.round(eased.current)}
    <span class="dot" class:on={state?.marker_present}></span>
  </div>
  <div class="label">revolutions</div>
  <div class="sub mono-num">
    <span>{state?.rpm ?? 0} rpm</span>
    {#if state?.distance_m != null}<span>{state.distance_m} m</span>{/if}
  </div>
</div>

<style>
  .counter {
    text-align: center;
  }
  .big {
    font-size: clamp(3.5rem, 18vw, 7rem);
    font-weight: 600;
    line-height: 1;
    color: var(--halo-text-main);
    position: relative;
    display: inline-block;
    transition: color var(--halo-d-fast);
  }
  .big.active {
    color: var(--halo-accent);
  }
  .dot {
    position: absolute;
    top: 0.4rem;
    right: -0.9rem;
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    background: var(--halo-off-bg);
    transition: background var(--halo-d-fast);
  }
  .dot.on {
    background: var(--halo-accent);
  }
  .label {
    font-family: var(--halo-font-heading);
    text-transform: lowercase;
    letter-spacing: 0.04em;
    color: var(--halo-text-muted);
    margin-top: 0.3rem;
  }
  .sub {
    margin-top: 0.8rem;
    display: flex;
    gap: 1.2rem;
    justify-content: center;
    color: var(--halo-text-muted);
  }
</style>
