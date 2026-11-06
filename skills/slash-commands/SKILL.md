---
name: slash-commands
description: "Add slash commands to a discord.py bot: app_commands, groups, checks, autocomplete, cooldowns, and error handling that answers the user instead of failing silently. Use when the user says 'add a /balance command', 'my command does not show up', or 'interaction failed'. Do NOT use for prefix commands or for the bot skeleton; use build-discord-bot for setup."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, no paid services"
metadata:
  version: "0.5.0"
  author: "drewdestar"
---

# Slash Commands

discord.py slash commands are `app_commands`. This skill covers the patterns that keep them fast, permission-aware, and honest about errors.

## A basic command

```python
import discord
from discord import app_commands
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot is awake.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! Latency: {latency} ms")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
```

## Sync: test guild first, global on release

```python
# In setup_hook or a sync command:
if config.TEST_GUILD_ID:
    guild = discord.Object(id=config.TEST_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)   # instant in the test guild
else:
    await bot.tree.sync()              # global, up to 1 hour to propagate
```

- Never sync globally on every startup during development. Global propagation is slow and every sync is a rate-limited API call.
- Keep one test guild id in the environment and sync to it while building. Sync globally only when releasing.
- If a command's callback changed but Discord still runs the old version, that is `CommandSignatureMismatch`: sync again in the same scope (test guild or global) after changing a signature. Changing code without re-syncing changes nothing users see.
- Never sync on every message or every command invocation. Sync once at startup (test guild) or once on release (global).
- Persistent views (buttons that must work after a restart) need `bot.add_view()` in `setup_hook` or `on_ready`, with a stable `custom_id`. A view registered only inside a command dies with the restart.

## Verify live

- The command appears in the test guild immediately after a guild sync. Global sync can take up to an hour; that is normal, not a bug.
- Run the command once in Discord. It answers within 3 seconds or defers first.
- Run it with a user who lacks permission. The user sees the permission error, not silence.
- Change the command description, re-sync, and confirm Discord shows the new text. This proves the sync path works.

## Quality bar (no slop)

- Every command answers or shows an error. No dead commands.
- No invented data in replies: a value shown to a user comes from the database or the API, never from a placeholder.
- No em dash in any message or embed the bot sends.

## Defer when the command is slow

Discord gives a command 3 seconds to answer. Anything slower must defer first:

```python
@app_commands.command(name="profile", description="Show a user profile.")
async def profile(self, interaction: discord.Interaction, user: discord.Member) -> None:
    await interaction.response.defer()          # "Bot is thinking..."
    data = await fetch_profile(user.id)         # slow work happens here
    await interaction.followup.send(embed=build_embed(data))
```

- `defer()` then `followup.send()` is the pattern for database reads, API calls, and image generation.
- A command that does fast work answers directly with `interaction.response.send_message()`. Do not defer fast commands; the extra round trip adds visible delay.
- Once deferred, the first real answer must go through `followup`. Calling `response.send_message()` after a defer raises an error.

## Checks: who may run it

```python
@app_commands.command(name="kick", description="Remove a member from the server.")
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.checks.bot_has_permissions(kick_members=True)
async def kick(self, interaction: discord.Interaction, member: discord.Member) -> None:
    await member.kick(reason=f"Kicked by {interaction.user}")
    await interaction.response.send_message(f"{member} was kicked.", ephemeral=True)
```

- `has_permissions` checks the user. `bot_has_permissions` checks the bot. Use both for moderation commands; a command that passes the user check and then fails on the bot side is a confusing half-error.
- Custom predicates use `@app_commands.check(predicate)`. Keep predicates fast and side-effect free; they run before the command body.
- Important: **checks are not evaluated for autocomplete interactions.** If an autocomplete list must hide choices from users who lack permission, filter inside the autocomplete callback itself. Do not rely on the command check to hide autocomplete results.

## Autocomplete

```python
async def item_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    items = await search_items(current)   # keep this fast, under 1 second
    return [
        app_commands.Choice(name=item.name, value=item.id)
        for item in items[:25]            # Discord allows at most 25 choices
    ]

@app_commands.command(name="buy", description="Buy an item from the shop.")
@app_commands.autocomplete(item=item_autocomplete)
async def buy(self, interaction: discord.Interaction, item: str) -> None:
    ...
```

- Autocomplete must answer quickly. Do the search against an in-memory list or a fast indexed query, never a slow scan.
- At most 25 choices. Slice the list; Discord rejects more.
- The `value` is what the command receives. The `name` is what the user sees. Keep values stable ids, not display names, so renaming an item does not break stored data.

## Cooldowns

```python
@app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
```

- One use per 60 seconds per user, in this example. Cooldowns stop one user from spamming a shared resource (daily claims, shop purchases, giveaways).
- A cooldown error is an `app_commands.CommandOnCooldown` error. Handle it in the error handler with the retry time, so the user sees "try again in 42 seconds" instead of silence.

## Error handling that answers the user

Error handling that answers the user: the cog handler and the global tree handler. See `references/error-handling.md`.

## Groups

```python
shop = app_commands.Group(name="shop", description="Shop commands.")

@shop.command(name="buy", description="Buy an item.")
async def shop_buy(interaction: discord.Interaction, item: str) -> None:
    ...

bot.tree.add_command(shop)  # or add the group inside a cog with GroupCog
```

- Groups keep the command list readable once a bot passes ten commands. One group per feature area (shop, profile, admin).
- Group names and command names must be lowercase, no spaces, 1 to 32 characters. Discord rejects anything else at sync time with an error that names the command.

## Checklist

- [ ] Every command answers within 3 seconds or defers
- [ ] Every error path sends the user a message
- [ ] Moderation commands check both user and bot permissions
- [ ] Autocomplete returns at most 25 choices and answers fast
- [ ] Sync targets the test guild during development, global on release
- [ ] Command names are lowercase, no spaces
