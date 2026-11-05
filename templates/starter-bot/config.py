"""Configuration from the environment.

Required values fail fast at startup when missing. Nothing secret lives
in this file: the token comes from the DISCORD_TOKEN environment variable
(or a local .env file, which is never committed).
"""

import os

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

TEST_GUILD_ID = int(os.environ.get("TEST_GUILD_ID", "0") or 0)

DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/bot.db")
