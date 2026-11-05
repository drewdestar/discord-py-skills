---
name: build-discord-bot
description: "Build a production discord.py bot from scratch: intents, cogs, async setup, config from environment, logging, and a project layout that survives real use. Use when starting a new Discord bot or fixing a bot that crashes on startup."
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

```python
import asyncio
import logging
import discord
from discord.ext import commands

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger("bot")

class Bot(commands.Bot):
    async def setup_hook(self) -> None:
        # setup_hook runs before the bot connects. Load cogs here,
        # not in on_ready (on_ready can fire more than once).
        for cog in ("cogs.general",):
            await self.load_extension(cog)
        log.info("Cogs loaded.")

    async def on_ready(self) -> None:
        log.info("Logged in as %s (%s)", self.user, self.user.id)

def main() -> None:
    intents = discord.Intents.default()
    intents.message_content = True  # only if the bot reads message text
    bot = Bot(command_prefix="!", intents=intents)
    bot.run(config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()
```

Rules that matter:

- Load extensions in `setup_hook`, never in `on_ready`. `on_ready` can fire again after a reconnect, and loading the same cog twice raises an error.
- Pass the token to `bot.run()` from config, never as a literal string in the code.
- `message_content` is a privileged intent. Enable it in the Developer Portal only if the bot actually reads message text. Slash-command-only bots do not need it.
- Keep `bot.py` free of feature code. If a helper is needed by two cogs, it belongs in its own module, not in `bot.py`.

## Config from the environment

```python
import os

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

## Common mistakes

1. **Blocking the event loop.** Never call `time.sleep()`, `requests.get()`, or a synchronous database call inside a command or event. Use `asyncio.sleep()`, `aiohttp`, and an async database driver. One blocking call freezes every command for every user.
2. **Syncing global commands on every startup.** Global command sync can take up to an hour to propagate and counts against rate limits. Sync to one test guild during development, sync globally only on release (see the slash-commands skill).
3. **Catching every exception and staying silent.** A bare `except Exception: pass` in `on_command_error` hides the bug and the user sees nothing. Log the traceback, then answer the user with a short error message.
4. **Hardcoding the token.** A token in source code ends up in git history, and git history is forever. Rotate the token, move it to the environment, and check the history is clean.
5. **One giant `on_message`.** Message handling belongs in cogs and commands. `on_message` is for the few things that are genuinely message-driven, and it must call `await bot.process_commands(message)` or prefix commands stop working.
6. **No `setup()` in a cog file.** Every cog module needs an `async def setup(bot)` that calls `await bot.add_cog(...)`. Without it, `load_extension` fails with an error that names the missing function.

## Checklist before first run

- [ ] `python -m py_compile` passes on every file
- [ ] `.env` exists locally, `.env.example` has placeholders only
- [ ] `.gitignore` covers `.env`, `*.db`, `__pycache__`, `.venv`
- [ ] Bot starts, logs in, and `on_ready` prints once
- [ ] One slash command answers in the test guild
- [ ] Stopping the bot with Ctrl+C exits cleanly with no traceback
