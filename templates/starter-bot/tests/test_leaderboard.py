"""Tests for the leaderboard paginator, using mocked interactions."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

import db as db_module
from cogs.leaderboard import Leaderboard, PaginatorView, build_page


def make_interaction(user_id: int = 1) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.original_response = AsyncMock()
    return interaction


def make_bot(database=None) -> MagicMock:
    bot = MagicMock()
    bot.db = database
    bot.db_lock = asyncio.Lock()
    return bot


def make_pages(n: int = 3) -> list[discord.Embed]:
    return [discord.Embed(title=f"Page {i}") for i in range(n)]


def _click(view: PaginatorView, name: str) -> discord.ui.Button:
    for child in view.children:
        if isinstance(child, discord.ui.Button) and child.label == name:
            return child
    raise AssertionError(f"no button labelled {name!r}")


async def test_first_page_disables_previous():
    view = PaginatorView(author_id=1, pages=make_pages())
    assert _click(view, "Previous").disabled is True
    assert _click(view, "Next").disabled is False


async def test_next_moves_forward_and_enables_previous():
    view = PaginatorView(author_id=1, pages=make_pages())
    interaction = make_interaction(user_id=1)
    await _click(view, "Next").callback(interaction)
    assert view.current == 1
    interaction.response.edit_message.assert_awaited_once()
    kwargs = interaction.response.edit_message.await_args.kwargs
    assert kwargs["embed"].title == "Page 1"
    assert _click(view, "Previous").disabled is False


async def test_last_page_disables_next():
    view = PaginatorView(author_id=1, pages=make_pages())
    interaction = make_interaction(user_id=1)
    await _click(view, "Next").callback(interaction)
    await _click(view, "Next").callback(interaction)
    assert view.current == 2
    assert _click(view, "Next").disabled is True
    assert _click(view, "Previous").disabled is False


async def test_other_user_is_rejected_and_page_does_not_move():
    view = PaginatorView(author_id=1, pages=make_pages())
    stranger = make_interaction(user_id=99)
    allowed = await view.interaction_check(stranger)
    assert allowed is False
    assert view.current == 0
    stranger.response.send_message.assert_awaited_once()
    text = stranger.response.send_message.await_args.args[0]
    assert "Only the person who ran the command" in text


async def test_timeout_disables_buttons_and_edits_message():
    view = PaginatorView(author_id=1, pages=make_pages())
    message = AsyncMock()
    view.message = message
    await view.on_timeout()
    assert all(child.disabled for child in view.children)
    message.edit.assert_awaited_once_with(view=view)


async def test_timeout_without_message_still_disables():
    view = PaginatorView(author_id=1, pages=make_pages())
    await view.on_timeout()  # no message stored: must not raise
    assert all(child.disabled for child in view.children)


async def test_build_page_numbers_rows():
    rows = [(7, 250), (9, 100)]
    embed = build_page(rows, page_index=1, page_count=3)
    assert embed.title == "Leaderboard"
    assert embed.description == "Page 2 of 3"
    assert embed.fields[0].name == "#6"
    assert embed.fields[1].name == "#7"
    assert "250 gold" in embed.fields[0].value
    assert "—" not in embed.fields[0].value  # pack rule: no em dash in bot output


async def test_top_balances_orders_richest_first(tmp_path):
    database = await db_module.connect(str(tmp_path / "test.db"))
    await db_module.init_db(database)
    try:
        lock = asyncio.Lock()
        await db_module.credit_once(database, lock, 7, 250, "reward", "seed:7")
        await db_module.credit_once(database, lock, 9, 500, "reward", "seed:9")
        await db_module.credit_once(database, lock, 3, 100, "reward", "seed:3")
        assert await db_module.top_balances(database, limit=2) == [(9, 500), (7, 250)]
    finally:
        await database.close()


async def test_leaderboard_answers_empty_economy(tmp_path):
    database = await db_module.connect(str(tmp_path / "test.db"))
    await db_module.init_db(database)
    try:
        cog = Leaderboard(bot=make_bot(database))
        interaction = make_interaction(user_id=1)
        await cog.leaderboard.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        text = interaction.response.send_message.await_args.args[0]
        assert text == "Nobody has any gold yet."
    finally:
        await database.close()


async def test_leaderboard_sends_first_page(tmp_path):
    database = await db_module.connect(str(tmp_path / "test.db"))
    await db_module.init_db(database)
    try:
        lock = asyncio.Lock()
        for user_id, amount in [(1, 50), (2, 150), (3, 100), (4, 200), (5, 75), (6, 300)]:
            await db_module.credit_once(database, lock, user_id, amount, "reward", f"seed:{user_id}")
        cog = Leaderboard(bot=make_bot(database))
        interaction = make_interaction(user_id=1)
        message = AsyncMock()
        interaction.original_response.return_value = message
        await cog.leaderboard.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        kwargs = interaction.response.send_message.await_args.kwargs
        assert kwargs["embed"].title == "Leaderboard"
        assert kwargs["embed"].description == "Page 1 of 2"
        assert len(kwargs["embed"].fields) == 5
        assert kwargs["embed"].fields[0].name == "#1"
        assert "300 gold" in kwargs["embed"].fields[0].value
        assert isinstance(kwargs["view"], PaginatorView)
    finally:
        await database.close()
