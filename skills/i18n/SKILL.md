---
name: i18n
description: "Ship a multi-language discord.py bot: per-user locale preference, locale tables, fallback chain, and the translation pitfalls that break other languages. Use when adding languages or fixing wrong-language replies."
---

# Multi-Language Bots (i18n)

A bot that answers in the wrong language is worse than a bot that answers in English only. This skill builds locale support that is correct for every user, not just for the developer testing it.

## How Discord locales work

- Every interaction carries `interaction.locale`, the user's Discord client language (for example `id`, `en-US`, `ja`).
- discord.py resolves command names and descriptions through an `app_commands.Translator`. Subclass it, implement `translate()`, and set `bot.tree.translator`.
- Command names and descriptions can have per-locale strings. The user sees the command in their own language; the bot still receives the same command object.

## Store one preference per user

```python
# users table: user_id INTEGER PRIMARY KEY, locale TEXT NOT NULL DEFAULT 'en'
async def get_locale(db, user_id: int) -> str:
    row = await (await db.execute(
        "SELECT locale FROM users WHERE user_id = ?", (user_id,)
    )).fetchone()
    return row[0] if row else "en"
```

- One row per user, keyed by Discord user id. A `/language` command updates it. The choice survives restarts because it lives in the database, not in memory.
- Default is English. Never default to the developer's own language; the developer is not the average user.

## The fallback chain

Every string lookup follows this order, and stops at the first hit:

1. The user's chosen locale, if a translation exists for that exact key.
2. English. English is the base language and must have every key.
3. The key itself, so a missing translation shows `shop.buy.success` instead of crashing or showing nothing.

```python
STRINGS = {
    "en": {"shop.buy.success": "Bought {item} for {price} gold."},
    "id": {"shop.buy.success": "Membeli {item} seharga {price} gold."},
}

def t(locale: str, key: str, **kwargs: object) -> str:
    text = STRINGS.get(locale, {}).get(key) or STRINGS["en"].get(key) or key
    return text.format(**kwargs)
```

- The chain is code, not a hope. A lookup that raises `KeyError` on a missing translation is a bug that only appears for users of the least-tested language.
- Placeholders (`{item}`, `{price}`) are part of the key contract. Every translation of a key must contain exactly the same placeholders, or `.format()` raises at runtime.

## Rules that prevent wrong-language replies

1. **Never translate at runtime with an unvalidated machine translator.** Crowdsourced translation APIs return wrong-language results for short strings, and a bad result cached once poisons every later reply. Translate offline, review the strings, and ship a fixed table.
2. **Never translate single words without context.** "Shop" as a noun and "shop" as a verb translate differently in most languages. Keys carry the full sentence or the full UI string, never isolated words.
3. **Never guess a locale from a display name or a message.** Only `interaction.locale` and the stored per-user preference decide the reply language.
4. **Never cache by key alone.** Cache entries are keyed by `(locale, key)`. A cache keyed by key only serves the first language that asked and the wrong language to everyone after.
5. **Test every locale, not just the new one.** Adding Indonesian must not break Japanese. A test that renders one command in every supported locale catches regressions before users do.
6. **Keep placeholders intact.** A translator (human or machine) that drops `{user}` or renames it breaks the format call. Validate every translation file at load time: same placeholders as the English source, or the bot refuses to start.

## Validate translations at startup

```python
import string

def validate_table(table: dict[str, dict[str, str]]) -> list[str]:
    errors = []
    for locale, strings in table.items():
        for key, text in strings.items():
            source = table["en"].get(key)
            if source is None:
                errors.append(f"{locale}:{key} has no English source")
                continue
            want = {f for _, f, _, _ in string.Formatter().parse(source) if f}
            got = {f for _, f, _, _ in string.Formatter().parse(text) if f}
            if want != got:
                errors.append(f"{locale}:{key} placeholders differ: want {want}, got {got}")
    return errors
```

- Run this before the bot logs in. A translation bug found at startup costs a restart; the same bug found by a user costs trust.

## Translator for command names

```python
class AppTranslator(app_commands.Translator):
    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context) -> str | None:
        return STRINGS.get(locale.value, {}).get(string.message)
```

- Return `None` when no translation exists; discord.py falls back to the source string. Returning the key or an empty string is worse than falling back.

## Checklist

- [ ] Every user-facing string lives in the table, none hardcoded in commands
- [ ] Fallback chain is code: locale, then English, then the key
- [ ] Placeholders validated at startup for every locale
- [ ] Cache keyed by `(locale, key)`
- [ ] One command rendered in every locale in tests
- [ ] `/language` updates the stored preference and the next reply uses it
