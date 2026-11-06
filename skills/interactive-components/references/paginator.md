## A paginator: the pattern everything else copies

```python
import discord
from discord.ext import commands

class PaginatorView(discord.ui.View):
    """Page through a list of embeds with buttons. Author-only."""

    def __init__(self, author_id: int, pages: list[discord.Embed]) -> None:
        super().__init__(timeout=180)  # buttons die after 3 minutes
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
        # A View has no .message attribute of its own. The command
        # that sent it stores one (see below); on timeout we edit
        # that message so the user sees the buttons go dead instead
        # of clicking into silence.
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
```

Use it from a command:

```python
@app_commands.command(name="leaderboard", description="Top balances, page by page.")
async def leaderboard(self, interaction: discord.Interaction) -> None:
    rows = await top_balances(self.bot.db, limit=50)
    page_count = (len(rows) + 4) // 5
    pages = [
        build_page(rows[i:i + 5], i // 5, page_count)
        for i in range(0, len(rows), 5)
    ]
    view = PaginatorView(author_id=interaction.user.id, pages=pages)
    await interaction.response.send_message(embed=pages[0], view=view)
    # Keep the message so on_timeout can edit it and show the buttons
    # going dead. A View has no .message of its own; store it here.
    view.message = await interaction.original_response()
```

Rules that matter:

- **`interaction_check` is the author gate.** Without it, anyone can
  turn someone else's pages, confirm someone else's purchase, or
  close someone else's form. Every View that acts for one user needs
  this check. Answer the rejected user ephemerally; silence looks
  like a broken button.
- **A button click must answer within 3 seconds** or defer, exactly
  like a slash command. `interaction.response.edit_message()` is the
  normal answer for a button: it edits the message the button sits on.
- **Disable at the edges.** A "Previous" button on page 1 that does
  nothing is a broken button. `_refresh_buttons` runs on every page
  change, and `on_timeout` disables everything when the View dies.
- **One View, one job.** A View that paginates, confirms, and
  opens a modal is three Views sharing one class. Split it.
