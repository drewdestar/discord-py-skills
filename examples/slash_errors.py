"""Slash commands with error handling that answers the user.

This example follows skills/slash-commands/SKILL.md. Every command
either answers or, when it fails, reaches ``cog_app_command_error``,
which sends the user a short message instead of failing silently.
The full traceback goes to the log, never to chat.

What each command shows:

* ``/ping``: a fast command that answers directly.
* ``/profile``: a slow-shaped command that defers first, then answers
  with ``followup``. The defer is the slot where a real bot would do
  its database or API read, so adding that read later cannot hit the
  3 second limit.
* ``/kick``: a moderation command that checks both the user and the
  bot (``has_permissions`` and ``bot_has_permissions``).
* ``/claim``: a cooldown (one use per 60 seconds per user), so the
  cooldown error path has something real to report.
* ``/buy``: autocomplete over a small in-memory catalogue, capped at
  the 25 choices Discord allows.
* ``/boom``: raises on purpose, so the unexpected-error path can be
  seen. It exists only to prove the handler answers when a command
  fails in a way nobody planned for.

Run it with::

    DISCORD_TOKEN=... TEST_GUILD_ID=... python examples/slash_errors.py

``TEST_GUILD_ID`` is optional. With it set, commands sync to that
guild at once. Without it, they sync globally, which can take up to
an hour to show up. The token comes from the environment only.
"""

import logging
import os
from typing import NamedTuple

import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("slash_errors")

CLAIM_COOLDOWN_SECONDS = 60.0


class Item(NamedTuple):
    """One catalogue entry. The id is stable, the name is display only."""

    id: str
    name: str


# Small in-memory catalogue for the /buy autocomplete. Thirty entries,
# so the 25-choice cap in the autocomplete is exercised, not assumed.
ITEMS: tuple[Item, ...] = (
    Item("apple", "Apple"),
    Item("apricot", "Apricot"),
    Item("avocado", "Avocado"),
    Item("banana", "Banana"),
    Item("bread", "Bread"),
    Item("butter", "Butter"),
    Item("carrot", "Carrot"),
    Item("cheese", "Cheese"),
    Item("cherry", "Cherry"),
    Item("chocolate", "Chocolate"),
    Item("coffee", "Coffee"),
    Item("cookie", "Cookie"),
    Item("corn", "Corn"),
    Item("cucumber", "Cucumber"),
    Item("donut", "Donut"),
    Item("egg", "Egg"),
    Item("fish", "Fish"),
    Item("grapes", "Grapes"),
    Item("honey", "Honey"),
    Item("ice-cream", "Ice Cream"),
    Item("jam", "Jam"),
    Item("juice", "Juice"),
    Item("kiwi", "Kiwi"),
    Item("lemon", "Lemon"),
    Item("mango", "Mango"),
    Item("milk", "Milk"),
    Item("noodles", "Noodles"),
    Item("orange", "Orange"),
    Item("pasta", "Pasta"),
    Item("peach", "Peach"),
)


def _permission_names(missing: list[str]) -> str:
    """Turn permission flags such as kick_members into plain words."""
    return ", ".join(name.replace("_", " ") for name in missing)


def error_message(error: BaseException) -> str:
    """Short user-facing text for a command error.

    Pure function, so tests can check every branch without a mock.
    Order matters here: CommandOnCooldown, MissingPermissions, and
    BotMissingPermissions are all subclasses of CheckFailure, so they
    must be checked before the generic CheckFailure branch.
    """
    if isinstance(error, app_commands.CommandOnCooldown):
        return f"Slow down. Try again in {error.retry_after:.0f} seconds."
    if isinstance(error, app_commands.MissingPermissions):
        text = "You do not have permission to use this command."
        if error.missing_permissions:
            text += f" You need: {_permission_names(error.missing_permissions)}."
        return text
    if isinstance(error, app_commands.BotMissingPermissions):
        text = "I do not have permission to do that."
        if error.missing_permissions:
            text += f" I need: {_permission_names(error.missing_permissions)}."
        return text
    if isinstance(error, app_commands.CheckFailure):
        return "You cannot use this command here."
    if isinstance(error, discord.Forbidden):
        return "I tried to do that, but Discord refused. I may be missing a permission."
    return "Something went wrong. The error was logged."


async def answer_error(interaction: discord.Interaction, text: str) -> None:
    """Send an error message to the user, wherever the command got to.

    If the command already answered or deferred, the message must go
    through followup. Sending through response after a defer raises.
    If even the error message cannot be delivered (the interaction
    expired, for example), log it and move on. There is nobody left
    to tell.
    """
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except discord.HTTPException:
        log.warning("Could not answer the failed command.")


async def item_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Suggest catalogue items whose name starts with what was typed.

    Kept fast on purpose: the search runs over an in-memory list, and
    the result is sliced to the 25 choices Discord allows.
    """
    needle = current.lower()
    return [
        app_commands.Choice(name=item.name, value=item.id)
        for item in ITEMS
        if item.name.lower().startswith(needle)
    ][:25]


class ErrorHandling(commands.Cog):
    """Slash commands whose errors always reach the user."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot is awake.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! Latency: {latency} ms")

    @app_commands.command(name="profile", description="Show a member profile.")
    async def profile(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        await interaction.response.defer()
        if user.joined_at is not None:
            joined = user.joined_at.date().isoformat()
        else:
            joined = "unknown"
        await interaction.followup.send(
            f"Profile for {user.display_name} (id {user.id}). Joined: {joined}."
        )

    @app_commands.command(name="kick", description="Remove a member from the server.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        await member.kick(reason=f"Kicked by {interaction.user.id}")
        await interaction.response.send_message(
            f"{member.display_name} was kicked.", ephemeral=True
        )

    @app_commands.command(name="claim", description="Claim a reward. Limited to once a minute.")
    @app_commands.checks.cooldown(
        1, CLAIM_COOLDOWN_SECONDS, key=lambda i: i.user.id
    )
    async def claim(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "Claim recorded. You can claim again in 60 seconds."
        )

    @app_commands.command(name="buy", description="Pick an item from the shop.")
    @app_commands.autocomplete(item=item_autocomplete)
    async def buy(self, interaction: discord.Interaction, item: str) -> None:
        found = next((entry for entry in ITEMS if entry.id == item), None)
        if found is None:
            await interaction.response.send_message(
                "I do not recognise that item. Pick one from the list.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(f"You picked {found.name}.")

    @app_commands.command(
        name="boom", description="Fail on purpose, to show the error handler."
    )
    async def boom(self, interaction: discord.Interaction) -> None:
        raise RuntimeError("boom")

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Answer every error from this cog. No silent failures.

        discord.py wraps exceptions raised inside a command callback
        in CommandInvokeError, so unwrap first to see the real cause.
        Known errors get a short log line. Anything else gets the full
        traceback in the log, and the user gets the generic message.
        """
        if isinstance(error, app_commands.CommandInvokeError):
            original: BaseException = error.original
        else:
            original = error
        if isinstance(
            original,
            (
                app_commands.CheckFailure,
                discord.Forbidden,
            ),
        ):
            log.info(
                "Command %s failed for user %s: %s",
                interaction.command,
                interaction.user.id,
                original,
            )
        else:
            log.exception("Command failed: %s", interaction.command)
        await answer_error(interaction, error_message(original))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ErrorHandling(bot))


class Bot(commands.Bot):
    """Minimal bot that loads the cog and syncs once, at startup."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await self.add_cog(ErrorHandling(self))
        test_guild_id = int(os.environ.get("TEST_GUILD_ID", "0") or 0)
        if test_guild_id:
            guild = discord.Object(id=test_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Commands synced to test guild %s.", test_guild_id)
        else:
            await self.tree.sync()
            log.info("Commands synced globally.")


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("set the DISCORD_TOKEN environment variable")
    Bot().run(token)


if __name__ == "__main__":
    main()
