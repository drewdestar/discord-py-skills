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
        # Sync to one test guild during development: guild sync is
        # instant. Sync globally only on release (global sync can
        # take up to an hour to propagate).
        if config.TEST_GUILD_ID:
            guild = discord.Object(id=config.TEST_GUILD_ID)
            await self.tree.sync(guild=guild)
            log.info("Commands synced to test guild %s.", guild.id)

    async def on_ready(self) -> None:
        log.info("Logged in as %s (%s)", self.user, self.user.id)

def main() -> None:
    intents = discord.Intents.default()
    intents.message_content = False  # set True only if the bot reads message text (privileged intent)
    bot = Bot(
        command_prefix="!",
        intents=intents,
        # The library default allows @everyone and @role mentions: a
        # command that echoes user text could ping a whole server.
        allowed_mentions=discord.AllowedMentions(
            everyone=False, roles=False, users=True, replied_user=True),
    )
    bot.run(config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()
```

Rules that matter:

- Load extensions in `setup_hook`, never in `on_ready`. `on_ready` can fire again after a reconnect, and loading the same cog twice raises an error.
- Sync commands in `setup_hook`, after the cogs load: to the test guild while developing, globally only on release.
- Pass the token to `bot.run()` from config, never as a literal string in the code.
- Set a global `AllowedMentions` policy in the constructor (see `main()` above). The library default allows `@everyone` and `@role` mentions; a command that echoes user text with the default can ping a whole server.
- `message_content` is a privileged intent. Enable it in the Developer Portal only if the bot actually reads message text. Slash-command-only bots do not need it.
- Keep `bot.py` free of feature code. If a helper is needed by two cogs, it belongs in its own module, not in `bot.py`.
