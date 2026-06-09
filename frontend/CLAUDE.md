# Frontend

Svelte 5 + Vite (raw Svelte, not SvelteKit). Single-screen, mobile-first.
Consumes halo-design tokens via `frontend/src/styles/colors_and_type.css`
(copied verbatim) and `--halo-*` vars in scoped `<style>` blocks. See the
`ocular-design` skill for the brand delta.

## Validation

Run `yarn validate` after changes — typecheck + lint + format in one shot.

Individual scripts:

- `yarn lint` / `yarn lint:fix` (eslint, house `eslint-config/svelte` preset)
- `yarn format` / `yarn format:fix` (prettier)
- `yarn typecheck` (`svelte-check`)

Use yarn (not npm). Dev server proxies `/api` and `/stream.mjpg` to the backend
at `:8099`.
