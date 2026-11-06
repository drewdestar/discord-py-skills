#!/usr/bin/env python3
"""Tests for examples/human_replies.py.

Stdlib only; run from the repo root on a plain VM with no discord.py
installed:
    python3 -m unittest tests.test_example_human_replies -v

discord.py is NOT imported. The repo rule is that every test runs
with the standard library alone, so a small stand-in for the discord.py
surface the example touches is built below and installed in
``sys.modules`` before the example module is imported. The stand-in
covers only what the example uses (``app_commands.command``,
``commands.Cog``/``Bot``, ``discord.ui.View``/``button``,
``ButtonStyle``, ``Interaction``, ``Intents``, ``Object``,
``HTTPException``), and its shapes were checked against the real
discord.py 2.5.2 signatures: ``command`` keeps ``.callback`` and
``.name``; the cog metaclass collects ``__cog_app_commands__``; a
button click calls the method as ``func(view, interaction, button)``;
``InteractionResponse.is_done()`` is sync; an unconnected bot reports
``latency`` as nan. The stand-in is removed from ``sys.modules``
again right after the example is imported, so later test modules see
a plain interpreter: a neighbouring suite that runs live tests only
when real discord.py is installed keeps skipping them instead of
tripping over the stand-in. No token, no network, no live bot.
Commands are called through their callbacks with mocked
interactions, following skills/testing. Expected reply strings come
from this file, never recomputed from the code under test, so a
wording change turns a test red.
"""

import os
import subprocess
import sys
import types
import unittest
from importlib.machinery import ModuleSpec
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


def _build_discord_stub():
    """Build the minimal discord.py stand-in used by these tests.

    Returns a mapping of module name to module object. Only the names
    the example module touches at import time or in the tested paths
    are faked; anything else raises AttributeError, which is the point:
    a test that reaches past the faked surface fails loudly instead of
    silently passing against a made-up API.
    """
    discord_mod = types.ModuleType("discord")
    app_commands_mod = types.ModuleType("discord.app_commands")
    ui_mod = types.ModuleType("discord.ui")
    ext_mod = types.ModuleType("discord.ext")
    commands_mod = types.ModuleType("discord.ext.commands")

    # A module in sys.modules with __spec__ set to None makes
    # importlib.util.find_spec() raise ValueError, which broke a
    # neighbouring test module when the suite ran together. Give every
    # stand-in a spec so find_spec works; the two packages also get an
    # empty __path__ so a submodule import fails as "not found"
    # instead of crashing the import machinery.
    discord_mod.__spec__ = ModuleSpec("discord", loader=None, is_package=True)
    discord_mod.__path__ = []
    app_commands_mod.__spec__ = ModuleSpec("discord.app_commands", loader=None)
    ui_mod.__spec__ = ModuleSpec("discord.ui", loader=None)
    ext_mod.__spec__ = ModuleSpec("discord.ext", loader=None, is_package=True)
    ext_mod.__path__ = []
    commands_mod.__spec__ = ModuleSpec("discord.ext.commands", loader=None)

    discord_mod._is_test_stub = True

    class Interaction:
        # Class attributes only: MagicMock(spec=Interaction) allows
        # exactly these names, which is the surface the example uses.
        user = None
        response = None
        followup = None
        command = None
        guild = None

    class HTTPException(Exception):
        pass

    class Object:
        def __init__(self, id=None):
            self.id = id

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

    class View:
        def __init__(self, *, timeout=180.0):
            self.timeout = timeout
            self.children = []
            for attr_name in dir(type(self)):
                func = getattr(type(self), attr_name, None)
                spec = getattr(func, "__discord_button__", None)
                if spec is not None:
                    label, style, custom_id = spec
                    self.children.append(
                        Button(label, style, custom_id, func, self)
                    )

        def add_item(self, item):
            item.view = self
            self.children.append(item)

    ui_mod.Button = Button
    ui_mod.ButtonStyle = ButtonStyle
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
            self.copied_to = None

        def copy_global_to(self, guild=None):
            self.copied_to = guild

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

        async def add_cog(self, cog):
            self._cogs.append(cog)

        def add_view(self, view, message_id=None):
            self._views.append(view)

    commands_mod.Cog = Cog
    commands_mod.Bot = Bot

    discord_mod.Interaction = Interaction
    discord_mod.HTTPException = HTTPException
    discord_mod.Object = Object
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


_STUB_MODULES = _build_discord_stub()
_PREVIOUS_MODULES = {name: sys.modules.get(name) for name in _STUB_MODULES}
for _name, _module in _STUB_MODULES.items():
    sys.modules[_name] = _module

import discord  # noqa: E402  (the stub above, from sys.modules)
from discord import app_commands  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from examples.human_replies import (  # noqa: E402
    BalanceView,
    Bot,
    HumanReplies,
    MemoryStore,
    format_balance,
    format_help,
    format_inventory,
    format_ping,
)
import examples.human_replies as _human_replies_module  # noqa: E402

# The example module is imported now, so the stand-in has served its
# purpose. Remove it again so the rest of the process sees a plain
# interpreter: names this file already bound (discord, app_commands,
# the example's classes) keep pointing at the stand-in objects, and
# nothing else is affected.
for _name, _module in _STUB_MODULES.items():
    if sys.modules.get(_name) is _module:
        _previous = _PREVIOUS_MODULES.get(_name)
        if _previous is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _previous

CHECKER = REPO_ROOT / "scripts" / "check_antislop.py"
EXAMPLE = REPO_ROOT / "examples" / "human_replies.py"

# Phrases the antislop skill bans in bot replies (R-02, R-15, R-16, R-36).
# Kept here as test data only; the shipped replies must contain none of
# them. The mechanical checker does not catch closers, openers, or
# signposting, so these assertions cover what it misses.
BANNED_PHRASES = [
    "\u2014",  # em dash
    "Seamless",
    "Revolutionary",
    "Cutting Edge",
    "Next Generation",
    "AI Powered",
    "Ultimate",
    "Powerful",
    "Effortless",
    "I hope this helps!",
    "Let me know if you have any questions",
    "Would you like me to expand on this?",
    "You are welcome!",
    "Honestly?",
    "Here is the thing",
    "Let us be honest",
    "Let us dive in",
    "Here is what you need to know",
    "In today\u2019s fast-paced world",
    "In an era of rapid technological disruption",
    "Read that again.",
    "Let that sink in.",
    "The bottom line:",
    "That distinction matters.",
    "Get Started",
    "Learn More",
    "Try Now",
    "In order to",
    "Due to the fact that",
]

SAMPLE_REPLIES = [
    format_balance(0),
    format_balance(250),
    format_balance(1250),
    format_ping(42),
    format_ping(None),
    format_inventory([]),
    format_inventory(["rope"]),
    format_inventory(["rope", "lantern", "map"]),
    format_inventory([f"item {n}" for n in range(25)]),
    format_help(),
]


def make_interaction(user_id: int = 1) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.response = AsyncMock()
    # is_done() is sync on the real InteractionResponse; an AsyncMock
    # would make it return a coroutine (truthy), so pin it to a plain
    # Mock returning False by default.
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = AsyncMock()
    return interaction


def make_bot(latency: float = 0.042) -> MagicMock:
    bot = MagicMock()
    bot.latency = latency
    return bot


class FailingStore:
    """A store that always fails, for the error-path tests."""

    async def get_balance(self, user_id: int) -> int:
        raise RuntimeError("database is down")

    async def get_items(self, user_id: int) -> list[str]:
        raise RuntimeError("database is down")


def _click(view: BalanceView, label: str) -> discord.ui.Button:
    for child in view.children:
        if isinstance(child, discord.ui.Button) and child.label == label:
            return child
    raise AssertionError(f"no button labelled {label!r}")


def _sent_text(interaction: MagicMock) -> str:
    return interaction.response.send_message.await_args.args[0]


class TestReplyBuilders(unittest.TestCase):
    def test_balance_shows_sourced_amount(self):
        self.assertEqual(format_balance(250), "Your balance is 250 gold.")

    def test_balance_zero_for_new_user(self):
        self.assertEqual(format_balance(0), "Your balance is 0 gold.")

    def test_balance_groups_thousands(self):
        self.assertEqual(format_balance(1250), "Your balance is 1,250 gold.")

    def test_ping_shows_measured_latency(self):
        self.assertEqual(format_ping(42), "Pong! Latency is 42 ms.")

    def test_ping_without_measurement_shows_no_number(self):
        text = format_ping(None)
        self.assertEqual(text, "Pong! I am awake.")
        self.assertFalse(any(char.isdigit() for char in text))

    def test_inventory_empty_state(self):
        self.assertEqual(format_inventory([]), "You have no items yet.")

    def test_inventory_singular(self):
        self.assertEqual(
            format_inventory(["rope"]), "You have 1 item:\n- rope"
        )

    def test_inventory_lists_items_answer_first(self):
        text = format_inventory(["rope", "lantern", "map"])
        self.assertEqual(
            text, "You have 3 items:\n- rope\n- lantern\n- map"
        )

    def test_inventory_caps_long_list_with_sourced_counts(self):
        items = [f"item {n}" for n in range(25)]
        text = format_inventory(items)
        lines = text.splitlines()
        self.assertEqual(lines[0], "You have 25 items:")
        self.assertEqual(lines[-1], "Showing 20 of 25 items.")
        self.assertEqual(len(lines), 22)

    def test_help_lists_only_commands_that_exist(self):
        self.assertEqual(
            format_help(),
            "/ping: check the bot is awake.\n"
            "/balance: show your gold.\n"
            "/inventory: list the items you own.\n"
            "Pick a command and Discord fills in the rest.",
        )

    def test_help_lines_vary_in_length(self):
        lengths = {len(line) for line in format_help().splitlines()}
        self.assertGreater(len(lengths), 1)

    def test_no_reply_contains_a_banned_phrase(self):
        for text in SAMPLE_REPLIES:
            for phrase in BANNED_PHRASES:
                with self.subTest(reply=text, phrase=phrase):
                    self.assertNotIn(phrase.lower(), text.lower())


class TestCommands(unittest.IsolatedAsyncioTestCase):
    async def test_ping_answers_with_measured_latency(self):
        cog = HumanReplies(bot=make_bot(latency=0.042))
        interaction = make_interaction()
        await cog.ping.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        self.assertEqual(_sent_text(interaction), "Pong! Latency is 42 ms.")

    async def test_ping_without_latency_answers_without_a_number(self):
        cog = HumanReplies(bot=make_bot(latency=float("nan")))
        interaction = make_interaction()
        await cog.ping.callback(cog, interaction)
        text = _sent_text(interaction)
        self.assertEqual(text, "Pong! I am awake.")
        self.assertFalse(any(char.isdigit() for char in text))

    async def test_balance_answers_from_store_and_attaches_refresh_button(self):
        store = MemoryStore()
        await store.set_balance(7, 250)
        cog = HumanReplies(bot=make_bot(), store=store)
        interaction = make_interaction(user_id=7)
        await cog.balance.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        self.assertEqual(_sent_text(interaction), "Your balance is 250 gold.")
        view = interaction.response.send_message.await_args.kwargs["view"]
        self.assertIsInstance(view, BalanceView)
        self.assertIsNone(view.timeout)

    async def test_balance_error_answers_user_without_traceback(self):
        cog = HumanReplies(bot=make_bot(), store=FailingStore())
        interaction = make_interaction()
        await cog.balance.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        text, kwargs = _sent_text(interaction), interaction.response.send_message.await_args.kwargs
        self.assertEqual(text, "I could not read your balance. Try again in a bit.")
        self.assertTrue(kwargs["ephemeral"])
        self.assertNotIn("Traceback", text)
        self.assertNotIn("database is down", text)

    async def test_inventory_defers_then_lists_items(self):
        store = MemoryStore()
        await store.add_item(7, "rope")
        await store.add_item(7, "lantern")
        cog = HumanReplies(bot=make_bot(), store=store)
        interaction = make_interaction(user_id=7)
        await cog.inventory.callback(cog, interaction)
        interaction.response.defer.assert_awaited_once()
        interaction.followup.send.assert_awaited_once()
        text = interaction.followup.send.await_args.args[0]
        self.assertEqual(text, "You have 2 items:\n- rope\n- lantern")

    async def test_inventory_empty_state_after_defer(self):
        cog = HumanReplies(bot=make_bot(), store=MemoryStore())
        interaction = make_interaction()
        await cog.inventory.callback(cog, interaction)
        interaction.response.defer.assert_awaited_once()
        text = interaction.followup.send.await_args.args[0]
        self.assertEqual(text, "You have no items yet.")

    async def test_inventory_error_answers_user(self):
        cog = HumanReplies(bot=make_bot(), store=FailingStore())
        interaction = make_interaction()
        await cog.inventory.callback(cog, interaction)
        interaction.response.defer.assert_awaited_once()
        text = interaction.followup.send.await_args.args[0]
        kwargs = interaction.followup.send.await_args.kwargs
        self.assertEqual(text, "I could not read your items. Try again in a bit.")
        self.assertTrue(kwargs["ephemeral"])
        self.assertNotIn("database is down", text)

    async def test_help_answers(self):
        cog = HumanReplies(bot=make_bot())
        interaction = make_interaction()
        await cog.help_command.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        self.assertEqual(_sent_text(interaction), format_help())
        self.assertTrue(
            interaction.response.send_message.await_args.kwargs["ephemeral"]
        )

    async def test_refresh_button_re_reads_store(self):
        store = MemoryStore()
        await store.set_balance(7, 250)
        view = BalanceView(store)
        interaction = make_interaction(user_id=7)
        await _click(view, "Check again").callback(interaction)
        self.assertEqual(_sent_text(interaction), "Your balance is 250 gold.")
        await store.set_balance(7, 300)
        interaction2 = make_interaction(user_id=7)
        await _click(view, "Check again").callback(interaction2)
        self.assertEqual(_sent_text(interaction2), "Your balance is 300 gold.")

    async def test_refresh_button_error_answers_user(self):
        view = BalanceView(FailingStore())
        interaction = make_interaction()
        await _click(view, "Check again").callback(interaction)
        text = _sent_text(interaction)
        self.assertEqual(text, "I could not read your balance. Try again in a bit.")
        self.assertNotIn("database is down", text)

    async def test_cog_error_handler_answers_before_response(self):
        cog = HumanReplies(bot=make_bot())
        interaction = make_interaction()
        interaction.response.is_done.return_value = False
        await cog.cog_app_command_error(
            interaction, app_commands.AppCommandError("boom")
        )
        interaction.response.send_message.assert_awaited_once()
        self.assertEqual(
            _sent_text(interaction), "Something went wrong. The error was logged."
        )

    async def test_cog_error_handler_uses_followup_after_response(self):
        cog = HumanReplies(bot=make_bot())
        interaction = make_interaction()
        interaction.response.is_done.return_value = True
        await cog.cog_app_command_error(
            interaction, app_commands.AppCommandError("boom")
        )
        interaction.followup.send.assert_awaited_once()
        text = interaction.followup.send.await_args.args[0]
        self.assertEqual(text, "Something went wrong. The error was logged.")

    async def test_setup_hook_registers_cog_view_and_syncs(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_GUILD_ID", None)
            bot = Bot()
            await bot.setup_hook()
        self.assertEqual(len(bot._cogs), 1)
        self.assertIsInstance(bot._cogs[0], HumanReplies)
        self.assertEqual(len(bot._views), 1)
        self.assertIsInstance(bot._views[0], BalanceView)
        self.assertEqual(bot.tree.synced, [None])


class TestWiring(unittest.TestCase):
    def test_example_runs_against_the_stub_not_real_discord(self):
        # Both references were captured when this test module was
        # imported, so a neighbouring test module overwriting
        # sys.modules["discord"] with its own stand-in afterwards
        # cannot change what this asserts. Asserting on sys.modules
        # here would test shared global state, not this example.
        self.assertTrue(
            getattr(_human_replies_module.discord, "_is_test_stub", False)
        )
        self.assertIs(_human_replies_module.discord, discord)

    def test_stub_leaves_no_trace_after_import(self):
        # The stand-in is removed from sys.modules right after the
        # example is imported. A neighbouring suite decides whether to
        # run its live tests by calling importlib.util.find_spec on
        # discord: while the stand-in was left installed, find_spec
        # either raised ValueError (no __spec__) or returned the
        # stand-in's spec, and the live tests then ran against names
        # the stand-in never faked. Run this module alone in a fresh
        # interpreter and prove no stub trace is left. The check is
        # environment-independent: on a machine with real discord.py
        # installed, find_spec correctly finds the real package (a
        # spec with a real file origin), which is not a stub trace.
        code = (
            "import sys; sys.path.insert(0, %r);"
            "import tests.test_example_human_replies;"
            "import importlib.util;"
            "m = sys.modules.get('discord');"
            "assert m is None or not getattr(m, '_is_test_stub', False), 'stub left in sys.modules';"
            "spec = importlib.util.find_spec('discord');"
            "assert spec is None or spec.origin is not None, spec"
            % str(REPO_ROOT)
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_cog_registers_four_commands(self):
        names = {cmd.name for cmd in HumanReplies.__cog_app_commands__}
        self.assertEqual(names, {"ping", "balance", "inventory", "help"})

    def test_refresh_button_has_label_and_stable_custom_id(self):
        view = BalanceView(MemoryStore())
        button = _click(view, "Check again")
        self.assertEqual(button.custom_id, "human_replies:balance_again")
        self.assertEqual(button.style, discord.ButtonStyle.secondary)
        self.assertIsNone(view.timeout)

    def test_token_comes_from_environment_only(self):
        text = EXAMPLE.read_text(encoding="utf-8")
        self.assertIn('os.environ.get("DISCORD_TOKEN")', text)

    def test_checker_passes_on_example_file(self):
        proc = subprocess.run(
            [sys.executable, str(CHECKER), str(EXAMPLE)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("clean", proc.stdout)


if __name__ == "__main__":
    unittest.main()
