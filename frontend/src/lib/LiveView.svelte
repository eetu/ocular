<!-- Live MJPEG feed with a draggable + resizable ROI rectangle overlaid in
     processing-pixel space. Built for touch: drag the box to move, drag the
     corner handle to resize. Changes are debounced and emitted to the parent,
     which POSTs them to the backend (live reconfigure). -->
<script lang="ts">
  let {
    roi,
    procWidth,
    procHeight,
    mask,
    onchange,
  }: {
    roi: [number, number, number, number];
    procWidth: number;
    procHeight: number;
    mask: boolean;
    onchange: (roi: [number, number, number, number]) => void;
  } = $props();

  // Local working copy so we can drag without mutating the prop; re-sync from
  // the prop only while not dragging (avoids fighting the parent's updates).
  let box = $state<[number, number, number, number]>([0, 0, 0, 0]);
  $effect(() => {
    if (!drag) box = [...roi];
  });

  let dispW = $state(0);
  const scale = $derived(dispW > 0 && procWidth > 0 ? dispW / procWidth : 1);
  const streamSrc = $derived(mask ? "/stream.mjpg?mask=1" : "/stream.mjpg");

  type Drag = {
    mode: "move" | "resize";
    sx: number;
    sy: number;
    o: [number, number, number, number];
  };
  let drag: Drag | null = null;
  let emitTimer: ReturnType<typeof setTimeout>;

  const clamp = (v: number, lo: number, hi: number) =>
    Math.max(lo, Math.min(hi, v));

  function emit() {
    clearTimeout(emitTimer);
    emitTimer = setTimeout(() => onchange(box), 150);
  }

  function start(mode: "move" | "resize", e: PointerEvent) {
    e.preventDefault();
    e.stopPropagation();
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    drag = { mode, sx: e.clientX, sy: e.clientY, o: [...box] };
  }

  function move(e: PointerEvent) {
    if (!drag) return;
    const dx = (e.clientX - drag.sx) / scale;
    const dy = (e.clientY - drag.sy) / scale;
    const [ox, oy, ow, oh] = drag.o;
    if (drag.mode === "move") {
      box = [
        Math.round(clamp(ox + dx, 0, procWidth - ow)),
        Math.round(clamp(oy + dy, 0, procHeight - oh)),
        ow,
        oh,
      ];
    } else {
      box = [
        ox,
        oy,
        Math.round(clamp(ow + dx, 16, procWidth - ox)),
        Math.round(clamp(oh + dy, 16, procHeight - oy)),
      ];
    }
    emit();
  }

  function end() {
    if (!drag) return;
    drag = null;
    clearTimeout(emitTimer);
    onchange(box);
  }
</script>

<div class="wrap">
  <img
    class="feed"
    src={streamSrc}
    alt="camera feed"
    bind:clientWidth={dispW}
  />
  <div
    class="roi"
    role="application"
    aria-label="region of interest"
    style="left:{box[0] * scale}px; top:{box[1] * scale}px; width:{box[2] *
      scale}px; height:{box[3] * scale}px;"
    onpointerdown={(e) => start("move", e)}
    onpointermove={move}
    onpointerup={end}
    onpointercancel={end}
  >
    <div
      class="handle"
      role="button"
      aria-label="resize region"
      tabindex="-1"
      onpointerdown={(e) => start("resize", e)}
    ></div>
  </div>
</div>

<style>
  .wrap {
    position: relative;
    width: 100%;
    border-radius: var(--halo-radius);
    overflow: hidden;
    background: #000;
    line-height: 0;
    touch-action: none;
  }
  .feed {
    width: 100%;
    height: auto;
    display: block;
  }
  .roi {
    position: absolute;
    border: 2px solid var(--halo-accent);
    background: var(--halo-accent-soft);
    box-sizing: border-box;
    cursor: move;
    touch-action: none;
  }
  .handle {
    position: absolute;
    right: -11px;
    bottom: -11px;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--halo-accent);
    border: 2px solid var(--halo-bg-main);
    touch-action: none;
  }
</style>
