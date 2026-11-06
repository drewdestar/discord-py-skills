## Portability: OSes, platforms, agents, languages

The v0.5.0 bar is portability across OSes, platforms, agents, and languages. Each claim below is labelled with what was verified on this VM and what is still UNVERIFIED. For this skill:

- **Operating systems.** Everything here is pure discord.py and
  asyncio: no shell commands, no OS-specific paths, no signal
  handling, no `sys.platform` checks. The starter bot's imports are
  `discord`, `aiosqlite`, `asyncio`, `logging`, `os` (environment
  variables only), and `dotenv`. It runs wherever Python 3.10+ and
  discord.py install: Linux, Windows, macOS. Verified on this VM:
  Linux, Python 3.12, discord.py 2.7.1, both test suites green.
  Windows and macOS runs are UNVERIFIED from this VM: there is no
  Windows or macOS machine here to run them on. Do not claim they
  were tested.
- **Platforms (CLI / desktop / web).** The bot itself is a CLI
  process (`python bot.py`); it has no GUI and needs none. Its users
  are on Discord desktop, web, and mobile clients, where buttons,
  selects, and modals render through the Discord API. Server-side
  behaviour (the View, the timeout, the author check) is verified
  here with mocked interactions. How each client renders a
  component is UNVERIFIED from this VM: no Discord client runs here.
- **All AI agents.** This skill is plain Markdown with YAML
  frontmatter in the Agent Skills shape: `name` matching the
  directory, a `description` with a "Use when" line, `license`,
  `compatibility`, and string `metadata`. Any agent that loads
  SKILL.md files can use it; nothing in it is specific to one
  agent. Loading in each individual agent is UNVERIFIED beyond this
  repo's own test harness (the frontmatter rules were checked
  against the repo's test logic, not against every agent).
- **All languages.** The skill text is English, the pack's working
  language. Bot-facing strings in the examples are English too:
  pass them through the i18n skill for other languages, and keep
  placeholders (`{user}`, counts) intact across translations.
  Discord's own component guidance says to anticipate translation
  and test for text expansion in button labels
  (discord/discord-api-docs, component reference). Non-English bot
  output is NOT covered by this skill; use i18n.
- **Versions.** Components V2 needs discord.py 2.6+. Selects inside
  modals need 2.6+; modal checkbox/radio groups need 2.7+ (both
  from the discord.py changelog). The paginator and persistent-view
  patterns use only core View/button APIs and run on the starter
  bot's `discord.py>=2.7.1` pin. Running them on older versions is
  UNVERIFIED: the suites here ran on 2.7.1 only, and no older
  install was tested.
