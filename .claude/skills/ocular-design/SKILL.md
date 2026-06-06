---
name: ocular-design
description: Visual identity for ocular — a sibling in eetu's homebrew web app family. Layers ocular's glyph, wordmark, layout, and voice on top of the shared halo-design tokens. Use when building or styling ocular's UI.
user-invocable: true
---

# ocular-design

Shared tokens + conventions come from `halo-design` — copy `colors_and_type.css`
verbatim (already at `frontend/src/styles/colors_and_type.css`) and use the
`--halo-*` vars in Svelte `<style>` blocks. Below is ocular's delta.

## The four deltas

**Glyph** — an **eye**. 64×64, `currentColor` outline (almond + iris), the one
hardcoded color a warm `#f78f08` pupil (the family "warm centre"). Source:
`frontend/public/favicon.svg`. Stroke ~3 (almond) / ~2.5 (iris), round caps.

**Wordmark** — `ocular` + accent period. Full riff: *"a quiet eye on the
ocular."* collapsing to bare `ocular.` under ~520px (see
`frontend/src/lib/Wordmark.svelte`). Lowercase, Inter 600, `-0.04em`.

**Layout / density** — single-screen, **mobile-first** (the primary use is an
iPhone held at the cat wheel). Vertical stack, max-width 560px, centered:
live feed → big counter → tuning controls. Touch targets ≥44px; sliders full
width. The live feed is full-bleed with a draggable ROI box drawn right on it.

**Voice** — terse, numbers-do-the-talking. Lowercase labels in Space Grotesk.
No marketing tone, no emoji. The big revolution count is the hero; rpm/distance
are quiet subtitles. Empty/:connecting states get one quiet line.

## Differences from halo / chat / scribe

| | ocular |
|---|---|
| Stack | **Python** (FastAPI) backend + **Svelte** SPA (first Svelte app in the family) |
| Glyph | eye + warm pupil |
| Hero element | a single large eased numeral (revolution count) |
| Accent use | ROI box + marker-present dot light up `--halo-accent` when active |

## Source-of-truth files

- `frontend/src/styles/colors_and_type.css` — canonical tokens (verbatim copy).
- `frontend/src/lib/Wordmark.svelte` — brand.
- `frontend/src/lib/{Counter,Controls,LiveView}.svelte` — the screen.
- `frontend/public/favicon.svg` — the glyph.
