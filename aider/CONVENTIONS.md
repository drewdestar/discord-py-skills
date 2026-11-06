# CONVENTIONS.md: discord-py-skills digest for Aider

Aider has no skill system, so this file is the condensed digest of
the discord-py-skills pack (seven skills). It is generated from the
skills; the full text lives in `skills/<name>/SKILL.md` in the repo
https://github.com/drewdestar/discord-py-skills. Read the full skill
before doing the work it covers.

## Router

- New bot or broken skeleton: build-discord-bot.
- Slash command work: slash-commands.
- Currency, shop, inventory: economy-database.
- Languages: i18n.
- Tests: testing.
- Deploy and staying online: deploy-and-monitor.
- Unsure: start with using-discord-py-skills.

## Build (build-discord-bot)

- `discord.py>=2.5`. Check `pip show discord.py` before trusting an API.
- Entry point: intents, `setup_hook` loads cogs, `bot.run(config.DISCORD_TOKEN)`.
  Never load cogs in `on_ready` (it can fire twice).
- Config from environment only. Token never in code. `.env` chmod 600,
  `.env.example` placeholders only, `.gitignore` covers `.env`, `*.db`.
- `Intents.default()` plus `message_content = True` only if the bot reads
  message text. Enable the same intents in the Developer Portal.
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

## Deploy and monitor (deploy-and-monitor)

- systemd `Restart=always`, `RestartSec=10`. Token in an
  `EnvironmentFile` with mode 600. Never `kill -9`.
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
