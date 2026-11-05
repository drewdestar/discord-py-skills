"""General commands: /ping and /balance."""

import discord
from discord import app_commands
from discord.ext import commands

import db as db_module


class General(commands.Cog):
    """General commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot is awake.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! Latency: {latency} ms")

    @app_commands.command(name="balance", description="Show your gold balance.")
    async def balance(self, interaction: discord.Interaction) -> None:
        amount = await db_module.get_balance(self.bot.db, interaction.user.id)
        await interaction.response.send_message(
            f"Your balance: {amount} gold."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
