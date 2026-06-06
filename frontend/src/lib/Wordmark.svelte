<!-- House wordmark: lowercase, accent dot. The full riff collapses to the bare
     app name on narrow screens. -->
<script lang="ts">
  let { compact = false }: { compact?: boolean } = $props();
</script>

<span class="halo-wordmark wm">
  {#if !compact}<span class="riff">a quiet eye on the </span>{/if}ocular<span
    class="accent">.</span
  >
</span>

<style>
  .wm {
    font-size: 1.1rem;
  }
  .riff {
    color: var(--halo-text-muted);
    font-weight: 400;
  }
  @media (max-width: 520px) {
    .riff {
      display: none;
    }
  }
</style>
