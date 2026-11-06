<p align="center">
  <a href="assets/banner.png"><img src="assets/banner.png" alt="discord-py-skills" width="100%" /></a>
</p>

<div align="center">

[![version](https://img.shields.io/badge/version-0.5.0-5865F2?style=flat-square)](https://github.com/drewdestar/discord-py-skills)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![MIT license](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

# discord-py-skills

### Agent skills and a production starter kit for building Discord bots with discord.py.

**Twelve skills, one router, one installer.** The router reads the job,
loads the one skill the job needs, and each skill teaches one job:
scaffolding, slash commands, buttons and modals, a SQLite economy that cannot create
money, honest i18n, deploys that restart themselves, tests that
can fail, a web dashboard, antislop copy, the .newr language,
and Hallmark design for the bot's look.

`newr install all`

[Before and after](#before--after) · [Install](#install-with-newr-like-homebrew) · [Skills](#skills) · [newr language](#write-a-bot-in-the-newr-language)

</div>

Works with 33 AI coding agents, from Claude Code and Codex to
Qwen Code, Kimi Code, Kiro, JetBrains Junie, Muse Code, and Grok
Build, plus Aider via a `CONVENTIONS.md` digest. See
[docs/AGENTS.md](docs/AGENTS.md) for the full list, including the
agents with no skill system (Meta AI, DeepSeek chat, Qwen chat,
Google Jules) that this pack honestly cannot install into.

Documentation lives in `docs/`; the VitePress site in `website/`
builds it into a searchable site (`cd website && npm install &&
npm run docs:build`) — no hosted URL yet.

## Install with newr (like Homebrew)

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

`newr init` copies the starter bot into a new directory, writes your token into `.env` (never printed, never logged, never committed — `.gitignore` already covers it), and prints the next steps. `newr init --yes` accepts every default without prompting. `newr` resolves the latest release from GitHub Releases and falls back to `main` when no release is published yet or the lookup fails; see [Exit codes and machine output](#machine-readable-output-and-exit-codes).

<p align="center">
  <a href="assets/terminal-install.png"><img src="assets/terminal-install.png" alt="Terminal output of newr install all: all twelve skills installed" width="100%" /></a>
</p>

Real output of `newr install all` (v0.5.0). Skills install to
`~/.newr/skills/<name>`; `NEWR_HOME` overrides the prefix.

**Requirements:** Python 3.10 or newer, Node.js 18 or newer (only for the
npm package metadata), and git — on macOS or Linux. `newr` checks the
Python version on startup and exits with a clear error on anything older.

**Windows:** `newr` is a plain Python script, so it runs wherever
Python 3.10+ runs. From a clone, run `newr.bat <command>` (the `.bat`
launcher sits next to the `newr` script). `pip install .` also works and
creates a `newr.exe` on Windows. Neither path has been run on a real
Windows machine yet; both are UNVERIFIED there.

| Command | What it does |
|---|---|
| `newr search [query]` | List installable packages |
| `newr info <package>` | Show a package's details and install state |
| `newr install <pkg>...` | Install packages (`all` = the twelve skills) |
| `newr uninstall <pkg>...` | Remove installed skills |
| `newr list` | Show installed skills |
| `newr update` | Refresh the registry and update installed skills |
| `newr init` | Scaffold a starter bot (prompts for name, token, guild id) |
| `newr version` | Print the newr version |
| `newr agents` | List supported agents and their skill dirs |

### Machine-readable output and exit codes

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
changing anything. The full agent contract is in `llms.txt`.

**Offline install:** `newr` fetches the registry and the skill files
from GitHub by default. If the machine has no network, or you want a
fixed copy, clone the repo and point `newr` at it:
`NEWR_LOCAL_SOURCE=/path/to/discord-py-skills newr install all`.
The local source wins over the network; everything else works the
same. Network-first stays the default.

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

All twelve skills share the pack version in this release; per-skill
versioning is a post-1.0 change. Run `newr list` to see the installed
version of each skill.

| Skill | What it covers | Use when |
|---|---|---|
| `using-discord-py-skills` | Routes any bot job to the right skill, in the right order | starting bot work, or unsure which skill applies |
| `build-discord-bot` | Scaffold a correct bot: intents, cogs, async setup, config from the environment, logging | "build me a bot", "my bot does not answer" |
| `slash-commands` | Slash commands, groups, checks, autocomplete, cooldowns, error handling that answers the user | "add a /balance command", "interaction failed" |
| `economy-database` | SQLite economy: WAL mode, atomic transfers, idempotency keys, ledger, backups | "add currency", "gold duplicated" |
| `i18n` | Multi-language bots: per-user locale, fallback chain, translation pitfalls | "speak Indonesian", "wrong language replies" |
| `deploy-and-monitor` | systemd service, watchdog restarts, log rotation, health checks, safe restarts | "keep my bot online", "my bot keeps dying" |
| `testing` | Unit tests for logic, mocked interactions for commands, async tests with pytest-asyncio | "write tests", "the test passes but the bot is broken" |
| `design-with-hallmark` | Hallmark themes for embeds, web dashboard, README visuals: 23 themes that survive Discord's dark client, embed color + limit checks | "make the bot look good", "my embeds all look the same" |
| `antislop` | Stop the bot sounding AI-generated: no em dash, no invented numbers, no generic copy in replies, embeds, or code comments | "my bot sounds like AI", "make the replies sound human" |
| `newr-language` | Write a small bot in the `.newr` language and compile it with `newr build` | "write a bot in .newr", "make me a small bot" |
| `interactive-components` | Buttons, Views, modals, selects, pagination, Components V2 | "add buttons", "make a paginated leaderboard", "my buttons stop working" |
| `bot-dashboard` | Web dashboard and backend API for a bot: one SQLite database, Discord OAuth2 login, live numbers | "make a dashboard for my bot", "show bot stats on a page" |

## How the router works

`using-discord-py-skills` does no bot work itself. It reads the job,
loads the one skill the job needs, and for a new bot it runs them in
this order. On the first bot-work turn it says, verbatim:

> I'll build this with the discord-py-skills pack. First I'll match
> your job to the one skill it needs and load only that skill — I
> won't load the whole pack up front. Once that skill is loaded I'll
> follow it, and if the job turns out to need a second skill I'll say
> so and load that one next.

Load on demand, never preload: the router loads only the skill the
task actually reaches, when it reaches it. The full route table is in
`skills/using-discord-py-skills/SKILL.md`.

<p align="center">
  <a href="assets/routing.png"><img src="assets/routing.png" alt="Router order: using-discord-py-skills, then build-discord-bot, slash-commands, interactive-components, economy-database, i18n, testing, design-with-hallmark, bot-dashboard, deploy-and-monitor" width="100%" /></a>
</p>

Skip steps that do not apply. Do not add an economy to a bot that has
no currency, and do not add i18n to a bot with one language.

## Write a bot in the newr language

`newr` has its own small language for defining a bot. A `.newr`
file is not a general-purpose programming language: it describes a
bot (its name, its slash commands, and two simple events), and
`newr build` compiles it into a runnable discord.py bot. Full
syntax in [docs/NEWR-LANG.md](docs/NEWR-LANG.md).

```newr
bot "HelloBot":
  description: "A friendly bot that answers in plain words"

command ping:
  description: "Answer with pong"
  reply: "Pong! Hello {user}"

command greet:
  description: "Greet someone in this server"
  reply: "Hello {user}, welcome to {guild}!"
  ephemeral: true

event ready:
  log: "{bot} is online"

event member_join:
  reply: "Welcome to {guild}, {user}!"
```

```bash
newr build hello.newr            # writes hello.py next to it
newr build hello.newr -o bot.py  # writes bot.py instead
newr build --check hello.newr    # parse and compile, write nothing
DISCORD_TOKEN=... python hello.py
```

The generated bot follows the same rules as the starter bot:
slash commands on the tree synced in `setup_hook`, intents
derived from the source (members intent only when a
`member_join` event exists), the token from `DISCORD_TOKEN` only,
and command errors answered instead of failing silently. A
working example is in [examples/hello.newr](examples/hello.newr)
with its generated output in
[examples/hello.py](examples/hello.py). If the bot needs logic
the language cannot say (economy, arguments, buttons), write
Python with the skills instead.

## Quality bar

Every skill enforces the same bar, written up in
[docs/QUALITY.md](docs/QUALITY.md): no em dash in anything the bot
sends, no invented numbers, every command answers, every feature has
a one-line reason, and nothing is called done until it is verified
live in Discord. A green test suite is not proof the bot answers.

## Before / after

The same bot, written twice: once the way an agent writes it with no
guidance, once the way the skills write it.

| **Before: one file, token in source, no commit** | **After: cogs, env token, atomic ledger** |
|:--|:--|
| <a href="assets/compare-before.png"><img src="assets/compare-before.png" alt="Before: one file, token in source, time.sleep(2) blocking, f-string SQL, no commit, no ledger row" width="100%"></a> | <a href="assets/compare-after.png"><img src="assets/compare-after.png" alt="After: token from the environment, cogs loaded in setup_hook, balance change and ledger row in one atomic transaction" width="100%"></a> |
| One file, blocking calls, token in source, silent failures. The gold is gone on restart. | Cogs in `setup_hook`, token from the environment, every balance change in a ledger inside one atomic transaction. See `templates/starter-bot/` for the runnable version. |

Every image here opens full size if you click it. The before code is
the block this section used to show, verbatim. The after code is
trimmed from the real starter bot (`config.py`, `bot.py`, `db.py`):
long SQL strings are elided with `...` inside the string literal.

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

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=drewdestar/discord-py-skills&type=Date)](https://star-history.com/#drewdestar/discord-py-skills&Date)

## What's new in 0.5.0

0.5.0 never shipped, so the research-driven changes below fold into
it. All twelve skills share the pack version; per-skill versioning
is a post-1.0 change.

- **bot-dashboard** (new skill): one-screen layout, per-widget
  polling, FastAPI + Pydantic production server, Discord OAuth2
  login gated by guild and role, the events endpoint, watch/notify,
  environment-variable table, server-only vs browser rules, licence
  safety, and a security checklist. Chart.js is the default chart;
  ApexCharts is only ever named with its licence note.
- **economy-database**: atomic compare-and-swap transfers, the
  revision feed (global sequence + per-user version, compensating
  rows instead of edits), migrations discipline with
  `scripts/migrate.py` and a shadow-DB drift check, backups via the
  backup API with verification and a portable dump, dashboard
  read-only rules, `/daily` wiring, and a race test that fails a
  naive check-then-insert.
- **testing**: the ping sample now runs against the starter bot's
  own pattern with a proven red check, the cooldown test fixed, the
  database fence hardened, a wiring-test sketch, and pinned dev
  requirements (pytest 9.2.0, pytest-asyncio 1.4.1.post1).
- **using-discord-py-skills** (router): a verbatim first-response
  blurb, four new route rows (`newr init`, install/update skills,
  token leaked, stale dashboard numbers), and load-on-demand plus
  discovery-first as the first rules.
- **newr**: `--json` machine-readable output on every command,
  typed exit codes (0/1/2/3/4), `llms.txt` agent contract, latest
  release resolved from GitHub Releases with a 1-hour cache,
  `newr init` scaffolding, `newr add` skill scaffolding, atomic
  installs, clean errors on corrupt JSON, the detection circularity
  fix, and `newr update --check`.
- **build-discord-bot**, **interactive-components**, **starter bot**:
  discord.py pin raised to `>=2.7.1` everywhere (Components V2
  needs 2.6.0+; the pack was live-verified against 2.7.1).
- **All skills**: bodies split into `references/` under the Codex
  8 KB cap — the body stays complete and coherent, the detail lives
  in `references/`, and the router loads both.

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
