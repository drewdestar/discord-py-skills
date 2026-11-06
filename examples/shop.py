"""Example: economy plus shop commands for a discord.py bot.

Showcases skills/economy-database/SKILL.md: WAL mode, one writer
(one connection plus one asyncio.Lock), a ledger table as the source
of truth, atomic purchases, and idempotency keys on every credit.

Run it with:
    DISCORD_TOKEN=... python examples/shop.py
The token comes from the environment only, never from source.
Set TEST_GUILD_ID to sync commands to one test guild while building;
without it the bot syncs globally, which can take up to an hour.
"""

import asyncio
import logging
import os

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("shopbot")

# The shop catalog. Prices and stock live in the database after
# init_db seeds them; this tuple is only the seed data, and every
# price the bot shows comes from a database query, never from here.
SHOP_ITEMS = (
    ("snack", "Trail Snack", 10, 200),
    ("potion", "Healing Potion", 50, 100),
    ("shield", "Wooden Shield", 150, 25),
    ("sword", "Iron Sword", 250, 10),
    ("cape", "Lucky Cape", 500, 5),
)

MAX_QUANTITY = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    idem_key    TEXT UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

CREATE TABLE IF NOT EXISTS items (
    item_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    price       INTEGER NOT NULL CHECK (price > 0),
    stock       INTEGER NOT NULL CHECK (stock >= 0)
);

CREATE TABLE IF NOT EXISTS inventory (
    user_id     INTEGER NOT NULL,
    item_id     TEXT NOT NULL,
    quantity    INTEGER NOT NULL CHECK (quantity >= 0),
    PRIMARY KEY (user_id, item_id),
    FOREIGN KEY (user_id) REFERENCES users (user_id),
    FOREIGN KEY (item_id) REFERENCES items (item_id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_user
    ON transactions (user_id, created_at);
"""


async def connect(path: str) -> aiosqlite.Connection:
    """Open the economy database with the skill's pragmas.

    WAL mode is the single most important setting: readers do not
    block the writer. busy_timeout turns a collision into a short
    wait instead of an immediate error.
    """
    db = await aiosqlite.connect(path)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA synchronous=NORMAL")
    return db


async def init_db(db: aiosqlite.Connection) -> None:
    """Create the tables and seed the shop catalog (once)."""
    await db.executescript(SCHEMA)
    await db.executemany(
        "INSERT OR IGNORE INTO items (item_id, name, price, stock) "
        "VALUES (?, ?, ?, ?)",
        SHOP_ITEMS,
    )
    await db.commit()


async def get_balance(db: aiosqlite.Connection, user_id: int) -> int:
    cursor = await db.execute(
        "SELECT balance FROM users WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    return row[0] if row else 0


async def list_items(db: aiosqlite.Connection) -> list[tuple[str, str, int, int]]:
    """Shop catalog from the database: (item_id, name, price, stock)."""
    cursor = await db.execute(
        "SELECT item_id, name, price, stock FROM items ORDER BY price ASC"
    )
    return [(row[0], row[1], row[2], row[3]) async for row in cursor]


async def get_inventory(
    db: aiosqlite.Connection, user_id: int
) -> list[tuple[str, str, int]]:
    """Items a user owns: (item_id, name, quantity)."""
    cursor = await db.execute(
        "SELECT i.item_id, it.name, i.quantity FROM inventory i "
        "JOIN items it ON it.item_id = i.item_id "
        "WHERE i.user_id = ? ORDER BY it.name ASC",
        (user_id,),
    )
    return [(row[0], row[1], row[2]) async for row in cursor]


async def credit_once(
    db: aiosqlite.Connection,
    lock: asyncio.Lock,
    user_id: int,
    amount: int,
    kind: str,
    idem_key: str,
) -> bool:
    """Credit amount once. True if credited, False if the key was used.

    The UNIQUE constraint on transactions.idem_key is what makes this
    safe under concurrency; application-level check-then-insert is not.
    """
    if amount <= 0:
        raise ValueError("amount must be positive")
    async with lock:
        await db.execute("BEGIN IMMEDIATE")
        try:
            # User row first: transactions has a foreign key on user_id.
            await db.execute(
                "INSERT INTO users (user_id, balance) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
                (user_id, amount, amount),
            )
            await db.execute(
                "INSERT INTO transactions (user_id, amount, kind, idem_key) "
                "VALUES (?, ?, ?, ?)",
                (user_id, amount, kind, idem_key),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            await db.rollback()
            return False
    return True


def _validate_quantity(quantity: int) -> None:
    if quantity < 1 or quantity > MAX_QUANTITY:
        raise ValueError("quantity must be between 1 and 10")


def _receipt(
    item_id: str,
    name: str,
    quantity: int,
    total_price: int,
    balance_after: int,
    already_purchased: bool,
) -> dict:
    return {
        "item_id": item_id,
        "name": name,
        "quantity": quantity,
        "total_price": total_price,
        "balance_after": balance_after,
        "already_purchased": already_purchased,
    }


async def buy_item(
    db: aiosqlite.Connection,
    lock: asyncio.Lock,
    user_id: int,
    item_id: str,
    quantity: int = 1,
    idem_key: str | None = None,
) -> dict:
    """Buy quantity of an item, atomically.

    One transaction checks the stock and the balance, debits the
    buyer, decrements the stock, adds the inventory row, and writes
    the ledger row. Any failure rolls everything back, so a failed
    purchase changes nothing. Replaying the same idem_key returns
    the original receipt without charging again.
    """
    _validate_quantity(quantity)
    async with lock:
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                "SELECT name, price, stock FROM items WHERE item_id = ?",
                (item_id,),
            )
            item = await cursor.fetchone()
            if item is None:
                raise ValueError("unknown item")
            name, price, stock = item
            total = price * quantity
            if stock < quantity:
                raise ValueError("not enough stock")
            if idem_key is not None:
                cursor = await db.execute(
                    "SELECT amount FROM transactions WHERE idem_key = ?",
                    (idem_key,),
                )
                row = await cursor.fetchone()
                if row is not None:
                    balance = await get_balance(db, user_id)
                    await db.commit()
                    return _receipt(
                        item_id, name, quantity, -row[0], balance, True
                    )
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            balance = row[0] if row else 0
            if balance < total:
                raise ValueError("insufficient funds")
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                (user_id,),
            )
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (total, user_id),
            )
            await db.execute(
                "UPDATE items SET stock = stock - ? WHERE item_id = ?",
                (quantity, item_id),
            )
            await db.execute(
                "INSERT INTO inventory (user_id, item_id, quantity) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, item_id) "
                "DO UPDATE SET quantity = quantity + ?",
                (user_id, item_id, quantity, quantity),
            )
            await db.execute(
                "INSERT INTO transactions (user_id, amount, kind, idem_key) "
                "VALUES (?, ?, 'purchase', ?)",
                (user_id, -total, idem_key),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return _receipt(item_id, name, quantity, total, balance - total, False)


def sell_unit_price(price: int) -> int:
    """What the shop pays for one item: half its price, rounded down."""
    return price // 2


async def sell_item(
    db: aiosqlite.Connection,
    lock: asyncio.Lock,
    user_id: int,
    item_id: str,
    quantity: int = 1,
    idem_key: str | None = None,
) -> dict:
    """Sell quantity of an owned item back to the shop, atomically.

    Same guarantees as buy_item: one transaction checks ownership,
    credits the seller at half price, returns the stock, removes the
    inventory row, and writes the ledger row. Replaying the same
    idem_key credits nothing the second time.
    """
    _validate_quantity(quantity)
    async with lock:
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                "SELECT name, price, stock FROM items WHERE item_id = ?",
                (item_id,),
            )
            item = await cursor.fetchone()
            if item is None:
                raise ValueError("unknown item")
            name, price, stock = item
            unit_price = sell_unit_price(price)
            total = unit_price * quantity
            if idem_key is not None:
                cursor = await db.execute(
                    "SELECT amount FROM transactions WHERE idem_key = ?",
                    (idem_key,),
                )
                row = await cursor.fetchone()
                if row is not None:
                    balance = await get_balance(db, user_id)
                    await db.commit()
                    return _receipt(
                        item_id, name, quantity, row[0], balance, True
                    )
            cursor = await db.execute(
                "SELECT quantity FROM inventory "
                "WHERE user_id = ? AND item_id = ?",
                (user_id, item_id),
            )
            row = await cursor.fetchone()
            owned = row[0] if row else 0
            if owned < quantity:
                raise ValueError("you do not own that many")
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            balance = row[0] if row else 0
            await db.execute(
                "INSERT INTO users (user_id, balance) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
                (user_id, total, total),
            )
            await db.execute(
                "UPDATE items SET stock = stock + ? WHERE item_id = ?",
                (quantity, item_id),
            )
            if owned == quantity:
                await db.execute(
                    "DELETE FROM inventory WHERE user_id = ? AND item_id = ?",
                    (user_id, item_id),
                )
            else:
                await db.execute(
                    "UPDATE inventory SET quantity = quantity - ? "
                    "WHERE user_id = ? AND item_id = ?",
                    (quantity, user_id, item_id),
                )
            await db.execute(
                "INSERT INTO transactions (user_id, amount, kind, idem_key) "
                "VALUES (?, ?, 'sale', ?)",
                (user_id, total, idem_key),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return _receipt(item_id, name, quantity, total, balance + total, False)


def format_shop_list(items: list[tuple[str, str, int, int]]) -> str:
    """Pure formatting for /shop list, so tests need no Discord."""
    lines = ["Shop:"]
    for item_id, name, price, stock in items:
        lines.append(f"- {name} ({item_id}): {price} gold, {stock} in stock")
    return "\n".join(lines)


def format_inventory(
    items: list[tuple[str, str, int]], balance: int
) -> str:
    """Pure formatting for /shop inventory, so tests need no Discord."""
    if not items:
        return f"Your bag is empty. Balance: {balance} gold."
    lines = ["Your bag:"]
    for item_id, name, quantity in items:
        lines.append(f"- {quantity} x {name} ({item_id})")
    lines.append(f"Balance: {balance} gold.")
    return "\n".join(lines)


async def _handle_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    """Answer every command error instead of failing silently."""
    if isinstance(error, app_commands.CommandOnCooldown):
        text = f"Slow down. Try again in {error.retry_after:.0f} seconds."
    elif isinstance(error, app_commands.CheckFailure):
        text = "You cannot use this command here."
    else:
        log.exception("Command failed: %s", interaction.command)
        text = "Something went wrong. The error was logged."
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


class Shop(commands.GroupCog, group_name="shop", group_description="Buy and sell items."):
    """Shop commands: /shop list, /shop buy, /shop sell, /shop inventory."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def item_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest shop items by name or id, at most 25 choices."""
        items = await list_items(self.bot.db)
        needle = current.strip().lower()
        choices = [
            app_commands.Choice(name=name, value=item_id)
            for item_id, name, price, stock in items
            if not needle or needle in name.lower() or needle in item_id
        ]
        return choices[:25]

    @app_commands.command(name="list", description="List the items for sale.")
    async def list_items_command(
        self, interaction: discord.Interaction
    ) -> None:
        items = await list_items(self.bot.db)
        await interaction.response.send_message(format_shop_list(items))

    @app_commands.command(name="buy", description="Buy an item from the shop.")
    @app_commands.autocomplete(item=item_autocomplete)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def buy(
        self,
        interaction: discord.Interaction,
        item: str,
        quantity: app_commands.Range[int, 1, 10] = 1,
    ) -> None:
        # The interaction id makes the purchase idempotent: if Discord
        # delivers the same interaction twice, the second run replays
        # the receipt instead of charging again. A new /buy gets a
        # new interaction id, so buying the same item twice still works.
        idem_key = (
            f"purchase:{interaction.user.id}:{item}:{quantity}"
            f":{interaction.id}"
        )
        try:
            receipt = await buy_item(
                self.bot.db,
                self.bot.db_lock,
                interaction.user.id,
                item,
                quantity,
                idem_key,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        if receipt["already_purchased"]:
            text = (
                f"Already bought: {receipt['quantity']} x {receipt['name']} "
                f"for {receipt['total_price']} gold. "
                f"Balance: {receipt['balance_after']} gold."
            )
        else:
            text = (
                f"You bought {receipt['quantity']} x {receipt['name']} "
                f"for {receipt['total_price']} gold. "
                f"Balance: {receipt['balance_after']} gold."
            )
        await interaction.response.send_message(text)

    @app_commands.command(name="sell", description="Sell an item back to the shop.")
    @app_commands.autocomplete(item=item_autocomplete)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def sell(
        self,
        interaction: discord.Interaction,
        item: str,
        quantity: app_commands.Range[int, 1, 10] = 1,
    ) -> None:
        idem_key = (
            f"sale:{interaction.user.id}:{item}:{quantity}"
            f":{interaction.id}"
        )
        try:
            receipt = await sell_item(
                self.bot.db,
                self.bot.db_lock,
                interaction.user.id,
                item,
                quantity,
                idem_key,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        if receipt["already_purchased"]:
            text = (
                f"Already sold: {receipt['quantity']} x {receipt['name']} "
                f"for {receipt['total_price']} gold. "
                f"Balance: {receipt['balance_after']} gold."
            )
        else:
            text = (
                f"You sold {receipt['quantity']} x {receipt['name']} "
                f"for {receipt['total_price']} gold. "
                f"Balance: {receipt['balance_after']} gold."
            )
        await interaction.response.send_message(text)

    @app_commands.command(name="inventory", description="Show the items you own.")
    async def inventory(
        self, interaction: discord.Interaction
    ) -> None:
        items = await get_inventory(self.bot.db, interaction.user.id)
        balance = await get_balance(self.bot.db, interaction.user.id)
        await interaction.response.send_message(
            format_inventory(items, balance)
        )

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        await _handle_command_error(interaction, error)


class Wallet(commands.Cog):
    """Wallet command: /balance."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="balance", description="Show your gold balance.")
    async def balance(self, interaction: discord.Interaction) -> None:
        amount = await get_balance(self.bot.db, interaction.user.id)
        await interaction.response.send_message(
            f"Your balance: {amount} gold."
        )

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        await _handle_command_error(interaction, error)


class ShopBot(commands.Bot):
    """Bot that owns the one economy connection and its lock."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.db: aiosqlite.Connection | None = None
        self.db_lock = asyncio.Lock()

    async def setup_hook(self) -> None:
        self.db = await connect(
            os.environ.get("SHOP_DB_PATH", "shop.db")
        )
        await init_db(self.db)
        await setup(self)
        log.info("Shop cog loaded.")
        test_guild_id = os.environ.get("TEST_GUILD_ID")
        if test_guild_id:
            guild = discord.Object(id=int(test_guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Commands synced to test guild %s.", test_guild_id)
        else:
            await self.tree.sync()
            log.info("Commands synced globally.")

    async def on_ready(self) -> None:
        log.info("Logged in as %s (%s).", self.user, self.user.id)

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
        await super().close()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Shop(bot))
    await bot.add_cog(Wallet(bot))


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("set the DISCORD_TOKEN environment variable")
    ShopBot().run(token)


if __name__ == "__main__":
    main()
