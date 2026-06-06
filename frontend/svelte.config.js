import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

export default {
  // `{ script: true }` enables full TS support in <script lang="ts"> blocks.
  preprocess: vitePreprocess({ script: true }),
};
