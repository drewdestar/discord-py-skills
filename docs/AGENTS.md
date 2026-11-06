# Agent Compatibility

The skills in this repo follow the open Agent Skills format: one
folder per skill, a `SKILL.md` with YAML frontmatter (`name`,
`description`, plus the spec fields `license`, `compatibility`,
`metadata`), and optional `scripts/`, `references/`, and `assets/`
subdirectories. The canonical source is `skills/<name>/SKILL.md`.
`newr` copies those folders into each agent's skill directory; it
never rewrites them.

Spec: https://agentskills.io/specification (name 1-64 characters and
equal to the folder name, description 1-1024 characters, body under
500 lines). Only the six spec frontmatter fields are used, so the
same files work everywhere.

## Install

```bash
newr install --agent claude-code all   # one agent
newr install --agent codex,cursor all  # several agents
newr install --agent auto all          # every agent detected here
newr install --agent all all           # every known agent
newr install --agent copilot --project testing  # project scope
newr agents                            # list agents and detection
```

`--project` installs into the project directory (for example
`.claude/skills/`) instead of the user directory. Without `--agent`,
skills install to `~/.newr/skills/` as before.

## Where skills land

| Agent | User scope | Project scope | Invoke |
|---|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` | auto by description, or `/skill-name` |
| OpenAI Codex | `~/.agents/skills/` and `~/.codex/skills/` (legacy) | `.agents/skills/` | auto, or `$skill-name` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` | auto, or `/skill-name` |
| Windsurf / Devin Local | `~/.config/devin/skills/` | `.devin/skills/` | auto, or `/skill-name` |
| GitHub Copilot | `~/.copilot/skills/` | `.github/skills/` | auto, or `/skill-name` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` | auto (asks before activating), or `/skills` |
| OpenCode | `~/.config/opencode/skills/` | `.opencode/skills/` | `skill` tool, or `@skill-name` |
| Kilo Code | `~/.agents/skills/` | `.kilocode/skills/` | auto by description |
| Cline | `~/.cline/skills/` | `.cline/skills/` | `use_skill` tool, or slash command |
| Zed | `~/.agents/skills/` | `.agents/skills/` | auto, or `/skill-name` |
| Qwen Code | `~/.qwen/skills/` | `.qwen/skills/` | auto by description |
| Kimi Code | `~/.kimi-code/skills/` | `.kimi-code/skills/` | auto by description, or `/skill:<name>` |
| Kiro | `~/.kiro/skills/` | `.kiro/skills/` | auto by description |
| JetBrains Junie | `~/.junie/skills/` | `.junie/skills/` | auto by description |
| Roo Code | `~/.roo/skills/` | `.roo/skills/` | auto by description |
| Continue.dev (`cn` CLI) | `~/.continue/skills/` | `.continue/skills/` | auto by description (CLI only) |
| Muse Code (Meta) | `~/.config/muse/skills/` | `.agents/skills/` | auto by description |
| Grok Build | `~/.grok/skills/` | `.grok/skills/` | auto by description |
| Tabnine CLI | `~/.tabnine/agent/skills/` | `.tabnine/agent/skills/` | auto by description |
| Amp | `~/.config/agents/skills/` | `.agents/skills/` | auto by description |
| Mistral Vibe | `~/.vibe/skills/` | `.vibe/skills/` | auto by description |
| Trae | `~/.trae/skills/` | `.trae/skills/` | auto by description |
| Crush | `~/.config/crush/skills/` | `.crush/skills/` | auto by description |
| Goose | `~/.config/goose/skills/` | `.agents/skills/` | auto by description |
| Factory Droid | `~/.factory/skills/` | `.factory/skills/` | auto by description |
| Augment Code | `~/.augment/skills/` | `.augment/skills/` | auto by description |
| Google Antigravity | `~/.gemini/config/skills/` and `~/.gemini/antigravity-cli/skills/` | `.agents/skills/` | auto by description |
| ZCode | `~/.zcode/skills/` | `.zcode/skills/` | auto by description |
| DeepSeek Harness | `~/.dsh/skills/` | `.dsh/skills/` | auto by description |
| OpenClaw | `~/.openclaw/skills/` | `.agents/skills/` | auto by description |
| Pi | `~/.pi/agent/skills/` | `.pi/skills/` | auto by description |
| Shared dir | `~/.agents/skills/` | `.agents/skills/` | read by Codex, Cursor, Gemini, OpenCode, Kilo, Zed, Windsurf, Qwen, Kimi, Junie, Roo, Muse Code, Grok, Tabnine, Amp, Mistral Vibe, Trae, Crush, Goose, Augment, Antigravity, DeepSeek Harness, OpenClaw, Pi, Devin |
| Aider | `~/.newr/aider/CONVENTIONS.md` | `./CONVENTIONS.md` | `read:` in `.aider.conf.yml` (see below) |

## Notes and conflicts

- **Claude Code is the exception.** It does not read
  `.agents/skills/`; it needs its own `~/.claude/skills/`. Every
  other major agent reads the shared `.agents/skills/` location.
- **Codex moved.** Current docs use `~/.agents/skills/` and
  `.agents/skills/`. The old `~/.codex/skills/` location is still
  read by older installs and by the `$skill-installer`, so `newr`
  installs Codex skills to both. `newr` never installs to
  `.codex/skills/` for a project; `.agents/skills/` is the project
  location.
- **Windsurf became Devin Local.** Cognition's rebrand moved the
  canonical paths to `.devin/skills/` and `~/.config/devin/skills/`.
  The legacy `.windsurf/skills/` and `~/.codeium/windsurf/skills/`
  paths are still read, but `newr` installs to the Devin paths.
- **OpenCode moved.** Older posts say `~/.opencode/skills/`; the
  current docs use `~/.config/opencode/skills/`. `newr` uses the
  current path.
- **Kilo Code is ambiguous.** Its docs mention `.kilocode/`,
  `.kilo/`, and `~/.agents/skills/` in different places. `newr`
  installs personal skills to `~/.agents/skills/` (the location its
  docs explicitly recommend) and project skills to
  `.kilocode/skills/`.
- **Gemini CLI asks first.** It requests confirmation before
  activating a skill. That is its own behavior, not a broken
  install; check with `/skills list`.
- **Project beats personal.** When the same skill name exists in
  both scopes, the project copy wins in Copilot, Gemini, OpenCode,
  Kilo, and Cline.
- **Kimi needs nothing extra.** Its docs list a `type` frontmatter
  field, but `type` defaults to `prompt`; only `name` and
  `description` are required in a directory-form `SKILL.md`, and
  the pack has both. Verified against the Kimi docs 2026-11-06.
- **Roo Code is shut down.** Roo Code was shut down 2026-05-15;
  the extension and docs still work on existing installs, but it
  is unmaintained and its own docs point users at Cline and Kilo
  Code. `newr` still installs to its directory for anyone still
  running it.
- **Continue.dev is CLI-only.** The skill drop-in works in the
  `cn` CLI. The Continue IDE extension has no `SKILL.md` drop-in;
  it uses `config.yaml` rules and prompts instead. The repo has
  been read-only since the June 2026 Cursor acquisition.
- **Devin has no global directory.** The Devin cloud agent only
  reads project skills, recommended at `.agents/skills/`. That is
  exactly what `newr install --agent agents --project all`
  installs, so Devin is covered by the shared project dir, not by
  a Devin entry of its own.
- **Antigravity installs twice.** Google Antigravity reads two
  global dirs (the app's `~/.gemini/config/skills/` and the CLI's
  `~/.gemini/antigravity-cli/skills/`), so `newr` installs to both.
- **The shared dir covers 20+ agents.** One project install into
  `.agents/skills/` is read natively by most agents in the table
  above, so it is the fastest way to cover a machine with several
  agents at once. It does not replace the native dirs: agents
  that read only their own directory (Claude Code, Kimi's
  `~/.kimi-code/skills/`, and others) still need their own install.

## Agents with no skill system

These are real products, but there is nowhere to install a skill
into. `newr` does not pretend otherwise.

- **Meta AI (the Muse app, muse.ai).** Skills exist but are
  Meta-authored built-ins only; Meta's Help Center says you do
  not install them. Do not confuse it with **Muse Code**, Meta's
  separate developer CLI, which does read `SKILL.md`.
- **DeepSeek chat app / API.** A chatbot and an API, with no
  agent harness and no skill directory. DeepSeek's agent product
  is the separate **DeepSeek Harness** (in the table above).
- **Qwen chat app (chat.qwen.ai).** A consumer chatbot with no
  skill system. Coding work belongs to the separate **Qwen Code**
  CLI (in the table above).
- **Google Jules.** A cloud-only agent: there is no machine to
  install a skill directory on. Its only repo-level control
  surface is a root `AGENTS.md`.
- **Amazon Q Developer CLI.** Deprecated and superseded by Kiro;
  it never had an Agent Skills / `SKILL.md` system. Install for
  **Kiro** instead.

## Checked but not verified

These were checked against live sources and no skill directory
could be verified, so `newr` installs nothing for them. Do not
invent a directory for them.

- **MiniMax Agent.** No official MiniMax coding-agent CLI exists;
  the `MiniMax-CLI` package on PyPI is explicitly unofficial.
- **PearAI.** No `SKILL.md` system or skill directory found.
- **Void editor.** Development is paused; no `SKILL.md` system
  or skill directory found.
- **Zhipu GLM Coding Plan.** Not an agent at all: a model
  subscription that plugs GLM models into other agents. Zhipu's
  actual agent is **ZCode** (in the table above).

## Aider

Aider has no skill system and does not read `SKILL.md`. `newr
install --agent aider` installs a condensed digest,
`CONVENTIONS.md`, built from all seven skills. Wire it in:

```yaml
# .aider.conf.yml
read:
  - CONVENTIONS.md
```

For a project install, `newr` writes `./CONVENTIONS.md` in the
current directory. For a user install, it writes
`~/.newr/aider/CONVENTIONS.md`; point `read:` at that path.

## Sources

- Agent Skills specification: https://agentskills.io/specification
- Claude Code skills: https://code.claude.com/docs/en/skills.md
- Codex skills: https://developers.openai.com/codex/skills/
- Cursor skills: https://cursor.com/docs/skills
- Windsurf / Devin skills: https://docs.windsurf.com/windsurf/cascade/skills
- Copilot skills: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills
  and https://code.visualstudio.com/docs/agent-customization/agent-skills
- Gemini CLI skills: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/creating-skills.md
- OpenCode skills: https://opencode.ai/docs/skills/
- Kilo Code skills: https://kilo.ai/docs/customize/skills
- Cline skills: https://docs.cline.bot/features/skills
- Zed skills: https://zed.dev/docs/ai/skills
- Qwen Code skills: https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/
- Kimi Code skills: https://moonshotai.github.io/kimi-code/en/customization/skills.html
- Kiro skills: https://kiro.dev/docs/skills/
- Junie skills: https://junie.jetbrains.com/docs/agent-skills.html
- Roo Code skills: https://roocodeinc.github.io/Roo-Code/features/skills/
- Continue.dev CLI skills: https://github.com/ar9av/agent-manual/blob/HEAD/tools/continue-cli/README.md
- Muse Code skills: https://dev.meta.ai/docs/muse-code/extending
- Grok Build skills: https://docs.x.ai/build/features/skills-plugins-marketplaces
- Tabnine CLI skills: https://docs.tabnine.com/main/getting-started/tabnine-cli/features/agent-skills
- Amp skills: https://ampcode.com/docs/customize/skills
- Devin skills: https://docs.devin.ai/product-guides/skills
- Mistral Vibe: https://github.com/mistralai/mistral-vibe
- Trae skills: https://docs.trae.ai/ide/skills
- Crush: https://github.com/charmbracelet/crush
- Goose docs: https://block.github.io/goose/docs
- Factory skills: https://docs.factory.ai/cli/configuration/skills
- Augment Code skills: https://docs.augmentcode.com/cli/v0/skills
- Antigravity skills: https://antigravity.google/docs/skills
- ZCode skills: https://zcode.z.ai/en/docs/skill
- DeepSeek Harness: https://github.com/deepseek-ai/deepseek-harness
- OpenClaw skills: https://docs.openclaw.ai/tools/skills
- Pi skills: https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/skills.md
- Meta AI skills (Help Center, no install path): https://www.meta.com/help/superintelligence/2797651547267109/
- Amazon Q end of support: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/q-developer-ide-end-of-support.html
