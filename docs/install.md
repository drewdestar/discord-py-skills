# Install

`newr` is the package manager for this pack. Install it once, then
install skills by name:

```bash
curl -fsSL https://raw.githubusercontent.com/drewdestar/discord-py-skills/main/install.sh | sh
newr init                          # scaffold a working bot (asks for name, token, guild id)
newr search
newr install slash-commands
newr install all                   # all twelve skills
newr install starter-bot           # same starter bot, no prompts, into ./starter-bot
```

`newr init` copies the starter bot into a new directory, writes your
token into `.env` (never printed, never logged, never committed —
`.gitignore` already covers it), and prints the next steps.
`newr init --yes` accepts every default without prompting.

**Requirements:** Python 3.10 or newer, Node.js 18 or newer (only for
the npm package metadata), and git — on macOS or Linux. `newr`
checks the Python version on startup and exits with a clear error
on anything older.

**Windows:** `newr` is a plain Python script, so it runs wherever
Python 3.10+ runs. From a clone, run `newr.bat <command>` (the `.bat`
launcher sits next to the `newr` script). `pip install .` also works
and creates a `newr.exe` on Windows. Neither path has been run on a
real Windows machine yet; both are UNVERIFIED there.

| Command | What it does |
|---|---|
| `newr search [query]` | List installable packages |
| `newr info <package>` | Show a package's details and install state |
| `newr install <pkg>...` | Install packages (`all` = the twelve skills) |
| `newr uninstall <pkg>...` | Remove installed skills |
| `newr list` | Show installed skills |
| `newr update` | Refresh the registry and update installed skills |
| `newr update --check` | Print the update verdict without changing anything |
| `newr init` | Scaffold a starter bot (prompts for name, token, guild id) |
| `newr add <skill>` | Scaffold a new skill (boilerplate + registry entry) |
| `newr version` | Print the newr version |
| `newr agents` | List supported agents and their skill dirs |

Skills install to `~/.newr/skills/<name>` (`NEWR_HOME` overrides the
prefix). Templates install into the current directory. No account, no
token, no build step. `newr` is one Python file, standard library only.

## Install into an agent

```bash
newr install --agent claude-code all    # Claude Code
newr install --agent codex,cursor all   # several agents at once
newr install --agent auto all           # every agent detected here
newr install --agent all all            # every known agent
newr install --agent copilot --project testing  # into this project
```

| Agent | Skill directory |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex | `~/.agents/skills/` (older installs also read `~/.codex/skills/`) |
| Cursor | `~/.cursor/skills/` |
| Windsurf / Devin Local | `~/.config/devin/skills/` |
| GitHub Copilot | `~/.copilot/skills/` |
| Gemini CLI | `~/.gemini/skills/` |
| OpenCode | `~/.config/opencode/skills/` |
| Kilo Code, Zed | `~/.agents/skills/` |
| Cline | `~/.cline/skills/` |
| Aider | no skill system; copy `aider/CONVENTIONS.md` and add it to `read:` in `.aider.conf.yml` |

The full matrix, including project-scope directories, is in the
repo's `docs/AGENTS.md`. The pack works with 33 agents in total.

## Install with npx (no install step)

No install, no clone. Needs Node.js 18 or newer, Python 3.10 or
newer, and git, on macOS or Linux:

```bash
npx -y github:drewdestar/discord-py-skills install all
npx -y github:drewdestar/discord-py-skills install --agent claude-code all
```

This runs `newr` straight from the repo. The `newr` package is not
published to the npm registry yet, so `npx newr` on its own does not
work; use the `github:` form above.

Claude Code can also install the pack as a plugin:

```
/plugin marketplace add drewdestar/discord-py-skills
/plugin install discord-py-skills@discord-py-skills
```

## Install by hand

Copy the `skills/` folder into your agent's skills directory. The
recommended way is `newr install --agent <name> all` (see above).

## Machine-readable output and exit codes

For scripts and agents, run any command with `--json`: stdout is
exactly one JSON object — `{ok, command, newr, data, warnings,
error}` — logs go to stderr, and prompts are disabled. A failed
command still prints one JSON object, with `error` set:

```json
{"ok": false, "command": "install", "newr": "0.5.0", "data": null,
 "warnings": [], "error": {"code": "usage",
 "message": "no package named 'slash-command'. Run `newr search` to see what exists.",
 "hint": "Run `newr search` to see what exists."}}
```

| Exit code | Meaning |
|---|---|
| 0 | Success |
| 1 | Usage error: bad command, flags, or package name |
| 2 | Environment error: Python older than 3.10 |
| 3 | Network error: registry, tarball, or release lookup failed |
| 4 | Build error: `newr build` on a bad `.newr` file |

`newr` checks the latest GitHub Release (unauthenticated GitHub API
limit: 60 requests/hour; set `NEWR_GITHUB_TOKEN` to raise it to
5,000) and falls back to `main` when no release exists yet or the
lookup fails. `newr update --check` prints the verdict without
changing anything. The full agent contract is in
[`llms.txt`](/llms.txt).

## Offline install

`newr` fetches the registry and the skill files from GitHub by
default. If the machine has no network, or you want a fixed copy,
clone the repo and point `newr` at it:
`NEWR_LOCAL_SOURCE=/path/to/discord-py-skills newr install all`.
The local source wins over the network; everything else works the
same. Network-first stays the default.
