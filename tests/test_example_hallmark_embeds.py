#!/usr/bin/env python3
"""Tests for examples/hallmark_embeds.py. Stdlib unittest only; run with:
    python3 -m unittest tests.test_example_hallmark_embeds
from the repo root, or: python3 -m unittest discover -s tests.

discord.py is NOT installed on this machine, and this file must
not import discord, aiohttp, or aiosqlite. Instead it builds a
small stub for the discord.py 2.x surface the example uses
(Embed.from_dict/to_dict, Colour.value, app_commands.command
with .callback, Cog, Bot.add_cog/get_cog, Intents.default),
installs it in sys.modules, imports the example, then restores
sys.modules so no other test module sees the stub. The stub
mirrors the real API and nothing else. Real discord.py 2.5
behaviour is verified separately against an installed discord.py,
not by this file. No token, no network: every interaction is a
mock, and the stub bot refuses to connect.
"""

import copy
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
HELPER_DIR = REPO_ROOT / "skills" / "design-with-hallmark" / "scripts"


def _build_discord_stub():
    """Minimal stand-in for the discord.py 2.x surface the example
    uses. Only what hallmark_embeds.py touches, with the same
    shapes the real library returns."""
    discord_mod = types.ModuleType("discord")

    class Colour:
        __slots__ = ("value",)

        def __init__(self, value):
            self.value = int(value)

        def __eq__(self, other):
            if isinstance(other, Colour):
                return self.value == other.value
            if isinstance(other, int):
                return self.value == other
            return NotImplemented

        def __ne__(self, other):
            result = self.__eq__(other)
            return result if result is NotImplemented else not result

        def __hash__(self):
            return hash(self.value)

        def __int__(self):
            return self.value

        def __repr__(self):
            return "Colour(0x%06X)" % self.value

    class _EmbedProxy:
        """Like discord's EmbedProxy: a missing key reads as None."""

        def __init__(self, layer):
            self._layer = dict(layer)

        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            return self._layer.get(name)

        def __repr__(self):
            return "_EmbedProxy(%r)" % (self._layer,)

    class Embed:
        def __init__(self, *, colour=None, color=None, title=None,
                     description=None, url=None):
            value = colour if colour is not None else color
            data = {}
            if value is not None:
                data["color"] = int(value)
            if title is not None:
                data["title"] = title
            if description is not None:
                data["description"] = description
            if url is not None:
                data["url"] = url
            self._data = data

        @classmethod
        def from_dict(cls, data):
            obj = cls.__new__(cls)
            obj._data = copy.deepcopy(data)
            return obj

        def to_dict(self):
            return copy.deepcopy(self._data)

        @property
        def colour(self):
            if "color" in self._data:
                return Colour(self._data["color"])
            return None

        color = colour

        @property
        def title(self):
            return self._data.get("title")

        @property
        def description(self):
            return self._data.get("description")

        @property
        def url(self):
            return self._data.get("url")

        @property
        def fields(self):
            return [_EmbedProxy(f) for f in self._data.get("fields", [])]

        @property
        def footer(self):
            return _EmbedProxy(self._data.get("footer") or {})

        @property
        def thumbnail(self):
            return _EmbedProxy(self._data.get("thumbnail") or {})

        @property
        def author(self):
            return _EmbedProxy(self._data.get("author") or {})

    class Intents:
        def __init__(self):
            self.members = False
            self.guilds = True

        @classmethod
        def default(cls):
            return cls()

    class Interaction:
        pass

    class HTTPException(Exception):
        pass

    app_commands_mod = types.ModuleType("discord.app_commands")

    class AppCommandError(Exception):
        pass

    class _Command:
        def __init__(self, func, name, description):
            self.callback = func
            self.name = name
            self.description = description
            self.__name__ = func.__name__
            self.__doc__ = func.__doc__

    def command(*, name=None, description=None):
        def decorator(func):
            return _Command(func, name or func.__name__,
                            description or "")
        return decorator

    def describe(**kwargs):
        def decorator(func):
            func.__discord_app_commands_param_descriptions__ = dict(kwargs)
            return func
        return decorator

    app_commands_mod.AppCommandError = AppCommandError
    app_commands_mod.command = command
    app_commands_mod.describe = describe

    ext_mod = types.ModuleType("discord.ext")
    commands_mod = types.ModuleType("discord.ext.commands")

    class Cog:
        pass

    class _Tree:
        def __init__(self):
            self.synced = False

        async def sync(self):
            self.synced = True
            return []

    class Bot:
        def __init__(self, command_prefix=None, intents=None, **kwargs):
            self.command_prefix = command_prefix
            self.intents = intents
            self.tree = _Tree()
            self._cogs = {}

        async def add_cog(self, cog, *, override=False):
            self._cogs[type(cog).__name__] = cog

        def get_cog(self, name):
            return self._cogs.get(name)

        def run(self, token, **kwargs):
            raise RuntimeError("stub bot cannot connect to Discord")

    commands_mod.Cog = Cog
    commands_mod.Bot = Bot
    ext_mod.commands = commands_mod

    discord_mod.Embed = Embed
    discord_mod.Colour = Colour
    discord_mod.Intents = Intents
    discord_mod.Interaction = Interaction
    discord_mod.HTTPException = HTTPException
    discord_mod.app_commands = app_commands_mod
    discord_mod.ext = ext_mod
    return {
        "discord": discord_mod,
        "discord.app_commands": app_commands_mod,
        "discord.ext": ext_mod,
        "discord.ext.commands": commands_mod,
    }


# Install the stub, import the example, then restore sys.modules
# so other test modules never see the stub.
_STUB = _build_discord_stub()
_PREVIOUS = {name: sys.modules.get(name) for name in _STUB}
sys.modules.update(_STUB)
sys.path.insert(0, str(EXAMPLES_DIR))
sys.path.insert(0, str(HELPER_DIR))
try:
    import hallmark_embeds  # noqa: E402
finally:
    for _name, _previous in _PREVIOUS.items():
        if _previous is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _previous

import hallmark_theme  # noqa: E402

DARKROOM = 0xEC8D38  # Darkroom accent #ec8d38, from `theme darkroom`
SQUEEZE = 0xFFB37C  # Squeeze accent #ffb37c, from `theme squeeze`


def make_interaction(user_id=1, display_name="Andreas",
                     avatar_url="https://cdn.example.com/avatar.png"):
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.user.display_name = display_name
    interaction.user.mention = "<@%d>" % user_id
    interaction.user.display_avatar.url = avatar_url
    interaction.response = AsyncMock()
    # is_done() is a plain sync method on the real InteractionResponse,
    # so it needs a sync Mock: an AsyncMock child would return a
    # coroutine (always truthy) instead of False.
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = AsyncMock()
    return interaction


def sent_embed(interaction):
    """The embed the command sent with response.send_message."""
    interaction.response.send_message.assert_awaited_once()
    return interaction.response.send_message.await_args.kwargs["embed"]


def _all_text(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _all_text(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _all_text(item)


class ShopEmbedTest(unittest.TestCase):
    def test_shop_embed_uses_darkroom_stripe(self):
        embed = hallmark_embeds.shop_embed_dict(
            hallmark_embeds.SHOP_ITEMS, 4830)
        self.assertEqual(embed["color"], DARKROOM)
        self.assertEqual(embed["title"], "Shop")
        self.assertEqual(embed["description"],
                         "Spend gold on things that do something.")

    def test_shop_embed_lists_items_then_balance(self):
        embed = hallmark_embeds.shop_embed_dict(
            hallmark_embeds.SHOP_ITEMS, 4830)
        self.assertEqual(len(embed["fields"]), 4)
        self.assertEqual(embed["fields"][0],
                         {"name": "Iron Sword", "value": "1,200 gold, +5 attack",
                          "inline": True})
        self.assertEqual(embed["fields"][1],
                         {"name": "Healing Potion",
                          "value": "150 gold, restores 50 HP", "inline": True})
        self.assertEqual(embed["fields"][2],
                         {"name": "Torch", "value": "40 gold, lights dark rooms",
                          "inline": True})
        # The balance stands alone: it is not inline.
        self.assertEqual(embed["fields"][3],
                         {"name": "Your gold", "value": "4,830 gold",
                          "inline": False})
        self.assertEqual(embed["footer"]["text"],
                         "Prices change when the shop restocks.")

    def test_shop_embed_numbers_come_from_arguments(self):
        items = [("Copper Dagger", 25, "a starting blade")]
        embed = hallmark_embeds.shop_embed_dict(items, 0)
        self.assertEqual(embed["fields"][0]["value"],
                         "25 gold, a starting blade")
        self.assertEqual(embed["fields"][1]["value"], "0 gold")

    def test_shop_embed_passes_discord_limits(self):
        embed = hallmark_embeds.shop_embed_dict(
            hallmark_embeds.SHOP_ITEMS, 4830)
        self.assertEqual(hallmark_theme.validate_embed(embed), [])

    def test_shop_stripe_matches_helper(self):
        self.assertEqual(hallmark_theme.embed_color("darkroom"), DARKROOM)


class ProfileEmbedTest(unittest.TestCase):
    def test_profile_embed_uses_squeeze_stripe(self):
        embed = hallmark_embeds.profile_embed_dict(
            "Andreas", 12, 4830,
            avatar_url="https://cdn.example.com/avatar.png")
        self.assertEqual(embed["color"], SQUEEZE)
        self.assertEqual(embed["title"], "Andreas")
        self.assertEqual(embed["description"],
                         "Your record in this server, kept in one place.")
        self.assertEqual(embed["fields"],
                         [{"name": "Level", "value": "12", "inline": True},
                          {"name": "Gold", "value": "4,830 gold",
                           "inline": True}])
        self.assertEqual(embed["thumbnail"]["url"],
                         "https://cdn.example.com/avatar.png")
        self.assertEqual(embed["footer"]["text"],
                         "Your gold changes when you earn or spend it.")

    def test_profile_embed_without_avatar_has_no_thumbnail(self):
        embed = hallmark_embeds.profile_embed_dict("Andreas", 1, 0)
        self.assertNotIn("thumbnail", embed)

    def test_profile_embed_passes_discord_limits(self):
        embed = hallmark_embeds.profile_embed_dict(
            "Andreas", 12, 4830, avatar_url="https://cdn.example.com/a.png")
        self.assertEqual(hallmark_theme.validate_embed(embed), [])

    def test_profile_embed_rejects_blank_display_name(self):
        # discord_embed() enforces the limits; a whitespace-only
        # title is one Discord rejects as empty.
        with self.assertRaises(ValueError):
            hallmark_embeds.profile_embed_dict("   ", 1, 0)

    def test_profile_stripe_matches_helper(self):
        self.assertEqual(hallmark_theme.embed_color("squeeze"), SQUEEZE)


class DealEmbedTest(unittest.TestCase):
    def test_deal_embed_lists_the_dealt_hand(self):
        picks = hallmark_theme.deal("rpg economy shop", seed=7)
        embed = hallmark_embeds.deal_embed_dict("rpg economy shop", picks)
        self.assertEqual(embed["color"], DARKROOM)  # first pick
        self.assertEqual(embed["title"], "Theme deal")
        self.assertEqual([f["name"] for f in embed["fields"]],
                         ["Darkroom", "Squeeze", "Sport"])
        self.assertTrue(
            embed["fields"][0]["value"].startswith("Accent #ec8d38"))
        self.assertTrue(
            embed["fields"][1]["value"].startswith("Accent #ffb37c"))
        self.assertTrue(
            embed["fields"][2]["value"].startswith("Accent #c8e928"))
        for field in embed["fields"]:
            self.assertFalse(field["inline"])

    def test_deal_embed_passes_discord_limits(self):
        picks = hallmark_theme.deal("rpg economy shop", seed=7)
        embed = hallmark_embeds.deal_embed_dict("rpg economy shop", picks)
        self.assertEqual(hallmark_theme.validate_embed(embed), [])

    def test_deal_embed_needs_at_least_one_pick(self):
        with self.assertRaises(ValueError):
            hallmark_embeds.deal_embed_dict("shop", [])

    def test_deal_embed_rejects_unknown_theme(self):
        picks = [{"slug": "nope", "name": "Nope", "accent": "#000000",
                  "material": "nothing here"}]
        with self.assertRaises(KeyError):
            hallmark_embeds.deal_embed_dict("shop", picks)


class FloorTest(unittest.TestCase):
    def test_embeds_follow_the_floor(self):
        picks = hallmark_theme.deal("rpg economy shop", seed=7)
        embeds = [
            hallmark_embeds.shop_embed_dict(
                hallmark_embeds.SHOP_ITEMS, 4830),
            hallmark_embeds.profile_embed_dict(
                "Andreas", 12, 4830,
                avatar_url="https://cdn.example.com/a.png"),
            hallmark_embeds.deal_embed_dict("rpg economy shop", picks),
        ]
        for embed in embeds:
            for text in _all_text(embed):
                self.assertNotIn("\u2014", text, embed)  # no em dash
                self.assertNotIn("\u00b7", text, embed)  # no middle dot
            self.assertLessEqual(
                len(embed["description"].split()), 12, embed)
            for field in embed["fields"]:
                self.assertNotEqual(field["name"], field["name"].upper(),
                                    field)  # no tracked-caps label
            self.assertEqual(hallmark_theme.validate_embed(embed), [])

    def test_source_has_no_em_dash_or_middle_dot(self):
        source = (EXAMPLES_DIR / "hallmark_embeds.py").read_text()
        self.assertNotIn("\u2014", source)
        self.assertNotIn("\u00b7", source)


class ToEmbedTest(unittest.TestCase):
    def test_to_embed_round_trip(self):
        embed = hallmark_embeds.to_embed(
            hallmark_embeds.shop_embed_dict(
                hallmark_embeds.SHOP_ITEMS, 4830))
        self.assertEqual(embed.color, DARKROOM)
        self.assertEqual(embed.colour, DARKROOM)
        self.assertEqual(embed.title, "Shop")
        self.assertEqual(embed.fields[0].name, "Iron Sword")
        self.assertEqual(embed.fields[0].value, "1,200 gold, +5 attack")
        self.assertTrue(embed.fields[0].inline)
        self.assertEqual(embed.footer.text,
                         "Prices change when the shop restocks.")
        self.assertEqual(embed.to_dict()["color"], DARKROOM)


class CogCommandTest(unittest.IsolatedAsyncioTestCase):
    def make_cog(self, ledger=None, levels=None):
        bot = MagicMock()
        return hallmark_embeds.HallmarkEmbeds(bot, ledger, levels)

    async def test_shop_command_sends_darkroom_embed(self):
        cog = self.make_cog(ledger={1: 4830})
        interaction = make_interaction(user_id=1)
        await cog.shop.callback(cog, interaction)
        embed = sent_embed(interaction)
        self.assertEqual(embed.color, DARKROOM)
        self.assertEqual(embed.title, "Shop")
        self.assertEqual(embed.fields[3].value, "4,830 gold")

    async def test_shop_command_zero_gold_for_unknown_user(self):
        cog = self.make_cog(ledger={})
        interaction = make_interaction(user_id=9)
        await cog.shop.callback(cog, interaction)
        embed = sent_embed(interaction)
        self.assertEqual(embed.fields[3].value, "0 gold")

    async def test_profile_command_uses_invoker(self):
        cog = self.make_cog(ledger={1: 4830}, levels={1: 12})
        interaction = make_interaction(user_id=1, display_name="Andreas")
        await cog.profile.callback(cog, interaction)
        embed = sent_embed(interaction)
        self.assertEqual(embed.color, SQUEEZE)
        self.assertEqual(embed.title, "Andreas")
        self.assertEqual(embed.fields[0].value, "12")
        self.assertEqual(embed.fields[1].value, "4,830 gold")
        self.assertEqual(embed.thumbnail.url,
                         "https://cdn.example.com/avatar.png")

    async def test_profile_command_new_adventurer_starts_at_level_1(self):
        cog = self.make_cog()
        interaction = make_interaction(user_id=7, display_name="Newcomer")
        await cog.profile.callback(cog, interaction)
        embed = sent_embed(interaction)
        self.assertEqual(embed.fields[0].value, "1")
        self.assertEqual(embed.fields[1].value, "0 gold")

    async def test_themes_command_deals_three_strong_themes(self):
        cog = self.make_cog()
        interaction = make_interaction()
        await cog.themes.callback(cog, interaction, "rpg economy shop")
        embed = sent_embed(interaction)
        self.assertEqual(embed.title, "Theme deal")
        self.assertEqual(len(embed.fields), 3)
        strong = {hallmark_theme.embed_color(t["slug"]) for t in
                  hallmark_theme.list_themes(strong_only=True)}
        self.assertIn(int(embed.color), strong)

    async def test_themes_command_defaults_to_shop_keywords(self):
        cog = self.make_cog()
        interaction = make_interaction()
        await cog.themes.callback(cog, interaction)
        embed = sent_embed(interaction)
        self.assertEqual(len(embed.fields), 3)

    async def test_cog_registers_three_commands(self):
        cog = self.make_cog()
        self.assertEqual(cog.shop.name, "shop")
        self.assertEqual(cog.profile.name, "profile")
        self.assertEqual(cog.themes.name, "themes")
        for command in (cog.shop, cog.profile, cog.themes):
            self.assertTrue(command.description, command.name)

    async def test_error_handler_replies_ephemeral(self):
        cog = self.make_cog()
        interaction = make_interaction()
        await cog.cog_app_command_error(
            interaction,
            hallmark_embeds.app_commands.AppCommandError("boom"))
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.await_args
        self.assertTrue(args[0].startswith("Sorry,"))
        self.assertTrue(kwargs["ephemeral"])
        interaction.followup.send.assert_not_awaited()

    async def test_error_handler_uses_followup_when_responded(self):
        cog = self.make_cog()
        interaction = make_interaction()
        interaction.response.is_done.return_value = True
        await cog.cog_app_command_error(
            interaction,
            hallmark_embeds.app_commands.AppCommandError("boom"))
        interaction.followup.send.assert_awaited_once()
        args, kwargs = interaction.followup.send.await_args
        self.assertTrue(args[0].startswith("Sorry,"))
        self.assertTrue(kwargs["ephemeral"])
        interaction.response.send_message.assert_not_awaited()

    async def test_error_handler_survives_send_failure(self):
        cog = self.make_cog()
        interaction = make_interaction()
        interaction.response.send_message = AsyncMock(
            side_effect=hallmark_embeds.discord.HTTPException("boom"))
        await cog.cog_app_command_error(
            interaction,
            hallmark_embeds.app_commands.AppCommandError("boom"))
        interaction.response.send_message.assert_awaited_once()


class WiringTest(unittest.IsolatedAsyncioTestCase):
    async def test_setup_adds_cog(self):
        bot = hallmark_embeds.commands.Bot(
            command_prefix="!",
            intents=hallmark_embeds.discord.Intents.default())
        await hallmark_embeds.setup(bot)
        self.assertIsInstance(bot.get_cog("HallmarkEmbeds"),
                              hallmark_embeds.HallmarkEmbeds)

    async def test_setup_hook_loads_cog_and_syncs_tree(self):
        bot = hallmark_embeds.Bot()
        calls = []

        async def sync_spy():
            calls.append(True)
            return []

        bot.tree.sync = sync_spy
        await bot.setup_hook()
        self.assertIsInstance(bot.get_cog("HallmarkEmbeds"),
                              hallmark_embeds.HallmarkEmbeds)
        self.assertEqual(calls, [True])

    def test_main_requires_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                hallmark_embeds.main()

    def test_main_runs_bot_with_token(self):
        with patch.dict(os.environ, {"DISCORD_TOKEN": "test-token"}):
            with patch.object(hallmark_embeds.Bot, "run") as run_mock:
                hallmark_embeds.main()
        run_mock.assert_called_once_with("test-token")


if __name__ == "__main__":
    unittest.main()
