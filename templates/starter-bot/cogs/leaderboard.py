"""Leaderboard: /leaderboard pages through the richest balances.

Uses the PaginatorView pattern from skills/interactive-components:
author-only buttons, disabled at the edges, dead on timeout.
"""

import discord
from discord import app_commands
from discord.ext import commands

import db as db_module

PAGE_SIZE = 5


def build_page(
    rows: list[tuple[int, int]], page_index: int, page_count: int
) -> discord.Embed:
    """One leaderboard page. Rows are (user_id, balance) pairs."""
    embed = discord.Embed(
        title="Leaderboard",
        description=f"Page {page_index + 1} of {page_count}",
    )
    start = page_index * PAGE_SIZE
    for offset, (user_id, balance) in enumerate(rows):
        embed.add_field(
            name=f"#{start + offset + 1}",
            value=f"<@{user_id}> - {balance} gold",
            inline=False,
        )
    return embed


class PaginatorView(discord.ui.View):
    """Page through embeds with buttons. Author-only."""

    def __init__(self, author_id: int, pages: list[discord.Embed]) -> None:
        super().__init__(timeout=180)
        self.author_id = author_id
        self.pages = pages
        self.current = 0
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        self.prev_button.disabled = self.current == 0
        self.next_button.disabled = self.current == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the person who ran the command can turn these pages.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if getattr(self, "message", None) is not None:
            await self.message.edit(view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.current -= 1
        self._refresh_buttons()
        await interaction.response.edit_message(
            embed=self.pages[self.current], view=self
        )

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.current += 1
        self._refresh_buttons()
        await interaction.response.edit_message(
            embed=self.pages[self.current], view=self
        )


class Leaderboard(commands.Cog):
    """Leaderboard commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="leaderboard", description="Show the richest users, page by page."
    )
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        rows = await db_module.top_balances(self.bot.db, limit=50)
        if not rows:
            await interaction.response.send_message(
                "Nobody has any gold yet."
            )
            return
        pages = [
            build_page(rows[i : i + PAGE_SIZE], i // PAGE_SIZE, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
            for i in range(0, len(rows), PAGE_SIZE)
        ]
        view = PaginatorView(author_id=interaction.user.id, pages=pages)
        await interaction.response.send_message(embed=pages[0], view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
