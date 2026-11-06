#!/usr/bin/env python3
"""Tests for examples/i18n_bot.py. Stdlib unittest only; run with:
    python3 -m unittest tests.test_example_i18n_bot
from the repo root, using the plain system python3.

No test touches the network or a real Discord token, and no test
imports discord.py or aiosqlite: neither is installed on this VM.
Both are stubbed in sys.modules below, before the example module is
imported, with small fakes that implement exactly the API surface
the example uses. The locale store is still exercised against real
SQL: the aiosqlite stub runs the example's statements through
stdlib sqlite3 in memory, so the SELECT and upsert strings
themselves are tested; only the async driver is faked.

Commands are tested through their callback with a mocked
interaction, as skills/testing/SKILL.md prescribes. Expected
strings come from skills/i18n/SKILL.md and the example's own
reviewed table, never recomputed from the code under test.
"""

import copy
import enum
import importlib.util
import os
import sqlite3
import sys
import types
import unittest
from importlib.machinery import ModuleSpec, SourceFileLoader
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Stubs for discord.py and aiosqlite (stdlib only, no real imports).
# Installed into sys.modules BEFORE the example module is imported,
# so `import discord` / `import aiosqlite` inside it resolve here.
# Each fake implements only the API surface the example uses.
# ---------------------------------------------------------------------------


class _Locale(enum.Enum):
    """discord.Locale: values are the client locale tags."""

    american_english = "en-US"
    british_english = "en-GB"
    indonesian = "id"
    japanese = "ja"


class _Interaction:
    """Shape of discord.Interaction, for MagicMock(spec=...).

    Attributes must be class attributes: dir() of the class is what
    the mock spec allows, instance attributes would not count.
    """

    user = None
    locale = None
    response = None
    followup = None
    guild = None


class _HTTPException(Exception):
    pass


class _DiscordObject:
    def __init__(self, id):
        self.id = id


class _Intents:
    def __init__(self):
        self.members = False

    @classmethod
    def default(cls):
        return cls()


class _LocaleStr(str):
    """discord.app_commands.locale_str: a str with a .message."""

    def __new__(cls, message):
        obj = super().__new__(cls, message)
        obj.message = message
        return obj


class _Choice:
    def __init__(self, name, value):
        self.name = name
        self.value = value


class _AppCommandError(Exception):
    pass


class _Translator:
    pass


class _FakeCommand:
    """What @app_commands.command returns: carries .callback."""

    def __init__(self, func, name=None, description=None):
        self.callback = func
        self.name = name
        self.description = description


def _command(name=None, description=None):
    def decorator(func):
        return _FakeCommand(func, name=name, description=description)

    return decorator


def _passthrough_decorator(**kwargs):
    """@app_commands.describe / @app_commands.choices: keep the func."""

    def decorator(func):
        return func

    return decorator


class _CommandTree:
    def __init__(self):
        self.translator = None

    def error(self, func):
        return func

    def copy_global_to(self, guild):
        return None

    async def sync(self, guild=None):
        return []


class _Bot:
    def __init__(self, command_prefix=None, intents=None):
        self.command_prefix = command_prefix
        self.intents = intents
        self.tree = _CommandTree()
        self.user = None

    async def add_cog(self, cog):
        self._cog = cog

    async def close(self):
        pass

    def run(self, token):
        self._token = token


class _Cog:
    pass


class _FakeAiosqliteCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    async def fetchone(self):
        return self._cursor.fetchone()


class _FakeAiosqliteConnection:
    """aiosqlite.Connection stand-in: real SQL via stdlib sqlite3."""

    def __init__(self, path=":memory:"):
        self._conn = sqlite3.connect(path)

    async def execute(self, sql, parameters=()):
        return _FakeAiosqliteCursor(self._conn.execute(sql, parameters))

    async def commit(self):
        self._conn.commit()

    async def close(self):
        self._conn.close()


async def _aiosqlite_connect(path=":memory:"):
    return _FakeAiosqliteConnection(path)


_STUB_NAMES = ("discord", "discord.app_commands", "discord.ext",
               "discord.ext.commands", "aiosqlite")
_PREVIOUS_MODULES: dict = {}


def _install_stubs():
    global _PREVIOUS_MODULES
    _PREVIOUS_MODULES = {name: sys.modules.get(name) for name in _STUB_NAMES}
    discord_mod = types.ModuleType("discord")
    discord_mod.Locale = _Locale
    discord_mod.Interaction = _Interaction
    discord_mod.HTTPException = _HTTPException
    discord_mod.Object = _DiscordObject
    discord_mod.Intents = _Intents

    app_commands_mod = types.ModuleType("discord.app_commands")
    app_commands_mod.Translator = _Translator
    app_commands_mod.locale_str = _LocaleStr
    app_commands_mod.Choice = _Choice
    app_commands_mod.AppCommandError = _AppCommandError
    app_commands_mod.command = _command
    app_commands_mod.describe = _passthrough_decorator
    app_commands_mod.choices = _passthrough_decorator
    discord_mod.app_commands = app_commands_mod

    ext_mod = types.ModuleType("discord.ext")
    ext_mod.__path__ = []
    commands_mod = types.ModuleType("discord.ext.commands")
    commands_mod.Bot = _Bot
    commands_mod.Cog = _Cog
    ext_mod.commands = commands_mod
    discord_mod.ext = ext_mod

    aiosqlite_mod = types.ModuleType("aiosqlite")
    aiosqlite_mod.Connection = _FakeAiosqliteConnection
    aiosqlite_mod.connect = _aiosqlite_connect

    # A module in sys.modules with __spec__ set to None makes
    # importlib.util.find_spec() raise ValueError, which broke a
    # neighbouring test module when the suite ran together. Give every
    # stand-in a spec so find_spec works.
    discord_mod.__spec__ = ModuleSpec("discord", loader=None, is_package=True)
    discord_mod.__path__ = []
    discord_mod._is_test_stub = True
    app_commands_mod.__spec__ = ModuleSpec("discord.app_commands", loader=None)
    ext_mod.__spec__ = ModuleSpec("discord.ext", loader=None, is_package=True)
    commands_mod.__spec__ = ModuleSpec("discord.ext.commands", loader=None)
    aiosqlite_mod.__spec__ = ModuleSpec("aiosqlite", loader=None)

    sys.modules["discord"] = discord_mod
    sys.modules["discord.app_commands"] = app_commands_mod
    sys.modules["discord.ext"] = ext_mod
    sys.modules["discord.ext.commands"] = commands_mod
    sys.modules["aiosqlite"] = aiosqlite_mod


def _remove_stubs():
    """Restore whatever sys.modules held before _install_stubs."""
    for name in _STUB_NAMES:
        prev = _PREVIOUS_MODULES.get(name)
        if prev is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = prev


_install_stubs()


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "i18n_bot_example",
        REPO_ROOT / "examples" / "i18n_bot.py",
        loader=SourceFileLoader(
            "i18n_bot_example", str(REPO_ROOT / "examples" / "i18n_bot.py")
        ),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


i18n_bot = _load_example_module()

# Names bound from the stubs above, never from real packages.
discord = sys.modules["discord"]
app_commands = sys.modules["discord.app_commands"]
aiosqlite = sys.modules["aiosqlite"]

# The example module is imported now, so the stand-ins have served their
# purpose. Remove them again so the rest of the process (and the other
# test modules) sees a plain interpreter: names this file already bound
# keep pointing at the stand-in objects, and nothing else is affected.
_remove_stubs()


def make_interaction(user_id=1, locale=discord.Locale.american_english):
    """A mocked interaction in the shape skills/testing/SKILL.md uses."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.mention = f"<@{user_id}>"
    interaction.locale = locale
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


def sent_text(interaction):
    """The message text the user would see from a send_message call."""
    interaction.response.send_message.assert_awaited_once()
    return interaction.response.send_message.await_args.args[0]


class TestFallbackChain(unittest.TestCase):
    def test_indonesian_reply_uses_indonesian_table(self):
        self.assertEqual(
            i18n_bot.t("id", "shop.buy.success", item="Brick", price=118),
            "Membeli Brick seharga 118 gold.",
        )

    def test_english_reply_uses_english_table(self):
        self.assertEqual(
            i18n_bot.t("en", "shop.buy.success", item="Brick", price=118),
            "Bought Brick for 118 gold.",
        )

    def test_unsupported_locale_falls_back_to_english(self):
        self.assertEqual(
            i18n_bot.t("ja", "greet.hello", user="<@1>"),
            "Hello, <@1>!",
        )

    def test_missing_key_falls_back_to_the_key_itself(self):
        self.assertEqual(i18n_bot.t("id", "no.such.key"), "no.such.key")
        self.assertEqual(i18n_bot.t("en", "no.such.key"), "no.such.key")

    def test_missing_indonesian_key_falls_back_to_english(self):
        # Drop one Indonesian translation, then prove the English text
        # (not a crash, not an empty reply) is what the user sees.
        removed = i18n_bot.STRINGS["id"].pop("greet.hello")
        i18n_bot._TEMPLATE_CACHE.clear()
        try:
            self.assertEqual(
                i18n_bot.t("id", "greet.hello", user="<@1>"),
                "Hello, <@1>!",
            )
        finally:
            i18n_bot.STRINGS["id"]["greet.hello"] = removed
            i18n_bot._TEMPLATE_CACHE.clear()

    def test_client_locale_variants_map_to_base_language(self):
        self.assertEqual(
            i18n_bot.t("en-US", "greet.hello", user="<@1>"),
            "Hello, <@1>!",
        )
        self.assertEqual(
            i18n_bot.t("en-GB", "greet.hello", user="<@1>"),
            "Hello, <@1>!",
        )

    def test_cache_is_keyed_by_locale_and_key(self):
        i18n_bot._TEMPLATE_CACHE.clear()
        indonesian = i18n_bot.t("id", "greet.hello", user="<@1>")
        english = i18n_bot.t("en", "greet.hello", user="<@1>")
        self.assertEqual(indonesian, "Halo, <@1>!")
        self.assertEqual(english, "Hello, <@1>!")
        self.assertNotEqual(indonesian, english)
        # The second language did not get the first language's cached
        # template: both (locale, key) entries exist and differ.
        self.assertIn(("id", "greet.hello"), i18n_bot._TEMPLATE_CACHE)
        self.assertIn(("en", "greet.hello"), i18n_bot._TEMPLATE_CACHE)
        self.assertNotEqual(
            i18n_bot._TEMPLATE_CACHE[("id", "greet.hello")],
            i18n_bot._TEMPLATE_CACHE[("en", "greet.hello")],
        )

    def test_normalize_locale(self):
        self.assertEqual(
            i18n_bot.normalize_locale(discord.Locale.indonesian), "id"
        )
        self.assertEqual(
            i18n_bot.normalize_locale(discord.Locale.american_english), "en"
        )
        self.assertEqual(i18n_bot.normalize_locale("en-US"), "en")
        self.assertEqual(i18n_bot.normalize_locale("pt-BR"), "pt")
        self.assertEqual(i18n_bot.normalize_locale(None), "en")

    def test_no_em_dash_in_any_shipped_string(self):
        for locale, strings in i18n_bot.STRINGS.items():
            for key, text in strings.items():
                self.assertNotIn(
                    "\u2014", text, f"{locale}:{key} contains an em dash"
                )

    def test_shipped_table_validates_clean(self):
        self.assertEqual(i18n_bot.validate_table(i18n_bot.STRINGS), [])

    def test_validate_table_catches_dropped_placeholder(self):
        broken = copy.deepcopy(i18n_bot.STRINGS)
        broken["id"]["shop.buy.success"] = "Membeli {item}."
        errors = i18n_bot.validate_table(broken)
        self.assertEqual(len(errors), 1)
        self.assertIn("id:shop.buy.success", errors[0])
        self.assertIn("price", errors[0])

    def test_validate_table_catches_key_with_no_english_source(self):
        broken = copy.deepcopy(i18n_bot.STRINGS)
        broken["id"]["only.in.indonesian"] = "Hanya bahasa Indonesia."
        errors = i18n_bot.validate_table(broken)
        self.assertEqual(len(errors), 1)
        self.assertIn("has no English source", errors[0])

    def test_validate_table_catches_missing_english_table(self):
        self.assertEqual(
            i18n_bot.validate_table({"id": {"greet.hello": "Halo!"}}),
            ["table has no English ('en') source"],
        )


class TestLocaleStore(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = await aiosqlite.connect(":memory:")
        await i18n_bot.init_db(self.db)

    async def asyncTearDown(self):
        await self.db.close()

    async def test_unknown_user_defaults_to_english(self):
        self.assertEqual(await i18n_bot.get_locale(self.db, 1), "en")

    async def test_set_then_get_round_trips(self):
        await i18n_bot.set_locale(self.db, 1, "id")
        self.assertEqual(await i18n_bot.get_locale(self.db, 1), "id")

    async def test_set_overwrites_previous_choice(self):
        await i18n_bot.set_locale(self.db, 1, "id")
        await i18n_bot.set_locale(self.db, 1, "en")
        self.assertEqual(await i18n_bot.get_locale(self.db, 1), "en")

    async def test_users_are_independent(self):
        await i18n_bot.set_locale(self.db, 1, "id")
        self.assertEqual(await i18n_bot.get_locale(self.db, 2), "en")

    async def test_unsupported_locale_is_rejected_and_stores_nothing(self):
        with self.assertRaises(ValueError):
            await i18n_bot.set_locale(self.db, 1, "xx")
        self.assertEqual(await i18n_bot.get_locale(self.db, 1), "en")


class TestResolveLocale(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = await aiosqlite.connect(":memory:")
        await i18n_bot.init_db(self.db)

    async def asyncTearDown(self):
        await self.db.close()

    async def test_stored_preference_beats_client_locale(self):
        await i18n_bot.set_locale(self.db, 1, "id")
        interaction = make_interaction(
            user_id=1, locale=discord.Locale.american_english
        )
        self.assertEqual(
            await i18n_bot.resolve_locale(interaction, self.db), "id"
        )

    async def test_explicit_english_beats_indonesian_client(self):
        await i18n_bot.set_locale(self.db, 1, "en")
        interaction = make_interaction(
            user_id=1, locale=discord.Locale.indonesian
        )
        self.assertEqual(
            await i18n_bot.resolve_locale(interaction, self.db), "en"
        )

    async def test_no_stored_preference_uses_client_locale(self):
        interaction = make_interaction(
            user_id=1, locale=discord.Locale.indonesian
        )
        self.assertEqual(
            await i18n_bot.resolve_locale(interaction, self.db), "id"
        )

    async def test_no_database_uses_client_locale(self):
        interaction = make_interaction(
            user_id=1, locale=discord.Locale.indonesian
        )
        self.assertEqual(
            await i18n_bot.resolve_locale(interaction, None), "id"
        )


class TestAppTranslator(unittest.IsolatedAsyncioTestCase):
    async def test_command_description_translated_to_indonesian(self):
        translator = i18n_bot.AppTranslator()
        text = await translator.translate(
            app_commands.locale_str("Greet someone in this server."),
            discord.Locale.indonesian,
            None,
        )
        self.assertEqual(text, "Sapa seseorang di server ini.")

    async def test_parameter_descriptions_translated_to_indonesian(self):
        translator = i18n_bot.AppTranslator()
        for source, expected in (
            ("The item to buy.", "Barang yang mau dibeli."),
            ("The price in gold.", "Harga dalam gold."),
            ("The language to use.", "Bahasa yang mau dipakai."),
        ):
            with self.subTest(source=source):
                text = await translator.translate(
                    app_commands.locale_str(source),
                    discord.Locale.indonesian,
                    None,
                )
                self.assertEqual(text, expected)

    async def test_american_english_gets_english_source(self):
        translator = i18n_bot.AppTranslator()
        text = await translator.translate(
            app_commands.locale_str("Buy an item from the shop."),
            discord.Locale.american_english,
            None,
        )
        self.assertEqual(text, "Buy an item from the shop.")

    async def test_missing_translation_returns_none(self):
        translator = i18n_bot.AppTranslator()
        self.assertIsNone(
            await translator.translate(
                app_commands.locale_str("No such description."),
                discord.Locale.indonesian,
                None,
            )
        )

    async def test_unsupported_locale_returns_none(self):
        translator = i18n_bot.AppTranslator()
        self.assertIsNone(
            await translator.translate(
                app_commands.locale_str("Greet someone in this server."),
                discord.Locale.japanese,
                None,
            )
        )


class TestCommands(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = await aiosqlite.connect(":memory:")
        await i18n_bot.init_db(self.db)
        self.cog = i18n_bot.I18nCog(bot=MagicMock())
        self.cog.bot.db = self.db

    async def asyncTearDown(self):
        await self.db.close()

    async def test_greet_renders_in_every_supported_locale(self):
        for locale, expected in (
            ("en", "Hello, <@1>!"),
            ("id", "Halo, <@1>!"),
        ):
            with self.subTest(locale=locale):
                await i18n_bot.set_locale(self.db, 1, locale)
                interaction = make_interaction(user_id=1)
                await self.cog.greet.callback(self.cog, interaction)
                self.assertEqual(sent_text(interaction), expected)

    async def test_greet_uses_client_locale_without_stored_preference(self):
        interaction = make_interaction(
            user_id=1, locale=discord.Locale.indonesian
        )
        await self.cog.greet.callback(self.cog, interaction)
        self.assertEqual(sent_text(interaction), "Halo, <@1>!")

    async def test_greet_defaults_to_english(self):
        interaction = make_interaction(
            user_id=1, locale=discord.Locale.american_english
        )
        await self.cog.greet.callback(self.cog, interaction)
        self.assertEqual(sent_text(interaction), "Hello, <@1>!")

    async def test_buy_success_in_indonesian(self):
        await i18n_bot.set_locale(self.db, 1, "id")
        interaction = make_interaction(user_id=1)
        await self.cog.buy.callback(
            self.cog, interaction, item="Brick", price=118
        )
        self.assertEqual(
            sent_text(interaction), "Membeli Brick seharga 118 gold."
        )

    async def test_buy_success_in_english(self):
        interaction = make_interaction(user_id=1)
        await self.cog.buy.callback(
            self.cog, interaction, item="Brick", price=118
        )
        self.assertEqual(
            sent_text(interaction), "Bought Brick for 118 gold."
        )

    async def test_buy_zero_price_is_rejected_ephemerally(self):
        interaction = make_interaction(user_id=1)
        await self.cog.buy.callback(
            self.cog, interaction, item="Brick", price=0
        )
        self.assertEqual(
            sent_text(interaction), "Price must be more than 0 gold."
        )
        kwargs = interaction.response.send_message.await_args.kwargs
        self.assertTrue(kwargs.get("ephemeral"))

    async def test_language_switch_confirms_in_the_new_language(self):
        interaction = make_interaction(
            user_id=1, locale=discord.Locale.american_english
        )
        await self.cog.language.callback(self.cog, interaction, locale="id")
        self.assertEqual(
            sent_text(interaction), "Bahasa diatur ke Bahasa Indonesia."
        )
        self.assertEqual(await i18n_bot.get_locale(self.db, 1), "id")

    async def test_next_command_uses_the_new_preference(self):
        first = make_interaction(
            user_id=1, locale=discord.Locale.american_english
        )
        await self.cog.language.callback(self.cog, first, locale="id")
        second = make_interaction(
            user_id=1, locale=discord.Locale.american_english
        )
        await self.cog.greet.callback(self.cog, second)
        self.assertEqual(sent_text(second), "Halo, <@1>!")

    async def test_language_rejects_unsupported_value(self):
        interaction = make_interaction(
            user_id=1, locale=discord.Locale.indonesian
        )
        await self.cog.language.callback(self.cog, interaction, locale="xx")
        self.assertEqual(
            sent_text(interaction), "Bahasa itu belum didukung."
        )
        self.assertEqual(await i18n_bot.get_locale(self.db, 1), "en")

    async def test_app_command_error_answers_in_user_language(self):
        interaction = make_interaction(
            user_id=1, locale=discord.Locale.indonesian
        )
        interaction.response.is_done = MagicMock(return_value=False)
        previous_db = i18n_bot.bot.db
        i18n_bot.bot.db = self.db
        try:
            await i18n_bot.on_app_command_error(
                interaction, app_commands.AppCommandError("boom")
            )
        finally:
            i18n_bot.bot.db = previous_db
        self.assertEqual(
            sent_text(interaction), "Terjadi kesalahan. Coba lagi."
        )


class TestBotWiring(unittest.IsolatedAsyncioTestCase):
    async def test_setup_hook_connects_db_sets_translator_and_syncs(self):
        bot = i18n_bot.I18nBot(db_path=":memory:")
        old = os.environ.pop("TEST_GUILD_ID", None)
        try:
            await bot.setup_hook()
        finally:
            if old is not None:
                os.environ["TEST_GUILD_ID"] = old
        self.assertIsNotNone(bot.db)
        self.assertIsInstance(bot.tree.translator, i18n_bot.AppTranslator)
        await i18n_bot.set_locale(bot.db, 7, "id")
        self.assertEqual(await i18n_bot.get_locale(bot.db, 7), "id")
        await bot.close()
        self.assertIsNone(bot.db)


if __name__ == "__main__":
    unittest.main()
