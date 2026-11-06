## First command

Every bot in this skill starts with one command, so the "verify live" steps below have something to run:

```python
# cogs/general.py
import logging
import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)

class General(commands.Cog):
    @app_commands.command(name="ping", description="Check the bot is alive.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Pong!", ephemeral=True)

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            text = f"Slow down. Try again in {error.retry_after:.0f} seconds."
        elif isinstance(error, app_commands.MissingPermissions):
            text = "You do not have permission to use this command."
        elif isinstance(error, app_commands.CheckFailure):
            text = "You cannot use this command here."
        else:
            log.exception("Command failed: %s", interaction.command)
            text = "Something went wrong. The error was logged."

        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General())
```

The error handler is the same one the slash-commands skill explains in full. A cog that answers commands but never answers errors looks dead the first time a command fails.
