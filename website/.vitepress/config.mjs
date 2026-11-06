import { defineConfig } from "vitepress";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// Absolute paths so the build works from any cwd. Content lives in
// docs/ at the repo root; the generator code lives here in website/.
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

export default defineConfig({
  title: "discord-py-skills",
  description:
    "Agent skills and a production starter kit for building Discord bots with discord.py.",
  srcDir: resolve(ROOT, "docs"),
  outDir: resolve(ROOT, "website/.vitepress/dist"),
  // VitePress copies srcDir/public to the output, whatever publicDir
  // says, so the sync script puts llms.txt in docs/public/.
  cleanUrls: true,
  // docs/AGENTS.md is repo-internal house rules, not a site page.
  srcExclude: ["AGENTS.md"],
  // srcDir lives outside this VitePress root (docs/ at the repo root),
  // so a bare `vue` import inside a page cannot walk up to
  // website/node_modules. Alias the two imports the SSR build needs
  // to the exact files normal resolution would give.
  vite: {
    resolve: {
      alias: [
        {
          find: /^vue$/,
          replacement: resolve(
            ROOT,
            "website/node_modules/vue/dist/vue.runtime.esm-bundler.js",
          ),
        },
        {
          find: /^vue\/server-renderer$/,
          replacement: resolve(
            ROOT,
            "website/node_modules/vue/server-renderer/index.mjs",
          ),
        },
      ],
    },
  },
  themeConfig: {
    nav: [
      { text: "Install", link: "/install" },
      { text: "Skills", link: "/skills/" },
      { text: "Router", link: "/router" },
      { text: ".newr language", link: "/NEWR-LANG" },
      { text: "Changelog", link: "/changelog" },
    ],
    sidebar: [
      {
        text: "Guide",
        items: [
          { text: "Install", link: "/install" },
          { text: "Skills", link: "/skills/" },
          { text: "How the router works", link: "/router" },
          { text: ".newr language", link: "/NEWR-LANG" },
          { text: "Quality bar", link: "/QUALITY" },
          { text: "Changelog", link: "/changelog" },
        ],
      },
    ],
    search: { provider: "local" },
    socialLinks: [
      { icon: "github", link: "https://github.com/drewdestar/discord-py-skills" },
    ],
    footer: {
      message:
        'MIT Licensed. Agent contract: <a href="/llms.txt">llms.txt</a>.',
      copyright: "Copyright © 2026 drewdestar",
    },
  },
});
