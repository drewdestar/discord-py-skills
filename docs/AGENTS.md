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
| Shared dir | `~/.agents/skills/` | `.agents/skills/` | read by Codex, Cursor, Gemini, OpenCode, Kilo, Zed, Windsurf |
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
