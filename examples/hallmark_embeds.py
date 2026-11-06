"""Hallmark-themed embeds: a discord.py cog.

Showcases the design-with-hallmark skill
(``skills/design-with-hallmark/SKILL.md``): one Hallmark theme per
feature, applied to Discord embeds through
``skills/design-with-hallmark/scripts/hallmark_theme.py``.

The pick, said in one line before writing code: shop embeds use
Darkroom, profile embeds use Squeeze, both dealt for
"rpg economy shop" (seed 7). Darkroom was dealt 1/3, Squeeze 2/3,
Sport 3/3. One theme per feature, so the two surfaces do not
converge on one look, and each embed carries one accent stripe
only, never a gradient.

The Floor rules from the skill bind every embed here: no invented
numbers (gold and level are read from the ledger and level records
the cog is given, never made up), no eyebrow labels, no
middle-dot meta strings, no em dash anywhere, one fact per field,
and every fact said once.

Run it like the other examples::

    DISCORD_TOKEN=your-bot-token-here python3 examples/hallmark_embeds.py

The cog is also loadable as an extension: ``await setup(bot)``.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

# The helper is stdlib only and lives with its skill. Resolve it
# relative to this file so the example runs from the repo root.
_HELPER_DIR = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "design-with-hallmark"
    / "scripts"
)
if str(_HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(_HELPER_DIR))

from hallmark_theme import deal, discord_embed  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("hallmark_embeds")

# The shop catalogue. These prices are the shop's own data, passed
# in as arguments, not invented per user: a balance is always read
# from the ledger, never typed here.
SHOP_ITEMS: tuple[tuple[str, int, str], ...] = (
    ("Iron Sword", 1200, "+5 attack"),
    ("Healing Potion", 150, "restores 50 HP"),
    ("Torch", 40, "lights dark rooms"),
)

SHOP_THEME = "darkroom"
PROFILE_THEME = "squeeze"
DEAL_KEYWORDS = "rpg economy shop"


def shop_embed_dict(
    items: Sequence[tuple[str, int, str]], gold: int
) -> dict:
    """Build the shop embed as a discord.py-ready dict.

    ``items`` is the shop catalogue, ``gold`` is the caller's real
    balance. ``discord_embed()`` raises ``ValueError`` if the copy
    breaks a Discord limit; fix the copy, do not catch and send
    anyway.
    """
    fields = [
        (name, f"{price:,} gold, {detail}", True)
        for name, price, detail in items
    ]
    fields.append(("Your gold", f"{gold:,} gold", False))
    return discord_embed(
        SHOP_THEME,
        title="Shop",
        description="Spend gold on things that do something.",
        fields=fields,
        footer="Prices change when the shop restocks.",
    )


def profile_embed_dict(
    display_name: str,
    level: int,
    gold: int,
    avatar_url: str | None = None,
) -> dict:
    """Build the profile embed as a discord.py-ready dict.

    One fact per field, each with its unit. The thumbnail is the
    member's real avatar, or absent when there is none to show.
    """
    return discord_embed(
        PROFILE_THEME,
        title=display_name,
        description="Your record in this server, kept in one place.",
        fields=[
            ("Level", str(level), True),
            ("Gold", f"{gold:,} gold", True),
        ],
        footer="Your gold changes when you earn or spend it.",
        thumbnail=avatar_url,
    )


def deal_embed_dict(
    keywords: str, picks: Sequence[Mapping[str, object]]
) -> dict:
    """Build the theme-deal embed as a discord.py-ready dict.

    ``picks`` is a hand from ``deal()``: three discord-strong
    themes. The embed takes its stripe from the first pick, and
    each field says one pick's name, accent, and material line.
    """
    if not picks:
        raise ValueError("a deal needs at least one theme")
    fields = []
    for pick in picks:
        material = str(pick["material"])
        if not material.endswith("."):
            material += "."
        fields.append(
            (
                str(pick["name"]),
                f"Accent {pick['accent']}. {material}",
                False,
            )
        )
    return discord_embed(
        str(picks[0]["slug"]),
        title="Theme deal",
        description="Three themes that fit those words. Pick one.",
        fields=fields,
        footer="Deal again for a fresh hand.",
    )


def to_embed(embed_dict: dict) -> discord.Embed:
    """Turn a ``discord_embed()`` dict into a real ``discord.Embed``."""
    return discord.Embed.from_dict(embed_dict)


class HallmarkEmbeds(commands.Cog):
    """Shop, profile, and theme-deal commands in Hallmark themes.

    ``ledger`` maps a user id to their gold, ``levels`` maps a user
    id to their level. Both are the bot's records: the commands
    read numbers from them and never invent any. A user with no
    record starts at level 1 with 0 gold.
    """

    def __init__(
        self,
        bot: commands.Bot,
        ledger: dict[int, int] | None = None,
        levels: dict[int, int] | None = None,
    ) -> None:
        self.bot = bot
        self.ledger = {} if ledger is None else ledger
        self.levels = {} if levels is None else levels

    @app_commands.command(name="shop", description="Browse the shop.")
    async def shop(self, interaction: discord.Interaction) -> None:
        gold = self.ledger.get(interaction.user.id, 0)
        embed = to_embed(shop_embed_dict(SHOP_ITEMS, gold))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="profile", description="Show your adventurer record."
    )
    async def profile(self, interaction: discord.Interaction) -> None:
        user = interaction.user
        embed = to_embed(
            profile_embed_dict(
                user.display_name,
                self.levels.get(user.id, 1),
                self.ledger.get(user.id, 0),
                avatar_url=user.display_avatar.url,
            )
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="themes", description="Deal three Hallmark themes for these words."
    )
    @app_commands.describe(keywords="Words that describe the bot's job.")
    async def themes(
        self,
        interaction: discord.Interaction,
        keywords: str = DEAL_KEYWORDS,
    ) -> None:
        picks = deal(keywords)
        embed = to_embed(deal_embed_dict(keywords, picks))
        await interaction.response.send_message(embed=embed)

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        log.warning("Command failed: %s", error)
        message = "Sorry, that command hit a problem. Try again."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(
                    message, ephemeral=True
                )
        except discord.HTTPException:
            log.warning("Could not answer the failed command.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HallmarkEmbeds(bot))


class Bot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await setup(self)
        await self.tree.sync()
        log.info("Commands synced globally.")

    async def on_ready(self) -> None:
        log.info(f"{self.user} is online")


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("set the DISCORD_TOKEN environment variable")
    Bot().run(token)


if __name__ == "__main__":
    main()
