#!/usr/bin/env python3
"""Tests for the shop example: examples/shop.py.

Stdlib only. Run with plain python3 from the repo root:
    python3 -m unittest tests.test_example_shop -v
or:
    python3 tests/test_example_shop.py

discord.py and aiosqlite are NOT installed on this VM, so this file
stubs both in sys.modules BEFORE importing the example module (see
_install_stubs below). The discord stub emulates only what the
example uses: app_commands.command / autocomplete / checks.cooldown
(with a real token-bucket predicate), Choice, Range, GroupCog, Cog,
Bot with a command tree, Interaction, Intents, and Object. The
aiosqlite stub wraps stdlib sqlite3 in autocommit mode, which is
what real aiosqlite does, so BEGIN IMMEDIATE / COMMIT / ROLLBACK
behave the same way. No Discord token, no network to Discord.
Commands are exercised through their callbacks with a mocked
interaction, and the database is a fresh temp file per test.
"""

import asyncio
import importlib.util
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from importlib.machinery import ModuleSpec
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------
# Stubs for discord.py and aiosqlite. Installed into sys.modules
# before the example module is imported, so `import discord` and
# `import aiosqlite` inside examples/shop.py resolve to these.
# ---------------------------------------------------------------------


class _AppCommandError(Exception):
    """Stub for discord.app_commands.AppCommandError."""


class _CheckFailure(_AppCommandError):
    """Stub for discord.app_commands.CheckFailure."""


class _Cooldown:
    """Stub for discord.app_commands.Cooldown."""

    def __init__(self, rate, per):
        self.rate = rate
        self.per = per


class _CommandOnCooldown(_AppCommandError):
    """Stub for discord.app_commands.CommandOnCooldown."""

    def __init__(self, cooldown, retry_after):
        super().__init__(
            "You are on cooldown. Try again in %.1f seconds." % retry_after
        )
        self.cooldown = cooldown
        self.retry_after = retry_after


class _Choice:
    """Stub for discord.app_commands.Choice."""

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __class_getitem__(cls, params):
        # Real Choice is generic (Choice[str]); annotations subscript it.
        return cls


class _Range:
    """Stub for discord.app_commands.Range.

    Only used as an annotation (Range[int, 1, 10]), so subscribing
    just needs to return something.
    """

    def __class_getitem__(cls, params):
        return cls


def _cooldown_decorator(rate, per, *, key=None):
    """Stub for app_commands.checks.cooldown, with a real bucket.

    First call for a key passes; a second call inside the window
    raises CommandOnCooldown with the remaining wait, like the real
    decorator. The bucket lives in this closure, exactly as the real
    decorator keeps one per command.
    """

    def decorator(func):
        buckets = {}
        cooldown = _Cooldown(rate, per)

        async def predicate(interaction):
            bucket_key = key(interaction) if key else interaction.user.id
            now = time.monotonic()
            last = buckets.get(bucket_key)
            if last is not None and now - last < per:
                raise _CommandOnCooldown(cooldown, per - (now - last))
            buckets[bucket_key] = now
            return True

        checks = getattr(func, "_stub_checks", None)
        if checks is None:
            checks = []
            func._stub_checks = checks
        checks.append(predicate)
        return func

    return decorator


def _autocomplete_decorator(**kwargs):
    """Stub for app_commands.autocomplete: records, passes through."""

    def decorator(func):
        func._stub_autocomplete = dict(kwargs)
        return func

    return decorator


class _FakeCommand:
    """What the app_commands.command stub returns.

    Holds the raw callback (so tests can call
    cog.buy.callback(cog, interaction, ...) exactly like the
    testing skill does with the real library) plus the checks the
    decorators attached.
    """

    def __init__(self, func, name, description=None):
        self.callback = func
        self.func = func
        self.name = name
        self.description = description
        self.qualified_name = name
        self.checks = list(getattr(func, "_stub_checks", []))
        self.autocomplete = getattr(func, "_stub_autocomplete", {})


def _command_decorator(name=None, description=None):
    """Stub for app_commands.command."""

    def decorator(func):
        return _FakeCommand(func, name or func.__name__, description)

    return decorator


class _FakeGroup:
    """A stub command group, as returned by tree.get_command("shop")."""

    def __init__(self, name, description=None):
        self.name = name
        self.description = description
        self.qualified_name = name
        self.commands = []


class _FakeTree:
    """Stub for discord.app_commands.CommandTree (get/sync only)."""

    def __init__(self):
        self._commands = {}

    def get_command(self, name):
        return self._commands.get(name)

    async def sync(self, guild=None):
        return []

    def copy_global_to(self, guild=None):
        pass


class _Cog:
    """Stub for discord.ext.commands.Cog."""

    def __init__(self, *args, **kwargs):
        if args:
            self.bot = args[0]
        elif "bot" in kwargs:
            self.bot = kwargs["bot"]


class _GroupCog(_Cog):
    """Stub for discord.ext.commands.GroupCog.

    Accepts group_name / group_description as class kwargs, like the
    real GroupCog, and remembers them for tree registration.
    """

    __cog_group_name__ = None
    __cog_group_description__ = None

    def __init_subclass__(cls, *, group_name=None, group_description=None,
                          **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__cog_group_name__ = group_name
        cls.__cog_group_description__ = group_description


class _FakeBot:
    """Stub for discord.ext.commands.Bot (cogs + tree only)."""

    def __init__(self, command_prefix=None, intents=None, **kwargs):
        self.command_prefix = command_prefix
        self.intents = intents
        self.tree = _FakeTree()
        self.db = None
        self.db_lock = None
        self._cogs = {}

    async def add_cog(self, cog):
        self._cogs[type(cog).__name__] = cog
        group_name = getattr(type(cog), "__cog_group_name__", None)
        group = None
        if group_name:
            group = _FakeGroup(
                group_name,
                getattr(type(cog), "__cog_group_description__", None),
            )
            self.tree._commands[group_name] = group
        for attr in vars(type(cog)).values():
            if isinstance(attr, _FakeCommand):
                if group is not None:
                    attr.qualified_name = "%s %s" % (group_name, attr.name)
                    group.commands.append(attr)
                else:
                    attr.qualified_name = attr.name
                    self.tree._commands[attr.name] = attr

    def get_cog(self, name):
        return self._cogs.get(name)

    async def close(self):
        pass


class _Intents:
    """Stub for discord.Intents (default() only)."""

    def __init__(self):
        self.members = False

    @classmethod
    def default(cls):
        return cls()


class _Interaction:
    """Stub for discord.Interaction.

    The attributes are class-level so MagicMock(spec=...) in the
    tests allows them; the tests replace them per interaction.
    """

    user = None
    id = None
    created_at = None
    response = None
    followup = None
    command = None
    guild = None
    channel = None


class _Object:
    """Stub for discord.Object."""

    def __init__(self, id):
        self.id = id


class _AioCursor:
    """Cursor for the aiosqlite stub: async fetch, async iteration."""

    def __init__(self, rows):
        self._rows = list(rows)

    async def fetchone(self):
        return self._rows[0] if self._rows else None

    async def fetchall(self):
        return list(self._rows)

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for row in self._rows:
            yield row


class _AioConnection:
    """Connection for the aiosqlite stub.

    stdlib sqlite3 in autocommit mode (isolation_level=None), which
    is what real aiosqlite uses, so explicit BEGIN IMMEDIATE /
    COMMIT / ROLLBACK work the same way.
    """

    def __init__(self, path):
        self._conn = sqlite3.connect(path, isolation_level=None)

    async def execute(self, sql, parameters=()):
        cursor = self._conn.execute(sql, parameters)
        return _AioCursor(cursor.fetchall())

    async def executemany(self, sql, seq_of_parameters):
        self._conn.executemany(sql, seq_of_parameters)

    async def executescript(self, sql):
        self._conn.executescript(sql)

    async def commit(self):
        self._conn.commit()

    async def rollback(self):
        self._conn.rollback()

    async def close(self):
        self._conn.close()


async def _aio_connect(path):
    return _AioConnection(path)


_STUB_NAMES = ("discord", "discord.app_commands", "discord.app_commands.checks",
               "discord.ext", "discord.ext.commands", "aiosqlite")
_PREVIOUS_MODULES: dict = {}


def _install_stubs():
    global _PREVIOUS_MODULES
    _PREVIOUS_MODULES = {name: sys.modules.get(name) for name in _STUB_NAMES}
    app_commands = types.ModuleType("discord.app_commands")
    app_commands.AppCommandError = _AppCommandError
    app_commands.CheckFailure = _CheckFailure
    app_commands.Cooldown = _Cooldown
    app_commands.CommandOnCooldown = _CommandOnCooldown
    app_commands.Choice = _Choice
    app_commands.Range = _Range
    app_commands.command = _command_decorator
    app_commands.autocomplete = _autocomplete_decorator
    checks = types.ModuleType("discord.app_commands.checks")
    checks.cooldown = _cooldown_decorator
    app_commands.checks = checks

    commands = types.ModuleType("discord.ext.commands")
    commands.Cog = _Cog
    commands.GroupCog = _GroupCog
    commands.Bot = _FakeBot

    ext = types.ModuleType("discord.ext")
    ext.commands = commands

    discord = types.ModuleType("discord")
    discord.Intents = _Intents
    discord.Interaction = _Interaction
    discord.Object = _Object
    discord.app_commands = app_commands
    discord.ext = ext

    aiosqlite = types.ModuleType("aiosqlite")
    aiosqlite.connect = _aio_connect
    aiosqlite.Connection = _AioConnection
    aiosqlite.IntegrityError = sqlite3.IntegrityError

    # A module in sys.modules with __spec__ set to None makes
    # importlib.util.find_spec() raise ValueError, which broke a
    # neighbouring test module when the suite ran together. Give every
    # stand-in a spec so find_spec works.
    discord.__spec__ = ModuleSpec("discord", loader=None, is_package=True)
    discord.__path__ = []
    discord._is_test_stub = True
    app_commands.__spec__ = ModuleSpec("discord.app_commands", loader=None)
    checks.__spec__ = ModuleSpec("discord.app_commands.checks", loader=None)
    ext.__spec__ = ModuleSpec("discord.ext", loader=None, is_package=True)
    ext.__path__ = []
    commands.__spec__ = ModuleSpec("discord.ext.commands", loader=None)
    aiosqlite.__spec__ = ModuleSpec("aiosqlite", loader=None)

    sys.modules["discord"] = discord
    sys.modules["discord.app_commands"] = app_commands
    sys.modules["discord.app_commands.checks"] = checks
    sys.modules["discord.ext"] = ext
    sys.modules["discord.ext.commands"] = commands
    sys.modules["aiosqlite"] = aiosqlite


def _remove_stubs():
    """Restore whatever sys.modules held before _install_stubs."""
    for name in _STUB_NAMES:
        prev = _PREVIOUS_MODULES.get(name)
        if prev is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = prev


_install_stubs()

import discord
from discord.ext import commands

REPO_ROOT = Path(__file__).resolve().parent.parent
SHOP_PY = REPO_ROOT / "examples" / "shop.py"

_spec = importlib.util.spec_from_file_location("shop_example", SHOP_PY)
shop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shop)

# The example module is imported now, so the stand-ins have served their
# purpose. Remove them again so the rest of the process (and the other
# test modules) sees a plain interpreter: names this file already bound
# keep pointing at the stand-in objects, and nothing else is affected.
_remove_stubs()


def make_interaction(user_id: int = 1, interaction_id: int = 100) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.id = interaction_id
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


def make_bot(database=None) -> MagicMock:
    bot = MagicMock()
    bot.db = database
    bot.db_lock = asyncio.Lock()
    return bot


def reply_text(interaction: MagicMock) -> str:
    return interaction.response.send_message.await_args.args[0]


def reply_kwargs(interaction: MagicMock) -> dict:
    return interaction.response.send_message.await_args.kwargs


async def ledger_sum(db, user_id: int) -> int:
    cursor = await db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    return row[0]


class ShopFileTest(unittest.TestCase):
    def test_files_exist(self):
        self.assertTrue(SHOP_PY.is_file(), "examples/shop.py missing")

    def test_follows_the_economy_skill(self):
        text = SHOP_PY.read_text(encoding="utf-8")
        for needle in (
            "PRAGMA journal_mode=WAL",
            "PRAGMA busy_timeout=5000",
            "PRAGMA foreign_keys=ON",
            "BEGIN IMMEDIATE",
            "idem_key",
            "CHECK (balance >= 0)",
        ):
            self.assertIn(needle, text, needle)

    def test_no_em_dash_anywhere(self):
        self.assertNotIn("\u2014", SHOP_PY.read_text(encoding="utf-8"))

    def test_token_from_environment_only(self):
        text = SHOP_PY.read_text(encoding="utf-8")
        self.assertIn("DISCORD_TOKEN", text)
        self.assertNotIn("TOKEN = ", text)

    def test_all_sql_is_parameterized(self):
        # No f-string ever builds SQL: every execute call uses "?" slots.
        text = SHOP_PY.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if "db.execute" in stripped or "db.executemany" in stripped:
                self.assertNotIn('f"', stripped, stripped)
                self.assertNotIn("f'", stripped, stripped)


class ShopDbTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "test.db")

    async def asyncSetUp(self):
        self.db = await shop.connect(self.db_path)
        await shop.init_db(self.db)
        self.lock = asyncio.Lock()

    async def asyncTearDown(self):
        if getattr(self, "db", None) is not None:
            await self.db.close()

    def tearDown(self):
        self.tmp.cleanup()

    async def test_wal_mode_and_foreign_keys_on(self):
        cursor = await self.db.execute("PRAGMA journal_mode")
        self.assertEqual((await cursor.fetchone())[0], "wal")
        cursor = await self.db.execute("PRAGMA foreign_keys")
        self.assertEqual((await cursor.fetchone())[0], 1)

    async def test_new_user_balance_is_zero(self):
        self.assertEqual(await shop.get_balance(self.db, 1), 0)

    async def test_seed_catalog_has_five_items_with_prices(self):
        items = await shop.list_items(self.db)
        self.assertEqual(
            items,
            [
                ("snack", "Trail Snack", 10, 200),
                ("potion", "Healing Potion", 50, 100),
                ("shield", "Wooden Shield", 150, 25),
                ("sword", "Iron Sword", 250, 10),
                ("cape", "Lucky Cape", 500, 5),
            ],
        )

    async def test_init_db_twice_does_not_reseed_or_duplicate(self):
        await shop.init_db(self.db)
        self.assertEqual(len(await shop.list_items(self.db)), 5)

    async def test_credit_once_pays_only_once(self):
        self.assertTrue(
            await shop.credit_once(self.db, self.lock, 1, 100, "reward", "seed:1")
        )
        self.assertFalse(
            await shop.credit_once(self.db, self.lock, 1, 100, "reward", "seed:1")
        )
        self.assertEqual(await shop.get_balance(self.db, 1), 100)

    async def test_credit_once_rejects_non_positive_amount(self):
        with self.assertRaisesRegex(ValueError, "amount must be positive"):
            await shop.credit_once(self.db, self.lock, 1, 0, "reward", "seed:0")

    async def test_buy_charges_and_records_ledger(self):
        await shop.credit_once(self.db, self.lock, 1, 1000, "reward", "seed:1")
        receipt = await shop.buy_item(
            self.db, self.lock, 1, "potion", 2, "buy:1"
        )
        self.assertEqual(
            receipt,
            {
                "item_id": "potion",
                "name": "Healing Potion",
                "quantity": 2,
                "total_price": 100,
                "balance_after": 900,
                "already_purchased": False,
            },
        )
        self.assertEqual(await shop.get_balance(self.db, 1), 900)
        self.assertEqual(
            await shop.get_inventory(self.db, 1),
            [("potion", "Healing Potion", 2)],
        )
        self.assertEqual(await ledger_sum(self.db, 1), 900)
        cursor = await self.db.execute(
            "SELECT amount, kind FROM transactions WHERE user_id = ? ORDER BY id",
            (1,),
        )
        self.assertEqual(
            await cursor.fetchall(), [(1000, "reward"), (-100, "purchase")]
        )
        items = {row[0]: row for row in await shop.list_items(self.db)}
        self.assertEqual(items["potion"][3], 98)

    async def test_buy_without_idem_key_charges_each_time(self):
        await shop.credit_once(self.db, self.lock, 1, 1000, "reward", "seed:1")
        first = await shop.buy_item(self.db, self.lock, 1, "potion", 1)
        second = await shop.buy_item(self.db, self.lock, 1, "potion", 1)
        self.assertFalse(first["already_purchased"])
        self.assertFalse(second["already_purchased"])
        self.assertEqual(await shop.get_balance(self.db, 1), 900)

    async def test_buy_insufficient_funds_changes_nothing(self):
        await shop.credit_once(self.db, self.lock, 1, 100, "reward", "seed:1")
        with self.assertRaisesRegex(ValueError, "insufficient funds"):
            await shop.buy_item(self.db, self.lock, 1, "sword", 1, "buy:1")
        self.assertEqual(await shop.get_balance(self.db, 1), 100)
        self.assertEqual(await shop.get_inventory(self.db, 1), [])
        self.assertEqual(await ledger_sum(self.db, 1), 100)
        items = {row[0]: row for row in await shop.list_items(self.db)}
        self.assertEqual(items["sword"][3], 10)

    async def test_buy_unknown_item_raises(self):
        with self.assertRaisesRegex(ValueError, "unknown item"):
            await shop.buy_item(self.db, self.lock, 1, "dragon", 1, "buy:1")

    async def test_buy_rejects_quantity_out_of_range(self):
        for bad in (0, 11):
            with self.assertRaisesRegex(
                ValueError, "quantity must be between 1 and 10"
            ):
                await shop.buy_item(self.db, self.lock, 1, "potion", bad, "buy:1")

    async def test_buy_out_of_stock_changes_nothing(self):
        await shop.credit_once(self.db, self.lock, 1, 10000, "reward", "seed:1")
        await shop.buy_item(self.db, self.lock, 1, "cape", 5, "buy:cape")
        with self.assertRaisesRegex(ValueError, "not enough stock"):
            await shop.buy_item(self.db, self.lock, 1, "cape", 1, "buy:cape2")
        self.assertEqual(await shop.get_balance(self.db, 1), 7500)

    async def test_buy_same_idem_key_charges_once(self):
        await shop.credit_once(self.db, self.lock, 1, 1000, "reward", "seed:1")
        first = await shop.buy_item(self.db, self.lock, 1, "potion", 2, "buy:1")
        second = await shop.buy_item(self.db, self.lock, 1, "potion", 2, "buy:1")
        self.assertFalse(first["already_purchased"])
        self.assertTrue(second["already_purchased"])
        self.assertEqual(second["total_price"], 100)
        self.assertEqual(await shop.get_balance(self.db, 1), 900)
        self.assertEqual(
            await shop.get_inventory(self.db, 1),
            [("potion", "Healing Potion", 2)],
        )

    async def test_concurrent_buy_same_key_charges_once(self):
        await shop.credit_once(self.db, self.lock, 1, 1000, "reward", "seed:1")
        results = await asyncio.gather(
            shop.buy_item(self.db, self.lock, 1, "potion", 2, "buy:race"),
            shop.buy_item(self.db, self.lock, 1, "potion", 2, "buy:race"),
        )
        self.assertEqual(
            sum(1 for r in results if not r["already_purchased"]), 1
        )
        self.assertEqual(await shop.get_balance(self.db, 1), 900)

    async def test_concurrent_buy_of_last_stock_only_one_succeeds(self):
        await shop.credit_once(self.db, self.lock, 1, 3000, "reward", "seed:1")
        await shop.credit_once(self.db, self.lock, 2, 3000, "reward", "seed:2")
        await shop.buy_item(self.db, self.lock, 1, "cape", 4, "buy:cape4")
        results = await asyncio.gather(
            shop.buy_item(self.db, self.lock, 1, "cape", 1, "buy:last1"),
            shop.buy_item(self.db, self.lock, 2, "cape", 1, "buy:last2"),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, ValueError)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertEqual(str(failures[0]), "not enough stock")
        items = {row[0]: row for row in await shop.list_items(self.db)}
        self.assertEqual(items["cape"][3], 0)

    async def test_sell_returns_half_price_and_restores_stock(self):
        await shop.credit_once(self.db, self.lock, 1, 1000, "reward", "seed:1")
        await shop.buy_item(self.db, self.lock, 1, "sword", 1, "buy:1")
        receipt = await shop.sell_item(
            self.db, self.lock, 1, "sword", 1, "sell:1"
        )
        self.assertEqual(receipt["total_price"], 125)
        self.assertEqual(receipt["balance_after"], 875)
        self.assertFalse(receipt["already_purchased"])
        self.assertEqual(await shop.get_inventory(self.db, 1), [])
        self.assertEqual(await ledger_sum(self.db, 1), 875)
        items = {row[0]: row for row in await shop.list_items(self.db)}
        self.assertEqual(items["sword"][3], 10)

    async def test_sell_unowned_raises_and_changes_nothing(self):
        await shop.credit_once(self.db, self.lock, 1, 1000, "reward", "seed:1")
        with self.assertRaisesRegex(ValueError, "you do not own that many"):
            await shop.sell_item(self.db, self.lock, 1, "sword", 1, "sell:1")
        self.assertEqual(await shop.get_balance(self.db, 1), 1000)
        self.assertEqual(await ledger_sum(self.db, 1), 1000)

    async def test_sell_same_idem_key_credits_once(self):
        await shop.credit_once(self.db, self.lock, 1, 1000, "reward", "seed:1")
        await shop.buy_item(self.db, self.lock, 1, "potion", 2, "buy:1")
        first = await shop.sell_item(self.db, self.lock, 1, "potion", 1, "sell:1")
        second = await shop.sell_item(self.db, self.lock, 1, "potion", 1, "sell:1")
        self.assertFalse(first["already_purchased"])
        self.assertTrue(second["already_purchased"])
        # 1000 - 100 + 25 = 925; the replay must not credit a second 25.
        self.assertEqual(await shop.get_balance(self.db, 1), 925)

    async def test_balance_survives_reconnect(self):
        await shop.credit_once(self.db, self.lock, 1, 250, "reward", "seed:1")
        await shop.buy_item(self.db, self.lock, 1, "potion", 1, "buy:1")
        await self.db.close()
        self.db = None
        reopened = await shop.connect(self.db_path)
        try:
            await shop.init_db(reopened)
            self.assertEqual(await shop.get_balance(reopened, 1), 200)
            self.assertEqual(
                await shop.get_inventory(reopened, 1),
                [("potion", "Healing Potion", 1)],
            )
        finally:
            await reopened.close()

    def test_format_shop_list(self):
        text = shop.format_shop_list(
            [("potion", "Healing Potion", 50, 100)]
        )
        self.assertEqual(
            text, "Shop:\n- Healing Potion (potion): 50 gold, 100 in stock"
        )

    def test_format_inventory_empty(self):
        self.assertEqual(
            shop.format_inventory([], 42), "Your bag is empty. Balance: 42 gold."
        )

    def test_sell_unit_price_is_half_rounded_down(self):
        self.assertEqual(shop.sell_unit_price(250), 125)
        self.assertEqual(shop.sell_unit_price(11), 5)


class ShopCommandTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "test.db")

    async def asyncSetUp(self):
        self.db = await shop.connect(self.db_path)
        await shop.init_db(self.db)
        self.bot = make_bot(self.db)
        self.cog = shop.Shop(self.bot)
        self.wallet = shop.Wallet(self.bot)

    async def asyncTearDown(self):
        if getattr(self, "db", None) is not None:
            await self.db.close()

    def tearDown(self):
        self.tmp.cleanup()

    async def test_shop_list_answers_with_items_and_prices(self):
        interaction = make_interaction()
        await self.cog.list_items_command.callback(self.cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        text = reply_text(interaction)
        self.assertIn("Healing Potion (potion): 50 gold, 100 in stock", text)
        self.assertIn("Lucky Cape (cape): 500 gold, 5 in stock", text)
        self.assertNotIn("\u2014", text)

    async def test_buy_command_success_replies_with_new_balance(self):
        await shop.credit_once(self.db, self.bot.db_lock, 7, 1000, "reward", "seed:7")
        interaction = make_interaction(user_id=7, interaction_id=555)
        await self.cog.buy.callback(
            self.cog, interaction, item="potion", quantity=2
        )
        interaction.response.send_message.assert_awaited_once()
        self.assertEqual(
            reply_text(interaction),
            "You bought 2 x Healing Potion for 100 gold. Balance: 900 gold.",
        )
        self.assertEqual(await shop.get_balance(self.db, 7), 900)

    async def test_buy_command_insufficient_funds_replies_ephemeral(self):
        await shop.credit_once(self.db, self.bot.db_lock, 7, 10, "reward", "seed:7")
        interaction = make_interaction(user_id=7, interaction_id=556)
        await self.cog.buy.callback(
            self.cog, interaction, item="sword", quantity=1
        )
        interaction.response.send_message.assert_awaited_once()
        self.assertEqual(reply_text(interaction), "insufficient funds")
        self.assertTrue(reply_kwargs(interaction).get("ephemeral"))
        self.assertEqual(await shop.get_balance(self.db, 7), 10)

    async def test_buy_command_replay_same_interaction_charges_once(self):
        await shop.credit_once(self.db, self.bot.db_lock, 7, 1000, "reward", "seed:7")
        interaction = make_interaction(user_id=7, interaction_id=557)
        await self.cog.buy.callback(
            self.cog, interaction, item="potion", quantity=1
        )
        self.assertEqual(
            reply_text(interaction),
            "You bought 1 x Healing Potion for 50 gold. Balance: 950 gold.",
        )
        await self.cog.buy.callback(
            self.cog, interaction, item="potion", quantity=1
        )
        self.assertEqual(
            reply_text(interaction),
            "Already bought: 1 x Healing Potion for 50 gold. Balance: 950 gold.",
        )
        self.assertEqual(await shop.get_balance(self.db, 7), 950)

    async def test_buy_cooldown_blocks_second_call_within_window(self):
        self.assertEqual(len(self.cog.buy.checks), 1)
        self.assertEqual(len(self.cog.sell.checks), 1)
        interaction = make_interaction(user_id=9)
        check = self.cog.buy.checks[0]
        self.assertTrue(await check(interaction))
        with self.assertRaises(discord.app_commands.CommandOnCooldown) as ctx:
            await check(interaction)
        self.assertGreater(ctx.exception.retry_after, 0)
        self.assertLessEqual(ctx.exception.retry_after, 5.0)

    async def test_sell_command_success(self):
        await shop.credit_once(self.db, self.bot.db_lock, 7, 1000, "reward", "seed:7")
        await shop.buy_item(self.db, self.bot.db_lock, 7, "sword", 1, "buy:1")
        interaction = make_interaction(user_id=7, interaction_id=558)
        await self.cog.sell.callback(
            self.cog, interaction, item="sword", quantity=1
        )
        self.assertEqual(
            reply_text(interaction),
            "You sold 1 x Iron Sword for 125 gold. Balance: 875 gold.",
        )

    async def test_inventory_command_lists_owned_items(self):
        await shop.credit_once(self.db, self.bot.db_lock, 7, 1000, "reward", "seed:7")
        await shop.buy_item(self.db, self.bot.db_lock, 7, "potion", 2, "buy:1")
        interaction = make_interaction(user_id=7)
        await self.cog.inventory.callback(self.cog, interaction)
        self.assertEqual(
            reply_text(interaction),
            "Your bag:\n- 2 x Healing Potion (potion)\nBalance: 900 gold.",
        )

    async def test_inventory_command_empty_bag(self):
        interaction = make_interaction(user_id=7)
        await self.cog.inventory.callback(self.cog, interaction)
        self.assertEqual(
            reply_text(interaction), "Your bag is empty. Balance: 0 gold."
        )

    async def test_balance_command_shows_balance(self):
        await shop.credit_once(self.db, self.bot.db_lock, 7, 250, "reward", "seed:7")
        interaction = make_interaction(user_id=7)
        await self.wallet.balance.callback(self.wallet, interaction)
        self.assertEqual(reply_text(interaction), "Your balance: 250 gold.")

    async def test_autocomplete_matches_name_and_id(self):
        interaction = make_interaction()
        choices = await self.cog.item_autocomplete(interaction, "heal")
        self.assertEqual([(c.name, c.value) for c in choices],
                         [("Healing Potion", "potion")])
        choices = await self.cog.item_autocomplete(interaction, "sword")
        self.assertEqual([(c.name, c.value) for c in choices],
                         [("Iron Sword", "sword")])
        self.assertEqual(await self.cog.item_autocomplete(interaction, "zzz"), [])
        self.assertLessEqual(
            len(await self.cog.item_autocomplete(interaction, "")), 25
        )

    async def test_error_handler_answers_generic_error(self):
        interaction = make_interaction()
        interaction.response.is_done = MagicMock(return_value=False)
        await self.cog.cog_app_command_error(
            interaction, RuntimeError("boom")
        )
        interaction.response.send_message.assert_awaited_once()
        self.assertEqual(
            reply_text(interaction), "Something went wrong. The error was logged."
        )
        self.assertTrue(reply_kwargs(interaction).get("ephemeral"))

    async def test_error_handler_uses_followup_after_response_done(self):
        interaction = make_interaction()
        interaction.response.is_done = MagicMock(return_value=True)
        await self.cog.cog_app_command_error(
            interaction, RuntimeError("boom")
        )
        interaction.followup.send.assert_awaited_once()
        self.assertEqual(
            interaction.followup.send.await_args.args[0],
            "Something went wrong. The error was logged.",
        )

    async def test_error_handler_cooldown_message(self):
        interaction = make_interaction()
        interaction.response.is_done = MagicMock(return_value=False)
        error = discord.app_commands.CommandOnCooldown(
            discord.app_commands.Cooldown(1, 5.0), 3.7
        )
        await self.cog.cog_app_command_error(interaction, error)
        self.assertEqual(
            reply_text(interaction), "Slow down. Try again in 4 seconds."
        )

    async def test_commands_register_under_shop_group(self):
        bot = commands.Bot(
            command_prefix="!", intents=discord.Intents.default()
        )
        await shop.setup(bot)
        group = bot.tree.get_command("shop")
        self.assertIsNotNone(group)
        self.assertEqual(group.description, "Buy and sell items.")
        self.assertEqual(
            sorted(c.name for c in group.commands),
            ["buy", "inventory", "list", "sell"],
        )
        self.assertEqual(
            sorted(c.qualified_name for c in group.commands),
            ["shop buy", "shop inventory", "shop list", "shop sell"],
        )
        self.assertIsNotNone(bot.tree.get_command("balance"))
        await bot.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
