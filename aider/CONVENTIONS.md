# CONVENTIONS.md: discord-py-skills digest for Aider

Aider has no skill system, so this file is the condensed digest of
the discord-py-skills pack (twelve skills). It is generated from the
skills; the full text lives in `skills/<name>/SKILL.md` in the repo
https://github.com/drewdestar/discord-py-skills. Read the full skill
before doing the work it covers.

## Router

- New bot or broken skeleton: build-discord-bot.
- Small bot in the .newr language: newr-language (`newr build`).
- Slash command work: slash-commands.
- Buttons, selects, modals, pagination: interactive-components.
- Currency, shop, inventory: economy-database.
- Languages: i18n.
- Tests: testing.
- Look and feel (embeds, dashboard, README): design-with-hallmark.
- Web dashboard for the bot: bot-dashboard.
- Bot copy sounds like AI, replies need checking: antislop.
- Deploy and staying online: deploy-and-monitor.
- Unsure: start with using-discord-py-skills.

## Build (build-discord-bot)

- `discord.py>=2.5.2`. Check `pip show discord.py` before trusting an API.
- Entry point: intents, `setup_hook` loads cogs, `bot.run(config.DISCORD_TOKEN)`.
  Never load cogs in `on_ready` (it can fire twice).
- Config from environment only. Token never in code. `.env` chmod 600,
  `.env.example` placeholders only, `.gitignore` covers `.env`, `*.db`.
- `Intents.default()` plus `message_content = False` unless the bot reads
  message text (privileged intent; enable the same intents in the
  Developer Portal). Set a global `AllowedMentions` policy: the library
  default allows `@everyone` and `@role` mentions.
- Dead APIs, never use: `Intents.messages_intents`, `VoiceState.voice_channel`,
  `pass_context=True`, `client.delete_message()`, `discord.Client(command_prefix=...)`.
  A `/` prefix is not a slash command.
- If you define `on_message`, its last line must be
  `await bot.process_commands(message)`, or prefix commands die silently.
- Never block the event loop: `time.sleep()` becomes `await asyncio.sleep()`,
  `requests` becomes `aiohttp`, sync `sqlite3` becomes `aiosqlite`.

## Slash commands (slash-commands)

- Commands are `app_commands`. Answer within 3 seconds or `defer()` first,
  then answer through `followup`.
- Sync to one test guild during development; sync globally only on release.
  Never sync on every startup, message, or command. Changing a callback
  without re-syncing changes nothing users see (`CommandSignatureMismatch`).
- Autocomplete: at most 25 choices, answer fast, filter by permission
  inside the callback (checks do not apply to autocomplete).
- Every error path sends the user a message. Log the traceback; never
  send it to chat. Persistent views need `bot.add_view()` in `setup_hook`.

## .newr language (newr-language)

- `.newr` describes one small bot: one `bot` block first, `command` blocks
  with replies, `ready`/`member_join` events only. `newr build` compiles
  it to runnable discord.py; the generated file is never edited by hand.
- Command names follow Discord's rule: 1-32 characters, lowercase
  letters, digits, `_` and `-`; any language's letters count. Names must
  be unique and must not sanitize to the same function name.
- Replies are checked at build time: description at most 100 characters,
  reply at most 2000 after placeholder expansion, empty descriptions
  and replies rejected. Placeholders only from the table (`{user}`,
  `{guild}`, `{channel}` for commands).
- Generated code targets Python 3.10+ and discord.py 2.x. No currency,
  arguments, buttons, modals, or scheduled tasks: use the other skills.

## Interactive components (interactive-components)

- Buttons, selects, modals, pagination live in `discord.ui.View` subclasses.
  Every View that acts for one user has `interaction_check`; buttons
  disable at the edges and on timeout.
- Persistent views use `timeout=None`, a stable `custom_id`, and
  `bot.add_view()` in `setup_hook`.
- Modals use `discord.TextStyle`, never `TextInputStyle` (renamed).
  `discord.ext.pages` does not exist in discord.py; paginate by hand.
- Components V2 needs discord.py 2.6+: `LayoutView()` takes no arguments,
  build it empty and `add_item` a `Container`. A V2 message cannot carry
  embeds. Selects in modals need 2.6+; checkbox/radio groups need 2.7+.

## Economy (economy-database)

- A bot economy is a ledger. Every balance change is a row in
  `transactions`; the balance column is a cache, the ledger wins.
- One writer: one connection plus one `asyncio.Lock`. WAL mode on,
  `busy_timeout=5000`, foreign keys on.
- Atomic transfers: `BEGIN IMMEDIATE`, check and update inside the
  same transaction, commit once. Never read-then-write a balance.
- Every external credit carries a unique idempotency key
  (`daily:<user_id>:<YYYY-MM-DD>`); the UNIQUE constraint enforces it.
- Parameterized queries always. Never build SQL with f-strings.
- `balance >= 0` as a CHECK constraint. Migrations are numbered files
  tracked by `PRAGMA user_version`.
- Hourly backups, 7 days, and test a restore. Never commit a `.db`.
- SQLite is a file: on hosts that wipe local files on redeploy
  (Railway, Heroku), use Postgres with asyncpg instead.

## i18n

- One locale preference per user, stored in the database, default English.
- Fallback chain is code: locale, then English, then the key itself.
- Never translate at runtime with an unvalidated machine translator.
  Translate offline, review, ship a fixed table.
- Never translate single words without context. Placeholders are part
  of the key contract; validate them at startup for every locale, or
  the bot refuses to start. Cache keyed by `(locale, key)`.
- Test every locale, not just the new one.

## Testing (testing)

- Pure logic: plain pytest, expected values from the spec, never
  recomputed the way the code does.
- Database: fresh temp database per test; assert the failed transfer
  changed nothing.
- Commands: call the callback with a mocked interaction; assert what
  the user would see. `AsyncMock` for `response` and `followup`.
- No network, no live token in tests. Do not test discord.py itself.
- Write the failing test first. Assert exact values, not truthiness.
  Never mock the unit under test. Every command needs an error-path test.
- Before trusting a suite, break something on purpose and confirm a
  test goes red.

## Design (design-with-hallmark)

- Deal a theme first, then style embeds and the dashboard in it: one
  accent only (the embed color stripe), paper/ink for dashboard colors.
  All 50 themes pass WCAG AA (4.5:1).
- Embed rules: title at most 256 characters, description at most 4096,
  25 fields, 6000 total characters. Validate with `validate_embed()`
  before sending; fix the copy, do not catch and send anyway.
- Theme voice goes in embed words; fonts, textures, radii, and spacing
  do not transfer to Discord. Keyword matching is English web-category
  words only.
- `discord_embed(timestamp=...)` accepts a datetime or an ISO string;
  the helper normalizes it (`Embed.from_dict` only takes strings).

## Anti-slop (antislop)

- Runs DURING the work, not after: every reply the bot sends goes
  through the filter before it ships.
- No em dash in any bot message, embed, or reply. No invented
  numbers: balances, counts, and latencies come from the database
  or the library. No generic copy ("Get Started", "Learn More"),
  no buzzwords ("Seamless", "Revolutionary", "AI Powered"), no
  temporal runway ("In today's fast-paced world"), no theatrical
  takeaway ("Read that again."), no title case in list elements.
- Every button, select, link, and command must do something real
  or be removed. A command that fails silently looks like a dead
  bot. Errors get a short user-facing message; the traceback goes
  to the log, never to chat.
- Every feature gets a one-line reason, or it is removed. Verify
  before claiming done: run the bot, invoke each command in a test
  guild, trigger one error path, restart and confirm data survives.
  Report what you observed; never claim more than you verified.
- Runnable check: `python3 scripts/check_antislop.py <file>` (exit
  0 clean, 1 warnings, 2 errors). It catches mechanical tells only;
  it never judges purpose or substance.
- Web-UI rules (gradients, glassmorphism, shadows, glow, theme
  toggles) do not transfer; they live in design-with-hallmark.

## Bot dashboard (bot-dashboard)

- A dashboard is a backend problem first: one SQLite database shared
  by the bot and the API, never a browser touching the bot token.
- Auth is Discord OAuth2 with a `state` token, proving guild membership
  plus a staff role. No role, no dashboard.
- Live numbers: poll first, then SSE, then WebSocket — in that order.
  `/health` returns 200 only when the database answers a real query.
- Bind `127.0.0.1` only; the API reads the database read-only
  (`mode=ro`) so a dashboard bug cannot corrupt balances.

## Deploy and monitor (deploy-and-monitor)

- systemd `Restart=always`, `RestartSec=10`. Token in an
  `EnvironmentFile` with mode 600. Never `kill -9`.
- `StartLimitIntervalSec` + `StartLimitBurst` stop a crash loop from
  burning Discord's 1,000 IDENTIFY-per-day budget. Install a SIGTERM
  handler that closes the bot (and the database) gracefully; without
  it, `systemctl stop` kills mid-write.
- Heartbeat file every 60 seconds from inside the event loop; watchdog
  restarts on staleness. A process can be alive and completely wedged.
- Logs rotate (10 MB, 5 files). Never log the token.
- Health check probed from outside; `/health` returns 200 only when
  the bot is connected and the database answers.
- Keeping it online is the killer step: supervisor plus watchdog plus
  outside health check. Never run a production bot on a laptop lid.
- Token leaked: reset it in the Developer Portal, update `.env`,
  restart, check the audit log.

## Quality bar (applies to everything)

- No em dash in any message, embed, or reply the bot sends.
- No invented numbers: balances, counts, and latencies come from the
  database or the library.
- Every command answers. Every feature has a one-line reason, or it
  is removed.
- Verify live before claiming done: run the bot, invoke each command
  in a test guild, trigger one error path, restart and confirm data
  survives. Report what you observed, step by step.
