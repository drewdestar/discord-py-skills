---
name: interactive-components
description: "Add interactive components to a discord.py bot: buttons, Views, modals, selects, and pagination. Use when the user says 'add buttons', 'make a paginated leaderboard', 'my buttons stop working', 'add a form/modal', or 'add a dropdown'. Do NOT use for the command itself; use slash-commands for the command and this skill for what happens after the user clicks."
license: MIT
compatibility: "discord.py 2.7.1, Python 3.10+, no paid services"
metadata:
  version: "0.5.0"
  author: "drewdestar"
---

# Interactive Components

A slash command that only sends text is a dead end. Buttons, selects,
and modals turn it into an interface: paginate a leaderboard, confirm
a purchase, collect input in a form. This skill covers the patterns
that keep components working after restarts, after timeouts, and for
the right user only.

## The one rule

Every component belongs to a `discord.ui.View`. The View holds the
buttons, owns the timeout, and decides who may click. There is no
other way to attach a button to a message in discord.py.

## A paginator: the pattern everything else copies

The paginator pattern everything else copies: author gate, edge disabling, timeout. See `references/paginator.md`.

## There is no built-in paginator in discord.py

Say this plainly, because 2026 tutorials get it wrong:
**`discord.ext.pages` does not exist in discord.py.** It is a py-cord
module. `from discord.ext import pages` raises ImportError on
discord.py 2.7.1. There is no official paginator to import. The
hand-rolled View above is the correct pattern, or a third-party
library (`discord-pager`, `dpy-paginator`) if the project already
depends on one. Do not write `from discord.ext import pages` in a
discord.py bot, no matter how confident the tutorial looks.

## Persistent views: buttons that survive a restart

A normal View dies with the process. A persistent View is re-registered
on startup:

```python
class ConfirmView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)  # no timeout: persistent

    @discord.ui.button(
        label="Confirm", style=discord.ButtonStyle.green,
        custom_id="confirm_purchase",  # stable id, never random
    )
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message("Confirmed.", ephemeral=True)

# In setup_hook, before the bot connects:
bot.add_view(ConfirmView())
```

- `timeout=None` and a **stable `custom_id`** are both required.
  A random or missing `custom_id` cannot be matched after a restart,
  and Discord drops the button silently.
- Register with `bot.add_view()` in `setup_hook` (or `on_ready`),
  never inside a command. A View registered only inside a command
  dies with the restart, which is the normal kind.
- Persistent Views cannot hold per-user state in the object: the View
  is rebuilt from the `custom_id` alone. Anything the button needs
  (which purchase, whose) must come from the database, keyed by the
  interaction or by data encoded in the `custom_id` itself.
- Only five action rows per message, five buttons per row. A View
  with more items than that fails when you add the item
  (`add_item` raises ValueError: width over 5 per row, or over 25
  children in the View).

## Modals: forms, not commands

Modals: forms, not commands, with `discord.TextStyle` and the 5-item limit. See `references/modals.md`.

## Selects: dropdowns and pickers

```python
class RoleSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="Announcements", value="news"),
            discord.SelectOption(label="Events", value="events"),
        ]
        super().__init__(placeholder="Pick a channel role", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        await assign_role(interaction.user, self.values[0])
        await interaction.response.send_message(
            f"Added {self.values[0]}.", ephemeral=True
        )

view = discord.ui.View()
view.add_item(RoleSelect())
await interaction.response.send_message("Choose:", view=view, ephemeral=True)
```

- At most 25 options per select. More than that needs pagination or
  a modal with a text field instead.
- `discord.ui.UserSelect`, `ChannelSelect`, and `RoleSelect` pick
  real Discord objects instead of strings. Use them when the choice
  is a user, a channel, or a role; a string select for those is a
  list that goes stale.
- `self.values` is the list the user picked. Read it in the
  callback, never from the message.

## Components V2: the new layout system

discord.py 2.6+ (verified on 2.7.1) supports Discord's Components V2:
layout components that replace embeds in a message.

```python
container = discord.ui.Container(
    discord.ui.TextDisplay("**Leaderboard**"),
    discord.ui.Section(
        discord.ui.TextDisplay("Top players this week"),
        accessory=discord.ui.Button(label="Refresh", custom_id="refresh_lb"),
    ),
)
view = discord.ui.LayoutView()
view.add_item(container)
await interaction.response.send_message(view=view)
```

- `LayoutView` takes **no constructor arguments**: passing the container to the constructor raises `TypeError: __init__() takes 1 positional argument but 2 were given` (verified on discord.py 2.7.1). Build the view empty, then `add_item` the container.

- The classes live directly under **`discord.ui`**: `Container`,
  `TextDisplay`, `Section`, `ActionRow`, `Separator`,
  `MediaGallery`, `Thumbnail`, `File`. There is no
  `discord.ui.layout` module.
- A Components V2 message **cannot carry embeds**. Use V2 when the
  whole message is a layout; use embeds + a normal View when the
  message is an embed with buttons. Do not mix them in one message.
- V2 needs discord.py 2.6+ (changelog v2.6.0, GH-10166). Whether
  every client version renders V2 layouts is UNVERIFIED from this
  VM; test on the clients your users use. The starter bot and this
  skill default to embeds + Views, which work everywhere; reach
  for V2 only when the layout needs it.

## Portability: OSes, platforms, agents, languages

Portability: operating systems, platforms, agents, languages, and versions. See `references/portability.md`.

## Checklist

- [ ] Every View has an `interaction_check` when it acts for one user
- [ ] Buttons disable at the edges and on timeout
- [ ] Persistent Views use `timeout=None`, a stable `custom_id`, and `bot.add_view()` in `setup_hook`
- [ ] Modals use `discord.TextStyle`, never `TextInputStyle`
- [ ] No `from discord.ext import pages` anywhere: it does not exist in discord.py
- [ ] Selects have at most 25 options
- [ ] Every click answers within 3 seconds or defers

## Verify live

1. Run the command, click Next to the last page: the Next button
   is disabled and Previous works.
2. Have another user click the buttons: they get the "only the
   person who ran the command" message, and the page does not move.
3. Wait 3 minutes (or set a 5 second timeout while testing):
   the buttons disable themselves.
4. Restart the bot, then click a persistent button from before the
   restart: it still answers. If it does nothing, the View was not
   re-registered in `setup_hook` or the `custom_id` changed.
5. Submit a modal: the answer arrives and the data is in the
   database, not just in the reply text.

Report what you observed for each step. "It should work" is not an
observation.

## Quality bar (no slop)

- **Every click answers.** A button that does nothing is a dead bot,
  even if the command that sent it worked.
- **No invented data in components.** A button label, a page count,
  or a select option shown to a user comes from the database or the
  API, never from a placeholder.
- **No em dash** in any label, placeholder, or reply the bot sends.
- **Verify before claiming done.** Run the steps above and report the
  evidence. A bare "done" with no observation is not done.
