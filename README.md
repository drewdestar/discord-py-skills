# discord-py-skills

Agent skills and a production starter kit for building Discord bots with
discord.py. Each skill teaches an AI coding agent one job, with the
patterns that keep a real bot running: correct intents, slash commands
that answer errors, a SQLite economy that cannot create money, honest
i18n, and deploys that restart themselves. Current release: v0.3.0.

Works with Claude Code, Codex, Cursor, Windsurf, GitHub Copilot,
Gemini CLI, OpenCode, Kilo Code, Cline, Zed, and Aider. See
[docs/AGENTS.md](docs/AGENTS.md) for every install directory.

## Install with newr (like Homebrew)

`newr` is the package manager for this pack. Install it once, then
install skills by name:

```bash
curl -fsSL https://raw.githubusercontent.com/drewdestar/discord-py-skills/main/install.sh | sh
newr search
newr install slash-commands
newr install all               # all seven skills
newr install starter-bot       # runnable starter bot into ./starter-bot
```

| Command | What it does |
|---|---|
| `newr search [query]` | List installable packages |
| `newr info <package>` | Show a package's details and install state |
| `newr install <pkg>...` | Install packages (`all` = the seven skills) |
| `newr uninstall <pkg>...` | Remove installed skills |
| `newr list` | Show installed skills |
| `newr update` | Refresh the registry and update installed skills |
| `newr version` | Print the newr version |
| `newr agents` | List supported agents and their skill dirs |

Skills install to `~/.newr/skills/<name>` (`NEWR_HOME` overrides the
prefix). Templates install into the current directory. No account, no
token, no build step. `newr` is one Python file, standard library only.

Install straight into an agent instead:

```bash
newr install --agent claude-code all    # Claude Code
newr install --agent codex,cursor all   # several agents at once
newr install --agent auto all           # every agent detected here
newr install --agent all all            # every known agent
newr install --agent copilot --project testing  # into this project
```

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
recommended way is `newr install --agent <name> all` (see above);
by hand, the directories are:

| Agent | Copy to |
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

Full matrix, including project-scope directories, is in
[docs/AGENTS.md](docs/AGENTS.md).

Then ask your agent to build a bot. It picks the skill that matches the
job: `using-discord-py-skills` routes the work first,
`build-discord-bot` for scaffolding, `slash-commands` for commands,
`economy-database` for currency, `i18n` for languages,
`deploy-and-monitor` for running it, `testing` for proving it works.

## Skills

| Skill | What it covers | Use when |
|---|---|---|
| `using-discord-py-skills` | Routes any bot job to the right skill, in the right order | starting bot work, or unsure which skill applies |
| `build-discord-bot` | Scaffold a correct bot: intents, cogs, async setup, config from the environment, logging | "build me a bot", "my bot does not answer" |
| `slash-commands` | Slash commands, groups, checks, autocomplete, cooldowns, error handling that answers the user | "add a /balance command", "interaction failed" |
| `economy-database` | SQLite economy: WAL mode, atomic transfers, idempotency keys, ledger, backups | "add currency", "gold duplicated" |
| `i18n` | Multi-language bots: per-user locale, fallback chain, translation pitfalls | "speak Indonesian", "wrong language replies" |
| `deploy-and-monitor` | systemd service, watchdog restarts, log rotation, health checks, safe restarts | "keep my bot online", "my bot keeps dying" |
| `testing` | Unit tests for logic, mocked interactions for commands, async tests with pytest-asyncio | "write tests", "the test passes but the bot is broken" |

## Quality bar

Every skill enforces the same bar, written up in
[docs/QUALITY.md](docs/QUALITY.md): no em dash in anything the bot
sends, no invented numbers, every command answers, every feature has
a one-line reason, and nothing is called done until it is verified
live in Discord. A green test suite is not proof the bot answers.

## Before / after

Without the skills, an agent writes a bot like this:

```python
# One file, blocking calls, token in source, silent failures.
import discord, time, sqlite3
TOKEN = "paste-your-token-here"  # do not do this

@bot.event
async def on_message(message):
    time.sleep(2)  # freezes every command for every user
    db = sqlite3.connect("bot.db")
    db.execute(f"UPDATE users SET balance = balance + 10 WHERE id = {message.author.id}")
    # No commit, no ledger row, no error handling. The gold is gone on restart.
```

With the skills, the same bot loads cogs in `setup_hook`, reads the token
from the environment, answers every error, and records every balance
change in a ledger inside one atomic transaction. See
`templates/starter-bot/` for a runnable version of the good pattern.

## Starter bot

`templates/starter-bot/` is a minimal working bot (`/ping`, `/balance`)
with a SQLite economy and a passing test suite. Install it with newr,
or copy it to start a real project:

```bash
newr install starter-bot
cd starter-bot
pip install -r requirements.txt
cp .env.example .env   # put your real token in .env
python bot.py
```

## Scripts

- `scripts/make_cog.py`: generate a new cog file from a template.
- `scripts/check_setup.py`: validate a bot project (intents, token
  handling, gitignore, cogs, requirements). Run it before every deploy.

Both scripts have smoke tests in `scripts/test_scripts.py`.

## Examples in production

These bots run the patterns in this pack. They are examples to read,
not code to copy: the skills generalize the patterns, the bots keep
their own implementations.

- [NEWR Support](https://github.com/drewdestar/NEWR-Support-discord)
- [NEWR AI](https://github.com/drewdestar/NEWR-AI-discord)
- [NEWR Music](https://github.com/drewdestar/NEWR-Music-discord)
- [NEWR Adventure](https://github.com/drewdestar/NEWR-Adventure-discord)

## Honest notes

- This pack is new. It has no star count to show, and it does not claim
  to be the best way to build a bot, only a way that has survived real
  use across several production bots.
- discord.py changes. If a pattern here stops matching the current
  discord.py release, open an issue with the version number.
- Nothing here needs a paid service. SQLite, systemd, and the skills
  themselves are free.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).

---

## Bahasa Indonesia (singkat)

Paket skill agen dan starter kit produksi untuk membuat bot Discord
dengan discord.py. Setiap skill mengajari agen AI satu pekerjaan:
scaffolding bot, slash command, ekonomi SQLite yang aman, i18n,
deploy dan monitoring, serta testing. Pasang dengan `newr` (lihat
bagian Install with newr di atas), atau salin folder `skills/` ke
direktori skill agen kamu, lalu minta agen membangun bot. Contoh bot
yang berjalan ada di daftar di atas. Starter bot lengkap dengan tes
ada di `templates/starter-bot/`.
