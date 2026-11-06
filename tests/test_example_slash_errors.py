"""Tests for examples/slash_errors.py. Standard library only.

This file never pulls in discord, aiohttp, or aiosqlite. Before the
example module is imported, setUpModule installs small stand-in
modules in sys.modules, so the example's ``discord`` import binds
to the stand-ins. tearDownModule restores sys.modules afterwards.

The stand-ins mirror the discord.py 2.5 behaviour the example
relies on (checked against discord.py 2.5.2 before writing them):

* ``InteractionResponse.is_done()`` is a plain method returning a
  bool, while ``send_message`` and ``defer`` are coroutines.
* ``CommandOnCooldown(cooldown, retry_after)`` takes a ``Cooldown``
  and a float, and is a subclass of ``CheckFailure``, as are
  ``MissingPermissions`` and ``BotMissingPermissions``.
* ``CommandInvokeError(command, error)`` stores the cause as
  ``.original``.
* ``MissingPermissions`` and ``BotMissingPermissions`` take a list
  of permission names and expose it as ``.missing_permissions``.
* ``app_commands.checks.cooldown`` raises ``CommandOnCooldown``
  when one user calls too often; the permission check decorators
  record which permissions a command requires.
* ``Command.callback`` is the plain function, called as
  ``callback(cog, interaction, ...)``.

The tests exercise the example's real code through those seams:
the pure ``error_message`` function, each command callback with a
hand-built fake interaction, and the cog error handler. No token,
no network, no real Discord connection.

Run from the repo root with the plain interpreter:

    python3 -m unittest tests.test_example_slash_errors -v
"""

import inspect
import os
import sys
import time
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

slash_errors = None
_STUBS = {}
_SAVED_MODULES = {}
_STUB_NAMES = (
    "discord",
    "discord.app_commands",
    "discord.ext",
    "discord.ext.commands",
)


# Stand-in discord.py: only the surface the example touches.


class FakeAppCommandError(Exception):
    """Stand-in for app_commands.AppCommandError."""


class FakeCheckFailure(FakeAppCommandError):
    """Stand-in for app_commands.CheckFailure."""


class FakeCooldown:
    """Stand-in for app_commands.Cooldown."""

    def __init__(self, rate, per):
        self.rate = rate
        self.per = per


class FakeCommandOnCooldown(FakeCheckFailure):
    """Stand-in for app_commands.CommandOnCooldown."""

    def __init__(self, cooldown, retry_after):
        super().__init__(f"You are on cooldown. Try again in {retry_after:.1f}s.")
        self.cooldown = cooldown
        self.retry_after = retry_after


class FakeMissingPermissions(FakeCheckFailure):
    """Stand-in for app_commands.MissingPermissions."""

    def __init__(self, missing_permissions, *args):
        super().__init__(f"Missing permissions: {missing_permissions}")
        self.missing_permissions = list(missing_permissions)


class FakeBotMissingPermissions(FakeCheckFailure):
    """Stand-in for app_commands.BotMissingPermissions."""

    def __init__(self, missing_permissions, *args):
        super().__init__(f"Bot missing permissions: {missing_permissions}")
        self.missing_permissions = list(missing_permissions)


class FakeCommandInvokeError(FakeAppCommandError):
    """Stand-in for app_commands.CommandInvokeError."""

    def __init__(self, command, error):
        super().__init__(str(error))
        self.command = command
        self.original = error


class FakeHTTPException(Exception):
    """Stand-in for discord.HTTPException."""

    def __init__(self, response, message):
        super().__init__(message)
        self.response = response
        self.status = getattr(response, "status", None)
        self.text = message


class FakeForbidden(FakeHTTPException):
    """Stand-in for discord.Forbidden."""


class FakeChoice:
    """Stand-in for app_commands.Choice."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, *, name, value):
        self.name = name
        self.value = value

    def __eq__(self, other):
        return (
            isinstance(other, FakeChoice)
            and self.name == other.name
            and self.value == other.value
        )

    def __repr__(self):
        return f"Choice(name={self.name!r}, value={self.value!r})"


class FakeInteraction:
    """Placeholder for discord.Interaction (annotations only)."""


class FakeMember:
    """Placeholder for discord.Member (annotations only)."""


class FakeIntents:
    """Stand-in for discord.Intents."""

    @classmethod
    def default(cls):
        return cls()


class FakeObject:
    """Stand-in for discord.Object."""

    def __init__(self, id):
        self.id = id


def _attach_check(func, marker):
    checks = getattr(func, "_stub_checks", None)
    if checks is None:
        checks = []
        func._stub_checks = checks
    checks.append(marker)
    return func


class FakeCommand:
    """Stand-in for app_commands.Command.

    ``.callback`` is the plain function, so tests call it the way
    the testing skill prescribes: ``cog.ping.callback(cog, ...)``.
    """

    def __init__(self, func, *, name, description):
        self.callback = func
        self.name = name
        self.description = description
        self.checks = list(getattr(func, "_stub_checks", []))
        self.autocomplete = dict(getattr(func, "_stub_autocomplete", {}))


def _command_decorator(*, name, description):
    def decorator(func):
        return FakeCommand(func, name=name, description=description)

    return decorator


def _has_permissions(**perms):
    def decorator(func):
        return _attach_check(func, ("has_permissions", perms))

    return decorator


def _bot_has_permissions(**perms):
    def decorator(func):
        return _attach_check(func, ("bot_has_permissions", perms))

    return decorator


def _cooldown(rate, per, *, key=None):
    """Per-user bucket that raises CommandOnCooldown when exceeded."""
    buckets = {}

    def check(interaction):
        lookup = key(interaction) if key is not None else interaction.user.id
        now = time.monotonic()
        start, count = buckets.get(lookup, (now, 0))
        if now - start >= per:
            start, count = now, 0
        count += 1
        buckets[lookup] = (start, count)
        if count > rate:
            raise FakeCommandOnCooldown(
                FakeCooldown(rate, per), per - (now - start)
            )
        return True

    check.rate = rate
    check.per = per

    def decorator(func):
        return _attach_check(func, ("cooldown", check))

    return decorator


def _autocomplete(**mapping):
    def decorator(func):
        existing = getattr(func, "_stub_autocomplete", None)
        if existing is None:
            existing = {}
            func._stub_autocomplete = existing
        existing.update(mapping)
        return func

    return decorator


class FakeTree:
    """Stand-in for discord.app_commands.CommandTree."""

    def __init__(self):
        self.copy_global_to_calls = []
        self.sync_calls = []

    def copy_global_to(self, guild):
        self.copy_global_to_calls.append(guild)

    async def sync(self, guild=None):
        self.sync_calls.append(guild)


class FakeBot:
    """Stand-in for discord.ext.commands.Bot."""

    last_run_token = None

    def __init__(self, command_prefix, intents):
        self.command_prefix = command_prefix
        self.intents = intents
        self.tree = FakeTree()
        self.cogs = []
        self.latency = 0.0

    async def add_cog(self, cog):
        self.cogs.append(cog)

    def run(self, token):
        type(self).last_run_token = token


class FakeCog:
    """Stand-in for discord.ext.commands.Cog."""


def _install_stubs():
    """Put the stand-in discord modules into sys.modules."""
    global _SAVED_MODULES
    _SAVED_MODULES = {
        name: sys.modules[name] for name in _STUB_NAMES if name in sys.modules
    }

    discord_mod = types.ModuleType("discord")
    discord_mod.Interaction = FakeInteraction
    discord_mod.Member = FakeMember
    discord_mod.Intents = FakeIntents
    discord_mod.Object = FakeObject
    discord_mod.HTTPException = FakeHTTPException
    discord_mod.Forbidden = FakeForbidden

    app_commands_mod = types.ModuleType("discord.app_commands")
    app_commands_mod.AppCommandError = FakeAppCommandError
    app_commands_mod.CheckFailure = FakeCheckFailure
    app_commands_mod.Cooldown = FakeCooldown
    app_commands_mod.CommandOnCooldown = FakeCommandOnCooldown
    app_commands_mod.MissingPermissions = FakeMissingPermissions
    app_commands_mod.BotMissingPermissions = FakeBotMissingPermissions
    app_commands_mod.CommandInvokeError = FakeCommandInvokeError
    app_commands_mod.Choice = FakeChoice
    app_commands_mod.command = _command_decorator
    app_commands_mod.autocomplete = _autocomplete
    app_commands_mod.checks = SimpleNamespace(
        has_permissions=_has_permissions,
        bot_has_permissions=_bot_has_permissions,
        cooldown=_cooldown,
    )

    ext_mod = types.ModuleType("discord.ext")
    commands_mod = types.ModuleType("discord.ext.commands")
    commands_mod.Cog = FakeCog
    commands_mod.Bot = FakeBot

    discord_mod.app_commands = app_commands_mod
    discord_mod.ext = ext_mod
    ext_mod.commands = commands_mod

    sys.modules["discord"] = discord_mod
    sys.modules["discord.app_commands"] = app_commands_mod
    sys.modules["discord.ext"] = ext_mod
    sys.modules["discord.ext.commands"] = commands_mod
    _STUBS["discord"] = discord_mod
    _STUBS["app_commands"] = app_commands_mod
    _STUBS["commands"] = commands_mod


def _remove_stubs():
    """Restore whatever sys.modules held before _install_stubs."""
    for name in _STUB_NAMES:
        if name in _SAVED_MODULES:
            sys.modules[name] = _SAVED_MODULES[name]
        else:
            sys.modules.pop(name, None)
    sys.modules.pop("examples.slash_errors", None)
    sys.modules.pop("examples", None)
    _STUBS.clear()
    _SAVED_MODULES.clear()


def setUpModule():
    global slash_errors
    _install_stubs()
    import examples.slash_errors as module

    slash_errors = module


def tearDownModule():
    global slash_errors
    slash_errors = None
    _remove_stubs()


# Fake interactions: hand-built, no Discord objects involved.


class FakeResponse:
    """Mimics InteractionResponse: is_done is sync, the rest async."""

    def __init__(self, done=False):
        self._done = done
        self.send_message = AsyncMock()
        self.defer = AsyncMock()

    def is_done(self):
        return self._done


class FakeFollowup:
    def __init__(self):
        self.send = AsyncMock()


class FakeUser:
    def __init__(self, user_id=7):
        self.id = user_id
        self.display_name = "Tester"
        self.mention = f"<@{user_id}>"


class FakeTestInteraction:
    """What the command sees: response, followup, user, command."""

    def __init__(self, user_id=7, response_done=False, command="ping"):
        self.user = FakeUser(user_id)
        self.response = FakeResponse(done=response_done)
        self.followup = FakeFollowup()
        self.command = command
        self.guild = None


class FakeTestMember:
    def __init__(self, member_id=9, display_name="Tester", joined_at=None):
        self.id = member_id
        self.display_name = display_name
        self.joined_at = joined_at
        self.kick = AsyncMock()


def make_cog():
    bot = SimpleNamespace(latency=0.042)
    return slash_errors.ErrorHandling(bot)


async def run_check(check, interaction):
    """Run one app-command check, awaiting it if it is async."""
    result = check(interaction)
    if inspect.isawaitable(result):
        result = await result
    return result


def sent_text(interaction):
    """The text the user would see, and which channel carried it."""
    if interaction.response.send_message.await_count:
        args = interaction.response.send_message.await_args
        return "response", args.args[0], args.kwargs
    if interaction.followup.send.await_count:
        args = interaction.followup.send.await_args
        return "followup", args.args[0], args.kwargs
    return None, None, {}


# Pure logic: error_message


class TestErrorMessage(unittest.TestCase):
    def test_cooldown_names_retry_seconds(self):
        error = FakeCommandOnCooldown(FakeCooldown(1, 60.0), 42.4)
        self.assertEqual(
            slash_errors.error_message(error),
            "Slow down. Try again in 42 seconds.",
        )

    def test_cooldown_rounds_to_nearest_second(self):
        error = FakeCommandOnCooldown(FakeCooldown(1, 60.0), 61.6)
        self.assertEqual(
            slash_errors.error_message(error),
            "Slow down. Try again in 62 seconds.",
        )

    def test_cooldown_is_not_swallowed_by_generic_check_failure(self):
        error = FakeCommandOnCooldown(FakeCooldown(1, 60.0), 42.4)
        self.assertIsInstance(error, FakeCheckFailure)
        self.assertNotEqual(
            slash_errors.error_message(error),
            "You cannot use this command here.",
        )

    def test_missing_permissions_names_what_is_needed(self):
        error = FakeMissingPermissions(["kick_members"])
        self.assertEqual(
            slash_errors.error_message(error),
            "You do not have permission to use this command. "
            "You need: kick members.",
        )

    def test_missing_permissions_without_a_list_stays_plain(self):
        error = FakeMissingPermissions([])
        self.assertEqual(
            slash_errors.error_message(error),
            "You do not have permission to use this command.",
        )

    def test_bot_missing_permissions_names_what_it_needs(self):
        error = FakeBotMissingPermissions(["kick_members", "ban_members"])
        self.assertEqual(
            slash_errors.error_message(error),
            "I do not have permission to do that. "
            "I need: kick members, ban members.",
        )

    def test_generic_check_failure(self):
        self.assertEqual(
            slash_errors.error_message(FakeCheckFailure()),
            "You cannot use this command here.",
        )

    def test_forbidden(self):
        error = FakeForbidden(SimpleNamespace(status=403), "Missing Permissions")
        self.assertEqual(
            slash_errors.error_message(error),
            "I tried to do that, but Discord refused. "
            "I may be missing a permission.",
        )

    def test_unknown_error_is_generic(self):
        self.assertEqual(
            slash_errors.error_message(RuntimeError("boom")),
            "Something went wrong. The error was logged.",
        )


# Commands through their callbacks


class TestCommands(unittest.IsolatedAsyncioTestCase):
    async def test_ping_answers_directly_with_real_latency(self):
        cog = make_cog()
        interaction = FakeTestInteraction()
        await cog.ping.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        text = interaction.response.send_message.await_args.args[0]
        self.assertEqual(text, "Pong! Latency: 42 ms")

    async def test_profile_defers_then_uses_followup(self):
        cog = make_cog()
        interaction = FakeTestInteraction()
        member = FakeTestMember(
            joined_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        )
        await cog.profile.callback(cog, interaction, member)
        interaction.response.defer.assert_awaited_once()
        interaction.response.send_message.assert_not_awaited()
        interaction.followup.send.assert_awaited_once()
        text = interaction.followup.send.await_args.args[0]
        self.assertEqual(
            text, "Profile for Tester (id 9). Joined: 2026-01-02."
        )

    async def test_profile_with_no_join_date_says_unknown(self):
        cog = make_cog()
        interaction = FakeTestInteraction()
        member = FakeTestMember(joined_at=None)
        await cog.profile.callback(cog, interaction, member)
        text = interaction.followup.send.await_args.args[0]
        self.assertEqual(
            text, "Profile for Tester (id 9). Joined: unknown."
        )

    async def test_kick_kicks_and_confirms_ephemeral(self):
        cog = make_cog()
        interaction = FakeTestInteraction(user_id=7)
        member = FakeTestMember()
        await cog.kick.callback(cog, interaction, member)
        member.kick.assert_awaited_once_with(reason="Kicked by 7")
        channel, text, kwargs = sent_text(interaction)
        self.assertEqual(channel, "response")
        self.assertEqual(text, "Tester was kicked.")
        self.assertTrue(kwargs.get("ephemeral"))

    async def test_kick_checks_both_user_and_bot_permissions(self):
        cog = make_cog()
        kinds = {}
        for kind, perms in cog.kick.checks:
            kinds[kind] = perms
        self.assertEqual(kinds.get("has_permissions"), {"kick_members": True})
        self.assertEqual(
            kinds.get("bot_has_permissions"), {"kick_members": True}
        )

    async def test_claim_answers(self):
        cog = make_cog()
        interaction = FakeTestInteraction()
        await cog.claim.callback(cog, interaction)
        channel, text, _kwargs = sent_text(interaction)
        self.assertEqual(channel, "response")
        self.assertEqual(
            text, "Claim recorded. You can claim again in 60 seconds."
        )

    async def test_claim_cooldown_fires_on_second_use_for_same_user(self):
        cog = make_cog()
        cooldown_checks = [
            check for kind, check in cog.claim.checks if kind == "cooldown"
        ]
        self.assertEqual(len(cooldown_checks), 1)
        check = cooldown_checks[0]
        self.assertEqual((check.rate, check.per), (1, 60.0))
        first = FakeTestInteraction(user_id=7)
        await run_check(check, first)
        second = FakeTestInteraction(user_id=7)
        with self.assertRaises(FakeCommandOnCooldown) as caught:
            await run_check(check, second)
        retry_after = caught.exception.retry_after
        self.assertGreater(retry_after, 0)
        self.assertLessEqual(retry_after, 60.0)
        other_user = FakeTestInteraction(user_id=8)
        await run_check(check, other_user)

    async def test_buy_autocomplete_is_wired_to_the_command(self):
        cog = make_cog()
        self.assertIs(
            cog.buy.autocomplete.get("item"), slash_errors.item_autocomplete
        )

    async def test_buy_autocomplete_caps_at_25_choices(self):
        interaction = FakeTestInteraction()
        choices = await slash_errors.item_autocomplete(interaction, "")
        self.assertEqual(len(choices), 25)
        self.assertEqual(choices[0], FakeChoice(name="Apple", value="apple"))
        self.assertEqual(choices[-1], FakeChoice(name="Mango", value="mango"))
        self.assertEqual(len(slash_errors.ITEMS), 30)

    async def test_buy_autocomplete_filters_by_prefix(self):
        interaction = FakeTestInteraction()
        names = [
            choice.name
            for choice in await slash_errors.item_autocomplete(interaction, "ap")
        ]
        self.assertEqual(names, ["Apple", "Apricot"])
        names = [
            choice.name
            for choice in await slash_errors.item_autocomplete(interaction, "c")
        ]
        self.assertEqual(
            names,
            [
                "Carrot",
                "Cheese",
                "Cherry",
                "Chocolate",
                "Coffee",
                "Cookie",
                "Corn",
                "Cucumber",
            ],
        )
        choices = await slash_errors.item_autocomplete(interaction, "zzz")
        self.assertEqual(choices, [])

    async def test_buy_known_item_answers_with_its_name(self):
        cog = make_cog()
        interaction = FakeTestInteraction()
        await cog.buy.callback(cog, interaction, "apple")
        channel, text, _kwargs = sent_text(interaction)
        self.assertEqual(channel, "response")
        self.assertEqual(text, "You picked Apple.")

    async def test_buy_unknown_item_answers_instead_of_crashing(self):
        cog = make_cog()
        interaction = FakeTestInteraction()
        await cog.buy.callback(cog, interaction, "nope")
        channel, text, kwargs = sent_text(interaction)
        self.assertEqual(channel, "response")
        self.assertEqual(
            text, "I do not recognise that item. Pick one from the list."
        )
        self.assertTrue(kwargs.get("ephemeral"))

    async def test_boom_raises(self):
        cog = make_cog()
        interaction = FakeTestInteraction()
        with self.assertRaises(RuntimeError):
            await cog.boom.callback(cog, interaction)

    def test_command_names_are_lowercase_with_no_spaces(self):
        commands = [
            value
            for value in vars(slash_errors.ErrorHandling).values()
            if isinstance(value, FakeCommand)
        ]
        self.assertEqual(
            sorted(cmd.name for cmd in commands),
            ["boom", "buy", "claim", "kick", "ping", "profile"],
        )
        for cmd in commands:
            self.assertRegex(cmd.name, r"^[a-z][a-z0-9_]{0,31}$")
            self.assertNotIn(" ", cmd.name)


# The error handler: every failure answers the user.


class TestErrorHandler(unittest.IsolatedAsyncioTestCase):
    async def test_handler_cooldown_answers_before_response(self):
        cog = make_cog()
        interaction = FakeTestInteraction(response_done=False, command="claim")
        error = FakeCommandOnCooldown(FakeCooldown(1, 60.0), 42.4)
        await cog.cog_app_command_error(interaction, error)
        channel, text, kwargs = sent_text(interaction)
        self.assertEqual(channel, "response")
        self.assertEqual(text, "Slow down. Try again in 42 seconds.")
        self.assertTrue(kwargs.get("ephemeral"))

    async def test_handler_after_defer_uses_followup(self):
        cog = make_cog()
        interaction = FakeTestInteraction(response_done=True, command="kick")
        error = FakeMissingPermissions(["kick_members"])
        await cog.cog_app_command_error(interaction, error)
        interaction.response.send_message.assert_not_awaited()
        channel, text, kwargs = sent_text(interaction)
        self.assertEqual(channel, "followup")
        self.assertEqual(
            text,
            "You do not have permission to use this command. "
            "You need: kick members.",
        )
        self.assertTrue(kwargs.get("ephemeral"))

    async def test_handler_unexpected_error_logs_and_answers_generic(self):
        cog = make_cog()
        interaction = FakeTestInteraction(command="boom")
        error = FakeCommandInvokeError(cog.boom, RuntimeError("boom"))
        with self.assertLogs("slash_errors", level="ERROR") as logs:
            await cog.cog_app_command_error(interaction, error)
        self.assertTrue(
            any("Command failed" in line for line in logs.output),
            logs.output,
        )
        _channel, text, _kwargs = sent_text(interaction)
        self.assertEqual(text, "Something went wrong. The error was logged.")

    async def test_handler_forbidden_wrapped_in_invoke_error(self):
        cog = make_cog()
        interaction = FakeTestInteraction(command="kick")
        wrapped = FakeForbidden(SimpleNamespace(status=403), "Missing Access")
        error = FakeCommandInvokeError(cog.kick, wrapped)
        await cog.cog_app_command_error(interaction, error)
        _channel, text, _kwargs = sent_text(interaction)
        self.assertEqual(
            text,
            "I tried to do that, but Discord refused. "
            "I may be missing a permission.",
        )

    async def test_answer_error_swallows_expired_interaction(self):
        interaction = FakeTestInteraction(response_done=False)
        interaction.response.send_message = AsyncMock(
            side_effect=FakeHTTPException(
                SimpleNamespace(status=400), "Unknown interaction"
            )
        )
        with self.assertLogs("slash_errors", level="WARNING") as logs:
            await slash_errors.answer_error(interaction, "hi")
        self.assertTrue(
            any("Could not answer" in line for line in logs.output),
            logs.output,
        )


# Wiring: setup, sync scope, and the entry point.


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_setup_adds_the_cog(self):
        bot = SimpleNamespace(add_cog=AsyncMock())
        await slash_errors.setup(bot)
        bot.add_cog.assert_awaited_once()
        cog = bot.add_cog.await_args.args[0]
        self.assertIsInstance(cog, slash_errors.ErrorHandling)

    async def test_bot_syncs_to_test_guild_first(self):
        with patch.dict(os.environ, {"TEST_GUILD_ID": "12345"}):
            bot = slash_errors.Bot()
            await bot.setup_hook()
        self.assertEqual(len(bot.cogs), 1)
        self.assertIsInstance(bot.cogs[0], slash_errors.ErrorHandling)
        self.assertEqual(
            [guild.id for guild in bot.tree.copy_global_to_calls], [12345]
        )
        self.assertEqual(
            [guild.id for guild in bot.tree.sync_calls], [12345]
        )

    async def test_bot_syncs_globally_without_a_test_guild(self):
        with patch.dict(os.environ, {}, clear=True):
            bot = slash_errors.Bot()
            await bot.setup_hook()
        self.assertEqual(bot.tree.copy_global_to_calls, [])
        self.assertEqual(bot.tree.sync_calls, [None])

    def test_main_exits_without_a_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                slash_errors.main()

    def test_main_runs_the_bot_with_the_token(self):
        slash_errors.Bot.last_run_token = None
        with patch.dict(os.environ, {"DISCORD_TOKEN": "test-token"}):
            slash_errors.main()
        self.assertEqual(slash_errors.Bot.last_run_token, "test-token")

    def test_example_uses_the_stand_in_discord(self):
        self.assertIs(slash_errors.discord, _STUBS["discord"])
        self.assertIs(
            slash_errors.discord.Forbidden, FakeForbidden
        )


if __name__ == "__main__":
    unittest.main()
