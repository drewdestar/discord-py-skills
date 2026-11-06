---
name: testing
description: "Test a discord.py bot: unit tests for pure logic, mocked interactions for commands, and async tests with pytest-asyncio. Use when the user says 'write tests for the bot', 'the test passes but the bot is broken', or before changing anything that touches balances or permissions. Do NOT use for manual live checks alone; live verification is separate from the test suite."
license: MIT
compatibility: "discord.py 2.x, Python 3.10+, no paid services"
metadata:
  version: "0.5.0"
  author: "drewdestar"
---

# Testing Discord Bots

Tests for a bot verify behavior through public interfaces, not by hitting the real Discord API. A test suite that needs a live bot token is a test suite that never runs in CI.

## What to test, and where

| Layer | What it catches | How |
|---|---|---|
| Pure logic | Economy math, cooldown rules, parsing, formatting | Plain pytest functions, no Discord objects |
| Database | Atomic transfers, idempotency, migrations | aiosqlite against a temporary file or `:memory:` |
| Commands | The command answers, defers, or errors correctly | Call the command callback with a mocked interaction |
| Wiring | Cogs load, commands register, config validates | Import the cog module, load the extension in a test bot |

Test only at these seams. Do not mock the internals of a function to test that function; if the test needs to reach inside, the seam is wrong.

## Test setup

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
```

For a plain `pytest.ini` the same settings use INI syntax instead
(`[pytest]` header, `asyncio_mode = auto` with no quotes). Do not
paste the TOML block into a `.ini` file: pytest will ignore it and
async tests will fail as unsupported.

```txt
# requirements-dev.txt
pytest==9.2.0
pytest-asyncio==1.4.1.post1
discord.py>=2.7.1
aiosqlite==0.22.1
```

- `asyncio_mode = "auto"` makes every `async def test_` function run without a decorator. One less thing to forget.
- Tests import the bot package from the project root. A `tests/conftest.py` that inserts the project root into `sys.path` keeps imports working from any directory.

## Pure logic first

```python
import pytest


def validate_transfer_amount(amount: int) -> None:
    if amount <= 0:
        raise ValueError("amount must be positive")

def test_transfer_rejects_zero_amount():
    with pytest.raises(ValueError):
        validate_transfer_amount(0)
```

- `validate_transfer_amount` is the same rule the economy skill's `transfer` enforces; the test pins the rule, not the implementation. Pure functions (validation, formatting, cooldown math) are the cheapest tests in the codebase and the most valuable: they never need a mock and they never flake.
- Expected values come from the spec or a worked example, never by recomputing the value the way the code does. A test that asserts `add(a, b) == a + b` passes by construction and can never catch a bug.

## Database tests

Database tests: a fresh database per test, the transfer test, and the failure case. See `references/database-tests.md`.

## Mocking an interaction

Mocking an interaction: the ping sample, the cooldown test, and what `.callback()` bypasses. See `references/mocking-interaction.md`.

## Wiring: cogs load

A command test proves the callback works; it does not prove the
cog loads. A wiring test loads the extension in a test bot
through `setup_hook`, exactly as the starter's `bot.py:31-35`
does:

```python
import discord
from discord.ext import commands


class TestBot(commands.Bot):
    async def setup_hook(self) -> None:
        await self.load_extension("cogs.general")


async def test_cogs_load():
    bot = TestBot(command_prefix="!", intents=discord.Intents.default())
    await bot.setup_hook()
    assert bot.get_cog("General") is not None
    await bot.close()
```

No token, no login, no network — `setup_hook` runs the same
`load_extension` calls the real bot runs at startup, so a cog
that fails to import or register fails here first.

## Tests must be able to fail

Tests must be able to fail: the red check, and the vacuous-assertion trap. See `references/tests-must-fail.md`.

## What not to test

- Do not call the real Discord API in tests. No live token, no test server, no network. A test that needs the network is flaky by definition.
- Do not test discord.py itself. If `app_commands.command` registers a command, that is the library's job to verify.
- Do not snapshot entire embeds. Assert the fields that matter (title, one value), not a byte-for-byte dump that breaks on every wording change.

## Red, green, refactor

1. Write one failing test for one behavior.
2. Write the smallest code that makes it pass.
3. Run the full suite. Everything green before the next test.

One test, one behavior, one cycle. Writing ten tests first and then the implementation tests imagined behavior, and the tests go insensitive to real changes.

## CI

```yaml
# .github/workflows/test.yml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt pytest pytest-asyncio
      - run: python -m pytest -q
```

- CI runs on every push and every pull request. A test suite that only runs on the developer's machine is a suggestion, not a gate.
- Install the test tools explicitly (`pytest pytest-asyncio`). Do not install a `requirements-dev.txt` the project does not have — the install step fails on a file that does not exist. If the project does have one, install that instead.
- Pin action majors to the latest at the time of writing (v7 for both checkout and setup-python, checked 2026-11-06). Re-check before copying: a stale major is a silent downgrade.

## Verify live

A green suite is not proof the bot works. Tests use mocks; Discord
does not. After the suite passes:

1. Run the bot against the test guild.
2. Invoke every command the suite covers, once, in Discord.
3. Trigger one error path in Discord (for example, a command the
   user has no permission for, or an interaction that times out).
   It must answer with the error message, not silence.
4. Restart the bot. Balances and data survive the restart.

Report the observed reply for each command. "Tests pass" is a
statement about the suite, not about the bot.

## Quality bar (no slop)

- **Evidence over claims.** Never report "all tests pass" without
  running them. Quote the actual output (`pytest -q`, the count,
  the failures). A number you did not measure is invented.
- **No em dash** in any message, embed, or reply the bot sends.
- **No fabricated coverage.** Do not claim a percentage of coverage
  or a number of cases unless the tool printed it.
- **Every check has a reason.** A test exists because a real failure
  mode exists. If you cannot name the failure in one line, delete
  the test.

## Checklist

- [ ] Pure logic has plain pytest tests with independent expected values
- [ ] Database tests use a fresh temp database per test
- [ ] Commands are tested through the callback with a mocked interaction
- [ ] Assertions check what the user sees, not internal calls
- [ ] No test touches the network or a real token
- [ ] `pytest -q` passes locally and in CI
