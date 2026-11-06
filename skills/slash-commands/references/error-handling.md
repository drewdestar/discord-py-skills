## Error handling that answers the user

```python
import logging

log = logging.getLogger(__name__)

class General(commands.Cog):
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
```

- Every command error must produce a user-visible answer. A command that fails silently looks like a dead bot.
- Log the full traceback for unexpected errors (`log.exception`), but send the user a short message. Stack traces in chat leak internals.
- `cog_app_command_error` handles errors for one cog. A global handler is `CommandTree.on_error`: subclass the tree and pass it as `tree_cls`. There is no `on_app_command_error` on the bot — that name does not exist in discord.py.

```python
class MyTree(app_commands.CommandTree):
    async def on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        log.exception("Command failed: %s", interaction.command)
        text = "Something went wrong. The error was logged."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)

bot = commands.Bot(command_prefix="!", intents=intents, tree_cls=MyTree)
```

- Use the cog handler for cog-specific messages and the global one as a backstop, not both for the same error.
