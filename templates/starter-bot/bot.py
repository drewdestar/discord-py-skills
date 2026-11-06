"""Minimal working discord.py starter bot.

Slash commands only: /ping, /balance, and /leaderboard, backed by a
small SQLite economy (see db.py). Run the tests with: python -m pytest -q
"""

import asyncio
import logging

import discord
from discord.ext import commands

import config
import db as db_module
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("starter-bot")


class Bot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.db = None
        self.db_lock = asyncio.Lock()

    async def setup_hook(self) -> None:
        self.db = await db_module.connect(config.DATABASE_PATH)
        await db_module.init_db(self.db)
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.leaderboard")
        log.info("Cogs loaded.")

        if config.TEST_GUILD_ID:
            guild = discord.Object(id=config.TEST_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Commands synced to test guild %s.", config.TEST_GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Commands synced globally.")

    async def on_ready(self) -> None:
        log.info("Logged in as %s (%s).", self.user, self.user.id)

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
        await super().close()


def main() -> None:
    load_dotenv()
    bot = Bot()
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
