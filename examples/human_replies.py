"""Reply copy that follows the antislop skill, in a runnable bot.

The replies here are plain and short. No voice sample was supplied for
this example, so there is no invented personality behind them. Replace
the reply strings with words your own server already uses, and keep
the rules the builders enforce: every number comes from a measured
source, and every failure still answers the user.

Run it with:
    DISCORD_TOKEN=... python examples/human_replies.py
"""

import logging
import math
import os
from typing import Protocol

import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("human_replies")

MAX_ITEMS_SHOWN = 20


class Store(Protocol):
    """The two reads the replies need. Any database that offers these
    two methods can replace the memory store below."""

    async def get_balance(self, user_id: int) -> int: ...

    async def get_items(self, user_id: int) -> list[str]: ...


class MemoryStore:
    """Example-only storage. Balances start at 0 and change only when
    the operator sets them, so no reply ever shows a number with no source."""

    def __init__(self) -> None:
        self._balances: dict[int, int] = {}
        self._items: dict[int, list[str]] = {}

    async def get_balance(self, user_id: int) -> int:
        return self._balances.get(user_id, 0)

    async def set_balance(self, user_id: int, amount: int) -> None:
        if amount < 0:
            raise ValueError("balance cannot be below 0")
        self._balances[user_id] = amount

    async def get_items(self, user_id: int) -> list[str]:
        return list(self._items.get(user_id, []))

    async def add_item(self, user_id: int, name: str) -> None:
        self._items.setdefault(user_id, []).append(name)


def format_balance(amount: int) -> str:
    return f"Your balance is {amount:,} gold."


def format_ping(latency_ms: int | None) -> str:
    if latency_ms is None:
        return "Pong! I am awake."
    return f"Pong! Latency is {latency_ms} ms."


def format_inventory(items: list[str]) -> str:
    if not items:
        return "You have no items yet."
    noun = "item" if len(items) == 1 else "items"
    lines = [f"You have {len(items)} {noun}:"]
    lines.extend(f"- {name}" for name in items[:MAX_ITEMS_SHOWN])
    if len(items) > MAX_ITEMS_SHOWN:
        lines.append(f"Showing {MAX_ITEMS_SHOWN} of {len(items)} items.")
    return "\n".join(lines)


def format_help() -> str:
    return (
        "/ping: check the bot is awake.\n"
        "/balance: show your gold.\n"
        "/inventory: list the items you own.\n"
        "Pick a command and Discord fills in the rest."
    )


def latency_ms(bot: commands.Bot) -> int | None:
    """Measured latency in ms, or None when the bot is not connected.
    A missing measurement means no number, not a guessed one."""
    value = bot.latency
    if value is None or not math.isfinite(value) or value < 0:
        return None
    return round(value * 1000)


class BalanceView(discord.ui.View):
    """One button that re-reads the balance. It has no timeout and a
    stable custom id, so it keeps working after a restart instead of
    failing silently once the message gets old."""

    def __init__(self, store: Store) -> None:
        super().__init__(timeout=None)
        self.store = store

    @discord.ui.button(
        label="Check again",
        style=discord.ButtonStyle.secondary,
        custom_id="human_replies:balance_again",
    )
    async def check_again(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            amount = await self.store.get_balance(interaction.user.id)
        except Exception:
            log.exception("Could not read balance for user %s", interaction.user.id)
            await interaction.response.send_message(
                "I could not read your balance. Try again in a bit.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            format_balance(amount), ephemeral=True
        )


class HumanReplies(commands.Cog):
    """Slash commands that answer in plain words. Each command has one
    reason: ping proves the bot is awake, balance shows sourced gold,
    inventory lists owned items, help lists the commands that exist."""

    def __init__(self, bot: commands.Bot, store: Store | None = None) -> None:
        self.bot = bot
        self.store = store if store is not None else MemoryStore()

    @app_commands.command(name="ping", description="Check the bot is awake.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(format_ping(latency_ms(self.bot)))

    @app_commands.command(name="balance", description="Show your gold balance.")
    async def balance(self, interaction: discord.Interaction) -> None:
        try:
            amount = await self.store.get_balance(interaction.user.id)
        except Exception:
            log.exception("Could not read balance for user %s", interaction.user.id)
            await interaction.response.send_message(
                "I could not read your balance. Try again in a bit.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            format_balance(amount), view=BalanceView(self.store)
        )

    @app_commands.command(name="inventory", description="List the items you own.")
    async def inventory(self, interaction: discord.Interaction) -> None:
        # The store read can be slow, so this command defers first and
        # answers through followup. Answering through response after a
        # defer raises an error, so followup is the only path here.
        await interaction.response.defer()
        try:
            items = await self.store.get_items(interaction.user.id)
        except Exception:
            log.exception("Could not read items for user %s", interaction.user.id)
            await interaction.followup.send(
                "I could not read your items. Try again in a bit.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(format_inventory(items))

    @app_commands.command(name="help", description="List the commands this bot has.")
    async def help_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(format_help(), ephemeral=True)

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        log.exception("Command failed: %s", interaction.command)
        text = "Something went wrong. The error was logged."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)
        except discord.HTTPException:
            log.warning("Could not answer the failed command.")


class Bot(commands.Bot):
    def __init__(self, store: Store | None = None) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.store = store if store is not None else MemoryStore()

    async def setup_hook(self) -> None:
        await self.add_cog(HumanReplies(self, self.store))
        self.add_view(BalanceView(self.store))
        test_guild_id = os.environ.get("TEST_GUILD_ID")
        if test_guild_id:
            guild = discord.Object(id=int(test_guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Commands synced to test guild %s.", test_guild_id)
        else:
            await self.tree.sync()
            log.info("Commands synced globally.")

    async def on_ready(self) -> None:
        log.info("%s is online", self.user)


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("set the DISCORD_TOKEN environment variable")
    Bot().run(token)


if __name__ == "__main__":
    main()
