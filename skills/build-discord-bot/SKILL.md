---
name: build-discord-bot
description: "Build a production discord.py bot from scratch: intents, cogs, async setup, config from environment, logging, and a project layout that survives real use. Use when the user says 'build me a Discord bot', 'my bot does not answer', or 'set up a new bot project'. Do NOT use for adding a single slash command or for writing tests; use slash-commands or testing for those."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, no paid services"
metadata:
  version: "0.5.0"
  author: "drewdestar"
---

# Build a Discord Bot

This skill scaffolds a discord.py bot the production way: one entry point, cogs for features, config from the environment, and logging from the first line. Follow it when starting a new bot. Use it to audit an existing bot that crashes on startup, loses its token, or grows into one giant file.

## Project layout

```
bot/
  bot.py            # entry point only: intents, load cogs, run
  config.py         # reads environment variables, nothing else
  cogs/
    __init__.py
    general.py      # one cog per feature
  db.py             # database access, if the bot stores data
  requirements.txt
  .env.example      # placeholder values only, never a real token
  .gitignore        # .env, *.db, __pycache__, .venv
```

One file per feature. A cog that passes 400 lines is a sign it holds two features; split it.

## Entry point

The entry point: intents, `setup_hook`, cog loading, sync, and the token from config. See `references/entry-point.md`.

## First command

The first command (`/ping`) and the error handler that answers the user. See `references/first-command.md`.

## Config from the environment

```python
import os
from dotenv import load_dotenv

load_dotenv()  # local development only; production sets real env vars

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]  # KeyError on startup if missing
TEST_GUILD_ID = int(os.environ.get("TEST_GUILD_ID", "0") or 0)
DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/bot.db")
```

- Required values use `os.environ["NAME"]` so a missing value fails fast at startup with a clear error, instead of failing later inside a command.
- Optional values use `.get()` with a documented default.
- Local development loads `.env` with `python-dotenv` (`load_dotenv()` before reading). Production sets real environment variables. The `.env` file itself is never committed.

## Logging

- Configure logging once, in `bot.py`, before anything else runs.
- Use module loggers (`logging.getLogger(__name__)`), not `print()`. Logs need timestamps and levels to be useful after a crash.
- Log at startup: which cogs loaded, which guild the bot connected to, and any command sync result. When something breaks at 3 AM, those three lines are the whole investigation.

## APIs that no longer exist (do not use)

AI assistants often write discord.py from old tutorials. These APIs
are gone or renamed in discord.py 2.x. If generated code uses one,
it is wrong, no matter how confident it looks:

| Dead or wrong | Use instead |
|---|---|
| `Intents.messages_intents = True` | `Intents.message_content = True` |
| `VoiceState.voice_channel` | `VoiceState.channel` |
| `@commands.command(pass_context=True)` | `pass_context` was removed years ago; drop it |
| `client.delete_message(msg)` | `await msg.delete()` |
| `discord.Client(command_prefix="!")` | `commands.Bot(command_prefix="!")` |
| `command_prefix="/"` to make slash commands | Slash commands are `app_commands` and must be synced; a prefix is not a slash command |

Pin the version: `discord.py>=2.7.1` in requirements, and check the
installed version with `pip show discord.py` before trusting any
API you are unsure of. The starter bot requires `discord.py>=2.7.1` (Components V2 needs 2.6.0+, and this pack was live-verified against 2.7.1).

## on_message is a gate, not a hook

If you define `on_message`, its last line must be
`await bot.process_commands(message)`. Without that line, every
prefix command silently stops working, and the bot looks dead while
it is actually swallowing messages. Prefer a listener in a cog over
overriding `on_message` in the bot class. A test must prove a bot
with a custom `on_message` still answers `!ping` (see testing).

## Blocking calls: banned list

These freeze the event loop and every command for every user. Never
use them inside a handler, command, or event:

- `time.sleep()` becomes `await asyncio.sleep()`
- `requests.get/post()` becomes `aiohttp`
- synchronous `sqlite3` becomes `aiosqlite`
- `pyautogui`, blocking subprocess calls, and slow file scans do not
  belong in a handler at all; move them to a task or a worker

## Common mistakes

1. **Blocking the event loop.** Never call `time.sleep()`, `requests.get()`, or a synchronous database call inside a command or event. Use `asyncio.sleep()`, `aiohttp`, and an async database driver. One blocking call freezes every command for every user.
2. **Syncing global commands on every startup.** Global command sync can take up to an hour to propagate and counts against rate limits. Sync to one test guild during development, sync globally only on release (see the slash-commands skill).
3. **Catching every exception and staying silent.** A bare `except Exception: pass` in `on_command_error` hides the bug and the user sees nothing. Log the traceback, then answer the user with a short error message.
4. **Hardcoding the token.** A token in source code ends up in git history, and git history is forever. Rotate the token, move it to the environment, and check the history is clean. If a token ever leaks: reset it in the Developer Portal immediately, update `.env` on the server, then check the audit log for what the stolen token did. A leaked token is a compromised bot, not a cleanup task.
5. **One giant `on_message`.** Message handling belongs in cogs and commands. `on_message` is for the few things that are genuinely message-driven, and it must call `await bot.process_commands(message)` or prefix commands stop working.
6. **No `setup()` in a cog file.** Every cog module needs an `async def setup(bot)` that calls `await bot.add_cog(...)`. Without it, `load_extension` fails with an error that names the missing function.

## Checklist before first run

- [ ] `python -m py_compile` passes on every file
- [ ] `.env` exists locally, `.env.example` has placeholders only
- [ ] `.gitignore` covers `.env`, `*.db`, `__pycache__`, `.venv`
- [ ] Bot starts, logs in, and `on_ready` prints once
- [ ] One slash command answers in the test guild
- [ ] Stopping the bot with Ctrl+C exits cleanly with no traceback

## Verify live

A checklist is not proof. After the bot starts, prove it in Discord:

1. `python bot.py` prints the login line and the cogs-loaded line.
2. In the test guild, run `/ping`. It answers within 3 seconds.
3. Run a prefix command (`!ping`, if one exists) with a custom
   `on_message` in place. It answers, proving `process_commands`
   is wired.
4. Check the Developer Portal: the intents the code requests are
   the intents enabled in the portal. A bot that is online but
   silent almost always has an intent enabled in only one place.
5. Stop the bot with Ctrl+C and start it again. It logs in cleanly
   with no traceback.

Report what you observed for each step. "It should work" is not
an observation.

## Quality bar (no slop)

These rules apply to every bot this skill produces:

- **No em dash** in any message, embed, or reply the bot sends.
  Use a period or a comma instead.
- **No invented numbers.** A balance, a member count, or a latency
  shown to a user must come from the database or the library, never
  from a guess or a placeholder presented as real.
- **Every command answers.** A command that fails silently looks
  like a dead bot. Errors get a short user-facing message; the
  traceback goes to the log, never to chat.
- **Every feature has a reason.** If a command, a cog, or a setting
  has no one-line reason to exist, remove it. A bot with ten
  commands that all work beats a bot with forty that half work.
- **Verify before claiming done.** Run the steps above and report
  the evidence. A bare "done" with no observation is not done.
