"""Tests for the general cog commands, using mocked interactions."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

import db as db_module
from cogs.general import General


def make_interaction(user_id: int = 1) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


def make_bot(database=None) -> MagicMock:
    bot = MagicMock()
    bot.latency = 0.042
    bot.db = database
    bot.db_lock = asyncio.Lock()
    return bot


async def test_ping_answers_with_latency():
    cog = General(bot=make_bot())
    interaction = make_interaction()
    await cog.ping.callback(cog, interaction)
    interaction.response.send_message.assert_awaited_once()
    text = interaction.response.send_message.await_args.args[0]
    assert text.startswith("Pong! Latency: 42 ms")


async def test_balance_shows_zero_for_new_user(tmp_path):
    database = await db_module.connect(str(tmp_path / "test.db"))
    await db_module.init_db(database)
    try:
        cog = General(bot=make_bot(database))
        interaction = make_interaction(user_id=7)
        await cog.balance.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        text = interaction.response.send_message.await_args.args[0]
        assert text == "Your balance: 0 gold."
    finally:
        await database.close()


async def test_balance_shows_credited_amount(tmp_path):
    database = await db_module.connect(str(tmp_path / "test.db"))
    await db_module.init_db(database)
    try:
        lock = asyncio.Lock()
        await db_module.credit_once(database, lock, 7, 250, "reward", "seed:7")
        cog = General(bot=make_bot(database))
        interaction = make_interaction(user_id=7)
        await cog.balance.callback(cog, interaction)
        text = interaction.response.send_message.await_args.args[0]
        assert text == "Your balance: 250 gold."
    finally:
        await database.close()
