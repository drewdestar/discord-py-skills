#!/usr/bin/env python3
"""Tests for examples/pagination.py.

Stdlib only; run from the repo root on a plain VM with no discord.py
installed:
    python3 -m unittest tests.test_example_pagination -v

discord.py is NOT imported. The repo rule is that every test runs
with the standard library alone, so a small stand-in for the
discord.py surface the example touches is built below and installed
in ``sys.modules`` before the example module is imported. This
follows the same pattern as tests/test_example_human_replies.py.
The stand-in covers only what the example uses (``Embed``,
``Colour``, ``SelectOption``, ``discord.ui.View``/``button``/
``Select``/``Button``, ``ButtonStyle``, ``Interaction``, ``Message``,
``Intents``, ``HTTPException``, ``app_commands.command``,
``commands.Cog``/``Bot``), and its shapes were checked against the
real discord.py 2.5.2 before the stub was written: a button click
calls the method as ``func(view, interaction, button)``; buttons
are reachable as instance attributes (``view.prev_button``) and
start enabled unless disabled; ``Select.values`` is the picked
list; ``InteractionResponse.edit_message`` edits the message the
component sits on; ``app_commands.command`` keeps ``.callback``.
One deliberate divergence: the stub View does not require a
running event loop to construct, while real discord.py 2.5.2
raises RuntimeError outside a loop. No token, no network, no live
bot. Commands are called through their callbacks with mocked
interactions, following skills/testing. Expected strings come from
this file, never recomputed from the code under test, so a wording
change turns a test red.
"""

import os
import re
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


def _build_discord_stub():
    """Build the minimal discord.py stand-in used by these tests.

    Returns a mapping of module name to module object. Only the
    names the example module touches at import time or in the tested
    paths are faked; anything else raises AttributeError, which is
    the point: a test that reaches past the faked surface fails
    loudly instead of silently passing against a made-up API.
    """
    discord_mod = types.ModuleType("discord")
    app_commands_mod = types.ModuleType("discord.app_commands")
    ui_mod = types.ModuleType("discord.ui")
    ext_mod = types.ModuleType("discord.ext")
    commands_mod = types.ModuleType("discord.ext.commands")

    discord_mod._is_test_stub = True

    class Interaction:
        # Class attributes only: MagicMock(spec=Interaction) allows
        # exactly these names, which is the surface the example uses.
        user = None
        response = None
        followup = None
        original_response = None
        command = None
        guild = None

    class Message:
        pass

    class HTTPException(Exception):
        pass

    class Intents:
        def __init__(self):
            self.members = False

        @classmethod
        def default(cls):
            return cls()

    class ButtonStyle:
        primary = 1
        secondary = 2
        success = 3
        danger = 4
        link = 5
        # Aliases discord.py itself defines.
        blurple = primary
        gray = secondary
        grey = secondary
        green = success
        red = danger

    class Colour:
        def __init__(self, value=0):
            self.value = value

        @classmethod
        def blurple(cls):
            return cls(0x5865F2)

    class Embed:
        def __init__(self, *, title=None, description=None, colour=None):
            self.title = title
            self.description = description
            self.colour = colour
            self._footer_text = None

        def set_footer(self, *, text=None, **_kwargs):
            self._footer_text = text

        @property
        def footer(self):
            return SimpleNamespace(text=self._footer_text)

    class SelectOption:
        def __init__(self, *, label, value, description=None, **_kwargs):
            self.label = label
            self.value = value
            self.description = description

    class AppCommandError(Exception):
        pass

    class Command:
        """Stand-in for app_commands.Command: keeps the callback and
        the name, which is what the tests call and read."""

        def __init__(self, func, name, description):
            self.callback = func
            self.name = name
            self.description = description

    def command(name=None, description=None, **_kwargs):
        def decorator(func):
            return Command(func, name or func.__name__, description)

        return decorator

    app_commands_mod.AppCommandError = AppCommandError
    app_commands_mod.Command = Command
    app_commands_mod.command = command

    class Button:
        def __init__(self, label, style, custom_id, func, view):
            self.label = label
            self.style = style
            self.custom_id = custom_id
            self.disabled = False
            self._func = func
            self.view = view

        async def callback(self, interaction):
            return await self._func(self.view, interaction, self)

    def button(*, label=None, style=None, custom_id=None, **_kwargs):
        def decorator(func):
            func.__discord_button__ = (label, style, custom_id)
            return func

        return decorator

    class Select:
        def __init__(
            self,
            *,
            placeholder=None,
            options=None,
            min_values=1,
            max_values=1,
            **_kwargs
        ):
            self.placeholder = placeholder
            self.options = list(options or [])
            self.min_values = min_values
            self.max_values = max_values
            self.disabled = False
            self._values = []
            self.view = None

        @property
        def values(self):
            return self._values

        async def callback(self, interaction):
            pass

    class View:
        def __init__(self, *, timeout=180.0):
            self.timeout = timeout
            self.children = []
            # Collect button-decorated methods in definition order
            # and expose each Button as an instance attribute, as
            # real discord.py does (view.prev_button is the Button).
            seen = set()
            for klass in type(self).__mro__:
                for attr_name, member in vars(klass).items():
                    if attr_name in seen:
                        continue
                    spec = getattr(member, "__discord_button__", None)
                    if spec is not None:
                        seen.add(attr_name)
                        label, style, custom_id = spec
                        item = Button(label, style, custom_id, member, self)
                        self.children.append(item)
                        setattr(self, attr_name, item)

        def add_item(self, item):
            item.view = self
            self.children.append(item)

        async def interaction_check(self, interaction):
            return True

        async def on_timeout(self):
            pass

    ui_mod.Button = Button
    ui_mod.ButtonStyle = ButtonStyle
    ui_mod.Select = Select
    ui_mod.SelectOption = SelectOption
    ui_mod.View = View
    ui_mod.button = button

    class _CogMeta(type):
        def __new__(mcls, name, bases, attrs):
            cls = super().__new__(mcls, name, bases, attrs)
            found = [v for v in attrs.values() if isinstance(v, Command)]
            for base in bases:
                found.extend(getattr(base, "__cog_app_commands__", []))
            cls.__cog_app_commands__ = found
            return cls

    class Cog(metaclass=_CogMeta):
        pass

    class _Tree:
        def __init__(self):
            self.synced = []

        async def sync(self, guild=None):
            self.synced.append(guild)

    class Bot:
        def __init__(self, command_prefix=None, intents=None, **kwargs):
            self.command_prefix = command_prefix
            self.intents = intents
            # An unconnected client reports latency as nan in real
            # discord.py, so the stand-in does the same.
            self.latency = float("nan")
            self.tree = _Tree()
            self._cogs = []
            self._views = []
            self.user = None

        async def add_cog(self, cog):
            self._cogs.append(cog)

        def add_view(self, view, message_id=None):
            self._views.append(view)

    commands_mod.Cog = Cog
    commands_mod.Bot = Bot

    discord_mod.Embed = Embed
    discord_mod.Colour = Colour
    discord_mod.SelectOption = SelectOption
    discord_mod.Interaction = Interaction
    discord_mod.Message = Message
    discord_mod.HTTPException = HTTPException
    discord_mod.Intents = Intents
    discord_mod.ButtonStyle = ButtonStyle
    discord_mod.app_commands = app_commands_mod
    discord_mod.ui = ui_mod
    discord_mod.ext = ext_mod

    ext_mod.commands = commands_mod

    return {
        "discord": discord_mod,
        "discord.app_commands": app_commands_mod,
        "discord.ui": ui_mod,
        "discord.ext": ext_mod,
        "discord.ext.commands": commands_mod,
    }


for _name, _module in _build_discord_stub().items():
    sys.modules[_name] = _module

import discord  # noqa: E402  (the stub above, from sys.modules)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from examples.pagination import (  # noqa: E402
    MAX_PAGES,
    PAGE_SIZE,
    LeaderboardCog,
    LeaderboardRow,
    PageSelect,
    PaginatorView,
    PaginationBot,
    build_page,
    build_pages,
    chunk_rows,
    main,
)


def sample_rows(count: int) -> list[LeaderboardRow]:
    """Rows with exact, hand-computed points (1200, 1100, 1000, ...)."""
    return [LeaderboardRow(f"Player {i + 1}", 1200 - i * 100) for i in range(count)]


def make_interaction(user_id: int = 1) -> MagicMock:
    """A mocked interaction in the shape the testing skill uses."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.original_response = AsyncMock()
    return interaction


def three_pages() -> list[discord.Embed]:
    return build_pages(sample_rows(12))


class TestChunkRows(unittest.TestCase):
    def test_splits_twelve_rows_into_five_five_two(self):
        chunks = chunk_rows(sample_rows(12))
        self.assertEqual([len(c) for c in chunks], [5, 5, 2])

    def test_exact_multiple_has_no_empty_last_page(self):
        chunks = chunk_rows(sample_rows(10))
        self.assertEqual([len(c) for c in chunks], [5, 5])

    def test_rejects_zero_page_size(self):
        with self.assertRaises(ValueError):
            chunk_rows(sample_rows(3), page_size=0)


class TestBuildPages(unittest.TestCase):
    def test_twelve_rows_make_three_embeds(self):
        pages = three_pages()
        self.assertEqual(len(pages), 3)
        for page in pages:
            self.assertEqual(page.title, "Leaderboard")

    def test_ranks_keep_counting_across_pages(self):
        pages = three_pages()
        self.assertIn("1. Player 1 - 1,200 points", pages[0].description)
        self.assertIn("6. Player 6 - 700 points", pages[1].description)
        self.assertIn("12. Player 12 - 100 points", pages[2].description)

    def test_footer_shows_page_numbers(self):
        pages = three_pages()
        self.assertEqual(pages[0].footer.text, "Page 1 of 3")
        self.assertEqual(pages[1].footer.text, "Page 2 of 3")
        self.assertEqual(pages[2].footer.text, "Page 3 of 3")

    def test_build_page_uses_the_given_start_rank(self):
        page = build_page(sample_rows(2), page_index=1, page_count=4, start_rank=6)
        self.assertIn("6. Player 1 - 1,200 points", page.description)
        self.assertEqual(page.footer.text, "Page 2 of 4")

    def test_empty_leaderboard_is_one_page_that_says_so(self):
        pages = build_pages([])
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].description, "No entries yet.")

    def test_more_than_25_pages_is_rejected(self):
        # 26 pages of 5: the jump-to-page select holds at most 25.
        rows = [LeaderboardRow(f"Player {i}", i) for i in range(26 * PAGE_SIZE)]
        with self.assertRaises(ValueError):
            build_pages(rows)

    def test_exactly_25_pages_is_allowed(self):
        rows = [LeaderboardRow(f"Player {i}", i) for i in range(MAX_PAGES * PAGE_SIZE)]
        self.assertEqual(len(build_pages(rows)), MAX_PAGES)


class TestPaginatorView(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.pages = three_pages()

    def view(self, author_id: int = 1) -> PaginatorView:
        return PaginatorView(author_id=author_id, pages=self.pages)

    def test_starts_on_page_one_with_previous_disabled(self):
        view = self.view()
        self.assertEqual(view.current, 0)
        self.assertTrue(view.prev_button.disabled)
        self.assertFalse(view.next_button.disabled)

    def test_select_lists_one_option_per_page(self):
        view = self.view()
        select = view.page_select
        self.assertIsInstance(select, PageSelect)
        self.assertEqual(
            [o.label for o in select.options], ["Page 1", "Page 2", "Page 3"]
        )
        self.assertEqual([o.value for o in select.options], ["0", "1", "2"])
        self.assertEqual(select.placeholder, "Jump to a page")

    async def test_next_button_advances_one_page(self):
        view = self.view()
        interaction = make_interaction()
        await view.next_button.callback(interaction)
        self.assertEqual(view.current, 1)
        interaction.response.edit_message.assert_awaited_once()
        embed = interaction.response.edit_message.await_args.kwargs["embed"]
        self.assertEqual(embed.footer.text, "Page 2 of 3")
        self.assertFalse(view.prev_button.disabled)
        self.assertFalse(view.next_button.disabled)

    async def test_next_button_disables_on_the_last_page(self):
        view = self.view()
        interaction = make_interaction()
        await view.next_button.callback(interaction)
        await view.next_button.callback(interaction)
        self.assertEqual(view.current, 2)
        self.assertTrue(view.next_button.disabled)
        self.assertFalse(view.prev_button.disabled)

    async def test_previous_button_goes_back(self):
        view = self.view()
        interaction = make_interaction()
        await view.next_button.callback(interaction)
        await view.next_button.callback(interaction)
        await view.prev_button.callback(interaction)
        self.assertEqual(view.current, 1)
        embed = interaction.response.edit_message.await_args.kwargs["embed"]
        self.assertEqual(embed.footer.text, "Page 2 of 3")

    async def test_go_to_page_clamps_out_of_range(self):
        view = self.view()
        interaction = make_interaction()
        await view.go_to_page(interaction, 99)
        self.assertEqual(view.current, 2)
        await view.go_to_page(interaction, -5)
        self.assertEqual(view.current, 0)

    async def test_select_jumps_to_the_picked_page(self):
        view = self.view()
        interaction = make_interaction()
        # _values is what real discord.py fills in when the user
        # picks an option (during dispatch); setting it here
        # simulates that pick, so the callback reads values[0].
        view.page_select._values = ["2"]
        await view.page_select.callback(interaction)
        self.assertEqual(view.current, 2)
        embed = interaction.response.edit_message.await_args.kwargs["embed"]
        self.assertEqual(embed.footer.text, "Page 3 of 3")
        self.assertTrue(view.next_button.disabled)

    async def test_author_passes_the_gate(self):
        view = self.view(author_id=7)
        interaction = make_interaction(user_id=7)
        self.assertTrue(await view.interaction_check(interaction))
        interaction.response.send_message.assert_not_awaited()

    async def test_other_user_is_turned_away_ephemerally(self):
        view = self.view(author_id=7)
        interaction = make_interaction(user_id=9)
        self.assertFalse(await view.interaction_check(interaction))
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.await_args
        self.assertIn("Only the person who ran the command", args[0])
        self.assertTrue(kwargs["ephemeral"])
        self.assertEqual(view.current, 0)

    async def test_timeout_disables_everything_and_edits_the_message(self):
        view = self.view()
        message = AsyncMock()
        view.message = message
        await view.on_timeout()
        for item in view.children:
            self.assertTrue(item.disabled)
        message.edit.assert_awaited_once_with(view=view)

    async def test_timeout_without_a_message_does_not_raise(self):
        view = self.view()
        self.assertIsNone(view.message)
        await view.on_timeout()
        for item in view.children:
            self.assertTrue(item.disabled)


class TestLeaderboardCommand(unittest.IsolatedAsyncioTestCase):
    async def test_command_sends_the_first_page_with_an_author_only_view(self):
        cog = LeaderboardCog(bot=MagicMock())
        interaction = make_interaction(user_id=7)
        message = AsyncMock()
        interaction.original_response.return_value = message
        await cog.leaderboard.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        kwargs = interaction.response.send_message.await_args.kwargs
        embed = kwargs["embed"]
        self.assertEqual(embed.title, "Leaderboard")
        self.assertEqual(embed.footer.text, "Page 1 of 3")
        self.assertIn("1. Ada - 4,820 points", embed.description)
        view = kwargs["view"]
        self.assertIsInstance(view, PaginatorView)
        self.assertEqual(view.author_id, 7)
        self.assertEqual(view.current, 0)
        self.assertIs(view.message, message)

    async def test_setup_hook_registers_the_cog_and_syncs(self):
        bot = PaginationBot()
        await bot.setup_hook()
        self.assertEqual(len(bot._cogs), 1)
        self.assertIsInstance(bot._cogs[0], LeaderboardCog)
        self.assertEqual(bot.tree.synced, [None])


class TestModuleHygiene(unittest.TestCase):
    def test_no_discord_ext_pages_import(self):
        # discord.ext.pages is py-cord, not discord.py. The example
        # docstring warns against it, but no import of it may exist
        # (see interactive-components skill).
        source = (REPO_ROOT / "examples" / "pagination.py").read_text(encoding="utf-8")
        self.assertNotRegex(
            source,
            r"(?m)^\s*(from\s+discord\.ext\s+import\s+pages|import\s+discord\.ext\.pages)\b",
        )

    def test_no_em_dash_in_user_facing_text(self):
        # The repo quality bar forbids em dashes in bot output.
        source = (REPO_ROOT / "examples" / "pagination.py").read_text(encoding="utf-8")
        self.assertNotIn("\u2014", source)

    def test_main_exits_without_a_token(self):
        with patch.dict(os.environ, {"DISCORD_TOKEN": ""}):
            with self.assertRaises(SystemExit):
                main()


if __name__ == "__main__":
    unittest.main()
