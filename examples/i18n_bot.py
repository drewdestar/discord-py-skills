#!/usr/bin/env python3
"""Example bot for the i18n skill: replies in Indonesian and English.

Every user-facing string lives in the STRINGS table, none hardcoded in
commands. The reply language is decided only by the stored per-user
preference (set with /language) or, when no preference is stored, by
``interaction.locale``. The lookup follows the skill's fallback chain:

1. The user's locale, for that exact key.
2. English, which must have every key.
3. The key itself, so a missing translation never crashes a reply.

Run it with::

    DISCORD_TOKEN=... python3 examples/i18n_bot.py

No network to Discord is needed for the tests:
``python3 -m unittest discover -s tests -p 'test_example_i18n_bot.py'``
from the repo root (run with a Python that has discord.py and
aiosqlite installed).
"""

import logging
import os
import string

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("i18nbot")

DEFAULT_LOCALE = "en"

# Display name per locale, in that language's own name. Used by
# /language and by the confirmation reply.
SUPPORTED_LOCALES = {
    "en": "English",
    "id": "Bahasa Indonesia",
}

# Full sentences only, never isolated words: "Shop" as a noun and as a
# verb translate differently, so keys carry the whole string. Command
# descriptions are keys here too, keyed by their English source text,
# because AppTranslator looks translations up by that source string.
STRINGS = {
    "en": {
        "greet.hello": "Hello, {user}!",
        "shop.buy.success": "Bought {item} for {price} gold.",
        "shop.buy.invalid_price": "Price must be more than 0 gold.",
        "language.set": "Language set to {language}.",
        "language.current": "Your language is {language}.",
        "language.unsupported": "That language is not supported yet.",
        "error.generic": "Something went wrong. Try again.",
        "Greet someone in this server.": "Greet someone in this server.",
        "Buy an item from the shop.": "Buy an item from the shop.",
        "The item to buy.": "The item to buy.",
        "The price in gold.": "The price in gold.",
        "Change the language the bot uses for you.": (
            "Change the language the bot uses for you."
        ),
        "The language to use.": "The language to use.",
    },
    "id": {
        "greet.hello": "Halo, {user}!",
        "shop.buy.success": "Membeli {item} seharga {price} gold.",
        "shop.buy.invalid_price": "Harga harus lebih dari 0 gold.",
        "language.set": "Bahasa diatur ke {language}.",
        "language.current": "Bahasa kamu saat ini {language}.",
        "language.unsupported": "Bahasa itu belum didukung.",
        "error.generic": "Terjadi kesalahan. Coba lagi.",
        "Greet someone in this server.": "Sapa seseorang di server ini.",
        "Buy an item from the shop.": "Beli barang dari toko.",
        "The item to buy.": "Barang yang mau dibeli.",
        "The price in gold.": "Harga dalam gold.",
        "Change the language the bot uses for you.": (
            "Ubah bahasa yang dipakai bot untuk kamu."
        ),
        "The language to use.": "Bahasa yang mau dipakai.",
    },
}

# Cache of resolved templates, keyed by (locale, key). Never by key
# alone: a key-only cache serves the first language that asked to
# everyone after. Only the template is cached; .format() still runs
# per call, so different placeholders never leak across replies.
_TEMPLATE_CACHE: dict[tuple[str, str], str] = {}


def normalize_locale(locale: str | discord.Locale | None) -> str:
    """Reduce a locale to its base language subtag, lowercased.

    ``discord.Locale`` values look like ``id`` or ``en-US``; the table
    is keyed by the base language (``id``, ``en``), so ``en-US`` and
    ``en-GB`` both become ``en``. An unknown value (``ja``) is passed
    through unchanged so ``t()`` falls back to English for it.
    """
    if locale is None:
        return DEFAULT_LOCALE
    value = locale.value if isinstance(locale, discord.Locale) else str(locale)
    return value.split("-")[0].split("_")[0].lower() or DEFAULT_LOCALE


def t(locale: str | discord.Locale | None, key: str, **kwargs: object) -> str:
    """Translate ``key`` following the fallback chain.

    The user's locale first, then English, then the key itself.
    Placeholders are part of the key contract: every translation of a
    key carries exactly the same placeholders (enforced at startup by
    ``validate_table``), so ``.format()`` cannot fail on a shipped key.
    """
    lang = normalize_locale(locale)
    cache_key = (lang, key)
    template = _TEMPLATE_CACHE.get(cache_key)
    if template is None:
        template = (
            STRINGS.get(lang, {}).get(key)
            or STRINGS["en"].get(key)
            or key
        )
        _TEMPLATE_CACHE[cache_key] = template
    return template.format(**kwargs)


def validate_table(table: dict[str, dict[str, str]]) -> list[str]:
    """Check every translation against its English source.

    Returns a list of problems; an empty list means the table is safe
    to ship. A translation is a problem when its key has no English
    source, or when its placeholders differ from the English source.
    Run before the bot logs in: a bug found at startup costs a
    restart, the same bug found by a user costs trust.
    """
    errors: list[str] = []
    if DEFAULT_LOCALE not in table:
        return ["table has no English ('en') source"]
    for locale, strings in table.items():
        for key, text in strings.items():
            source = table["en"].get(key)
            if source is None:
                errors.append(f"{locale}:{key} has no English source")
                continue
            want = {f for _, f, _, _ in string.Formatter().parse(source) if f}
            got = {f for _, f, _, _ in string.Formatter().parse(text) if f}
            if want != got:
                errors.append(
                    f"{locale}:{key} placeholders differ: "
                    f"want {want}, got {got}"
                )
    return errors


async def init_db(db: aiosqlite.Connection) -> None:
    """Create the per-user locale table. One row per user."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "user_id INTEGER PRIMARY KEY, "
        "locale TEXT NOT NULL DEFAULT 'en'"
        ")"
    )
    await db.commit()


async def _get_stored_locale(
    db: aiosqlite.Connection, user_id: int
) -> str | None:
    """Return the stored locale, or None when the user has no row."""
    row = await (await db.execute(
        "SELECT locale FROM users WHERE user_id = ?", (user_id,)
    )).fetchone()
    return row[0] if row else None


async def get_locale(db: aiosqlite.Connection, user_id: int) -> str:
    """Return the stored locale for a user, or 'en' when none is stored."""
    stored = await _get_stored_locale(db, user_id)
    return stored if stored is not None else DEFAULT_LOCALE


async def set_locale(db: aiosqlite.Connection, user_id: int, locale: str) -> None:
    """Store a user's locale choice. Only supported locales are stored."""
    if locale not in SUPPORTED_LOCALES:
        raise ValueError(f"unsupported locale: {locale!r}")
    await db.execute(
        "INSERT INTO users (user_id, locale) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET locale = excluded.locale",
        (user_id, locale),
    )
    await db.commit()


async def resolve_locale(
    interaction: discord.Interaction, db: aiosqlite.Connection | None
) -> str:
    """Decide the reply language for one interaction.

    The stored per-user preference wins when it exists. Otherwise the
    Discord client language (``interaction.locale``) decides. Nothing
    else guesses: never a display name, never a message. An explicit
    stored choice of English still wins over an Indonesian client:
    the row existing is what matters, not the value in it.
    """
    if db is not None:
        stored = await _get_stored_locale(db, interaction.user.id)
        if stored is not None:
            return stored
    return normalize_locale(interaction.locale)


class AppTranslator(app_commands.Translator):
    """Translate command names and descriptions for the tree.

    Returns ``None`` when no translation exists; discord.py then falls
    back to the source string. Returning the key or an empty string
    would be worse than falling back.
    """

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context,
    ) -> str | None:
        return STRINGS.get(normalize_locale(locale), {}).get(string.message)


class I18nCog(commands.Cog):
    """Slash commands that answer in the caller's language."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="greet", description="Greet someone in this server."
    )
    async def greet(self, interaction: discord.Interaction) -> None:
        locale = await resolve_locale(interaction, self.bot.db)
        await interaction.response.send_message(
            t(locale, "greet.hello", user=interaction.user.mention)
        )

    @app_commands.command(name="buy", description="Buy an item from the shop.")
    @app_commands.describe(
        item="The item to buy.",
        price="The price in gold.",
    )
    async def buy(
        self, interaction: discord.Interaction, item: str, price: int
    ) -> None:
        locale = await resolve_locale(interaction, self.bot.db)
        if price <= 0:
            await interaction.response.send_message(
                t(locale, "shop.buy.invalid_price"), ephemeral=True
            )
            return
        await interaction.response.send_message(
            t(locale, "shop.buy.success", item=item, price=price)
        )

    @app_commands.command(
        name="language",
        description="Change the language the bot uses for you.",
    )
    @app_commands.describe(locale="The language to use.")
    @app_commands.choices(
        locale=[
            app_commands.Choice(name="Bahasa Indonesia", value="id"),
            app_commands.Choice(name="English", value="en"),
        ]
    )
    async def language(
        self, interaction: discord.Interaction, locale: str
    ) -> None:
        # The choice list only offers supported locales, but the
        # callback still validates: a crafted call must not store junk.
        if locale not in SUPPORTED_LOCALES:
            current = await resolve_locale(interaction, self.bot.db)
            await interaction.response.send_message(
                t(current, "language.unsupported"), ephemeral=True
            )
            return
        await set_locale(self.bot.db, interaction.user.id, locale)
        # Confirm in the NEW language: the reply itself proves the
        # switch took effect.
        await interaction.response.send_message(
            t(locale, "language.set", language=SUPPORTED_LOCALES[locale])
        )


class I18nBot(commands.Bot):
    """Slash-command bot with a per-user locale stored in SQLite."""

    def __init__(self, db_path: str = "i18n_bot.db") -> None:
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def setup_hook(self) -> None:
        self.db = await aiosqlite.connect(self.db_path)
        await init_db(self.db)
        self.tree.translator = AppTranslator()
        await self.add_cog(I18nCog(self))
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
        log.info("%s is online", self.user)

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None
        await super().close()


bot = I18nBot()


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    log.warning("Command failed: %s", error)
    db = getattr(bot, "db", None)
    try:
        locale = await resolve_locale(interaction, db)
    except Exception:  # noqa: BLE001 - error path must still answer
        locale = normalize_locale(getattr(interaction, "locale", None))
    message = t(locale, "error.generic")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        log.warning("Could not answer the failed command.")


def main() -> None:
    errors = validate_table(STRINGS)
    if errors:
        raise SystemExit(
            "Refusing to start with broken translations:\n"
            + "\n".join(f"  - {error}" for error in errors)
        )
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("set the DISCORD_TOKEN environment variable")
    bot.run(token)


if __name__ == "__main__":
    main()
