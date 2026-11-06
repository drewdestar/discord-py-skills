"""Button pagination plus a jump-to-page select menu.

Showcases the interactive-components skill: a ``discord.ui.View``
that pages through leaderboard embeds with Previous/Next buttons and
a select menu that jumps straight to a page.

Run it with a bot token in the environment:

    DISCORD_TOKEN=... python examples/pagination.py

Then use ``/leaderboard`` in a server. The leaderboard rows here are
sample data: replace :func:`load_leaderboard_rows` with a real
database query in a production bot. The pagination logic itself
(:func:`build_pages`, :class:`PaginatorView`, :class:`PageSelect`)
does not care where the rows came from.

Patterns taken from ``skills/interactive-components/SKILL.md``:

- every component lives in one ``discord.ui.View``;
- ``interaction_check`` gates the View to the command author;
- buttons disable at the edges and on timeout;
- the select lists at most 25 options (one per page), so more than
  25 pages is rejected in :func:`build_pages` instead of silently
  dropping pages from the menu;
- there is no ``discord.ext.pages`` in discord.py, so the paginator
  is hand-rolled on a View.
"""

import logging
import os
from dataclasses import dataclass

import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("pagination")

PAGE_SIZE = 5
MAX_PAGES = 25  # a select menu holds at most 25 options, one per page
VIEW_TIMEOUT = 180.0  # seconds; buttons die after 3 minutes


@dataclass(frozen=True)
class LeaderboardRow:
    """One leaderboard entry: a display name and a point total."""

    name: str
    points: int


# Sample data for the example. Replace load_leaderboard_rows with a
# real query (for example, top balances from the bot database) when
# this becomes a real command.
SAMPLE_LEADERBOARD = [
    LeaderboardRow("Ada", 4820),
    LeaderboardRow("Ben", 4310),
    LeaderboardRow("Cleo", 3985),
    LeaderboardRow("Dara", 3740),
    LeaderboardRow("Eli", 3515),
    LeaderboardRow("Faye", 3290),
    LeaderboardRow("Gus", 3010),
    LeaderboardRow("Hana", 2875),
    LeaderboardRow("Ivo", 2640),
    LeaderboardRow("Jae", 2410),
    LeaderboardRow("Kira", 2185),
    LeaderboardRow("Leo", 1990),
]


async def load_leaderboard_rows() -> list[LeaderboardRow]:
    """Load the rows to paginate.

    Sample data in this example. In a real bot, query the database
    here (for example, ``SELECT name, points ... ORDER BY points
    DESC``) and return the rows in ranked order.
    """
    return list(SAMPLE_LEADERBOARD)


def chunk_rows(
    rows: list[LeaderboardRow], page_size: int = PAGE_SIZE
) -> list[list[LeaderboardRow]]:
    """Split rows into pages of at most ``page_size`` rows."""
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    return [rows[i : i + page_size] for i in range(0, len(rows), page_size)]


def build_page(
    page_rows: list[LeaderboardRow],
    page_index: int,
    page_count: int,
    start_rank: int,
) -> discord.Embed:
    """Build the embed for one page.

    ``start_rank`` is the 1-based rank of the first row on the page,
    so ranks keep counting across pages instead of restarting at 1.
    """
    lines = [
        f"{start_rank + i}. {row.name} - {row.points:,} points"
        for i, row in enumerate(page_rows)
    ]
    embed = discord.Embed(
        title="Leaderboard",
        description="\n".join(lines),
        colour=discord.Colour.blurple(),
    )
    embed.set_footer(text=f"Page {page_index + 1} of {page_count}")
    return embed


def build_pages(
    rows: list[LeaderboardRow], page_size: int = PAGE_SIZE
) -> list[discord.Embed]:
    """Build one embed per page for ``rows``.

    An empty leaderboard still yields one page that says so, so the
    command always has something to send. More than 25 pages is
    rejected: the jump-to-page select can list at most 25 options,
    one per page, and silently dropping pages would be a broken menu.
    """
    chunks = chunk_rows(rows, page_size)
    if not chunks:
        return [
            discord.Embed(
                title="Leaderboard",
                description="No entries yet.",
                colour=discord.Colour.blurple(),
            )
        ]
    if len(chunks) > MAX_PAGES:
        raise ValueError(
            f"{len(chunks)} pages is too many: the page select "
            f"holds at most {MAX_PAGES} options"
        )
    return [
        build_page(chunk, index, len(chunks), index * page_size + 1)
        for index, chunk in enumerate(chunks)
    ]


class PageSelect(discord.ui.Select):
    """Jump-to-page dropdown. One option per page, at most 25."""

    def __init__(self, page_count: int) -> None:
        options = [
            discord.SelectOption(
                label=f"Page {page + 1}",
                value=str(page),
                description=f"Jump to page {page + 1} of {page_count}",
            )
            for page in range(page_count)
        ]
        super().__init__(
            placeholder="Jump to a page",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        # self.view is the PaginatorView this select was added to.
        view = self.view
        assert isinstance(view, PaginatorView)
        await view.go_to_page(interaction, int(self.values[0]))


class PaginatorView(discord.ui.View):
    """Page through embeds with buttons and a jump-to-page select.

    Author-only: ``interaction_check`` turns away anyone who did
    not run the command. Buttons disable at the first and last
    page, and everything disables when the View times out.
    """

    def __init__(
        self,
        author_id: int,
        pages: list[discord.Embed],
        timeout: float = VIEW_TIMEOUT,
    ) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.pages = pages
        self.current = 0
        # A View has no .message of its own. The command that sends
        # it stores the message here so on_timeout can edit it.
        self.message: discord.Message | None = None
        self.page_select = PageSelect(len(pages))
        self.add_item(self.page_select)
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

    async def go_to_page(
        self, interaction: discord.Interaction, index: int
    ) -> None:
        """Show page ``index`` (0-based), clamped to the valid range."""
        self.current = max(0, min(index, len(self.pages) - 1))
        await self._show_current_page(interaction)

    async def _show_current_page(self, interaction: discord.Interaction) -> None:
        self._refresh_buttons()
        await interaction.response.edit_message(
            embed=self.pages[self.current], view=self
        )

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                log.warning("Could not disable the timed out paginator.")

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.go_to_page(interaction, self.current - 1)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.go_to_page(interaction, self.current + 1)


class LeaderboardCog(commands.Cog):
    """Slash command that sends the first page with its View."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="leaderboard", description="Show the leaderboard, page by page."
    )
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        rows = await load_leaderboard_rows()
        pages = build_pages(rows)
        view = PaginatorView(author_id=interaction.user.id, pages=pages)
        await interaction.response.send_message(embed=pages[0], view=view)
        # Keep the message so on_timeout can edit it and show the
        # buttons going dead.
        view.message = await interaction.original_response()


class PaginationBot(commands.Bot):
    """Minimal bot that hosts the leaderboard command."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await self.add_cog(LeaderboardCog(self))
        await self.tree.sync()
        log.info("Commands synced globally.")

    async def on_ready(self) -> None:
        log.info(f"{self.user} is online")


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("set the DISCORD_TOKEN environment variable")
    PaginationBot().run(token)


if __name__ == "__main__":
    main()
