"""Tests for the economy database layer (db.py)."""

import asyncio

import pytest

import db as db_module


@pytest.fixture
async def database(tmp_path):
    database = await db_module.connect(str(tmp_path / "test.db"))
    await db_module.init_db(database)
    yield database
    await database.close()


async def test_new_user_balance_is_zero(database):
    assert await db_module.get_balance(database, 1) == 0


async def test_credit_once_pays_only_once(database):
    lock = asyncio.Lock()
    assert await db_module.credit_once(database, lock, 1, 100, "reward", "seed:1")
    assert await db_module.credit_once(database, lock, 1, 100, "reward", "seed:1") is False
    assert await db_module.get_balance(database, 1) == 100


async def test_credit_once_rejects_non_positive_amount(database):
    lock = asyncio.Lock()
    with pytest.raises(ValueError, match="amount must be positive"):
        await db_module.credit_once(database, lock, 1, 0, "reward", "seed:0")


async def test_transfer_moves_money(database):
    lock = asyncio.Lock()
    await db_module.credit_once(database, lock, 1, 100, "reward", "seed:1")
    await db_module.transfer(database, lock, 1, 2, 40)
    assert await db_module.get_balance(database, 1) == 60
    assert await db_module.get_balance(database, 2) == 40


async def test_transfer_with_insufficient_funds_changes_nothing(database):
    lock = asyncio.Lock()
    await db_module.credit_once(database, lock, 1, 100, "reward", "seed:1")
    with pytest.raises(ValueError, match="insufficient funds"):
        await db_module.transfer(database, lock, 1, 2, 1000)
    assert await db_module.get_balance(database, 1) == 100
    assert await db_module.get_balance(database, 2) == 0


async def test_transfer_rejects_non_positive_amount(database):
    lock = asyncio.Lock()
    with pytest.raises(ValueError, match="amount must be positive"):
        await db_module.transfer(database, lock, 1, 2, -5)


async def test_ledger_records_every_transfer(database):
    lock = asyncio.Lock()
    await db_module.credit_once(database, lock, 1, 100, "reward", "seed:1")
    await db_module.transfer(database, lock, 1, 2, 25)
    cursor = await database.execute(
        "SELECT amount, kind FROM transactions WHERE user_id = ? ORDER BY id",
        (1,),
    )
    rows = await cursor.fetchall()
    assert rows == [(100, "reward"), (-25, "transfer")]
