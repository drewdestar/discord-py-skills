## Mocking an interaction

```python
from unittest.mock import AsyncMock, MagicMock

import discord
from discord import app_commands
from discord.ext import commands

from cogs.general import General  # the /ping cog from build-discord-bot

def make_bot() -> MagicMock:
    bot = MagicMock()
    bot.latency = 0.042
    return bot

def make_interaction(user_id: int = 1) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.response = AsyncMock()
    # is_done() is a SYNC method on the real response object. An
    # AsyncMock's auto-created is_done returns a coroutine (always
    # truthy, never awaited), which would send every error down the
    # followup branch. Override it with a plain MagicMock.
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = AsyncMock()
    return interaction

async def test_ping_answers():
    cog = General(bot=make_bot())
    interaction = make_interaction()
    await cog.ping.callback(cog, interaction)
    interaction.response.send_message.assert_awaited_once_with(
        "Pong! Latency: 42 ms")
    text = interaction.response.send_message.await_args.args[0]
    assert text == "Pong! Latency: 42 ms"


class CooldownCog(commands.Cog):
    """Minimal cog with a cooldown error handler.

    The full handler (cooldown, permissions, check failure,
    fallback) lives in the slash-commands skill; this is the
    cooldown branch only, so the test below has a handler to
    call. The starter's General has no cog_app_command_error
    at all — a test that calls it on General raises
    AttributeError, not a cooldown reply.
    """

    @app_commands.command(name="ping", description="Check the bot is awake.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Pong!")

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            text = f"Slow down. Try again in {error.retry_after:.0f} seconds."
        else:
            raise error
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


async def test_cooldown_error_answers():
    cog = CooldownCog()
    interaction = make_interaction()
    error = app_commands.CommandOnCooldown(
        app_commands.Cooldown(1, 60.0), 30.0)
    await cog.cog_app_command_error(interaction, error)
    interaction.response.send_message.assert_awaited_once()
    text = interaction.response.send_message.await_args.args[0]
    assert "Slow down" in text
```

- `General` takes the bot (`__init__(self, bot)`); pass a
  `MagicMock` bot with a fixed `latency`, exactly as the starter's
  `test_cogs.py` does — a bare `MagicMock` latency round-trips as
  `<MagicMock …>` text and the test passes vacuously.
- Call the command callback directly: `cog.ping.callback(cog, interaction)`. This exercises the real command code with a fake interaction, no network involved.
- `.callback()` bypasses checks, cooldowns, and error handlers — it calls the command body and nothing else. Test error paths by invoking the check predicate or `cog_app_command_error` directly, as the cooldown test above does; do not call `.callback()` and expect a cooldown to fire.
- Assert on what the user would see (the message text), not on internal calls. If the test asserts the bot called an internal helper, it breaks on every refactor.
- `AsyncMock` for `response` and `followup`: `send_message` and `defer` are coroutines, and a plain `MagicMock` for them returns a non-awaitable that fails with a confusing error.
- The error-path test is the seam the "Tests must be able to fail" section demands: call `cog_app_command_error` directly with a real `CommandOnCooldown` (constructed from a `Cooldown` + retry seconds) and assert the user-facing text.
